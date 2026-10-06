"""Termos de autorização (módulo 4). Paridade com `viagens_termos` da referência: herança do
ofício, regras de destino/data, um documento por servidor + genérico + viatura, PDF único,
ZIP de DOCX, cancelar/reativar/excluir. Dados fictícios."""

from __future__ import annotations

import io
import zipfile
from datetime import date, timedelta

import pikepdf
import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio, Servidor, Viatura
from gestao.viagens import termos
from gestao.viagens.models import Oficio, TermoAutorizacao

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


class TestPeriodo:
    @pytest.mark.parametrize("inicio,fim,texto", [
        (date(2026, 7, 10), None, "no dia 10 de julho de 2026"),
        (date(2026, 7, 10), date(2026, 7, 12), "nos dias 10 até 12 de julho de 2026"),
        (date(2026, 7, 30), date(2026, 8, 2), "nos dias 30 de julho até 2 de agosto de 2026"),
        (date(2026, 12, 30), date(2027, 1, 2),
         "nos dias 30 de dezembro de 2026 até 2 de janeiro de 2027"),
    ])
    def test_por_extenso(self, inicio, fim, texto):
        assert termos.periodo_por_extenso(inicio, fim) == texto


class TestRegras:
    def test_termo_do_oficio_herda_o_que_fica_em_branco(self, c):
        oficio = _oficio(c)
        termo = termos.salvar(c.usuarios["operador"], oficio=oficio)
        ef = termos.efetivo(termo)
        assert set(ef.herdados) >= {"destinos", "período", "servidores"}
        assert ef.servidores == [v.servidor for v in oficio.viajantes.order_by("servidor__nome")]
        assert ef.destinos and ef.inicio is not None
        assert termo.evento == "PCPR na Comunidade"

    def test_o_proprio_vence_o_do_oficio(self, c):
        oficio = _oficio(c)
        londrina = Municipio.objects.get(nome="Londrina", uf="PR")
        um = Servidor.objects.first()
        termo = termos.salvar(c.usuarios["operador"], oficio=oficio, destinos=[londrina],
                              data_inicio=date(2030, 5, 1), servidores=[um])
        ef = termos.efetivo(termo)
        assert ef.destinos == [londrina] and ef.servidores == [um]
        assert (ef.inicio, ef.fim) == (date(2030, 5, 1), date(2030, 5, 1))  # fim = início
        assert "destinos" not in ef.herdados and "servidores" not in ef.herdados

    def test_rascunho_sem_destino_e_data_mas_periodo_coerente(self, c):
        # "Novo termo" cria o rascunho na hora: destino e período ficam como pendência.
        rascunho = termos.salvar(c.usuarios["operador"])
        assert not termos.efetivo(rascunho).completo
        londrina = Municipio.objects.get(nome="Londrina", uf="PR")
        with pytest.raises(termos.TermoInvalido, match="anterior"):
            termos.salvar(c.usuarios["operador"], destinos=[londrina],
                          data_inicio=date(2030, 1, 5), data_fim=date(2030, 1, 1))

    def test_oficio_cancelado_nao_serve(self, c):
        cancelado = Oficio.objects.get(pk=c.ids["oficio_cancelado"])
        with pytest.raises(termos.TermoInvalido, match="cancelado"):
            termos.salvar(c.usuarios["operador"], oficio=cancelado)

    def test_oficio_de_outra_unidade_nao_serve(self, c):
        outra = Oficio.objects.get(pk=c.ids["oficio_outra_unidade"])
        with pytest.raises(PermissionDenied):
            termos.salvar(c.usuarios["operador"], oficio=outra)

    def test_cancelar_exige_motivo_e_bloqueia_edicao(self, c):
        termo = termos.salvar(c.usuarios["operador"], oficio=_oficio(c))
        with pytest.raises(termos.TermoInvalido, match="motivo"):
            termos.cancelar(c.usuarios["operador"], termo.pk, " ")
        termos.cancelar(c.usuarios["operador"], termo.pk, "Evento adiado")
        with pytest.raises(PermissionDenied):
            termos.salvar(c.usuarios["operador"], pk=termo.pk, oficio=_oficio(c))
        termos.reativar(c.usuarios["operador"], termo.pk)
        termo.refresh_from_db()
        assert not termo.cancelado and termo.motivo_cancelamento == ""

    def test_consulta_so_ve(self, c):
        termo = termos.salvar(c.usuarios["operador"], oficio=_oficio(c))
        with pytest.raises(PermissionDenied):
            termos.excluir(c.usuarios["consulta"], termo.pk)


