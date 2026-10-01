"""A trilha de auditoria é garantida pelo banco, não pela aplicação."""

from __future__ import annotations

import pytest
from django.db import DatabaseError, connection, transaction

from gestao.identidade.models import Usuario
from gestao.plataforma import auditoria
from gestao.plataforma.models import EventoAuditoria

pytestmark = pytest.mark.django_db(transaction=True)


def _eventos(tabela: str):
    return EventoAuditoria.objects.filter(tabela=tabela).order_by("id")


def test_insert_update_delete_sao_registrados_com_autor():
    with auditoria.contexto(usuario_id=42, ip="10.0.0.7", requisicao_id="req-1"):
        u = Usuario.objects.create_user("ana", "ana@pc.pr.gov.br", "x" * 12, nome="Ana")
        u.nome = "Ana Souza"
        u.save()
        u.delete()
    ops = list(_eventos("identidade_usuario").values_list("operacao", flat=True))
    assert ops == ["INSERT", "UPDATE", "DELETE"]
    update = _eventos("identidade_usuario").get(operacao="UPDATE")
    assert update.usuario_id == 42
    assert str(update.ip) == "10.0.0.7"
    assert update.requisicao_id == "req-1"
    assert "nome" in update.alterados
    assert update.antes["nome"] == "Ana" and update.depois["nome"] == "Ana Souza"


def test_senha_nunca_entra_na_trilha():
    Usuario.objects.create_user("bia", "bia@pc.pr.gov.br", "segredo-123456", nome="Bia")
    evento = _eventos("identidade_usuario").last()
    assert "password" not in evento.depois


def test_update_sem_mudanca_efetiva_nao_gera_evento():
    u = Usuario.objects.create_user("caio", "caio@pc.pr.gov.br", "x" * 12, nome="Caio")
    antes = EventoAuditoria.objects.count()
    Usuario.objects.filter(pk=u.pk).update(nome="Caio")
    assert EventoAuditoria.objects.count() == antes


@pytest.mark.parametrize("sql", [
    "UPDATE auditoria_evento SET operacao = 'INSERT'",
    "DELETE FROM auditoria_evento",
    "TRUNCATE auditoria_evento",
])
def test_trilha_e_somente_insercao(sql):
    Usuario.objects.create_user("dani", "dani@pc.pr.gov.br", "x" * 12, nome="Dani")
    with pytest.raises(DatabaseError, match="somente inserção"), transaction.atomic():
        with connection.cursor() as cur:
            cur.execute(sql)


def test_cadeia_de_hash_integra_e_detecta_adulteracao():
    for i in range(3):
        Usuario.objects.create_user(f"u{i}", f"u{i}@pc.pr.gov.br", "x" * 12, nome=f"U{i}")
    integra, total, quebra = auditoria.verificar_cadeia()
    assert integra and total >= 3 and quebra is None

    # Simula um DBA mal-intencionado que desliga o trigger de proteção.
    with connection.cursor() as cur:
        cur.execute("ALTER TABLE auditoria_evento DISABLE TRIGGER auditoria_evento_imutavel")
        cur.execute("UPDATE auditoria_evento SET depois = '{}'::jsonb "
                    "WHERE id = (SELECT min(id) FROM auditoria_evento)")
        cur.execute("ALTER TABLE auditoria_evento ENABLE TRIGGER auditoria_evento_imutavel")
    integra, _, quebra = auditoria.verificar_cadeia()
    assert not integra and quebra is not None
