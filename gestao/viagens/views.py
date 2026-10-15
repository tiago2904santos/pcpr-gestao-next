"""Telas do módulo Viagens (piloto: painel, lista, novo, edição, emissão, documentos).

A leitura de um ofício é a janela de resumo que a lista abre (views.resumo): não há
página separada só para ler — ela repetia a folha e dividia a atenção."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import F, Prefetch, Q, QuerySet, prefetch_related_objects
from django.db.models.expressions import OrderBy
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    JsonResponse,
    QueryDict,
)
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

from . import exportacao, itinerario, linha_lista, policies, queries, rotas, services
from .documentos.dados import dados_do_oficio
from .documentos.pdf import ASSETS, buscar_recurso, html_do_documento
from .dominio import busca as dominio_busca
from .dominio import recorte
from .dominio.diarias import Faixa
from .enderecos import url_na_lista
from .eprotocolo import ProjecaoEprotocolo, projetar_dados_eprotocolo
from .forms import (
    FORM_ID,
    FiltrosOficio,
    FormularioJustificativa,
    FormularioOficio,
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
                                      "viatura__combustivel", "sede", "transporte_combustivel",
                                      "viagem", "criado_por"),  # viagem e autor: sub-header
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
    abre na própria lista. Arquivado só aparece com Documento = Arquivados."""
    return url_na_lista(oficio)


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


@dataclass
class RecorteDaLista:
    """O que a lista mostra — a mesma conta serve à tela e à planilha, para quem exporta
    levar exatamente o que estava vendo (abas, documento, busca, filtros e ordem)."""

    qs: QuerySet[Oficio]
    filtrado: QuerySet[Oficio]       # base + busca + filtros (sem aba nem documento)
    aba: str
    documento: str
    termo: str
    escopo: str
    avancados: FiltrosOficio
    ordem: str

    @property
    def tem_filtro(self) -> bool:
        """Algo além da aba restringe a lista (o que pede "N de M" e o vazio de busca)."""
        return bool(self.termo or self.documento or self.avancados.fichas)


def _recorte_da_lista(request: HttpRequest, base, anos: list[int]) -> RecorteDaLista:
    get = request.GET
    aba = get.get("aba") or ""
    aba = aba if aba in recorte.CHAVES_ABAS else ""
    documento = get.get("documento") or ""
    documento = documento if documento in recorte.CHAVES_DOCUMENTOS else ""
    termo = (get.get("q") or "").strip()
    escopo = (get.get("escopo") or "") if termo else ""
    avancados = FiltrosOficio(get, anos=anos)
    filtrado = queries.aplicar_filtros_avancados(
        services.buscar_por_texto(base, termo, escopo), avancados.validos)
    ordem = get.get("ordem") or recorte.ORDEM_PADRAO
    ordem = ordem if ordem in recorte.CHAVES_ORDENS else recorte.ORDEM_PADRAO
    qs = queries.com_dados_de_lista(queries.aplicar_recorte(filtrado, aba, documento)).order_by(
        *ORDENS_DA_LISTA[ordem])
    return RecorteDaLista(qs, filtrado, aba, documento, termo, escopo, avancados, ordem)


def _endereco_antigo(request: HttpRequest) -> HttpResponse | None:
    """`?situacao=rascunho` (abas de antes do Lote 2) → o mesmo recorte no vocabulário novo.
    Favoritos, o painel antigo e outras telas continuam chegando onde queriam."""
    novos = recorte.traduzir_endereco_antigo(request.GET.dict())
    if novos is None:
        return None
    destino = reverse("viagens:oficios")
    return redirect(f"{destino}?{urlencode(novos)}" if novos else destino)


