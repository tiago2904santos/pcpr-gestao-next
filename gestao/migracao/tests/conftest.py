"""Fixtures comuns aos testes das etapas de viagens/prestação e da correção pontual."""

from __future__ import annotations

import pytest

from gestao.cadastros.models import ConfiguracaoInstitucional, Municipio, Servidor, Unidade
from gestao.migracao.models import MapaLegado


@pytest.fixture
def base():
    """Destino com o que a etapa de cadastros deixaria: configuração, servidores, municípios
    (e o mapa do legado para eles)."""
    unidade = Unidade.objects.create(nome="Unidade sintética de migração", sigla="USM")
    m1, m2 = Municipio.objects.order_by("pk")[:2]
    conf = ConfiguracaoInstitucional.objects.first() or ConfiguracaoInstitucional.objects.create(
        unidade=unidade, nome_extenso="Unidade sintética", sede=m1, chefia_nome="X",
        chefia_cargo="Y", destinatario_nome="Z", destinatario_cargo="W",
        destinatario_orgao="V")
    s1 = Servidor.objects.create(nome="SERVIDOR SINTÉTICO UM")
    s2 = Servidor.objects.create(nome="SERVIDOR SINTÉTICO DOIS")
    pares = [("ev", "viagens_cadastros_servidor", 1, s1), ("ev", "viagens_cadastros_servidor", 2,
                                                            s2),
             ("gv", "cadastros_servidor", 71, s1), ("gv", "cadastros_servidor", 72, s2),
             ("ev", "cadastros_municipio", 10, m1), ("ev", "cadastros_municipio", 20, m2),
             ("gv", "cadastros_cidade", 110, m1), ("gv", "cadastros_cidade", 120, m2)]
    for sistema, tabela, pk, obj in pares:
        MapaLegado.objects.create(sistema=sistema, tabela=tabela, origem_pk=str(pk),
                                  modelo=f"{obj._meta.app_label}.{obj.__class__.__name__}",
                                  destino_pk=str(obj.pk), lote="cadastros")
    return {"conf": conf, "s1": s1, "s2": s2, "m1": m1, "m2": m2}
