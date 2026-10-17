"""Correções da auditoria de paridade com a referência (matriz EV-F*): cancelar mantém a
decisão da DG (F44), anexos só em rascunho/devolvida (F50), transferir sem cair em 404
(F46), o ajuste de servidores muda a versão e recusa valor inválido (F37), devolver não
aplica as quantidades (F35), CEP com 8 dígitos (F12) e motorista só de quem dirige (F14)."""

from __future__ import annotations

import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import Cargo, Servidor, Viatura
from gestao.eventos import solicitacoes
from gestao.eventos.forms import MSG_CEP, FormularioSolicitacao
from gestao.eventos.models import Equipe, Solicitacao

from .test_solicitacoes import _completa, _estrutura, _usuario, ana, dg  # noqa: F401

pytestmark = pytest.mark.django_db


def _aguardando(quem):
    s = solicitacoes.criar(quem, _completa(), _estrutura())
    solicitacoes.enviar(quem, s.pk)
    return s


def test_cancelar_mantem_a_decisao_da_dg(ana, dg):  # noqa: F811
    s = _aguardando(ana)
    solicitacoes.despachar(dg, s.pk, "atender")
    solicitacoes.cancelar(dg, s.pk, "Chuva")
    s.refresh_from_db()
    assert s.status == "cancelada" and s.decisao_dg == "atender"
    t = _aguardando(ana)
    solicitacoes.cancelar(ana, t.pk, "Desistiu")
    t.refresh_from_db()
    assert t.status == "cancelada" and t.decisao_dg == "pendente"  # sem decisão inventada


def test_anexos_so_em_rascunho_ou_devolvida(ana, dg, settings, tmp_path):  # noqa: F811
    settings.MEDIA_ROOT = tmp_path
    s = solicitacoes.criar(ana, _completa(), _estrutura())
    a = solicitacoes.anexar(ana, s.pk, SimpleUploadedFile("o.pdf", b"%PDF-1.4 x"))
    solicitacoes.enviar(ana, s.pk)
    with pytest.raises(PermissionDenied):
        solicitacoes.anexar(ana, s.pk, SimpleUploadedFile("p.pdf", b"%PDF-1.4 y"))
    with pytest.raises(PermissionDenied):
        solicitacoes.remover_anexo(ana, a.pk)
    solicitacoes.despachar(dg, s.pk, "devolver", "Falta o ofício assinado")
    solicitacoes.anexar(ana, s.pk, SimpleUploadedFile("p.pdf", b"%PDF-1.4 y"))
    assert s.anexos.count() == 2


def test_transferir_volta_a_lista_quando_nao_ve_mais(ana):  # noqa: F811
    bia = _usuario("bia")
    s = solicitacoes.criar(ana, _completa(), _estrutura())
    c = Client()
    c.force_login(ana)
    r = c.post(reverse("eventos:transferir", args=[s.pk]),
               {"responsavel": bia.pk, "motivo_transferencia": "Férias"}, follow=True)
    assert r.status_code == 200
    assert r.redirect_chain[-1][0] == reverse("eventos:solicitacoes")
    assert "transferida para Bia" in r.content.decode()


def test_ajuste_da_dg_muda_a_versao_e_recusa_valor_invalido(ana, dg):  # noqa: F811
    s = _aguardando(ana)
    antes = Solicitacao.objects.get(pk=s.pk).atualizado_em
    alfa = Equipe.objects.get(nome="Alfa")
    assert solicitacoes.ajustar_servidores(dg, s.pk, {alfa.pk: 7})
    s.refresh_from_db()
    assert s.quantidade_servidores == 7 and s.atualizado_em > antes
    c = Client()
    c.force_login(dg)
    for ruim in ("", "0", "abc"):
        r = c.post(reverse("eventos:despachar", args=[s.pk]),
                   {"decisao": "atender", f"quantidade_dg_{alfa.pk}": ruim}, follow=True)
        assert "Informe uma quantidade válida de servidores para Alfa." in r.content.decode()
        s.refresh_from_db()
        assert s.status == "aguardando_despacho" and s.quantidade_servidores == 7


def test_devolver_nao_aplica_as_quantidades(ana, dg):  # noqa: F811
    s = _aguardando(ana)
    alfa = Equipe.objects.get(nome="Alfa")
    c = Client()
    c.force_login(dg)
    c.post(reverse("eventos:despachar", args=[s.pk]),
           {"decisao": "devolver", "observacao": "Corrigir", f"quantidade_dg_{alfa.pk}": "x"})
    s.refresh_from_db()
    assert s.status == "devolvida" and s.quantidade_servidores == 3


def _form(**dados) -> FormularioSolicitacao:
    base = {"data_solicitacao": "17/10/2026", "tipo_operacao": "diaria"}
    return FormularioSolicitacao(data={**base, **dados})


@pytest.mark.parametrize(("digitado", "gravado"), [
    ("80010000", "80010-000"), ("80010-000", "80010-000"), (" 80010 000 ", "80010-000"),
    ("", "")])
def test_cep_normalizado(digitado, gravado):
    f = _form(cep=digitado)
    assert f.is_valid(), f.errors
    assert f.cleaned_data["cep"] == gravado


@pytest.mark.parametrize("digitado", ["8001", "800100001", "abc", "8001O-000"])
def test_cep_invalido(digitado):
    f = _form(cep=digitado)
    assert not f.is_valid() and f.errors["cep"] == [MSG_CEP]


