"""A prestação de uma equipe numa folha só, organizada como a viagem: as etapas no topo (como
a solicitação de evento), os servidores, as folhas da equipe (diário, relatório e documentos)
numa trilha e a conferência do que falta, servidor a servidor. Só leitura: os dados vêm
prontos de `prestacao`, `anexos` e do ofício; nada é criado ao abrir (GET).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.urls import reverse

from . import carimbo, diario, relatorio
from .anexos import Situacao
from .models import PrestacaoContas, PrestacaoServidor


@dataclass(frozen=True)
class Etapa:
    titulo: str
    estado: str  # concluido | atual | pendente (as classes de .etapas-progresso)


@dataclass(frozen=True)
class Chip:
    texto: str
    tom: str = "neutro"  # sucesso | aviso | perigo | neutro (as classes de .selo)


@dataclass(frozen=True)
class Folha:
    chave: str
    titulo: str
    icone: str
    descricao: str
    url: str
    chip: Chip
    subtexto: str
    feito: bool


@dataclass(frozen=True)
class Pendencia:
    mensagem: str
    url: str


@dataclass
class Conferencia:
    abertas: list[tuple[PrestacaoServidor, list[Pendencia]]] = field(default_factory=list)
    prontas: list[tuple[PrestacaoServidor, str]] = field(default_factory=list)
    total: int = 0

    @property
    def concluidas(self) -> int:
        return len(self.prontas)

    @property
    def pronta(self) -> bool:
        return not self.abertas


def destino(p: PrestacaoContas, ps: PrestacaoServidor, texto: str) -> str:
    """Onde se resolve cada pendência (os textos são os de `prestacao.pendencias`)."""
    documentos = reverse("viagens:documentos_prestacao", args=[p.pk])
    if texto == diario.PENDENCIA:
        return reverse("viagens:diario", args=[p.pk])
    if texto == relatorio.PENDENCIA:
        return reverse("viagens:relatorio", args=[p.pk])
    if texto == carimbo.PENDENCIA:
        return f"{documentos}#oficio_assinado"
    if "despacho" in texto:
        return f"{documentos}#despacho"
    if "comprovante" in texto:
        return f"{documentos}#ps-{ps.pk}"
    return f"{reverse('viagens:prestacao_equipe', args=[p.pk])}#ps-{ps.pk}"


def etapas(membros: list[PrestacaoServidor], folhas: list[Folha]) -> list[Etapa]:
    """Solicitações → Diário → Relatório → Documentos → Finalização → Envio: a primeira que
    falta é a atual (como a solicitação de evento)."""
    feitas = [
        ("Solicitações", bool(membros) and all(
            ps.finalizada or ps.numero_solicitacao.strip() for ps in membros)),
        *[(f.titulo, f.feito) for f in folhas],
        ("Finalização", bool(membros) and all(ps.finalizada for ps in membros)),
        ("Envio", bool(membros) and all(ps.situacao in ("enviada", "aprovada")
                                         for ps in membros)),
    ]
    atual = next((i for i, (_, feito) in enumerate(feitas) if not feito), len(feitas))
    return [Etapa(t, "concluido" if feito else ("atual" if i == atual else "pendente"))
            for i, (t, feito) in enumerate(feitas)]


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def folhas(p: PrestacaoContas, membros: list[PrestacaoServidor], s: Situacao,
           trechos: int) -> list[Folha]:
    """As três folhas da equipe, com a situação de cada uma numa linha."""
    total = len(membros)
    if p.pk in s.diarios:
        chip_diario = Chip("Preenchido", "sucesso")
    elif p.pk in s.db_assinados:
        chip_diario = Chip("Assinado anexado", "sucesso")
    else:
        chip_diario = Chip("A preencher", "aviso")
    rts = sum(1 for ps in membros if ps.pk in s.rt_assinados)
    if p.pk in s.relatorios:
        chip_rt = Chip("Preenchido", "sucesso")
    elif total and rts == total:
        chip_rt = Chip("Assinados anexados", "sucesso")
    else:
        chip_rt = Chip("A preencher", "aviso")
    comprovantes = sum(1 for ps in membros if s.comprovantes.get(ps.pk))
    despacho = p.pk in s.despachos
    falta_docs = (not despacho) + (comprovantes < total)
    if not falta_docs:
        chip_docs = Chip("Completos", "sucesso")
    elif not despacho:
        chip_docs = Chip("Falta o despacho", "aviso")
    else:
        chip_docs = Chip(f"Faltam {total - comprovantes} comprovante"
                         f"{'' if total - comprovantes == 1 else 's'}", "aviso")
    comprovantes_lidos = comprovantes  # a leitura vale quando há o que ler
    return [
        Folha("diario", "Diário de bordo", "gauge",
              "Km e abastecimento de cada trecho, motorista e horários realizados.",
              reverse("viagens:diario", args=[p.pk]), chip_diario,
              f"{_plural(trechos, 'trecho', 'trechos')} do ofício · PDF e planilha",
              chip_diario.tom == "sucesso"),
        Folha("relatorio", "Relatório técnico", "file-pen-line",
              "Um texto da equipe e um documento por servidor.",
              reverse("viagens:relatorio", args=[p.pk]), chip_rt,
              f"RT assinado de {rts} de {_plural(total, 'servidor', 'servidores')}",
              chip_rt.tom == "sucesso"),
        Folha("documentos", "Documentos", "files",
              "Despacho, comprovantes, vias assinadas e o pacote final.",
              reverse("viagens:documentos_prestacao", args=[p.pk]), chip_docs,
              f"Despacho {'anexado' if despacho else 'pendente'} · comprovantes de "
              f"{comprovantes} de {_plural(total, 'servidor', 'servidores')}"
              f"{' · ofício assinado' if p.pk in s.vias else ''}",
              not falta_docs),
        Folha("leitura", "Leitura dos anexos", "scan-text",
              "O que está escrito nos comprovantes, no RT e no diário assinados, para copiar e conferir.",
              reverse("viagens:leitura_prestacao", args=[p.pk]),
              Chip("Com o que ler", "neutro") if comprovantes_lidos or rts or p.pk in s.db_assinados
              else Chip("Nada anexado ainda", "neutro"),
              f"{_plural(comprovantes_lidos, 'comprovante', 'comprovantes')} · "
              f"{_plural(rts, 'RT assinado', 'RTs assinados')}",
              bool(total) and comprovantes >= total and rts >= total),
    ]


def conferencia(p: PrestacaoContas, linhas: list[dict]) -> Conferencia:
    """Quem ainda tem pendência (com o caminho de cada uma) e quem está pronto."""
    c = Conferencia(total=len(linhas))
    for linha in linhas:
        ps = linha["ps"]
        if ps.finalizada:
            c.prontas.append((ps, "Finalizada"))
        elif linha["pendencias"]:
            c.abertas.append((ps, [Pendencia(t, destino(p, ps, t))
                                   for t in linha["pendencias"]]))
        else:
            c.prontas.append((ps, "Pronta para finalizar"))
    return c


@dataclass(frozen=True)
class EtapaFolha:
    numero: int
    chave: str
    titulo: str
    url: str
    estado: str  # concluido | atual | pendente
    rotulo: str  # Concluída · Em edição · A seguir
    atual: bool


def etapas_folha(folhas: list[Folha], bloco: dict, atual: str) -> list[EtapaFolha]:
    """A barra das folhas: 1 Diário → 2 Relatório → 3 Documentos → 4 Leitura e conferência.
    Concluída vem da completude (nunca só por abrir a página); a atual é a folha aberta."""
    feitas = {f.chave: f.feito for f in folhas}
    urls = {f.chave: f.url for f in folhas}
    passos = [("diario", "Diário de bordo"), ("relatorio", "Relatório técnico"),
              ("documentos", "Documentos"), ("leitura", "Leitura e conferência")]
    saida = []
    for i, (chave, titulo) in enumerate(passos, 1):
        feita = feitas.get(chave, bloco.get("todas_finalizadas", False))
        estado = "atual" if chave == atual else "concluido" if feita else "pendente"
        saida.append(EtapaFolha(i, chave, titulo, urls[chave], estado,
                                "Em edição" if chave == atual else "Concluída" if feita
                                else "A seguir", chave == atual))
    return saida
