"""Telas do módulo Viagens (piloto: painel, lista, novo, edição, emissão, documentos).

A leitura de um ofício é a janela de resumo que a lista abre (views.resumo): não há
página separada só para ler — ela repetia a folha e dividia a atenção."""

from __future__ import annotations

from itertools import pairwise
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import F, Prefetch, Q, prefetch_related_objects
from django.db.models.expressions import OrderBy
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.csp import CSP
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csp import csp_override
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.vary import vary_on_headers

from gestao.cadastros.forms import FormularioServidor, FormularioViatura
from gestao.cadastros.models import Municipio, Servidor
from gestao.plataforma.templatetags.ui import formatar_moeda

from . import exportacao, itinerario, policies, queries, rotas, services
from .documentos.dados import dados_do_oficio
from .documentos.pdf import ASSETS, buscar_recurso, html_do_documento
from .dominio import busca as dominio_busca
from .dominio.diarias import Faixa
from .forms import (
    FORM_ID,
    FiltrosOficio,
    FormularioJustificativa,
    FormularioOficio,
    iniciais_de_trechos,
    resolver_municipio,
)
from .models import Documento, Oficio
from .queries import trechos_de, viajantes_de
from .templatetags.viagens import formatar_periodo

POR_PAGINA = 20


def _htmx(request: HttpRequest) -> bool:
    return bool(getattr(request, "htmx", False))


def _oficio_visivel(request: HttpRequest, pk: int) -> Oficio:
    oficio = get_object_or_404(
        Oficio.objects.select_related("unidade", "unidade__configuracao", "viatura",
                                      "viatura__combustivel", "sede", "transporte_combustivel"),
        pk=pk)
    if not policies.pode_ver(request.user, oficio):
        raise Http404  # não revela a existência de ofícios de outras unidades
    return oficio


def _resumo_pedido(request: HttpRequest) -> dict:
    """Contexto da janela de resumo quando a lista é aberta com "?resumo=<pk>"."""
    pk = (request.GET.get("resumo") or "").strip()
    if not pk.isdigit():
        return {}
    try:
        oficio = _oficio_visivel(request, int(pk))
    except Http404:
        return {}
    return {"abrir_resumo": oficio.pk, "resumo": _contexto_resumo(request, oficio)}


def _voltar(request: HttpRequest, oficio) -> str:
    """Depois de uma ação do ciclo de vida, a lista como estava (aba, filtros, página) —
    o formulário manda o endereço em `voltar`; sem ele (ou fora da lista), a lista do ofício."""
    voltar = request.POST.get("voltar") or ""
    if (urlsplit(voltar).path == reverse("viagens:oficios")
            and url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()})):
        return voltar
    return _na_lista(oficio)


def _na_lista(oficio) -> str:
    """A lista filtrada neste ofício. É o destino de quem termina uma ação (emitir,
    cancelar) e de quem não pode editar: a leitura completa é a janela de resumo, que
    abre na própria lista. Arquivado só aparece na aba Arquivados."""
    aba = "situacao=arquivado&" if oficio.arquivado_em else ""
    return f"{reverse('viagens:oficios')}?{aba}q={oficio.numero_formatado}"


def _migalhas(*itens: tuple[str, str]) -> list[tuple[str, str]]:
    return [("Início", reverse("painel:inicio")), ("Viagens", reverse("viagens:painel")),
            *itens]


# ------------------------------------------------------------------ painel
@require_GET
def painel(request: HttpRequest) -> HttpResponse:
    qs = policies.oficios_visiveis(request.user)
    pendentes = list(queries.com_dados_de_lista(
        qs.filter(situacao=Oficio.Situacao.RASCUNHO)).order_by("-atualizado_em")[:5])
    proximos = list(queries.com_dados_de_lista(
        qs.exclude(situacao=Oficio.Situacao.CANCELADO).filter(
            trechos__ordem=1, trechos__saida_em__gte=timezone.now())
    ).order_by("primeira_saida")[:5])  # type: ignore[misc]  # anotado em com_dados_de_lista
    return render(request, "viagens/painel.html", {
        "indicadores": queries.indicadores_do_painel(qs),
        "pendentes": pendentes, "proximos": proximos,
        "pode_editar_oficios": policies.edita_oficios(request.user),
        "pode_criar": policies.pode_criar(request.user),
        "migalhas": [("Início", reverse("painel:inicio")), ("Viagens", "")],
    })


# ------------------------------------------------------------------ lista
ORDENS_DA_LISTA: dict[str, tuple[str | OrderBy, ...]] = {
    "-numero": ("-ano", "-numero"), "numero": ("ano", "numero"),
    "saida": (F("primeira_saida").asc(nulls_last=True),),
    "-saida": (F("primeira_saida").desc(nulls_last=True),),  # sem roteiro vão ao fim
    # "Criação" da referência = data do ofício; empate pela gravação (como lá).
    "-criacao": ("-data_oficio", "-criado_em"), "criacao": ("data_oficio", "criado_em"),
}


def _recorte_da_lista(request: HttpRequest, base):
    """O que a lista mostra (busca, situação, filtros avançados e ordem) — a mesma conta
    serve à tela e à planilha, para quem exporta levar exatamente o que estava vendo."""
    situacao = request.GET.get("situacao") or ""
    termo = (request.GET.get("q") or "").strip()
    escopo = request.GET.get("escopo") or ""
    qs = queries.aplicar_filtro_situacao(base, situacao)
    qs = services.buscar_por_texto(qs, termo, escopo)
    avancados = FiltrosOficio(request.GET)
    qs = queries.aplicar_filtros_avancados(
        qs, avancados.cleaned_data if avancados.is_valid() else {})
    ordem = request.GET.get("ordem") or "-numero"
    qs = queries.com_dados_de_lista(qs).order_by(
        *ORDENS_DA_LISTA.get(ordem, ORDENS_DA_LISTA["-numero"]))
    return qs, situacao, termo, escopo, avancados, ordem


