"""Uso de assistência do Painel (descoberto pela assistência no `ready()` dela):

- AUT-94 `painel.nota_executiva` — nota executiva de um mês sobre o relatório consolidado.
  Os números vêm do próprio relatório, com a permissão de quem pede (seção que a pessoa não vê
  não entra); o validador recusa qualquer número que não esteja nele. Só leitura.

O recurso é `<id do usuário>:<ano>-<mês>` (ex.: `7:2026-10`): o relatório depende da
permissão de quem pede, então a nota é dessa pessoa — e a obsolescência refaz o relatório com
ela.
"""

from __future__ import annotations

import re
from datetime import date

from django.urls import reverse
from django.utils import timezone

from gestao.assistencia.dominio import textos as redacao
from gestao.assistencia.ganchos import (
    Assunto,
    Contexto,
    Fato,
    Item,
    RecursoInexistente,
    UsoIA,
    registrar_uso,
)

from . import consolidado

MODULOS = {"Palestras": "palestras", "PCPR na Comunidade": "pcpr",
           "Eventos em geral": "eventos", "Coffee break": "coffee",
           "Publicações": "publicacoes", "Atendimento à imprensa": "imprensa",
           "Viagens": "viagens"}
CHAVES = ("mes", *MODULOS.values())
LACUNAS = {"mes_sem_registro": "Nenhum módulo registrou atividade neste mês."}


def _partes(recurso_id: str) -> tuple[int, int, int]:
    m = re.fullmatch(r"(\d+):(\d{4})-(\d{1,2})", str(recurso_id))
    if not m or not 1 <= int(m.group(3)) <= 12:
        raise RecursoInexistente(recurso_id)
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _dono(usuario, recurso_id: str) -> bool:
    pk, ano, _ = _partes(recurso_id)
    return (bool(getattr(usuario, "is_authenticated", False)) and usuario.pk == pk
            and ano in consolidado.anos_disponiveis(timezone.localdate()))


def _contexto(usuario, recurso_id: str) -> Contexto:
    _, ano, mes = _partes(recurso_id)
    r = consolidado.montar(usuario, ano, timezone.localdate())
    fatos = [Fato("mes", "Relatório consolidado · mês", f"{mes:02d}/{ano}")]
    for linha in (r.quadro.linhas if r.quadro else []):
        chave = MODULOS.get(linha[0])
        if chave:
            fatos.append(Fato(chave, f"Relatório consolidado · {linha[0]} no mês",
                              str(linha[mes])))
    lacunas = () if any(f.valor not in ("0", "") for f in fatos[1:]) else ("mes_sem_registro",)
    return Contexto(recurso_rotulo=f"Relatório consolidado {mes:02d}/{ano}",
                    fatos=tuple(fatos), lacunas=lacunas)


def _montar(usuario, recurso_id: str, opcoes: dict) -> Contexto:
    if not _dono(usuario, recurso_id):
        raise RecursoInexistente(recurso_id)
    return _contexto(usuario, recurso_id)


def _versao(recurso_id: str) -> str | None:
    from gestao.identidade.models import Usuario

    pk, _, _ = _partes(recurso_id)
    usuario = Usuario.objects.filter(pk=pk, is_active=True).first()
    return _contexto(usuario, recurso_id).versao if usuario else None


def _deterministico(ctx: Contexto) -> dict:
    partes = [f"{f.rotulo.removeprefix('Relatório consolidado · ').removesuffix(' no mês')}: "
              f"{f.valor}" for f in ctx.fatos[1:] if f.valor not in ("0", "")]
    if not partes:
        return {"textos": [], "lacunas": ["mes_sem_registro"]}
    texto = (f"Em {ctx.valor('mes')}, o relatório consolidado registra: "
             + "; ".join(partes) + ".")
    fontes = ["mes", *[f.chave for f in ctx.fatos[1:] if f.valor not in ("0", "")]]
    return {"textos": [{"campo": "nota", "texto": texto, "fontes": fontes}], "lacunas": []}


registrar_uso(UsoIA(
    chave="painel.nota_executiva", codigo="AUT-94",
    rotulo="Nota executiva do mês (relatório consolidado)",
    descricao="Texto curto de apresentação do mês a partir dos números do relatório "
              "consolidado que você vê. Todo número citado tem de bater com o relatório.",
    versao_prompt="nota-mes-v1",
    instrucoes=("Escreva uma nota executiva de até 4 frases sobre o mês do bloco de fatos, "
                "citando só os números dos fatos (sem somar, sem percentuais, sem comparar "
                "com outros meses) e sem adjetivos de desempenho."),
    esquema=redacao.esquema_textos(("nota",), CHAVES, LACUNAS, 900),
    campos_permitidos=CHAVES,
    dados_excluidos=("nomes de pessoas", "listas de eventos e cidades", "contatos"),
    lacunas_conhecidas=LACUNAS, montar=_montar, deterministico=_deterministico,
    validar=lambda d, c: redacao.validar_textos(
        d, fatos_texto=redacao.serializar_fatos(c.fatos), chaves=[f.chave for f in c.fatos],
        campos_alvo=("nota",), max_caracteres=900),
    itens=lambda d, c: [Item("nota", "Nota executiva", t["texto"],
                             tuple(c.rotulos(t["fontes"])), False)
                        for t in d.get("textos", [])],
    pode_pedir=_dono, pode_ver=_dono,
    descrever=lambda r: Assunto(f"Relatório consolidado {_partes(r)[2]:02d}/{_partes(r)[1]}",
                                reverse("painel:relatorios") + f"?ano={_partes(r)[1]}"),
    versao_atual=_versao, acao="Pedir nota executiva",
))


def recurso_do_mes(usuario, hoje: date | None = None) -> str:
    """O recurso da nota do mês corrente, para o botão na tela de relatórios."""
    hoje = hoje or timezone.localdate()
    return f"{usuario.pk}:{hoje.year}-{hoje.month}"
