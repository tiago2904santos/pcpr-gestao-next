"""Etapa 4 — eventos: solicitações de evento (serviços, equipes, anexos, movimentos,
lembretes, viagens geradas), o mapa dos serviços antigos e as notificações.

Regras (docs da migração, 04-eventos-coffee):

* Só o EV (Eventos Sociais) tem estes módulos; o GV não tem nenhuma destas tabelas.
* Os catálogos (tipo de evento, serviço → atividade do plano, equipe, órgão, unidade móvel,
  texto de despacho) já vieram na etapa de cadastros: aqui só se resolvem pelo `MapaLegado`.
* A solicitação PRESERVA o id do legado (#103–#224): os textos, documentos e avisos que citam
  "Solicitação #N" continuam certos. Id já ocupado no destino → id novo e conferência. No fim,
  `setval` da sequência.
* `SolicitacaoServico.nome_registrado` guarda o nome do serviço no legado (não o canônico).
* Movimentos "ATUALIZACAO" e "IMPORTACAO" usam as ações novas (G6); a lista de campos
  alterados (`alteracoes`) vira texto na observação, uma linha por campo.
* Notificações: só as 35 de solicitação (o link é reescrito para a rota nova); os 28 resumos
  das rotinas antigas ficam de fora (G7).
* Status e decisão incoerentes, decisão sem data/autor e unidade móvel sem a unidade vêm como
  estão e vão para a conferência (G10). Total de servidores vazio vira 0 (G11).
* Nada de dado pessoal no relatório: só ids, contagens, nomes de campos e motivos.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from django.core.management.color import no_style
from django.db import IntegrityError, connection, models, transaction
from django.db.models.functions import Lower
from django.urls import reverse

from gestao.eventos.models import (
    AnexoSolicitacao,
    Lembrete,
    Movimento,
    ServicoLegado,
    Solicitacao,
    SolicitacaoEquipe,
    SolicitacaoServico,
    ViagemGerada,
)
from gestao.plataforma.models import Notificacao

from ..contexto import Contexto
from .comum import (
    _restricao,
    arquivo,
    caminho_no_backup,
    fk,
    por_id,
    preservar_datas,
    tab,
    texto,
    usuario,
)

# Tabelas de origem (só EV).
TE = {
    "solicitacao": "solicitacoes_solicitacaoevento",
    "servico": "solicitacoes_solicitacaoeventoservico",
    "equipe": "solicitacoes_solicitacaoeventoequipe",
    "anexo": "solicitacoes_anexosolicitacao",
    "historico": "solicitacoes_historicosolicitacao",
    "lembrete": "solicitacoes_lembretesolicitacao",
    "juntadas": "viagens_viagem_viagem_solicitacoes_juntadas",
    "viagem": "viagens_viagem_viagem",
    "notificacao": "core_notificacao",
    # catálogos (mapeados pela etapa de cadastros)
    "cat_servico": "cadastros_servico",
    "cat_tipo": "cadastros_tipoevento",
    "cat_orgao": "cadastros_orgaoresponsavel",
    "cat_equipe": "cadastros_equipe",
    "cat_unidade_movel": "cadastros_unidademovel",
}

STATUS = {"RASCUNHO": "rascunho", "AGUARDANDO_DESPACHO": "aguardando_despacho",
          "DEVOLVIDA": "devolvida", "DEFERIDA_EM_ANDAMENTO": "deferida", "ATENDIDA": "atendida",
          "NAO_ATENDIDA": "nao_atendida", "CANCELADA": "cancelada"}
DECISAO = {"PENDENTE": "pendente", "ATENDER": "atender", "NAO_ATENDER": "nao_atender",
           "CANCELADO": "cancelado"}
OPERACAO = {"DIARIA": "diaria", "EXTRAJORNADA": "extrajornada"}
ACAO = {"CRIACAO": "criacao", "ENVIO": "envio", "DEVOLUCAO": "devolucao", "REENVIO": "reenvio",
        "AJUSTE_DG": "ajuste_dg", "DECISAO": "decisao", "CONCLUSAO": "conclusao",
        "CANCELAMENTO": "cancelamento", "TRANSFERENCIA": "transferencia", "ANEXO": "anexo",
        "VIAGEM": "viagem", "ATUALIZACAO": "atualizacao", "IMPORTACAO": "importacao"}
LEMBRETE = {"CONFIRMAR_ATENDIMENTO": "confirmar_atendimento",
            "DESPACHO_PROXIMO": "despacho_proximo", "DEVOLUCAO_PARADA": "devolucao_parada"}

# Decisão da DG coerente com cada status (G10). Cancelada vale com qualquer decisão: o evento
# pode ser cancelado antes ou depois do despacho.
DECISOES_COERENTES = {"rascunho": {"pendente"}, "aguardando_despacho": {"pendente"},
                      "devolvida": {"pendente"}, "deferida": {"atender"},
                      "atendida": {"atender"}, "nao_atendida": {"nao_atender"}}

# "/solicitacoes/N/editar/#ancora" do sistema anterior.
LINK_ANTIGO = re.compile(r"^/solicitacoes/(\d+)/editar/?(#[\w-]+)?$")
CRITERIO_SERVICO = "importacao_ev"


# ---------------------------------------------------------------------------- utilitários
def enum(mapa: dict[str, str], valor: Any, campo: str, notas: list[str]) -> str:
    bruto = texto(valor).upper()
    if not bruto:
        return ""
    if bruto not in mapa:
        notas.append(f"{campo}: valor desconhecido no legado")
        return bruto.lower()
    return mapa[bruto]


def diff_em_texto(alteracoes: Any) -> str:
    """`alteracoes` do legado ([{campo, antes, depois}]) → "campo: antes → depois", uma linha
    por campo (G6). Vazio vira "—"."""
    if not isinstance(alteracoes, list):
        return ""
    linhas = []
    for item in alteracoes:
        if not isinstance(item, dict):
            continue
        antes, depois = (texto(item.get(k)) or "—" for k in ("antes", "depois"))
        linhas.append(f"{texto(item.get('campo')) or '?'}: {antes} → {depois}")
    return "\n".join(linhas)


def observacao_movimento(observacao: Any, alteracoes: Any) -> str:
    partes = [p for p in (texto(observacao), diff_em_texto(alteracoes)) if p]
    return "\n".join(partes)


def reescrever_link(link: Any, destino_da_solicitacao: Any) -> tuple[str, bool]:
    """Link do sistema anterior → rota nova. Devolve (link, reescrito). "/" e "" ficam."""
    bruto = texto(link)
    m = LINK_ANTIGO.match(bruto)
    if m is None:
        return bruto, False
    alvo = destino_da_solicitacao(m.group(1))
    if alvo is None:
        return "", False
    return reverse("eventos:solicitacao", args=[alvo]) + (m.group(2) or ""), True


def assinatura_confere(caminho: Path | None, extensao: str) -> bool | None:
    """Conteúdo × extensão (só PDF e PNG; outros: None = não conferido)."""
    esperado = {".pdf": b"%PDF", ".png": b"\x89PNG"}.get(extensao.lower())
    if esperado is None or caminho is None:
        return None
    with caminho.open("rb") as f:
        return f.read(len(esperado)) == esperado


def conferir_assinatura(ctx: Contexto, relativo: str, entidade: str, tabela: str,
                        origem_pk: Any) -> None:
    caminho = caminho_no_backup(ctx.midia_ev, relativo.strip().lstrip("/"))
    ok = assinatura_confere(caminho, Path(relativo).suffix)
    if ok is False:
        ctx.relatorio.conta("arquivo", "assinatura_diverge_da_extensao")
        ctx.relatorio.revisar(entidade, "conteúdo do arquivo não confere com a extensão",
                              sistema="ev", tabela=tabela, origem_pk=str(origem_pk))
    elif ok:
        ctx.relatorio.conta("arquivo", "assinatura_conferida")


def setval(modelo: type[models.Model]) -> None:
    """Sequência do id depois do maior id (o id do legado foi preservado)."""
    with connection.cursor() as cur:
        for sql in connection.ops.sequence_reset_sql(no_style(), [modelo]):
            cur.execute(sql)


def _novo(ctx: Contexto, entidade: str, tabela: str, pk: Any) -> bool:
    """Ainda sem correspondência (senão conta como já mapeado)."""
    if ctx.destino("ev", tabela, pk) is not None:
        ctx.relatorio.conta(entidade, "ja_mapeado")
        return False
    return True


def _criar(ctx: Contexto, entidade: str, tabela: str, pk: Any, modelo: type[models.Model],
           campos: dict[str, Any], **datas_: datetime | None) -> models.Model | None:
    """Cria (com savepoint), preserva as datas do legado e grava o mapa."""
    try:
        with transaction.atomic():
            obj = modelo._default_manager.create(**campos)
    except IntegrityError as erro:
        ctx.relatorio.conta(entidade, "invalido")
        ctx.relatorio.revisar(entidade, "restrição do banco recusou o registro", sistema="ev",
                              tabela=tabela, origem_pk=str(pk), restricao=_restricao(erro))
        return None
    preservar_datas(modelo, obj.pk, **datas_)
    ctx.mapear("ev", tabela, pk, obj, criado=True)
    ctx.relatorio.conta(entidade, "criado")
    return obj


# ---------------------------------------------------------------------------- solicitações
def _campos_solicitacao(ctx: Contexto, r: dict, notas: list[str]) -> dict[str, Any]:
    status = enum(STATUS, r["status"], "status", notas)
    decisao = enum(DECISAO, r["decisao_dg"], "decisao_dg", notas) or "pendente"
    qtd = r.get("quantidade_servidores")
    return {
        "status": status or "rascunho", "decisao_dg": decisao,
        "tipo_operacao": enum(OPERACAO, r.get("tipo_operacao"), "tipo_operacao", notas)
        or "diaria",
        "data_solicitacao": r["data_solicitacao"],
        "data_inicio_evento": r.get("data_inicio_evento"),
        "data_fim_evento": r.get("data_fim_evento"),
        "municipio_id": fk(ctx, "ev", "municipio", r.get("municipio_id"), notas, "municipio"),
        "tipo_evento_id": _catalogo(ctx, "cat_tipo", r.get("tipo_evento_id"), notas,
                                    "tipo_evento"),
        "orgao_responsavel_id": _catalogo(ctx, "cat_orgao", r.get("orgao_responsavel_id"),
                                          notas, "orgao_responsavel"),
        "unidade_movel": bool(r.get("unidade_movel")),
        "unidade_movel_designada_id": _catalogo(ctx, "cat_unidade_movel",
                                                r.get("unidade_movel_designada_id"), notas,
                                                "unidade_movel_designada"),
        "solicitante_nome": texto(r.get("solicitante_nome"), 150),
        "solicitante_cargo_unidade": texto(r.get("solicitante_cargo_unidade"), 255),
        "contato": texto(r.get("contato"), 100),
        "local_evento": texto(r.get("local_evento"), 255),
        "endereco": texto(r.get("endereco"), 255),
        "bairro": texto(r.get("bairro"), 120),
        "cep": texto(r.get("cep"), 9),
        "protocolo": texto(r.get("protocolo"), 20),
        "descricao_complementar": r.get("descricao_complementar") or "",
        "quantidade_servidores": qtd if qtd is not None else 0,
        "quantidade_cin": r.get("quantidade_cin"),
        "motorista_id": fk(ctx, "ev", "servidor", r.get("motorista_id"), notas, "motorista"),
        "observacoes_dg": r.get("observacoes_dg") or "",
        "decidido_por_id": (usuario(ctx, "ev", r["decidido_por_id"])
                            if r.get("decidido_por_id") is not None else None),
        "decidido_em": r.get("decidido_em"),
        "criado_por_id": usuario(ctx, "ev", r.get("criado_por_id")),
    }


def _catalogo(ctx: Contexto, chave: str, pk: Any, notas: list[str], campo: str) -> int | None:
    if pk is None:
        return None
    alvo = ctx.destino_int("ev", TE[chave], pk)
    if alvo is None:
        notas.append(f"{campo}: referência sem correspondente ({TE[chave]}:{pk})")
    return alvo


def conferencias_da_solicitacao(campos: dict[str, Any], r: dict,
                                soma_equipes: int | None) -> list[str]:
    """Inconsistências herdadas da planilha, que entram como estão (G10/G11)."""
    motivos = []
    coerentes = DECISOES_COERENTES.get(campos["status"])
    if coerentes is not None and campos["decisao_dg"] not in coerentes:
        motivos.append("status e decisão da DG incoerentes (herdado do legado)")
    if campos["decisao_dg"] != "pendente" and (campos["decidido_em"] is None
                                               or campos["decidido_por_id"] is None):
        motivos.append("decisão da DG sem data ou sem autor (herdado do legado)")
    if campos["unidade_movel"] and campos["unidade_movel_designada_id"] is None:
        motivos.append("unidade móvel marcada sem a unidade designada")
    if r.get("quantidade_servidores") is None:
        motivos.append("total de servidores vazio no legado: entrou 0")
    elif soma_equipes is not None and soma_equipes != r["quantidade_servidores"]:
        motivos.append("total de servidores difere da soma das equipes (vale o do legado)")
    return motivos


def _solicitacoes(ctx: Contexto) -> None:
    rel = ctx.relatorio
    tabela = TE["solicitacao"]
    ctx.precarregar("ev", tabela)
    equipes: dict[int, int] = {}
    for e in tab(ctx, "ev", TE["equipe"]):
        if e.get("quantidade_servidores") is not None:
            equipes[e["solicitacao_id"]] = (equipes.get(e["solicitacao_id"], 0)
                                            + e["quantidade_servidores"])
    preservados = 0
    for r in tab(ctx, "ev", tabela):
        notas: list[str] = []
        campos = _campos_solicitacao(ctx, r, notas)
        for motivo in conferencias_da_solicitacao(campos, r, equipes.get(r["id"], 0)):
            rel.conta("solicitacao_evento_conferir", motivo.split(" (")[0].split(":")[0])
            if ctx.destino("ev", tabela, r["id"]) is None:
                rel.revisar("solicitacao_evento", motivo, sistema="ev", tabela=tabela,
                            origem_pk=str(r["id"]))
        if not _novo(ctx, "solicitacao_evento", tabela, r["id"]):
            continue
        if Solicitacao.objects.filter(pk=r["id"]).exists():
            rel.conta("solicitacao_evento", "id_do_legado_ocupado")
            rel.revisar("solicitacao_evento", "id do legado já ocupado no destino: entrou com "
                        "id novo", sistema="ev", tabela=tabela, origem_pk=str(r["id"]))
        else:
            campos["id"] = r["id"]
            preservados += 1
        obj = _criar(ctx, "solicitacao_evento", tabela, r["id"], Solicitacao, campos,
                     criado_em=r.get("criado_em"), atualizado_em=r.get("atualizado_em"))
        for nota in notas:
            rel.revisar("solicitacao_evento", nota, sistema="ev", tabela=tabela,
                        origem_pk=str(r["id"]), destino_pk=getattr(obj, "pk", None))
    rel.conta("solicitacao_evento", "id_preservado", preservados)
    setval(Solicitacao)


def _destino_solicitacao(ctx: Contexto, pk: Any) -> int | None:
    return ctx.destino_int("ev", TE["solicitacao"], pk)


def _filhos(ctx: Contexto) -> None:
    rel = ctx.relatorio
    nomes_servico = {r["id"]: texto(r["nome"], 255) for r in tab(ctx, "ev", TE["cat_servico"])}
    # Serviços: canônico pelo mapa; o nome do legado fica registrado.
    t = TE["servico"]
    ctx.precarregar("ev", t)
    for r in tab(ctx, "ev", t):
        if not _novo(ctx, "solicitacao_servico", t, r["id"]):
            continue
        sol = _destino_solicitacao(ctx, r["solicitacao_id"])
        servico = ctx.destino_int("ev", TE["cat_servico"], r["servico_id"])
        if sol is None or servico is None:
            rel.conta("solicitacao_servico", "sem_pai_ou_servico")
            rel.revisar("solicitacao_servico", "solicitação ou serviço sem correspondente",
                        sistema="ev", tabela=t, origem_pk=str(r["id"]))
            continue
        _criar(ctx, "solicitacao_servico", t, r["id"], SolicitacaoServico, {
            "solicitacao_id": sol, "servico_id": servico,
            "observacao": texto(r.get("observacao"), 255),
            "nome_registrado": nomes_servico.get(r["servico_id"], "")})
    # Equipes.
    t = TE["equipe"]
    ctx.precarregar("ev", t)
    for r in tab(ctx, "ev", t):
        if not _novo(ctx, "solicitacao_equipe", t, r["id"]):
            continue
        sol = _destino_solicitacao(ctx, r["solicitacao_id"])
        equipe = ctx.destino_int("ev", TE["cat_equipe"], r["equipe_id"])
        if sol is None or equipe is None:
            rel.conta("solicitacao_equipe", "sem_pai_ou_equipe")
            rel.revisar("solicitacao_equipe", "solicitação ou equipe sem correspondente",
                        sistema="ev", tabela=t, origem_pk=str(r["id"]))
            continue
        _criar(ctx, "solicitacao_equipe", t, r["id"], SolicitacaoEquipe, {
            "solicitacao_id": sol, "equipe_id": equipe,
            "quantidade_servidores": r.get("quantidade_servidores"),
            "observacao": texto(r.get("observacao"), 255)})
    _anexos(ctx)
    _movimentos(ctx)
    _lembretes(ctx)
    _viagens_geradas(ctx)


def _anexos(ctx: Contexto) -> None:
    rel = ctx.relatorio
    t = TE["anexo"]
    ctx.precarregar("ev", t)
    for r in tab(ctx, "ev", t):
        if not _novo(ctx, "anexo_solicitacao", t, r["id"]):
            continue
        sol = _destino_solicitacao(ctx, r["solicitacao_id"])
        if sol is None:
            rel.conta("anexo_solicitacao", "sem_pai")
            continue
        arq = arquivo(ctx, "ev", r.get("arquivo"), entidade="anexo_solicitacao", tabela=t,
                      origem_pk=r["id"])
        if arq is not None and arq.existe:
            conferir_assinatura(ctx, arq.origem, "anexo_solicitacao", t, r["id"])
        _criar(ctx, "anexo_solicitacao", t, r["id"], AnexoSolicitacao, {
            "solicitacao_id": sol, "arquivo": arq.nome if arq else "",
            "nome_original": texto(r.get("nome_original"), 255) or "anexo",
            "tamanho": arq.tamanho if arq and arq.existe else (r.get("tamanho") or 0),
            "enviado_por_id": usuario(ctx, "ev", r.get("enviado_por_id"))},
            criado_em=r.get("criado_em"))


def _movimentos(ctx: Contexto) -> None:
    rel = ctx.relatorio
    t = TE["historico"]
    ctx.precarregar("ev", t)
    for r in tab(ctx, "ev", t):
        if not _novo(ctx, "movimento_evento", t, r["id"]):
            continue
        sol = _destino_solicitacao(ctx, r["solicitacao_id"])
        if sol is None:
            rel.conta("movimento_evento", "sem_pai")
            continue
        notas: list[str] = []
        acao = enum(ACAO, r.get("acao"), "acao", notas)
        obj = _criar(ctx, "movimento_evento", t, r["id"], Movimento, {
            "solicitacao_id": sol, "acao": acao,
            "status_anterior": enum(STATUS, r.get("status_anterior"), "status_anterior", notas),
            "status_novo": enum(STATUS, r.get("status_novo"), "status_novo", notas),
            "observacao": observacao_movimento(r.get("observacao"), r.get("alteracoes")),
            "usuario_id": usuario(ctx, "ev", r.get("usuario_id"))},
            em=r.get("criado_em"))
        if obj is not None:
            rel.conta("movimento_evento", f"acao:{acao}")
            if r.get("alteracoes"):
                rel.conta("movimento_evento", "com_campos_alterados_na_observacao")
        for nota in notas:
            rel.revisar("movimento_evento", nota, sistema="ev", tabela=t, origem_pk=str(r["id"]))


def _lembretes(ctx: Contexto) -> None:
    rel = ctx.relatorio
    t = TE["lembrete"]
    ctx.precarregar("ev", t)
    for r in tab(ctx, "ev", t):
        if not _novo(ctx, "lembrete", t, r["id"]):
            continue
        sol = _destino_solicitacao(ctx, r["solicitacao_id"])
        if sol is None:
            rel.conta("lembrete", "sem_pai")
            continue
        notas: list[str] = []
        tipo = enum(LEMBRETE, r.get("tipo"), "tipo", notas)
        existente = Lembrete.objects.filter(solicitacao_id=sol, tipo=tipo,
                                            referencia=r["referencia"]).first()
        if existente is not None:
            ctx.mapear("ev", t, r["id"], existente, criado=False)
            rel.conta("lembrete", "casado_por_chave")
            continue
        _criar(ctx, "lembrete", t, r["id"], Lembrete, {
            "solicitacao_id": sol, "tipo": tipo, "referencia": r["referencia"]},
            enviado_em=r.get("enviado_em"))


def _viagens_geradas(ctx: Contexto) -> None:
    """G9: sem autor nem data no legado → o responsável da solicitação e a criação da viagem."""
    rel = ctx.relatorio
    t = TE["juntadas"]
    ctx.precarregar("ev", t)
    viagens = por_id(ctx, "ev", TE["viagem"])
    for r in tab(ctx, "ev", t):
        if not _novo(ctx, "viagem_gerada", t, r["id"]):
            continue
        sol = _destino_solicitacao(ctx, r["solicitacaoevento_id"])
        viagem = ctx.destino_int("ev", TE["viagem"], r["viagem_id"])
        if sol is None or viagem is None:
            rel.conta("viagem_gerada", "sem_solicitacao_ou_viagem")
            rel.revisar("viagem_gerada", "solicitação ou viagem sem correspondente",
                        sistema="ev", tabela=t, origem_pk=str(r["id"]))
            continue
        existente = ViagemGerada.objects.filter(solicitacao_id=sol, viagem_id=viagem).first()
        if existente is not None:
            ctx.mapear("ev", t, r["id"], existente, criado=False)
            rel.conta("viagem_gerada", "casado_por_chave")
            continue
        dono = Solicitacao.objects.values_list("criado_por_id", flat=True).get(pk=sol)
        legado = viagens.get(str(r["viagem_id"])) or {}
        _criar(ctx, "viagem_gerada", t, r["id"], ViagemGerada, {
            "solicitacao_id": sol, "viagem_id": viagem, "criada_por_id": dono},
            criada_em=legado.get("criado_em") or legado.get("created_at"))


# ---------------------------------------------------------------------------- serviços antigos
def _servicos_legados(ctx: Contexto) -> None:
    """O mapa dos serviços do EV dentro do banco (padrão da migração 0008 de eventos)."""
    rel = ctx.relatorio
    usos: dict[int, list[int]] = {}
    for r in tab(ctx, "ev", TE["servico"]):
        sol = _destino_solicitacao(ctx, r["solicitacao_id"])
        if sol is not None:
            usos.setdefault(r["servico_id"], []).append(sol)
    existentes = {n.lower() for n in ServicoLegado.objects.annotate(n=Lower("nome"))
                  .values_list("n", flat=True)}
    for r in tab(ctx, "ev", TE["cat_servico"]):
        nome = texto(r["nome"], 150)
        canonico = ctx.destino_int("ev", TE["cat_servico"], r["id"])
        if not nome or canonico is None:
            rel.conta("servico_legado", "sem_correspondente")
            continue
        if nome.lower() in existentes:
            rel.conta("servico_legado", "ja_existia")
            continue
        obj = ServicoLegado.objects.create(
            nome=nome, ativo=bool(r.get("ativo", True)), canonico_id=canonico,
            criterio=CRITERIO_SERVICO,
            vinculos_originais={"ev_id": r["id"], "solicitacoes": sorted(usos.get(r["id"], []))})
        preservar_datas(ServicoLegado, obj.pk, criado_em=r.get("criado_em"),
                        atualizado_em=r.get("atualizado_em"))
        existentes.add(nome.lower())
        rel.conta("servico_legado", "criado")


# ---------------------------------------------------------------------------- notificações
def eh_resumo(r: dict) -> bool:
    """Resumo das rotinas antigas ("Resumo de hoje", "Limpeza semanal de arquivos"): sem
    solicitação. Fica de fora (G7)."""
    return r.get("solicitacao_id") is None


def _notificacoes(ctx: Contexto) -> None:
    rel = ctx.relatorio
    t = TE["notificacao"]
    ctx.precarregar("ev", t)
    for r in tab(ctx, "ev", t):
        if eh_resumo(r):
            rel.conta("notificacao", "resumo_ignorado")
            continue
        if not _novo(ctx, "notificacao", t, r["id"]):
            continue
        link, reescrito = reescrever_link(r.get("link"),
                                          lambda pk: _destino_solicitacao(ctx, pk))
        if texto(r.get("link")) and not link:
            rel.conta("notificacao", "link_sem_solicitacao")
            rel.revisar("notificacao", "link para solicitação sem correspondente: ficou vazio",
                        sistema="ev", tabela=t, origem_pk=str(r["id"]))
        obj = _criar(ctx, "notificacao", t, r["id"], Notificacao, {
            "usuario_id": usuario(ctx, "ev", r.get("usuario_id")),
            "titulo": texto(r.get("titulo"), 150), "mensagem": texto(r.get("mensagem"), 255),
            "link": link, "lida": bool(r.get("lida"))}, criada_em=r.get("criada_em"))
        if obj is not None and reescrito:
            rel.conta("notificacao", "link_reescrito")


# ---------------------------------------------------------------------------- etapa
def executar(ctx: Contexto) -> None:
    rel = ctx.relatorio
    if ctx.gv is not None:
        # O GV não tem eventos sociais, coffee nem notificações (o `eventos_evento` dele é a
        # viagem antiga, já trazida pela etapa de viagens).
        for nome in (TE["solicitacao"], "coffee_break_solicitacaocoffeebreak", TE["notificacao"]):
            if ctx.gv.tem_tabela(nome):
                rel.revisar("eventos", "o GV tem uma tabela que esta etapa não lê",
                            sistema="gv", tabela=nome)
    _solicitacoes(ctx)
    _filhos(ctx)
    _servicos_legados(ctx)
    _notificacoes(ctx)
    for nome, alvo in (("demandas_eventos_demandaevento", "palestras"),
                       ("atendimento_imprensa_atendimento", "imprensa"),
                       ("publicacoes_publicacao", "publicacoes")):
        n = len(tab(ctx, "ev", nome))
        if n:
            rel.conta("nao_migrado", alvo, n)
            rel.revisar(alvo, "o legado tem linhas que esta etapa não traz (G15)",
                        sistema="ev", tabela=nome, linhas=n)
