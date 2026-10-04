"""Regras e textos do plano de trabalho (Python puro, sem Django).

Os textos do documento são os da referência (`viagens_planos/services.py`): contextualização
e considerações finais automáticas, a designação dos coordenadores com concordância de
gênero, as listas de atividades, metas e recursos, o efetivo por cargo e o valor das
diárias. A montagem é reescrita aqui sobre dados simples.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from . import diarias as motor
from .escrita import MESES, cargo_no_plural, legivel, moeda
from .extenso import reais_por_extenso

VAZIO = "________"
HORARIO_PADRAO = "09:00 até 17:00"
UNIDADE_MOVEL = "UNIDADE_MOVEL"
ESTRUTURA_UNIDADE_MOVEL = ("Estrutura: Unidade móvel da PCPR equipada para atendimento e "
                           "confecção de documentos.")
RECURSO_UNIDADE_MOVEL = "Prever unidade móvel institucional e o suporte operacional associado."
MASCULINO, FEMININO = "M", "F"


# ---------------------------------------------------------------- dados
@dataclass(frozen=True)
class Coordenador:
    nome: str
    cargo: str = ""
    genero: str = MASCULINO  # "M" ou "F"

    @property
    def feminino(self) -> bool:
        return self.genero == FEMININO


@dataclass(frozen=True)
class Atividade:
    codigo: str
    nome: str
    meta: str
    recurso: str = ""


@dataclass(frozen=True)
class LinhaEfetivo:
    quantidade: int
    cargo: str
    sigla_unidade: str = ""
    unidade: str = ""  # nome, para ordenar


@dataclass
class DadosPlano:
    """O que as regras precisam saber de um plano de um evento."""

    destinos: list[str] = field(default_factory=list)  # "Cidade/UF", o 1º é o principal
    inicio: date | None = None
    fim: date | None = None
    programa: str = ""
    coordenador_adm: Coordenador | None = None
    coordenador_op: Coordenador | None = None
    efetivo: list[LinhaEfetivo] = field(default_factory=list)
    diarias_total: Decimal | None = None
    tem_deslocamento: bool = False  # saída e chegada na sede informadas
    tem_atividades: bool = False
    # Eventos adicionais (o 1 são os campos do plano): (número, tem destino, tem data).
    eventos_extras: list[tuple[int, bool, bool]] = field(default_factory=list)


# ---------------------------------------------------------------- períodos
def _dia(d: date) -> str:
    return f"{d.day:02d}"


def periodo_por_extenso(inicio: date | None, fim: date | None) -> str:
    """"25 de junho de 2026", "25 a 27 de junho de 2026", "30 de junho a 02 de julho de
    2026", "30 de dezembro de 2025 a 02 de janeiro de 2026" (referência)."""
    if not inicio:
        return ""
    fim = fim or inicio
    if fim == inicio:
        return f"{_dia(inicio)} de {MESES[inicio.month - 1]} de {inicio.year}"
    if (inicio.month, inicio.year) == (fim.month, fim.year):
        return f"{_dia(inicio)} a {_dia(fim)} de {MESES[fim.month - 1]} de {fim.year}"
    if inicio.year == fim.year:
        return (f"{_dia(inicio)} de {MESES[inicio.month - 1]} a {_dia(fim)} de "
                f"{MESES[fim.month - 1]} de {fim.year}")
    return (f"{_dia(inicio)} de {MESES[inicio.month - 1]} de {inicio.year} a {_dia(fim)} de "
            f"{MESES[fim.month - 1]} de {fim.year}")


def cabecalho_do_evento(inicio: date | None, fim: date | None) -> str:
    """"Dia 06 de outubro de 2026" / "Dias 08 a 09 de outubro de 2026" (vários eventos)."""
    if not inicio:
        return "Data a definir"
    prefixo = "Dia" if not fim or fim == inicio else "Dias"
    return f"{prefixo} {periodo_por_extenso(inicio, fim)}"


def rotulo_do_total(inicio: date | None, fim: date | None) -> str:
    """"Valor total do evento dia: 17/06/2026" / "… dias: 06 a 09/10/2026" / "… dias:
    30/06/2026 a 02/07/2026" (referência)."""
    if not inicio:
        return "Valor total"
    fim = fim or inicio
    if fim == inicio:
        return f"Valor total do evento dia: {inicio:%d/%m/%Y}"
    if (inicio.month, inicio.year) == (fim.month, fim.year):
        return f"Valor total do evento dias: {inicio:%d} a {fim:%d/%m/%Y}"
    return f"Valor total do evento dias: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"


