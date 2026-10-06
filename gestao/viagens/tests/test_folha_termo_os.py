"""Folhas de termo e OS na linguagem da folha do ofício: o documento como vai sair (sem
efeito colateral), a gravação automática e o histórico lido da trilha do banco."""

from __future__ import annotations

from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import ConfiguracaoInstitucional, Municipio, Servidor
from gestao.viagens import linha_do_tempo, ordens, termos
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


def _londrina():
    return Municipio.objects.get(nome="Londrina", uf="PR")


def _os(c, **extra):
    um = Servidor.objects.first()
    ordem, _ = ordens.salvar(c.usuarios["operador"], destinos=[_londrina()],
                             servidores=[um], motivo="a feira fictícia", **extra)
    return ordem, um


class TestFolhaDaOS:
    def test_folha_mostra_o_documento_sem_fixar_data_nem_contar_geracao(self, c):
        ordem, _ = _os(c)
        r = _cliente(c.usuarios["operador"]).get(reverse("viagens:folha_ordem", args=[ordem.pk]))
        html = r.content.decode()
        assert r.status_code == 200 and "DETERMINO" in html
        assert "css/folha.css" in html and 'nonce="' in html
        assert "frame-ancestors 'self'" in r["Content-Security-Policy"]
        assert r["Cache-Control"] == "no-store"
        ordem.refresh_from_db()
        assert ordem.data_documento is None and ordem.documento_gerado_em is None

    def test_pdf_do_visualizador_nao_conta_como_geracao(self, c):
        ordem, _ = _os(c)
        cli = _cliente(c.usuarios["operador"])
        r = cli.get(reverse("viagens:documento_ordem", args=[ordem.pk, "pdf"]) + "?previa=1")
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
        assert "frame-ancestors 'self'" in r["Content-Security-Policy"]
        ordem.refresh_from_db()
        assert ordem.documento_gerado_em is None
        cli.get(reverse("viagens:documento_ordem", args=[ordem.pk, "pdf"]))
        ordem.refresh_from_db()
        assert ordem.documento_gerado_em is not None

    def test_unidade_sem_configuracao_mostra_aviso_na_folha(self, c):
        ordem, _ = _os(c)
        ConfiguracaoInstitucional.objects.filter(unidade=ordem.unidade).delete()
        r = _cliente(c.usuarios["operador"]).get(reverse("viagens:folha_ordem", args=[ordem.pk]))
        assert r.status_code == 200 and "ainda não tem configuração" in r.content.decode()

    def test_outra_unidade_nao_ve_a_folha(self, c):
        ordem, _ = _os(c)
        r = _cliente(c.usuarios["outra"]).get(reverse("viagens:folha_ordem", args=[ordem.pk]))
        assert r.status_code == 403

    def test_tela_em_cartoes_com_conferencia_previa_e_historico(self, c):
        ordem, _ = ordens.salvar(c.usuarios["operador"], destinos=[_londrina()])
        html = _cliente(c.usuarios["operador"]).get(
            reverse("viagens:editar_ordem", args=[ordem.pk])).content.decode()
        for ancora in ("identificacao", "dados", "destinos", "equipe", "motivo", "assinatura",
                       "documento", "conferencia", "previa", "historico"):
            assert f'id="{ancora}"' in html
        assert 'href="#equipe">Falta equipe' in html and 'href="#motivo">Falta motivo' in html
        assert reverse("viagens:folha_ordem", args=[ordem.pk]) in html
        assert f'data-autosave="{reverse("viagens:autosave_ordem", args=[ordem.pk])}"' in html


