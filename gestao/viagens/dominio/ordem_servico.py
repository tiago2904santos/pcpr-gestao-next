"""Textos da Ordem de Serviço por tipo de necessidade (Python puro, sem Django).

Os textos são os da referência (`viagens_ordens/docxtpl_context.py`), que avisa: "são os
mesmos, letra por letra: entram no documento assinado". A montagem (quem vai, com que cargo,
para onde e quando) é reescrita aqui sobre dados simples.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from itertools import groupby

from .escrita import MESES, data_por_extenso, lista_com_e
from .escrita import eh_sigla as _sigla
from .escrita import plural_palavra as _plural

PADRAO = "padrao"
OPERACAO_RETORNO_POSTERIOR = "operacao_retorno_posterior"
CAMINHAO = "caminhao"
MICROONIBUS = "microonibus"
CERIMONIAL_ANTECIPADO = "cerimonial_antecipado"

TIPOS = (
    (PADRAO, "Padrão / texto livre"),
    (OPERACAO_RETORNO_POSTERIOR, "Operação policial - um dia posterior"),
    (CAMINHAO, "Caminhão - dois dias antes e depois"),
    (MICROONIBUS, "Micro-ônibus"),
    (CERIMONIAL_ANTECIPADO, "Cerimonial - ida antecipada"),
)

CONDUCAO, TECNICO, APOIO, COORDENACAO, PREPARACAO = (
    "conducao", "tecnico", "apoio", "coordenacao", "preparacao")
FUNCOES = ((CONDUCAO, "Condução (motorista)"), (TECNICO, "Técnico"),
           (APOIO, "Apoio (montagem, escolta)"), (COORDENACAO, "Coordenação (cerimonial)"),
           (PREPARACAO, "Preparação"))

# Tipos em que cada um da equipe recebe uma função, e quais funções cada um usa.
FUNCOES_DO_TIPO = {
    CAMINHAO: (CONDUCAO, TECNICO, APOIO),
    MICROONIBUS: (CONDUCAO, TECNICO, APOIO),
    CERIMONIAL_ANTECIPADO: (COORDENACAO, APOIO, PREPARACAO),
}


@dataclass(frozen=True)
class Pessoa:
    id: int
    nome: str
    cargo: str = ""


@dataclass
class DadosOS:
    tipo: str = PADRAO
    destinos: list[str] = field(default_factory=list)   # "Cidade/UF", na ordem
    inicio: date | None = None
    fim: date | None = None
    motivo: str = ""
    equipe: list[Pessoa] = field(default_factory=list)
    funcoes: dict[int, str] = field(default_factory=dict)  # id da pessoa -> função




def periodo_por_extenso(inicio: date | None, fim: date | None) -> str:
    """"no dia 10 de julho de 2026", "nos dias 10 a 12 de julho de 2026" (texto da OS)."""
    if not inicio:
        return ""
    if not fim or fim == inicio:
        return f"no dia {data_por_extenso(inicio)}"
    if (inicio.month, inicio.year) == (fim.month, fim.year):
        return f"nos dias {inicio.day} a {fim.day} de {MESES[inicio.month - 1]} de {inicio.year}"
    return f"nos dias {data_por_extenso(inicio)} a {data_por_extenso(fim)}"


def cargo_no_texto(nome: str, *, plural: bool) -> str:
    """"Agente de Polícia Judiciária" -> "agentes de polícia judiciária" (siglas mantidas)."""
    saida = []
    for i, palavra in enumerate(nome.split()):
        if _sigla(palavra):
            saida.append(palavra)
        elif i == 0 and plural:
            saida.append(_plural(palavra.lower()))
        else:
            saida.append(palavra.lower())
    return " ".join(saida)


def equipe_no_texto(equipe: list[Pessoa]) -> str:
    """"do agente de polícia judiciária Fulano e os escrivães de polícia A e B" (por cargo)."""
    if not equipe:
        return "da equipe"
    sem_cargo = "￿"
    ordenada = sorted(equipe, key=lambda p: (p.cargo or sem_cargo, p.nome))
    partes: list[str] = []
    for cargo, grupo in groupby(ordenada, key=lambda p: p.cargo or sem_cargo):
        nomes = [p.nome for p in grupo]
        primeiro = not partes
        if cargo == sem_cargo:
            partes.append(lista_com_e(nomes))
        elif len(nomes) == 1:
            partes.append(f"{'do' if primeiro else 'o'} {cargo_no_texto(cargo, plural=False)} "
                          f"{nomes[0]}")
        else:
            partes.append(f"{'dos' if primeiro else 'os'} {cargo_no_texto(cargo, plural=True)} "
                          f"{lista_com_e(nomes)}")
    return lista_com_e(partes)


def _por_funcao(dados: DadosOS, funcao: str) -> list[str]:
    return [p.nome for p in dados.equipe if dados.funcoes.get(p.id) == funcao]


def _competencia(nomes: list[str], texto: str) -> str:
    if not nomes:
        return ""
    return f"{lista_com_e(nomes)}{' – ' if len(nomes) == 1 else ': '}{texto}"


def _competencias(dados: DadosOS, textos: dict[str, str]) -> list[str]:
    return [c for c in (_competencia(_por_funcao(dados, f), t) for f, t in textos.items()) if c]


def motivo_no_texto(motivo: str) -> str:
    """O motivo entra no meio da frase ("… para realizar ___."): sem o ponto final e com a
    inicial minúscula (o do ofício costuma ser uma frase solta). Sigla fica como está."""
    texto = " ".join((motivo or "").split()).rstrip(" .;")
    if not texto:
        return ""
    primeira = texto.split()[0]
    if not _sigla(primeira) and not (len(primeira) > 1 and primeira[1].isupper()):
        texto = texto[0].lower() + texto[1:]
    return texto


def municipios_no_texto(destinos: list[str]) -> str:
    """"o município de A" / "os municípios de A e B" (depois de "para")."""
    if len(destinos) > 1:
        return f"os municípios de {lista_com_e(destinos)}"
    return f"o município de {destinos[0] if destinos else 'destino informado'}"


def faltam_funcoes(dados: DadosOS) -> bool:
    """Tipo com função e ninguém da equipe com função: o texto sairia sem atribuições."""
    return dados.tipo in FUNCOES_DO_TIPO and bool(dados.equipe) and not any(
        dados.funcoes.get(p.id) for p in dados.equipe)


# Como cada tipo continua a frase depois do motivo (ajuda do campo na tela).
FRASE_DO_MOTIVO = {
    PADRAO: "… para realizar ___.",
    OPERACAO_RETORNO_POSTERIOR: "… para atuação em operação policial relacionada a ___.",
    CAMINHAO: "… para apoio logístico com caminhão em ___.",
    MICROONIBUS: "… para apoio logístico com micro-ônibus em ___.",
    CERIMONIAL_ANTECIPADO: "… para atuação na organização e realização de ___.",
}

# O que cada tipo faz com o documento (ajuda do campo "Tipo de necessidade").
EFEITO_DO_TIPO = {
    PADRAO: "Texto simples: quem vai, para onde, quando e para quê.",
    OPERACAO_RETORNO_POSTERIOR: "Justifica um dia a mais depois da operação. Confira se o "
                                "período inclui esse dia.",
    CAMINHAO: "Atribuições por função (condução, técnico, apoio) e justificativa de dois dias "
              "antes e dois depois do evento. Confira se o período cobre isso.",
    MICROONIBUS: "Atribuições por função (condução, técnico, apoio).",
    CERIMONIAL_ANTECIPADO: "Atribuições por função (coordenação, apoio, preparação) e "
                           "justificativa da ida antecipada. Confira o período.",
}


def textos_da_os(dados: DadosOS) -> dict:
    """Referência, determinação, competências da equipe, justificativas e finalidade."""
    municipios = municipios_no_texto(dados.destinos)
    motivo = motivo_no_texto(dados.motivo) or "atuação na atividade institucional designada"
    periodo = periodo_por_extenso(dados.inicio, dados.fim)
    equipe = equipe_no_texto(dados.equipe)
    textos: dict = {
        "referencia": "Diligências",
        "determinacao": (f"O deslocamento {equipe} para {municipios}, {periodo}, "
                         f"para realizar {motivo}."),
        "competencias": [],
        "justificativas": [],
        "finalidade": ("A presente Ordem de Serviço tem por finalidade garantir a execução da "
                       "atividade designada, com observância às normas administrativas "
                       "aplicáveis."),
    }
    if dados.tipo == OPERACAO_RETORNO_POSTERIOR:
        textos.update({
            "referencia": "Deslocamento - Operação policial com um dia posterior",
            "determinacao": (f"O deslocamento {equipe} para {municipios}, "
                             f"{periodo}, para atuação em operação policial relacionada a "
                             f"{motivo}."),
            "justificativas": [
                "A concessão de um dia posterior justifica-se pelo fato de que as atividades "
                "planejadas para a operação policial abrangem desde a produção de material "
                "jornalístico durante o briefing e o acompanhamento do cumprimento dos mandados "
                "judiciais, até a prestação de assessoria de imprensa pós-operação, incluindo a "
                "condução de entrevistas coletivas e o atendimento às demandas dos veículos de "
                "comunicação. Diante disso, evidencia-se a necessidade de permanência da equipe "
                "policial na referida localidade mesmo após a conclusão das diligências "
                "operacionais.",
            ],
            "finalidade": ("A presente Ordem de Serviço tem por finalidade assegurar a cobertura "
                           "jornalística, a assessoria de imprensa e o atendimento às demandas "
                           "de comunicação vinculadas à operação policial."),
        })
    elif dados.tipo == CAMINHAO:
        destino_caminhao = lista_com_e(dados.destinos) or "município de destino"
        competencias = _competencias(dados, {
            CONDUCAO: (
                "conduzir a Unidade Móvel (caminhão), realizando o deslocamento desde o local "
                "onde o veículo estiver estacionado até o município de destino e, ao término "
                "das atividades, o retorno ao local de guarda do veículo, computando-se todo o "
                "percurso. Caberá, ainda, prestar apoio às atividades de instalação, "
                "posicionamento, operação e desmontagem da estrutura da Unidade Móvel."),
            TECNICO: (
                "prestar apoio técnico na instalação, configuração, testes e operação dos "
                "equipamentos de informática, rede lógica, comunicação e demais sistemas "
                "utilizados durante os atendimentos. Deverá deslocar-se antecipadamente ao "
                "local do evento para verificar as condições de fornecimento de energia "
                "elétrica, conectividade de internet e infraestrutura necessária ao "
                "funcionamento da Unidade Móvel, considerando que, em razão da dinâmica da "
                "operação, não foi possível a realização de visita técnica prévia."),
            APOIO: (
                f"realizar a escolta e o apoio operacional da Unidade Móvel durante todo o "
                f"deslocamento entre Curitiba e {destino_caminhao}, "
                f"bem como no retorno, computando-se todo o trajeto. Deverá auxiliar na "
                f"montagem, organização, manutenção operacional e desmontagem dos equipamentos "
                f"da Unidade Móvel."),
        })
        if not competencias:  # sem função na equipe, o texto padrão (como na referência)
            return textos
        textos.update({
            "referencia": "Deslocamento - Caminhão de apoio",
            "determinacao": (f"O deslocamento da equipe abaixo relacionada para "
                             f"{municipios}, {periodo}, para apoio logístico com caminhão em "
                             f"{motivo}, observadas as atribuições a seguir:"),
            "competencias": competencias,
            "justificativas": [
                "O deslocamento do caminhão com dois dias de antecedência faz-se necessário "
                "para viabilizar o traslado, descarga, montagem, conferência técnica e "
                "adequação dos materiais e equipamentos no local do evento.",
                "A permanência por dois dias posteriores ao evento justifica-se pela "
                "necessidade de desmontagem, conferência, acondicionamento, carregamento dos "
                "materiais e retorno do veículo com segurança, preservando os bens públicos "
                "utilizados.",
            ],
            "finalidade": ("A presente Ordem de Serviço tem por finalidade garantir o "
                           "planejamento, a execução e a desmobilização do apoio logístico "
                           "prestado com caminhão."),
        })
    elif dados.tipo == MICROONIBUS:
        textos.update({
            "referencia": "Deslocamento - Micro-ônibus",
            "determinacao": (f"O deslocamento da equipe abaixo relacionada para "
                             f"{municipios}, {periodo}, para apoio logístico com micro-ônibus em "
                             f"{motivo}, observadas as atribuições a seguir:"),
            "competencias": _competencias(dados, {
                CONDUCAO: ("conduzir o micro-ônibus oficial durante os deslocamentos de ida e "
                           "retorno, zelando pela segurança da equipe e dos passageiros"),
                TECNICO: ("prestar suporte técnico à operação dos equipamentos e acompanhar a "
                          "organização dos materiais utilizados na atividade"),
                APOIO: ("prestar apoio operacional à equipe, auxiliando na organização, "
                        "montagem, escolta e movimentação necessárias à realização da "
                        "atividade"),
            }),
            "justificativas": [
                "O micro-ônibus será utilizado para transporte e apoio logístico da equipe, "
                "observando-se o cronograma da atividade, sem necessidade de deslocamento com "
                "dois dias de antecedência ou permanência por dois dias posteriores ao evento.",
            ],
            "finalidade": ("A presente Ordem de Serviço tem por finalidade garantir o "
                           "transporte, a organização e o apoio logístico necessários à "
                           "realização da atividade."),
        })
    elif dados.tipo == CERIMONIAL_ANTECIPADO:
        textos.update({
            "referencia": "Deslocamento - Equipe de Cerimonial",
            "determinacao": (f"O deslocamento da equipe abaixo relacionada para "
                             f"{municipios}, {periodo}, para atuação na organização e realização "
                             f"de {motivo}, observadas as atribuições a seguir:"),
            "competencias": _competencias(dados, {
                COORDENACAO: (
                    "conduzir o veículo oficial durante o deslocamento de ida e retorno, bem "
                    "como coordenar as atividades de Cerimonial, supervisionando os "
                    "procedimentos protocolares, a recepção das autoridades, a composição do "
                    "dispositivo de honra e a execução do roteiro oficial"),
                APOIO: ("prestar apoio às atividades de Cerimonial, auxiliando na organização "
                        "do ambiente, recepção das autoridades e execução dos procedimentos "
                        "protocolares"),
                PREPARACAO: ("auxiliar na preparação da solenidade, conferência dos materiais, "
                             "organização dos espaços e demais atividades necessárias à "
                             "realização do evento"),
            }),
            "justificativas": [
                "O deslocamento da equipe com dois dias de antecedência faz-se necessário, "
                "sendo o primeiro destinado ao deslocamento até o município do evento e o "
                "segundo à organização dos trabalhos, em razão da inexistência de visita "
                "técnica prévia.",
                "A permanência da equipe permitirá verificar a estrutura do local, sistema de "
                "sonorização, disposição do palco, púlpito, bandeiras, autoridades e convidados, "
                "decoração, acessos e demais aspectos logísticos, possibilitando os ajustes "
                "necessários para assegurar a adequada realização da solenidade.",
            ],
            "finalidade": ("A presente Ordem de Serviço tem por finalidade garantir o "
                           "planejamento, a organização e a execução das atividades de "
                           "Cerimonial, assegurando o cumprimento das normas de protocolo e a "
                           "realização do evento institucional com eficiência e observância aos "
                           "padrões da Polícia Civil do Paraná."),
        })
    return textos
