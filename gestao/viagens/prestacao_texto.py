"""Os documentos da prestação de contas no visualizador/editor (ADR 0018): o diário de
bordo (um por equipe) e o relatório técnico (um por servidor), como o documento da OS e os
do termo — a folha em HTML, o PDF/DOCX e o texto editado por região, com versões.

A prestação emite vários documentos: `chave` diz qual — ``diario`` ou ``rt-<pk do servidor
na prestação>``. Os dados vêm de diario.dados_do_documento e relatorio.dados_do_documento;
as regras de versão são as de edicao_texto.py; cada versão é uma EdicaoPrestacao.
"""

from __future__ import annotations

from django.db import transaction

from . import diario as servico_diario
from . import policies
from . import relatorio as servico_rt
from .models import DiarioBordo, EdicaoPrestacao, PrestacaoContas, PrestacaoServidor
from .prestacao import PrestacaoInvalida, ativos

CHAVE_DIARIO = "diario"
TEMPLATES = {"diario": "viagens/documentos/diario_bordo.html",
             "rt": "viagens/documentos/relatorio_tecnico.html"}
ROTULOS = {"diario": {"corpo": "Diário de bordo"},
           "rt": {"corpo": "Relatório", "assinatura": "Assinatura"}}


class ConflitoDeEdicao(PrestacaoInvalida):
    """Outra pessoa salvou o texto deste documento depois que a folha foi aberta."""


def chave_rt(ps_pk: int) -> str:
    return f"rt-{ps_pk}"


def tipo_da_chave(chave: str) -> str:
    """"diario" ou "rt"; outra chave é inválida."""
    if chave == CHAVE_DIARIO:
        return "diario"
    if chave.startswith("rt-") and chave[3:].isdigit():
        return "rt"
    raise PrestacaoInvalida("Documento da prestação desconhecido.")


def servidor_da_chave(prestacao: PrestacaoContas, chave: str) -> PrestacaoServidor:
    ps = (ativos(PrestacaoServidor.objects.filter(prestacao=prestacao))
          .select_related("servidor").filter(pk=int(chave[3:])).first())
    if ps is None:
        raise PrestacaoInvalida("Este servidor não está na prestação.")
    ps.prestacao = prestacao
    return ps


def documentos(prestacao: PrestacaoContas, membros: list[PrestacaoServidor] | None = None
               ) -> list[dict]:
    """Os documentos que a prestação emite, na ordem das páginas: o diário e um RT por
    servidor — {chave, titulo, descricao, servidor}."""
    if membros is None:
        membros = list(ativos(PrestacaoServidor.objects.filter(prestacao=prestacao))
                       .select_related("servidor").order_by("servidor__nome"))
    saida: list[dict] = [{"chave": CHAVE_DIARIO, "titulo": "Diário de bordo",
                          "descricao": "da viatura, para a equipe", "servidor": None}]
    for ps in membros:
        saida.append({"chave": chave_rt(ps.pk), "titulo": "Relatório técnico",
                      "descricao": ps.servidor.nome, "servidor": ps})
    return saida


# ---------------------------------------------------------------- dados e HTML
def dados_do_documento(prestacao: PrestacaoContas, chave: str) -> dict:
    """Os dados do documento, com o texto editado em vigor (``regioes_editadas``)."""
    tipo = tipo_da_chave(chave)
    if tipo == "diario":
        d = DiarioBordo.objects.filter(prestacao=prestacao).first()
        if d is None:
            d = servico_diario.obter(prestacao)
        d.prestacao = prestacao
        dados = servico_diario.dados_do_documento(d)
    else:
        ps = servidor_da_chave(prestacao, chave)
        rt = servico_rt.obter(prestacao)
        dados = servico_rt.dados_do_documento(rt, ps)
    dados["chave"] = chave
    dados["regioes_editadas"] = regioes_vigentes(prestacao, chave)
    return dados


def html_do_modelo(dados: dict, *, folha: bool = False, nonce: str = "") -> str:
    """O documento como o modelo o gera, sem nenhum texto editado."""
    from django.template.loader import render_to_string

    from .documentos.pdf import _recursos
    return render_to_string(TEMPLATES[tipo_da_chave(dados["chave"])],
                            {"d": dados, "folha": folha, "nonce": nonce, **_recursos(folha)})


def html_do_documento(dados: dict, *, folha: bool = False, nonce: str = "",
                      regioes: dict[str, str] | None = None,
                      blocos_alterados: set[str] | None = None) -> str:
    """HTML com o texto editado em vigor (o de `dados`, se `regioes` não vier); `folha=True`
    é a versão de tela. PDF, DOCX, XLSX-não (o diário em planilha sai dos dados) e a folha."""
    from .documentos.regioes import aplicar_regioes, marcar_blocos_alterados
    if regioes is None:
        regioes = dados.get("regioes_editadas") or {}
    html = html_do_modelo(dados, folha=folha, nonce=nonce)
    if regioes:
        html = aplicar_regioes(html, regioes)
    if blocos_alterados:
        html = marcar_blocos_alterados(html, blocos_alterados)
    return html


