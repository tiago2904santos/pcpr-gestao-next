"""Anexos da prestação (módulo 9d): o despacho, o diário assinado e, por servidor, os
comprovantes e o RT assinado — anexar, abrir, remover, voltar uma versão anterior, corrigir
valor/data/operação do comprovante e a posição do nº da solicitação no ofício assinado. A
tela é a leitura e conferência (a antiga folha de documentos leva para lá). Regra em
`anexos.py`."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from gestao.plataforma.downloads import responder_fila

from . import anexos, carimbo, pacote_prestacao, policies
from . import prestacao as servico
from .dominio import relatorio as dominio_rt
from .models import AnexoPrestacao, PrestacaoContas, PrestacaoServidor


def _prestacao(request: HttpRequest, pk: int) -> PrestacaoContas:
    p = get_object_or_404(PrestacaoContas.objects.select_related("oficio__unidade"), pk=pk)
    if not policies.pode_ver_equipe_prestacao(request.user, p):
        raise Http404
    return p


def _anexo(request: HttpRequest, pk: int) -> AnexoPrestacao:
    a = get_object_or_404(AnexoPrestacao.objects.select_related(
        "prestacao__oficio", "servidor__servidor"), pk=pk)
    if not policies.pode_ver_equipe_prestacao(request.user, a.prestacao):
        raise Http404
    return a


def _valor(texto: str) -> Decimal | None:
    valor, _ = dominio_rt.ler_valor(texto)
    return valor


def _data(texto: str) -> date | None:
    texto = (texto or "").strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato).date() if texto else None
        except ValueError:
            continue
    raise anexos.AnexoInvalido(f"Data da operação inválida: {texto}. Use dd/mm/aaaa.")


@require_GET
def folha(request: HttpRequest, pk: int) -> HttpResponse:
    """A antiga folha "Documentos e fechamento" (apagada a pedido do usuário, 16/10/2026):
    os arquivos chegam pelo importador e se conferem na leitura — o endereço leva para lá."""
    p = _prestacao(request, pk)
    servidor = request.GET.get("servidor") or ""
    consulta = f"?servidor={servidor}" if servidor.isdigit() else ""
    return redirect(reverse("viagens:leitura_prestacao", args=[p.pk]) + consulta)


def _voltar(p: PrestacaoContas, ancora: str, servidor: str | int | None = "") -> str:
    """De volta à leitura e conferência, no servidor que estava aberto e na âncora."""
    base = reverse("viagens:leitura_prestacao", args=[p.pk])
    consulta = f"?servidor={servidor}" if str(servidor or "").isdigit() else ""
    return f"{base}{consulta}#{ancora}"


def _servidor_aberto(request: HttpRequest) -> str:
    return str(request.POST.get("servidor_atual") or request.POST.get("servidor") or "")


@require_POST
def anexar(request: HttpRequest, pk: int) -> HttpResponse:
    p = _prestacao(request, pk)
    tipo = request.POST.get("tipo", "")
    servidor_pk = str(request.POST.get("servidor") or "")
    ancora = f"ps-{servidor_pk}" if servidor_pk else tipo
    arquivo = request.FILES.get("arquivo")
    try:
        if arquivo is None:
            raise anexos.AnexoInvalido("Escolha o arquivo.")
        if (arquivo.size or 0) > anexos.TAMANHO_MAXIMO:
            raise anexos.AnexoInvalido("O arquivo excede o limite de 10 MB.")
        anexos.anexar(request.user, p.pk, tipo, nome=arquivo.name or "", conteudo=arquivo.read(),
                      servidor_pk=int(servidor_pk) if servidor_pk.isdigit() else None,
                      valor=_valor(request.POST.get("valor", "")),
                      data_operacao=_data(request.POST.get("data_operacao", "")),
                      operacao=request.POST.get("operacao", ""))
    except (anexos.AnexoInvalido, dominio_rt.ValorInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Documento anexado.")
    return redirect(_voltar(p, ancora, _servidor_aberto(request)))


@require_GET
def abrir(request: HttpRequest, anexo_pk: int) -> FileResponse:
    a = _anexo(request, anexo_pk)
    ext = anexos.extensao(a.arquivo.name or "")
    resposta = FileResponse(a.arquivo.open("rb"),
                            content_type=anexos.TIPO_DE_CONTEUDO.get(ext, "application/pdf"),
                            as_attachment=request.GET.get("baixar") == "1",
                            filename=a.nome_original or f"{a.tipo}{ext}")
    resposta["Cache-Control"] = "no-store"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


@require_GET
def pacote_servidor(request: HttpRequest, ps_pk: int) -> HttpResponse:
    ps = get_object_or_404(servico.ativos(PrestacaoServidor.objects.select_related(
        "servidor", "prestacao__oficio")), pk=ps_pk)
    if not policies.pode_ver_equipe_prestacao(request.user, ps.prestacao):
        raise Http404
    try:
        conteudo = pacote_prestacao.pdf(ps)
    except pacote_prestacao.PacoteIncompleto as exc:
        if request.headers.get("X-Requested-With") == "fetch":
            resposta_erro = JsonResponse({"erro": f"{ps.servidor.nome}: {exc}"}, status=422)
            resposta_erro["Cache-Control"] = "no-store"
            return resposta_erro
        messages.error(request, f"{ps.servidor.nome}: {exc}")
        return redirect(_voltar(ps.prestacao, f"ps-{ps.pk}", ps.pk))
    resposta = HttpResponse(conteudo, content_type="application/pdf")
    resposta["Content-Disposition"] = (
        f'attachment; filename="{pacote_prestacao.nome_do_pdf(ps)}"')
    return resposta


@require_GET
def pacote_equipe(request: HttpRequest, pk: int) -> HttpResponse:
    p = _prestacao(request, pk)
    pessoas = list(servico.ativos(PrestacaoServidor.objects.filter(prestacao=p))
                   .select_related("servidor").order_by("servidor__nome"))
    if not pessoas:
        messages.error(request, "Nenhum servidor está com o pacote pronto: veja o que falta "
                                "em cada um.")
        return redirect(_voltar(p, "servidores"))
    return responder_fila(request, [{"nome": ps.servidor.nome,
        "url": reverse("viagens:pacote_servidor", args=[ps.pk]), "metodo": "GET"}
        for ps in pessoas])


def _fracao(texto: str, rotulo: str) -> float:
    try:
        valor = float((texto or "").replace(",", ".").replace("%", "").strip())
    except ValueError:
        raise carimbo.CarimboInvalido(f"{rotulo}: informe um número de 0 a 100.") from None
    return valor / 100


@require_POST
def carimbar(request: HttpRequest, ps_pk: int) -> HttpResponse:
    """Onde desenhar o número de solicitação deste servidor no ofício assinado."""
    ps = get_object_or_404(servico.ativos(PrestacaoServidor.objects.select_related(
        "prestacao__oficio")), pk=ps_pk)
    if not policies.pode_ver_equipe_prestacao(request.user, ps.prestacao):
        raise Http404
    try:
        pagina = int(request.POST.get("pagina") or "1") - 1
        carimbo.posicionar(request.user, ps.pk, pagina=pagina,
                           x=_fracao(request.POST.get("x", ""), "Posição horizontal"),
                           y=_fracao(request.POST.get("y", ""), "Posição vertical"))
    except (carimbo.CarimboInvalido, ValueError, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Posição do número salva — confira na prévia.")
    return redirect(_voltar(ps.prestacao, "oficio_assinado", ps.pk))


@require_GET
def previa_carimbo(request: HttpRequest, pk: int) -> HttpResponse:
    p = _prestacao(request, pk)
    via = carimbo.via_do_oficio(p)
    if via is None:
        raise Http404
    resposta = HttpResponse(carimbo.carimbado(via), content_type="application/pdf")
    resposta["Content-Disposition"] = 'inline; filename="oficio-carimbado-previa.pdf"'
    resposta["Cache-Control"] = "no-store"
    return resposta


@require_POST
def acao(request: HttpRequest, anexo_pk: int, nome: str) -> HttpResponse:
    a = _anexo(request, anexo_pk)
    ancora = f"ps-{a.servidor_id}" if a.servidor_id else a.tipo
    try:
        if nome == "remover":
            anexos.remover(request.user, a.pk)
            messages.success(request, "Documento removido — fica 30 dias em versões anteriores.")
        elif nome == "restaurar":
            anexos.restaurar(request.user, a.pk)
            messages.success(request, "Documento de volta.")
        elif nome == "comprovante":
            anexos.editar_comprovante(
                request.user, a.pk, valor=_valor(request.POST.get("valor", "")),
                data_operacao=_data(request.POST.get("data_operacao", "")),
                operacao=request.POST.get("operacao", ""))
            messages.success(request, "Comprovante atualizado.")
        else:
            raise Http404
    except (anexos.AnexoInvalido, dominio_rt.ValorInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    return redirect(_voltar(a.prestacao, ancora, _servidor_aberto(request) or a.servidor_id))