def periodo_curto(inicio: date | None, fim: date | None) -> str:
    if not inicio:
        return ""
    fim = fim or inicio
    return f"{inicio:%d/%m/%Y}" if fim == inicio else f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"


# ---------------------------------------------------------------- textos automáticos
def _municipios(destinos: list[str]) -> str:
    unicos = list(dict.fromkeys(d for d in destinos if d))
    return ", ".join(unicos) or VAZIO


def contextualizacao(destinos: list[str], programas: list[str]) -> str:
    """Três parágrafos (separados por linha em branco), como na referência."""
    programa = ", ".join(dict.fromkeys(legivel(p) for p in programas if p)) or VAZIO
    return "\n\n".join((
        "A Assessoria de Comunicação Social da Polícia Civil do Paraná (PCPR), no âmbito do "
        "programa “PCPR na Comunidade”, promoverá ação itinerante no município de "
        f"{_municipios(destinos)}.",
        f"A iniciativa visa atender à solicitação formulada pelo {programa} (Ofício em anexo), "
        "levando serviços essenciais de polícia judiciária às populações urbanas, rurais e "
        "ribeirinhas, especialmente em localidades de difícil acesso.",
        "A ação tem como foco principal garantir o acesso à documentação básica e prestar "
        "orientações de polícia judiciária, promovendo cidadania e fortalecendo a aproximação "
        "institucional com a comunidade.",
    ))


def consideracoes_finais(destinos: list[str]) -> str:
    return (f"A realização da ação no município de {_municipios(destinos)} reforça o compromisso "
            "institucional da Polícia Civil do Paraná com a promoção da cidadania e com a "
            "ampliação do acesso a serviços públicos essenciais, especialmente em regiões com "
            "limitações de deslocamento e maior vulnerabilidade social.")


def _quem(c: Coordenador) -> str:
    artigo = "a" if c.feminino else "o"
    nome = legivel(c.nome)
    return f"{artigo} {legivel(c.cargo)} {nome}" if c.cargo else f"{artigo} {nome}"


def coordenacao(adm: Coordenador | None, op: Coordenador | None, *,
                varios_eventos: bool = False) -> str:
    """Designação dos coordenadores. No plano de vários eventos só o administrativo é
    designado (o operacional muda de evento para evento)."""
    partes = []
    if adm and adm.nome.strip():
        f = adm.feminino
        partes.append(
            f"Fica {'designada' if f else 'designado'} como "
            f"{'Coordenadora Administrativa' if f else 'Coordenador Administrativo'} do Plano "
            f"{_quem(adm)}, {'a' if f else 'o'} qual ficará responsável pelo acompanhamento da "
            "execução administrativa do presente Plano de Trabalho, organização das escalas de "
            "servidores, controle de materiais e equipamentos, consolidação de dados "
            "estatísticos, elaboração de relatório final e demais providências necessárias ao "
            "regular cumprimento da ação.")
    if op and op.nome.strip() and not varios_eventos:
        f = op.feminino
        partes.append(
            f"Fica {'designada' if f else 'designado'} como "
            f"{'Coordenadora Operacional do Evento' if f else 'Coordenador Operacional do Evento'} "
            f"{_quem(op)}, {'a' if f else 'o'} qual ficará responsável pela execução operacional "
            "da ação no local do evento, acompanhamento das equipes e suporte às demandas "
            "surgidas durante o atendimento.")
    return "\n\n".join(partes)


# ---------------------------------------------------------------- atividades e efetivo
def textos_das_atividades(atividades: list[Atividade]) -> dict[str, str]:
    """Atividades, metas e recursos (uma linha "• …" por item, sem repetir), na ordem
    alfabética das atividades; a unidade móvel acrescenta a estrutura e o recurso."""
    ordenadas = sorted(atividades, key=lambda a: a.nome.lower())
    metas = list(dict.fromkeys(a.meta.strip() for a in ordenadas if a.meta.strip()))
    recursos = list(dict.fromkeys(a.recurso.strip() for a in ordenadas if a.recurso.strip()))
    movel = any(a.codigo == UNIDADE_MOVEL for a in ordenadas)
    if movel:
        recursos.append(RECURSO_UNIDADE_MOVEL)
    return {
        "atividades": "\n".join(f"• {a.nome}" for a in ordenadas),
        "metas": "\n".join(f"• {m}" for m in metas),
        "recursos": "\n".join(f"• {r}" for r in recursos),
        "unidade_movel": ESTRUTURA_UNIDADE_MOVEL if movel else "",
    }


