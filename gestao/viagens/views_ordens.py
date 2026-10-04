"""Telas das Ordens de Serviço (paridade com `viagens_ordens` da referência): lista com abas e
busca, cadastro numa tela só (com o documento ao alcance), ciclo de vida e "Nova ordem de
serviço" a partir do ofício."""

from __future__ import annotations

from urllib.parse import urlsplit

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from gestao.cadastros import policies as politicas_cadastros

from . import ordens, policies
from .forms import FormularioOrdem
from .models import Oficio, OrdemServico
from .views import POR_PAGINA, _migalhas

ABAS = [("", "Todas", "todas"), ("futuras", "Que vão acontecer", "futuras"),
        ("andamento", "Em andamento e realizadas", "andamento"),
        ("canceladas", "Canceladas", "canceladas")]


def _filtrar(qs, aba: str):
    hoje = timezone.localdate()
    ativas = qs.filter(situacao=OrdemServico.Situacao.ATIVA)
    if aba == "futuras":  # sem data, a OS ainda "vai acontecer" (referência)
        return ativas.filter(Q(data_inicio__gt=hoje) | Q(data_inicio__isnull=True))
    if aba == "andamento":
        return ativas.filter(data_inicio__lte=hoje)
    if aba == "canceladas":
        return qs.filter(situacao=OrdemServico.Situacao.CANCELADA)
    return qs


def _buscar(qs, busca: str):
    if not busca:
        return qs
    filtro = (Q(destinos__municipio__nome__unaccent__icontains=busca)
              | Q(servidores__nome__unaccent__icontains=busca)
              | Q(motivo__unaccent__icontains=busca))
    # "OS 7/2026" procura só a OS; "7/2026" procura a OS e o ofício vinculado com esse número.
    so_os = busca[:2].lower() == "os"
    partes = (busca[2:] if so_os else busca).strip().split("/", 1)
    if all(p.isascii() and p.isdecimal() for p in partes) and partes[0]:
        if len(partes) == 2:
            numero, ano = int(partes[0][:6]), int(partes[1][:4])
            filtro |= Q(numero=numero, ano=ano)
            if not so_os:
                filtro |= Q(oficios__numero=numero, oficios__ano=ano)
        else:
            filtro |= Q(numero=int(partes[0][:6]))
    return qs.filter(filtro).distinct()


@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    if not request.user.has_perm("viagens.view_ordemservico"):
        raise PermissionDenied
    base = policies.ordens_visiveis(request.user)
    oficio = None
    oficio_pk = request.GET.get("oficio") or ""
    if oficio_pk.isascii() and oficio_pk.isdecimal():
        oficio = policies.oficios_visiveis(request.user).filter(pk=int(oficio_pk)).first()
        base = base.filter(oficios__pk=int(oficio_pk))
    aba = request.GET.get("aba") or ""
    if aba not in {a for a, _, _ in ABAS}:
        aba = ""
    busca = (request.GET.get("q") or "").strip()
    qs = ordens.com_dados(_buscar(_filtrar(base, aba), busca).order_by("-ano", "-numero"))
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    linhas = [{"ordem": o, "periodo": ordens.periodo_curto(o), "faltando": ordens.faltando(o),
               "editavel": policies.pode_editar_ordem(request.user, o),
               "cancelavel": policies.pode_cancelar_ordem(request.user, o),
               "excluivel": policies.pode_excluir_ordem(request.user, o)}
              for o in pagina.object_list]
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    return render(request, "viagens/ordens/lista.html", {
        "page_obj": pagina, "linhas": linhas, "abas": ABAS, "aba": aba, "busca": busca,
        "contagens": {"todas": base.count(),
                      **{c: _filtrar(base, c).count() for c, _, _ in ABAS if c}},
        "hoje": timezone.localdate(), "oficio": oficio,
        "oficio_filtro": oficio_pk if oficio is not None else "",
        "pode_os_do_oficio": (oficio is not None
                              and policies.pode_criar_ordem_do_oficio(request.user, oficio)),
        "querystring_base": (filtros.urlencode() + "&") if filtros else "",
        "voltar": request.get_full_path(), "pode_criar": policies.pode_criar_ordem(request.user),
        "migalhas": _migalhas(("Ordens de serviço", ""))})


def _ordem_visivel(request: HttpRequest, pk: int) -> OrdemServico:
    ordem = get_object_or_404(ordens.com_dados(OrdemServico.objects.all()), pk=pk)
    if not policies.pode_ver_ordem(request.user, ordem):
        raise PermissionDenied
    return ordem


