"""Cadastros mantidos em tela (módulo 2): servidores, viaturas, unidades, cargos,
combustíveis, tabela de diárias e configuração da unidade.

Cada teste diz qual regra da referência (ou decisão) prova. Dados fictícios.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse

from gestao.cadastros import services
from gestao.cadastros.carga import garantir_municipios
from gestao.cadastros.models import (
    Cargo,
    Combustivel,
    ConfiguracaoInstitucional,
    Lotacao,
    Municipio,
    Servidor,
    TabelaDiaria,
    Unidade,
    Viatura,
)
from gestao.cadastros.validacoes import RG_NAO_POSSUI
from gestao.identidade.models import Usuario
from gestao.identidade.papeis import sincronizar_papeis

pytestmark = pytest.mark.django_db

CPF_VALIDO = "529.982.247-25"  # dígito verificador correto (exemplo público de validação)
CPF_VALIDO_2 = "111.444.777-35"


@pytest.fixture
def base():
    sincronizar_papeis()
    ascom = Unidade.objects.create(sigla="ASCOM", nome="Assessoria de Comunicação Social")
    dpc = Unidade.objects.create(sigla="DPC", nome="Divisão de Polícia da Capital")
    agente = Cargo.objects.create(nome="Agente de Polícia Judiciária")
    Cargo.objects.create(nome="Escrivão de Polícia")
    diesel = Combustivel.objects.create(nome="Diesel")
    Combustivel.objects.create(nome="Gasolina")
    usuarios = {}
    for login, papel, unidade in (("operador", "OPERADOR_VIAGENS", ascom),
                                  ("gestor", "GESTOR_VIAGENS", ascom),
                                  ("consulta", "CONSULTA", None)):
        u = Usuario.objects.create_user(login, f"{login}@pc.pr.gov.br", "senha-local-123",
                                        nome=login.capitalize())
        u.groups.add(Group.objects.get(name=papel))
        if unidade:
            Lotacao.objects.create(usuario=u, unidade=unidade)
        usuarios[login] = u
    return {"ascom": ascom, "dpc": dpc, "agente": agente, "diesel": diesel, **usuarios}


def _cliente(usuario) -> Client:
    c = Client()
    c.force_login(usuario)
    return c


# ---------------------------------------------------------------- permissões (perfis)
class TestPerfis:
    """Referência: gestor e operador mantêm os cadastros; diárias só o gestor; quem só
    consulta vê sem escrever."""

    def test_operador_cria_servidor_e_consulta_nao(self, base):
        dados = {"nome": "Paula Fictícia Andrade"}
        r = _cliente(base["operador"]).post(reverse("cadastros:salvar_servidor"), dados)
        assert r.status_code == 302
        assert Servidor.objects.filter(nome="Paula Fictícia Andrade").exists()
        r = _cliente(base["consulta"]).post(reverse("cadastros:salvar_servidor"),
                                            {"nome": "Outra Pessoa"})
        assert r.status_code == 403
        assert not Servidor.objects.filter(nome="Outra Pessoa").exists()

    def test_consulta_ve_a_lista_sem_acoes_de_escrita(self, base):
        Servidor.objects.create(nome="Carlos Fictício Lima")
        html = _cliente(base["consulta"]).get(reverse("cadastros:servidores")).content.decode()
        assert "Carlos Fictício Lima" in html
        assert "Novo servidor" not in html and "dialogo-servidor" not in html
        assert "Ações de Carlos" not in html  # sem menu de ações na linha

    def test_diarias_so_o_gestor_escreve(self, base):
        dados = {"faixa": "interior", "vigente_desde": "01/01/2027", "valor_24h": "300.00"}
        r = _cliente(base["operador"]).post(reverse("cadastros:salvar_vigencia"), dados)
        assert r.status_code == 403
        r = _cliente(base["gestor"]).post(reverse("cadastros:salvar_vigencia"), dados)
        assert r.status_code == 302
        assert TabelaDiaria.objects.filter(vigente_desde=date(2027, 1, 1)).exists()

    def test_operador_ve_diarias_sem_botao_de_nova(self, base):
        html = _cliente(base["operador"]).get(reverse("cadastros:diarias")).content.decode()
        assert "Nova vigência" not in html

    def test_indice_mostra_so_o_que_o_perfil_abre(self, base):
        html = _cliente(base["consulta"]).get(reverse("cadastros:indice")).content.decode()
        assert "Servidores" in html and "Cargos" in html
        assert "Tabela de diárias" not in html and "Configuração da unidade" not in html
        html = _cliente(base["gestor"]).get(reverse("cadastros:indice")).content.decode()
        assert "Tabela de diárias" in html and "Configuração da unidade" in html


# ---------------------------------------------------------------- servidores
class TestServidor:
    def test_so_o_nome_e_obrigatorio_e_o_cadastro_fica_incompleto(self, base):
        """Referência: "Só o nome é obrigatório"; o status sinaliza o que falta."""
        r = _cliente(base["operador"]).post(reverse("cadastros:salvar_servidor"),
                                            {"nome": "  Paula   Fictícia  "}, follow=True)
        s = Servidor.objects.get(nome="Paula Fictícia")  # espaços normalizados
        assert s.cargo is None and s.unidade is None and s.cpf == ""
        assert s.faltando == ["cargo", "CPF"] and not s.completo
        assert "cadastro incompleto: falta cargo e CPF" in r.content.decode()

    def test_cadastro_completo_normaliza_documentos(self, base):
        c = _cliente(base["operador"])
        c.post(reverse("cadastros:salvar_servidor"), {
            "nome": "Paula Fictícia", "cargo": base["agente"].pk, "cpf": CPF_VALIDO,
            "rg": "12.345.678-9", "telefone": "(41) 99999-0000",
            "unidade": base["ascom"].pk})
        s = Servidor.objects.get(nome="Paula Fictícia")
        assert (s.cpf, s.rg, s.telefone) == ("52998224725", "123456789", "41999990000")
        assert s.completo
        assert s.cpf_formatado == CPF_VALIDO and s.telefone_formatado == "(41) 99999-0000"
        assert s.rg_formatado == "12.345.678-9"

    def test_cpf_invalido_e_recusado_no_campo(self, base):
        r = _cliente(base["operador"]).post(reverse("cadastros:salvar_servidor"),
                                            {"nome": "Paula Fictícia", "cpf": "123.456.789-00"})
        assert r.status_code == 422
        assert "CPF inválido" in r.content.decode()
        assert not Servidor.objects.exists()

    def test_cpf_antigo_que_nao_confere_continua_editavel(self, base):
        """Dados DEMO têm CPF fictício que não confere: editar outro campo não trava."""
        s = Servidor.objects.create(nome="Paula Fictícia", cpf="90000791900")
        r = _cliente(base["operador"]).post(reverse("cadastros:salvar_servidor"), {
            "pk": s.pk, "nome": "Paula Fictícia", "cpf": "900.007.919-00",
            "telefone": "4130000000"})
        assert r.status_code == 302
        s.refresh_from_db()
        assert s.telefone == "4130000000" and s.cpf == "90000791900"

    @pytest.mark.parametrize("campo,valor,mensagem", [
        ("nome", "PAULA fictícia", "Já existe um servidor com este nome: Paula Fictícia."),
        ("cpf", CPF_VALIDO, "Já existe um servidor com este CPF: Paula Fictícia."),
        ("rg", "12345678-9", "Já existe um servidor com este RG: Paula Fictícia."),
        ("telefone", "(41) 3000-0000", "Já existe um servidor com este telefone: Paula Fictícia."),
    ])
    def test_unicidade_vira_mensagem_no_campo(self, base, campo, valor, mensagem):
        Servidor.objects.create(nome="Paula Fictícia", cpf="52998224725", rg="123456789",
                                telefone="4130000000")
        dados = {"nome": "Outra Pessoa", campo: valor}
        r = _cliente(base["operador"]).post(reverse("cadastros:salvar_servidor"), dados)
        assert r.status_code == 422
        assert mensagem in r.content.decode()

    def test_repetido_inativo_diz_onde_reativar(self, base):
        Servidor.objects.create(nome="Paula Fictícia", ativo=False)
        r = _cliente(base["operador"]).post(reverse("cadastros:salvar_servidor"),
                                            {"nome": "paula fictícia"})
        assert "inativo: reative-o na aba Inativos" in r.content.decode()

    def test_varios_servidores_sem_rg(self, base):
        """"Não possui RG" é uma marca, não um RG: não colide (referência)."""
        c = _cliente(base["operador"])
        for nome in ("Paula Fictícia", "Rui Fictício"):
            c.post(reverse("cadastros:salvar_servidor"), {"nome": nome, "rg": "não possui"})
        assert Servidor.objects.filter(rg=RG_NAO_POSSUI).count() == 2

    def test_cargo_padrao_vem_escolhido_no_novo(self, base):
        services.definir_padrao(base["gestor"], Cargo, base["agente"].pk)
        html = _cliente(base["operador"]).get(
            reverse("cadastros:servidores") + "?novo=1").content.decode()
        assert f'<option value="{base["agente"].pk}" selected>' in html

    def test_aba_incompletos_e_filtro_por_cargo_com_contagem(self, base):
        Servidor.objects.create(nome="Sem Cargo Fictício")
        Servidor.objects.create(nome="Completo Fictício", cargo=base["agente"],
                                cpf="52998224725")
        c = _cliente(base["consulta"])
        html = c.get(reverse("cadastros:servidores") + "?aba=incompletos").content.decode()
        assert "Sem Cargo Fictício" in html and "Completo Fictício" not in html
        html = c.get(reverse("cadastros:servidores")).content.decode()
        assert "Todos (2)" in html and f"{base['agente'].nome} (1)" in html
        html = c.get(reverse("cadastros:servidores") + f"?cargo={base['agente'].pk}").content \
            .decode()
        assert "Completo Fictício" in html and "Sem Cargo Fictício" not in html

    def test_busca_sem_acento_por_cargo_e_unidade(self, base):
        Servidor.objects.create(nome="Paula Fictícia", cargo=base["agente"],
                                unidade=base["dpc"])
        c = _cliente(base["consulta"])
        assert "Paula Fictícia" in c.get(reverse("cadastros:servidores") + "?q=judiciaria") \
            .content.decode()
        assert "Paula Fictícia" in c.get(reverse("cadastros:servidores") + "?q=dpc") \
            .content.decode()

    def test_editar_abre_a_janela_preenchida(self, base):
        s = Servidor.objects.create(nome="Paula Fictícia", cpf="52998224725")
        html = _cliente(base["operador"]).get(
            reverse("cadastros:servidores") + f"?editar={s.pk}").content.decode()
        assert "data-abrir-ao-carregar" in html and CPF_VALIDO in html
        assert f'name="pk" value="{s.pk}"' in html

    def test_busca_de_servidores_para_escolha(self, base):
        Servidor.objects.create(nome="Paula Fictícia", cargo=base["agente"],
                                unidade=base["ascom"])
        Servidor.objects.create(nome="Paula Inativa", ativo=False)
        dados = _cliente(base["consulta"]).get(
            reverse("cadastros:buscar_servidores") + "?q=paula").json()
        assert [r["titulo"] for r in dados["resultados"]] == ["Paula Fictícia"]
        assert dados["resultados"][0]["meta"] == "Agente de Polícia Judiciária · ASCOM"


# ---------------------------------------------------------------- viaturas
class TestViatura:
    def test_so_a_placa_e_obrigatoria(self, base):
        r = _cliente(base["operador"]).post(reverse("cadastros:salvar_viatura"),
                                            {"placa": "zzt-1a23"}, follow=True)
        v = Viatura.objects.get(placa="ZZT1A23")
        assert v.faltando == ["modelo", "combustível", "tipo"]
        assert "cadastro incompleto" in r.content.decode()

    @pytest.mark.parametrize("placa", ["ABC12345", "1BC1234", "ABCD123"])
    def test_placa_invalida(self, base, placa):
        r = _cliente(base["operador"]).post(reverse("cadastros:salvar_viatura"),
                                            {"placa": placa})
        assert r.status_code == 422 and "Placa inválida" in r.content.decode()

    def test_placa_repetida(self, base):
        Viatura.objects.create(placa="ABC1234")
        r = _cliente(base["operador"]).post(reverse("cadastros:salvar_viatura"),
                                            {"placa": "abc-1234"})
        assert r.status_code == 422 and "Já existe uma viatura" in r.content.decode()

    def test_motoristas_e_padroes_da_viatura_nova(self, base):
        services.definir_padrao(base["gestor"], Combustivel, base["diesel"].pk)
        c = _cliente(base["operador"])
        html = c.get(reverse("cadastros:viaturas") + "?novo=1").content.decode()
        assert f'<option value="{base["diesel"].pk}" selected>' in html
        assert '<option value="descaracterizada" selected>' in html
        a = Servidor.objects.create(nome="Paula Fictícia")
        b = Servidor.objects.create(nome="Rui Fictício")
        c.post(reverse("cadastros:salvar_viatura"), {
            "placa": "ABC1D23", "modelo": "Renault Master", "tipo": "caracterizada",
            "combustivel": base["diesel"].pk, "unidade": base["ascom"].pk,
            "motoristas": [a.pk, b.pk]})
        v = Viatura.objects.get(placa="ABC1D23")
        assert v.completo and set(v.motoristas.all()) == {a, b}
        # Na edição, os escolhidos voltam desenhados (só eles, com o nome).
        html = c.get(reverse("cadastros:viaturas") + f"?editar={v.pk}").content.decode()
        assert f'name="motoristas" value="{a.pk}"' in html and "Rui Fictício" in html
        c.post(reverse("cadastros:salvar_viatura"), {"pk": v.pk, "placa": "ABC1D23",
                                                     "motoristas": [b.pk]})
        assert list(v.motoristas.all()) == [b]

    def test_filtro_por_combustivel_conta_tambem_as_sem_combustivel(self, base):
        Viatura.objects.create(placa="ABC1234", combustivel=base["diesel"])
        Viatura.objects.create(placa="ABC1235")
        html = _cliente(base["consulta"]).get(reverse("cadastros:viaturas")).content.decode()
        assert "Todos (2)" in html and "Diesel (1)" in html


# ---------------------------------------------------------------- catálogos simples
class TestCatalogos:
    def test_criar_cargo_e_repetido_sem_diferenciar_caixa(self, base):
        c = _cliente(base["operador"])
        r = c.post(reverse("cadastros:salvar_catalogo", args=["cargos"]),
                   {"nome": "Papiloscopista"})
        assert r.status_code == 302 and Cargo.objects.filter(nome="Papiloscopista").exists()
        r = c.post(reverse("cadastros:salvar_catalogo", args=["cargos"]),
                   {"nome": "PAPILOSCOPISTA"})
        assert r.status_code == 422 and "Já existe um cargo" in r.content.decode()

    def test_um_padrao_por_cadastro(self, base):
        outro = Cargo.objects.get(nome="Escrivão de Polícia")
        services.definir_padrao(base["gestor"], Cargo, base["agente"].pk)
        services.definir_padrao(base["gestor"], Cargo, outro.pk)
        assert list(Cargo.objects.filter(padrao=True)) == [outro]

    def test_editar_o_nome_preserva_o_padrao(self, base):
        """Referência P05: editar só o nome não desmarca o padrão."""
        services.definir_padrao(base["gestor"], Cargo, base["agente"].pk)
        _cliente(base["operador"]).post(reverse("cadastros:salvar_catalogo", args=["cargos"]),
                                        {"pk": base["agente"].pk, "nome": "Agente (APJ)"})
        base["agente"].refresh_from_db()
        assert base["agente"].nome == "Agente (APJ)" and base["agente"].padrao

    def test_desativar_o_padrao_tira_o_padrao_e_inativo_nao_vira_padrao(self, base):
        services.definir_padrao(base["gestor"], Cargo, base["agente"].pk)
        services.alternar_ativo(base["gestor"], Cargo, base["agente"].pk)
        base["agente"].refresh_from_db()
        assert not base["agente"].ativo and not base["agente"].padrao
        with pytest.raises(services.CadastroInvalido, match="inativo"):
            services.definir_padrao(base["gestor"], Cargo, base["agente"].pk)

    def test_unidade_com_sigla_opcional_e_busca_por_sigla(self, base):
        c = _cliente(base["operador"])
        c.post(reverse("cadastros:salvar_catalogo", args=["unidades"]),
               {"nome": "Núcleo de Apoio Fictício", "sigla": "  nuaf "})
        u = Unidade.objects.get(nome="Núcleo de Apoio Fictício")
        assert u.sigla == "NUAF"
        html = c.get(reverse("cadastros:unidades") + "?q=nuaf").content.decode()
        assert "Núcleo de Apoio Fictício" in html

    def test_lista_mostra_quanto_cada_um_e_usado(self, base):
        Servidor.objects.create(nome="Paula Fictícia", cargo=base["agente"])
        html = _cliente(base["consulta"]).get(reverse("cadastros:cargos")).content.decode()
        assert "1 servidor" in html and "Ainda não usado" in html

    def test_aba_inativos(self, base):
        services.alternar_ativo(base["gestor"], Combustivel, base["diesel"].pk)
        c = _cliente(base["consulta"])
        assert "Diesel" not in c.get(reverse("cadastros:combustiveis")).content.decode()
        assert "Diesel" in c.get(reverse("cadastros:combustiveis") + "?aba=inativos") \
            .content.decode()

    def test_cadastro_desconhecido_e_404(self, base):
        r = _cliente(base["gestor"]).post(reverse("cadastros:salvar_catalogo",
                                                  args=["viagens"]), {"nome": "x"})
        assert r.status_code == 404


# ---------------------------------------------------------------- excluir e desativar
class TestExcluir:
    def test_sem_vinculos_exclui(self, base):
        s = Servidor.objects.create(nome="Paula Fictícia")
        r = _cliente(base["operador"]).post(
            reverse("cadastros:excluir", args=["servidores", s.pk]), follow=True)
        assert not Servidor.objects.filter(pk=s.pk).exists()
        assert "excluído" in r.content.decode()

    def test_com_vinculos_recusa_e_diz_quais(self, base):
        Servidor.objects.create(nome="Paula Fictícia", cargo=base["agente"])
        r = _cliente(base["operador"]).post(
            reverse("cadastros:excluir", args=["cargos", base["agente"].pk]), follow=True)
        assert Cargo.objects.filter(pk=base["agente"].pk).exists()
        html = r.content.decode()
        assert "Não é possível excluir" in html and "1 servidor" in html and "Desative" in html

    def test_unidade_com_lotacao_de_usuario_nao_se_exclui(self, base):
        assert services.vinculos(base["ascom"])  # a lotação dos usuários protege
        with pytest.raises(services.CadastroInvalido):
            services.excluir(base["gestor"], Unidade, base["ascom"].pk)

    def test_consulta_nao_exclui(self, base):
        s = Servidor.objects.create(nome="Paula Fictícia")
        r = _cliente(base["consulta"]).post(
            reverse("cadastros:excluir", args=["servidores", s.pk]), follow=True)
        assert Servidor.objects.filter(pk=s.pk).exists()
        assert "Você não pode excluir" in r.content.decode()

    def test_get_nao_exclui(self, base):
        s = Servidor.objects.create(nome="Paula Fictícia")
        r = _cliente(base["gestor"]).get(reverse("cadastros:excluir", args=["servidores", s.pk]))
        assert r.status_code == 405 and Servidor.objects.filter(pk=s.pk).exists()

    def test_desativado_sai_da_busca_de_escolha(self, base):
        s = Servidor.objects.create(nome="Paula Fictícia")
        _cliente(base["operador"]).post(reverse("cadastros:alternar_ativo",
                                                args=["servidores", s.pk]))
        s.refresh_from_db()
        assert not s.ativo
        dados = _cliente(base["operador"]).get(
            reverse("cadastros:buscar_servidores") + "?q=paula").json()
        assert dados["resultados"] == []

    def test_voltar_so_para_a_mesma_lista(self, base):
        s = Servidor.objects.create(nome="Paula Fictícia")
        c = _cliente(base["operador"])
        r = c.post(reverse("cadastros:alternar_ativo", args=["servidores", s.pk]),
                   {"voltar": "https://exemplo.invalido/cadastros/servidores/"})
        assert r["Location"] == reverse("cadastros:servidores")
        r = c.post(reverse("cadastros:alternar_ativo", args=["servidores", s.pk]),
                   {"voltar": reverse("cadastros:servidores") + "?aba=inativos&q=paula"})
        assert r["Location"] == reverse("cadastros:servidores") + "?aba=inativos&q=paula"


# ---------------------------------------------------------------- tabela de diárias
class TestDiarias:
    def _vigencia(self, gestor, **extra):
        dados = {"faixa": "interior", "vigente_desde": "01/01/2027", "valor_24h": "300.00",
                 **extra}
        return _cliente(gestor).post(reverse("cadastros:salvar_vigencia"), dados)

    def test_valor_minimo_quatro_centavos(self, base):
        """Referência P08: abaixo de R$ 0,04 os 15% arredondam para zero."""
        r = self._vigencia(base["gestor"], valor_24h="0.03")
        assert r.status_code == 422 and "15% ficaria zerado" in r.content.decode()
        assert self._vigencia(base["gestor"], valor_24h="0.04").status_code == 302

    def test_mesma_faixa_e_data_nao_repete(self, base):
        self._vigencia(base["gestor"])
        r = self._vigencia(base["gestor"], valor_24h="310.00")
        assert r.status_code == 422 and "Já existe uma vigência" in r.content.decode()

    def test_lista_mostra_percentuais_derivados(self, base):
        TabelaDiaria.objects.create(faixa="interior", vigente_desde=date(2026, 1, 1),
                                    valor_24h=Decimal("290.55"))
        html = _cliente(base["gestor"]).get(reverse("cadastros:diarias")).content.decode()
        assert "43,58" in html and "87,17" in html  # 15% e 30% arredondados ao centavo

    def test_nao_exclui_a_unica_vigencia_da_faixa(self, base):
        v = TabelaDiaria.objects.create(faixa="capital", vigente_desde=date(2026, 1, 1),
                                        valor_24h=Decimal("371.26"))
        with pytest.raises(services.CadastroInvalido, match="única vigência"):
            services.excluir_vigencia(base["gestor"], v.pk)
        TabelaDiaria.objects.create(faixa="capital", vigente_desde=date(2027, 1, 1),
                                    valor_24h=Decimal("400.00"))
        services.excluir_vigencia(base["gestor"], v.pk)
        assert not TabelaDiaria.objects.filter(pk=v.pk).exists()

    def test_operador_nao_exclui_vigencia(self, base):
        v = TabelaDiaria.objects.create(faixa="capital", vigente_desde=date(2026, 1, 1),
                                        valor_24h=Decimal("371.26"))
        with pytest.raises(PermissionDenied):
            services.excluir_vigencia(base["operador"], v.pk)


# ---------------------------------------------------------------- configuração da unidade
class TestConfiguracao:
    @pytest.fixture
    def dados(self):
        garantir_municipios()
        return {
            "nome_extenso": "Assessoria de Comunicação Social", "sede": "Curitiba/PR",
            "endereco_rodape": "Rua Fictícia, 100 - Curitiba/PR",
            "chefia_nome": "Chefe Fictício", "chefia_cargo": "Chefe da Assessoria",
            "destinatario_tratamento": "Exmo. Sr", "destinatario_nome": "Destinatário Fictício",
            "destinatario_cargo": "Delegado-Geral Adjunto", "destinatario_orgao": "Gabinete",
            "destinatario_cidade": "CURITIBA – Pr.", "prazo_justificativa_dias": "10",
        }

    def test_gestor_salva_a_configuracao_da_unidade(self, base, dados):
        r = _cliente(base["gestor"]).post(reverse("cadastros:configuracao") +
                                          f"?unidade={base['dpc'].pk}", dados)
        assert r.status_code == 302
        config = ConfiguracaoInstitucional.objects.get(unidade=base["dpc"])
        assert config.sede == Municipio.objects.get(nome="Curitiba", uf="PR")
        assert config.chefia_nome == "Chefe Fictício"

    def test_operador_ve_sem_poder_alterar(self, base, dados):
        c = _cliente(base["operador"])
        html = c.get(reverse("cadastros:configuracao")).content.decode()
        assert "Salvar configuração" not in html and "disabled" in html
        assert c.post(reverse("cadastros:configuracao"), dados).status_code == 403

    def test_cidade_inexistente_volta_com_erro(self, base, dados):
        dados["sede"] = "Cidade Que Não Existe/PR"
        r = _cliente(base["gestor"]).post(reverse("cadastros:configuracao"), dados)
        assert r.status_code == 422 and "lista oficial de municípios" in r.content.decode()

    def test_consulta_sem_permissao(self, base):
        assert _cliente(base["consulta"]).get(
            reverse("cadastros:configuracao")).status_code == 403


# ---------------------------------------------------------------- desempenho
class TestConsultasPorTela:
    """O número de consultas não cresce com as linhas (sem N+1)."""

    @pytest.mark.parametrize("rota", ["cadastros:servidores", "cadastros:viaturas",
                                      "cadastros:unidades", "cadastros:cargos",
                                      "cadastros:diarias", "cadastros:indice"])
    def test_lista_nao_cresce_com_os_registros(self, base, rota):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        c = _cliente(base["gestor"])

        def contar() -> int:
            with CaptureQueriesContext(connection) as ctx:
                assert c.get(reverse(rota)).status_code == 200
            return len(ctx.captured_queries)

        def criar(de: int, ate: int) -> None:
            for i in range(de, ate):
                s = Servidor.objects.create(nome=f"Pessoa Fictícia {i:02d}",
                                            cargo=base["agente"], unidade=base["ascom"])
                v = Viatura.objects.create(placa=f"ZZA{i % 10}A{i:02d}",
                                           combustivel=base["diesel"], unidade=base["ascom"])
                v.motoristas.add(s)

        criar(0, 3)
        poucos = contar()
        criar(3, 40)  # mais que uma página
        assert contar() == poucos
        assert poucos <= 20


# ---------------------------------------------------------------- achados das revisões
class TestRevisoes:
    def test_gestor_sem_ver_todas_so_configura_a_propria_unidade(self, base):
        """Segurança M1: a política decide por unidade."""
        from django.contrib.auth.models import Permission

        local = Usuario.objects.create_user("local", "local@pc.pr.gov.br", "senha-local-123",
                                            nome="Gestor Local")
        local.user_permissions.add(*Permission.objects.filter(codename__in=[
            "view_configuracaoinstitucional", "change_configuracaoinstitucional"]))
        Lotacao.objects.create(usuario=local, unidade=base["ascom"])
        c = _cliente(local)
        assert c.get(reverse("cadastros:configuracao") +
                     f"?unidade={base['dpc'].pk}").status_code == 404
        assert c.get(reverse("cadastros:configuracao")).status_code == 200

    @pytest.mark.parametrize("url", ["cadastros:servidores", "cadastros:viaturas"])
    def test_parametro_numerico_estranho_nao_derruba(self, base, url):
        """Segurança B1: "²".isdigit() é True, int("²") estoura."""
        c = _cliente(base["gestor"])
        assert c.get(reverse(url) + "?cargo=%C2%B2&combustivel=%C2%B2&editar=%C2%B2") \
            .status_code == 200
        r = c.post(reverse("cadastros:salvar_servidor"), {"pk": "²", "nome": "X"})
        assert r.status_code == 404

    def test_documentos_so_com_digitos_ascii(self, base):
        """Segurança B2."""
        from gestao.cadastros.validacoes import normalizar_rg, somente_digitos
        assert somente_digitos("١٢٣-45") == "45"
        assert normalizar_rg("çã-12/Ω") == "CA12"

    def test_motorista_inativo_nao_entra_por_post_forjado(self, base):
        """Segurança B5."""
        inativo = Servidor.objects.create(nome="Inativo Fictício", ativo=False)
        r = _cliente(base["operador"]).post(reverse("cadastros:salvar_viatura"), {
            "placa": "ABC1234", "motoristas": [inativo.pk]})
        assert r.status_code == 422 and not Viatura.objects.filter(placa="ABC1234").exists()

    def test_excluir_servidor_avisa_que_saiu_das_viaturas(self, base):
        """Segurança B4: o vínculo de motorista habitual não protege, mas é dito."""
        s = Servidor.objects.create(nome="Paula Fictícia")
        Viatura.objects.create(placa="ABC1234").motoristas.add(s)
        nome = services.excluir(base["gestor"], Servidor, s.pk)
        assert "deixou de ser motorista habitual de 1 viatura" in nome

    def test_incluir_outro_volta_com_a_janela_de_novo(self, base):
        r = _cliente(base["operador"]).post(reverse("cadastros:salvar_servidor"), {
            "nome": "Paula Fictícia", "outro": "1",
            "voltar": reverse("cadastros:servidores") + "?q=pa&"})
        assert r["Location"].endswith("novo=1") and "q=pa" in r["Location"]

    def test_sem_rg_e_excluir_so_sem_uso(self, base):
        Servidor.objects.create(nome="Paula Fictícia", rg=RG_NAO_POSSUI, cargo=base["agente"])
        html = _cliente(base["gestor"]).get(reverse("cadastros:servidores")).content.decode()
        assert "Sem RG" in html and "RG NÃO POSSUI" not in html
        html = _cliente(base["gestor"]).get(reverse("cadastros:cargos")).content.decode()
        # O cargo usado não oferece "Excluir"; o que não é usado, oferece.
        usado = Cargo.objects.get(pk=base["agente"].pk)
        livre = Cargo.objects.get(nome="Escrivão de Polícia")
        assert f'id="excluir-{usado.pk}"' not in html and f'id="excluir-{livre.pk}"' in html

    def test_entrada_mostra_pendencias(self, base):
        Servidor.objects.create(nome="Paula Fictícia")
        html = _cliente(base["gestor"]).get(reverse("cadastros:indice")).content.decode()
        assert "1 incompleto" in html and "?aba=incompletos" in html
        assert "sem configuração" in html  # as unidades do cenário não têm configuração

    def test_vigencia_vigente_marcada(self, base):
        TabelaDiaria.objects.create(faixa="interior", vigente_desde=date(2020, 1, 1),
                                    valor_24h=Decimal("200.00"))
        TabelaDiaria.objects.create(faixa="interior", vigente_desde=date(2024, 1, 1),
                                    valor_24h=Decimal("290.55"))
        TabelaDiaria.objects.create(faixa="interior", vigente_desde=date(2099, 1, 1),
                                    valor_24h=Decimal("999.00"))
        html = _cliente(base["gestor"]).get(reverse("cadastros:diarias")).content.decode()
        assert html.count(">Vigente</span>") == 1
