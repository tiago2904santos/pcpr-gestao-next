"""Conferência e registro explícito de envio manual; abrir WhatsApp não envia."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import envios_manuais as envios
from . import policies
from .dominio.envios import url_whatsapp

# A entrada é a aba Pendências da Agenda (seção dos envios); esta lista guarda o histórico.
PENDENCIAS = "painel:pendencias"


@require_GET
def lista(request):
    if not policies.pode_listar_prestacoes(request.user):
        raise PermissionDenied
    historico = request.GET.get("aba") == "historico"
    qs = envios.pendencias(request.user)
    qs = qs.filter(situacao="manual") if historico else qs.filter(situacao="aguardando_aprovacao")
    pagina = Paginator(qs, 25).get_page(request.GET.get("pagina"))
    return render(request, "viagens/envios/lista.html", {
        "page_obj": pagina, "historico": historico, "modo_manual": envios.manual(),
        "querystring_base": "aba=historico&" if historico else "",
        "pode_atualizar": policies.altera_prestacoes(request.user),
        "migalhas": [("Agenda", reverse("painel:agenda")), ("Pendências", reverse(PENDENCIAS)),
                     ("Envios manuais", "")]})


@require_POST
def atualizar(request):
    if not policies.altera_prestacoes(request.user):
        raise PermissionDenied
    total = envios.sincronizar(request.user)
    messages.success(request, f"Pendências atualizadas: {total} novo(s) pacote(s).")
    # Volta para onde o botão estava (a aba Pendências da Agenda ou esta lista).
    proximo = request.POST.get("proximo", "")
    if proximo.startswith("/") and url_has_allowed_host_and_scheme(
            proximo, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(proximo)
    return redirect("viagens:envios_manuais")


@never_cache
@require_http_methods(["GET", "POST"])
def detalhe(request, ps_pk):
    ps = get_object_or_404(policies.prestacoes_visiveis(request.user).select_related(
        "servidor", "prestacao__oficio__unidade"), pk=ps_pk)
    ticket, c, pacote = "", None, None
    if request.method == "GET":
        if request.GET.get("envio", "").isdigit():
            c = get_object_or_404(envios.pendencias(request.user),
                                  pk=int(request.GET["envio"]), contexto__ps=ps.pk,
                                  situacao="manual")
        else:
            ticket = request.session.get(f"envio-manual:{ps.pk}", "")
        if ticket:
            try:
                dados = envios.signing.loads(ticket, salt=envios.SALT, max_age=1800)
                pacote = envios.ler(ps)
                c = envios.pendencias(request.user).filter(
                    pk=dados["c"], revisao=dados["r"],
                    situacao="aguardando_aprovacao", versao=pacote.versao).first()
                if c is None or not hasattr(c, "conteudo"):
                    ticket, c, pacote = "", None, None
            except (envios.signing.BadSignature, ValueError):
                ticket, c, pacote = "", None, None
    if request.method == "POST":
        if not policies.pode_editar_prestacao(request.user, ps):
            raise PermissionDenied
        try:
            if request.POST.get("acao") == "confirmar":
                if request.POST.get("confirmo") != "sim":
                    raise ValueError("Confirme que você enviou a mensagem no WhatsApp.")
                envios.confirmar(request.user, ps.pk, request.POST.get("ticket", ""))
                messages.success(request, "Envio manual registrado. "
                                 "A entrega não é verificada pelo sistema.")
                return redirect(PENDENCIAS)
            if request.POST.get("acao") != "preparar":
                return HttpResponse(status=400)
            c, ticket, pacote = envios.preparar(request.user, ps.pk)
            request.session[f"envio-manual:{ps.pk}"] = ticket
        except ValueError as erro:
            messages.error(request, str(erro))
    try:
        pacote = pacote or envios.ler(ps)
    except ValueError as erro:
        messages.error(request, str(erro))
        return redirect("viagens:envios_manuais")
    texto = c.conteudo.texto if c and hasattr(c, "conteudo") else ""
    return render(request, "viagens/envios/detalhe.html", {
        "ps": ps, "pacote": pacote, "texto": texto, "ticket": ticket, "comunicacao": c,
        "whatsapp": url_whatsapp(ps.servidor.telefone, texto) if texto else "",
        "pode_editar": policies.pode_editar_prestacao(request.user, ps),
        "confirmado": c is not None and c.situacao == "manual",
        "arquivos_atuais": c is not None and c.versao == pacote.versao,
        "pendencias": reverse(PENDENCIAS),
        "migalhas": [("Agenda", reverse("painel:agenda")), ("Pendências", reverse(PENDENCIAS)),
                     (ps.servidor.nome, "")]})


@never_cache
@require_GET
def baixar(request, ps_pk, comunicacao_pk, formato):
    get_object_or_404(policies.prestacoes_visiveis(request.user), pk=ps_pk)
    try:
        conteudo, nome, mime = envios.arquivos(request.user, ps_pk, comunicacao_pk, formato)
    except ValueError as erro:
        messages.error(request, str(erro))
        return redirect("viagens:envio_manual", ps_pk=ps_pk)
    resposta = HttpResponse(conteudo, content_type=mime)
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resposta
