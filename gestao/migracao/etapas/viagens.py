"""Etapa 2 — viagens: viagens (destinos, tipos, anexos), roteiros (trechos), numeração, ofícios
(justificativa, equipe, trechos, histórico), termos, ordens de serviço, planos de trabalho,
documentos emitidos, vias assinadas, textos editados e o cache de distâncias.

Regras (docs da migração, 02-viagens):

* EV é a base; o GV só entra com o que não está no `migracao_legado_registro` do EV. Uma
  linha do GV que o EV trouxe é comparada pela impressão digital: mudou só no GV → a versão do
  GV entra; mudou nos dois → vale a edição mais recente e a outra vai para a conferência.
  O agregado (documento + filhos) entra inteiro do lado que venceu.
* Apagado no EV depois da carga não é recriado pelo GV.
* Ofícios 127/2026 e 128/2026 do GV (documentos diferentes dos nativos do EV com o mesmo
  número): entram com o próximo número livre do ano; o número antigo fica no histórico.
* Arquivos: só a referência (`legado/<ev|gv>/<xx>/<sha256>.<ext>`, ver `comum`), com hash e
  tamanho do backup.
* Nada de dado pessoal na conferência: só ids, tabelas, campos e motivos.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Max

from gestao.cadastros.validacoes import normalizar_placa, somente_digitos
from gestao.viagens.models import (
    AnexoViagem,
    DistanciaMunicipios,
    Documento,
    EdicaoDocumento,
    EdicaoOrdem,
    EdicaoPlano,
    EfetivoEvento,
    EfetivoPlano,
    EventoDestino,
    EventoPlano,
    FuncaoOS,
    Historico,
    ModeloOS,
    NumeracaoAnual,
    NumeracaoOrdemServico,
    NumeracaoPlano,
    Oficio,
    OrdemServico,
    OrdemServicoDestino,
    PlanoDestino,
    PlanoTrabalho,
    ResultadoAtividade,
    Roteiro,
    TermoAutorizacao,
    TermoDestino,
    TermoViatura,
    Trecho,
    TrechoRoteiro,
    Viagem,
    ViagemDestino,
    Viajante,
)

from ..contexto import Contexto
from .comum import (
    Agregado,
    Carga,
    agrupar,
    arquivo,
    aware,
    configuracao,
    criar_filhos,
    data_local,
    datas,
    depois_da_carga,
    executar_carga,
    fk,
    inserir_via,
    inverso,
    json_legado,
    municipio_por_nome,
    pais_alterados_no_gv,
    por_id,
    preservar_datas,
    registro,
    tab,
    texto,
    usuario,
)

# Tabelas de origem: (EV, GV).
TV: dict[str, tuple[str, str | None]] = {
    "viagem": ("viagens_viagem_viagem", "eventos_evento"),
    "viagem_tipos": ("viagens_viagem_viagem_tipos", "eventos_evento_tipos"),
    "anexo_viagem": ("viagens_viagem_viagemdocumentosolicitacao",
                     "eventos_eventodocumentosolicitacao"),
    "roteiro": ("viagens_roteiros_roteiro", "roteiros_roteiro"),
    "trecho": ("viagens_roteiros_roteirotrecho", "roteiros_roteirotrecho"),
    "componente": ("viagens_roteiros_roteirodiariacomponente",
                   "roteiros_roteirodiariacomponente"),
    "oficio": ("viagens_oficios_oficio", "oficios_oficio"),
    "oficio_servidores": ("viagens_oficios_oficio_servidores", "oficios_oficio_servidores"),
    "justificativa": ("viagens_oficios_justificativa", "justificativas_justificativa"),
    "numeracao": ("viagens_oficios_configuracaonumeracaooficio",
                  "oficios_configuracaonumeracaooficio"),
    "termo": ("viagens_termos_termoautorizacao", "termos_termoautorizacao"),
    "termo_servidores": ("viagens_termos_termoautorizacao_servidores",
                         "termos_termoautorizacao_servidores"),
    "os": ("viagens_ordens_ordemservico", "ordens_servico_ordemservico"),
    "os_destinos": ("viagens_ordens_ordemservico_destinos",
                    "ordens_servico_ordemservico_destinos"),
    "os_oficios": ("viagens_ordens_ordemservico_oficios", "ordens_servico_ordemservico_oficios"),
    "os_servidores": ("viagens_ordens_ordemservico_servidores",
                      "ordens_servico_ordemservico_servidores"),
    "plano": ("viagens_planos_planotrabalho", "planos_trabalho_planotrabalho"),
    "plano_destino": ("viagens_planos_planodestino", "planos_trabalho_planodestino"),
    "efetivo_plano": ("viagens_planos_efetivoplano", "planos_trabalho_efetivoplano"),
    "evento_plano": ("viagens_planos_eventoplano", "planos_trabalho_eventoplano"),
    "efetivo_evento": ("viagens_planos_efetivoevento", "planos_trabalho_efetivoevento"),
    "plano_atividades": ("viagens_planos_planotrabalho_atividades_selecionadas",
                         "planos_trabalho_planotrabalho_atividades_selecionadas"),
    "evento_atividades": ("viagens_planos_eventoplano_atividades_selecionadas",
                          "planos_trabalho_eventoplano_atividades_selecionadas"),
    "resultado": ("viagens_planos_resultadoatividade", None),
    "artefato": ("documentos_documentoartefato", "documentos_documentoartefato"),
    "assinatura_versao": ("documentos_documentoassinaturaversao",
                          "documentos_documentoassinaturaversao"),
    "versao_editada": ("documentos_documentoversaoeditada", None),
    "distancia": ("viagens_roteiros_distanciamunicipios", None),
    "prestacao": ("viagens_prestacoes_prestacaocontas", "prestacoes_contas_prestacaocontas"),
    "solicitacoes_juntadas": ("viagens_viagem_viagem_solicitacoes_juntadas", None),
    "equipe_prevista": ("viagens_viagem_equipeprevista", None),
}


def t(nome: str, sistema: str) -> str:
    par = TV[nome]
    alvo = par[0] if sistema == "ev" else par[1]
    return alvo or ""


def c_viagem(sistema: str) -> str:
    return "viagem_id" if sistema == "ev" else "evento_id"


def _par(ctx: Contexto, nome: str, sistema: str, pk: Any) -> tuple[str | None, str | None]:
    """(pk no EV, pk no GV) da mesma linha nos dois sistemas."""
    tg = TV[nome][1]
    if sistema == "ev":
        return str(pk), (inverso(ctx, tg).get(str(pk)) if tg else None)
    reg = registro(ctx, tg or "").get(str(pk))
    return (reg[0] if reg else None), str(pk)


def _linha_ev(ctx: Contexto, nome: str, sistema: str, linha: dict) -> dict | None:
    """A linha do EV que corresponde a esta (ela mesma, se já é do EV)."""
    if sistema == "ev":
        return linha
    ev_pk, _ = _par(ctx, nome, sistema, linha["id"])
    return por_id(ctx, "ev", t(nome, "ev")).get(ev_pk) if ev_pk else None


def _jsonavel(v: Any) -> Any:
    if isinstance(v, Decimal):
        return str(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _km(v: Any) -> Decimal | None:
    if v is None:
        return None
    return Decimal(str(v)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _min(v: Any) -> int | None:
    return int(v) if v is not None and int(v) >= 0 else None


def _ids(ctx: Contexto, sistema: str, entidade: str, pks: list[Any], notas: list[str],
         campo: str) -> list[int]:
    vistos: list[int] = []
    for pk in pks:
        alvo = fk(ctx, sistema, entidade, pk, notas, campo)
        if alvo is not None and alvo not in vistos:
            vistos.append(alvo)
    return vistos


def _m2m(ctx: Contexto, nome: str, sistema: str, dono_col: str, dono_pk: Any,
         alvo_col: str) -> list[Any]:
    """Os ids do outro lado de uma tabela M2M do legado, na ordem do id da linha."""
    return [r[alvo_col] for r in agrupar(ctx, sistema, t(nome, sistema), dono_col)
            .get(str(dono_pk), [])]


def _destino_viagem(ctx: Contexto, nome: str, sistema: str, pk: Any) -> int | None:
    """FK para um documento já migrado nesta etapa (viagem, roteiro, ofício…)."""
    if pk is None:
        return None
    return ctx.destino_int(sistema, t(nome, sistema), pk)


# ============================================================================ viagens
SITUACAO_VIAGEM = {"rascunho": "rascunho", "em_preparacao": "preparacao",
                   "documentos_gerados": "gerados", "cancelado": "cancelada"}


def _construir_viagem(ctx: Contexto, sistema: str, r: dict) -> Agregado:
    notas: list[str] = []
    conf = configuracao(ctx)
    unidade = fk(ctx, sistema, "unidade", r.get("unidade_responsavel_id"), notas, "unidade")
    status = (r.get("status") or "").strip().lower()
    cancelada = bool(r.get("cancelado")) or status == "cancelado"
    situacao = "cancelada" if cancelada else SITUACAO_VIAGEM.get(status, "rascunho")
    if status and status not in SITUACAO_VIAGEM:
        notas.append(f"situação de viagem desconhecida ({status}): ficou rascunho")
    motivo_canc = texto(r.get("motivo_cancelamento"))
    if len(motivo_canc) > 1000:
        notas.append("motivo do cancelamento com mais de 1000 caracteres: truncado")
    destinos: list[int] = []
    if sistema == "ev":
        principal = fk(ctx, sistema, "municipio", r.get("destino_municipio_id"), notas, "destino")
    else:
        principal = (municipio_por_nome(ctx, r.get("destino_cidade"), r.get("destino_uf"))
                     if r.get("destino_cidade") else None)
        if r.get("destino_cidade") and principal is None:
            notas.append("destino principal (texto) sem município correspondente")
    if principal is not None:
        destinos.append(principal)
    for extra in json_legado(r.get("destinos_extras")) or []:
        if not isinstance(extra, dict):
            continue
        m = municipio_por_nome(ctx, extra.get("cidade"), extra.get("uf"))
        if m is None:
            notas.append("destino extra (texto) sem município correspondente")
        elif m not in destinos:
            destinos.append(m)
    t_tipo = "tipoviagem_id" if sistema == "ev" else "tipoevento_id"
    tipos = _ids(ctx, sistema, "tipo_viagem",
                 _m2m(ctx, "viagem_tipos", sistema, c_viagem(sistema), r["id"], t_tipo),
                 notas, "tipo")
    criado, atualizado = datas(r)
    return Agregado(
        campos={"unidade_id": unidade or conf.unidade_id, "titulo": texto(r.get("titulo"), 255),
                "descricao": r.get("descricao") or "", "motivo": r.get("motivo") or "",
                "data_inicio": r.get("data_inicio"), "data_fim": r.get("data_fim"),
                "situacao": situacao, "situacao_anterior": "rascunho" if cancelada else "",
                "motivo_cancelamento": motivo_canc[:1000],
                "cancelado_em": r.get("cancelado_em") if cancelada else None},
        filhos={"destinos": [{"municipio_id": m, "ordem": i} for i, m in enumerate(destinos)]},
        m2m={"tipos": tipos}, notas=notas, quando=atualizado,
        extra={"criado_em": criado, "atualizado_em": atualizado})


def _criar_viagem(ctx: Contexto, sistema: str, r: dict, ag: Agregado) -> Viagem:
    v = Viagem.objects.create(**ag.campos, criado_por_id=ctx.usuario_migracao.pk)
    criar_filhos(ViagemDestino, {"viagem": v}, ag.filhos["destinos"])
    if ag.m2m["tipos"]:
        v.tipos.add(*ag.m2m["tipos"])
    preservar_datas(Viagem, v.pk, criado_em=ag.extra["criado_em"],
                    atualizado_em=ag.extra["atualizado_em"])
    return v


def _construir_anexo_viagem(ctx: Contexto, sistema: str, r: dict) -> Agregado | None:
    notas: list[str] = []
    viagem = _destino_viagem(ctx, "viagem", sistema, r.get(c_viagem(sistema)))
    if viagem is None:
        notas.append("anexo de viagem sem viagem migrada")
    arq = arquivo(ctx, sistema, r.get("arquivo"), entidade="anexo_viagem",
                  tabela=t("anexo_viagem", sistema), origem_pk=r["id"])
    if arq is None or not arq.existe:
        notas.append("anexo sem arquivo no backup: não migrado (o modelo exige o hash)")
    nome = texto(r.get("nome_original"), 255)
    ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    return Agregado(
        campos={"viagem_id": viagem, "tipo": "email" if ext in ("eml", "msg") else "oficio",
                "nome_original": nome, "arquivo": arq.nome if arq else "",
                "sha256": arq.sha256 if arq else "", "tamanho": arq.tamanho if arq else 0},
        notas=notas, extra={"criado_em": datas(r)[0], "ok": viagem is not None and bool(
            arq and arq.existe)})


def _criar_anexo_viagem(ctx: Contexto, sistema: str, r: dict, ag: Agregado) -> Any:
    if not ag.extra["ok"]:
        return None
    a = AnexoViagem.objects.create(**ag.campos, enviado_por_id=ctx.usuario_migracao.pk)
    preservar_datas(AnexoViagem, a.pk, enviado_em=ag.extra["criado_em"])
    return a


# ============================================================================ roteiros
def _trechos_legado(ctx: Contexto, nome: str, sistema: str, roteiro_pk: Any,
                    notas: list[str]) -> list[dict[str, Any]]:
    """Trechos de um roteiro do legado, na ordem da viagem (saída, ordem), renumerados 0..n.
    Trecho sem município, sem data, chegando antes de sair ou com origem = destino fica de fora
    (as restrições do modelo não o aceitam) e vai para a conferência."""
    tabela = t(nome, sistema)
    col_o, col_d = (("origem_municipio_id", "destino_municipio_id") if sistema == "ev"
                    else ("origem_cidade_id", "destino_cidade_id"))
    col_tempo = "tempo_viagem_min" if sistema == "ev" else "tempo_cru_estimado_min"
    linhas = sorted(agrupar(ctx, sistema, tabela, "roteiro_id").get(str(roteiro_pk), []),
                    key=lambda r: (r.get("saida_dt") is None,
                                   r["saida_dt"].timestamp() if r.get("saida_dt") else 0.0,
                                   r.get("ordem") or 0, r["id"]))
    reg = registro(ctx, TV[nome][1] or "")
    inv = inverso(ctx, TV[nome][1] or "")
    trechos: list[dict[str, Any]] = []
    for r in linhas:
        origem = fk(ctx, sistema, "municipio", r.get(col_o))
        destino = fk(ctx, sistema, "municipio", r.get(col_d))
        saida, chegada = r.get("saida_dt"), r.get("chegada_dt")
        motivo = ""
        if origem is None or destino is None:
            motivo = "sem município de origem/destino"
        elif saida is None or chegada is None:
            motivo = "sem data de saída/chegada"
        elif chegada <= saida:
            motivo = "chegada não é depois da saída"
        elif origem == destino:
            motivo = "origem igual ao destino"
        if motivo:
            notas.append(f"trecho {sistema}:{r['id']} descartado ({motivo})")
            ctx.relatorio.conta("trecho", "descartado")
            continue
        origem_mapa: list[tuple[str, str, Any]] = [(sistema, tabela, r["id"])]
        if sistema == "ev" and inv.get(str(r["id"])):
            origem_mapa.append(("gv", TV[nome][1] or "", inv[str(r["id"])]))
        elif sistema == "gv" and str(r["id"]) in reg:
            origem_mapa.append(("ev", TV[nome][0] or "", reg[str(r["id"])][0]))
        trechos.append({
            "ordem": len(trechos), "origem_id": origem, "destino_id": destino,
            "saida_em": saida, "chegada_em": chegada, "distancia_km": _km(r.get("distancia_km")),
            "tempo_viagem_min": _min(r.get(col_tempo)),
            "tempo_adicional_min": _min(r.get("tempo_adicional_min")) or 0,
            "_origem": origem_mapa})
    return trechos


def _componentes(ctx: Contexto, sistema: str, roteiro_pk: Any) -> list[dict[str, Any]]:
    linhas = agrupar(ctx, sistema, t("componente", sistema), "roteiro_id").get(
        str(roteiro_pk), [])
    campos = ("origem", "faixa", "percentual", "quantidade", "valor_unitario", "subtotal",
              "tabela_vigencia_inicio", "periodo_inicio", "periodo_fim")
    return [{k: _jsonavel(r.get(k)) for k in campos}
            for r in sorted(linhas, key=lambda r: (r.get("ordem") or 0, r["id"]))]


def _roteiros_so_ajustados(ctx: Contexto) -> set[tuple[str, str]]:
    """Roteiros que só existem como "roteiro ajustado" de uma prestação (cópia editável):
    viram trechos realizados na etapa de prestação, não um Roteiro."""
    chave = "roteiros_so_ajustados"
    if chave not in ctx.memo:
        res: set[tuple[str, str]] = set()
        for s in ("ev", "gv"):
            usados = {str(o.get("roteiro_id")) for o in tab(ctx, s, t("oficio", s))}
            for p in tab(ctx, s, t("prestacao", s)):
                aj = p.get("roteiro_ajustado_id")
                if aj is not None and str(aj) not in usados:
                    res.add((s, str(aj)))
        ctx.memo[chave] = res
    return ctx.memo[chave]


def _construir_roteiro(ctx: Contexto, sistema: str, r: dict) -> Agregado | None:
    if (sistema, str(r["id"])) in _roteiros_so_ajustados(ctx):
        ctx.relatorio.conta("roteiro", "so_ajuste_da_prestacao")
        return None
    notas: list[str] = []
    conf = configuracao(ctx)
    col_o = "origem_municipio_id" if sistema == "ev" else "origem_cidade_id"
    sede = fk(ctx, sistema, "municipio", r.get(col_o), notas, "sede")
    if sede is None:
        sede = conf.sede_id
        notas.append("roteiro sem cidade de origem: ficou a sede da configuração")
    cancelado = bool(r.get("cancelado"))
    if cancelado and texto(r.get("motivo_cancelamento")):
        notas.append("motivo do cancelamento do roteiro sem campo no destino (lacuna)")
    resumo = texto(r.get("resumo_diarias") if sistema == "ev" else r.get("quantidade_diarias"))
    qtd = r.get("quantidade_servidores") if sistema == "ev" else None
    if not qtd:
        qtd = 1
        for o in tab(ctx, sistema, t("oficio", sistema)):
            if str(o.get("roteiro_id")) == str(r["id"]):
                qtd = max(1, len(_m2m(ctx, "oficio_servidores", sistema, "oficio_id", o["id"],
                                      "servidor_id")))
                break
    trechos = _trechos_legado(ctx, "trecho", sistema, r["id"], notas)
    criado, atualizado = datas(r)
    return Agregado(
        campos={"unidade_id": conf.unidade_id,
                "viagem_id": _destino_viagem(ctx, "viagem", sistema, r.get(c_viagem(sistema))),
                "sede_id": sede, "quantidade_servidores": max(1, min(int(qtd), 32767)),
                "observacoes": r.get("observacoes") or "", "bate_volta": False,
                "situacao": "cancelado" if cancelado else "ativo",
                "diarias_total": r.get("valor_diarias") or Decimal(0),
                "diarias_resumo": resumo[:120],
                "diarias_calculo": {"legado": {
                    "valor_diarias": _jsonavel(r.get("valor_diarias")), "resumo": resumo,
                    "componentes": _componentes(ctx, sistema, r["id"])}}},
        filhos={"trechos": trechos}, notas=notas, quando=atualizado,
        extra={"criado_em": criado, "atualizado_em": atualizado})


def _criar_roteiro(ctx: Contexto, sistema: str, r: dict, ag: Agregado) -> Roteiro:
    ro = Roteiro.objects.create(**ag.campos, criado_por_id=ctx.usuario_migracao.pk)
    criar_filhos(TrechoRoteiro, {"roteiro": ro}, ag.filhos["trechos"], ctx)
    preservar_datas(Roteiro, ro.pk, criado_em=ag.extra["criado_em"],
                    atualizado_em=ag.extra["atualizado_em"])
    return ro


def _roteiro_gv_alterado(ctx: Contexto, r: dict) -> bool:
    pk = str(r["id"])
    return (pk in pais_alterados_no_gv(ctx, t("trecho", "gv"), "roteiro_id", t("trecho", "ev"),
                                       "roteiro_id", t("roteiro", "gv"))
            or pk in pais_alterados_no_gv(ctx, t("componente", "gv"), "roteiro_id",
                                          t("componente", "ev"), "roteiro_id",
                                          t("roteiro", "gv")))


def _filhos_ev_alterados(ctx: Contexto, nome: str, col: str, pai: dict) -> bool:
    """Filho do EV criado/alterado depois da carga (num pai que veio do GV)."""
    for f in agrupar(ctx, "ev", t(nome, "ev"), col).get(str(pai["id"]), []):
        if depois_da_carga(ctx, *datas(f)):
            return True
    return False


def _roteiro_ev_alterado(ctx: Contexto, r: dict) -> bool:
    return (_filhos_ev_alterados(ctx, "trecho", "roteiro_id", r)
            or _filhos_ev_alterados(ctx, "componente", "roteiro_id", r))


# ============================================================================ ofícios
SITUACAO_OFICIO = {"RASCUNHO": "rascunho", "GERADO": "emitido", "FINALIZADO": "emitido",
                   "ARQUIVADO": "emitido"}
CUSTEIO = {"UNIDADE_DPC": "unidade", "OUTRA_INSTITUICAO": "outra_instituicao",
           "ONUS_LIMITADO": "onus_limitado"}


def _artefatos_do(ctx: Contexto, nome: str, sistema: str, pk: Any, col: str,
                  tipos: tuple[str, ...]) -> list[dict]:
    """Artefatos (PDFs gerados) dos dois sistemas para o mesmo documento."""
    ev_pk, gv_pk = _par(ctx, nome, sistema, pk)
    res: list[dict] = []
    if ev_pk is not None:
        res += [a for a in agrupar(ctx, "ev", t("artefato", "ev"), col).get(ev_pk, [])
                if a["tipo"] in tipos]
    if gv_pk is not None and col == "oficio_id":
        res += [a for a in agrupar(ctx, "gv", t("artefato", "gv"), col).get(gv_pk, [])
                if a["tipo"] in tipos]
    return res


def _justificativa(ctx: Contexto, sistema: str, oficio_pk: Any,
                   notas: list[str]) -> tuple[str, int | None]:
    linhas = agrupar(ctx, sistema, t("justificativa", sistema), "oficio_id").get(
        str(oficio_pk), [])
    if sistema == "ev" and not any((j.get("texto") or "").strip() for j in linhas):
        # Justificativa escrita no GV depois da carga (o EV não a tem).
        _, gv_pk = _par(ctx, "oficio", "ev", oficio_pk)
        reg = registro(ctx, t("justificativa", "gv"))
        novas = [j for j in agrupar(ctx, "gv", t("justificativa", "gv"), "oficio_id")
                 .get(str(gv_pk), []) if str(j["id"]) not in reg] if gv_pk else []
        if novas:
            notas.append("justificativa escrita só no GV depois da carga: entrou a do GV")
            ctx.relatorio.conta("justificativa", "so_no_gv_acrescentada")
            j = novas[-1]
            return j.get("texto") or "", fk(ctx, "gv", "modelo_justificativa",
                                             j.get("modelo_id"), notas, "modelo")
    if not linhas:
        return "", None
    if len(linhas) > 1:
        notas.append("mais de uma justificativa no legado: ficou a última")
    j = linhas[-1]
    return j.get("texto") or "", fk(ctx, sistema, "modelo_justificativa", j.get("modelo_id"),
                                     notas, "modelo de justificativa")


def _construir_oficio(ctx: Contexto, sistema: str, r: dict) -> Agregado | None:
    notas: list[str] = []
    conf = configuracao(ctx)
    status = (r.get("status") or "").upper()
    cancelado = bool(r.get("cancelado"))
    situacao_status = SITUACAO_OFICIO.get(status, "rascunho")
    if status not in SITUACAO_OFICIO:
        notas.append(f"status de ofício desconhecido ({status}): ficou rascunho")
    situacao = "cancelado" if cancelado else situacao_status
    criado, atualizado = datas(r)
    artefatos = _artefatos_do(ctx, "oficio", sistema, r["id"], "oficio_id", ("oficio",))
    primeiro = min((a["criado_em"] for a in artefatos if a.get("criado_em")), default=None)
    # Sem PDF gerado: a última atualização (a da cópia do EV, igual para os dois lados).
    base_ev = _linha_ev(ctx, "oficio", sistema, r) or r
    emitido_em = (primeiro or datas(base_ev)[1]) if situacao_status == "emitido" else None
    motivo_canc = texto(r.get("motivo_cancelamento"))
    if cancelado and not motivo_canc:
        motivo_canc = "Cancelado no sistema anterior (sem motivo registrado)."
        notas.append("ofício cancelado sem motivo no legado: motivo padrão")
    protocolo = somente_digitos(r.get("protocolo"))
    if protocolo and len(protocolo) != 9:
        notas.append(f"protocolo com {len(protocolo)} dígitos: ficou vazio")
        protocolo = ""
    origem_prot = {"MANUAL": "manual", "SIMULADO": "simulado"}.get(
        (r.get("protocolo_origem") or "").upper(), "manual") if protocolo else ""
    custeio = CUSTEIO.get((r.get("custeio") or "").upper(), "unidade")
    instituicao = texto(r.get("custeio_observacao"), 160) if custeio == "outra_instituicao" \
        else ""
    viatura = fk(ctx, sistema, "viatura", r.get("viatura_id"), notas, "viatura")
    manual = any(texto(r.get(c)) for c in ("transporte_modelo_manual", "transporte_placa_manual",
                                           "transporte_tipo_manual"))
    meio = (r.get("transporte_tipo_manual") or "").strip().lower()
    if meio and meio not in Oficio.MeioTransporte.values:
        notas.append("meio de transporte manual sem correspondente: ficou na descrição")
        meio = ""
    roteiro = _destino_viagem(ctx, "roteiro", sistema, r.get("roteiro_id"))
    if r.get("roteiro_id") is not None and roteiro is None:
        notas.append("roteiro do ofício não migrado: ofício sem trechos")
    roteiro_obj = Roteiro.objects.filter(pk=roteiro).first() if roteiro else None
    trechos = ([{k: getattr(tr, k) for k in ("ordem", "origem_id", "destino_id", "saida_em",
                                              "chegada_em", "distancia_km", "tempo_viagem_min",
                                              "tempo_adicional_min")}
                for tr in roteiro_obj.trechos.all()] if roteiro_obj else [])
    roteiro_legado = por_id(ctx, sistema, t("roteiro", sistema)).get(str(r.get("roteiro_id")))
    # Equipe: ordem do id da linha M2M; o motorista da equipe é marcado no viajante.
    servidores = _ids(ctx, sistema, "servidor",
                      _m2m(ctx, "oficio_servidores", sistema, "oficio_id", r["id"],
                           "servidor_id"), notas, "servidor")
    motorista = fk(ctx, sistema, "servidor", r.get("motorista_id"), notas, "motorista")
    modo = (r.get("motorista_modo") or "").upper()
    externo: dict[str, Any] = {"motorista_externo": "", "motorista_externo_servidor_id": None,
                               "motorista_externo_nome": "", "motorista_externo_rg": "",
                               "motorista_externo_cpf": "", "motorista_externo_cargo": "",
                               "motorista_externo_unidade": "",
                               "motorista_externo_observacao": ""}
    if modo == "MANUAL":
        externo.update({
            "motorista_externo": "manual",
            "motorista_externo_nome": texto(r.get("motorista_manual_nome"), 255),
            "motorista_externo_rg": texto(r.get("motorista_manual_rg"), 30),
            "motorista_externo_cpf": somente_digitos(r.get("motorista_manual_cpf"))[:11],
            "motorista_externo_cargo": texto(r.get("motorista_manual_cargo"), 120),
            "motorista_externo_unidade": texto(r.get("motorista_manual_unidade"), 255),
            "motorista_externo_observacao": r.get("motorista_manual_observacao") or ""})
    elif motorista is not None and motorista not in servidores:
        externo.update({"motorista_externo": "servidor",
                        "motorista_externo_servidor_id": motorista})
    prot_mot = somente_digitos(r.get("motorista_protocolo_ref"))
    justificativa, modelo = _justificativa(ctx, sistema, r["id"], notas)
    retificado, complementar = bool(r.get("retificado_documento")), bool(
        r.get("complementar_documento"))
    if retificado and complementar:
        notas.append("ofício retificado E complementar no legado: ficou retificado")
    campos = {
        "unidade_id": conf.unidade_id,
        "viagem_id": _destino_viagem(ctx, "viagem", sistema, r.get(c_viagem(sistema))),
        "ano": r["ano"], "numero": r["numero"],
        "data_oficio": r.get("data_criacao") or data_local(criado),
        "data_oficio_manual": False, "protocolo": protocolo, "protocolo_origem": origem_prot,
        "marcador": "retificado" if retificado else ("complementar" if complementar else ""),
        "motivo": r.get("motivo") or "", "bate_volta": False, "custeio": custeio,
        "custeio_instituicao": instituicao,
        "tipo_transporte": "viatura" if viatura or not manual else "outro",
        "viatura_id": viatura, "transporte_descricao": texto(r.get("transporte_modelo_manual"),
                                                              120),
        "transporte_meio": meio,
        "transporte_placa": normalizar_placa(r.get("transporte_placa_manual"))[:7],
        "transporte_combustivel_id": fk(ctx, sistema, "combustivel",
                                        r.get("transporte_combustivel_manual_id"), notas,
                                        "combustível"),
        "porte_arma": bool(r.get("porte_transporte_armas")),
        "sede_id": roteiro_obj.sede_id if roteiro_obj else conf.sede_id,
        "justificativa_modelo_id": modelo, "justificativa": justificativa,
        "roteiro_id": roteiro,
        "diarias_total": (roteiro_legado or {}).get("valor_diarias") or Decimal(0),
        "diarias_resumo": (roteiro_obj.diarias_resumo if roteiro_obj else ""),
        "diarias_calculo": roteiro_obj.diarias_calculo if roteiro_obj else {},
        "diarias_erro": "", "situacao": situacao, "versao": 1,
        "emitido_em": emitido_em, "cancelado_em": r.get("cancelado_em") if cancelado else None,
        "motivo_cancelamento": motivo_canc if cancelado else "",
        "situacao_anterior": situacao_status if cancelado else "",
        "motorista_oficio_origem": texto(r.get("motorista_oficio_referencia"), 12),
        "motorista_protocolo_origem": prot_mot if len(prot_mot) == 9 else "",
        **externo,
    }
    viajantes = [{"servidor_id": s, "motorista": s == motorista and modo == "SERVIDOR",
                  "ordem": i} for i, s in enumerate(servidores)]
    return Agregado(campos=campos, filhos={"viajantes": viajantes, "trechos": trechos},
                    notas=notas, quando=atualizado,
                    extra={"criado_em": criado, "atualizado_em": atualizado,
                           "status": status, "destino_gabinete": r.get("destino_gabinete")})


def _numero_livre(ctx: Contexto, ano: int) -> int:
    """Próximo número do ano, acima de tudo o que existe no destino e nos dois legados."""
    legado = [o["numero"] for s in ("ev", "gv") for o in tab(ctx, s, t("oficio", s))
              if o.get("ano") == ano]
    no_destino = Oficio.objects.filter(ano=ano).aggregate(m=Max("numero"))["m"] or 0
    return max([no_destino, *legado]) + 1


def _criar_oficio(ctx: Contexto, sistema: str, r: dict, ag: Agregado) -> Oficio:
    campos = dict(ag.campos)
    anterior = None
    if Oficio.objects.filter(ano=campos["ano"], numero=campos["numero"]).exists():
        anterior = campos["numero"]
        campos["numero"] = _numero_livre(ctx, campos["ano"])
        ctx.relatorio.conta("oficio", "renumerado")
        ctx.relatorio.revisar("oficio", f"número {anterior}/{campos['ano']} já usado por outro "
                              f"documento: renumerado para {campos['numero']}/{campos['ano']} "
                              "(o PDF emitido no legado mostra o número antigo)",
                              sistema=sistema, tabela=t("oficio", sistema), origem_pk=r["id"])
    o = Oficio.objects.create(**campos, criado_por_id=ctx.usuario_migracao.pk)
    criar_filhos(Viajante, {"oficio": o}, ag.filhos["viajantes"])
    criar_filhos(Trecho, {"oficio": o}, ag.filhos["trechos"])
    preservar_datas(Oficio, o.pk, criado_em=ag.extra["criado_em"],
                    atualizado_em=ag.extra["atualizado_em"])
    origem = "EV" if sistema == "ev" else "GV"
    descricao = f"Migrado do sistema anterior ({origem}, ofício {r['id']})."
    if anterior is not None:
        descricao = (f"Migrado do sistema anterior ({origem}, ofício {r['id']}), onde era o nº "
                     f"{anterior:02d}/{campos['ano']}; renumerado por conflito de numeração.")
    dados: dict[str, Any] = {"origem": sistema, "pk": r["id"],
                             "status_legado": ag.extra["status"], "lote": ctx.lote}
    if anterior is not None:
        dados["numero_anterior"] = anterior
    if ag.extra.get("destino_gabinete"):
        dados["destino_gabinete"] = ag.extra["destino_gabinete"]
    h = Historico.objects.create(oficio=o, acao="criado", descricao=descricao[:300],
                                 usuario_id=ctx.usuario_migracao.pk, dados=dados)
    Historico.objects.filter(pk=h.pk).update(em=ag.extra["criado_em"] or h.em)
    return o


def _oficio_gv_alterado(ctx: Contexto, r: dict) -> bool:
    if str(r["id"]) in pais_alterados_no_gv(ctx, t("justificativa", "gv"), "oficio_id",
                                            t("justificativa", "ev"), "oficio_id",
                                            t("oficio", "gv")):
        return True
    ev_pk, _ = _par(ctx, "oficio", "gv", r["id"])
    if ev_pk is None:
        return False
    gv = {fk(ctx, "gv", "servidor", s) for s in _m2m(ctx, "oficio_servidores", "gv",
                                                      "oficio_id", r["id"], "servidor_id")}
    ev = {fk(ctx, "ev", "servidor", s) for s in _m2m(ctx, "oficio_servidores", "ev",
                                                      "oficio_id", ev_pk, "servidor_id")}
    return gv != ev


def _oficio_ev_alterado(ctx: Contexto, r: dict) -> bool:
    return _filhos_ev_alterados(ctx, "justificativa", "oficio_id", r)


# ============================================================================ termos
def _construir_termo(ctx: Contexto, sistema: str, r: dict) -> Agregado:
    notas: list[str] = []
    conf = configuracao(ctx)
    destinos: list[int] = []
    principal = fk(ctx, sistema, "municipio", r.get("destino_cidade_id"), notas, "destino")
    if principal is not None:
        destinos.append(principal)
    for extra in json_legado(r.get("destinos_extras")) or []:
        m = (municipio_por_nome(ctx, extra.get("cidade"), extra.get("uf"))
             if isinstance(extra, dict) else None)
        if m is None:
            notas.append("destino extra do termo sem município correspondente")
        elif m not in destinos:
            destinos.append(m)
    oficio = _destino_viagem(ctx, "oficio", sistema, r.get("oficio_id"))
    if r.get("oficio_id") is not None and oficio is None:
        notas.append("ofício do termo não migrado")
    servidores = _ids(ctx, sistema, "servidor",
                      _m2m(ctx, "termo_servidores", sistema, "termoautorizacao_id", r["id"],
                           "servidor_id"), notas, "servidor")
    viatura = fk(ctx, sistema, "viatura", r.get("viatura_id"), notas, "viatura")
    cancelado = bool(r.get("cancelado"))
    motivo = texto(r.get("motivo_cancelamento"))
    if cancelado and not motivo:
        motivo = "Cancelado no sistema anterior (sem motivo registrado)."
        notas.append("termo cancelado sem motivo no legado: motivo padrão")
    inicio, fim = r.get("data_evento_inicio"), r.get("data_evento_fim")
    if fim is not None and (inicio is None or fim < inicio):
        notas.append("período do termo fora de ordem: ficou só o início")
        fim = None
    criado, atualizado = datas(r)
    return Agregado(
        campos={"unidade_id": conf.unidade_id,
                "viagem_id": _destino_viagem(ctx, "viagem", sistema, r.get(c_viagem(sistema))),
                "oficio_id": oficio, "evento": "PCPR na Comunidade", "data_inicio": inicio,
                "data_fim": fim, "viatura_id": viatura,
                "situacao": "cancelado" if cancelado else "ativo",
                "motivo_cancelamento": motivo[:1000] if cancelado else "",
                "cancelado_em": r.get("cancelado_em") if cancelado else None},
        filhos={"destinos": [{"municipio_id": m, "ordem": i} for i, m in enumerate(destinos)],
                "viaturas": ([{"viatura_id": viatura, "ordem": 0,
                               "_m2m": {"servidores": servidores}}] if viatura else [])},
        m2m={"servidores": servidores, "oficios": [oficio] if oficio else []},
        notas=notas, quando=atualizado, extra={"criado_em": criado, "atualizado_em": atualizado})


def _criar_termo(ctx: Contexto, sistema: str, r: dict, ag: Agregado) -> TermoAutorizacao:
    termo = TermoAutorizacao.objects.create(**ag.campos, criado_por_id=ctx.usuario_migracao.pk)
    criar_filhos(TermoDestino, {"termo": termo}, ag.filhos["destinos"])
    criar_filhos(TermoViatura, {"termo": termo}, ag.filhos["viaturas"])
    for nome, ids in ag.m2m.items():
        if ids:
            getattr(termo, nome).add(*ids)
    preservar_datas(TermoAutorizacao, termo.pk, criado_em=ag.extra["criado_em"],
                    atualizado_em=ag.extra["atualizado_em"])
    return termo


# ============================================================================ ordens de serviço
MODELO_OS = {"PADRAO": None, "OPERACAO_RETORNO_POSTERIOR": "operacao_policial",
             "MICROONIBUS": "unidade_movel", "CAMINHAO": "unidade_movel",
             "CERIMONIAL_ANTECIPADO": "cerimonial"}


def _funcoes_os(ctx: Contexto, sistema: str, r: dict, modelo: ModeloOS | None,
                notas: list[str]) -> dict[str, str]:
    """{id do servidor novo: código da função}. A OS que veio do GV é lida do GV (a carga do EV
    gravou a chave com o id do servidor NO GV e o JSON duplamente codificado)."""
    fonte_s, linha = sistema, r
    if sistema == "ev" and r.get("legado_origem"):
        _, gv_pk = _par(ctx, "os", "ev", r["id"])
        gv_linha = por_id(ctx, "gv", t("os", "gv")).get(gv_pk) if gv_pk else None
        if gv_linha is not None:
            fonte_s, linha = "gv", gv_linha
    bruto = json_legado(linha.get("funcoes_servidores")) or {}
    if not isinstance(bruto, dict) or not bruto:
        return {}
    validos = set(FuncaoOS.objects.filter(modelo=modelo).values_list("codigo", flat=True)) \
        if modelo else set()
    res: dict[str, str] = {}
    for servidor_pk, codigo in bruto.items():
        alvo = fk(ctx, fonte_s, "servidor", servidor_pk)
        cod = str(codigo or "").strip().lower()
        if alvo is None:
            notas.append("função da OS para servidor sem correspondente: descartada")
        elif cod not in validos:
            notas.append(f"função '{cod}' não existe no modelo da OS: descartada")
        else:
            res[str(alvo)] = cod
    return res


def _primeiro_gerado(artefatos: list[dict]) -> datetime | None:
    return min((a["criado_em"] for a in artefatos if a.get("criado_em")
                and a.get("formato") == "pdf"), default=None)


def _artefatos_os(ctx: Contexto, sistema: str, r: dict) -> list[dict]:
    ev_pk, gv_pk = _par(ctx, "os", sistema, r["id"])
    res = list(agrupar(ctx, "ev", t("artefato", "ev"), "ordem_servico_id").get(ev_pk, [])) \
        if ev_pk else []
    gv = por_id(ctx, "gv", t("os", "gv")).get(gv_pk) if gv_pk else None
    if gv is not None:
        oficios = {str(o) for o in _m2m(ctx, "os_oficios", "gv", "ordemservico_id", gv["id"],
                                        "oficio_id")}
        for a in tab(ctx, "gv", t("artefato", "gv")):
            if a["tipo"] != "ordem_servico":
                continue
            if (str(a.get("oficio_id")) in oficios
                    or (not oficios and gv.get("evento_id") is not None
                        and a.get("evento_id") == gv.get("evento_id"))):
                res.append(a)
    return res


def _construir_os(ctx: Contexto, sistema: str, r: dict) -> Agregado:
    notas: list[str] = []
    conf = configuracao(ctx)
    tipo = (r.get("tipo_necessidade") or "PADRAO").upper()
    if tipo not in MODELO_OS:
        notas.append(f"tipo de OS desconhecido ({tipo}): ficou a OS padrão")
    chave_modelo = MODELO_OS.get(tipo)
    modelo = ModeloOS.objects.filter(chave=chave_modelo).first() if chave_modelo else None
    if chave_modelo and modelo is None:
        notas.append(f"modelo de OS '{chave_modelo}' não existe no destino: ficou a padrão")
    col_m = "municipio_id" if sistema == "ev" else "cidade_id"
    linhas_dest = agrupar(ctx, sistema, t("os_destinos", sistema), "ordemservico_id").get(
        str(r["id"]), [])
    if sistema == "ev":
        linhas_dest = sorted(linhas_dest, key=lambda d: (d.get("ordem") or 0, d["id"]))
    destinos = _ids(ctx, sistema, "municipio", [d[col_m] for d in linhas_dest], notas, "destino")
    oficios = [o for o in (_destino_viagem(ctx, "oficio", sistema, pk) for pk in _m2m(
        ctx, "os_oficios", sistema, "ordemservico_id", r["id"], "oficio_id")) if o]
    servidores = _ids(ctx, sistema, "servidor", _m2m(
        ctx, "os_servidores", sistema, "ordemservico_id", r["id"], "servidor_id"), notas,
        "servidor")
    trechos = Trecho.objects.filter(oficio_id__in=oficios)
    saidas = [tr.saida_em for tr in trechos]
    chegadas = [tr.chegada_em for tr in trechos]
    ev_inicio, ev_fim = r.get("data_evento_inicio"), r.get("data_evento_fim")
    if ev_fim is not None and (ev_inicio is None or ev_fim < ev_inicio):
        notas.append("período do evento da OS fora de ordem: ficou só o início")
        ev_fim = None
    inicio = data_local(min(saidas)) if saidas else ev_inicio
    fim = data_local(max(chegadas)) if chegadas else ev_fim
    if fim is not None and (inicio is None or fim < inicio):
        fim = inicio
    gerado = _primeiro_gerado(_artefatos_os(ctx, sistema, r))
    ev_linha = _linha_ev(ctx, "os", sistema, r)
    data_doc = (ev_linha or {}).get("data_documento") or data_local(gerado)
    cancelado = bool(r.get("cancelado"))
    motivo = texto(r.get("motivo_cancelamento"))
    if cancelado and not motivo:
        motivo = "Cancelada no sistema anterior (sem motivo registrado)."
        notas.append("OS cancelada sem motivo no legado: motivo padrão")
    assinante = fk(ctx, "ev", "servidor", ev_linha.get("assinante_id"), notas, "assinante") \
        if ev_linha else None
    criado, atualizado = datas(r)
    return Agregado(
        campos={"unidade_id": conf.unidade_id,
                "viagem_id": _destino_viagem(ctx, "viagem", sistema, r.get(c_viagem(sistema))),
                "numero": r["numero"], "ano": r["ano"], "modelo_id": modelo.pk if modelo else None,
                "data_inicio": inicio, "data_fim": fim, "data_evento_inicio": ev_inicio,
                "data_evento_fim": ev_fim, "hora": None, "data_documento": data_doc,
                "documento_gerado_em": gerado,
                "funcoes": _funcoes_os(ctx, sistema, r, modelo, notas),
                "motivo": r.get("motivo") or "", "assinante_id": assinante,
                "situacao": "cancelada" if cancelado else "ativa",
                "motivo_cancelamento": motivo[:1000] if cancelado else "",
                "cancelado_em": r.get("cancelado_em") if cancelado else None},
        filhos={"destinos": [{"municipio_id": m, "posicao": i} for i, m in enumerate(destinos)]},
        m2m={"oficios": oficios, "servidores": servidores}, notas=notas, quando=atualizado,
        extra={"criado_em": criado, "atualizado_em": atualizado})


def _criar_os(ctx: Contexto, sistema: str, r: dict, ag: Agregado) -> OrdemServico:
    os_ = OrdemServico.objects.create(**ag.campos, criado_por_id=ctx.usuario_migracao.pk)
    criar_filhos(OrdemServicoDestino, {"ordem": os_}, ag.filhos["destinos"])
    for nome, ids in ag.m2m.items():
        if ids:
            getattr(os_, nome).add(*ids)
    preservar_datas(OrdemServico, os_.pk, criado_em=ag.extra["criado_em"],
                    atualizado_em=ag.extra["atualizado_em"])
    if sistema == "gv":
        # Só no GV: a mesma OS pode ter sido digitada no EV com outro número.
        equipe = sorted(ag.m2m["servidores"])
        for outra in OrdemServico.objects.filter(
                data_evento_inicio=ag.campos["data_evento_inicio"],
                data_evento_fim=ag.campos["data_evento_fim"]).exclude(pk=os_.pk):
            if equipe and sorted(outra.servidores.values_list("pk", flat=True)) == equipe:
                ctx.relatorio.revisar("ordem_servico", "OS só do GV com o mesmo período e a "
                                      "mesma equipe de outra OS: provável duplicata (as duas "
                                      "foram mantidas, números diferentes)", sistema="gv",
                                      tabela=t("os", "gv"), origem_pk=r["id"],
                                      destino_pk=os_.pk, outra_destino_pk=outra.pk)
    return os_


# ============================================================================ planos
GENERO = {"MASCULINO": "M", "FEMININO": "F"}


def _coordenador(ctx: Contexto, sistema: str, r: dict, prefixo: str,
                 notas: list[str]) -> dict[str, Any]:
    modo = (r.get(f"{prefixo}_modo") or "").upper()
    servidor = fk(ctx, sistema, "servidor", r.get(f"{prefixo}_id"), notas, prefixo) \
        if modo != "MANUAL" else None
    campos = {f"{prefixo}_id": servidor,
              f"{prefixo}_nome": texto(r.get(f"{prefixo}_nome_manual"), 255)
              if modo == "MANUAL" else "",
              f"{prefixo}_cargo": texto(r.get(f"{prefixo}_cargo_manual"), 120)
              if modo == "MANUAL" else ""}
    return campos


def _efetivo(ctx: Contexto, sistema: str, linhas: list[dict], notas: list[str]) -> list[dict]:
    res: list[dict[str, Any]] = []
    for e in sorted(linhas, key=lambda e: e["id"]):
        cargo = fk(ctx, sistema, "cargo", e.get("cargo_id"), notas, "cargo do efetivo")
        if cargo is None or not e.get("quantidade") or e["quantidade"] < 1:
            notas.append(f"linha de efetivo {sistema}:{e['id']} sem cargo ou quantidade: "
                         "descartada")
            continue
        res.append({"cargo_id": cargo,
                    "unidade_id": fk(ctx, sistema, "unidade", e.get("unidade_id"), notas,
                                     "unidade do efetivo"),
                    "quantidade": min(e["quantidade"], 32767), "posicao": len(res)})
    return res


def _destinos_plano(ctx: Contexto, sistema: str, linhas: list[dict], notas: list[str],
                    principal: Any = None) -> list[dict]:
    ids: list[int] = []
    if principal is not None:
        alvo = fk(ctx, sistema, "municipio", principal, notas, "destino")
        if alvo is not None:
            ids.append(alvo)
    for d in sorted(linhas, key=lambda d: (d.get("ordem") or 0, d["id"])):
        alvo = fk(ctx, sistema, "municipio", d.get("cidade_id"), notas, "destino")
        if alvo is not None and alvo not in ids:
            ids.append(alvo)
    return [{"municipio_id": m, "posicao": i} for i, m in enumerate(ids)]


def _eventos_plano(ctx: Contexto, sistema: str, plano_pk: Any,
                   notas: list[str]) -> list[dict[str, Any]]:
    res = []
    eventos = sorted(agrupar(ctx, sistema, t("evento_plano", sistema), "plano_id")
                     .get(str(plano_pk), []), key=lambda e: (e.get("ordem") or 0, e["id"]))
    destinos = agrupar(ctx, sistema, t("plano_destino", sistema), "evento_id")
    for i, e in enumerate(eventos):
        efetivo = agrupar(ctx, sistema, t("efetivo_evento", sistema), "evento_id").get(
            str(e["id"]), [])
        fonte_ef = sistema
        if sistema == "ev" and not efetivo and e.get("legado_origem"):
            # A carga do EV não trouxe o efetivo dos eventos do plano: vem do GV.
            _, gv_pk = _par(ctx, "evento_plano", "ev", e["id"])
            efetivo = agrupar(ctx, "gv", t("efetivo_evento", "gv"), "evento_id").get(
                str(gv_pk), []) if gv_pk else []
            fonte_ef = "gv"
            if efetivo:
                ctx.relatorio.conta("efetivo_evento", "trazido_do_gv")
        programa = fk(ctx, sistema, "programa", e.get("programa_id"), notas, "programa")
        atividades = _ids(ctx, sistema, "atividade", _m2m(
            ctx, "evento_atividades", sistema, "eventoplano_id", e["id"],
            "atividadeplanotrabalho_id"), notas, "atividade")
        inicio, fim = e.get("data_evento_inicio"), e.get("data_evento_fim")
        if fim is not None and (inicio is None or fim < inicio):
            fim = None
            notas.append(f"evento do plano {sistema}:{e['id']} com período fora de ordem")
        res.append({
            "posicao": i, "programa_id": programa,
            "programa_outros": texto(e.get("programa_outros"), 200),
            "data_inicio": inicio, "data_fim": fim,
            "horario": texto(e.get("horario_atendimento"), 60),
            "diarias_composicao": texto(e.get("diarias_composicao"), 120),
            "diarias_unitario": e.get("diarias_valor_unitario"),
            "diarias_total": e.get("diarias_valor_total"),
            "atividades_texto": e.get("atividades_texto") or "", "metas": e.get("metas") or "",
            "recursos": e.get("recursos_necessarios") or "",
            "unidade_movel_texto": e.get("unidade_movel_texto") or "",
            "_m2m": {"atividades": atividades, "programas": [programa] if programa else []},
            "_destinos": _destinos_plano(ctx, sistema, destinos.get(str(e["id"]), []), notas),
            "_efetivo": _efetivo(ctx, fonte_ef, efetivo, notas),
            "_datas": dict(zip(("criado_em", "atualizado_em"), datas(e), strict=True)),
            "_origem": [(sistema, t("evento_plano", sistema), e["id"])]})
    return res


def _artefatos_plano(ctx: Contexto, sistema: str, r: dict) -> list[dict]:
    ev_pk, gv_pk = _par(ctx, "plano", sistema, r["id"])
    res = list(agrupar(ctx, "ev", t("artefato", "ev"), "plano_trabalho_id").get(ev_pk, [])) \
        if ev_pk else []
    if gv_pk is not None:
        gv = por_id(ctx, "gv", t("plano", "gv")).get(gv_pk)
        if gv is not None:
            prefixo = f"{gv['numero']:02d}/{gv['ano']}"
            for a in tab(ctx, "gv", t("artefato", "gv")):
                plano = (json_legado(a.get("payload_snapshot")) or {}).get("plano") \
                    if a["tipo"] == "plano_trabalho" else None
                if isinstance(plano, dict) and str(plano.get("numero_plano_trabalho") or "") \
                        .startswith(prefixo):
                    res.append(a)
    return res


def _construir_plano(ctx: Contexto, sistema: str, r: dict) -> Agregado:
    notas: list[str] = []
    conf = configuracao(ctx)
    status = (r.get("status") or "").upper()
    cancelado = bool(r.get("cancelado"))
    motivo = texto(r.get("motivo_cancelamento"))
    if cancelado and not motivo:
        motivo = "Cancelado no sistema anterior (sem motivo registrado)."
        notas.append("plano cancelado sem motivo no legado: motivo padrão")
    programa = fk(ctx, sistema, "programa", r.get("programa_id"), notas, "programa")
    atividades = _ids(ctx, sistema, "atividade", _m2m(
        ctx, "plano_atividades", sistema, "planotrabalho_id", r["id"],
        "atividadeplanotrabalho_id"), notas, "atividade")
    destinos = [d for d in agrupar(ctx, sistema, t("plano_destino", sistema), "plano_id")
                .get(str(r["id"]), []) if d.get("evento_id") is None]
    efetivo = agrupar(ctx, sistema, t("efetivo_plano", sistema), "plano_id").get(str(r["id"]),
                                                                                  [])
    viagem = _destino_viagem(ctx, "viagem", sistema, r.get(c_viagem(sistema)))
    oficios = sorted(Oficio.objects.filter(viagem_id=viagem).values_list("pk", flat=True)) \
        if viagem else []
    inicio, fim = r.get("data_evento_inicio"), r.get("data_evento_fim")
    if fim is not None and (inicio is None or fim < inicio):
        notas.append("período do plano fora de ordem: ficou só o início")
        fim = None
    gerado = _primeiro_gerado(_artefatos_plano(ctx, sistema, r))
    ev_linha = _linha_ev(ctx, "plano", sistema, r)
    criado, atualizado = datas(r)
    campos = {
        "unidade_id": conf.unidade_id, "viagem_id": viagem, "numero": r["numero"],
        "ano": r["ano"], "sufixo": texto(r.get("sufixo_numero"), 20),
        "situacao": "gerado" if status == "GERADO" else "rascunho", "cancelado": cancelado,
        "motivo_cancelamento": motivo[:1000] if cancelado else "",
        "cancelado_em": r.get("cancelado_em") if cancelado else None,
        "data_documento": (ev_linha or {}).get("data_documento") or data_local(gerado),
        "documento_gerado_em": gerado,
        "assinante_id": fk(ctx, "ev", "servidor", ev_linha.get("assinante_id"), notas,
                           "assinante") if ev_linha else None,
        "programa_id": programa, "programa_outros": texto(r.get("programa_outros"), 200),
        "data_inicio": inicio, "data_fim": fim,
        "horario": texto(r.get("horario_atendimento"), 60),
        **_coordenador(ctx, sistema, r, "coordenador_adm", notas),
        **_coordenador(ctx, sistema, r, "coordenador_op", notas),
        "coordenador_adm_genero": GENERO.get((r.get("coordenador_adm_genero") or "").upper(), ""),
        "coordenador_op_genero": GENERO.get((r.get("coordenador_op_genero") or "").upper(), ""),
        "contextualizacao": r.get("contextualizacao") or "",
        "contextualizacao_auto": bool(r.get("contextualizacao_auto")),
        "coordenacao": r.get("coordenacao") or "",
        "coordenacao_auto": bool(r.get("coordenacao_auto")),
        "consideracoes": r.get("consideracao_final") or "",
        "consideracoes_auto": bool(r.get("consideracao_auto")),
        "saida_em": aware(r.get("saida_sede_data"), r.get("saida_sede_hora")),
        "chegada_em": aware(r.get("chegada_sede_data"), r.get("chegada_sede_hora")),
        "diarias_composicao": texto(r.get("diarias_composicao"), 120),
        "diarias_unitario": r.get("diarias_valor_unitario"),
        "diarias_total": r.get("diarias_valor_total"),
        "atividades_texto": r.get("atividades") or "", "metas": r.get("metas") or "",
        "recursos": r.get("recursos_necessarios") or "",
        "unidade_movel_texto": r.get("unidade_movel_texto") or "",
    }
    resultados = [] if sistema == "gv" else [
        {"atividade_id": fk(ctx, "ev", "atividade", x.get("atividade_id"), notas, "atividade"),
         "realizado": x.get("realizado"), "observacao": texto(x.get("observacao"), 500)}
        for x in agrupar(ctx, "ev", t("resultado", "ev"), "plano_id").get(str(r["id"]), [])]
    return Agregado(
        campos=campos,
        filhos={"destinos": _destinos_plano(ctx, sistema, destinos, notas,
                                            r.get("destino_cidade_id")),
                "efetivo": _efetivo(ctx, sistema, efetivo, notas),
                "eventos": _eventos_plano(ctx, sistema, r["id"], notas),
                "resultados": [x for x in resultados if x["atividade_id"]]},
        m2m={"atividades": atividades, "programas": [programa] if programa else [],
             "oficios": oficios},
        notas=notas, quando=atualizado, extra={"criado_em": criado, "atualizado_em": atualizado})


def _criar_plano(ctx: Contexto, sistema: str, r: dict, ag: Agregado) -> PlanoTrabalho:
    plano = PlanoTrabalho.objects.create(**ag.campos, criado_por_id=ctx.usuario_migracao.pk)
    criar_filhos(PlanoDestino, {"plano": plano}, ag.filhos["destinos"])
    criar_filhos(EfetivoPlano, {"plano": plano}, ag.filhos["efetivo"])
    criar_filhos(ResultadoAtividade, {"plano": plano}, ag.filhos["resultados"])
    for e in ag.filhos["eventos"]:
        [evento] = criar_filhos(EventoPlano, {"plano": plano}, [e], ctx)
        criar_filhos(EventoDestino, {"evento": evento}, e["_destinos"])
        criar_filhos(EfetivoEvento, {"evento": evento}, e["_efetivo"])
    for nome, ids in ag.m2m.items():
        if ids:
            getattr(plano, nome).add(*ids)
    preservar_datas(PlanoTrabalho, plano.pk, criado_em=ag.extra["criado_em"],
                    atualizado_em=ag.extra["atualizado_em"])
    return plano


def _plano_gv_alterado(ctx: Contexto, r: dict) -> bool:
    pk = str(r["id"])
    return any(pk in pais_alterados_no_gv(ctx, t(n, "gv"), "plano_id", t(n, "ev"), "plano_id",
                                          t("plano", "gv"))
               for n in ("plano_destino", "efetivo_plano", "evento_plano"))


def _plano_ev_alterado(ctx: Contexto, r: dict) -> bool:
    return any(_filhos_ev_alterados(ctx, n, "plano_id", r)
               for n in ("plano_destino", "efetivo_plano", "evento_plano"))


# ============================================================================ numeração
def _numeracao_anual(ctx: Contexto) -> None:
    """O piso do ano entra antes dos ofícios (a numeração continua do maior importado)."""
    for s in ("ev", "gv"):
        for r in tab(ctx, s, t("numeracao", s)):
            _, criado = NumeracaoAnual.objects.get_or_create(
                ano=r["ano"], defaults={"piso": r.get("numero_inicial") or 1})
            ctx.relatorio.conta("numeracao_anual", "criado" if criado else "ja_existia")


def _numeracao(ctx: Contexto) -> None:
    for modelo, entidade, qs in (
            (NumeracaoOrdemServico, "numeracao_os", OrdemServico.objects),
            (NumeracaoPlano, "numeracao_plano", PlanoTrabalho.objects)):
        for ano in sorted(set(qs.values_list("ano", flat=True))):
            _, criado = modelo.objects.get_or_create(ano=ano)
            ctx.relatorio.conta(entidade, "criado" if criado else "ja_existia")


# ============================================================================ documentos
def _emitido(oficio: Oficio) -> bool:
    return oficio.situacao == "emitido" or (oficio.situacao == "cancelado"
                                            and oficio.situacao_anterior == "emitido")


def _candidatos_documento(ctx: Contexto) -> dict[int, list[tuple[str, dict]]]:
    """Artefatos PDF de ofício/justificativa por ofício do destino: todos os do EV e os do GV
    gerados depois da carga (os do GV que o EV trouxe já estão no EV — ou o EV os descartou)."""
    por_oficio: dict[int, list[tuple[str, dict]]] = {}
    for s in ("ev", "gv"):
        reg = registro(ctx, t("artefato", "gv")) if s == "gv" else {}
        for a in tab(ctx, s, t("artefato", s)):
            if a["tipo"] not in ("oficio", "justificativa") or a.get("formato") != "pdf":
                continue
            if s == "gv" and str(a["id"]) in reg:
                continue
            alvo = _destino_viagem(ctx, "oficio", s, a.get("oficio_id"))
            if alvo is None:
                continue
            por_oficio.setdefault(alvo, []).append((s, a))
    return por_oficio


def _documentos(ctx: Contexto) -> None:
    rel = ctx.relatorio
    for oficio_pk, candidatos in sorted(_candidatos_documento(ctx).items()):
        oficio = Oficio.objects.get(pk=oficio_pk)
        for tipo in ("oficio", "justificativa"):
            lista = [(s, a) for s, a in candidatos if a["tipo"] == tipo]
            if not lista:
                continue
            emitidas = [(s, a) for s, a in lista if a.get("versao_emitida")]
            if emitidas:
                escolhidos = [(s, a, int(a["versao_emitida"])) for s, a in emitidas]
            elif _emitido(oficio):
                s, a = max(lista, key=lambda sa: (sa[1]["criado_em"], str(sa[1]["id"])))
                escolhidos = [(s, a, 1)]
            else:
                rel.conta("documento", "oficio_nao_emitido_sem_documento", len(lista))
                continue
            rel.conta("documento", "regeracao_nao_migrada", len(lista) - len(escolhidos))
            for s, a, versao in escolhidos:
                _documento(ctx, oficio, tipo, s, a, versao)


def _documento(ctx: Contexto, oficio: Oficio, tipo: str, s: str, a: dict, versao: int) -> None:
    rel = ctx.relatorio
    tabela = t("artefato", s)
    if ctx.destino(s, tabela, a["id"]) is not None:
        rel.conta("documento", "ja_mapeado")
        return
    existente = Documento.objects.filter(oficio=oficio, tipo=tipo, versao=versao).first()
    if existente is not None:
        ctx.mapear(s, tabela, a["id"], existente, criado=False)
        rel.conta("documento", "casado_por_chave")
        return
    arq = arquivo(ctx, s, a.get("arquivo"), entidade="documento", tabela=tabela,
                  origem_pk=a["id"])
    hash_legado = (a.get("hash_sha256") or "").lower()
    if arq and arq.existe and hash_legado and hash_legado != arq.sha256:
        rel.revisar("documento", "hash gravado no legado difere do arquivo do backup",
                    sistema=s, tabela=tabela, origem_pk=str(a["id"]))
    ok = bool(arq and arq.existe)
    dados = json_legado(a.get("payload_snapshot")) or {}
    if not isinstance(dados, dict):
        dados = {"payload": dados}
    dados = {**dados, "legado": {
        "origem": s, "artefato_id": str(a["id"]), "cache_key": a.get("cache_key") or "",
        "generator_version": a.get("generator_version") or "", "engine": a.get("engine") or "",
        "pdfa": False}}
    legado = por_id(ctx, s, t("oficio", s)).get(str(a.get("oficio_id")))
    if legado is not None and legado.get("numero") != oficio.numero:
        dados["legado"]["numero_do_oficio_no_pdf"] = legado.get("numero")
    autor = a.get("emitida_por_id") or a.get("criado_por_id")
    doc = Documento.objects.create(
        oficio=oficio, tipo=tipo, versao=versao, situacao="pronto" if ok else "falhou",
        dados=dados, arquivo=arq.nome if arq else "", sha256=arq.sha256 if ok and arq else "",
        tamanho=arq.tamanho if ok and arq else 0,
        erro="" if ok else "Arquivo do sistema anterior ausente no backup da migração.",
        emitido_por_id=usuario(ctx, s, autor), gerado_em=a.get("criado_em"))
    preservar_datas(Documento, doc.pk, emitido_em=a.get("emitida_em") or a.get("criado_em"))
    ctx.mapear(s, tabela, a["id"], doc, criado=True)
    rel.conta("documento", "criado" if ok else "criado_sem_arquivo")


def _termo_do_oficio(ctx: Contexto, oficio_pk: int) -> TermoAutorizacao:
    """Termo assinado gerado do ofício, sem termo cadastrado no legado: usa o termo ligado ao
    ofício; sem nenhum, cria um termo do ofício (herda dele destinos, período e equipe)."""
    termo = TermoAutorizacao.objects.filter(oficio_id=oficio_pk).order_by("pk").first()
    if termo is not None:
        return termo
    oficio = Oficio.objects.get(pk=oficio_pk)
    termo = TermoAutorizacao.objects.create(
        unidade_id=oficio.unidade_id, viagem_id=oficio.viagem_id, oficio=oficio,
        criado_por_id=ctx.usuario_migracao.pk)
    termo.oficios.add(oficio)
    ctx.relatorio.conta("termo", "criado_para_via_assinada")
    ctx.relatorio.revisar("termo", "termo assinado do legado sem termo cadastrado: criado um "
                          "termo do ofício (herda os dados dele)", destino_pk=termo.pk,
                          oficio_destino_pk=oficio_pk)
    return termo


def _vias_dos_documentos(ctx: Contexto) -> None:
    """Vias assinadas dos documentos gerados (`arquivo_assinado` e as versões de assinatura)."""
    for s in ("ev", "gv"):
        reg = registro(ctx, t("artefato", "gv")) if s == "gv" else {}
        versoes = agrupar(ctx, s, t("assinatura_versao", s), "artefato_id")
        for a in tab(ctx, s, t("artefato", s)):
            if s == "gv" and str(a["id"]) in reg:
                continue   # a cópia do EV traz a via
            lista = sorted(versoes.get(str(a["id"]), []), key=lambda v: v["criado_em"])
            if not lista and not (a.get("arquivo_assinado") or "").strip():
                continue
            dono = _dono_da_via(ctx, s, a)
            if dono is None:
                continue
            documento = ctx.destino_int(s, t("artefato", s), a["id"]) \
                if a["tipo"] in ("oficio", "justificativa") else None
            if lista:
                for v in lista:
                    arq = arquivo(ctx, s, v.get("arquivo"), entidade="via_assinada",
                                  tabela=t("assinatura_versao", s), origem_pk=v["id"])
                    inserir_via(ctx, "via_assinada", dono=dono, arq=arq,
                                nome_original=texto(v.get("nome_original")),
                                enviado_em=v.get("criado_em"),
                                enviado_por_id=usuario(ctx, s, v.get("criado_por_id")),
                                revogada_em=v.get("revogada_em"), documento_id=documento,
                                origem=[(s, t("assinatura_versao", s), v["id"])])
            else:
                arq = arquivo(ctx, s, a.get("arquivo_assinado"), entidade="via_assinada",
                              tabela=t("artefato", s), origem_pk=a["id"])
                inserir_via(ctx, "via_assinada", dono=dono, arq=arq,
                            nome_original=texto(a.get("assinado_nome_original")),
                            enviado_em=a.get("assinado_em") or a.get("criado_em"),
                            enviado_por_id=ctx.usuario_migracao.pk, documento_id=documento,
                            origem=[(s, f"{t('artefato', s)}.arquivo_assinado", a["id"])])


def _dono_da_via(ctx: Contexto, s: str, a: dict) -> dict[str, Any] | None:
    rel = ctx.relatorio
    tipo = a["tipo"]
    if tipo in ("oficio", "justificativa"):
        oficio = _destino_viagem(ctx, "oficio", s, a.get("oficio_id"))
        if oficio is not None:
            return {"tipo": tipo, "oficio_id": oficio}
    elif tipo == "termo_autorizacao":
        termo = _destino_viagem(ctx, "termo", s, a.get("termo_id"))
        if termo is None and a.get("oficio_id") is not None:
            oficio = _destino_viagem(ctx, "oficio", s, a.get("oficio_id"))
            termo = _termo_do_oficio(ctx, oficio).pk if oficio else None
        if termo is not None:
            servidor = fk(ctx, s, "servidor", a.get("servidor_id"))
            return {"tipo": "termo", "termo_id": termo,
                    "chave": str(servidor) if servidor else "generico"}
    elif tipo == "ordem_servico":
        ordem = _destino_viagem(ctx, "os", s, a.get("ordem_servico_id"))
        if ordem is not None:
            return {"tipo": "ordem", "ordem_id": ordem}
    rel.conta("via_assinada", "sem_documento_de_destino")
    rel.revisar("via_assinada", f"via assinada de '{tipo}' sem documento correspondente no "
                "destino (plano não tem via assinada no sistema novo)", sistema=s,
                tabela=t("artefato", s), origem_pk=str(a["id"]))
    return None


# ============================================================================ textos editados
ACAO_EDICAO = {"edicao": "editado", "restauracao": "restaurado", "modelo": "modelo"}
EDICAO = {"oficio": (EdicaoDocumento, "oficio", "oficio"),
          "ordem_servico": (EdicaoOrdem, "ordem", "os"),
          "plano_trabalho": (EdicaoPlano, "plano", "plano")}


def _edicoes(ctx: Contexto) -> None:
    rel = ctx.relatorio
    tabela = t("versao_editada", "ev")
    linhas = sorted(tab(ctx, "ev", tabela), key=lambda e: (e["criado_em"], e["id"]))
    contador: dict[tuple[str, int], int] = {}
    for e in linhas:
        spec = EDICAO.get(e["tipo_documento"])
        if spec is None:
            rel.conta("edicao_documento", "tipo_sem_destino")
            continue
        modelo, campo, nome = spec
        col = {"oficio": "oficio_id", "os": "ordem_servico_id", "plano": "plano_trabalho_id"}[nome]
        dono = _destino_viagem(ctx, nome, "ev", e.get(col))
        entidade = f"edicao_{campo}"
        if dono is None:
            rel.conta(entidade, "sem_documento")
            continue
        chave = (e["tipo_documento"], dono)
        contador[chave] = contador.get(chave, 0) + 1
        if ctx.destino("ev", tabela, e["id"]) is not None:
            rel.conta(entidade, "ja_mapeado")
            continue
        regioes = json_legado(e.get("regioes")) or {}
        campos: dict[str, Any] = {
            f"{campo}_id": dono, "numero": contador[chave],
            "acao": ACAO_EDICAO.get(e.get("acao") or "", "editado"),
            "regioes": regioes if isinstance(regioes, dict) else {}, "blocos_alterados": [],
            "impressoes": {},
            "restaurada_de_id": ctx.destino_int("ev", tabela, e.get("restaurada_de_id"))
            if e.get("restaurada_de_id") else None,
            "criado_por_id": usuario(ctx, "ev", e.get("criado_por_id"))}
        if modelo is EdicaoDocumento:
            campos.update({"tipo": "oficio", "modelos": {}})
        obj = modelo._default_manager.create(**campos)
        preservar_datas(modelo, obj.pk, criado_em=e["criado_em"])
        ctx.mapear("ev", tabela, e["id"], obj, criado=True)
        rel.conta(entidade, "criado")
        rel.revisar(entidade, "texto editado no EV: conferir contra o modelo do sistema novo "
                    "(a impressão do modelo antigo não se aplica)", sistema="ev", tabela=tabela,
                    origem_pk=e["id"], destino_pk=obj.pk)


# ============================================================================ distâncias
def _distancias(ctx: Contexto) -> None:
    for r in tab(ctx, "ev", t("distancia", "ev")):
        origem = fk(ctx, "ev", "municipio", r.get("origem_id"))
        destino = fk(ctx, "ev", "municipio", r.get("destino_id"))
        minutos = r.get("tempo_viagem_min") or r.get("duracao_min")
        if origem is None or destino is None or r.get("distancia_km") is None or minutos is None:
            ctx.relatorio.conta("distancia_municipios", "ignorado")
            continue
        _, criado = DistanciaMunicipios.objects.get_or_create(
            origem_id=origem, destino_id=destino,
            defaults={"km": _km(r["distancia_km"]) or Decimal(0), "minutos": int(minutos),
                      "fonte": texto(r.get("fonte"), 20) or "legado", "regra_tempo": 0,
                      "geometria": []})
        ctx.relatorio.conta("distancia_municipios", "criado" if criado else "ja_existia")


# ============================================================================ lacunas
def _lacunas(ctx: Contexto) -> None:
    """Dados sem lugar no sistema novo: só contados (o relatório da migração os lista)."""
    rel = ctx.relatorio
    rel.conta("lacuna", "viagem_equipe_prevista", len(tab(ctx, "ev", t("equipe_prevista", "ev"))))
    rel.conta("lacuna", "oficio_servidores_termo_autorizacao", len(tab(
        ctx, "ev", "viagens_oficios_oficio_servidores_termo_autorizacao")))
    rel.conta("lacuna", "artefatos_docx_termo_os_plano_nao_migrados", sum(
        1 for s in ("ev", "gv") for a in tab(ctx, s, t("artefato", s))
        if a["tipo"] not in ("oficio", "justificativa") or a.get("formato") != "pdf"))


# ============================================================================ etapa
def executar(ctx: Contexto) -> None:
    configuracao(ctx)   # falha cedo sem a etapa de cadastros
    cargas = [
        Carga("viagem", Viagem, t("viagem", "ev"), t("viagem", "gv"), _construir_viagem,
              _criar_viagem),
        Carga("anexo_viagem", AnexoViagem, t("anexo_viagem", "ev"), t("anexo_viagem", "gv"),
              _construir_anexo_viagem, _criar_anexo_viagem, conferir_apagados=False,
              ignorar_na_comparacao=("arquivo",)),
        Carga("roteiro", Roteiro, t("roteiro", "ev"), t("roteiro", "gv"), _construir_roteiro,
              _criar_roteiro, gv_alterado=_roteiro_gv_alterado,
              ev_alterado=_roteiro_ev_alterado,
              ignorar_na_comparacao=("quantidade_servidores",)),
        Carga("oficio", Oficio, t("oficio", "ev"), t("oficio", "gv"), _construir_oficio,
              _criar_oficio, gv_alterado=_oficio_gv_alterado, ev_alterado=_oficio_ev_alterado),
        Carga("termo", TermoAutorizacao, t("termo", "ev"), t("termo", "gv"), _construir_termo,
              _criar_termo),
        Carga("ordem_servico", OrdemServico, t("os", "ev"), t("os", "gv"), _construir_os,
              _criar_os),
        Carga("plano", PlanoTrabalho, t("plano", "ev"), t("plano", "gv"), _construir_plano,
              _criar_plano, gv_alterado=_plano_gv_alterado, ev_alterado=_plano_ev_alterado),
    ]
    for c in cargas:
        executar_carga(ctx, c)
        if c.entidade == "roteiro":
            _numeracao_anual(ctx)
    _numeracao(ctx)
    _documentos(ctx)
    _vias_dos_documentos(ctx)
    _edicoes(ctx)
    _distancias(ctx)
    _lacunas(ctx)
