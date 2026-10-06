"""Termos de autorização: o que vale em cada termo (próprio ou herdado do ofício), a escrita
e os dados dos documentos.

Paridade com `viagens_termos` da referência:
- o termo pode estar ligado a um ofício e herda dele o que ficar em branco — destinos (os
  do roteiro do ofício), período (saída e chegada), servidores (a equipe) e viatura;
- sem ofício, destino e data são obrigatórios; a data final, vazia, repete a inicial;
- um documento por servidor (variante completa, com ou sem viatura), o **genérico** (só
  destino e período, para preencher à mão) e o **da viatura** (servidor em branco).

Toda gravação passa por aqui; a auditoria é do banco (trigger).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from django.db import transaction
from django.db.models import Prefetch, prefetch_related_objects
from django.utils import timezone

from gestao.cadastros.models import ConfiguracaoInstitucional, Municipio, Servidor, Viatura

from . import policies
from .models import Oficio, TermoAutorizacao, TermoDestino, Trecho, Viajante


class TermoInvalido(Exception):
    """Erro com mensagem pronta para o usuário."""


# Limites de um termo (cada servidor é um documento a gerar; cada destino, uma busca).
MAX_SERVIDORES = 50
MAX_DESTINOS = 30


MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro")

# O que a lista e as telas carregam de uma vez (número fixo de consultas).
PREFETCH_TERMOS = (
    Prefetch("destinos", queryset=TermoDestino.objects.select_related("municipio")),
    Prefetch("servidores", queryset=Servidor.objects.select_related("cargo", "unidade")
             .order_by("nome")),
    Prefetch("oficio__trechos", queryset=Trecho.objects.select_related("destino")
             .order_by("ordem")),
    Prefetch("oficio__viajantes", queryset=Viajante.objects.select_related(
        "servidor__cargo", "servidor__unidade").order_by("servidor__nome")),
)


def com_dados(qs):
    return qs.select_related("oficio__sede", "oficio__viatura__combustivel",
                             "viatura__combustivel", "viatura__unidade",
                             "unidade").prefetch_related(*PREFETCH_TERMOS)


# ---------------------------------------------------------------- valores efetivos
@dataclass
class Efetivo:
    destinos: list[Municipio] = field(default_factory=list)
    inicio: date | None = None
    fim: date | None = None
    servidores: list[Servidor] = field(default_factory=list)
    viatura: Viatura | None = None
    herdados: list[str] = field(default_factory=list)

    @property
    def destino_texto(self) -> str:
        return ", ".join(f"{m.nome}/{m.uf}" for m in self.destinos)

    @property
    def periodo_curto(self) -> str:
        """"23/10 a 24/10/2026" — o mesmo formato das listas de ofícios e roteiros."""
        if not self.inicio:
            return ""
        if not self.fim or self.fim == self.inicio:
            return f"{self.inicio:%d/%m/%Y}"
        if self.inicio.year == self.fim.year:
            return f"{self.inicio:%d/%m} a {self.fim:%d/%m/%Y}"
        return f"{self.inicio:%d/%m/%Y} a {self.fim:%d/%m/%Y}"

    @property
    def completo(self) -> bool:
        """Com destino e período (sem eles, o documento sai só com lacunas)."""
        return bool(self.destinos and self.inicio)

    @property
    def destinos_frase(self) -> str:
        """"no município de A" / "nos municípios de A e B" (concordância do documento)."""
        nomes = [f"{m.nome}/{m.uf}" for m in self.destinos]
        if not nomes:
            return ""
        if len(nomes) == 1:
            return f"no município de {nomes[0]}"
        return f"nos municípios de {', '.join(nomes[:-1])} e {nomes[-1]}"

    @property
    def periodo_extenso(self) -> str:
        return periodo_por_extenso(self.inicio, self.fim)


def periodo_por_extenso(inicio: date | None, fim: date | None) -> str:
    """"no dia 10 de julho de 2026", "nos dias 10 até 12 de julho de 2026"… (referência)."""
    if not inicio:
        return ""

    def extenso(d: date) -> str:
        return f"{d.day} de {MESES[d.month - 1]} de {d.year}"

    if not fim or fim == inicio:
        return f"no dia {extenso(inicio)}"
    if (inicio.month, inicio.year) == (fim.month, fim.year):
        return f"nos dias {inicio.day} até {fim.day} de {MESES[inicio.month - 1]} de {inicio.year}"
    if inicio.year == fim.year:
        return (f"nos dias {inicio.day} de {MESES[inicio.month - 1]} até {fim.day} de "
                f"{MESES[fim.month - 1]} de {fim.year}")
    return f"nos dias {extenso(inicio)} até {extenso(fim)}"


def _do_oficio(oficio: Oficio) -> tuple[list[Municipio], date | None, date | None]:
    trechos = list(oficio.trechos.all())
    destinos: list[Municipio] = []
    for t in trechos:
        if t.destino_id != oficio.sede_id and t.destino not in destinos:
            destinos.append(t.destino)
    if not trechos:
        return destinos, None, None
    inicio = timezone.localdate(trechos[0].saida_em)
    fim = timezone.localdate(trechos[-1].chegada_em)
    return destinos, inicio, fim


def heranca_do_oficio(oficio: Oficio | None) -> dict[str, str]:
    """O que um termo em branco usaria deste ofício, em texto (para a tela mostrar antes de
    salvar e ao lado de cada campo)."""
    if oficio is None:
        return {}
    ef = efetivo(TermoAutorizacao(oficio=oficio, unidade_id=oficio.unidade_id))
    equipe = ef.servidores
    nomes = ", ".join(s.nome for s in equipe[:4]) + (f" e mais {len(equipe) - 4}"
                                                     if len(equipe) > 4 else "")
    return {k: v for k, v in {
        "destinos": ef.destino_texto,
        "periodo": ef.periodo_curto,
        "servidores": f"{len(equipe)} servidor{'es' if len(equipe) != 1 else ''}: {nomes}"
        if equipe else "",
        "viatura": str(ef.viatura) if ef.viatura else "",
    }.items() if v}


def efetivo(termo: TermoAutorizacao) -> Efetivo:
    """O que vale no termo: o próprio, ou o do ofício quando em branco."""
    if termo.pk and not hasattr(termo, "_prefetched_objects_cache"):
        prefetch_related_objects([termo], *PREFETCH_TERMOS)
    ef = Efetivo()
    oficio = termo.oficio if termo.oficio_id else None
    ef.destinos = [d.municipio for d in termo.destinos.all()] if termo.pk else []
    ef.inicio, ef.fim = termo.data_inicio, termo.data_fim or termo.data_inicio
    ef.servidores = list(termo.servidores.all()) if termo.pk else []
    ef.viatura = termo.viatura if termo.viatura_id else None
    if oficio is None:
        return ef
    destinos, inicio, fim = _do_oficio(oficio)
    if not ef.destinos and destinos:
        ef.destinos = destinos
        ef.herdados.append("destinos")
    if not ef.inicio and inicio:
        ef.inicio, ef.fim = inicio, fim
        ef.herdados.append("período")
    if not ef.servidores:
        equipe = [v.servidor for v in oficio.viajantes.all()]
        if equipe:
            ef.servidores = equipe
            ef.herdados.append("servidores")
    if (ef.viatura is None and oficio.viatura_id
            and oficio.tipo_transporte == Oficio.TipoTransporte.VIATURA):
        ef.viatura = oficio.viatura
        ef.herdados.append("viatura")
    return ef


# ---------------------------------------------------------------- escrita
@transaction.atomic
def salvar(usuario, *, pk: int | None = None, oficio: Oficio | None = None,
           evento: str = "", data_inicio: date | None = None, data_fim: date | None = None,
           destinos: list[Municipio] | None = None, servidores=(),
           viatura: Viatura | None = None, versao: str = "") -> TermoAutorizacao:
    """Cria ou altera. `versao` (o `atualizado_em` que a tela abriu) recusa gravar por cima
    de quem salvou depois (a tela grava sozinha a cada pausa)."""
    destinos = list(dict.fromkeys(destinos or []))  # sem repetir, na ordem informada
    if pk:
        termo = TermoAutorizacao.objects.select_for_update().get(pk=pk)
        policies.exigir(policies.pode_editar_termo(usuario, termo),
                        "Você não pode alterar este termo.")
        if versao and versao != versao_de(termo):
            raise TermoInvalido("Outra pessoa alterou este termo depois que você abriu a tela. "
                         "Recarregue a página para ver a versão atual (o que você "
                         "digitou continua na tela até lá).")
    else:
        policies.exigir(policies.pode_criar_termo(usuario),
                        "Você não pode criar termos de autorização.")
        termo = TermoAutorizacao(unidade=policies.unidade_do_usuario(usuario),
                                 criado_por=usuario)
    # Os documentos de antes: os que surgirem agora (servidor, viatura) herdam o texto editado.
    docs_antes = {d["chave"] for d in documentos_do_termo(termo)} if termo.pk else set()
    if oficio is not None:
        policies.exigir(policies.pode_ver(usuario, oficio), "Ofício não encontrado.")
        if oficio.situacao == Oficio.Situacao.CANCELADO:
            raise TermoInvalido("O ofício escolhido está cancelado.")
        if termo.pk is None:
            # O termo é da unidade do ofício (senão a equipe e os dados de um ofício de
            # outra unidade ficariam à vista de quem não os vê).
            termo.unidade = oficio.unidade
        elif oficio.unidade_id != termo.unidade_id:
            raise TermoInvalido("O ofício escolhido é de outra unidade.")
    servidores = list(servidores)
    if len(servidores) > MAX_SERVIDORES:
        raise TermoInvalido(f"No máximo {MAX_SERVIDORES} servidores por termo.")
    if len(destinos) > MAX_DESTINOS:
        raise TermoInvalido(f"No máximo {MAX_DESTINOS} destinos por termo.")
    # Destino e período podem ficar para depois: o termo nasce rascunho ("Novo termo" já o
    # cria) e o que falta aparece como pendência (efetivo().completo).
    if data_inicio and data_fim and data_fim < data_inicio:
        raise TermoInvalido("A data final não pode ser anterior à inicial.")
    if data_fim and not data_inicio:
        raise TermoInvalido("Informe a data inicial.")
    termo.oficio = oficio
    termo.evento = " ".join((evento or "").split()) or TermoAutorizacao._meta.get_field(
        "evento").default
    termo.data_inicio, termo.data_fim = data_inicio, (data_fim or data_inicio)
    termo.viatura = viatura
    termo.save()
    termo.servidores.set(servidores)
    atuais = [d.municipio_id for d in termo.destinos.order_by("ordem", "id")]
    if atuais != [m.pk for m in destinos]:  # só regrava se mudou (trilha de auditoria limpa)
        termo.destinos.all().delete()
        TermoDestino.objects.bulk_create(
            [TermoDestino(termo=termo, municipio=m, ordem=i) for i, m in enumerate(destinos)])
    if docs_antes:
        _herdar_texto_editado(termo, usuario, docs_antes)
    return termo


def versao_de(termo: TermoAutorizacao) -> str:
    return termo.atualizado_em.isoformat() if termo.atualizado_em else ""


@transaction.atomic
def cancelar(usuario, pk: int, motivo: str) -> TermoAutorizacao:
    termo = TermoAutorizacao.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_cancelar_termo(usuario, termo),
                    "Você não pode cancelar este termo.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise TermoInvalido("Informe o motivo do cancelamento.")
    if len(motivo) > 1000:
        raise TermoInvalido("O motivo passa de 1000 caracteres: resuma.")
    if termo.cancelado:
        raise TermoInvalido("O termo já está cancelado.")
    termo.situacao, termo.motivo_cancelamento = TermoAutorizacao.Situacao.CANCELADO, motivo
    termo.cancelado_em = timezone.now()
    termo.save(update_fields=["situacao", "motivo_cancelamento", "cancelado_em",
                              "atualizado_em"])
    return termo


@transaction.atomic
def reativar(usuario, pk: int) -> TermoAutorizacao:
    termo = TermoAutorizacao.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_cancelar_termo(usuario, termo),
                    "Você não pode reativar este termo.")
    if not termo.cancelado:
        raise TermoInvalido("O termo não está cancelado.")
    termo.situacao, termo.motivo_cancelamento = TermoAutorizacao.Situacao.ATIVO, ""
    termo.cancelado_em = None
    termo.save(update_fields=["situacao", "motivo_cancelamento", "cancelado_em",
                              "atualizado_em"])
    return termo


@transaction.atomic
def excluir(usuario, pk: int) -> str:
    termo = TermoAutorizacao.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_excluir_termo(usuario, termo),
                    "Você não pode excluir este termo.")
    if termo.vias_assinadas.exists():
        raise TermoInvalido("Este termo tem via assinada guardada: cancele-o em vez de "
                            "excluir.")
    nome = str(termo)
    termo.delete()
    return nome


# ---------------------------------------------------------------- documentos
GENERICO, VIATURA = "generico", "viatura"


def documentos_do_termo(termo: TermoAutorizacao, ef: Efetivo | None = None) -> list[dict]:
    """Os documentos que o termo emite: um por servidor, o genérico e (havendo viatura) o
    da viatura. `chave` é o que a rota de geração recebe."""
    ef = ef or efetivo(termo)
    docs = [{"chave": str(s.pk), "titulo": s.nome, "descricao": "Termo do servidor"}
            for s in ef.servidores]
    docs.append({"chave": GENERICO, "titulo": "Termo genérico",
                 "descricao": "Só destino e período, para preencher à mão"})
    if ef.viatura is not None:
        docs.append({"chave": VIATURA, "titulo": f"Termo da viatura {ef.viatura}",
                     "descricao": "Viatura preenchida, servidor em branco"})
    return docs


def dados_do_documento(termo: TermoAutorizacao, chave: str) -> dict:
    """Dados de um documento do termo (`chave`: id do servidor, "generico" ou "viatura"),
    com o texto editado no visualizador (EdicaoTermo), que vale para a folha, o PDF e o
    DOCX — já levado para os dados atuais (regioes_vigentes)."""
    dados = _dados_do_modelo(termo, chave)
    dados["regioes_editadas"] = regioes_vigentes(termo, chave, dados)
    return dados


def _dados_do_modelo(termo: TermoAutorizacao, chave: str) -> dict:
    """Os dados do documento sem o texto editado: o que o modelo usa para gerar."""
    ef = efetivo(termo)
    config = ConfiguracaoInstitucional.objects.filter(unidade=termo.unidade).first()
    if config is None:
        raise TermoInvalido("A unidade do termo ainda não tem configuração (cabeçalho e "
                            "rodapé): peça ao gestor para cadastrá-la.")
    participante = None
    if chave not in (GENERICO, VIATURA):
        participante = next((s for s in ef.servidores if str(s.pk) == chave), None)
        if participante is None:
            raise TermoInvalido("Este servidor não está no termo.")
    viatura = ef.viatura if chave != GENERICO else None
    sigla = termo.unidade.sigla or termo.unidade.nome
    return {
        "titulo": f"Termo de autorização #{termo.pk}",
        "sigla": sigla,
        "unidade_nome": config.nome_extenso,
        "cabecalho_unidade": config.nome_extenso.upper(),
        "rodape": config.rodape,
        "evento": termo.evento,
        "periodo": ef.periodo_extenso,
        "destino": ef.destino_texto,
        "destinos_frase": ef.destinos_frase,
        # Frases em duas partes — a ligação ("nos dias", "no município de") e o dado, que
        # sai em negrito como os demais dados preenchidos (nome, CPF, lotação…).
        "periodo_partes": _partes(ef.periodo_extenso, ("nos dias", "no dia")),
        "destinos_partes": _partes(ef.destinos_frase, ("nos municípios de", "no município de")),
        "participante": None if participante is None else {
            "nome": participante.nome, "rg": participante.rg_formatado or participante.rg,
            "cpf": participante.cpf_formatado, "telefone": participante.telefone_formatado,
            "lotacao": getattr(participante.unidade, "nome", ""),
        },
        "viatura": None if viatura is None else {
            "modelo": viatura.modelo, "placa": viatura.placa_formatada,
            "combustivel": getattr(viatura.combustivel, "nome", ""),
        },
    }


def _partes(frase: str, ligacoes: tuple[str, ...]) -> tuple[str, str]:
    """"nos dias 13 até 16 de outubro" → ("nos dias", "13 até 16 de outubro")."""
    for ligacao in ligacoes:
        if frase.startswith(ligacao + " "):
            return ligacao, frase[len(ligacao) + 1:]
    return "", frase


def nome_do_arquivo(termo: TermoAutorizacao, chave: str, extensao: str) -> str:
    sufixo = {GENERICO: "generico", VIATURA: "viatura"}.get(chave, f"servidor-{chave}")
    return f"termo-{termo.pk}-{sufixo}.{extensao}"


def html_do_modelo(dados: dict, *, folha: bool = False, nonce: str = "") -> str:
    """O documento como o modelo o gera, sem nenhum texto editado."""
    from django.template.loader import render_to_string

    from .documentos.pdf import _recursos
    return render_to_string("viagens/documentos/termo.html",
                            {"d": dados, "folha": folha, "nonce": nonce, **_recursos(folha)})


def html_do_documento(dados: dict, *, folha: bool = False, nonce: str = "",
                      regioes: dict[str, str] | None = None,
                      blocos_alterados: set[str] | None = None) -> str:
    """HTML do documento com o texto editado em vigor (o de `dados`, se `regioes` não vier);
    `folha=True` é a versão de tela (dentro do visualizador). PDF, DOCX e a folha saem
    daqui: o que se edita é o que se baixa."""
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
    """PDF/A-2a marcado, como os demais documentos."""
    import hashlib

    from weasyprint import HTML

    from .documentos.pdf import ASSETS
    html = html_do_documento(dados)
    identificador = hashlib.sha256(html.encode()).digest()[:16]
    from .documentos.pdf import buscar_recurso
    return HTML(string=html, base_url=str(ASSETS), url_fetcher=buscar_recurso()).write_pdf(
        pdf_variant="pdf/a-2a", pdf_identifier=identificador, pdf_tags=True,
        custom_metadata=True, presentational_hints=True)


def docx_do_documento(dados: dict) -> bytes:
    from .documentos.docx import docx_do_html
    from .documentos.pdf import ASSETS
    return docx_do_html(html_do_documento(dados), base_imagens=ASSETS)


def pdf_unico(termo: TermoAutorizacao) -> bytes:
    """Todos os documentos do termo num PDF só (servidores, genérico e viatura)."""
    import io

    import pikepdf
    saida = pikepdf.Pdf.new()
    abertos = []
    for doc in documentos_do_termo(termo):
        parte = pikepdf.Pdf.open(io.BytesIO(pdf_do_documento(
            dados_do_documento(termo, doc["chave"]))))
        abertos.append(parte)
        saida.pages.extend(parte.pages)
    buffer = io.BytesIO()
    saida.save(buffer)
    for parte in abertos:
        parte.close()
    return buffer.getvalue()


def zip_de_docx(termo: TermoAutorizacao) -> bytes:
    import io
    import zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as arquivo:
        for doc in documentos_do_termo(termo):
            arquivo.writestr(nome_do_arquivo(termo, doc["chave"], "docx"),
                             docx_do_documento(dados_do_documento(termo, doc["chave"])))
    return buffer.getvalue()


# ---------------------------------------------------------------- texto editado (ADR 0018)
# Como no ofício: cada documento do termo (servidor, genérico, viatura) pode ter o texto
# editado no visualizador; as regras de versão ficam em edicao_texto.py.


class ConflitoDeEdicao(TermoInvalido):
    """Outra pessoa salvou o texto deste documento depois que a folha foi aberta."""


def _chave_valida(termo: TermoAutorizacao, chave: str) -> str:
    if chave not in {d["chave"] for d in documentos_do_termo(termo)}:
        raise TermoInvalido("Este documento não é do termo.")
    return chave


def _versoes(termo: TermoAutorizacao, chave: str):
    from .models import EdicaoTermo
    return EdicaoTermo.objects.filter(termo=termo, chave=chave)


def _criar(termo: TermoAutorizacao, chave: str):
    from .models import EdicaoTermo
    return lambda **campos: EdicaoTermo.objects.create(termo=termo, chave=chave, **campos)


def edicao_vigente(termo: TermoAutorizacao, chave: str):
    from . import edicao_texto
    return edicao_texto.vigente(_versoes(termo, chave))


def regioes_vigentes(termo: TermoAutorizacao, chave: str, dados: dict | None = None
                     ) -> dict[str, str]:
    """O texto editado em vigor, já com os dados atuais. A edição foi feita sobre o modelo
    de então (`modelos` da versão); se os dados mudaram depois (outra viatura, outro
    período…), o que a pessoa mudou é levado para o modelo de agora por fusão a três — a
    edição fica, e os dados acompanham o cadastro. Versões antigas, sem `modelos`, valem
    como foram salvas."""
    from .documentos.regioes import mesclar_alteracao, normalizar
    edicao = edicao_vigente(termo, chave)
    if edicao is None or not edicao.regioes:
        return {}
    regioes = dict(edicao.regioes)
    if not edicao.modelos:
        return regioes
    agora = regioes_do_modelo(dados if dados is not None else _dados_do_modelo(termo, chave))
    for regiao, html in regioes.items():
        antes, novo = edicao.modelos.get(regiao), agora.get(regiao)
        if antes is None or novo is None or normalizar(antes) == normalizar(novo):
            continue
        regioes[regiao], _ = mesclar_alteracao(antes, html, novo)
    return regioes


def _herdar_texto_editado(termo: TermoAutorizacao, usuario, docs_antes: set[str]) -> None:
    """Os documentos que surgiram agora (um servidor a mais, a viatura) nascem com o texto
    já editado nos irmãos: as mudanças do documento editado mais recente (de servidor, para
    um servidor novo, quando há) vão para o modelo do novo por fusão a três — só o texto
    comum; os dados de cada um ficam os dele."""
    from . import edicao_texto
    from .documentos.regioes import mesclar_alteracao
    atuais = [d["chave"] for d in documentos_do_termo(termo)]
    novos = [c for c in atuais if c not in docs_antes]
    if not novos:
        return
    editados = []
    for chave in atuais:
        if chave in docs_antes:
            edicao = edicao_vigente(termo, chave)
            if edicao is not None and not edicao.do_modelo:
                editados.append((chave, edicao))
    if not editados:
        return
    for chave in novos:
        de_servidor = chave not in (GENERICO, VIATURA)
        mesmo_tipo = [par for par in editados if (par[0] not in (GENERICO, VIATURA)) == de_servidor]
        origem, _ = max(mesmo_tipo or editados, key=lambda par: par[1].criado_em)
        dados_origem = dados_do_documento(termo, origem)
        modelo_origem = regioes_do_modelo(dados_origem)
        modelo_novo = regioes_do_modelo(_dados_do_modelo(termo, chave))
        regioes = {r: mesclar_alteracao(modelo_origem[r], html, modelo_novo[r])[0]
                   for r, html in dados_origem["regioes_editadas"].items()
                   if r in modelo_origem and r in modelo_novo}
        try:
            edicao_texto.salvar(_versoes(termo, chave), _criar(termo, chave), usuario,
                                modelo_novo, regioes, versao_base=None, invalido=TermoInvalido,
                                conflito=ConflitoDeEdicao, guardar_modelos=True)
        except TermoInvalido:  # nada a levar (ficou igual ao modelo)
            continue


def regioes_do_modelo(dados: dict) -> dict[str, str]:
    from .documentos.regioes import extrair_regioes
    return extrair_regioes(html_do_modelo(dados))


def _travar(usuario, termo: TermoAutorizacao) -> TermoAutorizacao:
    atual = TermoAutorizacao.objects.select_for_update().get(pk=termo.pk)
    policies.exigir(policies.pode_editar_termo(usuario, atual),
                    "Você não pode alterar o texto deste termo.")
    return atual


@transaction.atomic
def salvar_texto(termo: TermoAutorizacao, usuario, chave: str, regioes: dict[str, str], *,
                 versao_base: int | None = None):
    from . import edicao_texto
    atual = _travar(usuario, termo)
    chave = _chave_valida(atual, chave)
    return edicao_texto.salvar(
        _versoes(atual, chave), _criar(atual, chave), usuario,
        regioes_do_modelo(_dados_do_modelo(atual, chave)), regioes,
        versao_base=versao_base, invalido=TermoInvalido, conflito=ConflitoDeEdicao,
        guardar_modelos=True)


@transaction.atomic
def restaurar_texto(termo: TermoAutorizacao, usuario, chave: str, numero: int):
    from . import edicao_texto
    atual = _travar(usuario, termo)
    chave = _chave_valida(atual, chave)
    return edicao_texto.restaurar(_versoes(atual, chave), _criar(atual, chave), usuario,
                                  numero, invalido=TermoInvalido)


@transaction.atomic
def voltar_texto_ao_modelo(termo: TermoAutorizacao, usuario, chave: str):
    from . import edicao_texto
    atual = _travar(usuario, termo)
    chave = _chave_valida(atual, chave)
    return edicao_texto.voltar_ao_modelo(_versoes(atual, chave), _criar(atual, chave), usuario)


@transaction.atomic
def aplicar_texto_em_todos(termo: TermoAutorizacao, usuario, chave_origem: str
                           ) -> tuple[int, list[str]]:
    """Leva para os outros documentos do termo as alterações feitas no texto de um.

    Cada bloco alterado na origem passa por uma fusão a três (regioes.mesclar_alteracao):
    o que mudou vai para o mesmo ponto de cada documento irmão, onde o texto em volta é o
    mesmo — inclusive no parágrafo do servidor (apagar ou reescrever o fim dele vale para
    todos) —, e só o que cai em dado de cada um (nome, CPF, lotação) fica de fora. Devolve
    quantos documentos mudaram e os blocos em que algo não pôde ir."""
    from . import edicao_texto
    from .documentos.regioes import bloco_original, mesclar_alteracao, trocar_bloco
    atual = _travar(usuario, termo)
    chave_origem = _chave_valida(atual, chave_origem)
    origem = edicao_vigente(atual, chave_origem)
    if origem is None or origem.do_modelo:
        raise TermoInvalido("O texto deste documento está como o modelo: não há o que levar.")
    dados_origem = dados_do_documento(atual, chave_origem)
    modelo_origem = regioes_do_modelo(dados_origem)
    texto_origem = dados_origem["regioes_editadas"]  # a edição, com os dados atuais
    blocos = [b for b in origem.blocos_alterados if b["chave"] not in ("texto", "quebras")]

    atualizados, ficaram = 0, set()
    for doc in documentos_do_termo(atual):
        chave = doc["chave"]
        if chave == chave_origem:
            continue
        dados_destino = dados_do_documento(atual, chave)
        modelo_destino = regioes_do_modelo(dados_destino)
        vigentes = dados_destino["regioes_editadas"]
        regioes = {r: vigentes.get(r, html) for r, html in modelo_destino.items()}
        mudou = False
        for bloco in blocos:
            for regiao, html_modelo in modelo_origem.items():
                antes = bloco_original(html_modelo, bloco["chave"])
                if antes is None or regiao not in regioes:
                    continue
                editado = bloco_original(texto_origem.get(regiao, ""), bloco["chave"])
                atual_destino = bloco_original(regioes[regiao], bloco["chave"])
                if editado is None or atual_destino is None:
                    ficaram.add(bloco["rotulo"])
                    continue
                fundido, fora = mesclar_alteracao(antes, editado, atual_destino)
                if fora:
                    ficaram.add(bloco["rotulo"])
                novo = trocar_bloco(regioes[regiao], bloco["chave"], fundido)
                if novo is not None and novo != regioes[regiao]:
                    regioes[regiao], mudou = novo, True
        if mudou:
            edicao_texto.salvar(_versoes(atual, chave), _criar(atual, chave), usuario,
                                modelo_destino, regioes, versao_base=None,
                                invalido=TermoInvalido, conflito=ConflitoDeEdicao,
                                guardar_modelos=True)
            atualizados += 1
    return atualizados, sorted(ficaram)
