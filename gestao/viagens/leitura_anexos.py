"""Leitura dos anexos da prestação: o texto do que foi anexado (relatório técnico assinado,
diário de bordo assinado e comprovantes de saque/transferência) transcrito em campos para
copiar — como os dados para o eProtocolo do ofício — e, no comprovante, o número de
autorização, a data e o valor conferidos com a diária do ofício e com a do relatório.

Só leitura: o PDF é lido pelo texto que ele carrega (pypdf; `pdftotext` como segunda
tentativa). Um PDF digitalizado (só imagem) e as imagens PNG/JPG não têm texto para ler —
a tela diz isso em vez de inventar.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from .anexos import extensao
from .dominio import relatorio as dominio_rt

log = logging.getLogger(__name__)

PAGINAS_LIDAS = 6
TEXTO_MAXIMO = 20_000  # caracteres mostrados na transcrição completa

# Rótulos do nosso documento (documentos/relatorio_tecnico.html, diario_bordo.html) e os
# que costumam vir de outros modelos de RT.
_ROTULOS_RT_TOPO = ("Nome", "CPF", "Diária", "Translado", "Combustível", "Passagem")
_ROTULOS_DB_TOPO = ("Ofício do motorista", "Protocolo", "Viatura", "Placa", "Combustível",
                    "Placa reservada", "Motorista", "CPF")
_RX_DATA = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_RX_VALOR = re.compile(r"R\$\s*([\d.]+,\d{2})")
_RX_VALOR_SOLTO = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{3})*,\d{2})(?![\d.])")
# "Autenticação: A1B2.C3D4.E5F6.0718" / "Código de autorização 7F3A9C…" / "ID: E0F1…"
_RX_AUTORIZACAO_ROTULADA = re.compile(
    r"(?:autentica[çc][ãa]o|autoriza[çc][ãa]o|c[óo]digo|identificador|id da transa[çc][ãa]o"
    r"|n[úu]mero do documento|comprovante|protocolo)\s*(?:de\s+\w+\s*)?[:\-]?\s*"
    r"([0-9A-Fa-f][0-9A-Fa-f.\- ]{10,}[0-9A-Fa-f])", re.I)
_RX_AUTORIZACAO_SOLTA = re.compile(r"\b(?=[0-9A-Fa-f.]*[A-Fa-f])(?=[0-9A-Fa-f.]*\d)"
                                   r"[0-9A-Fa-f]{4,}(?:[.\-][0-9A-Fa-f]{4,}){1,7}\b|"
                                   r"\b(?=[0-9A-F]*[A-F])(?=[0-9A-F]*\d)[0-9A-F]{16,40}\b")
_OPERACOES = (("pix", "Pix"), ("ted", "TED"), ("doc", "DOC"), ("saque", "Saque"),
              ("dep[óo]sito", "Depósito"), ("transfer", "Transferência"))


@dataclass(frozen=True)
class Campo:
    rotulo: str
    valor: str
    longo: bool = False  # textarea em vez de input


@dataclass
class Leitura:
    anexo: object
    titulo: str
    tipo: str  # comprovante | rt | diario
    campos: list[Campo] = field(default_factory=list)
    texto: str = ""
    legivel: bool = False
    aviso: str = ""
    # só o comprovante
    valor: Decimal | None = None
    data: date | None = None
    operacao: str = ""
    autorizacao: str = ""
    conferencias: list[tuple[str, str]] = field(default_factory=list)  # (texto, tom)

    @property
    def copiar_tudo(self) -> str:
        return "\n".join(f"{c.rotulo}: {c.valor}" for c in self.campos if c.valor)


# ---------------------------------------------------------------- texto
def _com_pypdf(dados: bytes) -> str:
    from pypdf import PdfReader
    registro = logging.getLogger("pypdf")
    nivel = registro.level
    registro.setLevel(logging.ERROR)
    try:
        leitor = PdfReader(BytesIO(dados))
        partes = []
        for pagina in list(leitor.pages)[:PAGINAS_LIDAS]:
            try:
                partes.append(pagina.extract_text() or "")
            except Exception:
                partes.append("")
        return "\n".join(partes)
    except Exception:
        return ""
    finally:
        registro.setLevel(nivel)


def _com_pdftotext(dados: bytes) -> str:
    programa = shutil.which("pdftotext")
    if not programa:
        return ""
    try:
        saida = subprocess.run([programa, "-layout", "-l", str(PAGINAS_LIDAS), "-", "-"],
                               input=dados, capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return saida.stdout.decode("utf-8", "replace") if saida.returncode == 0 else ""


def extrair_texto(dados: bytes, nome: str) -> str:
    """O texto do PDF (vazio para imagem ou PDF digitalizado)."""
    if extensao(nome) != ".pdf":
        return ""
    texto = _com_pypdf(dados)
    if len(texto.strip()) < 20:
        texto = _com_pdftotext(dados) or texto
    texto = texto.replace("\x00", "").replace("\r", "")
    return re.sub(r"[ \t]+\n", "\n", texto).strip()[:TEXTO_MAXIMO]


def _linhas(texto: str) -> list[str]:
    return [linha.strip() for linha in texto.split("\n") if linha.strip()]


def _depois_do_rotulo(linhas: list[str], rotulos: tuple[str, ...]) -> dict[str, str]:
    """{rótulo: o que vem depois dele na mesma linha} — o layout das nossas tabelas."""
    achados: dict[str, str] = {}
    padroes = {r: re.compile(rf"(?<![\wÀ-ÿ]){re.escape(r)}\s*:?\s*", re.I) for r in rotulos}
    for linha in linhas:
        for rotulo, padrao in padroes.items():
            if rotulo in achados:
                continue
            m = padrao.search(linha)
            if not m:
                continue
            resto = linha[m.end():]
            # Corta no próximo rótulo da mesma linha ("Viatura X Placa ABC1D23").
            for outro, p2 in padroes.items():
                if outro != rotulo and (m2 := p2.search(resto)):
                    resto = resto[:m2.start()]
            resto = resto.strip(" :-–")
            if resto:
                achados[rotulo] = resto
    return achados


def _secoes(linhas: list[str], titulos: list[str]) -> dict[str, str]:
    """O texto entre um título de seção e o próximo (os rótulos do nosso RT)."""
    posicoes = []
    for i, linha in enumerate(linhas):
        for t in titulos:
            if linha.lower().rstrip(":") == t.lower():
                posicoes.append((i, t))
                break
    saida = {}
    for n, (i, t) in enumerate(posicoes):
        fim = posicoes[n + 1][0] if n + 1 < len(posicoes) else len(linhas)
        saida[t] = " ".join(linhas[i + 1:fim]).strip()
    return saida


# ---------------------------------------------------------------- leituras
def _valor(texto: str) -> Decimal | None:
    try:
        return Decimal(texto.replace(".", "").replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError):
        return None


def _data(texto: str) -> date | None:
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError:
        return None


def ler_comprovante(texto: str) -> dict:
    """Autorização (o código, hexadecimal na maioria dos bancos), data, valor e operação."""
    valores = [_valor(v) for v in _RX_VALOR.findall(texto)]
    if not valores:
        valores = [_valor(v) for v in _RX_VALOR_SOLTO.findall(texto)]
    valores = [v for v in valores if v]
    valor = None
    rotulado = re.search(r"valor[^\n:]*:?\s*R?\$?\s*([\d.]+,\d{2})", texto, re.I)
    if rotulado:
        valor = _valor(rotulado.group(1))
    if valor is None and valores:
        valor = max(valores)
    datas = [_data(f"{d}/{m}/{a}") for d, m, a in _RX_DATA.findall(texto)]
    datas = [d for d in datas if d]
    autorizacao = ""
    if (m := _RX_AUTORIZACAO_ROTULADA.search(texto)):
        autorizacao = re.sub(r"\s+", "", m.group(1))
    elif (m := _RX_AUTORIZACAO_SOLTA.search(texto)):
        autorizacao = m.group(0)
    operacao = ""
    baixo = texto.lower()
    for padrao, nome in _OPERACOES:
        if re.search(padrao, baixo):
            operacao = nome
            break
    return {"valor": valor, "data": datas[0] if datas else None, "autorizacao": autorizacao,
            "operacao": operacao}


def ler_rt(texto: str) -> dict[str, str]:
    linhas = _linhas(texto)
    campos = _depois_do_rotulo(linhas, _ROTULOS_RT_TOPO)
    campos.update(_secoes(linhas, list(dominio_rt.ROTULOS.values())))
    return campos


def ler_diario(texto: str) -> tuple[dict[str, str], list[str]]:
    linhas = _linhas(texto)
    campos = _depois_do_rotulo(linhas, _ROTULOS_DB_TOPO)
    # As linhas dos trechos: data e hora de saída, km, data e hora de chegada, km…
    trechos = [linha for linha in linhas
               if re.match(r"\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\s+\d", linha)]
    return campos, trechos


def _moeda(valor: Decimal | None) -> str:
    return dominio_rt.moeda(valor) if valor is not None else ""


def conferir(valor: Decimal | None, diaria_oficio: Decimal | None,
             diaria_rt: Decimal | None, soma_comprovantes: Decimal | None = None
             ) -> list[tuple[str, str]]:
    """O valor lido contra a diária do ofício e a do RT (texto, tom do selo)."""
    saida: list[tuple[str, str]] = []
    if valor is None:
        return [("Valor não encontrado no comprovante", "aviso")]
    for rotulo, esperado in (("diária do ofício", diaria_oficio), ("diária do RT", diaria_rt)):
        if esperado is None:
            saida.append((f"Sem {rotulo} para conferir", "neutro"))
        elif valor == esperado:
            saida.append((f"Bate com a {rotulo} ({_moeda(esperado)})", "sucesso"))
        elif soma_comprovantes is not None and soma_comprovantes == esperado:
            saida.append((f"A soma dos comprovantes bate com a {rotulo} ({_moeda(esperado)})",
                          "sucesso"))
        else:
            saida.append((f"Difere da {rotulo} ({_moeda(esperado)})", "perigo"))
    return saida


def ler(anexo, *, diaria_oficio: Decimal | None = None, diaria_rt: Decimal | None = None,
        soma_comprovantes: Decimal | None = None) -> Leitura:
    """A leitura de um anexo em uso (comprovante, RT assinado ou diário assinado)."""
    from .models import AnexoPrestacao
    tipo = {AnexoPrestacao.Tipo.COMPROVANTE: "comprovante",
            AnexoPrestacao.Tipo.RT_ASSINADO: "rt",
            AnexoPrestacao.Tipo.DB_ASSINADO: "diario"}.get(anexo.tipo, "")
    titulo = anexo.nome_original or anexo.arquivo.name.rsplit("/", 1)[-1]
    leitura = Leitura(anexo, titulo, tipo)
    try:
        with anexo.arquivo.open("rb") as arquivo:
            dados = arquivo.read()
    except (OSError, ValueError):
        leitura.aviso = "O arquivo não está disponível para leitura."
        return leitura
    nome = anexo.nome_original or anexo.arquivo.name
    if extensao(nome) != ".pdf":
        leitura.aviso = ("Imagem: não há texto para transcrever. Para a leitura automática, "
                         "anexe o PDF emitido pelo banco ou pelo sistema.")
        return leitura
    texto = extrair_texto(dados, nome)
    leitura.texto = texto
    if len(texto) < 20:
        leitura.aviso = ("Este PDF é digitalizado (só imagem): não há texto para transcrever. "
                         "Anexe o PDF original, com texto, para a leitura automática.")
        return leitura
    leitura.legivel = True
    if tipo == "comprovante":
        lido = ler_comprovante(texto)
        leitura.valor, leitura.data = lido["valor"], lido["data"]
        leitura.autorizacao, leitura.operacao = lido["autorizacao"], lido["operacao"]
        leitura.campos = [
            Campo("Nº de autorização", leitura.autorizacao),
            Campo("Data da operação", f"{leitura.data:%d/%m/%Y}" if leitura.data else ""),
            Campo("Valor", _moeda(leitura.valor)),
            Campo("Operação", leitura.operacao),
        ]
        leitura.conferencias = conferir(leitura.valor, diaria_oficio, diaria_rt,
                                        soma_comprovantes)
    elif tipo == "rt":
        campos = ler_rt(texto)
        leitura.campos = [Campo(r, campos.get(r, ""), longo=r in dominio_rt.ROTULOS.values())
                          for r in (*_ROTULOS_RT_TOPO, *dominio_rt.ROTULOS.values())]
    elif tipo == "diario":
        campos, trechos = ler_diario(texto)
        leitura.campos = [Campo(r, campos.get(r, "")) for r in _ROTULOS_DB_TOPO
                          if r != "Placa reservada"]
        leitura.campos.append(Campo("Trechos", "\n".join(trechos), longo=True))
    return leitura
