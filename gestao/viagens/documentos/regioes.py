"""Regiões editáveis, blocos e campos vinculados do HTML de um documento (ADR 0018).

O modelo do documento (``viagens/documentos/*.html``) marca:

- **regiões** com ``{% regiao "corpo" "Corpo" %}…{% endregiao %}`` — o que o editor deixa
  escrever; cada região sai do modelo entre marcadores ``<!--[regiao:corpo]-->`` e
  ``<!--[/regiao:corpo]-->``;
- **blocos** com ``data-bloco="chave" data-rotulo="…"`` em elementos dentro das regiões —
  as peças que o histórico legível nomeia ("Saudação alterada") e que podem voltar ao
  original uma a uma;
- **campos vinculados** com ``data-campo="motivo"`` — trechos que continuam vivos: o valor
  vem do cadastro em toda renderização, mesmo quando a região em volta foi editada;
- **pontos de quebra** com ``data-quebra="chave"`` — quebras de página que o editor liga e
  desliga.

Tudo aqui é texto puro (``html.parser`` da biblioteca padrão), sem dependência de Django.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser

MARCADOR_INICIO = "<!--[regiao:{}]-->"
MARCADOR_FIM = "<!--[/regiao:{}]-->"
_REGIAO = re.compile(r"<!--\[regiao:([a-z_]+)\]-->(.*?)<!--\[/regiao:\1\]-->", re.S)
_CAMPO = re.compile(r'(<span\b[^>]*\bdata-campo="([a-z_]+)"[^>]*>)(.*?)(</span>)', re.S)
_ESPACOS = re.compile(r"\s+")

# O que o editor pode gravar. Tudo fora disto é descartado (a marcação, nunca o texto).
TAGS_PERMITIDAS = frozenset({
    "p", "br", "strong", "b", "em", "i", "u", "s", "span", "div", "table", "thead", "tbody",
    "tfoot", "tr", "td", "th", "ul", "ol", "li", "h1", "h2", "h3", "sup", "sub", "blockquote",
})
TAGS_VAZIAS = frozenset({"br"})
ATRIBUTOS_PERMITIDOS = frozenset({
    "class", "colspan", "rowspan", "scope", "align", "style", "data-bloco", "data-rotulo",
    "data-campo", "data-obrigatorio", "data-multilinha", "data-quebra",
})
CLASSES_PERMITIDAS = frozenset({
    "centro", "titulo-secao", "sem-borda", "marcacao", "assinatura", "nome", "cargo",
    "destinatario", "quebra", "quebra--ativa", "quebra--livre", "bloco--alterado",
})
MAX_SPAN = 20  # mesclas de tabela aceitas no texto editado
_ESTILO = re.compile(r"^\s*text-align\s*:\s*(left|center|right|justify)\s*;?\s*$", re.I)
_ALINHAMENTO = frozenset({"left", "center", "right", "justify"})


# ---------------------------------------------------------------- regiões
def extrair_regioes(html: str) -> dict[str, str]:
    """Chave → HTML interno de cada região marcada, na ordem do documento."""
    return dict(_REGIAO.findall(html))


def aplicar_regioes(html: str, regioes: dict[str, str]) -> str:
    """Substitui o conteúdo das regiões presentes em ``regioes``; as demais ficam do modelo."""
    def trocar(m: re.Match[str]) -> str:
        chave = m.group(1)
        if chave not in regioes:
            return m.group(0)
        return f"{MARCADOR_INICIO.format(chave)}{regioes[chave]}{MARCADOR_FIM.format(chave)}"
    return _REGIAO.sub(trocar, html)


def impressao(html: str) -> str:
    """sha256 do HTML normalizado (espaços colapsados): a "versão do modelo" de uma região."""
    return hashlib.sha256(normalizar(html).encode()).hexdigest()


def normalizar(html: str) -> str:
    return _ESPACOS.sub(" ", html).replace("> <", "><").strip()


# ---------------------------------------------------------------- campos vinculados
def sincronizar_campos(html: str, valores: dict[str, str]) -> str:
    """Reescreve o conteúdo dos ``<span data-campo>`` com os valores atuais do cadastro."""
    def trocar(m: re.Match[str]) -> str:
        abertura, chave, _, fecho = m.groups()
        if chave not in valores:
            return m.group(0)
        valor = escape(valores[chave] or "")
        if "data-multilinha" in abertura:
            valor = valor.replace("\n", "<br>")
        return f"{abertura}{valor}{fecho}"
    return _CAMPO.sub(trocar, html)


def campos_presentes(html: str) -> set[str]:
    return {chave for _, chave, _, _ in _CAMPO.findall(html)}


# ---------------------------------------------------------------- blocos
@dataclass(frozen=True)
class Elemento:
    chave: str
    rotulo: str
    inicio: int
    fim: int
    texto: str


class _Marcados(HTMLParser):
    """Localiza (posição inicial e final) os elementos com um atributo ``data-*`` dado."""

    def __init__(self, texto: str, atributo: str):
        super().__init__(convert_charrefs=True)
        self.texto = texto
        self.atributo = atributo
        self.linhas = [0]
        for linha in texto.splitlines(keepends=True):
            self.linhas.append(self.linhas[-1] + len(linha))
        self.pilha: list[tuple[str, int]] = []  # (tag, profundidade) de tags abertas
        self.abertos: list[tuple[int, str, str, int, list[str]]] = []
        self.achados: list[Elemento] = []
        self.profundidade = 0

    def _pos(self) -> int:
        linha, coluna = self.getpos()
        return self.linhas[linha - 1] + coluna

    def handle_starttag(self, tag, attrs):
        if tag in TAGS_VAZIAS:
            return
        self.profundidade += 1
        atributos = dict(attrs)
        if self.atributo in atributos:
            self.abertos.append((self.profundidade, atributos.get(self.atributo) or "",
                                 atributos.get("data-rotulo") or "", self._pos(), []))

    def handle_data(self, data):
        for aberto in self.abertos:
            aberto[4].append(data)

    def handle_endtag(self, tag):
        if tag in TAGS_VAZIAS:
            return
        if self.abertos and self.abertos[-1][0] == self.profundidade:
            _prof, chave, rotulo, inicio, textos = self.abertos.pop()
            fim = self._pos() + len(tag) + 3  # "</tag>"
            self.achados.append(Elemento(chave, rotulo, inicio, fim,
                                         normalizar("".join(textos))))
        self.profundidade -= 1


def elementos_marcados(html: str, atributo: str = "data-bloco") -> list[Elemento]:
    p = _Marcados(html, atributo)
    p.feed(html)
    p.close()
    return sorted(p.achados, key=lambda e: e.inicio)


def blocos_alterados(original: str, editado: str) -> list[dict[str, str]]:
    """Blocos cujo texto mudou (ou que sumiram), mais quebras de página e texto solto.

    Cada item é ``{"chave", "rotulo"}``; as chaves ``quebras`` e ``texto`` são pseudo-blocos.
    """
    antes = {e.chave: e for e in elementos_marcados(original)}
    depois = {e.chave: e for e in elementos_marcados(editado)}
    alterados: list[dict[str, str]] = []
    for chave, e in antes.items():
        if chave not in depois:
            alterados.append({"chave": chave, "rotulo": f"{e.rotulo or chave} (removido)"})
        elif depois[chave].texto != e.texto:
            alterados.append({"chave": chave, "rotulo": e.rotulo or chave})
    quebras_antes = {q.chave for q in elementos_marcados(original, "data-quebra")
                     if "quebra--ativa" in original[q.inicio:q.inicio + 200]}
    quebras_depois = {q.chave for q in elementos_marcados(editado, "data-quebra")
                      if "quebra--ativa" in editado[q.inicio:q.inicio + 200]}
    if quebras_antes != quebras_depois or editado.count("quebra--livre") != original.count(
            "quebra--livre"):
        alterados.append({"chave": "quebras", "rotulo": "Quebras de página"})
    if not alterados and normalizar(texto_sem_marcacao(original)) != normalizar(
            texto_sem_marcacao(editado)):
        alterados.append({"chave": "texto", "rotulo": "Texto"})
    return alterados


def bloco_original(html: str, chave: str) -> str | None:
    """HTML completo (abertura a fechamento) do bloco ``chave`` como o modelo o gera."""
    for e in elementos_marcados(html):
        if e.chave == chave:
            return html[e.inicio:e.fim]
    return None


class _SoTexto(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []

    def handle_data(self, data):
        self.partes.append(data)


def texto_sem_marcacao(html: str) -> str:
    p = _SoTexto()
    p.feed(html)
    p.close()
    return " ".join(p.partes)


# ---------------------------------------------------------------- saneamento
class _Saneador(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.saida: list[str] = []
        self.ignorando = 0  # dentro de <script>/<style>: descarta até fechar

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "iframe", "object", "embed"):
            self.ignorando += 1
            return
        if self.ignorando or tag not in TAGS_PERMITIDAS:
            return
        limpos = []
        for nome, valor in attrs:
            if nome not in ATRIBUTOS_PERMITIDOS or valor is None:
                if nome in ("data-obrigatorio", "data-multilinha") and valor is None:
                    limpos.append(f" {nome}")
                continue
            if nome == "class":
                tokens = [t for t in valor.split() if t in CLASSES_PERMITIDAS]
                if not tokens:
                    continue
                valor = " ".join(tokens)
            elif nome == "style":
                m = _ESTILO.match(valor)
                if not m:
                    continue
                valor = f"text-align: {m.group(1).lower()}"
            elif nome == "align":
                if valor.lower() not in _ALINHAMENTO:
                    continue
                valor = valor.lower()
            elif nome in ("colspan", "rowspan"):
                # Só algarismos ASCII e um teto realista: um colspan de 99999 travava o
                # DOCX (revisão de segurança, 03/10/2026).
                if not (valor.isascii() and valor.isdecimal() and 1 <= int(valor) <= MAX_SPAN):
                    continue
            elif nome in ("data-bloco", "data-campo", "data-quebra", "scope"):
                if not re.fullmatch(r"[a-z0-9_-]{1,40}", valor):
                    continue
            limpos.append(f' {nome}="{escape(valor, quote=True)}"')
        self.saida.append(f"<{tag}{''.join(limpos)}>")

    def handle_startendtag(self, tag, attrs):
        if tag in TAGS_VAZIAS and not self.ignorando:
            self.saida.append(f"<{tag}>")
        else:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "iframe", "object", "embed"):
            self.ignorando = max(0, self.ignorando - 1)
            return
        if self.ignorando or tag not in TAGS_PERMITIDAS or tag in TAGS_VAZIAS:
            return
        self.saida.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.ignorando:
            self.saida.append(escape(data, quote=False))

    def handle_entityref(self, name):  # pragma: no cover - convert_charrefs=True
        self.saida.append(f"&{name};")

    def handle_comment(self, data):
        return  # comentários (inclusive marcadores de região) nunca entram pelo editor


def sanear_html(html: str) -> str:
    """Mantém só a marcação que o documento conhece; o texto fica sempre."""
    s = _Saneador()
    s.feed(html or "")
    s.close()
    return "".join(s.saida).strip()


def marcar_blocos_alterados(html: str, chaves_alteradas: set[str]) -> str:
    """Acrescenta ``bloco--alterado`` à classe dos blocos listados (para a folha destacar)."""
    if not chaves_alteradas:
        return html
    def trocar(m: re.Match[str]) -> str:
        chave = m.group(2)
        if chave not in chaves_alteradas or "bloco--alterado" in m.group(0):
            return m.group(0)
        tag = m.group(0)
        if ' class="' in tag:
            return tag.replace(' class="', ' class="bloco--alterado ', 1)
        return tag[:-1] + ' class="bloco--alterado">'
    return re.sub(r'<([a-z0-9]+)\b[^>]*\bdata-bloco="([a-z0-9_-]+)"[^>]*>', trocar, html)


def rotulos_dos_blocos(html: str) -> dict[str, str]:
    return {e.chave: e.rotulo or e.chave for e in elementos_marcados(html)}
