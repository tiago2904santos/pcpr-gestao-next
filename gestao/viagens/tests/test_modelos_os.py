"""Modelos de OS cadastráveis: os do sistema semeados pela migração, o cadastro do gestor
(criar, alterar, desativar, excluir), a prévia sem gravar e as permissões."""

from __future__ import annotations

from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import Municipio, Servidor
from gestao.viagens import modelos_os, ordens
from gestao.viagens.forms import FormularioOrdem
from gestao.viagens.models import ModeloOS

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    return cenario_completo()


def _cliente(usuario) -> Client:
    cli = Client()
    cli.force_login(usuario)
    return cli


def _modelo(chave: str) -> ModeloOS:
    return ModeloOS.objects.get(chave=chave)


def _dados(**extra) -> dict:
    base = {"nome": "Operação com foto", "referencia": "Deslocamento de Operação Policial",
            "ida": "O deslocamento {equipe} para {municipio} {data}.",
            "evento": "Que o policial {servidores} acompanhe a operação em {destino} {data}.",
            "volta": "Que a equipe retorne a {sede} {data}.",
            "funcao_nome_1": "Motorista", "funcao_icone_1": "car",
            "funcao_texto_1": "Que {servidores} conduza o veículo oficial.",
            "funcao_nome_2": "Fotógrafo", "funcao_icone_2": "camera",
            "funcao_texto_2": "Que {servidores} registre em fotografia a operação."}
    return {**base, **extra}


class TestModelosDoSistema:
    def test_semeados_com_funcoes_e_textos(self):
        chaves = set(ModeloOS.objects.values_list("chave", flat=True))
        assert {"operacao_policial", "caminhao", "microonibus", "cerimonial"} <= chaves
        caminhao = _modelo("caminhao")
        assert caminhao.padrao_sistema and caminhao.ativo
        assert [f.codigo for f in caminhao.funcoes.all()] == ["conducao", "tecnico", "apoio"]
        assert caminhao.para_dominio().combinados == {"ida_e_antes", "depois_e_volta"}
        assert not caminhao.usa_hora
        assert _modelo("operacao_policial").usa_hora
        assert _modelo("cerimonial").para_dominio().justificativas[0] \
            .startswith("O deslocamento da equipe com antecedência")