class TestAutosaveDaOS:
    def test_grava_quando_valido(self, c):
        ordem, um = _os(c)
        r = _cliente(c.usuarios["operador"]).post(
            reverse("viagens:autosave_ordem", args=[ordem.pk]),
            {"tipo": "padrao", "destinos": ["Londrina/PR"], "servidores": [um.pk],
             "motivo": "o novo motivo"})
        assert r.json()["salvo"] is True and r.json()["em"]
        ordem.refresh_from_db()
        assert ordem.motivo == "o novo motivo"

    def test_invalido_diz_o_que_impede_e_nao_grava(self, c):
        ordem, um = _os(c)
        r = _cliente(c.usuarios["operador"]).post(
            reverse("viagens:autosave_ordem", args=[ordem.pk]),
            {"tipo": "padrao", "destinos": ["Londrina/PR"], "servidores": [um.pk],
             "motivo": "outro", "data_inicio": "10/03/2030", "data_fim": "01/03/2030"})
        corpo = r.json()
        assert corpo["salvo"] is False and corpo["mensagem"].startswith("Não salvo")
        ordem.refresh_from_db()
        assert ordem.motivo == "a feira fictícia"

    def test_cancelada_nao_grava(self, c):
        ordem, _ = _os(c)
        ordens.cancelar(c.usuarios["operador"], ordem.pk, "Evento adiado")
        r = _cliente(c.usuarios["operador"]).post(
            reverse("viagens:autosave_ordem", args=[ordem.pk]),
            {"tipo": "padrao", "motivo": "x"})
        assert r.json() == {"salvo": False, "mensagem": "Esta OS não pode ser alterada."}

    def test_consulta_nao_grava_e_outra_unidade_nem_ve(self, c):
        ordem, _ = _os(c)
        url = reverse("viagens:autosave_ordem", args=[ordem.pk])
        r = _cliente(c.usuarios["consulta"]).post(url, {"tipo": "padrao"})
        assert r.status_code == 200 and r.json()["salvo"] is False
        assert _cliente(c.usuarios["outra"]).post(url, {"tipo": "padrao"}).status_code == 403

    def test_so_post(self, c):
        ordem, _ = _os(c)
        r = _cliente(c.usuarios["operador"]).get(reverse("viagens:autosave_ordem",
                                                         args=[ordem.pk]))
        assert r.status_code == 405


class TestHistoricoDaOS:
    def test_criacao_alteracoes_juntas_e_cancelamento(self, c):
        um = Servidor.objects.first()
        cli = _cliente(c.usuarios["operador"])
        cli.post(reverse("viagens:nova_ordem"), {
            "tipo": "padrao", "destinos": ["Londrina/PR"], "servidores": [um.pk],
            "motivo": "a feira"})
        ordem = OrdemServico.objects.get()
        url = reverse("viagens:autosave_ordem", args=[ordem.pk])
        base = {"tipo": "padrao", "destinos": ["Londrina/PR"], "servidores": [um.pk]}
        cli.post(url, {**base, "motivo": "a feira fictícia"})
        cli.post(url, {**base, "motivo": "a feira fictícia", "data_inicio": "10/03/2030"})
        cli.post(reverse("viagens:cancelar_ordem", args=[ordem.pk]), {"motivo": "Adiada"})
        eventos = linha_do_tempo.da_ordem(ordem)
        textos = [e.descricao for e in eventos]
        assert textos == ["Cancelada — Adiada", "Alterou período e motivo",
                          "Ordem de serviço criada"]
        assert all(e.usuario == c.usuarios["operador"] for e in eventos)

    def test_primeira_geracao_entra_no_historico(self, c):
        ordem, _ = _os(c)
        _cliente(c.usuarios["operador"]).get(
            reverse("viagens:documento_ordem", args=[ordem.pk, "pdf"]))
        eventos = linha_do_tempo.da_ordem(ordem)
        assert eventos[0].acao == "documento"
        assert eventos[0].descricao == "Documento gerado pela primeira vez"

    def test_destinos_e_equipe_vem_das_tabelas_filhas(self, c):
        ordem, um = _os(c)
        outro = Servidor.objects.exclude(pk=um.pk).first()
        _cliente(c.usuarios["operador"]).post(
            reverse("viagens:autosave_ordem", args=[ordem.pk]),
            {"tipo": "padrao", "destinos": ["Londrina/PR", "Curitiba/PR"],
             "servidores": [um.pk, outro.pk], "motivo": "a feira fictícia"})
        assert linha_do_tempo.da_ordem(ordem)[0].descricao == "Alterou destinos e equipe"

    def test_id_reaproveitado_nao_herda_o_historico_do_registro_antigo(self, c):
        op = c.usuarios["operador"]
        antiga, _ = _os(c)
        pk, unidade = antiga.pk, antiga.unidade
        ordens.excluir(op, pk)
        nova = OrdemServico.objects.create(pk=pk, unidade=unidade, numero=99, ano=2030,
                                           criado_por=op)
        textos = [e.descricao for e in linha_do_tempo.da_ordem(nova)]
        assert textos == ["Ordem de serviço criada"]


