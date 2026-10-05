"""Relatório técnico da prestação de contas em Python puro (paridade com `rt_services`,
`services.aplicar_diaria_recebida`, `core/utils/dinheiro.py` e os textos de custeio da
referência)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .prestacao import somar_dias_uteis

OUTRO = "__outro__"
# Opções fixas de cada custeio (o resto é "Outro", com texto livre) e o padrão.
CUSTEIO = {
    "translado": ("Translado", ("Não houve",), "Não houve"),
    "combustivel": ("Combustível", ("Cartão Prime",), "Cartão Prime"),
    "passagem": ("Passagem", ("Não houve",), "Não houve"),
}
CAMPOS_TEXTO = ("motivo", "atividade", "conclusao", "medidas", "info_complementares")
ROTULOS = {"motivo": "Descrição do evento", "atividade": "Objetivo da participação",
           "conclusao": "Conclusão", "medidas": "Medidas a serem adotadas pelo órgão",
           "info_complementares": "Informações complementares"}
# O tipo de texto pronto de cada campo (cadastros.ModeloTexto.Tipo).
TIPO_DO_CAMPO = {"motivo": "rt_motivo", "atividade": "rt_atividade",
                 "conclusao": "rt_conclusao", "medidas": "rt_medidas",
                 "info_complementares": "rt_info"}
PENDENCIA = ("Escreva a descrição, o objetivo e a conclusão do relatório técnico, ou anexe "
             "o RT assinado.")
DIAS_UTEIS_DEPOIS_DO_RETORNO = 3

_VALOR = re.compile(r"""^\s*(?:R\$)?\s*(?P<inteiro>\d{1,3}(?:\.\d{3})+|\d+)
                        (?:[,.](?P<centavos>\d{1,2}))?\s*(?P<resto>.*)$""",
                    re.VERBOSE | re.IGNORECASE | re.DOTALL)
ERRO_VALOR = ("Informe um valor em reais, como “R$ 87,00”. Se precisar explicar a diferença, "
              "escreva depois do valor: “R$ 87,00 (saque)”.")


class ValorInvalido(ValueError):
    pass


def espacos(texto: object) -> str:
    return " ".join(str(texto or "").split())


def ler_valor(texto: object) -> tuple[Decimal | None, str]:
    """"R$ 87,00 (saque)" → (Decimal("87.00"), "(saque)"); vazio → (None, "")."""
    bruto = str(texto or "").strip()
    if not bruto:
        return None, ""
    m = _VALOR.match(bruto)
    if m is None:
        raise ValorInvalido(ERRO_VALOR)
    resto = m.group("resto").strip()
    if resto[:1].isdigit() or resto[:1] in {",", "."}:
        raise ValorInvalido(ERRO_VALOR)
    centavos = (m.group("centavos") or "").ljust(2, "0")
    return Decimal(f"{m.group('inteiro').replace('.', '')}.{centavos}"), espacos(resto)


def moeda(valor: Decimal) -> str:
    inteiro, centavos = f"{valor:.2f}".split(".")
    grupos: list[str] = []
    while inteiro:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    return f"R$ {'.'.join(grupos)},{centavos}"


def conferir_recebido(valor: Decimal | None, liberado: Decimal | None) -> str:
    """O erro do valor recebido, ou "" (vazio vale: usa o liberado)."""
    if valor is None:
        return ""
    if valor <= 0:
        return "O valor recebido precisa ser maior que zero."
    if liberado is not None and valor > liberado:
        return (f"O valor recebido não pode passar do liberado ({moeda(liberado)}). O servidor "
                "pode receber menos — no saque o caixa não entrega centavos —, nunca mais.")
    return ""


def custeio(campo: str, escolha: str, outro: str = "") -> str | None:
    """O valor a gravar no custeio: a opção fixa, ou o texto de "Outro" (None: não mexe)."""
    _, fixas, _ = CUSTEIO[campo]
    if escolha == OUTRO:
        texto = espacos(outro)
        return texto or None
    return escolha if escolha in fixas else None


def data_do_documento(hoje: date, retorno: date | None,
                      extras: Iterable[date] = ()) -> date:
    """Hoje, mas não antes do retorno e no máximo retorno + 3 dias úteis (referência)."""
    if retorno is None:
        return hoje
    if hoje < retorno:
        return retorno
    return min(hoje, somar_dias_uteis(retorno, DIAS_UTEIS_DEPOIS_DO_RETORNO, extras))


_MARCADOR = re.compile(r"\{(\w+)\}")


def aplicar_marcadores(texto: str, valores: Mapping[str, str]) -> str:
    """{destino}, {periodo}, {motivo}… trocados pelos dados; marcador desconhecido fica."""
    return _MARCADOR.sub(lambda m: valores.get(m.group(1), m.group(0)), texto or "")


def preenchido(textos: Mapping[str, str]) -> bool:
    """Descrição, objetivo e conclusão escritos (o que a finalização cobra)."""
    return all(espacos(textos.get(c)) for c in ("motivo", "atividade", "conclusao"))


# ---------------------------------------------------------------- "Sugerir texto" (9c-2)
# Regra local, sem serviço externo (referência m103): o rascunho sai de modelos de frase com
# o que o sistema já sabe — evento, destino, período, atividades e resultados do plano — e o
# que já está escrito no próprio RT. Só volta para a tela; quem grava é a pessoa.
CAMPOS_SUGERIR = ("conclusao", "medidas")
SINAIS_DE_PENDENCIA = ("pendên", "pendente", "não foi possível", "não pôde", "faltou",
                       "faltaram", "intercorrência", "problema", "dificuldade")


@dataclass(frozen=True)
class Contexto:
    evento: str = ""
    motivo: str = ""
    destino: str = ""
    periodo: str = ""
    atividades: tuple[str, ...] = ()
    realizados: tuple[str, ...] = ()


def listar(itens: Iterable[str], maximo: int = 4) -> str:
    """"a, b e c" — e "a, b, c, d e outras 2" quando a lista é longa."""
    itens = [espacos(i) for i in itens if espacos(i)]
    if not itens:
        return ""
    if len(itens) > maximo:
        return ", ".join(itens[:maximo]) + f" e outras {len(itens) - maximo}"
    if len(itens) == 1:
        return itens[0]
    return ", ".join(itens[:-1]) + f" e {itens[-1]}"


def frase(texto: str) -> str:
    """Primeira letra maiúscula e ponto final, sem dobrar a pontuação."""
    texto = espacos(texto)
    if not texto:
        return ""
    texto = texto[0].upper() + texto[1:]
    return texto if texto[-1] in ".!?" else texto + "."


def _onde_e_quando(ctx: Contexto) -> str:
    partes = []
    if ctx.destino:
        partes.append(f"em {ctx.destino}")
    if ctx.periodo:
        partes.append(("no período de " if " a " in ctx.periodo else "no dia ") + ctx.periodo)
    return ", ".join(partes)


def sugerir_conclusao(ctx: Contexto, textos: Mapping[str, str]) -> str:
    if ctx.evento:
        abertura = f"a participação no evento “{ctx.evento}”"
    elif ctx.motivo:
        abertura = f"a viagem para {ctx.motivo[0].lower() + ctx.motivo[1:]}"
    else:
        abertura = "a viagem"
    onde = _onde_e_quando(ctx)
    # Sem destino nem período, sem a vírgula (a referência deixava "A viagem, foi…").
    frases = [frase(f"{abertura}{', ' + onde + ',' if onde else ''} foi realizada conforme "
                    "o planejado")]
    if ctx.realizados:
        frases.append(frase(f"foram realizados: {'; '.join(ctx.realizados)}"))
    elif ctx.atividades:
        frases.append(frase(f"as atividades previstas no plano de trabalho "
                            f"({listar(ctx.atividades)}) foram desenvolvidas"))
    objetivo = espacos(textos.get("atividade"))
    if objetivo and len(objetivo) <= 160 and not ctx.realizados:
        frases.append(frase(f"o objetivo da participação — {objetivo.rstrip('.')} — foi "
                            "atingido"))
    elif objetivo:
        frases.append("O objetivo da participação foi atingido.")
    frases.append("Não houve intercorrências que comprometessem os resultados.")
    return " ".join(frases)


def sugerir_medidas(ctx: Contexto, textos: Mapping[str, str]) -> str:
    if ctx.evento:
        referencia = f"do evento “{ctx.evento}”"
    else:
        referencia = "da viagem" + (f" a {ctx.destino}" if ctx.destino else "")
    itens = [f"registrar e divulgar internamente os resultados {referencia}"]
    if ctx.atividades:
        itens.append("dar seguimento às demandas identificadas durante as atividades "
                     f"({listar(ctx.atividades, maximo=3)})")
    else:
        itens.append("dar seguimento às demandas identificadas durante a viagem")
    conclusao = espacos(textos.get("conclusao")).lower()
    if any(sinal in conclusao for sinal in SINAIS_DE_PENDENCIA):
        itens.append("acompanhar a pendência apontada na conclusão até a sua solução")
    if ctx.destino:
        itens.append(f"avaliar a necessidade de novas ações em {ctx.destino}, conforme a "
                     "demanda da unidade")
    else:
        itens.append("avaliar a necessidade de novas ações, conforme a demanda da unidade")
    return (f"Recomenda-se ao órgão: {'; '.join(itens)}. Não há outras medidas a adotar além "
            "da prestação de contas das diárias.")


def sugerir(campo: str, ctx: Contexto, textos: Mapping[str, str]) -> str:
    if campo == "conclusao":
        return sugerir_conclusao(ctx, textos)
    if campo == "medidas":
        return sugerir_medidas(ctx, textos)
    raise ValueError("Este campo não tem sugestão de texto.")
