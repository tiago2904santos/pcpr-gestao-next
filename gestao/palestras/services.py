"""Escritas das palestras e eventos (transação; autorização pelas policies).

- `criar` / `salvar`: os campos do pedido, do evento e da palestra (a folha se grava
  sozinha). Telefone, CEP e protocolo saem formatados; só o canal Protocolo tem número.
- `registrar_andamento`: muda o status com a anotação; o que o status pede e ainda falta
  (data, palestrante, público) vem junto e é gravado na mesma transação.
- `registrar_resposta`: guarda o texto enviado ao solicitante e, se pedido, muda o status.
- Cadastros de apoio: temas, palestrantes e respostas padrão.

A trilha de auditoria do banco registra cada gravação; o histórico da folha a lê.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from . import dominio, policies
from .models import Andamento, Palestra, Palestrante, RespostaEnviada, RespostaPadrao, Tema

CAMPOS = ("data_solicitacao", "canal_solicitacao", "protocolo", "solicitante", "telefone",
          "email", "assunto_email", "pedido_contato", "informacoes_previas", "descricao",
          "evento", "data_inicio_evento", "data_fim_evento", "hora_inicio", "municipio",
          "local", "endereco", "bairro", "cep", "quantidade_publico")
UMA_LINHA = ("solicitante", "assunto_email", "local", "endereco", "bairro")
PalestraInvalida = dominio.RegraViolada


def _aplicar(p: Palestra, dados: dict[str, Any]) -> None:
    for campo in CAMPOS:
        if campo in dados:
            valor = dados[campo]
            if campo in UMA_LINHA:
                valor = dominio.uma_linha(valor)
            setattr(p, campo, valor)
    p.email = (p.email or "").strip().lower()
    p.telefone = dominio.formatar_telefone(p.telefone)
    p.cep = dominio.formatar_cep(p.cep)
    p.protocolo = dominio.formatar_protocolo(p.canal_solicitacao, p.protocolo)
    if p.hora_inicio:  # o horário de verdade substitui o escrito à mão (planilha)
        p.periodo_evento_texto = ""


def _conferir(p: Palestra) -> None:
    if not p.solicitante:
        raise PalestraInvalida("Informe o solicitante.", "solicitante")
    if not isinstance(p.data_solicitacao, date):
        raise PalestraInvalida("Informe a data da solicitação.", "data_solicitacao")
    dominio.conferir_periodo(p.data_inicio_evento, p.data_fim_evento)


def _relacoes(p: Palestra, dados: dict[str, Any]) -> None:
    if "temas" in dados:
        p.temas.set(dados["temas"] or [])
    if "palestrantes" in dados:
        p.palestrantes.set(dados["palestrantes"] or [])


@transaction.atomic
def criar(usuario, dados: dict[str, Any]) -> Palestra:
    if not policies.pode_criar(usuario):
        raise PermissionDenied
    p = Palestra(criado_por=usuario)
    _aplicar(p, dados)
    _conferir(p)
    p.save()
    _relacoes(p, dados)
    return p


@transaction.atomic
def salvar(usuario, pk: int, dados: dict[str, Any]) -> Palestra:
    if not policies.pode_editar(usuario):
        raise PermissionDenied
    p = Palestra.objects.select_for_update().get(pk=pk)
    _aplicar(p, dados)
    _conferir(p)
    p.save()
    _relacoes(p, dados)
    return p


def tem_palestrante(p: Palestra) -> bool:
    return p.palestrantes.exists()


@transaction.atomic
def registrar_andamento(usuario, pk: int, novo: str, anotacao: str = "", *,
                        data_evento: date | None = None,
                        palestrante: Palestrante | None = None,
                        quantidade_publico: int | None = None) -> Palestra:
    if not policies.pode_editar(usuario):
        raise PermissionDenied
    p = Palestra.objects.select_for_update().get(pk=pk)
    erros = dominio.conferir_andamento(
        atual=p.status, novo=novo, hoje=timezone.localdate(), data_inicio=p.data_inicio_evento,
        data_fim=p.data_fim_evento, data_informada=data_evento,
        tem_palestrante=tem_palestrante(p), palestrante_informado=palestrante is not None,
        publico=p.quantidade_publico, publico_informado=quantidade_publico)
    if erros:
        raise PalestraInvalida(" ".join(erros), "novo_status")
    campos = ["status", "andamento", "atualizado_em"]
    if novo in (dominio.AGENDADA, dominio.ATENDIDA) and p.data_inicio_evento is None:
        p.data_inicio_evento = data_evento
        campos.append("data_inicio_evento")
    if novo == dominio.ATENDIDA and p.quantidade_publico is None:
        p.quantidade_publico = quantidade_publico
        campos.append("quantidade_publico")
    if novo == dominio.AGENDADA and palestrante is not None and not tem_palestrante(p):
        p.palestrantes.add(palestrante)
    anotacao = (anotacao or "").strip()
    anterior = p.status
    p.status = novo
    if anotacao:
        p.andamento = anotacao
    p.save(update_fields=campos)
    Andamento.objects.create(palestra=p, status_anterior=anterior, status_novo=novo,
                             anotacao=anotacao, usuario=usuario)
    return p


def ultima_anotacao(p: Palestra) -> str:
    ultimo = p.andamentos.order_by("-em", "-pk").first()
    return ultimo.anotacao if ultimo else p.andamento


def valores_dos_marcadores(p: Palestra) -> dict[str, str]:
    return {
        "solicitante": p.solicitante,
        "data": dominio.data_do_evento(p.data_inicio_evento, p.data_fim_evento),
        "horario": f"{p.hora_inicio:%H:%M}" if p.hora_inicio else "",
        "municipio": f"{p.municipio.nome}/{p.municipio.uf}" if p.municipio else "",
        "palestrante": ", ".join(x.nome for x in p.palestrantes.all()),
        "tema": ", ".join(t.nome for t in p.temas.all()),
    }


@transaction.atomic
def registrar_resposta(usuario, pk: int, resposta: RespostaPadrao, texto: str,
                       novo_status: str = "") -> Palestra:
    """Guarda a resposta enviada e, se pedido, muda o status (com a anotação da resposta)."""
    if not policies.pode_editar(usuario):
        raise PermissionDenied
    texto = (texto or "").strip()
    if not texto:
        raise PalestraInvalida("A resposta está vazia.", "texto")
    p = Palestra.objects.select_for_update().get(pk=pk)
    RespostaEnviada.objects.create(palestra=p, tipo=resposta.tipo, texto=texto, usuario=usuario)
    if novo_status and novo_status != p.status:
        registrar_andamento(usuario, p.pk, novo_status,
                            f"Resposta padrão enviada: {resposta.tipo}.")
        p.refresh_from_db()
    return p


# ------------------------------------------------------------------ cadastros de apoio
def usos_de_temas() -> dict[int, int]:
    return dict(Tema.objects.annotate(n=Count("palestras")).values_list("pk", "n"))


def usos_de_palestrantes() -> dict[int, int]:
    return dict(Palestrante.objects.annotate(n=Count("palestras")).values_list("pk", "n"))


def _exigir_gestao(usuario) -> None:
    if not policies.pode_gerir_cadastros(usuario):
        raise PermissionDenied


@transaction.atomic
def salvar_tema(usuario, nome: str, pk: int | None = None) -> Tema:
    _exigir_gestao(usuario)
    nome = dominio.uma_linha(nome)
    if not nome:
        raise PalestraInvalida("Informe o nome.", "nome")
    if len(nome) > 200:
        raise PalestraInvalida("Use no máximo 200 caracteres.", "nome")
    if Tema.objects.filter(nome__iexact=nome).exclude(pk=pk or 0).exists():
        raise PalestraInvalida(f"Já existe “{nome}” no cadastro.", "nome")
    tema = Tema.objects.select_for_update().get(pk=pk) if pk else Tema()
    tema.nome = nome
    try:
        with transaction.atomic():
            tema.save()
    except IntegrityError as exc:
        raise PalestraInvalida(f"Já existe “{nome}” no cadastro.", "nome") from exc
    return tema


@transaction.atomic
def salvar_palestrante(usuario, dados: dict[str, Any], pk: int | None = None) -> Palestrante:
    _exigir_gestao(usuario)
    item = Palestrante.objects.select_for_update().get(pk=pk) if pk else Palestrante()
    for campo in ("nome", "servidor", "municipio", "divisao", "lotacao", "contato", "email",
                  "tema_abordagem"):
        if campo in dados:
            valor = dados[campo]
            setattr(item, campo, dominio.uma_linha(valor) if isinstance(valor, str) else valor)
    if not item.nome:
        raise PalestraInvalida("Informe o nome.", "nome")
    if Palestrante.objects.filter(nome__iexact=item.nome, lotacao__iexact=item.lotacao) \
            .exclude(pk=pk or 0).exists():
        raise PalestraInvalida("Já existe um palestrante com esse nome nessa lotação.", "nome")
    try:
        with transaction.atomic():
            item.save()
    except IntegrityError as exc:
        raise PalestraInvalida("Já existe um palestrante com esse nome nessa lotação.",
                               "nome") from exc
    return item


@transaction.atomic
def salvar_resposta_padrao(usuario, tipo: str, mensagem: str,
                           pk: int | None = None) -> RespostaPadrao:
    _exigir_gestao(usuario)
    tipo = dominio.uma_linha(tipo)
    mensagem = (mensagem or "").strip()
    if not tipo:
        raise PalestraInvalida("Informe o tipo.", "tipo")
    if not mensagem:
        raise PalestraInvalida("Escreva a mensagem.", "mensagem")
    if RespostaPadrao.objects.filter(tipo__iexact=tipo).exclude(pk=pk or 0).exists():
        raise PalestraInvalida(f"Já existe a resposta “{tipo}”.", "tipo")
    item = RespostaPadrao.objects.select_for_update().get(pk=pk) if pk else RespostaPadrao()
    item.tipo, item.mensagem = tipo, mensagem
    try:
        with transaction.atomic():
            item.save()
    except IntegrityError as exc:
        raise PalestraInvalida(f"Já existe a resposta “{tipo}”.", "tipo") from exc
    return item


@transaction.atomic
def excluir_cadastro(usuario, tipo: str, pk: int) -> str:
    """Tema e palestrante só saem quando nenhuma palestra os usa; resposta padrão sai
    sempre (as respostas enviadas guardam o próprio texto)."""
    _exigir_gestao(usuario)
    modelo: Any = {"temas": Tema, "palestrantes": Palestrante, "respostas": RespostaPadrao}[tipo]
    item = modelo.objects.select_for_update().get(pk=pk)
    if tipo != "respostas":
        usos = item.palestras.count()
        if usos:
            raise PalestraInvalida(
                f"“{item}” está em {usos} palestra{'s' if usos > 1 else ''}: não dá para excluir.")
    nome = str(item)
    item.delete()
    return nome
