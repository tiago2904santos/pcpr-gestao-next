"""Conversão/extração isolada em processo com orçamento de memória, CPU e tempo.

Executável interno: recebe caminhos temporários criados pelo serviço, nunca URLs.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess  # nosec B404
import sys
import tempfile
import zipfile
from email import policy
from email.parser import BytesParser
from html import escape
from html.parser import HTMLParser
from pathlib import Path

MAX_BYTES = 25 * 1024 * 1024
MAX_PAGINAS = 100
OFFICE = {".doc", ".docx", ".odt", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp", ".rtf"}
IMAGENS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp", ".gif", ".avif"}


class TextoHTML(HTMLParser):
    """Extrai somente texto. HTML enviado nunca acessa rede ou executa scripts."""

    def __init__(self):
        super().__init__()
        self.partes: list[str] = []
        self.ignorar = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.ignorar += 1
        if tag in {"p", "div", "br", "tr", "h1", "h2", "h3", "li"}:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.ignorar = max(0, self.ignorar - 1)

    def handle_data(self, data):
        if not self.ignorar:
            self.partes.append(data)


class LeituraInvalida(Exception):
    pass


def executar(args: list[str], timeout: int = 45) -> bytes:
    if args[0] not in {"libreoffice", "pdftoppm", "tesseract"}:
        raise LeituraInvalida("Conversor não permitido.")
    caminho = shutil.which(args[0])
    if not caminho:
        raise LeituraInvalida(
            "O conversor não está disponível. Peça ao gestor para verificar o worker."
        )
    try:
        # Executável da lista fixa; argumentos separados, sem shell e com timeout.
        return subprocess.run(  # noqa: S603 # nosec B603
            [caminho, *args[1:]],
            check=True,
            capture_output=True,
            timeout=timeout,
            env={**os.environ, "OMP_THREAD_LIMIT": "1"},
        ).stdout
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        raise LeituraInvalida(
            "Não foi possível ler este arquivo no prazo. Exporte em PDF e reenvie."
        ) from exc


def converter(origem: Path, pasta: Path) -> bytes:
    dados = origem.read_bytes()
    if dados.startswith(b"%PDF-"):
        return dados
    ext = origem.suffix.lower()
    if ext in IMAGENS or dados.startswith((b"\x89PNG", b"\xff\xd8\xff", b"II*\x00", b"MM\x00*")):
        from PIL import Image, ImageOps, ImageSequence

        try:
            with Image.open(io.BytesIO(dados)) as imagem:
                if getattr(imagem, "n_frames", 1) > MAX_PAGINAS:
                    raise LeituraInvalida("A imagem tem mais de 100 páginas.")
                paginas = []
                for frame in ImageSequence.Iterator(imagem):
                    if frame.width * frame.height > 30_000_000:
                        raise LeituraInvalida("Imagem muito grande. Reduza para até 30 megapixels.")
                    paginas.append(ImageOps.exif_transpose(frame).convert("RGB"))
                saida = io.BytesIO()
                paginas[0].save(saida, format="PDF", save_all=True, append_images=paginas[1:])
                return saida.getvalue()
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise LeituraInvalida("A imagem está danificada. Exporte novamente e reenvie.") from exc
    if ext in {".txt", ".csv", ".eml", ".mht", ".mhtml", ".html", ".htm"}:
        html = ext in {".html", ".htm"}
        if ext in {".eml", ".mht", ".mhtml"}:
            mensagem = BytesParser(policy=policy.default).parsebytes(dados)
            corpo = mensagem.get_body(preferencelist=("plain", "html"))
            html = corpo is not None and corpo.get_content_type() == "text/html"
            texto = (
                str(mensagem.get("Subject", ""))
                + "\n"
                + (str(corpo.get_content()) if corpo else "")
            )
        else:
            try:
                texto = dados.decode("utf-8-sig")
            except UnicodeDecodeError:
                texto = dados.decode("cp1252")
        if html:
            leitor_html = TextoHTML()
            leitor_html.feed(texto)
            texto = "".join(leitor_html.partes)
        from weasyprint import HTML

        return HTML(
            string="<meta charset='utf-8'><style>pre{white-space:pre-wrap;"
            "font:11pt sans-serif}</style><pre>" + escape(texto) + "</pre>"
        ).write_pdf()
    if ext in OFFICE:
        if ext in {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}:
            try:
                with zipfile.ZipFile(io.BytesIO(dados)) as pacote:
                    if sum(f.file_size for f in pacote.infolist()) > 100 * 1024 * 1024:
                        raise LeituraInvalida("Documento expandido muito grande. Exporte em PDF.")
                    for f in pacote.infolist():
                        if "vbaproject" in f.filename.lower():
                            raise LeituraInvalida(
                                "Documento com macros. Exporte em PDF antes de enviar."
                            )
                        if f.filename.endswith(".rels") and b'TargetMode="External"' in pacote.read(
                            f
                        ):
                            raise LeituraInvalida(
                                "Documento com vínculos externos. Exporte em PDF antes de enviar."
                            )
            except zipfile.BadZipFile as exc:
                raise LeituraInvalida(
                    "O documento está danificado ou protegido. Exporte em PDF."
                ) from exc
        perfil = pasta / "perfil"
        (perfil / "user").mkdir(parents=True)
        (perfil / "user" / "registrymodifications.xcu").write_text(
            '<?xml version="1.0"?><oor:items xmlns:oor="http://openoffice.org/2001/registry">'
            '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
            '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>'
            "</item></oor:items>",
            encoding="utf-8",
        )
        executar(
            [
                "libreoffice",
                "--headless",
                "--nologo",
                "--nodefault",
                "--norestore",
                f"-env:UserInstallation={perfil.as_uri()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(pasta),
                str(origem),
            ]
        )
        convertido = pasta / (origem.stem + ".pdf")
        if not convertido.is_file() or convertido.stat().st_size > MAX_BYTES:
            raise LeituraInvalida("A conversão falhou ou ultrapassou 25 MB. Exporte um PDF menor.")
        return convertido.read_bytes()
    raise LeituraInvalida(
        "Este formato não pôde ser convertido. Exporte em PDF ou envie uma imagem."
    )


def _imagem_grande(recursos, profundidade=0) -> bool:
    if hasattr(recursos, "get_object"):
        recursos = recursos.get_object()
    if not isinstance(recursos, dict):
        return False
    objetos = recursos.get("/XObject", {})
    if hasattr(objetos, "get_object"):
        objetos = objetos.get_object()
    if not isinstance(objetos, dict):
        return False
    for ref in objetos.values():
        obj = ref.get_object()
        if obj.get("/Subtype") == "/Image":
            if int(obj.get("/Width", 0)) >= 600 and int(obj.get("/Height", 0)) >= 700:
                return True
        elif profundidade < 2 and _imagem_grande(obj.get("/Resources"), profundidade + 1):
            return True
    return False


def extrair(origem: Path, pasta: Path) -> dict:
    from pypdf import PdfReader, PdfWriter

    from gestao.viagens.dominio.importacao import separar

    pdf = converter(origem, pasta)
    caminho = pasta / "convertido.pdf"
    caminho.write_bytes(pdf)
    try:
        leitor = PdfReader(io.BytesIO(pdf))
        if leitor.is_encrypted:
            raise LeituraInvalida("PDF protegido por senha. Envie uma cópia desbloqueada.")
        if not 0 < len(leitor.pages) <= MAX_PAGINAS:
            raise LeituraInvalida("Envie arquivos com até 100 páginas.")
        textos, ocr = [], 0
        for i, pagina in enumerate(leitor.pages, 1):
            texto = pagina.extract_text() or ""
            # Um carimbo digital pode fornecer centenas de caracteres enquanto o
            # documento principal continua sendo uma imagem (comum em eProtocolo).
            imagem_grande = _imagem_grande(pagina.get("/Resources"))
            if len(texto.strip()) < 50 or (imagem_grande and len(texto.strip()) < 500):
                prefixo = pasta / f"ocr-{i}"
                executar(
                    [
                        "pdftoppm",
                        "-f",
                        str(i),
                        "-l",
                        str(i),
                        "-scale-to",
                        "2400",
                        "-singlefile",
                        "-png",
                        str(caminho),
                        str(prefixo),
                    ]
                )
                lido = executar(
                    ["tesseract", str(prefixo) + ".png", "stdout", "-l", "por+eng", "--psm", "3"]
                ).decode("utf-8", errors="replace")
                texto = lido + "\n" + texto
                ocr += 1
            textos.append(texto[:50_000])
        partes = separar(textos)
        resultado = []
        for i, parte in enumerate(partes):
            nome = f"parte-{i}.pdf"
            if len(partes) == 1:
                conteudo = pdf  # preserva os bytes e assinatura quando não há separação
            else:
                escritor = PdfWriter()
                for pagina in leitor.pages[parte.inicio - 1 : parte.fim]:
                    escritor.add_page(pagina)
                buffer = io.BytesIO()
                escritor.write(buffer)
                conteudo = buffer.getvalue()
            (pasta / nome).write_bytes(conteudo)
            resultado.append(
                {
                    "inicio": parte.inicio,
                    "fim": parte.fim,
                    "tipo": parte.tipo,
                    "texto": parte.texto,
                    "arquivo": nome,
                }
            )
        return {"partes": resultado, "ocr": ocr, "paginas": len(textos)}
    except LeituraInvalida:
        raise
    except Exception as exc:
        raise LeituraInvalida("O PDF não pôde ser lido. Exporte novamente e reenvie.") from exc


def analisar(dados: bytes, nome: str) -> tuple[dict, bytes, list[bytes]]:
    if not dados or len(dados) > MAX_BYTES:
        raise LeituraInvalida("Envie um arquivo de até 25 MB.")
    with tempfile.TemporaryDirectory(prefix="pcpr-importacao-") as tmp:
        pasta = Path(tmp)
        origem = pasta / ("entrada" + Path(nome).suffix.lower())
        origem.write_bytes(dados)
        try:
            # Python e módulo internos, caminho temporário gerado aqui; sem shell.
            subprocess.run(  # noqa: S603 # nosec B603
                [sys.executable, "-m", __name__, str(origem), str(pasta)],
                check=True,
                capture_output=True,
                timeout=240,
                env={
                    **{
                        k: v
                        for k, v in os.environ.items()
                        if k in {"PATH", "SYSTEMROOT", "LANG", "LC_ALL", "FONTCONFIG_PATH"}
                    },
                    "HOME": str(pasta),
                    "TMPDIR": str(pasta),
                    "OMP_THREAD_LIMIT": "1",
                    "SAL_USE_VCLPLUGIN": "svp",
                },
            )
        except subprocess.TimeoutExpired as exc:
            raise LeituraInvalida("A leitura demorou demais. Divida o arquivo e reenvie.") from exc
        except subprocess.CalledProcessError as exc:
            raise LeituraInvalida(
                "A leitura foi interrompida. Exporte um PDF menor e reenvie."
            ) from exc
        resultado = json.loads((pasta / "resultado.json").read_text(encoding="utf-8"))
        if resultado.get("erro"):
            raise LeituraInvalida(resultado["erro"])
        return (
            resultado,
            (pasta / "convertido.pdf").read_bytes(),
            [(pasta / p["arquivo"]).read_bytes() for p in resultado["partes"]],
        )


def _principal():
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
        resource.setrlimit(resource.RLIMIT_FSIZE, (120 * 1024**2, 120 * 1024**2))
    origem, pasta = Path(sys.argv[1]), Path(sys.argv[2])
    try:
        resultado = extrair(origem, pasta)
    except Exception as exc:
        resultado = {
            "erro": str(exc)
            if isinstance(exc, LeituraInvalida)
            else "Não foi possível converter o arquivo. Exporte em PDF e reenvie."
        }
    (pasta / "resultado.json").write_text(json.dumps(resultado), encoding="utf-8")


if __name__ == "__main__":
    _principal()
