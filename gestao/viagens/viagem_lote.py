"""Gerar documentos em lote (módulo 8c, paridade com `pacote.py` da referência): um ofício
por equipe (com o roteiro e o motivo da viagem), os termos (menos quem é da unidade
emissora), a OS e o plano se a viagem ainda não os tem. Tudo em rascunho, já vinculado;
nada é emitido nem protocolado. A "meta da DG" chega com o módulo de Solicitações.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction

from gestao.cadastros.models import Servidor, Viatura

from . import ordens, planos, policies, services, termos
from .models import Oficio, Viagem
from .viagem import _situacao_pelos_documentos, documentos

MAX_OFICIOS = 20


class LoteInvalido(Exception):
    def __init__(self, erros: list[str]):
        super().__init__(" ".join(erros))
        self.erros = erros


@dataclass
class Equipe:
    servidores: list[Servidor] = field(default_factory=list)
    motorista: Servidor | None = None
    viatura: Viatura | None = None


@dataclass
class Resultado:
    oficios: list[Oficio] = field(default_factory=list)
    termos: int = 0
    ordem: object | None = None
    plano: object | None = None
    avisos: list[str] = field(default_factory=list)


def validar(viagem: Viagem, equipes: list[Equipe]) -> list[str]:
    """As mensagens da referência, todas de uma vez."""
    erros: list[str] = []
    if not equipes or not any(e.servidores for e in equipes):
        return ["Monte ao menos um ofício com a equipe."]
    if len(equipes) > MAX_OFICIOS:
        erros.append(f"No máximo {MAX_OFICIOS} ofícios de uma vez.")
    onde: dict[int, int] = {}
    for i, e in enumerate(equipes, 1):
        if not e.servidores:
            erros.append(f"Ofício {i}: escolha ao menos um servidor.")
        for s in e.servidores:
            if s.pk in onde and onde[s.pk] != i:
                erros.append(f"{s.nome} está nos ofícios {onde[s.pk]} e {i}: cada servidor vai "
                             "em um ofício só.")
            onde.setdefault(s.pk, i)
    ja = {v.servidor_id: o for o in documentos(viagem).oficios
          if o.situacao != Oficio.Situacao.CANCELADO for v in o.viajantes.all()}
    for e in equipes:
        for s in e.servidores:
            if s.pk in ja:
                erros.append(f"{s.nome} já está no {ja[s.pk]} desta viagem.")
    viaturas: dict[int, int] = {}
    for i, e in enumerate(equipes, 1):
        if e.viatura is None:
            continue
        if e.viatura.pk in viaturas:
            erros.append(f"A viatura {e.viatura} está nos ofícios {viaturas[e.viatura.pk]} e {i}.")
        viaturas.setdefault(e.viatura.pk, i)
    return list(dict.fromkeys(erros))


@transaction.atomic
def gerar(usuario, viagem_pk: int, equipes: list[Equipe], *, com_termos: bool = True,
          com_ordem: bool = True, com_plano: bool = True) -> Resultado:
    viagem = Viagem.objects.select_for_update().get(pk=viagem_pk)
    policies.exigir(policies.pode_editar_viagem(usuario, viagem),
                    "Reative a viagem antes de gerar documentos.")
    # O motorista que não está em equipe nenhuma entra na do ofício dele (referência).
    todos = {s.pk for e in equipes for s in e.servidores}
    for e in equipes:
        if e.motorista is not None and e.motorista.pk not in todos:
            e.servidores.append(e.motorista)
            todos.add(e.motorista.pk)
    erros = validar(viagem, equipes)
    if erros:
        raise LoteInvalido(erros)
    docs = documentos(viagem)
    roteiro = next((r for r in reversed(docs.roteiros) if r.editavel), None)
    resultado = Resultado()
    if roteiro is None:
        resultado.avisos.append("A viagem ainda não tem roteiro: os ofícios saíram sem roteiro "
                                "e sem diárias.")
    for e in equipes:
        oficio = (services.criar_oficio_do_roteiro(usuario, roteiro) if roteiro is not None
                  else services.criar_rascunho(usuario))
        dados: dict = {"motivo": viagem.motivo} if viagem.motivo else {}
        if e.viatura is not None:
            dados.update(tipo_transporte=Oficio.TipoTransporte.VIATURA, viatura=e.viatura)
        if dados:
            oficio = services.salvar_dados(oficio, usuario, dados)
        viajantes = {s.pk: services.adicionar_viajante(oficio, usuario, s) for s in e.servidores}
        if e.motorista is not None and e.viatura is not None:
            services.definir_motorista(oficio, usuario, viajantes[e.motorista.pk].pk)
        Oficio.objects.filter(pk=oficio.pk).update(viagem=viagem)
        oficio.refresh_from_db()
        resultado.oficios.append(oficio)
        if com_termos:
            fora = [s for s in e.servidores if s.unidade_id != oficio.unidade_id]
            if fora:
                termo = termos.salvar(usuario, oficio=oficio, servidores=fora)
                type(termo).objects.filter(pk=termo.pk).update(viagem=viagem)
                resultado.termos += 1
    ativas = [o for o in docs.ordens if not o.cancelada]
    if com_ordem and not ativas:
        ordem, _ = ordens.salvar(usuario, oficios=resultado.oficios)
        type(ordem).objects.filter(pk=ordem.pk).update(viagem=viagem)
        resultado.ordem = ordem
    elif com_ordem and ativas:
        resultado.avisos.append(f"A viagem já tinha a {ativas[0]}; ela não foi alterada.")
    ativos = [p for p in docs.planos if not p.cancelado]
    if com_plano and not ativos:
        plano, _ = planos.salvar(usuario, oficios=resultado.oficios)
        type(plano).objects.filter(pk=plano.pk).update(viagem=viagem)
        resultado.plano = plano
    elif com_plano and ativos:
        resultado.avisos.append(f"A viagem já tinha o {ativos[0]}; ele não foi alterado.")
    _situacao_pelos_documentos(viagem)
    if viagem.situacao in (Viagem.Situacao.RASCUNHO, Viagem.Situacao.PREPARACAO):
        Viagem.objects.filter(pk=viagem.pk).update(situacao=Viagem.Situacao.GERADOS)
    return resultado