@require_GET
def exportar(request: HttpRequest) -> HttpResponse:
    """A lista de agora (com os mesmos filtros) numa planilha Excel."""
    if not policies.pode_listar(request.user):
        raise PermissionDenied
    base = policies.oficios_visiveis(request.user)
    get = request.GET
    if (novos := recorte.traduzir_endereco_antigo(get.dict())) is not None:
        request.GET = QueryDict(urlencode(novos))  # type: ignore[misc]  # link antigo
    qs = _recorte_da_lista(request, base, queries.anos_dos_numeros(base)).qs
    nome = f"oficios-{timezone.localdate():%Y-%m-%d}.xlsx"
    resposta = HttpResponse(
        exportacao.planilha_de_oficios(qs.iterator(chunk_size=200)),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resposta


def _sem(get: QueryDict, *chaves: str, so: tuple[str, ...] | None = None) -> str:
    """A lista com os parâmetros de agora menos `chaves` (ou só com `so`), na página 1."""
    copia = get.copy()
    copia.pop("pagina", None)
    for chave in list(copia.keys()):
        if chave in chaves or (so is not None and chave not in so) or not copia.get(chave):
            copia.pop(chave)
    consulta = copia.urlencode()
    return f"{reverse('viagens:oficios')}?{consulta}" if consulta else reverse("viagens:oficios")


def _trocar(get: QueryDict, chave: str, valor: str) -> str:
    """A lista com `chave` = `valor` (vazio tira a chave) e o resto como está."""
    copia = QueryDict(mutable=True)
    if valor:
        copia[chave] = valor  # a chave trocada vem primeiro: endereço fácil de ler
    for outra, valores in get.lists():
        if outra != chave:
            copia.setlist(outra, valores)
    return _sem(copia)


def _fichas(get: QueryDict, r: RecorteDaLista, refino_atual: dict | None) -> list[dict]:
    """Uma ficha por filtro valendo (D6), cada uma tira só o que diz. A busca, a aba e o
    Documento não são fichas: a busca tem o próprio campo (com o X), a aba se troca na
    fileira e o Documento é o segmentado sempre à vista ("Todos" é o X dele) — uma ficha a
    mais repetia o que está marcado e custava uma linha no celular (QA Lote 2, I4)."""
    fichas: list[tuple[str, tuple[str, ...]]] = []
    if refino_atual:
        fichas.append((f"Buscando em: {refino_atual['rotulo']}", ("escopo",)))
    fichas += r.avancados.fichas
    if r.ordem != recorte.ORDEM_PADRAO:
        fichas.append(("Ordem: " + recorte.rotulo(recorte.ORDENS, r.ordem), ("ordem",)))
    return [{"rotulo": rotulo, "url": _sem(get, *chaves)} for rotulo, chaves in fichas]


def _grupos_por_mes(oficios: list, ordem: str, pagina, totais: dict | None = None) -> None:
    """Cabeçalho de mês com quantos ofícios do mês estão nesta página (LP-26). O grupo que
    continua na página vizinha diz "nesta página" — a conta não finge ser do mês todo. O
    total de diárias é do mês inteiro no recorte (`queries.totais_por_mes`)."""
    por_saida = ordem in ("saida", "-saida")
    totais = totais or {}

    def chave(o):
        if por_saida:
            return timezone.localtime(o.primeira_saida).strftime("%Y-%m") if o.primeira_saida \
                else ""
        return o.data_oficio.strftime("%Y-%m")

    grupos: list[list] = []
    for o in oficios:
        if grupos and chave(grupos[-1][0]) == chave(o):
            grupos[-1].append(o)
        else:
            grupos.append([o])
    for i, grupo in enumerate(grupos):
        parcial = (i == 0 and pagina.has_previous()) or (
            i == len(grupos) - 1 and pagina.has_next())
        n_mes, total_mes = totais.get(chave(grupo[0]), (len(grupo), None))
        grupo[0].grupo = {"quantidade": len(grupo), "parcial": parcial,
                          "quantidade_mes": n_mes, "total": total_mes}


# Linha da lista: o que falta, a urgência e a estrada. Sem consulta por linha — tudo vem
# de `com_dados_de_lista` (equipe, trechos, unidade). As ações ficam só no ⋮ (pedido do
# dono: nenhum botão no cartão).
def _cartoes_de_atencao(request: HttpRequest, atencao: str, contas: dict) -> list[dict]:
    """A faixa "pede atenção" (componentes/atencao_lista.html): cada cartão filtra a lista;
    o ativo volta. Os vazios, à vista, ganham "Excluir" (para quem pode excluir)."""
    get, cartoes = request.GET, []
    if u := contas["urgentes"]:
        cartoes.append({"tipo": "urgente", "icone": "timer", "ativo": atencao == "urgentes",
                        "titulo": f"{u} rascunho{' sai' if u == 1 else 's saem'} em até 7 dias",
                        "nota": "Emita antes da saída — o mais perto primeiro",
                        "url": _sem(get, "atencao") if atencao == "urgentes"
                        else _trocar(get, "atencao", "urgentes")})
    if v := contas["vazios"]:
        cartao = {"tipo": "vazio", "icone": "inbox", "ativo": atencao == "vazios",
                  "titulo": f"{v} rascunho{' vazio' if v == 1 else 's vazios'}",
                  "nota": "Sem roteiro, equipe, protocolo nem transporte",
                  "url": _sem(get, "atencao") if atencao == "vazios"
                  else _trocar(get, "atencao", "vazios")}
        if request.user.has_perm("viagens.delete_oficio"):
            cartao.update(
                excluir_url=reverse("viagens:excluir_vazios"),
                excluir_rotulo="Excluir o vazio" if v == 1 else f"Excluir os {v}",
                excluir_confirmar=(
                    f"{v} rascunho{' vazio é excluído' if v == 1 else 's vazios são excluídos'}"
                    " e os números voltam a ficar disponíveis. Rascunhos com qualquer dado "
                    "preenchido ficam."))
        cartoes.append(cartao)
    return cartoes


def _situacao_da_linha(usuario, o, agora) -> dict:
    trechos = trechos_de(o)
    cancelado = o.situacao == Oficio.Situacao.CANCELADO
    rascunho = o.situacao == Oficio.Situacao.RASCUNHO and not o.arquivado
    linha: dict = {"pendencias": [], "vazio": False,
                   **linha_lista.estado_temporal(
                       trechos[0].saida_em if trechos and not cancelado else None,
                       trechos[-1].chegada_em if trechos else None, agora, pendente=rascunho)}
    if rascunho:
        folha = reverse("viagens:editar", args=[o.pk])
        pendencias = services.pendencias_que_impedem(o)
        linha["pendencias"] = [{"mensagem": p.mensagem, "url": f"{folha}#{p.secao}"}
                               for p in pendencias]
        # D4: "Justificativa pendente" é o alerta que vence — a linha fica com o filete de
        # urgência, mas o selo é o da justificativa.
        linha["selo_urgencia"] = bool(linha["urgencia"]) and not any(
            p.secao == "justificativa" for p in pendencias)
        linha["url_conferencia"] = f"{folha}#conferencia"
        linha["vazio"] = not (trechos or viajantes_de(o) or o.protocolo or o.viatura_id
                              or o.transporte_descricao or getattr(o, "tem_documentos", False))
    return linha


def _mais_da_lista(request: HttpRequest) -> list[dict[str, str]]:
    """Itens do "Mais" da barra (D8): o que a página faz além do dia a dia, por permissão.
    Hoje vazio — a tela de Numeração foi excluída a pedido do dono do produto (4a3f835);
    "Importar processo do eProtocolo" entra aqui quando existir (D10), nunca antes, inativo."""
    return []


@require_GET
@vary_on_headers("HX-Request", "HX-Target")  # senão o "Voltar" do navegador reusa o fragmento
def lista(request: HttpRequest) -> HttpResponse:
    if not policies.pode_listar(request.user):
        raise PermissionDenied
    if (antigo := _endereco_antigo(request)) is not None:
        return antigo
    base = policies.oficios_visiveis(request.user)
    anos = queries.anos_dos_numeros(base)
    r = _recorte_da_lista(request, base, anos)
    # Leituras do termo ("26" é número de ofício? protocolo?) com quantos ofícios cada uma
    # traria dentro do recorte de agora: a tela oferece o refino em vez de despejar tudo o
    # que casou por acaso.
    leituras = dominio_busca.ler(r.termo, timezone.localdate().year)
    contagem_leituras = queries.contar_leituras(queries.aplicar_recorte(
        queries.aplicar_filtros_avancados(base, r.avancados.validos), r.aba, r.documento),
        leituras) if leituras else {}
    refinos = [
        {"escopo": leitura.escopo, "rotulo": leitura.rotulo,
         "quantidade": contagem_leituras.get(leitura.escopo, 0)}
        for leitura in leituras if contagem_leituras.get(leitura.escopo, 0)
    ]
    refino_atual = next((x for x in refinos if x["escopo"] == r.escopo), None)
    # "Atenção" (rascunhos que saem em até 7 dias; rascunhos vazios): um recorte por cima
    # das abas, com ficha própria. Urgentes vêm na ordem da saída — o mais perto primeiro.
    hoje = timezone.localdate()
    atencao = request.GET.get("atencao") or ""
    atencao = atencao if atencao in queries.ATENCOES else ""
    qs = r.qs.filter(queries.q_da_atencao(atencao, hoje)) if atencao else r.qs
    if atencao == "urgentes":
        qs = qs.order_by("_saida", "pk")  # type: ignore[misc]  # anotação de com_primeira_saida
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    pagina.object_list = list(pagina.object_list)  # avaliada uma vez: view e template
    # Urgentes vêm pela saída: os meses do cabeçalho também.
    por_saida = r.ordem in ("saida", "-saida") or atencao == "urgentes"
    totais = queries.totais_por_mes(queries.aplicar_recorte(r.filtrado, r.aba, r.documento)
                                    .filter(queries.q_da_atencao(atencao, hoje)),
                                    por_saida) if pagina.object_list else {}
    _grupos_por_mes(pagina.object_list, "saida" if por_saida else r.ordem, pagina, totais)
    agora = timezone.now()
    for o in pagina.object_list:
        o.linha = _situacao_da_linha(request.user, o, agora)  # type: ignore[attr-defined]
    contagens = queries.contagens_do_recorte(
        base, r.filtrado if (r.termo or r.avancados.validos) else None, r.aba, r.documento)
    get = request.GET
    filtros = get.copy()
    filtros.pop("pagina", None)
    fichas = _fichas(get, r, refino_atual)
    if atencao:
        fichas.insert(0, {"rotulo": queries.ATENCOES[atencao], "url": _sem(get, "atencao")})
    contexto = {
        "page_obj": pagina,
        "oficios": pagina.object_list,
        "contagens": contagens,
        # As abas trocam só a aba: tudo o mais que a pessoa filtrou continua valendo.
        "abas": [(chave, rotulo, f"aba-{chave or 'todos'}", _trocar(get, "aba", chave))
                 for chave, rotulo in recorte.ABAS],
        "documentos": [(chave, rotulo, f"doc-{chave or 'todos'}")
                       for chave, rotulo in recorte.DOCUMENTOS],
        "ordens": recorte.ORDENS,
        "aba": r.aba,
        "documento": r.documento,
        "termo": r.termo,
        "ordem": r.ordem,
        "escopo": r.escopo,
        "por_saida": por_saida,
        "atencao": atencao,
        "cartoes_atencao": _cartoes_de_atencao(request, atencao,
                                               queries.atencao_da_lista(base, hoje)),
        "tem_filtro": r.tem_filtro,
        # Outra tela mandou abrir a janela de um ofício (roteiros → "usado em…"): ela já
        # vai desenhada no HTML, para abrir pronta em vez de piscar o esqueleto.
        **_resumo_pedido(request),
        "refinos": refinos,
        "refino_atual": refino_atual,
        # Uma leitura só também aparece quando a busca ampla não achou nada ("1234" não é
        # protocolo para a busca ampla, que pede 5 dígitos, mas é "Protocolo com 1234").
        "mostrar_refino": not r.escopo and (len(refinos) > 1 or (
            bool(refinos) and not pagina.paginator.count)),
        "fichas": fichas,
        "filtros_na_gaveta": r.avancados.ativos + (r.ordem != recorte.ORDEM_PADRAO),
        # "Limpar" nunca apaga a busca nem a aba (F8); cada um diz o que tira.
        "url_limpar_tudo": _sem(get, so=("q", "aba")),
        "url_limpar_gaveta": _sem(get, "ordem", *FiltrosOficio.base_fields),
        "url_limpar_busca": _sem(get, "q", "escopo"),
        "url_ver_todos": reverse("viagens:oficios"),
        "querystring_base": (filtros.urlencode() + "&") if filtros else "",
        "querystring_refino": _sem(get, "escopo").partition("?")[2],
        "avancados": r.avancados,
        "pode_criar": policies.pode_criar(request.user),
        "pode_editar_oficios": policies.edita_oficios(request.user),
        "mais": _mais_da_lista(request),
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
    viajantes = viajantes_de(oficio)
    trechos = trechos_de(oficio)
    documentos = list(oficio.documentos.all())
    copia = (ProjecaoEprotocolo(
        dados=None, fonte="rascunho",
        aviso="Salve o rascunho antes de copiar os dados para o eProtocolo.")
        if (form is not None and form.is_bound) or calculo is not None
        else projetar_dados_eprotocolo(
            oficio, documentos=documentos, viajantes=viajantes, trechos=trechos))
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
        # Para onde o servidor recém-cadastrado vai: direto para a equipe deste ofício.
        "url_adicionar_viajante": reverse("viagens:adicionar_viajante", args=[oficio.pk]),
        # Pendências em vermelho só depois de salvar ou de pedir para emitir: abrir um
        # rascunho novo não é erro de ninguém.
        "mostrar_pendencias": bool(form is not None
                                   or request.GET.get("salvo") == "1"
                                   or request.GET.get("revisar")),
        "oficio": oficio,
        "form": form or FormularioOficio(instance=oficio),
        "secoes": secoes,
        **itin.contexto(),
        "trechos": trechos,
        "secoes_ok": sum(1 for sec in secoes if sec["ok"]),
        "recem_salvo": request.GET.get("salvo") == "1",
        "erro_roteiro": erro_roteiro,
        "viajantes": viajantes,
        "copia": copia,
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
        "documentos": documentos,
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
        if request.GET.get("cadastros") == "1":
            return render(request, "componentes/dialogos_cadastro.html", {
                "form_servidor": FormularioServidor(),
                "form_viatura": FormularioViatura(
                    fonte_motoristas=reverse("cadastros:buscar_servidores")),
                "envio_url": reverse("viagens:adicionar_viajante", args=[oficio.pk]),
                "alvo": "#equipe", "destino": "id_viatura",
            })
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
            trechos = None if vazio else itinerario.trechos(itin, lento=_lenta(form))
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
                try:
                    revisado = services.preparar_data_emissao(oficio)
                except services.RegraViolada as exc:
                    messages.error(request, str(exc))
                    return redirect(f"{reverse('viagens:editar', args=[oficio.pk])}#emissao")
                bloqueantes = services.verificar_prontidao(revisado).bloqueantes
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


@require_POST
def limpar_roteiro(request: HttpRequest, pk: int) -> HttpResponse:
    """"Limpar roteiro" da folha: apaga os trechos e o vínculo com o roteiro cadastrado."""
    oficio = _oficio_visivel(request, pk)
    if not policies.pode_editar(request.user, oficio):
        raise PermissionDenied
    try:
        services.limpar_roteiro(oficio, request.user)
    except (services.RegraViolada, services.ConflitoDeEdicao) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Roteiro limpo. Monte o percurso de novo ou aplique "
                                   "outro roteiro.")
    return redirect(f"{reverse('viagens:editar', args=[oficio.pk])}#roteiro")


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
    """Aplica um roteiro cadastrado: grava os trechos dele (sede inclusive), o vínculo e as
    diárias, preservando o que estiver válido no resto da folha."""
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
    # Escolher um roteiro cadastrado é decidir o percurso: grava na hora (trechos, vínculo e
    # diárias), junto com o que estiver válido no resto da folha. Não há o que "informar" depois.
    form = FormularioOficio(dados, instance=oficio)
    valido = form.is_valid()
    gravar = {k: v for k, v in form.cleaned_data.items() if k != "versao"} if valido else {}
    gravar.update(roteiro=roteiro, sede=roteiro.sede)
    informados = [services.TrechoInformado(t.origem_id, t.destino_id, t.saida_em, t.chegada_em)
                  for t in queries.trechos_do_roteiro(roteiro)]
    try:
        services.salvar_edicao(oficio, request.user, gravar, informados,
                               versao=form.cleaned_data.get("versao") if valido else None)
    except (services.ConflitoDeEdicao, services.RegraViolada) as exc:
        itin = itinerario.com_iniciais(FORM_ID, request.POST)
        contexto = _contexto_edicao(request, oficio, form, itin, str(exc))
        contexto.update(sujo=True, foco="alerta-roteiro")
        return render(request, "viagens/oficios/editar.html", contexto, status=422)
    messages.success(request, f"Roteiro #{roteiro.pk} aplicado: trechos e diárias gravados.")
    return redirect(f"{reverse('viagens:editar', args=[oficio.pk])}?salvo=1#roteiro")


# ------------------------------------------------------------------ equipe (HTMX)
def _secao_equipe(request, oficio, erro: str = "") -> HttpResponse:
    oficio.refresh_from_db()
    viajantes = viajantes_de(oficio)
    contexto = {
        "oficio": oficio, "erro_equipe": erro, "oob": True,
        "viajantes": viajantes,
        "prontidao": services.verificar_prontidao(oficio),
        # Mexer na equipe é uma gravação: daqui em diante a pendência pode falar.
        "mostrar_pendencias": True,
    }
    contexto["copia"] = projetar_dados_eprotocolo(
        oficio, documentos=(), viajantes=viajantes, trechos=trechos_de(oficio))
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

    Mostra a data efetiva e suas consequências, inclusive pendências que bloqueiam emitir.
    Reaproveita equipe, trechos e prontidão; só reavalia esta última quando a data muda.
    """
    if request.GET.get("revisar") != "1":
        return {}
    if not policies.pode_emitir(request.user, oficio):
        return {}
    data_anterior = oficio.data_oficio
    try:
        oficio = services.preparar_data_emissao(oficio)
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
        return {}
    return {"abrir_resumo": oficio.pk, "resumo": {
        "revisao": True, "oficio": oficio, "dados": dados_do_oficio(oficio),
        "pode_emitir": True, "assunto": services.assunto_do_oficio(oficio),
        "prazo": services.avaliar_prazo_do_oficio(oficio),
        "data_anterior": data_anterior, "data_atualizada": data_anterior != oficio.data_oficio,
        "calculo": oficio.diarias_calculo, "viajantes": folha["viajantes"],
        "trechos": folha["trechos"], "documentos": folha["documentos"],
        "prontidao": (folha["prontidao"] if data_anterior == oficio.data_oficio
                      else services.verificar_prontidao(oficio)),
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
                trechos = itinerario.trechos(itin, lento=_lenta(form))
            except services.RegraViolada:
                trechos = None
    try:
        salvo = services.salvar_edicao(oficio, request.user, dados, trechos,
                                       versao=form.cleaned_data.get("versao"),
                                       registrar=False)
    except (services.ConflitoDeEdicao, services.RegraViolada) as exc:
        return JsonResponse({"salvo": False, "motivo": str(exc), "mensagem": str(exc)})
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
def excluir_vazios(request: HttpRequest) -> HttpResponse:
    """"Excluir os rascunhos vazios" da faixa de atenção da lista (pede confirmação)."""
    if not policies.pode_listar(request.user):
        raise PermissionDenied
    excluidos = services.excluir_rascunhos_vazios(
        request.user, policies.oficios_visiveis(request.user))
    if excluidos:
        messages.success(request, f"{len(excluidos)} rascunho{'s' if len(excluidos) > 1 else ''} "
                                  f"vazio{'s' if len(excluidos) > 1 else ''} excluído"
                                  f"{'s' if len(excluidos) > 1 else ''} ({', '.join(excluidos)}); "
                                  "os números voltam a ficar disponíveis.")
    else:
        messages.info(request, "Nenhum rascunho vazio para excluir.")
    return redirect("viagens:oficios")


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


@require_GET
def acoes_oficio(request: HttpRequest, pk: int) -> HttpResponse:
    """Os itens do menu ⋮ de uma linha (D7), pedidos quando a pessoa chega ao botão: a
    lista não carrega 15 itens descritos por linha, e o menu sai com o estado de agora."""
    oficio = (queries.com_dados_de_lista(policies.oficios_visiveis(request.user).filter(pk=pk))
              .first())
    if oficio is None:
        raise Http404
    resposta = render(request, "viagens/oficios/_menu_oficio.html",
                      {"o": oficio, "m": policies.menu_do_oficio(request.user, oficio), "p": "m"})
    resposta["Cache-Control"] = "no-store"  # muda com a situação e com quem pede
    return resposta


_MARCA_NA_MENSAGEM = {("retificado", True): "marcado como retificado",
                      ("retificado", False): "deixou de ser retificado",
                      ("complementar", True): "marcado como complementar",
                      ("complementar", False): "deixou de ser complementar"}


@require_POST
def marcar(request: HttpRequest, pk: int) -> HttpResponse:
    """Liga/desliga Retificado ou Complementar de um rascunho pelo menu ⋮ (D7); a lista
    volta como estava."""
    oficio = _oficio_visivel(request, pk)
    marca = request.POST.get("marca", "")
    try:
        oficio = services.alternar_marcador(oficio, request.user, marca)
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
    else:
        texto = _MARCA_NA_MENSAGEM[(marca, oficio.marcador == marca)]
        messages.success(request, f"Ofício {oficio.numero_formatado} {texto}. O documento "
                                  "já sai assim na minuta.")
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
    from django.db.models import Exists

    from .documentos_versoes import projetar_documentos
    from .models import ViaAssinada

    documentos = list(oficio.documentos.select_related("emitido_por")
                      .annotate(_tem_vias=Exists(ViaAssinada.objects.filter(oficio=oficio)))
                      .order_by("tipo", "-versao"))
    viajantes = viajantes_de(oficio)
    trechos = trechos_de(oficio)
    # A existência vem na consulta documental: primeira emissão sem vias não paga uma
    # consulta vazia. Quando existem, trazer todas (inclusive revogadas) uma vez só.
    vias = list(oficio.vias_assinadas.select_related("enviado_por").order_by("enviado_em", "pk")) \
        if documentos and getattr(documentos[0], "_tem_vias", False) else []
    projecao = projetar_documentos(oficio, documentos=documentos, vias=vias)
    correntes: list[dict] = []
    historicos: list[dict] = []

    def linha_documental(versao):
        documento = projecao.documentos_por_id[versao.documento.id]
        return {"documento": documento,
                "pdf_disponivel": projecao.pdf_disponivel(documento.pk),
                "vias": [{"via": projecao.vias_por_id[via.id], "revogada": via.revogada}
                         for via in versao.vias if projecao.via_disponivel(via.id)]}

    for selecao in projecao.selecoes:
        if selecao.corrente is not None:
            correntes.append(linha_documental(selecao.corrente))
        historicos.extend(linha_documental(versao) for versao in selecao.historico)
    pdf = projecao.pdf_original("oficio")
    via_pdf = projecao.via_assinada("oficio")
    pdf_url = (reverse("viagens:abrir_via_assinada", args=[via_pdf.pk]) if via_pdf else
               reverse("viagens:baixar_documento", args=[pdf.pk]) if pdf else "")
    extras = {"revisao": True, "dados": dados_do_oficio(oficio),
              "pode_emitir": policies.pode_emitir(request.user, oficio)} if revisao else {}
    return {**extras,
        "oficio": oficio,
        "assunto": services.assunto_do_oficio(oficio),
        "prazo": services.avaliar_prazo_do_oficio(oficio),
        "calculo": oficio.diarias_calculo,
        "viajantes": viajantes,
        "trechos": trechos,
        "documentos": documentos,
        "projecao_documentos": projecao,
        "selecao_oficio": projecao.por_tipo("oficio"),
        "documentos_correntes": correntes,
        "documentos_historicos": historicos,
        "gerando": any(selecao.estado_geracao == Documento.Situacao.GERANDO
                       for selecao in projecao.selecoes),
        "pode_regenerar_documentos": policies.pode_regenerar_documentos(request.user, oficio),
        "prontidao": services.verificar_prontidao(oficio) if oficio.editavel else None,
        "pode_editar": policies.pode_editar(request.user, oficio),
        "pode_retificar": policies.pode_retificar(request.user, oficio),
        # Os registros que nasceram do ofício e que quem pede vê — só quando existem (o link
        # levava a uma lista vazia; QA Lote 3, M5). Uma consulta para os três.
        **_registros_do_oficio(request, oficio),
        # PDF original corrente: identidade máxima pronta com caminho preenchido.
        "pdf_oficio": pdf,
        "pdf_oficio_url": pdf_url,
        "docx_oficio": projecao.docx_corrente("oficio"),
        "vias": _vias_do_oficio(request, oficio, projecao),
        "menu": policies.menu_do_oficio(request.user, oficio, projecao=projecao),
    }


def _registros_do_oficio(request: HttpRequest, oficio) -> dict:
    """Termos, OS e planos deste ofício que o usuário vê: os cartões do bloco de vínculos do
    resumo e, para o menu ("Termos deste ofício"…), se existem."""
    from . import resumo_listas

    vinculos = resumo_listas.vinculos_do_oficio(request.user, oficio)
    tipos = {c["tipo"] for c in vinculos}
    return {"vinculos": vinculos, "termos_do_oficio": "termo" in tipos,
            "ordens_do_oficio": "ordem" in tipos, "planos_do_oficio": "plano" in tipos}


def _vias_do_oficio(request: HttpRequest, oficio, projecao) -> list[dict]:
    """Cartões somente das identidades correntes prontas com arquivo disponível."""
    from . import assinados, views_assinados

    # O resumo é um fragmento: remover volta para a lista com o resumo aberto.
    voltar = f"{reverse('viagens:oficios')}?resumo={oficio.pk}"
    cartoes = []
    for tipo in ("oficio", "justificativa"):
        documento = projecao.pdf_original(tipo)
        via = projecao.via_assinada(tipo)
        if documento is None and via is None:
            continue
        selecao = projecao.por_tipo(tipo)
        if selecao is None or selecao.corrente is None:
            continue
        versao = selecao.corrente.documento.versao
        cartoes.append(views_assinados.cartao(
            request, assinados.Alvo(tipo, oficio), via,
            titulo=(f"Ofício {oficio.numero_formatado} · v{versao}" if tipo == "oficio"
                    else f"Justificativa do Ofício {oficio.numero_formatado} · v{versao}"),
            original_url=reverse("viagens:baixar_documento", args=[documento.pk])
            if documento else "", voltar=voltar))
    return cartoes


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
        "pode_regenerar_documentos": policies.pode_regenerar_documentos(request.user, oficio),
        "gerando": any(d.situacao == Documento.Situacao.GERANDO for d in documentos)})


@require_POST
def regenerar_documento(request: HttpRequest, documento_id: int) -> HttpResponse:
    doc = get_object_or_404(Documento.objects.select_related("oficio"), pk=documento_id)
    if not policies.pode_ver(request.user, doc.oficio):
        raise Http404
    try:
        services.regenerar_documento(doc, request.user)
    except services.RegraViolada as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Geração solicitada. O documento aparece aqui quando "
                                  "estiver pronto.")
    return redirect(f"{reverse('viagens:oficios')}?resumo={doc.oficio_id}")


@require_GET
def baixar_documento(request: HttpRequest, documento_id: int) -> FileResponse:
    doc = get_object_or_404(Documento.objects.select_related("oficio"), pk=documento_id)
    if not policies.pode_ver(request.user, doc.oficio):
        raise Http404
    if doc.situacao != Documento.Situacao.PRONTO:
        raise Http404("Documento ainda não gerado.")
    if request.GET.get("versao") != "original":
        via = doc.vias_assinadas.filter(
            oficio_id=doc.oficio_id, tipo=doc.tipo, revogada_em__isnull=True,
        ).select_related("oficio").order_by("-enviado_em").first()
        from . import assinados

        if (via is not None and str(via.arquivo.name or "").strip()
                and assinados.pode_abrir(request.user, via)):
            from .views_assinados import resposta_da_via
            return resposta_da_via(via, baixar=request.GET.get("baixar") == "1")
    if not str(doc.arquivo.name or "").strip():
        raise Http404("O arquivo deste documento está indisponível.")
    try:
        arquivo = doc.arquivo.open("rb")
    except FileNotFoundError:
        raise Http404("O arquivo deste documento está indisponível.") from None
    resposta = FileResponse(arquivo, content_type="application/pdf",
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
    if request.GET.get("emissao") == "1" and oficio.editavel:
        try:
            oficio = services.preparar_data_emissao(oficio)
        except services.RegraViolada as exc:
            return HttpResponse(str(exc), status=422, content_type="text/plain; charset=utf-8")
    tipo = request.GET.get("tipo", "oficio")
    if tipo not in {"oficio", "justificativa", "todos"}:
        raise Http404
    dados = dados_do_oficio(oficio)
    from weasyprint import HTML

    # O texto editado vai junto: a minuta é a mesma folha do editor, em PDF (ADR 0018).
    # Sem `regioes`, `html_do_documento` cairia no modelo puro — e o botão "PDF" da barra
    # mostrava um documento diferente do que estava escrito ao lado, no modo "Texto".
    # "todos": o ofício e a justificativa num PDF só (o modo PDF do bloco de documentos).
    tipos = ["oficio", "justificativa"] if tipo == "todos" else [tipo]
    folhas = [HTML(string=html_do_documento(t, dados, previa=True,
                                            regioes=services.regioes_vigentes(oficio, t)),
                   base_url=str(ASSETS), url_fetcher=buscar_recurso()).render()
              for t in tipos]
    pdf = folhas[0].copy([pagina for f in folhas for pagina in f.pages]).write_pdf()
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
    from .documentos_versoes import projetar_documentos

    rascunho = oficio.situacao == Oficio.Situacao.RASCUNHO
    emitido = None
    if not rascunho:
        projecao = projetar_documentos(oficio, documentos=list(oficio.documentos.all()), vias=())
        emitido = projecao.docx_corrente(tipo)
        selecao = projecao.por_tipo(tipo)
        if oficio.situacao == Oficio.Situacao.CANCELADO and selecao is not None:
            # Leitura histórica já autorizada pela rota: não chama isso de corrente.
            ultima = selecao.ultima_emissao
            if ultima is not None and ultima.situacao == Documento.Situacao.PRONTO:
                emitido = projecao.documentos_por_id[ultima.id]
        if emitido is None:
            return HttpResponse(
                "O DOCX desta versão está indisponível. Confira os documentos do ofício; "
                "se a geração falhou, solicite gerar novamente.",
                status=422, content_type="text/plain; charset=utf-8")
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



def _lenta(form) -> bool:
    """A viatura escolhida no ofício é unidade móvel pesada (trechos mais demorados)."""
    return bool(getattr((getattr(form, "cleaned_data", None) or {}).get("viatura"), "lenta",
                        False))


# ------------------------------------------------------------------ rota (mapa do itinerário)
@require_GET
def rota(request: HttpRequest) -> JsonResponse:
    """Pernas da rota entre as paradas informadas (?p=Cidade/UF&p=...): km, tempo de estrada,
    tempo adicional sugerido e traçado para o mapa. Paradas inválidas voltam com erro."""
    if not (request.user.has_perm("viagens.view_oficio")
            or request.user.has_perm("viagens.view_roteiro")):
        raise PermissionDenied
    textos = [t.strip() for t in request.GET.getlist("p")][:12]
    lento = request.GET.get("lento") == "1"  # viatura unidade móvel pesada
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
        p = rotas.calcular(a, b, lento=lento)
        pernas.append({"km": float(p.km), "minutos": p.minutos,
                       "adicional_sugerido": p.adicional_sugerido, "fonte": p.fonte,
                       "tracado": p.tracado})
    validas = [p for p in pernas if p]
    return JsonResponse({
        "pontos": pontos, "pernas": pernas,
        "total": {"km": round(sum(p["km"] for p in validas), 1),
                  "minutos": sum(p["minutos"] for p in validas)},
    })


# ------------------------------------------------------------------ justificativas (D6)
def _lista_justificativas(request: HttpRequest, *, form=None, editando=None, status=200):
    policies.exigir(policies.pode_listar(request.user))
    base = policies.oficios_visiveis(request.user)
    contagens = queries.contagens_justificativas(base)
    filtros_atuais = (QueryDict(request.POST.get("voltar", ""))
                      if request.method == "POST" else request.GET)
    aba = filtros_atuais.get("aba") or request.POST.get("aba") or ""
    if not aba and contagens["pendentes"]:
        aba = "pendentes"  # a tela existe para zerar as pendentes: abre nelas
    if aba not in queries.ABAS_JUSTIFICATIVAS:
        aba = ""
    termo = (filtros_atuais.get("q") or "").strip()
    qs = queries.justificativas(base, aba)
    if termo:
        achados = services.buscar_por_texto(base, termo).values("pk")
        qs = qs.filter(Q(pk__in=achados) | Q(justificativa__unaccent__icontains=termo))
    qs = (queries.com_dados_de_lista(qs).select_related("justificativa_modelo")
          .prefetch_related(Prefetch("documentos", to_attr="docs_justificativa",
                                     queryset=Documento.objects.filter(
                                         tipo=Documento.Tipo.JUSTIFICATIVA).order_by("-versao")))
          # Pendentes pela saída mais próxima (urgência); as demais, pelo número.
          .order_by(*((F("saida_dia").asc(nulls_last=True), "-ano", "-numero")
                      if aba == "pendentes" else ("-ano", "-numero"))))
    pagina = Paginator(qs, POR_PAGINA).get_page(filtros_atuais.get("pagina"))
    pagina.object_list = list(pagina.object_list)
    for o in pagina.object_list:  # o que cada linha oferece vem da política
        corrente = queries.pdf_corrente_da_lista(o, "justificativa")
        o.docs_justificativa = [  # type: ignore[attr-defined]
            d for d in o.docs_justificativa if corrente and d.pk == corrente[0]]  # type: ignore[attr-defined]
        o.editavel_aqui = policies.pode_editar(request.user, o)  # type: ignore[attr-defined]
        saida_dia = getattr(o, "saida_dia", None)  # anotado por queries.com_regra_de_prazo
        o.antecedencia = (  # type: ignore[attr-defined]
            (saida_dia - o.data_oficio).days if saida_dia else None)
        trechos = trechos_de(o)  # urgência (sem justificativa, sai em até 7 dias) e estrada
        o.tempo = linha_lista.estado_temporal(  # type: ignore[attr-defined]
            trechos[0].saida_em if trechos and o.situacao != Oficio.Situacao.CANCELADO
            else None, trechos[-1].chegada_em if trechos else None, timezone.now(),
            pendente=not o.justificativa.strip())
    if form is None and (pk := request.GET.get("editar", "")).isdigit():
        editando = _oficio_visivel(request, int(pk))
        if policies.pode_editar(request.user, editando):
            form = FormularioJustificativa(initial={
                "justificativa": editando.justificativa, "versao": editando.versao,
                "justificativa_modelo": editando.justificativa_modelo_id})
        else:
            editando = None
    filtros = filtros_atuais.copy()
    for chave in ("pagina", "editar"):
        filtros.pop(chave, None)
    return render(request, "viagens/justificativas/lista.html", {
        "page_obj": pagina, "oficios": pagina.object_list, "aba": aba, "termo": termo,
        "abas": [("", "Todas", "todas")] + [(k, r, k) for k, r in
                                             queries.ABAS_JUSTIFICATIVAS.items()],
        "contagens": contagens,
        "querystring_base": (filtros.urlencode() + "&") if filtros else "",
        "form": form, "editando": editando, "lista_url": reverse("viagens:justificativas"),
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
