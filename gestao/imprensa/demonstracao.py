"""Dados DEMO do atendimento à imprensa (só PREVIEW; chamado por `viagens.demonstracao`).

Fictícios e determinísticos: equipe, veículos e uns sessenta pedidos espalhados pelos
últimos seis meses, em todas as situações — alguns com deadline vencido, hoje e nos
próximos dias, com fontes, respostas e andamentos, para o painel, a lista, a folha e a
agenda poderem ser avaliados.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from . import dominio
from .models import Andamento, Atendimento, Integrante, Veiculo

SEMENTE = 20261005
EQUIPE = ("Mariana", "Rafael", "Juliana", "Paulo", "Helena")
VEICULOS = ("RPC", "RIC", "Band Paraná", "CBN Curitiba", "Banda B", "Bem Paraná",
            "Plural", "Tribuna", "Rádio Clube", "g1 PR")
JORNALISTAS = ("Ana Souza", "Bruno Lima", "Carla Mendes", "Diego Rocha", "Elaine Prado",
               "Fábio Costa", "Gabriela Nunes", "Henrique Alves", "Isabela Moraes",
               "João Pires", "Karen Duarte", "Leonardo Teles")
PEDIDOS = (
    "Informações sobre a operação desta manhã (DEMO): número de presos e mandados cumpridos.",
    "Pedido de entrevista com o delegado responsável pelo caso (DEMO).",
    "Dados de furtos de veículos no último trimestre, por região (DEMO).",
    "Posicionamento da instituição sobre a reportagem de ontem (DEMO).",
    "Imagens da apreensão para o telejornal do meio-dia (DEMO).",
    "Andamento do inquérito sobre o golpe do falso empréstimo (DEMO).",
    "Orientações à população sobre golpes por aplicativo de mensagens (DEMO).",
    "Estatística de desaparecidos localizados no mês (DEMO).",
)
FONTES = ("Del. Fulano (fictício)", "Ascom DPCAP (fictício)", "Divisão de Homicídios (fictício)",
          "IML (fictício)", "Delegacia da Mulher (fictício)")
ANOTACOES = {
    "aguardando_fonte": "Fonte acionada; aguardando retorno.",
    "aguardando_produtora": "Equipe do veículo vai confirmar o horário da gravação.",
    "em_andamento_texto": "Preparando a nota por escrito.",
    "em_andamento_video": "Entrevista agendada com o delegado.",
    "aguardar_nova_solicitacao": "Jornalista vai voltar a pedir na semana que vem.",
    "proximo_mes": "Dados fechados só no mês que vem.",
    "atendido": "Nota enviada ao jornalista.",
    "nao_responder": "Assunto sob sigilo: a assessoria não vai se manifestar.",
}


def semear(usuario, hoje: date | None = None) -> int:
    """Cria os dados DEMO (as tabelas já foram limpas pelo seed de Viagens). Devolve quantos
    atendimentos foram criados."""
    hoje = hoje or timezone.localdate()
    rng = random.Random(SEMENTE)  # noqa: S311  # nosec B311 — determinismo, não segurança
    equipe = [Integrante.objects.create(nome=n) for n in EQUIPE]
    veiculos = [Veiculo.objects.create(nome=n) for n in VEICULOS]
    situacoes = [v for v, _r, _d, _t in dominio.SITUACOES]
    criados = 0
    for i in range(60):
        dias_atras = (i * 3 + rng.randint(0, 2)) if i < 50 else rng.randint(0, 4)
        data = hoje - timedelta(days=dias_atras)
        recente = dias_atras <= 6
        situacao = (rng.choice(situacoes[:7]) if recente and rng.random() < 0.7
                    else rng.choice(("atendido", "atendido", "atendido", "nao_responder",
                                     "atendido")))
        deadline = data + timedelta(days=rng.choice((0, 1, 1, 2, 3, 5)))
        fontes = rng.sample(FONTES, rng.randint(0, 2))
        horario = time(rng.randint(8, 18), rng.choice((0, 10, 25, 40, 55)))
        atendido = situacao == "atendido"
        a = Atendimento.objects.create(
            data=data, horario=horario, jornalista=rng.choice(JORNALISTAS),
            veiculo=rng.choice(veiculos) if rng.random() < 0.9 else None,
            contato=f"(41) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)} (fictício)",
            pedido=rng.choice(PEDIDOS), responsavel=rng.choice(equipe),
            deadline=deadline,
            fonte="\n\n".join(fontes),
            inicio_pedido="\n\n".join(f"{horario.hour + n + 1:02d}h{rng.randint(0, 5)}0"
                                      for n in range(len(fontes))),
            final_pedido="\n\n".join(f"{horario.hour + n + 2:02d}h{rng.randint(0, 5)}5"
                                     for n in range(len(fontes))) if atendido else "",
            resposta=("Nota enviada (DEMO): a instituição informa que o caso segue em "
                      "investigação e novas informações serão divulgadas oportunamente.")
            if atendido else "",
            horario_resposta=time(min(horario.hour + 3, 23), 15) if atendido else None,
            responsavel_resposta=rng.choice(equipe) if atendido else None,
            andamento=ANOTACOES.get(situacao, ""), situacao=situacao, criado_por=usuario)
        criados += 1
        if situacao != dominio.INICIAL:
            quando = timezone.make_aware(datetime.combine(data, horario)) + timedelta(hours=2)
            andamento = Andamento.objects.create(
                atendimento=a, situacao_anterior=dominio.INICIAL, situacao_nova=situacao,
                anotacao=ANOTACOES.get(situacao, ""), usuario=usuario)
            Andamento.objects.filter(pk=andamento.pk).update(em=quando)
    return criados
