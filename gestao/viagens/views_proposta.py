"""Proposta consolidada (AUT-14): escolher a viagem, informar quem vai, ver a prévia (GET,
nada gravado) e "Criar rascunhos" (POST com a assinatura da prévia). A regra está em
`proposta.py`; a decisão em docs/automacao/proposta-consolidada.md."""

from __future__ import annotations

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse, QueryDict
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from gestao.cadastros.models import Servidor, Viatura

from . import proposta as regra
from .forms import CampoEquipe
from .views import _migalhas


class EscolhaDeViagem(forms.ModelChoiceField):
    """A viagem como o operador a reconhece: título e período."""

    def label_from_instance(self, obj) -> str:
        from .viagem import periodo_curto
        periodo = periodo_curto(obj.data_inicio, obj.data_fim)
        return f"{obj} · {periodo}" if periodo else str(obj)


class FormularioProposta(forms.Form):
    """A viagem e quem vai. Ninguém é sugerido: a pessoa escolhe cada servidor."""

    termos = forms.BooleanField(label="Termos de autorização", required=False, initial=True,
                                help_text="Para quem é de outra unidade.")
    ordem = forms.BooleanField(label="Ordem de serviço", required=False, initial=True,
                               help_text="Se a viagem ainda não tem.")
    plano = forms.BooleanField(label="Plano de trabalho", required=False, initial=True,
                               help_text="Se a viagem ainda não tem.")

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        fonte = reverse("cadastros:buscar_servidores")
        ativos = Servidor.objects.filter(ativo=True)
        self.viagens = regra.viagens_para_propor(usuario)
        viagem = EscolhaDeViagem(label="Viagem", queryset=self.viagens,
                                 empty_label="Escolha a viagem",
                                 widget=forms.Select(attrs={"class": "selecao"}))
        equipe: forms.ModelMultipleChoiceField = forms.ModelMultipleChoiceField(
            label="Quem vai", queryset=ativos,
            widget=CampoEquipe(fonte=fonte, rotulo="Adicionar servidor"))
        motorista: forms.ModelMultipleChoiceField = forms.ModelMultipleChoiceField(
            label="Quem dirige (opcional)", queryset=ativos, required=False,
            help_text="Só vale com viatura. Fora da equipe, entra nela.",
            widget=CampoEquipe(fonte=fonte, rotulo="Quem dirige (opcional)",
                               rotulo_vazio="Ninguém escolhido para dirigir.", maximo=1))
        for campo in (equipe, motorista):
            campo.widget.choices = campo.choices  # type: ignore[attr-defined]
        viatura: forms.ModelChoiceField = forms.ModelChoiceField(
            label="Viatura (opcional)", required=False, empty_label="Sem viatura",
            queryset=Viatura.objects.filter(ativo=True).order_by("placa"),
            widget=forms.Select(attrs={"class": "selecao"}))
        # A ordem da tela: a viagem, quem vai, quem dirige, a viatura e o que sai junto.
        opcoes = {n: self.fields.pop(n) for n in ("termos", "ordem", "plano")}
        self.fields.update({"viagem": viagem, "servidores": equipe, "motorista": motorista,
                            "viatura": viatura, **opcoes})

    def clean_motorista(self):
        motoristas = list(self.cleaned_data.get("motorista") or [])
        if len(motoristas) > 1:
            raise forms.ValidationError("Escolha um motorista só.")
        return motoristas[0] if motoristas else None

    def entrada(self) -> regra.Entrada:
        d = self.cleaned_data
        return regra.Entrada.de(d["viagem"], d["servidores"], d.get("motorista"),
                                d.get("viatura"), termos=d["termos"], ordem=d["ordem"],
                                plano=d["plano"])




def _ids(valores: list[str]) -> tuple[int, ...]:
    try:
        return tuple(int(v) for v in valores if v)
    except ValueError:
        raise Http404 from None


def _entrada_do_post(request: HttpRequest) -> regra.Entrada:
    p = request.POST
    viagem = _ids([p.get("viagem", "")])
    if not viagem:
        raise Http404
    motorista = _ids([p.get("motorista", "")])
    viatura = _ids([p.get("viatura", "")])
    return regra.Entrada.de(viagem[0], _ids(p.getlist("servidores")),
                            motorista[0] if motorista else None,
                            viatura[0] if viatura else None,
                            termos=p.get("termos") == "1", ordem=p.get("ordem") == "1",
                            plano=p.get("plano") == "1")


