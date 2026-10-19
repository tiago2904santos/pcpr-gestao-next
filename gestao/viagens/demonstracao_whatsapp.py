"""PREVIEW: o link de km e os avisos à equipe pelo WhatsApp simulado (ADR 0046/0047; fluxos
10-4 e 10-2), depois do seed de Viagens e do da automação.

Monta o que uma pessoa precisa ver para avaliar: um `viagens.link_km` **enviado** (com o
link pessoal criado no envio — o token não aparece em lugar nenhum; a tela mostra a
comunicação), um aviso de viagem cancelada enviado à equipe, um lembrete de km agendado para
depois da volta e um pedido de aprovação pendente (um colega pediu, pela ferramenta
`comunicacoes.cancelar`, para cancelar esse lembrete; quem pede não aprova, então o DEMO
decide). Canal sempre simulado; números sintéticos que nunca recebem nada.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.db.models import Min, Q
from django.utils import timezone

from gestao.automacao import chaves, dominio, entrega, ferramentas
from gestao.automacao import comunicacoes as automacao
from gestao.automacao.models import Comunicacao, ContatoVerificado, DestinatarioAutorizado
from gestao.cadastros.models import Servidor
from gestao.identidade.models import Usuario
from gestao.integracoes.whatsapp import config as whatsapp_config
from gestao.integracoes.whatsapp.adaptadores import AdaptadorSimulado
from gestao.plataforma import ambiente

from . import comunicacoes_viagem as cv
from . import diario as servico_diario
from . import km_link
from .models import Oficio, Viajante

CANAL = "whatsapp"


def _contato(demo, servidor: Servidor) -> ContatoVerificado | None:
    """Contato verificado com opt-in (simulado) e na lista de testadores do DEMO."""
    if not dominio.e164_do_brasil(servidor.telefone):
        # Número sintético e estável (o DEMO nunca envia de verdade: canal simulado).
        servidor.telefone = f"419{(700_000_00 + servidor.pk) % 100_000_000:08d}"
        servidor.save(update_fields=["telefone"])
    endereco = dominio.e164_do_brasil(servidor.telefone)
    if not endereco:
        return None
    contato = automacao.contato_vigente(servidor.pk, CANAL)
    if contato is None:
        agora = timezone.now()
        contato = ContatoVerificado.objects.create(
            servidor=servidor, endereco=endereco, verificado_em=agora,
            metodo=ContatoVerificado.Metodo.SIMULADO, optin_em=agora,
            optin_origem=ContatoVerificado.OrigemOptin.SIMULADO, optin_versao="demo",
            criado_por=demo)
    if not DestinatarioAutorizado.objects.filter(endereco=contato.endereco,
                                                 removido_em__isnull=True).exists():
        DestinatarioAutorizado.objects.create(
            endereco=contato.endereco, descricao="Testador DEMO de Viagens (fictício)",
            adicionado_por=demo)
    return contato


def _diario_com_link():
    """O primeiro ofício emitido, de viatura, que ainda vai sair e tem motorista com
    cadastro — o diário dele recebe o link."""
    candidatos = (Oficio.objects.filter(situacao=Oficio.Situacao.EMITIDO,
                                        tipo_transporte=Oficio.TipoTransporte.VIATURA,
                                        prestacao__isnull=False)
                  .annotate(_saida=Min("trechos__saida_em"))
                  .filter(_saida__gte=timezone.now())
                  .select_related("prestacao").order_by("_saida", "pk"))
    for oficio in candidatos[:30]:
        d = servico_diario.obter(oficio.prestacao)
        if km_link.responsavel(d) is not None and not km_link.motivo_inelegivel(d):
            return d
    return None


def _rodar_worker() -> None:
    if whatsapp_config.carregar().real:
        raise RuntimeError("A demonstração só roda com o canal simulado.")
    antes = entrega.VERIFICAR_TRANSACAO
    entrega.VERIFICAR_TRANSACAO = False
    try:
        for _ in range(100):
            if not entrega.processar_uma(porta=AdaptadorSimulado()):
                break
    finally:
        entrega.VERIFICAR_TRANSACAO = antes


def _depois_da_volta(d) -> datetime:
    datas = km_link.periodo(d)
    dia = timezone.localtime(datas[1]).date() + timedelta(days=1) if datas else (
        timezone.localdate() + timedelta(days=7))
    return timezone.make_aware(datetime.combine(dia, time(9, 0)))


def semear(demo, hoje: date) -> dict[str, int]:
    ambiente.exigir_ambiente_de_demonstracao("semear o WhatsApp de Viagens")
    for fluxo in (cv.FLUXO_KM, cv.FLUXO_LEMBRETES_KM, cv.FLUXO_AVISOS):
        chaves.alterar(demo, chaves.nome_fluxo(fluxo), estado="ligada", modo="automatico",
                       motivo="Demonstração (canal simulado).")
    # 1. O link de km: o motorista ganha contato e o envio sai agora (no DEMO não se espera
    #    a véspera das 09:00).
    lembrete = None
    d = _diario_com_link()
    if d is not None:
        _contato(demo, km_link.responsavel(d))
        cv._agendar_link(d, hoje, quando=timezone.now())
        pessoa = km_link.responsavel(d)
        lembrete = automacao.agendar(
            tipo=cv.LEMBRETE_KM, servidor_id=pessoa.pk, recurso=km_link.recurso(d.pk),
            chave=f"{cv.LEMBRETE_KM}:{d.pk}:demo", unidade_id=d.prestacao.oficio.unidade_id,
            criada_por=demo, contexto={"diario": d.pk, "servidor": pessoa.pk},
            versao=km_link.versao(d), agendada_para=_depois_da_volta(d))
    # 2. Aviso de viagem cancelada a quem estava no ofício (o seed de Viagens cancelou antes
    #    de haver contatos; o aviso é o que o cancelamento teria agendado).
    cancelado = (Oficio.objects.filter(situacao=Oficio.Situacao.CANCELADO,
                                       viajantes__isnull=False)
                 .order_by("-situacao_anterior", "pk").distinct().first())
    if cancelado is not None:
        for v in (Viajante.objects.filter(oficio=cancelado).select_related("servidor")
                  .order_by("ordem", "pk")[:2]):
            _contato(demo, v.servidor)
        cv.oficio_cancelado(cancelado, demo, Oficio.Situacao.EMITIDO)
    _rodar_worker()
    # 3. Um pedido de aprovação pendente: um colega da unidade pede para cancelar o lembrete
    #    (ferramenta irreversível = sempre passa por uma pessoa; quem pede não aprova).
    pedidos = 0
    if lembrete is not None:
        # unidade_id=None vira IS NULL (quem não tem lotação), como o filtro direto faria.
        da_unidade = (Q(lotacao__unidade_id=lembrete.unidade_id)
                      if lembrete.unidade_id is not None else Q(lotacao__unidade_id__isnull=True))
        colega = (Usuario.objects.filter(da_unidade, is_active=True,
                                         groups__name="OPERADOR_VIAGENS")
                  .exclude(pk=demo.pk).order_by("pk").first())
        if colega is not None:
            resultado = ferramentas.executar("comunicacoes.cancelar",
                                             {"comunicacao": lembrete.pk}, usuario=colega,
                                             origem="tela")
            pedidos = int(resultado.aprovacao is not None)
    from gestao.plataforma.models import Notificacao

    Notificacao.objects.filter(titulo__startswith="Automação:").delete()
    return {"links_km": Comunicacao.objects.filter(tipo=cv.LINK_KM,
                                                   situacao=Comunicacao.Situacao.ENVIADA)
            .count(), "pedidos": pedidos}
