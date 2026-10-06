"""Dados DEMO do Coffee Break (só PREVIEW; chamado por `viagens.demonstracao`).

Fictícios: dois fornecedores (CNPJ de teste), três contratos — um vigente, um vencendo em
menos de 60 dias, um com termo aditivo que estende a vigência —, lotes de dois exercícios
com municípios do Paraná e a configuração do ofício com valores neutros. As ordens de
serviço entram com a CB2."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from gestao.cadastros.models import Municipio

from .models import ConfiguracaoOficio, Contrato, Fornecedor, Lote, TermoAditivo

FORNECEDORES = (("Sabores do Paraná Buffet Ltda (fictício)", "11222333000181",
                 "contato@sabores.invalid"),
                ("Café & Cia Eventos EIRELI (fictício)", "44555666000172",
                 "pedidos@cafeecia.invalid"))
LOTES = ((1, ("Curitiba", "São José dos Pinhais", "Colombo", "Pinhais")),
         (2, ("Londrina", "Maringá", "Apucarana", "Arapongas")),
         (3, ("Cascavel", "Foz do Iguaçu", "Toledo")))


def semear(hoje: date) -> int:
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
    cfg = ConfiguracaoOficio.atual()
    cfg.destinatario = "Ao Grupo Administrativo Financeiro (DEMO)\nNesta"
    cfg.emails_ascom = "ascom@exemplo.invalid"
    cfg.save()
    return criados
