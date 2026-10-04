"""UI Lab: vitrine viva do Design System.

Cada componente aparece em todos os estados (padrão, hover/foco via
interação real, ativo, desabilitado, carregando, erro, sucesso, vazio,
conteúdo longo). Os testes visuais e de acessibilidade percorrem esta página
nas larguras de referência antes de qualquer tela de negócio.
"""

from __future__ import annotations

from django import forms
from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, QueryDict
from django.middleware.csp import get_nonce
from django.shortcuts import render
from django.utils.csp import CSP
from django.views.decorators.csp import csp_override

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


# ---------------------------------------------------------------- editor de documento (ADR 0018)
DADOS_FOLHA_EXEMPLO = {
    "numero": "00/2026", "ano": 2026, "data_oficio": "01/10/2026", "protocolo": "00.000.000-0",
    "assunto": "Solicitação de autorização e concessão de diárias.",
    "assunto_rotulo": "(Autorização)", "assunto_termo": "autorização",
    "origem": "Assessoria de Comunicação Social", "unidade_sigla": "ASCOM",
    "destinatario": {"tratamento": "Ao Senhor", "nome": "Delegado Fictício de Exemplo",
                     "cargo": "Delegado-Geral Adjunto", "orgao": "Gabinete do Delegado-Geral",
                     "cidade": "Curitiba/PR"},
    "chefia": {"nome": "Chefia Fictícia de Exemplo", "cargo": "Delegada de Polícia"},
    "cabecalho_unidade": "ASSESSORIA DE COMUNICAÇÃO SOCIAL",
    "rodape": "Rua Fictícia, 100 - Centro - Curitiba/PR - CEP 80000-000",
    "viajantes": [{"nome": "Ana Fictícia Almeida", "cpf": "000.000.000-00", "rg": "0",
                   "cargo": "Investigadora de Polícia", "motorista": True},
                  {"nome": "Bruno Fictício Barbosa", "cpf": "000.000.000-00", "rg": "0",
                   "cargo": "Escrivão de Polícia", "motorista": False}],
    "destinos": ["Londrina/PR"],
    "ida": [{"origem": "Curitiba/PR", "destino": "Londrina/PR",
             "saida": {"data": "08/10/2026", "hora": "07:00"},
             "chegada": {"data": "08/10/2026", "hora": "12:30"}}],
    "volta": [{"origem": "Londrina/PR", "destino": "Curitiba/PR",
               "saida": {"data": "09/10/2026", "hora": "14:00"},
               "chegada": {"data": "09/10/2026", "hora": "19:30"}}],
    "bate_volta": False, "trechos": [],
    "transporte": {"meio": "Viatura (exemplo)", "placa": "ZZZ-0000", "combustivel": "Flex",
                   "viatura": "Caracterizada", "oficial": True},
    "motorista": "Ana Fictícia Almeida", "porte_arma": True, "custeio": "unidade",
    "custeio_instituicao": "", "motivo": "Cobertura de evento institucional (exemplo).",
    "diarias": {"resumo": "1 x 100% + 1 x 30%", "total": "R$ 377,72",
                "total_decimal": "377.72", "extenso": "trezentos e setenta e sete reais",
                "calculo": {}},
    "justificativa": "", "prazo": {"dias": 7, "prazo": 10, "obrigatoria": True},
    "emitido_em": "01/10/2026 09:00",
}


@csp_override({**settings.SECURE_CSP, "frame-ancestors": [CSP.SELF],
               "style-src": [CSP.SELF, CSP.NONCE]})
def folha_exemplo(request: HttpRequest) -> HttpResponse:
    """A folha do ofício com dados fictícios, para a vitrine do editor (nada é salvo)."""
    from gestao.viagens.documentos.pdf import html_do_documento

    preguicoso = get_nonce(request)
    nonce = str(preguicoso) if preguicoso is not None else ""
    return HttpResponse(html_do_documento("oficio", DADOS_FOLHA_EXEMPLO, previa=True,
                                          folha=True, nonce=nonce))


def baixar_exemplo(request: HttpRequest) -> HttpResponse:
    """Vitrine da janela "Baixar documentos": itens fictícios (GET) e um arquivo de texto
    no lugar do pacote (POST) — nada é gerado nem lido do banco."""
    from django.http import JsonResponse

    if request.method == "GET":
        return JsonResponse({"itens": [
            {"valor": "oficio", "nome": "Ofício", "detalhe": "Ofício 131/2026",
             "estado": "Assinado", "assinado": True},
            {"valor": "justificativa", "nome": "Justificativa", "detalhe": "Justificativa de prazo",
             "estado": "PDF emitido · v1", "assinado": False},
            {"valor": "termo-1", "nome": "Termo · Servidora Fictícia", "detalhe": "Termo #1",
             "estado": "Gerado na hora", "assinado": False},
        ]})
    resposta = HttpResponse("Vitrine do UI Lab: nenhum documento foi gerado.\n",
                            content_type="text/plain; charset=utf-8")
    resposta["Content-Disposition"] = 'attachment; filename="ui-lab-exemplo.txt"'
    return resposta