class TestDocumentos:
    def test_um_por_servidor_mais_generico_e_viatura(self, c):
        viatura = Viatura.objects.filter(ativo=True).first()
        termo = termos.salvar(c.usuarios["operador"], oficio=_oficio(c), viatura=viatura)
        docs = termos.documentos_do_termo(termo)
        ef = termos.efetivo(termo)
        assert [d["chave"] for d in docs] == [str(s.pk) for s in ef.servidores] + [
            "generico", "viatura"]

    def test_dados_de_cada_variante(self, c):
        viatura = Viatura.objects.filter(ativo=True).first()
        termo = termos.salvar(c.usuarios["operador"], oficio=_oficio(c), viatura=viatura)
        servidor = termos.efetivo(termo).servidores[0]
        completo = termos.dados_do_documento(termo, str(servidor.pk))
        assert completo["participante"]["nome"] == servidor.nome
        assert completo["viatura"]["placa"] == viatura.placa_formatada
        generico = termos.dados_do_documento(termo, "generico")
        assert generico["participante"] is None and generico["viatura"] is None
        da_viatura = termos.dados_do_documento(termo, "viatura")
        assert da_viatura["participante"] is None and da_viatura["viatura"] is not None
        with pytest.raises(termos.TermoInvalido):
            termos.dados_do_documento(termo, "999999")

    def test_texto_do_documento(self, c):
        termo = termos.salvar(c.usuarios["operador"], oficio=_oficio(c))
        servidor = termos.efetivo(termo).servidores[0]
        html = termos.html_do_documento(termos.dados_do_documento(termo, str(servidor.pk)))
        assert "TERMO DE AUTORIZAÇÃO PARA PARTICIPAÇÃO EM EVENTOS DA ASCOM" in html
        assert servidor.nome in html and "PCPR na Comunidade" in html
        assert "cartão corporativo vigente" in html and "Autorização da Chefia" in html

    def test_telas_geram_pdf_docx_pdf_unico_e_zip(self, c):
        termo = termos.salvar(c.usuarios["operador"], oficio=_oficio(c))
        cli = _cliente(c.usuarios["operador"])
        r = cli.get(reverse("viagens:documento_termo", args=[termo.pk, "generico", "pdf"]))
        assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
        r = cli.get(reverse("viagens:documento_termo", args=[termo.pk, "generico", "docx"]))
        assert r.status_code == 200 and "attachment" in r["Content-Disposition"]
        r = cli.get(reverse("viagens:todos_termo", args=[termo.pk, "pdf"]))
        total = len(termos.documentos_do_termo(termo))
        with pikepdf.Pdf.open(io.BytesIO(r.content)) as pdf:
            assert len(pdf.pages) == total  # um termo por página
        r = cli.get(reverse("viagens:todos_termo", args=[termo.pk, "zip"]))
        assert len(zipfile.ZipFile(io.BytesIO(r.content)).namelist()) == total
        assert cli.get(reverse("viagens:documento_termo",
                               args=[termo.pk, "generico", "exe"])).status_code == 404

    def test_cancelado_nao_gera(self, c):
        termo = termos.salvar(c.usuarios["operador"], oficio=_oficio(c))
        termos.cancelar(c.usuarios["operador"], termo.pk, "Evento adiado")
        r = _cliente(c.usuarios["operador"]).get(
            reverse("viagens:documento_termo", args=[termo.pk, "generico", "pdf"]))
        assert r.status_code == 403


class TestTextoEditado:
    """O texto editado no visualizador acompanha os dados e passa para os documentos novos."""

    def _editar(self, c, termo, chave):
        modelo = termos.regioes_do_modelo(termos.dados_do_documento(termo, chave))
        corpo = modelo["corpo"].replace("cartão corporativo vigente",
                                        "cartão corporativo vigente e o crachá")
        assert corpo != modelo["corpo"]
        termos.salvar_texto(termo, c.usuarios["operador"], chave, {"corpo": corpo})

    def test_edicao_acompanha_a_troca_de_viatura(self, c):
        op = c.usuarios["operador"]
        s1 = Servidor.objects.order_by("pk").first()
        v1, v2 = Viatura.objects.filter(ativo=True).order_by("pk")[:2]
        termo = termos.salvar(op, servidores=[s1], viatura=v1, data_inicio=date(2030, 5, 10))
        self._editar(c, termo, str(s1.pk))
        termo = termos.salvar(op, pk=termo.pk, servidores=[s1], viatura=v2,
                              data_inicio=date(2030, 5, 10))
        html = termos.html_do_documento(termos.dados_do_documento(termo, str(s1.pk)))
        assert "e o crachá" in html  # a edição fica
        assert v2.placa_formatada in html and v1.placa_formatada not in html  # o dado acompanha

    def test_servidor_novo_nasce_com_o_texto_editado(self, c):
        op = c.usuarios["operador"]
        s1, s2 = Servidor.objects.order_by("pk")[:2]
        termo = termos.salvar(op, servidores=[s1], data_inicio=date(2030, 5, 10))
        self._editar(c, termo, str(s1.pk))
        termo = termos.salvar(op, pk=termo.pk, servidores=[s1, s2], data_inicio=date(2030, 5, 10))
        novo = termos.html_do_documento(termos.dados_do_documento(termo, str(s2.pk)))
        assert "e o crachá" in novo and s2.nome in novo and s1.nome not in novo
        # O genérico já existia e não foi editado: continua como o modelo.
        generico = termos.html_do_documento(termos.dados_do_documento(termo, termos.GENERICO))
        assert "e o crachá" not in generico


