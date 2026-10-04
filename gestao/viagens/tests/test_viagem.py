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


def test_criar_reaproveita_a_vazia_esquecida(c):
    op = c.usuarios["operador"]
    primeira = viagem.criar(op)
    assert viagem.criar(op).pk != primeira.pk  # recente: não reaproveita
    Viagem.objects.filter(pk=primeira.pk).update(
        atualizado_em=timezone.now() - timedelta(hours=1))
    assert viagem.criar(op).pk == primeira.pk


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
    viagem.salvar_dados(op, v.pk, tipos=[], motivo="cobertura da feira", data_inicio=hoje,
                        destinos=[_londrina()])
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
    assert viagem.documentos(Viagem.objects.get(pk=v.pk)).total == 5


def test_termo_sem_periodo_ou_destino_avisa(c):
    v = viagem.criar(c.usuarios["operador"])
    with pytest.raises(viagem.ViagemInvalida, match="Informe o período e o destino"):
        viagem.novo_documento(c.usuarios["operador"], v.pk, "termo")


def test_tela_lista_busca_e_abas(c):
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    viagem.salvar_dados(op, v.pk, tipos=list(TipoViagem.objects.filter(nome="Unidade Móvel")),
                        data_inicio=timezone.localdate() + timedelta(days=5),
                        destinos=[_londrina()])
    cli = _cliente(op)
    html = cli.get(reverse("viagens:viagens")).content.decode()
    assert "Unidade Móvel · Londrina/PR" in html and "faltam 5 dias" in html
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
    assert "Tipo e motivo" in html and "Documentos da viagem" in html
    assert "Falta o tipo" in html and "Nenhum ofício vinculado a esta viagem." in html


def test_autosave_grava_e_recarrega_quando_o_titulo_muda(c):
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    tipo = TipoViagem.objects.get(nome="Unidade Móvel")
    r = _cliente(op).post(reverse("viagens:autosave_viagem", args=[v.pk]), {
        "versao": viagem.versao_de(v), "tipos": [tipo.pk], "motivo": "x",
        "data_inicio": "10/10/2030", "destinos": ["Londrina/PR"]})
    dados = r.json()
    assert dados["salvo"] and dados["recarregar"]
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
    assert "Informe o período e o destino" in r.content.decode()
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
