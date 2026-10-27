"""Texto da Ordem de Serviço padrão (Python puro, sem Django) e os dados que ela e os
modelos cadastrados (`modelo_os.py`) usam.

O texto padrão é o da referência (`viagens_ordens/docxtpl_context.py`), que avisa: "são os
mesmos, letra por letra: entram no documento assinado". A montagem (quem vai, com que cargo,
para onde e quando) é reescrita aqui sobre dados simples. Os antigos tipos com função
(caminhão, micro-ônibus, cerimonial, operação policial) viram modelos do sistema
(`viagens/modelos_do_sistema.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from itertools import groupby

from .escrita import MESES, data_por_extenso, lista_com_e
from .escrita import eh_sigla as _sigla
from .escrita import plural_palavra as _plural

PADRAO = "padrao"

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
    # Só os modelos cadastrados usam (dominio/modelo_os.py): o período do evento dentro da
    # viagem, o horário do briefing e a sede ("Curitiba/PR") para o retorno.
    evento_inicio: date | None = None
    evento_fim: date | None = None
    hora: time | None = None
    sede: str = ""




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
            # Sem cargo, o nome entra direto — mas a frase ainda pede o "de" ("O
            # deslocamento de Fulano para…").
            partes.append(f"de {lista_com_e(nomes)}" if primeiro else lista_com_e(nomes))
        elif len(nomes) == 1:
            partes.append(f"{'do' if primeiro else 'o'} {cargo_no_texto(cargo, plural=False)} "
                          f"{nomes[0]}")
        else:
            partes.append(f"{'dos' if primeiro else 'os'} {cargo_no_texto(cargo, plural=True)} "
                          f"{lista_com_e(nomes)}")
    return lista_com_e(partes)


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


def textos_da_os(dados: DadosOS) -> dict:
    """O texto padrão: referência, determinação (parágrafo único) e finalidade."""
    municipios = municipios_no_texto(dados.destinos)
    motivo = motivo_no_texto(dados.motivo) or "atuação na atividade institucional designada"
    periodo = periodo_por_extenso(dados.inicio, dados.fim)
    equipe = equipe_no_texto(dados.equipe)
    textos: dict = {
        "referencia": "Diligências",
        "determinacao": (f"O deslocamento {equipe} para {municipios}, "
                         + (f"{periodo}, " if periodo else "") + f"para realizar {motivo}."),
        "competencias": [],
        "justificativas": [],
        "finalidade": ("A presente Ordem de Serviço tem por finalidade garantir a execução da "
                       "atividade designada, com observância às normas administrativas "
                       "aplicáveis."),
    }
    return textos
