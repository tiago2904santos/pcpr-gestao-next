"""Menu ⋮ canônico da linha do ofício (LP-30, D7): o que cada perfil vê em cada estado, as
marcas Retificado/Complementar (exclusão mútua, só no rascunho) e o fragmento que a lista
pede ao abrir o menu."""

from __future__ import annotations

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from gestao.viagens import policies, queries, services
from gestao.viagens.models import Documento, Historico, Oficio

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def cenario():
    return cenario_completo()


def _da_lista(pk: int) -> Oficio:
    """O ofício como a lista o carrega (anotações de PDF, via e documentos)."""
    return queries.com_dados_de_lista(Oficio.objects.filter(pk=pk)).get()


def _pdf_pronto(pk: int) -> Documento:
    """Gera os PDFs pendentes como o worker da outbox faria."""
    from gestao.plataforma import outbox

    while outbox.processar_lote():
        pass
    return Documento.objects.get(oficio_id=pk, tipo=Documento.Tipo.OFICIO,
                                 situacao=Documento.Situacao.PRONTO)


class TestPolitica:
    def test_rascunho_para_quem_edita(self, cenario):
        m = policies.menu_do_oficio(cenario.usuarios["operador"],
                                    _da_lista(cenario.ids["oficio_rascunho"]))
        assert m.abrir and not m.retificar and m.minuta and m.pdf is None
        assert m.baixar and m.duplicar and m.termo
        # Sem PDF emitido, "Anexar assinado" aparece inativo e diz por quê (como no legado).
        assert m.anexar == "inativo" and "Emita o ofício" in m.anexar_motivo
        assert [o.marca.value for o in m.marcas] == ["retificado", "complementar"]
        assert m.ciclo["excluir"] and m.ciclo["arquivar"] and not m.ciclo["cancelar"]

    def test_emitido_com_pdf(self, cenario):
        pk = cenario.ids["oficio_emitido"]
        doc = _pdf_pronto(pk)
        m = policies.menu_do_oficio(cenario.usuarios["gestor"], _da_lista(pk))
        assert not m.abrir and m.retificar and not m.minuta
        assert m.pdf == (doc.pk, doc.versao)
        assert m.anexar == "ativo" and not m.anexar_troca
        assert m.marcas == []  # o emitido se corrige por retificação
        assert m.ciclo["cancelar"] and not m.ciclo.get("excluir")

    def test_emitido_sem_pdf_pronto_explica_a_espera(self, cenario):
        m = policies.menu_do_oficio(cenario.usuarios["gestor"],
                                    _da_lista(cenario.ids["oficio_emitido"]))
        assert m.minuta and m.anexar == "inativo" and "sendo gerado" in m.anexar_motivo

    def test_cancelado_so_le_e_reativa(self, cenario):
        m = policies.menu_do_oficio(cenario.usuarios["gestor"],
                                    _da_lista(cenario.ids["oficio_cancelado"]))
        assert not (m.abrir or m.retificar or m.baixar or m.anexar or m.termo or m.ordem
                    or m.plano or m.marcas)
        assert m.ciclo["reativar"] and not m.ciclo["cancelar"]

    def test_arquivado_desarquiva_e_anexar_explica(self, cenario):
        pk = cenario.ids["oficio_emitido"]
        _pdf_pronto(pk)
        services.arquivar(Oficio.objects.get(pk=pk), cenario.usuarios["operador"])
        m = policies.menu_do_oficio(cenario.usuarios["operador"], _da_lista(pk))
        assert m.ciclo["desarquivar"] and not m.ciclo["arquivar"]
        assert m.anexar == "inativo" and "Desarquive" in m.anexar_motivo

    def test_quem_so_consulta_so_le(self, cenario):
        for chave in ("oficio_rascunho", "oficio_emitido", "oficio_cancelado"):
            m = policies.menu_do_oficio(cenario.usuarios["consulta"], _da_lista(cenario.ids[chave]))
            assert not (m.abrir or m.retificar or m.baixar or m.anexar or m.termo or m.ordem
                        or m.plano or m.duplicar or m.marcas or m.ciclo["alguma"]), chave

    def test_via_em_vigor_vira_troca(self, cenario):
        from gestao.viagens import assinados

        pk = cenario.ids["oficio_emitido"]
        _pdf_pronto(pk)
        alvo = assinados.Alvo("oficio", Oficio.objects.get(pk=pk))
        assinados.anexar(cenario.usuarios["operador"], alvo, nome="ass.pdf",
                         conteudo=b"%PDF-1.4\n%%EOF\n")
        m = policies.menu_do_oficio(cenario.usuarios["operador"], _da_lista(pk))
        assert m.anexar == "ativo" and m.anexar_troca


