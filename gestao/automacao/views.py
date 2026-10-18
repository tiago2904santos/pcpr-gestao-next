"""Telas da automação: painel, canal e chaves, comunicações, recebidos, exceções, contatos e
testadores — mais o simulador (só com o canal simulado).

Toda escrita vai pelos serviços (que conferem a permissão de novo, com a linha travada);
aqui só se decide o que mostrar e para onde voltar. Fora do escopo da unidade é 404.
"""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from gestao.integracoes.whatsapp import config as whatsapp_config
from gestao.integracoes.whatsapp import servico as whatsapp

from . import (
    chaves,
    comunicacoes,
    contatos,
    excecoes,
    forms,
    ganchos,
    policies,
    recebimentos,
    simulador,
)
from .models import (
    ChaveAutomacao,
    Comunicacao,
    ContatoVerificado,
    DestinatarioAutorizado,
    ExcecaoAutomacao,
    Recebimento,
)

POR_PAGINA = 25
S = Comunicacao.Situacao


def _exigir(condicao: bool) -> None:
    if not condicao:
        raise PermissionDenied


def _migalhas(*itens: tuple[str, str]) -> list[tuple[str, str]]:
    return [("Início", reverse("painel:inicio")), ("Automação", reverse("automacao:painel")),
            *itens]


def _voltar(request: HttpRequest, padrao: str) -> HttpResponse:
    destino = request.POST.get("voltar") or ""
    if destino.startswith("/automacao/") and "//" not in destino:
        return redirect(destino)
    return redirect(padrao)


def _paginar(request: HttpRequest, qs):
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    pares = [(k, v) for k, vs in request.GET.lists() for v in vs if k != "pagina" and v]
    base = urlencode(pares)
    return pagina, f"{base}&" if base else ""


def _conteudo(obj):
    """O conteúdo com retenção (pode já ter sido apagado)."""
    try:
        return obj.conteudo
    except (AttributeError, ObjectDoesNotExist):
        return None


def _rotulo_tipo(chave: str) -> str:
    t = ganchos.tipo(chave)
    return t.rotulo if t else chave


# ------------------------------------------------------------------ painel
@require_GET
def painel(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_ver(request.user))
    u = request.user
    hoje = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    com = policies.filtrar_por_unidade(u, Comunicacao.objects.all())
    numeros = com.aggregate(
        pendentes=Count("pk", filter=Q(situacao__in=Comunicacao.PENDENTES)),
        aguardando=Count("pk", filter=Q(situacao=S.AGUARDANDO_APROVACAO)),
        enviadas_hoje=Count("pk", filter=Q(enviada_em__gte=hoje)),
        lidas_hoje=Count("pk", filter=Q(enviada_em__gte=hoje, entrega="lida")),
        problemas=Count("pk", filter=Q(situacao__in=Comunicacao.PROBLEMAS)))
    abertas = policies.filtrar_por_unidade(u, ExcecaoAutomacao.objects.filter(
        situacao=ExcecaoAutomacao.Situacao.ABERTA))
    recebidos_hoje = policies.filtrar_por_unidade(u, Recebimento.objects.filter(
        registrado_em__gte=hoje)).count()
    c = whatsapp_config.carregar()
    motivo_geral, desligados = chaves.bloqueios("whatsapp", ROTULOS_FLUXOS)
    return render(request, "automacao/painel.html", {
        "numeros": numeros, "excecoes_abertas": abertas.count(),
        "recebidos_hoje": recebidos_hoje, "canal": c, "geral": _chave(chaves.GERAL),
        "chave_canal": _chave(chaves.nome_canal("whatsapp")), "motivo_geral": motivo_geral,
        "fluxos_desligados": [ROTULOS_FLUXOS[f] for f in desligados],
        "recentes": [_linha(x) for x in com.select_related("servidor")[:6]],
        "excecoes": list(abertas.select_related("responsavel")[:5]),
        "simulador": simulador.disponivel() and policies.pode_operar(u),
        "pode_administrar": policies.pode_administrar(u),
        "migalhas": [("Início", reverse("painel:inicio")), ("Automação", "")],
    })


