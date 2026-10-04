"""Planos de trabalho — plano de um evento (6c). Paridade com `viagens_planos` da
referência: numeração anual com sufixo e lacunas, criação a partir do ofício, textos
automáticos com "voltar ao automático", atividades → metas e recursos, diárias de um trecho
(cópia gravada), pendências, finalizar, documento, ciclo de vida e telas. Dados fictícios."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import (
    AtividadePlano,
    Cargo,
    ConfiguracaoInstitucional,
    Municipio,
    PresetAtividades,
    ProgramaSolicitante,
    Servidor,
    Unidade,
)
from gestao.viagens import linha_do_tempo, planos
from gestao.viagens.models import LacunaPlano, Oficio, PlanoTrabalho

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


def _aware(*args) -> datetime:
    return timezone.make_aware(datetime(*args))


def _completo(c, **extra):
    """Um plano sem pendência: coordenador, destino, data, efetivo e deslocamento."""
    op = c.usuarios["operador"]
    agente = Cargo.objects.get(nome="Agente de Polícia Judiciária")
    ascom = Unidade.objects.get(sigla="ASCOM")
    campos = {
        "programa": ProgramaSolicitante.objects.get(nome="PROGRAMA PARANÁ EM AÇÃO"),
        "destinos": [Municipio.objects.get(nome="Maringá", uf="PR")],
        "data_inicio": date(2030, 6, 25), "data_fim": date(2030, 6, 27),
        "coordenador_adm": Servidor.objects.filter(unidade=ascom).first(),
        "coordenador_adm_genero": "M",
        "efetivo": [planos.LinhaInformada(cargo=agente, quantidade=6, unidade=ascom)],
        "saida_em": _aware(2030, 6, 24, 7), "chegada_em": _aware(2030, 6, 28, 14),
        "atividades": list(AtividadePlano.objects.filter(codigo__in=["CIN", "UNIDADE_MOVEL"]))}
    campos.update(extra)
    return planos.salvar(op, **campos)[0]


class TestNumeracao:
    def test_sequencia_com_sufixo_e_lacuna_da_exclusao(self, c):
        op = c.usuarios["operador"]
        a, _ = planos.salvar(op)
        b, _ = planos.salvar(op)
        ano = timezone.localdate().year
        assert (a.numero, b.numero) == (1, 2)
        assert a.numero_formatado == f"01/{ano}/ASCOM"
        assert str(a) == f"Plano de Trabalho 01/{ano}/ASCOM"
        planos.excluir(op, a.pk)
        assert LacunaPlano.objects.filter(ano=ano, numero=1).exists()
        assert planos.salvar(op)[0].numero == 1
        assert planos.salvar(op)[0].numero == 3

    def test_sufixo_da_configuracao_vence_a_sigla(self, c):
        ConfiguracaoInstitucional.objects.filter(unidade__sigla="ASCOM").update(sufixo_plano="AC")
        assert planos.salvar(c.usuarios["operador"])[0].sufixo == "AC"

    def test_depois_de_gerado_nao_exclui(self, c):
        plano = _completo(c)
        planos.finalizar(c.usuarios["operador"], plano.pk)  # gera: o número saiu
        with pytest.raises(planos.PlanoInvalido, match="Cancele em vez de excluir"):
            planos.excluir(c.usuarios["operador"], plano.pk)


class TestCriacaoDoOficio:
    def test_destino_datas_efetivo_e_deslocamento_vem_do_oficio(self, c):
        oficio = _oficio(c)
        plano, copiados = planos.salvar(c.usuarios["operador"], oficios=[oficio])
        assert set(copiados) == {"destinos", "período", "efetivo", "deslocamento"}
        assert planos.destinos_texto(plano) == ["Arapongas/PR"]
        linhas = {(e.cargo.nome, e.quantidade) for e in plano.efetivo.all()}
        assert linhas == {("Agente de Polícia Judiciária", 1), ("Escrivão de Polícia", 1)}
        trechos = list(oficio.trechos.order_by("ordem"))
        assert plano.saida_em == trechos[0].saida_em and plano.chegada_em == trechos[-1].chegada_em
        assert plano.diarias_total is not None  # com tudo isso, as diárias já fecham

    def test_coordenador_padrao_da_configuracao(self, c):
        coord = Servidor.objects.first()
        ConfiguracaoInstitucional.objects.filter(unidade__sigla="ASCOM").update(
            coordenador_plano=coord)
        plano, _ = planos.salvar(c.usuarios["operador"])
        assert plano.coordenador_adm == coord

    def test_oficio_de_outra_unidade_recusado(self, c):
        outra = Oficio.objects.get(pk=c.ids["oficio_outra_unidade"])
        with pytest.raises(PermissionDenied):  # nem aparece para quem é de outra unidade
            planos.salvar(c.usuarios["operador"], oficios=[outra])


class TestTextosEAtividades:
    def test_textos_automaticos_e_voltar_ao_automatico(self, c):
        plano = _completo(c)
        assert "município de Maringá/PR" in plano.contextualizacao
        assert "Programa Paraná em Ação" in plano.contextualizacao
        assert plano.coordenacao.startswith("Fica designado como Coordenador Administrativo")
        op = c.usuarios["operador"]
        base = {"destinos": [Municipio.objects.get(nome="Maringá", uf="PR")],
                "data_inicio": plano.data_inicio}
        plano, _ = planos.salvar(op, pk=plano.pk, contextualizacao="Texto escrito à mão.",
                                 **base)
        assert plano.contextualizacao == "Texto escrito à mão." and not plano.contextualizacao_auto
        sarandi = Municipio.objects.get(nome="Sarandi", uf="PR")
        plano, _ = planos.salvar(op, pk=plano.pk, destinos=[sarandi],
                                 data_inicio=plano.data_inicio)
        assert plano.contextualizacao == "Texto escrito à mão."  # escrito fica
        plano, _ = planos.salvar(op, pk=plano.pk, contextualizacao="", destinos=[sarandi],
                                 data_inicio=plano.data_inicio)
        assert plano.contextualizacao_auto and "Sarandi/PR" in plano.contextualizacao

    def test_metas_recursos_e_unidade_movel(self, c):
        plano = _completo(c)
        assert plano.atividades_texto.count("• ") == 2
        assert plano.unidade_movel_texto.startswith("Estrutura: Unidade móvel da PCPR")
        assert plano.recursos.endswith("Prever unidade móvel institucional e o suporte "
                                       "operacional associado.")

    def test_coordenador_do_cadastro_apaga_o_manual_e_manual_em_maiusculas(self, c):
        op = c.usuarios["operador"]
        plano, _ = planos.salvar(op, coordenador_adm_nome="  fulana de tal ",
                                 coordenador_adm_cargo="Papiloscopista",
                                 coordenador_adm_genero="F")
        assert plano.coordenador_adm_nome == "FULANA DE TAL"
        assert "Fica designada como Coordenadora Administrativa do Plano a Papiloscopista " \
               "Fulana de Tal" in plano.coordenacao
        s = Servidor.objects.first()
        plano, _ = planos.salvar(op, pk=plano.pk, coordenador_adm=s,
                                 coordenador_adm_nome="FULANA DE TAL")
        assert plano.coordenador_adm == s and plano.coordenador_adm_nome == ""


class TestDiariasEPendencias:
    def test_copia_das_diarias_ao_centavo(self, c):
        plano = _completo(c)  # Maringá, 6 servidores, 24/06 07:00 a 28/06 14:00
        assert plano.diarias_composicao == "4 x 100% + 1 x 15%"
        assert str(plano.diarias_unitario) == "1205.78" and str(plano.diarias_total) == "7234.68"

    def test_calculo_invalido_apaga_a_copia_e_vira_pendencia(self, c):
        plano = _completo(c)
        plano, _ = planos.salvar(c.usuarios["operador"], pk=plano.pk,
                                 destinos=[m.municipio for m in plano.destinos.all()],
                                 data_inicio=plano.data_inicio, saida_em=None, chegada_em=None)
        assert plano.diarias_total is None
        assert "Informe a saída e a chegada na sede." in [
            p.mensagem for p in planos.pendencias(plano)]

    def test_finalizar_so_sem_pendencias(self, c):
        op = c.usuarios["operador"]
        vazio, _ = planos.salvar(op)
        with pytest.raises(planos.PlanoInvalido, match="Falta"):
            planos.finalizar(op, vazio.pk)
        plano = planos.finalizar(op, _completo(c).pk)
        plano.refresh_from_db()
        assert plano.gerado and plano.documento_gerado_em and plano.data_documento


class TestDocumentoECicloDeVida:
    def test_geracao_fixa_data_e_marca_gerado_previa_nao(self, c):
        plano = _completo(c)
        dados = planos.dados_do_documento(plano, fixar=False)
        assert dados["previa"] and "MINUTA" in planos.html_do_documento(dados)
        plano.refresh_from_db()
        assert plano.documento_gerado_em is None and not plano.gerado
        planos.finalizar(c.usuarios["operador"], plano.pk)
        plano.refresh_from_db()
        dados = planos.dados_do_documento(plano)
        html = planos.html_do_documento(dados)
        assert "MINUTA" not in html and "PLANO DE TRABALHO Nº" in html
        for trecho in ("Breve contextualização", "Atuação", "Metas estabelecidas",
                       "Valor total do plano", "Coordenador do evento", "Considerações finais",
                       "R$7.234,68", "6 Agentes de Polícia Judiciária (ASCOM)"):
            assert trecho in html
        plano.refresh_from_db()
        assert plano.gerado and plano.documento_gerado_em and plano.data_documento

    def test_incompleto_nao_gera(self, c):
        plano, _ = planos.salvar(c.usuarios["operador"])
        with pytest.raises(planos.PlanoInvalido, match="Finalizar e gerar"):
            planos.dados_do_documento(plano)

    def test_cancelado_nao_altera_e_reativa(self, c):
        op = c.usuarios["operador"]
        plano = _completo(c)
        with pytest.raises(planos.PlanoInvalido, match="motivo"):
            planos.cancelar(op, plano.pk, "  ")
        planos.cancelar(op, plano.pk, "Evento adiado")
        with pytest.raises(Exception, match="não pode ser alterado"):
            planos.salvar(op, pk=plano.pk)
        assert not planos.reativar(op, plano.pk).cancelado

    def test_historico(self, c):
        cli = _cliente(c.usuarios["operador"])
        cli.post(reverse("viagens:novo_plano"), {"programa": "outro",
                                                 "programa_outros": "Feira fictícia"})
        plano = PlanoTrabalho.objects.get()
        cli.post(reverse("viagens:cancelar_plano", args=[plano.pk]), {"motivo": "Adiado"})
        textos = [e.descricao for e in linha_do_tempo.do_plano(plano)]
        assert textos == ["Cancelado — Adiado", "Plano de trabalho criado"]


class TestTelas:
    def test_novo_pela_tela_e_folha_em_cartoes(self, c):
        cli = _cliente(c.usuarios["operador"])
        html = cli.get(reverse("viagens:novo_plano")).content.decode()
        assert "Recebe o número" in html
        r = cli.post(reverse("viagens:novo_plano"), {
            "programa": "outro", "programa_outros": "Feira fictícia", "horario": "09:00 até 17:00",
            "efetivo_presente": "1", "efetivo_unidade": [""], "efetivo_cargo": [""],
            "efetivo_quantidade": ["1"], "atividades_presente": "1"})
        plano = PlanoTrabalho.objects.get()
        assert r["Location"] == reverse("viagens:editar_plano", args=[plano.pk])
        html = cli.get(r["Location"]).content.decode()
        for ancora in ("identificacao", "efetivo", "atividades", "documento", "conferencia",
                       "previa", "historico"):
            assert f'id="{ancora}"' in html
        assert 'href="#identificacao">Informe o coordenador administrativo.' in html
        assert reverse("viagens:folha_plano", args=[plano.pk]) in html

    def test_conjunto_padrao_vem_marcado_no_plano_sem_atividade(self, c):
        cin = AtividadePlano.objects.get(codigo="CIN")
        preset = PresetAtividades.objects.create(nome="PADRÃO", padrao=True)
        preset.atividades.add(cin)
        html = _cliente(c.usuarios["operador"]).get(reverse("viagens:novo_plano")).content.decode()
        assert f'value="{cin.pk}" id="atividade-{cin.pk}" checked' in html

    def test_efetivo_em_linhas_com_erro_por_linha(self, c):
        plano, _ = planos.salvar(c.usuarios["operador"])
        agente = Cargo.objects.get(nome="Agente de Polícia Judiciária")
        ascom = Unidade.objects.get(sigla="ASCOM")
        cli = _cliente(c.usuarios["operador"])
        url = reverse("viagens:autosave_plano", args=[plano.pk])
        r = cli.post(url, {"efetivo_presente": "1", "efetivo_unidade": [str(ascom.pk), ""],
                           "efetivo_cargo": ["", str(agente.pk)],
                           "efetivo_quantidade": ["2", "3"]})
        assert r.json()["salvo"] is False and "Linha 1: selecione o cargo" in r.json()["mensagem"]
        r = cli.post(url, {"efetivo_presente": "1", "efetivo_unidade": [str(ascom.pk), ""],
                           "efetivo_cargo": [str(agente.pk), str(agente.pk)],
                           "efetivo_quantidade": ["2", "3"]})
        assert r.json()["salvo"] is True
        gravado = PlanoTrabalho.objects.get(pk=plano.pk)
        assert sum(e.quantidade for e in gravado.efetivo.all()) == 5  # cargo pode repetir

    def test_autosave_versao_e_cancelado(self, c):
        plano, _ = planos.salvar(c.usuarios["operador"])
        aberta = planos.versao_de(plano)
        planos.salvar(c.usuarios["gestor"], pk=plano.pk, programa_outros="Outro")
        url = reverse("viagens:autosave_plano", args=[plano.pk])
        r = _cliente(c.usuarios["operador"]).post(url, {"versao": aberta, "programa": "outro",
                                                        "programa_outros": "Meu"})
        assert r.json()["salvo"] is False and "Outra pessoa" in r.json()["mensagem"]
        planos.cancelar(c.usuarios["operador"], plano.pk, "Adiado")
        r = _cliente(c.usuarios["operador"]).post(url, {})
        assert r.json()["salvo"] is False

    def test_lista_abas_busca_e_permissoes(self, c):
        op = c.usuarios["operador"]
        futuro = _completo(c)
        sem_data, _ = planos.salvar(op, programa_outros="Avulso sem data")
        cli = _cliente(op)
        html = cli.get(reverse("viagens:planos") + "?aba=futuros").content.decode()
        assert str(futuro) in html and str(sem_data) in html
        html = cli.get(reverse("viagens:planos") + "?q=Maringá").content.decode()
        assert str(futuro) in html and str(sem_data) not in html
        num = f"{futuro.numero}/{futuro.ano}"
        assert str(futuro) in cli.get(reverse("viagens:planos") + f"?q={num}").content.decode()
        assert _cliente(c.usuarios["outra"]).get(
            reverse("viagens:editar_plano", args=[futuro.pk])).status_code == 403
        assert _cliente(c.usuarios["consulta"]).get(
            reverse("viagens:folha_plano", args=[futuro.pk])).status_code == 403

    def test_documento_pdf_docx_e_previa(self, c):
        plano = _completo(c)
        cli = _cliente(c.usuarios["operador"])
        r = cli.get(reverse("viagens:documento_plano", args=[plano.pk, "pdf"]) + "?previa=1")
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
        plano.refresh_from_db()
        assert plano.documento_gerado_em is None
        # Sem "Finalizar e gerar", o GET não gera (nem por link de fora): volta à folha.
        r = cli.get(reverse("viagens:documento_plano", args=[plano.pk, "docx"]))
        assert r.status_code == 302
        plano.refresh_from_db()
        assert plano.documento_gerado_em is None
        planos.finalizar(c.usuarios["operador"], plano.pk)
        r = cli.get(reverse("viagens:documento_plano", args=[plano.pk, "docx"]))
        assert r.status_code == 200 and "attachment" in r["Content-Disposition"]

    def test_criar_do_oficio_e_janela_do_oficio(self, c):
        oficio = _oficio(c)
        cli = _cliente(c.usuarios["operador"])
        html = cli.get(reverse("viagens:oficios") + f"?resumo={oficio.pk}").content.decode()
        assert reverse("viagens:criar_plano_do_oficio", args=[oficio.pk]) in html
        r = cli.post(reverse("viagens:criar_plano_do_oficio", args=[oficio.pk]))
        plano = PlanoTrabalho.objects.get()
        assert r["Location"] == reverse("viagens:editar_plano", args=[plano.pk])

    def test_consultas_da_lista_nao_crescem(self, c, django_assert_max_num_queries):
        for _ in range(3):
            _completo(c)
        cli = _cliente(c.usuarios["operador"])
        cli.get(reverse("viagens:planos"))
        with django_assert_max_num_queries(30):
            cli.get(reverse("viagens:planos"))
        for _ in range(5):
            _completo(c, data_inicio=date(2030, 7, 2), data_fim=date(2030, 7, 3))
        with django_assert_max_num_queries(30):
            cli.get(reverse("viagens:planos"))



class TestRevisoes:
    def _post_da_tela(self, plano, **extra):
        """O que a folha enviaria (o formulário do plano como está)."""
        from gestao.viagens.forms import FormularioPlano
        inicial = FormularioPlano.de(plano).initial
        dados = {k: v for k, v in inicial.items() if v not in (None, "")}
        dados["destinos"] = inicial["destinos"]
        dados["coordenador_adm"] = plano.coordenador_adm_id or ""
        dados["data_inicio"] = plano.data_inicio.strftime("%d/%m/%Y") if plano.data_inicio else ""
        dados["data_fim"] = plano.data_fim.strftime("%d/%m/%Y") if plano.data_fim else ""
        for campo in ("saida_em", "chegada_em"):
            valor = getattr(plano, campo)
            if valor:
                local = timezone.localtime(valor)
                dados[f"{campo}_0"], dados[f"{campo}_1"] = f"{local:%d/%m/%Y}", f"{local:%H:%M}"
                dados.pop(campo, None)
        dados["efetivo_presente"] = "1"
        dados["efetivo_unidade"] = [str(e.unidade_id or "") for e in plano.efetivo.all()]
        dados["efetivo_cargo"] = [str(e.cargo_id) for e in plano.efetivo.all()]
        dados["efetivo_quantidade"] = [str(e.quantidade) for e in plano.efetivo.all()]
        dados["atividades_presente"] = "1"
        dados["atividades"] = [str(a.pk) for a in plano.atividades.all()]
        dados.update(extra)
        return dados

    def test_enter_salva_o_primeiro_botao_e_salvar(self, c):
        plano = _completo(c)
        html = _cliente(c.usuarios["operador"]).get(
            reverse("viagens:editar_plano", args=[plano.pk])).content.decode()
        formulario = html[html.index('id="form-plano"'):]
        primeiro = formulario[formulario.index("<button"):formulario.index("</button>")]
        assert "formaction" not in primeiro and "Salvar" in primeiro

    def test_finalizar_grava_o_que_esta_na_tela(self, c):
        plano = _completo(c)
        cli = _cliente(c.usuarios["operador"])
        r = cli.post(reverse("viagens:finalizar_plano", args=[plano.pk]),
                     self._post_da_tela(plano, horario="10:00 até 18:00"))
        assert r.status_code == 302
        plano.refresh_from_db()
        assert plano.horario == "10:00 até 18:00" and plano.documento_gerado_em is not None

    def test_aba_velha_depois_de_gerar_nao_apaga_a_data(self, c):
        plano = _completo(c)
        aberta = planos.versao_de(plano)
        planos.finalizar(c.usuarios["operador"], plano.pk)
        plano.refresh_from_db()
        assert planos.versao_de(plano) != aberta  # gerar toca a versão
        r = _cliente(c.usuarios["operador"]).post(
            reverse("viagens:autosave_plano", args=[plano.pk]),
            self._post_da_tela(plano, versao=aberta, data_documento=""))
        assert r.json()["salvo"] is False and "Outra pessoa" in r.json()["mensagem"]
        planos.salvar(c.usuarios["operador"], pk=plano.pk, data_documento=None,
                      destinos=[d.municipio for d in plano.destinos.all()])
        plano.refresh_from_db()
        assert plano.data_documento is not None  # em branco não apaga a data fixada

    def test_cargo_desativado_continua_na_linha(self, c):
        plano = _completo(c)
        Cargo.objects.filter(nome="Agente de Polícia Judiciária").update(ativo=False)
        r = _cliente(c.usuarios["operador"]).post(
            reverse("viagens:autosave_plano", args=[plano.pk]), self._post_da_tela(plano))
        assert r.json()["salvo"] is True
        assert PlanoTrabalho.objects.get(pk=plano.pk).efetivo.count() == 1

    def test_linhas_demais_recusadas(self, c):
        plano = _completo(c)
        agente = Cargo.objects.get(nome="Agente de Polícia Judiciária")
        r = _cliente(c.usuarios["operador"]).post(
            reverse("viagens:autosave_plano", args=[plano.pk]),
            self._post_da_tela(plano, efetivo_unidade=[""] * 60,
                               efetivo_cargo=[str(agente.pk)] * 60,
                               efetivo_quantidade=["1"] * 60))
        assert r.json()["salvo"] is False and "No máximo 50 linhas" in r.json()["mensagem"]

    def test_outra_unidade_nao_alcanca_nenhuma_rota(self, c):
        plano = _completo(c)
        outra = _cliente(c.usuarios["outra"])
        for nome, args, metodo in (
                ("autosave_plano", [plano.pk], "post"), ("finalizar_plano", [plano.pk], "post"),
                ("documento_plano", [plano.pk, "pdf"], "get"),
                ("cancelar_plano", [plano.pk], "post"), ("reativar_plano", [plano.pk], "post"),
                ("excluir_plano", [plano.pk], "post")):
            r = getattr(outra, metodo)(reverse(f"viagens:{nome}", args=args))
            assert r.status_code == 403, nome
        oficio = _oficio(c)
        r = outra.post(reverse("viagens:criar_plano_do_oficio", args=[oficio.pk]))
        assert r.status_code in (403, 404)

    def test_conjunto_padrao_gravado_ao_criar_do_oficio(self, c):
        cin = AtividadePlano.objects.get(codigo="CIN")
        preset = PresetAtividades.objects.create(nome="PADRÃO", padrao=True)
        preset.atividades.add(cin)
        plano, _ = planos.salvar(c.usuarios["operador"], oficios=[_oficio(c)])
        assert list(plano.atividades.all()) == [cin] and plano.metas

    def test_tratamento_do_coordenador_padrao_vem_da_configuracao(self, c):
        coord = Servidor.objects.first()
        ConfiguracaoInstitucional.objects.filter(unidade__sigla="ASCOM").update(
            coordenador_plano=coord, coordenador_plano_genero="F")
        plano, _ = planos.salvar(c.usuarios["operador"])
        assert plano.coordenador_adm_genero == "F"
        assert "Coordenadora Administrativa" in plano.coordenacao



class TestVariosEventos:
    def _sarandi(self):
        return Municipio.objects.get(nome="Sarandi", uf="PR")

    def test_evento_adicional_entra_nos_textos_e_no_documento(self, c):
        op = c.usuarios["operador"]
        plano = _completo(c)
        bo = AtividadePlano.objects.get(codigo="BO")
        outro = ProgramaSolicitante.objects.get(nome="PROGRAMA JUSTIÇA NO BAIRRO")
        planos.salvar_evento(op, plano.pk, programa=outro, data_inicio=date(2030, 6, 27),
                             destinos=[self._sarandi()], atividades=[bo])
        plano = PlanoTrabalho.objects.get(pk=plano.pk)
        assert "Maringá/PR, Sarandi/PR" in plano.contextualizacao
        assert "Programa Justiça no Bairro" in plano.contextualizacao
        assert plano.coordenacao.count("Fica designad") == 1  # só o administrativo
        assert planos.periodo_geral(plano) == (date(2030, 6, 25), date(2030, 6, 27))
        evento = plano.eventos.get()
        assert evento.atividades_texto == "• Registro de Boletins de Ocorrência"
        planos.finalizar(op, plano.pk)
        plano.refresh_from_db()
        html = planos.html_do_documento(planos.dados_do_documento(plano))
        assert "Dias 25 a 27 de junho de 2030 - PROGRAMA PARANÁ EM AÇÃO:" in html
        assert "Dia 27 de junho de 2030 - PROGRAMA JUSTIÇA NO BAIRRO:" in html
        assert "Valor total do evento dias: 25 a 27/06/2030:" in html
        assert "<strong>Datas:</strong>" not in html  # a data vai no título de cada evento

    def test_pendencias_do_evento_e_remover_volta_a_um_evento(self, c):
        op = c.usuarios["operador"]
        plano = _completo(c)
        evento = planos.salvar_evento(op, plano.pk)
        plano = PlanoTrabalho.objects.get(pk=plano.pk)
        assert [p.mensagem for p in planos.pendencias(plano)] == [
            "Informe o destino do evento 2.", "Informe a data do evento 2."]
        planos.remover_evento(op, plano.pk, evento.pk)
        plano = PlanoTrabalho.objects.get(pk=plano.pk)
        assert planos.pendencias(plano) == [] and not plano.eventos.exists()
        assert "Coordenador Administrativo" in plano.coordenacao

    def test_janela_do_evento_pela_tela(self, c):
        plano = _completo(c)
        cli = _cliente(c.usuarios["operador"])
        url = reverse("viagens:editar_plano", args=[plano.pk])
        html = cli.get(url + "?evento=novo").content.decode()
        assert 'id="dialogo-evento"' in html and 'id="evento_data_inicio"' in html
        r = cli.post(reverse("viagens:salvar_evento_plano", args=[plano.pk]), {
            "programa": "outro", "programa_outros": "Feira fictícia", "data_inicio": "28/06/2030",
            "destinos": ["Sarandi/PR"], "horario": "09:00 até 17:00"})
        assert r["Location"].endswith("#eventos")
        evento = plano.eventos.get()
        assert evento.programa_outros == "Feira fictícia"
        html = cli.get(url).content.decode()
        assert "Evento" in html and "Sarandi/PR" in html and "2 eventos" in html
        r = cli.post(reverse("viagens:salvar_evento_plano", args=[plano.pk]), {
            "evento": str(evento.pk), "data_inicio": "29/06/2030", "data_fim": "28/06/2030"})
        assert r.status_code == 422 and "anterior à data inicial" in r.content.decode()
        cli.post(reverse("viagens:remover_evento_plano", args=[plano.pk, evento.pk]))
        assert not plano.eventos.exists()

    def test_evento_de_outra_unidade_nem_cancelado(self, c):
        plano = _completo(c)
        r = _cliente(c.usuarios["outra"]).post(
            reverse("viagens:salvar_evento_plano", args=[plano.pk]), {})
        assert r.status_code == 403
        planos.cancelar(c.usuarios["operador"], plano.pk, "Adiado")
        with pytest.raises(PermissionDenied):
            planos.salvar_evento(c.usuarios["operador"], plano.pk)