class TestMarcas:
    def test_ligar_uma_tira_a_outra_e_fica_no_historico(self, cenario):
        pk, operador = cenario.ids["oficio_rascunho"], cenario.usuarios["operador"]
        services.alternar_marcador(Oficio.objects.get(pk=pk), operador, "retificado")
        o = services.alternar_marcador(Oficio.objects.get(pk=pk), operador, "complementar")
        assert o.marcador == "complementar"
        ultimo = Historico.objects.filter(oficio_id=pk).order_by("-pk").first()
        assert ultimo is not None and "complementar" in ultimo.descricao
        assert "retificado saiu" in ultimo.descricao
        o = services.alternar_marcador(o, operador, "complementar")
        assert o.marcador == ""

    def test_emitido_nao_se_marca(self, cenario):
        with pytest.raises(PermissionDenied):
            services.alternar_marcador(Oficio.objects.get(pk=cenario.ids["oficio_emitido"]),
                                       cenario.usuarios["gestor"], "complementar")

    def test_marca_invalida_volta_com_mensagem(self, cenario):
        with pytest.raises(services.RegraViolada, match="retificado ou complementar"):
            services.alternar_marcador(Oficio.objects.get(pk=cenario.ids["oficio_rascunho"]),
                                       cenario.usuarios["operador"], "")

    def test_pela_tela_volta_a_lista_como_estava(self, client, cenario):
        client.force_login(cenario.usuarios["operador"])
        pk = cenario.ids["oficio_rascunho"]
        voltar = reverse("viagens:oficios") + "?documento=rascunho&q=mar"
        r = client.post(reverse("viagens:marcar_oficio", args=[pk]),
                        {"marca": "complementar", "voltar": voltar})
        assert r.status_code == 302 and r["Location"] == voltar
        assert Oficio.objects.get(pk=pk).marcador == "complementar"
        r = client.get(voltar)
        assert "marcado como complementar" in r.content.decode()
        # Um emitido não se marca: 403 (a política diz não).
        r = client.post(reverse("viagens:marcar_oficio", args=[cenario.ids["oficio_emitido"]]),
                        {"marca": "complementar"})
        assert r.status_code == 403


class TestFragmentoDoMenu:
    def test_lista_nao_carrega_os_itens_e_aponta_o_fragmento(self, client, cenario):
        client.force_login(cenario.usuarios["operador"])
        html = client.get(reverse("viagens:oficios")).content.decode()
        pk = cenario.ids["oficio_rascunho"]
        assert f'data-menu-carregar="{reverse("viagens:acoes_oficio", args=[pk])}"' in html
        assert "Carregando as ações…" in html and "Marcar como complementar" not in html

    def test_fragmento_do_rascunho(self, client, cenario):
        client.force_login(cenario.usuarios["operador"])
        r = client.get(reverse("viagens:acoes_oficio", args=[cenario.ids["oficio_rascunho"]]))
        html = r.content.decode()
        assert r.status_code == 200 and r["Cache-Control"] == "no-store"
        for texto in ("Ver resumo", "Abrir o ofício", "Ver minuta", "Baixar documentos…",
                      "Anexar assinado…", "Duplicar", "Marcar como retificado",
                      "Marcar como complementar", "Arquivar", "Excluir rascunho"):
            assert texto in html, texto
        assert 'aria-disabled="true"' in html  # anexar inativo, com o porquê
        assert "Cancelar ofício" not in html  # operador não cancela

    def test_outra_unidade_nao_existe(self, client, cenario):
        client.force_login(cenario.usuarios["operador"])
        r = client.get(reverse("viagens:acoes_oficio", args=[cenario.ids["oficio_outra_unidade"]]))
        assert r.status_code == 404

    def test_consultas_fixas(self, client, cenario, django_assert_max_num_queries):
        client.force_login(cenario.usuarios["gestor"])
        with django_assert_max_num_queries(12):
            client.get(reverse("viagens:acoes_oficio", args=[cenario.ids["oficio_emitido"]]))
