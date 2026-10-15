"""Modelos de OS cadastráveis: os do sistema semeados pela migração, o cadastro do gestor
(criar, alterar, desativar, excluir), a prévia sem gravar e as permissões."""

from __future__ import annotations

import pytest

from gestao.viagens.models import ModeloOS

pytestmark = pytest.mark.django_db


class TestModelosDoSistema:
    def test_semeados_com_funcoes_e_textos(self):
        chaves = set(ModeloOS.objects.values_list("chave", flat=True))
        assert {"operacao_policial", "caminhao", "microonibus", "cerimonial"} <= chaves
        caminhao = ModeloOS.objects.get(chave="caminhao")
        assert caminhao.padrao_sistema and caminhao.ativo
        assert [f.codigo for f in caminhao.funcoes.all()] == ["conducao", "tecnico", "apoio"]
        assert caminhao.para_dominio().combinados == {"ida_e_antes", "depois_e_volta"}
        assert not caminhao.usa_hora
        assert ModeloOS.objects.get(chave="operacao_policial").usa_hora
        assert ModeloOS.objects.get(chave="cerimonial").para_dominio().justificativas[0] \
            .startswith("O deslocamento da equipe com antecedência")
