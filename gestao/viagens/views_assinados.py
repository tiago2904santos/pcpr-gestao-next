"""Vias assinadas: anexar, abrir e remover (paridade com `assinatura_artefato` da
referência, para ofício, justificativa, termo e OS). A regra fica em `assinados.py`."""

from __future__ import annotations

from urllib.parse import urlsplit

from django.contrib import messages
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import assinados, policies, termos
from .models import Oficio, OrdemServico, TermoAutorizacao, ViaAssinada


def _alvo(request: HttpRequest, tipo: str, pk: int, chave: str) -> assinados.Alvo:
    """O documento pedido, só se quem pede vê o registro (senão, 404: não revela que existe)."""
    if tipo in (ViaAssinada.Tipo.OFICIO, ViaAssinada.Tipo.JUSTIFICATIVA):
        oficio = get_object_or_404(Oficio, pk=pk)
        if chave or not policies.pode_ver(request.user, oficio):
            raise Http404
        return assinados.Alvo(tipo, oficio)
    if tipo == ViaAssinada.Tipo.TERMO:
        termo = get_object_or_404(TermoAutorizacao, pk=pk)
        if not policies.pode_ver_termo(request.user, termo):
            raise Http404
        if chave not in {d["chave"] for d in termos.documentos_do_termo(termo)}:
            raise Http404
        return assinados.Alvo(tipo, termo, chave)
    if tipo == ViaAssinada.Tipo.ORDEM:
        ordem = get_object_or_404(OrdemServico, pk=pk)
        if chave or not policies.pode_ver_ordem(request.user, ordem):
            raise Http404
        return assinados.Alvo(tipo, ordem)
    raise Http404


def destino_padrao(alvo: assinados.Alvo) -> str:
    dono = alvo.dono
    if isinstance(dono, Oficio):
        aba = "situacao=arquivado&" if dono.arquivado_em else ""
        return f"{reverse('viagens:oficios')}?{aba}q={dono.numero_formatado}&resumo={dono.pk}"
    if isinstance(dono, TermoAutorizacao):
        return f"{reverse('viagens:editar_termo', args=[dono.pk])}?previa={alvo.chave}#documentos"
    return f"{reverse('viagens:editar_ordem', args=[dono.pk])}#documento"


def _voltar(request: HttpRequest, padrao: str) -> str:
    """A página de onde a janela foi aberta (mesmo site), ou o registro."""
    voltar = request.POST.get("voltar") or ""
    if (voltar.startswith("/") and not voltar.startswith("//")
            and url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()})
            and not urlsplit(voltar).path.startswith("/viagens/assinados/")):
        return voltar
    return padrao


@require_http_methods(["GET", "POST"])
def anexar(request: HttpRequest, tipo: str, pk: int, chave: str = "") -> HttpResponse:
    alvo = _alvo(request, tipo, pk, chave)
    policies.exigir(assinados.pode_anexar(request.user, alvo),
                    "Você não pode anexar a via assinada deste documento.")
    padrao = destino_padrao(alvo)
    voltar = _voltar(request, padrao) if request.method == "POST" else padrao
    erro = ""
    if request.method == "POST":
        arquivo = request.FILES.get("arquivo")
        if arquivo is None:
            erro = "Escolha o PDF assinado."
        else:
            havia = assinados.vigente(alvo) is not None
            try:
                assinados.validar(arquivo.name or "", arquivo.size or 0, arquivo.read(5))
                arquivo.seek(0)
                via = assinados.anexar(request.user, alvo, nome=arquivo.name or "",
                                       conteudo=arquivo.read())
            except assinados.ArquivoAssinadoInvalido as exc:
                erro = str(exc)
            else:
                messages.success(request, "Via assinada trocada; a anterior ficou no histórico."
                                 if havia else "Via assinada anexada.")
                # O que se leu do PDF (referência m112): quem assinou, ou os avisos.
                conferencia = via.conferencia or {}
                if conferencia:
                    (messages.info if conferencia.get("assinado") else messages.warning)(
                        request, conferencia.get("resumo", ""))
                for aviso in conferencia.get("avisos", []):
                    messages.warning(request, aviso)
                return redirect(voltar)
    # Erro (inclusive vindo da janela): a página de anexar com o erro no campo e o caminho
    # de volta guardado — sem perder o contexto nem reabrir a janela.
    s = assinados.situacao(assinados.vigente(alvo), alvo)
    return render(request, "viagens/assinados/anexar.html", {
        "alvo": alvo, "titulo": alvo.rotulo, "s": s, "erro": erro, "voltar_url": voltar,
        "original_url": _original_url(alvo),
        "migalhas": [("Início", reverse("painel:inicio")), ("Viagens", reverse("viagens:painel")),
                     _modulo(alvo), (alvo.rotulo, padrao), ("Via assinada", "")],
    }, status=422 if erro else 200)


