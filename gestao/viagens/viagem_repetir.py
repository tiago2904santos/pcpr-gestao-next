"""Repetir viagem (módulo 8d, paridade com `duplicar.py` da referência): a mesma viagem em
outra data — tipos, motivo, destinos, roteiros, ofícios (equipe, viatura, trechos), OS,
plano e termos —, com todas as datas deslocadas pela diferença, a cidade principal trocada
se pedido, números novos e nada de protocolo, emissão ou assinatura. Cancelados ficam de fora.

Cada documento é criado pelo serviço do módulo dele (numeração, histórico e regras valem).
"""

from __future__ import annotations

from datetime import date, datetime

from django.db import transaction

from gestao.cadastros.models import Municipio

from . import ordens, planos, policies, services, termos
from .models import Oficio, OrdemServico, PlanoTrabalho, Roteiro, TermoAutorizacao, Viagem
from .viagem import ViagemInvalida, documentos

CAMPOS_DO_OFICIO = ("motivo", "custeio", "custeio_instituicao", "tipo_transporte", "viatura",
                    "transporte_descricao", "transporte_placa", "transporte_combustivel",
                    "porte_arma", "justificativa_modelo", "justificativa")


def data_base(viagem: Viagem) -> date | None:
    """O início da viagem ou, sem ele, a saída mais cedo dos roteiros dela."""
    if viagem.data_inicio:
        return viagem.data_inicio
    saidas = [t.saida_em for r in documentos(viagem).roteiros for t in r.trechos.all()]
    return min(saidas).date() if saidas else None


