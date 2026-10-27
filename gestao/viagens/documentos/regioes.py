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
from collections import Counter
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser

MARCADOR_INICIO = "<!--[regiao:{}]-->"
MARCADOR_FIM = "<!--[/regiao:{}]-->"
_REGIAO = re.compile(r"<!--\[regiao:([a-z_]+)\]-->(.*?)<!--\[/regiao:\1\]-->", re.S)
_CAMPO = re.compile(r'(<span\b[^>]*\bdata-campo="([a-z0-9_]+)"[^>]*>)(.*?)(</span>)', re.S)
_ESPACOS = re.compile(r"\s+")

# O que o editor pode gravar. Tudo fora disto é descartado (a marcação, nunca o texto).
TAGS_PERMITIDAS = frozenset({
    "p", "br", "strong", "b", "em", "i", "u", "s", "span", "div", "section", "table", "thead",
    "tbody",
    "tfoot", "tr", "td", "th", "ul", "ol", "li", "h1", "h2", "h3", "sup", "sub", "blockquote",
})
TAGS_VAZIAS = frozenset({"br"})
ATRIBUTOS_PERMITIDOS = frozenset({
    "class", "colspan", "rowspan", "scope", "align", "style", "data-bloco", "data-rotulo",
    "data-campo", "data-obrigatorio", "data-multilinha", "data-quebra",
    # Quem é quem no texto (servidor, motorista, transporte): o clique abre o formulário.
    "data-entidade", "data-id",
})
CLASSES_PERMITIDAS = frozenset({
    "centro", "titulo-secao", "sem-borda", "marcacao", "assinatura", "nome", "cargo",
    "destinatario", "quebra", "quebra--ativa", "quebra--livre", "bloco--alterado",
    # Termo de autorização: linhas para preencher à mão e rótulo colado à linha.
    "branco", "branco--curto", "branco--nome", "branco--cpf", "par", "assinaturas",
    # Ordem de serviço.
    "referencia", "determino", "competencias",
    # Plano de trabalho (as classes do recuo: listas, dados da atuação, subtítulos).
    "capa", "lista", "evento", "itens", "subtitulo", "evento__titulo", "evento__dados",
    "efetivo", "prosa", "varios", "nova-pagina",
})
MAX_SPAN = 20  # mesclas de tabela aceitas no texto editado
_ALINHAMENTO = frozenset({"left", "center", "right", "justify"})

# Cores de fonte que o editor oferece (a paleta da barra). Fechada de propósito: documento
# oficial não é lugar de qualquer cor, e uma lista fixa não deixa passar nada estranho.
CORES_DE_FONTE = {
    "#000000": "Preto", "#555555": "Cinza", "#a3241a": "Vermelho", "#1b5592": "Azul",
    "#17603d": "Verde",
}


_RGB = re.compile(r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)")


def _cor_hex(valor: str) -> str:
    """"rgb(163, 36, 26)" → "#a3241a" (é assim que o navegador escreve a cor escolhida no
    editor); "#a3241a" fica como está."""
    m = _RGB.fullmatch(valor)
    if not m:
        return valor
    r, g, b = (int(x) for x in m.groups())
    return f"#{r:02x}{g:02x}{b:02x}" if max(r, g, b) <= 255 else valor


