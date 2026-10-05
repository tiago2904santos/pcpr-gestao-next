"""Viagem realizada (módulo 9b-2, paridade com o `roteiro_ajustado` da referência; desenho em
docs/migration/prestacao.md).

A prestação guarda uma cópia dos trechos do ofício (criada no primeiro ajuste) com saída e
chegada corrigidas para o que de fato aconteceu. O ofício emitido não muda. As diárias se
recalculam com as mesmas regras do ofício; o diário passa a seguir os realizados e o RT usa a
diária recalculada e lista as mudanças de horário. "Voltar ao do ofício" apaga o ajuste.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from . import diario, policies, services
from .dominio import diarias as dominio_diarias
from .models import PrestacaoContas, TrechoRealizado


class AjusteInvalido(Exception):
    pass


def trechos(prestacao: PrestacaoContas) -> list[TrechoRealizado]:
    return list(prestacao.trechos_realizados.select_related("origem", "destino")
                .order_by("ordem"))


def ajustado(prestacao: PrestacaoContas) -> bool:
    return prestacao.trechos_realizados.exists()


def _travar(usuario, prestacao_pk: int) -> PrestacaoContas:
    p = (PrestacaoContas.objects.select_for_update(of=("self",))
         .select_related("oficio__sede").get(pk=prestacao_pk))
    if diario.equipe_finalizada(p):
        raise AjusteInvalido("Prestação finalizada — reabra para editar.")
    policies.exigir(policies.pode_editar_equipe_prestacao(usuario, p),
                    "Você não pode alterar esta prestação.")
    return p


def _recalcular(p: PrestacaoContas) -> None:
    lista = trechos(p)
    try:
        calculo = services._calcular_trechos(lista, p.oficio.sede, p.oficio.viajantes.count())
    except (dominio_diarias.RoteiroIncalculavel, dominio_diarias.SemTabelaDeDiarias) as exc:
        p.diarias_realizadas_total, p.diarias_realizadas_resumo = None, ""
        p.diarias_realizadas_calculo, p.diarias_realizadas_erro = {}, str(exc)[:300]
    else:
        p.diarias_realizadas_total, p.diarias_realizadas_resumo = calculo.total, calculo.resumo
        p.diarias_realizadas_calculo, p.diarias_realizadas_erro = calculo.como_dict(), ""
    p.save(update_fields=["diarias_realizadas_total", "diarias_realizadas_resumo",
                          "diarias_realizadas_calculo", "diarias_realizadas_erro",
                          "atualizado_em"])


@transaction.atomic
def ajustar(usuario, prestacao_pk: int) -> PrestacaoContas:
    """Cria a cópia dos trechos do ofício (só na primeira vez)."""
    p = _travar(usuario, prestacao_pk)
    if ajustado(p):
        return p
    antes = _diaria_automatica(p)
    origem = list(p.oficio.trechos.order_by("ordem"))
    if not origem:
        raise AjusteInvalido("O ofício não tem trechos para ajustar.")
    TrechoRealizado.objects.bulk_create([
        TrechoRealizado(prestacao=p, trecho_oficio=t, ordem=i, origem_id=t.origem_id,
                        destino_id=t.destino_id, saida_em=t.saida_em, chegada_em=t.chegada_em,
                        distancia_km=t.distancia_km)
        for i, t in enumerate(origem, start=1)])
    _recalcular(p)
    _seguir_no_rt(p, antes)
    return p


@transaction.atomic
def salvar(usuario, prestacao_pk: int,
           horarios: dict[int, tuple[datetime, datetime]]) -> PrestacaoContas:
    """{trecho realizado: (saída, chegada)} — a sequência é conferida como no ofício (cada
    trecho chega depois de sair e sai depois de o anterior chegar)."""
    p = _travar(usuario, prestacao_pk)
    lista = trechos(p)
    if not lista:
        raise AjusteInvalido("Ajuste a viagem antes de corrigir os horários.")
    for t in lista:
        if t.pk in horarios:
            t.saida_em, t.chegada_em = horarios[t.pk]
        if t.chegada_em <= t.saida_em:
            raise AjusteInvalido(f"{t}: a chegada precisa ser depois da saída.")
    try:
        services._validar_sequencia([
            services.TrechoInformado(t.origem_id, t.destino_id, t.saida_em, t.chegada_em)
            for t in lista])
    except services.RegraViolada as exc:
        raise AjusteInvalido(str(exc)) from exc
    antes = _diaria_automatica(p)
    for t in lista:
        if t.pk in horarios:
            t.save(update_fields=["saida_em", "chegada_em", "atualizado_em"])
    _recalcular(p)
    _seguir_no_rt(p, antes)
    return p


@transaction.atomic
def desfazer(usuario, prestacao_pk: int) -> PrestacaoContas:
    """Volta ao do ofício: apaga os realizados e as diárias recalculadas."""
    p = _travar(usuario, prestacao_pk)
    antes = _diaria_automatica(p)
    p.trechos_realizados.all().delete()
    p.diarias_realizadas_total, p.diarias_realizadas_resumo = None, ""
    p.diarias_realizadas_calculo, p.diarias_realizadas_erro = {}, ""
    p.save(update_fields=["diarias_realizadas_total", "diarias_realizadas_resumo",
                          "diarias_realizadas_calculo", "diarias_realizadas_erro",
                          "atualizado_em"])
    _seguir_no_rt(p, antes)
    return p


# ---------------------------------------------------------------- leitura para o RT
def por_servidor(p: PrestacaoContas) -> Decimal | None:
    """A diária por servidor recalculada (None sem ajuste ou sem cálculo)."""
    valor = (p.diarias_realizadas_calculo or {}).get("por_servidor")
    if valor and Decimal(valor) > 0:
        return Decimal(valor).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return None


def _legivel(dt: datetime) -> str:
    return f"{timezone.localtime(dt):%d/%m/%Y às %H:%M}"


def alteracoes(p: PrestacaoContas) -> list[str]:
    """Frases das mudanças de saída/chegada entre o ofício e o realizado, pareadas pela
    posição (referência: `alteracoes_datas_horarios_roteiro`)."""
    realizados = trechos(p)
    if not realizados:
        return []
    originais = list(p.oficio.trechos.select_related("origem", "destino").order_by("ordem"))
    itens = []
    for novo, velho in zip(realizados, originais, strict=False):
        rota = f"{novo.origem} → {novo.destino}"
        if _legivel(novo.saida_em) != _legivel(velho.saida_em):
            itens.append(f"saída ({rota}) de {_legivel(velho.saida_em)} para "
                         f"{_legivel(novo.saida_em)}")
        if _legivel(novo.chegada_em) != _legivel(velho.chegada_em):
            itens.append(f"chegada ({rota}) de {_legivel(velho.chegada_em)} para "
                         f"{_legivel(novo.chegada_em)}")
    return itens


def _diaria_automatica(p: PrestacaoContas) -> str:
    from . import relatorio
    return relatorio.diaria_padrao(p)


def _seguir_no_rt(p: PrestacaoContas, antes: str) -> None:
    """A diária do RT segue a recalculada enquanto ainda for a automática (vazia ou igual à
    de antes da mudança) — o que a equipe escreveu à mão não muda (referência)."""
    from .models import RelatorioTecnico
    rt = RelatorioTecnico.objects.filter(prestacao=p).first()
    depois = _diaria_automatica(p)
    if rt is not None and rt.diaria in ("", antes) and rt.diaria != depois:
        RelatorioTecnico.objects.filter(pk=rt.pk).update(diaria=depois)
    from . import relatorio
    relatorio.preencher_informacoes_complementares(p)