def test_motorista_so_quem_dirige(ana):  # noqa: F811
    motorista = Servidor.objects.create(
        nome="Moacir", cargo=Cargo.objects.create(nome="Motorista Policial"))
    habitual = Servidor.objects.create(nome="Helena")
    Viatura.objects.create(placa="ABC1D23").motoristas.add(habitual)
    escrivao = Servidor.objects.create(nome="Ester",
                                       cargo=Cargo.objects.create(nome="Escrivão"))
    Servidor.objects.create(nome="Inativo", cargo=motorista.cargo, ativo=False)
    opcoes = set(FormularioSolicitacao().fields["motorista"].queryset)
    assert opcoes == {motorista, habitual}
    # O que a solicitação já tem continua na lista.
    s = solicitacoes.criar(ana, _completa(unidade_movel=True, motorista=escrivao), _estrutura())
    assert escrivao in FormularioSolicitacao(instance=s).fields["motorista"].queryset


def test_historico_do_reenvio_mostra_o_que_mudou(ana, dg):  # noqa: F811
    """EV-F28: alterar depois do despacho muda dados e situação juntos — a diferença dos
    campos continua no histórico."""
    from gestao.eventos import queries

    s = _aguardando(ana)
    solicitacoes.despachar(dg, s.pk, "atender")
    solicitacoes.reabrir_e_reenviar(ana, s.pk, {"local_evento": "Praça Central"},
                                    _estrutura(5))
    eventos = queries.historico(s)
    mudancas = [m for e in eventos for m in e.mudancas]
    assert ("Local do evento", "Ginásio", "Praça Central") in mudancas


def test_lista_e_exportacao_na_ordem_escolhida(ana):  # noqa: F811
    """EV-F82/EV-F86: `?ordem=` vale na tela (gaveta "Ordenar por") e na exportação."""
    s1 = solicitacoes.criar(ana, _completa(solicitante_nome="Zeta"), _estrutura())
    s2 = solicitacoes.criar(ana, _completa(solicitante_nome="Alfa"), _estrutura())
    c = Client()
    c.force_login(ana)
    html = c.get(reverse("eventos:solicitacoes"), {"ordem": "solicitante"}).content.decode()
    assert '<option value="solicitante" selected>' in html
    assert html.index(f"#{s2.pk}") < html.index(f"#{s1.pk}")
    csv = c.get(reverse("eventos:exportar"), {"ordem": "solicitante"}).content.decode("utf-8-sig")
    assert csv.index("Alfa") < csv.index("Zeta")


def test_faixa_da_devolucao_diz_quando_e_quem(ana, dg):  # noqa: F811
    """EV-F57: motivo, data e quem devolveu."""
    s = _aguardando(ana)
    solicitacoes.despachar(dg, s.pk, "devolver", "Falta o endereço")
    c = Client()
    c.force_login(ana)
    html = c.get(reverse("eventos:solicitacao", args=[s.pk])).content.decode()
    assert "Falta o endereço" in html and "por Dg. Corrija e envie de novo." in html


def test_marcar_como_atendida_pelo_menu_da_linha(ana, dg):  # noqa: F811
    """EV-F85: deferida, do responsável e com o evento já feito: "Marcar como atendida"."""
    from datetime import timedelta

    from django.utils import timezone
    s = _aguardando(ana)
    solicitacoes.despachar(dg, s.pk, "atender")
    c = Client()
    c.force_login(ana)
    assert "Marcar como atendida" not in c.get(reverse("eventos:solicitacoes")).content.decode()
    ontem = timezone.localdate() - timedelta(days=1)
    Solicitacao.objects.filter(pk=s.pk).update(data_inicio_evento=ontem, data_fim_evento=ontem)
    html = c.get(reverse("eventos:solicitacoes")).content.decode()
    assert "Marcar como atendida" in html
    c.post(reverse("eventos:concluir", args=[s.pk]))
    s.refresh_from_db()
    assert s.status == "atendida"


def test_toda_tabela_de_eventos_e_coffee_tem_trilha_no_banco():
    """EV-F*/CB-F109: cada tabela dos dois módulos tem o trigger da auditoria do banco."""
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute("""SELECT c.relname FROM pg_class c
                       JOIN pg_namespace n ON n.oid = c.relnamespace
                       WHERE c.relkind = 'r' AND n.nspname = current_schema()
                         AND (c.relname LIKE 'eventos\\_%' OR c.relname LIKE 'coffee\\_%')""")
        tabelas = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")
        gatilhos = {r[0] for r in cur.fetchall()}
    assert tabelas
    # O lembrete diário já enviado é registro do sistema, sem trilha (models_solicitacao.py).
    sem_trilha = sorted(t for t in tabelas - {"eventos_lembrete"}
                        if f"auditoria_{t}" not in gatilhos)
    assert not sem_trilha, sem_trilha


def test_anexo_so_sai_pela_view_de_quem_ve(ana, settings, tmp_path):  # noqa: F811
    """EV-F96: não há rota /media/; o anexo sai só pela view, para quem vê a solicitação."""
    settings.MEDIA_ROOT = tmp_path
    s = solicitacoes.criar(ana, _completa(), _estrutura())
    a = solicitacoes.anexar(ana, s.pk, SimpleUploadedFile("o.pdf", b"%PDF-1.4 x"))
    outro = Client()
    outro.force_login(_usuario("bia"))
    assert outro.get(reverse("eventos:abrir_anexo", args=[s.pk, a.pk])).status_code == 404
    assert outro.get(f"/media/{a.arquivo.name}").status_code == 404
    assert Client().get(f"/media/{a.arquivo.name}").status_code in (302, 404)  # anônimo
    dono = Client()
    dono.force_login(ana)
    assert dono.get(reverse("eventos:abrir_anexo", args=[s.pk, a.pk])).status_code == 200