def _estilo_saneado(valor: str, tag: str) -> str:
    """Só as declarações conhecidas, cada uma com o valor dentro da faixa — remontadas.

    - text-align: left | center | right | justify (qualquer tag);
    - font-size: 7pt a 24pt, de meio em meio ponto;
    - color: só as da paleta do editor;
    - width: 10% a 100% ou 5mm a 200mm, em tabela e célula;
    - height: 4mm a 60mm, em linha e célula.
    """
    aceitas: list[str] = []
    for declaracao in valor.split(";"):
        if ":" not in declaracao:
            continue
        nome, _, bruto = declaracao.partition(":")
        nome, bruto = nome.strip().lower(), bruto.strip().lower()
        if nome == "text-align" and bruto in _ALINHAMENTO:
            aceitas.append(f"text-align: {bruto}")
        elif nome == "font-size":
            m = re.fullmatch(r"(\d{1,2})(\.5)?pt", bruto)
            if m and 7 <= int(m.group(1)) <= 24:
                aceitas.append(f"font-size: {m.group(1)}{m.group(2) or ''}pt")
        elif nome == "color" and _cor_hex(bruto) in CORES_DE_FONTE:
            aceitas.append(f"color: {_cor_hex(bruto)}")
        elif nome == "width" and tag in ("table", "td", "th"):
            m = re.fullmatch(r"(\d{1,3})(%|mm)", bruto)
            if m:
                numero, unidade = int(m.group(1)), m.group(2)
                if (unidade == "%" and 10 <= numero <= 100) or (unidade == "mm"
                                                                  and 5 <= numero <= 200):
                    aceitas.append(f"width: {numero}{unidade}")
        elif nome == "height" and tag in ("tr", "td", "th"):
            m = re.fullmatch(r"(\d{1,2})mm", bruto)
            if m and 4 <= int(m.group(1)) <= 60:
                aceitas.append(f"height: {int(m.group(1))}mm")
    return "; ".join(aceitas)


# ---------------------------------------------------------------- regiões
def extrair_regioes(html: str) -> dict[str, str]:
    """Chave → HTML interno de cada região marcada, na ordem do documento."""
    return dict(_REGIAO.findall(html))


_PARAGRAFO_DE_MARCADORES = re.compile(r"<p>\s*(•[^<]*(?:<br\s*/?>\s*•[^<]*)*)</p>")


def listas_de_marcadores(html: str) -> str:
    """Parágrafo feito só de linhas "• item" (o texto salvo antes das listas de verdade) vira
    `<ul class="itens">` — com o recuo e o alinhamento das listas do documento."""
    def lista(m: re.Match) -> str:
        itens = [linha.strip().removeprefix("•").strip()
                 for linha in re.split(r"<br\s*/?>", m.group(1))]
        return '<ul class="itens">' + "".join(f"<li>{i}</li>" for i in itens if i) + "</ul>"
    return _PARAGRAFO_DE_MARCADORES.sub(lista, html)


def aplicar_regioes(html: str, regioes: dict[str, str]) -> str:
    """Substitui o conteúdo das regiões presentes em ``regioes``; as demais ficam do modelo."""
    def trocar(m: re.Match[str]) -> str:
        chave = m.group(1)
        if chave not in regioes:
            return m.group(0)
        return f"{MARCADOR_INICIO.format(chave)}{regioes[chave]}{MARCADOR_FIM.format(chave)}"
    return _REGIAO.sub(trocar, html)


_TABELA = re.compile(r"<table\b[^>]*>.*?</table>", re.S)
_LINHA = re.compile(r"<tr\b([^>]*)>(.*?)</tr>", re.S)
_CELULA = re.compile(r"<(td|th)\b([^>]*)>(.*?)</\1>", re.S)
_ATRIBUTO = re.compile(r'([a-z-]+)="([^"]*)"')
_VAZIA = re.compile(r"<[^>]+>|&nbsp;|\s|\xa0")


def _linha_de_quem(atributos: str) -> tuple[str, str] | None:
    attrs = dict(_ATRIBUTO.findall(atributos))
    if attrs.get("data-entidade") and attrs.get("data-id"):
        return attrs["data-entidade"], attrs["data-id"]
    return None


def _largura(celulas: list[tuple[str, str, str]]) -> int:
    total = 0
    for _tag, atributos, _conteudo in celulas:
        span = dict(_ATRIBUTO.findall(atributos)).get("colspan", "1")
        total += int(span) if span.isdecimal() else 1
    return total


def _celula_vazia(celula: tuple[str, str, str]) -> bool:
    _tag, atributos, conteudo = celula
    return "colspan" not in atributos and "data-campo" not in conteudo and not _VAZIA.sub(
        "", conteudo)


