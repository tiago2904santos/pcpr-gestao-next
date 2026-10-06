"""Preencher o atendimento novo com um e-mail (I2; comportamento da referência,
`atendimento_imprensa/preenchimento.py` §2.4 — leitura própria em `dominio_email`): data e
hora do envio, quem pede (o nome já usado no histórico mantém a grafia), o veículo (só
sugestão: o cadastrado citado, ou o nome para "Outro veículo"), o contato, o pedido e o
deadline (a hora do prazo vai no texto do pedido). Nada aqui grava."""

from __future__ import annotations

from dataclasses import dataclass, field

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from . import dominio_email, policies
from .models import Atendimento, Veiculo

MSG_VAZIO = ("Não deu para ler nada do texto: confira se é o e-mail ou a mensagem do "
             "jornalista (com o pedido e o contato).")


@dataclass
class Sugestoes:
    iniciais: dict = field(default_factory=dict)
    lidos: list[tuple[str, str]] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _nome_do_historico(nome: str) -> str:
    """A grafia já usada em atendimentos anteriores, quando o nome casa (sem acento/caixa)."""
    if not nome:
        return ""
    chave = dominio_email.dobrar(" ".join(nome.split()))
    for existente in (Atendimento.objects.values_list("jornalista", flat=True)
                      .order_by("-data").distinct()[:2000]):
        if dominio_email.dobrar(" ".join(existente.split())) == chave:
            return existente
    return nome


def sugerir(usuario, texto: str) -> Sugestoes:
    if not policies.pode_criar(usuario):
        raise PermissionDenied
    agora = timezone.localtime()
    veiculos = list(Veiculo.objects.values_list("pk", "nome"))
    leitura = dominio_email.ler(texto, agora.replace(tzinfo=None), veiculos)
    s = Sugestoes()
    if leitura.vazia:
        s.avisos.append(MSG_VAZIO)
        return s
    nomes = dict(veiculos)
    jornalista = _nome_do_historico(leitura.jornalista)
    campos = (
        ("data", "Data do pedido", leitura.data,
         f"{leitura.data:%d/%m/%Y}" if leitura.data else ""),
        ("horario", "Horário", leitura.horario,
         f"{leitura.horario:%H:%M}" if leitura.horario else ""),
        ("jornalista", "Jornalista", jornalista, jornalista),
        ("veiculo", "Veículo", leitura.veiculo_id, nomes.get(leitura.veiculo_id or 0, "")),
        ("veiculo_novo", "Outro veículo (sugestão, confira)", leitura.veiculo_texto,
         leitura.veiculo_texto),
        ("contato", "Contato", leitura.contato, leitura.contato),
        ("deadline", "Deadline / veiculação", leitura.prazo.data if leitura.prazo else None,
         (f"{leitura.prazo.data:%d/%m/%Y}" + (f" até {leitura.prazo.hora:%H:%M}"
                                              if leitura.prazo.hora else ""))
         if leitura.prazo else ""),
        ("pedido", "Pedido", leitura.pedido, " ".join(leitura.pedido.split())[:120]),
    )
    for chave, rotulo, valor, mostrado in campos:
        if valor not in ("", None):
            s.iniciais[chave] = valor
            s.lidos.append((rotulo, mostrado))
    if leitura.prazo and leitura.prazo.data < agora.date():
        s.avisos.append(f"O prazo pedido ({leitura.prazo.data:%d/%m/%Y}) já passou: confira.")
    return s
