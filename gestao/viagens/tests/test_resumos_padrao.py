"""Contrato comum das janelas de resumo (docs/visual-agents/resumos/README.md §3): o que
cada pessoa vê (documentos só para quem os abre; lápis só para quem edita), a minuta que
não fixa a geração, o aviso de cancelamento, o rodapé que só aponta para formulários
existentes na lista e os vínculos do ofício."""

from __future__ import annotations

import re

import pytest
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import Municipio, Servidor
from gestao.viagens import ordens
from gestao.viagens.models import Oficio, OrdemServico

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    return cenario_completo()


def _cliente(usuario) -> Client:
    cli = Client()
    cli.force_login(usuario)
    return cli


def _ordem(c, **extra) -> OrdemServico:
    ordem, _ = ordens.salvar(c.usuarios["operador"],
                             destinos=[Municipio.objects.get(nome="Londrina", uf="PR")],
                             servidores=[Servidor.objects.first()], motivo="a feira fictícia",
                             **extra)
    return ordem


def _resumo(cli: Client, nome: str, pk: int) -> str:
    resposta = cli.get(reverse(nome, args=[pk]), HTTP_HX_REQUEST="true")
    assert resposta.status_code == 200
    return resposta.content.decode()


def _rodape(html: str) -> str:
    return html[html.index('id="resumo-rodape"'):]


def _abrir(html: str) -> str:
    """O botão Abrir do rodapé (a âncora inteira)."""
    achado = re.search(r'<a class="botao[^"]*" href="[^"]+">.{0,400}?Abrir[^<]*</a>',
                       _rodape(html), re.S)
    assert achado, "rodapé sem Abrir"
    return achado.group(0)


class TestOrdemDeServico:
    def test_rascunho_mostra_a_minuta_sem_fixar_a_geracao(self, c):
        ordem = _ordem(c)
        html = _resumo(_cliente(c.usuarios["operador"]), "viagens:resumo_ordem", ordem.pk)
        pdf = reverse("viagens:documento_ordem", args=[ordem.pk, "pdf"])
        assert 'id="resumo-documentos"' in html
        assert "A minuta está disponível" in html
        assert f'href="{pdf}?previa=1"' in _rodape(html)
        # No resumo, nem o DOCX (que fixaria a geração) nem o PDF definitivo.
        assert reverse("viagens:documento_ordem", args=[ordem.pk, "docx"]) not in html
        assert f'href="{pdf}"' not in html
        ordem.refresh_from_db()
        assert ordem.documento_gerado_em is None

    def test_gerada_le_o_pdf_e_quem_edita_tem_o_lapis(self, c):
        ordem = _ordem(c)
        ordens.dados_do_documento(ordem, fixar=True)
        html = _resumo(_cliente(c.usuarios["operador"]), "viagens:resumo_ordem", ordem.pk)
        pdf = reverse("viagens:documento_ordem", args=[ordem.pk, "pdf"])
        assert f'href="{pdf}"' in html
        assert "Ver o PDF" in _rodape(html)
        abrir = _abrir(html)
        assert "botao--primario" in abrir and "#i-pencil" in abrir

    def test_cancelada_avisa_e_abre_so_para_ler(self, c):
        ordem = _ordem(c)
        ordens.cancelar(c.usuarios["operador"], ordem.pk, "Evento adiado (teste).")
        html = _resumo(_cliente(c.usuarios["operador"]), "viagens:resumo_ordem", ordem.pk)
        assert "Cancelada em" in html and "Evento adiado (teste)." in html
        assert 'id="resumo-documentos"' not in html
        assert 'id="resumo-conferencia"' not in html
        abrir = _abrir(html)
        assert "botao--primario" not in abrir and "#i-eye" in abrir

    def test_quem_so_le_nao_ve_documentos_nem_lapis(self, c):
        ordem = _ordem(c)
        ordens.dados_do_documento(ordem, fixar=True)
        html = _resumo(_cliente(c.usuarios["consulta"]), "viagens:resumo_ordem", ordem.pk)
        assert 'id="resumo-documentos"' not in html
        assert reverse("viagens:documento_ordem", args=[ordem.pk, "pdf"]) not in html
        abrir = _abrir(html)
        assert "botao--primario" not in abrir and "#i-eye" in abrir

    @pytest.mark.parametrize("cancelar", [False, True])
    def test_menu_do_rodape_so_aponta_para_formularios_da_lista(self, c, cancelar):
        ordem = _ordem(c)
        if cancelar:
            ordens.cancelar(c.usuarios["operador"], ordem.pk, "Evento adiado (teste).")
        cli = _cliente(c.usuarios["gestor"])
        html = _resumo(cli, "viagens:resumo_ordem", ordem.pk)
        lista = cli.get(reverse("viagens:ordens")).content.decode()
        alvos = set(re.findall(r'form="([^"]+)"', _rodape(html)))
        assert alvos, "o menu deveria ter cancelar/reativar"
        for alvo in alvos:
            assert f'id="{alvo}"' in lista, alvo