class TestOficiosVinculados:
    """Vários ofícios num termo: só da mesma ação (mesma viagem ou mesmo roteiro); o termo
    une os dados deles."""

    def _dois(self, c):
        return (Oficio.objects.get(pk=c.ids["oficio_emitido"]),
                Oficio.objects.get(pk=c.ids["oficio_rascunho"]))

    def test_oficios_de_acoes_diferentes_nao_se_juntam(self, c):
        o1, o2 = self._dois(c)
        with pytest.raises(termos.TermoInvalido, match="mesma viagem ou usar o mesmo roteiro"):
            termos.salvar(c.usuarios["operador"], oficios=[o1, o2])

    def test_da_mesma_viagem_unem_destinos_periodo_e_equipe(self, c):
        from gestao.viagens import viagem
        op = c.usuarios["operador"]
        o1, o2 = self._dois(c)
        v = viagem.criar(op)
        Oficio.objects.filter(pk__in=[o1.pk, o2.pk]).update(viagem=v)
        o1.refresh_from_db()
        o2.refresh_from_db()
        termo = termos.salvar(op, oficios=[o1, o2])
        assert termo.oficio == o1 and set(termo.oficios.all()) == {o1, o2}
        ef = termos.efetivo(TermoAutorizacao.objects.get(pk=termo.pk))
        separados = [termos.efetivo(TermoAutorizacao.objects.get(
            pk=termos.salvar(op, oficio=o).pk)) for o in (o1, o2)]
        assert set(ef.destinos) == set(separados[0].destinos) | set(separados[1].destinos)
        assert set(ef.servidores) == set(separados[0].servidores) | set(separados[1].servidores)
        assert ef.inicio == min(e.inicio for e in separados)
        assert ef.fim == max(e.fim for e in separados)

    def test_busca_so_oferece_os_que_se_juntam(self, c):
        from gestao.viagens import viagem
        op = c.usuarios["operador"]
        o1, o2 = self._dois(c)
        cli = _cliente(op)
        url = reverse("viagens:buscar_oficios")
        separado = cli.get(url, {"excluir": o1.pk, "q": o2.numero_formatado}).json()
        assert separado["resultados"] == []
        Oficio.objects.filter(pk__in=[o1.pk, o2.pk]).update(viagem=viagem.criar(op))
        junto = cli.get(url, {"excluir": o1.pk, "q": o2.numero_formatado}).json()
        assert [r["id"] for r in junto["resultados"]] == [str(o2.pk)]


