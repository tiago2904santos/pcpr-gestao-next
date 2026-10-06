"""Baixar documentos (paridade com o modal "Baixar documentos" da referência): os documentos
de um registro para marcar, e o pacote pedido — um arquivo, um PDF só ou um ZIP.

Regras da referência: todos marcados ao abrir; PDF ou DOCX; com PDF, a via assinada em vigor
(padrão) ou o arquivo original; "um PDF só" com 2 ou mais documentos em PDF; a ordem é a da
tela, não a do pedido; um documento que falha aborta o lote com a mensagem dele.

Diferença intencional: o ofício em rascunho entra como **minuta** (marca d'água) e nunca é
emitido por aqui — emitir é a ação da folha, com a conferência (a referência emitia ao baixar).
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass

from . import assinados, services, termos
from .models import Oficio, TermoAutorizacao, ViaAssinada

FORMATOS = ("pdf", "docx")


class PacoteInvalido(Exception):
    pass


@dataclass
class Item:
    valor: str
    nome: str
    detalhe: str
    estado: str  # "Minuta" | "PDF emitido" | "Gerado na hora" | "Assinado" | ...
    arquivo: str  # nome sem extensão
    pdf: Callable[[], bytes]
    docx: Callable[[], bytes]
    via: ViaAssinada | None = None

    def para_tela(self) -> dict:
        return {"valor": self.valor, "nome": self.nome, "detalhe": self.detalhe,
                "estado": self.estado, "assinado": self.via is not None}


def em_json(itens: list[Item]) -> str:
    return json.dumps([i.para_tela() for i in itens], ensure_ascii=False)


# ---------------------------------------------------------------- ofício
def _itens_do_oficio_proprio(oficio: Oficio) -> list[Item]:
    from .documentos.dados import dados_do_oficio
    from .documentos.docx import docx_do_html
    from .documentos.pdf import ASSETS, buscar_recurso, html_do_documento

    vias = assinados.vigentes_do(oficio)
    tipos = ["oficio"] + (["justificativa"] if oficio.justificativa.strip() else [])
    rascunho = oficio.situacao == Oficio.Situacao.RASCUNHO
    saida = []
    for tipo in tipos:
        emitido = None if rascunho else assinados.documento_emitido(oficio, tipo)
        via = vias.get((tipo, "")) if emitido is not None else None
        rotulo = "Ofício" if tipo == "oficio" else "Justificativa"

        def pdf(tipo=tipo, emitido=emitido) -> bytes:
            if emitido is not None:
                with emitido.arquivo.open("rb") as f:
                    return f.read()
            from weasyprint import HTML
            html = html_do_documento(tipo, dados_do_oficio(oficio), previa=True,
                                     regioes=services.regioes_vigentes(oficio, tipo))
            return HTML(string=html, base_url=str(ASSETS),
                        url_fetcher=buscar_recurso()).write_pdf()

        def docx(tipo=tipo, emitido=emitido) -> bytes:
            if emitido is not None:
                return docx_do_html(html_do_documento(tipo, emitido.dados),
                                    base_imagens=ASSETS)
            html = html_do_documento(tipo, dados_do_oficio(oficio),
                                     regioes=services.regioes_vigentes(oficio, tipo))
            return docx_do_html(html, base_imagens=ASSETS, minuta=True)

        base = f"{tipo}-{oficio.numero:02d}-{oficio.ano}"
        saida.append(Item(
            valor=tipo, nome=rotulo,
            detalhe=(f"Ofício {oficio.numero_formatado}" if tipo == "oficio"
                     else "Justificativa de prazo"),
            estado=("Minuta" if emitido is None else
                    "Assinado" if via is not None else f"PDF emitido · v{emitido.versao}"),
            arquivo=base if emitido is not None else f"minuta-{base}",
            pdf=pdf, docx=docx, via=via))
    return saida


def _itens_dos_termos(termos_do_registro, prefixo: bool) -> list[Item]:
    saida = []
    for termo in termos_do_registro:
        vias = assinados.vigentes_do(termo)
        ef = termos.efetivo(termo)
        for doc in termos.documentos_do_termo(termo, ef):
            chave = doc["chave"]

            def dados(termo=termo, chave=chave) -> dict:
                try:
                    return termos.dados_do_documento(termo, chave)
                except termos.TermoInvalido as exc:
                    raise PacoteInvalido(str(exc)) from None

            def pdf(dados=dados) -> bytes:
                return termos.pdf_do_documento(dados())

            def docx(dados=dados) -> bytes:
                return termos.docx_do_documento(dados())

            via = vias.get(("termo", chave))
            saida.append(Item(
                valor=f"termo-{termo.pk}-{chave}" if prefixo else chave,
                nome=f"Termo · {doc['titulo']}" if prefixo else doc["titulo"],
                detalhe=f"{termo}" if prefixo else doc["descricao"],
                estado="Assinado" if via is not None else "Gerado na hora",
                arquivo=termos.nome_do_arquivo(termo, chave, "pdf").rsplit(".", 1)[0],
                pdf=pdf, docx=docx,
                via=via))
    return saida


def itens_do_oficio(oficio: Oficio) -> list[Item]:
    """Ofício, justificativa (se houver texto) e os termos ativos ligados a ele."""
    ligados = list(TermoAutorizacao.objects.filter(
        oficio=oficio, situacao=TermoAutorizacao.Situacao.ATIVO).order_by("pk"))
    return _itens_do_oficio_proprio(oficio) + _itens_dos_termos(ligados, prefixo=True)


def itens_da_justificativa(oficio: Oficio) -> list[Item]:
    """Na lista de justificativas: a justificativa primeiro, depois o ofício (referência)."""
    proprios = _itens_do_oficio_proprio(oficio)
    return sorted(proprios, key=lambda i: i.valor != "justificativa")


def itens_do_termo(termo: TermoAutorizacao) -> list[Item]:
    return _itens_dos_termos([termo], prefixo=False)


def itens_da_ordem(ordem) -> list[Item]:
    """A OS (a via assinada, se houver). Baixar o PDF gera: fixa a data do documento."""
    from . import ordens
    via = assinados.vigentes_do(ordem).get(("ordem", ""))

    def pdf() -> bytes:
        return ordens.pdf_do_documento(ordens.dados_do_documento(ordem, fixar=True))

    def docx() -> bytes:
        return ordens.docx_do_documento(ordens.dados_do_documento(ordem, fixar=True))

    return [Item(valor="os", nome=str(ordem), detalhe=ordem.get_tipo_display(),
                 estado="Assinado" if via else ("Gerado" if ordem.documento_gerado_em
                                                else "Gerado na hora"),
                 arquivo=f"os-{ordem.numero:03d}-{ordem.ano}", pdf=pdf, docx=docx, via=via)]


def itens_do_plano(plano) -> list[Item]:
    """O plano: gerado, sai como está; ainda não gerado, com a marca de minuta."""
    from . import planos
    gerado = bool(plano.documento_gerado_em)

    def pdf() -> bytes:
        return planos.pdf_do_documento(planos.dados_do_documento(plano, fixar=gerado))

    def docx() -> bytes:
        return planos.docx_do_documento(planos.dados_do_documento(plano, fixar=gerado))

    return [Item(valor="plano", nome=str(plano), detalhe="Plano de trabalho",
                 estado="Gerado" if gerado else "Minuta",
                 arquivo=f"plano-{plano.numero:02d}-{plano.ano}", pdf=pdf, docx=docx)]


# ---------------------------------------------------------------- pacote
def _unicos(nomes: list[str]) -> list[str]:
    vistos: dict[str, int] = {}
    saida = []
    for nome in nomes:
        base, ponto, ext = nome.rpartition(".")
        n = vistos.get(nome, 0) + 1
        vistos[nome] = n
        saida.append(nome if n == 1 else f"{base} ({n}).{ext}" if ponto else f"{nome} ({n})")
    return saida


def _juntar(pdfs: list[bytes]) -> bytes:
    import pikepdf
    saida = pikepdf.Pdf.new()
    abertos = []
    try:
        for conteudo in pdfs:
            parte = pikepdf.Pdf.open(io.BytesIO(conteudo))
            abertos.append(parte)
            saida.pages.extend(parte.pages)
        buffer = io.BytesIO()
        saida.save(buffer)
        return buffer.getvalue()
    except pikepdf.PdfError:
        raise PacoteInvalido("Um dos PDFs (provavelmente uma via assinada) não pôde ser "
                             "juntado aos outros: baixe em arquivos separados.") from None
    finally:
        for parte in abertos:
            parte.close()


def montar(itens: list[Item], marcados: list[str], *, formato: str, versao: str,
           saida: str, nome_base: str) -> tuple[bytes, str, str]:
    """(conteúdo, nome do arquivo, tipo) do pacote pedido."""
    if formato not in FORMATOS:
        raise ValueError(formato)
    por_valor = {i.valor: i for i in itens}
    desconhecidos = [m for m in marcados if m not in por_valor]
    if desconhecidos:
        raise KeyError(desconhecidos[0])
    escolhidos = [i for i in itens if i.valor in set(marcados)]  # a ordem da tela
    if not escolhidos:
        raise PacoteInvalido("Marque ao menos um documento para baixar.")
    usar_via = formato == "pdf" and versao != "original"
    arquivos: list[tuple[str, bytes]] = []
    for item in escolhidos:
        if usar_via and item.via is not None:
            with item.via.arquivo.open("rb") as f:
                arquivos.append((f"{item.arquivo}-assinado.pdf", f.read()))
        else:
            gerar = item.pdf if formato == "pdf" else item.docx
            arquivos.append((f"{item.arquivo}.{formato}", gerar()))
    tipo_doc = ("application/pdf" if formato == "pdf" else
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    if len(arquivos) == 1:
        return arquivos[0][1], arquivos[0][0], tipo_doc
    if formato == "pdf" and saida == "unico":
        return _juntar([c for _, c in arquivos]), f"{nome_base}-documentos.pdf", "application/pdf"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as pacote:
        for nome, (_, conteudo) in zip(_unicos([n for n, _ in arquivos]), arquivos,
                                       strict=True):
            pacote.writestr(re.sub(r"[\\/]", "-", nome), conteudo)
    return buffer.getvalue(), f"{nome_base}-documentos.zip", "application/zip"



# ---------------------------------------------------------------- viagem (módulo 8c)
def itens_da_viagem(viagem) -> list[Item]:
    """Na ordem do processo (referência): por ofício, o ofício, a justificativa e os termos
    dele; os planos já gerados; as OS já geradas; os termos sem ofício. Cancelados ficam
    de fora; plano e OS ainda não gerados também (gerar é a ação da folha deles)."""
    from . import ordens, planos
    from .viagem import documentos

    docs = documentos(viagem)
    saida: list[Item] = []
    for oficio in docs.oficios:
        if oficio.situacao == Oficio.Situacao.CANCELADO:
            continue
        for item in _itens_do_oficio_proprio(oficio):
            item.valor = f"oficio-{oficio.pk}:{item.valor}"
            item.nome = f"{item.nome} {oficio.numero_formatado}" if item.nome == "Ofício" else (
                f"{item.nome} · Ofício {oficio.numero_formatado}")
            saida.append(item)
        ligados = [t for t in docs.termos if t.oficio_id == oficio.pk and not t.cancelado]
        saida += _itens_dos_termos(ligados, prefixo=True)
    for plano in docs.planos:
        if plano.cancelado or not plano.documento_gerado_em:
            continue

        def pdf_plano(plano=plano) -> bytes:
            return planos.pdf_do_documento(planos.dados_do_documento(plano, fixar=True))

        def docx_plano(plano=plano) -> bytes:
            return planos.docx_do_documento(planos.dados_do_documento(plano, fixar=True))

        saida.append(Item(valor=f"plano-{plano.pk}", nome=str(plano), detalhe="Plano de trabalho",
                          estado="Gerado", arquivo=f"plano-{plano.numero:02d}-{plano.ano}",
                          pdf=pdf_plano, docx=docx_plano))
    for ordem in docs.ordens:
        if ordem.cancelada or not ordem.documento_gerado_em:
            continue
        via = assinados.vigentes_do(ordem).get(("ordem", ""))

        def pdf_os(ordem=ordem) -> bytes:
            return ordens.pdf_do_documento(ordens.dados_do_documento(ordem, fixar=True))

        def docx_os(ordem=ordem) -> bytes:
            return ordens.docx_do_documento(ordens.dados_do_documento(ordem, fixar=True))

        saida.append(Item(valor=f"os-{ordem.pk}", nome=str(ordem), detalhe="Ordem de serviço",
                          estado="Assinado" if via else "Gerado",
                          arquivo=f"os-{ordem.numero:03d}-{ordem.ano}", pdf=pdf_os,
                          docx=docx_os, via=via))
    avulsos = [t for t in docs.termos if t.oficio_id is None and not t.cancelado]
    saida += _itens_dos_termos(avulsos, prefixo=True)
    return saida


def _seguro(nome: str) -> str:
    return " ".join(re.sub(r"[\/:*?\"<>|]", "-", nome).split())[:120]


def baixar_tudo(viagem) -> tuple[bytes, str, list[str]]:
    """O processo inteiro em PDF, um arquivo por documento, numerado na ordem do processo,
    com o LEIA-ME (referência): a via assinada onde houver; o que falhar não derruba o
    pacote — vai para "Não entraram"."""
    from . import ordens, planos
    falhas_conhecidas = (PacoteInvalido, ordens.OrdemInvalida, planos.PlanoInvalido,
                         services.RegraViolada)
    itens = itens_da_viagem(viagem)
    if not itens:
        raise PacoteInvalido("Nenhum documento pronto para baixar ainda.")
    arquivos: list[tuple[str, bytes]] = []
    sem_via: list[str] = []
    falhas: list[str] = []
    largura = max(2, len(str(len(itens))))
    for item in itens:
        rotulo = item.nome if item.detalhe in item.nome else f"{item.detalhe} · {item.nome}"
        try:
            if item.via is not None:
                with item.via.arquivo.open("rb") as f:
                    conteudo = f.read()
            else:
                conteudo = item.pdf()
                sem_via.append(rotulo)
        except falhas_conhecidas as exc:
            falhas.append(f"{rotulo}: {exc}")
            continue
        numero = str(len(arquivos) + 1).zfill(largura)
        arquivos.append((f"{numero} - {_seguro(rotulo)}.pdf", conteudo))
    if not arquivos:
        raise PacoteInvalido("Nenhum documento pronto para baixar ainda.")
    destinos = ", ".join(str(d.municipio) for d in viagem.destinos.select_related("municipio"))
    inicio, fim = viagem.data_inicio, viagem.data_fim or viagem.data_inicio
    periodo = (f"{inicio:%d/%m/%Y}" + (f" a {fim:%d/%m/%Y}" if fim and fim != inicio else "")
               if inicio else "não informado")
    linhas = [f"Viagem: {viagem}", f"Período: {periodo}", f"Destino: {destinos or '—'}", "",
              "Cada documento está num arquivo, na ordem do processo, para subir e assinar no "
              "eProtocolo.", "", *[nome for nome, _ in arquivos]]
    if sem_via:
        linhas += ["", "Ainda sem a versão assinada anexada no sistema:",
                   *[f"- {r}" for r in sem_via]]
    if falhas:
        linhas += ["", "Não entraram (complete o documento e baixe de novo):",
                   *[f"- {f}" for f in falhas]]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as pacote:
        pacote.writestr("00 - LEIA-ME.txt", "\r\n".join(linhas) + "\r\n")
        for nome, conteudo in arquivos:
            pacote.writestr(nome, conteudo)
    return buffer.getvalue(), f"viagem-{viagem.pk}-processo.zip", falhas
