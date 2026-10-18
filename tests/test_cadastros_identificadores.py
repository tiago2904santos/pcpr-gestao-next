"""Identificadores adulterados não viram criação nem erro de servidor."""

import pytest


@pytest.mark.django_db
@pytest.mark.parametrize("valor", ["²", "abc", "9" * 5000, "0", "-1"])
@pytest.mark.parametrize("rota", ["/eventos/cadastros/servicos/",
                                  "/coffee/cadastros/fornecedores/salvar/"])
def test_post_invalido_nao_cria(cliente_logado, usuario, valor, rota):
    from gestao.cadastros.models import AtividadePlano
    from gestao.coffee.models import Fornecedor

    usuario.is_superuser = True
    usuario.save(update_fields=["is_superuser"])
    antes = (AtividadePlano.objects.count(), Fornecedor.objects.count())
    resposta = cliente_logado.post(rota, {"pk": valor, "nome": "Não criar por engano"})
    assert resposta.status_code == 404
    assert (AtividadePlano.objects.count(), Fornecedor.objects.count()) == antes
