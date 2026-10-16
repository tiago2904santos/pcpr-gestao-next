"""Entrada global e revisão privada das importações do próprio usuário."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import importacao
from .documentos.importador import LeituraInvalida
from .dominio.importacao import TIPOS
from .models import ArquivoImportado, ParteImportada


def _arquivos(request):
    importacao.exigir(request.user)
    return ArquivoImportado.objects.filter(usuario=request.user)


@require_GET
@never_cache
def lista(request):
    pagina = Paginator(_arquivos(request).prefetch_related("partes"), 25).get_page(
        request.GET.get("pagina")
    )
    return render(request, "viagens/importacao/lista.html", {"pagina": pagina})


@require_POST
def enviar(request):
    importacao.exigir(request.user)
    arquivos = request.FILES.getlist("arquivos")
    if not 1 <= len(arquivos) <= 50:
        return JsonResponse({"erro": "Escolha de 1 a 50 arquivos."}, status=422)
    resultados = []
    for arquivo in arquivos:
        try:
            if arquivo.size > 25 * 1024 * 1024:
                raise LeituraInvalida("O arquivo ultrapassa 25 MB. Divida e reenvie.")
            registro, criado = importacao.receber(request.user, arquivo.name, arquivo.read())
            resultados.append(
                {
                    "id": registro.pk,
                    "nome": registro.nome,
                    "repetido": not criado,
                    "estado": registro.estado,
                }
            )
        except LeituraInvalida as exc:
            resultados.append({"nome": arquivo.name, "erro": str(exc)})
    if request.headers.get("X-Requested-With") != "fetch":
        return redirect("viagens:importacoes")
    return JsonResponse({"arquivos": resultados}, status=202)


@require_GET
def estado(request):
    qs = _arquivos(request).prefetch_related("partes")
    ids = [int(n) for n in request.GET.get("ids", "").split(",") if n.isdecimal()][:50]
    if ids:
        qs = qs.filter(pk__in=ids)
    saida = []
    for arquivo in qs[:50]:
        saida.append(
            {
                "id": arquivo.pk,
                "nome": arquivo.nome,
                "estado": arquivo.estado,
                "erro": arquivo.erro,
                "duracao_ms": arquivo.duracao_ms,
                "partes": [
                    {
                        "id": p.pk,
                        "tipo": TIPOS.get(p.tipo, "Documento"),
                        "estado": p.estado,
                        "destino": p.rotulo,
                        "motivo": p.motivo,
                        "url": reverse("viagens:revisar_importacao", args=[p.pk]),
                    }
                    for p in arquivo.partes.all()
                ],
            }
        )
    resposta = JsonResponse({"arquivos": saida})
    resposta["Cache-Control"] = "no-store"
    return resposta


def _parte(request, pk):
    importacao.exigir(request.user)
    return get_object_or_404(
        ParteImportada.objects.select_related("importacao"), pk=pk, importacao__usuario=request.user
    )


@require_http_methods(["GET", "POST"])
@never_cache
def revisar(request, pk):
    parte = _parte(request, pk)
    if request.method == "POST":
        try:
            if request.POST.get("acao") == "ignorar":
                ParteImportada.objects.filter(pk=pk, estado="revisao").update(
                    estado="ignorado",
                    revisado_por=request.user,
                    motivo="Documento ignorado pelo usuário.",
                )
            else:
                importacao.aplicar(
                    request.user,
                    pk,
                    request.POST.get("destino", ""),
                    confirmar=request.POST.get("confirmar") == "sim",
                    revisao=True,
                )
            importacao.atualizar_estado(parte.importacao_id)
            messages.success(request, "Decisão registrada.")
            return redirect("viagens:importacoes")
        except (LeituraInvalida, PermissionDenied) as exc:
            messages.error(request, str(exc))
    destinos = list({d.chave: d for d in importacao.destinos_do_usuario(request.user)}.values())
    return render(
        request,
        "viagens/importacao/revisao.html",
        {"parte": parte, "destinos": destinos, "tipos": TIPOS},
    )


@require_GET
def arquivo(request, pk):
    parte = _parte(request, pk)
    resposta = FileResponse(
        parte.arquivo.open("rb"),
        content_type="application/pdf",
        filename=f"documento-p{parte.inicio}-{parte.fim}.pdf",
        as_attachment=request.GET.get("baixar") == "1",
    )
    resposta["Cache-Control"] = "no-store"
    resposta["X-Content-Type-Options"] = "nosniff"
    # PDF privado na prévia de mesma origem, nunca embutido em site de terceiros.
    resposta["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'self'"
    resposta["X-Frame-Options"] = "SAMEORIGIN"
    return resposta


@require_GET
def original(request, pk):
    registro = get_object_or_404(_arquivos(request), pk=pk)
    resposta = FileResponse(
        registro.original.open("rb"),
        as_attachment=True,
        content_type="application/octet-stream",
        filename=registro.nome,
    )
    resposta["Cache-Control"] = "no-store"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta
