"""Catálogos do plano de trabalho (módulo 6a): programas solicitantes, horários de
atendimento, atividades (com meta e recurso) e conjuntos de atividades; e os campos do
plano na configuração da unidade. Paridade com `viagens_planos/catalogos` da referência.
Dados fictícios."""

from __future__ import annotations

from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from gestao.cadastros import services
from gestao.cadastros.carga import garantir_municipios
from gestao.cadastros.models import (
    AtividadePlano,
    ConfiguracaoInstitucional,
    HorarioAtendimento,
    Lotacao,
    Municipio,
    PresetAtividades,
    ProgramaSolicitante,
    Servidor,
    SubstituicaoAssinante,
    Unidade,
)
from gestao.identidade.models import Usuario
from gestao.identidade.papeis import sincronizar_papeis

pytestmark = pytest.mark.django_db


@pytest.fixture
def base():
    sincronizar_papeis()
    ascom = Unidade.objects.create(sigla="ASCOM", nome="Assessoria de Comunicação Social")
    usuarios = {}
    for login, papel in (("operador", "OPERADOR_VIAGENS"), ("gestor", "GESTOR_VIAGENS"),
                         ("consulta", "CONSULTA")):
        u = Usuario.objects.create_user(login, f"{login}@pc.pr.gov.br", "senha-local-123",
                                        nome=login.capitalize())
        u.groups.add(Group.objects.get(name=papel))
        Lotacao.objects.create(usuario=u, unidade=ascom)
        usuarios[login] = u
    return {"ascom": ascom, **usuarios}


def _cliente(usuario) -> Client:
    c = Client()
    c.force_login(usuario)
    return c


class TestCargaInicial:
    def test_programas_horarios_e_onze_atividades(self):
        assert set(ProgramaSolicitante.objects.values_list("nome", flat=True)) >= {
            "PROGRAMA PARANÁ EM AÇÃO", "PROGRAMA JUSTIÇA NO BAIRRO", "PCPR NA COMUNIDADE"}
        assert set(HorarioAtendimento.objects.values_list("nome", flat=True)) >= {
            "09:00 até 17:00", "08:00 até 16:00", "10:00 até 18:00"}
        assert AtividadePlano.objects.count() >= 11
        movel = AtividadePlano.objects.get(codigo=AtividadePlano.UNIDADE_MOVEL)
        assert movel.nome == "Unidade móvel (ônibus ou caminhão)" and movel.meta and movel.recurso


class TestRegras:
    def test_programa_em_maiusculas_e_sem_repetir(self, base):
        c = _cliente(base["operador"])
        r = c.post(reverse("cadastros:salvar_catalogo", args=["programas"]),
                   {"nome": "  programa  cidadania  "})
        assert r.status_code == 302
        assert ProgramaSolicitante.objects.filter(nome="PROGRAMA CIDADANIA").exists()
        r = c.post(reverse("cadastros:salvar_catalogo", args=["programas"]),
                   {"nome": "Programa Cidadania"})
        assert r.status_code == 422 and "Já existe" in r.content.decode()

    def test_horario_de_inicio_e_fim(self, base):
        c = _cliente(base["operador"])
        url = reverse("cadastros:salvar_catalogo", args=["horarios"])
        assert c.post(url, {"inicio": "08:30", "fim": "12:00"}).status_code == 302
        assert HorarioAtendimento.objects.filter(nome="08:30 até 12:00").exists()
        r = c.post(url, {"inicio": "12:00", "fim": "08:00"})
        assert r.status_code == 422 and "depois do início" in r.content.decode()
        r = c.post(url, {"inicio": "08:30", "fim": "12:00"})
        assert r.status_code == 422 and "Já existe" in r.content.decode()

    def test_editar_horario_abre_com_inicio_e_fim(self, base):
        h = HorarioAtendimento.objects.get(nome="09:00 até 17:00")
        html = _cliente(base["operador"]).get(
            reverse("cadastros:horarios") + f"?editar={h.pk}").content.decode()
        assert 'value="09:00"' in html and 'value="17:00"' in html

    def test_codigo_da_atividade_nasce_do_nome_e_nao_muda(self, base):
        op = base["operador"]
        a = services.salvar_atividade(op, nome="Exposição de arte-sacra", meta="Mostrar.")
        assert a.codigo == "EXPOSICAO_DE_ARTE_SACRA"
        b = services.salvar_atividade(op, nome="Exposição de arte sacra", meta="Outra.")
        assert b.codigo == "EXPOSICAO_DE_ARTE_SACRA_2"
        a = services.salvar_atividade(op, pk=a.pk, nome="Mostra de arte", meta="Mostrar.")
        assert a.codigo == "EXPOSICAO_DE_ARTE_SACRA"
        assert services.codigo_da_atividade("", set()) == "ATIVIDADE"

    def test_atividade_exige_meta(self, base):
        r = _cliente(base["operador"]).post(
            reverse("cadastros:salvar_catalogo", args=["atividades"]),
            {"nome": "Sem meta", "meta": "   "})
        assert r.status_code == 422 and not AtividadePlano.objects.filter(nome="Sem meta").exists()

    def test_conjunto_exige_atividade_e_um_so_padrao(self, base):
        c = _cliente(base["operador"])
        url = reverse("cadastros:salvar_catalogo", args=["conjuntos"])
        r = c.post(url, {"nome": "básico"})
        assert r.status_code == 422 and "Selecione ao menos uma atividade." in r.content.decode()
        cin, bo = (AtividadePlano.objects.get(codigo=x) for x in ("CIN", "BO"))
        assert c.post(url, {"nome": "básico", "atividades": [cin.pk, bo.pk]}).status_code == 302
        basico = PresetAtividades.objects.get(nome="BÁSICO")
        assert set(basico.atividades.all()) == {cin, bo}
        outro = services.salvar_preset(base["operador"], nome="OUTRO", atividades=[cin])
        services.definir_padrao(base["operador"], PresetAtividades, basico.pk)
        services.definir_padrao(base["operador"], PresetAtividades, outro.pk)
        basico.refresh_from_db()
        assert not basico.padrao and PresetAtividades.objects.get(pk=outro.pk).padrao

    def test_atividade_usada_num_conjunto_nao_se_exclui_na_lista(self, base):
        cin = AtividadePlano.objects.get(codigo="CIN")
        services.salvar_preset(base["operador"], nome="COM CIN", atividades=[cin])
        html = _cliente(base["operador"]).get(reverse("cadastros:atividades")).content.decode()
        assert "1 conjunto" in html
        assert reverse("cadastros:excluir", args=["atividades", cin.pk]) not in html

    def test_conjunto_mantem_atividade_desativada_ao_editar(self, base):
        cin = AtividadePlano.objects.get(codigo="CIN")
        preset = services.salvar_preset(base["operador"], nome="COM CIN", atividades=[cin])
        services.alternar_ativo(base["operador"], AtividadePlano, cin.pk)
        html = _cliente(base["operador"]).get(
            reverse("cadastros:conjuntos") + f"?editar={preset.pk}").content.decode()
        assert f'value="{cin.pk}"' in html and "checked" in html


