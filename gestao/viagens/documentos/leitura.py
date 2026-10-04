"""Leitura de PDF para conferir a via assinada (ADR 0022): o texto das primeiras páginas e
os campos de assinatura, com `pypdf`. Tudo local; nenhum certificado é validado. Qualquer
falha vira aviso — a conferência nunca derruba o anexo. A interpretação do que se leu fica
em `viagens/dominio/conferencia.py`."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta, timezone
from io import BytesIO

from django.utils import timezone as dj_timezone

from ..dominio import conferencia as dominio

log = logging.getLogger(__name__)

RX_DATA_PDF = re.compile(
    r"D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?([+\-Z])?(\d{2})?'?(\d{2})?")
# CN no DER do certificado: OID 2.5.4.3, depois UTF8String (0x0C) ou PrintableString (0x13).
RX_CN_DER = re.compile(rb"\x06\x03\x55\x04\x03[\x0c\x13]([\x01-\x7f])")
RX_AC = re.compile(r"(?i)^(AC\b|Autoridade Certificadora|ICP-Brasil)")


def _data_pdf(valor) -> datetime | None:
    """`D:20260924103000-03'00'` → datetime no fuso local (ingênuo, como a tela mostra)."""
    m = RX_DATA_PDF.search(str(valor or ""))
    if not m:
        return None
    try:
        momento = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                           int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0))
    except ValueError:
        return None
    sinal = m.group(7)
    if sinal in ("+", "-"):
        desvio = timedelta(hours=int(m.group(8) or 0), minutes=int(m.group(9) or 0))
        momento = momento.replace(tzinfo=timezone(desvio if sinal == "+" else -desvio))
    elif sinal == "Z":
        momento = momento.replace(tzinfo=UTC)
    else:
        return momento
    return dj_timezone.localtime(momento).replace(tzinfo=None)


def _nome_do_certificado(contents) -> str:
    """O CN do assinante no PKCS#7, sem validar nada: o da ICP-Brasil é "NOME:CPF"."""
    try:
        dados = bytes(contents)
    except (TypeError, ValueError):
        return ""
    candidatos = []
    for m in RX_CN_DER.finditer(dados):
        valor = dados[m.end():m.end() + m.group(1)[0]]
        try:
            texto = valor.decode("utf-8").strip()
        except UnicodeDecodeError:
            continue
        if texto:
            candidatos.append(texto)
    for texto in candidatos:  # o do assinante traz o CPF
        if re.search(r":\d{11}$", texto):
            return texto.rsplit(":", 1)[0].strip()
    for texto in reversed(candidatos):  # senão, o último que não é autoridade certificadora
        if not RX_AC.match(texto):
            return texto
    return ""


def _texto(valor) -> str:
    return str(valor or "").strip()


def ler(dados: bytes) -> tuple[str, list[dominio.Assinante], int, bool]:
    """(texto das primeiras páginas, campos de assinatura, páginas lidas, abriu?)."""
    from pypdf import PdfReader

    registro = logging.getLogger("pypdf")  # PDF malformado é caso normal aqui, não erro
    nivel = registro.level
    registro.setLevel(logging.ERROR)
    try:
        leitor = PdfReader(BytesIO(dados))
        paginas = list(leitor.pages[:dominio.PAGINAS_LIDAS])
    except Exception:
        registro.setLevel(nivel)
        return "", [], 0, False
    try:
        partes = []
        for pagina in paginas:
            try:
                partes.append(pagina.extract_text() or "")
            except Exception:
                partes.append("")
        campos = []
        try:
            for campo in (leitor.get_fields() or {}).values():
                if str(campo.get("/FT") or "") != "/Sig":
                    continue
                valor = campo.get("/V")
                valor = valor.get_object() if hasattr(valor, "get_object") else valor
                if not valor:
                    continue
                nome_campo = _texto(valor.get("/Name"))
                nome = nome_campo or _nome_do_certificado(valor.get("/Contents") or b"")
                campos.append(dominio.Assinante(
                    nome, _data_pdf(valor.get("/M")),
                    "campo" if nome_campo else "certificado"))
        except Exception:
            log.info("campos de assinatura ilegíveis", exc_info=True)
        return "\n".join(partes), campos, len(paginas), True
    finally:
        registro.setLevel(nivel)


def conferir(dados: bytes, esperado: dominio.Esperado) -> dominio.Conferencia:
    try:
        texto, campos, paginas, legivel = ler(dados)
        return dominio.conferir(texto, campos, esperado, paginas=paginas, legivel=legivel)
    except Exception:
        log.exception("Falha ao conferir a via assinada")
        falha = dominio.Conferencia()
        falha.avisos.append("Não foi possível conferir o PDF assinado.")
        return falha
