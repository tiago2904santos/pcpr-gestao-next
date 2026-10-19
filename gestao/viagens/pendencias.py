"""As seções de Viagens na aba Pendências da Agenda (`plataforma.pendencias`): os envios
aos servidores (envios manuais pelo WhatsApp), os documentos que ainda não saíram e a
prestação de contas vencida ou vencendo. Registradas no `ready` do app.

Nada aqui é regra nova: cada recorte é o mesmo das telas de origem — "rascunho" é o da
lista de ofícios (`queries.q_do_documento`), "pendente" de OS, termos e planos é o da faixa
"pede atenção" das listas (`atencao_listas`), sem os de viagens com as contas prestadas
(aba "Finalizados"); vencida e vencendo são as abas da prestação de contas
(`prestacao.filtrar`). A visibilidade é a das policies (unidade, permissões); os
documentos só aparecem para quem pode terminá-los.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time
from typing import TypedDict

from django.db.models import Count, Prefetch, Q, QuerySet
from django.urls import reverse
from django.utils import timezone

from gestao.automacao.models import Comunicacao
from gestao.plataforma.pendencias import (
    LIMITE,
    Acao,
    Grupo,
    Item,
    Secao,
    carregar,
    por_urgencia,
    registrar_secao,
)

from . import atencao_listas, envios_manuais, policies, prestacao, queries
from . import termos as termos_mod
from .dominio import prestacao as dominio_prestacao
from .dominio import recorte
from .dominio.envios import telefone_whatsapp
from .linha_lista import DIAS_DE_URGENCIA
from .models import PrestacaoServidor, Trecho

DIAS_PARADO = 2  # envio pendente há mais tempo que isso ganha o selo "Parado há N dias"
TOM_DO_SELO = {"vencido": "perigo", "alerta": "aviso", "ok": "neutro"}


def _plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


class _Selo(TypedDict):
    selo: str
    tom: str


def _selo_inicio(inicio: date | None, hoje: date, verbo: str = "Começa") -> _Selo:
    """O selo de urgência das listas: até `DIAS_DE_URGENCIA` dias antes; já passou, perigo."""
    if inicio is None:
        return {"selo": "", "tom": "neutro"}
    dias = (inicio - hoje).days
    if dias < 0:
        return {"selo": "Data já passou", "tom": "perigo"}
    if dias == 0:
        return {"selo": f"{verbo} hoje", "tom": "aviso"}
    if dias <= DIAS_DE_URGENCIA:
        return {"selo": f"{verbo} em {_plural(dias, 'dia', 'dias')}", "tom": "aviso"}
    return {"selo": "", "tom": "neutro"}


def _data(rotulo: str, d: date | None, vazio: str) -> tuple[str, str]:
    return ("calendar", f"{rotulo} {d:%d/%m/%Y}" if d else vazio)


def _unidade(usuario, obj) -> tuple[tuple[str, str], ...]:
    """Quem vê todas as unidades precisa saber de qual é; os demais só veem a sua."""
    if policies.ve_todas_unidades(usuario) and getattr(obj, "unidade", None):
        return (("building-2", obj.unidade.sigla or obj.unidade.nome),)
    return ()


def _destinos(itens: Iterable) -> str:
    return ", ".join(dict.fromkeys(str(d.municipio) for d in itens))


# ---------------------------------------------------------------- envios aos servidores
def _pode_envios(usuario) -> bool:
    return policies.pode_listar_prestacoes(usuario)


def _envios(usuario, hoje: date) -> list[Grupo]:
    qs = (envios_manuais.pendencias(usuario)
          .filter(situacao=Comunicacao.Situacao.AGUARDANDO_APROVACAO)
          .order_by("criada_em", "pk"))
    linhas, total = carregar(qs)
    itens = []
    for c in linhas:
        criada = timezone.localtime(c.criada_em)
        parado = (hoje - criada.date()).days
        conteudo = ", ".join(c.contexto.get("itens") or []) or "Itens na conferência"
        selo, tom = "", "neutro"
        if not telefone_whatsapp(c.servidor.telefone if c.servidor_id else ""):
            selo, tom = "Sem telefone cadastrado", "perigo"
        elif parado >= DIAS_PARADO:
            selo, tom = f"Parado há {_plural(parado, 'dia', 'dias')}", "aviso"
        itens.append(Item(
            chave=f"envio-{c.pk}", titulo=str(c.servidor) if c.servidor_id else "Servidor",
            url=reverse("viagens:envio_manual", args=[c.contexto["ps"]]),
            acao="Conferir e enviar", rotulo="Ofício", numero=c.contexto.get("oficio", ""),
            fatos=(("files", conteudo), ("clock", f"Pendente desde {criada:%d/%m/%Y}")),
            selo=selo, tom=tom))
    return [Grupo("envios", "Para conferir e enviar pelo WhatsApp", total, itens,
                  ajuda="Baixe os PDFs, abra a conversa do servidor, anexe e confirme "
                        "depois de enviar. Nada é marcado como enviado sozinho.",
                  ver_todos=reverse("viagens:envios_manuais"))]


def _acoes_envios(usuario) -> list[Acao]:
    acoes = []
    if policies.altera_prestacoes(usuario) and envios_manuais.manual():
        acoes.append(Acao("Atualizar pendências", reverse("viagens:atualizar_envios"),
                          "refresh-cw", post=True))
    acoes.append(Acao("Enviados", reverse("viagens:envios_manuais") + "?aba=historico",
                      "history"))
    return acoes


# ---------------------------------------------------------------- documentos a terminar
def _pode_documentos(usuario) -> bool:
    return (policies.edita_oficios(usuario) or policies.edita_ordens(usuario)
            or policies.edita_termos(usuario) or policies.edita_planos(usuario))


def _oficios(usuario, hoje: date) -> Grupo:
    inicio = timezone.make_aware(datetime.combine(hoje, time.min))
    qs = por_urgencia(
        queries.com_primeira_saida(policies.oficios_visiveis(usuario))
        .filter(queries.q_do_documento(recorte.RASCUNHO)), "_saida", inicio
    ).select_related("unidade").prefetch_related(
        Prefetch("trechos", queryset=Trecho.objects.select_related("destino").order_by("ordem")))
    linhas, total = carregar(qs)
    itens = []
    for o in linhas:
        trechos = list(o.trechos.all())
        sede = trechos[0].origem_id if trechos else None
        destinos = ", ".join(dict.fromkeys(str(t.destino) for t in trechos
                                           if t.destino_id != sede))
        saida = timezone.localtime(o._saida).date() if o._saida else None
        itens.append(Item(
            chave=f"oficio-{o.pk}", titulo=destinos or "Sem roteiro",
            url=reverse("viagens:editar", args=[o.pk]), acao="Continuar",
            rotulo="Ofício", numero=o.numero_formatado,
            fatos=(_data("Saída", saida, "Sem data de saída"), *_unidade(usuario, o)),
            **_selo_inicio(saida, hoje, "Sai")))
    return Grupo("oficios", "Ofícios em rascunho", total, itens,
                 ajuda="Termine e emita: o rascunho não vale como documento.",
                 ver_todos=reverse("viagens:oficios") + f"?documento={recorte.RASCUNHO}")


def _ordens(usuario, hoje: date) -> Grupo:
    qs = por_urgencia(
        policies.ordens_visiveis(usuario).filter(atencao_listas.ORDEM.pendente(),
                                                 ~prestacao.prestadas("ordem")),
        "data_inicio", hoje).select_related("unidade").prefetch_related("destinos__municipio")
    linhas, total = carregar(qs)
    itens = [Item(
        chave=f"ordem-{o.pk}", titulo=_destinos(o.destinos.all()) or o.motivo[:80]
        or "Sem destino", url=reverse("viagens:editar_ordem", args=[o.pk]), acao="Continuar",
        rotulo="OS", numero=o.numero_formatado,
        fatos=(_data("Início", o.data_inicio, "Sem período"), *_unidade(usuario, o)),
        **_selo_inicio(o.data_inicio, hoje))
        for o in linhas]
    return Grupo("ordens", "Ordens de serviço não geradas", total, itens,
                 ajuda="Confira a equipe e o período e gere a OS.",
                 ver_todos=reverse("viagens:ordens"))


def _termos(usuario, hoje: date) -> Grupo:
    qs = por_urgencia(
        termos_mod.com_inicio(policies.termos_visiveis(usuario))
        .filter(atencao_listas.TERMO.pendente(), ~prestacao.prestadas("termo")),
        "inicio_efetivo", hoje).select_related("unidade")
    linhas, total = carregar(qs)
    itens = [Item(
        chave=f"termo-{t.pk}", titulo=t.evento or "Termo de autorização",
        url=reverse("viagens:editar_termo", args=[t.pk]), acao="Anexar assinado",
        rotulo="Termo", numero=f"#{t.pk}",
        fatos=(_data("Início", t.inicio_efetivo, "Sem período"), *_unidade(usuario, t)),
        **_selo_inicio(t.inicio_efetivo, hoje)) for t in linhas]
    return Grupo("termos", "Termos sem via assinada", total, itens,
                 ajuda="Gere os termos, colha as assinaturas e anexe a via assinada.",
                 ver_todos=reverse("viagens:termos"))


def _planos(usuario, hoje: date) -> Grupo:
    qs = por_urgencia(
        policies.planos_visiveis(usuario).filter(atencao_listas.PLANO.pendente(),
                                                 ~prestacao.prestadas("plano")),
        "data_inicio", hoje).select_related("unidade").prefetch_related("destinos__municipio")
    linhas, total = carregar(qs)
    itens = [Item(
        chave=f"plano-{p.pk}", titulo=_destinos(p.destinos.all()) or "Sem destino",
        url=reverse("viagens:editar_plano", args=[p.pk]), acao="Continuar",
        rotulo="Plano", numero=p.numero_formatado,
        fatos=(_data("Início", p.data_inicio, "Sem período"), *_unidade(usuario, p)),
        **_selo_inicio(p.data_inicio, hoje))
        for p in linhas]
    return Grupo("planos", "Planos de trabalho não gerados", total, itens,
                 ajuda="Feche o efetivo e as atividades e gere o plano.",
                 ver_todos=reverse("viagens:planos"))


def _documentos(usuario, hoje: date) -> list[Grupo]:
    grupos = []
    if policies.edita_oficios(usuario):
        grupos.append(_oficios(usuario, hoje))
    if policies.edita_ordens(usuario):
        grupos.append(_ordens(usuario, hoje))
    if policies.edita_termos(usuario):
        grupos.append(_termos(usuario, hoje))
    if policies.edita_planos(usuario):
        grupos.append(_planos(usuario, hoje))
    return grupos


# ---------------------------------------------------------------- prestação de contas
def _pode_prestacao(usuario) -> bool:
    return policies.pode_listar_prestacoes(usuario)


def _ids(qs: QuerySet[PrestacaoServidor]) -> list[tuple[int, date | None]]:
    """(pk, prazo de saque) do recorte, o prazo mais antigo primeiro (sem prazo no fim)."""
    linhas = list(qs.select_related(None).values_list("pk", "prazo_limite_saque"))
    return sorted(linhas, key=lambda x: (x[1] is None, x[1] or date.max, x[0]))


GRUPOS_PRESTACAO = (
    ("prestacao_vencida", "Prestação vencida", "Passou o prazo para prestar contas: cobre "
     "o servidor e finalize a prestação."),
    ("saque_vencendo", "Saque vencendo, sem comprovante", "O prazo de saque das diárias "
     "vence em poucos dias e o comprovante ainda não chegou."),
    ("devolvidas", "Devolvidas para correção", "Corrija o que foi apontado e envie de novo."),
)


def _prestacao(usuario, hoje: date) -> list[Grupo]:
    base = policies.prestacoes_visiveis(usuario)
    recortes = {
        "prestacao_vencida": prestacao.filtrar(base, "prestacao_vencida", hoje),
        "saque_vencendo": prestacao.filtrar(prestacao.filtrar(base, "saque_vencendo", hoje),
                                            "sem_comprovante", hoje),
        "devolvidas": prestacao.filtrar(base, "devolvidas", hoje),
    }
    vistos: set[int] = set()
    por_grupo: dict[str, list[tuple[int, date | None]]] = {}
    for chave, _, _ in GRUPOS_PRESTACAO:  # cada servidor no grupo mais urgente em que está
        por_grupo[chave] = [x for x in _ids(recortes[chave]) if x[0] not in vistos]
        vistos.update(pk for pk, _ in por_grupo[chave])
    mostrar = {pk for linhas in por_grupo.values() for pk, _ in linhas[:LIMITE]}
    objetos = ({ps.pk: ps for ps in PrestacaoServidor.objects.filter(pk__in=mostrar)
                .select_related("servidor", "prestacao__oficio__unidade")} if mostrar else {})
    lista = reverse("viagens:prestacoes")
    grupos = []
    for chave, titulo, ajuda in GRUPOS_PRESTACAO:
        itens = []
        for pk, prazo in por_grupo[chave][:LIMITE]:
            ps = objetos[pk]
            if chave == "prestacao_vencida":
                s = dominio_prestacao.selo_da_prestacao(prazo, finalizada=False, hoje=hoje)
            elif chave == "saque_vencendo":
                s = dominio_prestacao.selo_do_saque(prazo, finalizada=False,
                                                    tem_comprovante=False, hoje=hoje)
            else:
                s = dominio_prestacao.Selo("Devolvida", "alerta")
            oficio = ps.prestacao.oficio
            itens.append(Item(
                chave=f"prestacao-{ps.pk}", titulo=ps.servidor.nome,
                url=reverse("viagens:prestacao_equipe", args=[ps.prestacao_id]),
                acao="Abrir a prestação", rotulo="Ofício", numero=oficio.numero_formatado,
                fatos=(_data("Saque até", prazo, "Sem prazo de saque"),
                       *_unidade(usuario, oficio)),
                selo=s.texto if s else "", tom=TOM_DO_SELO.get(s.tom, "neutro") if s else "neutro"))
        grupos.append(Grupo(chave, titulo, len(por_grupo[chave]), itens, ajuda=ajuda,
                            ver_todos=f"{lista}?aba={chave}"))
    return grupos


COBRAR_EM_LOTE = (("sem_solicitacao", "Sem solicitação"), ("sem_comprovante", "Sem comprovante"))


def _acoes_prestacao(usuario) -> list[Acao]:
    """Os recortes "para cobrar em lote" da lista, com o número de agora."""
    base = policies.prestacoes_visiveis(usuario)
    contas = base.aggregate(**{chave: _contar(base, chave) for chave, _ in COBRAR_EM_LOTE})
    lista = reverse("viagens:prestacoes")
    return [Acao(rotulo, f"{lista}?aba={chave}", "filter", contagem=contas[chave])
            for chave, rotulo in COBRAR_EM_LOTE if contas[chave]]


def _contar(base: QuerySet, chave: str) -> Count:
    return Count("pk", filter=Q(pk__in=prestacao.filtrar(base, chave).values("pk")))


def registrar() -> None:
    registrar_secao(Secao(
        "envios", "Envios aos servidores", "send",
        "Mensagem e documentos de cada servidor, para enviar pelo WhatsApp do setor.",
        _pode_envios, _envios, _acoes_envios,
        vazio="Nenhum envio pendente. Quando as diárias forem liberadas ou os documentos "
              "mudarem, o pacote do servidor aparece aqui.", ordem=10))
    registrar_secao(Secao(
        "documentos", "Documentos para terminar", "file-pen-line",
        "Ofícios em rascunho, OS e planos ainda não gerados e termos sem via assinada.",
        _pode_documentos, _documentos,
        vazio="Nenhum documento esperando: tudo o que foi começado já saiu.", ordem=20))
    registrar_secao(Secao(
        "prestacao", "Prestação de contas", "receipt",
        "Prazos vencidos ou vencendo e prestações devolvidas.",
        _pode_prestacao, _prestacao, _acoes_prestacao,
        vazio="Nenhuma prestação vencida, vencendo ou devolvida.", ordem=30))
