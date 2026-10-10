"""Contratos dos contextos de identificação e cabeçalho compartilhados."""

from types import SimpleNamespace

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


def test_cabecalho_preserva_identificacao_completa_com_sufixo_secundario():
    html = render_to_string("componentes/registro_hero.html", {
        "rotulo": "Plano de Trabalho", "numero": "1250/2026", "pagina": True,
        "titulo": "Preparação", "complemento_numero": "ASCOM",
        "complemento": "Equipe e documentos",
    })
    assert "Plano de Trabalho 1250/2026/ASCOM" in html
    assert '<span class="identidade-documental__complemento">ASCOM</span>' in html
    assert html.count("Equipe e documentos") == 1


def test_evento_preserva_destinos_longos_em_consulta_e_edicao():
    nomes = ["Santo Antônio do Paraíso/PR", "São José dos Pinhais/PR"]
    evento = SimpleNamespace(pk=42, destinos=SimpleNamespace(
        all=lambda: [SimpleNamespace(municipio=n) for n in nomes]),
        atividades=SimpleNamespace(all=lambda: []), efetivo_total=1,
        programa_nome="Evento", diarias_total=None)
    for editavel in (False, True):
        html = render_to_string("viagens/planos/_registro_evento.html", {
            "e": evento, "plano": SimpleNamespace(pk=7), "editavel": editavel,
            "forloop": {"counter": 1},
        })
        assert f'title="{", ".join(nomes)}"' in html
        assert 'aria-label="Editar o evento' not in html
        assert all(n in html for n in nomes)
        if editavel:
            assert '/viagens/planos/7/?evento=42#eventos' in html
