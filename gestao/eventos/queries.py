"""Leituras das solicitações de evento: filas e filtros da lista, a linha da lista e o
histórico (paridade com `solicitacoes/views.py` e `presenters.py` da referência)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import cast

from django.db.models import F, Field, Model, Q, QuerySet
from django.db.models.expressions import OrderBy

from gestao.plataforma.auditoria import passos_do_registro

from . import dominio, policies
from .models import Solicitacao

FILAS = (("", "Todas"), ("despacho", "Aguardando despacho"),
         ("devolvidas", "Devolvidas para ajuste"),
         ("deferidas", "Deferidas"), ("confirmar", "Confirmar atendimento"),
         ("canceladas", "Canceladas"), ("rascunhos", "Meus rascunhos"), ("minhas", "Minhas"))


def base(usuario) -> QuerySet[Solicitacao]:
    return policies.solicitacoes_visiveis(usuario).select_related(
        "municipio", "tipo_evento", "orgao_responsavel", "unidade_movel_designada", "criado_por")


def filas_visiveis(usuario) -> list[tuple[str, str]]:
    return [(c, r) for c, r in FILAS if c != "despacho" or policies.pode_despachar(usuario)]


def aplicar_fila(qs: QuerySet[Solicitacao], fila: str, usuario, hoje: date) -> QuerySet:
    if fila == "despacho":
        return qs.filter(status=dominio.AGUARDANDO)
    if fila == "devolvidas":
        return qs.filter(status=dominio.DEVOLVIDA)
    if fila == "deferidas":
        return qs.filter(status=dominio.DEFERIDA)
    if fila == "confirmar":
        return qs.filter(status=dominio.DEFERIDA).filter(
            Q(data_fim_evento__lt=hoje) | Q(data_fim_evento__isnull=True,
                                             data_inicio_evento__lt=hoje))
    if fila == "canceladas":
        return qs.filter(status=dominio.CANCELADA)
    if fila == "rascunhos":
        return qs.filter(status=dominio.RASCUNHO, criado_por=usuario)
    if fila == "minhas":
        return qs.filter(criado_por=usuario)
    if fila == "proximos":
        return qs.filter(data_inicio_evento__gte=hoje,
                         data_inicio_evento__lte=hoje + timedelta(days=30)).exclude(
            status__in=(dominio.CANCELADA, dominio.NAO_ATENDIDA))
    if fila == "deferidas_ano":
        return qs.filter(status__in=(dominio.DEFERIDA, dominio.ATENDIDA),
                         data_solicitacao__year=hoje.year)
    return qs


@dataclass
class Filtros:
    q: str = ""
    fila: str = ""
    status: str = ""
    inicio: date | None = None
    fim: date | None = None
    municipio: int | None = None
    tipo: int | None = None

    @property
    def ativos(self) -> int:
        return sum(1 for v in (self.inicio, self.fim, self.municipio, self.tipo) if v)


def _data(texto: str | None) -> date | None:
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime((texto or "").strip(), formato).date()
        except ValueError:
            continue
    return None


def _inteiro(texto: str | None) -> int | None:
    return int(texto) if texto and re.fullmatch(r"[0-9]{1,9}", texto) else None


def ler_filtros(get) -> Filtros:
    fila = get.get("fila") or ""
    status = get.get("status") or ""
    return Filtros(q=" ".join((get.get("q") or "").split())[:100],
                   fila=fila if fila in {c for c, _r in FILAS} | {"proximos", "deferidas_ano"}
                   else "", status=status if status in dominio.ROTULOS else "",
                   inicio=_data(get.get("inicio")), fim=_data(get.get("fim")),
                   municipio=_inteiro(get.get("municipio")), tipo=_inteiro(get.get("tipo")))


# "Ordenar por" (referência: `?ordem=`): chave → (rótulo, campos). A fila do despacho vem,
# por padrão, pelo evento mais próximo (a ordem do "Registrar e abrir a próxima").
ORDENS: dict[str, tuple[str, tuple[str | OrderBy, ...]]] = {
    "-data": ("Solicitação mais recente", ("-data_solicitacao", "-criado_em")),
    "data": ("Solicitação mais antiga", ("data_solicitacao", "criado_em")),
    "periodo": ("Evento mais próximo", (F("data_inicio_evento").asc(nulls_last=True), "pk")),
    "-periodo": ("Evento mais distante", (F("data_inicio_evento").desc(nulls_last=True), "-pk")),
    "municipio": ("Município (A–Z)", ("municipio__nome", "-data_solicitacao")),
    "tipo": ("Tipo de evento (A–Z)", ("tipo_evento__nome", "-data_solicitacao")),
    "solicitante": ("Solicitante (A–Z)", ("solicitante_nome", "-data_solicitacao")),
    "numero": ("Número", ("-pk",)),
}


def ordem_de(texto: str | None, fila: str = "") -> str:
    padrao = "periodo" if fila == "despacho" else "-data"
    return texto if texto in ORDENS else padrao


def ordenar(qs: QuerySet, ordem: str) -> QuerySet:
    return qs.order_by(*ORDENS[ordem][1])


def filtrar(usuario, f: Filtros, hoje: date, *, com_fila: bool = True) -> QuerySet:
    qs = base(usuario)
    if com_fila:
        qs = aplicar_fila(qs, f.fila, usuario, hoje)
    if f.q:
        termo = f.q.lstrip("#")
        busca = (Q(solicitante_nome__unaccent__icontains=f.q)
                 | Q(local_evento__unaccent__icontains=f.q)
                 | Q(municipio__nome__unaccent__icontains=f.q)
                 | Q(tipo_evento__nome__unaccent__icontains=f.q)
                 | Q(orgao_responsavel__nome__unaccent__icontains=f.q))
        digitos = re.sub(r"\D", "", f.q)
        if re.fullmatch(r"[0-9]{1,9}", termo):
            busca |= Q(pk=int(termo))
        if len(digitos) >= 5:  # protocolo com ou sem os pontos
            busca |= Q(protocolo__regex=r"\D?".join(digitos))
        qs = qs.filter(busca)
    if f.status:
        qs = qs.filter(status=f.status)
    if f.inicio:
        qs = qs.filter(data_inicio_evento__gte=f.inicio)
    if f.fim:
        qs = qs.filter(data_inicio_evento__lte=f.fim)
    if f.municipio:
        qs = qs.filter(municipio_id=f.municipio)
    if f.tipo:
        qs = qs.filter(tipo_evento_id=f.tipo)
    return qs


@dataclass
class Linha:
    s: Solicitacao
    selo: dominio.Selo | None
    em_cima: str
    fatos: list[tuple[str, str, str, bool]] = field(default_factory=list)
    coffee: str = ""  # o "Pedir coffee break" da linha (a view preenche)


def periodo(s: Solicitacao) -> str:
    if not s.data_inicio_evento:
        return ""
    fim = s.data_fim_evento or s.data_inicio_evento
    if fim == s.data_inicio_evento:
        return f"{s.data_inicio_evento:%d/%m/%Y}"
    return f"{s.data_inicio_evento:%d/%m} a {fim:%d/%m/%Y}"


JANELA_VIZINHOS = timedelta(days=30)
FOLGA_VIZINHOS = timedelta(days=2)  # encostadas: no máximo um dia livre entre uma e outra


def vizinhos(usuario, s: Solicitacao) -> list[Solicitacao]:
    """As outras solicitações da mesma cidade cujas datas encostam nesta (sobrepostas ou
    com até um dia livre entre elas), em cadeia (06, 07 e 08–09 formam um bloco só), dentro
    de 30 dias: o que dá para atender numa viagem só. Sem rascunho, recusada ou cancelada."""
    if not (s.municipio_id and s.data_inicio_evento):
        return []
    inicio, fim = s.data_inicio_evento, s.data_fim_evento or s.data_inicio_evento
    candidatos = list(
        policies.solicitacoes_visiveis(usuario)
        .filter(municipio_id=s.municipio_id, data_inicio_evento__isnull=False,
                data_inicio_evento__lte=fim + JANELA_VIZINHOS,
                data_inicio_evento__gte=inicio - JANELA_VIZINHOS)
        .exclude(pk=s.pk).exclude(status__in=(dominio.RASCUNHO, dominio.NAO_ATENDIDA,
                                              dominio.CANCELADA))
        .order_by("data_inicio_evento", "pk"))
    bloco: list[Solicitacao] = []
    mudou = True
    while mudou:
        mudou = False
        for c in candidatos:
            c_fim = c.data_fim_evento or c.data_inicio_evento
            if c not in bloco and c.data_inicio_evento <= fim + FOLGA_VIZINHOS \
                    and c_fim >= inicio - FOLGA_VIZINHOS:
                bloco.append(c)
                inicio, fim = min(inicio, c.data_inicio_evento), max(fim, c_fim)
                mudou = True
    return sorted(bloco, key=lambda c: (c.data_inicio_evento, c.pk))


def linha(s: Solicitacao, hoje: date) -> Linha:
    local = " — ".join(p for p in (s.local_evento, s.endereco) if p)
    quem = " — ".join(p for p in (s.solicitante_nome, s.solicitante_cargo_unidade) if p)
    um = (s.unidade_movel_designada.nome if s.unidade_movel_designada
          else "Unidade móvel a designar") if s.unidade_movel else ""
    fatos = [("calendar", "Período", periodo(s) or "Sem período", not periodo(s)),
             ("map-pin", "Local", local or "Local não informado", not local),
             ("user-round", "Solicitante", quem or "Sem solicitante", not quem)]
    if um:
        fatos.append(("bus", "Unidade móvel", um, not s.unidade_movel_designada_id))
    fatos.append(("clock", "Solicitada", f"Solicitada em {s.data_solicitacao:%d/%m/%Y}", False))
    return Linha(s, dominio.selo_de_tempo(s.data_inicio_evento, s.data_fim_evento, s.status, hoje),
                 dominio.em_cima_da_hora(s.data_solicitacao, s.data_inicio_evento), fatos)


def titulo(s: Solicitacao) -> str:
    tipo = s.tipo_evento.nome if s.tipo_evento else "Evento"
    return f"{tipo} · {s.municipio.nome}" if s.municipio else tipo


# ---------------------------------------------------------------- histórico
NOMES = {
    "data_solicitacao": "data da solicitação", "data_inicio_evento": "período",
    "data_fim_evento": "período", "municipio_id": "município", "tipo_evento_id": "tipo",
    "solicitante_nome": "solicitante", "solicitante_cargo_unidade": "solicitante",
    "contato": "contato", "orgao_responsavel_id": "órgão", "unidade_movel": "unidade móvel",
    "unidade_movel_designada_id": "unidade móvel", "local_evento": "local",
    "endereco": "local", "bairro": "local", "cep": "local", "protocolo": "protocolo",
    "descricao_complementar": "descrição", "tipo_operacao": "tipo de operação",
    "quantidade_cin": "CIN", "motorista_id": "motorista",
}
FILHAS = {"eventos_solicitacaoservico": "serviços", "eventos_solicitacaoequipe": "equipes"}


@dataclass
class Evento:
    em: datetime
    texto: str
    usuario: object | None
    marca: bool = False
    mudancas: list[tuple[str, str, str]] = field(default_factory=list)  # campo, antes, depois
    # O tipo na linha do tempo das folhas (componentes/historico_folha.html): o ícone e o
    # filtro (Dados, Documentos…) seguem as ações de Viagens.
    acao: str = "dados"

    @property
    def descricao(self) -> str:
        return self.texto


# Movimento da solicitação → ação equivalente na linha do tempo de Viagens.
ACAO_NA_LINHA_DO_TEMPO = {"criacao": "criado", "envio": "emitido", "decisao": "emitido",
                          "conclusao": "emitido", "devolucao": "reaberto",
                          "reenvio": "reaberto", "cancelamento": "cancelado",
                          "anexo": "documento", "transferencia": "viajante",
                          "ajuste_dg": "viajante", "viagem": "documento"}


def _campo(coluna: str) -> Field:
    return cast(Field, Solicitacao._meta.get_field(coluna.removesuffix("_id")))


def _legivel(campo: str, valor: object, nomes_fk: dict[tuple[str, object], str]) -> str:
    """O valor gravado na trilha como a pessoa o lê (datas, Sim/Não, nomes, rótulos)."""
    if valor in (None, ""):
        return ""
    f = _campo(campo)
    if f.is_relation:
        return nomes_fk.get((campo, valor), f"#{valor}")
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if f.choices:
        return str(dict(f.choices).get(valor, valor))
    texto = str(valor)
    if f.get_internal_type() == "DateField" and len(texto) == 10:
        texto = f"{texto[8:10]}/{texto[5:7]}/{texto[:4]}"
    return texto if len(texto) <= 80 else texto[:79] + "…"


def _nomes_fk(passos) -> dict[tuple[str, object], str]:
    """Os nomes dos cadastros citados nas mudanças, numa consulta por cadastro."""
    ids: dict[str, set] = {}
    for p in passos:
        for c in p.campos:
            if c.endswith("_id") and c in NOMES:
                ids.setdefault(c, set()).update(
                    v for v in (p.antes.get(c), p.depois.get(c)) if v not in (None, ""))
    nomes = {}
    for c, pks in ids.items():
        modelo = cast(type[Model], _campo(c).related_model)
        for pk, obj in modelo._default_manager.in_bulk(pks).items():
            nomes[(c, pk)] = str(getattr(obj, "nome", None) or obj)
    return nomes


def historico(s: Solicitacao) -> list[Evento]:
    eventos: list[Evento] = []
    ordem = list(dict.fromkeys([*NOMES.values(), *FILHAS.values()]))
    passos = passos_do_registro(Solicitacao._meta.db_table, s.pk,
                                dict.fromkeys(FILHAS, "solicitacao_id"))
    nomes_fk = _nomes_fk(passos)
    for p in passos:
        if p.operacao != "UPDATE":
            continue
        # O passo que muda a situação já tem o seu movimento (envio, despacho…): dele entram
        # os campos alterados junto (reenvio, "editar e enviar"); as equipes que a decisão da
        # DG ajusta já estão no movimento do ajuste.
        decisao = "status" in p.campos and p.depois.get("decidido_por_id")
        filhas = set() if decisao else p.filhas
        partes = [n for n in ordem if n in {NOMES[c] for c in p.campos if c in NOMES}
                  | {FILHAS[t] for t in filhas if t in FILHAS}]
        if partes:
            texto = partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1]
            mudancas = []
            for c in NOMES:  # na ordem do formulário
                if c not in p.campos:
                    continue
                antes, depois = (_legivel(c, v.get(c), nomes_fk) for v in (p.antes, p.depois))
                if antes != depois:
                    rotulo = str(_campo(c).verbose_name)
                    mudancas.append((rotulo[:1].upper() + rotulo[1:], antes, depois))
            eventos.append(Evento(p.em, f"Alterou {texto}", p.usuario, mudancas=mudancas))
    for m in s.movimentos.select_related("usuario"):
        texto = m.get_acao_display()
        if m.observacao:
            texto += f" — {m.observacao}"
        eventos.append(Evento(m.em, texto, m.usuario, marca=m.acao != "anexo",
                              acao=ACAO_NA_LINHA_DO_TEMPO.get(m.acao, "dados")))
    eventos.sort(key=lambda e: e.em, reverse=True)
    return eventos