def _modulo(alvo: assinados.Alvo) -> tuple[str, str]:
    if isinstance(alvo.dono, Oficio):
        return ("Ofícios", reverse("viagens:oficios"))
    if isinstance(alvo.dono, TermoAutorizacao):
        return ("Termos de autorização", reverse("viagens:termos"))
    return ("Ordens de serviço", reverse("viagens:ordens"))


def _original_url(alvo: assinados.Alvo) -> str:
    """O PDF gerado do documento, para conferir antes de anexar ou trocar."""
    if isinstance(alvo.dono, Oficio):
        doc = assinados.documento_emitido(alvo.dono, alvo.tipo)
        return (reverse("viagens:baixar_documento", args=[doc.pk]) + "?versao=original"
                if doc else "")
    if isinstance(alvo.dono, TermoAutorizacao):
        return reverse("viagens:documento_termo", args=[alvo.dono.pk, alvo.chave, "pdf"])
    return reverse("viagens:documento_ordem", args=[alvo.dono.pk, "pdf"])


@require_GET
def abrir(request: HttpRequest, via_pk: int) -> FileResponse:
    via = get_object_or_404(ViaAssinada.objects.select_related("oficio", "termo", "ordem"),
                            pk=via_pk)
    if not assinados.pode_abrir(request.user, via):
        raise Http404
    return resposta_da_via(via, baixar=request.GET.get("baixar") == "1")


def resposta_da_via(via: ViaAssinada, *, baixar: bool = False) -> FileResponse:
    resposta = FileResponse(via.arquivo.open("rb"), content_type="application/pdf",
                            as_attachment=baixar, filename=via.nome_download)
    resposta["Cache-Control"] = "no-store"
    resposta["X-Content-SHA256"] = via.sha256
    return resposta


@require_POST
def remover(request: HttpRequest, via_pk: int) -> HttpResponse:
    via = get_object_or_404(ViaAssinada.objects.select_related("oficio", "termo", "ordem"),
                            pk=via_pk)
    alvo = assinados.alvo_da_via(via)
    if not assinados.pode_abrir(request.user, via):
        raise Http404
    try:
        assinados.revogar(request.user, via.pk)
    except assinados.ViaJaRemovida as exc:
        messages.warning(request, str(exc))
    else:
        messages.success(request, "Via assinada removida: o PDF gerado volta a valer.")
    return redirect(_voltar(request, destino_padrao(alvo)))


def cartao(request: HttpRequest, alvo: assinados.Alvo, via: ViaAssinada | None, *,
           titulo: str, original_url: str = "", voltar: str = "") -> dict:
    """O que as telas precisam para mostrar a via de um documento (selo, abrir, anexar,
    trocar, remover) — consumido por viagens/assinados/_itens_menu.html e _selo.html."""
    args = [alvo.tipo, alvo.dono.pk] + ([alvo.chave] if alvo.chave else [])
    nome = "viagens:anexar_assinado_de" if alvo.chave else "viagens:anexar_assinado"
    return {"s": assinados.situacao(via, alvo), "titulo": titulo, "original_url": original_url,
            "anexar_url": reverse(nome, args=args), "voltar": voltar or request.get_full_path(),
            "pode": assinados.pode_anexar(request.user, alvo)}
