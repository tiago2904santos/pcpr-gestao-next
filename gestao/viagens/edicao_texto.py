"""Texto editado dos documentos fora do ofício (termo, OS) — ADR 0018, as mesmas regras do
editor do ofício (services.salvar_texto_do_documento):

- cada salvamento, restauração ou "voltar ao modelo" é uma versão nova; a vigente é a de
  maior `numero`; `regioes == {}` é "como o modelo gera";
- região igual ao modelo não é guardada; a impressão do modelo de cada região editada fica
  guardada para avisar quando o cadastro mudar depois (texto desatualizado);
- `versao_base` diferente da vigente: alguém salvou antes — conflito;
- salvamentos seguidos da mesma pessoa em poucos minutos viram uma versão só;
- `guardar_modelos` (o termo): guarda também o HTML do modelo de cada região editada, para
  a edição acompanhar os dados quando eles mudarem depois (fusão a três, termos.py).

Quem chama (termos.py, ordens.py) trava o documento, confere a permissão e diz onde as
versões moram (`versoes`: a consulta das versões daquele documento; `criar`: como criar
uma). Os erros são os do módulo que chama.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.utils import timezone

JANELA_DE_COALESCENCIA = timedelta(minutes=10)


def vigente(versoes) -> Any:
    return versoes.select_related("criado_por").order_by("-numero").first()


def salvar(versoes, criar: Callable[..., Any], usuario, originais: dict[str, str],
           regioes: dict[str, str], *, versao_base: int | None,
           invalido: type[Exception], conflito: type[Exception],
           guardar_modelos: bool = False) -> Any:
    from .documentos.regioes import blocos_alterados, impressao, normalizar, sanear_html
    from .models import EdicaoDocumento

    atual = vigente(versoes)
    numero_vigente = atual.numero if atual else 0
    if versao_base is not None and versao_base != numero_vigente:
        raise conflito(
            "Outra pessoa alterou o texto deste documento enquanto você editava. Recarregue "
            "a folha para ver a versão atual antes de salvar de novo.")
    limpas: dict[str, str] = {}
    alterados: list[dict[str, str]] = []
    impressoes: dict[str, str] = {}
    modelos: dict[str, str] = {}
    for regiao, original in originais.items():
        if regiao not in regioes:
            if atual is not None and regiao in atual.regioes:  # não enviada: mantém
                limpas[regiao] = atual.regioes[regiao]
                alterados += blocos_alterados(original, limpas[regiao])
                impressoes[regiao] = atual.impressoes.get(regiao, impressao(original))
                modelos[regiao] = getattr(atual, "modelos", {}).get(regiao, original)
            continue
        html = sanear_html(regioes[regiao])
        if normalizar(html) == normalizar(sanear_html(original)):
            continue
        limpas[regiao] = html
        alterados += blocos_alterados(original, html)
        impressoes[regiao] = impressao(original)
        modelos[regiao] = original
    extras: dict[str, Any] = {"modelos": modelos} if guardar_modelos else {}
    acao = EdicaoDocumento.Acao.EDITADO if limpas else EdicaoDocumento.Acao.MODELO
    if atual is not None and atual.regioes == limpas:
        return atual  # nada mudou
    if atual is None and not limpas:
        raise invalido("O texto está igual ao modelo: não há o que salvar.")
    if (atual is not None and atual.acao == EdicaoDocumento.Acao.EDITADO
            and acao == EdicaoDocumento.Acao.EDITADO
            and atual.criado_por_id == getattr(usuario, "pk", None)
            and timezone.now() - atual.criado_em < JANELA_DE_COALESCENCIA):
        atual.regioes, atual.blocos_alterados, atual.impressoes = limpas, alterados, impressoes
        for campo, valor in extras.items():
            setattr(atual, campo, valor)
        atual.save(update_fields=["regioes", "blocos_alterados", "impressoes", *extras])
        return atual
    return criar(numero=numero_vigente + 1, acao=acao, regioes=limpas,
                 blocos_alterados=alterados, impressoes=impressoes, criado_por=usuario,
                 **extras)


def restaurar(versoes, criar: Callable[..., Any], usuario, numero: int, *,
              invalido: type[Exception]) -> Any:
    """Volta a um texto anterior criando uma versão nova (o histórico nunca perde nada)."""
    from .models import EdicaoDocumento

    origem = versoes.filter(numero=numero).first()
    if origem is None:
        raise invalido(f"Não existe a versão {numero} do texto.")
    atual = vigente(versoes)
    if atual is not None and atual.pk == origem.pk:
        return atual
    extras = {"modelos": dict(origem.modelos)} if hasattr(origem, "modelos") else {}
    return criar(numero=(atual.numero if atual else 0) + 1,
                 acao=EdicaoDocumento.Acao.RESTAURADO, regioes=dict(origem.regioes),
                 blocos_alterados=list(origem.blocos_alterados),
                 impressoes=dict(origem.impressoes), restaurada_de=origem, criado_por=usuario,
                 **extras)


def voltar_ao_modelo(versoes, criar: Callable[..., Any], usuario) -> Any:
    """Descarta o texto editado: o documento volta a sair como o modelo gera."""
    from .models import EdicaoDocumento

    atual = vigente(versoes)
    if atual is None or atual.do_modelo:
        return atual
    return criar(numero=atual.numero + 1, acao=EdicaoDocumento.Acao.MODELO, criado_por=usuario)
