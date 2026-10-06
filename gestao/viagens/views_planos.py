"""Telas dos planos de trabalho (paridade com `viagens_planos` da referência): lista com
abas e busca, a folha do plano (cartões numerados, gravação automática, conferência,
documento como vai sair, histórico), finalizar, gerar PDF/DOCX e o ciclo de vida."""

from __future__ import annotations

from typing import cast
from urllib.parse import urlencode, urlsplit

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from gestao.cadastros import policies as cadastros_policies
from gestao.cadastros.forms import FormularioHorario
from gestao.cadastros.models import PresetAtividades

from . import linha_do_tempo, planos, policies, prestacao, resultados
from .dominio import plano_trabalho as dominio
from .forms import FormularioEvento, FormularioPlano
from .models import Oficio, PlanoTrabalho
from .views import POR_PAGINA, _migalhas
from .views_editor import (
    moldura_da_folha,
    moldura_do_pdf,
    primeiro_erro,
    resposta_de_folha,
)

ABAS = [("", "Todos", "todos"), ("futuros", "Que vão acontecer", "futuros"),
        ("andamento", "Em andamento e realizados", "andamento"),
        ("finalizados", "Finalizados", "finalizados"),
        ("cancelados", "Cancelados", "cancelados")]


def _filtrar(qs, aba: str):
    """Abas da referência; sem data, o plano ainda "vai acontecer". "Finalizados": as
    contas dos ofícios da viagem do plano estão prestadas (referência)."""
    hoje = timezone.localdate()
    ativos = qs.filter(cancelado=False)
    prestadas = prestacao.prestadas("plano")
    if aba == "finalizados":
        return ativos.filter(prestadas)
    if aba == "futuros":
        return ativos.filter(~prestadas, Q(data_inicio__gt=hoje) | Q(data_inicio__isnull=True))
    if aba == "andamento":
        return ativos.filter(~prestadas, data_inicio__lte=hoje)
    if aba == "cancelados":
        return qs.filter(cancelado=True)
    return qs


def _buscar(qs, busca: str):
    """Número ("7", "7/2026"), destino, programa ou contextualização."""
    if not busca:
        return qs
    filtro = (Q(destinos__municipio__nome__unaccent__icontains=busca)
              | Q(programa__nome__unaccent__icontains=busca)
              | Q(programa_outros__unaccent__icontains=busca)
              | Q(contextualizacao__unaccent__icontains=busca))
    partes = busca.split("/")
    if partes[0].isascii() and partes[0].isdecimal():
        if len(partes) >= 2 and partes[1].isascii() and partes[1].isdecimal():
            filtro |= Q(numero=int(partes[0][:6]), ano=int(partes[1][:4]))
        elif len(partes) == 1:
            filtro |= Q(numero=int(partes[0][:6])) | Q(ano=int(partes[0][:4]))
    return qs.filter(filtro).distinct()


# Ordens da lista: número (o padrão, mais recente primeiro) ou o período do evento.
ORDENS = {
    "-numero": ("-ano", "-numero"),
    "numero": ("ano", "numero"),
    "periodo": (F("data_inicio").asc(nulls_last=True), "-ano", "-numero"),
    "-periodo": (F("data_inicio").desc(nulls_last=True), "-ano", "-numero"),
}