def _oficios_escolhiveis(request: HttpRequest):
    return policies.oficios_visiveis(request.user).exclude(situacao=Oficio.Situacao.CANCELADO)


def _formulario(request: HttpRequest, *args, ordem=None, **kwargs) -> FormularioOrdem:
    extras = {"oficios": _oficios_escolhiveis(request),
              "unidade": policies.unidade_do_usuario(request.user),
              "fonte_oficios": reverse("viagens:buscar_oficios"),
              "fonte_servidores": reverse("cadastros:buscar_servidores"),
              "fonte_municipios": reverse("cadastros:buscar_municipios")}
    if ordem is not None and not args and not kwargs.get("initial"):
        return FormularioOrdem.de(ordem, **extras)
    return FormularioOrdem(*args, ordem=ordem, **extras, **kwargs)


def _copia_prevista(form: FormularioOrdem, ordem) -> dict:
    """O que os ofícios ligados preencheriam nos campos vazios (mostrado sob cada campo)."""
    if ordem is not None:
        oficios = list(ordem.oficios.all())
    else:
        pks = form.initial.get("oficios") or []
        oficios = list(Oficio.objects.filter(pk__in=pks))
    if not oficios:
        return {}
    base = ordens.dados_dos_oficios(oficios)
    equipe = base["servidores"]
    return {k: v for k, v in {
        "destinos": ", ".join(f"{m.nome}/{m.uf}" for m in base["destinos"]),
        "periodo": ordens.periodo_curto(OrdemServico(data_inicio=base["inicio"],
                                                     data_fim=base["fim"])),
        "servidores": (f"{len(equipe)} servidor{'es' if len(equipe) != 1 else ''}: "
                       + ", ".join(s.nome for s in equipe[:4])
                       + (f" e mais {len(equipe) - 4}" if len(equipe) > 4 else ""))
        if equipe else "",
        "motivo": base["motivo"],
    }.items() if v}


def _tela(request: HttpRequest, form: FormularioOrdem, ordem=None, status: int = 200):
    editavel = ordem is None or policies.pode_editar_ordem(request.user, ordem)
    unidade = ordem.unidade if ordem else policies.unidade_do_usuario(request.user)
    return render(request, "viagens/ordens/editar.html", {
        "form": form, "ordem": ordem, "editavel": editavel,
        "faltando": ordens.faltando(ordem) if ordem else [],
        "copia": _copia_prevista(form, ordem),
        "assinatura_prevista": ordens.assinatura_prevista(ordem, unidade),
        "periodo": ordens.periodo_curto(ordem) if ordem else "",
        "proximo_numero": None if ordem else ordens.proximo_numero_do_ano(
            timezone.localdate().year),
        "ano": timezone.localdate().year,
        "pode_cancelar": ordem is not None and policies.pode_cancelar_ordem(request.user, ordem),
        "pode_excluir": ordem is not None and policies.pode_excluir_ordem(request.user, ordem),
        "pode_gerir_textos": politicas_cadastros.pode_gerir_textos(request.user),
        "migalhas": _migalhas(("Ordens de serviço", reverse("viagens:ordens")),
                              (str(ordem) if ordem else "Nova ordem de serviço", ""))},
        status=status)


def _gravar(request: HttpRequest, form: FormularioOrdem, ordem=None) -> HttpResponse:
    if form.is_valid():
        try:
            salva, copiados = ordens.salvar(request.user, pk=ordem.pk if ordem else None,
                                            **form.cleaned_data)
        except ordens.OrdemInvalida as exc:
            form.add_error(None, str(exc))
        else:
            texto = f"{salva} {'atualizada' if ordem else 'criada'}."
            if copiados:
                texto += f" Copiado dos ofícios: {', '.join(copiados)}."
            if "função da equipe" in ordens.faltando(salva):
                messages.warning(request, f"{texto} Agora escolha a função de cada um da equipe "
                                          "(o tipo de necessidade usa funções).")
                return redirect(reverse("viagens:editar_ordem", args=[salva.pk]) + "#t-equipe")
            messages.success(request, texto)
            return redirect("viagens:editar_ordem", salva.pk)
    return _tela(request, form, ordem, status=422)


