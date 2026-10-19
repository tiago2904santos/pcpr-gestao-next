"""Termos de autorização: o que vale em cada termo (próprio ou herdado do ofício), a escrita
e os dados dos documentos.

Paridade com `viagens_termos` da referência:
- o termo pode estar ligado a um ofício e herda dele o que ficar em branco — destinos (os
  do roteiro do ofício), período (saída e chegada), servidores (a equipe) e viatura;
- pode juntar vários ofícios da mesma ação (mesma viagem ou mesmo roteiro — vinculos.py):
  herda a união deles (destinos de todos, da primeira saída à última chegada, a equipe
  toda e a viatura de cada um, com quem vai nela);
- pode ter mais de uma viatura (TermoViatura), cada uma com a sua equipe: o termo de cada
  servidor sai com a viatura em que ele vai, e cada viatura tem o seu "termo da viatura";
- o período é o **do evento**: vem do plano de trabalho, da OS ou da viagem dos ofícios
  (nessa ordem, só quando início e fim estão preenchidos); sem nenhum, o da viagem (da
  primeira saída à última chegada) — `periodo_do_evento`;
- sem ofício, destino e data são obrigatórios; a data final, vazia, repete a inicial;
- um documento por servidor (variante completa, com ou sem viatura), o **genérico** (só
  destino e período, para preencher à mão) e o **da viatura** (servidor em branco).

Toda gravação passa por aqui; a auditoria é do banco (trigger).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from django.db import transaction
from django.db.models import DateField, Min, OuterRef, Prefetch, Subquery, prefetch_related_objects
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from gestao.cadastros.models import ConfiguracaoInstitucional, Municipio, Servidor, Viatura

from . import policies
from .models import Oficio, TermoAutorizacao, TermoDestino, TermoViatura, Trecho, Viajante


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
    Prefetch("oficios", queryset=Oficio.objects.select_related(
        "sede", "viatura__combustivel", "viagem").order_by("ano", "numero")),
    "oficios__planos", "oficios__ordens", "oficio__planos", "oficio__ordens",
    Prefetch("oficios__trechos", queryset=Trecho.objects.select_related("destino")
             .order_by("ordem")),
    Prefetch("oficios__viajantes", queryset=Viajante.objects.select_related(
        "servidor__cargo", "servidor__unidade").order_by("ordem", "id")),
    Prefetch("viaturas", queryset=TermoViatura.objects.select_related(
        "viatura__combustivel", "viatura__unidade").prefetch_related(
        Prefetch("servidores", queryset=Servidor.objects.order_by("nome")))),
)


def com_dados(qs):
    return qs.select_related("oficio__sede", "oficio__viatura__combustivel",
                             "viatura__combustivel", "viatura__unidade",
                             "unidade").prefetch_related(*PREFETCH_TERMOS)


def com_inicio(qs):
    """Anota `inicio_efetivo`: a data do termo ou, herdando, a saída do ofício (a lista
    de termos e as Pendências ordenam e recortam por ela)."""
    saida = (Trecho.objects.filter(oficio=OuterRef("oficio_id")).order_by()
             .values("oficio").annotate(m=Min("saida_em")).values("m"))
    return qs.annotate(inicio_efetivo=Coalesce(
        "data_inicio", TruncDate(Subquery(saida)), output_field=DateField()))


# ---------------------------------------------------------------- valores efetivos
@dataclass
class ViaturaDoTermo:
    """Uma viatura e quem vai nela (vazio: ninguém marcado — com uma viatura só, todos)."""
    viatura: Viatura
    servidores: list[Servidor] = field(default_factory=list)


@dataclass
class Efetivo:
    destinos: list[Municipio] = field(default_factory=list)
    inicio: date | None = None
    fim: date | None = None
    servidores: list[Servidor] = field(default_factory=list)
    viaturas: list[ViaturaDoTermo] = field(default_factory=list)
    herdados: list[str] = field(default_factory=list)
    # De onde vem o período ("Período do evento no Plano de Trabalho 05/2026", "Período da
    # viagem (ofícios)", "Informado no termo") — a tela mostra junto da data.
    fonte_periodo: str = ""
    # A ida e a volta dos ofícios (mesmo quando a data do evento é outra): a tela desenha o
    # evento dentro da viagem.
    viagem_inicio: date | None = None
    viagem_fim: date | None = None

    @property
    def viatura(self) -> Viatura | None:
        """A principal (a primeira): o que o resto do sistema entende por "a viatura"."""
        return self.viaturas[0].viatura if self.viaturas else None

    def viatura_de(self, servidor: Servidor) -> Viatura | None:
        """Em que viatura o servidor vai: a do grupo dele; com uma viatura só, todos nela."""
        for grupo in self.viaturas:
            if any(s.pk == servidor.pk for s in grupo.servidores):
                return grupo.viatura
        return self.viaturas[0].viatura if len(self.viaturas) == 1 else None

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
        "viatura": ", ".join(str(g.viatura) for g in ef.viaturas),
    }.items() if v}


def oficios_do_termo(termo: TermoAutorizacao) -> list[Oficio]:
    """Os ofícios que o termo junta (o vínculo antigo, de um só, vale como lista de um)."""
    oficios = list(termo.oficios.all()) if termo.pk else []
    if not oficios and termo.oficio is not None:
        oficios = [termo.oficio]
    return oficios


def viaturas_dos_oficios(oficios: list[Oficio]) -> list[ViaturaDoTermo]:
    """A viatura de cada ofício (os que vão de viatura), com a equipe dele; a mesma viatura
    em dois ofícios junta as equipes. Cada servidor fica na primeira em que aparece."""
    grupos: list[ViaturaDoTermo] = []
    alocados: set[int] = set()
    for oficio in oficios:
        if not (oficio.viatura_id and oficio.tipo_transporte == Oficio.TipoTransporte.VIATURA):
            continue
        viatura = oficio.viatura
        if viatura is None:
            continue
        grupo = next((g for g in grupos if g.viatura.pk == oficio.viatura_id), None)
        if grupo is None:
            grupo = ViaturaDoTermo(viatura)
            grupos.append(grupo)
        for v in oficio.viajantes.all():
            if v.servidor_id not in alocados:
                grupo.servidores.append(v.servidor)
                alocados.add(v.servidor_id)
    return grupos


def periodo_do_evento(oficios: list[Oficio]) -> tuple[date | None, date | None, str]:
    """A data do evento dos ofícios: a do plano de trabalho, senão a da OS, senão a da
    viagem (Viagem/Evento) — só o que tem início e fim (preenchido pela metade não conta).
    Mais de um da mesma fonte: do primeiro início ao último fim. Nada: (None, None, "")."""
    fontes = (
        ("Plano de Trabalho", lambda o: [p for p in o.planos.all() if not p.cancelado]),
        ("OS", lambda o: [x for x in o.ordens.all() if not x.cancelada]),
        ("Viagem", lambda o: [o.viagem] if o.viagem_id and not o.viagem.cancelada else []),
    )
    for nome, de in fontes:
        achados = {r.pk: r for o in oficios for r in de(o) if r.data_inicio and r.data_fim}
        if achados:
            registros = list(achados.values())
            inicio = min(r.data_inicio for r in registros)
            fim = max(r.data_fim for r in registros)
            quem = (f"{nome} {registros[0]}".replace(f"{nome} {nome}", nome)
                    if len(registros) == 1 else f"{len(registros)} registros de {nome}")
            return inicio, fim, f"Período do evento — {quem}"
    return None, None, ""


def uniao_dos_oficios(oficios: list[Oficio]) -> dict:
    """O que os ofícios dão juntos: destinos de todos (na ordem, sem repetir), da primeira
    saída à última chegada, a equipe toda (sem repetir) e a viatura de cada um."""
    destinos: list[Municipio] = []
    servidores: list[Servidor] = []
    inicio: date | None = None
    fim: date | None = None
    for oficio in oficios:
        seus, saida, chegada = _do_oficio(oficio)
        destinos += [m for m in seus if m not in destinos]
        if saida:
            inicio = min(inicio, saida) if inicio else saida
        if chegada:
            fim = max(fim, chegada) if fim else chegada
        servidores += [v.servidor for v in oficio.viajantes.all()
                       if v.servidor not in servidores]
    viaturas = viaturas_dos_oficios(oficios)
    # O termo fala do evento: a data dele vence a ida e a volta (que fica de reserva).
    evento_inicio, evento_fim, fonte = periodo_do_evento(oficios)
    viagem_inicio, viagem_fim = inicio, fim
    if evento_inicio:
        inicio, fim = evento_inicio, evento_fim
    elif inicio:
        fonte = "Período da viagem — " + (f"Ofício {oficios[0].numero_formatado}"
                                          if len(oficios) == 1 else f"{len(oficios)} ofícios")
    return {"destinos": destinos, "inicio": inicio, "fim": fim, "servidores": servidores,
            "viaturas": viaturas, "viatura": viaturas[0].viatura if viaturas else None,
            "fonte_periodo": fonte, "viagem_inicio": viagem_inicio, "viagem_fim": viagem_fim}


def efetivo(termo: TermoAutorizacao) -> Efetivo:
    """O que vale no termo: o próprio, ou o dos ofícios (unidos) quando em branco."""
    if termo.pk and not hasattr(termo, "_prefetched_objects_cache"):
        prefetch_related_objects([termo], *PREFETCH_TERMOS)
    ef = Efetivo()
    ef.destinos = [d.municipio for d in termo.destinos.all()] if termo.pk else []
    ef.inicio, ef.fim = termo.data_inicio, termo.data_fim or termo.data_inicio
    ef.servidores = list(termo.servidores.all()) if termo.pk else []
    ef.viaturas = [ViaturaDoTermo(tv.viatura, list(tv.servidores.all()))
                   for tv in termo.viaturas.all()] if termo.pk else []
    if ef.inicio:
        ef.fonte_periodo = "Informado no termo"
    oficios = oficios_do_termo(termo)
    if not oficios:
        return ef
    base = uniao_dos_oficios(oficios)
    ef.viagem_inicio, ef.viagem_fim = base["viagem_inicio"], base["viagem_fim"]
    if ef.inicio and (ef.inicio, ef.fim) == (base["inicio"], base["fim"] or base["inicio"]):
        ef.fonte_periodo = base["fonte_periodo"]  # o termo guardou o que veio dos ofícios
    if not ef.destinos and base["destinos"]:
        ef.destinos = base["destinos"]
        ef.herdados.append("destinos")
    if not ef.inicio and base["inicio"]:
        ef.inicio, ef.fim = base["inicio"], base["fim"]
        ef.fonte_periodo = base["fonte_periodo"]
        ef.herdados.append("período")
    if not ef.servidores and base["servidores"]:
        ef.servidores = base["servidores"]
        ef.herdados.append("servidores")
    if not ef.viaturas and base["viaturas"]:
        ef.viaturas = base["viaturas"]
        ef.herdados.append("viatura")
    return ef


# ---------------------------------------------------------------- escrita
@transaction.atomic
def salvar(usuario, *, pk: int | None = None, oficio: Oficio | None = None,
           oficios=None, evento: str | None = None, data_inicio: date | None = None,
           data_fim: date | None = None, destinos: list[Municipio] | None = None,
           servidores=(), viatura: Viatura | None = None,
           viaturas: list[tuple[Viatura, list[Servidor]]] | None = None,
           versao: str = "") -> TermoAutorizacao:
    """Cria ou altera. `versao` (o `atualizado_em` que a tela abriu) recusa gravar por cima
    de quem salvou depois (a tela grava sozinha a cada pausa).

    `oficios`: os ofícios que o termo junta (`oficio`, um só, vale como lista de um). Juntar
    mais de um exige que sejam da mesma ação (vinculos.incompatibilidade).

    `viaturas`: [(viatura, quem vai nela)], na ordem; `viatura` (uma só, sem equipe marcada)
    vale como lista de uma. Um ofício que entra agora traz a viatura dele (com a equipe dele)
    se ela ainda não está no termo — é o que "puxar dos ofícios" faz sozinho."""
    from .vinculos import incompatibilidade
    destinos = list(dict.fromkeys(destinos or []))  # sem repetir, na ordem informada
    oficios = list(dict.fromkeys(oficios if oficios is not None else ([oficio] if oficio else [])))
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
    ja_ligados = {o.pk for o in oficios_do_termo(termo)} if termo.pk else set()
    for i, o in enumerate(oficios):
        policies.exigir(policies.pode_ver(usuario, o), "Ofício não encontrado.")
        if o.situacao == Oficio.Situacao.CANCELADO and o.pk not in ja_ligados:
            raise TermoInvalido(f"O Ofício {o.numero_formatado} está cancelado.")
        if termo.pk is None and i == 0:
            # O termo é da unidade do ofício (senão a equipe e os dados de um ofício de
            # outra unidade ficariam à vista de quem não os vê).
            termo.unidade = o.unidade
        elif o.unidade_id != termo.unidade_id:
            raise TermoInvalido(f"O Ofício {o.numero_formatado} é de outra unidade.")
    if {o.pk for o in oficios} != ja_ligados and (erro := incompatibilidade(oficios)):
        raise TermoInvalido(erro)
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
    termo.oficio = oficios[0] if oficios else None
    if evento is not None or not termo.evento:  # sem o campo na tela, fica o que estava
        termo.evento = " ".join((evento or "").split()) or TermoAutorizacao._meta.get_field(
            "evento").default
    termo.data_inicio, termo.data_fim = data_inicio, (data_fim or data_inicio)
    if viaturas is None:
        viaturas = [(viatura, [])] if viatura is not None else []
    viaturas = _com_viaturas_dos_novos(viaturas, [o for o in oficios if o.pk not in ja_ligados])
    termo.viatura = viaturas[0][0] if viaturas else None
    termo.save()
    termo.oficios.set(oficios)
    termo.servidores.set(servidores)
    _gravar_viaturas(termo, viaturas)
    atuais = [d.municipio_id for d in termo.destinos.order_by("ordem", "id")]
    if atuais != [m.pk for m in destinos]:  # só regrava se mudou (trilha de auditoria limpa)
        termo.destinos.all().delete()
        TermoDestino.objects.bulk_create(
            [TermoDestino(termo=termo, municipio=m, ordem=i) for i, m in enumerate(destinos)])
    if docs_antes:
        # O que foi carregado antes de gravar (destinos, servidores) não vale mais.
        termo.__dict__.pop("_prefetched_objects_cache", None)
        _herdar_texto_editado(termo, usuario, docs_antes)
    return termo


def _com_viaturas_dos_novos(viaturas: list, novos: list[Oficio]) -> list:
    """A lista informada mais a viatura de cada ofício que entrou agora (se ainda não está),
    com a equipe dele que não esteja em outra viatura."""
    viaturas = [(v, list(equipe)) for v, equipe in viaturas]
    if not novos:
        return viaturas
    presentes = {v.pk for v, _ in viaturas}
    alocados = {s.pk for _, equipe in viaturas for s in equipe}
    for grupo in viaturas_dos_oficios(novos):
        equipe = [s for s in grupo.servidores if s.pk not in alocados]
        if grupo.viatura.pk in presentes:
            for v, atual in viaturas:
                if v.pk == grupo.viatura.pk:
                    atual.extend(equipe)
        else:
            viaturas.append((grupo.viatura, equipe))
            presentes.add(grupo.viatura.pk)
        alocados.update(s.pk for s in equipe)
    return viaturas


def _gravar_viaturas(termo: TermoAutorizacao, viaturas: list) -> None:
    """Regrava as viaturas só se mudaram (a trilha de auditoria fica limpa). Cada servidor
    vai numa só: aparecendo em duas, vale a primeira."""
    alocados: set[int] = set()
    desejado: list[tuple[Viatura, list[int], int]] = []
    for i, (viatura, equipe) in enumerate(viaturas):
        if any(v.pk == viatura.pk for v, _, _ in desejado):
            continue
        ids = [s.pk for s in equipe if s.pk not in alocados]
        alocados.update(ids)
        desejado.append((viatura, ids, i))
    atual = [(tv.viatura_id, sorted(tv.servidores.values_list("pk", flat=True)))
             for tv in termo.viaturas.order_by("ordem", "id")]
    if atual == [(v.pk, sorted(ids)) for v, ids, _ in desejado]:
        return
    termo.viaturas.all().delete()
    for viatura, ids, ordem in desejado:
        tv = TermoViatura.objects.create(termo=termo, viatura=viatura, ordem=ordem)
        if ids:
            tv.servidores.set(ids)


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


def chave_da_viatura(indice: int, viatura: Viatura) -> str:
    """A primeira viatura guarda a chave de sempre ("viatura" — o texto editado de antes
    continua valendo); as demais, "viatura-<id>"."""
    return VIATURA if indice == 0 else f"{VIATURA}-{viatura.pk}"


def viatura_da_chave(ef: Efetivo, chave: str) -> Viatura | None:
    for i, grupo in enumerate(ef.viaturas):
        if chave_da_viatura(i, grupo.viatura) == chave:
            return grupo.viatura
    return None


def documentos_do_termo(termo: TermoAutorizacao, ef: Efetivo | None = None) -> list[dict]:
    """Os documentos que o termo emite: um por servidor (com a viatura em que ele vai), o
    genérico e um por viatura. `chave` é o que a rota de geração recebe."""
    ef = ef or efetivo(termo)
    docs = [{"chave": str(s.pk), "titulo": s.nome, "descricao": "Termo do servidor"}
            for s in ef.servidores]
    docs.append({"chave": GENERICO, "titulo": "Termo genérico",
                 "descricao": "Só destino e período, para preencher à mão"})
    for i, grupo in enumerate(ef.viaturas):
        docs.append({"chave": chave_da_viatura(i, grupo.viatura),
                     "titulo": f"Termo da viatura {grupo.viatura}",
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
    if chave == GENERICO:
        viatura = None
    elif chave == VIATURA or chave.startswith(f"{VIATURA}-"):
        viatura = viatura_da_chave(ef, chave)
        if viatura is None:
            raise TermoInvalido("Esta viatura não está no termo.")
    else:
        participante = next((s for s in ef.servidores if str(s.pk) == chave), None)
        if participante is None:
            raise TermoInvalido("Este servidor não está no termo.")
        viatura = ef.viatura_de(participante)
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
    sufixo = (chave if chave == GENERICO or chave.startswith(VIATURA)
              else f"servidor-{chave}")
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


def _de_servidor(chave: str) -> bool:
    return chave != GENERICO and not chave.startswith(VIATURA)


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
        de_servidor = _de_servidor(chave)
        mesmo_tipo = [par for par in editados if _de_servidor(par[0]) == de_servidor]
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


# ---------------------------------------------------------------- duplicar e finalizar
@transaction.atomic
def duplicar(usuario, pk: int) -> TermoAutorizacao:
    """Um termo novo com os mesmos dados (ofícios, evento, período, destinos, servidores,
    viatura) e o mesmo texto editado de cada documento — fora a viagem, as vias assinadas e
    o histórico, que são de cada termo."""
    from .models import EdicaoDocumento, EdicaoTermo
    origem = TermoAutorizacao.objects.get(pk=pk)
    policies.exigir(policies.pode_ver_termo(usuario, origem)
                    and policies.pode_criar_termo(usuario), "Você não pode duplicar este termo.")
    novo = salvar(
        usuario, oficios=[o for o in oficios_do_termo(origem)
                          if o.situacao != Oficio.Situacao.CANCELADO],
        evento=origem.evento, data_inicio=origem.data_inicio, data_fim=origem.data_fim,
        destinos=[d.municipio for d in origem.destinos.order_by("ordem", "id")],
        servidores=list(origem.servidores.all()),
        viaturas=[(tv.viatura, list(tv.servidores.all())) for tv in origem.viaturas.all()])
    for doc in documentos_do_termo(novo):
        edicao = edicao_vigente(origem, doc["chave"])
        if edicao is not None and edicao.regioes:
            EdicaoTermo.objects.create(
                termo=novo, chave=doc["chave"], numero=1, acao=EdicaoDocumento.Acao.EDITADO,
                regioes=dict(edicao.regioes), blocos_alterados=list(edicao.blocos_alterados),
                impressoes=dict(edicao.impressoes), modelos=dict(edicao.modelos),
                criado_por=usuario)
    return novo
