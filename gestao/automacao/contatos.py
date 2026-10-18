"""Contatos verificados, opt-in e a lista fechada de testadores.

O número vem sempre do cadastro do servidor (nada de digitar um número solto para mandar
mensagem): o operador escolhe o servidor, o contato nasce "não verificado" e passa a ativo
quando (a) a própria pessoa escreve deste número — ou o operador confirma com ela — e (b) o
opt-in é registrado (ACEITO pelo WhatsApp, termo assinado ou concordância presencial).
Revogar é imediato e cancela o que estava para sair.
"""

from __future__ import annotations

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from gestao.cadastros.models import Servidor

from . import dominio, policies
from .models import (
    CANAL_WHATSAPP,
    Comunicacao,
    ContatoVerificado,
    DestinatarioAutorizado,
    EventoContato,
    registrar_evento_contato,
)


class ContatoInvalido(Exception):
    pass


def servidores_sem_contato(usuario):
    vigentes = ContatoVerificado.objects.filter(canal=CANAL_WHATSAPP, revogado_em__isnull=True)
    qs = (Servidor.objects.filter(ativo=True).exclude(telefone="")
          .exclude(pk__in=vigentes.values("servidor_id")).order_by("nome"))
    if not (policies.ve_todas_unidades(usuario) or policies.pode_administrar(usuario)):
        unidade = policies.unidade_do_usuario(usuario)
        sem_unidade = qs.filter(unidade__isnull=True)
        # Sem unidade, unidade_id=None já equivaleria a unidade__isnull=True.
        qs = qs.filter(unidade_id=unidade) | sem_unidade if unidade is not None else sem_unidade
    return qs


@transaction.atomic
def cadastrar(usuario, servidor_pk: int) -> ContatoVerificado:
    servidor = Servidor.objects.select_for_update().get(pk=servidor_pk)
    policies.exigir(policies.pode_cuidar_do_contato(usuario, servidor),
                    "Você não cuida dos contatos deste servidor.")
    endereco = dominio.e164_do_brasil(servidor.telefone)
    if not endereco:
        raise ContatoInvalido("O telefone do cadastro não é um celular brasileiro válido.")
    try:
        with transaction.atomic():
            contato = ContatoVerificado.objects.create(servidor=servidor, endereco=endereco,
                                                       criado_por=usuario)
            registrar_evento_contato(EventoContato.Acao.CADASTRADO, contato=contato, por=usuario,
                                     origem="operador")
            return contato
    except IntegrityError as erro:
        raise ContatoInvalido("Este servidor ou este número já tem um contato vigente.") from erro


def _travar(usuario, pk: int) -> ContatoVerificado:
    contato = (ContatoVerificado.objects.select_for_update(of=("self",))
               .select_related("servidor").get(pk=pk))
    policies.exigir(policies.pode_cuidar_do_contato(usuario, contato),
                    "Você não cuida dos contatos deste servidor.")
    if contato.revogado_em:
        raise ContatoInvalido("Este contato foi revogado: cadastre de novo.")
    return contato


@transaction.atomic
def confirmar_numero(usuario, pk: int) -> ContatoVerificado:
    contato = _travar(usuario, pk)
    do_cadastro = dominio.e164_do_brasil(contato.servidor.telefone)
    if not dominio.mesmo_numero(contato.endereco, do_cadastro):
        raise ContatoInvalido("O telefone do cadastro mudou: revogue e cadastre de novo.")
    if contato.verificado_em:
        raise ContatoInvalido("O número já estava verificado.")
    contato.verificado_em, contato.verificado_por = timezone.now(), usuario
    contato.metodo = ContatoVerificado.Metodo.OPERADOR
    contato.save(update_fields=["verificado_em", "verificado_por", "metodo"])
    registrar_evento_contato(EventoContato.Acao.VERIFICADO, contato=contato, por=usuario,
                             origem="operador")
    return contato


@transaction.atomic
def registrar_optin(usuario, pk: int, origem: str) -> ContatoVerificado:
    contato = _travar(usuario, pk)
    if origem not in (ContatoVerificado.OrigemOptin.FORMULARIO,
                      ContatoVerificado.OrigemOptin.PRESENCIAL):
        raise ContatoInvalido("Origem do opt-in inválida.")
    if contato.optin_em:
        raise ContatoInvalido("O opt-in já estava registrado.")
    contato.optin_em, contato.optin_origem = timezone.now(), origem
    contato.optin_versao = getattr(settings, "AUTOMACAO_TERMO_VERSAO", "2026-10")
    contato.optin_registrado_por = usuario
    contato.save(update_fields=["optin_em", "optin_origem", "optin_versao",
                                "optin_registrado_por"])
    registrar_evento_contato(EventoContato.Acao.OPTIN, contato=contato, por=usuario,
                             origem=origem)
    return contato


@transaction.atomic
def revogar(usuario, pk: int, motivo: str) -> ContatoVerificado:
    contato = _travar(usuario, pk)
    contato.revogado_em = timezone.now()
    contato.revogado_motivo = (motivo or "Revogado pela equipe.").strip()[:120]
    contato.save(update_fields=["revogado_em", "revogado_motivo"])
    registrar_evento_contato(EventoContato.Acao.REVOGADO, contato=contato, por=usuario,
                             origem="operador")
    Comunicacao.objects.filter(contato=contato, situacao__in=(
        Comunicacao.Situacao.AGUARDANDO_APROVACAO, Comunicacao.Situacao.AGENDADA)).update(
        situacao=Comunicacao.Situacao.CANCELADA, motivo="O contato foi revogado.",
        atualizada_em=timezone.now())
    return contato


# ------------------------------------------------------------------ testadores (LAB)
@transaction.atomic
def autorizar_testador(usuario, endereco: str, descricao: str,
                       valido_ate=None) -> DestinatarioAutorizado:
    policies.exigir(policies.pode_administrar(usuario),
                    "Só quem administra a automação mexe na lista de testadores.")
    endereco = dominio.e164_do_brasil(endereco)
    if not endereco:
        raise ContatoInvalido("Informe um celular brasileiro com DDD.")
    if valido_ate and valido_ate < timezone.localdate():
        raise ContatoInvalido("A validade não pode estar no passado.")
    if DestinatarioAutorizado.objects.filter(endereco__in=dominio.variantes(endereco),
                                             removido_em__isnull=True).exists():
        raise ContatoInvalido("Este número já está na lista.")
    d = DestinatarioAutorizado.objects.create(
        endereco=endereco, descricao=descricao.strip()[:120], valido_ate=valido_ate,
        adicionado_por=usuario)
    registrar_evento_contato(EventoContato.Acao.TESTADOR_INCLUIDO, destinatario=d, por=usuario,
                             origem="operador")
    return d


@transaction.atomic
def remover_testador(usuario, pk: int) -> DestinatarioAutorizado:
    policies.exigir(policies.pode_administrar(usuario),
                    "Só quem administra a automação mexe na lista de testadores.")
    d = DestinatarioAutorizado.objects.select_for_update().get(pk=pk)
    if d.removido_em:
        raise ContatoInvalido("Este número já tinha sido removido.")
    d.removido_em, d.removido_por = timezone.now(), usuario
    d.save(update_fields=["removido_em", "removido_por"])
    registrar_evento_contato(EventoContato.Acao.TESTADOR_REMOVIDO, destinatario=d, por=usuario,
                             origem="operador")
    return d