def efetivo_total(linhas: list[LinhaEfetivo]) -> int:
    return sum(max(0, linha.quantidade) for linha in linhas if linha.cargo)


def texto_do_efetivo(linhas: list[LinhaEfetivo]) -> str:
    """"6 Policiais Civis (ASCOM)", "1 Papiloscopista" — uma linha por item, por unidade e
    cargo; linha sem quantidade ou sem cargo fica de fora."""
    validas = [lin for lin in linhas if lin.quantidade > 0 and lin.cargo]
    validas.sort(key=lambda lin: ((lin.unidade or lin.sigla_unidade).lower(), lin.cargo.lower()))
    saida = []
    for lin in validas:
        cargo = cargo_no_plural(lin.cargo) if lin.quantidade > 1 else legivel(lin.cargo)
        sufixo = f" ({lin.sigla_unidade})" if lin.sigla_unidade else ""
        saida.append(f"{lin.quantidade} {cargo}{sufixo}")
    return "\n".join(saida)


# ---------------------------------------------------------------- pendências
@dataclass(frozen=True)
class Pendencia:
    mensagem: str
    secao: str  # âncora do cartão onde se resolve
    rotulo: str = ""  # curto, para o selo do cartão ("Falta destino")


def _tratamento_falta(c: Coordenador | None) -> bool:
    return bool(c and c.nome.strip() and c.genero not in (MASCULINO, FEMININO))


def pendencias(d: DadosPlano) -> list[Pendencia]:
    """O que impede gerar o documento, na ordem da referência. A mais: o tratamento do
    coordenador (um padrão "o Coordenador" sairia errado para uma coordenadora); e a
    pendência de diárias só aparece quando é dela mesma (sem destino ou efetivo, já há a
    pendência que a explica)."""
    falta = []
    if not (d.coordenador_adm and d.coordenador_adm.nome.strip()):
        falta.append(Pendencia("Informe o coordenador administrativo.", "identificacao",
                               "Falta coordenador administrativo"))
    elif _tratamento_falta(d.coordenador_adm):
        falta.append(Pendencia("Diga se o administrativo sai como “o Coordenador” ou “a "
                               "Coordenadora”.", "identificacao", "Falta o tratamento"))
    if _tratamento_falta(d.coordenador_op):
        falta.append(Pendencia("Diga se o operacional sai como “o Coordenador” ou “a "
                               "Coordenadora”.", "identificacao", "Falta o tratamento"))
    if not d.destinos:
        falta.append(Pendencia("Informe o destino (cidade/UF).", "identificacao",
                               "Falta destino"))
    if not d.inicio:
        falta.append(Pendencia("Informe a data do evento.", "identificacao",
                               "Falta data do evento"))
    for numero, tem_destino, tem_data in d.eventos_extras:
        if not tem_destino:
            falta.append(Pendencia(f"Informe o destino do evento {numero}.", "eventos",
                                   f"Falta destino do evento {numero}"))
        if not tem_data:
            falta.append(Pendencia(f"Informe a data do evento {numero}.", "eventos",
                                   f"Falta data do evento {numero}"))
    if efetivo_total(d.efetivo) <= 0:
        falta.append(Pendencia("Informe o efetivo (cargo e quantidade).", "efetivo",
                               "Falta efetivo"))
    if d.diarias_total is None and d.destinos and efetivo_total(d.efetivo) > 0:
        if not d.tem_deslocamento:
            falta.append(Pendencia("Informe a saída e a chegada na sede.", "efetivo",
                                   "Falta saída e chegada"))
        else:
            falta.append(Pendencia("As diárias não fecham: veja o cartão Efetivo e diárias.",
                                   "efetivo", "Diárias não calculadas"))
    return falta


def avisos(d: DadosPlano) -> list[Pendencia]:
    """O que não impede gerar, mas sai em branco no documento."""
    saida = []
    if not d.programa.strip():
        saida.append(Pendencia("Sem programa: a contextualização sai com “________”.",
                               "identificacao", "Sem programa"))
    if not d.tem_atividades:
        saida.append(Pendencia("Nenhuma atividade marcada: atividades, metas e recursos saem "
                               "em branco.", "atividades", "Sem atividades"))
    return saida


# ---------------------------------------------------------------- diárias
class PlanoIncalculavel(ValueError):
    """As diárias não fecham; `mensagens` diz tudo o que falta de uma vez."""

    def __init__(self, mensagens: list[str]):
        super().__init__(" ".join(mensagens))
        self.mensagens = mensagens


