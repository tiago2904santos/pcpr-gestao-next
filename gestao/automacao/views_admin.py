"""Telas de governança da automação: credenciais por integração (serviço e pessoais),
aprovações de ações irreversíveis, histórico das ferramentas executadas e links pessoais.

O token em claro aparece UMA vez, na própria resposta da criação/rotação (nunca vai para
a sessão, o log ou a URL).
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import ferramentas, links, policies
from .api import credenciais
from .models import LinkAcesso
from .models_api import CredencialIntegracao, ExecucaoFerramenta, PedidoAprovacao

T = CredencialIntegracao.Tipo


def _exigir(condicao: bool) -> None:
    if not condicao:
        raise PermissionDenied


def _migalhas(*itens):
    return [("Início", reverse("painel:inicio")), ("Automação", reverse("automacao:painel")),
            *itens]


def _pagina(request, qs, por=25):
    return Paginator(qs, por).get_page(request.GET.get("pagina"))


# ------------------------------------------------------------------ credenciais
@never_cache
@require_http_methods(["GET", "POST"])
def credenciais_lista(request: HttpRequest) -> HttpResponse:
    """Quem administra vê e emite as de serviço; cada pessoa vê e emite as pessoais dela."""
    u = request.user
    _exigir(policies.pode_ver(u))
    if not u.is_authenticated:  # pode_ver já barrou o anônimo; aqui só estreita o tipo
        raise PermissionDenied
    token_novo = ""  # nosec B105 — ainda nenhum token emitido nesta requisição
    if request.method == "POST":
        tipo = request.POST.get("tipo", "")
        nome = (request.POST.get("nome") or "").strip()
        try:
            dias = int(request.POST.get("dias") or 30)
            lista = [f.strip() for f in (request.POST.get("ferramentas") or "").split(",")
                     if f.strip()]
            if tipo not in T.values or not nome:
                raise credenciais.CredencialInvalida("Informe o nome e o tipo.")
            _, token_novo = credenciais.emitir(u, nome=nome, tipo=tipo, dias=dias,
                                               ferramentas=lista if tipo == T.IA else None)
        except credenciais.CredencialInvalida as erro:
            messages.error(request, str(erro) or "Confira o nome, o tipo e a validade.")
        except ValueError:
            messages.error(request, "Validade: informe o número de dias (só algarismos).")
        except PermissionDenied as erro:
            messages.error(request, str(erro) or "Sem permissão.")
    qs = CredencialIntegracao.objects.select_related("usuario", "criada_por")
    if not policies.pode_administrar(u):
        qs = qs.filter(tipo=T.PESSOAL, usuario=u)
    agora = timezone.now()
    return render(request, "automacao/credenciais.html", {
        "linhas": [(c, c.revogada_em is None and not c.emergencia and c.expira_em > agora)
                   for c in qs[:100]],
        "token_novo": token_novo, "pode_administrar": policies.pode_administrar(u),
        "nomes_ferramentas": [f.nome for f in ferramentas.todas()],
        "migalhas": _migalhas(("Credenciais", "")),
    })


@never_cache
@require_POST
def acao_credencial(request: HttpRequest, pk: int, acao: str) -> HttpResponse:
    _exigir(policies.pode_ver(request.user))
    c = get_object_or_404(CredencialIntegracao, pk=pk)
    token_novo = ""  # nosec B105 — ainda nenhum token emitido nesta requisição
    try:
        if acao == "revogar":
            credenciais.revogar(request.user, c.pk)
            messages.success(request, "Credencial revogada: a próxima chamada leva 401.")
        elif acao == "emergencia":
            credenciais.emergencia(request.user, c.pk, ligar=not c.emergencia)
            messages.success(request, "Modo emergência alterado.")
        elif acao == "rotacionar":
            _, token_novo = credenciais.rotacionar(request.user, c.pk)
        else:
            raise Http404
    except PermissionDenied:
        raise Http404 from None
    except credenciais.CredencialInvalida as erro:
        messages.error(request, str(erro))
    if token_novo:
        return render(request, "automacao/credencial_nova.html", {
            "token_novo": token_novo, "migalhas": _migalhas(("Credenciais", reverse(
                "automacao:credenciais")), ("Nova credencial", ""))})
    return redirect("automacao:credenciais")


# ------------------------------------------------------------------ aprovações
@require_GET
def aprovacoes(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_operar(request.user))
    qs = PedidoAprovacao.objects.select_related("pedido_por", "decidido_por")
    if not (policies.ve_todas_unidades(request.user) or policies.pode_administrar(request.user)):
        unidade = policies.unidade_do_usuario(request.user)
        # unidade_id=None seria o mesmo que unidade__isnull=True.
        qs = (qs.filter(unidade_id=unidade) if unidade is not None
              else qs.filter(unidade__isnull=True))
    pendentes = request.GET.get("aba") != "decididos"
    qs = qs.filter(situacao=PedidoAprovacao.Situacao.PENDENTE) if pendentes else \
        qs.exclude(situacao=PedidoAprovacao.Situacao.PENDENTE)
    pagina = _pagina(request, qs)
    itens = []
    for p in pagina:
        f = ferramentas.obter(p.ferramenta)
        itens.append({"p": p, "acao": f.descricao if f else p.ferramenta})
    return render(request, "automacao/aprovacoes.html", {
        "page_obj": pagina, "itens": itens, "pendentes": pendentes,
        "migalhas": _migalhas(("Aprovações", "")),
    })


@require_POST
def decidir_aprovacao(request: HttpRequest, pk: int, acao: str) -> HttpResponse:
    _exigir(policies.pode_operar(request.user))
    if not policies.pode_operar_objeto(request.user, get_object_or_404(PedidoAprovacao, pk=pk)):
        raise Http404
    try:
        if acao == "aprovar":
            p = ferramentas.aprovar(request.user, pk)
            if p.situacao == PedidoAprovacao.Situacao.FALHOU:
                messages.error(request, f"Aprovado, mas não executou: {p.motivo}")
            else:
                messages.success(request, "Aprovado e executado com a sua permissão.")
        elif acao == "recusar":
            ferramentas.recusar(request.user, pk, request.POST.get("motivo", ""))
            messages.success(request, "Pedido recusado.")
        else:
            raise Http404
    except ferramentas.FerramentaRecusada as erro:
        messages.error(request, str(erro))
    except PermissionDenied as erro:
        messages.error(request, str(erro) or "Você não tem permissão para esta ação.")
    return redirect("automacao:aprovacoes")


# ------------------------------------------------------------------ histórico
@require_GET
def execucoes(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_administrar(request.user))
    qs = ExecucaoFerramenta.objects.select_related("usuario", "credencial", "delegacao")
    if f := request.GET.get("ferramenta"):
        qs = qs.filter(ferramenta=f[:80])
    return render(request, "automacao/execucoes.html", {
        "page_obj": _pagina(request, qs, 50), "ferramentas": ferramentas.todas(),
        "filtro": request.GET.get("ferramenta", ""),
        "migalhas": _migalhas(("Histórico da automação", "")),
    })


# ------------------------------------------------------------------ links pessoais
@require_GET
def links_lista(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_operar(request.user))
    qs = LinkAcesso.objects.select_related("servidor", "criado_por")
    if not (policies.ve_todas_unidades(request.user) or policies.pode_administrar(request.user)):
        unidade = policies.unidade_do_usuario(request.user)
        qs = qs.filter(Q(servidor__unidade_id=unidade) | Q(servidor__unidade__isnull=True))
    agora = timezone.now()
    vigentes_24h = LinkAcesso.objects.filter(
        revogado_em__isnull=True, expira_em__gt=agora,
        criado_em__gte=agora - timedelta(hours=24)).count()
    if request.GET.get("todos") != "1":
        qs = qs.filter(revogado_em__isnull=True, expira_em__gt=agora)
    return render(request, "automacao/links.html", {
        "vigentes_24h": vigentes_24h,
        "motivos_massa": [
            (LinkAcesso.Motivo.VAZAMENTO, "Suspeita de vazamento ou aparelho perdido"),
            (LinkAcesso.Motivo.MANUAL, "Outro motivo (fica no histórico)")],
        "page_obj": _pagina(request, qs), "todos": request.GET.get("todos") == "1",
        "pode_administrar": policies.pode_administrar(request.user),
        "migalhas": _migalhas(("Links pessoais", "")),
    })


@require_POST
def revogar_link(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(policies.pode_operar(request.user))
    try:
        links.revogar(request.user, pk)
        messages.success(request, "Link revogado.")
    except links.LinkInvalido as erro:
        messages.error(request, str(erro))
    except LinkAcesso.DoesNotExist as erro:
        raise Http404 from erro
    return redirect("automacao:links")


@require_POST
def revogar_links_em_massa(request: HttpRequest) -> HttpResponse:
    """Roteiro de incidente: todos os links emitidos nas últimas N horas param de valer."""
    _exigir(policies.pode_administrar(request.user))
    try:
        horas = max(1, min(24 * 30, int(request.POST.get("horas") or 24)))
    except ValueError:
        horas = 24
    motivo = request.POST.get("motivo") or ""
    if motivo not in (LinkAcesso.Motivo.VAZAMENTO, LinkAcesso.Motivo.MANUAL):
        messages.error(request, "Escolha o motivo da revogação.")
        return redirect("automacao:links")
    total = links.revogar_em_massa(request.user, desde=timezone.now() - timedelta(hours=horas),
                                   motivo=motivo)
    messages.success(request, f"{total} link{'s' if total != 1 else ''} revogado"
                              f"{'s' if total != 1 else ''} (emitidos nas últimas {horas} h).")
    return redirect("automacao:links")


# ------------------------------------------------------------------ delegação
@never_cache
@require_http_methods(["GET", "POST"])
def delegar(request: HttpRequest) -> HttpResponse:
    """A ação humana que autoriza uma automação de IA a agir por você, uma vez, num recurso:
    escolhe a credencial de IA, a ferramenta e o recurso. O id da delegação aparece uma vez
    (vai no evento ou no pedido ao n8n). Perfil administrativo não delega (regra do contrato).
    """
    from .api import delegacoes

    _exigir(policies.pode_ver(request.user))
    agora = timezone.now()
    credenciais_ia = list(CredencialIntegracao.objects.filter(
        tipo=T.IA, revogada_em__isnull=True, emergencia=False, expira_em__gt=agora))
    emitido = ""  # o identificador da delegação, mostrado uma vez
    if request.method == "POST":
        cred = next((c for c in credenciais_ia
                     if str(c.pk) == request.POST.get("credencial", "")), None)
        ferramenta = (request.POST.get("ferramenta") or "").strip()
        recurso = (request.POST.get("recurso") or "").strip()[:80]
        f = ferramentas.obter(ferramenta)
        try:
            if cred is None or f is None:
                raise delegacoes.DelegacaoNegada("Escolha a credencial e a ferramenta.")
            entrada = _entrada_do_recurso(f, recurso)
            if not entrada or f.recurso(entrada) != recurso:
                raise delegacoes.DelegacaoNegada("O recurso não corresponde à ferramenta.")
            if not f.permitido(request.user, entrada):
                raise delegacoes.DelegacaoNegada("Você não pode delegar o que não pode fazer.")
            _, emitido = delegacoes.emitir(request.user, cred, ferramentas=[ferramenta],
                                         recurso=recurso,
                                         motivo=(request.POST.get("motivo") or "")[:200]
                                         or "Delegação pela tela", minutos=10)
        except delegacoes.DelegacaoNegada as erro:
            messages.error(request, str(erro))
    return render(request, "automacao/delegar.html", {
        "credenciais_ia": credenciais_ia, "token": emitido,
        "ferramentas": [f for f in ferramentas.todas()
                        if any(f.nome in (c.ferramentas or []) for c in credenciais_ia)],
        "migalhas": _migalhas(("Delegar a uma automação", "")),
    })


def _entrada_do_recurso(f, recurso: str) -> dict:
    """`viagens.prestacaoservidor:42` → a entrada da ferramenta (o primeiro campo inteiro)."""
    _, _, pk = recurso.rpartition(":")
    campo = next((nome for nome, c in f.entrada.items() if c.tipo == "inteiro"), "")
    return {campo: int(pk)} if campo and pk.isdigit() else {}