def reparar_tabelas(html: str, modelo: str = "") -> str:
    """Linhas de tabela com mais (ou menos) células que o cabeçalho voltam ao alinhamento.

    O editor escreve no navegador (contenteditable), e uma seleção apagada ou um texto colado
    entre células pode deixar uma linha com células a mais — no PDF, nome, CPF e cargo saem
    empurrados uma coluna para a direita. Linha de alguém (``data-entidade``/``data-id``) volta
    a ser a linha que o modelo gera para essa pessoa; nas demais, saem as células vazias que
    sobram (as da frente primeiro) e faltando célula, completa-se no fim. Tabela com
    ``rowspan`` fica como está: lá a contagem por linha não diz nada."""
    do_modelo = {quem: m.group(0) for m in _LINHA.finditer(modelo)
                 if (quem := _linha_de_quem(m.group(1)))}

    def reparar(tabela: re.Match[str]) -> str:
        texto = tabela.group(0)
        if "rowspan" in texto or texto.count("<table") > 1:
            return texto
        linhas = [(m, _CELULA.findall(m.group(2))) for m in _LINHA.finditer(texto)]
        larguras = [_largura(c) for _m, c in linhas if c]
        if not larguras or len(set(larguras)) == 1:
            return texto
        cabecalho = re.search(r"<thead\b.*?<tr\b[^>]*>(.*?)</tr>", texto, re.S)
        if cabecalho:
            esperada = _largura(_CELULA.findall(cabecalho.group(1)))
        else:
            esperada = Counter(larguras).most_common(1)[0][0]

        def linha_reparada(m: re.Match[str], celulas: list[tuple[str, str, str]]) -> str:
            sobra = _largura(celulas) - esperada
            if not celulas or sobra == 0:
                return m.group(0)
            quem = _linha_de_quem(m.group(1))
            if sobra > 0 and quem in do_modelo:
                return do_modelo[quem]
            celulas = list(celulas)
            if sobra > 0:
                while sobra and celulas and _celula_vazia(celulas[0]):
                    del celulas[0]
                    sobra -= 1
                while sobra and celulas and _celula_vazia(celulas[-1]):
                    del celulas[-1]
                    sobra -= 1
                if sobra:
                    return m.group(0)
            else:
                celulas += [("td", "", "")] * -sobra
            corpo = "".join(f"<{t}{a}>{c}</{t}>" for t, a, c in celulas)
            return f"<tr{m.group(1)}>{corpo}</tr>"

        saida, fim = [], 0
        for m, celulas in linhas:
            saida += [texto[fim:m.start()], linha_reparada(m, celulas)]
            fim = m.end()
        return "".join(saida) + texto[fim:]

    return _TABELA.sub(reparar, html)


def impressao(html: str) -> str:
    """sha256 do HTML normalizado (espaços colapsados): a "versão do modelo" de uma região."""
    return hashlib.sha256(normalizar(html).encode()).hexdigest()


def normalizar(html: str) -> str:
    return _ESPACOS.sub(" ", html).replace("> <", "><").strip()


# ---------------------------------------------------------------- campos vinculados
_ABRE_CAMPO = re.compile(r'<span\b[^>]*\bdata-campo="[a-z0-9_]+"[^>]*>')
_SPAN = re.compile(r"<span\b[^>]*>|</span>")


def _achatar_campos(html: str) -> str:
    """Um ``<span data-campo>`` só tem texto: marcação que o editor tenha posto dentro (cor,
    tamanho aplicados a parte do campo) sai, o texto fica — senão o fecho da marcação
    interna seria tomado pelo do campo e o valor sairia repetido no documento."""
    saida, pos = [], 0
    for m in _ABRE_CAMPO.finditer(html):
        if m.start() < pos:
            continue  # campo dentro de campo: já achatado com o de fora
        nivel, fim = 1, None
        for t in _SPAN.finditer(html, m.end()):
            nivel += -1 if t.group(0) == "</span>" else 1
            if nivel == 0:
                fim = t
                break
        if fim is None:
            break
        interno = html[m.end():fim.start()]
        if "<" in interno:
            interno = re.sub(r"<(?!br\b)[^>]*>", "", interno)
        saida += [html[pos:m.end()], interno, "</span>"]
        pos = fim.end()
    saida.append(html[pos:])
    return "".join(saida)