@require_GET
def lista(request: HttpRequest) -> HttpResponse:
    if not request.user.has_perm("viagens.view_planotrabalho"):
        raise PermissionDenied
    base = policies.planos_visiveis(request.user)
    oficio = None
    oficio_pk = request.GET.get("oficio") or ""
    if oficio_pk.isascii() and oficio_pk.isdecimal():
        oficio = policies.oficios_visiveis(request.user).filter(pk=int(oficio_pk)).first()
        base = base.filter(oficios__pk=int(oficio_pk))
    aba = request.GET.get("aba") or ""
    if aba not in {a for a, _, _ in ABAS}:
        aba = ""
    busca = (request.GET.get("q") or "").strip()
    ordem = request.GET.get("ordem") or "-numero"
    if ordem not in ORDENS:
        ordem = "-numero"
    qs = planos.com_dados(_buscar(_filtrar(base, aba), busca).order_by(*ORDENS[ordem]))
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    linhas = [{"plano": p, "periodo": dominio.periodo_curto(*planos.periodo_geral(p)),
               "eventos": len(p.eventos.all()) + 1 if p.eventos.all() else 0,
               "efetivo": planos.efetivo_geral(p), "diarias": planos.diarias_geral(p),
               "coordenador": planos.coordenador(p, "adm"),
               "estado": planos.estado(p),
               "editavel": policies.pode_editar_plano(request.user, p),
               "cancelavel": policies.pode_cancelar_plano(request.user, p),
               "excluivel": policies.pode_excluir_plano(request.user, p)}
              for p in pagina.object_list]
    return render(request, "viagens/planos/lista.html", {
        "page_obj": pagina, "linhas": linhas, "abas": ABAS, "aba": aba, "busca": busca,
        "ordem": ordem, "por_periodo": ordem in ("periodo", "-periodo"),
        # O que as abas preservam ao trocar de situação (busca, ordem e o filtro do ofício).
        "querystring_abas": urlencode({k: v for k, v in (
            ("oficio", oficio_pk if oficio is not None else ""), ("q", busca),
            ("ordem", ordem if ordem != "-numero" else "")) if v}),
        "contagens": {"todos": base.count(),
                      **{c: _filtrar(base, c).count() for c, _, _ in ABAS if c}},
        "oficio": oficio, "oficio_filtro": oficio_pk if oficio is not None else "",
        "pode_plano_do_oficio": (oficio is not None
                                 and policies.pode_criar_plano_do_oficio(request.user, oficio)),
        "pode_criar": policies.pode_criar_plano(request.user),
        "voltar": request.get_full_path(),
        "migalhas": _migalhas(("Planos de trabalho", ""))})


# ---------------------------------------------------------------- folha
def _plano_visivel(request: HttpRequest, pk: int) -> PlanoTrabalho:
    plano = get_object_or_404(planos.com_dados(PlanoTrabalho.objects.all()), pk=pk)
    if not policies.pode_ver_plano(request.user, plano):
        raise PermissionDenied
    return plano


def _oficios_escolhiveis(request: HttpRequest):
    return policies.oficios_visiveis(request.user).exclude(situacao=Oficio.Situacao.CANCELADO)


def _formulario(request: HttpRequest, *args, plano=None, **kwargs) -> FormularioPlano:
    extras = {"oficios": _oficios_escolhiveis(request),
              "unidade": policies.unidade_do_usuario(request.user),
              "fonte_oficios": reverse("viagens:buscar_oficios"),
              "fonte_municipios": reverse("cadastros:buscar_municipios")}
    if plano is not None and not args and not kwargs.get("initial"):
        return FormularioPlano.de(plano, **extras)
    return FormularioPlano(*args, plano=plano, **extras, **kwargs)


def _linhas_para_tela(form, dono) -> list[dict]:
    """As linhas do efetivo como a tela as desenha (`dono`: o plano ou o evento): as
    enviadas (com erro) ou as gravadas; o novo começa com uma linha em branco."""
    if form.is_bound:
        return form.linhas_informadas() or [{"unidade": "", "cargo": "", "quantidade": "1"}]
    if dono is not None and dono.efetivo.all():
        return [{"unidade": str(e.unidade_id or ""), "cargo": str(e.cargo_id),
                 "quantidade": str(e.quantidade)} for e in dono.efetivo.all()]
    return [{"unidade": "", "cargo": "", "quantidade": "1"}]


def _atividades_na_tela(form: FormularioPlano) -> set[str]:
    return {str(v) for v in (form["atividades"].value() or [])}


def _textos_desatualizados(plano) -> list[str]:
    """Textos escritos à mão que já não batem com o automático de agora (ex.: trocou o
    coordenador depois de ajustar a coordenação) — a tela avisa."""
    if plano is None:
        return []
    automaticos = planos.textos_automaticos(plano)
    nomes = {"contextualizacao": "Breve contextualização", "coordenacao": "Coordenador do evento",
             "consideracoes": "Considerações finais"}
    return [nomes[c] for c in nomes
            if not getattr(plano, f"{c}_auto") and getattr(plano, c).strip()
            != automaticos[c].strip()]


