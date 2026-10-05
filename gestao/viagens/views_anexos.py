"""Documentos da prestação (módulo 9d): a folha com o ofício assinado (a via do módulo 7),
o despacho, o diário assinado, e por servidor os comprovantes e o RT assinado; anexar,
abrir, remover, voltar uma versão anterior e corrigir valor/data/operação do comprovante.
Regra em `anexos.py`."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from . import anexos, assinados, diario, policies
from . import prestacao as servico
from .dominio import relatorio as dominio_rt
from .models import AnexoPrestacao, PrestacaoContas, PrestacaoServidor, ViaAssinada
from .views import _migalhas


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
    p = _prestacao(request, pk)
    oficio = p.oficio
    pode = policies.pode_editar_equipe_prestacao(request.user, p)
    equipe_travada = diario.equipe_finalizada(p)
    todos = list(anexos.ativos(AnexoPrestacao.objects.filter(prestacao=p))
                 .select_related("servidor__servidor"))
    da_equipe: dict[str, list[AnexoPrestacao]] = {
        str(t): [a for a in todos if a.tipo == t and a.servidor_id is None]
        for t in (AnexoPrestacao.Tipo.DESPACHO, AnexoPrestacao.Tipo.DB_ASSINADO)}
    servidores = []
    for ps in servico.ativos(PrestacaoServidor.objects.filter(prestacao=p)
                             .select_related("servidor").order_by("servidor__nome")):
        ps.prestacao = p
        comprovantes = sorted(
            (a for a in todos if a.servidor_id == ps.pk
             and a.tipo == AnexoPrestacao.Tipo.COMPROVANTE),
            key=lambda a: (a.data_operacao is None, a.data_operacao or date.min, a.pk))
        liberada = servico.diaria_liberada(ps)
        esperado = ps.diaria_valor_override or liberada
        div = anexos.divergencia(ps, [a.valor for a in comprovantes], liberada)
        servidores.append({
            "ps": ps, "comprovantes": comprovantes,
            "rt": next((a for a in todos if a.servidor_id == ps.pk
                        and a.tipo == AnexoPrestacao.Tipo.RT_ASSINADO), None),
            "esperado": dominio_rt.moeda(esperado) if esperado else "",
            "divergencia": (dominio_rt.moeda(div[0]), dominio_rt.moeda(div[1])) if div else None,
            "editavel": pode and not ps.finalizada})
    via = assinados.vigente(assinados.Alvo(ViaAssinada.Tipo.OFICIO, oficio))
    return render(request, "viagens/anexos/folha.html", {
        "p": p, "oficio": oficio, "via": via, "despachos": da_equipe["despacho"],
        "db": next(iter(da_equipe["db_assinado"]), None), "servidores": servidores,
        "editavel_equipe": pode and not equipe_travada, "equipe_finalizada": equipe_travada,
        "operacoes": AnexoPrestacao.Operacao.choices,
        "anteriores": list(anexos.versoes_anteriores(p)), "pode": pode,
        "migalhas": _migalhas(("Prestação de contas", reverse("viagens:prestacoes")),
                              (f"Documentos · {oficio}", ""))})


def _voltar(p: PrestacaoContas, ancora: str) -> str:
    return reverse("viagens:documentos_prestacao", args=[p.pk]) + f"#{ancora}"


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
    return redirect(_voltar(p, ancora))


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
    return redirect(_voltar(a.prestacao, ancora))