def pdf_do_documento(dados: dict) -> bytes:
    import hashlib

    from weasyprint import HTML

    from .documentos.pdf import ASSETS, buscar_recurso
    html = html_do_documento(dados)
    return HTML(string=html, base_url=str(ASSETS), url_fetcher=buscar_recurso()).write_pdf(
        pdf_variant="pdf/a-2a", pdf_identifier=hashlib.sha256(html.encode()).digest()[:16],
        pdf_tags=True, custom_metadata=True, presentational_hints=True)


def docx_do_documento(dados: dict) -> bytes:
    from .documentos.docx import docx_do_html
    from .documentos.pdf import ASSETS
    return docx_do_html(html_do_documento(dados), base_imagens=ASSETS)


def regioes_do_modelo(dados: dict) -> dict[str, str]:
    from .documentos.regioes import extrair_regioes
    return extrair_regioes(html_do_modelo(dados))


# ---------------------------------------------------------------- versões do texto
def _versoes(prestacao: PrestacaoContas, chave: str):
    return EdicaoPrestacao.objects.filter(prestacao=prestacao, chave=chave)


def _criar(prestacao: PrestacaoContas, chave: str):
    return lambda **campos: EdicaoPrestacao.objects.create(prestacao=prestacao, chave=chave,
                                                           **campos)


def edicao_vigente(prestacao: PrestacaoContas, chave: str):
    from . import edicao_texto
    return edicao_texto.vigente(_versoes(prestacao, chave))


def regioes_vigentes(prestacao: PrestacaoContas, chave: str) -> dict[str, str]:
    edicao = edicao_vigente(prestacao, chave)
    return dict(edicao.regioes) if edicao is not None else {}


def regioes_da_versao(prestacao: PrestacaoContas, chave: str, pedido: str
                      ) -> tuple[dict[str, str] | None, set[str]]:
    """O que a folha mostra: ``?versao=N`` é uma versão do histórico (0, o modelo); sem
    pedido, a vigente. Devolve (regiões ou None para a vigente, blocos alterados); versão
    que não existe devolve (None, None) para a folha responder 404."""
    if pedido.isascii() and pedido.isdigit():
        numero = int(pedido)
        edicao = _versoes(prestacao, chave).filter(numero=numero).first() if numero else None
        if numero and edicao is None:
            return None, None  # type: ignore[return-value]
        return (dict(edicao.regioes) if edicao else {},
                {b["chave"] for b in edicao.blocos_alterados} if edicao else set())
    vigente = edicao_vigente(prestacao, chave)
    return None, ({b["chave"] for b in vigente.blocos_alterados} if vigente else set())


def pode_editar(usuario, prestacao: PrestacaoContas) -> bool:
    return servico_diario.pode_editar(usuario, prestacao)


def _travar(usuario, prestacao: PrestacaoContas) -> PrestacaoContas:
    atual = (PrestacaoContas.objects.select_for_update().select_related("oficio")
             .get(pk=prestacao.pk))
    policies.exigir(pode_editar(usuario, atual),
                    "Os documentos desta prestação não podem mais ser alterados.")
    return atual


@transaction.atomic
def salvar_texto(prestacao: PrestacaoContas, usuario, chave: str, regioes: dict[str, str], *,
                 versao_base: int | None = None):
    from . import edicao_texto
    atual = _travar(usuario, prestacao)
    return edicao_texto.salvar(
        _versoes(atual, chave), _criar(atual, chave), usuario,
        regioes_do_modelo(dados_do_documento(atual, chave)), regioes,
        versao_base=versao_base, invalido=PrestacaoInvalida, conflito=ConflitoDeEdicao,
        guardar_modelos=True)


@transaction.atomic
def restaurar_texto(prestacao: PrestacaoContas, usuario, chave: str, numero: int):
    from . import edicao_texto
    atual = _travar(usuario, prestacao)
    return edicao_texto.restaurar(_versoes(atual, chave), _criar(atual, chave), usuario,
                                  numero, invalido=PrestacaoInvalida)


@transaction.atomic
def voltar_texto_ao_modelo(prestacao: PrestacaoContas, usuario, chave: str):
    from . import edicao_texto
    atual = _travar(usuario, prestacao)
    return edicao_texto.voltar_ao_modelo(_versoes(atual, chave), _criar(atual, chave), usuario)