class TestFolhaDoTermo:
    def _termo(self, c):
        um = Servidor.objects.first()
        return termos.salvar(c.usuarios["operador"], destinos=[_londrina()],
                             servidores=[um], data_inicio=date(2030, 3, 10)), um

    def test_folha_por_documento_e_chave_invalida_vira_aviso(self, c):
        termo, um = self._termo(c)
        cli = _cliente(c.usuarios["operador"])
        r = cli.get(reverse("viagens:folha_termo", args=[termo.pk, str(um.pk)]))
        html = r.content.decode()
        assert r.status_code == 200 and um.nome in html and "css/folha.css" in html
        assert "frame-ancestors 'self'" in r["Content-Security-Policy"]
        r = cli.get(reverse("viagens:folha_termo", args=[termo.pk, "999999"]))
        assert "não está no termo" in r.content.decode()

    def test_tela_com_previa_escolhida_e_conferencia(self, c):
        termo, um = self._termo(c)
        cli = _cliente(c.usuarios["operador"])
        url = reverse("viagens:editar_termo", args=[termo.pk])
        html = cli.get(url).content.decode()
        assert reverse("viagens:folha_termo", args=[termo.pk, str(um.pk)]) in html
        # Pronto para gerar: só o selo do cartão (o aviso verde saiu — o rodapé já diz tudo).
        assert "Pronto para gerar" in html and "documentos prontos para gerar" not in html
        html = cli.get(url + "?previa=generico").content.decode()
        assert reverse("viagens:folha_termo", args=[termo.pk, "generico"]) in html
        assert "Como vai sair — Termo genérico" in html

    def test_autosave_e_historico(self, c):
        termo, um = self._termo(c)
        cli = _cliente(c.usuarios["operador"])
        r = cli.post(reverse("viagens:autosave_termo", args=[termo.pk]), {
            "evento": "Feira fictícia", "destinos": ["Londrina/PR"],
            "servidores": [um.pk], "data_inicio": "12/03/2030"})
        assert r.json()["salvo"] is True
        termo.refresh_from_db()
        assert termo.evento == "Feira fictícia"
        assert linha_do_tempo.do_termo(termo)[0].descricao == "Alterou evento e período"
        # Incompleto grava (o termo é rascunho); o que não grava é o período invertido.
        r = cli.post(reverse("viagens:autosave_termo", args=[termo.pk]), {
            "evento": "Feira fictícia", "destinos": ["Londrina/PR"],
            "data_inicio": "12/03/2030", "data_fim": "01/03/2030"})
        assert r.json()["salvo"] is False



