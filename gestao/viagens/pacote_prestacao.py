"""Pacote final da prestação de contas (módulo 9d-2, paridade com `partes_do_pacote`,
`pacotes_da_equipe_zip` e `nome_arquivo_prestacao_consolidado` da referência).

Um PDF por servidor, na ordem oficial: ofício (a via assinada; sem ela, o PDF emitido) →
despacho(s) → relatório técnico (o assinado dele; sem ele, o gerado) → diário de bordo (o
assinado; sem ele, o gerado) → comprovante(s) pela data da operação. Imagens viram página.
Sem nº da solicitação, despacho ou comprovante não há pacote (não há substituto gerado).
"""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile

from django.utils import timezone

from . import anexos, assinados, diario, relatorio
from .models import AnexoPrestacao, PrestacaoContas, PrestacaoServidor, ViaAssinada
from .pacotes import PacoteInvalido, _juntar


class PacoteIncompleto(Exception):
    pass


def pendencias_do_pacote(ps: PrestacaoServidor) -> list[str]:
    """O que o pacote cobra e o sistema não gera (referência: `pendencias_consolidado`)."""
    falta = []
    if not ps.numero_solicitacao.strip():
        falta.append("Informe o número da solicitação deste servidor.")
    ativos = anexos.ativos(AnexoPrestacao.objects.filter(prestacao_id=ps.prestacao_id))
    if not ativos.filter(tipo=AnexoPrestacao.Tipo.DESPACHO).exists():
        falta.append("Anexe o despacho assinado do ofício.")
    if not ativos.filter(tipo=AnexoPrestacao.Tipo.COMPROVANTE, servidor=ps).exists():
        falta.append("Anexe o comprovante de saque/transferência deste servidor.")
    return falta


def _como_pdf(anexo: AnexoPrestacao) -> bytes:
    with anexo.arquivo.open("rb") as f:
        conteudo = f.read()
    if conteudo.startswith(b"%PDF-"):
        return conteudo
    from PIL import Image  # PNG/JPG: uma página, do tamanho da imagem (como a referência)
    saida = io.BytesIO()
    Image.open(io.BytesIO(conteudo)).convert("RGB").save(saida, format="PDF", resolution=150)
    return saida.getvalue()


def _ordenados(qs, tipo: str):
    qs = anexos.ativos(qs.filter(tipo=tipo))
    if tipo == AnexoPrestacao.Tipo.COMPROVANTE:
        from django.db.models import F
        return qs.order_by(F("data_operacao").asc(nulls_last=True), "enviado_em", "pk")
    return qs.order_by("enviado_em", "pk")


def partes(ps: PrestacaoServidor) -> list[tuple[str, bytes]]:
    falta = pendencias_do_pacote(ps)
    if falta:
        raise PacoteIncompleto(" ".join(falta))
    p = ps.prestacao
    oficio = p.oficio
    da_equipe = AnexoPrestacao.objects.filter(prestacao=p, servidor__isnull=True)
    do_servidor = AnexoPrestacao.objects.filter(servidor=ps)
    saida: list[tuple[str, bytes]] = []
    via = assinados.vigente(assinados.Alvo(ViaAssinada.Tipo.OFICIO, oficio))
    if via is not None:  # com os números de solicitação carimbados (9d-3), se houver
        from . import carimbo
        saida.append(("ofício assinado", carimbo.carimbado(via)))
    else:
        doc = assinados.documento_emitido(oficio, "oficio")
        if doc is None or not doc.arquivo:
            raise PacoteIncompleto("O PDF do ofício ainda não foi gerado.")
        with doc.arquivo.open("rb") as f:
            saida.append(("ofício", f.read()))
    saida += [("despacho assinado", _como_pdf(a))
              for a in _ordenados(da_equipe, AnexoPrestacao.Tipo.DESPACHO)]
    rts = [("relatório técnico assinado", _como_pdf(a))
           for a in _ordenados(do_servidor, AnexoPrestacao.Tipo.RT_ASSINADO)]
    if not rts:
        rt = relatorio.obter(p)
        rts = [("relatório técnico",
                relatorio.pdf_do_documento(relatorio.dados_do_documento(rt, ps)))]
    saida += rts
    dbs = [("diário de bordo assinado", _como_pdf(a))
           for a in _ordenados(da_equipe, AnexoPrestacao.Tipo.DB_ASSINADO)]
    if not dbs:
        d = diario.obter(p)
        dbs = [("diário de bordo", diario.pdf_do_documento(diario.dados_do_documento(d)))]
    saida += dbs
    saida += [("comprovante", _como_pdf(a))
              for a in _ordenados(do_servidor, AnexoPrestacao.Tipo.COMPROVANTE)]
    return saida