ROTULOS_FLUXOS = {
    "diarias_liberadas": "Aviso de diárias liberadas",
    "lembretes_comprovante": "Lembretes de comprovante",
    "respostas_automaticas": "Respostas automáticas (confirmação, ajuda, descadastro)",
    "atendimento": "Respostas escritas pela equipe",
    "assistente_whatsapp": "Assistente no WhatsApp (sem IA)",
    "recebimento_automatico": "Associar arquivos recebidos automaticamente",
    "km_vespera": "Link de km na véspera",
    "km_lembretes": "Lembretes de km",
    "avisos_viagem": "Avisos de cancelamento, remarcação e substituição",
    "ferramentas": "Ferramentas da automação (preparação e ações)",
}


def _chave(nome: str) -> ChaveAutomacao:
    return ChaveAutomacao.objects.filter(nome=nome).first() or ChaveAutomacao(nome=nome)


# ------------------------------------------------------------------ canal e chaves
@require_GET
def canal(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_administrar(request.user))
    existentes = {c.nome: c for c in ChaveAutomacao.objects.select_related("alterada_por")}
    linhas = [("Chave geral", "Desliga todos os efeitos novos de uma vez.", chaves.GERAL),
              ("Canal WhatsApp", "Envio e associação automática pelo WhatsApp.",
               chaves.nome_canal("whatsapp"))]
    conhecidos = dict(ROTULOS_FLUXOS)
    for chave, rotulo in ganchos.fluxos():
        conhecidos.setdefault(chave, rotulo)
    for fluxo, rotulo in sorted(conhecidos.items(), key=lambda par: par[1]):
        linhas.append((f"Fluxo: {rotulo}", "", chaves.nome_fluxo(fluxo)))
    return render(request, "automacao/canal.html", {
        "diagnostico": whatsapp.diagnostico(),
        "chaves": [(rotulo, ajuda, nome, existentes.get(nome) or ChaveAutomacao(nome=nome))
                   for rotulo, ajuda, nome in linhas],
        "url_webhook": request.build_absolute_uri(reverse("integracoes_whatsapp:webhook")),
        "estados": [(ChaveAutomacao.Estado.DESLIGADA, "Desligada"),
                    (ChaveAutomacao.Estado.LIGADA, "Ligada")],
        "modos": ChaveAutomacao.Modo.choices,
        "migalhas": _migalhas(("Canal e chaves", "")),
    })


@require_POST
def alterar_chave(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_administrar(request.user))
    form = forms.FormularioChave(request.POST)
    if not form.is_valid():
        messages.error(request, "Escolha um estado válido para a chave.")
        return redirect("automacao:canal")
    d = form.cleaned_data
    try:
        chave = chaves.alterar(request.user, d["nome"], estado=d["estado"],
                               modo=d["modo"] or None, motivo=d["motivo"])
    except ValueError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"{chave.nome}: {chave.get_estado_display().lower()}"
                         + (f", {chave.get_modo_display().lower()}"
                            if chave.nome.startswith("fluxo:") else "") + ".")
    return redirect(reverse("automacao:canal") + "#chaves")


@require_POST
def desligar_tudo(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_administrar(request.user))
    chaves.desligar_tudo(request.user, (request.POST.get("motivo") or "").strip())
    messages.success(request, "Automação desligada: nenhum envio novo sai até alguém religar. "
                              "Os resultados que chegarem continuam sendo registrados.")
    return _voltar(request, reverse("automacao:painel"))


# ------------------------------------------------------------------ simulador
@require_POST
def processar_agora(request: HttpRequest) -> HttpResponse:
    try:
        total = simulador.processar_agora(request.user)
    except simulador.SimuladorIndisponivel as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"Fila processada: {total} item(ns) tratado(s)."
                         if total else "A fila estava vazia (ou as chaves estão desligadas).")
    return _voltar(request, reverse("automacao:painel"))