class TestTelas:
    def test_novo_a_partir_do_oficio(self, c):
        oficio = _oficio(c)
        cli = _cliente(c.usuarios["operador"])
        html = cli.get(reverse("viagens:novo_termo") + f"?oficio={oficio.pk}").content.decode()
        assert f"Ofício {oficio.numero_formatado}" in html
        r = cli.post(reverse("viagens:novo_termo"), {"oficios": [oficio.pk]})
        termo = TermoAutorizacao.objects.get()
        assert r["Location"] == reverse("viagens:editar_termo", args=[termo.pk]) + "#t-documentos"
        assert termo.oficio == oficio and termo.unidade == oficio.unidade

    def test_avulso_pela_tela_com_destinos_e_servidores(self, c):
        um, dois = Servidor.objects.all()[:2]
        r = _cliente(c.usuarios["operador"]).post(reverse("viagens:novo_termo"), {
            "destinos": ["Londrina/PR", "Maringá/PR"], "data_inicio": "10/07/2030",
            "data_fim": "12/07/2030", "servidores": [um.pk, dois.pk], "evento": "Feira"})
        assert r.status_code == 302
        termo = TermoAutorizacao.objects.get()
        assert [str(d.municipio) for d in termo.destinos.all()] == ["Londrina/PR", "Maringá/PR"]
        assert termo.evento == "Feira" and termo.servidores.count() == 2

    def test_erro_volta_com_mensagem(self, c):
        r = _cliente(c.usuarios["operador"]).post(reverse("viagens:novo_termo"), {
            "data_inicio": "10/07/2030", "data_fim": "01/07/2030"})
        assert r.status_code == 422
        assert "A data final não pode ser anterior à inicial." in r.content.decode()

    def test_lista_abas_busca_e_filtro_por_oficio(self, c):
        oficio = _oficio(c)
        londrina = Municipio.objects.get(nome="Londrina", uf="PR")
        futuro = termos.salvar(c.usuarios["operador"], destinos=[londrina],
                               data_inicio=timezone.localdate() + timedelta(days=30))
        do_oficio = termos.salvar(c.usuarios["operador"], oficio=oficio)
        cli = _cliente(c.usuarios["operador"])
        html = cli.get(reverse("viagens:termos") + "?aba=futuros").content.decode()
        assert f"{futuro} ·" in html
        html = cli.get(reverse("viagens:termos") + "?q=londrina").content.decode()
        assert f"{futuro} ·" in html and f"{do_oficio} ·" not in html
        html = cli.get(reverse("viagens:termos") + f"?oficio={oficio.pk}").content.decode()
        assert f"{do_oficio} ·" in html and f"{futuro} ·" not in html
        html = cli.get(reverse("viagens:termos") + f"?q={oficio.numero_formatado}") \
            .content.decode()
        assert f"{do_oficio} ·" in html

    def test_outra_unidade_nao_ve(self, c):
        termo = termos.salvar(c.usuarios["operador"], oficio=_oficio(c))
        r = _cliente(c.usuarios["outra"]).get(reverse("viagens:editar_termo", args=[termo.pk]))
        assert r.status_code == 403
        assert f"{termo} ·" not in _cliente(c.usuarios["outra"]).get(
            reverse("viagens:termos")).content.decode()

    def test_busca_de_oficios_nao_traz_cancelados(self, c):
        dados = _cliente(c.usuarios["operador"]).get(
            reverse("viagens:buscar_oficios") + "?q=arapongas").json()
        ids = {int(r["id"]) for r in dados["resultados"]}
        assert c.ids["oficio_cancelado"] not in ids and ids

    def test_criar_do_oficio_em_um_clique(self, c):
        oficio = _oficio(c)
        r = _cliente(c.usuarios["operador"]).post(
            reverse("viagens:criar_termo_do_oficio", args=[oficio.pk]))
        termo = TermoAutorizacao.objects.get()
        assert r["Location"].endswith(f"/viagens/termos/{termo.pk}/#t-documentos")
        assert termo.oficio == oficio
        # Ofício sem roteiro: o termo nasce do mesmo jeito (rascunho), com o que falta
        # como pendência na folha.
        vazio = Oficio.objects.get(pk=c.ids["oficio_vazio"])
        r = _cliente(c.usuarios["operador"]).post(
            reverse("viagens:criar_termo_do_oficio", args=[vazio.pk]))
        novo = TermoAutorizacao.objects.exclude(pk=termo.pk).get()
        assert r["Location"].endswith(f"/viagens/termos/{novo.pk}/#t-documentos")

    def test_tela_preenche_os_campos_com_o_que_vem_do_oficio(self, c):
        # Vincular um ofício preenche os campos (sem o antigo "Do ofício: …" sob eles).
        oficio = _oficio(c)
        html = _cliente(c.usuarios["operador"]).get(
            reverse("viagens:novo_termo") + f"?oficio={oficio.pk}").content.decode()
        destinos, _, _ = termos._do_oficio(oficio)
        assert destinos and all(f'value="{m.nome}/{m.uf}"' in html for m in destinos)
        assert "Do ofício:" not in html

    def test_novo_termo_cria_o_rascunho_na_hora(self, c):
        cli = _cliente(c.usuarios["operador"])
        r = cli.post(reverse("viagens:novo_termo"), {"acao": "criar"})
        termo = TermoAutorizacao.objects.get()
        assert r["Location"] == reverse("viagens:editar_termo", args=[termo.pk])
        html = cli.get(r["Location"]).content.decode()
        assert "Falta destino" in html and "Falta período" in html

    def test_janela_do_oficio_oferece_novo_termo(self, c):
        oficio = _oficio(c)
        html = _cliente(c.usuarios["operador"]).get(
            reverse("viagens:resumo", args=[oficio.pk])).content.decode()
        assert "Novo termo de autorização" in html

    def test_consultas_da_lista_nao_crescem(self, c):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        cli = _cliente(c.usuarios["gestor"])
        termos.salvar(c.usuarios["operador"], oficio=_oficio(c))

        def contar():
            with CaptureQueriesContext(connection) as ctx:
                cli.get(reverse("viagens:termos"))
            return len(ctx.captured_queries)

        poucos = contar()
        for _ in range(6):
            termos.salvar(c.usuarios["operador"], oficio=_oficio(c))
        assert contar() == poucos