def _vem_do_oficio(form: FormularioPlano, plano) -> str:
    """No plano novo ligado a um ofício: o que vem dele ao criar (dito antes)."""
    if plano is not None:
        return ""
    pks = form.initial.get("oficios") or []
    oficios = list(Oficio.objects.filter(pk__in=pks))
    if not oficios:
        return ""
    base = planos.dados_dos_oficios(oficios)
    partes = []
    if base["destinos"]:
        partes.append("destino " + ", ".join(f"{m.nome}/{m.uf}" for m in base["destinos"]))
    if base["inicio"]:
        partes.append(f"período {dominio.periodo_curto(base['inicio'], base['fim'])}")
    total = sum(linha.quantidade for linha in base["efetivo"])
    if total:
        partes.append(f"efetivo de {total} servidor{'es' if total != 1 else ''}")
    if base["saida"]:
        partes.append("saída e chegada na sede")
    return ", ".join(partes)


def _servidor_escolhido(form: FormularioPlano, campo: str):
    """O servidor do campo (enviado ou gravado), para a busca mostrar o nome dele."""
    valor = form[campo].value()
    if not valor or not str(valor).isdecimal():
        return None
    opcoes = cast(forms.ModelChoiceField, form.fields[campo]).queryset
    return opcoes.filter(pk=valor).first() if opcoes is not None else None


def _form_evento(request: HttpRequest, plano, *args, evento=None) -> FormularioEvento:
    fonte = reverse("cadastros:buscar_municipios")
    if evento is not None and not args:
        return FormularioEvento.de(evento, fonte_municipios=fonte)
    return FormularioEvento(*args, evento=evento, fonte_municipios=fonte)


def _evento_pedido(request: HttpRequest, plano):
    """?evento=novo abre a janela vazia; ?evento=<id>, a do evento (para editar)."""
    pedido = request.GET.get("evento") or ""
    if pedido == "novo":  # o evento novo começa como o plano novo: horário e conjunto padrão
        form = FormularioEvento(fonte_municipios=reverse("cadastros:buscar_municipios"),
                                initial={"horario": dominio.HORARIO_PADRAO,
                                         "atividades": FormularioPlano.conjunto_padrao()})
        return form, None
    if pedido.isascii() and pedido.isdecimal():
        evento = plano.eventos.filter(pk=int(pedido)).first()
        if evento is not None:
            return _form_evento(request, plano, evento=evento), evento
    return None, None


def _tela(request: HttpRequest, form: FormularioPlano, plano=None, status: int = 200,
          form_evento=None, evento_editando=None):
    editavel = plano is None or policies.pode_editar_plano(request.user, plano)
    calculo, mensagens_calculo = (planos.calculo(plano) if plano else (None, []))
    pend = planos.pendencias(plano) if plano else []
    if plano is not None and form_evento is None and request.method == "GET":
        form_evento, evento_editando = _evento_pedido(request, plano)
    # No cartão 2, só o que é do cálculo (destino e efetivo já têm pendência própria).
    mensagens_calculo = [m for m in mensagens_calculo
                         if not m.startswith(("Informe o destino", "Informe o efetivo"))]
    conjuntos = list(PresetAtividades.objects.filter(ativo=True).prefetch_related("atividades"))
    # Quem assina já aparece no campo: a escolha "da configuração" leva o nome de quem assina.
    prevista = planos.assinatura_prevista(plano) if plano else ""
    return render(request, "viagens/planos/editar.html", {
        "form": form, "plano": plano, "editavel": editavel,
        # O "+" do horário: o cadastro rápido de horário (cadastros › Horários).
        "form_horario": FormularioHorario(auto_id="horario-novo-%s"),
        "linhas_efetivo": _linhas_para_tela(form, plano),
        "linhas_efetivo_evento": (_linhas_para_tela(form_evento, evento_editando)
                                  if form_evento is not None else []),
        "calculo_evento": (planos.calculo_do_evento(evento_editando)[0]
                           if evento_editando is not None else None),
        "atividades_marcadas": _atividades_na_tela(form),
        "estado": planos.estado(plano, pend) if plano else None,
        "eventos": list(plano.eventos.all()) if plano else [],
        "form_evento": form_evento, "evento_editando": evento_editando,
        "periodo_geral": dominio.periodo_curto(*planos.periodo_geral(plano)) if plano else "",
        "avisos": planos.avisos(plano) if plano else [],
        "textos_desatualizados": _textos_desatualizados(plano),
        "vem_do_oficio": _vem_do_oficio(form, plano),
        # O "+" de "Aplicar conjunto": cadastrar um conjunto novo (cadastros › Conjuntos).
        "pode_criar_conjunto": editavel and cadastros_policies.pode_criar_cadastro(
            request.user, PresetAtividades),
        "conjuntos": [{"nome": c.nome, "padrao": c.padrao,
                       "ids": ",".join(str(a.pk) for a in c.atividades.all())}
                      for c in conjuntos],
        "pendencias": pend, "calculo": calculo, "mensagens_calculo": mensagens_calculo,
        "efetivo_total": dominio.efetivo_total(planos.linhas_do_efetivo(plano)) if plano else 0,
        "efetivo_geral": planos.efetivo_geral(plano) if plano else 0,
        "diarias_geral": planos.diarias_geral(plano) if plano else None,
        "periodo": dominio.periodo_curto(plano.data_inicio, plano.data_fim) if plano else "",
        "destinos": planos.destinos_texto(plano) if plano else [],
        "coordenador_adm": planos.coordenador(plano, "adm") if plano else None,
        "escolhido_adm": _servidor_escolhido(form, "coordenador_adm"),
        "escolhido_op": _servidor_escolhido(form, "coordenador_op"),
        "coordenador_padrao": (None if plano else getattr(planos.configuracao(
            policies.unidade_do_usuario(request.user)), "coordenador_plano", None)),
        "assinatura_prevista": prevista,
        "historico": (linha_do_tempo.do_plano(plano)
                      if plano and policies.pode_ver_historico_plano(request.user, plano)
                      else []),
        "pode_ver_documento": (plano is not None
                               and policies.pode_ver_documento_plano(request.user, plano)),
        "pode_cancelar": plano is not None and policies.pode_cancelar_plano(request.user, plano),
        "pode_excluir": plano is not None and policies.pode_excluir_plano(request.user, plano),
        "proximo_numero": None if plano else planos.proximo_numero_do_ano(
            timezone.localdate().year),
        "ano": timezone.localdate().year,
        "migalhas": _migalhas(("Planos de trabalho", reverse("viagens:planos")),
                              (str(plano) if plano else "Novo plano de trabalho", ""))},
        status=status)


