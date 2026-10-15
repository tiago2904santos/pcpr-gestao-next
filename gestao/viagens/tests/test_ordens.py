"""Ordens de Serviço (módulo 5). Paridade com `viagens_ordens` da referência: numeração
anual com lacunas, cópia do ofício, tipos com função, cancelar/reativar/excluir (libera o
número), documento com o texto do tipo. Dados fictícios."""

from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import ConfiguracaoInstitucional, Municipio, Servidor
from gestao.viagens import ordens
from gestao.viagens.models import ModeloOS, Oficio, OrdemServico

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    return cenario_completo()


def _modelo(chave: str) -> ModeloOS:
    return ModeloOS.objects.get(chave=chave)


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

    def test_o_preenchido_fica_e_o_oficio_soma(self, c):
        # Ligar o ofício une a equipe dele à que já está na OS; o motivo escrito fica.
        um = Servidor.objects.first()
        oficio = _oficio(c)
        ordem, copiados = ordens.salvar(c.usuarios["operador"], oficios=[oficio],
                                        servidores=[um], motivo="Motivo próprio")
        assert set(ordem.servidores.all()) == {um} | {v.servidor for v in oficio.viajantes.all()}
        assert ordem.motivo == "Motivo próprio" and "motivo" not in copiados

    def test_oficio_de_outra_unidade_nao_entra(self, c):
        outra = Oficio.objects.get(pk=c.ids["oficio_outra_unidade"])
        with pytest.raises((PermissionDenied, ordens.OrdemInvalida)):
            ordens.salvar(c.usuarios["gestor"], oficios=[outra])


