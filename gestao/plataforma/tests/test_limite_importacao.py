"""A exceção de upload não amplia o teto de outros formulários."""

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from gestao.plataforma.middleware import LimiteDoCorpoMiddleware


@pytest.mark.parametrize(
    ("caminho", "tamanho", "status"),
    [
        ("/viagens/importacoes/enviar/", 25 * 1024**2 + 4096, 200),
        ("/viagens/importacoes/enviar/", 26 * 1024**2 + 1, 413),
        ("/viagens/importacoes/estado/", 17 * 1024**2, 413),
        ("/viagens/oficios/1/", 17 * 1024**2, 413),
        ("/viagens/importacoes/enviar/outro/", 17 * 1024**2, 413),
    ],
)
def test_limite_por_caminho_exato(caminho, tamanho, status):
    middleware = LimiteDoCorpoMiddleware(lambda request: HttpResponse("ok"))
    request = RequestFactory().post(caminho)
    request.META["CONTENT_LENGTH"] = str(tamanho)
    resposta = middleware(request)
    assert resposta.status_code == status
    if status == 413:
        assert ("25 MB" if caminho.endswith("enviar/") else "15 MB") in resposta.content.decode()
