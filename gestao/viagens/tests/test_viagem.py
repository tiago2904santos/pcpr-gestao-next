"""Viagem (módulo 8a): criar (reaproveitando a vazia esquecida), dados da etapa 1, título
dos tipos, destinos, vínculos, documentos da viagem, novo documento já vinculado, lista e
permissões (paridade com viagens_viagem da referência)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio, TipoViagem
from gestao.viagens import ordens, termos, viagem
from gestao.viagens.models import Oficio, OrdemServico, TermoAutorizacao, Viagem

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    cen = cenario_completo()
    TipoViagem.objects.create(nome="PCPR na Comunidade")
    TipoViagem.objects.create(nome="Unidade Móvel")
    return cen


def _cliente(usuario) -> Client:
    cli = Client()
    cli.force_login(usuario)
    return cli


def _londrina():
    return Municipio.objects.get(nome="Londrina", uf="PR")


def test_titulo_nasce_dos_tipos():
    assert viagem.titulo_dos_tipos(["PCPR na Comunidade", "Unidade Móvel"]) == (
        "PCPR na Comunidade / Unidade Móvel")
    assert viagem.titulo_dos_tipos([]) == ""


def test_criar_reaproveita_a_vazia(c):
    """A vazia da mesma pessoa volta na hora (dois cliques não deixam lixo); a de outra
    pessoa da unidade, só depois de 30 minutos esquecida (referência)."""
    op, gestor = c.usuarios["operador"], c.usuarios["gestor"]
    primeira = viagem.criar(op)
    assert viagem.criar(op).pk == primeira.pk
    assert viagem.criar(gestor).pk != primeira.pk
    Viagem.objects.filter(pk=primeira.pk).update(
        atualizado_em=timezone.now() - timedelta(hours=1))
    assert viagem.criar(gestor).pk == primeira.pk


def test_salvar_dados_titulo_destinos_e_vinculos(c):
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    oficio = Oficio.objects.get(pk=c.ids["oficio_emitido"])
    tipos = list(TipoViagem.objects.order_by("nome"))
    hoje = timezone.localdate()
    salva = viagem.salvar_dados(op, v.pk, tipos=tipos, motivo="Ação na feira",
                                data_inicio=hoje, data_fim=hoje + timedelta(days=2),
                                destinos=[_londrina()], vinculos={"oficios": [oficio]})
    assert salva.titulo == "PCPR na Comunidade / Unidade Móvel"
    assert [d.municipio for d in salva.destinos.all()] == [_londrina()]
    oficio.refresh_from_db()
    assert oficio.viagem_id == v.pk
    docs = viagem.documentos(salva)
    assert docs.oficios == [oficio] and docs.total >= 1
    # Desmarcar solta.
    viagem.salvar_dados(op, v.pk, tipos=tipos, vinculos={"oficios": []})
    oficio.refresh_from_db()
    assert oficio.viagem_id is None


def test_periodo_invertido_e_versao_antiga(c):
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    with pytest.raises(viagem.ViagemInvalida, match="não pode ser anterior"):
        viagem.salvar_dados(op, v.pk, tipos=[], data_inicio=date(2030, 1, 5),
                            data_fim=date(2030, 1, 1))
    with pytest.raises(viagem.ViagemInvalida, match="Outra pessoa alterou"):
        viagem.salvar_dados(op, v.pk, tipos=[], versao="2000-01-01T00:00:00")


def test_nao_vincula_documento_de_outra_unidade_ou_de_outra_viagem(c):
    op = c.usuarios["operador"]
    v, outra = viagem.criar(op), viagem.criar(op)
    alheio = Oficio.objects.get(pk=c.ids["oficio_outra_unidade"])
    meu = Oficio.objects.get(pk=c.ids["oficio_emitido"])
    viagem.salvar_dados(op, outra.pk, tipos=[], vinculos={"oficios": [meu]})
    viagem.salvar_dados(op, v.pk, tipos=[], vinculos={"oficios": [alheio, meu]})
    alheio.refresh_from_db()
    meu.refresh_from_db()
    assert alheio.viagem_id is None and meu.viagem_id == outra.pk


def test_termo_pelo_oficio_conta_como_da_viagem(c):
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    oficio = Oficio.objects.get(pk=c.ids["oficio_emitido"])
    termo = termos.salvar(op, oficio=oficio)
    viagem.salvar_dados(op, v.pk, tipos=[], vinculos={"oficios": [oficio]})
    assert termo in viagem.documentos(Viagem.objects.get(pk=v.pk)).termos


def test_novo_documento_ja_vinculado_e_semeado(c):
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    hoje = timezone.localdate()
    viagem.salvar_dados(op, v.pk, tipos=list(TipoViagem.objects.filter(nome="Unidade Móvel")),
                        motivo="cobertura da feira", data_inicio=hoje, destinos=[_londrina()])
    ordem = viagem.novo_documento(op, v.pk, "ordem")
    assert isinstance(ordem, OrdemServico)
    ordem = OrdemServico.objects.get(pk=ordem.pk)
    assert ordem.viagem_id == v.pk and ordem.data_inicio == hoje
    assert ordem.motivo == "cobertura da feira"
    termo = viagem.novo_documento(op, v.pk, "termo")
    assert TermoAutorizacao.objects.get(pk=termo.pk).viagem_id == v.pk
    oficio = viagem.novo_documento(op, v.pk, "oficio")
    assert Oficio.objects.get(pk=oficio.pk).motivo == "cobertura da feira"
    assert viagem.novo_documento(op, v.pk, "roteiro").viagem_id == v.pk
    assert viagem.novo_documento(op, v.pk, "plano").viagem_id == v.pk
    salva = Viagem.objects.get(pk=v.pk)
    assert viagem.documentos(salva).total == 5
    assert salva.situacao == Viagem.Situacao.PREPARACAO  # com documentos
    assert TermoAutorizacao.objects.get(pk=termo.pk).evento == "Unidade Móvel"


def test_termo_sem_periodo_ou_destino_avisa(c):
    v = viagem.criar(c.usuarios["operador"])
    with pytest.raises(viagem.ViagemInvalida, match="Informe o tipo, o período e o destino"):
        viagem.novo_documento(c.usuarios["operador"], v.pk, "termo")


def test_tela_lista_busca_e_abas(c):
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    viagem.salvar_dados(op, v.pk, tipos=list(TipoViagem.objects.filter(nome="Unidade Móvel")),
                        data_inicio=timezone.localdate() + timedelta(days=5),
                        destinos=[_londrina()])
    cli = _cliente(op)
    html = cli.get(reverse("viagens:viagens")).content.decode()
    # Rascunho a 5 dias: o tempo vira o selo de urgência ("sai em 5 dias · gerar…").
    assert "Unidade Móvel · Londrina/PR" in html and "sai em 5 dias" in html
    achadas = cli.get(reverse("viagens:viagens"), {"q": "londrina"}).content.decode()
    assert "Unidade Móvel" in achadas
    assert "Nenhuma viagem encontrada" in cli.get(reverse("viagens:viagens"),
                                                  {"aba": "atuais"}).content.decode()


def test_criar_pela_tela_e_folha(c):
    cli = _cliente(c.usuarios["operador"])
    r = cli.post(reverse("viagens:nova_viagem"))
    v = Viagem.objects.get()
    assert r["Location"] == reverse("viagens:editar_viagem", args=[v.pk])
    html = cli.get(r["Location"]).content.decode()
    assert "Identificação" in html and "Documentos da viagem" in html
    assert "Falta o tipo" in html and "A equipe e a solicitação da viagem." in html
    assert html.count('class="viagem-docs__vazio"') == 5
    assert html.index('id="documentos"') < html.index('id="vinculos"')


def test_lista_paginada_preserva_busca_abas_e_criacao_post(c):
    """21 registros reais: paginação/HTMX continuam usando a mesma lista e filtros."""
    op = c.usuarios["operador"]
    unidade = Oficio.objects.get(pk=c.ids["oficio_emitido"]).unidade
    for i in range(21):
        Viagem.objects.create(unidade=unidade, criado_por=op, titulo=f"Atendimento {i}",
                              data_inicio=timezone.localdate() + timedelta(days=5))
    cli = _cliente(op)
    rota = reverse("viagens:viagens")
    primeira = cli.get(rota, {"q": "Atendimento", "aba": "futuras"})
    assert len(primeira.context["linhas"]) == 20
    assert primeira.context["page_obj"].paginator.count == 21
    assert "q=Atendimento&amp;aba=futuras&amp;pagina=2" in primeira.content.decode()
    segunda = cli.get(rota, {"q": "Atendimento", "aba": "futuras", "pagina": 2},
                      HTTP_HX_REQUEST="true")
    assert len(segunda.context["linhas"]) == 1
    html = segunda.content.decode()
    assert 'id="abas-filtro"' in html and 'id="resultados"' in html
    assert 'action="' + reverse("viagens:nova_viagem") + '"' in html
    consulta = _cliente(c.usuarios["consulta"]).get(rota)
    assert 'action="' + reverse("viagens:nova_viagem") + '"' not in consulta.content.decode()


def test_autosave_grava_sem_recarregar(c):
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    tipo = TipoViagem.objects.get(nome="Unidade Móvel")
    r = _cliente(op).post(reverse("viagens:autosave_viagem", args=[v.pk]), {
        "versao": viagem.versao_de(v), "tipos": [tipo.pk], "motivo": "x",
        "data_inicio": "10/10/2030", "destinos": ["Londrina/PR"]})
    dados = r.json()
    assert dados["salvo"] and not dados["recarregar"]  # o título está nas regiões vivas
    v.refresh_from_db()
    assert v.titulo == "Unidade Móvel" and v.data_inicio == date(2030, 10, 10)


def test_novo_documento_pela_tela_abre_a_folha(c):
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    r = _cliente(op).post(reverse("viagens:novo_documento_viagem", args=[v.pk, "ordem"]))
    ordem = OrdemServico.objects.get(viagem=v)
    assert r["Location"] == reverse("viagens:editar_ordem", args=[ordem.pk])
    r = _cliente(op).post(reverse("viagens:novo_documento_viagem", args=[v.pk, "termo"]),
                          follow=True)
    assert "Informe o tipo, o período e o destino" in r.content.decode()
    assert _cliente(op).post(reverse("viagens:novo_documento_viagem",
                                     args=[v.pk, "nada"])).status_code == 404


def test_permissoes(c):
    v = viagem.criar(c.usuarios["operador"])
    url = reverse("viagens:editar_viagem", args=[v.pk])
    assert _cliente(c.usuarios["outra"]).get(url).status_code == 404  # outra unidade
    consulta = _cliente(c.usuarios["consulta"])
    assert consulta.get(url).status_code == 200  # consulta lê
    assert consulta.post(reverse("viagens:salvar_viagem", args=[v.pk]), {}).status_code == 403
    with pytest.raises(PermissionDenied):
        viagem.criar(c.usuarios["consulta"])


def test_ordens_ja_existentes_continuam_sem_viagem(c):
    """Documento sem viagem segue valendo (a referência também aceita)."""
    ordem, _ = ordens.salvar(c.usuarios["operador"], destinos=[_londrina()],
                             motivo="avulsa")
    assert ordem.viagem_id is None


def test_gravacao_da_tela_nao_solta_documento_vinculado_depois(c):
    """A folha manda os vínculos de quando abriu: um documento vinculado depois (outra aba,
    "Novo …") não pode ser solto por ela."""
    import json
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    form_aberto = json.dumps({"ordens": []})
    ordem = viagem.novo_documento(op, v.pk, "ordem")  # criada depois que a tela abriu
    r = _cliente(op).post(reverse("viagens:autosave_viagem", args=[v.pk]), {
        "versao": viagem.versao_de(Viagem.objects.get(pk=v.pk)), "vinculos_presentes": "on",
        "conhecidos": form_aberto})
    assert r.json()["salvo"]
    assert OrdemServico.objects.get(pk=ordem.pk).viagem_id == v.pk


def test_folha_abre_com_candidatos_datados(c):
    """Regressão: plano/OS/termo livres com data na unidade derrubavam a folha (500)."""
    op = c.usuarios["operador"]
    ordens.salvar(op, destinos=[_londrina()], data_inicio=date(2030, 3, 1),
                  data_fim=date(2030, 3, 3), motivo="livre")
    termos.salvar(op, destinos=[_londrina()], data_inicio=date(2030, 3, 1))
    v = viagem.criar(op)
    r = _cliente(op).get(reverse("viagens:editar_viagem", args=[v.pk]))
    assert r.status_code == 200 and "01/03 a 03/03/2030" in r.content.decode()


def test_periodo_curto():
    assert viagem.periodo_curto(date(2030, 3, 1), None) == "01/03/2030"
    assert viagem.periodo_curto(date(2030, 12, 30), date(2031, 1, 2)) == "30/12/2030 a 02/01/2031"


def test_excluir_solta_os_documentos(c):
    """Diferença intencional: excluir a viagem não apaga documento (eles ficam sem viagem)."""
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    oficio = viagem.novo_documento(op, v.pk, "oficio")
    cli = _cliente(op)
    r = cli.post(reverse("viagens:excluir_viagem", args=[v.pk]), follow=True)
    assert "1 documento(s) continuam existindo, sem viagem." in r.content.decode()
    assert not Viagem.objects.filter(pk=v.pk).exists()
    assert Oficio.objects.get(pk=oficio.pk).viagem_id is None


def test_cancelar_e_reativar_em_cascata(c):
    gestor = c.usuarios["gestor"]
    v = viagem.criar(gestor)
    hoje = timezone.localdate()
    viagem.salvar_dados(gestor, v.pk, tipos=list(TipoViagem.objects.all()[:1]),
                        data_inicio=hoje, destinos=[_londrina()])
    oficio = viagem.novo_documento(gestor, v.pk, "oficio")
    ordem = viagem.novo_documento(gestor, v.pk, "ordem")
    avulsa, _ = ordens.salvar(gestor, destinos=[_londrina()], motivo="outra")
    ordens.cancelar(gestor, avulsa.pk, "Cancelada antes, por outro motivo")
    OrdemServico.objects.filter(pk=avulsa.pk).update(viagem=v)
    with pytest.raises(viagem.ViagemInvalida, match="motivo"):
        viagem.cancelar(gestor, v.pk, "  ")
    viagem.cancelar(gestor, v.pk, "Evento adiado")
    assert Oficio.objects.get(pk=oficio.pk).motivo_cancelamento == "Viagem cancelada: Evento adiado"
    assert OrdemServico.objects.get(pk=ordem.pk).cancelada
    viagem.reativar(gestor, v.pk)
    v.refresh_from_db()
    assert not v.cancelada
    assert Oficio.objects.get(pk=oficio.pk).situacao == Oficio.Situacao.RASCUNHO
    assert not OrdemServico.objects.get(pk=ordem.pk).cancelada
    assert OrdemServico.objects.get(pk=avulsa.pk).cancelada  # não caiu junto: fica


def test_operador_nao_cancela_viagem_com_oficio(c):
    """Cancelar ofício é do gestor: a cascata não fica pela metade."""
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    oficio = viagem.novo_documento(op, v.pk, "oficio")
    with pytest.raises(viagem.ViagemInvalida, match="Não foi possível cancelar"):
        viagem.cancelar(op, v.pk, "Adiada")
    assert not Viagem.objects.get(pk=v.pk).cancelada
    assert Oficio.objects.get(pk=oficio.pk).situacao == Oficio.Situacao.RASCUNHO


def test_cancelar_pela_tela(c):
    gestor = c.usuarios["gestor"]
    v = viagem.criar(gestor)
    cli = _cliente(gestor)
    html = cli.get(reverse("viagens:editar_viagem", args=[v.pk])).content.decode()
    assert "Cancelar viagem" in html and 'id="dialogo-motivo"' in html
    r = cli.post(reverse("viagens:cancelar_viagem", args=[v.pk]), {"motivo": "Adiada"},
                 follow=True)
    assert "Viagem cancelada." in r.content.decode() and "Reativar viagem" in r.content.decode()
    r = cli.post(reverse("viagens:reativar_viagem", args=[v.pk]), follow=True)
    assert "Viagem reativada." in r.content.decode()


def test_consulta_ve_a_viagem_como_texto(c):
    v = viagem.criar(c.usuarios["operador"])
    html = _cliente(c.usuarios["consulta"]).get(
        reverse("viagens:editar_viagem", args=[v.pk])).content.decode()
    assert 'id="form-viagem"' not in html and "Dados da viagem" in html


def test_documento_mostra_o_caminho_de_volta_para_a_viagem(c):
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    ordem = viagem.novo_documento(op, v.pk, "ordem")
    html = _cliente(op).get(reverse("viagens:editar_ordem", args=[ordem.pk])).content.decode()
    assert reverse("viagens:editar_viagem", args=[v.pk]) in html and "Viagem:" in html


class TestTipoDaViagemInteligente:
    """O tipo da viagem traz o motivo e o tipo da OS; a viatura unidade móvel do ofício põe
    a OS em "Unidade móvel" e marca a atividade no plano."""

    def _operacao(self):
        return TipoViagem.objects.create(nome="Operação Policial", motivo="Acompanhar a operação.",
                                         tipo_os=TipoViagem.TipoOS.OPERACAO_POLICIAL)

    def test_escolher_o_tipo_escreve_o_motivo_so_na_escolha(self, c):
        op = c.usuarios["operador"]
        v = viagem.criar(op)
        operacao = self._operacao()
        viagem.salvar_dados(op, v.pk, tipos=[operacao])
        assert Viagem.objects.get(pk=v.pk).motivo == "Acompanhar a operação."
        # Apagar o motivo depois não o traz de volta (o tipo já estava escolhido).
        viagem.salvar_dados(op, v.pk, tipos=[operacao], motivo="")
        assert Viagem.objects.get(pk=v.pk).motivo == ""
        # O motivo escrito pela pessoa nunca é trocado.
        outra = viagem.criar(c.usuarios["gestor"])
        viagem.salvar_dados(c.usuarios["gestor"], outra.pk, tipos=[operacao], motivo="Meu.")
        assert Viagem.objects.get(pk=outra.pk).motivo == "Meu."

    def test_a_tela_leva_os_motivos_dos_tipos(self, c):
        op = c.usuarios["operador"]
        v = viagem.criar(op)
        operacao = self._operacao()
        html = _cliente(op).get(reverse("viagens:editar_viagem", args=[v.pk])).content.decode()
        assert "data-motivos-dos-tipos=" in html and f"&quot;{operacao.pk}&quot;" in html

    def test_os_da_viagem_nasce_com_o_tipo_do_tipo_da_viagem(self, c):
        op = c.usuarios["operador"]
        v = viagem.criar(op)
        viagem.salvar_dados(op, v.pk, tipos=[self._operacao()], data_inicio=timezone.localdate(),
                            destinos=[_londrina()])
        ordem = OrdemServico.objects.get(pk=viagem.novo_documento(op, v.pk, "ordem").pk)
        assert ordem.modelo is not None and ordem.modelo.chave == "operacao_policial"

    def test_viatura_unidade_movel_poe_a_os_e_o_plano_em_unidade_movel(self, c):
        from gestao.cadastros.models import AtividadePlano, Viatura
        from gestao.viagens.models import PlanoTrabalho

        op = c.usuarios["operador"]
        oficio = Oficio.objects.get(pk=c.ids["oficio_emitido"])
        Viatura.objects.filter(pk=oficio.viatura_id).update(tipo="unidade_movel", porte="van")
        AtividadePlano.objects.get_or_create(
            codigo=AtividadePlano.UNIDADE_MOVEL,
            defaults={"nome": "Unidade móvel", "meta": "Atender."})
        oficio.refresh_from_db()
        # A OS criada do ofício: tipo "Unidade móvel".
        ordem, copiados = ordens.salvar(op, oficios=[oficio])
        assert ordem.modelo.chave == "unidade_movel" and "tipo de OS" in copiados
        # Na viagem com esse ofício: a OS e o plano novos também.
        v = viagem.criar(op)
        viagem.salvar_dados(op, v.pk, tipos=[], data_inicio=timezone.localdate(),
                            destinos=[_londrina()], vinculos={"oficios": [oficio]})
        nova = OrdemServico.objects.get(pk=viagem.novo_documento(op, v.pk, "ordem").pk)
        assert nova.modelo.chave == "unidade_movel"
        plano = PlanoTrabalho.objects.get(pk=viagem.novo_documento(op, v.pk, "plano").pk)
        assert plano.atividades.filter(codigo=AtividadePlano.UNIDADE_MOVEL).exists()

    def test_tipos_de_os_do_cadastro_batem_com_os_do_sistema(self):
        from gestao.viagens.modelos_do_sistema import MODELOS

        assert set(TipoViagem.TipoOS.values) == {m["chave"] for m in MODELOS}