def _gravar(request: HttpRequest, form: FormularioPlano, plano=None) -> HttpResponse:
    if form.is_valid():
        try:
            salvo, copiados = planos.salvar(request.user, pk=plano.pk if plano else None,
                                            **form.cleaned_data)
        except planos.PlanoInvalido as exc:
            form.add_error(None, str(exc))
        else:
            texto = f"{salvo} {'salvo' if plano else 'criado como rascunho'}."
            if copiados:
                texto += f" Veio dos ofícios: {', '.join(copiados)}."
            messages.success(request, texto)
            return redirect("viagens:editar_plano", salvo.pk)
    return _tela(request, form, plano, status=422)


@require_http_methods(["GET", "POST"])
def novo(request: HttpRequest) -> HttpResponse:
    policies.exigir(policies.pode_criar_plano(request.user),
                    "Você não pode criar planos de trabalho.")
    if request.method == "POST" and request.POST.get("acao") == "criar":
        # "Novo plano" (lista): cria na hora e abre a folha — o documento já aparece e vai se
        # refazendo enquanto a pessoa preenche (como o termo, a OS e o ofício).
        try:
            # Sem `atividades`, o conjunto padrão já nasce gravado (planos.salvar).
            plano, _ = planos.salvar(request.user, horario=dominio.HORARIO_PADRAO)
        except planos.PlanoInvalido as exc:
            messages.error(request, str(exc))
            return redirect("viagens:planos")
        return redirect("viagens:editar_plano", plano.pk)
    if request.method == "POST":
        return _gravar(request, _formulario(request, request.POST))
    inicial: dict = {"horario": dominio.HORARIO_PADRAO,
                     "atividades": FormularioPlano.conjunto_padrao()}
    oficio_pk = request.GET.get("oficio") or ""
    if (oficio_pk.isascii() and oficio_pk.isdecimal()
            and _oficios_escolhiveis(request).filter(pk=int(oficio_pk)).exists()):
        inicial["oficios"] = [int(oficio_pk)]
    return _tela(request, _formulario(request, initial=inicial))


