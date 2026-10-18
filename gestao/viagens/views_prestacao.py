"""Prestação de contas (módulo 9a), organizada como a gestão de viagens: a lista (uma linha
por ofício/equipe, com o que falta) e a folha da equipe (etapas, um cartão por servidor, as
folhas da equipe e a conferência). A solicitação de cada cartão grava sozinha (como a
referência); arquivar/finalizar (servidor e equipe), envio ao financeiro e a planilha.
Regra em `prestacao.py`; ficha em docs/migration/prestacao.md."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from . import (
    anexos,
    assinados,
    carimbo,
    comunicacoes,
    exportacao,
    leitura_anexos,
    pacote_prestacao,
    policies,
    prestacao,
    prestacao_equipe,
)
from .diario import equipe_finalizada
from .dominio.prestacao import prazo_para_prestar
from .models import AnexoPrestacao, PrestacaoContas, PrestacaoServidor, Trecho, ViaAssinada
from .viagem import periodo_curto
from .views import _migalhas

POR_PAGINA = 25  # ofícios por página (referência)
ATENCAO = prestacao.PENDENCIAS
NUMERO_OFICIO = re.compile(r"^\s*(\d{1,5})\s*/\s*(\d{4})\s*$")
VAZIOS = {
    "nao_liberadas": "Nenhum servidor com diárias pendentes de liberação.",
    "liberadas": "Nenhum servidor com diárias já liberadas.",
    "devolvidas": "Nenhuma prestação devolvida para correção.",
    "arquivados": "Nenhuma prestação de servidor arquivada.",
    "finalizados": "Nenhuma equipe com todas as prestações finalizadas.",
    "saque_vencendo": "Nenhum saque perto do prazo sem comprovante.",
    "prestacao_vencida": "Nenhuma prestação com o prazo vencido.",
    "sem_solicitacao": "Nenhuma prestação em aberto sem número de solicitação.",
    "sem_despacho": "Nenhuma prestação em aberto sem o despacho assinado.",
    "sem_comprovante": "Nenhuma prestação em aberto sem comprovante.",
    "comprovante_diferente": "Nenhum comprovante com valor diferente da diária.",
    "finalizadas_mes": "Nenhuma prestação finalizada neste mês.",
}
ROTULOS = {"arquivar": "arquivada", "desarquivar": "desarquivada", "finalizar": "finalizada",
           "reabrir": "reaberta"}
ROTULOS_EQUIPE = {"arquivar": "arquivadas", "desarquivar": "desarquivadas",
                  "finalizar": "finalizadas", "reabrir": "reabertas"}


def _data(texto: str, rotulo: str = "Data") -> date | None:
    texto = (texto or "").strip()
    if not texto:
        return None
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise prestacao.PrestacaoInvalida(f"{rotulo} inválida: {texto}. Use dd/mm/aaaa.")


def _voltar(request: HttpRequest, ancora: str = "") -> str:
    voltar = (request.POST.get("voltar") or "").split("#")[0]
    if not (voltar.startswith("/") and not voltar.startswith("//")
            and url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()})):
        voltar = reverse("viagens:prestacoes")
    return f"{voltar}#{ancora}" if ancora else voltar


def _buscar(qs, termo: str):
    if not termo:
        return qs
    filtro = (Q(servidor__nome__unaccent__icontains=termo)
              | Q(numero_solicitacao__icontains=termo)
              | Q(prestacao__oficio__protocolo__icontains=re.sub(r"\D", "", termo) or termo))
    if (m := NUMERO_OFICIO.match(termo)):
        filtro |= Q(prestacao__oficio__numero=int(m.group(1)),
                    prestacao__oficio__ano=int(m.group(2)))
    return qs.filter(filtro)


def _linhas(request: HttpRequest):
    base = policies.prestacoes_visiveis(request.user).select_related(
        "servidor", "prestacao__oficio")
    abas = [a for a in request.GET.getlist("aba") if a in dict(prestacao.ABAS)]
    busca = (request.GET.get("q") or "").strip()
    buscadas = _buscar(base, busca)
    qs = buscadas
    if abas:
        ids: set[int] = set()
        for aba in abas:
            ids.update(prestacao.filtrar(buscadas, aba).values_list("pk", flat=True))
        qs = buscadas.filter(pk__in=ids)
    return buscadas, qs, abas, busca


@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    policies.exigir(policies.pode_listar_prestacoes(request.user))
    buscadas, qs, abas, busca = _linhas(request)
    contagens = {"todas": buscadas.count(),
                 **{a: prestacao.filtrar(buscadas, a).count() for a, _ in prestacao.ABAS}}
    # A paginação é por ofício: a equipe não se parte entre páginas (referência).
    ids = qs.select_related(None).values("prestacao_id")
    prestacoes = (PrestacaoContas.objects.filter(pk__in=ids)
                  .select_related("oficio__unidade")
                  .prefetch_related(Prefetch("oficio__trechos", queryset=Trecho.objects
                                             .select_related("destino").order_by("ordem")))
                  .annotate(equipe=Count("oficio__viajantes", distinct=True))
                  .order_by("-oficio__ano", "-oficio__numero"))
    pagina = Paginator(prestacoes, POR_PAGINA).get_page(request.GET.get("pagina"))
    da_pagina = {p.pk: p for p in pagina.object_list}
    por_prestacao: dict[int, list] = {}
    equipes: dict[int, list] = {}
    hoje = timezone.localdate()
    situacao = anexos.situacao(da_pagina)
    # Uma consulta por página: estado da equipe inteira, linhas apenas do recorte.
    consulta_membros = (PrestacaoServidor.objects.filter(prestacao__in=list(da_pagina),
                                                         removida_em__isnull=True)
                        .select_related("servidor")
                        .annotate(no_recorte=Exists(qs.filter(pk=OuterRef("pk"))))
                        .order_by("servidor__nome"))
    motoristas = _motoristas(list(da_pagina))
    membros = list(consulta_membros)
    avisos = comunicacoes.situacoes([ps.pk for ps in membros])
    for ps in membros:
        ps.prestacao = da_pagina[ps.prestacao_id]
        linha = _linha(request, ps, hoje, situacao, motoristas.get(ps.prestacao_id),
                       avisos.get(ps.pk))
        equipes.setdefault(ps.prestacao_id, []).append(linha)
        if ps.no_recorte:
            por_prestacao.setdefault(ps.prestacao_id, []).append(linha)
    blocos = [_bloco(request, p, por_prestacao.get(p.pk, []), equipes.get(p.pk, []))
              for p in pagina.object_list]
    filtros = request.GET.copy()
    filtros.pop("pagina", None)
    return render(request, "viagens/prestacao/lista.html", {
        "page_obj": pagina, "blocos": blocos, "aba": abas[0] if len(abas) == 1 else "",
        "abas_selecionadas": abas,
        "abas_situacao": [(c, r) for c, r in prestacao.ABAS if c not in ATENCAO],
        "abas_atencao": [(c, r) for c, r in prestacao.ABAS if c in ATENCAO],
        "contagens": contagens, "busca": busca, "total_servidores": qs.count(),
        "acoes_equipe": list(ROTULOS),
        "vazio": VAZIOS.get(abas[0], "Nenhuma prestação encontrada.") if len(abas) == 1
        else "Nenhuma prestação encontrada.",
        "querystring_base": (filtros.urlencode() + "&") if filtros else "",
        "migalhas": _migalhas(("Prestação de contas", ""))})


def _feitos(ps: PrestacaoServidor, s: anexos.Situacao) -> dict:
    """O que já foi feito, como a linha mostra: ✓ com o assinado anexado, "gerado" quando
    preenchido e o assinado ainda não voltou (nunca só por existir a linha)."""
    p = ps.prestacao_id
    valores = [v for v in s.comprovantes.get(ps.pk, []) if v]
    return {
        "diario": "assinado" if p in s.db_assinados else "gerado" if p in s.diarios else "",
        "rt": "assinado" if ps.pk in s.rt_assinados else "gerado" if p in s.relatorios else "",
        "comprovante": ps.pk in s.comprovantes,
        "comprovante_valor": sum(valores) if valores else None,
        "despacho": p in s.despachos,
    }


def _whatsapp(ps: PrestacaoServidor, diaria) -> str:
    """Conferência agrupada no modo manual; aviso legado nos outros transportes."""
    from . import envios_manuais
    if envios_manuais.manual():
        return reverse("viagens:envio_manual", args=[ps.pk])
    from urllib.parse import quote
    telefone = re.sub(r"\D", "", ps.servidor.telefone or "")
    if not telefone or not ps.data_liberacao_diarias:
        return ""
    from .dominio.relatorio import moeda
    o = ps.prestacao.oficio
    prazo = (f"; o prazo para saque é {ps.prazo_limite_saque:%d/%m/%Y}"
             if ps.prazo_limite_saque else "")
    texto = (f"Olá, {ps.servidor.nome.split()[0]}. As diárias do Ofício {o.numero_formatado}"
             f"{f' ({moeda(diaria)})' if diaria else ''} foram liberadas em "
             f"{ps.data_liberacao_diarias:%d/%m/%Y}"
             f"{prazo}."
             f" Depois do saque, envie o comprovante para a prestação de contas.")
    return f"https://wa.me/55{telefone}?text={quote(texto)}"


def _situacao_texto(ps: PrestacaoServidor, feitos: dict) -> tuple[str, str]:
    """O selo da situação (texto, tom): enviada/aprovada/devolvida contam mais que
    finalizada; em aberto, "Em preenchimento" quando já há algo e "Pendente" quando nada."""
    if ps.situacao == "enviada":
        return "Enviada", "info"
    if ps.situacao == "aprovada":
        return "Aprovada", "sucesso"
    if ps.situacao == "devolvida":
        return "Devolvida", "perigo"
    if ps.finalizada:
        return "Finalizada", "sucesso"
    comecou = (ps.numero_solicitacao.strip() or ps.data_liberacao_diarias or feitos["diario"]
               or feitos["rt"] or feitos["comprovante"] or feitos["despacho"])
    return ("Em preenchimento", "info") if comecou else ("Pendente", "aviso")


def _linha(request: HttpRequest, ps: PrestacaoServidor, hoje: date,
           situacao: anexos.Situacao, motoristas: set[int] | None = None,
           aviso_automatico: tuple[int, str] | None = None) -> dict:
    selos = prestacao.selos(ps, hoje, tem_comprovante=bool(situacao.comprovantes.get(ps.pk)))
    pendencias = prestacao.pendencias(ps, situacao)
    diaria = prestacao.diaria_liberada(ps, getattr(ps.prestacao, "equipe", None))
    p = ps.prestacao
    feitos = _feitos(ps, situacao)
    return {"ps": ps, "selos": selos, "pendencias": pendencias,
            "situacao": _situacao_texto(ps, feitos),
            "pendencias_links": [prestacao_equipe.Pendencia(t, prestacao_equipe.destino(p, ps, t))
                                 for t in pendencias],
            "url_pendencias": f"{reverse('viagens:prestacao_equipe', args=[p.pk])}#ps-{ps.pk}",
            "diaria": diaria, "prestar_ate": prazo_para_prestar(ps.prazo_limite_saque),
            "feitos": feitos,
            "motorista": ps.servidor_id in (motoristas or set()),
            "whatsapp": _whatsapp(ps, diaria),
            "whatsapp_automatico": aviso_automatico,
            "editavel": policies.pode_editar_prestacao(request.user, ps)}


def _motoristas(prestacao_ids: list[int]) -> dict[int, set[int]]:
    """{prestação: {servidores que dirigem no ofício}} — o crachá com o volante."""
    from .models import Viajante
    saida: dict[int, set[int]] = {}
    for prestacao_id, servidor_id in (Viajante.objects
                                      .filter(oficio__prestacao__in=prestacao_ids, motorista=True)
                                      .values_list("oficio__prestacao", "servidor_id")):
        saida.setdefault(prestacao_id, set()).add(servidor_id)
    return saida


def _bloco(request: HttpRequest, p: PrestacaoContas, linhas: list, equipe: list) -> dict:
    trechos = list(p.oficio.trechos.all())
    destinos = list(dict.fromkeys(str(t.destino) for t in trechos))
    periodo = (periodo_curto(timezone.localtime(trechos[0].saida_em).date(),
                             timezone.localtime(trechos[-1].chegada_em).date())
               if trechos else "")
    abertas = [linha for linha in equipe if not linha["ps"].finalizada]
    por_enviar = [linha for linha in equipe if linha["ps"].finalizada
                  and linha["ps"].situacao not in ("enviada", "aprovada")]
    # A linha da lista: o que falta (com o nome de quem), o prazo mais perto e o selo mais
    # urgente da equipe — como a linha da viagem.
    pendencias = [prestacao_equipe.Pendencia(f"{linha['ps'].servidor.nome}: {t}",
                                             prestacao_equipe.destino(p, linha["ps"], t))
                  for linha in abertas for t in linha.get("pendencias", [])]
    prazos = [linha["prestar_ate"] for linha in abertas if linha.get("prestar_ate")]
    selos = [s for linha in abertas for s in linha.get("selos", [])]
    ordem = {"vencido": 0, "alerta": 1}
    return {"p": p, "linhas": linhas, "destinos": ", ".join(destinos), "periodo": periodo,
            "editavel": policies.pode_editar_equipe_prestacao(request.user, p),
            "todas_finalizadas": bool(equipe) and not abertas,
            "reabrivel": bool(por_enviar), "por_enviar": por_enviar,
            "alguma_arquivada": any(linha["ps"].arquivada for linha in equipe),
            "total": len(equipe), "finalizadas": len(equipe) - len(abertas),
            "devolvidas": sum(1 for linha in equipe if linha["ps"].situacao == "devolvida"),
            "enviadas": sum(1 for linha in equipe
                            if linha["ps"].situacao in ("enviada", "aprovada")),
            "pendencias": pendencias, "prestar_ate": min(prazos) if prazos else None,
            "selo": min(selos, key=lambda s: ordem.get(s.tom, 2)) if selos else None,
            "trechos": len(trechos), "url": reverse("viagens:prestacao_equipe", args=[p.pk]),
            "por_servidor": (equipe[0]["diaria"] if equipe else None),
            # Para os avatares da linha (componentes/avatares_mini.html): o motorista primeiro.
            "pessoas": sorted(({"servidor": linha["ps"].servidor, "motorista": linha["motorista"]}
                               for linha in equipe), key=lambda x: not x["motorista"]),
            "quantidade_diarias": (p.oficio.diarias_calculo or {}).get("resumo", "")}


@require_GET
def equipe(request: HttpRequest, pk: int) -> HttpResponse:
    """A visão da equipe: etapas, servidores (as mesmas linhas da lista), as folhas da equipe
    e a conferência. Nada é criado ao abrir."""
    p = get_object_or_404(
        PrestacaoContas.objects.select_related("oficio__unidade").prefetch_related(
            Prefetch("oficio__trechos", queryset=Trecho.objects.select_related("destino")
                     .order_by("ordem")))
        .annotate(equipe=Count("oficio__viajantes", distinct=True)), pk=pk)
    if not policies.pode_ver_equipe_prestacao(request.user, p):
        raise Http404
    contexto = contexto_folha(request, p, "")
    linhas = contexto["equipe_linhas"]
    situacao = anexos.situacao([p.pk])
    membros = [linha["ps"] for linha in linhas]
    folhas = prestacao_equipe.folhas(p, membros, situacao, contexto["b"]["trechos"])
    o = p.oficio
    return render(request, "viagens/prestacao/equipe.html", {
        **contexto, "linhas": linhas, "folhas": folhas,
        "etapas": prestacao_equipe.etapas(membros, folhas),
        "conferencia": prestacao_equipe.conferencia(p, linhas),
        "folhas_feitas": sum(1 for f in folhas if f.feito),
        "acoes_equipe": list(ROTULOS),
        "migalhas": _migalhas(("Prestação de contas", reverse("viagens:prestacoes")),
                              (f"Ofício {o.numero_formatado}", ""))})


def _ps(request: HttpRequest, pk: int) -> PrestacaoServidor:
    ps = get_object_or_404(PrestacaoServidor.objects.select_related(
        "servidor", "prestacao__oficio"), pk=pk)
    if not policies.pode_ver_prestacao(request.user, ps):
        raise Http404
    return ps


def _gravar_cartao(request: HttpRequest, ps: PrestacaoServidor) -> None:
    """Os campos do cartão, quando vieram (o cartão aberto manda os três)."""
    if "numero" not in request.POST or ps.finalizada:
        return
    prestacao.salvar_solicitacao(
        request.user, ps.pk, numero=request.POST.get("numero", ""),
        liberacao=_data(request.POST.get("liberacao", ""), "Data de liberação"),
        prazo=_data(request.POST.get("prazo", ""), "Prazo de saque"))


@require_POST
def salvar(request: HttpRequest, pk: int) -> HttpResponse:
    """Sem JavaScript (ou Enter num campo): grava o cartão e volta para ele."""
    ps = _ps(request, pk)
    try:
        _gravar_cartao(request, ps)
    except (prestacao.PrestacaoInvalida, PermissionDenied) as exc:
        messages.error(request, f"{ps.servidor.nome}: {exc}")
    else:
        messages.success(request, f"Solicitação de {ps.servidor.nome} salva.")
    return redirect(_voltar(request, f"ps-{ps.pk}"))


@require_POST
def autosave(request: HttpRequest, pk: int) -> JsonResponse:
    """Contrato do autosave.js: {"salvo", "em", "campos", "recarregar", "mensagem"}."""
    ps = _ps(request, pk)
    try:
        _gravar_cartao(request, ps)
    except (prestacao.PrestacaoInvalida, PermissionDenied) as exc:
        return JsonResponse({"salvo": False, "mensagem": str(exc)})
    return JsonResponse({"salvo": True, "em": f"{timezone.localtime():%H:%M}", "campos": {},
                         "recarregar": False})


@require_POST
def acao_servidor(request: HttpRequest, pk: int, acao: str) -> HttpResponse:
    ps = _ps(request, pk)
    if acao not in {*ROTULOS, "enviar", "aprovar", "devolver"}:
        raise Http404
    ancora = f"ps-{ps.pk}"
    try:
        # O que está digitado no cartão vale antes da ação (nada se perde ao clicar).
        _gravar_cartao(request, ps)
        if acao == "arquivar":
            prestacao.arquivar(request.user, ps.pk, True)
        elif acao == "desarquivar":
            prestacao.arquivar(request.user, ps.pk, False)
        elif acao == "finalizar":
            prestacao.finalizar(request.user, ps.pk, request.POST.get("justificativa", ""))
        elif acao == "reabrir":
            prestacao.reabrir(request.user, ps.pk)
        elif acao == "enviar":
            n = prestacao.enviar(request.user, ps.pk, enviada_em=_data(
                request.POST.get("enviada_em", ""), "Data do envio"),
                protocolo=request.POST.get("protocolo", ""),
                equipe=request.POST.get("equipe") == "1")
            plural = "servidor" if n == 1 else "servidores"
            messages.success(request, f"Envio registrado para {n} {plural}.")
            return redirect(_voltar(request, ancora))
        elif acao == "aprovar":
            prestacao.aprovar(request.user, ps.pk)
            messages.success(request, f"Prestação de {ps.servidor.nome} aprovada.")
            return redirect(_voltar(request, ancora))
        else:
            prestacao.devolver(request.user, ps.pk, request.POST.get("motivo", ""))
            messages.success(request, f"Prestação de {ps.servidor.nome} devolvida e reaberta "
                                      "para correção.")
            return redirect(_voltar(request, ancora))
    except (prestacao.PrestacaoInvalida, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Prestação de {ps.servidor.nome} {ROTULOS[acao]}.")
    return redirect(_voltar(request, ancora))


@require_POST
def acao_equipe(request: HttpRequest, pk: int, acao: str) -> HttpResponse:
    p = get_object_or_404(PrestacaoContas.objects.select_related("oficio"), pk=pk)
    if not policies.pode_ver_equipe_prestacao(request.user, p):
        raise Http404
    if acao not in ROTULOS:
        raise Http404
    ancora = f"equipe-{p.pk}"
    try:
        r = prestacao.acao_da_equipe(request.user, p.pk, acao)
    except PermissionDenied as exc:
        messages.error(request, str(exc))
        return redirect(_voltar(request, ancora))
    if r.pulados:
        nomes = (" e ".join([", ".join(r.pulados[:-1]), r.pulados[-1]])
                 if len(r.pulados) > 1 else r.pulados[0])
        quem = "ainda tem" if len(r.pulados) == 1 else "ainda têm"
        inicio = "Ficaram de fora" if r.feitos else "Ninguém foi finalizado"
        messages.warning(request, f"{inicio}: {nomes} {quem} pendência (veja “Falta para "
                                  "finalizar” no cartão).")
    if r.feitos:
        plural = "servidor" if r.feitos == 1 else "servidores"
        messages.success(request, f"Prestações {ROTULOS_EQUIPE[acao]}: {r.feitos} {plural}.")
    elif not r.pulados:
        messages.info(request, "Nada a fazer: a equipe já estava assim.")
    return redirect(_voltar(request, ancora))


@require_GET
def exportar(request: HttpRequest) -> HttpResponse:
    policies.exigir(policies.pode_listar_prestacoes(request.user))
    _, qs, _, _ = _linhas(request)
    conteudo = exportacao.planilha_de_prestacoes(
        qs.select_related("servidor", "prestacao__oficio").order_by(
            "-prestacao__oficio__ano", "-prestacao__oficio__numero", "servidor__nome"))
    resposta = HttpResponse(conteudo, content_type=(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
    resposta["Content-Disposition"] = (
        f'attachment; filename="prestacoes_{timezone.localdate():%Y-%m-%d}.xlsx"')
    return resposta


@require_GET
def leitura(request: HttpRequest, pk: int) -> HttpResponse:
    """Leitura e conferência (etapa 3): o ofício assinado com a posição do nº da solicitação
    de cada servidor e o despacho; o texto dos comprovantes, do RT e do diário assinados em
    campos para copiar, com autorização, data e valor conferidos com a diária do ofício e a
    do RT; remover um anexo e trazer de volta uma versão anterior. Os arquivos chegam pelo
    importador. Nada é gravado ao abrir."""
    p = get_object_or_404(PrestacaoContas.objects.select_related("oficio__unidade"), pk=pk)
    if not policies.pode_ver_equipe_prestacao(request.user, p):
        raise Http404
    membros = list(PrestacaoServidor.objects.filter(prestacao=p, removida_em__isnull=True)
                   .select_related("servidor").order_by("servidor__nome"))
    for ps in membros:
        ps.prestacao = p
    todos = list(anexos.ativos(AnexoPrestacao.objects.filter(prestacao=p))
                 .select_related("servidor__servidor").order_by("servidor__servidor__nome",
                                                               "data_operacao", "pk"))
    tipos = AnexoPrestacao.Tipo
    pode = policies.pode_editar_equipe_prestacao(request.user, p)
    o = p.oficio
    via = assinados.vigente(assinados.Alvo(ViaAssinada.Tipo.OFICIO, o))
    carimbos = {c.servidor_id: c for c in carimbo.carimbos(via)} if via else {}
    db_anexo = next((a for a in todos if a.tipo == tipos.DB_ASSINADO), None)
    diario = leitura_anexos.ler(db_anexo) if db_anexo else None
    servidores: list[dict[str, Any]] = []
    lidos = 0
    for ps in membros:
        liberada = prestacao.diaria_liberada(ps)
        rt_anexo = next((a for a in todos if a.servidor_id == ps.pk
                         and a.tipo == tipos.RT_ASSINADO), None)
        rt = leitura_anexos.ler(rt_anexo) if rt_anexo else None
        # A diária do RT: a que está escrita no RT assinado; sem ela, a do RT gerado.
        diaria_rt = ps.diaria_valor_override or liberada
        if rt and rt.legivel:
            escrita = next((c.valor for c in rt.campos if c.rotulo == "Diária"), "")
            lida = leitura_anexos.ler_comprovante(escrita)["valor"] if escrita else None
            diaria_rt = lida or diaria_rt
        comprovantes = [a for a in todos if a.servidor_id == ps.pk
                        and a.tipo == tipos.COMPROVANTE]
        soma = sum((a.valor for a in comprovantes if a.valor), Decimal("0")) or None
        leituras = [leitura_anexos.ler(a, diaria_oficio=liberada, diaria_rt=diaria_rt,
                                       soma_comprovantes=soma) for a in comprovantes]
        c = carimbos.get(ps.pk)
        servidores.append({"ps": ps, "liberada": liberada, "diaria_rt": diaria_rt,
                           "comprovantes": leituras, "rt": rt, "rt_anexo": rt_anexo,
                           "carimbo": c, "carimbo_x": round(c.x * 100, 1) if c else "",
                           "carimbo_y": round(c.y * 100, 1) if c else "",
                           "falta_pacote": pacote_prestacao.pendencias_do_pacote(ps),
                           "editavel": policies.pode_editar_prestacao(request.user, ps)
                           and not ps.finalizada})
        lidos += sum(1 for c in leituras if c.legivel) + (1 if rt and rt.legivel else 0)
    lidos += 1 if diario and diario.legivel else 0
    folha = contexto_folha(request, p, "leitura")
    atual = folha["servidor_atual"]
    pacote = next((s for s in servidores if atual and s["ps"].pk == atual["ps"].pk), None)
    pacote_pronto = pacote if pacote and not pacote["falta_pacote"] else None
    return render(request, "viagens/prestacao/leitura.html", {
        "p": p, "oficio": o, "servidores": servidores, "diario": diario, "db_anexo": db_anexo,
        "lidos": lidos, "via": via, "pode": pode,
        "paginas_via": range(1, carimbo.numero_de_paginas(via) + 1) if via else range(0),
        "despachos": [a for a in todos if a.tipo == tipos.DESPACHO and a.servidor_id is None],
        "editavel_equipe": pode and not equipe_finalizada(p),
        "anteriores": list(anexos.versoes_anteriores(p)),
        "operacoes": AnexoPrestacao.Operacao.choices,
        "pacote_pronto": pacote_pronto,
        "menu_leitura": "viagens/prestacao/_menu_leitura.html" if via or pacote_pronto else "",
        **folha,
        "migalhas": _migalhas(("Prestação de contas", reverse("viagens:prestacoes")),
                              (f"Ofício {o.numero_formatado}",
                               reverse("viagens:prestacao_equipe", args=[p.pk])),
                              ("Leitura e conferência", ""))})


def contexto_folha(request: HttpRequest, p: PrestacaoContas, atual: str) -> dict:
    """O que as folhas da prestação (diário, relatório, leitura) têm em comum:
    as etapas, a equipe (as linhas da lista) e o bloco do ofício para a lateral."""
    if not hasattr(p, "equipe"):
        p.equipe = p.oficio.viajantes.count()  # type: ignore[attr-defined]
    hoje = timezone.localdate()
    situacao = anexos.situacao([p.pk])
    membros = list(PrestacaoServidor.objects.filter(prestacao=p, removida_em__isnull=True)
                   .select_related("servidor").order_by("servidor__nome"))
    for ps in membros:
        ps.prestacao = p
    motoristas = _motoristas([p.pk])
    avisos = comunicacoes.situacoes([ps.pk for ps in membros])
    linhas = [_linha(request, ps, hoje, situacao, motoristas.get(p.pk), avisos.get(ps.pk))
              for ps in membros]
    b = _bloco(request, p, linhas, linhas)
    folhas = prestacao_equipe.folhas(p, membros, situacao, b["trechos"])
    # O servidor da folha (?servidor=): troca de servidor na mesma etapa; sem ele, o primeiro.
    pedido = request.GET.get("servidor") or ""
    atual_linha = next((linha for linha in linhas
                        if pedido.isdigit() and linha["ps"].pk == int(pedido)),
                       linhas[0] if linhas else None)
    return {"equipe_linhas": linhas, "b": b, "oficio": p.oficio, "p": p,
            "servidor_atual": atual_linha,
            "etapas_folha": prestacao_equipe.etapas_folha(folhas, b, atual)}