class TestFuncoesEDocumento:
    def test_funcoes_so_nos_tipos_que_usam_e_validas(self, c):
        um, dois = Servidor.objects.all()[:2]
        op = c.usuarios["operador"]
        ordem, _ = ordens.salvar(op, modelo=_modelo("unidade_movel"), servidores=[um, dois],
                                 destinos=[_londrina()],
                                 funcoes={str(um.pk): "conducao", "999999": "apoio"})
        assert ordem.funcoes == {str(um.pk): "conducao"}  # quem não está na equipe sai
        with pytest.raises(ordens.OrdemInvalida, match="função válida"):
            ordens.salvar(op, pk=ordem.pk, modelo=_modelo("unidade_movel"), servidores=[um],
                          funcoes={str(um.pk): "coordenacao"})
        padrao, _ = ordens.salvar(op, servidores=[um],
                                  funcoes={str(um.pk): "conducao"})
        assert padrao.funcoes == {}

    def test_documento_com_texto_do_tipo_assinatura_e_data_fixada(self, c):
        um = Servidor.objects.first()
        config = ConfiguracaoInstitucional.objects.get(unidade__sigla="ASCOM")
        config.delegado_geral_nome = "Delegado-Geral Fictício"
        config.save()
        ordem, _ = ordens.salvar(c.usuarios["operador"], modelo=_modelo("unidade_movel"),
                                 servidores=[um], destinos=[_londrina()],
                                 data_inicio=date(2030, 3, 10), motivo="o evento fictício",
                                 funcoes={str(um.pk): "conducao"})
        dados = ordens.dados_do_documento(ordem)
        assert dados["referencia"] == "Deslocamento - Unidade Móvel"
        assert dados["itens"][0][0] == "I"
        assert dados["itens"][0][1].startswith("O deslocamento d")
        assert f"{um.nome}, na função de condutor da Unidade Móvel" in dados["itens"][0][1]
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

    def test_salvar_sem_assinante_mantem_o_gravado(self, c):
        # A tela não manda mais quem assina (módulo próprio): o autosave não pode apagá-lo.
        um, dois = Servidor.objects.all()[:2]
        ordem, _ = ordens.salvar(c.usuarios["operador"], servidores=[um],
                                 destinos=[_londrina()], assinante=dois)
        ordem, _ = ordens.salvar(c.usuarios["operador"], pk=ordem.pk, servidores=[um],
                                 destinos=[_londrina()], motivo="novo motivo")
        ordem.refresh_from_db()
        assert ordem.assinante_id == dois.pk

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
        assert "Recebe o número" in html
        r = cli.post(reverse("viagens:nova_ordem"), {
            "destinos": ["Londrina/PR"], "data_inicio": "10/03/2030",
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

    def test_funcao_se_escolhe_no_cartao_da_equipe(self, c):
        um = Servidor.objects.first()
        ordem, _ = ordens.salvar(c.usuarios["operador"], modelo=_modelo("cerimonial"),
                                 servidores=[um], destinos=[_londrina()])
        cli = _cliente(c.usuarios["operador"])
        html = cli.get(reverse("viagens:editar_ordem", args=[ordem.pk])).content.decode()
        assert f'name="funcao_{um.pk}"' in html and "Coordenação" in html
        # O seletor fica no cartão da pessoa (rádios), com as opções do tipo.
        assert 'class="funcao-escolha"' in html and 'value="preparacao"' in html
        assert "Função de cada um" not in html
        # Quem acabou de entrar na equipe já leva a função, sem gravar a equipe antes.
        outro = Servidor.objects.exclude(pk=um.pk).first()
        cli.post(reverse("viagens:editar_ordem", args=[ordem.pk]), {
            "modelo": _modelo("cerimonial").pk, "destinos": ["Londrina/PR"],
            "servidores": [um.pk, outro.pk], f"funcao_{um.pk}": "coordenacao",
            f"funcao_{outro.pk}": "apoio"})
        ordem.refresh_from_db()
        assert ordem.funcoes == {str(um.pk): "coordenacao", str(outro.pk): "apoio"}

    def test_campos_de_evento_e_hora_so_com_modelo(self, c):
        op = c.usuarios["operador"]
        cli = _cliente(op)
        padrao, _ = ordens.salvar(op, destinos=[_londrina()])
        html = cli.get(reverse("viagens:editar_ordem", args=[padrao.pk])).content.decode()
        # O período do evento não se digita: vem da viagem (ordens.evento_do_vinculo).
        assert "data-campo-evento" not in html and "Período do evento" not in html
        assert "data-campo-hora hidden>" in html  # a coluna Briefing do cartão do período
        assert "OS padrão" in html and "Unidade móvel" in html
        policial, _ = ordens.salvar(op, modelo=_modelo("operacao_policial"),
                                    destinos=[_londrina()], hora=time(5, 0))
        html = cli.get(reverse("viagens:editar_ordem", args=[policial.pk])).content.decode()
        assert 'class="briefing" data-campo-hora>' in html
        assert 'name="hora"' in html and 'value="05:00"' in html
        assert "pede o horário do briefing" in html
        # Tipo desativado no banco continua selecionado e a OS continua gravando.
        ModeloOS.objects.filter(chave="operacao_policial").update(ativo=False)
        html = cli.get(reverse("viagens:editar_ordem", args=[policial.pk])).content.decode()
        assert "Operação policial" in html
        r = cli.post(reverse("viagens:autosave_ordem", args=[policial.pk]), {
            "modelo": _modelo("operacao_policial").pk, "destinos": ["Londrina/PR"],
            "hora": "06:30", "motivo": "x"})
        assert r.json()["salvo"] is True
        policial.refresh_from_db()
        assert policial.hora == time(6, 30)

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

    def test_evento_vem_da_viagem_do_oficio_e_acompanha_a_viagem(self, c):
        from gestao.viagens.models import Viagem
        oficio = _oficio(c)
        viagem = Viagem.objects.create(unidade=oficio.unidade, titulo="Feira (teste)",
                                       data_inicio=date(2030, 5, 5), data_fim=date(2030, 5, 6),
                                       criado_por=c.usuarios["operador"])
        Oficio.objects.filter(pk=oficio.pk).update(viagem=viagem)
        oficio.refresh_from_db()
        op = c.usuarios["operador"]
        ordem, copiados = ordens.salvar(op, oficios=[oficio], modelo=_modelo("unidade_movel"),
                                        data_inicio=date(2030, 5, 3), data_fim=date(2030, 5, 8))
        assert (ordem.data_evento_inicio, ordem.data_evento_fim) == (date(2030, 5, 5),
                                                                     date(2030, 5, 6))
        # Não é cópia que a tela precise mostrar: vem do vínculo, sem recarregar.
        assert "período do evento" not in copiados
        # A viagem mudou de data: a próxima gravação da OS acompanha.
        Viagem.objects.filter(pk=viagem.pk).update(data_inicio=date(2030, 5, 6),
                                                   data_fim=date(2030, 5, 6))
        oficio.refresh_from_db()  # como numa requisição nova
        ordem, _ = ordens.salvar(op, pk=ordem.pk, oficios=[oficio], modelo=_modelo("unidade_movel"),
                                 data_inicio=date(2030, 5, 3), data_fim=date(2030, 5, 8))
        assert (ordem.data_evento_inicio, ordem.data_evento_fim) == (date(2030, 5, 6),
                                                                     date(2030, 5, 6))

    def test_os_criada_na_viagem_usa_o_evento_dela_sem_gravar_antes(self, c):
        from gestao.viagens.models import Viagem
        op = c.usuarios["operador"]
        viagem = Viagem.objects.create(unidade=Oficio.objects.get(
            pk=c.ids["oficio_emitido"]).unidade, titulo="Solenidade (teste)",
            data_inicio=date(2030, 5, 6), data_fim=date(2030, 5, 6), criado_por=op)
        um = Servidor.objects.first()
        ordem, _ = ordens.salvar(op, modelo=_modelo("cerimonial"), destinos=[_londrina()],
                                 data_inicio=date(2030, 5, 4), data_fim=date(2030, 5, 7),
                                 servidores=[um], motivo="a solenidade",
                                 funcoes={str(um.pk): "coordenacao"})
        OrdemServico.objects.filter(pk=ordem.pk).update(viagem=viagem)  # como em viagem.py
        ordem = OrdemServico.objects.get(pk=ordem.pk)
        textos = [t for _, t in ordens.dados_do_documento(ordem, fixar=False)["itens"]]
        # Saída 4, evento 6: dia 4 deslocamento, dia 5 visita técnica.
        assert "no dia 4 de maio de 2030" in textos[1]
        assert textos[2].startswith("Que a equipe realize no dia 5 de maio de 2030 a visita "
                                    "técnica")

    def test_evento_fora_do_periodo_e_recusado(self, c):
        with pytest.raises(ordens.OrdemInvalida, match="caber"):
            ordens.salvar(c.usuarios["operador"], modelo=_modelo("unidade_movel"),
                          data_inicio=date(2030, 5, 4), data_fim=date(2030, 5, 7),
                          data_evento_inicio=date(2030, 5, 2), data_evento_fim=date(2030, 5, 3))

    def test_modelo_desativado_so_fica_em_quem_ja_tinha(self, c):
        op = c.usuarios["operador"]
        modelo = _modelo("unidade_movel")
        ordem, _ = ordens.salvar(op, modelo=modelo, destinos=[_londrina()])
        ModeloOS.objects.filter(pk=modelo.pk).update(ativo=False)
        modelo.refresh_from_db()
        ordens.salvar(op, pk=ordem.pk, modelo=modelo, destinos=[_londrina()])  # continua
        with pytest.raises(ordens.OrdemInvalida, match="desativado"):
            ordens.salvar(op, modelo=modelo, destinos=[_londrina()])

    def test_dois_na_mesma_funcao_vao_para_o_plural(self, c):
        um, dois = Servidor.objects.all()[:2]
        for chave, plural in (("unidade_movel", "na função de condutores da Unidade Móvel, "
                                                "responsáveis pelo deslocamento"),):
            ordem, _ = ordens.salvar(
                c.usuarios["operador"], modelo=_modelo(chave), destinos=[_londrina()],
                data_inicio=date(2030, 5, 3), data_fim=date(2030, 5, 3),
                servidores=[um, dois], motivo="a Feira",
                funcoes={str(um.pk): "conducao", str(dois.pk): "conducao"})
            textos = [t for _, t in ordens.dados_do_documento(ordem, fixar=False)["itens"]]
            assert plural in textos[0], chave
            assert um.nome in textos[0] and dois.nome in textos[0]  # cada um com o cargo
        ordem, _ = ordens.salvar(
            c.usuarios["operador"], modelo=_modelo("cerimonial"), destinos=[_londrina()],
            data_inicio=date(2030, 5, 3), servidores=[um, dois], motivo="a solenidade",
            funcoes={str(um.pk): "apoio", str(dois.pk): "apoio"})
        textos = [t for _, t in ordens.dados_do_documento(ordem, fixar=False)["itens"]]
        assert " prestem apoio às atividades de Cerimonial" in textos[0]

    def test_documento_da_unidade_movel_sai_em_itens(self, c):
        um, dois = Servidor.objects.all()[:2]
        ordem, _ = ordens.salvar(
            c.usuarios["operador"], modelo=_modelo("unidade_movel"), destinos=[_londrina()],
            data_inicio=date(2030, 5, 3), data_fim=date(2030, 5, 8),
            data_evento_inicio=date(2030, 5, 5), data_evento_fim=date(2030, 5, 6),
            servidores=[um, dois], motivo="a Feira",
            funcoes={str(um.pk): "conducao", str(dois.pk): "apoio"})
        dados = ordens.dados_do_documento(ordem, fixar=False)
        numeros = [n for n, _ in dados["itens"]]
        assert numeros == ["I", "II", "III", "IV", "V", "VI", "VII"]
        textos = [t for _, t in dados["itens"]]
        # Depois do DETERMINO: o deslocamento de cada um com a sua função…
        assert textos[0].startswith("O deslocamento d") and "na função de condutor " in textos[0]
        assert "na função de apoio, responsável pela escolta" in textos[1]
        # …e os dias: deslocamento, montagem, evento, desmontagem e volta à sede.
        assert textos[2] == ("Que a equipe realize no dia 3 de maio de 2030 o deslocamento até "
                             "o município de Londrina/PR, para apoio logístico com a Unidade "
                             "Móvel em a Feira.")
        assert textos[3].startswith("Que a equipe realize no dia 4 de maio de 2030 a montagem")
        assert textos[4].startswith("Que a equipe participe nos dias 5 e 6 de maio de 2030 do "
                                    "evento")
        assert textos[5].startswith("Que a equipe realize no dia 7 de maio de 2030 a "
                                    "desmontagem")
        assert textos[6] == ("Que a equipe realize no dia 8 de maio de 2030 o deslocamento de "
                             "volta à sede de lotação em Curitiba/PR.")
        assert dados["justificativas"] and dados["finalidade"]
        html = ordens.html_do_modelo(dados)
        assert '<ol class="itens">' in html and "I - Que" in html and "DETERMINO" in html
        assert ordens.faltando(ordem) == []

    def test_operacao_policial_com_hora(self, c):
        um = Servidor.objects.first()
        op = c.usuarios["operador"]
        ordem, _ = ordens.salvar(
            op, modelo=_modelo("operacao_policial"), destinos=[_londrina()],
            data_inicio=date(2030, 9, 17), data_fim=date(2030, 9, 19),
            data_evento_inicio=date(2030, 9, 18), servidores=[um], motivo="a operação")
        assert "horário do briefing" in ordens.faltando(ordem)
        ordem, _ = ordens.salvar(
            op, pk=ordem.pk, modelo=_modelo("operacao_policial"), destinos=[_londrina()],
            data_inicio=date(2030, 9, 17), data_fim=date(2030, 9, 19),
            data_evento_inicio=date(2030, 9, 18), servidores=[um], motivo="a operação",
            hora=time(5, 0))
        assert "horário do briefing" not in ordens.faltando(ordem)
        textos = [t for _, t in ordens.dados_do_documento(ordem, fixar=False)["itens"]]
        # Ida, briefing, permanência no dia da operação e volta (a OS real).
        assert len(textos) == 4
        assert "às 05h00min do dia 18 de setembro de 2030" in textos[1]
        assert "durante todo o dia 18 de setembro de 2030" in textos[2]
        assert textos[3].startswith("Que o policial efetue o retorno")

    def test_tipo_com_funcao_sem_funcao_e_sinalizado(self, c):
        ordem, _ = ordens.salvar(c.usuarios["operador"], modelo=_modelo("unidade_movel"),
                                 servidores=[Servidor.objects.first()], destinos=[_londrina()],
                                 data_inicio=date(2030, 1, 1), motivo="x")
        assert ordens.faltando(ordem) == ["função da equipe"]

    def test_data_do_documento_fica_quando_a_tela_nao_a_envia(self, c):
        # A tela não tem o campo: a data fixada (na 1ª geração) não se perde a cada gravação.
        op = c.usuarios["operador"]
        ordem, _ = ordens.salvar(op, destinos=[_londrina()], data_documento=date(2030, 1, 1))
        ordem, _ = ordens.salvar(op, pk=ordem.pk, destinos=[_londrina()])
        assert ordem.data_documento == date(2030, 1, 1)
        ordem, _ = ordens.salvar(op, pk=ordem.pk, destinos=[_londrina()], data_documento=None)
        assert ordem.data_documento is None

    def test_documento_sem_cache(self, c):
        ordem, _ = ordens.salvar(c.usuarios["operador"], destinos=[_londrina()])
        r = _cliente(c.usuarios["operador"]).get(
            reverse("viagens:documento_ordem", args=[ordem.pk, "pdf"]))
        assert r["Cache-Control"] == "no-store"


def test_os_so_junta_oficios_da_mesma_acao(c):
    from gestao.viagens import viagem
    op = c.usuarios["operador"]
    o1 = Oficio.objects.get(pk=c.ids["oficio_emitido"])
    o2 = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    with pytest.raises(ordens.OrdemInvalida, match="mesma viagem ou usar o mesmo roteiro"):
        ordens.salvar(op, oficios=[o1, o2])
    Oficio.objects.filter(pk__in=[o1.pk, o2.pk]).update(viagem=viagem.criar(op))
    o1.refresh_from_db()
    o2.refresh_from_db()
    ordem, copiados = ordens.salvar(op, oficios=[o1])
    # Ligar o segundo une o que ele traz ao que a OS já tem.
    antes = set(ordem.servidores.all())
    ordem, copiados = ordens.salvar(op, pk=ordem.pk, oficios=[o1, o2],
                                    destinos=[m.municipio for m in ordem.destinos.all()],
                                    data_inicio=ordem.data_inicio, data_fim=ordem.data_fim,
                                    servidores=list(antes), motivo=ordem.motivo)
    assert antes < set(ordem.servidores.all()) and "equipe" in copiados


def test_duplicar_e_finalizar_a_os(c):
    op = c.usuarios["operador"]
    ordem, _ = ordens.salvar(op, destinos=[_londrina()], motivo="Motivo de teste",
                             servidores=[Servidor.objects.first()])
    cli = _cliente(op)
    r = cli.post(reverse("viagens:duplicar_ordem", args=[ordem.pk]))
    nova = OrdemServico.objects.exclude(pk=ordem.pk).get()
    assert r["Location"] == reverse("viagens:editar_ordem", args=[nova.pk])
    assert nova.numero != ordem.numero and nova.motivo == "Motivo de teste"
    assert list(nova.servidores.all()) == list(ordem.servidores.all())
    r = cli.post(reverse("viagens:finalizar_ordem", args=[ordem.pk]))
    ordem.refresh_from_db()
    assert r["Location"] == reverse("viagens:ordens") and ordem.documento_gerado_em is not None