@require_POST
def criar_do_oficio(request: HttpRequest, oficio_pk: int) -> HttpResponse:
    """"Novo plano de trabalho" na janela do ofício: cria ligado a ele (destino, datas,
    efetivo e deslocamento vêm dele) e abre a folha."""
    oficio = get_object_or_404(_oficios_escolhiveis(request), pk=oficio_pk)
    policies.exigir(policies.pode_criar_plano_do_oficio(request.user, oficio),
                    "Só a unidade do ofício cria planos de trabalho a partir dele.")
    try:
        plano, _ = planos.salvar(request.user, oficios=[oficio])
    except planos.PlanoInvalido as exc:
        messages.error(request, str(exc))
        return redirect(f"{reverse('viagens:novo_plano')}?oficio={oficio.pk}")
    messages.success(request, f"{plano} criado a partir do Ofício {oficio.numero_formatado}. "
                              "Confira o programa, os coordenadores e as atividades.")
    return redirect("viagens:editar_plano", plano.pk)


@require_http_methods(["GET", "POST"])
def editar(request: HttpRequest, pk: int) -> HttpResponse:
    plano = _plano_visivel(request, pk)
    if request.method == "POST":
        policies.exigir(policies.pode_editar_plano(request.user, plano),
                        "Este plano de trabalho não pode ser alterado.")
        return _gravar(request, _formulario(request, request.POST, plano=plano), plano)
    return _tela(request, _formulario(request, plano=plano), plano)


@require_POST
def autosave(request: HttpRequest, pk: int) -> JsonResponse:
    """Grava o plano a cada pausa na digitação (componentes/autosave.js), quando o
    formulário inteiro é válido; senão diz o que impede, no status da barra."""
    plano = _plano_visivel(request, pk)
    if not policies.pode_editar_plano(request.user, plano):
        return JsonResponse({"salvo": False,
                             "mensagem": "Este plano não pode ser alterado (cancelado?)."})
    form = _formulario(request, request.POST, plano=plano)
    if not form.is_valid():
        return JsonResponse({"salvo": False, "mensagem": primeiro_erro(form)})
    try:
        salvo, copiados = planos.salvar(request.user, pk=plano.pk, **form.cleaned_data)
    except planos.PlanoInvalido as exc:
        return JsonResponse({"salvo": False, "mensagem": f"Não salvo: {exc}"})
    except PermissionDenied:
        return JsonResponse({"salvo": False, "mensagem": "Este plano não pode mais ser alterado."})
    except PlanoTrabalho.DoesNotExist:
        return JsonResponse({"salvo": False, "mensagem": "Este plano foi excluído."})
    return JsonResponse({"salvo": True, "recarregar": bool(copiados),
                         "em": timezone.localtime(salvo.atualizado_em).strftime("%H:%M"),
                         "campos": {"versao": planos.versao_de(salvo)}})


@require_POST
def salvar_evento(request: HttpRequest, pk: int) -> HttpResponse:
    """A janela do evento adicional: cria ou altera e volta ao bloco dos eventos."""
    plano = _plano_visivel(request, pk)
    policies.exigir(policies.pode_editar_plano(request.user, plano),
                    "Este plano de trabalho não pode ser alterado.")
    pedido = request.POST.get("evento") or ""
    evento = None
    if pedido:
        if not (pedido.isascii() and pedido.isdecimal()):
            raise Http404
        evento = get_object_or_404(plano.eventos, pk=int(pedido))
    form = _form_evento(request, plano, request.POST, evento=evento)
    if form.is_valid():
        try:
            salvo = planos.salvar_evento(request.user, plano.pk,
                                         evento_pk=evento.pk if evento else None,
                                         **form.cleaned_data)
        except planos.PlanoInvalido as exc:
            form.add_error(None, str(exc))
        else:
            numero = list(plano.eventos.values_list("pk", flat=True)).index(salvo.pk) + 2
            messages.success(request, f"Evento {numero} {'salvo' if evento else 'acrescentado'}"
                                      " — o plano agora tem vários eventos.")
            return redirect(reverse("viagens:editar_plano", args=[plano.pk]) + "#eventos")
    return _tela(request, _formulario(request, plano=plano), plano, status=422,
                 form_evento=form, evento_editando=evento)


