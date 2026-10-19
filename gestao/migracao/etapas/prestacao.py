"""Etapa 3 — prestação de contas: prestações (com os trechos realizados), prestações dos
servidores, diários de bordo (e as linhas), relatórios técnicos, anexos, ofícios assinados
(vias do ofício), carimbos do número de solicitação e importações de processo.

Regras (docs da migração, 03-prestacao):

* Uma prestação por ofício (mapa de ofícios da etapa de viagens; nunca por nº/ano).
* Os dois sistemas continuaram editando as mesmas prestações depois da carga: cada linha é
  comparada com a cópia do EV (impressão digital); editada nos dois → vale a mais recente e a
  outra vai para a conferência; campo vazio nunca apaga campo preenchido.
* Diário e relatório criados nos dois sistemas para a mesma prestação: fica o mais recente,
  completado com o outro (linhas do diário juntadas pela ordem).
* Anexo: mesmo (prestação, tipo, servidor, SHA-256) = o mesmo anexo. O ofício assinado é a via
  assinada do próprio ofício (o original sem carimbo). Os de um só por dono (RT e diário
  assinados) ficam com o mais recente em vigor; os outros, "substituídos".
* Apagado no GV depois da carga = apagado pelo usuário (anexo removido; carimbo não entra).
* Carimbo do GV com y = 0 (posicionamento automático que falhou): não entra.
* Não migram: protocolos simulados, assinatura eletrônica do GV, lançamentos e link do diário
  de campo (token em claro), JSON de leitura das importações (só contados).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.utils import timezone

from gestao.cadastros.validacoes import somente_digitos
from gestao.viagens import realizado
from gestao.viagens.models import (
    AnexoPrestacao,
    ArquivoImportado,
    CarimboSolicitacao,
    DiarioBordo,
    DiarioBordoTrecho,
    Oficio,
    ParteImportada,
    PrestacaoContas,
    PrestacaoServidor,
    RelatorioTecnico,
    Trecho,
    TrechoRealizado,
    TrechoRoteiro,
    ViaAssinada,
)

from ..contexto import Contexto
from .comum import (
    Agregado,
    Carga,
    agrupar,
    arquivo,
    criar_filhos,
    datas,
    depois_da_carga,
    destino_com_modelo,
    diferencas,
    executar_carga,
    fk,
    inserir_via,
    inverso,
    pais_alterados_no_gv,
    por_id,
    preencher_vazios,
    preservar_datas,
    registro,
    tab,
    texto,
    usuario,
)
from .viagens import TV as TV_VIAGENS
from .viagens import _trechos_legado

TP: dict[str, tuple[str, str | None]] = {
    "prestacao": ("viagens_prestacoes_prestacaocontas", "prestacoes_contas_prestacaocontas"),
    "servidor": ("viagens_prestacoes_prestacaoservidor", "prestacoes_contas_prestacaoservidor"),
    "diario": ("viagens_prestacoes_diariobordo", "prestacoes_contas_diariobordo"),
    "linha": ("viagens_prestacoes_diariobordotrecho", "prestacoes_contas_diariobordotrecho"),
    "rt": ("viagens_prestacoes_relatoriotecnico", "prestacoes_contas_relatoriotecnico"),
    "anexo": ("viagens_prestacoes_prestacaodocumentoanexo",
              "prestacoes_contas_prestacaodocumentoanexo"),
    "carimbo": ("viagens_prestacoes_carimbosolicitacao", "prestacoes_contas_carimbosolicitacao"),
    "importacao": ("viagens_prestacoes_importacaoprocesso", None),
    "oficio": TV_VIAGENS["oficio"],
    "trecho": TV_VIAGENS["trecho"],
}


def t(nome: str, sistema: str) -> str:
    par = TP[nome]
    return (par[0] if sistema == "ev" else par[1]) or ""


def _mapa(ctx: Contexto, nome: str, sistema: str, pk: Any) -> int | None:
    return ctx.destino_int(sistema, t(nome, sistema), pk) if pk is not None else None


def _par_ev(ctx: Contexto, nome: str, sistema: str, linha: dict) -> dict | None:
    """A cópia do EV de uma linha do GV (ou a própria linha do EV)."""
    if sistema == "ev":
        return linha
    reg = registro(ctx, t(nome, "gv")).get(str(linha["id"]))
    return por_id(ctx, "ev", t(nome, "ev")).get(reg[0]) if reg else None


def _apagado_no_gv(ctx: Contexto, nome: str, ev_pk: Any) -> bool:
    """Linha do EV que veio do GV e que o GV apagou depois da carga."""
    gv_pk = inverso(ctx, t(nome, "gv")).get(str(ev_pk))
    return gv_pk is not None and ctx.gv is not None and gv_pk not in por_id(
        ctx, "gv", t(nome, "gv"))


# ============================================================================ prestação
def _construir_prestacao(ctx: Contexto, sistema: str, r: dict) -> Agregado:
    notas: list[str] = []
    oficio = _mapa(ctx, "oficio", sistema, r.get("oficio_id"))
    if oficio is None:
        notas.append("prestação de ofício não migrado")
    criado, atualizado = datas(r)
    return Agregado(campos={"oficio_id": oficio, "observacoes": r.get("observacoes") or ""},
                    notas=notas, quando=atualizado,
                    extra={"criado_em": criado, "atualizado_em": atualizado,
                           "ajustado": r.get("roteiro_ajustado_id")})


def _criar_prestacao(ctx: Contexto, sistema: str, r: dict, ag: Agregado) -> Any:
    if ag.campos["oficio_id"] is None:
        return None
    p = PrestacaoContas.objects.create(**ag.campos)
    oficio = Oficio.objects.get(pk=p.oficio_id)
    if oficio.situacao == "rascunho":
        ctx.relatorio.conta("prestacao", "de_oficio_em_rascunho")
        ctx.relatorio.revisar("prestacao", "prestação de um ofício ainda em rascunho (mantida: "
                              "tem dados)", sistema=sistema, tabela=t("prestacao", sistema),
                              origem_pk=r["id"], destino_pk=p.pk)
    if ag.extra["ajustado"] is not None:
        _trechos_realizados(ctx, sistema, r, p, ag)
    preservar_datas(PrestacaoContas, p.pk, criado_em=ag.extra["criado_em"],
                    atualizado_em=ag.extra["atualizado_em"])
    return p


def _trechos_realizados(ctx: Contexto, sistema: str, r: dict, p: PrestacaoContas,
                        ag: Agregado) -> None:
    """O roteiro ajustado do legado vira os trechos realizados (não um Roteiro); as diárias
    realizadas são recalculadas pela regra do sistema novo."""
    trechos = _trechos_legado(ctx, "trecho", sistema, ag.extra["ajustado"], ag.notas)
    do_oficio = {tr.ordem: tr.pk for tr in Trecho.objects.filter(oficio_id=p.oficio_id)}
    for tr in trechos:
        TrechoRealizado.objects.create(
            prestacao=p, trecho_oficio_id=do_oficio.get(tr["ordem"]), ordem=tr["ordem"],
            origem_id=tr["origem_id"], destino_id=tr["destino_id"], saida_em=tr["saida_em"],
            chegada_em=tr["chegada_em"], distancia_km=tr["distancia_km"])
    ctx.relatorio.conta("trecho_realizado", "criado", len(trechos))
    if trechos:
        realizado._recalcular(p)
        ctx.relatorio.conta("prestacao", "diarias_realizadas_recalculadas")


def _prestacao_chave(ctx: Contexto, r: dict, ag: Agregado) -> Any:
    return PrestacaoContas.objects.filter(oficio_id=ag.campos["oficio_id"]).first()


# ============================================================================ servidores
SITUACAO_SERVIDOR = {"pendente": "pendente", "em_preenchimento": "preenchimento",
                     "enviada": "enviada", "aprovada": "aprovada", "devolvida": "devolvida"}


def _marca(r: dict, flag: str, quando: str) -> datetime | None:
    if not r.get(flag):
        return None
    return r.get(quando) or datas(r)[1]


def _construir_servidor(ctx: Contexto, sistema: str, r: dict) -> Agregado:
    notas: list[str] = []
    prestacao = _mapa(ctx, "prestacao", sistema, r.get("prestacao_id"))
    servidor = fk(ctx, sistema, "servidor", r.get("servidor_id"), notas, "servidor")
    status = (r.get("status") or "").strip().lower()
    if status not in SITUACAO_SERVIDOR:
        notas.append(f"situação desconhecida ({status}): ficou pendente")
    ev = _par_ev(ctx, "servidor", sistema, r) or {}
    liberacao, prazo = r.get("data_liberacao_diarias"), r.get("prazo_limite_saque")
    if liberacao and prazo and prazo < liberacao:
        notas.append("prazo de saque antes da liberação: prazo ficou vazio")
        prazo = None
    override = r.get("diaria_valor_override")
    if override is not None and override <= 0:
        notas.append("diária manual não positiva: descartada")
        override = None
    criado, atualizado = datas(r)
    return Agregado(
        campos={"prestacao_id": prestacao, "servidor_id": servidor,
                "numero_solicitacao": texto(r.get("numero_solicitacao"), 60),
                "data_liberacao_diarias": liberacao, "prazo_limite_saque": prazo,
                "diaria_valor_override": override,
                "diaria_valor_override_observacao": texto(
                    r.get("diaria_valor_override_observacao"), 255),
                "situacao": SITUACAO_SERVIDOR.get(status, "pendente"),
                "arquivada_em": _marca(r, "arquivada", "arquivada_em"),
                "finalizada_em": _marca(r, "finalizada", "finalizada_em"),
                # Só o EV tem estes campos: a versão do GV leva os da cópia do EV.
                "justificativa_finalizacao": ev.get("justificativa_finalizacao") or "",
                "enviada_em": ev.get("enviada_em"),
                "protocolo_envio": texto(ev.get("protocolo_envio"), 120),
                "decidida_em": ev.get("decidida_em"),
                "motivo_devolucao": ev.get("motivo_devolucao") or "",
                "removida_em": r.get("removida_em")},
        notas=notas, quando=atualizado,
        extra={"criado_em": criado, "atualizado_em": atualizado})


def _criar_servidor(ctx: Contexto, sistema: str, r: dict, ag: Agregado) -> Any:
    if ag.campos["prestacao_id"] is None or ag.campos["servidor_id"] is None:
        ag.notas.append("sem prestação ou servidor migrado")
        return None
    ps = PrestacaoServidor.objects.create(**ag.campos)
    preservar_datas(PrestacaoServidor, ps.pk, criado_em=ag.extra["criado_em"],
                    atualizado_em=ag.extra["atualizado_em"])
    return ps


def _servidor_chave(ctx: Contexto, r: dict, ag: Agregado) -> Any:
    return PrestacaoServidor.objects.filter(prestacao_id=ag.campos["prestacao_id"],
                                            servidor_id=ag.campos["servidor_id"]).first()


# ============================================================================ diário de bordo
MOTORISTA = {"OFICIO": "oficio", "SERVIDOR": "servidor", "OUTRO_OFICIO": "outro_oficio",
             "MANUAL": "oficio"}
VIATURA = {"OFICIO": "oficio", "CADASTRO": "cadastro", "MANUAL": "manual"}


def _trecho_do_oficio(ctx: Contexto, sistema: str, oficio_pk: int | None, trecho_legado: Any,
                      ordem: int) -> int | None:
    """Linha do diário → trecho do ofício: o trecho do roteiro do legado tem a mesma ordem que
    a cópia no ofício; sem ele, a ordem da própria linha."""
    if oficio_pk is None or trecho_legado is None:
        return None
    alvo = ctx.destino_int(sistema, t("trecho", sistema), trecho_legado)
    ordem_tr = (TrechoRoteiro.objects.filter(pk=alvo).values_list("ordem", flat=True).first()
                if alvo else None)
    if ordem_tr is None:
        ordem_tr = ordem
    return (Trecho.objects.filter(oficio_id=oficio_pk, ordem=ordem_tr)
            .values_list("pk", flat=True).first())


def _construir_diario(ctx: Contexto, sistema: str, r: dict) -> Agregado:
    notas: list[str] = []
    prestacao = _mapa(ctx, "prestacao", sistema, r.get("prestacao_id"))
    oficio = (PrestacaoContas.objects.filter(pk=prestacao).values_list("oficio_id", flat=True)
              .first() if prestacao else None)
    modo_m = (r.get("motorista_modo") or "OFICIO").upper()
    modo_v = (r.get("viatura_modo") or "OFICIO").upper()
    tipo = (r.get("viatura_manual_tipo") or "").strip().lower()
    linhas = []
    for x in sorted(agrupar(ctx, sistema, t("linha", sistema), "diario_id").get(str(r["id"]), []),
                    key=lambda x: (x.get("ordem") or 0, x["id"])):
        km_i, km_f = x.get("km_inicial"), x.get("km_final")
        if km_i is not None and km_f is not None and km_f < km_i:
            notas.append(f"linha {sistema}:{x['id']} com km final menor que o inicial: km final "
                         "vazio")
            km_f = None
        linhas.append({
            "trecho_id": _trecho_do_oficio(ctx, sistema, oficio, x.get("trecho_id"),
                                           x.get("ordem") or 0),
            "ordem": x.get("ordem") or 0, "km_inicial": km_i, "km_final": km_f,
            "abastecimento": x.get("abastecimento"),
            "_origem": [(sistema, t("linha", sistema), x["id"])],
            "_datas": {"atualizado_em": x.get("atualizado_em")}})
    criado, atualizado = datas(r)
    return Agregado(
        campos={"prestacao_id": prestacao, "motorista_modo": MOTORISTA.get(modo_m, "oficio"),
                "motorista_servidor_id": fk(ctx, sistema, "servidor",
                                            r.get("motorista_servidor_id"), notas, "motorista"),
                "motorista_nome": texto(r.get("motorista_manual_nome"), 255),
                "motorista_cpf": somente_digitos(r.get("motorista_manual_cpf"))[:11],
                "motorista_oficio": texto(r.get("motorista_oficio_referencia"), 16),
                "motorista_protocolo": texto(r.get("motorista_protocolo_ref"), 30),
                "viatura_modo": VIATURA.get(modo_v, "oficio"),
                "viatura_id": fk(ctx, sistema, "viatura", r.get("viatura_id"), notas, "viatura"),
                "viatura_modelo": texto(r.get("viatura_manual_modelo"), 120),
                "viatura_placa": texto(r.get("viatura_manual_placa"), 8),
                "viatura_tipo": tipo if tipo in ("caracterizada", "descaracterizada",
                                                 "unidade_movel") else "",
                "viatura_combustivel": texto(r.get("viatura_manual_combustivel"), 60)},
        filhos={"linhas": linhas}, notas=notas, quando=atualizado,
        extra={"criado_em": criado, "atualizado_em": atualizado})


def _criar_diario(ctx: Contexto, sistema: str, r: dict, ag: Agregado) -> Any:
    if ag.campos["prestacao_id"] is None:
        ag.notas.append("diário sem prestação migrada")
        return None
    d = DiarioBordo.objects.create(**ag.campos)
    criar_filhos(DiarioBordoTrecho, {"diario": d}, ag.filhos["linhas"], ctx)
    preservar_datas(DiarioBordo, d.pk, criado_em=ag.extra["criado_em"],
                    atualizado_em=ag.extra["atualizado_em"])
    return d


def _diario_chave(ctx: Contexto, r: dict, ag: Agregado) -> Any:
    return DiarioBordo.objects.filter(prestacao_id=ag.campos["prestacao_id"]).first()


def _fundir_diario(ctx: Contexto, existente: Any, r: dict, ag: Agregado) -> None:
    """Diário criado nos dois sistemas para a mesma prestação: vale o mais recente, e as linhas
    se juntam pela ordem (km digitado nunca se perde)."""
    rel = ctx.relatorio
    atual = _agregado_do_objeto(existente, ag)
    vence_gv = bool(ag.quando and existente.atualizado_em and ag.quando > existente.atualizado_em)
    campos = diferencas(atual, ag, ("prestacao_id",))
    if vence_gv:
        novos = dict(ag.campos)
        preencher_vazios(Agregado(campos=novos), atual)
        DiarioBordo.objects.filter(pk=existente.pk).update(**novos)
    conflitos: list[int] = []
    linhas = {x.ordem: x for x in existente.linhas.all()}
    for nova in ag.filhos["linhas"]:
        velha = linhas.get(nova["ordem"])
        if velha is None:
            criar_filhos(DiarioBordoTrecho, {"diario": existente}, [nova], ctx)
            continue
        for sistema, tabela, pk in nova["_origem"]:
            ctx.mapear(sistema, tabela, pk, velha, criado=False)
        mudar = {}
        for campo in ("km_inicial", "km_final", "trecho_id"):
            antes, depois = getattr(velha, campo), nova[campo]
            if antes is None and depois is not None:
                mudar[campo] = depois
            elif antes is not None and depois is not None and antes != depois:
                conflitos.append(nova["ordem"])
                if vence_gv:
                    mudar[campo] = depois
        if mudar:
            DiarioBordoTrecho.objects.filter(pk=velha.pk).update(**mudar)
    rel.conta("diario_bordo", "criado_nos_dois_juntado")
    rel.revisar("diario_bordo", f"diário criado nos dois sistemas: juntados (valeu o "
                f"{'GV' if vence_gv else 'EV'}, o mais recente)", destino_pk=existente.pk,
                gv_pk=r["id"], campos=campos, linhas_com_km_diferente=sorted(set(conflitos)))


def _agregado_do_objeto(obj: Any, modelo_ag: Agregado) -> Agregado:
    return Agregado(campos={k: getattr(obj, k) for k in modelo_ag.campos})


def _diario_gv_alterado(ctx: Contexto, r: dict) -> bool:
    return str(r["id"]) in pais_alterados_no_gv(ctx, t("linha", "gv"), "diario_id",
                                                t("linha", "ev"), "diario_id", t("diario", "gv"))


def _diario_ev_alterado(ctx: Contexto, r: dict) -> bool:
    return any(depois_da_carga(ctx, x.get("atualizado_em")) for x in agrupar(
        ctx, "ev", t("linha", "ev"), "diario_id").get(str(r["id"]), []))


# ============================================================================ relatório técnico
CAMPOS_RT = {"motivo": None, "diaria": 255, "translado": 255, "combustivel": 255,
             "passagem": 255, "atividade": None, "conclusao": None, "medidas": None,
             "info_complementares": None}


def _construir_rt(ctx: Contexto, sistema: str, r: dict) -> Agregado:
    prestacao = _mapa(ctx, "prestacao", sistema, r.get("prestacao_id"))
    criado, atualizado = datas(r)
    campos: dict[str, Any] = {"prestacao_id": prestacao}
    for campo, limite in CAMPOS_RT.items():
        campos[campo] = texto(r.get(campo), limite) if limite else (r.get(campo) or "")
    return Agregado(campos=campos, quando=atualizado,
                    extra={"criado_em": criado, "atualizado_em": atualizado})


def _criar_rt(ctx: Contexto, sistema: str, r: dict, ag: Agregado) -> Any:
    if ag.campos["prestacao_id"] is None:
        ag.notas.append("relatório técnico sem prestação migrada")
        return None
    rt = RelatorioTecnico.objects.create(**ag.campos)
    preservar_datas(RelatorioTecnico, rt.pk, criado_em=ag.extra["criado_em"],
                    atualizado_em=ag.extra["atualizado_em"])
    return rt


def _rt_chave(ctx: Contexto, r: dict, ag: Agregado) -> Any:
    return RelatorioTecnico.objects.filter(prestacao_id=ag.campos["prestacao_id"]).first()


def _fundir_rt(ctx: Contexto, existente: Any, r: dict, ag: Agregado) -> None:
    """Relatório criado nos dois sistemas: vale o mais recente, completado com o outro."""
    atual = _agregado_do_objeto(existente, ag)
    campos = diferencas(atual, ag, ("prestacao_id",))
    vence_gv = bool(ag.quando and existente.atualizado_em and ag.quando > existente.atualizado_em)
    vencedor, outro = (ag, atual) if vence_gv else (atual, ag)
    novos = dict(vencedor.campos)
    preenchidos = preencher_vazios(Agregado(campos=novos), outro)
    if vence_gv or preenchidos:
        RelatorioTecnico.objects.filter(pk=existente.pk).update(
            **{k: v for k, v in novos.items() if k != "prestacao_id"})
    ctx.relatorio.conta("relatorio_tecnico", "criado_nos_dois_juntado")
    if campos:
        ctx.relatorio.revisar("relatorio_tecnico", f"relatório criado nos dois sistemas: valeu o "
                              f"{'GV' if vence_gv else 'EV'} (o mais recente), vazios "
                              "completados com o outro", destino_pk=existente.pk, gv_pk=r["id"],
                              campos=campos)


# ============================================================================ anexos e vias
UNICOS = ("rt_assinado", "db_assinado")


def _anexos(ctx: Contexto) -> None:
    rel = ctx.relatorio
    apagados_no_gv: list[int] = []
    for s in ("ev", "gv"):
        reg = registro(ctx, t("anexo", "gv")) if s == "gv" else {}
        for a in tab(ctx, s, t("anexo", s)):
            tabela = t("anexo", s)
            if s == "gv" and str(a["id"]) in reg:
                ev_pk = reg[str(a["id"])][0]
                alvo = destino_com_modelo("ev", t("anexo", "ev"), ev_pk)
                if alvo is not None and ctx.destino("gv", tabela, a["id"]) is None:
                    _mapear_rotulo(ctx, "gv", tabela, a["id"], alvo)
                rel.conta("anexo_prestacao", "mapeado_pelo_registro_ev")
                continue
            if ctx.destino(s, tabela, a["id"]) is not None:
                rel.conta("anexo_prestacao", "ja_mapeado")
                continue
            destino = _anexo(ctx, s, a)
            if destino is not None and s == "ev" and _apagado_no_gv(ctx, "anexo", a["id"]):
                apagados_no_gv.append(destino)
    _marcar_apagados_no_gv(ctx, apagados_no_gv)
    _um_em_vigor(ctx)


def _mapear_rotulo(ctx: Contexto, sistema: str, tabela: str, pk: Any,
                   alvo: tuple[str, int]) -> None:
    modelo = ViaAssinada if alvo[0].endswith("ViaAssinada") else AnexoPrestacao
    ctx.mapear(sistema, tabela, pk, modelo.objects.get(pk=alvo[1]), criado=False)


def _arquivo_do_anexo(ctx: Contexto, s: str, a: dict, coluna: str) -> Any:
    """O arquivo do anexo; a cópia do EV que falta no backup cai para o arquivo do GV."""
    arq = arquivo(ctx, s, a.get(coluna), entidade="anexo_prestacao", tabela=t("anexo", s),
                  origem_pk=a["id"])
    if (arq is None or not arq.existe) and s == "ev":
        gv_pk = inverso(ctx, t("anexo", "gv")).get(str(a["id"]))
        gv = por_id(ctx, "gv", t("anexo", "gv")).get(gv_pk) if gv_pk else None
        if gv is not None:
            outro = arquivo(ctx, "gv", gv.get(coluna), entidade="anexo_prestacao",
                            tabela=t("anexo", "gv"), origem_pk=gv["id"])
            if outro is not None and outro.existe:
                return outro
    return arq


def _anexo(ctx: Contexto, s: str, a: dict) -> int | None:
    rel = ctx.relatorio
    tabela = t("anexo", s)
    prestacao = _mapa(ctx, "prestacao", s, a.get("prestacao_id"))
    tipo = (a.get("tipo") or "").strip().lower()
    if prestacao is None:
        rel.conta("anexo_prestacao", "ignorado")
        rel.revisar("anexo_prestacao", "anexo sem prestação migrada", sistema=s, tabela=tabela,
                    origem_pk=a["id"])
        return None
    if tipo == "oficio_assinado":
        _via_do_oficio(ctx, s, a, prestacao)
        return None
    if tipo not in AnexoPrestacao.Tipo.values:
        rel.conta("anexo_prestacao", "ignorado")
        rel.revisar("anexo_prestacao", f"tipo de anexo desconhecido ({tipo})", sistema=s,
                    tabela=tabela, origem_pk=a["id"])
        return None
    servidor = _mapa(ctx, "servidor", s, a.get("servidor_prestacao_id"))
    if tipo in ("despacho", "db_assinado"):
        if servidor is not None:
            rel.conta("anexo_prestacao", "dono_servidor_descartado")
        servidor = None
    elif servidor is None:
        rel.conta("anexo_prestacao", "ignorado")
        rel.revisar("anexo_prestacao", "comprovante/RT assinado sem prestação do servidor "
                    "migrada", sistema=s, tabela=tabela, origem_pk=a["id"])
        return None
    arq = _arquivo_do_anexo(ctx, s, a, "arquivo")
    if arq is None or not arq.existe:
        rel.conta("anexo_prestacao", "sem_arquivo_no_backup")
        return None
    mesmo = AnexoPrestacao.objects.filter(prestacao_id=prestacao, tipo=tipo, servidor_id=servidor,
                                          sha256=arq.sha256).first()
    if mesmo is not None:
        ctx.mapear(s, tabela, a["id"], mesmo, criado=False)
        rel.conta("anexo_prestacao", "casado_por_chave")
        return None
    valor = a.get("valor")
    operacao = (a.get("operacao") or "").strip().lower()
    motivo = (a.get("removido_motivo") or "").strip().lower()
    anexo = AnexoPrestacao.objects.create(
        prestacao_id=prestacao, servidor_id=servidor, tipo=tipo, arquivo=arq.nome,
        nome_original=texto(a.get("nome_original"), 255), sha256=arq.sha256,
        tamanho=arq.tamanho, valor=valor if valor is not None and valor > 0 else None,
        data_operacao=a.get("data_operacao"),
        operacao=operacao if operacao in AnexoPrestacao.Operacao.values else "",
        enviado_por_id=ctx.usuario_migracao.pk, removido_em=a.get("removido_em"),
        removido_motivo=(motivo if motivo in AnexoPrestacao.Removido.values else "excluido")
        if a.get("removido_em") else "")
    preservar_datas(AnexoPrestacao, anexo.pk, enviado_em=a.get("criado_em"))
    ctx.mapear(s, tabela, a["id"], anexo, criado=True)
    rel.conta("anexo_prestacao", "criado" if s == "ev" else "criado_so_no_gv")
    return anexo.pk


def _via_do_oficio(ctx: Contexto, s: str, a: dict, prestacao: int) -> None:
    """O ofício assinado anexado à prestação é a via assinada do próprio ofício: guarda-se o
    original (sem o carimbo desenhado pelo sistema antigo)."""
    coluna = "arquivo_original" if (a.get("arquivo_original") or "").strip() else "arquivo"
    if coluna == "arquivo":
        ctx.relatorio.conta("via_assinada_prestacao", "sem_original_usou_o_carimbado")
    arq = _arquivo_do_anexo(ctx, s, a, coluna)
    oficio = PrestacaoContas.objects.filter(pk=prestacao).values_list("oficio_id",
                                                                       flat=True).first()
    revogada = a.get("removido_em")
    if s == "ev" and revogada is None and _apagado_no_gv(ctx, "anexo", a["id"]):
        revogada = timezone.now()
    inserir_via(ctx, "via_assinada_prestacao", dono={"tipo": "oficio", "oficio_id": oficio},
                arq=arq, nome_original=texto(a.get("nome_original")),
                enviado_em=a.get("criado_em"), enviado_por_id=ctx.usuario_migracao.pk,
                revogada_em=revogada, origem=[(s, t("anexo", s), a["id"])])


def _marcar_apagados_no_gv(ctx: Contexto, ids: list[int]) -> None:
    """Anexo que o GV apagou depois da carga (o EV ainda tinha): removido agora — a guarda de
    30 dias conta da migração, não da data antiga."""
    for anexo in AnexoPrestacao.objects.filter(pk__in=ids, removido_em__isnull=True):
        mais_novo = AnexoPrestacao.objects.filter(
            prestacao_id=anexo.prestacao_id, tipo=anexo.tipo, servidor_id=anexo.servidor_id,
            enviado_em__gt=anexo.enviado_em).exclude(pk=anexo.pk).exists()
        AnexoPrestacao.objects.filter(pk=anexo.pk).update(
            removido_em=timezone.now(), removido_motivo="substituido" if mais_novo
            else "excluido")
        ctx.relatorio.conta("anexo_prestacao", "apagado_no_gv_removido")


def _um_em_vigor(ctx: Contexto) -> None:
    """RT assinado (por servidor) e diário assinado (por prestação): um só em vigor, o mais
    recente; os anteriores ficam "substituídos" (o arquivo fica)."""
    grupos: dict[tuple[int, str, int | None], list[AnexoPrestacao]] = {}
    for a in AnexoPrestacao.objects.filter(tipo__in=UNICOS, removido_em__isnull=True).order_by(
            "enviado_em", "pk"):
        grupos.setdefault((a.prestacao_id, a.tipo, a.servidor_id), []).append(a)
    for lista in grupos.values():
        for velho in lista[:-1]:
            AnexoPrestacao.objects.filter(pk=velho.pk).update(removido_em=timezone.now(),
                                                              removido_motivo="substituido")
            ctx.relatorio.conta("anexo_prestacao", "substituido_pelo_mais_recente")
            ctx.relatorio.revisar("anexo_prestacao", "dois em vigor do mesmo tipo e dono (um "
                                  "de cada sistema): ficou o mais recente", destino_pk=velho.pk,
                                  mantido_pk=lista[-1].pk)


# ============================================================================ carimbos
def _carimbos(ctx: Contexto) -> None:
    rel = ctx.relatorio
    for s in ("ev", "gv"):
        reg = registro(ctx, t("carimbo", "gv")) if s == "gv" else {}
        for c in tab(ctx, s, t("carimbo", s)):
            tabela = t("carimbo", s)
            if s == "gv" and str(c["id"]) in reg:
                continue   # a cópia do EV representa a linha
            if ctx.destino(s, tabela, c["id"]) is not None:
                rel.conta("carimbo", "ja_mapeado")
                continue
            if s == "ev" and _apagado_no_gv(ctx, "carimbo", c["id"]):
                rel.conta("carimbo", "apagado_no_gv_nao_migrado")
                continue
            if s == "gv" and not c.get("y"):
                rel.conta("carimbo", "sem_posicao_nao_migrado")
                continue
            alvo = destino_com_modelo(s, t("anexo", s), c.get("anexo_id"))
            servidor = _mapa(ctx, "servidor", s, c.get("servidor_prestacao_id"))
            if alvo is None or not alvo[0].endswith("ViaAssinada") or servidor is None:
                rel.conta("carimbo", "ignorado")
                rel.revisar("carimbo", "carimbo sem via assinada ou servidor migrado", sistema=s,
                            tabela=tabela, origem_pk=c["id"])
                continue
            via = ViaAssinada.objects.get(pk=alvo[1])
            if via.revogada_em is not None:
                rel.conta("carimbo", "via_revogada_nao_migrado")
                continue
            existente = CarimboSolicitacao.objects.filter(via=via, servidor_id=servidor).first()
            if existente is not None:
                ctx.mapear(s, tabela, c["id"], existente, criado=False)
                rel.conta("carimbo", "casado_por_chave")
                continue
            x, y = float(c.get("x") or 0), float(c.get("y") or 0)
            if not (0 <= x <= 1 and 0 <= y <= 1):
                rel.conta("carimbo", "ignorado")
                rel.revisar("carimbo", "posição fora da página", sistema=s, tabela=tabela,
                            origem_pk=c["id"])
                continue
            carimbo = CarimboSolicitacao.objects.create(
                via=via, servidor_id=servidor, pagina=max(0, c.get("pagina") or 0), x=x, y=y,
                tamanho=float(c.get("tamanho") or 0.012))
            preservar_datas(CarimboSolicitacao, carimbo.pk, atualizado_em=c.get("atualizado_em"))
            ctx.mapear(s, tabela, c["id"], carimbo, criado=True)
            rel.conta("carimbo", "criado" if s == "ev" else "criado_so_no_gv")


# ============================================================================ importações
ESTADO_IMPORTACAO = {"aplicada": 0, "analisada": 1}


def _paginas(texto_paginas: str) -> tuple[int, int] | None:
    partes = [p for p in (texto_paginas or "").replace(" ", "").split("-") if p]
    if not partes or not all(p.isdigit() for p in partes):
        return None
    inicio, fim = int(partes[0]), int(partes[-1])
    return (inicio, fim) if 0 < inicio <= fim else None


def _importacoes(ctx: Contexto) -> None:
    rel = ctx.relatorio
    tabela = t("importacao", "ev")
    linhas = sorted(tab(ctx, "ev", tabela), key=lambda r: (
        ESTADO_IMPORTACAO.get(r.get("situacao") or "", 9), r["id"]))
    for r in linhas:
        if ctx.destino("ev", tabela, r["id"]) is not None:
            rel.conta("importacao", "ja_mapeado")
            continue
        if r.get("situacao") not in ESTADO_IMPORTACAO:
            rel.conta("importacao", "descartada_nao_migrada")
            continue
        dono = usuario(ctx, "ev", r.get("criado_por_id"))
        arq = arquivo(ctx, "ev", r.get("arquivo"), entidade="importacao", tabela=tabela,
                      origem_pk=r["id"])
        if arq is None or not arq.existe:
            rel.conta("importacao", "sem_arquivo_no_backup")
            continue
        sha = (r.get("hash_sha256") or arq.sha256).lower()
        existente = ArquivoImportado.objects.filter(usuario_id=dono, sha256=sha).first()
        if existente is not None:
            ctx.mapear("ev", tabela, r["id"], existente, criado=False)
            rel.conta("importacao", "mesmo_arquivo_de_outra_importacao")
            continue
        plano = r.get("plano") if isinstance(r.get("plano"), dict) else {}
        paginas = plano.get("total_paginas") if isinstance(plano, dict) else None
        imp = ArquivoImportado.objects.create(
            usuario_id=dono, nome=texto(r.get("nome_original"), 255) or "importacao",
            sha256=sha, original=arq.nome, estado="concluido",
            concluido_em=r.get("aplicado_em") or r.get("criado_em"),
            paginas=min(int(paginas), 32767) if isinstance(paginas, int) and paginas > 0 else 0)
        preservar_datas(ArquivoImportado, imp.pk, criado_em=r.get("criado_em"))
        ctx.mapear("ev", tabela, r["id"], imp, criado=True)
        rel.conta("importacao", "criado")
    _partes(ctx)


def _partes(ctx: Contexto) -> None:
    rel = ctx.relatorio
    t_anexo = t("anexo", "ev")
    t_parte = f"{t_anexo}.importacao"
    importacoes = por_id(ctx, "ev", t("importacao", "ev"))
    for a in tab(ctx, "ev", t_anexo):
        if a.get("importacao_id") is None:
            continue
        if ctx.destino("ev", t_parte, a["id"]) is not None:
            rel.conta("parte_importada", "ja_mapeado")
            continue
        imp = ctx.destino_int("ev", t("importacao", "ev"), a["importacao_id"])
        alvo = destino_com_modelo("ev", t_anexo, a["id"])
        paginas = _paginas(a.get("paginas_origem") or "")
        if imp is None or alvo is None or paginas is None:
            rel.conta("parte_importada", "ignorado")
            continue
        if ParteImportada.objects.filter(importacao_id=imp, inicio=paginas[0]).exists():
            rel.conta("parte_importada", "pagina_ja_usada")
            continue
        via = alvo[1] if alvo[0].endswith("ViaAssinada") else None
        dono_arq = (ViaAssinada.objects.get(pk=via) if via
                    else AnexoPrestacao.objects.get(pk=alvo[1]))
        r = importacoes.get(str(a["importacao_id"]), {})
        parte = ParteImportada.objects.create(
            importacao_id=imp, inicio=paginas[0], fim=paginas[1],
            tipo=(a.get("tipo") or "")[:20], arquivo=dono_arq.arquivo.name,
            sha256=dono_arq.sha256, candidatos=[], estado="anexado", via_id=via,
            anexo_id=None if via else alvo[1],
            aplicado_em=r.get("aplicado_em") or a.get("criado_em"))
        ctx.mapear("ev", t_parte, a["id"], parte, criado=True)
        rel.conta("parte_importada", "criado")


# ============================================================================ lacunas
def _lacunas(ctx: Contexto) -> None:
    rel = ctx.relatorio
    for sistema, tabela in (("ev", "viagens_prestacoes_lancamentodiariocampo"),
                            ("ev", "viagens_prestacoes_linkdiariocampo"),
                            ("gv", "prestacoes_contas_assinaturadocumento"),
                            ("gv", "protocolos_protocolo")):
        n = len(tab(ctx, sistema, tabela))
        if n:
            rel.conta("lacuna", tabela, n)


# ============================================================================ etapa
def executar(ctx: Contexto) -> None:
    cargas = [
        Carga("prestacao", PrestacaoContas, t("prestacao", "ev"), t("prestacao", "gv"),
              _construir_prestacao, _criar_prestacao, chave_natural=_prestacao_chave),
        Carga("prestacao_servidor", PrestacaoServidor, t("servidor", "ev"), t("servidor", "gv"),
              _construir_servidor, _criar_servidor, chave_natural=_servidor_chave,
              preencher_vazios=True, conferir_apagados=False),
        Carga("diario_bordo", DiarioBordo, t("diario", "ev"), t("diario", "gv"),
              _construir_diario, _criar_diario, gv_alterado=_diario_gv_alterado,
              ev_alterado=_diario_ev_alterado, chave_natural=_diario_chave,
              fundir=_fundir_diario, preencher_vazios=True, conferir_apagados=False),
        Carga("relatorio_tecnico", RelatorioTecnico, t("rt", "ev"), t("rt", "gv"),
              _construir_rt, _criar_rt, chave_natural=_rt_chave, fundir=_fundir_rt,
              preencher_vazios=True, conferir_apagados=False),
    ]
    for c in cargas:
        executar_carga(ctx, c)
    _anexos(ctx)
    _carimbos(ctx)
    _importacoes(ctx)
    _lacunas(ctx)
