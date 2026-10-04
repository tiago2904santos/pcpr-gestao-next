"""Resultados do plano de trabalho (paridade com `viagens_planos/resultados.py` da
referência): o realizado por atividade prevista e o relatório final montado dele."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from gestao.cadastros.models import AtividadePlano

from . import planos, policies
from .dominio import plano_trabalho as dominio
from .models import PlanoTrabalho, ResultadoAtividade


class ResultadosInvalidos(Exception):
    def __init__(self, erros: list[str]):
        super().__init__(" ".join(erros))
        self.erros = erros


@dataclass
class Linha:
    atividade: AtividadePlano
    realizado: int | None = None
    observacao: str = ""
    prevista: bool = True  # fora do plano agora, mas com resultado lançado antes
    digitado: str | None = None  # o que voltou numa gravação com erro


def atividades_previstas(plano: PlanoTrabalho) -> list[AtividadePlano]:
    """As do evento 1 e as dos demais eventos, sem repetir, em ordem alfabética."""
    planos.carregar(plano)
    vistas: dict[int, AtividadePlano] = {a.pk: a for a in plano.atividades.all()}
    for e in plano.eventos.all():
        for a in e.atividades.all():
            vistas.setdefault(a.pk, a)
    return sorted(vistas.values(), key=lambda a: a.nome.lower())


def linhas(plano: PlanoTrabalho) -> list[Linha]:
    previstas = atividades_previstas(plano)
    lancados = {r.atividade_id: r for r in plano.resultados.select_related("atividade")}
    saida = [Linha(a, getattr(lancados.get(a.pk), "realizado", None),
                   getattr(lancados.get(a.pk), "observacao", "")) for a in previstas]
    ids = {a.pk for a in previstas}
    saida += [Linha(r.atividade, r.realizado, r.observacao, prevista=False)
              for r in lancados.values() if r.atividade_id not in ids]
    return saida


@transaction.atomic
def salvar(usuario, plano_pk: int, valores: dict[int, tuple[str, str]]) -> PlanoTrabalho:
    """`valores`: {id da atividade: (realizado digitado, observação)}. Linha vazia apaga o
    resultado; os erros vêm todos de uma vez."""
    plano = PlanoTrabalho.objects.select_for_update().get(pk=plano_pk)
    policies.exigir(policies.pode_editar_plano(usuario, plano),
                    "Este plano de trabalho não pode ser alterado.")
    permitidas = {linha.atividade.pk: linha.atividade for linha in linhas(plano)}
    erros, gravar, apagar = [], [], []
    for atividade_id, (texto, observacao) in valores.items():
        atividade = permitidas.get(atividade_id)
        if atividade is None:
            continue  # atividade que não é deste plano: ignorada
        observacao = " ".join((observacao or "").split())[:500]
        try:
            realizado = dominio.ler_realizado(texto, atividade.nome)
        except dominio.RealizadoInvalido as exc:
            erros.append(str(exc))
            continue
        if realizado is None and not observacao:
            apagar.append(atividade_id)
        else:
            gravar.append((atividade, realizado, observacao))
    if erros:
        raise ResultadosInvalidos(erros)
    ResultadoAtividade.objects.filter(plano=plano, atividade_id__in=apagar).delete()
    for atividade, realizado, observacao in gravar:
        ResultadoAtividade.objects.update_or_create(
            plano=plano, atividade=atividade,
            defaults={"realizado": realizado, "observacao": observacao})
    return plano


def relatorio_final(plano: PlanoTrabalho) -> str:
    inicio, fim = planos.periodo_geral(plano)
    return dominio.relatorio_final(
        numero=plano.numero_formatado,
        programa=", ".join(dict.fromkeys(dominio.legivel(p)
                                         for p in planos.todos_os_programas(plano))),
        municipios=planos.todos_os_destinos(plano),
        periodo=dominio.periodo_curto(inicio, fim),
        resultados=[dominio.Resultado(linha.atividade.nome, linha.realizado, linha.observacao)
                    for linha in linhas(plano)],
        consideracoes=plano.consideracoes)


def sugestao_para_rt(plano: PlanoTrabalho) -> dict[str, str]:
    """Para o Relatório Técnico da prestação de contas (módulo 9): objetivo e conclusão a
    partir dos resultados (vazio sem lançamento)."""
    lancados = [linha for linha in linhas(plano) if linha.realizado]
    if not lancados:
        return {}
    local = ", ".join(planos.todos_os_destinos(plano)) or dominio.VAZIO
    programa = ", ".join(dict.fromkeys(dominio.legivel(p)
                                       for p in planos.todos_os_programas(plano)))
    nomes = "; ".join(linha.atividade.nome for linha in lancados)
    feitos = "; ".join(f"{linha.atividade.nome}: {linha.realizado}" for linha in lancados)
    return {"objetivo": f"Participação na ação em {local}" + (f" ({programa})" if programa
                                                            else "")
                        + f", com as atividades: {nomes}.",
            "conclusao": f"Foram realizados: {feitos}." + (f" {plano.consideracoes.strip()}"
                                                           if plano.consideracoes.strip()
                                                           else "")}
