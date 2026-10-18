"""Proposta consolidada (AUT-14; fluxo 11-3 §4–§5.4): escolher a viagem, informar quem vai e
conferir numa tela só o roteiro, o ofício, as diárias, os termos, a OS, o plano, os conflitos
de agenda e o que falta — antes de gravar qualquer coisa.

Duas funções, uma regra só:

- `montar` é **leitura pura**: não grava, não reserva número, não toca a outbox. Usa as
  mesmas peças que a criação usa (`viagem_lote.validar`, `services.calcular_informados`
  sobre `services.trechos_informados_do_roteiro`, `plataforma.conflitos`), então o que a
  prévia mostra é o que o lote grava.
- `aplicar` trava a viagem, **remonta** a proposta com as mesmas entradas e só segue se a
  assinatura for a mesma da prévia que a pessoa conferiu (equipe, viatura, roteiro, viagem,
  documentos existentes e conflitos). Mudou algo → recusa e pede nova prévia. Criar passa pelo
  serviço existente (`viagem_lote.gerar`), na mesma transação.

Numeração: a prévia não reserva número. O ofício, a OS e o plano recebem o número oficial
quando o rascunho é criado (regra atual de `services.criar_rascunho`, `ordens.salvar` e
`planos.salvar` — o número é obrigatório nesses modelos). Por isso o número só existe
depois de "Criar rascunhos", nunca na prévia; termos, roteiro e a própria viagem não têm
número.

Quem vai é SEMPRE informado por uma pessoa: esta função não sugere equipe, motorista nem
viatura. A ferramenta tipada `viagens.proposta_previa` (risco leitura) só monta a prévia com
os ids que recebeu; criar os rascunhos não existe como ferramenta.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from gestao.cadastros.models import ConfiguracaoInstitucional, Municipio, Servidor, Viatura
from gestao.plataforma import conflitos as agenda_conflitos

from . import policies
from .dominio import diarias as dominio_diarias
from .dominio.prazos import avaliar_prazo
from .models import Viagem

ROTULO_DIARIAS = "Estimativa para conferência — o valor oficial sai no documento."
NUMERO_NA_CRIACAO = "nº atribuído ao criar o rascunho"
MAX_SERVIDORES = 40


class ForaDoEscopo(Exception):
    """A viagem não existe ou não é visível para quem pede (a tela responde 404)."""


class PropostaDesatualizada(Exception):
    """Algo mudou entre a prévia e o "Criar rascunhos": nada foi gravado."""


class PropostaBloqueada(Exception):
    """A prévia tem pendência que impede criar (nada foi gravado)."""

    def __init__(self, mensagens: list[str]):
        super().__init__(" ".join(mensagens))
        self.mensagens = mensagens


# ---------------------------------------------------------------- entrada
@dataclass(frozen=True)
class Entrada:
    """O que a pessoa informou. A ordem dos servidores é a do ofício."""

    viagem: int
    servidores: tuple[int, ...]
    motorista: int | None = None
    viatura: int | None = None
    termos: bool = True
    ordem: bool = True
    plano: bool = True

    @classmethod
    def de(cls, viagem, servidores, motorista=None, viatura=None, *, termos=True, ordem=True,
           plano=True) -> Entrada:
        ids = tuple(dict.fromkeys(int(getattr(s, "pk", s)) for s in servidores or ()))
        return cls(viagem=int(getattr(viagem, "pk", viagem)), servidores=ids,
                   motorista=int(getattr(motorista, "pk", motorista)) if motorista else None,
                   viatura=int(getattr(viatura, "pk", viatura)) if viatura else None,
                   termos=bool(termos), ordem=bool(ordem), plano=bool(plano))


# ---------------------------------------------------------------- saída
@dataclass(frozen=True)
class Pessoa:
    id: int
    nome: str
    unidade: str
    de_fora: bool          # de outra unidade que não a emissora: ganha termo de autorização
    motorista: bool
    falta_no_cadastro: str = ""


@dataclass(frozen=True)
class Diarias:
    rotulo: str
    servidores: int
    total: str = ""
    por_servidor: str = ""
    resumo: str = ""
    tipo_destino: str = ""
    erro: str = ""


@dataclass(frozen=True)
class DocumentoPrevisto:
    tipo: str              # roteiro | oficio | termo | ordem | plano
    titulo: str
    detalhe: str
    cria: bool             # False: já existe e não muda


@dataclass(frozen=True)
class Item:
    secao: str
    mensagem: str


@dataclass
class Proposta:
    entrada: Entrada
    viagem_id: int
    titulo: str
    periodo: str
    unidade: str
    destinos: list[str]
    solicitacoes: list[int]
    roteiro: dict | None
    equipe: list[Pessoa]
    viatura: str
    documentos: list[DocumentoPrevisto]
    diarias: Diarias | None
    conflitos: list[str]
    bloqueios: list[Item]
    avisos: list[Item]
    depois: list[Item]
    versao_viagem: str
    calculada_em: datetime = field(default_factory=timezone.now)
    assinatura: str = ""

    @property
    def pode_criar(self) -> bool:
        return not self.bloqueios

    def dados(self) -> dict:
        """Tudo o que a pessoa vê (sem o horário do cálculo): é o que a assinatura cobre."""
        d = asdict(self)
        d.pop("calculada_em")
        d.pop("assinatura")
        d["entrada"] = asdict(self.entrada)
        return d

    def como_dict(self) -> dict:
        """Para a ferramenta tipada e para quem precisar de JSON."""
        return {**self.dados(), "calculada_em": self.calculada_em.isoformat(),
                "assinatura": self.assinatura, "pode_criar": self.pode_criar,
                "aviso": "Prévia: nada foi gravado e nenhum número foi reservado."}


def assinar(dados: dict) -> str:
    bruto = json.dumps(dados, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(bruto.encode()).hexdigest()


# ---------------------------------------------------------------- autorização
def viagem_no_escopo(usuario, viagem_id: int) -> Viagem:
    """A viagem, se quem pede a vê (senão `ForaDoEscopo`: a tela responde 404)."""
    viagem = (policies.viagens_visiveis(usuario).select_related("unidade")
              .filter(pk=viagem_id).first())
    if viagem is None:
        raise ForaDoEscopo("Viagem não encontrada.")
    return viagem


def pode_propor(usuario, viagem: Viagem | None = None) -> bool:
    """Montar e aplicar: quem altera a viagem e cria ofícios (as policies do contexto)."""
    if not policies.pode_criar(usuario):
        return False
    return viagem is None or policies.pode_editar_viagem(usuario, viagem)


def viagens_para_propor(usuario):
    """As viagens que aceitam proposta: visíveis e não canceladas, as mais próximas primeiro."""
    return (policies.viagens_visiveis(usuario).exclude(situacao=Viagem.Situacao.CANCELADA)
            .select_related("unidade").order_by("-data_inicio", "-pk"))


# ---------------------------------------------------------------- montar (só leitura)
def _diarias(trechos, sede, servidores: int) -> Diarias:
    from . import services

    if not trechos:
        return Diarias(ROTULO_DIARIAS, servidores,
                       erro="Sem roteiro: o ofício sai sem trechos e sem diárias.")
    try:
        calculo = services.calcular_informados(trechos, sede, servidores=max(servidores, 1))
    except (dominio_diarias.RoteiroIncalculavel, dominio_diarias.SemTabelaDeDiarias) as exc:
        return Diarias(ROTULO_DIARIAS, servidores, erro=str(exc))
    total = calculo.total if servidores else Decimal("0.00")
    return Diarias(ROTULO_DIARIAS, servidores, total=str(total),
                   por_servidor=str(calculo.por_servidor), resumo=calculo.resumo,
                   tipo_destino=calculo.tipo_destino)


def _periodo_dos_trechos(trechos):
    if trechos:
        return trechos[0].saida_em, trechos[-1].chegada_em
    return None, None


def montar(usuario, entrada: Entrada) -> Proposta:
    """A prévia consolidada. Não grava nada e não reserva número (ver o docstring do módulo).
    `ForaDoEscopo` se a viagem não é visível; `PermissionDenied` sem permissão de propor."""
    from . import services, viagem_lote
    from .viagem import documentos, periodo_curto

    viagem = viagem_no_escopo(usuario, entrada.viagem)
    policies.exigir(pode_propor(usuario, viagem),
                    "Você não pode preparar documentos para esta viagem (ela está cancelada "
                    "ou seu perfil não cria ofícios).")
    unidade = policies.unidade_do_usuario(usuario)
    bloqueios: list[Item] = []
    avisos: list[Item] = []
    depois: list[Item] = []

    # Quem vai: só os ids informados, na ordem informada. Inativo ou inexistente bloqueia.
    if len(entrada.servidores) > MAX_SERVIDORES:
        bloqueios.append(Item("equipe", f"No máximo {MAX_SERVIDORES} servidores por ofício."))
    ids = list(entrada.servidores[:MAX_SERVIDORES])
    if entrada.motorista and entrada.motorista not in ids:
        ids.append(entrada.motorista)  # o motorista de fora da equipe entra nela (lote)
    por_id = Servidor.objects.select_related("unidade", "cargo").in_bulk(ids)
    servidores: list[Servidor] = []
    for sid in ids:
        s = por_id.get(sid)
        if s is None or not s.ativo:
            bloqueios.append(Item("equipe", f"O servidor #{sid} não existe ou está inativo "
                                            "no cadastro."))
        else:
            servidores.append(s)
    motorista = por_id.get(entrada.motorista) if entrada.motorista else None
    viatura = (Viatura.objects.select_related("unidade").filter(pk=entrada.viatura, ativo=True)
               .first() if entrada.viatura else None)
    if entrada.viatura and viatura is None:
        bloqueios.append(Item("transporte", "A viatura escolhida não existe ou está inativa."))
    if not servidores and not bloqueios:
        bloqueios.append(Item("equipe", "Informe quem vai: ao menos um servidor."))

    # As mesmas validações do lote (servidor já em ofício desta viagem etc.).
    if servidores:
        equipe_lote = viagem_lote.Equipe(servidores=list(servidores), motorista=motorista,
                                         viatura=viatura)
        for erro in viagem_lote.validar(viagem, [equipe_lote]):
            bloqueios.append(Item("equipe", erro))

    configuracao = None
    if unidade is not None:
        try:
            configuracao = unidade.configuracao
        except ConfiguracaoInstitucional.DoesNotExist:
            bloqueios.append(Item("unidade", f"A unidade {unidade} ainda não tem configuração "
                                             "institucional: peça ao administrador."))

    # Documentos que já existem e o roteiro de referência (o mesmo critério do lote).
    docs = documentos(viagem)
    roteiro = next((r for r in reversed(docs.roteiros) if r.editavel), None)
    trechos = services.trechos_informados_do_roteiro(roteiro) if roteiro is not None else []
    sede = roteiro.sede if roteiro is not None else (configuracao.sede if configuracao else None)
    roteiro_dados = None
    if roteiro is not None:
        nomes = dict(Municipio.objects.filter(
            pk__in={t.origem_id for t in trechos} | {t.destino_id for t in trechos})
            .values_list("pk", "nome"))
        roteiro_dados = {
            "id": roteiro.pk, "titulo": str(roteiro), "sede": str(roteiro.sede),
            "versao": roteiro.atualizado_em.isoformat() if roteiro.atualizado_em else "",
            "trechos": [
                f"{nomes.get(t.origem_id, '?')} → {nomes.get(t.destino_id, '?')}: "
                f"{timezone.localtime(t.saida_em):%d/%m %H:%M} a "
                f"{timezone.localtime(t.chegada_em):%d/%m %H:%M}" for t in trechos]}
    else:
        avisos.append(Item("roteiro", "A viagem ainda não tem roteiro: o ofício sai sem trechos "
                                      "e sem diárias. Crie o roteiro na viagem antes, se puder."))

    diarias = _diarias(trechos, sede, len(servidores)) if servidores else None
    if diarias and diarias.erro and roteiro is not None:
        avisos.append(Item("diarias", diarias.erro))

    # Equipe como a prévia mostra; termos para quem é de outra unidade (regra do lote).
    unidade_id = getattr(unidade, "pk", None)
    equipe = [Pessoa(id=s.pk, nome=s.nome, unidade=str(s.unidade) if s.unidade_id else "",
                     de_fora=s.unidade_id != unidade_id,
                     motorista=bool(motorista and s.pk == motorista.pk and viatura),
                     falta_no_cadastro=" e ".join(s.faltando)) for s in servidores]
    for p in equipe:
        if p.falta_no_cadastro:
            avisos.append(Item("equipe", f"O cadastro de {p.nome} está incompleto (falta "
                                         f"{p.falta_no_cadastro}): o documento sai sem esse "
                                         "dado."))
    if viatura is not None and not viatura.completo:
        avisos.append(Item("transporte", f"O cadastro da viatura {viatura.placa_formatada} está "
                                         f"incompleto (falta {', '.join(viatura.faltando)})."))
    if motorista is not None and viatura is None:
        avisos.append(Item("transporte", "Quem dirige só vale com viatura: sem viatura, "
                                         f"{motorista.nome} vai como integrante da equipe."))

    # Documentos que seriam criados, com o que cada um leva.
    previstos: list[DocumentoPrevisto] = []
    if roteiro is not None:
        previstos.append(DocumentoPrevisto("roteiro", str(roteiro),
                                           "Já existe: os trechos são copiados para o ofício.",
                                           cria=False))
    transporte = (f"viatura {viatura.placa_formatada}" if viatura is not None
                  else "sem viatura (descreva o meio de transporte depois)")
    if servidores:
        previstos.append(DocumentoPrevisto(
            "oficio", f"Ofício ({NUMERO_NA_CRIACAO})",
            f"{len(servidores)} servidor(es), {transporte}; motivo da viagem"
            + ("; trechos do roteiro" if roteiro is not None else "; sem trechos"), cria=True))
    fora = [p for p in equipe if p.de_fora]
    termos_pode = entrada.termos and policies.pode_criar_termo(usuario)
    if entrada.termos and fora:
        if termos_pode:
            previstos.append(DocumentoPrevisto(
                "termo", "Termo de autorização",
                "Para " + ", ".join(p.nome for p in fora) + " (de fora da unidade emissora).",
                cria=True))
        else:
            avisos.append(Item("documentos", "Seu perfil não cria termos de autorização: eles "
                                             "não serão criados."))
    ordens_ativas = [o for o in docs.ordens if not o.cancelada]
    ordem_pode = entrada.ordem and policies.pode_criar_ordem(usuario) and not ordens_ativas
    if entrada.ordem and ordens_ativas:
        previstos.append(DocumentoPrevisto("ordem", str(ordens_ativas[0]),
                                           "A viagem já tem a OS: ela não muda.", cria=False))
    elif ordem_pode and servidores:
        previstos.append(DocumentoPrevisto("ordem", f"Ordem de serviço ({NUMERO_NA_CRIACAO})",
                                           "Com a equipe, os destinos e o período do ofício.",
                                           cria=True))
    elif entrada.ordem and not policies.pode_criar_ordem(usuario):
        avisos.append(Item("documentos", "Seu perfil não cria ordens de serviço: a OS não será "
                                         "criada."))
    planos_ativos = [p for p in docs.planos if not p.cancelado]
    plano_pode = entrada.plano and policies.pode_criar_plano(usuario) and not planos_ativos
    if entrada.plano and planos_ativos:
        previstos.append(DocumentoPrevisto("plano", str(planos_ativos[0]),
                                           "A viagem já tem o plano: ele não muda.", cria=False))
    elif plano_pode and servidores:
        previstos.append(DocumentoPrevisto("plano", f"Plano de trabalho ({NUMERO_NA_CRIACAO})",
                                           "Com o efetivo e os destinos do ofício.", cria=True))
    elif entrada.plano and not policies.pode_criar_plano(usuario):
        avisos.append(Item("documentos", "Seu perfil não cria planos de trabalho: o plano não "
                                         "será criado."))

    # Conflitos de agenda: aviso, não bloqueio (plataforma.conflitos, todas as unidades).
    inicio, fim = _periodo_dos_trechos(trechos)
    if inicio is None:
        inicio, fim = agenda_conflitos.periodo_de_datas(viagem.data_inicio, viagem.data_fim)
    conflitos: list[str] = []
    if inicio is None:
        if servidores:
            avisos.append(Item("conflitos", "Sem roteiro nem período na viagem: a agenda da "
                                            "equipe não foi conferida."))
    else:
        consulta = agenda_conflitos.consulta(
            inicio, fim, servidores=[s.pk for s in servidores],
            viaturas=[viatura.pk] if viatura is not None else [])
        conflitos = [c.mensagem for c in agenda_conflitos.conflitos(consulta)]

    # O que fica para depois de criar (não impede criar; impede emitir).
    if servidores:
        depois.append(Item("oficio", "Informe o protocolo do eProtocolo no ofício."))
        if viatura is not None and motorista is None:
            depois.append(Item("oficio", "Indique quem dirige a viatura, na folha do ofício."))
        if viatura is None:
            depois.append(Item("oficio", "Descreva o meio de transporte, na folha do ofício."))
        if configuracao is not None and trechos:
            prazo = avaliar_prazo(timezone.localdate(),
                                  timezone.localtime(trechos[0].saida_em).date(),
                                  configuracao.prazo_justificativa_dias)
            if prazo.justificativa_obrigatoria:
                depois.append(Item("justificativa", prazo.mensagem))
        if ordem_pode:
            depois.append(Item("ordem", "Confira o tipo da OS e as funções da equipe."))
        if plano_pode:
            depois.append(Item("plano", "Confira as atividades e os coordenadores do plano."))

    destinos = [str(d.municipio) for d in viagem.destinos.select_related("municipio")]
    proposta = Proposta(
        entrada=entrada, viagem_id=viagem.pk, titulo=str(viagem),
        periodo=periodo_curto(viagem.data_inicio, viagem.data_fim) or "Período não informado",
        unidade=str(viagem.unidade), destinos=destinos,
        solicitacoes=_solicitacoes(viagem), roteiro=roteiro_dados,
        equipe=equipe, viatura=str(viatura) if viatura is not None else "",
        documentos=previstos, diarias=diarias, conflitos=conflitos,
        bloqueios=list(dict.fromkeys(bloqueios)), avisos=list(dict.fromkeys(avisos)),
        depois=depois,
        versao_viagem=viagem.atualizado_em.isoformat() if viagem.atualizado_em else "")
    proposta.assinatura = assinar(proposta.dados())
    return proposta


def _solicitacoes(viagem: Viagem) -> list[int]:
    """A solicitação de evento que originou a viagem, quando houver (só o número)."""
    relacao = getattr(viagem, "solicitacoes_de_evento", None)
    if relacao is None:
        return []
    return sorted(relacao.values_list("solicitacao_id", flat=True))


# ---------------------------------------------------------------- aplicar (cria rascunhos)
def _travar_fontes(viagem: Viagem, entrada: Entrada) -> None:
    """Trava, em ordem fixa, as linhas que a assinatura da prévia cobre e que outros
    escritores travam por conta própria (`salvar_roteiro` trava o Roteiro, não a viagem):
    roteiros da viagem (e os dos ofícios dela), ofícios, OS, planos, as pessoas e a viatura.
    Assim nada muda entre a conferência da assinatura e a criação pelo lote."""
    from .models import Oficio, OrdemServico, PlanoTrabalho, Roteiro

    oficios = list(Oficio.objects.select_for_update().filter(viagem=viagem)
                   .order_by("pk").values_list("pk", flat=True))
    roteiros = set(Roteiro.objects.filter(Q(viagem=viagem) | Q(oficios__pk__in=oficios))
                   .values_list("pk", flat=True))
    list(Roteiro.objects.select_for_update().filter(pk__in=roteiros).order_by("pk")
         .values_list("pk", flat=True))  # FOR UPDATE não aceita DISTINCT: trava pelos ids
    list(OrdemServico.objects.select_for_update().filter(viagem=viagem).order_by("pk")
         .values_list("pk", flat=True))
    list(PlanoTrabalho.objects.select_for_update().filter(viagem=viagem).order_by("pk")
         .values_list("pk", flat=True))
    pessoas = sorted({*entrada.servidores, *([entrada.motorista] if entrada.motorista else [])})
    list(Servidor.objects.select_for_update().filter(pk__in=pessoas).order_by("pk")
         .values_list("pk", flat=True))
    if entrada.viatura:
        list(Viatura.objects.select_for_update().filter(pk=entrada.viatura)
             .values_list("pk", flat=True))


@transaction.atomic
def aplicar(usuario, entrada: Entrada, assinatura: str):
    """Cria os rascunhos da prévia conferida. Trava a viagem, remonta a proposta com as
    mesmas entradas e compara a assinatura: diferente → `PropostaDesatualizada`, nada gravado.
    Cria pelo lote existente (`viagem_lote.gerar`), na mesma transação."""
    from . import viagem_lote

    viagem = viagem_no_escopo(usuario, entrada.viagem)
    Viagem.objects.select_for_update().filter(pk=viagem.pk).first()
    _travar_fontes(viagem, entrada)
    proposta = montar(usuario, entrada)  # remontada DEPOIS das travas: assinatura = o que se cria
    if not assinatura or proposta.assinatura != assinatura:
        raise PropostaDesatualizada(
            "Algo mudou desde a prévia (equipe, viatura, roteiro, documentos da viagem ou a "
            "agenda de alguém). Nada foi criado: veja a prévia de novo e confira.")
    if proposta.bloqueios:
        raise PropostaBloqueada([b.mensagem for b in proposta.bloqueios])
    por_id = Servidor.objects.in_bulk(entrada.servidores)
    equipe = viagem_lote.Equipe(
        servidores=[por_id[s] for s in entrada.servidores],
        motorista=Servidor.objects.get(pk=entrada.motorista) if entrada.motorista else None,
        viatura=Viatura.objects.get(pk=entrada.viatura) if entrada.viatura else None)
    previstos = {d.tipo for d in proposta.documentos if d.cria}
    resultado = viagem_lote.gerar(usuario, viagem.pk, [equipe],
                                  com_termos="termo" in previstos,
                                  com_ordem="ordem" in previstos,
                                  com_plano="plano" in previstos)
    return proposta, resultado


# ---------------------------------------------------------------- ferramenta tipada (ADR 0020)
def _entrada_da_ferramenta(dados: dict) -> Entrada:
    from gestao.automacao.ferramentas import FerramentaInvalida

    servidores = dados.get("servidores") or []
    if (not all(isinstance(s, int) and not isinstance(s, bool) for s in servidores)
            or len(servidores) > MAX_SERVIDORES):
        raise FerramentaInvalida(f"servidores deve ser uma lista de até {MAX_SERVIDORES} ids "
                                 "inteiros, informada por uma pessoa.")
    return Entrada.de(dados["viagem"], servidores, dados.get("motorista"),
                      dados.get("viatura"), termos=dados.get("termos", True),
                      ordem=dados.get("ordem", True), plano=dados.get("plano", True))


def _ferramenta_permitida(usuario, dados: dict) -> bool:
    try:
        viagem = viagem_no_escopo(usuario, dados["viagem"])
    except ForaDoEscopo:
        return False
    return pode_propor(usuario, viagem)


def _ferramenta_previa(usuario, dados: dict) -> dict:
    return montar(usuario, _entrada_da_ferramenta(dados)).como_dict()


def registrar_ferramentas() -> None:
    """Registra `viagens.proposta_previa` (leitura). Chamado no `ready` do app Viagens.
    Não há ferramenta que crie os rascunhos: isso é ação de uma pessoa, na tela."""
    from gestao.automacao import ferramentas
    from gestao.automacao.ferramentas import Campo, Ferramenta

    ferramentas.registrar(Ferramenta(
        nome="viagens.proposta_previa", risco=ferramentas.LEITURA,
        descricao="Prévia consolidada da viagem para a equipe INFORMADA por uma pessoa: "
                  "documentos que seriam criados, diárias estimadas, conflitos e pendências. "
                  "Não grava nem reserva número; não escolhe equipe.",
        entrada={"viagem": Campo("inteiro"), "servidores": Campo("lista"),
                 "motorista": Campo("inteiro", obrigatorio=False),
                 "viatura": Campo("inteiro", obrigatorio=False),
                 "termos": Campo("booleano", obrigatorio=False),
                 "ordem": Campo("booleano", obrigatorio=False),
                 "plano": Campo("booleano", obrigatorio=False)},
        executar=_ferramenta_previa, permitido=_ferramenta_permitida,
        recurso=lambda e: f"viagens.viagem:{e['viagem']}",
        saida={"documentos": "lista", "diarias": "objeto", "conflitos": "lista de textos",
               "bloqueios": "lista", "assinatura": "texto"}))
