"""Diário de bordo (módulo 9b): a folha (motorista e viatura, trechos com km e
abastecimento, conferência do hodômetro, documento) e o documento em PDF/XLSX. Regra em
`diario.py`."""

from __future__ import annotations

import re
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from gestao.cadastros.models import Viatura
from gestao.cadastros.validacoes import formatar_cpf

from . import diario, policies, realizado, views_prestacao
from .dominio.diario import comparar_rodado
from .dominio.diario import km as dominio_km
from .models import DiarioBordo, PrestacaoContas
from .views import _migalhas
from .views_editor import moldura_da_folha, resposta_de_folha

CAMPO_LINHA = re.compile(r"^l-(\d+)-(km_inicial|km_final|abastecimento)$")


def _prestacao(request: HttpRequest, pk: int) -> PrestacaoContas:
    p = get_object_or_404(PrestacaoContas.objects.select_related(
        "oficio__unidade", "oficio__viatura__combustivel"), pk=pk)
    if not policies.pode_ver_equipe_prestacao(request.user, p):
        raise Http404
    return p


def _valores(request: HttpRequest) -> dict[int, dict[str, object]]:
    valores: dict[int, dict[str, object]] = {}
    for chave, valor in request.POST.items():
        if (m := CAMPO_LINHA.match(chave)):
            valores.setdefault(int(m.group(1)), {})[m.group(2)] = valor
    return valores


@require_GET
def folha(request: HttpRequest, pk: int) -> HttpResponse:
    p = _prestacao(request, pk)
    finalizada = diario.equipe_finalizada(p)
    editavel = diario.pode_editar(request.user, p, finalizada)
    if editavel and request.GET.get("cadastros") == "1":
        # Os "+" de servidor e viatura: o formulário só vem quando o diálogo abre.
        from gestao.cadastros.forms import formularios_de_cadastro_rapido
        return render(request, "componentes/dialogos_cadastro.html",
                      formularios_de_cadastro_rapido())
    d = (diario.obter(p) if editavel
         else DiarioBordo.objects.filter(prestacao=p).select_related("prestacao__oficio")
         .first())  # consulta, diário ainda não aberto: mostra sem criar nada
    # Motorista de outro ofício: os trechos e os km são os do diário daquele ofício.
    de_la = diario.origem(d) if d else None
    lista = diario.linhas(de_la or d) if d else []
    conf = diario.conferencia(de_la or d, lista) if d else None
    oficio = p.oficio
    mot_oficio, via_oficio = diario.motorista_do_oficio(oficio), diario.viatura_do_oficio(oficio)
    nome, cpf = diario.motorista(d) if d else mot_oficio
    v = diario.viatura(d) if d else via_oficio
    def km(valor):
        return dominio_km(valor) if valor is not None else ""

    def item(i, linha):
        prevista, rodado = diario.prevista(linha), conf.rodados[i] if conf else None
        situacao, diferenca = comparar_rodado(rodado, prevista)
        return {"l": linha, "rota": diario.rota(linha), "prevista": prevista,
                "origem": diario.rota(linha).split(" → ")[0],
                "destino": diario.rota(linha).split(" → ")[-1],
                "rodado": km(rodado), "situacao": situacao,
                "diferenca": (f"{'+' if diferenca > 0 else '−'}{dominio_km(abs(diferenca))}"
                              if diferenca else ""),
                "km_inicial": km(linha.km_inicial), "km_final": km(linha.km_final),
                "fonte": diario.fonte(linha)}

    linhas = [item(i, linha) for i, linha in enumerate(lista)]
    preenchidas = sum(1 for linha in lista
                      if linha.km_inicial is not None and linha.km_final is not None)
    realizados = realizado.trechos(p)
    from .dominio.relatorio import moeda
    por_servidor_oficio = (oficio.diarias_calculo or {}).get("por_servidor")
    nova = realizado.por_servidor(p)
    return render(request, "viagens/diario/folha.html", {
        "realizados": realizados, "alteracoes_horario": realizado.alteracoes(p),
        "diaria_oficio": moeda(Decimal(por_servidor_oficio)) if por_servidor_oficio else "",
        "diaria_realizada": moeda(nova) if nova is not None else "",
        "p": p, "oficio": oficio, "d": d, "linhas": linhas, "conf": conf,
        "editavel": editavel, "equipe_finalizada": finalizada,
        "de_la": de_la, "editavel_km": editavel and de_la is None,
        "protocolo_de_la": (diario.protocolo_formatado(de_la.prestacao.oficio.protocolo)
                            if de_la else ""),
        **(_contexto_da_escolha(d) if editavel and d is not None else {}),
        "preenchidas": preenchidas, "completo": bool(lista) and preenchidas == len(lista),
        "faltam": len(lista) - preenchidas,
        "motorista": {"nome": nome, "cpf": formatar_cpf(cpf)}, "viatura": v,
        "motorista_oficio": mot_oficio[0], "viatura_oficio": via_oficio,
        "alteracoes": (diario.alteracoes(d, do_oficio=mot_oficio, viatura_oficio=via_oficio)
                       if d else []),
        "equipe": [vj.servidor for vj in oficio.viajantes.select_related(
            "servidor__cargo", "servidor__unidade").order_by("ordem")],
        "viaturas": Viatura.objects.filter(ativo=True).order_by("modelo", "placa"),
        "tipos_viatura": Viatura.Tipo.choices,
        **views_prestacao.contexto_folha(request, p, "diario"),
        "migalhas": _migalhas(("Prestação de contas", reverse("viagens:prestacoes")),
                              (f"Ofício {oficio.numero_formatado}",
                               reverse("viagens:prestacao_equipe", args=[p.pk])),
                              ("Diário de bordo", ""))})


