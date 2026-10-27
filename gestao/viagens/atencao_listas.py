"""A faixa "pede atenção" das listas de Viagens (ofícios, OS, termos, planos, viagens).

Dois recortes por cima das abas, iguais em todas as listas:
- urgentes: o documento ainda não saiu e a viagem começa de hoje a 7 dias — o mais perto
  primeiro;
- vazios: criados e esquecidos (nada preenchido) — prendem um número à toa; com eles à
  vista, quem pode excluir limpa todos de uma vez (cada um pela regra da sua exclusão).

Cada lista descreve o seu tipo num `Tipo` (o que é "pendente", onde está o início, o que é
"vazio", como se exclui); a view chama `aplicar`, `cartoes` e `excluir_vazios`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest

from . import ordens, planos, termos, viagem
from .linha_lista import DIAS_DE_URGENCIA
from .models import (
    AnexoViagem,
    EfetivoPlano,
    EventoPlano,
    Oficio,
    OrdemServico,
    OrdemServicoDestino,
    PlanoDestino,
    PlanoTrabalho,
    Roteiro,
    TermoAutorizacao,
    TermoDestino,
    ViaAssinada,
    Viagem,
    ViagemDestino,
)
from .ordens import OrdemInvalida
from .planos import PlanoInvalido
from .termos import TermoInvalido
from .viagem import ViagemInvalida

RECORTES = ("urgentes", "vazios")


@dataclass(frozen=True)
class Tipo:
    singular: str            # "OS", "termo", "plano", "viagem"
    plural: str
    feminino: bool
    acao: str                # o que falta fazer antes da saída: "gerar", "assinar"…
    campo_inicio: str        # data de início no queryset (campo ou anotação)
    pendente: Callable[[], Q]
    vazio: Callable[[], Q]
    nota_vazio: str
    excluir: Callable[[object, int], object]
    rota_excluir: str
    permissao_excluir: str

    def q_urgente(self, hoje: date) -> Q:
        return self.pendente() & Q(**{f"{self.campo_inicio}__gte": hoje,
                                      f"{self.campo_inicio}__lte": hoje + timedelta(
                                          days=DIAS_DE_URGENCIA)})

    def q(self, recorte: str, hoje: date) -> Q:
        if recorte == "urgentes":
            return self.q_urgente(hoje)
        if recorte == "vazios":
            return self.vazio()
        return Q()


def _sem(modelo, campo: str) -> Q:
    """Nenhum `modelo` aponta para o registro. Subconsulta não correlacionada (entra no
    filtro de uma contagem); os nulos ficam de fora — `NOT IN (…, NULL)` não casa nada."""
    return ~Q(pk__in=modelo.objects.filter(**{f"{campo}__isnull": False}).values(campo))


ORDEM = Tipo(
    "OS", "OS", True, "gerar", "data_inicio",
    pendente=lambda: Q(documento_gerado_em__isnull=True,
                       situacao=OrdemServico.Situacao.ATIVA),
    vazio=lambda: (Q(documento_gerado_em__isnull=True, situacao=OrdemServico.Situacao.ATIVA,
                     data_inicio__isnull=True, motivo="")
                   & _sem(OrdemServicoDestino, "ordem_id")
                   & _sem(OrdemServico.servidores.through, "ordemservico_id")
                   & _sem(OrdemServico.oficios.through, "ordemservico_id")),
    nota_vazio="Sem ofício, período, destino, equipe nem motivo",
    excluir=ordens.excluir, rota_excluir="viagens:excluir_ordens_vazias",
    permissao_excluir="viagens.delete_ordemservico")

TERMO = Tipo(
    "termo", "termos", False, "assinar", "inicio_efetivo",
    # Termo não se "emite": pende enquanto não tem via assinada em vigor.
    pendente=lambda: (Q(situacao=TermoAutorizacao.Situacao.ATIVO)
                      & ~Q(pk__in=ViaAssinada.objects.filter(
                          termo__isnull=False, revogada_em__isnull=True).values("termo_id"))),
    vazio=lambda: (Q(situacao=TermoAutorizacao.Situacao.ATIVO, oficio__isnull=True,
                     data_inicio__isnull=True, viatura__isnull=True)
                   & _sem(TermoDestino, "termo_id")
                   & _sem(TermoAutorizacao.servidores.through, "termoautorizacao_id")
                   & _sem(TermoAutorizacao.oficios.through, "termoautorizacao_id")
                   & _sem(ViaAssinada, "termo_id")),
    nota_vazio="Sem ofício, destino, período, equipe nem viatura",
    excluir=termos.excluir, rota_excluir="viagens:excluir_termos_vazios",
    permissao_excluir="viagens.delete_termoautorizacao")

PLANO = Tipo(
    "plano", "planos", False, "gerar", "data_inicio",
    pendente=lambda: Q(documento_gerado_em__isnull=True, cancelado=False),
    # A contextualização nasce escrita (texto automático): não conta para "vazio".
    vazio=lambda: (Q(documento_gerado_em__isnull=True, cancelado=False,
                     data_inicio__isnull=True, programa__isnull=True, programa_outros="")
                   & _sem(PlanoTrabalho.oficios.through, "planotrabalho_id")
                   & _sem(EventoPlano, "plano_id") & _sem(PlanoDestino, "plano_id")
                   & _sem(EfetivoPlano, "plano_id")),
    nota_vazio="Sem ofício, período, programa, destino nem efetivo",
    excluir=planos.excluir, rota_excluir="viagens:excluir_planos_vazios",
    permissao_excluir="viagens.delete_planotrabalho")

VIAGEM = Tipo(
    "viagem", "viagens", True, "gerar os documentos", "data_inicio",
    pendente=lambda: Q(situacao__in=[Viagem.Situacao.RASCUNHO, Viagem.Situacao.PREPARACAO]),
    vazio=lambda: (Q(situacao=Viagem.Situacao.RASCUNHO, data_inicio__isnull=True, titulo="",
                     motivo="")
                   & _sem(Viagem.tipos.through, "viagem_id") & _sem(ViagemDestino, "viagem_id")
                   & _sem(Oficio, "viagem_id") & _sem(OrdemServico, "viagem_id")
                   & _sem(PlanoTrabalho, "viagem_id") & _sem(TermoAutorizacao, "viagem_id")
                   & _sem(Roteiro, "viagem_id") & _sem(AnexoViagem, "viagem_id")),
    nota_vazio="Sem tipo, período, destino, documento nem pedido anexado",
    excluir=viagem.excluir, rota_excluir="viagens:excluir_viagens_vazias",
    permissao_excluir="viagens.delete_viagem")


def aplicar(qs: QuerySet, tipo: Tipo, recorte: str, hoje: date) -> QuerySet:
    if recorte not in RECORTES:
        return qs
    qs = qs.filter(tipo.q(recorte, hoje)).distinct()
    return qs.order_by(tipo.campo_inicio, "pk") if recorte == "urgentes" else qs


def contas(base: QuerySet, tipo: Tipo, hoje: date) -> dict[str, int]:
    """Urgentes e vazios numa agregação só (subconsultas não correlacionadas)."""
    return base.order_by().aggregate(
        urgentes=Count("pk", filter=tipo.q_urgente(hoje), distinct=True),
        vazios=Count("pk", filter=tipo.vazio(), distinct=True))


def _url(request: HttpRequest, valor: str) -> str:
    copia = request.GET.copy()
    copia.pop("pagina", None)
    copia.pop("atencao", None)
    if valor:
        copia["atencao"] = valor
    consulta = copia.urlencode()
    return f"{request.path}?{consulta}" if consulta else request.path


def recorte_pedido(request: HttpRequest) -> str:
    valor = request.GET.get("atencao") or ""
    return valor if valor in RECORTES else ""


def _nome(tipo: Tipo, n: int) -> str:
    return tipo.singular if n == 1 else tipo.plural


def cartoes(request: HttpRequest, tipo: Tipo, recorte: str, n: dict[str, int],
            rota_excluir_url: str = "") -> list[dict]:
    """Os cartões de componentes/atencao_lista.html para esta lista."""
    resultado = []
    if u := n["urgentes"]:
        verbo = "começa" if u == 1 else "começam"
        resultado.append({
            "tipo": "urgente", "icone": "timer", "ativo": recorte == "urgentes",
            "titulo": f"{u} {_nome(tipo, u)} {verbo} em até 7 dias",
            "nota": f"Ainda falta {tipo.acao} — o mais perto primeiro",
            "url": _url(request, "" if recorte == "urgentes" else "urgentes")})
    if v := n["vazios"]:
        vazio = ("vazia" if v == 1 else "vazias") if tipo.feminino else (
            "vazio" if v == 1 else "vazios")
        cartao = {"tipo": "vazio", "icone": "inbox", "ativo": recorte == "vazios",
                  "titulo": f"{v} {_nome(tipo, v)} {vazio}", "nota": tipo.nota_vazio,
                  "url": _url(request, "" if recorte == "vazios" else "vazios")}
        if rota_excluir_url and request.user.has_perm(tipo.permissao_excluir):
            artigo = ("a" if tipo.feminino else "o") if v == 1 else (
                "as" if tipo.feminino else "os")
            cartao.update(
                excluir_url=rota_excluir_url,
                excluir_rotulo=f"Excluir {artigo} {v}" if v > 1 else f"Excluir {artigo} {vazio}",
                excluir_confirmar=(f"{v} {_nome(tipo, v)} {vazio} "
                                   f"{'é excluíd' if v == 1 else 'são excluíd'}"
                                   f"{'a' if tipo.feminino else 'o'}{'' if v == 1 else 's'}. "
                                   "O que tiver qualquer dado preenchido fica."))
        resultado.append(cartao)
    return resultado


def mensagem_exclusao(tipo: Tipo, excluidos: list) -> str:
    if not excluidos:
        genero = "a" if tipo.feminino else "o"
        return f"Nada a excluir: nenhum{'a' if tipo.feminino else ''} {tipo.singular} vazi{genero}."
    n = len(excluidos)
    fim = ("a" if tipo.feminino else "o") + ("" if n == 1 else "s")
    return f"{n} {_nome(tipo, n)} vazi{fim} excluíd{fim}."


def excluir_vazios(usuario, visiveis: QuerySet, tipo: Tipo) -> list:
    """Exclui os vazios que a pessoa enxerga, um a um pela regra da exclusão do tipo (cada
    um na sua transação). "Vazio" é reconferido aqui; quem não pode excluir um, pula."""
    excluidos = []
    for pk in visiveis.filter(tipo.vazio()).values_list("pk", flat=True).distinct():
        try:
            excluidos.append(tipo.excluir(usuario, pk))
        except (PermissionDenied, OrdemInvalida, TermoInvalido, PlanoInvalido,
                ViagemInvalida):
            continue
    return excluidos
