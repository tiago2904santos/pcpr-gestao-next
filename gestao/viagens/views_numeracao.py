"""Numeração de ofícios (LP-32, D9): o gestor vê, por ano, o piso, o último número ocupado,
as lacunas que voltam e o próximo número — e muda o piso. A regra é do domínio
(`dominio.numeracao`), a escrita de `services.definir_piso`, o histórico da trilha do banco
(`linha_do_tempo.do_piso`). Entrada: "Mais" da barra da lista de ofícios (só gestor)."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import linha_do_tempo, policies, services
from .dominio.numeracao import ExplicacaoDoProximo, formatar_numero
from .forms import FormularioPiso


def _anos(ano_pedido: int | None) -> tuple[list[services.AnoDeNumeracao], int]:
    """Todos os anos com algo (e o atual e o próximo, para preparar a virada) e o escolhido."""
    atual = timezone.localdate().year
    extras = [atual + 1] + ([ano_pedido] if ano_pedido and 2000 <= ano_pedido <= 2100 else [])
    anos = services.resumo_numeracao(extras)
    escolhido = ano_pedido if ano_pedido in {a.ano for a in anos} else atual
    return anos, escolhido


def _efeito(ano: int, e: ExplicacaoDoProximo, maior: int | None) -> str:
    """O que muda agora, em uma ou duas frases (vai na mensagem depois de salvar)."""
    proximo = formatar_numero(e.proximo, ano)
    if e.piso_sem_efeito and e.origem == "sequencia":
        texto = (f"Nada muda agora: o último número usado é {formatar_numero(maior, ano)}, "
                 f"então o próximo continua {proximo}.")
    elif e.origem == "lacuna":
        texto = f"O próximo ofício de {ano} usa o {proximo}, liberado pela exclusão de um rascunho."
    else:
        texto = f"O próximo ofício de {ano} será {proximo}."
    if e.lacunas_abaixo:
        lista = ", ".join(formatar_numero(n, ano) for n in e.lacunas_abaixo)
        if len(e.lacunas_abaixo) == 1:
            texto += f" A lacuna {lista} fica abaixo do piso e não será reaproveitada."
        else:
            texto += f" As lacunas {lista} ficam abaixo do piso e não serão reaproveitadas."
    return texto


@require_http_methods(["GET", "POST"])
def numeracao(request: HttpRequest) -> HttpResponse:
    policies.exigir(policies.pode_gerir_numeracao(request.user),
                    "Só o gestor de viagens define a numeração dos ofícios.")
    pedido = request.POST.get("ano") or request.GET.get("ano") or ""
    anos, ano = _anos(int(pedido) if pedido.isdigit() else None)
    do_ano = next(a for a in anos if a.ano == ano)
    form = FormularioPiso(request.POST or None, initial={"ano": ano, "piso": do_ano.piso})
    status = 200
    if request.method == "POST":
        if form.is_valid():
            novo = form.cleaned_data["piso"]
            if novo == do_ano.piso:
                messages.info(request, f"O número inicial de {ano} já era {novo}; nada mudou.")
                return redirect(f"{reverse('viagens:numeracao')}?ano={ano}")
            try:
                services.definir_piso(request.user, ano, novo)
            except services.RegraViolada as exc:
                form.add_error("piso", str(exc))
            else:
                depois = next(a for a in services.resumo_numeracao([ano]) if a.ano == ano)
                messages.success(request, f"Número inicial de {ano} gravado: {novo}. "
                                 + _efeito(ano, depois.explicacao, depois.maior)
                                 + " Nenhum ofício já numerado mudou.")
                return redirect(f"{reverse('viagens:numeracao')}?ano={ano}")
        status = 422
    return render(request, "viagens/numeracao.html", {
        "anos": anos, "ano": ano, "do_ano": do_ano, "explicacao": do_ano.explicacao,
        "ano_atual": timezone.localdate().year, "form": form,
        "encerrado": ano < timezone.localdate().year,
        "ajuda_piso": f"Ex.: 100 faz o primeiro ofício de {ano} sair 100/{ano}. Para voltar ao "
                      "padrão, use 1.",
        "historico": linha_do_tempo.do_piso(ano),
        "migalhas": [("Início", reverse("painel:inicio")), ("Viagens", reverse("viagens:painel")),
                     ("Ofícios", reverse("viagens:oficios")), ("Numeração", "")],
    }, status=status)
