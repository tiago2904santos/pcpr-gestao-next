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
    destinos_oficio, inicio_oficio, _ = _do_oficio(oficio) if oficio else ([], None, None)
    if not destinos and not destinos_oficio:
        raise TermoInvalido("Informe o destino ou escolha um ofício com roteiro.")
    if not data_inicio and not inicio_oficio:
        raise TermoInvalido("Informe a data ou escolha um ofício com período.")
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
    """Dados de um documento do termo (`chave`: id do servidor, "generico" ou "viatura")."""
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


def nome_do_arquivo(termo: TermoAutorizacao, chave: str, extensao: str) -> str:
    sufixo = {GENERICO: "generico", VIATURA: "viatura"}.get(chave, f"servidor-{chave}")
    return f"termo-{termo.pk}-{sufixo}.{extensao}"


def html_do_documento(dados: dict, *, folha: bool = False, nonce: str = "") -> str:
    """HTML do documento; `folha=True` é a versão de tela (dentro do visualizador)."""
    from django.template.loader import render_to_string

    from .documentos.pdf import _recursos
    return render_to_string("viagens/documentos/termo.html",
                            {"d": dados, "folha": folha, "nonce": nonce, **_recursos(folha)})


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