def calcular_diarias(*, saida: datetime | None, chegada: datetime | None,
                     destino: tuple[str, str] | None, servidores: int, sede: tuple[str, str],
                     buscar_tabelas: Callable[[date], Mapping]) -> motor.CalculoDiarias:
    """Um trecho só: da sede ao destino principal e de volta (os destinos adicionais não
    entram — referência). Usa o motor de diárias do ofício."""
    faltas = []
    if saida is None:
        faltas.append("Informe data e hora de saída da sede.")
    if chegada is None:
        faltas.append("Informe data e hora de chegada na sede.")
    if not destino:
        faltas.append("Informe o destino na identificação.")
    if servidores <= 0:
        faltas.append("Informe o efetivo (cargo e quantidade).")
    if faltas or saida is None or chegada is None or not destino:
        raise PlanoIncalculavel(faltas)
    if chegada <= saida:
        raise PlanoIncalculavel(["A chegada na sede deve ser depois da saída."])
    try:
        return motor.calcular([motor.Destino(destino[0], destino[1], saida)], chegada,
                              buscar_tabelas=buscar_tabelas, servidores=servidores, sede=sede)
    except motor.SemTabelaDeDiarias as exc:
        raise PlanoIncalculavel([str(exc)]) from exc
    except motor.RoteiroIncalculavel as exc:
        raise PlanoIncalculavel([str(exc)]) from exc


def texto_do_valor(composicao: str, unitario: Decimal, total: Decimal) -> str:
    """"Valor total: R$7.234,68 (…). Valor correspondente a 4 x 100% + 1 x 15%, por servidor,
    no valor unitário de R$1.205,78 (…)." — sem espaço depois de "R$", como na referência."""
    return (f"Valor total: R${moeda(total)} ({reais_por_extenso(total)}). Valor correspondente "
            f"a {composicao}, por servidor, no valor unitário de R${moeda(unitario)} "
            f"({reais_por_extenso(unitario)}).")


def numero_formatado(numero: int | None, ano: int | None, sufixo: str = "") -> str:
    """"07/2026/ASCOM"; sem número, "—"."""
    if not numero or not ano:
        return "—"
    return f"{numero:02d}/{ano}" + (f"/{sufixo}" if sufixo else "")


# ---------------------------------------------------------------- resultados (6e)
class RealizadoInvalido(ValueError):
    """O que foi digitado em "Realizado" não é um inteiro ≥ 0 (mensagem pronta)."""


def ler_realizado(texto: str, atividade: str) -> int | None:
    """"1.234" -> 1234 (ponto como milhar); vazio -> None; o resto é recusado com a
    mensagem da referência."""
    limpo = (texto or "").strip().replace(".", "")
    if not limpo:
        return None
    if limpo.startswith("-") and limpo[1:].isascii() and limpo[1:].isdecimal():
        raise RealizadoInvalido(f"{atividade}: O realizado não pode ser negativo.")
    if not (limpo.isascii() and limpo.isdecimal()) or len(limpo) > 9:
        raise RealizadoInvalido(f"{atividade}: \u201c{texto.strip()}\u201d não é um número "
                                "inteiro.")
    return int(limpo)


@dataclass(frozen=True)
class Resultado:
    atividade: str
    realizado: int | None
    observacao: str = ""


def relatorio_final(*, numero: str, programa: str, municipios: list[str], periodo: str,
                    resultados: list[Resultado], consideracoes: str) -> str:
    """O relatório final do plano, montado dos lançamentos (vazio sem lançamento)."""
    lancados = [r for r in resultados if r.realizado is not None or r.observacao.strip()]
    if not lancados:
        return ""
    linhas = [f"Plano de Trabalho {numero}" + (f" \u2014 {programa}" if programa else ""),
              f"Local: {', '.join(municipios) or VAZIO}. Período: {periodo or VAZIO}.", "",
              "Resultados alcançados:"]
    for r in lancados:
        valor = str(r.realizado) if r.realizado is not None else "—"
        obs = f" ({r.observacao.strip()})" if r.observacao.strip() else ""
        linhas.append(f"• {r.atividade}: {valor}{obs}")
    soma = sum(r.realizado or 0 for r in lancados)
    if soma > 0:
        linhas.append(f"Total de atendimentos registrados: {soma}.")
    if consideracoes.strip():
        linhas += ["", consideracoes.strip()]
    return "\n".join(linhas)
