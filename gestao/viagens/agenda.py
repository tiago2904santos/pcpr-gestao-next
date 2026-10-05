"""As fontes de Viagens na agenda (paridade com `agenda/fontes.py`, `agenda/prazos.py` e
`agenda/feriados.py` da referência): as viagens, os prazos de saque das diárias e os
feriados nacionais (os mesmos dias que os prazos pulam). A permissão é a das telas de
Viagens (policies), como na referência. Registradas no `ready` do app.

Como na referência, a fonte é a Viagem (o agrupador): ofício sem viagem não aparece.
"""

from __future__ import annotations

from datetime import date

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from gestao.plataforma.agenda import Compromisso, Fonte, registrar_fonte

from . import policies
from .dominio import prestacao as dominio
from .models import Oficio, Viagem
from .viagem import periodo_curto

DIAS_DE_AVISO = 7  # referência: o prazo entra em destaque até 7 dias antes


def _pode_viagens(usuario) -> bool:
    return usuario.has_perm("viagens.view_viagem")


def _pessoas_da_viagem(v: Viagem) -> tuple[str, ...]:
    nomes: list[str] = []
    for o in v.oficios.all():
        if o.situacao == Oficio.Situacao.CANCELADO:
            continue
        nomes.extend(x.servidor.nome for x in o.viajantes.all())
        if o.motorista_externo_servidor is not None:
            nomes.append(o.motorista_externo_servidor.nome)
    return tuple(dict.fromkeys(nomes))


def _viagens(usuario, inicio: date, fim: date) -> list[Compromisso]:
    consulta = (policies.viagens_visiveis(usuario)
                .filter(data_inicio__isnull=False, data_inicio__lte=fim)
                .filter(Q(data_fim__gte=inicio) | Q(data_fim__isnull=True,
                                                     data_inicio__gte=inicio))
                .select_related("unidade")
                .prefetch_related("destinos__municipio", "oficios__viajantes__servidor",
                                  "oficios__motorista_externo_servidor")
                .order_by("data_inicio", "pk"))
    saida = []
    for v in consulta:
        if v.data_inicio is None:  # filtrado acima; o tipo não sabe
            continue
        destinos = [str(d.municipio) for d in v.destinos.all()]
        motivo = (v.motivo or "").strip()
        titulo = ", ".join(destinos) or v.titulo or "Viagem"
        if motivo:
            titulo += f" — {motivo[:80]}"
        cancelada = v.situacao == Viagem.Situacao.CANCELADA
        saida.append(Compromisso(
            fonte="viagem", chave=f"viagem-{v.pk}", titulo=titulo, inicio=v.data_inicio,
            fim=v.data_fim, url=reverse("viagens:editar_viagem", args=[v.pk]),
            situacao="Cancelada" if cancelada else v.get_situacao_display(),
            tom="perigo" if cancelada else "info", encerrado=cancelada,
            meu=v.criado_por_id == getattr(usuario, "pk", None),
            pessoas=_pessoas_da_viagem(v),
            detalhes=(("Destino", ", ".join(destinos)),
                      ("Período", periodo_curto(v.data_inicio, v.data_fim)),
                      ("Tipo", v.titulo), ("Motivo", motivo),
                      ("Unidade", v.unidade.sigla or v.unidade.nome),
                      ("Cancelada", v.motivo_cancelamento if cancelada else ""))))
    return saida


def _pode_prazos(usuario) -> bool:
    return usuario.has_perm("viagens.view_prestacaoservidor")


def _situacao_do_prazo(data: date, hoje: date) -> tuple[str, str]:
    faltam = (data - hoje).days
    if faltam < 0:
        return "Vencido", "perigo"
    if faltam == 0:
        return "Vence hoje", "aviso"
    if faltam <= DIAS_DE_AVISO:
        return f"Vence em até {DIAS_DE_AVISO} dias", "aviso"
    return "No prazo", "neutro"


def _prazos_de_saque(usuario, inicio: date, fim: date) -> list[Compromisso]:
    hoje = timezone.localdate()
    consulta = (policies.prestacoes_visiveis(usuario)
                .filter(finalizada_em__isnull=True, prazo_limite_saque__gte=inicio,
                        prazo_limite_saque__lte=fim,
                        prestacao__oficio__situacao=Oficio.Situacao.EMITIDO)
                .select_related("servidor", "prestacao__oficio")
                .order_by("prazo_limite_saque", "pk"))
    saida = []
    for ps in consulta:
        oficio = ps.prestacao.oficio
        if ps.prazo_limite_saque is None:  # filtrado acima
            continue
        situacao, tom = _situacao_do_prazo(ps.prazo_limite_saque, hoje)
        saida.append(Compromisso(
            fonte="prazo_diarias", chave=f"prazo-{ps.pk}",
            titulo=f"Saque das diárias — {ps.servidor.nome} · {oficio}",
            inicio=ps.prazo_limite_saque, prazo=True, situacao=situacao, tom=tom,
            url=reverse("viagens:prestacoes") + f"?q={oficio.numero_formatado}",
            detalhes=(("Servidor", ps.servidor.nome), ("Ofício", str(oficio)),
                      ("Prazo de saque", f"{ps.prazo_limite_saque:%d/%m/%Y}"),
                      ("Situação da prestação", ps.get_situacao_display()))))
    return saida


def _feriados(usuario, inicio: date, fim: date) -> list[Compromisso]:
    saida = []
    for ano in range(inicio.year, fim.year + 1):
        for dia, nome in dominio.feriados_nacionais_com_nome(ano).items():
            if inicio <= dia <= fim:
                saida.append(Compromisso(fonte="feriados", chave=f"feriado-{dia:%Y%m%d}",
                                         titulo=nome, inicio=dia, faixa=True,
                                         situacao="Feriado nacional"))
    return saida


def registrar() -> None:
    registrar_fonte(Fonte("viagem", "Viagens", _pode_viagens, _viagens, ordem=10))
    registrar_fonte(Fonte("prazo_diarias", "Prazos de saque das diárias", _pode_prazos,
                          _prazos_de_saque, ordem=20))
    registrar_fonte(Fonte("feriados", "Feriados nacionais",
                          lambda usuario: bool(getattr(usuario, "is_authenticated", False)),
                          _feriados, ordem=90))
