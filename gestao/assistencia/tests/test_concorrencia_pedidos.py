"""Pedidos e sugestões sob concorrência real (threads com conexões próprias, banco real): o
mesmo pedido de duas pessoas ao mesmo tempo vira um só, sem erro; dois pedidos diferentes do
mesmo registro concluindo juntos deixam UMA sugestão pronta. A espera artificial alarga a
janela entre a consulta e a gravação, onde a corrida acontecia."""

from __future__ import annotations

import threading
import time

import pytest
from django.db import connection

from gestao.assistencia import ganchos, servicos
from gestao.assistencia.models import ConfiguracaoUso, PedidoSugestao, Sugestao
from gestao.viagens.models import PrestacaoContas
from gestao.viagens.tests.cenarios import cenario_completo

RT = "viagens.rt_rascunho"


@pytest.fixture
def c(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.IA = {}
    cen = cenario_completo()
    cen.p = PrestacaoContas.objects.get(oficio_id=cen.ids["oficio_emitido"])
    return cen


def _modo(modo: str) -> None:
    ConfiguracaoUso.objects.update_or_create(uso=RT, defaults={"modo": modo, "ligado": True})


def _juntos(*chamadas):
    """Roda as chamadas ao mesmo tempo; devolve (resultados, erros)."""
    largada = threading.Barrier(len(chamadas))
    resultados: list[object] = []
    erros: list[BaseException] = []

    def rodar(chamada):
        try:
            largada.wait(timeout=10)
            resultados.append(chamada())
        except BaseException as e:  # o teste confere que não houve nenhum
            erros.append(e)
        finally:
            connection.close()

    threads = [threading.Thread(target=rodar, args=(ch,)) for ch in chamadas]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return resultados, erros


def _devagar(monkeypatch, nome: str, segundos: float = 0.4) -> None:
    original = getattr(servicos, nome)

    def lento(*args, **kwargs):
        time.sleep(segundos)
        return original(*args, **kwargs)

    monkeypatch.setattr(servicos, nome, lento)


@pytest.mark.django_db(transaction=True)
def test_mesmo_pedido_de_duas_pessoas_ao_mesmo_tempo_vira_um(c, monkeypatch):
    _modo("ia")
    _devagar(monkeypatch, "_inicio_do_dia")  # entre achar a fila vazia e criar o pedido
    pessoas = (c.usuarios["operador"], c.usuarios["gestor"])
    resultados, erros = _juntos(*(lambda u=u: servicos.pedir(u, RT, c.p.pk) for u in pessoas))
    assert erros == []
    assert len({p.pk for p in resultados}) == 1  # type: ignore[attr-defined]
    assert PedidoSugestao.objects.filter(uso=RT, recurso_id=str(c.p.pk)).count() == 1


@pytest.mark.django_db(transaction=True)
def test_dois_pedidos_do_mesmo_registro_concluindo_juntos_deixam_uma_pronta(c, monkeypatch):
    """Dois pedidos diferentes do mesmo registro (pessoas e relatos diferentes) concluem no
    worker ao mesmo tempo: cada um trava só o próprio pedido; sem a trava por uso e registro,
    os dois criavam uma sugestão PRONTA."""
    _modo("ia")
    uso = ganchos.uso(RT)
    assert uso is not None
    chamadas = []
    for login, relato in (("operador", "Relato A."), ("gestor", "Relato B.")):
        usuario = c.usuarios[login]
        pedido = servicos.pedir(usuario, RT, c.p.pk, {"relato": relato})
        ctx = uso.montar(usuario, str(c.p.pk), servicos.opcoes_limpas(uso, {"relato": relato}))
        chamadas.append(lambda p=pedido, x=ctx: servicos._registrar(
            p, uso, x, uso.deterministico(x), origem=Sugestao.Origem.REGRA))
    assert PedidoSugestao.objects.filter(uso=RT).count() == 2
    PedidoSugestao.objects.filter(uso=RT).update(estado=PedidoSugestao.Estado.PROCESSANDO)
    # Entre tornar obsoleta a anterior e criar a nova (folga para o outro chegar ao mesmo ponto).
    _devagar(monkeypatch, "codigos", 2.0)
    _, erros = _juntos(*chamadas)
    assert erros == []
    assert Sugestao.objects.filter(uso=RT, recurso_id=str(c.p.pk)).count() == 2
    assert Sugestao.objects.filter(uso=RT, recurso_id=str(c.p.pk),
                                   estado=Sugestao.Estado.PRONTA).count() == 1