def _viagem_pedida(request: HttpRequest, valor: str):
    """A viagem do parâmetro: fora do escopo → 404; sem permissão de propor → 403."""
    try:
        viagem = regra.viagem_no_escopo(request.user, int(valor))
    except (ValueError, regra.ForaDoEscopo):
        raise Http404 from None
    if not regra.pode_propor(request.user, viagem):
        raise PermissionDenied("Esta viagem não aceita novos documentos (cancelada ou sem "
                               "permissão).")
    return viagem


def _tela(request: HttpRequest, form: FormularioProposta, previa=None, *, erro: str = "",
          status: int = 200) -> HttpResponse:
    url_alterar = ""
    if previa is not None:
        # Depois da prévia, o passo 1 vira resumo: alterar volta ao formulário preenchido
        # (assim o "Criar" nunca usa escolhas diferentes das que a tela mostra).
        q = _dados_do_form(previa.entrada)
        q["acao"] = "alterar"
        url_alterar = f"{reverse('viagens:proposta')}?{q.urlencode()}"
    return render(request, "viagens/proposta/proposta.html", {
        "form": form, "previa": previa, "erro": erro, "url_alterar": url_alterar,
        "tem_viagens": form.viagens.exists(),
        "migalhas": _migalhas(("Todas as viagens", reverse("viagens:viagens")),
                              ("Proposta consolidada", ""))}, status=status)


@require_GET
def proposta(request: HttpRequest) -> HttpResponse:
    """Escolher e ver a prévia. GET de propósito: a prévia não grava nada."""
    if not regra.pode_propor(request.user):
        raise PermissionDenied("Seu perfil não cria ofícios.")
    if request.GET.get("viagem"):
        _viagem_pedida(request, request.GET["viagem"])
    if request.GET.get("acao") == "alterar":
        return _tela(request, FormularioProposta(request.GET, usuario=request.user))
    if request.GET.get("acao") != "previa":
        inicial = {"viagem": request.GET.get("viagem")} if request.GET.get("viagem") else {}
        return _tela(request, FormularioProposta(initial=inicial, usuario=request.user))
    form = FormularioProposta(request.GET, usuario=request.user)
    if not form.is_valid():
        return _tela(request, form, status=422)
    try:
        previa = regra.montar(request.user, form.entrada())
    except regra.ForaDoEscopo:
        raise Http404 from None
    return _tela(request, form, previa)


@require_POST
def criar(request: HttpRequest) -> HttpResponse:
    """Cria os rascunhos da prévia conferida (a assinatura dela vem no POST)."""
    if not regra.pode_propor(request.user):
        raise PermissionDenied("Seu perfil não cria ofícios.")
    entrada = _entrada_do_post(request)
    viagem = _viagem_pedida(request, str(entrada.viagem))
    try:
        _, r = regra.aplicar(request.user, entrada, request.POST.get("assinatura", ""))
    except regra.ForaDoEscopo:
        raise Http404 from None
    except (regra.PropostaDesatualizada, regra.PropostaBloqueada) as exc:
        previa = regra.montar(request.user, entrada)
        form = FormularioProposta(_dados_do_form(entrada), usuario=request.user)
        form.is_valid()
        return _tela(request, form, previa, erro=str(exc), status=409)
    numeros = ", ".join(o.numero_formatado for o in r.oficios)
    partes = [f"{len(r.oficios)} ofício(s) ({numeros})"]
    if r.termos:
        partes.append(f"{r.termos} termo(s)")
    if r.ordem:
        partes.append(str(r.ordem))
    if r.plano:
        partes.append(str(r.plano))
    messages.success(request, "Rascunhos criados conforme a prévia: " + ", ".join(partes)
                     + ". Revise e emita cada um na folha dele.")
    for aviso in r.avisos:
        messages.warning(request, aviso)
    return redirect(reverse("viagens:editar_viagem", args=[viagem.pk]) + "#documentos")


def _dados_do_form(e: regra.Entrada) -> QueryDict:
    """As entradas do POST de volta no formulário (a tela de recusa mostra a prévia nova)."""
    dados: dict = {"viagem": str(e.viagem), "servidores": [str(s) for s in e.servidores],
                   "motorista": [str(e.motorista)] if e.motorista else [],
                   "viatura": str(e.viatura) if e.viatura else ""}
    for nome in ("termos", "ordem", "plano"):
        if getattr(e, nome):
            dados[nome] = "on"
    q = QueryDict(mutable=True)
    for chave, valor in dados.items():
        if isinstance(valor, list):
            q.setlist(chave, valor)
        else:
            q[chave] = valor
    return q