def sincronizar_campos(html: str, valores: dict[str, str]) -> str:
    """Reescreve o conteúdo dos ``<span data-campo>`` com os valores atuais do cadastro."""
    html = _achatar_campos(html)

    def trocar(m: re.Match[str]) -> str:
        abertura, chave, _, fecho = m.groups()
        if chave not in valores:
            return m.group(0)
        valor = escape((valores[chave] or "").replace("\r\n", "\n").replace("\r", "\n"))
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
        # Só "\n" conta como quebra (é o que o HTMLParser conta em getpos): um "\r" solto
        # de texto colado não pode deslocar as posições.
        for linha in texto.split("\n")[:-1]:
            self.linhas.append(self.linhas[-1] + len(linha) + 1)
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


_TOKEN = re.compile(r"<[^>]+>|\s+|[^\s<]+")
_MARCA_ALTERADO = re.compile(r'\s*class="bloco--alterado"|(?<=[" ])bloco--alterado\b')


def mesclar_alteracao(original: str, editado: str, destino: str) -> tuple[str, int]:
    """Leva para `destino` as mudanças que `editado` fez em `original` (fusão a três).

    Os três são o mesmo bloco em documentos irmãos (os termos de cada servidor): o texto
    comum é igual e só os dados de cada um diferem. Cada trecho mudado na origem vai para
    o destino onde o texto em volta é o mesmo; o que cai em dado que difere (o nome, o CPF)
    não vai. Devolve o destino com as mudanças e quantas ficaram de fora."""
    from difflib import SequenceMatcher

    def tokens(html: str) -> list[str]:
        return _TOKEN.findall(_MARCA_ALTERADO.sub("", html))

    a, b, c = tokens(original), tokens(editado), tokens(destino)
    # Posição de cada símbolo de `original` no destino, onde os dois são iguais.
    mapa: dict[int, int] = {}
    for bloco in SequenceMatcher(None, a, c, autojunk=False).get_matching_blocks():
        for k in range(bloco.size):
            mapa[bloco.a + k] = bloco.b + k
    trocas: list[tuple[int, int, list[str]]] = []
    fora = 0
    for op, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        if i1 < i2:  # troca ou remoção: o trecho inteiro tem de estar igual no destino
            inicio = mapa.get(i1)
            if inicio is None or any(mapa.get(i1 + k) != inicio + k for k in range(i2 - i1)):
                fora += 1
                continue
            trocas.append((inicio, inicio + (i2 - i1), b[j1:j2]))
        else:  # inserção: ancorada no símbolo de antes (ou no de depois, no começo)
            if i1 > 0 and (i1 - 1) in mapa:
                pos = mapa[i1 - 1] + 1
            elif i1 in mapa:
                pos = mapa[i1]
            else:
                fora += 1
                continue
            trocas.append((pos, pos, b[j1:j2]))
    for inicio, fim, novo in sorted(trocas, key=lambda t: t[0], reverse=True):
        c[inicio:fim] = novo
    return "".join(c), fora


def trocar_bloco(html: str, chave: str, novo: str) -> str | None:
    """O HTML com o bloco ``chave`` trocado por ``novo`` (None se o bloco não estiver lá)."""
    for e in elementos_marcados(html):
        if e.chave == chave:
            return html[:e.inicio] + novo + html[e.fim:]
    return None


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
                valor = _estilo_saneado(valor, tag)
                if not valor:
                    continue
            elif nome == "align":
                if valor.lower() not in _ALINHAMENTO:
                    continue
                valor = valor.lower()
            elif nome in ("colspan", "rowspan"):
                # Só algarismos ASCII e um teto realista: um colspan de 99999 travava o
                # DOCX (revisão de segurança, 03/10/2026).
                if not (valor.isascii() and valor.isdecimal() and 1 <= int(valor) <= MAX_SPAN):
                    continue
            elif nome == "data-id":
                if not (valor.isascii() and valor.isdecimal() and len(valor) <= 12):
                    continue
            elif nome in ("data-bloco", "data-campo", "data-quebra", "data-entidade", "scope"):
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
