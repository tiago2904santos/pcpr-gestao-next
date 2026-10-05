"""Dados DEMO das palestras e eventos (só PREVIEW; chamado por `viagens.demonstracao`).

Fictícios e determinísticos: temas, palestrantes (alguns ligados a servidores do cadastro
DEMO), respostas padrão com marcadores e uns quarenta pedidos em todos os status —
próximos agendados, aguardando retorno, atendidos com público —, para o painel, a lista,
a folha e a agenda poderem ser avaliados.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from gestao.cadastros.models import Municipio, Servidor

from . import dominio
from .models import Andamento, Palestra, Palestrante, RespostaEnviada, RespostaPadrao, Tema

SEMENTE = 20261007
TEMAS = ("Golpes pela internet", "Violência contra a mulher", "Prevenção às drogas",
         "Segurança nas escolas", "Crimes contra idosos", "Educação no trânsito")
PALESTRANTES = (("Del. Ana Ribeiro (fictícia)", "DPCAP", "Golpes pela internet"),
                ("Inv. Bruno Teles (fictício)", "Delegacia da Mulher", "Violência contra a mulher"),
                ("Del. Carla Moura (fictícia)", "DENARC", "Prevenção às drogas"),
                ("Esc. Diego Paz (fictício)", "ASCOM", "Segurança nas escolas"))
SOLICITANTES = ("Colégio Estadual do Bairro (fictício)", "Associação de Moradores (fictícia)",
                "Empresa de Logística (fictícia)", "Escola Municipal Central (fictícia)",
                "Igreja da Comunidade (fictícia)", "Universidade Regional (fictícia)")
RESPOSTAS = (
    ("Confirmação de agenda",
     "Olá, {solicitante}! Confirmamos a palestra para {data}, às {horario}, em {municipio}, "
     "com {palestrante}. Tema: {tema}. Qualquer dúvida, estamos à disposição. ASCOM/PCPR"),
    ("Pedido de mais informações",
     "Olá, {solicitante}! Para agendar, precisamos do público estimado, do endereço e de "
     "duas sugestões de data. Obrigado! ASCOM/PCPR"),
    ("Sem agenda no período",
     "Olá, {solicitante}! Infelizmente não temos palestrante disponível no período pedido. "
     "Podemos sugerir outra data? ASCOM/PCPR"),
)
CIDADES = (("Curitiba", "PR"), ("Londrina", "PR"), ("Ponta Grossa", "PR"), ("Cascavel", "PR"))


def semear(usuario, hoje: date | None = None) -> int:
    hoje = hoje or timezone.localdate()
    rng = random.Random(SEMENTE)  # noqa: S311  # nosec B311 — determinismo, não segurança
    temas = [Tema.objects.create(nome=n) for n in TEMAS]
    servidores = list(Servidor.objects.order_by("pk")[:2])
    municipios = [m for nome, uf in CIDADES
                  if (m := Municipio.objects.filter(nome=nome, uf=uf).first()) is not None]
    palestrantes = [Palestrante.objects.create(
        nome=nome, lotacao=lotacao, tema_abordagem=tema, divisao="Divisão (fictícia)",
        servidor=servidores[i] if i < len(servidores) else None,
        municipio=municipios[0] if municipios else None)
        for i, (nome, lotacao, tema) in enumerate(PALESTRANTES)]
    respostas = [RespostaPadrao.objects.create(tipo=t, mensagem=m) for t, m in RESPOSTAS]
    criadas = 0
    for i in range(40):
        pedido = hoje - timedelta(days=i * 4 + rng.randint(0, 3))
        if i < 8:  # próximas: pedidas recentemente, com data à frente
            status = rng.choice((dominio.AGENDADA, dominio.AGENDADA, "em_andamento",
                                 dominio.AGUARDANDO, dominio.PENDENTE))
            evento = hoje + timedelta(days=rng.randint(2, 40))
        else:
            status = rng.choice((dominio.ATENDIDA,) * 5 + (dominio.CANCELADA,))
            evento = pedido + timedelta(days=rng.randint(7, 25))
            if evento >= hoje:
                evento = hoje - timedelta(days=1)
        tem_data = status != dominio.PENDENTE
        telefone = f"(41) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
        p = Palestra.objects.create(
            data_solicitacao=pedido, canal_solicitacao=rng.choice(("email", "whatsapp",
                                                                   "telefone")),
            solicitante=rng.choice(SOLICITANTES), telefone=telefone,
            email=f"contato{i + 1}@example.invalid",
            assunto_email="Pedido de palestra (DEMO)",
            pedido_contato="Gostaríamos de uma palestra para os alunos e famílias (DEMO).",
            evento=rng.choice(("palestra", "palestra", "pcpr_na_comunidade", "evento")),
            data_inicio_evento=evento if tem_data else None,
            hora_inicio=time(rng.choice((9, 14, 19)), 0) if tem_data else None,
            municipio=rng.choice(municipios) if municipios else None,
            local="Auditório (fictício)", endereco="Rua Exemplo, 100 (fictícia)",
            bairro="Centro", cep="80000-000",
            quantidade_publico=rng.choice((40, 80, 120, 200)) if status == dominio.ATENDIDA
            else None,
            status=status, criado_por=usuario)
        p.temas.set(rng.sample(temas, rng.randint(1, 2)))
        if status in (dominio.AGENDADA, dominio.ATENDIDA):
            p.palestrantes.set(rng.sample(palestrantes, 1))
        criadas += 1
        if status != dominio.PENDENTE:
            quando = timezone.make_aware(datetime.combine(pedido, time(10, 0)))
            a = Andamento.objects.create(palestra=p, status_anterior=dominio.PENDENTE,
                                         status_novo=status, usuario=usuario,
                                         anotacao="Tratativa com o solicitante (DEMO).")
            Andamento.objects.filter(pk=a.pk).update(em=quando)
        if status in (dominio.AGENDADA, dominio.ATENDIDA):
            r = RespostaEnviada.objects.create(palestra=p, tipo=respostas[0].tipo,
                                               texto="Confirmação enviada (DEMO).",
                                               usuario=usuario)
            RespostaEnviada.objects.filter(pk=r.pk).update(
                em=timezone.make_aware(datetime.combine(pedido, time(11, 0))))
    return criadas