def _contexto_da_escolha(d: DiarioBordo) -> dict:
    """O que a troca de motorista e viatura usa: a busca de ofícios (a mesma do termo) e a
    escolha de viatura do ofício, com o "+" que cadastra sem sair da folha."""
    from gestao.cadastros.models import Servidor

    from .forms import ViaturaDoDiarioForm
    equipe = d.prestacao.oficio.viajantes.values("servidor_id")
    outros = (Servidor.objects.filter(Q(ativo=True) | Q(pk=d.motorista_servidor_id))
              .exclude(pk__in=equipe).select_related("cargo", "unidade").order_by("nome"))
    return {"fonte_oficios": reverse("viagens:buscar_oficios"),
            "outros_servidores": outros,
            "form_viatura_diario": ViaturaDoDiarioForm(diario=d)}


@require_POST
def salvar(request: HttpRequest, pk: int) -> HttpResponse:
    """Sem JavaScript (ou "Salvar"): grava as linhas e volta para a folha."""
    p = _prestacao(request, pk)
    d = diario.obter(p)
    try:
        n = diario.salvar_linhas(request.user, d.pk, _valores(request))
    except (diario.DiarioInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Diário de bordo salvo." if n else "Nada mudou no diário.")
    return redirect(reverse("viagens:diario", args=[p.pk]) + "#trechos")


@require_POST
def autosave(request: HttpRequest, pk: int) -> JsonResponse:
    """Contrato do autosave.js: {"salvo", "em", "campos", "recarregar", "mensagem"}."""
    p = _prestacao(request, pk)
    try:
        d = diario.obter(p)
        diario.salvar_linhas(request.user, d.pk, _valores(request))
    except (diario.DiarioInvalido, PermissionDenied) as exc:
        return JsonResponse({"salvo": False, "mensagem": str(exc)})
    return JsonResponse({"salvo": True, "em": f"{timezone.localtime():%H:%M}", "campos": {},
                         "recarregar": False})


def _inteiro(texto: str | None) -> int | None:
    return int(texto) if texto and texto.isdigit() else None


def _trocar_recursos(request: HttpRequest, d: DiarioBordo) -> DiarioBordo:
    g = request.POST.get
    return diario.trocar_motorista_e_viatura(
        request.user, d.pk, motorista_modo=g("motorista_modo", ""),
        motorista_servidor_id=_inteiro(g("motorista_servidor")),
        motorista_nome=g("motorista_nome", ""), motorista_cpf=g("motorista_cpf", ""),
        motorista_oficio=g("motorista_oficio", ""),
        motorista_protocolo=g("motorista_protocolo", ""),
        oficio_do_motorista_id=_inteiro(g("oficio_do_motorista")),
        viatura_modo=g("viatura_modo", ""), viatura_id=_inteiro(g("viatura")),
        viatura_modelo=g("viatura_modelo", ""), viatura_placa=g("viatura_placa", ""),
        viatura_tipo=g("viatura_tipo", ""), viatura_combustivel=g("viatura_combustivel", ""))


@require_POST
def autosave_motorista(request: HttpRequest, pk: int) -> JsonResponse:
    """Motorista e transporte gravando sozinhos (contrato do autosave.js); o que falta para
    a escolha valer (ex.: "Da equipe" sem o servidor) volta como mensagem, sem gravar."""
    p = _prestacao(request, pk)
    d = diario.obter(p)
    antes = d.oficio_do_motorista_id if d.motorista_modo == DiarioBordo.Motorista.OUTRO else None
    try:
        d = _trocar_recursos(request, d)
    except (diario.DiarioInvalido, PermissionDenied) as exc:
        return JsonResponse({"salvo": False, "mensagem": str(exc)})
    # Ligar ou trocar o ofício do motorista troca o diário inteiro (trechos e documento).
    return JsonResponse({"salvo": True, "em": f"{timezone.localtime():%H:%M}", "campos": {},
                         "recarregar": d.oficio_do_motorista_id != antes})


@require_POST
def motorista(request: HttpRequest, pk: int) -> HttpResponse:
    p = _prestacao(request, pk)
    d = diario.obter(p)
    try:
        _trocar_recursos(request, d)
    except (diario.DiarioInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Motorista e viatura deste diário atualizados (o ofício não "
                                  "muda).")
    return redirect(reverse("viagens:diario", args=[p.pk]) + "#motorista")


def _momento(data: str, hora: str, rotulo: str):
    from datetime import datetime
    try:
        ingenuo = datetime.strptime(f"{data.strip()} {hora.strip()}", "%d/%m/%Y %H:%M")
    except ValueError:
        raise realizado.AjusteInvalido(
            f"{rotulo}: informe data (dd/mm/aaaa) e hora (hh:mm).") from None
    return timezone.make_aware(ingenuo)


@require_POST
def viagem_realizada(request: HttpRequest, pk: int, acao: str) -> HttpResponse:
    """Ajustar (copia os trechos do ofício), salvar os horários ou voltar ao do ofício."""
    p = _prestacao(request, pk)
    try:
        if acao == "ajustar":
            realizado.ajustar(request.user, p.pk)
            messages.success(request, "Viagem pronta para ajustar: corrija os horários do que "
                                      "de fato aconteceu.")
        elif acao == "salvar":
            horarios = {}
            for t in realizado.trechos(p):
                g = request.POST.get
                horarios[t.pk] = (
                    _momento(g(f"r-{t.pk}-saida_data", ""), g(f"r-{t.pk}-saida_hora", ""),
                             f"Saída de {t}"),
                    _momento(g(f"r-{t.pk}-chegada_data", ""), g(f"r-{t.pk}-chegada_hora", ""),
                             f"Chegada de {t}"))
            realizado.salvar(request.user, p.pk, horarios)
            messages.success(request, "Horários da viagem realizada salvos; as diárias foram "
                                      "recalculadas.")
        elif acao == "desfazer":
            realizado.desfazer(request.user, p.pk)
            messages.success(request, "Ajuste desfeito: vale de novo a viagem do ofício.")
        else:
            raise Http404
    except (realizado.AjusteInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    return redirect(reverse("viagens:diario", args=[p.pk]) + "#realizada")


@require_GET
def documento(request: HttpRequest, pk: int, formato: str) -> HttpResponse:
    if formato not in ("pdf", "xlsx"):
        raise Http404
    p = _prestacao(request, pk)
    d = (diario.obter(p) if diario.pode_editar(request.user, p)
         else get_object_or_404(DiarioBordo, prestacao=p))
    dados = diario.dados_do_documento(d)
    if formato == "pdf":
        resposta = HttpResponse(diario.pdf_do_documento(dados), content_type="application/pdf")
        disposicao = "inline"
    else:
        resposta = HttpResponse(diario.planilha_do_documento(dados), content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
        disposicao = "attachment"
    nome = diario.nome_do_arquivo(d, formato)
    resposta["Content-Disposition"] = f'{disposicao}; filename="{nome}"'
    return resposta


@require_GET
@moldura_da_folha
def folha_documento(request: HttpRequest, pk: int) -> HttpResponse:
    """O diário como sai (HTML), para o visualizador/editor da folha. ?versao=N mostra uma
    versão do texto (o histórico do editor); 0 é o modelo."""
    from . import prestacao_texto
    p = _prestacao(request, pk)
    if not diario.pode_editar(request.user, p):
        get_object_or_404(DiarioBordo, prestacao=p)  # consulta: só o diário já aberto
    regioes, marcados = prestacao_texto.regioes_da_versao(
        p, prestacao_texto.CHAVE_DIARIO, request.GET.get("versao") or "")
    if marcados is None:
        raise Http404
    return resposta_de_folha(request, lambda nonce: prestacao_texto.html_do_documento(
        prestacao_texto.dados_do_documento(p, prestacao_texto.CHAVE_DIARIO), folha=True,
        nonce=nonce, regioes=regioes, blocos_alterados=marcados),
        erros=(diario.DiarioInvalido, prestacao_texto.PrestacaoInvalida))