class TestRevisaoDeSeguranca:
    def test_previa_da_os_sai_com_marca_de_minuta_e_a_geracao_nao(self, c):
        ordem, _ = _os(c)
        cli = _cliente(c.usuarios["operador"])
        folha = cli.get(reverse("viagens:folha_ordem", args=[ordem.pk])).content.decode()
        assert "MINUTA" in folha
        r = cli.get(reverse("viagens:documento_ordem", args=[ordem.pk, "pdf"]) + "?previa=1")
        assert "previa" in r["Content-Disposition"]
        dados = ordens.dados_do_documento(ordem)  # a geração real
        assert "MINUTA" not in ordens.html_do_documento(dados)

    def test_folha_exige_a_regua_de_gerar(self, c):
        ordem, um = _os(c)
        termo = termos.salvar(c.usuarios["operador"], destinos=[_londrina()], servidores=[um],
                              data_inicio=date(2030, 3, 10))
        consulta = _cliente(c.usuarios["consulta"])
        assert consulta.get(reverse("viagens:folha_ordem", args=[ordem.pk])).status_code == 403
        assert consulta.get(reverse("viagens:folha_termo",
                                    args=[termo.pk, str(um.pk)])).status_code == 403
        html = consulta.get(reverse("viagens:editar_termo", args=[termo.pk])).content.decode()
        assert reverse("viagens:folha_termo", args=[termo.pk, str(um.pk)]) not in html
        assert "aparecem para quem prepara os termos" in html
        ordens.cancelar(c.usuarios["operador"], ordem.pk, "Adiada")
        op = _cliente(c.usuarios["operador"])
        assert op.get(reverse("viagens:folha_ordem", args=[ordem.pk])).status_code == 403
        html = op.get(reverse("viagens:editar_ordem", args=[ordem.pk])).content.decode()
        assert "reative para ver e gerar" in html

    def test_moldura_com_x_frame_options_coerente(self, c):
        ordem, _ = _os(c)
        r = _cliente(c.usuarios["operador"]).get(reverse("viagens:folha_ordem", args=[ordem.pk]))
        assert r["X-Frame-Options"] == "SAMEORIGIN"

    def test_erro_no_pdf_do_visualizador_vira_aviso_na_folha(self, c):
        ordem, _ = _os(c)
        ConfiguracaoInstitucional.objects.filter(unidade=ordem.unidade).delete()
        r = _cliente(c.usuarios["operador"]).get(
            reverse("viagens:documento_ordem", args=[ordem.pk, "pdf"]) + "?previa=1")
        assert r.status_code == 200 and "ainda não tem configuração" in r.content.decode()

    def test_autosave_recusa_gravar_por_cima_de_outra_pessoa(self, c):
        ordem, um = _os(c)
        versao_aberta = ordens.versao_de(ordem)
        ordens.salvar(c.usuarios["gestor"], pk=ordem.pk, destinos=[_londrina()],
                      servidores=[um], motivo="o motivo da gestora")
        url = reverse("viagens:autosave_ordem", args=[ordem.pk])
        base = {"tipo": "padrao", "destinos": ["Londrina/PR"], "servidores": [um.pk]}
        r = _cliente(c.usuarios["operador"]).post(url, {**base, "motivo": "o meu",
                                                         "versao": versao_aberta})
        assert r.json()["salvo"] is False and "Outra pessoa" in r.json()["mensagem"]
        ordem.refresh_from_db()
        assert ordem.motivo == "o motivo da gestora"
        r = _cliente(c.usuarios["operador"]).post(url, {**base, "motivo": "o meu",
                                                         "versao": ordens.versao_de(ordem)})
        corpo = r.json()
        assert corpo["salvo"] is True and corpo["campos"]["versao"] != ordens.versao_de(ordem)

    def test_termo_tambem_tem_versao(self, c):
        um = Servidor.objects.first()
        termo = termos.salvar(c.usuarios["operador"], destinos=[_londrina()], servidores=[um],
                              data_inicio=date(2030, 3, 10))
        aberta = termos.versao_de(termo)
        termos.salvar(c.usuarios["gestor"], pk=termo.pk, destinos=[_londrina()],
                      data_inicio=date(2030, 3, 11))
        r = _cliente(c.usuarios["operador"]).post(
            reverse("viagens:autosave_termo", args=[termo.pk]),
            {"versao": aberta, "destinos": ["Londrina/PR"], "data_inicio": "12/03/2030"})
        assert r.json()["salvo"] is False and "Outra pessoa" in r.json()["mensagem"]


