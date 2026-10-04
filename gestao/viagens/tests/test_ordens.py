"""Ordens de Serviço (módulo 5). Paridade com `viagens_ordens` da referência: numeração
anual com lacunas, cópia do ofício, tipos com função, cancelar/reativar/excluir (libera o
número), documento com o texto do tipo. Dados fictícios."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import ConfiguracaoInstitucional, Municipio, Servidor
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


def _oficio(c) -> Oficio:
    return Oficio.objects.get(pk=c.ids["oficio_emitido"])


def _londrina():
    return Municipio.objects.get(nome="Londrina", uf="PR")


class TestNumeracao:
    def test_sequencia_e_lacuna_reaproveitada(self, c):
        op = c.usuarios["operador"]
        a, _ = ordens.salvar(op, destinos=[_londrina()])
        b, _ = ordens.salvar(op, destinos=[_londrina()])
        ano = timezone.localdate().year
        assert (a.numero, b.numero, a.ano) == (1, 2, ano)
        assert str(a) == f"OS 001/{ano}"
        ordens.excluir(op, a.pk)
        novo, _ = ordens.salvar(op, destinos=[_londrina()])
        assert novo.numero == 1  # a lacuna do excluído volta
        terceiro, _ = ordens.salvar(op, destinos=[_londrina()])
        assert terceiro.numero == 3

    def test_cancelada_continua_ocupando_o_numero(self, c):
        op = c.usuarios["operador"]
        a, _ = ordens.salvar(op, destinos=[_londrina()])
        ordens.cancelar(op, a.pk, "Evento adiado")
        b, _ = ordens.salvar(op, destinos=[_londrina()])
        assert b.numero == 2


class TestCopiaDoOficio:
    def test_os_em_branco_copia_destinos_periodo_equipe_e_motivo(self, c):
        oficio = _oficio(c)
        ordem, copiados = ordens.salvar(c.usuarios["operador"], oficios=[oficio])
        assert set(copiados) == {"destinos", "período", "equipe", "motivo"}
        assert set(ordem.servidores.all()) == {v.servidor for v in oficio.viajantes.all()}
        assert ordem.motivo == oficio.motivo and ordem.data_inicio is not None
        assert ordem.destinos.exists()

    def test_o_preenchido_nao_e_trocado(self, c):
        um = Servidor.objects.first()
        ordem, copiados = ordens.salvar(c.usuarios["operador"], oficios=[_oficio(c)],
                                        servidores=[um], motivo="Motivo próprio")
        assert list(ordem.servidores.all()) == [um] and ordem.motivo == "Motivo próprio"
        assert "equipe" not in copiados and "motivo" not in copiados

    def test_oficio_de_outra_unidade_nao_entra(self, c):
        outra = Oficio.objects.get(pk=c.ids["oficio_outra_unidade"])
        with pytest.raises((PermissionDenied, ordens.OrdemInvalida)):
            ordens.salvar(c.usuarios["gestor"], oficios=[outra])


class TestFuncoesEDocumento:
    def test_funcoes_so_nos_tipos_que_usam_e_validas(self, c):
        um, dois = Servidor.objects.all()[:2]
        op = c.usuarios["operador"]
        ordem, _ = ordens.salvar(op, tipo="caminhao", servidores=[um, dois],
                                 destinos=[_londrina()],
                                 funcoes={str(um.pk): "conducao", "999999": "apoio"})
        assert ordem.funcoes == {str(um.pk): "conducao"}  # quem não está na equipe sai
        with pytest.raises(ordens.OrdemInvalida, match="função válida"):
            ordens.salvar(op, pk=ordem.pk, tipo="caminhao", servidores=[um],
                          funcoes={str(um.pk): "coordenacao"})
        padrao, _ = ordens.salvar(op, tipo="padrao", servidores=[um],
                                  funcoes={str(um.pk): "conducao"})
        assert padrao.funcoes == {}

    def test_documento_com_texto_do_tipo_assinatura_e_data_fixada(self, c):
        um = Servidor.objects.first()
        config = ConfiguracaoInstitucional.objects.get(unidade__sigla="ASCOM")
        config.delegado_geral_nome = "Delegado-Geral Fictício"
        config.save()
        ordem, _ = ordens.salvar(c.usuarios["operador"], tipo="caminhao", servidores=[um],
                                 destinos=[_londrina()], data_inicio=date(2030, 3, 10),
                                 motivo="o evento fictício", funcoes={str(um.pk): "conducao"})
        dados = ordens.dados_do_documento(ordem)
        assert dados["referencia"] == "Deslocamento - Caminhão de apoio"
        assert dados["competencias"][0].startswith(f"{um.nome} – conduzir a Unidade Móvel")
        assert dados["assina"]["nome"] == config.chefia_nome
        assert dados["delegado_geral"] == "Delegado-Geral Fictício"
        ordem.refresh_from_db()
        assert ordem.data_documento == timezone.localdate()  # nasce na primeira geração
        html = ordens.html_do_documento(dados)
        assert f"ORDEM DE SERVIÇO {ordem.numero_formatado} - ASCOM" in html and "DETERMINO" in html

    def test_assinante_da_os_vence_a_configuracao(self, c):
        um, dois = Servidor.objects.all()[:2]
        ordem, _ = ordens.salvar(c.usuarios["operador"], servidores=[um],
                                 destinos=[_londrina()], assinante=dois)
        assert ordens.dados_do_documento(ordem)["assina"]["nome"] == dois.nome

    def test_faltando(self, c):
        ordem, _ = ordens.salvar(c.usuarios["operador"])
        assert ordens.faltando(ordem) == ["período", "destino", "equipe", "motivo"]


class TestCicloDeVida:
    def test_cancelar_reativar(self, c):
        op = c.usuarios["operador"]
        ordem, _ = ordens.salvar(op, destinos=[_londrina()])
        with pytest.raises(ordens.OrdemInvalida, match="motivo"):
            ordens.cancelar(op, ordem.pk, "")
        ordens.cancelar(op, ordem.pk, "Evento adiado")
        with pytest.raises(PermissionDenied):
            ordens.salvar(op, pk=ordem.pk, destinos=[_londrina()])
        ordens.reativar(op, ordem.pk)
        with pytest.raises(ordens.OrdemInvalida):
            ordens.reativar(op, ordem.pk)

    def test_consulta_nao_altera(self, c):
        ordem, _ = ordens.salvar(c.usuarios["operador"], destinos=[_londrina()])
        with pytest.raises(PermissionDenied):
            ordens.excluir(c.usuarios["consulta"], ordem.pk)


class TestTelas:
    def test_nova_pela_tela_e_documento(self, c):
        um = Servidor.objects.first()
        cli = _cliente(c.usuarios["operador"])
        html = cli.get(reverse("viagens:nova_ordem")).content.decode()
        assert "Receberá o número" in html
        r = cli.post(reverse("viagens:nova_ordem"), {
            "tipo": "padrao", "destinos": ["Londrina/PR"], "data_inicio": "10/03/2030",
            "servidores": [um.pk], "motivo": "a feira fictícia"})
        ordem = OrdemServico.objects.get()
        assert r["Location"] == reverse("viagens:editar_ordem", args=[ordem.pk])
        r = cli.get(reverse("viagens:documento_ordem", args=[ordem.pk, "pdf"]))
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
        r = cli.get(reverse("viagens:documento_ordem", args=[ordem.pk, "docx"]))
        assert r.status_code == 200 and "attachment" in r["Content-Disposition"]

    def test_criar_do_oficio_em_um_clique(self, c):
        oficio = _oficio(c)
        r = _cliente(c.usuarios["operador"]).post(
            reverse("viagens:criar_ordem_do_oficio", args=[oficio.pk]))
        ordem = OrdemServico.objects.get()
        assert r["Location"] == reverse("viagens:editar_ordem", args=[ordem.pk])
        assert list(ordem.oficios.all()) == [oficio]

    def test_funcoes_aparecem_depois_de_salvar_a_equipe(self, c):
        um = Servidor.objects.first()
        ordem, _ = ordens.salvar(c.usuarios["operador"], tipo="cerimonial_antecipado",
                                 servidores=[um], destinos=[_londrina()])
        cli = _cliente(c.usuarios["operador"])
        html = cli.get(reverse("viagens:editar_ordem", args=[ordem.pk])).content.decode()
        assert f'name="funcao_{um.pk}"' in html and "Coordenação" in html
        cli.post(reverse("viagens:editar_ordem", args=[ordem.pk]), {
            "tipo": "cerimonial_antecipado", "destinos": ["Londrina/PR"],
            "servidores": [um.pk], f"funcao_{um.pk}": "coordenacao"})
        ordem.refresh_from_db()
        assert ordem.funcoes == {str(um.pk): "coordenacao"}

    def test_lista_abas_busca_e_filtro_por_oficio(self, c):
        op = c.usuarios["operador"]
        futura, _ = ordens.salvar(op, destinos=[_londrina()],
                                  data_inicio=timezone.localdate() + timedelta(days=20))
        do_oficio, _ = ordens.salvar(op, oficios=[_oficio(c)])
        cli = _cliente(op)
        assert f"{futura} ·" in cli.get(reverse("viagens:ordens") + "?aba=futuras").content \
            .decode()
        html = cli.get(reverse("viagens:ordens") + f"?q=OS%20{futura.numero_formatado}").content \
            .decode()
        assert f"{futura} ·" in html and f"{do_oficio} ·" not in html
        html = cli.get(reverse("viagens:ordens") + f"?oficio={_oficio(c).pk}").content.decode()
        assert f"{do_oficio} ·" in html and f"{futura} ·" not in html

    def test_outra_unidade_nao_ve(self, c):
        ordem, _ = ordens.salvar(c.usuarios["operador"], destinos=[_londrina()])
        r = _cliente(c.usuarios["outra"]).get(reverse("viagens:editar_ordem", args=[ordem.pk]))
        assert r.status_code == 403

    def test_janela_do_oficio_oferece_nova_os(self, c):
        html = _cliente(c.usuarios["operador"]).get(
            reverse("viagens:resumo", args=[_oficio(c).pk])).content.decode()
        assert "Nova ordem de serviço" in html

    def test_consultas_da_lista_nao_crescem(self, c):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        cli = _cliente(c.usuarios["gestor"])
        ordens.salvar(c.usuarios["operador"], oficios=[_oficio(c)])

        def contar():
            with CaptureQueriesContext(connection) as ctx:
                cli.get(reverse("viagens:ordens"))
            return len(ctx.captured_queries)

        poucas = contar()
        for _ in range(6):
            ordens.salvar(c.usuarios["operador"], oficios=[_oficio(c)])
        assert contar() == poucas


class TestRevisoes:
    def test_depois_de_gerado_nao_exclui_so_cancela(self, c):
        op = c.usuarios["operador"]
        ordem, _ = ordens.salvar(op, destinos=[_londrina()], servidores=[Servidor.objects.first()])
        ordens.dados_do_documento(ordem)  # gera: fixa data e marca a geração
        ordem.refresh_from_db()
        assert ordem.documento_gerado_em is not None
        from gestao.viagens import policies
        assert not policies.pode_excluir_ordem(op, ordem)
        with pytest.raises(ordens.OrdemInvalida, match="Cancele"):
            ordens.excluir(op, ordem.pk)

    def test_assinante_de_outra_unidade_recusado(self, c):
        de_fora = Servidor.objects.exclude(unidade__sigla="ASCOM").first()
        with pytest.raises(ordens.OrdemInvalida, match="unidade"):
            ordens.salvar(c.usuarios["operador"], destinos=[_londrina()], assinante=de_fora)

    def test_oficio_cancelado_recusado(self, c):
        cancelado = Oficio.objects.get(pk=c.ids["oficio_cancelado"])
        with pytest.raises(ordens.OrdemInvalida, match="cancelado"):
            ordens.salvar(c.usuarios["operador"], oficios=[cancelado])

    def test_tipo_com_funcao_sem_funcao_e_sinalizado(self, c):
        ordem, _ = ordens.salvar(c.usuarios["operador"], tipo="microonibus",
                                 servidores=[Servidor.objects.first()], destinos=[_londrina()],
                                 data_inicio=date(2030, 1, 1), motivo="x")
        assert ordens.faltando(ordem) == ["função da equipe"]

    def test_data_do_documento_em_branco_volta_ao_automatico(self, c):
        op = c.usuarios["operador"]
        ordem, _ = ordens.salvar(op, destinos=[_londrina()], data_documento=date(2030, 1, 1))
        ordem, _ = ordens.salvar(op, pk=ordem.pk, destinos=[_londrina()])
        assert ordem.data_documento is None

    def test_documento_sem_cache(self, c):
        ordem, _ = ordens.salvar(c.usuarios["operador"], destinos=[_londrina()])
        r = _cliente(c.usuarios["operador"]).get(
            reverse("viagens:documento_ordem", args=[ordem.pk, "pdf"]))
        assert r["Cache-Control"] == "no-store"