@require_POST
def simular_mensagem(request: HttpRequest) -> HttpResponse:
    try:
        simulador.simular_mensagem(request.user, request.POST.get("telefone", ""),
                                   request.POST.get("texto", "") or "Olá")
    except simulador.SimuladorIndisponivel as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, "Mensagem simulada recebida. Processe a fila para ver o que "
                                  "a automação faz com ela.")
    return _voltar(request, reverse("automacao:painel"))


# ------------------------------------------------------------------ comunicações
ABAS_COMUNICACAO = (
    ("", "Todas", Q()),
    ("aprovar", "Aguardando aprovação", Q(situacao=S.AGUARDANDO_APROVACAO)),
    ("pendentes", "A sair", Q(situacao__in=Comunicacao.PENDENTES)),
    ("problemas", "Com problema", Q(situacao__in=Comunicacao.PROBLEMAS)),
    ("enviadas", "Enviadas", Q(situacao__in=(S.ENVIADA, S.MANUAL))),
    ("outras", "Não saíram", Q(situacao__in=(S.OBSOLETA, S.EXPIRADA, S.CANCELADA, S.SOMBRA))),
)


def _linha(c: Comunicacao) -> dict:
    return {"c": c, "rotulo": _rotulo_tipo(c.tipo),
            "quem": str(c.servidor) if c.servidor_id else "Sem destinatário"}


@require_GET
def comunicacoes_lista(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_ver(request.user))
    base = policies.filtrar_por_unidade(request.user, Comunicacao.objects.all())
    q = (request.GET.get("q") or "").strip()[:80]
    if q:
        filtro = Q(servidor__nome__icontains=q)
        if q.isdigit():
            filtro |= Q(pk=int(q))
        base = base.filter(filtro)
    aba = request.GET.get("aba") or ""
    filtros = {chave: filtro for chave, _, filtro in ABAS_COMUNICACAO}
    if aba not in filtros:
        aba = ""
    contagens = base.aggregate(**{f"n_{chave or 'todas'}": Count("pk", filter=filtro)
                                  for chave, _, filtro in ABAS_COMUNICACAO})
    qs = base.filter(filtros[aba]).select_related("servidor")
    pagina, querystring = _paginar(request, qs)
    sem_aba = urlencode([(k, v) for k, v in request.GET.items() if k not in ("aba", "pagina")
                         and v])
    pode_operar = policies.pode_operar(request.user)
    return render(request, "automacao/comunicacoes.html", {
        "linhas": [_linha(c) for c in pagina], "page_obj": pagina,
        "ids_aprovar": [c.pk for c in pagina if c.situacao == S.AGUARDANDO_APROVACAO]
        if aba == "aprovar" and pode_operar else [],
        "querystring_base": querystring, "q": q, "aba": aba, "qs_sem_aba": sem_aba,
        "abas": [(chave, rotulo, contagens[f"n_{chave or 'todas'}"])
                 for chave, rotulo, _ in ABAS_COMUNICACAO],
        "migalhas": _migalhas(("Comunicações", "")),
    })


@require_POST
def aprovar_comunicacoes(request: HttpRequest) -> HttpResponse:
    """Aprovação em lote (modo assistido): os envios listados na página; cada um passa pela
    mesma regra da aprovação individual e é conferido de novo na hora de sair."""
    _exigir(policies.pode_operar(request.user))
    ids = [int(x) for x in request.POST.getlist("ids") if x.isdigit()][:POR_PAGINA]
    aprovadas = 0
    for pk in ids:
        try:
            comunicacoes.aprovar(request.user, pk)
            aprovadas += 1
        except (comunicacoes.ComunicacaoInvalida, PermissionDenied, Comunicacao.DoesNotExist):
            continue
    if aprovadas:
        messages.success(request, f"{aprovadas} envio{'s' if aprovadas > 1 else ''} "
                                  f"aprovado{'s' if aprovadas > 1 else ''}: saem na próxima "
                                  "passada do worker.")
    if aprovadas < len(ids):
        messages.warning(request, f"{len(ids) - aprovadas} não estava(m) mais aguardando "
                                  "aprovação ou não é(são) da sua unidade.")
    return redirect(reverse("automacao:comunicacoes") + "?aba=aprovar")


