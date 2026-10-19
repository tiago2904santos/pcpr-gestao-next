"""Telas da assistência: painel (uso, tokens e custo estimado), usos (liga/desliga, modo,
limites e orçamento), lista e revisão de sugestões, pedido em andamento — mais a Central de
ajuda (artigos aprovados e o assistente determinístico).

Nenhuma view chama a porta de IA: pedir cria o pedido (no modo regra a sugestão sai na hora,
local); a IA roda no worker `processar_ia`. Escritas pelos serviços; fora do escopo é 404.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from gestao.integracoes.ia import servico as servico_ia
from gestao.integracoes.ia.porta import Origem

from . import assistente, configuracao, conhecimento, ganchos, orcamento, policies, servicos
from .models import ConfiguracaoUso, ConteudoSugestao, PedidoSugestao, Sugestao
from .usos_proprios import recurso_da_pessoa

POR_PAGINA = 25
S = Sugestao.Estado


def _exigir(condicao: bool) -> None:
    if not condicao:
        raise PermissionDenied


def _migalhas(*itens: tuple[str, str]) -> list[tuple[str, str]]:
    return [("Início", reverse("painel:inicio")),
            ("Assistência", reverse("assistencia:painel")), *itens]


def _voltar(request: HttpRequest, padrao: str) -> HttpResponse:
    from django.utils.http import url_has_allowed_host_and_scheme

    destino = (request.POST.get("voltar") or "").strip()
    if (destino.startswith("/") and destino.isprintable() and not any(c.isspace() for c in destino)
            and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()},
                                                require_https=request.is_secure())):
        return redirect(destino)
    return redirect(padrao)


def _simulada() -> bool:
    return servico_ia.adaptador().origem == Origem.SIMULADO


def _descrever(uso: ganchos.UsoIA | None, recurso_id: str):
    if uso is None:
        return None
    try:
        return uso.descrever(recurso_id)
    except ganchos.RecursoInexistente:
        return None


# ------------------------------------------------------------------ painel
@require_GET
def painel(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_ver_painel(request.user))
    mes = orcamento.mes_atual()
    inicio_mes = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    do_mes = Sugestao.objects.filter(criada_em__gte=inicio_mes)
    numeros = do_mes.aggregate(
        total=Count("pk"), decididas=Count("pk", filter=Q(estado__in=Sugestao.DECIDIDAS)),
        aceitas=Count("pk", filter=Q(estado__in=(S.ACEITA, S.EDITADA))),
        com_ia=Count("pk", filter=~Q(origem=Sugestao.Origem.REGRA) & Q(fallback=False)),
        fallback=Count("pk", filter=Q(fallback=True)),
        tokens_entrada=Sum("tokens_entrada"), tokens_saida=Sum("tokens_saida"))
    taxa = (round(100 * numeros["aceitas"] / numeros["decididas"])
            if numeros["decididas"] else None)
    orc = orcamento.resumo(mes)
    por_uso = {linha["uso"]: linha for linha in do_mes.values("uso").annotate(
        total=Count("pk"), custo=Sum("custo_estimado_usd"),
        aceitas=Count("pk", filter=Q(estado__in=(S.ACEITA, S.EDITADA))),
        fallback=Count("pk", filter=Q(fallback=True)))}
    configs = configuracao.todas()
    usos: list[dict[str, object]] = [
        {"uso": u, "config": configs[u.chave], "numeros": por_uso.get(u.chave, {}),
         "orcamento": orc.get(u.chave)} for u in ganchos.usos()]
    return render(request, "assistencia/painel.html", {
        "numeros": numeros, "taxa": taxa, "global": orc.get(orcamento.GLOBAL), "usos": usos,
        "tokens_mes": f"{numeros['tokens_entrada'] or 0} / {numeros['tokens_saida'] or 0}",
        "diagnostico": servico_ia.diagnostico(),
        "pendentes": PedidoSugestao.objects.filter(estado__in=(
            PedidoSugestao.Estado.PENDENTE, PedidoSugestao.Estado.PROCESSANDO)).count(),
        "recentes": list(Sugestao.objects.select_related("decidida_por")[:8]),
        "rotulos": {u.chave: u.rotulo for u in ganchos.usos()},
        "simulador": _simulada() and policies.pode_administrar(request.user),
        "pode_administrar": policies.pode_administrar(request.user),
        "migalhas": [("Início", reverse("painel:inicio")), ("Assistência", "")],
    })


# ------------------------------------------------------------------ usos e orçamento
@require_GET
def usos(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_ver_painel(request.user))
    orc = orcamento.resumo()
    configs = configuracao.todas()
    chamadas = servicos.chamadas_hoje_por_uso()
    linhas = [{"uso": u, "config": configs[u.chave], "orcamento": orc.get(u.chave),
               "chamadas_hoje": chamadas.get(u.chave, 0)} for u in ganchos.usos()]
    return render(request, "assistencia/usos.html", {
        "linhas": linhas, "global": orc.get(orcamento.GLOBAL),
        "modos": ConfiguracaoUso.Modo.choices, "diagnostico": servico_ia.diagnostico(),
        "pode_administrar": policies.pode_administrar(request.user),
        "migalhas": _migalhas(("Usos, limites e orçamento", "")),
    })


def _inteiros(request: HttpRequest) -> dict[str, int]:
    saida = {}
    for nome in configuracao.LIMITES:
        bruto = (request.POST.get(nome) or "").strip()
        if bruto:
            if not bruto.isdigit():
                raise ValueError("Use só números inteiros nos limites.")
            saida[nome] = int(bruto)
    return saida


@require_POST
def alterar_uso(request: HttpRequest, chave: str) -> HttpResponse:
    _exigir(policies.pode_administrar(request.user))
    try:
        configuracao.alterar(request.user, chave, ligado=request.POST.get("ligado") == "1",
                             modo=request.POST.get("modo", ""),
                             motivo=request.POST.get("motivo", ""), **_inteiros(request))
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Configuração do uso salva.")
    return redirect(reverse("assistencia:usos") + f"#uso-{slugify(chave)}")


def _teto(bruto: str) -> Decimal | None:
    bruto = (bruto or "").strip().replace(",", ".")
    if not bruto:
        return None
    try:
        return Decimal(bruto).quantize(Decimal("0.0001"))
    except InvalidOperation:
        raise ValueError("Informe o teto em dólares, ex.: 5,00.") from None


@require_POST
def definir_teto(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_administrar(request.user))
    escopo = request.POST.get("escopo", "")
    if escopo != orcamento.GLOBAL and ganchos.uso(escopo) is None:
        raise Http404
    try:
        orcamento.definir_teto(request.user, escopo, _teto(request.POST.get("teto", "")))
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Teto do mês salvo (custo estimado).")
    return redirect(reverse("assistencia:usos") + (
        "#orcamento" if escopo == orcamento.GLOBAL else f"#uso-{slugify(escopo)}"))


@require_POST
def processar_agora(request: HttpRequest) -> HttpResponse:
    """Simulador: roda a fila na hora (só com a porta simulada, sem rede e sem custo)."""
    _exigir(policies.pode_administrar(request.user) and _simulada())
    n = servicos.processar_fila()
    messages.success(request, f"{n} pedido(s) processado(s) pela IA simulada.")
    return _voltar(request, reverse("assistencia:painel"))


# ------------------------------------------------------------------ sugestões
@require_GET
def sugestoes(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_ver_painel(request.user))
    qs = Sugestao.objects.select_related("decidida_por")
    estado = request.GET.get("estado", "")
    uso = request.GET.get("uso", "")
    if estado in S.values:
        qs = qs.filter(estado=estado)
    if uso and ganchos.uso(uso):
        qs = qs.filter(uso=uso)
    contagem = dict(Sugestao.objects.values_list("estado").annotate(n=Count("pk")))
    abas = [("", "Todas", sum(contagem.values()))] + [
        (valor, rotulo, contagem.get(valor, 0)) for valor, rotulo in S.choices]
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    pares = [(k, v) for k, v in request.GET.items() if k not in ("pagina", "estado") and v]
    return render(request, "assistencia/sugestoes.html", {
        "page_obj": pagina, "linhas": list(pagina), "abas": abas, "estado": estado,
        "uso_filtro": uso, "usos": ganchos.usos(),
        "rotulos": {u.chave: u.rotulo for u in ganchos.usos()},
        "qs_sem_aba": urlencode(pares),
        "querystring_base": urlencode([(k, v) for k, v in request.GET.items()
                                       if k != "pagina" and v]),
        "migalhas": _migalhas(("Sugestões", "")),
    })


def _sugestao_visivel(request: HttpRequest, pk: int) -> tuple[Sugestao, ganchos.UsoIA]:
    s = get_object_or_404(Sugestao.objects.select_related("pedido", "decidida_por"), pk=pk)
    uso = ganchos.uso(s.uso)
    if uso is None or not policies.pode_ver(request.user, uso, s.recurso_id):
        raise Http404
    return s, uso


def _revisao(request: HttpRequest, s: Sugestao, uso: ganchos.UsoIA,
             editados: dict[str, str] | None = None, *, status: int = 200) -> HttpResponse:
    """A tela de revisão. Depois de um envio que falhou, `editados` traz o que a pessoa
    escreveu: é ele que volta aos campos, nunca a sugestão original."""
    conteudo = ConteudoSugestao.objects.filter(sugestao=s).first()
    atuais = servicos.textos_atuais(request.user, s) if conteudo else {}
    editados = editados or {}
    itens = []
    for i in (conteudo.itens if conteudo else []):
        editado = editados.get(i["campo"])
        itens.append({**i, "atual": atuais.get(i["campo"], ""), "editado": editado,
                      "texto": editado if editado is not None else i["valor"]})
    aplicaveis = [i for i in itens if i.get("aplicavel")]
    assunto = _descrever(uso, s.recurso_id)
    rotulos = ", ".join(f"“{i['rotulo']}”" for i in aplicaveis)
    return render(request, "assistencia/sugestao.html", {
        "s": s, "uso": uso, "itens": itens, "conteudo": conteudo, "assunto": assunto,
        "lacunas": [(c, uso.lacunas_conhecidas.get(c, c)) for c in s.lacunas],
        "aplicavel": bool(uso.aplicar) and bool(aplicaveis),
        "pede_substituir": any(i.get("nota") for i in aplicaveis),
        "substituiveis": ", ".join(f"“{i['rotulo']}”" for i in aplicaveis
                                   if i.get("nota") and i["atual"].strip()),
        "acao_aplicar": (f"Gravar {rotulos} em {assunto.rotulo}" if assunto
                         else f"Gravar {rotulos} no registro"),
        "com_edicao": bool(editados),
        "pode_decidir": s.estado == S.PRONTA and policies.pode_decidir(request.user, uso,
                                                                       s.recurso_id),
        "motivos": [m for m in Sugestao.MotivoDescarte.choices if m[0]],
        "migalhas": _migalhas(("Sugestões", reverse("assistencia:sugestoes")
                               if policies.pode_ver_painel(request.user) else ""),
                              (f"Sugestão #{s.pk}", "")),
    }, status=status)


@require_GET
def sugestao(request: HttpRequest, pk: int) -> HttpResponse:
    s, uso = _sugestao_visivel(request, pk)
    servicos.marcar_obsoleta_se_mudou(s)
    return _revisao(request, s, uso)


@require_POST
def aceitar(request: HttpRequest, pk: int) -> HttpResponse:
    s, uso = _sugestao_visivel(request, pk)
    editados = {k.removeprefix("texto-"): request.POST.get(k, "") for k in request.POST
                if k.startswith("texto-")}
    try:
        s = servicos.aceitar(request.user, s.pk, editados,
                             substituir=request.POST.get("substituir") == "1")
    except ganchos.TextoHumano as exc:
        messages.warning(request, f"{exc} O seu texto editado continua nos campos.")
        return _revisao(request, s, uso, editados, status=409)
    except (ganchos.AplicacaoRecusada, PermissionDenied) as exc:
        messages.error(request, str(exc) or "Você não pode decidir esta sugestão.")
        s.refresh_from_db()
        return _revisao(request, s, uso, editados, status=409)
    if s.estado == S.OBSOLETA:
        messages.warning(request, "Os dados mudaram desde a sugestão: nada foi gravado. O seu "
                                  "texto editado aparece abaixo para copiar; peça outra "
                                  "sugestão com os dados atuais.")
        return _revisao(request, s, uso, editados, status=409)
    if s.aplicada:
        messages.success(request, "Texto aplicado no registro. Ele continua editável lá.")
        assunto = _descrever(uso, s.recurso_id)
        if assunto and assunto.url:
            return redirect(assunto.url)
    else:
        messages.success(request, "Decisão registrada. Nada foi gravado no registro.")
    return redirect("assistencia:sugestao", pk=s.pk)


@require_POST
def descartar(request: HttpRequest, pk: int) -> HttpResponse:
    s, _uso = _sugestao_visivel(request, pk)
    try:
        servicos.descartar(request.user, s.pk, request.POST.get("motivo", ""))
    except (ganchos.AplicacaoRecusada, PermissionDenied) as exc:
        messages.error(request, str(exc) or "Você não pode decidir esta sugestão.")
    else:
        messages.success(request, "Sugestão descartada. O registro não mudou.")
    return redirect("assistencia:sugestao", pk=s.pk)


# ------------------------------------------------------------------ pedir e acompanhar
def _uso_visivel(request: HttpRequest, chave: str, recurso_id: str) -> ganchos.UsoIA:
    uso = ganchos.uso(chave)
    if uso is None or not policies.pode_ver(request.user, uso, recurso_id):
        raise Http404
    return uso


def pedir(request: HttpRequest, chave: str, recurso_id: str) -> HttpResponse:
    uso = _uso_visivel(request, chave, recurso_id)
    if request.method == "GET":
        anterior, sugestao_anterior = servicos.ultima(uso.chave, recurso_id)
        return render(request, "assistencia/pedir.html", {
            "uso": uso, "recurso_id": recurso_id, "assunto": _descrever(uso, recurso_id),
            "anterior": anterior, "sugestao_anterior": sugestao_anterior,
            "config": configuracao.de(uso.chave),
            "pode_pedir": policies.pode_pedir(request.user, uso, recurso_id),
            "voltar": request.GET.get("voltar", ""),
            "migalhas": _migalhas((uso.rotulo, ""))})
    if request.method != "POST":
        return HttpResponse(status=405)
    opcoes = {o.nome: request.POST.get(o.nome, "") for o in uso.opcoes}
    try:
        pedido = servicos.pedir(request.user, uso.chave, recurso_id, opcoes)
    except servicos.PedidoRecusado as exc:
        messages.error(request, str(exc))
        return _voltar(request, reverse("assistencia:pedir", args=[uso.chave, recurso_id]))
    except (PermissionDenied, ganchos.RecursoInexistente):
        raise Http404 from None
    s = Sugestao.objects.filter(pedido=pedido).first()
    if s is not None:
        return redirect("assistencia:sugestao", pk=s.pk)
    return redirect("assistencia:pedido", pk=pedido.pk)


@require_GET
def pedido(request: HttpRequest, pk: int) -> HttpResponse:
    p = get_object_or_404(PedidoSugestao, pk=pk)
    uso = _uso_visivel(request, p.uso, p.recurso_id)
    s = Sugestao.objects.filter(pedido=p).first()
    if s is not None:
        return redirect("assistencia:sugestao", pk=s.pk)
    return render(request, "assistencia/pedido.html", {
        "p": p, "uso": uso, "assunto": _descrever(uso, p.recurso_id),
        "simulador": _simulada() and policies.pode_administrar(request.user),
        "migalhas": _migalhas((uso.rotulo, ""), (f"Pedido #{p.pk}", ""))})


# ------------------------------------------------------------------ Central de ajuda
@require_http_methods(["GET", "POST"])
def central(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_usar_central(request.user))
    q = " ".join((request.GET.get("q") or "").split())[:200]
    # A dúvida chega só no corpo de um POST (com CSRF) e a resposta sai na hora: nunca na URL,
    # onde iria para o log de acesso, o histórico do navegador e o Referer.
    pergunta = (" ".join((request.POST.get("pergunta") or "").split())[:1000]
                if request.method == "POST" else "")
    artigos = ([a for a, _ in conhecimento.buscar(q, publico="usuario", limite=20, minimo=0.5)]
               if q else conhecimento.aprovados("usuario"))
    resposta = assistente.responder(pergunta, None, publico="usuario") if pergunta else None
    reformular = configuracao.de("assistencia.reformular_resposta")
    return render(request, "assistencia/central.html", {
        "artigos": artigos, "q": q, "pergunta": pergunta, "resposta": resposta,
        "pode_reformular": bool(resposta and resposta.categoria in ("orientacao", "dados")
                                and reformular.ligado
                                and reformular.modo == ConfiguracaoUso.Modo.IA),
        "recurso_reformular": recurso_da_pessoa(request.user, pergunta) if pergunta else "",
        "hoje": timezone.localdate(),
        "migalhas": [("Início", reverse("painel:inicio")), ("Central de ajuda", "")],
    })


@require_GET
def artigo(request: HttpRequest, slug: str) -> HttpResponse:
    _exigir(policies.pode_usar_central(request.user))
    a = conhecimento.por_slug(slug)
    if a is None:
        raise Http404
    return render(request, "assistencia/artigo.html", {
        "a": a, "revisao_vencida": a.revisao_vencida(timezone.localdate()),
        "migalhas": [("Início", reverse("painel:inicio")),
                     ("Central de ajuda", reverse("ajuda:central")), (a.titulo, "")],
    })
