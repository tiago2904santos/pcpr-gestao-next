"""Dados DEMO do Coffee Break (só PREVIEW; chamado por `viagens.demonstracao`).

Fictícios: dois fornecedores (CNPJ de teste), três contratos — um vigente, um vencendo em
menos de 60 dias, um com termo aditivo que estende a vigência —, lotes de dois exercícios
com municípios do Paraná, a configuração do ofício com valores neutros e ~20 solicitações
em todas as situações financeiras (aguardando nota, protocolo, atesto, ordem bancária,
envio, concluída, cancelada; uma faturada a menos, uma retroativa)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from gestao.cadastros.models import Municipio

from .models import (
    ConfiguracaoOficio,
    Contrato,
    Fornecedor,
    Lote,
    Movimento,
    Solicitacao,
    TermoAditivo,
)

FORNECEDORES = (("Sabores do Paraná Buffet Ltda (fictício)", "11222333000181",
                 "contato@sabores.invalid"),
                ("Café & Cia Eventos EIRELI (fictício)", "44555666000172",
                 "pedidos@cafeecia.invalid"))
LOTES = ((1, ("Curitiba", "São José dos Pinhais", "Colombo", "Pinhais")),
         (2, ("Londrina", "Maringá", "Apucarana", "Arapongas")),
         (3, ("Cascavel", "Foz do Iguaçu", "Toledo")))


def semear(hoje: date, usuario=None) -> int:
    a, b = (Fornecedor.objects.create(razao_social=r, cnpj=c, email=e, contato="Atendimento",
                                      telefone="(41) 3000-0000") for r, c, e in FORNECEDORES)
    vigente = Contrato.objects.create(
        fornecedor=a, numero="101/2025", numero_gms="5001", fiscal="Fiscal do contrato (DEMO)",
        vigencia_inicio=hoje - timedelta(days=200), vigencia_fim=hoje + timedelta(days=400),
        quantidade_contratada=20000, valor_unitario=Decimal("21.0700"),
        valor_total=Decimal("421400.00"), objeto="Fornecimento de coffee break para eventos.")
    vencendo = Contrato.objects.create(
        fornecedor=b, numero="88/2024", numero_gms="4420", vigencia_estimada=True,
        vigencia_inicio=hoje - timedelta(days=330), vigencia_fim=hoje + timedelta(days=40),
        quantidade_contratada=8000, valor_unitario=Decimal("18.5000"),
        objeto="Fornecimento de coffee break para eventos (interior).")
    com_aditivo = Contrato.objects.create(
        fornecedor=b, numero="45/2024", numero_gms="4100", termo_aditivo="1",
        vigencia_inicio=hoje - timedelta(days=500), vigencia_fim=hoje - timedelta(days=10),
        quantidade_contratada=5000, valor_unitario=Decimal("19.9000"))
    TermoAditivo.objects.create(contrato=com_aditivo, numero="1",
                                vigencia_inicio=hoje - timedelta(days=10),
                                vigencia_fim=hoje + timedelta(days=355))
    criados = 0
    for (numero, cidades), contrato in zip(LOTES, (vigente, vencendo, com_aditivo), strict=True):
        for exercicio, ativo in ((str(hoje.year - 1), False), (str(hoje.year), True)):
            lote = Lote.objects.create(
                contrato=contrato, numero=numero, exercicio=exercicio, ativo=ativo,
                quantidade_total=3000 if ativo else 2500, empenho=f"{exercicio}NE{numero:05d}",
                valor_empenho=Decimal("60000.00"), municipios_texto=", ".join(cidades),
                orientacoes="Entregar 30 minutos antes do início do evento (DEMO).")
            lote.municipios.set(Municipio.objects.filter(uf="PR", nome__in=cidades))
            criados += 1
    if usuario is not None:
        _solicitacoes(hoje, usuario)
    cfg = ConfiguracaoOficio.atual()
    cfg.destinatario = "Ao Grupo Administrativo Financeiro (DEMO)\nNesta"
    cfg.emails_ascom = "ascom@exemplo.invalid"
    cfg.save()
    return criados


EVENTOS = ("Posse da diretoria regional", "Reunião com lideranças comunitárias",
           "Capacitação de atendimento à mulher", "Formatura do curso de investigação",
           "Encontro de delegados do interior", "Lançamento de campanha de prevenção",
           "Seminário de inteligência policial", "Visita técnica do Conselho de Segurança")
# (dias do evento a partir de hoje, situação, quantidade)
PLANO = ((12, "nota", 40), (5, "nota", 60), (2, "nota", 25), (-3, "nota", 80),
         (-8, "protocolo", 50), (-12, "atesto", 35), (-15, "ob", 45), (-20, "envio", 30),
         (-25, "concluida", 70), (-30, "concluida", 55), (-35, "concluida", 40),
         (-40, "cancelada", 30), (20, "cancelada", 50), (30, "nota", 100), (-45, "concluida", 65),
         (-50, "faturada", 90), (8, "nota", 20), (-6, "nota", 35))


def _solicitacoes(hoje: date, usuario) -> None:
    lotes = list(Lote.objects.filter(ativo=True).select_related("contrato").prefetch_related(
        "municipios").order_by("numero"))
    seq = 0
    for i, (dias, situacao, qtd) in enumerate(PLANO):
        lote = lotes[i % len(lotes)]
        municipio = lote.municipios.order_by("nome").first()
        if municipio is None:
            continue
        evento = hoje + timedelta(days=dias)
        pedido = min(evento - timedelta(days=10), hoje)
        seq += 1
        s = Solicitacao.objects.create(
            lote=lote, municipio=municipio, data_solicitacao=pedido,
            numero=f"{seq}/{pedido.year}", descricao=EVENTOS[i % len(EVENTOS)] + " (DEMO)",
            quantidade=qtd, data_evento=evento, local_entrega="Auditório da unidade (fictício)",
            endereco="Rua Exemplo, 300 (fictícia)", bairro="Centro", cep="80000-000",
            responsavel="Servidor de plantão — (41) 3000-0000 (fictício)",
            valor_unitario=lote.contrato.valor_unitario, criado_por=usuario)
        marcos: dict = {}
        if situacao in ("protocolo", "atesto", "ob", "envio", "concluida", "faturada"):
            marcos["nota_fiscal"] = str(8900 + i)
            marcos["numero_oficio"] = f"{100 + i}/{(evento + timedelta(days=1)).year}"
            marcos["data_oficio"] = evento + timedelta(days=1)
        if situacao in ("atesto", "ob", "envio", "concluida", "faturada"):
            marcos["protocolo_pagamento"] = f"23.{100 + i:03d}.{500 + i:03d}-{i % 10}"
            marcos["protocolo_pcpr"] = marcos["protocolo_pagamento"]
        if situacao in ("ob", "envio", "concluida", "faturada"):
            marcos["atesto_em"] = evento + timedelta(days=3)
        if situacao in ("envio", "concluida", "faturada"):
            marcos["ordem_bancaria_em"] = evento + timedelta(days=8)
        if situacao in ("concluida", "faturada"):
            marcos["envio_empresa_em"] = evento + timedelta(days=9)
        if situacao == "faturada":
            marcos["quantidade_faturada"] = qtd - 10
        if situacao == "cancelada":
            marcos.update(cancelada=True, motivo_cancelamento="Evento adiado pela organização "
                                                              "(DEMO).")
        if marcos:
            Solicitacao.objects.filter(pk=s.pk).update(**marcos)
        Movimento.objects.create(solicitacao=s, acao=Movimento.Acao.CRIADA, usuario=usuario,
                                 texto=f"Solicitação {s.numero} registrada no {lote} (DEMO).")