@require_POST
def remover_evento(request: HttpRequest, pk: int, evento_pk: int) -> HttpResponse:
    plano = _plano_visivel(request, pk)
    try:
        planos.remover_evento(request.user, plano.pk, evento_pk)
    except (planos.PlanoInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Evento removido do plano.")
    return redirect(reverse("viagens:editar_plano", args=[plano.pk]) + "#eventos")


@require_http_methods(["GET", "POST"])
def resultados_do_plano(request: HttpRequest, pk: int) -> HttpResponse:
    """Realizado por atividade (depois da ação) e o relatório final montado dele."""
    plano = _plano_visivel(request, pk)
    editavel = policies.pode_editar_plano(request.user, plano)
    erros: list[str] = []
    digitados: dict[int, tuple[str, str]] = {}
    if request.method == "POST":
        policies.exigir(editavel, "Este plano de trabalho não pode ser alterado.")
        for linha in resultados.linhas(plano):
            chave = linha.atividade.pk
            digitados[chave] = (request.POST.get(f"realizado_{chave}", ""),
                                request.POST.get(f"observacao_{chave}", ""))
        try:
            resultados.salvar(request.user, plano.pk, digitados)
        except resultados.ResultadosInvalidos as exc:
            erros = exc.erros
        else:
            messages.success(request, "Resultados salvos.")
            return redirect("viagens:resultados_plano", plano.pk)
    linhas = resultados.linhas(plano)
    for linha in linhas:  # depois de um erro, volta o que foi digitado
        if linha.atividade.pk in digitados:
            linha.digitado, linha.observacao = digitados[linha.atividade.pk]
    return render(request, "viagens/planos/resultados.html", {
        "plano": plano, "linhas": linhas, "erros": erros, "editavel": editavel,
        "relatorio": resultados.relatorio_final(plano),
        "periodo_geral": dominio.periodo_curto(*planos.periodo_geral(plano)),
        "destinos": planos.todos_os_destinos(plano),
        "migalhas": _migalhas(("Planos de trabalho", reverse("viagens:planos")),
                              (str(plano), reverse("viagens:editar_plano", args=[plano.pk])),
                              ("Resultados", ""))}, status=422 if erros else 200)


@require_POST
def finalizar(request: HttpRequest, pk: int) -> HttpResponse:
    """"Finalizar e gerar o plano": grava o que está na tela (com a versão), confere e
    gera — fixa a data do documento e libera o PDF/DOCX."""
    plano = _plano_visivel(request, pk)
    policies.exigir(policies.pode_editar_plano(request.user, plano),
                    "Este plano de trabalho não pode ser alterado.")
    # "Finalizar" do rodapé: a folha já se gravou sozinha (o envio espera o autosave) e o
    # pedido vem sem os campos — só conclui e volta à lista. Com os campos (sem JavaScript),
    # grava antes.
    com_campos = "versao" in request.POST
    if com_campos:
        form = _formulario(request, request.POST, plano=plano)
        if not form.is_valid():
            return _tela(request, form, plano, status=422)
    try:
        if com_campos:
            planos.salvar(request.user, pk=plano.pk, **form.cleaned_data)
        planos.finalizar(request.user, plano.pk)
    except planos.PlanoInvalido as exc:
        messages.error(request, str(exc))
        return redirect(reverse("viagens:editar_plano", args=[plano.pk]) + "#conferencia")
    messages.success(request, f"{plano} finalizado e gerado.")
    return redirect("viagens:planos")


@require_POST
def duplicar(request: HttpRequest, pk: int) -> HttpResponse:
    """Um plano novo com os mesmos dados; abre a folha dele."""
    plano = _plano_visivel(request, pk)
    try:
        novo = planos.duplicar(request.user, plano.pk)
    except (planos.PlanoInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
        return redirect("viagens:editar_plano", plano.pk)
    messages.success(request, f"{novo} criado a partir do {plano}.")
    return redirect("viagens:editar_plano", novo.pk)


@require_GET
@moldura_da_folha
def folha(request: HttpRequest, pk: int) -> HttpResponse:
    """O plano como vai sair, em HTML (prévia com MINUTA): não fixa a data nem marca como
    gerado."""
    plano = _plano_visivel(request, pk)
    policies.exigir(policies.pode_ver_documento_plano(request.user, plano),
                    "Reative o plano para ver o documento.")
    # ?versao=N mostra uma versão do texto (o histórico do editor); 0 é o modelo.
    regioes, marcados = None, set()
    pedido = request.GET.get("versao") or ""
    if pedido.isascii() and pedido.isdigit():
        numero = int(pedido)
        edicao = planos._versoes(plano).filter(numero=numero).first() if numero else None
        if numero and edicao is None:
            raise Http404
        regioes = dict(edicao.regioes) if edicao else {}
        marcados = {b["chave"] for b in edicao.blocos_alterados} if edicao else set()
    else:
        vigente = planos.edicao_vigente(plano)
        marcados = {b["chave"] for b in vigente.blocos_alterados} if vigente else set()

    def gerar(nonce: str) -> str:
        dados = planos.dados_do_documento(plano, fixar=False)
        # Gerado, a folha é o documento (número e data já fixados): sem a marca de minuta.
        dados["previa"] = plano.documento_gerado_em is None
        return planos.html_do_documento(dados, folha=True, nonce=nonce, regioes=regioes,
                                        blocos_alterados=marcados)
    return resposta_de_folha(request, gerar, erros=(planos.PlanoInvalido,))


@require_GET
@moldura_do_pdf
def documento(request: HttpRequest, pk: int, formato: str) -> HttpResponse:
    plano = _plano_visivel(request, pk)
    policies.exigir(policies.pode_editar_plano(request.user, plano),
                    "Reative o plano antes de gerar documentos.")
    if formato not in ("pdf", "docx"):
        raise Http404
    previa = formato == "pdf" and request.GET.get("previa") == "1"
    if not previa and plano.documento_gerado_em is None:
        messages.error(request, "Use “Finalizar e gerar o plano” no cartão Documento: é ele "
                                "que confere e fixa a data do documento.")
        return redirect(reverse("viagens:editar_plano", args=[plano.pk]) + "#conferencia")
    try:
        dados = planos.dados_do_documento(plano, fixar=not previa)
    except planos.PlanoInvalido as exc:
        if previa:
            return resposta_de_folha(request, lambda nonce: "", erros=(planos.PlanoInvalido,),
                                     erro=exc)
        messages.error(request, str(exc))
        return redirect(reverse("viagens:editar_plano", args=[plano.pk]) + "#conferencia")
    nome = f"plano-{plano.numero:02d}-{plano.ano}{'-previa' if previa else ''}.{formato}"
    if formato == "pdf":
        resposta = HttpResponse(planos.pdf_do_documento(dados), content_type="application/pdf")
        resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    else:
        resposta = HttpResponse(planos.docx_do_documento(dados), content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
        resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    resposta["Cache-Control"] = "no-store"
    return resposta


# ---------------------------------------------------------------- ciclo de vida
def _voltar(request: HttpRequest, padrao: str, plano_pk: int | None = None) -> str:
    voltar = request.POST.get("voltar") or ""
    caminhos = {reverse("viagens:planos")}
    if plano_pk is not None:
        caminhos.add(reverse("viagens:editar_plano", args=[plano_pk]))
    if (urlsplit(voltar).path in caminhos
            and url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()})):
        return voltar
    return padrao


def _acao(request: HttpRequest, pk: int, executar):
    plano = _plano_visivel(request, pk)
    try:
        mensagem = executar(plano)
    except (planos.PlanoInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    except PlanoTrabalho.DoesNotExist:
        messages.error(request, "Este plano de trabalho não existe mais.")
        return redirect("viagens:planos")
    else:
        messages.success(request, mensagem)
    return redirect(_voltar(request, reverse("viagens:planos"), plano_pk=pk))


@require_POST
def cancelar(request: HttpRequest, pk: int) -> HttpResponse:
    def executar(p):
        planos.cancelar(request.user, p.pk, request.POST.get("motivo", ""))
        return f"{p} cancelado. O histórico e o número foram mantidos."
    return _acao(request, pk, executar)


@require_POST
def reativar(request: HttpRequest, pk: int) -> HttpResponse:
    return _acao(request, pk, lambda p: f"{planos.reativar(request.user, p.pk)} reativado.")


@require_POST
def excluir(request: HttpRequest, pk: int) -> HttpResponse:
    def executar(p):
        nome = planos.excluir(request.user, p.pk)
        return f"{nome} excluído; o número volta a ficar livre."
    resposta = _acao(request, pk, executar)
    # Excluído: a folha dele não existe mais — volta à lista.
    if not PlanoTrabalho.objects.filter(pk=pk).exists():
        return redirect(_voltar(request, reverse("viagens:planos")))
    return resposta
