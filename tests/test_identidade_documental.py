"""Contratos dos contextos de identificação e cabeçalho compartilhados."""

from django.template.loader import render_to_string


def test_cabecalho_mantem_texto_auxiliar_fora_da_identificacao():
    html = render_to_string("componentes/registro_hero.html", {
        "rotulo": "Plano", "numero": "1250/2026", "titulo": "Preparação",
        "contexto": "Viagens", "complemento": "Equipe, percurso e documentos",
        "pagina": True,
    })
    identificacao = html.split('class="registro-hero__identidade">', 1)[1].split(
        '<div class="registro-hero__conteudo">', 1)[0]
    assert "1250/2026" in identificacao
    assert "Equipe, percurso" not in identificacao
    assert html.count("Equipe, percurso e documentos") == 1


def test_identificacao_exibe_sufixo_documental_quando_explicito():
    html = render_to_string("componentes/identidade_documental.html", {
        "rotulo": "Plano", "numero": "1250/2026", "complemento": "ASCOM",
        "compacta": True, "situacao": "cancelado",
    })
    assert "1250/2026" in html
    assert "ASCOM" in html
    assert "identidade-documental__numero--cancelado" in html