@require_http_methods(["GET", "POST"])
def nova(request: HttpRequest) -> HttpResponse:
    policies.exigir(policies.pode_criar_ordem(request.user),
                    "Você não pode criar Ordens de Serviço.")
    if request.method == "POST":
        return _gravar(request, _formulario(request, request.POST))
    inicial: dict = {"tipo": "padrao"}
    oficio_pk = request.GET.get("oficio") or ""
    if (oficio_pk.isascii() and oficio_pk.isdecimal()
            and _oficios_escolhiveis(request).filter(pk=int(oficio_pk)).exists()):
        inicial["oficios"] = [int(oficio_pk)]
    return _tela(request, _formulario(request, initial=inicial))


@require_POST
def criar_do_oficio(request: HttpRequest, oficio_pk: int) -> HttpResponse:
    """"Nova ordem de serviço" na janela do ofício: cria ligada a ele (copiando destinos,
    período, equipe e motivo) e abre a OS."""
    oficio = get_object_or_404(_oficios_escolhiveis(request), pk=oficio_pk)
    policies.exigir(policies.pode_criar_ordem_do_oficio(request.user, oficio),
                    "Só a unidade do ofício cria ordens de serviço a partir dele.")
    try:
        ordem, _ = ordens.salvar(request.user, oficios=[oficio])
    except ordens.OrdemInvalida as exc:
        messages.error(request, str(exc))
        return redirect(f"{reverse('viagens:nova_ordem')}?oficio={oficio.pk}")
    messages.success(request, f"{ordem} criada a partir do Ofício {oficio.numero_formatado}. "
                              "Confira o tipo de necessidade e gere o documento.")
    return redirect("viagens:editar_ordem", ordem.pk)


@require_http_methods(["GET", "POST"])
def editar(request: HttpRequest, pk: int) -> HttpResponse:
    ordem = _ordem_visivel(request, pk)
    if request.method == "POST":
        policies.exigir(policies.pode_editar_ordem(request.user, ordem),
                        "Esta Ordem de Serviço não pode ser alterada.")
        return _gravar(request, _formulario(request, request.POST, ordem=ordem), ordem)
    return _tela(request, _formulario(request, ordem=ordem), ordem)


@require_GET
def documento(request: HttpRequest, pk: int, formato: str) -> HttpResponse:
    ordem = _ordem_visivel(request, pk)
    policies.exigir(policies.pode_editar_ordem(request.user, ordem),
                    "Reative a Ordem de Serviço para gerar o documento.")
    if formato not in ("pdf", "docx"):
        raise Http404
    try:
        dados = ordens.dados_do_documento(ordem)
    except ordens.OrdemInvalida as exc:
        messages.error(request, str(exc))
        return redirect("viagens:editar_ordem", ordem.pk)
    nome = f"os-{ordem.numero:03d}-{ordem.ano}.{formato}"
    if formato == "pdf":
        resposta = HttpResponse(ordens.pdf_do_documento(dados), content_type="application/pdf")
        resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    else:
        resposta = HttpResponse(ordens.docx_do_documento(dados), content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
        resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    resposta["Cache-Control"] = "no-store"  # nomes e cargos da equipe
    return resposta


def _voltar(request: HttpRequest, padrao: str, ordem_pk: int | None = None) -> str:
    """A lista como estava, ou a própria OS (quando a ação veio dela)."""
    voltar = request.POST.get("voltar") or ""
    caminhos = {reverse("viagens:ordens")}
    if ordem_pk is not None:
        caminhos.add(reverse("viagens:editar_ordem", args=[ordem_pk]))
    if (urlsplit(voltar).path in caminhos
            and url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()})):
        return voltar
    return padrao


def _acao(request: HttpRequest, pk: int, executar):
    ordem = _ordem_visivel(request, pk)
    try:
        mensagem = executar(ordem)
    except (ordens.OrdemInvalida, PermissionDenied) as exc:
        messages.error(request, str(exc))
    except OrdemServico.DoesNotExist:  # excluída por outra pessoa no meio do caminho
        messages.error(request, "Esta Ordem de Serviço não existe mais.")
        return redirect("viagens:ordens")
    else:
        messages.success(request, mensagem)
    return redirect(_voltar(request, reverse("viagens:ordens"), ordem_pk=pk))


@require_POST
def cancelar(request: HttpRequest, pk: int) -> HttpResponse:
    def executar(o):
        ordens.cancelar(request.user, o.pk, request.POST.get("motivo", ""))
        return f"{o} cancelada. O histórico foi mantido."
    return _acao(request, pk, executar)


@require_POST
def reativar(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda o: f"{ordens.reativar(request.user, o.pk)} reativada.")


@require_POST
def excluir(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda o: f"{ordens.excluir(request.user, o.pk)} excluída; o "
                                        "número volta a ficar livre.")
