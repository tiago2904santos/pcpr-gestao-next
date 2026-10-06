"""Preencher a OS nova com um e-mail (CB7c; paridade de comportamento com
`coffee_break/preenchimento.py` §11): a leitura (`dominio_email`) vira as sugestões do
formulário; o município só do Paraná (é ele que decide o lote); o lote e o saldo são
conferidos já na leitura (falta vira aviso antes de salvar); uma data só por OS (período
vira aviso); o nº da OS nunca é sugerido; e as OS já criadas a partir do mesmo e-mail
aparecem. Nada aqui grava."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from django.core.exceptions import PermissionDenied

from gestao.cadastros.models import Municipio

from . import dominio_email, policies, queries
from . import dominio_pedido as regras
from .models import Solicitacao

MSG_VAZIO = ("Não deu para ler nada do e-mail: confira se o texto colado é o do pedido "
             "(com data, local e quantidade).")


@dataclass
class Sugestoes:
    iniciais: dict = field(default_factory=dict)
    lidos: list[tuple[str, str]] = field(default_factory=list)  # (campo, o que foi lido)
    avisos: list[str] = field(default_factory=list)
    anteriores: list[Solicitacao] = field(default_factory=list)


def nomes_do_parana() -> dict[str, str]:
    """Nome dobrado → "Cidade/PR"."""
    return {dominio_email.dobrar(n): f"{n}/PR"
            for n in Municipio.objects.filter(uf="PR").values_list("nome", flat=True)}


def _com_cidade(descricao: str, cidade: str) -> str:
    """"Encontro Regional" + Ponta Grossa → "Encontro Regional - Ponta Grossa"."""
    if cidade and dominio_email.dobrar(cidade) not in dominio_email.dobrar(descricao):
        return f"{descricao} - {cidade}"
    return descricao


def sugerir(usuario, texto: str, hoje: date) -> Sugestoes:
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    leitura = dominio_email.ler(texto, hoje, nomes_do_parana())
    s = Sugestoes()
    if leitura.vazia:
        s.avisos.append(MSG_VAZIO)
        return s
    cidade = leitura.municipio.rsplit("/", 1)[0] if leitura.municipio else ""
    campos = (
        ("municipio", "Município", leitura.municipio, leitura.municipio),
        ("data_evento", "Data do evento", leitura.data,
         f"{leitura.data:%d/%m/%Y}" if leitura.data else ""),
        ("horario", "Horário", leitura.horario,
         f"{leitura.horario:%H:%M}" if leitura.horario else ""),
        ("descricao", "Evento", _com_cidade(leitura.descricao, cidade) if leitura.descricao
         else "", leitura.descricao),
        ("quantidade", "Quantidade", leitura.quantidade.valor if leitura.quantidade else None,
         f"{leitura.quantidade.valor} (de “{leitura.quantidade.trecho}”)"
         if leitura.quantidade else ""),
        ("local_entrega", "Local de entrega", leitura.local, leitura.local),
        ("endereco", "Endereço", leitura.endereco, leitura.endereco),
        ("bairro", "Bairro", leitura.bairro, leitura.bairro),
        ("cep", "CEP", leitura.cep, leitura.cep),
        ("responsavel", "Quem recebe", leitura.responsavel, leitura.responsavel),
    )
    for chave, rotulo, valor, mostrado in campos:
        if valor not in ("", None):
            s.iniciais[chave] = valor
            s.lidos.append((rotulo, mostrado))
    if len(leitura.dias) > 1:
        s.avisos.append(
            f"O pedido fala de {len(leitura.dias)} dias ({leitura.dias[0]:%d/%m} a "
            f"{leitura.dias[-1]:%d/%m}), e a OS tem uma data só: preenchi o primeiro dia. "
            "Para os outros dias, registre uma solicitação por dia.")
    if cidade and (municipio := Municipio.objects.filter(uf="PR", nome=cidade).first()):
        info = queries.lote_para(municipio, leitura.data or hoje)
        if info is None:
            s.avisos.append(regras.MSG_SEM_LOTE.format(municipio=leitura.municipio))
        elif leitura.quantidade and leitura.quantidade.valor > info.saldo.restante:
            s.avisos.append(
                f"O {info.lote} ({info.lote.contrato.fornecedor}), que atende {cidade}, tem "
                f"saldo de {info.saldo.restante} unidade(s) e o pedido é de "
                f"{leitura.quantidade.valor}: a solicitação não poderá ser salva com essa "
                "quantidade.")
    digital = dominio_email.impressao(texto)
    s.iniciais["email_impressao"] = digital
    s.anteriores = list(Solicitacao.objects.filter(email_impressao=digital)
                        .order_by("-criado_em")[:10])
    return s
