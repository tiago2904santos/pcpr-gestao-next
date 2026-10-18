"""Etapa de cadastros com bancos legados FALSOS (só dados sintéticos, nenhum valor real)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from django.contrib.auth.hashers import make_password

from gestao.cadastros.models import Lotacao, Servidor, Unidade
from gestao.eventos.models import Equipe
from gestao.identidade.models import Usuario
from gestao.migracao.contexto import Contexto, Relatorio
from gestao.migracao.etapas import cadastros
from gestao.migracao.models import MapaLegado

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class FonteFalsa:
    """Imita `Fonte` com tabelas em memória."""

    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas

    def tabela(self, nome: str) -> list[dict]:
        return [dict(r) for r in self.tabelas.get(nome, [])]

    def tem_tabela(self, nome: str) -> bool:
        return nome in self.tabelas


def usuario_legado(pk: int, login: str, email: str, senha: str, *, ultimo: datetime | None,
                   superusuario: bool = False, **extra) -> dict:
    return {"id": pk, "username": login, "email": email, "password": senha,
            "first_name": extra.pop("first_name", ""), "last_name": "",
            "is_superuser": superusuario, "is_staff": superusuario, "is_active": True,
            "last_login": ultimo, "date_joined": T0, **extra}


def unidade(pk: int, sigla: str) -> dict:
    return {"id": pk, "nome": f"Unidade sintética {sigla}", "sigla": sigla,
            "criado_em": T0, "atualizado_em": T0, "created_at": T0, "updated_at": T0}


def rodar(ev: dict, gv: dict | None = None) -> Relatorio:
    ctx = Contexto(ev=FonteFalsa(ev), gv=FonteFalsa(gv) if gv is not None else None,
                   lote="teste", relatorio=Relatorio())
    cadastros.executar(ctx)
    return ctx.relatorio


def legados_usuarios(senha_ev: str, senha_gv: str, *, ev_mais_recente: bool) -> tuple[dict, dict]:
    recente, antigo = datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC)
    ev = {
        "viagens_cadastros_unidade": [unidade(10, "XPTO")],
        "accounts_user": [usuario_legado(
            1, "pessoa.teste", "pessoa@exemplo.test", senha_ev, superusuario=True,
            ultimo=recente if ev_mais_recente else antigo, deve_trocar_senha=False)],
    }
    gv = {
        "cadastros_unidade": [unidade(20, "XPTO")],
        "auth_user": [usuario_legado(5, "PESSOA.TESTE", "", senha_gv,
                                     ultimo=antigo if ev_mais_recente else recente,
                                     first_name="Pessoa Sintética")],
        "usuarios_areatrabalho": [{"id": 1, "sigla": "XPTO"}],
        "usuarios_vinculousuarioarea": [{"id": 1, "usuario_id": 5, "area_id": 1,
                                         "papel": "EDITOR", "area_padrao": True,
                                         "ativo": True}],
    }
    ev["migracao_legado_registro"] = [{"tabela": "cadastros_unidade", "origem_pk": "20",
                                       "destino_pk": "10"}]
    return ev, gv


def legados() -> list[Usuario]:
    return list(Usuario.objects.exclude(login=cadastros.LOGIN_MIGRACAO))


def test_mesma_pessoa_nos_dois_sistemas_vira_um_usuario_com_o_hash_copiado():
    hash_ev, hash_gv = make_password("sintetica-ev-123"), make_password("sintetica-gv-123")
    ev, gv = legados_usuarios(hash_ev, hash_gv, ev_mais_recente=True)

    rodar(ev, gv)

    [usuario] = legados()
    assert usuario.password == hash_ev            # copiado como está, sem set_password
    assert usuario.check_password("sintetica-ev-123")
    assert usuario.login == "pessoa.teste"        # o login do EV
    assert usuario.nome == "Pessoa Sintética"     # o nome que só o GV tinha
    assert usuario.is_superuser                   # superusuário vem do EV
    assert set(usuario.groups.values_list("name", flat=True)) == {"OPERADOR_VIAGENS"}
    assert Lotacao.objects.get(usuario=usuario).unidade.sigla == "XPTO"
    alvos = set(MapaLegado.objects.filter(tabela__in=["accounts_user", "auth_user"])
                .values_list("destino_pk", flat=True))
    assert alvos == {str(usuario.pk)}


def test_a_senha_vem_do_sistema_com_o_login_mais_recente():
    hash_ev, hash_gv = make_password("sintetica-ev-123"), make_password("sintetica-gv-123")
    ev, gv = legados_usuarios(hash_ev, hash_gv, ev_mais_recente=False)

    relatorio = rodar(ev, gv)

    [usuario] = legados()
    assert usuario.password == hash_gv
    assert usuario.is_superuser                   # mesmo com a senha do GV
    assert any("senhas diferentes" in c["motivo"] for c in relatorio.conferir)


def test_senha_inutilizavel_no_mais_recente_usa_a_do_outro_sistema():
    hash_gv = make_password("sintetica-gv-123")
    ev, gv = legados_usuarios("!marcador-sem-senha", hash_gv, ev_mais_recente=True)

    rodar(ev, gv)

    [usuario] = legados()
    assert usuario.password == hash_gv
    assert not usuario.deve_trocar_senha


def test_usuario_so_do_gv_sem_email_e_admin_superusuario():
    gv = {"auth_user": [usuario_legado(9, "so.gv", "", make_password("sintetica-123"),
                                       ultimo=None, superusuario=True)],
          "usuarios_areatrabalho": [{"id": 1, "sigla": "SEM-UNIDADE"}],
          "usuarios_vinculousuarioarea": [{"id": 1, "usuario_id": 9, "area_id": 1,
                                           "papel": "ADMIN", "area_padrao": True,
                                           "ativo": True}]}

    relatorio = rodar({}, gv)

    [usuario] = legados()
    assert usuario.email == f"so.gv@{cadastros.DOMINIO_PROVISORIO}"
    assert usuario.nome == "so.gv"
    assert usuario.is_superuser
    assert set(usuario.groups.values_list("name", flat=True)) == {"GESTOR_VIAGENS",
                                                                  "ADMINISTRADOR"}
    motivos = " | ".join(c["motivo"] for c in relatorio.conferir)
    assert "endereço provisório" in motivos and "sem lotação" in motivos


def test_usuario_tecnico_inativo_e_sem_senha():
    ctx = Contexto(ev=FonteFalsa({}), gv=None, lote="teste",
                   relatorio=Relatorio())
    cadastros.executar(ctx)

    tecnico = Usuario.objects.get(login=cadastros.LOGIN_MIGRACAO)
    assert ctx.usuario_migracao == tecnico
    assert not tecnico.is_active and not tecnico.has_usable_password()


def test_rodar_duas_vezes_nao_cria_nada_novo():
    ev, gv = legados_usuarios(make_password("sintetica-ev-123"),
                              make_password("sintetica-gv-123"), ev_mais_recente=True)
    ev["viagens_cadastros_cargo"] = [{"id": 1, "nome": "Cargo sintético", "is_padrao": True,
                                      "criado_em": T0, "atualizado_em": T0}]
    ev["viagens_cadastros_servidor"] = [
        {"id": 3, "nome": "SERVIDOR SINTÉTICO", "cpf": "", "rg": "", "sem_rg": True,
         "telefone": "41900000000", "cargo_id": 1, "unidade_id": 10, "criado_em": T0,
         "atualizado_em": T0}]
    gv["cadastros_servidor"] = [
        {"id": 7, "nome": "SERVIDOR SINTÉTICO", "cpf": "", "rg": "", "sem_rg": True,
         "telefone": "41900000000", "cargo_id": None, "unidade_id": 20, "created_at": T0,
         "updated_at": T0}]
    ev["migracao_legado_registro"].append({"tabela": "cadastros_servidor", "origem_pk": "7",
                                           "destino_pk": "3"})
    ev["cadastros_equipe"] = [{"id": 1, "nome": "Equipe sintética", "ativo": True,
                               "criado_em": T0, "atualizado_em": T0}]
    sementes = set(Equipe.objects.values_list("pk", flat=True))

    primeira = rodar(ev, gv)
    contagem = {m: m.objects.count() for m in (Usuario, Servidor, Unidade, Equipe, MapaLegado)}
    segunda = rodar(ev, gv)

    # O GV tem o mesmo servidor sem cargo e não é mais recente: vale o EV, o GV vai à conferência.
    assert primeira.contagens["servidor"] == {"criado": 1, "mapeado_pelo_registro_ev": 1,
                                              "editado_nos_dois": 1}
    assert {m: m.objects.count() for m in contagem} == contagem
    assert not any("criado" in n for n in segunda.contagens.values())
    servidor = Servidor.objects.get()
    assert servidor.criado_em == T0                    # data do legado preservada
    assert servidor.cargo is not None and servidor.unidade is not None
    # Semente sem correspondente no legado: inativada, nunca apagada.
    assert set(Equipe.objects.filter(pk__in=sementes).values_list("ativo", flat=True)) <= {
        False}
    assert Equipe.objects.filter(pk__in=sementes).count() == len(sementes)
