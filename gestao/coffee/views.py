"""Telas do Coffee Break — CB1: cadastros contratuais (fornecedores, contratos, termos
aditivos, lotes) numa tela só com uma aba por tabela, busca, lista e novo/editar numa janela
(`?novo=1`, `?editar=<pk>`; com erro, a janela volta aberta com o digitado), e a configuração
do ofício e do protocolo (registro único). Como na referência, só o administrador do módulo."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import contratos_pdf, dominio, entregas, policies, services
from .forms import (
    FormularioAditivo,
    FormularioConfiguracao,
    FormularioContrato,
    FormularioFornecedor,
    FormularioLote,
)
from .models import Contrato, Fornecedor, Lote, TermoAditivo
from .pedidos import PedidoInvalido

POR_PAGINA = 25


@dataclass(frozen=True)
class Tabela:
    chave: str
    titulo: str
    singular: str
    genero: str  # "o" | "a" — "Novo fornecedor" / "Nova ..."
    icone: str
    modelo: Any
    formulario: Any
    busca: tuple[str, ...] = ()
    descricao: str = ""
    # Grupos da janela: (legenda, ((campo, classe de largura), ...)).
    layout: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = ()


TABELAS = {t.chave: t for t in (
    Tabela(
        "fornecedores", "Fornecedores", "fornecedor", "o", "building-2", Fornecedor,
        FormularioFornecedor, busca=("razao_social", "nome_curto", "cnpj", "contato", "email"),
        descricao="Empresas contratadas: o CNPJ confere notas e certidões; o e-mail recebe a "
                  "ordem de serviço e a ordem bancária.",
        layout=(("Empresa", (("razao_social", "campo--cresce"), ("nome_curto", "campo--lg"),
                             ("cnpj", "campo--md"))),
                ("Contato", (("contato", "campo--lg"), ("telefone", "campo--md"),
                             ("email", "campo--lg"),
                             ("portal_certidao_municipal", "campo--cresce"))))),
    Tabela(
        "contratos", "Contratos", "contrato", "o", "file-text", Contrato, FormularioContrato,
        busca=("numero", "numero_gms", "fornecedor__razao_social", "objeto"),
        descricao="Número, GMS, vigência, preço unitário e a antecedência mínima do pedido.",
        layout=(("Contrato", (("fornecedor", "campo--cresce"), ("numero", "campo--md"),
                              ("numero_gms", "campo--md"), ("termo_aditivo", "campo--md"))),
                ("Vigência e valores", (("vigencia_inicio", "campo--md"),
                                        ("vigencia_fim", "campo--md"),
                                        ("vigencia_estimada", "campo--cresce"),
                                        ("quantidade_contratada", "campo--md"),
                                        ("valor_unitario", "campo--md"),
                                        ("valor_total", "campo--md"),
                                        ("antecedencia_minima_dias", "campo--md"))),
                ("Fiscal e documento", (("fiscal", "campo--lg"), ("cargo_fiscal", "campo--lg"),
                                        ("clausula_pagamento", "campo--lg"),
                                        ("arquivo", "campo--cresce"))),
                ("Objeto", (("objeto", "campo--cresce"), ("observacoes", "campo--cresce"))))),
    Tabela(
        "aditivos", "Termos aditivos", "termo aditivo", "o", "file-plus-2", TermoAditivo,
        FormularioAditivo,
        busca=("numero", "contrato__numero", "contrato__fornecedor__razao_social"),
        descricao="Todos ficam guardados; a vigência efetiva do contrato é o maior fim entre "
                  "ele e os aditivos.",
        layout=(("Termo aditivo", (("contrato", "campo--cresce"), ("numero", "campo--md"),
                                   ("vigencia_inicio", "campo--md"),
                                   ("vigencia_fim", "campo--md"),
                                   ("arquivo", "campo--cresce"))),)),
    Tabela(
        "lotes", "Lotes", "lote", "o", "layers", Lote, FormularioLote,
        busca=("contrato__numero", "contrato__fornecedor__razao_social", "exercicio", "empenho",
               "municipios_texto"),
        descricao="Quantidade contratada por exercício e os municípios que ele atende: o "
                  "pedido cai no lote pelo município.",
        layout=(("Lote", (("contrato", "campo--cresce"), ("numero", "campo--sm"),
                          ("exercicio", "campo--sm"), ("quantidade_total", "campo--md"),
                          ("ativo", "campo--cresce"))),
                ("Empenho", (("empenho", "campo--lg"), ("valor_empenho", "campo--md"))),
                ("Municípios", (("lista_municipios", "campo--cresce"),)),
                ("Orientações", (("orientacoes", "campo--cresce"),
                                 ("especificacoes", "campo--cresce"),
                                 ("observacoes", "campo--cresce"))))),
)}


def _exigir(usuario, tabela: str = "") -> None:
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    if not policies.pode_gerir_cadastros(usuario, tabela):
        raise PermissionDenied("Só o administrador do módulo mantém os cadastros.")


def _tabela(chave: str) -> Tabela:
    if chave not in TABELAS:
        raise Http404
    return TABELAS[chave]


def _migalhas(*fim: tuple[str, str]) -> list[tuple[str, str]]:
    return [("Início", reverse("painel:inicio")), ("Coffee Break", reverse("coffee:painel")),
            *fim]


def _linha(t: Tabela, obj, hoje, resumo=None) -> dict[str, Any]:
    """Título, selos e fatos de cada registro, pela tabela."""
    if t.chave == "fornecedores":
        return {"titulo": obj.razao_social, "selos": [], "fatos": [
            ("id-card", "CNPJ", obj.cnpj_formatado or "Sem CNPJ", not obj.cnpj),
            ("user-round", "Contato", obj.contato or "Sem contato", not obj.contato),
            ("mail", "E-mail", obj.email or "Sem e-mail", not obj.email),
            ("file-text", "Contratos", f"{obj.n_contratos} contrato(s)", False),
            ("clipboard-list", "Entregas", resumo.texto if resumo else
             "Nenhuma entrega registrada", not (resumo and resumo.entregas))]}
    if t.chave == "contratos":
        selo = dominio.selo_vigencia(obj.fim_efetivo(), hoje, obj.vigencia_estimada)
        valor = (f"R$ {obj.valor_unitario:.4f}".replace(".", ",") if obj.valor_unitario
                 else "Sem preço unitário")
        return {"titulo": f"Contrato {obj.numero} · {obj.fornecedor.razao_social}",
                "selos": [(selo.texto, selo.tom)], "fatos": [
                    ("calendar", "Vigência", selo.nota, obj.fim_efetivo() is None),
                    ("list-ordered", "GMS",
                     f"GMS {obj.numero_gms}" if obj.numero_gms else "Sem GMS",
                     not obj.numero_gms),
                    ("banknote", "Valor unitário", valor, not obj.valor_unitario),
                    ("clock", "Antecedência", f"{obj.antecedencia_minima_dias} dia(s) de "
                     "antecedência", False),
                    ("file-check-2", "PDF", "PDF anexado" if obj.arquivo else "Sem PDF",
                     not obj.arquivo)]}
    if t.chave == "aditivos":
        selo = dominio.selo_vigencia(obj.vigencia_fim, hoje)
        return {"titulo": f"Termo aditivo {obj.numero} · Contrato {obj.contrato.numero}",
                "selos": [(selo.texto, selo.tom)], "fatos": [
                    ("building-2", "Fornecedor", obj.contrato.fornecedor.razao_social, False),
                    ("calendar", "Vigência", selo.nota, obj.vigencia_fim is None),
                    ("file-check-2", "PDF", "PDF anexado" if obj.arquivo else "Sem PDF",
                     not obj.arquivo)]}
    municipios = ", ".join(m.nome for m in obj.municipios.all()[:6])
    total_m = obj.n_municipios
    if total_m > 6:
        municipios += f" e mais {total_m - 6}"
    fornecedor = obj.contrato.fornecedor.razao_social
    return {"titulo": f"Lote {obj.numero} ({obj.exercicio}) · {fornecedor}",
            "selos": [("Vigente", "sucesso") if obj.ativo else ("Encerrado", "neutro")],
            "fatos": [("file-text", "Contrato", f"Contrato {obj.contrato.numero}", False),
                      ("layers", "Capacidade", f"{obj.quantidade_total} unidades", False),
                      ("map-pin", "Municípios", municipios or "Nenhum município", not total_m),
                      ("receipt", "Empenho", obj.empenho or "Sem empenho", not obj.empenho)]}


def _consulta(t: Tabela):
    qs = t.modelo.objects.all()
    # Ordem explícita: com agregação, a ordem padrão do modelo não vale (e a paginação
    # ficaria instável).
    if t.chave == "fornecedores":
        return qs.annotate(n_contratos=Count("contratos")).order_by("razao_social", "pk")
    if t.chave == "contratos":
        return (qs.select_related("fornecedor").prefetch_related("aditivos")
                .order_by("-vigencia_fim", "numero", "pk"))
    if t.chave == "aditivos":
        return qs.select_related("contrato__fornecedor").order_by("contrato__numero", "numero",
                                                                  "pk")
    return (qs.select_related("contrato__fornecedor").prefetch_related("municipios")
            .annotate(n_municipios=Count("municipios", distinct=True))
            .order_by("-exercicio", "numero", "pk"))


@require_GET
def cadastros(request: HttpRequest, tabela: str) -> HttpResponse:
    _exigir(request.user, tabela)
    t = _tabela(tabela)
    termo = " ".join((request.GET.get("q") or "").split())[:100]
    qs = _consulta(t)
    if termo:
        filtro = Q()
        digitos = dominio.so_digitos(termo)
        for campo in t.busca:
            filtro |= Q(**{f"{campo}__icontains": digitos if campo == "cnpj" and digitos
                           else termo})
        qs = qs.filter(filtro)
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    editando, form = None, None
    if (pk := request.GET.get("editar") or "").isdecimal():
        editando = get_object_or_404(t.modelo, pk=int(pk))
        form = t.formulario(instance=editando)
    elif request.GET.get("novo"):
        form = t.formulario()
    return _render(request, t, pagina, termo, form, editando)


def _render(request, t: Tabela, pagina, termo: str, form, editando, status: int = 200):
    hoje = timezone.localdate()
    abrir = form is not None
    base = urlencode([(k, v) for k, v in (("q", termo),) if v])
    contagens = {c: TABELAS[c].modelo.objects.count() for c in TABELAS}
    form = form or t.formulario()
    resumos = (entregas.resumos([o.pk for o in pagina.object_list])
               if t.chave == "fornecedores" else {})
    return render(request, "coffee/cadastros.html", {
        "grupos": [(legenda, [(form[c], classe) for c, classe in campos])
                   for legenda, campos in t.layout],
        "t": t, "tabelas": [(c, x.titulo, x.icone, contagens[c]) for c, x in TABELAS.items()],
        "page_obj": pagina, "linhas": [(o, _linha(t, o, hoje, resumos.get(o.pk)))
                                       for o in pagina.object_list],
        "termo": termo, "querystring_base": f"{base}&" if base else "",
        "form": form, "editando": editando, "abrir_dialogo": abrir,
        "novo_rotulo": f"Nov{t.genero} {t.singular}",
        "migalhas": _migalhas(("Cadastros", "")),
    }, status=status)


@require_POST
def anexar_contrato(request: HttpRequest) -> HttpResponse:
    """Contrato ou termo aditivo por PDF: o sistema lê e preenche (CB5d)."""
    _exigir(request.user, "contratos")
    try:
        r = contratos_pdf.anexar(request.user, request.FILES.get("arquivo"))
    except PedidoInvalido as exc:
        messages.error(request, str(exc))
        return redirect(reverse("coffee:cadastros", args=["contratos"]))
    (messages.warning if r.aviso else messages.success)(request, r.mensagem)
    destino = reverse("coffee:cadastros", args=["contratos"])
    return redirect(f"{destino}?editar={r.contrato.pk}" if r.contrato else destino)


@require_POST
def salvar(request: HttpRequest, tabela: str) -> HttpResponse:
    _exigir(request.user, tabela)
    t = _tabela(tabela)
    editando = None
    if (pk := request.POST.get("pk") or "").isdecimal():
        editando = get_object_or_404(t.modelo, pk=int(pk))
    antigo = (t.modelo.objects.filter(pk=editando.pk).values_list("arquivo", flat=True)
              .first() or "") if editando is not None and hasattr(editando, "arquivo") else ""
    form = t.formulario(request.POST, request.FILES, instance=editando)
    obj = None
    if form.is_valid():
        try:
            obj = services.salvar(request.user, form, t.chave)
        except services.CadastroEmUso as exc:  # versão conferida de novo sob a trava
            form.add_error(None, str(exc))
    if obj is not None:
        if antigo and getattr(obj, "arquivo", None) is not None and obj.arquivo.name != antigo:
            services.apagar_arquivo_depois(t.modelo, antigo)
        messages.success(request, f"{t.singular.capitalize()} salvo com sucesso.")
        destino = reverse("coffee:cadastros", args=[t.chave])
        return redirect(f"{destino}?novo=1" if request.POST.get("outro") else destino)
    pagina = Paginator(_consulta(t), POR_PAGINA).get_page(1)
    return _render(request, t, pagina, "", form, editando, status=422)


@require_POST
def excluir(request: HttpRequest, tabela: str, pk: int) -> HttpResponse:
    _exigir(request.user, tabela)
    t = _tabela(tabela)
    obj = get_object_or_404(t.modelo, pk=pk)
    try:
        services.excluir(request.user, obj, t.singular, t.chave)
    except services.CadastroEmUso as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"{t.singular.capitalize()} excluído.")
    return redirect(reverse("coffee:cadastros", args=[t.chave]))


@require_GET
def arquivo(request: HttpRequest, tabela: str, pk: int) -> FileResponse:
    """O PDF do contrato ou do termo aditivo, só por aqui (sem rota pública de mídia)."""
    if not policies.pode_acessar(request.user):
        raise PermissionDenied
    if tabela not in ("contratos", "aditivos"):
        raise Http404
    obj = get_object_or_404(TABELAS[tabela].modelo, pk=pk)
    if not obj.arquivo:
        raise Http404
    seguro = re.sub(r"[^\w .-]", "-", f"{TABELAS[tabela].singular.capitalize()} {obj.numero}")
    nome = f"{seguro[:80]}.pdf"
    resposta = FileResponse(obj.arquivo.open("rb"), as_attachment=True, filename=nome,
                            content_type="application/pdf")
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Cache-Control"] = "private, no-store"
    return resposta


@require_http_methods(["GET", "POST"])
def configuracao(request: HttpRequest) -> HttpResponse:
    _exigir(request.user, "configuracao")
    obj = services.configuracao()
    form = FormularioConfiguracao(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        services.salvar_configuracao(request.user, form, form.cleaned_data.get("versao", ""))
        messages.success(request, "Configuração do ofício salva com sucesso.")
        return redirect("coffee:configuracao")
    return render(request, "coffee/configuracao.html", {
        "form": form, "tabelas": [(c, x.titulo, x.icone, x.modelo.objects.count())
                                  for c, x in TABELAS.items()],
        "migalhas": _migalhas(("Ofício e protocolo", "")),
    }, status=422 if request.method == "POST" else 200)
