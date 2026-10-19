"""Pendência manual por destinatário/prestação. Não chama um provedor de mensagens."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import CharField, Value
from django.db.models.functions import Cast, Concat
from django.urls import reverse
from django.utils import timezone

from gestao.automacao import comunicacoes, links
from gestao.automacao.models import Comunicacao, ConteudoComunicacao, LinkAcesso
from gestao.plataforma.models import Notificacao
from gestao.plataforma.notificacoes import notificar, usuarios_do_grupo

from . import assinados, km_link, pacotes, policies, relatorio
from .documentos_versoes import projetar_documentos
from .dominio import envios
from .dominio import relatorio as dominio_rt
from .models import DiarioBordo, Documento, Oficio, PrestacaoServidor, RelatorioTecnico, ViaAssinada

S = Comunicacao.Situacao
TIPO = "viagens.diarias_liberadas"
SALT = "viagens.envio-manual.v1"
MUDOU = "Os dados mudaram. Atualize a pendência e prepare a mensagem novamente."


@dataclass
class Pacote:
    ps: PrestacaoServidor
    aviso: str = ""
    oficio: Documento | ViaAssinada | None = None
    dados_rt: dict = field(default_factory=dict)
    diario: DiarioBordo | None = None
    faltas: list[str] = field(default_factory=list)
    versao: str = ""

    @property
    def tem_conteudo(self) -> bool:
        return bool(self.aviso or self.oficio or self.dados_rt or self.diario)


def manual() -> bool:
    return settings.AUTOMACAO_TRANSPORTE == "manual"


def elegiveis():
    return (PrestacaoServidor.objects.filter(
        removida_em__isnull=True, arquivada_em__isnull=True, finalizada_em__isnull=True,
        servidor__ativo=True, prestacao__oficio__situacao=Oficio.Situacao.EMITIDO)
        .select_related("servidor", "prestacao__oficio__unidade"))


def ler(ps: PrestacaoServidor) -> Pacote:
    p = Pacote(ps)
    o = ps.prestacao.oficio
    if (ps.removida_em or ps.arquivada_em or ps.finalizada_em
            or not ps.servidor.ativo or o.situacao != Oficio.Situacao.EMITIDO):
        raise ValueError("Esta prestação não está aberta para envio.")
    if ps.data_liberacao_diarias:
        p.aviso = f"liberadas em {ps.data_liberacao_diarias:%d/%m/%Y}."
        if ps.prazo_limite_saque:
            p.aviso += f" Prazo para saque: {ps.prazo_limite_saque:%d/%m/%Y}."
        p.aviso += " Depois do saque, encaminhe o comprovante ao setor."
    else:
        p.faltas.append("Saque: ainda não há data de liberação informada.")
    projecao = projetar_documentos(o, documentos=list(o.documentos.all()),
                                  vias=list(assinados.vigentes_do(o).values()))
    p.oficio = projecao.via_assinada("oficio") or projecao.pdf_original("oficio")
    if p.oficio is None:
        p.faltas.append("Ofício: aguarde a geração do PDF corrente.")
    rt = RelatorioTecnico.objects.filter(prestacao=ps.prestacao).first()
    if rt and dominio_rt.preenchido({c: getattr(rt, c) for c in dominio_rt.CAMPOS_TEXTO}):
        rt.prestacao = ps.prestacao
        p.dados_rt = relatorio.dados_do_documento(rt, ps)
    else:
        p.faltas.append("RT: preencha o relatório técnico antes de compartilhar.")
    d = DiarioBordo.objects.filter(prestacao=ps.prestacao).first()
    if d:
        d.prestacao = ps.prestacao
        pessoa = km_link.responsavel(d)
        if pessoa and pessoa.pk == ps.servidor_id and not km_link.motivo_inelegivel(d):
            p.diario = d
    if p.diario is None:
        p.faltas.append("KM: disponível apenas para o motorista responsável, em viagem elegível.")
    # A data de impressão muda por dia, mas não cria uma nova pendência por si só.
    rt_estavel = {k: v for k, v in p.dados_rt.items() if k != "data_extenso"}
    base = [ps.pk, o.numero_formatado, ps.servidor.nome,
            envios.telefone_whatsapp(ps.servidor.telefone),
            p.aviso, str(getattr(p.oficio, "arquivo", "")),
            getattr(p.oficio, "sha256", ""), rt_estavel,
            km_link.versao(p.diario) if p.diario else ""]
    p.versao = hashlib.sha256(json.dumps(base, cls=DjangoJSONEncoder, sort_keys=True,
                                       ensure_ascii=False).encode()).hexdigest()
    return p


def pendencias(usuario):
    return Comunicacao.objects.filter(
        contexto__manual=True, recurso__in=policies.prestacoes_visiveis(usuario).annotate(
            recurso=Concat(Value("viagens.prestacaoservidor:"), Cast("pk", CharField())))
        .values("recurso")).select_related("servidor", "criada_por", "aprovada_por")


@transaction.atomic
def enfileirar(ps: PrestacaoServidor, autor=None) -> Comunicacao | None:
    # O mesmo lock ordena liberação, rotina, preparação e confirmação desta prestação.
    ps = (elegiveis().select_for_update(of=("self",)).filter(pk=ps.pk).first())
    if ps is None:
        return None
    return _registrar_pacote(ler(ps), autor)


def _registrar_pacote(pacote: Pacote, autor) -> Comunicacao | None:
    ps = pacote.ps
    if not pacote.tem_conteudo:
        return None
    chave = f"manual:{ps.pk}:{pacote.versao}"
    anterior = Comunicacao.objects.filter(chave=chave).first()
    recurso = f"viagens.prestacaoservidor:{ps.pk}"
    for c in Comunicacao.objects.select_for_update().filter(
            recurso=recurso, contexto__manual=True,
            situacao__in=Comunicacao.PENDENTES).exclude(versao=pacote.versao):
        c.situacao, c.motivo = S.OBSOLETA, "O conteúdo da pendência foi atualizado."
        c.revisao += 1
        c.save()
    destino = reverse("viagens:envio_manual", args=[ps.pk])
    if anterior is not None:
        if anterior.situacao == S.MANUAL:
            Notificacao.objects.filter(link=destino, lida=False).update(lida=True)
        if anterior.situacao != S.OBSOLETA:
            return anterior
        # Uma correção desfeita pode restaurar um conteúdo antigo ainda não enviado.
        # A revisão nova invalida a conferência que existia antes de ficar obsoleto.
        c = anterior
        c.revisao += 1
    else:
        c = comunicacoes.agendar(
            tipo=TIPO, servidor_id=ps.servidor_id, recurso=recurso, chave=chave,
            unidade_id=ps.prestacao.oficio.unidade_id, criada_por=autor,
            contexto={"ps": ps.pk, "manual": True,
                      "oficio": ps.prestacao.oficio.numero_formatado}, versao=pacote.versao)
    c.situacao, c.expira_em = S.AGUARDANDO_APROVACAO, None
    c.motivo = "Envio manual pendente: prepare a mensagem e confirme depois de enviá-la."
    c.save()
    pessoas = list(usuarios_do_grupo("OPERADOR_VIAGENS").filter(
        lotacao__unidade_id=c.unidade_id))
    if autor is not None:
        pessoas.append(autor)
    ja_avisados = set(Notificacao.objects.filter(link=destino, lida=False)
                     .values_list("usuario_id", flat=True))
    notificar([u for u in pessoas if u.pk not in ja_avisados],
              f"Envio pendente: {ps.servidor.nome}",
              f"Reúna os documentos do Ofício {ps.prestacao.oficio.numero_formatado} "
              "e envie pelo seu WhatsApp.", destino)
    return c


def sincronizar(usuario=None) -> int:
    if not manual():
        return 0
    qs = elegiveis()
    if usuario is not None:
        qs = qs.filter(pk__in=policies.prestacoes_visiveis(usuario).values("pk"))
    total = 0
    for ps in qs.iterator(chunk_size=100):
        if usuario is not None and not policies.pode_editar_prestacao(usuario, ps):
            continue
        antes = Comunicacao.objects.filter(contexto__manual=True, contexto__ps=ps.pk).count()
        c = enfileirar(ps, usuario)
        total += int(c is not None and Comunicacao.objects.filter(
            contexto__manual=True, contexto__ps=ps.pk).count() > antes)
    return total


def _ps_travada(usuario, pk: int) -> PrestacaoServidor:
    ps = elegiveis().select_for_update(of=("self",)).filter(pk=pk).first()
    if ps is None:
        raise ValueError("Esta prestação não está aberta para envio.")
    policies.exigir(policies.pode_editar_prestacao(usuario, ps),
                    "Você não pode preparar envios desta prestação.")
    return ps


@transaction.atomic
def preparar(usuario, ps_pk: int) -> tuple[Comunicacao, str, Pacote]:
    ps = _ps_travada(usuario, ps_pk)
    if not envios.telefone_whatsapp(ps.servidor.telefone):
        raise ValueError("Cadastre um telefone brasileiro com DDD para este servidor.")
    pacote = ler(ps)
    c = _registrar_pacote(pacote, usuario)
    if c is None or c.situacao != S.AGUARDANDO_APROVACAO:
        raise ValueError("Este conteúdo já foi enviado ou não tem itens para enviar.")
    itens = []
    if pacote.oficio:
        itens.append(("Ofício", "segue anexo o documento da viagem para consulta", ""))
    if pacote.dados_rt:
        itens.append(("Relatório técnico (RT)", "segue anexo o seu relatório; confira, "
                      "providencie a assinatura e devolva o assinado ao setor", ""))
    if pacote.diario:
        datas = km_link.periodo(pacote.diario)
        if datas is None:
            raise ValueError(MUDOU)
        _, token = links.criar(
            escopo=LinkAcesso.Escopo.KM, recurso=km_link.recurso(pacote.diario.pk),
            servidor_id=ps.servidor_id, criado_por=usuario, comunicacao_id=c.pk,
            validade=km_link.valido_ate(datas[1]) - timezone.now(), revogar_anteriores=False)
        itens.append(("Quilometragem (KM)", "preencha o km inicial e final dos trechos "
                      "no diário de bordo. Link pessoal, válido até "
                      f"{km_link.valido_ate(datas[1]):%d/%m/%Y}", links.url_publica(token)))
    texto = envios.mensagem(ps.servidor.nome, ps.prestacao.oficio.numero_formatado,
                            pacote.aviso, itens)
    # O snapshot do RT e o texto com tokens ficam no conteúdo com retenção, fora da trilha.
    ConteudoComunicacao.objects.update_or_create(comunicacao=c, defaults={
        "texto": texto, "parametros": [{"rt": pacote.dados_rt}],
        "expira_em": timezone.now() + timedelta(days=30)})
    c.revisao += 1
    c.save(update_fields=["revisao", "atualizada_em"])
    ticket = signing.dumps({"c": c.pk, "ps": ps.pk, "r": c.revisao,
                            "v": pacote.versao}, salt=SALT)
    return c, ticket, pacote


@transaction.atomic
def confirmar(usuario, ps_pk: int, ticket: str) -> Comunicacao:
    ps = _ps_travada(usuario, ps_pk)
    try:
        dados = signing.loads(ticket, salt=SALT, max_age=1800)
    except signing.BadSignature:
        raise ValueError("A conferência venceu. Prepare a mensagem novamente.") from None
    c = Comunicacao.objects.select_for_update().filter(
        pk=dados.get("c"), contexto__manual=True, contexto__ps=ps.pk).first()
    if (not c or dados.get("ps") != ps.pk or dados.get("v") != ler(ps).versao
            or c.versao != dados.get("v")):
        raise ValueError(MUDOU)
    if c.situacao == S.MANUAL:
        return c  # repetição do mesmo POST não duplica o envio registrado
    if c.situacao != S.AGUARDANDO_APROVACAO or c.revisao != dados.get("r"):
        raise ValueError(MUDOU)
    c.situacao, c.origem_envio = S.MANUAL, "manual"
    c.enviada_em, c.aprovada_em, c.aprovada_por = timezone.now(), timezone.now(), usuario
    c.motivo = "O operador declarou ter enviado a mensagem manualmente pelo WhatsApp."
    c.revisao += 1
    c.save()
    Notificacao.objects.filter(link=reverse("viagens:envio_manual", args=[ps.pk]),
                               lida=False).update(lida=True)
    return c


def arquivos(usuario, ps_pk: int, comunicacao_pk: int, formato: str) -> tuple[bytes, str, str]:
    """Baixa só o ofício corrente e o RT deste destinatário, após a preparação."""
    if formato not in ("zip", "unico", "oficio", "rt"):
        raise ValueError("Escolha PDF único, PDFs separados, ofício ou RT.")
    ps = elegiveis().filter(pk=ps_pk).first()
    if ps is None:
        raise ValueError("Esta prestação não está aberta para download.")
    policies.exigir(policies.pode_ver_prestacao(usuario, ps),
                    "Você não pode baixar documentos desta prestação.")
    c = pendencias(usuario).filter(pk=comunicacao_pk, contexto__ps=ps.pk).first()
    pacote = ler(ps)
    if (c is None or c.versao != pacote.versao or not hasattr(c, "conteudo")
            or c.conteudo.expira_em <= timezone.now()
            or c.situacao not in (S.AGUARDANDO_APROVACAO, S.MANUAL)):
        raise ValueError(MUDOU)
    itens = []
    if pacote.oficio:
        documento = pacote.oficio

        def pdf_oficio():
            with documento.arquivo.open("rb") as arquivo:
                return arquivo.read()

        itens.append(pacotes.Item("oficio", "Ofício", "Da viagem", "PDF emitido",
                                  "oficio", pdf_oficio, pdf_oficio))
    if pacote.dados_rt:
        dados_rt = c.conteudo.parametros[0]["rt"]

        def pdf_rt():
            return relatorio.pdf_do_documento(dados_rt)

        itens.append(pacotes.Item("rt", "Relatório técnico", ps.servidor.nome,
                                  "Para conferir e assinar", "relatorio-tecnico", pdf_rt, pdf_rt))
    marcados = [i.valor for i in itens if formato in ("zip", "unico") or i.valor == formato]
    try:
        return pacotes.montar(itens, marcados, formato="pdf", versao="original",
                              saida="unico" if formato == "unico" else "separados",
                              nome_base=f"envio-{ps.pk}-{c.pk}")
    except OSError:
        raise ValueError("Um arquivo não está disponível. Gere o documento novamente "
                         "e atualize a pendência antes de enviar.") from None
    except pacotes.PacoteInvalido as erro:
        raise ValueError(str(erro)) from None


def atualizar_do_oficio(oficio_pk: int, autor=None) -> None:
    if manual():
        for ps in elegiveis().filter(prestacao__oficio_id=oficio_pk):
            enfileirar(ps, autor)
