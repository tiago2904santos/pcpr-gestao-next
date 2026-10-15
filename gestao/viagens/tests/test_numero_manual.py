"""Número manual de Plano/OS: domínio puro, depois serviço e HTTP."""

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from gestao.viagens import ordens, planos
from gestao.viagens.dominio.numeracao import erro_numero_manual
from gestao.viagens.models import LacunaOrdemServico, LacunaPlano
from gestao.viagens.tests.cenarios import cenario_completo


@pytest.mark.parametrize("numero", [0, -1, 1000000, True, 1.5, "2"])
def test_numero_manual_exige_inteiro_positivo_limitado(numero):
    assert "inteiro entre" in erro_numero_manual(numero, [])


def test_numero_manual_rejeita_ocupado_e_aceita_limites():
    assert "já está em uso" in erro_numero_manual(8, [8, 9])
    assert erro_numero_manual(1, [8]) == ""
    assert erro_numero_manual(999999, []) == ""


@pytest.fixture(params=[(planos, LacunaPlano, "plano", planos.PlanoInvalido),
                       (ordens, LacunaOrdemServico, "ordem", ordens.OrdemInvalida)])
def caso(request, db):
    servico, lacunas, nome, erro = request.param
    c = cenario_completo()
    return servico, lacunas, nome, erro, c.usuarios


def test_troca_numero_reserva_novo_devolve_anterior_e_preserva_ano(caso):
    servico, lacunas, _, _, usuarios = caso
    usuario = usuarios["operador"]
    doc, _ = servico.salvar(usuario, numero=803)
    ano = doc.ano
    lacunas.objects.get_or_create(ano=ano, numero=807)
    salvo, _ = servico.salvar(usuario, pk=doc.pk, numero=807, versao=servico.versao_de(doc))
    assert salvo.numero == 807 and salvo.ano == ano
    assert lacunas.objects.filter(ano=ano, numero=803).exists()
    assert not lacunas.objects.filter(ano=ano, numero=807).exists()
    mantido, _ = servico.salvar(usuario, pk=doc.pk)
    assert mantido.numero == 807
    novo, _ = servico.salvar(usuario)
    assert novo.numero == 803


def test_numero_ocupado_cancelado_e_invalido_nao_gravam_parcialmente(caso):
    servico, lacunas, nome, erro, usuarios = caso
    usuario = usuarios["operador"]
    doc, _ = servico.salvar(usuario, numero=811)
    outro, _ = servico.salvar(usuario, numero=812)
    campo = "cancelado" if nome == "plano" else "cancelada"
    type(outro).objects.filter(pk=outro.pk).update(**{campo: True})
    for pedido in (812, 0, -1, 1000000, True):
        with pytest.raises(erro):
            servico.salvar(usuario, pk=doc.pk, numero=pedido)
        doc.refresh_from_db()
        assert doc.numero == 811
        assert not lacunas.objects.filter(ano=doc.ano, numero=811).exists()
    with pytest.raises(erro):
        servico.salvar(usuario, numero=812)


def test_numero_respeita_versao_e_permissao(caso):
    servico, _, _, erro, usuarios = caso
    doc, _ = servico.salvar(usuarios["operador"])
    with pytest.raises(erro, match="Outra pessoa"):
        servico.salvar(usuarios["operador"], pk=doc.pk, numero=822, versao="antiga")
    with pytest.raises(PermissionDenied):
        servico.salvar(usuarios["consulta"], pk=doc.pk, numero=822)
    doc.refresh_from_db()
    assert doc.numero != 822


def test_numero_no_formulario_autosave_e_colisao(caso, client):
    servico, _, nome, _, usuarios = caso
    doc, _ = servico.salvar(usuarios["operador"], numero=831)
    servico.salvar(usuarios["operador"], numero=832)
    client.force_login(usuarios["operador"])
    pagina = client.get(reverse(f"viagens:editar_{nome}", args=[doc.pk]))
    assert pagina.status_code == 200
    assert pagina.context["form"]["numero"].value() == 831
    rota = reverse(f"viagens:autosave_{nome}", args=[doc.pk])
    resposta = client.post(rota, {"numero": "832", "versao": servico.versao_de(doc)})
    assert resposta.json()["salvo"] is False
    assert "já está em uso" in resposta.json()["mensagem"]
    resposta = client.post(rota, {"numero": "833", "versao": servico.versao_de(doc)})
    assert resposta.json()["salvo"] is True
    assert resposta.json()["recarregar"] is True
    doc.refresh_from_db()
    assert doc.numero == 833
