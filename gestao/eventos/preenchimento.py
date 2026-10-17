"""Preencher a solicitação nova com um e-mail (paridade de comportamento com a referência):
a leitura (`leitura_email`) conferida com os cadastros vira as sugestões do formulário — só
o que foi lido, nada grava —, a lista do que foi lido (com o trecho do período), os avisos e
as solicitações que já vieram do mesmo remetente."""

from __future__ import annotations

import email
import email.policy
import re
from dataclasses import dataclass, field
from datetime import date
from email.utils import parsedate_to_datetime

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from gestao.cadastros.models import Municipio

from . import leitura_email, policies
from .models import Servico, Solicitacao, TipoEvento

LIMITE_TEXTO = 20000
LIMITE_ARQUIVO = 2 * 1024 * 1024
MSG_VAZIO = ("Não deu para ler nada do e-mail: confira se o texto é o do pedido (com a data, "
             "a cidade e o que se pede).")
MSG_ARQUIVO = "Envie o e-mail salvo como .eml (até 2 MB) ou cole o texto."


@dataclass
class Sugestoes:
    iniciais: dict = field(default_factory=dict)
    servicos: list[int] = field(default_factory=list)
    lidos: list[tuple[str, str]] = field(default_factory=list)  # (campo, o que foi lido)
    avisos: list[str] = field(default_factory=list)
    anteriores: list[Solicitacao] = field(default_factory=list)


def texto_do_eml(conteudo: bytes) -> str:
    """O .eml como se tivesse sido colado: De, Enviado em, Assunto e o corpo em texto."""
    msg = email.message_from_bytes(conteudo, policy=email.policy.default)
    enviado = ""
    if msg["date"]:
        try:
            quando = timezone.localtime(parsedate_to_datetime(str(msg["date"])))
            enviado = f"{quando:%d/%m/%Y %H:%M}"
        except (TypeError, ValueError):
            enviado = ""
    parte = msg.get_body(preferencelist=("plain", "html"))  # type: ignore[attr-defined]
    corpo = parte.get_content() if parte is not None else ""
    if parte is not None and parte.get_content_type() == "text/html":
        corpo = re.sub(r"<[^>]+>", " ", re.sub(r"<br\s*/?>|</p>", "\n", corpo, flags=re.I))
    return (f"De: {msg['from'] or ''}\nEnviado em: {enviado}\nAssunto: {msg['subject'] or ''}"
            f"\n\n{corpo}")


def sugerir(usuario, texto: str, hoje: date) -> Sugestoes:
    if not policies.pode_criar(usuario):
        raise PermissionDenied
    tipos = {leitura_email.dobrar(t.nome): t for t in TipoEvento.objects.filter(ativo=True)}
    servicos = {leitura_email.dobrar(s.nome): s for s in Servico.objects.filter(ativo=True)}
    municipios = {leitura_email.dobrar(nome): (nome, uf) for nome, uf in
                  Municipio.objects.filter(uf="PR").values_list("nome", "uf")}
    lido = leitura_email.ler(texto[:LIMITE_TEXTO], hoje, tipos=set(tipos),
                             municipios={k: f"{n}/{u}" for k, (n, u) in municipios.items()},
                             nomes_servicos=set(servicos))
    s = Sugestoes()
    if lido.vazia:
        s.avisos.append(MSG_VAZIO)
        return s
    tipo = tipos.get(lido.tipo)
    cidade = "/".join(municipios[lido.municipio]) if lido.municipio else ""
    p = lido.periodo
    campos = (
        ("data_solicitacao", "Data do pedido", lido.enviado_em.date() if lido.enviado_em
         else None, f"{lido.enviado_em:%d/%m/%Y} (o envio do e-mail)" if lido.enviado_em
         else ""),
        ("data_inicio_evento", "Período do evento", p.inicio if p else None,
         (f"{p.inicio:%d/%m/%Y}" + (f" a {p.fim:%d/%m/%Y}" if p.fim != p.inicio else "")
          + f" (de “{p.trecho}”)") if p else ""),
        ("data_fim_evento", "", p.fim if p else None, ""),
        ("tipo_evento", "Tipo", tipo, tipo.nome if tipo else ""),
        ("municipio", "Município", cidade, cidade),
        ("local_evento", "Local", lido.local, lido.local),
        ("endereco", "Endereço", lido.endereco, lido.endereco),
        ("bairro", "Bairro", lido.bairro, lido.bairro),
        ("cep", "CEP", lido.cep, lido.cep),
        ("solicitante_nome", "Quem pede", lido.solicitante, lido.solicitante),
        ("solicitante_cargo_unidade", "Cargo / unidade", lido.cargo, lido.cargo),
        ("contato", "Contato", lido.contato, lido.contato),
        ("quantidade_cin", "CIN agendadas", lido.quantidade_cin,
         str(lido.quantidade_cin or "")),
        ("unidade_movel", "Unidade móvel", True if lido.unidade_movel else None,
         "Sim" if lido.unidade_movel else ""),
        ("descricao_complementar", "", lido.descricao, ""),
    )
    for chave, rotulo, valor, mostrado in campos:
        if valor not in ("", None):
            s.iniciais[chave] = valor
            if rotulo:
                s.lidos.append((rotulo, mostrado))
    s.servicos = [servicos[n].pk for n in lido.servicos]
    if s.servicos:
        s.lidos.append(("Serviços", ", ".join(servicos[n].nome for n in lido.servicos)))
    if p and p.certeza != "alta":
        s.avisos.append("O período juntou mais de uma data citada no e-mail: confira o "
                        "começo e o fim do evento.")
    if lido.tipo == "evento":
        s.avisos.append("Nenhum tipo específico foi citado: ficou “Evento”; troque se for o "
                        "caso.")
    if lido.email:
        visiveis = policies.solicitacoes_visiveis(usuario)
        s.anteriores = list(visiveis.filter(
            Q(descricao_complementar__icontains=lido.email) | Q(contato__iexact=lido.email))
            .order_by("-pk")[:5])
    return s