class TestRoteiro:
    def test_cancelado_avisa_e_nao_oferece_a_folha(self, c):
        html = _resumo(_cliente(c.usuarios["operador"]), "viagens:resumo_roteiro",
                       c.ids["roteiro_cancelado"])
        assert "Roteiro cancelado" in html
        assert reverse("viagens:editar_roteiro", args=[c.ids["roteiro_cancelado"]]) not in html
        assert "Reativar roteiro" in _rodape(html)

    def test_quem_so_le_nao_tem_rodape(self, c):
        html = _resumo(_cliente(c.usuarios["consulta"]), "viagens:resumo_roteiro",
                       c.ids["roteiro"])
        assert 'id="resumo-rodape"' not in html
        assert "Unidade Móvel na Expo Ponta Grossa." in html  # observações no Registro

    def test_percurso_vem_antes_dos_oficios(self, c):
        html = _resumo(_cliente(c.usuarios["operador"]), "viagens:resumo_roteiro",
                       c.ids["roteiro"])
        assert html.index('id="resumo-percurso"') < html.index("Ofícios vinculados")


class TestOficio:
    def test_documentos_vinculados_levam_a_folha(self, c):
        oficio = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
        ordem = _ordem(c, oficios=[oficio])
        html = _resumo(_cliente(c.usuarios["operador"]), "viagens:resumo", oficio.pk)
        assert "Documentos vinculados" in html
        assert f'href="{reverse("viagens:editar_ordem", args=[ordem.pk])}"' in html

    def test_sem_vinculos_diz_que_nao_ha(self, c):
        html = _resumo(_cliente(c.usuarios["operador"]), "viagens:resumo",
                       c.ids["oficio_rascunho"])
        assert "Nenhum termo, OS ou plano feito a partir deste ofício." in html

    def test_cabecalho_destaca_destino_e_data_e_o_resto_vai_para_o_subheader(self, c):
        html = _resumo(_cliente(c.usuarios["operador"]), "viagens:resumo",
                       c.ids["oficio_emitido"])
        cabecalho = html[:html.index("</header>")]
        assert 'class="registro-hero__data"' in cabecalho
        # O resto vai para o sub-header, que rola com o corpo (fora do cabeçalho fixo).
        assert 'class="resumo-subheader"' not in cabecalho
        sub = html[html.index('class="resumo-subheader"'):html.index('class="resumo-corpo"')]
        assert "Protocolo" in sub and "Ofício de" in sub
        assert 'class="resumo-narrativa"' in html and "Motivo" in html
        # Sem o cartão Registro: custeio e porte de arma ficam na folha e no documento.
        assert 'id="resumo-registro"' not in html
        assert "Custeio" not in html and "Porte de arma" not in html