@require_GET
def exportar(request: HttpRequest) -> HttpResponse:
    """A lista de agora (com os mesmos filtros) numa planilha Excel."""
    if not policies.pode_listar(request.user):
        raise PermissionDenied
    qs = _recorte_da_lista(request, policies.oficios_visiveis(request.user))[0]
    nome = f"oficios-{timezone.localdate():%Y-%m-%d}.xlsx"
    resposta = HttpResponse(
        exportacao.planilha_de_oficios(qs.iterator(chunk_size=200)),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resposta


@require_GET
@vary_on_headers("HX-Request", "HX-Target")  # senão o "Voltar" do navegador reusa o fragmento
def lista(request: HttpRequest) -> HttpResponse:
    if not policies.pode_listar(request.user):
        raise PermissionDenied
    base = policies.oficios_visiveis(request.user)
    qs, situacao, termo, escopo, avancados, ordem = _recorte_da_lista(request, base)
    # Leituras do termo ("26" é número de ofício? protocolo?) com quantos ofícios cada uma
    # traria: a tela oferece o refino em vez de despejar tudo o que casou por acaso.
    leituras = dominio_busca.ler(termo, timezone.localdate().year)
    contagem_leituras = queries.contar_leituras(
        queries.aplicar_filtro_situacao(base, situacao), leituras) if leituras else {}
    refinos = [
        {"escopo": leitura.escopo, "rotulo": leitura.rotulo,
         "quantidade": contagem_leituras.get(leitura.escopo, 0)}
        for leitura in leituras if contagem_leituras.get(leitura.escopo, 0)
    ]
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    pagina.object_list = list(pagina.object_list)  # avaliada uma vez: view e template
    for o in pagina.object_list:  # o menu de cada linha vem da política, por objeto
        o.acoes = policies.acoes_do_oficio(  # type: ignore[attr-defined]
            request.user, o, com_exclusao=True)
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    # As abas trocam só a situação: tudo o mais que a pessoa filtrou continua valendo.
    das_abas = filtros.copy()
    das_abas.pop("situacao", None)
    # As fichas de refino trocam só o escopo da busca.
    do_refino = filtros.copy()
    do_refino.pop("escopo", None)
    contexto = {
        "page_obj": pagina,
        "oficios": pagina.object_list,
        "contagens": queries.contagens(base),
        "situacao": situacao,
        "termo": termo,
        "ordem": ordem,
        "escopo": escopo,
        # Outra tela mandou abrir a janela de um ofício (roteiros → "usado em…"): ela já
        # vai desenhada no HTML, para abrir pronta em vez de piscar o esqueleto.
        **_resumo_pedido(request),
        "refinos": refinos,
        "refino_atual": next((r for r in refinos if r["escopo"] == escopo), None),
        "querystring_base": (filtros.urlencode() + "&") if filtros else "",
        "querystring_abas": das_abas.urlencode(),
        "querystring_refino": (do_refino.urlencode() + "&") if do_refino else "",
        "avancados": avancados,
        "abas": [("", "Todos", "todos")] + [
            (chave, rotulo, chave) for chave, (rotulo, _) in queries.FILTROS_SITUACAO.items()],
        "pode_criar": policies.pode_criar(request.user),
        "pode_editar_oficios": policies.edita_oficios(request.user),
        "agora": timezone.now(),
        "migalhas": _migalhas(("Ofícios", "")),
    }
    if _htmx(request) and request.htmx.target == "resultados":  # type: ignore[attr-defined]
        return render(request, "viagens/oficios/lista.html#resultados", contexto)
    return render(request, "viagens/oficios/lista.html", contexto)


def novo(request: HttpRequest) -> HttpResponse:
    """"Novo ofício" já cria o ofício, como no sistema de referência: reserva o número e abre
    a folha de edição. Não existe página intermediária (GET volta para a lista)."""
    policies.exigir(policies.pode_criar(request.user),
                    "Seu usuário precisa estar lotado em uma unidade para criar ofícios.")
    if request.method != "POST":  # link antigo/favorito: nada é criado por GET
        return redirect("viagens:oficios")
    try:
        oficio = services.criar_rascunho(request.user)
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
        return redirect("viagens:oficios")
    messages.success(request, f"Ofício {oficio.numero_formatado} criado. Preencha e salve.")
    return redirect("viagens:editar", oficio.pk)


# ------------------------------------------------------------------ edição
# A folha é lida em quatro cartões (decisão do dono): Identificação reúne os dados
# administrativos, a equipe e o transporte; Roteiro fica com sede, destinos, trechos e as
# diárias, que nascem do próprio roteiro; Justificativa só existe quando o prazo a exige;
# Documentos conclui (conferência, minuta e emissão) e não tem pendência própria — vale a
# prontidão inteira.
# As pendências continuam nascendo com a chave fina ("dados", "equipe", …): é o que leva o
# link da conferência ao bloco certo dentro do cartão.
SECOES_DO_OFICIO = [
    ("identificacao", "Identificação", ("dados", "equipe", "transporte")),
    ("roteiro", "Roteiro", ("roteiro", "diarias")),
    ("justificativa", "Justificativa", ("justificativa",)),
]


def _mostrar_justificativa(oficio, prazo, form) -> bool:
    """O cartão da justificativa só aparece quando o prazo a torna obrigatória.

    Exceção: texto já escrito (ou erro no campo) mantém o cartão à vista. A justificativa
    vai para o documento mesmo quando dispensada (`documentos/dados.py`), então esconder o
    cartão deixaria no ofício um texto que ninguém mais consegue ler, corrigir ou apagar.
    """
    if prazo.justificativa_obrigatoria:
        return True
    if oficio.justificativa.strip() or oficio.justificativa_modelo_id:
        return True
    return bool(form is not None
                and (form.errors.get("justificativa") or form.errors.get("justificativa_modelo")))


def _contexto_edicao(request, oficio, form=None, itin=None, erro_roteiro="", calculo=None):
    if itin is None:
        itin = itinerario.montar(FORM_ID, sede=oficio.sede, trechos=trechos_de(oficio))
    # Documentos numa consulta só: o cartão Documentos lista; `policies.pode_excluir`
    # pergunta se existe algum. Com o prefetch os dois leem do cache do ofício.
    prefetch_related_objects([oficio], "documentos")
    prontidao = services.verificar_prontidao(oficio)
    prazo = services.avaliar_prazo_do_oficio(oficio)
    mostrar_justificativa = _mostrar_justificativa(oficio, prazo, form)
    secoes = []
    for chave, rotulo, origens in SECOES_DO_OFICIO:
        if chave == "justificativa" and not mostrar_justificativa:
            continue
        pendencias = [p for origem in origens for p in prontidao.da_secao(origem)]
        bloqueia = any(p.bloqueia for p in pendencias)
        # Aviso (ex.: servidor em outro ofício no mesmo período) não deixa a seção pendente:
        # a conferência diria "tudo pronto" enquanto a faixa marca a seção em aberto.
        ok = not bloqueia and ("diarias" not in origens or bool(oficio.diarias_resumo))
        secoes.append({"chave": chave, "rotulo": rotulo, "ok": ok, "bloqueia": bloqueia})
    return {
        # Nome desta folha para quem sair dela e precisar voltar (botão do rodapé).
        "rotulo_de_volta": f"o ofício {oficio.numero_formatado}",
        # Cadastrar sem sair da folha: são os mesmos diálogos das telas de Cadastros, e
        # por isso levam os mesmos formulários (ver componentes/dialogo_*.html).
        "form_servidor": FormularioServidor(),
        # Para onde o servidor recém-cadastrado vai: direto para a equipe deste ofício.
        "url_adicionar_viajante": reverse("viagens:adicionar_viajante", args=[oficio.pk]),
        "form_viatura": FormularioViatura(
            fonte_motoristas=reverse("cadastros:buscar_servidores")),
        # Pendências em vermelho só depois de salvar ou de pedir para emitir: abrir um
        # rascunho novo não é erro de ninguém.
        "mostrar_pendencias": bool(form is not None
                                   or request.GET.get("salvo") == "1"
                                   or request.GET.get("revisar")),
        "oficio": oficio,
        "form": form or FormularioOficio(instance=oficio),
        "secoes": secoes,
        **itin.contexto(),
        "trechos": trechos_de(oficio),
        "secoes_ok": sum(1 for sec in secoes if sec["ok"]),
        "recem_salvo": request.GET.get("salvo") == "1",
        "erro_roteiro": erro_roteiro,
        "viajantes": viajantes_de(oficio),
        "prontidao": prontidao,
        "prazo": prazo,
        "mostrar_justificativa": mostrar_justificativa,
        "assunto": services.assunto_do_oficio(oficio),
        # `calculo` pode vir de fora como prévia (ex.: acabou de aplicar um roteiro e nada
        # foi gravado ainda); senão, é o que está no ofício.
        "calculo": oficio.diarias_calculo if calculo is None else calculo,
        "previa_diarias": calculo is not None,
        "faixas": {f.value: f.rotulo for f in Faixa},
        "pode_emitir": policies.pode_emitir(request.user, oficio),
        "pode_excluir": policies.pode_excluir(request.user, oficio),
        "pode_editar_texto": policies.pode_editar_texto(request.user, oficio),
        "pode_gerir_textos": policies.pode_gerir_textos_prontos(request.user),
        # None = o perfil não vê roteiros (a escolha nem aparece).
        "roteiros_disponiveis": (
            _opcoes_de_roteiro(queries.roteiros_para_oficio(
                policies.roteiros_visiveis(request.user), oficio))
            if request.user.has_perm("viagens.view_roteiro") else None),
        "pode_criar_roteiro": policies.pode_criar_roteiro(request.user),
        "historico": list(oficio.historico.select_related("usuario")[:30]),
        # O cartão Documentos lista o que já saiu em papel (do cache do prefetch acima).
        "documentos": list(oficio.documentos.all()),
        "migalhas": _migalhas(("Ofícios", reverse("viagens:oficios")),
                              (oficio.numero_formatado, "")),
    }


def editar(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    if not policies.pode_editar(request.user, oficio):
        if oficio.editavel:
            messages.info(request, "Seu perfil permite consultar, mas não editar ofícios.")
        else:
            messages.info(request, f"O Ofício {oficio.numero_formatado} está "
                                   f"{oficio.get_situacao_display().lower()} e não pode ser "
                                   "editado; abra o resumo na lista para conferir.")
        return redirect(_na_lista(oficio))
    if request.method != "POST":
        contexto = _contexto_edicao(request, oficio)
        contexto.update(_revisao_pedida(request, oficio, contexto))
        return render(request, "viagens/oficios/editar.html", contexto)

    form = FormularioOficio(request.POST, instance=oficio)
    acao = request.POST.get("acao")
    if acao == "usar_roteiro":
        return _usar_roteiro(request, oficio)
    if acao == "adicionar_destino":  # sem JavaScript; com JS a parada entra na hora
        itin = itinerario.com_iniciais(FORM_ID, request.POST, mais_um=True)
        form.is_valid()
        contexto = _contexto_edicao(request, oficio, form, itin)
        contexto["foco"] = f"id_destino-{itin.destinos.total_form_count() - 1}-cidade"
        contexto["sujo"] = True  # nada foi salvo ainda: avisa e protege a saída
        return render(request, "viagens/oficios/editar.html", contexto)
    itin = itinerario.montar(FORM_ID, dados=request.POST)
    vazio = itin.vazio(request.POST)
    sede_ok = itin.sede.is_valid()
    roteiro_ok = sede_ok and (vazio or itin.valido())
    if form.is_valid() and roteiro_ok:
        try:
            dados = {k: v for k, v in form.cleaned_data.items() if k != "versao"}
            dados["sede"] = itin.sede.cleaned_data["cidade"]
            trechos = None if vazio else itinerario.trechos(itin)
            oficio = services.salvar_edicao(oficio, request.user, dados, trechos,
                                            versao=form.cleaned_data.get("versao"))
        except services.ConflitoDeEdicao as exc:
            form.add_error(None, str(exc))
        except services.RegraViolada as exc:
            contexto = _contexto_edicao(request, oficio, form, itin, str(exc))
            contexto.update(sujo=True, foco="alerta-roteiro")
            return render(request, "viagens/oficios/editar.html", contexto, status=422)
        else:
            if acao == "emitir":
                bloqueantes = services.verificar_prontidao(oficio).bloqueantes
                if bloqueantes:
                    messages.warning(request, f"Rascunho salvo, mas ainda há {len(bloqueantes)} "
                                              "pendência(s) para emitir. Veja o que falta "
                                              "logo abaixo.")
                    return redirect(f"{reverse('viagens:editar', args=[oficio.pk])}#emissao")
                # A revisão é a janela de resumo aberta sobre a própria folha.
                return redirect(f"{reverse('viagens:editar', args=[oficio.pk])}?revisar=1")
            if acao == "finalizar":  # "Finalizar" do rodapé: salvo, volta à lista
                messages.success(request, f"Ofício {oficio.numero_formatado} salvo.")
                return redirect("viagens:oficios")
            # A confirmação é da própria barra de ações ("Rascunho salvo às HH:MM"),
            # não de um toast: o operador salva dezenas de vezes por dia.
            return redirect(f"{reverse('viagens:editar', args=[oficio.pk])}?salvo=1")
    contexto = _contexto_edicao(request, oficio, form, itin)
    contexto.update(sujo=True, foco="resumo-erros" if form.errors else "alerta-roteiro")
    return render(request, "viagens/oficios/editar.html", contexto, status=422)


def _opcoes_de_roteiro(roteiros) -> list[dict]:
    """Rótulo e detalhe de cada roteiro na escolha "Usar um roteiro cadastrado"."""
    opcoes = []
    for r in roteiros:
        sede = f"{r.sede.nome}/{r.sede.uf}"
        destinos = list(dict.fromkeys(p for p in r.paradas if p and p != sede))
        diarias = f"{formatar_moeda(r.diarias_total)} · {r.diarias_resumo}" if r.diarias_resumo \
            else "sem diárias"
        servidores = f"{r.quantidade_servidores} servidor" + (
            "es" if r.quantidade_servidores != 1 else "")
        opcoes.append({
            "pk": r.pk,
            "rotulo": f"#{r.pk} · {sede} → {', '.join(destinos)}",
            "meta": f"{formatar_periodo(r.primeira_saida, r.ultima_chegada)} · {diarias} · "
                    f"{servidores}",
        })
    return opcoes


def _usar_roteiro(request, oficio) -> HttpResponse:
    """Preenche o itinerário (sede inclusive) com os trechos de um roteiro cadastrado,
    preservando tudo o que foi digitado no resto da folha. Nada é gravado: a pessoa confere
    e salva."""
    escolhido = (request.POST.get("roteiro_modelo") or "").strip()
    roteiro = (policies.roteiros_visiveis(request.user).select_related("sede")
               .filter(pk=escolhido).first() if escolhido.isdigit() else None)
    dados = request.POST.copy()
    erro = "" if roteiro else "Escolha um roteiro da lista para preencher os trechos."
    if roteiro is not None:
        try:
            services.exigir_roteiro_compativel(roteiro, oficio)
        except services.RegraViolada as exc:
            erro = str(exc)
    if erro or roteiro is None:
        form = FormularioOficio(dados, instance=oficio)
        itin = itinerario.com_iniciais(FORM_ID, request.POST)
        contexto = _contexto_edicao(request, oficio, form, itin, erro)
        contexto.update(sujo=True, foco="alerta-roteiro")
        return render(request, "viagens/oficios/editar.html", contexto, status=422)
    dados["roteiro"] = str(roteiro.pk)
    form = FormularioOficio(dados, instance=oficio)
    form.is_valid()
    iniciais, inicial_retorno = iniciais_de_trechos(queries.trechos_do_roteiro(roteiro),
                                                    roteiro.sede_id)
    itin = itinerario.com_iniciais(FORM_ID, request.POST, destinos=iniciais,
                                   retorno=inicial_retorno, sede=roteiro.sede)
    # Os trechos vieram prontos do roteiro: as diárias já podem ser mostradas, mesmo antes
    # de salvar — é a mesma conta do salvamento, sobre a equipe que o ofício já tem.
    informados = [services.TrechoInformado(t.origem_id, t.destino_id, t.saida_em, t.chegada_em)
                  for t in queries.trechos_do_roteiro(roteiro)]
    equipe = max(1, len(viajantes_de(oficio)))
    previa = services.calcular_informados(informados, roteiro.sede, equipe)
    contexto = _contexto_edicao(request, oficio, form, itin, calculo=previa)
    contexto.update(sujo=True, foco="roteiro-aplicado", roteiro_aplicado=roteiro)
    return render(request, "viagens/oficios/editar.html", contexto)


# ------------------------------------------------------------------ equipe (HTMX)
def _secao_equipe(request, oficio, erro: str = "") -> HttpResponse:
    oficio.refresh_from_db()
    contexto = {
        "oficio": oficio, "erro_equipe": erro, "oob": True,
        "viajantes": viajantes_de(oficio),
        "prontidao": services.verificar_prontidao(oficio),
        # Mexer na equipe é uma gravação: daqui em diante a pendência pode falar.
        "mostrar_pendencias": True,
    }
    resposta = render(request, "viagens/oficios/_equipe.html", contexto)
    resposta["HX-Trigger"] = "equipe-alterada"
    return resposta


@require_POST
def adicionar_viajante(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    servidor = get_object_or_404(Servidor, pk=request.POST.get("id"))
    try:
        services.adicionar_viajante(oficio, request.user, servidor)
    except services.RegraViolada as exc:
        return _secao_equipe(request, oficio, str(exc))
    if not _htmx(request):
        return redirect(f"{reverse('viagens:editar', args=[pk])}#equipe")
    return _secao_equipe(request, oficio)


@require_POST
def remover_viajante(request: HttpRequest, pk: int, viajante_id: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    services.remover_viajante(oficio, request.user, viajante_id)
    if not _htmx(request):
        return redirect(f"{reverse('viagens:editar', args=[pk])}#equipe")
    return _secao_equipe(request, oficio)


@require_POST
def definir_motorista(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    viajante_id = request.POST.get("viajante") or None
    services.definir_motorista(oficio, request.user, int(viajante_id) if viajante_id else None)
    if not _htmx(request):
        return redirect(f"{reverse('viagens:editar', args=[pk])}#equipe")
    return _secao_equipe(request, oficio)


@require_GET
def secao_diarias(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    return render(request, "viagens/oficios/_diarias.html", {
        # Bloco dentro do cartão Identificação (a folha do ofício não numera mais assuntos).
        "oficio": oficio, "calculo": oficio.diarias_calculo, "bloco": True,
        "faixas": {f.value: f.rotulo for f in Faixa}})


# ------------------------------------------------------------------ emissão
def _revisao_pedida(request: HttpRequest, oficio, folha: dict) -> dict:
    """"Revisar e emitir": a janela de resumo, em modo revisão, aberta sobre a folha.

    Só abre quando quem pede pode emitir e o ofício não tem pendência — senão a folha já
    mostra o que falta, e uma janela com o botão desligado só atrapalharia. Reaproveita o
    que a folha já carregou (equipe, trechos, prontidão, prazo): a janela não consulta de novo.
    """
    if request.GET.get("revisar") != "1" or not folha["prontidao"].pode_emitir:
        return {}
    if not policies.pode_emitir(request.user, oficio):
        return {}
    return {"abrir_resumo": oficio.pk, "resumo": {
        "revisao": True, "oficio": oficio, "dados": dados_do_oficio(oficio),
        "pode_emitir": True, "assunto": folha["assunto"], "prazo": folha["prazo"],
        "calculo": oficio.diarias_calculo, "viajantes": folha["viajantes"],
        "trechos": folha["trechos"], "documentos": list(oficio.documentos.all()),
        "prontidao": folha["prontidao"],
    }}


@require_POST
def emitir(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    try:
        services.emitir(oficio, request.user, versao=int(request.POST.get("versao") or 0) or None)
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
        if oficio.editavel:
            return redirect(f"{reverse('viagens:editar', args=[pk])}#emissao")
        return redirect(_na_lista(oficio))
    messages.success(request, f"Ofício {oficio.numero_formatado} emitido. O PDF está sendo "
                              "gerado e aparece em Documentos em instantes.")
    return redirect(_na_lista(oficio))


@require_POST
def autosave(request: HttpRequest, pk: int) -> JsonResponse:
    """Grava o rascunho enquanto a pessoa preenche, a cada pausa na digitação.

    Salva o que der: campo que ainda não é válido fica de fora e o resto é gravado — nunca
    se perde o que já foi digitado. Os trechos só entram quando o itinerário fecha (ida,
    volta e datas), senão ficam como estão. Não escreve no histórico (services.salvar_edicao
    com `registrar=False`): quem conta a história é o salvamento explícito e a emissão.
    """
    oficio = _oficio_visivel(request, pk)
    if not policies.pode_editar(request.user, oficio):
        return JsonResponse({"salvo": False, "motivo": "Este ofício não pode ser alterado."})
    form = FormularioOficio(request.POST, instance=oficio)
    form.is_valid()  # `cleaned_data` fica com o que passou; o resto não é gravado
    dados = {k: v for k, v in form.cleaned_data.items() if k != "versao"}
    itin = itinerario.montar(FORM_ID, dados=request.POST)
    trechos = None
    if itin.sede.is_valid() and itin.sede.cleaned_data.get("cidade"):
        dados["sede"] = itin.sede.cleaned_data["cidade"]
        if itin.valido():
            try:
                trechos = itinerario.trechos(itin)
            except services.RegraViolada:
                trechos = None
    try:
        salvo = services.salvar_edicao(oficio, request.user, dados, trechos,
                                       versao=form.cleaned_data.get("versao"),
                                       registrar=False)
    except (services.ConflitoDeEdicao, services.RegraViolada) as exc:
        return JsonResponse({"salvo": False, "motivo": str(exc)})
    return JsonResponse({
        "salvo": True,
        "em": timezone.localtime(salvo.atualizado_em).strftime("%H:%M"),
        # A versão nova volta para o formulário: sem isso, o próximo salvamento acusaria
        # conflito com a gravação que o próprio autosave acabou de fazer.
        "campos": {"versao": salvo.versao},
    })


@require_POST
def retificar(request: HttpRequest, pk: int) -> HttpResponse:
    """Editar um ofício emitido: ele volta a rascunho como retificação e a folha abre."""
    oficio = _oficio_visivel(request, pk)
    try:
        services.retificar(oficio, request.user)
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
        return redirect(_na_lista(oficio))
    messages.success(request, f"Ofício {oficio.numero_formatado} aberto para retificação. "
                              "Ao emitir de novo sai a versão corrigida.")
    return redirect("viagens:editar", pk=pk)


@require_POST
def reabrir(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    try:
        services.reabrir(oficio, request.user, request.POST.get("motivo", ""))
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
        return redirect(_na_lista(oficio))
    messages.success(request, "Ofício reaberto. Corrija e emita uma nova versão.")
    return redirect("viagens:editar", pk=pk)


@require_POST
def cancelar(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    try:
        services.cancelar(oficio, request.user, request.POST.get("motivo", ""))
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Ofício {oficio.numero_formatado} cancelado. O gestor pode "
                                  "reativá-lo depois, com justificativa.")
    return redirect(_voltar(request, oficio))


@require_POST
def reativar(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    try:
        oficio = services.reativar(oficio, request.user, request.POST.get("justificativa", ""))
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Ofício {oficio.numero_formatado} reativado "
                                  f"({oficio.get_situacao_display().lower()}). O cancelamento "
                                  "e a justificativa ficam no histórico.")
    return redirect(_voltar(request, oficio))


@require_POST
def arquivar(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = services.arquivar(_oficio_visivel(request, pk), request.user)
    messages.success(request, f"Ofício {oficio.numero_formatado} arquivado. Ele fica na aba "
                              "Arquivados e pode ser desarquivado a qualquer momento.")
    return redirect(_voltar(request, oficio))


@require_POST
def desarquivar(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = services.desarquivar(_oficio_visivel(request, pk), request.user)
    messages.success(request, f"Ofício {oficio.numero_formatado} desarquivado.")
    return redirect(_voltar(request, oficio))


@require_POST
def duplicar(request: HttpRequest, pk: int) -> HttpResponse:
    """Um rascunho novo com os mesmos dados; abre a folha dele."""
    oficio = _oficio_visivel(request, pk)
    try:
        novo = services.duplicar_oficio(oficio, request.user)
    except (services.RegraViolada, PermissionDenied) as exc:
        messages.error(request, str(exc))
        return redirect(_voltar(request, oficio))
    messages.success(request, f"Ofício {novo.numero_formatado} criado a partir do "
                              f"Ofício {oficio.numero_formatado}.")
    return redirect("viagens:editar", novo.pk)


@require_POST
def excluir(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    numero = services.excluir_rascunho(oficio, request.user)
    messages.success(request, f"Rascunho {numero} excluído; o número volta a ficar disponível.")
    voltar = _voltar(request, oficio)
    return redirect(voltar if "q=" not in voltar else "viagens:oficios")
def _contexto_resumo(request: HttpRequest, oficio, *, revisao: bool = False) -> dict:
    """O que a janela de resumo mostra — serve ao fragmento HTMX e à janela já desenhada.

    Em `revisao` (antes de emitir) ela também mostra o que vai no papel e não está na
    folha — destinatário e quem assina — e troca o rodapé pelo botão de emitir.
    """
    documentos = list(oficio.documentos.select_related("emitido_por").order_by("tipo", "-versao"))
    extras = {"revisao": True, "dados": dados_do_oficio(oficio),
              "pode_emitir": policies.pode_emitir(request.user, oficio)} if revisao else {}
    return {**extras,
        "oficio": oficio,
        "assunto": services.assunto_do_oficio(oficio),
        "prazo": services.avaliar_prazo_do_oficio(oficio),
        "calculo": oficio.diarias_calculo,
        "viajantes": viajantes_de(oficio),
        "trechos": trechos_de(oficio),
        "documentos": documentos,
        "prontidao": services.verificar_prontidao(oficio) if oficio.editavel else None,
        "pode_editar": policies.pode_editar(request.user, oficio),
        "pode_retificar": policies.pode_retificar(request.user, oficio),
        "acoes": policies.acoes_do_oficio(request.user, oficio, com_exclusao=True),
        # Termos de autorização (módulo 4): criar a partir deste ofício e ver os dele.
        "pode_termo": (policies.pode_criar_termo(request.user)
                       and oficio.situacao != Oficio.Situacao.CANCELADO),
        # Sem contar (a janela tem orçamento de consultas): o link abre a lista filtrada.
        "termos_do_oficio": request.user.has_perm("viagens.view_termoautorizacao"),
        "pode_os": policies.pode_criar_ordem_do_oficio(request.user, oficio),
        "ordens_do_oficio": request.user.has_perm("viagens.view_ordemservico"),
        "pode_plano": policies.pode_criar_plano_do_oficio(request.user, oficio),
        "planos_do_oficio": request.user.has_perm("viagens.view_planotrabalho"),
        # O PDF do ofício que vale (o primeiro ofício pronto, não o primeiro documento).
        "pdf_oficio": next((d for d in documentos if d.tipo == Documento.Tipo.OFICIO
                            and d.situacao == Documento.Situacao.PRONTO), None),
        "vias": _vias_do_oficio(request, oficio, documentos),
        "pode_baixar": (policies.edita_oficios(request.user)
                        and oficio.situacao != Oficio.Situacao.CANCELADO),
    }


def _vias_do_oficio(request: HttpRequest, oficio, documentos) -> list[dict]:
    """A via assinada de cada documento emitido (o PDF pronto mais recente de cada tipo)."""
    from . import assinados, views_assinados

    prontos: dict[str, Documento] = {}
    for d in documentos:  # já vêm do mais novo para o mais velho
        if d.situacao == Documento.Situacao.PRONTO:
            prontos.setdefault(d.tipo, d)
    if not prontos:
        return []
    vias = assinados.vigentes_do(oficio)
    # O resumo é um fragmento: remover volta para a lista com o resumo aberto.
    voltar = f"{reverse('viagens:oficios')}?resumo={oficio.pk}"
    ordem: list[str] = ["oficio", "justificativa"]  # o ofício primeiro
    return [views_assinados.cartao(
        request, assinados.Alvo(tipo, oficio), vias.get((tipo, "")),
        titulo=(f"Ofício {oficio.numero_formatado} · v{doc.versao}" if tipo == "oficio"
                else f"Justificativa do Ofício {oficio.numero_formatado} · v{doc.versao}"),
        original_url=reverse("viagens:baixar_documento", args=[doc.pk]), voltar=voltar)
        for tipo, doc in sorted(prontos.items(), key=lambda par: ordem.index(par[0]))]


@require_GET
def resumo(request: HttpRequest, pk: int) -> HttpResponse:
    """Fragmento HTMX: a janela de resumo que a lista abre no clique. Traz o que a pessoa
    precisa para decidir sem abrir o ofício — o mesmo conteúdo da folha, menos o histórico."""
    oficio = _oficio_visivel(request, pk)
    return render(request, "viagens/oficios/_resumo.html", _contexto_resumo(request, oficio))


@require_GET
def documentos_parcial(request: HttpRequest, pk: int) -> HttpResponse:
    oficio = _oficio_visivel(request, pk)
    documentos = list(oficio.documentos.select_related("emitido_por"))
    return render(request, "viagens/oficios/_documentos.html", {
        "oficio": oficio, "documentos": documentos,
        "gerando": any(d.situacao == Documento.Situacao.GERANDO for d in documentos)})


@require_GET
def baixar_documento(request: HttpRequest, documento_id: int) -> FileResponse:
    doc = get_object_or_404(Documento.objects.select_related("oficio"), pk=documento_id)
    if not policies.pode_ver(request.user, doc.oficio):
        raise Http404
    if doc.situacao != Documento.Situacao.PRONTO:
        raise Http404("Documento ainda não gerado.")
    if request.GET.get("versao") != "original":
        via = doc.vias_assinadas.filter(revogada_em__isnull=True).order_by("-enviado_em").first()
        if via is not None:
            from .views_assinados import resposta_da_via
            return resposta_da_via(via, baixar=request.GET.get("baixar") == "1")
    resposta = FileResponse(doc.arquivo.open("rb"), content_type="application/pdf",
                            as_attachment=request.GET.get("baixar") == "1",
                            filename=doc.nome_arquivo)
    resposta["X-Content-SHA256"] = doc.sha256
    return resposta


@require_GET
# A folha do ofício mostra a minuta num iframe. A política comum manda `frame-ancestors
# 'none'` em toda resposta (contra clickjacking), o que proibiria o próprio sistema de
# emoldurá-la. Só nesta resposta, e só para a mesma origem, a moldura é permitida; todas as
# outras diretivas seguem iguais.
@csp_override({**settings.SECURE_CSP, "frame-ancestors": [CSP.SELF]})
def previa(request: HttpRequest, pk: int) -> HttpResponse:
    """Minuta em PDF gerada na hora (rascunho), com marca d'água — não é arquivada."""
    oficio = _oficio_visivel(request, pk)
    tipo = request.GET.get("tipo", "oficio")
    if tipo not in {"oficio", "justificativa"}:
        raise Http404
    dados = dados_do_oficio(oficio)
    from weasyprint import HTML

    # O texto editado vai junto: a minuta é a mesma folha do editor, em PDF (ADR 0018).
    # Sem `regioes`, `html_do_documento` cairia no modelo puro — e o botão "PDF" da barra
    # mostrava um documento diferente do que estava escrito ao lado, no modo "Texto".
    html = html_do_documento(tipo, dados, previa=True,
                             regioes=services.regioes_vigentes(oficio, tipo))
    pdf = HTML(string=html, base_url=str(ASSETS),
               url_fetcher=buscar_recurso()).write_pdf()
    resposta = HttpResponse(pdf, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="minuta-{oficio.numero}-{oficio.ano}.pdf"'
    return resposta


@require_GET
def baixar_docx(request: HttpRequest, pk: int, tipo: str) -> HttpResponse:
    """D4: o documento em DOCX editável (paridade com "Baixar DOCX" da referência). Emitido →
    a via emitida (dados e texto congelados); rascunho → como está agora, marcado MINUTA."""
    oficio = _oficio_visivel(request, pk)
    if tipo not in {"oficio", "justificativa"}:
        raise Http404
    from .documentos.docx import docx_do_html

    emitido = (oficio.documentos.filter(tipo=tipo, situacao=Documento.Situacao.PRONTO)
               .order_by("-versao").first() if oficio.situacao != Oficio.Situacao.RASCUNHO
               else None)
    if emitido is not None:
        html = html_do_documento(tipo, emitido.dados)
        nome = f"{tipo}-{oficio.numero:02d}-{oficio.ano}-v{emitido.versao}.docx"
    else:
        html = html_do_documento(tipo, dados_do_oficio(oficio),
                                 regioes=services.regioes_vigentes(oficio, tipo))
        nome = f"minuta-{tipo}-{oficio.numero:02d}-{oficio.ano}.docx"
    conteudo = docx_do_html(html, base_imagens=ASSETS, minuta=emitido is None)
    resposta = HttpResponse(conteudo, content_type=(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resposta


# ------------------------------------------------------------------ APIs (combobox/busca)
@require_GET
def buscar_servidores(request: HttpRequest) -> JsonResponse:
    if not policies.pode_buscar_servidores(request.user):
        raise PermissionDenied
    termo = (request.GET.get("q") or "").strip()
    digitos = "".join(c for c in termo if c.isdigit())
    filtro = Q(nome__unaccent__icontains=termo)
    if len(digitos) >= 3:
        filtro |= Q(cpf__contains=digitos) | Q(rg__contains=digitos)
    servidores = (Servidor.objects.filter(ativo=True).filter(filtro)
                  .select_related("cargo", "unidade").order_by("nome"))
    # `?oficio=<pk>`: quem já está na equipe sai da lista. Oferecer de novo quem já entrou só
    # produz o erro "já está na equipe" — a busca é para achar quem falta.
    if (pk := (request.GET.get("oficio") or "")).isdigit():
        servidores = servidores.exclude(viagens__oficio_id=int(pk))
    servidores = servidores[:15]
    return JsonResponse({"resultados": [
        {"id": str(s.pk), "titulo": s.nome, "meta": s.descricao}
        for s in servidores]})



# ------------------------------------------------------------------ rota (mapa do itinerário)
@require_GET
def rota(request: HttpRequest) -> JsonResponse:
    """Pernas da rota entre as paradas informadas (?p=Cidade/UF&p=...): km, tempo de estrada,
    tempo adicional sugerido e traçado para o mapa. Paradas inválidas voltam com erro."""
    if not (request.user.has_perm("viagens.view_oficio")
            or request.user.has_perm("viagens.view_roteiro")):
        raise PermissionDenied
    textos = [t.strip() for t in request.GET.getlist("p")][:12]
    pontos: list[dict] = []
    municipios: list[Municipio | None] = []
    for texto in textos:
        try:
            m = resolver_municipio(texto)
        except ValidationError as exc:
            pontos.append({"rotulo": texto, "erro": exc.messages[0]})
            municipios.append(None)
            continue
        pontos.append({"rotulo": f"{m.nome}/{m.uf}",
                       "lat": float(m.latitude) if m.latitude is not None else None,
                       "lon": float(m.longitude) if m.longitude is not None else None})
        municipios.append(m)
    pernas: list[dict | None] = []
    for a, b in pairwise(municipios):
        if a is None or b is None:
            pernas.append(None)
            continue
        p = rotas.calcular(a, b)
        pernas.append({"km": float(p.km), "minutos": p.minutos,
                       "adicional_sugerido": p.adicional_sugerido, "fonte": p.fonte,
                       "tracado": p.tracado})
    validas = [p for p in pernas if p]
    return JsonResponse({
        "pontos": pontos, "pernas": pernas,
        "total": {"km": round(sum(p["km"] for p in validas), 1),
                  "minutos": sum(p["minutos"] for p in validas)},
    })


# ------------------------------------------------------------------ numeração anual
def numeracao(request: HttpRequest) -> HttpResponse:
    """Piso da numeração por ano (paridade com "Numeração" da referência), com o que importa
    para decidir: maior número usado, lacunas livres e o próximo número que sai."""
    policies.exigir(policies.pode_gerir_numeracao(request.user),
                    "Só o gestor de viagens define a numeração anual.")
    erro = ""
    if request.method == "POST":
        try:
            ano, piso = int(request.POST.get("ano", "")), int(request.POST.get("piso", ""))
        except ValueError:
            erro = "Informe o ano e o piso em números, ex.: 2026 e 100."
        else:
            try:
                services.definir_piso(request.user, ano, piso)
            except services.RegraViolada as exc:
                erro = str(exc)
            else:
                proximo = next((a.proximo for a in services.resumo_numeracao([ano])
                                if a.ano == ano), piso)
                efeito = ("" if proximo == piso else
                          " O piso não muda a sequência agora: o maior número já usado é maior.")
                messages.success(request, f"Piso de {ano} gravado: {piso}. O próximo ofício de "
                                          f"{ano} será {proximo:02d}/{ano}.{efeito} Ofícios já "
                                          "numerados não mudam.")
                return redirect("viagens:numeracao")
    return render(request, "viagens/numeracao.html", {
        "anos": services.resumo_numeracao(), "erro": erro,
        "ano_atual": timezone.localdate().year,
        "migalhas": _migalhas(("Numeração dos ofícios", "")),
    }, status=422 if erro else 200)


# ------------------------------------------------------------------ justificativas (D6)
def _lista_justificativas(request: HttpRequest, *, form=None, editando=None, status=200):
    policies.exigir(policies.pode_listar(request.user))
    base = policies.oficios_visiveis(request.user)
    contagens = queries.contagens_justificativas(base)
    aba = request.GET.get("aba") or request.POST.get("aba") or ""
    if not aba and contagens["pendentes"]:
        aba = "pendentes"  # a tela existe para zerar as pendentes: abre nelas
    if aba not in queries.ABAS_JUSTIFICATIVAS:
        aba = ""
    termo = (request.GET.get("q") or "").strip()
    qs = queries.justificativas(base, aba)
    if termo:
        achados = services.buscar_por_texto(base, termo).values("pk")
        qs = qs.filter(Q(pk__in=achados) | Q(justificativa__unaccent__icontains=termo))
    qs = (queries.com_dados_de_lista(qs).select_related("justificativa_modelo")
          .prefetch_related(Prefetch("documentos", to_attr="docs_justificativa",
                                     queryset=Documento.objects.filter(
                                         tipo=Documento.Tipo.JUSTIFICATIVA,
                                         situacao=Documento.Situacao.PRONTO).order_by("-versao")))
          # Pendentes pela saída mais próxima (urgência); as demais, pelo número.
          .order_by(*((F("saida_dia").asc(nulls_last=True), "-ano", "-numero")
                      if aba == "pendentes" else ("-ano", "-numero"))))
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    pagina.object_list = list(pagina.object_list)
    for o in pagina.object_list:  # o que cada linha oferece vem da política
        o.editavel_aqui = policies.pode_editar(request.user, o)  # type: ignore[attr-defined]
        saida_dia = getattr(o, "saida_dia", None)  # anotado por queries.com_regra_de_prazo
        o.antecedencia = (  # type: ignore[attr-defined]
            (saida_dia - o.data_oficio).days if saida_dia else None)
    if form is None and (pk := request.GET.get("editar", "")).isdigit():
        editando = _oficio_visivel(request, int(pk))
        if policies.pode_editar(request.user, editando):
            form = FormularioJustificativa(initial={
                "justificativa": editando.justificativa, "versao": editando.versao,
                "justificativa_modelo": editando.justificativa_modelo_id})
        else:
            editando = None
    filtros = request.GET.copy()
    for chave in ("pagina", "editar"):
        filtros.pop(chave, None)
    return render(request, "viagens/justificativas/lista.html", {
        "page_obj": pagina, "oficios": pagina.object_list, "aba": aba, "termo": termo,
        "abas": [("", "Todas", "todas")] + [(k, r, k) for k, r in
                                             queries.ABAS_JUSTIFICATIVAS.items()],
        "contagens": contagens,
        "querystring_base": (filtros.urlencode() + "&") if filtros else "",
        "form": form, "editando": editando,
        "pode_gerir_textos": policies.pode_gerir_textos_prontos(request.user),
        "pode_baixar": policies.edita_oficios(request.user),
        "migalhas": _migalhas(("Justificativas", "")),
    }, status=status)


@require_GET
def justificativas(request: HttpRequest) -> HttpResponse:
    return _lista_justificativas(request)


@require_POST
def salvar_justificativa(request: HttpRequest, pk: int) -> HttpResponse:
    """Grava a justificativa no próprio ofício (mesma concorrência por versão da folha)."""
    oficio = _oficio_visivel(request, pk)
    policies.exigir(policies.pode_editar(request.user, oficio),
                    "Só a justificativa de um rascunho pode ser alterada — para um emitido, "
                    "edite o ofício (ele vira retificado).")
    form = FormularioJustificativa(request.POST)
    voltar = f"{reverse('viagens:justificativas')}?{request.POST.get('voltar', '')}"
    apagar = request.POST.get("apagar") == "1"
    if form.is_valid() and not apagar and not form.cleaned_data["justificativa"]:
        form.add_error("justificativa", "Escreva a justificativa. Para apagar o texto, use "
                                        "“Apagar justificativa” no menu do ofício.")
    if form.is_valid():
        dados = form.cleaned_data
        try:
            services.salvar_dados(oficio, request.user, {
                "justificativa": dados["justificativa"],
                "justificativa_modelo": dados["justificativa_modelo"]},
                versao=dados["versao"])
        except (services.ConflitoDeEdicao, services.RegraViolada) as exc:
            form.add_error(None, str(exc))
        else:
            if dados["justificativa"]:
                messages.success(request, f"Justificativa do Ofício {oficio.numero_formatado} "
                                          "gravada.")
            else:
                messages.success(request, f"Justificativa do Ofício {oficio.numero_formatado} "
                                          "apagada; o ofício volta a ficar pendente se o prazo "
                                          "exigir.")
            return redirect(voltar)
    return _lista_justificativas(request, form=form, editando=oficio, status=422)