def _comunicacao_visivel(request: HttpRequest, pk: int) -> Comunicacao:
    c = get_object_or_404(Comunicacao.objects.select_related(
        "servidor", "contato", "criada_por", "aprovada_por", "em_resposta_a"), pk=pk)
    if not policies.pode_ver_objeto(request.user, c):
        raise Http404
    return c


@require_GET
def comunicacao(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(policies.pode_ver(request.user))
    c = _comunicacao_visivel(request, pk)
    conteudo = _conteudo(c)
    pode_operar = policies.pode_operar_objeto(request.user, c)
    return render(request, "automacao/comunicacao.html", {
        "c": c, "rotulo_tipo": _rotulo_tipo(c.tipo), "conteudo": conteudo,
        "contexto_hero": f"Comunicação #{c.pk}",
        "assunto": ganchos.assunto(c.recurso, c.tipo),
        "tentativas": list(c.tentativas_entrega.all()),
        "status": list(c.status_entrega.all()),
        "recebimentos": list(c.recebimentos.select_related("servidor")[:10]),
        "excecoes": list(c.excecoes.select_related("responsavel")[:5]),
        "pode_operar": pode_operar,
        "simulador": pode_operar and simulador.disponivel(),
        "form_resposta": forms.FormularioSimularResposta(),
        "migalhas": _migalhas(("Comunicações", reverse("automacao:comunicacoes")),
                              (f"#{c.pk}", "")),
    })


ACOES_COMUNICACAO = {
    "aprovar": (comunicacoes.aprovar, "Envio aprovado: sai na próxima passada do worker."),
    "cancelar": (comunicacoes.cancelar, "Comunicação cancelada."),
    "chegou": (comunicacoes.confirmar_chegada, "Registrado: a mensagem chegou."),
    "manual": (comunicacoes.registrar_envio_manual, "Registrado como enviado à mão."),
}


@require_POST
def acao_comunicacao(request: HttpRequest, pk: int, acao: str) -> HttpResponse:
    c = _comunicacao_visivel(request, pk)
    _exigir(policies.pode_operar_objeto(request.user, c))
    destino = reverse("automacao:comunicacao", args=[c.pk])
    try:
        if acao == "tentar":
            comunicacoes.tentar_de_novo(
                request.user, c.pk,
                confirmou_que_nao_chegou=request.POST.get("nao_chegou") == "sim")
            messages.success(request, "Nova tentativa agendada.")
        elif acao in ACOES_COMUNICACAO:
            funcao, texto = ACOES_COMUNICACAO[acao]
            funcao(request.user, c.pk)
            messages.success(request, texto)
        elif acao == "simular_falha":
            comunicacoes.simular_proxima(request.user, c.pk, request.POST.get("resultado", ""))
            messages.success(request, "A próxima ida ao canal simulado vai falhar desse jeito.")
        elif acao == "simular_status":
            simulador.simular_status(request.user, c.pk, request.POST.get("status", ""))
            messages.success(request, "Status simulado recebido pelo webhook.")
        elif acao == "simular_resposta":
            form = forms.FormularioSimularResposta(request.POST, request.FILES)
            if not form.is_valid():
                messages.error(request, " ".join(map(str, form.non_field_errors())) or
                               "Confira o texto e o arquivo.")
                return redirect(destino)
            arquivo = form.cleaned_data.get("arquivo")
            simulador.simular_resposta(
                request.user, c.pk, texto=form.cleaned_data.get("texto") or "",
                conteudo=arquivo.read(simulador.LIMITE + 1) if arquivo else None,
                nome=getattr(arquivo, "name", ""))
            messages.success(request, "Resposta simulada recebida. Processe a fila para ver o "
                                      "arquivo entrar na prestação.")
        else:
            raise Http404
    except (comunicacoes.ComunicacaoInvalida, simulador.SimuladorIndisponivel) as erro:
        messages.error(request, str(erro))
    return _voltar(request, destino)


# ------------------------------------------------------------------ recebidos
ABAS_RECEBIMENTO = (
    ("", "Todos", Q()),
    ("pendentes", "Pedem uma pessoa", Q(situacao__in=(
        Recebimento.Situacao.IDENTIFICADO, Recebimento.Situacao.ENCAMINHADO,
        Recebimento.Situacao.QUARENTENA))),
    ("associados", "Associados", Q(situacao__in=(Recebimento.Situacao.ASSOCIADO,
                                                 Recebimento.Situacao.CONFERIDO))),
    ("recusados", "Recusados ou descartados", Q(situacao__in=(
        Recebimento.Situacao.RECUSADO, Recebimento.Situacao.DESCARTADO))),
)


@require_GET
def recebimentos_lista(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_ver(request.user))
    base = policies.filtrar_por_unidade(request.user, Recebimento.objects.all())
    aba = request.GET.get("aba") or ""
    filtros = {chave: filtro for chave, _, filtro in ABAS_RECEBIMENTO}
    if aba not in filtros:
        aba = ""
    contagens = base.aggregate(**{f"n_{chave or 'todos'}": Count("pk", filter=filtro)
                                  for chave, _, filtro in ABAS_RECEBIMENTO})
    pagina, querystring = _paginar(request, base.filter(filtros[aba]).select_related("servidor"))
    return render(request, "automacao/recebimentos.html", {
        "linhas": list(pagina), "page_obj": pagina, "querystring_base": querystring,
        "aba": aba, "abas": [(chave, rotulo, contagens[f"n_{chave or 'todos'}"])
                             for chave, rotulo, _ in ABAS_RECEBIMENTO],
        "migalhas": _migalhas(("Recebidos", "")),
    })


def _recebimento_visivel(request: HttpRequest, pk: int) -> Recebimento:
    r = get_object_or_404(Recebimento.objects.select_related(
        "servidor", "contato", "comunicacao", "associado_por", "conferido_por"), pk=pk)
    if not policies.pode_ver_objeto(request.user, r):
        raise Http404
    return r


@require_GET
def recebimento(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(policies.pode_ver(request.user))
    r = _recebimento_visivel(request, pk)
    destino = ganchos.destino(r.destino) if r.destino else None
    pode_operar = policies.pode_operar_objeto(request.user, r)
    return render(request, "automacao/recebimento.html", {
        "r": r, "conteudo": _conteudo(r), "contexto_hero": f"Recebimento #{r.pk}",
        "quem": str(r.servidor) if r.servidor_id else
        f"Número desconhecido (final {r.remetente_final or '?'})",
        "referencia": destino.descrever(r.referencia) if destino and r.referencia else None,
        "candidatos": recebimentos.candidatos(r) if pode_operar and r.arquivo
        and r.situacao == Recebimento.Situacao.IDENTIFICADO else [],
        "respostas": list(r.respostas.all()[:5]),
        "excecoes": list(r.excecoes.all()[:5]),
        "pode_operar": pode_operar, "form_resposta": forms.FormularioResposta(),
        "migalhas": _migalhas(("Recebidos", reverse("automacao:recebimentos")),
                              (f"#{r.pk}", "")),
    })


@require_GET
def arquivo_recebido(request: HttpRequest, pk: int) -> FileResponse:
    _exigir(policies.pode_operar(request.user))
    r = _recebimento_visivel(request, pk)
    if not r.arquivo:
        raise Http404
    resposta = FileResponse(r.arquivo.open("rb"), as_attachment=True,
                            filename=r.nome_arquivo or f"recebido-{r.pk}")
    resposta["Content-Type"] = r.mime or "application/octet-stream"
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Cache-Control"] = "no-store"
    return resposta


@require_POST
def acao_recebimento(request: HttpRequest, pk: int, acao: str) -> HttpResponse:
    r = _recebimento_visivel(request, pk)
    _exigir(policies.pode_operar_objeto(request.user, r))
    destino = reverse("automacao:recebimento", args=[r.pk])
    try:
        if acao == "associar":
            escolha = request.POST.get("candidato", "")
            chave, _, recurso = escolha.partition("|")
            recebimentos.associar_manual(request.user, r.pk, chave, recurso)
            messages.success(request, "Arquivo associado. A pessoa recebe a confirmação.")
        elif acao == "conferir":
            recebimentos.conferir(request.user, r.pk)
            messages.success(request, "Conferido.")
        elif acao == "descartar":
            recebimentos.descartar(request.user, r.pk, request.POST.get("motivo", ""))
            messages.success(request, "Descartado.")
        elif acao == "responder":
            form = forms.FormularioResposta(request.POST)
            if not form.is_valid():
                messages.error(request, "Escreva a resposta (até 1000 caracteres).")
                return redirect(destino)
            responder(request.user, r, form.cleaned_data["texto"])
            messages.success(request, "Resposta agendada: sai na próxima passada do worker.")
        else:
            raise Http404
    except recebimentos.RecebimentoInvalido as erro:
        messages.error(request, str(erro))
    return _voltar(request, destino)


def responder(usuario, r: Recebimento, texto: str) -> Comunicacao:
    """A equipe responde pelo WhatsApp (o texto vai para o conteúdo com retenção)."""
    from django.db import transaction

    from .entrega import retencao
    from .models import ConteudoComunicacao

    policies.exigir(policies.pode_operar_objeto(usuario, r))
    if not r.contato_id:
        raise recebimentos.RecebimentoInvalido("Número desconhecido: não respondemos a quem "
                                               "não tem contato verificado.")
    with transaction.atomic():
        c = comunicacoes.agendar(
            tipo="automacao.resposta", servidor_id=r.servidor_id,
            recurso=f"automacao.recebimento:{r.pk}",
            chave=f"resposta:{r.pk}:{timezone.now():%Y%m%d%H%M%S%f}", unidade_id=r.unidade_id,
            criada_por=usuario, contexto={"recebimento": r.pk}, em_resposta_a=r)
        ConteudoComunicacao.objects.update_or_create(comunicacao=c, defaults={
            "texto": texto.strip()[:1000], "expira_em": timezone.now() + retencao()})
        excecoes.encerrar_do_assunto(recebimento=r, usuario=usuario,
                                     resolucao="Respondida pela equipe.")
        if r.situacao == Recebimento.Situacao.ENCAMINHADO:
            r.situacao = Recebimento.Situacao.RESPONDIDO
            r.save(update_fields=["situacao"])
    return c


# ------------------------------------------------------------------ exceções
ABAS_EXCECAO = (
    ("", "Abertas", Q(situacao=ExcecaoAutomacao.Situacao.ABERTA)),
    ("minhas", "Comigo", Q(situacao=ExcecaoAutomacao.Situacao.ABERTA)),
    ("tratadas", "Tratadas", ~Q(situacao=ExcecaoAutomacao.Situacao.ABERTA)),
)


@require_GET
def excecoes_lista(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_ver(request.user))
    base = policies.filtrar_por_unidade(request.user, ExcecaoAutomacao.objects.all())
    aba = request.GET.get("aba") or ""
    filtros = {chave: filtro for chave, _, filtro in ABAS_EXCECAO}
    if aba not in filtros:
        aba = ""
    minhas = Q(responsavel=request.user)
    contagens = base.aggregate(
        n_=Count("pk", filter=filtros[""]), n_minhas=Count("pk", filter=filtros["minhas"] & minhas),
        n_tratadas=Count("pk", filter=filtros["tratadas"]))
    qs = base.filter(filtros[aba])
    if aba == "minhas":
        qs = qs.filter(minhas)
    pagina, querystring = _paginar(request, qs.select_related("responsavel"))
    return render(request, "automacao/excecoes.html", {
        "linhas": list(pagina), "page_obj": pagina, "querystring_base": querystring, "aba": aba,
        "abas": [(chave, rotulo, contagens[f"n_{chave}"]) for chave, rotulo, _ in ABAS_EXCECAO],
        "migalhas": _migalhas(("Exceções", "")),
    })


@require_GET
def excecao(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(policies.pode_ver(request.user))
    e = get_object_or_404(ExcecaoAutomacao.objects.select_related(
        "comunicacao__servidor", "recebimento__servidor", "responsavel", "resolvida_por"), pk=pk)
    if not policies.pode_ver_objeto(request.user, e):
        raise Http404
    return render(request, "automacao/excecao.html", {
        "e": e, "pode_operar": policies.pode_operar_objeto(request.user, e),
        "aberta": e.situacao == ExcecaoAutomacao.Situacao.ABERTA,
        "migalhas": _migalhas(("Exceções", reverse("automacao:excecoes")), (f"#{e.pk}", "")),
    })


@require_POST
def acao_excecao(request: HttpRequest, pk: int, acao: str) -> HttpResponse:
    from django.db import transaction

    e = get_object_or_404(ExcecaoAutomacao, pk=pk)
    if not policies.pode_ver_objeto(request.user, e):
        raise Http404
    _exigir(policies.pode_operar_objeto(request.user, e))
    try:
        if acao == "assumir":
            excecoes.assumir(request.user, e.pk)
            messages.success(request, "A exceção está com você.")
        elif acao in ("resolver", "descartar"):
            texto = (request.POST.get("resolucao") or "").strip()
            if not texto:
                messages.error(request, "Diga o que foi feito.")
                return redirect("automacao:excecao", pk=e.pk)
            with transaction.atomic():
                travada = ExcecaoAutomacao.objects.select_for_update().get(pk=e.pk)
                excecoes.encerrar(travada, request.user, texto, descartar=acao == "descartar")
            messages.success(request, "Exceção encerrada.")
        else:
            raise Http404
    except ValueError as erro:
        messages.error(request, str(erro))
    return redirect("automacao:excecao", pk=e.pk)


# ------------------------------------------------------------------ contatos
@require_GET
def contatos_lista(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_operar(request.user))
    qs = ContatoVerificado.objects.select_related("servidor").order_by(
        "revogado_em", "servidor__nome")
    if not (policies.ve_todas_unidades(request.user) or policies.pode_administrar(request.user)):
        unidade = policies.unidade_do_usuario(request.user)
        qs = qs.filter(Q(servidor__unidade_id=unidade) | Q(servidor__unidade__isnull=True))
    if request.GET.get("revogados") != "1":
        qs = qs.filter(revogado_em__isnull=True)
    pagina, querystring = _paginar(request, qs)
    return render(request, "automacao/contatos.html", {
        "linhas": list(pagina), "page_obj": pagina, "querystring_base": querystring,
        "revogados": request.GET.get("revogados") == "1",
        "lista_fechada": whatsapp_config.carregar().lista_fechada,
        "na_lista": set(DestinatarioAutorizado.objects.filter(removido_em__isnull=True)
                        .values_list("endereco", flat=True)),
        "migalhas": _migalhas(("Contatos e opt-in", "")),
    })


@require_http_methods(["GET", "POST"])
def novo_contato(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_operar(request.user))
    servidores = contatos.servidores_sem_contato(request.user)
    form = forms.FormularioContato(request.POST or None, servidores=servidores)
    if request.method == "POST" and form.is_valid():
        try:
            contato = contatos.cadastrar(request.user, form.cleaned_data["servidor"].pk)
        except contatos.ContatoInvalido as erro:
            form.add_error("servidor", str(erro))
        else:
            messages.success(request, "Contato cadastrado. Falta verificar o número e registrar "
                                      "o opt-in.")
            return redirect("automacao:contato", pk=contato.pk)
    return render(request, "automacao/novo_contato.html", {
        "form": form, "migalhas": _migalhas(("Contatos e opt-in", reverse("automacao:contatos")),
                                            ("Novo contato", ""))})


def _contato_visivel(request: HttpRequest, pk: int) -> ContatoVerificado:
    contato = get_object_or_404(ContatoVerificado.objects.select_related(
        "servidor", "verificado_por", "optin_registrado_por"), pk=pk)
    if not policies.pode_cuidar_do_contato(request.user, contato):
        raise Http404
    return contato


@require_GET
def contato(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(policies.pode_operar(request.user))
    ct = _contato_visivel(request, pk)
    c = whatsapp_config.carregar()
    na_lista = DestinatarioAutorizado.objects.filter(
        endereco=ct.endereco, removido_em__isnull=True).exists()
    return render(request, "automacao/contato.html", {
        "ct": ct, "mascarado": whatsapp_config.mascarar_telefone(ct.endereco),
        "na_lista": na_lista, "lista_fechada": c.lista_fechada,
        "form_optin": forms.FormularioOptin(), "form_revogar": forms.FormularioRevogar(),
        "comunicacoes": [_linha(x) for x in ct.comunicacoes.select_related("servidor")[:8]],
        "migalhas": _migalhas(("Contatos e opt-in", reverse("automacao:contatos")),
                              (str(ct.servidor), "")),
    })


@require_POST
def acao_contato(request: HttpRequest, pk: int, acao: str) -> HttpResponse:
    ct = _contato_visivel(request, pk)
    try:
        if acao == "verificar":
            contatos.confirmar_numero(request.user, ct.pk)
            messages.success(request, "Número verificado.")
        elif acao == "optin":
            form = forms.FormularioOptin(request.POST)
            if not form.is_valid():
                messages.error(request, "Confirme como a pessoa concordou.")
                return redirect("automacao:contato", pk=ct.pk)
            contatos.registrar_optin(request.user, ct.pk, form.cleaned_data["origem"])
            messages.success(request, "Opt-in registrado.")
        elif acao == "revogar":
            form_revogar = forms.FormularioRevogar(request.POST)
            if not form_revogar.is_valid():
                messages.error(request, "Diga o motivo da revogação.")
                return redirect("automacao:contato", pk=ct.pk)
            contatos.revogar(request.user, ct.pk, form_revogar.cleaned_data["motivo"])
            messages.success(request, "Contato revogado: nada mais sai para este número.")
        else:
            raise Http404
    except contatos.ContatoInvalido as erro:
        messages.error(request, str(erro))
    return redirect("automacao:contato", pk=ct.pk)


# ------------------------------------------------------------------ testadores
@require_http_methods(["GET", "POST"])
def testadores(request: HttpRequest) -> HttpResponse:
    _exigir(policies.pode_administrar(request.user))
    form = forms.FormularioTestador(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            contatos.autorizar_testador(request.user, d["telefone"], d["descricao"],
                                        d.get("valido_ate"))
        except contatos.ContatoInvalido as erro:
            form.add_error("telefone", str(erro))
        else:
            messages.success(request, "Testador autorizado.")
            return redirect("automacao:testadores")
    hoje = timezone.localdate()
    lista = list(DestinatarioAutorizado.objects.filter(removido_em__isnull=True)
                 .select_related("adicionado_por"))
    return render(request, "automacao/testadores.html", {
        "form": form, "hoje": hoje, "vencendo": hoje + timedelta(days=7),
        "linhas": [(d, whatsapp_config.mascarar_telefone(d.endereco), d.vigente(hoje))
                   for d in lista],
        "lista_fechada": whatsapp_config.carregar().lista_fechada,
        "migalhas": _migalhas(("Testadores autorizados", "")),
    })


@require_POST
def remover_testador(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir(policies.pode_administrar(request.user))
    try:
        contatos.remover_testador(request.user, pk)
    except contatos.ContatoInvalido as erro:
        messages.error(request, str(erro))
    except DestinatarioAutorizado.DoesNotExist as erro:
        raise Http404 from erro
    else:
        messages.success(request, "Número removido da lista: não recebe mais nada.")
    return redirect("automacao:testadores")
