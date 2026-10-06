"""Fontes da Agenda do Coffee Break (CB7a; paridade com `agenda/fontes.py` e
`agenda/prazos.py` da referência): as OS com data do evento ("<descrição> (N)", Ativa ou
Cancelada — cancelada entra encerrada); e os prazos "Fim da vigência — Contrato/Termo
aditivo …" e "Certidão X vence — <fornecedor>" (só a vigente de cada tipo: a renovada não
marca mais o dia em que a antiga venceria). Só para quem tem o módulo."""

from __future__ import annotations

from datetime import date

from django.urls import reverse
from django.utils import timezone

from gestao.plataforma.agenda import Compromisso, Fonte, registrar_fonte

from . import policies
from .models import Certidao, Contrato, Solicitacao, TermoAditivo

DIAS_DE_AVISO = 30


def _situacao(data: date, hoje: date) -> tuple[str, str]:
    faltam = (data - hoje).days
    if faltam < 0:
        return "Vencido", "perigo"
    if faltam == 0:
        return "Vence hoje", "aviso"
    if faltam <= DIAS_DE_AVISO:
        return f"Vence em até {DIAS_DE_AVISO} dias", "aviso"
    return "No prazo", "neutro"


def _endereco(s: Solicitacao) -> str:
    return ", ".join(p for p in (s.endereco, s.bairro, s.cep) if p)


def _ordens(usuario, inicio: date, fim: date) -> list[Compromisso]:
    consulta = (Solicitacao.objects.filter(data_evento__gte=inicio, data_evento__lte=fim)
                .select_related("lote", "municipio").order_by("data_evento", "horario", "pk"))
    saida = []
    for s in consulta:
        if s.data_evento is None:  # filtrado acima
            continue
        descricao = " ".join(s.descricao.split())
        saida.append(Compromisso(
            fonte="coffee", chave=f"coffee-{s.pk}",
            titulo=f"{descricao[:70] or 'Coffee break'} ({s.quantidade})",
            inicio=s.data_evento, hora=f"{s.horario:%H:%M}" if s.horario else "",
            situacao="Cancelada" if s.cancelada else "Ativa",
            tom="neutro" if s.cancelada else "info", encerrado=s.cancelada,
            url=reverse("coffee:solicitacao", args=[s.pk]),
            meu=s.criado_por_id == getattr(usuario, "pk", None),
            detalhes=tuple((r, v) for r, v in (
                ("Evento", descricao), ("Local", s.local_entrega), ("Endereço", _endereco(s)),
                ("Município", f"{s.municipio.nome}/{s.municipio.uf}"),
                ("Quantidade", f"{s.quantidade} pessoas"), ("Número", s.numero),
                ("Lote", str(s.lote)),
                ("Cancelada", s.motivo_cancelamento if s.cancelada else "")) if v)))
    return saida


def _vigencia(inicio: date | None, fim: date) -> str:
    return f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}" if inicio else f"{fim:%d/%m/%Y}"


def _contratos(usuario, inicio: date, fim: date) -> list[Compromisso]:
    hoje = timezone.localdate()
    url = reverse("coffee:cadastros", args=["contratos"])
    saida = []
    for c in (Contrato.objects.filter(vigencia_fim__gte=inicio, vigencia_fim__lte=fim)
              .select_related("fornecedor").order_by("vigencia_fim", "numero")):
        if c.vigencia_fim is None:  # filtrado acima
            continue
        situacao, tom = _situacao(c.vigencia_fim, hoje)
        saida.append(Compromisso(
            fonte="coffee_contratos", chave=f"contrato-{c.pk}",
            titulo=f"Fim da vigência — Contrato {c.numero} ({c.fornecedor.razao_social})",
            inicio=c.vigencia_fim, prazo=True, situacao=situacao, tom=tom,
            url=f"{url}?editar={c.pk}",
            detalhes=tuple((r, v) for r, v in (
                ("Contrato", c.numero), ("Fornecedor", c.fornecedor.razao_social),
                ("Vigência", _vigencia(c.vigencia_inicio, c.vigencia_fim)),
                ("Estimada", "Sim — conferir no termo aditivo" if c.vigencia_estimada else ""))
                if v)))
    url = reverse("coffee:cadastros", args=["aditivos"])
    for a in (TermoAditivo.objects.filter(vigencia_fim__gte=inicio, vigencia_fim__lte=fim)
              .select_related("contrato__fornecedor").order_by("vigencia_fim", "numero")):
        if a.vigencia_fim is None:
            continue
        c = a.contrato
        situacao, tom = _situacao(a.vigencia_fim, hoje)
        saida.append(Compromisso(
            fonte="coffee_contratos", chave=f"aditivo-{a.pk}",
            titulo=(f"Fim da vigência — Termo aditivo {a.numero} · Contrato {c.numero} "
                    f"({c.fornecedor.razao_social})"),
            inicio=a.vigencia_fim, prazo=True, situacao=situacao, tom=tom,
            url=f"{url}?editar={a.pk}",
            detalhes=(("Termo aditivo", a.numero), ("Contrato", c.numero),
                      ("Fornecedor", c.fornecedor.razao_social),
                      ("Vigência", _vigencia(a.vigencia_inicio, a.vigencia_fim)))))
    return saida


def _certidoes(usuario, inicio: date, fim: date) -> list[Compromisso]:
    hoje = timezone.localdate()
    vigentes: dict[tuple[int, str], Certidao] = {}
    for c in (Certidao.objects.select_related("fornecedor")
              .order_by("fornecedor_id", "tipo", "-validade", "-criada_em")):
        vigentes.setdefault((c.fornecedor_id, c.tipo), c)
    saida = []
    for c in vigentes.values():
        if not inicio <= c.validade <= fim:
            continue
        situacao, tom = _situacao(c.validade, hoje)
        tipo = c.get_tipo_display()
        saida.append(Compromisso(
            fonte="coffee_certidoes", chave=f"certidao-{c.pk}",
            titulo=f"Certidão {tipo} vence — {c.fornecedor.razao_social}",
            inicio=c.validade, prazo=True, situacao=situacao, tom=tom,
            url=reverse("coffee:certidoes") + f"?anexar={c.fornecedor_id}:{c.tipo}",
            detalhes=(("Fornecedor", c.fornecedor.razao_social), ("Certidão", tipo),
                      ("Validade", f"{c.validade:%d/%m/%Y}"))))
    return sorted(saida, key=lambda x: (x.inicio, x.titulo))


def registrar() -> None:
    registrar_fonte(Fonte("coffee", "Coffee break", policies.pode_acessar, _ordens, ordem=30))
    registrar_fonte(Fonte("coffee_contratos", "Vigência dos contratos do coffee break",
                          policies.pode_acessar, _contratos, ordem=31))
    registrar_fonte(Fonte("coffee_certidoes", "Certidões dos fornecedores",
                          policies.pode_acessar, _certidoes, ordem=32))
