"""Dados DEMO das publicações (só PREVIEW; chamado por `viagens.demonstracao`).

Fictícios e determinísticos: equipe, unidades e umas setenta pautas nos últimos seis
meses, em todos os status — publicadas com horários (para o tempo médio), divulgação na
SESP/AEN, pendentes recentes —, para o painel, a lista, a folha e a agenda poderem ser
avaliados.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from . import dominio
from .models import Andamento, Integrante, Publicacao, UnidadeResponsavel

SEMENTE = 20261006
EQUIPE = ("Gabriela", "Murilo", "Natália", "Otávio", "Simone", "Caio")
UNIDADES = ("DP de Ponta Grossa (fictícia)", "DHPP (fictícia)", "DENARC (fictícia)",
            "Delegacia da Mulher de Londrina (fictícia)", "DP de Irati (fictícia)",
            "COPE (fictícia)", "DPCAP (fictícia)", "13ª SDP (fictícia)")
TITULOS = (
    "Polícia Civil prende suspeito de furtos em série (DEMO)",
    "Operação cumpre mandados contra golpe do falso empréstimo (DEMO)",
    "Delegacia orienta população sobre golpes por aplicativo (DEMO)",
    "Investigação localiza pessoa desaparecida (DEMO)",
    "Polícia Civil apreende drogas em ação conjunta (DEMO)",
    "Campanha alerta para fraudes em compras on-line (DEMO)",
    "Inquérito sobre homicídio é concluído (DEMO)",
    "Mutirão de atendimento à mulher no interior (DEMO)",
)
FONTES = ("Del. Fulano (fictício)", "Investigador Beltrano (fictício)",
          "Assessoria da unidade (fictícia)", "")
ANOTACOES = {
    "em_andamento": "Texto em redação; aguardando fotos.",
    "publicada": "Matéria no ar.",
    "cancelada": "Pauta derrubada pela unidade.",
}


def semear(usuario, hoje: date | None = None) -> int:
    """Cria os dados DEMO (as tabelas já foram limpas pelo seed de Viagens). Devolve quantas
    pautas foram criadas."""
    hoje = hoje or timezone.localdate()
    rng = random.Random(SEMENTE)  # noqa: S311  # nosec B311 — determinismo, não segurança
    equipe = [Integrante.objects.create(nome=n) for n in EQUIPE]
    unidades = [UnidadeResponsavel.objects.create(nome=n) for n in UNIDADES]
    criadas = 0
    for i in range(70):
        dias_atras = (i * 5 // 2 + rng.randint(0, 1)) if i < 62 else rng.randint(0, 3)
        data = hoje - timedelta(days=dias_atras)
        recente = dias_atras <= 5
        status = (rng.choice((dominio.PENDENTE, dominio.EM_ANDAMENTO)) if recente
                  and rng.random() < 0.6 else rng.choice((dominio.PUBLICADA,) * 6
                                                         + (dominio.CANCELADA,)))
        inicio = time(rng.randint(8, 16), rng.choice((0, 15, 30, 45)))
        publicada = status == dominio.PUBLICADA
        espera = timedelta(minutes=rng.randint(40, 600))
        no_ar = datetime.combine(data, inicio) + espera
        aen = rng.random() < 0.3 if publicada else None
        pauta = Publicacao.objects.create(
            data=data, jornalista=rng.choice(equipe), unidade=rng.choice(unidades),
            fonte=rng.choice(FONTES), inicio_pauta=inicio, titulo=rng.choice(TITULOS),
            status=status, andamento=ANOTACOES.get(status, ""),
            colocada_edicao=(datetime.combine(data, inicio) + espera / 2).time().replace(
                second=0, microsecond=0) if publicada else None,
            data_publicacao=no_ar.date() if publicada else None,
            horario_publicacao=no_ar.time().replace(second=0, microsecond=0)
            if publicada else None,
            revisao=rng.choice(equipe) if publicada else None,
            galeria_fotos=rng.choice(equipe) if publicada and rng.random() < 0.5 else None,
            bitly_grupos=True if publicada else None,
            enviado_sesp=rng.random() < 0.6 if publicada else None, publicado_aen=aen,
            link_site=f"https://example.invalid/pcpr/noticia-demo-{i + 1}" if publicada else "",
            link_aen=f"https://example.invalid/aen/noticia-demo-{i + 1}" if aen else "",
            criado_por=usuario)
        criadas += 1
        if status != dominio.PENDENTE:
            quando = timezone.make_aware(datetime.combine(data, inicio)) + espera
            andamento = Andamento.objects.create(
                publicacao=pauta, status_anterior=dominio.PENDENTE, status_novo=status,
                anotacao=ANOTACOES.get(status, ""), usuario=usuario)
            Andamento.objects.filter(pk=andamento.pk).update(em=quando)
    return criadas