class TestRevisaoDeUX:
    def test_trocar_para_tipo_com_funcao_pede_recarregar(self, c):
        ordem, um = _os(c)
        url = reverse("viagens:autosave_ordem", args=[ordem.pk])
        base = {"destinos": ["Londrina/PR"], "servidores": [um.pk], "motivo": "a feira"}
        r = _cliente(c.usuarios["operador"]).post(url, {**base, "tipo": "padrao"})
        assert r.json()["recarregar"] is False
        r = _cliente(c.usuarios["operador"]).post(url, {**base, "tipo": "cerimonial_antecipado"})
        assert r.json()["recarregar"] is True  # aparecem os campos de função
        r = _cliente(c.usuarios["operador"]).post(url, {
            **base, "tipo": "cerimonial_antecipado", f"funcao_{um.pk}": "coordenacao"})
        assert r.json()["recarregar"] is False

    def test_apagar_o_motivo_nao_traz_de_volta_o_do_oficio(self, c):
        oficio = Oficio.objects.get(pk=c.ids["oficio_emitido"])
        ordem, copiados = ordens.salvar(c.usuarios["operador"], oficios=[oficio])
        assert "motivo" in copiados
        ordem.refresh_from_db()
        _, copiados = ordens.salvar(c.usuarios["operador"], pk=ordem.pk, oficios=[oficio],
                                    destinos=[d.municipio for d in ordem.destinos.all()],
                                    servidores=list(ordem.servidores.all()), motivo="",
                                    data_inicio=ordem.data_inicio)
        ordem.refresh_from_db()
        assert copiados == [] and ordem.motivo == ""

    def test_reativar_termo_volta_ao_proprio_termo(self, c):
        um = Servidor.objects.first()
        termo = termos.salvar(c.usuarios["operador"], destinos=[_londrina()], servidores=[um],
                              data_inicio=date(2030, 3, 10))
        termos.cancelar(c.usuarios["operador"], termo.pk, "Adiado")
        cli = _cliente(c.usuarios["operador"])
        html = cli.get(reverse("viagens:editar_termo", args=[termo.pk])).content.decode()
        destino = reverse("viagens:editar_termo", args=[termo.pk])
        assert f'name="voltar" value="{destino}"' in html
        r = cli.post(reverse("viagens:reativar_termo", args=[termo.pk]), {"voltar": destino})
        assert r["Location"] == destino


class TestTrilha:
    def test_criacao_e_cancelamento_nao_saem_por_causa_do_limite(self, c):
        from gestao.plataforma.auditoria import contexto, passos_do_registro

        op = c.usuarios["operador"]
        ordem, um = _os(c)
        for i in range(5):
            with contexto(op.pk, requisicao_id=f"req-motivo-{i}"):
                ordens.salvar(op, pk=ordem.pk, destinos=[_londrina()], servidores=[um],
                              motivo=f"motivo {i}")
        with contexto(op.pk, requisicao_id="req-cancelar"):
            ordens.cancelar(op, ordem.pk, "Adiada")
        with contexto(op.pk, requisicao_id="req-reativar"):
            ordens.reativar(op, ordem.pk)
        passos = passos_do_registro(OrdemServico._meta.db_table, ordem.pk, limite=1,
                                    marcos=("situacao",))
        assert [p.operacao for p in passos][-1] == "INSERT"
        assert sum("situacao" in p.campos for p in passos) == 2

    def test_filha_de_outro_registro_na_mesma_requisicao_nao_conta(self, c):
        from gestao.plataforma.auditoria import contexto

        op = c.usuarios["operador"]
        a, um = _os(c)
        b, _ = _os(c)
        curitiba = Municipio.objects.filter(nome="Curitiba").first()
        with contexto(op.pk, requisicao_id="req-teste-unica"):
            ordens.salvar(op, pk=a.pk, destinos=[_londrina()], servidores=[um],
                          motivo="só o motivo de A")
            ordens.salvar(op, pk=b.pk, destinos=[_londrina(), curitiba], servidores=[um],
                          motivo="a feira fictícia")
        assert linha_do_tempo.da_ordem(a)[0].descricao == "Alterou motivo"
