"""Correções da revisão de entrega do módulo Viagens (27/10/2026): cada teste trava um defeito
encontrado na auditoria — número reaproveitado, erros 500 por entrada adulterada ou clique
duplo, lote com motorista em outra equipe, viagem "vazia" com pedido anexado, prestação que
não podia sair da equipe, valores e km mal lidos, campo vinculado repetido no documento."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio, Servidor, TipoViagem, Viatura
from gestao.identidade.models import Usuario
from gestao.viagens import anexos, diario, prestacao, services, viagem, viagem_lote
from gestao.viagens.documentos.regioes import campos_presentes, sincronizar_campos
from gestao.viagens.dominio import relatorio as dominio_rt
from gestao.viagens.dominio.extenso import reais_por_extenso
from gestao.viagens.dominio.ordem_servico import DadosOS, Pessoa, textos_da_os
from gestao.viagens.models import (
    AnexoPrestacao,
    AnexoViagem,
    LacunaNumeracao,
    Oficio,
    PrestacaoServidor,
    Roteiro,
    Viagem,
)
from gestao.viagens.templatetags.documentos import campo_vinculado

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture
def c():
    return cenario_completo()


# ---------------------------------------------------------------- ofício
def test_numero_de_oficio_ja_emitido_nao_volta_para_a_fila(c):
    gestor = c.usuarios["gestor"]
    o = Oficio.objects.get(pk=c.ids["oficio_emitido"])
    antigo = o.numero
    o = services.retificar(o, gestor)
    services.salvar_dados(o, gestor, {"numero": 900})
    assert not LacunaNumeracao.objects.filter(ano=o.ano, numero=antigo).exists()
    novo = services.criar_rascunho(c.usuarios["operador"])
    assert novo.numero != antigo  # o número que está no papel não é dado de novo


def test_numero_de_rascunho_nunca_emitido_continua_voltando_para_a_fila(c):
    o = Oficio.objects.get(pk=c.ids["oficio_vazio"])
    antigo = o.numero
    services.salvar_dados(o, c.usuarios["operador"], {"numero": 901})
    assert LacunaNumeracao.objects.filter(ano=o.ano, numero=antigo).exists()


def test_remover_o_mesmo_servidor_duas_vezes_avisa_em_vez_de_erro(c, client):
    op = c.usuarios["operador"]
    o = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    v = o.viajantes.first()
    services.remover_viajante(o, op, v.pk)
    with pytest.raises(services.RegraViolada, match="já não está na equipe"):
        services.remover_viajante(o, op, v.pk)
    client.force_login(op)
    url = reverse("viagens:remover_viajante", args=[o.pk, v.pk])
    resposta = client.post(url, HTTP_HX_REQUEST="true")
    assert resposta.status_code == 200
    assert "já não está na equipe" in resposta.content.decode()


def test_servidor_adulterado_na_equipe_nao_derruba_a_pagina(c, client):
    op = c.usuarios["operador"]
    o = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    client.force_login(op)
    resposta = client.post(reverse("viagens:adicionar_viajante", args=[o.pk]), {"id": "abc"},
                           HTTP_HX_REQUEST="true")
    assert resposta.status_code == 200
    resposta = client.post(reverse("viagens:definir_motorista", args=[o.pk]),
                           {"viajante": "x1"}, HTTP_HX_REQUEST="true")
    assert resposta.status_code == 200


def test_duplicar_nao_leva_a_data_digitada_nem_o_marcador(c):
    op = c.usuarios["operador"]
    o = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    Oficio.objects.filter(pk=o.pk).update(data_oficio_manual=True,
                                          marcador=Oficio.Marcador.RETIFICADO)
    o.refresh_from_db()
    copia = services.duplicar_oficio(o, op)
    copia.refresh_from_db()
    assert copia.data_oficio_manual is False
    assert copia.marcador == Oficio.Marcador.NENHUM
    assert copia.motivo == o.motivo


def test_trocar_destinos_pelo_texto_nao_cria_trecho_da_cidade_para_ela_mesma(c):
    op = c.usuarios["operador"]
    curitiba = Municipio.objects.get(nome="Curitiba", uf="PR")
    arapongas = Municipio.objects.get(nome="Arapongas", uf="PR")
    maringa = Municipio.objects.get(nome="Maringá", uf="PR")
    o = services.criar_rascunho(op)
    saida = timezone.make_aware(datetime(2030, 3, 10, 8))
    services.salvar_trechos(o, op, [
        services.TrechoInformado(curitiba.pk, arapongas.pk, saida, saida + timedelta(hours=6)),
        services.TrechoInformado(arapongas.pk, maringa.pk, saida + timedelta(days=1),
                                 saida + timedelta(days=1, hours=1)),
        services.TrechoInformado(maringa.pk, curitiba.pk, saida + timedelta(days=2),
                                 saida + timedelta(days=2, hours=7)),
    ])
    o.refresh_from_db()
    with pytest.raises(services.RegraViolada, match="a mesma cidade"):
        services.salvar_campo_do_documento(o, op, "destinos", "Maringá/PR, Maringá/PR",
                                           versao=o.versao)


# ---------------------------------------------------------------- viagem
@pytest.fixture
def v(c):
    TipoViagem.objects.create(nome="Unidade Móvel")
    op = c.usuarios["operador"]
    nova = viagem.criar(op)
    viagem.salvar_dados(op, nova.pk, tipos=list(TipoViagem.objects.all()), motivo="Feira",
                        data_inicio=date(2030, 5, 10),
                        destinos=[Municipio.objects.get(nome="Londrina", uf="PR")],
                        vinculos={"roteiros": [Roteiro.objects.get(pk=c.ids["roteiro"])]})
    return Viagem.objects.get(pk=nova.pk)


def test_lote_com_quem_dirige_em_outra_equipe_vira_mensagem(c, v):
    a, b = Servidor.objects.filter(ativo=True).order_by("pk")[:2]
    viatura = Viatura.objects.filter(ativo=True).first()
    with pytest.raises(viagem_lote.LoteInvalido) as erro:
        viagem_lote.gerar(c.usuarios["operador"], v.pk, [
            viagem_lote.Equipe(servidores=[a]),
            viagem_lote.Equipe(servidores=[b], motorista=a, viatura=viatura)])
    assert any("dirige o ofício 2" in e for e in erro.value.erros)


def test_lote_motorista_sem_viatura_avisa(c, v):
    a, m = Servidor.objects.filter(ativo=True).order_by("pk")[:2]
    r = viagem_lote.gerar(c.usuarios["operador"], v.pk, [
        viagem_lote.Equipe(servidores=[a], motorista=m)], com_termos=False, com_ordem=False,
        com_plano=False)
    assert any("sem viatura" in aviso for aviso in r.avisos)


def test_lote_na_viagem_de_outra_unidade_e_recusado(c, v):
    a = Servidor.objects.filter(ativo=True).first()
    c.usuarios["outra"].user_permissions.add(
        *Permission.objects.filter(codename="ver_todas_unidades"))
    outra = Usuario.objects.get(pk=c.usuarios["outra"].pk)  # sem o cache de permissões
    with pytest.raises(PermissionDenied):
        viagem_lote.gerar(outra, v.pk, [viagem_lote.Equipe(servidores=[a])])


def test_viagem_com_pedido_anexado_nao_e_vazia(c):
    op = c.usuarios["operador"]
    nova = viagem.criar(op)
    assert viagem._vazia(nova)
    anexo = AnexoViagem(viagem=nova, nome_original="pedido.pdf", tamanho=len(PDF),
                        sha256=hashlib.sha256(PDF).hexdigest(), enviado_por=op)
    anexo.arquivo.save("pedido.pdf", ContentFile(PDF), save=True)
    assert not viagem._vazia(nova)
    from gestao.viagens import atencao_listas
    vazias = Viagem.objects.filter(atencao_listas.VIAGEM.vazio())
    assert not vazias.filter(pk=nova.pk).exists()


# ---------------------------------------------------------------- prestação
def _prestacao_do_emitido(c):
    o = Oficio.objects.get(pk=c.ids["oficio_emitido"])
    p = prestacao.sincronizar(o)
    return o, p


def test_quem_ja_tem_anexo_sai_da_equipe_sem_apagar_a_linha(c):
    o, p = _prestacao_do_emitido(c)
    ps = prestacao.ativos(PrestacaoServidor.objects.filter(prestacao=p)).first()
    anexos.anexar(c.usuarios["operador"], p.pk, AnexoPrestacao.Tipo.COMPROVANTE,
                  nome="saque.pdf", conteudo=PDF, servidor_pk=ps.pk)
    o.viajantes.filter(servidor_id=ps.servidor_id).delete()
    prestacao.sincronizar(o)  # antes: ProtectedError (o anexo protege a linha)
    ps.refresh_from_db()
    assert ps.removida_em is not None


@pytest.mark.parametrize(("lido", "esperado"), [
    ("transferencia", "transferencia"), ("Transferência", "transferencia"),
    ("depósito", "deposito"), ("PIX", "pix"), ("Saque", "saque"), ("boleto", ""), ("", "")])
def test_operacao_do_comprovante_aceita_o_rotulo_lido_do_pdf(lido, esperado):
    assert anexos.operacao_escolhida(lido) == esperado


def test_valor_maior_que_o_banco_guarda_e_recusado():
    assert dominio_rt.ler_valor("99.999.999,99")[0] == Decimal("99999999.99")
    with pytest.raises(dominio_rt.ValorInvalido):
        dominio_rt.ler_valor("123456789012,00")


def test_km_digitado_no_diario(c):
    _, p = _prestacao_do_emitido(c)
    linha = diario.obter(p).linhas.first()
    assert diario._km(linha, "12.345", "inicial") == 12345
    assert diario._km(linha, "12345 km", "inicial") == 12345
    assert diario._km(linha, "45678,9", "final") == 45678  # a casa do décimo cai
    assert diario._km(linha, "", "final") is None
    for errado in ("-120", "12a45", "123456789012"):
        with pytest.raises(diario.DiarioInvalido):
            diario._km(linha, errado, "inicial")


# ---------------------------------------------------------------- documentos
def test_campo_com_cor_aplicada_dentro_nao_sai_repetido():
    html = ('<p><span data-campo="motivo">Curso de <span style="color:red">tiro</span> em '
            'Curitiba</span> fim</p>')
    saida = sincronizar_campos(html, {"motivo": "Novo motivo"})
    assert saida == '<p><span data-campo="motivo">Novo motivo</span> fim</p>'
    assert campos_presentes(saida) == {"motivo"}


def test_campo_multilinha_com_quebra_do_windows():
    html = str(campo_vinculado("justificativa", "linha 1\r\nlinha 2"))
    assert "\r" not in html and "linha 1<br>linha 2" in html


def test_textos_da_os_sem_cargo_e_sem_periodo():
    dados = DadosOS(destinos=["Londrina/PR"], motivo="Apoio",
                    equipe=[Pessoa(id=1, nome="Fulano de Tal", cargo="")])
    texto = textos_da_os(dados)["determinacao"]
    assert texto.startswith("O deslocamento de Fulano de Tal para o município de Londrina/PR")
    assert ", ," not in texto


def test_zero_reais_por_extenso():
    assert reais_por_extenso(Decimal("0")) == "zero reais"