def pdf(ps: PrestacaoServidor) -> bytes:
    try:
        return _juntar([conteudo for _, conteudo in partes(ps)])
    except PacoteInvalido as exc:  # um PDF anexado que o pikepdf não abre
        raise PacoteIncompleto(str(exc)) from None


def _ascii(texto: str) -> str:
    """Sem acentos nem caracteres especiais (sistemas externos recusam) — referência."""
    texto = re.sub(r"[\\/]+", "-", (texto or "").strip())
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^A-Za-z0-9 ._-]", "", texto)
    return re.sub(r"\s+", " ", texto).strip(" .") or "documento"


def nome_do_pdf(ps: PrestacaoServidor) -> str:
    """"Prestação solicitação <nº> Ofício <n-ano> <primeiro nome> <destino> <data>.pdf"."""
    oficio = ps.prestacao.oficio
    trechos = list(oficio.trechos.select_related("destino").order_by("ordem"))
    destino = next((t.destino.nome for t in trechos if t.destino != oficio.sede), "")
    data = (f"{timezone.localtime(trechos[0].saida_em):%d-%m-%Y}" if trechos else "")
    partes_nome = ["Prestação"]
    if ps.numero_solicitacao.strip():
        partes_nome.append(f"solicitação {ps.numero_solicitacao.strip()}")
    partes_nome.append(f"Ofício {oficio.numero_formatado.replace('/', '-')}")
    primeiro = (ps.servidor.nome.split() or [""])[0].capitalize()
    partes_nome += [p for p in (primeiro, destino, data) if p]
    return f"{_ascii(' '.join(partes_nome))}.pdf"


def zip_da_equipe(prestacao: PrestacaoContas) -> tuple[bytes, int]:
    """Um PDF por servidor pronto; quem não está pronto vai para PENDENCIAS.txt com o que
    falta (o erro de um não derruba os outros). Devolve o ZIP e quantos pacotes entraram."""
    from . import prestacao as servico

    buffer = io.BytesIO()
    pendentes: list[tuple[str, list[str]]] = []
    gerados, usados = 0, set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for ps in servico.ativos(PrestacaoServidor.objects.filter(prestacao=prestacao)
                                 .select_related("servidor").order_by("servidor__nome", "pk")):
            ps.prestacao = prestacao
            try:
                conteudo = pdf(ps)
            except PacoteIncompleto as exc:
                pendentes.append((ps.servidor.nome, [str(exc)]))
                continue
            nome = nome_do_pdf(ps)
            if nome in usados:
                nome = f"{nome[:-4]} {ps.pk}.pdf"
            usados.add(nome)
            z.writestr(nome, conteudo)
            gerados += 1
        if pendentes:
            linhas = [f"Pendências da prestação do ofício {prestacao.oficio.numero_formatado}", ""]
            for nome, itens in pendentes:
                linhas += [nome, *(f"  - {i}" for i in itens), ""]
            z.writestr("PENDENCIAS.txt", "\n".join(linhas))
    return buffer.getvalue(), gerados


def nome_do_zip(prestacao: PrestacaoContas) -> str:
    return f"{_ascii(f'Pacotes da equipe Ofício {prestacao.oficio.numero_formatado}')}.zip"
