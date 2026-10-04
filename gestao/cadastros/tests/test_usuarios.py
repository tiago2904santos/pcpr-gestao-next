"""Usuários do sistema (paridade com a gestão de usuários da referência) e troca de senha
obrigatória no primeiro acesso."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import Lotacao, Unidade
from gestao.identidade.models import Usuario
from gestao.viagens.tests.cenarios import cenario_completo

pytestmark = pytest.mark.django_db
SENHA = "Senha-Forte-2026!"


@pytest.fixture
def c():
    cen = cenario_completo()
    admin = Usuario.objects.create_user("admin", "admin@pc.pr.gov.br", SENHA, nome="Admin Teste")
    admin.groups.add(Group.objects.get(name="ADMINISTRADOR"))
    cen.usuarios["admin"] = admin
    return cen


def _cliente(usuario) -> Client:
    cli = Client()
    cli.force_login(usuario)
    return cli


def _dados(**extra) -> dict:
    return {"nome": "Fulana de Teste", "login": "fulana", "email": "fulana@pc.pr.gov.br",
            "papeis": ["OPERADOR_VIAGENS"], "senha": SENHA, "confirmacao": SENHA, **extra}


def test_so_administrador_ve_e_gerencia(c):
    url = reverse("cadastros:usuarios")
    assert _cliente(c.usuarios["operador"]).get(url).status_code == 403
    assert _cliente(c.usuarios["gestor"]).get(url).status_code == 403
    html = _cliente(c.usuarios["admin"]).get(url).content.decode()
    assert "Usuários e perfis" in html and "Operador de Testes" in html


def test_criar_com_perfil_lotacao_e_troca_obrigatoria(c):
    ascom = Unidade.objects.get(sigla="ASCOM")
    r = _cliente(c.usuarios["admin"]).post(reverse("cadastros:salvar_usuario"),
                                           _dados(unidade=ascom.pk), follow=True)
    assert "Usuário “fulana” criado." in r.content.decode()
    novo = Usuario.objects.get(login="fulana")
    assert novo.deve_trocar_senha and novo.check_password(SENHA)
    assert list(novo.groups.values_list("name", flat=True)) == ["OPERADOR_VIAGENS"]
    assert Lotacao.objects.get(usuario=novo).unidade == ascom and novo.unidade_sigla == "ASCOM"


@pytest.mark.parametrize(("extra", "mensagem"), [
    ({"senha": "", "confirmacao": ""}, "Defina a senha inicial do usuário."),
    ({"confirmacao": "outra-coisa-123"}, "As senhas não conferem."),
    ({"senha": "123", "confirmacao": "123"}, "muito curta"),
    ({"login": "operador"}, "Já existe um usuário com este login."),
    ({"email": "fulana@gmail.com"}, "Use o e-mail institucional (@pc.pr.gov.br)."),
    ({"login": "com espaço"}, "sem espaços"),
])
def test_validacoes(c, extra, mensagem):
    r = _cliente(c.usuarios["admin"]).post(reverse("cadastros:salvar_usuario"), _dados(**extra))
    assert r.status_code == 422 and mensagem in r.content.decode()
    assert not Usuario.objects.filter(login="fulana").exists()


def test_editar_sem_trocar_senha_e_redefinir(c):
    op = c.usuarios["operador"]
    cli = _cliente(c.usuarios["admin"])
    base = {"pk": op.pk, "nome": "Operador Renomeado", "login": op.login, "email": op.email,
            "papeis": ["GESTOR_VIAGENS"], "senha": "", "confirmacao": ""}
    cli.post(reverse("cadastros:salvar_usuario"), base)
    op.refresh_from_db()
    assert op.nome == "Operador Renomeado" and not op.deve_trocar_senha
    assert list(op.groups.values_list("name", flat=True)) == ["GESTOR_VIAGENS"]
    assert not Lotacao.objects.filter(usuario=op).exists()  # sem unidade: sem lotação
    cli.post(reverse("cadastros:salvar_usuario"), {**base, "senha": SENHA, "confirmacao": SENHA})
    op.refresh_from_db()
    assert op.deve_trocar_senha and op.check_password(SENHA)


def test_nao_inativa_a_si_mesmo_nem_tira_o_proprio_admin(c):
    admin = c.usuarios["admin"]
    cli = _cliente(admin)
    r = cli.post(reverse("cadastros:alternar_ativo_usuario", args=[admin.pk]), follow=True)
    assert "Você não pode inativar o seu próprio usuário." in r.content.decode()
    r = cli.post(reverse("cadastros:salvar_usuario"),
                 {"pk": admin.pk, "nome": admin.nome, "login": admin.login, "email": admin.email,
                  "papeis": ["CONSULTA"]})
    assert "Você não pode tirar o seu próprio perfil de administrador." in r.content.decode()
    admin.refresh_from_db()
    assert admin.is_active and admin.groups.filter(name="ADMINISTRADOR").exists()


def test_inativar_e_ativar(c):
    op = c.usuarios["operador"]
    cli = _cliente(c.usuarios["admin"])
    cli.post(reverse("cadastros:alternar_ativo_usuario", args=[op.pk]))
    op.refresh_from_db()
    assert not op.is_active
    html = cli.get(reverse("cadastros:usuarios") + "?aba=inativos").content.decode()
    assert "Operador de Testes" in html
    cli.post(reverse("cadastros:alternar_ativo_usuario", args=[op.pk]))
    op.refresh_from_db()
    assert op.is_active


def test_admin_comum_nao_mexe_em_superusuario(c):
    sup = Usuario.objects.create_superuser("raiz", "raiz@pc.pr.gov.br", SENHA, nome="Raiz")
    cli = _cliente(c.usuarios["admin"])
    r = cli.post(reverse("cadastros:alternar_ativo_usuario", args=[sup.pk]), follow=True)
    assert "Você não pode alterar este usuário." in r.content.decode()
    r = cli.post(reverse("cadastros:salvar_usuario"),
                 {"pk": sup.pk, "nome": "x", "login": "raiz", "email": sup.email})
    assert r.status_code == 403


def test_busca_e_filtro_por_perfil(c):
    cli = _cliente(c.usuarios["admin"])
    html = cli.get(reverse("cadastros:usuarios"), {"q": "dpc"}).content.decode()
    assert "Operadora da DPC" in html and "Operador de Testes" not in html
    html = cli.get(reverse("cadastros:usuarios"), {"perfil": "CONSULTA"}).content.decode()
    assert "Usuário de Consulta" in html and "Operador de Testes" not in html


def test_troca_de_senha_obrigatoria(c):
    op = c.usuarios["operador"]
    Usuario.objects.filter(pk=op.pk).update(deve_trocar_senha=True)
    cli = Client()
    cli.login(username="operador", password="senha-local-123")
    r = cli.get(reverse("viagens:oficios"), follow=True)
    html = r.content.decode()
    assert r.redirect_chain[-1][0] == reverse("identidade:alterar_senha")
    assert "Defina sua senha" in html and "Defina uma senha só sua para continuar" in html
    assert f'href="{reverse("painel:inicio")}">Cancelar' not in html  # sem saída pela tangente
    nova = "Nova-Senha-Minha-2026"
    r = cli.post(reverse("identidade:alterar_senha"),
                 {"old_password": "senha-local-123", "new_password1": nova,
                  "new_password2": nova})
    assert r.status_code == 302
    assert cli.get(reverse("viagens:oficios")).status_code == 200
    op.refresh_from_db()
    assert not op.deve_trocar_senha
