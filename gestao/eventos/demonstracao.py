"""Dados DEMO das solicitações de evento social (só PREVIEW; chamado por
`viagens.demonstracao`).

Fictícios e determinísticos: textos prontos do despacho, duas unidades móveis, o modelo de
um tipo de evento e umas trinta solicitações em todos os status — rascunho, aguardando
despacho (algumas em cima da hora), devolvidas, deferidas próximas, atendidas, não
atendidas e canceladas —, de vários responsáveis, para a lista, as filas, a folha, o
despacho e a agenda poderem ser avaliados. Os catálogos vêm da carga inicial (migração).
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from gestao.cadastros.models import Municipio, Servidor

from . import dominio
from .models import (
    Equipe,
    Movimento,
    OrgaoResponsavel,
    Servico,
    Solicitacao,
    SolicitacaoEquipe,
    SolicitacaoServico,
    TextoDespacho,
    TipoEvento,
    TipoEventoEquipe,
    UnidadeMovel,
)

SEMENTE = 20261008
TEXTOS = (("Deferido — equipe designada",
           "Deferido. Encaminhe-se à equipe designada para as providências de deslocamento."),
          ("Não atendido — sem efetivo",
           "Não atendido por falta de efetivo disponível no período solicitado."),
          ("Devolvido — completar dados",
           "Devolvido para complementar o local, o endereço e o contato do solicitante."))
UNIDADES_MOVEIS = ("Unidade Móvel 01 (fictícia)", "Unidade Móvel 02 (fictícia)")
SOLICITANTES = (("Vereadora Ana Lima (fictícia)", "Câmara Municipal"),
                ("Prefeito Carlos Souza (fictício)", "Prefeitura"),
                ("Diretora Bruna Reis (fictícia)", "Colégio Estadual"),
                ("Coordenador Davi Melo (fictício)", "Associação de Moradores"))
LOCAIS = ("Ginásio de Esportes (fictício)", "Praça Central (fictícia)",
          "Salão Paroquial (fictício)", "Escola Municipal (fictícia)")
CIDADES = (("Curitiba", "PR"), ("Londrina", "PR"), ("Ponta Grossa", "PR"),
           ("Cascavel", "PR"), ("Maringá", "PR"))
# (status, deslocamento do início do evento em dias a partir de hoje)
PLANO = ((dominio.RASCUNHO, 30), (dominio.RASCUNHO, None),
         (dominio.AGUARDANDO, 5), (dominio.AGUARDANDO, 8), (dominio.AGUARDANDO, 18),
         (dominio.AGUARDANDO, 25), (dominio.AGUARDANDO, 40),
         (dominio.DEVOLVIDA, 20), (dominio.DEVOLVIDA, 33),
         (dominio.DEFERIDA, 0), (dominio.DEFERIDA, 3), (dominio.DEFERIDA, 9),
         (dominio.DEFERIDA, 15), (dominio.DEFERIDA, 22), (dominio.DEFERIDA, -2),
         *((dominio.ATENDIDA, -d) for d in (6, 12, 20, 31, 45, 60, 75, 90)),
         (dominio.NAO_ATENDIDA, 12), (dominio.NAO_ATENDIDA, -15),
         (dominio.CANCELADA, 7), (dominio.CANCELADA, -25))


def _em(dia: date, hora: int) -> datetime:
    return timezone.make_aware(datetime.combine(dia, time(hora, 0)))


def _movimento(s: Solicitacao, acao: str, de: str, para: str, usuario, quando: datetime,
               observacao: str = "") -> None:
    m = Movimento.objects.create(solicitacao=s, acao=acao, status_anterior=de, status_novo=para,
                                 observacao=observacao, usuario=usuario)
    Movimento.objects.filter(pk=m.pk).update(em=quando)


def _catalogos() -> tuple[list[TextoDespacho], list[UnidadeMovel]]:
    textos = [TextoDespacho.objects.get_or_create(nome=n, defaults={"texto": t})[0]
              for n, t in TEXTOS]
    unidades = [UnidadeMovel.objects.get_or_create(nome=n)[0] for n in UNIDADES_MOVEIS]
    tipo = TipoEvento.objects.filter(nome="PCPR na Comunidade").first()
    if tipo is not None:  # o modelo do tipo mais usado, para "Nova solicitação" vir pronta
        tipo.solicitante_padrao = "Coordenação do programa (fictícia)"
        tipo.cargo_padrao = "Delegacia-Geral"
        tipo.orgao_padrao = OrgaoResponsavel.objects.filter(nome="Delegacia-Geral").first()
        tipo.save()
        tipo.servicos_sugeridos.set(Servico.objects.filter(
            nome__in=("Emissão de CIN", "Atendimento social")))
        TipoEventoEquipe.objects.filter(tipo_evento=tipo).delete()
        for equipe in Equipe.objects.filter(nome__in=("Alfa", "Bravo")):
            TipoEventoEquipe.objects.create(tipo_evento=tipo, equipe=equipe, quantidade=3)
    return textos, unidades


def semear(usuario, hoje: date | None = None, outros: tuple = ()) -> int:
    """Cria as solicitações DEMO; `usuario` é o demo (despacha e vê todas); `outros` são
    responsáveis de outras unidades, para a fila "todas" ter gente diferente."""
    if usuario is None:
        return 0
    hoje = hoje or timezone.localdate()
    rng = random.Random(SEMENTE)  # noqa: S311  # nosec B311 — determinismo, não segurança
    textos, unidades = _catalogos()
    tipos = list(TipoEvento.objects.filter(ativo=True).order_by("nome"))
    servicos = list(Servico.objects.filter(ativo=True).order_by("nome"))
    equipes = list(Equipe.objects.filter(ativo=True).order_by("nome"))
    orgaos = list(OrgaoResponsavel.objects.filter(ativo=True).order_by("nome"))
    municipios = [m for nome, uf in CIDADES
                  if (m := Municipio.objects.filter(nome=nome, uf=uf).first()) is not None]
    motoristas = list(Servidor.objects.order_by("pk")[:4])
    responsaveis = [usuario, *outros]
    criadas = 0
    for i, (status, desloc) in enumerate(PLANO):
        inicio = hoje + timedelta(days=desloc) if desloc is not None else None
        fim = inicio + timedelta(days=rng.choice((0, 0, 1))) if inicio else None
        antecedencia = rng.choice((4, 15, 25, 40)) if status == dominio.AGUARDANDO else 30
        pedido = (inicio - timedelta(days=antecedencia)) if inicio else hoje
        pedido = min(pedido, hoje)
        nome, cargo = rng.choice(SOLICITANTES)
        com_unidade = i % 4 == 1 and status != dominio.RASCUNHO
        dono = responsaveis[i % len(responsaveis)]
        decidida = status in (dominio.DEFERIDA, dominio.ATENDIDA, dominio.NAO_ATENDIDA,
                              dominio.CANCELADA)
        decisao = {dominio.NAO_ATENDIDA: "nao_atender",
                   dominio.CANCELADA: "cancelado"}.get(status, "atender" if decidida
                                                       else "pendente")
        s = Solicitacao.objects.create(
            data_solicitacao=pedido, data_inicio_evento=inicio, data_fim_evento=fim,
            municipio=rng.choice(municipios) if municipios else None,
            tipo_evento=rng.choice(tipos) if tipos else None,
            solicitante_nome=nome, solicitante_cargo_unidade=cargo,
            contato=f"(41) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
            orgao_responsavel=rng.choice(orgaos) if orgaos else None,
            unidade_movel=com_unidade,
            unidade_movel_designada=rng.choice(unidades) if com_unidade else None,
            local_evento=rng.choice(LOCAIS), endereco="Rua Exemplo, 200 (fictícia)",
            bairro="Centro", cep="80000-000",
            protocolo=f"{rng.randint(10, 99)}.{rng.randint(100, 999)}.{rng.randint(100, 999)}"
                      f"-{rng.randint(0, 9)}" if i % 3 else "",
            descricao_complementar="Ação de cidadania com emissão de documentos (DEMO).",
            tipo_operacao=rng.choice(("diaria", "diaria", "extrajornada")),
            quantidade_cin=rng.choice((50, 100, 150)) if status == dominio.ATENDIDA else None,
            motorista=rng.choice(motoristas) if motoristas and decidida and i % 2 else None,
            status=status, decisao_dg=decisao, criado_por=dono,
            observacoes_dg=(textos[1].texto if status == dominio.NAO_ATENDIDA
                            else "Evento cancelado pelo solicitante (DEMO)."
                            if status == dominio.CANCELADA
                            else textos[0].texto if decidida else ""),
            decidido_por=usuario if decidida else None,
            decidido_em=_em(pedido + timedelta(days=1), 15) if decidida else None)
        if status != dominio.RASCUNHO or i == 0:
            for servico in rng.sample(servicos, min(len(servicos), rng.randint(1, 3))):
                SolicitacaoServico.objects.create(solicitacao=s, servico=servico)
            total = 0
            for equipe in rng.sample(equipes, min(len(equipes), rng.randint(1, 2))):
                qtd = rng.choice((2, 3, 4))
                total += qtd
                SolicitacaoEquipe.objects.create(solicitacao=s, equipe=equipe,
                                                 quantidade_servidores=qtd)
            Solicitacao.objects.filter(pk=s.pk).update(quantidade_servidores=total)
        _movimento(s, Movimento.Acao.CRIACAO, "", dominio.RASCUNHO, dono, _em(pedido, 9))
        if status != dominio.RASCUNHO:
            _movimento(s, Movimento.Acao.ENVIO, dominio.RASCUNHO, dominio.AGUARDANDO, dono,
                       _em(pedido, 10))
        if status == dominio.DEVOLVIDA:
            _movimento(s, Movimento.Acao.DEVOLUCAO, dominio.AGUARDANDO, dominio.DEVOLVIDA,
                       usuario, _em(pedido + timedelta(days=1), 14), textos[2].texto)
        if decidida:
            para = dominio.DEFERIDA if decisao == "atender" else status
            _movimento(s, Movimento.Acao.DECISAO, dominio.AGUARDANDO, para, usuario,
                       _em(pedido + timedelta(days=1), 15), s.observacoes_dg)
        if status == dominio.ATENDIDA and fim:
            _movimento(s, Movimento.Acao.CONCLUSAO, dominio.DEFERIDA, dominio.ATENDIDA, dono,
                       _em(min(fim + timedelta(days=1), hoje), 11))
        criadas += 1
    return criadas