@transaction.atomic
def repetir(usuario, pk: int, nova_data: date, nova_cidade: Municipio | None = None) -> Viagem:
    original = Viagem.objects.get(pk=pk)
    policies.exigir(policies.pode_ver_viagem(usuario, original)
                    and policies.pode_criar_viagem(usuario), "Você não pode repetir viagens.")
    base = data_base(original)
    if base is None:
        raise ViagemInvalida("A viagem não tem data para servir de base. Informe o período "
                             "antes de repetir.")
    delta = nova_data - base
    destinos = [d.municipio for d in original.destinos.select_related("municipio")]
    principal = destinos[0] if destinos else None

    def cidade(m: Municipio) -> Municipio:
        return nova_cidade if (nova_cidade and principal and m == principal) else m

    def dia(d: date | None) -> date | None:
        return d + delta if d else None

    def hora(d: datetime | None) -> datetime | None:
        return d + delta if d else None

    nova = Viagem.objects.create(
        unidade=original.unidade, criado_por=usuario, titulo=original.titulo,
        descricao=original.descricao, motivo=original.motivo,
        data_inicio=dia(original.data_inicio), data_fim=dia(original.data_fim))
    nova.tipos.set(original.tipos.all())
    novos_destinos = [cidade(m) for m in destinos] or ([nova_cidade] if nova_cidade else [])
    for i, m in enumerate(dict.fromkeys(novos_destinos)):
        nova.destinos.create(municipio=m, ordem=i)

    docs = documentos(original)
    roteiros: dict[int, Roteiro] = {}
    for r in docs.roteiros:
        if not r.editavel:
            continue
        trechos = [services.TrechoInformado(cidade(t.origem).pk, cidade(t.destino).pk,
                                            t.saida_em + delta, t.chegada_em + delta)
                   for t in r.trechos.select_related("origem", "destino").order_by("ordem")]
        copia_rot = services.salvar_roteiro(usuario, None, {
            "quantidade_servidores": r.quantidade_servidores, "observacoes": r.observacoes},
            trechos)
        Roteiro.objects.filter(pk=copia_rot.pk).update(viagem=nova)
        roteiros[r.pk] = copia_rot

    oficios: dict[int, Oficio] = {}
    for o in docs.oficios:
        if o.situacao == Oficio.Situacao.CANCELADO:
            continue
        copia_ofi = services.criar_rascunho(usuario)
        dados = {c: getattr(o, c) for c in CAMPOS_DO_OFICIO}
        if o.roteiro_id in roteiros:
            dados["roteiro"] = roteiros[o.roteiro_id]
        copia_ofi = services.salvar_dados(copia_ofi, usuario, dados)
        viajantes = {}
        for v in o.viajantes.select_related("servidor").order_by("ordem", "pk"):
            if v.servidor_id:
                viajantes[v.pk] = services.adicionar_viajante(copia_ofi, usuario, v.servidor)
        motorista = next((v for v in o.viajantes.all() if v.motorista), None)
        if motorista is not None and motorista.pk in viajantes:
            services.definir_motorista(copia_ofi, usuario, viajantes[motorista.pk].pk)
        trechos = [services.TrechoInformado(cidade(t.origem).pk, cidade(t.destino).pk,
                                            t.saida_em + delta, t.chegada_em + delta)
                   for t in o.trechos.select_related("origem", "destino").order_by("ordem")]
        if trechos:
            services.salvar_trechos(copia_ofi, usuario, trechos)
        Oficio.objects.filter(pk=copia_ofi.pk).update(viagem=nova)
        oficios[o.pk] = copia_ofi

    for os_ in docs.ordens:
        if os_.cancelada:
            continue
        copia_ord, _ = ordens.salvar(
            usuario, oficios=[oficios[x.pk] for x in os_.oficios.all() if x.pk in oficios],
            tipo=os_.tipo, destinos=[cidade(d.municipio) for d in os_.destinos.all()],
            data_inicio=dia(os_.data_inicio), data_fim=dia(os_.data_fim),
            servidores=list(os_.servidores.all()), motivo=os_.motivo, funcoes=os_.funcoes)
        OrdemServico.objects.filter(pk=copia_ord.pk).update(viagem=nova)

    for p in docs.planos:
        if p.cancelado:
            continue
        planos.carregar(p)
        copia_pla, _ = planos.salvar(
            usuario, oficios=[oficios[x.pk] for x in p.oficios.all() if x.pk in oficios],
            programa=p.programa, programa_outros=p.programa_outros,
            data_inicio=dia(p.data_inicio), data_fim=dia(p.data_fim), horario=p.horario,
            destinos=[cidade(d.municipio) for d in p.destinos.all()],
            coordenador_adm=p.coordenador_adm, coordenador_adm_nome=p.coordenador_adm_nome,
            coordenador_adm_cargo=p.coordenador_adm_cargo,
            coordenador_adm_genero=p.coordenador_adm_genero,
            coordenador_op=p.coordenador_op, coordenador_op_nome=p.coordenador_op_nome,
            coordenador_op_cargo=p.coordenador_op_cargo,
            coordenador_op_genero=p.coordenador_op_genero,
            saida_em=hora(p.saida_em), chegada_em=hora(p.chegada_em),
            efetivo=[planos.LinhaInformada(e.cargo, e.quantidade, e.unidade)
                     for e in p.efetivo.all()],
            atividades=list(p.atividades.all()))
        PlanoTrabalho.objects.filter(pk=copia_pla.pk).update(viagem=nova)

    for t in docs.termos:
        if t.cancelado:
            continue
        ligado = oficios.get(t.oficio_id) if t.oficio_id else None
        if t.oficio_id and ligado is None:
            continue  # o ofício dele não foi repetido (cancelado)
        copia_ter = termos.salvar(
            usuario, oficio=ligado, evento=t.evento, data_inicio=dia(t.data_inicio),
            data_fim=dia(t.data_fim), destinos=[cidade(d.municipio) for d in t.destinos.all()],
            servidores=list(t.servidores.all()), viatura=t.viatura)
        TermoAutorizacao.objects.filter(pk=copia_ter.pk).update(viagem=nova)

    from .viagem import _situacao_pelos_documentos
    _situacao_pelos_documentos(nova)
    return nova