class TestTelas:
    @pytest.mark.parametrize("rota", ["programas", "horarios", "atividades", "conjuntos"])
    def test_listas_abrem_e_consulta_nao_altera(self, base, rota):
        assert _cliente(base["operador"]).get(reverse(f"cadastros:{rota}")).status_code == 200
        r = _cliente(base["consulta"]).post(
            reverse("cadastros:salvar_catalogo", args=[rota]), {"nome": "X"})
        assert r.status_code in (302, 403, 422)
        assert not ProgramaSolicitante.objects.filter(nome="X").exists()

    def test_entrada_mostra_o_grupo_do_plano(self, base):
        html = _cliente(base["operador"]).get(reverse("cadastros:indice")).content.decode()
        assert "Plano de trabalho" in html and reverse("cadastros:atividades") in html


class TestConfiguracaoDoPlano:
    def _config(self, base):
        garantir_municipios()
        return ConfiguracaoInstitucional.objects.create(
            unidade=base["ascom"], nome_extenso="Assessoria de Comunicação Social",
            sede=Municipio.objects.get(nome="Curitiba", uf="PR"),
            chefia_nome="Chefe Fictícia", chefia_cargo="Delegada")

    def test_plano_sem_assinante_sai_sem_nome_nao_cai_na_chefia(self, base):
        config = self._config(base)
        assert services.quem_assina(config, "plano_trabalho", date(2030, 1, 1)) == (
            "", "", "sem assinante")
        assert services.quem_assina(config, "oficio", date(2030, 1, 1))[2] == "chefia"
        ana = Servidor.objects.create(nome="ANA FICTÍCIA", unidade=base["ascom"])
        config.assina_plano = ana
        config.save()
        assert services.quem_assina(config, "plano_trabalho", date(2030, 1, 1))[0] == ana.nome

    def test_substituto_do_plano_no_periodo(self, base):
        config = self._config(base)
        sub = Servidor.objects.create(nome="BEA SUBSTITUTA", unidade=base["ascom"])
        SubstituicaoAssinante.objects.create(configuracao=config, servidor=sub,
                                             tipo="plano_trabalho", inicio=date(2030, 1, 1),
                                             fim=date(2030, 1, 31))
        assert services.quem_assina(config, "plano_trabalho", date(2030, 1, 10))[0] == sub.nome
        assert services.quem_assina(config, "oficio", date(2030, 1, 10))[2] == "chefia"

    def test_gestor_grava_sufixo_e_coordenador_padrao(self, base):
        config = self._config(base)
        coord = Servidor.objects.create(nome="CAIO COORDENADOR", unidade=base["ascom"])
        services.salvar_configuracao(base["gestor"], base["ascom"], sufixo_plano="ASCOM",
                                     coordenador_plano=coord)
        config.refresh_from_db()
        assert config.sufixo_plano == "ASCOM" and config.coordenador_plano == coord