class TestCadastro:
    def test_gestor_cria_modelo_com_funcoes_e_operador_so_ve(self, c):
        gestor = _cliente(c.usuarios["gestor"])
        r = gestor.post(reverse("viagens:salvar_modelo_os"), _dados())
        assert r.status_code == 302, r.content.decode()[:500]
        modelo = ModeloOS.objects.get(nome="Operação com foto")
        assert [(f.codigo, f.nome, f.icone) for f in modelo.funcoes.all()] == [
            ("motorista", "Motorista", "car"), ("fotografo", "Fotógrafo", "camera")]
        assert not modelo.padrao_sistema and modelo.ativo and not modelo.usa_hora
        html = gestor.get(reverse("viagens:modelos_os")).content.decode()
        assert "Operação com foto" in html and "Novo modelo" in html and "Fotógrafo" in html
        operador = _cliente(c.usuarios["operador"])
        assert operador.post(reverse("viagens:salvar_modelo_os"), _dados()).status_code == 403
        html = operador.get(reverse("viagens:modelos_os")).content.decode()
        assert "Operação com foto" in html and "Novo modelo" not in html
        assert _cliente(c.usuarios["consulta"]).get(
            reverse("viagens:modelos_os")).status_code == 403

    def test_marcador_invalido_e_erro_no_campo(self, c):
        gestor = _cliente(c.usuarios["gestor"])
        r = gestor.post(reverse("viagens:salvar_modelo_os"),
                        _dados(evento="x {foo}", funcao_texto_1="y {data}"))
        assert r.status_code == 422
        html = r.content.decode()
        assert "Marcador desconhecido: {foo}" in html
        assert "Marcador desconhecido aqui: {data}" in html
        assert not ModeloOS.objects.filter(nome="Operação com foto").exists()

    def test_editar_mantem_o_codigo_da_funcao_e_a_os_que_a_usa(self, c):
        gestor = c.usuarios["gestor"]
        modelo = modelos_os.salvar(gestor, **_para_salvar(_dados()))
        londrina = Municipio.objects.get(nome="Londrina", uf="PR")
        um = Servidor.objects.first()
        ordem, _ = ordens.salvar(gestor, modelo=modelo, destinos=[londrina], servidores=[um],
                                 funcoes={str(um.pk): "fotografo"})
        assert ordem.funcoes == {str(um.pk): "fotografo"}
        # Renomear a função mantém o código (a OS continua apontando para ela).
        dados = _dados(funcao_codigo_2="fotografo", funcao_nome_2="Fotografia")
        modelos_os.salvar(gestor, pk=modelo.pk, **_para_salvar(dados))
        assert [f.nome for f in modelo.funcoes.all()] == ["Motorista", "Fotografia"]
        # Tirar uma função em uso é recusado.
        dados = _dados(funcao_nome_2="", funcao_texto_2="")
        with pytest.raises(modelos_os.ModeloInvalido, match="em uso"):
            modelos_os.salvar(gestor, pk=modelo.pk, **_para_salvar(dados))

    def test_excluir_so_sem_os_e_nunca_do_sistema(self, c):
        gestor = c.usuarios["gestor"]
        modelo = modelos_os.salvar(gestor, **_para_salvar(_dados()))
        londrina = Municipio.objects.get(nome="Londrina", uf="PR")
        ordem, _ = ordens.salvar(gestor, modelo=modelo, destinos=[londrina])
        cli = _cliente(gestor)
        cli.post(reverse("viagens:modelo_os_excluir", args=[modelo.pk]))
        assert ModeloOS.objects.filter(pk=modelo.pk).exists()  # em uso: recusado
        ordens.excluir(gestor, ordem.pk)
        cli.post(reverse("viagens:modelo_os_excluir", args=[modelo.pk]))
        assert not ModeloOS.objects.filter(pk=modelo.pk).exists()
        sistema = _modelo("caminhao")
        cli.post(reverse("viagens:modelo_os_excluir", args=[sistema.pk]))
        assert ModeloOS.objects.filter(pk=sistema.pk).exists()

    def test_desativar_some_das_opcoes_mas_a_os_antiga_continua(self, c):
        gestor = c.usuarios["gestor"]
        londrina = Municipio.objects.get(nome="Londrina", uf="PR")
        modelo = _modelo("microonibus")
        ordem, _ = ordens.salvar(gestor, modelo=modelo, destinos=[londrina],
                                 data_inicio=date(2030, 5, 5))
        _cliente(gestor).post(reverse("viagens:modelo_os_ativo", args=[modelo.pk]))
        modelo.refresh_from_db()
        assert not modelo.ativo
        nova = FormularioOrdem(unidade=ordem.unidade)
        assert modelo not in nova.fields["modelo"].queryset
        antiga = FormularioOrdem.de(ordem)
        assert modelo in antiga.fields["modelo"].queryset
        assert ordens.dados_do_documento(ordem, fixar=False)["referencia"] == modelo.referencia

    def test_exemplo_mostra_a_folha_sem_gravar(self, c):
        gestor = _cliente(c.usuarios["gestor"])
        r = gestor.post(reverse("viagens:exemplo_modelo_os"), _dados())
        assert r.status_code == 200
        html = r.content.decode()
        assert "DETERMINO" in html and "Ana Exemplo" in html and "MINUTA" in html
        # Três pessoas de exemplo e duas funções: a 1.ª e a 3.ª têm a primeira função.
        assert "I - Que Ana Exemplo e Carla Exemplo conduza o veículo oficial." in html
        assert "II - Que Bruno Exemplo registre em fotografia a operação." in html
        assert "Ref.:</strong> Deslocamento de Operação Policial" in html
        assert not ModeloOS.objects.filter(nome="Operação com foto").exists()
        r = gestor.post(reverse("viagens:exemplo_modelo_os"), _dados(nome=""))
        assert r.status_code == 422


def _para_salvar(dados: dict) -> dict:
    """O que a view manda ao serviço a partir dos dados da tela."""
    from gestao.viagens.forms import FormularioModeloOS
    form = FormularioModeloOS(dados)
    assert form.is_valid(), form.errors
    return form.dados_para_salvar()