class TestRevisaoDeSeguranca:
    def test_regex_de_municipio_nao_trava(self, c):
        import time

        from django import forms as djforms

        from gestao.cadastros.forms import resolver_municipio
        inicio = time.monotonic()
        with pytest.raises(djforms.ValidationError):
            resolver_municipio("a" + " " * 32000 + "x")
        assert time.monotonic() - inicio < 0.5

    def test_gestor_liga_oficio_de_outra_unidade_e_o_termo_vai_para_ela(self, c):
        outra = Oficio.objects.get(pk=c.ids["oficio_outra_unidade"])
        extra = {"destinos": [Municipio.objects.get(nome="Londrina", uf="PR")],
                 "data_inicio": date(2030, 1, 1)}
        termo = termos.salvar(c.usuarios["gestor"], oficio=outra, **extra)
        assert termo.unidade == outra.unidade
        mesmo = termos.salvar(c.usuarios["gestor"], oficio=_oficio(c))
        with pytest.raises(termos.TermoInvalido, match="outra unidade"):
            termos.salvar(c.usuarios["gestor"], pk=mesmo.pk, oficio=outra, **extra)

    def test_limite_de_servidores(self, c, monkeypatch):
        monkeypatch.setattr(termos, "MAX_SERVIDORES", 2)
        with pytest.raises(termos.TermoInvalido, match="No máximo 2"):
            termos.salvar(c.usuarios["operador"], oficio=_oficio(c),
                          servidores=list(Servidor.objects.all()[:3]))

    def test_busca_com_digito_unicode_nao_derruba(self, c):
        cli = _cliente(c.usuarios["operador"])
        assert cli.get(reverse("viagens:termos") + "?q=%C2%B2/2026").status_code == 200
        assert cli.get(reverse("viagens:buscar_oficios") + "?q=%C2%B2/2026").status_code == 200

    def test_motivo_longo_e_reativar_ativo(self, c):
        termo = termos.salvar(c.usuarios["operador"], oficio=_oficio(c))
        with pytest.raises(termos.TermoInvalido, match="1000"):
            termos.cancelar(c.usuarios["operador"], termo.pk, "x" * 1001)
        with pytest.raises(termos.TermoInvalido, match="não está cancelado"):
            termos.reativar(c.usuarios["operador"], termo.pk)

    def test_pdf_nao_busca_recurso_de_fora(self):
        from gestao.viagens.documentos.pdf import buscar_recurso
        with pytest.raises(ValueError):
            buscar_recurso().fetch("https://exemplo.invalido/x.png")
        with pytest.raises(ValueError):
            buscar_recurso().fetch("file:///etc/passwd")


class TestDuplicarEFinalizar:
    def test_duplicar_copia_dados_e_texto_editado(self, c):
        op = c.usuarios["operador"]
        s1 = Servidor.objects.order_by("pk").first()
        termo = termos.salvar(op, servidores=[s1], data_inicio=date(2030, 5, 10),
                              destinos=[Municipio.objects.get(nome="Londrina", uf="PR")])
        TestTextoEditado()._editar(c, termo, str(s1.pk))
        r = _cliente(op).post(reverse("viagens:duplicar_termo", args=[termo.pk]))
        novo = TermoAutorizacao.objects.exclude(pk=termo.pk).get()
        assert r["Location"] == reverse("viagens:editar_termo", args=[novo.pk])
        assert list(novo.servidores.all()) == [s1] and novo.data_inicio == date(2030, 5, 10)
        html = termos.html_do_documento(termos.dados_do_documento(novo, str(s1.pk)))
        assert "e o crachá" in html

    def test_finalizar_volta_a_lista(self, c):
        op = c.usuarios["operador"]
        termo = termos.salvar(op, data_inicio=date(2030, 5, 10))
        r = _cliente(op).post(reverse("viagens:finalizar_termo", args=[termo.pk]))
        assert r["Location"] == reverse("viagens:termos")
