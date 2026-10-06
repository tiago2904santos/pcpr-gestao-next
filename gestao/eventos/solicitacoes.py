"""Escritas da solicitação de evento (transação; autorização pelas policies; avisos no
sino depois do commit). Paridade com `solicitacoes/services.py` da referência; regras em
`dominio.py`. Cada passo deixa um `Movimento`; as edições dos campos ficam na trilha de
auditoria do banco.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import partial
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from gestao.plataforma.notificacoes import notificar

from . import dominio, policies
from .models import (
    AnexoSolicitacao,
    Equipe,
    Movimento,
    Servico,
    Solicitacao,
    SolicitacaoEquipe,
    SolicitacaoServico,
)

SolicitacaoInvalida = dominio.RegraViolada

CAMPOS = ("data_solicitacao", "data_inicio_evento", "data_fim_evento", "municipio",
          "tipo_evento", "solicitante_nome", "solicitante_cargo_unidade", "contato",
          "orgao_responsavel", "unidade_movel", "unidade_movel_designada", "local_evento",
          "endereco", "bairro", "cep", "protocolo", "descricao_complementar", "tipo_operacao",
          "quantidade_cin", "motorista")
UMA_LINHA = ("solicitante_nome", "solicitante_cargo_unidade", "contato", "local_evento",
             "endereco", "bairro")


# ---------------------------------------------------------------- avisos
def _link(s: Solicitacao) -> str:
    return reverse("eventos:solicitacao", args=[s.pk])


def _dg():
    usuarios = get_user_model().objects.filter(is_active=True)
    return usuarios.filter(Q(groups__permissions__codename="despachar_solicitacao")
                           | Q(user_permissions__codename="despachar_solicitacao")).distinct()


def _avisar(usuarios, titulo: str, mensagem: str, s: Solicitacao, exceto) -> None:
    link = _link(s)
    lista = list(usuarios)
    transaction.on_commit(lambda: notificar(lista, titulo, mensagem, link, exceto=exceto))


def _mover(s: Solicitacao, usuario, acao: str, anterior: str = "", observacao: str = "") -> None:
    Movimento.objects.create(solicitacao=s, acao=acao, status_anterior=anterior,
                             status_novo=s.status, observacao=(observacao or "").strip(),
                             usuario=usuario)


# ---------------------------------------------------------------- dados
@dataclass(frozen=True)
class Estrutura:
    """Serviços (id → observação) e equipes (id → quantidade) escolhidos na tela."""

    servicos: dict[int, str]
    equipes: dict[int, int | None]


def _aplicar(s: Solicitacao, dados: dict[str, Any]) -> None:
    for campo in CAMPOS:
        if campo in dados:
            valor = dados[campo]
            if campo in UMA_LINHA:
                valor = " ".join((valor or "").split())
            setattr(s, campo, valor)
    s.protocolo = dominio.formatar_protocolo(s.protocolo)
    if not s.unidade_movel:
        s.unidade_movel_designada = None
        s.motorista = None
    if not s.tipo_operacao:
        s.tipo_operacao = Solicitacao.Operacao.DIARIA
    dominio.conferir_periodo(s.data_inicio_evento, s.data_fim_evento)


def _estrutura(s: Solicitacao, e: Estrutura | None) -> None:
    if e is None:
        return
    SolicitacaoServico.objects.filter(solicitacao=s).exclude(servico_id__in=e.servicos).delete()
    for pk, obs in e.servicos.items():
        SolicitacaoServico.objects.update_or_create(solicitacao=s, servico_id=pk,
                                                    defaults={"observacao": obs[:255]})
    SolicitacaoEquipe.objects.filter(solicitacao=s).exclude(equipe_id__in=e.equipes).delete()
    for pk, qtd in e.equipes.items():
        SolicitacaoEquipe.objects.update_or_create(solicitacao=s, equipe_id=pk,
                                                   defaults={"quantidade_servidores": qtd})
    _recalcular(s)


def _recalcular(s: Solicitacao) -> None:
    total = sum(q or 0 for q in s.equipes.values_list("quantidade_servidores", flat=True))
    Solicitacao.objects.filter(pk=s.pk).update(quantidade_servidores=total)
    s.quantidade_servidores = total


def dados_do_envio(s: Solicitacao) -> dominio.DadosDoEnvio:
    return dominio.DadosDoEnvio(
        preenchidos={campo: bool(getattr(s, f"{campo}_id", None) or getattr(s, campo, None))
                     for campo, _r in dominio.CAMPOS_DO_ENVIO},
        servicos=s.servicos.count(),
        equipes={e.equipe.nome: e.quantidade_servidores
                 for e in s.equipes.select_related("equipe")},
        tipo_operacao=s.tipo_operacao, unidade_movel=s.unidade_movel,
        unidade_movel_designada=bool(s.unidade_movel_designada_id))


def _travar(pk: int) -> Solicitacao:
    return Solicitacao.objects.select_for_update().get(pk=pk)


# ---------------------------------------------------------------- criar e editar
@transaction.atomic
def criar(usuario, dados: dict[str, Any], estrutura: Estrutura | None = None) -> Solicitacao:
    if not policies.pode_criar(usuario):
        raise PermissionDenied
    s = Solicitacao(criado_por=usuario, data_solicitacao=timezone.localdate())
    _aplicar(s, dados)
    s.save()
    _estrutura(s, estrutura)
    _mover(s, usuario, Movimento.Acao.CRIACAO)
    return s


@transaction.atomic
def salvar(usuario, pk: int, dados: dict[str, Any],
           estrutura: Estrutura | None = None) -> Solicitacao:
    """Rascunho ou devolvida: grava como está (o envio é que confere tudo)."""
    s = _travar(pk)
    if not policies.pode_editar_dados(usuario, s):
        raise PermissionDenied
    _aplicar(s, dados)
    s.save()
    _estrutura(s, estrutura)
    return s


@transaction.atomic
def enviar(usuario, pk: int) -> Solicitacao:
    s = _travar(pk)
    if not policies.pode_ver(usuario, s) or not (
            policies.pode_editar_dados(usuario, s) or s.status not in dominio.EDITAVEIS):
        raise PermissionDenied
    erros = dominio.erros_do_envio(s.status, dados_do_envio(s))
    if erros:
        raise SolicitacaoInvalida(" ".join(erros))
    anterior = s.status
    dominio.conferir_transicao(anterior, dominio.AGUARDANDO)
    s.status = Solicitacao.Status.AGUARDANDO
    s.save(update_fields=["status", "atualizado_em"])
    _mover(s, usuario, Movimento.Acao.ENVIO, anterior)
    _avisar(_dg(), f"Solicitação #{s.pk} aguardando despacho",
            f"{s.tipo_evento or 'Evento'} — {s.solicitante_nome}", s, usuario)
    return s


@transaction.atomic
def reabrir_e_reenviar(usuario, pk: int, dados: dict[str, Any],
                       estrutura: Estrutura | None = None) -> tuple[Solicitacao, bool]:
    """Alterar depois do envio: volta a aguardar o despacho e limpa a decisão (com o mesmo
    crivo do envio). Devolve (solicitação, mudou?)."""
    s = _travar(pk)
    if not policies.pode_reabrir(usuario, s):
        raise PermissionDenied
    antes: dict[str, Any] = dict(Solicitacao.objects.filter(pk=pk).values().first() or {})
    servicos_antes = set(s.servicos.values_list("servico_id", "observacao"))
    equipes_antes = set(s.equipes.values_list("equipe_id", "quantidade_servidores"))
    _aplicar(s, dados)
    s.save()
    _estrutura(s, estrutura)
    depois: dict[str, Any] = dict(Solicitacao.objects.filter(pk=pk).values().first() or {})
    ignorar = {"atualizado_em", "quantidade_servidores"}
    mudou = (any(antes.get(k) != v for k, v in depois.items() if k not in ignorar)
             or servicos_antes != set(s.servicos.values_list("servico_id", "observacao"))
             or equipes_antes != set(s.equipes.values_list("equipe_id",
                                                            "quantidade_servidores")))
    if not mudou:
        return s, False
    erros = dominio.erros_do_envio(dominio.RASCUNHO, dados_do_envio(s))
    if erros:
        raise SolicitacaoInvalida(" ".join(erros))
    anterior = s.status
    s.status = Solicitacao.Status.AGUARDANDO
    s.decisao_dg = Solicitacao.Decisao.PENDENTE
    s.observacoes_dg, s.decidido_por, s.decidido_em = "", None, None
    s.save(update_fields=["status", "decisao_dg", "observacoes_dg", "decidido_por",
                          "decidido_em", "atualizado_em"])
    obs = ("Alterada depois do despacho: aguarda novo despacho da DG."
           if anterior == dominio.DEFERIDA else "")
    _mover(s, usuario, Movimento.Acao.REENVIO, anterior, obs)
    _avisar(_dg(), f"Solicitação #{s.pk} alterada: aguarda novo despacho", obs, s, usuario)
    return s, True


# ---------------------------------------------------------------- despacho da DG
def _ajustes(s: Solicitacao, quantidades: dict[int, int]) -> list[str]:
    mudancas = []
    for e in s.equipes.select_related("equipe"):
        nova = quantidades.get(e.equipe_id)
        if nova is not None and nova != e.quantidade_servidores:
            mudancas.append(f"{e.equipe.nome}: {e.quantidade_servidores or 0} → {nova}")
            e.quantidade_servidores = nova
            e.save(update_fields=["quantidade_servidores"])
    if mudancas:
        _recalcular(s)
    return mudancas


@transaction.atomic
def ajustar_servidores(usuario, pk: int, quantidades: dict[int, int]) -> list[str]:
    if not policies.pode_despachar(usuario):
        raise PermissionDenied
    s = _travar(pk)
    if not policies.pode_ver(usuario, s):
        raise PermissionDenied
    if s.status != dominio.AGUARDANDO:
        raise SolicitacaoInvalida(dominio.MSG_SO_AGUARDANDO)
    mudancas = _ajustes(s, quantidades)
    if mudancas:
        _mover(s, usuario, Movimento.Acao.AJUSTE_DG, s.status, "; ".join(mudancas))
    return mudancas


@transaction.atomic
def despachar(usuario, pk: int, decisao: str, observacao: str = "",
              quantidades: dict[int, int] | None = None) -> Solicitacao:
    if not policies.pode_despachar(usuario):
        raise PermissionDenied
    s = _travar(pk)
    if not policies.pode_ver(usuario, s):
        raise PermissionDenied
    novo = dominio.conferir_despacho(s.status, decisao, observacao or "")
    if quantidades:
        mudancas = _ajustes(s, quantidades)
        if mudancas:
            _mover(s, usuario, Movimento.Acao.AJUSTE_DG, s.status, "; ".join(mudancas))
    anterior = s.status
    s.status = novo
    s.observacoes_dg = (observacao or "").strip()
    if decisao != "devolver":
        s.decisao_dg = decisao
        s.decidido_por, s.decidido_em = usuario, timezone.now()
    s.save()
    if decisao == "devolver":
        _mover(s, usuario, Movimento.Acao.DEVOLUCAO, anterior, s.observacoes_dg)
        _avisar([s.criado_por], f"Solicitação #{s.pk} enviada para correção",
                s.observacoes_dg, s, usuario)
    else:
        _mover(s, usuario, Movimento.Acao.DECISAO, anterior, s.observacoes_dg)
        _avisar([s.criado_por], f"Solicitação #{s.pk}: {s.get_status_display().lower()}",
                s.observacoes_dg or "A Diretoria-Geral registrou a decisão.", s, usuario)
    return s


def proxima_da_fila(usuario, depois_de: int | None = None) -> Solicitacao | None:
    """A próxima aguardando despacho: o evento mais próximo primeiro (sem data, no fim)."""
    from django.db.models import F
    qs = (policies.solicitacoes_visiveis(usuario).filter(status=dominio.AGUARDANDO)
          .order_by(F("data_inicio_evento").asc(nulls_last=True), "pk"))
    if depois_de:
        qs = qs.exclude(pk=depois_de)
    return qs.first()


# ---------------------------------------------------------------- encerramento e outros
@transaction.atomic
def concluir(usuario, pk: int, hoje: date | None = None) -> Solicitacao:
    s = _travar(pk)
    if not policies.pode_concluir(usuario, s):
        raise PermissionDenied
    erro = dominio.pode_concluir(s.status, s.data_fim_evento or s.data_inicio_evento,
                                 hoje or timezone.localdate())
    if erro:
        raise SolicitacaoInvalida(erro)
    anterior = s.status
    s.status = Solicitacao.Status.ATENDIDA
    s.save(update_fields=["status", "atualizado_em"])
    _mover(s, usuario, Movimento.Acao.CONCLUSAO, anterior)
    _avisar(_dg(), f"Solicitação #{s.pk}: atendimento confirmado", "", s, usuario)
    return s


@transaction.atomic
def cancelar(usuario, pk: int, motivo: str) -> Solicitacao:
    s = _travar(pk)
    if not policies.pode_cancelar(usuario, s):
        raise PermissionDenied
    dominio.conferir_cancelamento(s.status, motivo or "")
    anterior = s.status
    s.status = Solicitacao.Status.CANCELADA
    s.decisao_dg = Solicitacao.Decisao.CANCELADO
    s.save(update_fields=["status", "decisao_dg", "atualizado_em"])
    _mover(s, usuario, Movimento.Acao.CANCELAMENTO, anterior, motivo)
    _avisar([*_dg(), s.criado_por], f"Solicitação #{s.pk}: evento cancelado", motivo, s,
            usuario)
    return s


@transaction.atomic
def transferir(usuario, pk: int, novo, motivo: str = "") -> Solicitacao:
    s = _travar(pk)
    if not policies.pode_transferir(usuario, s):
        raise PermissionDenied
    if novo is None or not novo.is_active:
        raise SolicitacaoInvalida("Escolha um usuário ativo para ser o novo responsável.",
                                  "responsavel")
    if novo.pk == s.criado_por_id:
        raise SolicitacaoInvalida("Essa pessoa já é a responsável pela solicitação.",
                                  "responsavel")
    anterior_resp = s.criado_por
    s.criado_por = novo
    s.save(update_fields=["criado_por", "atualizado_em"])
    obs = f"De {anterior_resp.nome} para {novo.nome}." + (f" {motivo.strip()}" if motivo else "")
    _mover(s, usuario, Movimento.Acao.TRANSFERENCIA, s.status, obs)
    _avisar([novo], f"Solicitação #{s.pk} transferida para você", motivo, s, usuario)
    _avisar([anterior_resp], f"Solicitação #{s.pk} transferida para {novo.nome}", motivo, s,
            usuario)
    return s


@transaction.atomic
def duplicar(usuario, pk: int) -> Solicitacao:
    """Novo rascunho com os dados (sem datas, protocolo, decisão e anexos)."""
    origem = Solicitacao.objects.get(pk=pk)
    if not policies.pode_ver(usuario, origem):
        raise PermissionDenied
    copia = Solicitacao(criado_por=usuario, data_solicitacao=timezone.localdate())
    for campo in ("municipio", "tipo_evento", "solicitante_nome", "solicitante_cargo_unidade",
                  "contato", "orgao_responsavel", "unidade_movel", "unidade_movel_designada",
                  "local_evento", "endereco", "bairro", "cep", "descricao_complementar",
                  "tipo_operacao", "quantidade_cin", "motorista"):
        setattr(copia, campo, getattr(origem, campo))
    copia.save()
    _estrutura(copia, Estrutura(
        servicos=dict(origem.servicos.values_list("servico_id", "observacao")),
        equipes=dict(origem.equipes.values_list("equipe_id", "quantidade_servidores"))))
    _mover(copia, usuario, Movimento.Acao.CRIACAO, "", f"Copiada da #{origem.pk}")
    return copia


@transaction.atomic
def excluir(usuario, pk: int) -> int:
    s = _travar(pk)
    if not policies.pode_excluir(usuario, s):
        raise PermissionDenied
    arquivos = [a.arquivo for a in s.anexos.all()]
    s.delete()
    for arquivo in arquivos:  # só depois do commit: se a transação voltar, os anexos ficam
        transaction.on_commit(partial(arquivo.delete, save=False))
    return pk


# ---------------------------------------------------------------- anexos
EXTENSOES = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".xls", ".xlsx", ".odt",
             ".ods", ".eml", ".msg", ".txt"}
TAMANHO_MAXIMO = 10 * 1024 * 1024
# Começo do arquivo esperado por extensão (os de texto puro — eml, txt — não têm).
ASSINATURAS = {".pdf": (b"%PDF",), ".png": (b"\x89PNG",), ".jpg": (b"\xff\xd8\xff",),
               ".jpeg": (b"\xff\xd8\xff",), ".docx": (b"PK",), ".xlsx": (b"PK",),
               ".odt": (b"PK",), ".ods": (b"PK",), ".doc": (b"\xd0\xcf\x11\xe0",),
               ".xls": (b"\xd0\xcf\x11\xe0",), ".msg": (b"\xd0\xcf\x11\xe0",)}


def validar_anexo(nome: str, tamanho: int, inicio: bytes) -> None:
    from pathlib import PurePath
    ext = PurePath(nome.lower()).suffix
    if ext not in EXTENSOES:
        raise SolicitacaoInvalida(f"{nome}: tipo de arquivo não permitido. Use: "
                                  + ", ".join(sorted(e.lstrip(".") for e in EXTENSOES)) + ".")
    if tamanho > TAMANHO_MAXIMO:
        raise SolicitacaoInvalida(f"{nome}: o arquivo não pode passar de 10 MB.")
    esperado = ASSINATURAS.get(ext)
    if esperado and not any(inicio.startswith(a) for a in esperado):
        raise SolicitacaoInvalida(f"{nome}: o conteúdo do arquivo não corresponde ao tipo "
                                  "informado. Gere o documento novamente e tente anexá-lo.")


@transaction.atomic
def anexar(usuario, pk: int, arquivo) -> AnexoSolicitacao:
    s = _travar(pk)
    if not policies.pode_mexer_nos_anexos(usuario, s):
        raise PermissionDenied
    inicio = arquivo.read(8)
    arquivo.seek(0)
    validar_anexo(arquivo.name, arquivo.size, inicio)
    anexo = AnexoSolicitacao.objects.create(solicitacao=s, arquivo=arquivo,
                                            nome_original=arquivo.name[:255],
                                            tamanho=arquivo.size, enviado_por=usuario)
    _mover(s, usuario, Movimento.Acao.ANEXO, s.status, f"Anexo adicionado: {anexo.nome_original}")
    return anexo


@transaction.atomic
def remover_anexo(usuario, anexo_pk: int) -> str:
    anexo = AnexoSolicitacao.objects.select_related("solicitacao").get(pk=anexo_pk)
    s = _travar(anexo.solicitacao_id)
    if not policies.pode_mexer_nos_anexos(usuario, s):
        raise PermissionDenied
    nome = anexo.nome_original
    arquivo = anexo.arquivo
    anexo.delete()
    transaction.on_commit(lambda: arquivo.delete(save=False))
    _mover(s, usuario, Movimento.Acao.ANEXO, s.status, f"Anexo removido: {nome}")
    return nome


def servicos_ativos():
    return Servico.objects.filter(ativo=True).order_by("nome")


def equipes_ativas():
    return Equipe.objects.filter(ativo=True).order_by("nome")
