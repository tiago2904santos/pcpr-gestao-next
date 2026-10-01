"""UI Lab: vitrine viva do Design System.

Cada componente aparece em todos os estados (padrão, hover/foco via
interação real, ativo, desabilitado, carregando, erro, sucesso, vazio,
conteúdo longo). Os testes visuais e de acessibilidade percorrem esta página
nas larguras de referência antes de qualquer tela de negócio.
"""

from __future__ import annotations

from django import forms
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

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
                                      "inputmode": "numeric", "placeholder": "26.655.434-6"}),
    )
    data_oficio = forms.DateField(label="Data do ofício",
                           widget=forms.DateInput(attrs={"class": "entrada", "type": "date"}))
    destino = forms.ChoiceField(
        label="Destino (órgão)",
        choices=[("", "Selecione…"), ("dga", "Gabinete do Delegado-Geral Adjunto Administrativo"),
                 ("dg", "Delegacia-Geral"), ("gaf", "Grupo Auxiliar Financeiro")],
        widget=forms.Select(attrs={"class": "selecao"}),
    )
    observacao = forms.CharField(label="Observação", required=False,
                                 widget=forms.Textarea(attrs={"class": "area-texto", "rows": 3}))
    ciente = forms.BooleanField(
        label="Declaro que os servidores possuem cartão corporativo vigente", required=False
    )


MUNICIPIOS = [
    "Curitiba", "Londrina", "Maringá", "Ponta Grossa", "Cascavel", "São José dos Pinhais",
    "Foz do Iguaçu", "Colombo", "Guarapuava", "Paranaguá", "Araucária", "Toledo", "Apucarana",
    "Pinhais", "Campo Largo", "Arapongas", "Almirante Tamandaré", "Umuarama", "Cianorte",
    "Rio Branco do Ivaí",
]


def indice(request: HttpRequest) -> HttpResponse:
    form_vazio = FormularioExemplo()
    form_erro = FormularioExemplo(
        data={"nome": "", "protocolo": "123", "destino": ""}
    )
    form_erro.is_valid()
    for nome in form_erro.errors:
        if nome in form_erro.fields:
            form_erro.fields[nome].widget.attrs["aria-invalid"] = "true"
    linhas = [
        {"numero": f"{n:03d}/2026", "destino": d, "servidores": s, "valor": v, "status": st}
        for n, d, s, v, st in [
            (131, "Arapongas/PR", "Gilberto Reinaldo Müller Junior, Sylvio Piva Junior", 2411.56,
             ("Emitido", "sucesso")),
            (129, "Antonina/PR", "Fabiano Rodrigo Teixeira Pinto", 2324.40,
             ("Pronto para emitir", "marca")),
            (128, "—", "—", 0, ("Rascunho", "neutro")),
            (127, "Rio Branco do Ivaí/PR",
             "Adilson José Domingues, Adriano Rodrigues da Silva, Aluízio Sebastião Crespo de "
             "Oliveira Junior, Vanderlim Cezar Rodrigues", 1336.54,
             ("Justificativa pendente", "aviso")),
            (126, "Fortaleza/CE", "Eliott Souza Cabral", 853.90, ("Cancelado", "perigo")),
        ]
    ]
    pagina = Paginator(range(1, 241), 20).get_page(request.GET.get("pagina", 5))
    contexto = {
        "tons_status": TONS_STATUS,
        "form_vazio": form_vazio,
        "form_erro": form_erro,
        "linhas": linhas,
        "page_obj": pagina,
        "querystring_base": "",
        "municipios": MUNICIPIOS,
        "migalhas": [("Início", "/"), ("Design System", "/ui-lab/"), ("UI Lab", "")],
    }
    return render(request, "ui_lab/indice.html", contexto)


def busca_exemplo(request: HttpRequest) -> HttpResponse:
    """Fonte remota de exemplo para o combobox do laboratório."""
    from django.http import JsonResponse

    termo = (request.GET.get("q") or "").lower()
    resultados = [
        {"id": str(i), "titulo": nome.upper(), "meta": "Agente de Polícia Judiciária • DM"}
        for i, nome in enumerate(["Gilberto Reinaldo Müller Junior", "Sylvio Piva Junior",
                                  "Fabiano Rodrigo Teixeira Pinto", "Adilson José Domingues"])
        if termo in nome.lower()
    ]
    return JsonResponse({"resultados": resultados})
