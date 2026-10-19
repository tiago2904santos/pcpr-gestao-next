"""Avisos à equipe pelo WhatsApp (fluxo 10-2, partes de cancelamento, reagendamento e
substituição), com o adaptador simulado: o serviço de Viagens agenda na própria transação,
o worker relê o ofício no envio e o aviso de uma mudança mais antiga fica obsoleto quando
outra mudança chega antes de ele sair.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group

from gestao.automacao import chaves, contatos, entrega, ganchos, links
from gestao.automacao.models import Comunicacao, ContatoVerificado, LinkAcesso
from gestao.identidade.models import Usuario
from gestao.integracoes.whatsapp.adaptadores import AdaptadorSimulado
from gestao.viagens import comunicacoes_viagem as cv
from gestao.viagens import diario as servico_diario
from gestao.viagens import km_link, services
from gestao.viagens.models import Oficio, Viajante

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db
S = Comunicacao.Situacao


class Espiao(AdaptadorSimulado):
    def __init__(self):
        self.envios = []

    def enviar(self, mensagem, simular=""):
        self.envios.append(mensagem)
        return super().enviar(mensagem, simular)


@pytest.fixture(autouse=True)
def _sem_trava_de_transacao(monkeypatch):
    monkeypatch.setattr(entrega, "VERIFICAR_TRANSACAO", False)
    cv.registrar()  # no app, `ViagensConfig.ready` (gestao/viagens/apps.py)


@pytest.fixture
def c():
    cen = cenario_completo()
    admin = Usuario.objects.create_user("admin-avisos", "admin-avisos@pc.pr.gov.br", "x",
                                        nome="Administração da automação")
    admin.groups.add(Group.objects.get(name="ADMINISTRADOR"))
    cen.usuarios["admin"] = admin
    cen.oficio = Oficio.objects.get(pk=cen.ids["oficio_emitido"])
    cen.equipe = [v.servidor for v in Viajante.objects.filter(oficio=cen.oficio)
                  .select_related("servidor").order_by("ordem", "pk")]
    for i, s in enumerate(cen.equipe):
        s.telefone = f"4199998000{i + 1}"
        s.save(update_fields=["telefone"])
    admin_ = cen.usuarios["admin"]
    chaves.alterar(admin_, chaves.GERAL, estado="ligada")
    chaves.alterar(admin_, chaves.nome_canal("whatsapp"), estado="ligada")
    chaves.alterar(admin_, chaves.nome_fluxo(cv.FLUXO_AVISOS), estado="ligada",
                   modo="automatico")
    return cen


def _contato(c, servidor):
    op = c.usuarios["operador"]
    contato = contatos.cadastrar(op, servidor.pk)
    contatos.confirmar_numero(op, contato.pk)
    contatos.registrar_optin(op, contato.pk, ContatoVerificado.OrigemOptin.FORMULARIO)
    contatos.autorizar_testador(c.usuarios["admin"],
                                ContatoVerificado.objects.get(pk=contato.pk).endereco,
                                f"Testador {servidor.pk}")


def _processar() -> Espiao:
    espiao = Espiao()
    while entrega.processar_uma(porta=espiao):
        pass
    return espiao


def _reemitir(c, deslocar: timedelta | None = None):
    services.reabrir(c.oficio, c.usuarios["gestor"], "Corrigir a viagem (teste).")
    oficio = Oficio.objects.get(pk=c.oficio.pk)
    if deslocar:
        services.salvar_trechos(oficio, c.usuarios["operador"], [
            services.TrechoInformado(t.origem_id, t.destino_id, t.saida_em + deslocar,
                                     t.chegada_em + deslocar)
            for t in oficio.trechos.order_by("ordem")])
        oficio.refresh_from_db()
    services.emitir(oficio, c.usuarios["operador"])
    c.oficio.refresh_from_db()


# ------------------------------------------------------------------ cancelamento
def test_cancelamento_avisa_quem_tem_contato_sem_o_motivo(c):
    com_contato, sem_contato = c.equipe[0], c.equipe[1]
    _contato(c, com_contato)
    services.cancelar(c.oficio, c.usuarios["gestor"], "Motivo interno que não vai na mensagem.")
    avisos = Comunicacao.objects.filter(tipo=cv.CANCELAMENTO)
    assert list(avisos.values_list("servidor_id", flat=True)) == [com_contato.pk]
    assert not avisos.filter(servidor_id=sem_contato.pk).exists()
    aviso = avisos.get()
    assert aviso.criada_por == c.usuarios["gestor"]
    espiao = _processar()
    aviso.refresh_from_db()
    assert aviso.situacao == S.ENVIADA, aviso.motivo
    texto = espiao.envios[0].texto
    assert "cancelada" in texto and c.oficio.numero_formatado in texto
    assert "Motivo interno" not in texto and "dados fictícios" in texto
    assert espiao.envios[0].modelo is not None  # aviso do negócio fora da janela: modelo
    assert espiao.envios[0].modelo.parametros[1] == c.oficio.numero_formatado


def test_cancelar_oficio_reaberto_depois_de_emitido_avisa_quem_recebeu(c):
    """Emitido, reaberto para correção e cancelado antes de sair de novo: quem recebeu a
    versão emitida é avisado (o ofício dele parece valer)."""
    _contato(c, c.equipe[0])
    services.reabrir(c.oficio, c.usuarios["gestor"], "Corrigir a viagem (teste).")
    oficio = Oficio.objects.get(pk=c.oficio.pk)
    assert oficio.situacao != Oficio.Situacao.EMITIDO
    services.cancelar(oficio, c.usuarios["gestor"], "Não vai mais.")
    avisos = Comunicacao.objects.filter(tipo=cv.CANCELAMENTO)
    assert list(avisos.values_list("servidor_id", flat=True)) == [c.equipe[0].pk]
    _processar()
    assert avisos.get().situacao == S.ENVIADA


def test_rascunho_cancelado_nao_avisa_ninguem(c):
    rascunho = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    for v in Viajante.objects.filter(oficio=rascunho).select_related("servidor"):
        v.servidor.telefone = "41999987777"
        v.servidor.save(update_fields=["telefone"])
        _contato(c, v.servidor)
    services.cancelar(rascunho, c.usuarios["gestor"], "Não vai mais.")
    assert not Comunicacao.objects.filter(tipo=cv.CANCELAMENTO).exists()


def test_aviso_de_cancelamento_fica_obsoleto_se_o_oficio_e_reativado(c):
    _contato(c, c.equipe[0])
    services.cancelar(c.oficio, c.usuarios["gestor"], "Adiado.")
    services.reativar(Oficio.objects.get(pk=c.oficio.pk), c.usuarios["gestor"],
                      "Evento confirmado de novo.")
    espiao = _processar()
    aviso = Comunicacao.objects.get(tipo=cv.CANCELAMENTO)
    assert aviso.situacao == S.OBSOLETA and espiao.envios == []


# ------------------------------------------------------------------ reemissão
def test_reemitir_com_outras_datas_avisa_o_reagendamento(c):
    for s in c.equipe:
        _contato(c, s)
    _reemitir(c, deslocar=timedelta(days=2))
    avisos = Comunicacao.objects.filter(tipo=cv.REAGENDAMENTO)
    assert avisos.count() == len(c.equipe)
    assert not Comunicacao.objects.filter(tipo=cv.SUBSTITUICAO).exists()
    espiao = _processar()
    assert set(avisos.values_list("situacao", flat=True)) == {S.ENVIADA}
    assert all("mudaram" in m.texto and "versão 2" in m.texto for m in espiao.envios)


def test_reemitir_sem_mudar_datas_avisa_a_substituicao(c):
    _contato(c, c.equipe[0])
    _reemitir(c)
    aviso = Comunicacao.objects.get(tipo=cv.SUBSTITUICAO)
    assert not Comunicacao.objects.filter(tipo=cv.REAGENDAMENTO).exists()
    espiao = _processar()
    aviso.refresh_from_db()
    assert aviso.situacao == S.ENVIADA, aviso.motivo
    assert "não vale mais" in espiao.envios[0].texto


def test_aviso_antigo_fica_obsoleto_quando_vem_outra_mudanca(c):
    _contato(c, c.equipe[0])
    _reemitir(c, deslocar=timedelta(days=1))   # v2: reagendamento agendado, não saiu
    reagendamento = Comunicacao.objects.get(tipo=cv.REAGENDAMENTO)
    _reemitir(c)                                # v3 antes do envio: o da v2 não vale mais
    reagendamento.refresh_from_db()
    assert reagendamento.situacao == S.OBSOLETA
    substituicao = Comunicacao.objects.get(tipo=cv.SUBSTITUICAO)
    services.reabrir(c.oficio, c.usuarios["gestor"], "Mais uma correção.")  # antes de sair
    espiao = _processar()
    substituicao.refresh_from_db()
    assert substituicao.situacao == S.OBSOLETA and espiao.envios == []
    assert "não está mais emitido" in substituicao.motivo


def test_cancelar_depois_de_reemitir_deixa_o_aviso_da_reemissao_obsoleto(c):
    _contato(c, c.equipe[0])
    _reemitir(c, deslocar=timedelta(days=1))
    services.cancelar(c.oficio, c.usuarios["gestor"], "Cancelado.")
    espiao = _processar()
    assert Comunicacao.objects.get(tipo=cv.REAGENDAMENTO).situacao == S.OBSOLETA
    assert Comunicacao.objects.get(tipo=cv.CANCELAMENTO).situacao == S.ENVIADA
    assert len(espiao.envios) == 1


def test_sem_os_tipos_registrados_os_servicos_seguem(c, monkeypatch):
    _contato(c, c.equipe[0])
    for tipo in (cv.CANCELAMENTO, cv.REAGENDAMENTO, cv.SUBSTITUICAO):
        monkeypatch.delitem(ganchos._TIPOS, tipo)
    _reemitir(c, deslocar=timedelta(days=1))
    services.cancelar(c.oficio, c.usuarios["gestor"], "Cancelado.")
    assert not Comunicacao.objects.exists()


def test_quem_sai_da_equipe_e_avisado_e_perde_o_link_de_km(c):
    for s in c.equipe:
        _contato(c, s)
    viajantes = list(Viajante.objects.filter(oficio=c.oficio).order_by("ordem", "pk"))
    saiu = next(v for v in viajantes if v.motorista)
    fica = next(v for v in viajantes if not v.motorista)
    d = servico_diario.obter(c.oficio.prestacao)
    links.criar(escopo="km", recurso=km_link.recurso(d.pk), servidor_id=saiu.servidor_id)
    services.reabrir(c.oficio, c.usuarios["gestor"], "Troca de motorista (teste).")
    oficio = Oficio.objects.get(pk=c.oficio.pk)
    services.definir_motorista(oficio, c.usuarios["operador"], fica.pk)
    services.remover_viajante(oficio, c.usuarios["operador"], saiu.pk)
    services.emitir(Oficio.objects.get(pk=c.oficio.pk), c.usuarios["operador"])
    link = LinkAcesso.objects.get()
    assert link.revogado_em and link.motivo_revogacao == LinkAcesso.Motivo.RESPONSAVEL_TROCADO
    aviso = Comunicacao.objects.get(tipo=cv.RETIRADA)
    assert aviso.servidor_id == saiu.servidor_id
    # Quem ficou recebe o aviso da reemissão; quem saiu, só o de saída.
    assert not Comunicacao.objects.filter(tipo=cv.SUBSTITUICAO,
                                          servidor_id=saiu.servidor_id).exists()
    assert Comunicacao.objects.filter(tipo=cv.SUBSTITUICAO,
                                      servidor_id=fica.servidor_id).exists()
    espiao = _processar()
    aviso.refresh_from_db()
    assert aviso.situacao == S.ENVIADA, aviso.motivo
    textos = [m.texto for m in espiao.envios]
    assert any("você não faz mais parte da equipe desta viagem (teste)" in t.lower()
               for t in textos)


def test_aviso_de_saida_fica_obsoleto_se_a_pessoa_volta(c):
    for s in c.equipe:
        _contato(c, s)
    viajantes = list(Viajante.objects.filter(oficio=c.oficio).order_by("ordem", "pk"))
    saiu = next(v for v in viajantes if not v.motorista)
    services.reabrir(c.oficio, c.usuarios["gestor"], "Tira um (teste).")
    services.remover_viajante(Oficio.objects.get(pk=c.oficio.pk), c.usuarios["operador"],
                              saiu.pk)
    services.emitir(Oficio.objects.get(pk=c.oficio.pk), c.usuarios["operador"])
    aviso = Comunicacao.objects.get(tipo=cv.RETIRADA)
    services.reabrir(c.oficio, c.usuarios["gestor"], "Volta (teste).")
    oficio = Oficio.objects.get(pk=c.oficio.pk)
    services.adicionar_viajante(oficio, c.usuarios["operador"], saiu.servidor)
    services.emitir(Oficio.objects.get(pk=c.oficio.pk), c.usuarios["operador"])
    aviso.refresh_from_db()
    assert aviso.situacao == S.OBSOLETA
