"""Leitura do e-mail de um pedido de evento (Python puro, sem Django): o que dá para sugerir
na solicitação nova a partir do texto colado — data do pedido (o envio), período do evento
(com o trecho de onde saiu), tipo (pelo nome ou sinônimo), município, local, endereço, CEP,
quem pede, cargo, contato, serviços (por palavra-chave, sem os negados), CIN agendadas,
unidade móvel (só quando o texto é claro) e a descrição. Nada aqui grava; quem chama
confere com os cadastros (`preenchimento.py`)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from gestao.plataforma import leitura_email as base

dobrar = base.dobrar

# Sinônimo (texto dobrado) → nome do tipo (dobrado). "Evento" fica de reserva.
SINONIMOS_TIPO = (
    (r"\b(curso|treinamento|capacitac\w*|oficina)s?\b", "capacitacao"),
    (r"\b(formatura|posse|solenidade|inaugurac\w*)\b", "inauguracao/solenidade"),
    (r"\b(exposic\w*|feira)\b", "feira"),
    (r"\b(palestra|roda de conversa)\b", "palestra"),
    (r"\breuniao\b", "reuniao"),
    (r"\bvisita\b", "visita"),
)
DIAS_DA_SEMANA = r"(segunda|terca|quarta|quinta|sexta)-feira"
# Palavra-chave (texto dobrado) → nome do serviço (dobrado).
SERVICOS = (
    (r"\b(cin|rg|identidade|carteira de identidade|2a via)\b", "emissao de cin"),
    (r"\b(digitais|biometria|coleta de digita\w*)\b", "coleta de digitais"),
    (r"\bfoto(s|grafia)?\b", "fotografia para documento"),
    (r"\bjuridic\w*\b", "orientacao juridica"),
    (r"\b(atendimento social|assistente social|assistencia social)\b", "atendimento social"),
)
_NEGACAO = re.compile(r"\b(nao|sem|dispensa\w*)\b[^.\n]{0,30}$")
_R_UNIDADE_MOVEL = re.compile(r"\bunidade movel\b|\bonibus da identificac\w*")
_R_CEP = re.compile(r"\b(\d{5})-?(\d{3})\b")
_R_CIN = re.compile(r"\b(\d{1,4})\s*(?:atendimentos?|cins?|carteiras?|identidades?|"
                    r"documentos?|rgs?)\b")
_MES = "|".join(base.MESES)
_R_DIA_MES = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
# "10 de novembro", "10 e 11 de novembro", "10, 11 e 12 de novembro", "10 a 12 de novembro"
_R_EXTENSO = re.compile(r"\b((?:\d{1,2}\s*(?:,|e|a|ao|ate)\s*)*\d{1,2})(?:o)?\s+de\s+(" + _MES
                        + r")(?:\s+de\s+(\d{4}))?\b")
_R_FAIXA_NUMERICA = re.compile(r"\b(\d{1,2})\s*(?:a|ao|ate|-)\s*(\d{1,2})/(\d{1,2})"
                               r"(?:/(\d{2,4}))?\b")
ROTULOS_LOCAL = ("local", "local do evento", "onde")
ROTULOS_ENDERECO = ("endereco", "end")
ROTULOS_BAIRRO = ("bairro",)
LIMITE_DESCRICAO = 4000


@dataclass
class Periodo:
    inicio: date
    fim: date
    trecho: str
    certeza: str  # "alta" (um trecho só) | "media" (juntou mais de um)


@dataclass
class Leitura:
    enviado_em: datetime | None = None
    remetente: str = ""
    email: str = ""
    assunto: str = ""
    periodo: Periodo | None = None
    tipo: str = ""  # nome dobrado do tipo
    municipio: str = ""  # chave do dicionário de municípios recebido
    local: str = ""
    endereco: str = ""
    bairro: str = ""
    cep: str = ""
    solicitante: str = ""
    cargo: str = ""
    contato: str = ""
    servicos: list[str] = field(default_factory=list)  # nomes dobrados
    quantidade_cin: int | None = None
    unidade_movel: bool = False
    descricao: str = ""

    @property
    def vazia(self) -> bool:
        return not (self.periodo or self.tipo or self.municipio or self.local
                    or self.servicos or self.solicitante)


def _ano(texto: str | None, mes: int, referencia: date) -> int:
    if texto:
        ano = int(texto)
        return ano + 2000 if ano < 100 else ano
    # Sem ano: o próximo (um pedido fala do que vem pela frente).
    return referencia.year + (1 if mes < referencia.month - 1 else 0)


def _data(ano: int, mes: int, dia: int) -> date | None:
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def periodo(corpo: str, referencia: date) -> Periodo | None:
    """O período do evento lido do corpo: as datas citadas (por extenso ou dd/mm), juntadas
    quando ficam a até 10 dias uma da outra; "10 a 12" vira a faixa toda."""
    d = dobrar(corpo)
    achados: list[tuple[list[date], str]] = []
    for m in _R_EXTENSO.finditer(d):
        mes = base.MESES[m.group(2)]
        ano = _ano(m.group(3), mes, referencia)
        numeros = [int(n) for n in re.findall(r"\d{1,2}", m.group(1))]
        faixa = re.search(r"\d\s*(a|ao|ate)\s*\d", m.group(1)) and len(numeros) == 2
        dias = (list(range(numeros[0], numeros[1] + 1)) if faixa else numeros)
        datas = [x for x in (_data(ano, mes, n) for n in dias) if x]
        if datas:
            achados.append((datas, corpo[m.start():m.end()]))
    for m in _R_FAIXA_NUMERICA.finditer(d):
        mes = int(m.group(3))
        ano = _ano(m.group(4), mes, referencia)
        a, b = int(m.group(1)), int(m.group(2))
        datas = [x for x in (_data(ano, mes, n) for n in range(a, b + 1)) if x] if a <= b else []
        if datas:
            achados.append((datas, corpo[m.start():m.end()]))
    ocupados = [(m.start(), m.end()) for m in _R_FAIXA_NUMERICA.finditer(d)]
    for m in _R_DIA_MES.finditer(d):
        if any(i <= m.start() < f for i, f in ocupados):
            continue
        mes, dia = int(m.group(2)), int(m.group(1))
        if not 1 <= mes <= 12:
            continue
        x = _data(_ano(m.group(3), mes, referencia), mes, dia)
        if x:
            achados.append(([x], corpo[m.start():m.end()]))
    futuras = [(ds, t) for ds, t in achados if ds[-1] >= referencia - timedelta(days=1)]
    if not futuras:
        return None
    futuras.sort(key=lambda par: par[0][0])
    datas, trechos = list(futuras[0][0]), [futuras[0][1]]
    for ds, t in futuras[1:]:
        if ds[0] - max(datas) <= timedelta(days=10):
            datas += ds
            if t not in trechos:
                trechos.append(t)
    return Periodo(min(datas), max(datas), " · ".join(trechos)[:120],
                   "alta" if len(trechos) == 1 else "media")


def tipo(texto: str, tipos: set[str]) -> str:
    """O tipo pelo nome (o mais longo citado) ou por sinônimo; "evento" só de reserva. Dias
    da semana ("quinta-feira") não contam como Feira; tipos no plural (listas) não contam."""
    d = re.sub(DIAS_DA_SEMANA, " ", dobrar(texto))
    for nome in sorted(tipos, key=len, reverse=True):
        if nome != "evento" and re.search(rf"\b{re.escape(nome)}\b(?!s\b)", d):
            return nome
    for padrao, nome in SINONIMOS_TIPO:
        if nome in tipos and re.search(padrao, d):
            return nome
    return "evento" if "evento" in tipos else ""


def municipio(texto: str, nomes: dict[str, str]) -> str:
    """O município citado (o nome mais longo, para "São José dos Pinhais" vencer "São José")."""
    d = dobrar(texto)
    ordem = sorted((c for c in nomes if len(c) >= 3), key=len, reverse=True)
    # Primeiro o que vem depois de "em", "de", "cidade de" (é onde o pedido diz a cidade);
    # depois qualquer citação.
    for prefixo in (r"\b(?:em|de|cidade de|municipio de)\s+", r"\b"):
        for chave in ordem:
            if re.search(rf"{prefixo}{re.escape(chave)}\b", d):
                return chave
    return ""


def _rotulado(texto: str, rotulos: tuple[str, ...]) -> str:
    for linha in texto.splitlines():
        d = dobrar(linha).strip()
        for r in rotulos:
            if d.startswith(r) and d[len(r):len(r) + 3].lstrip(" .").startswith(":"):
                return linha.split(":", 1)[1].strip(" .;")[:255]
    return ""


def servicos(texto: str, nomes: set[str]) -> list[str]:
    """Os serviços citados (por palavra-chave), sem os negados ("não precisa de foto")."""
    d = dobrar(texto)
    achados = []
    for padrao, nome in SERVICOS:
        if nome not in nomes:
            continue
        for m in re.finditer(padrao, d):
            inicio_da_frase = max(d.rfind(".", 0, m.start()), d.rfind("\n", 0, m.start())) + 1
            if not _NEGACAO.search(d[inicio_da_frase:m.start()]):
                achados.append(nome)
                break
    return achados


def ler(texto: str, referencia: date, *, tipos: set[str], municipios: dict[str, str],
        nomes_servicos: set[str]) -> Leitura:
    cab = base.cabecalhos(texto)
    corpo = base.corpo(texto)
    assinatura = base.assinatura(texto)
    leitura = Leitura(enviado_em=base.enviado_em(cab), assunto=base.assunto(cab),
                      remetente=base.nome_do_remetente(cab.get("de") or cab.get("from") or ""))
    if (m := base.R_EMAIL.search(cab.get("de") or cab.get("from") or "")):
        leitura.email = m.group(0)
    quando = (leitura.enviado_em.date() if leitura.enviado_em else referencia)
    tudo = f"{leitura.assunto}\n{corpo}"
    leitura.periodo = periodo(tudo, quando)
    leitura.tipo = tipo(tudo, tipos)
    leitura.municipio = municipio(tudo, municipios)
    leitura.local = _rotulado(corpo, ROTULOS_LOCAL)
    leitura.endereco = _rotulado(corpo, ROTULOS_ENDERECO)
    leitura.bairro = _rotulado(corpo, ROTULOS_BAIRRO)
    if (m := _R_CEP.search(corpo)):
        leitura.cep = f"{m.group(1)}-{m.group(2)}"
    leitura.solicitante = assinatura[0][:150] if assinatura else leitura.remetente
    if len(assinatura) > 1 and not base.R_TELEFONE.search(assinatura[1]):
        leitura.cargo = assinatura[1][:255]
    fone = base.R_TELEFONE.search(texto)
    leitura.contato = (fone.group(0) if fone else leitura.email)[:100]
    leitura.servicos = servicos(tudo, nomes_servicos)
    if (m := _R_CIN.search(dobrar(corpo))):
        leitura.quantidade_cin = int(m.group(1)) or None
    leitura.unidade_movel = bool(_R_UNIDADE_MOVEL.search(dobrar(tudo)))
    origem = (f"Origem: e-mail de {leitura.remetente or leitura.email or 'remetente'}"
              + (f" <{leitura.email}>" if leitura.email and leitura.remetente else "")
              + (f" em {leitura.enviado_em:%d/%m/%Y %H:%M}" if leitura.enviado_em else ""))
    leitura.descricao = (corpo[:LIMITE_DESCRICAO - len(origem) - 2].strip() + "\n\n"
                         + origem).strip()
    return leitura
