"""Tipos de OS fixos: OS padrão (sem modelo), operação policial, unidade móvel e
cerimonial — nomes, ordem e textos vêm do código (`modelos_do_sistema`); não há cadastro na
tela. No cerimonial, os dias entre a saída e o evento são de visita técnica."""

from __future__ import annotations

from datetime import date

import pytest
from django.test import Client
from django.urls import NoReverseMatch, reverse

from gestao.cadastros.models import Municipio, Servidor
from gestao.viagens import ordens
from gestao.viagens.forms import FormularioOrdem
from gestao.viagens.modelos_do_sistema import sincronizar
from gestao.viagens.models import FuncaoOS, ModeloOS

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    return cenario_completo()


def _modelo(chave: str) -> ModeloOS:
    return ModeloOS.objects.get(chave=chave)


class TestTiposFixos:
    def test_nomes_e_ordem_na_escolha_da_os(self, c):
        form = FormularioOrdem()
        campo = form.fields["modelo"]
        assert campo.label == "Tipo de OS" and campo.empty_label == "OS padrão"
        assert [m.nome for m in campo.queryset] == [
            "Operação policial", "Unidade móvel", "Cerimonial"]

    def test_funcoes_de_cada_tipo(self):
        assert [f.codigo for f in _modelo("unidade_movel").funcoes.all()] == [
            "conducao", "tecnico", "apoio"]
        assert [f.codigo for f in _modelo("cerimonial").funcoes.all()] == [
            "coordenacao", "apoio", "preparacao"]
        assert _modelo("operacao_policial").usa_hora
        assert _modelo("unidade_movel").para_dominio().combinados == {"ida_e_antes",
                                                                   "depois_e_volta"}

    def test_sincronizar_desfaz_mudanca_no_banco_e_mantem_funcao_em_uso(self, c):
        cerimonial = _modelo("cerimonial")
        ModeloOS.objects.filter(pk=cerimonial.pk).update(nome="Outro", ordem=99, ativo=False,
                                                         antes="x")
        sincronizar(ModeloOS, FuncaoOS)
        cerimonial.refresh_from_db()
        assert (cerimonial.nome, cerimonial.ordem, cerimonial.ativo) == ("Cerimonial", 40, True)
        assert "visita técnica" in cerimonial.antes

    def test_nao_ha_mais_cadastro_de_modelos(self, c):
        with pytest.raises(NoReverseMatch):
            reverse("viagens:modelos_os")
        cli = Client()
        cli.force_login(c.usuarios["gestor"])
        assert cli.get("/viagens/ordens/modelos/").status_code == 404
        assert "Modelos de OS" not in cli.get(reverse("cadastros:indice")).content.decode()


class TestCerimonialComVisitaTecnica:
    def _ordem(self, c, saida: int, evento: int):
        um = Servidor.objects.first()
        ordem, _ = ordens.salvar(
            c.usuarios["operador"], modelo=_modelo("cerimonial"),
            destinos=[Municipio.objects.get(nome="Londrina", uf="PR")],
            data_inicio=date(2030, 5, saida), data_fim=date(2030, 5, 8),
            data_evento_inicio=date(2030, 5, evento), data_evento_fim=date(2030, 5, evento),
            servidores=[um], motivo="a solenidade", funcoes={str(um.pk): "coordenacao"})
        return [t for _, t in ordens.dados_do_documento(ordem, fixar=False)["itens"]]

    def test_saida_dia_4_evento_dia_6(self, c):
        itens = self._ordem(c, saida=4, evento=6)
        # I = a função; II = deslocamento no dia 4; III = visita técnica no dia 5.
        assert itens[1].startswith("O deslocamento") and "no dia 4 de maio de 2030" in itens[1]
        assert itens[2].startswith("Que a equipe realize no dia 5 de maio de 2030 a visita "
                                   "técnica ao local do evento")
        assert "no dia 6 de maio de 2030" in itens[3]

    def test_saida_na_vespera_junta_deslocamento_e_visita(self, c):
        itens = self._ordem(c, saida=5, evento=6)
        assert "no dia 5 de maio de 2030, com a visita técnica ao local do evento no mesmo " \
               "dia" in itens[1]


class TestUnidadeMovel:
    def test_micro_onibus_e_caminhao_viram_unidade_movel(self, c):
        """Banco com os dois tipos antigos (antes da 0056): as OS passam para "Unidade
        móvel" e os antigos somem."""
        from gestao.viagens.modelos_do_sistema import juntar
        from gestao.viagens.models import OrdemServico

        destino = _modelo("unidade_movel")
        antigos = []
        for chave, nome in (("caminhao", "Caminhão"), ("microonibus", "Micro-ônibus")):
            antigo = ModeloOS.objects.create(chave=chave, nome=nome, referencia="x")
            FuncaoOS.objects.create(modelo=antigo, codigo="conducao", nome="Condução",
                                    texto="x")
            ordem, _ = ordens.salvar(c.usuarios["operador"], modelo=antigo,
                                     destinos=[Municipio.objects.get(nome="Londrina", uf="PR")])
            antigos.append(ordem.pk)
        juntar(ModeloOS, OrdemServico)
        sincronizar(ModeloOS, FuncaoOS)
        assert set(OrdemServico.objects.filter(pk__in=antigos).values_list(
            "modelo__chave", flat=True)) == {"unidade_movel"}
        assert not ModeloOS.objects.filter(chave__in=["caminhao", "microonibus"]).exists()
        assert _modelo("unidade_movel").pk == destino.pk
