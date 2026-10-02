"""UI Lab: vitrine viva do Design System.

Cada componente aparece em todos os estados (padrão, hover/foco via
interação real, ativo, desabilitado, carregando, erro, sucesso, vazio,
conteúdo longo). Os testes visuais e de acessibilidade percorrem esta página
nas larguras de referência antes de qualquer tela de negócio.
"""

from __future__ import annotations

from django import forms
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import render

from gestao.plataforma.widgets import (
    FORMATOS_DATA,
    FORMATOS_DATA_HORA,
    EntradaData,
    EntradaDataHora,
    EntradaHora,
    Selecao,
)

TONS_STATUS = [
    ("Rascunho", "neutro"),
    ("Em preenchimento", "info"),
    ("Pronto para emitir", "marca"),
    ("Emitido", "sucesso"),
    ("Justificativa pendente", "aviso"),
    ("Cancelado", "perigo"),
    ("Motorista", "forte"),
]


class FormularioExemplo(forms.Form):
    nome = forms.CharField(label="Nome completo", max_length=150,
                           widget=forms.TextInput(attrs={"class": "entrada"}))
    protocolo = forms.CharField(
        label="Protocolo", help_text="Nove dígitos, com ou sem pontuação.",
        widget=forms.TextInput(attrs={"class": "entrada", "data-mascara": "protocolo",
                                      "inputmode": "numeric", "placeholder": "12.345.678-9"}),
    )
    data_oficio = forms.DateField(label="Data do ofício", input_formats=FORMATOS_DATA,
                                  widget=EntradaData())
    destino = forms.ChoiceField(
        label="Destino (órgão)",
        choices=[("", "Selecione…"), ("dga", "Gabinete do Delegado-Geral Adjunto Administrativo"),
                 ("dg", "Delegacia-Geral"), ("gaf", "Grupo Auxiliar Financeiro")],
        widget=Selecao(),
    )
    observacao = forms.CharField(label="Observação", required=False,
                                 widget=forms.Textarea(attrs={"class": "area-texto", "rows": 3}))
    ciente = forms.BooleanField(
        label="Declaro que os servidores possuem cartão corporativo vigente", required=False
    )


class FormularioSeletores(forms.Form):
    """Calendário, relógio, data + hora e lista própria (seção 3 do laboratório)."""

    data_saida = forms.DateField(label="Data de saída", input_formats=FORMATOS_DATA,
                                 widget=EntradaData())
    hora_saida = forms.TimeField(label="Hora de saída", widget=EntradaHora())
    saida = forms.DateTimeField(label="Saída de Curitiba/PR", input_formats=FORMATOS_DATA_HORA,
                                widget=EntradaDataHora())
    ordem = forms.ChoiceField(
        label="Ordenar por", widget=Selecao(),
        choices=[("-numero", "Número (mais recente)"), ("numero", "Número (mais antigo)"),
                 ("saida", "Data de saída (próximas)"), ("-saida", "Data de saída (recentes)")])
    retorno = forms.DateTimeField(
        label="Chegada na sede", input_formats=FORMATOS_DATA_HORA, widget=EntradaDataHora(),
        error_messages={"invalid": "Informe data e hora, ex.: 08/10/2026 09:00."})


MUNICIPIOS = [
    "Curitiba", "Londrina", "Maringá", "Ponta Grossa", "Cascavel", "São José dos Pinhais",
    "Foz do Iguaçu", "Colombo", "Guarapuava", "Paranaguá", "Araucária", "Toledo", "Apucarana",
    "Pinhais", "Campo Largo", "Arapongas", "Almirante Tamandaré", "Umuarama", "Cianorte",
    "Rio Branco do Ivaí",
]


def _itinerario_exemplo() -> dict:
    """O itinerário 2.0 de verdade (ADR 0016), com uma ida e volta de exemplo."""
    from gestao.cadastros.models import Municipio
    from gestao.viagens import itinerario

    sede = Municipio.objects.filter(nome="Curitiba", uf="PR").first()
    destinos = [{"uf": "PR", "cidade": "Ponta Grossa/PR", "ORDER": 1,
                 "saida": "2026-10-08T07:00", "tempo_viagem": "02:00",
                 "tempo_adicional": "00:15"}]
    retorno = {"saida": "2026-10-09T16:00", "tempo_viagem": "02:00", "tempo_adicional": "00:15"}
    itin = itinerario.com_iniciais("lab-itin", QueryDict(), destinos=destinos, retorno=retorno,
                                   sede=sede)
    return itin.contexto()


def indice(request: HttpRequest) -> HttpResponse:
    form_vazio = FormularioExemplo()
    # Prefixo: os mesmos campos aparecem duas vezes na página (padrão e erro) sem ids repetidos.
    form_erro = FormularioExemplo(
        prefix="erro", data={"erro-nome": "", "erro-protocolo": "123", "erro-destino": ""}
    )
    form_erro.is_valid()
    form_seletores = FormularioSeletores(initial={
        "data_saida": "08/10/2026", "hora_saida": "09:00", "saida": "2026-10-08T09:00",
        "ordem": "-numero"})
    form_seletores_erro = FormularioSeletores(data={"retorno_0": "10/10/2026", "retorno_1": "25"})
    form_seletores_erro.is_valid()
    linhas = [
        {"numero": f"{n:02d}/2026", "destino": d, "servidores": s, "valor": v, "status": st}
        for n, d, s, v, st in [
            (131, "Arapongas/PR", "Ana Beatriz Correia Lima, Bruno Henrique Martins", 2411.56,
             ("Emitido", "sucesso")),
            (129, "Antonina/PR", "Carla Regina Duarte", 2324.40,
             ("Pronto para emitir", "marca")),
            (128, "—", "—", 0, ("Rascunho", "neutro")),
            (127, "Rio Branco do Ivaí/PR",
             "Diego Fernandes Rocha, Elaine Cristina Moraes, "
             "Fábio Augusto Teixeira, Gabriela Nunes Ribeiro", 1336.54,
             ("Justificativa pendente", "aviso")),
            (126, "Fortaleza/CE", "Henrique Lopes Batista", 853.90, ("Cancelado", "perigo")),
        ]
    ]
    pagina = Paginator(range(1, 241), 20).get_page(request.GET.get("pagina", 5))
    contexto = {
        "tons_status": TONS_STATUS,
        "form_vazio": form_vazio,
        "form_erro": form_erro,
        "form_seletores": form_seletores,
        "form_seletores_erro": form_seletores_erro,
        "linhas": linhas,
        "page_obj": pagina,
        "querystring_base": "",
        "municipios": MUNICIPIOS,
        "migalhas": [("Início", "/"), ("Design System", "/ui-lab/"), ("UI Lab", "")],
        **_itinerario_exemplo(),
    }
    return render(request, "ui_lab/indice.html", contexto)


def busca_exemplo(request: HttpRequest) -> HttpResponse:
    """Fonte remota de exemplo para o combobox do laboratório."""
    from django.http import JsonResponse

    termo = (request.GET.get("q") or "").lower()
    resultados = [
        {"id": str(i), "titulo": nome.upper(), "meta": "Agente de Polícia Judiciária • DM"}
        for i, nome in enumerate(["Ana Beatriz Correia Lima", "Bruno Henrique Martins",
                                  "Carla Regina Duarte", "Diego Fernandes Rocha"])
        if termo in nome.lower()
    ]
    return JsonResponse({"resultados": resultados})
