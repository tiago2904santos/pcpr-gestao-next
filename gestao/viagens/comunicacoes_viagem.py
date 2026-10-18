"""Viagens na automação, parte 2 (ADR 0047; fluxos 10-4 e 10-2): o link de km na véspera,
o lembrete de km depois da volta e os avisos à equipe quando o ofício é cancelado,
reagendado ou reemitido.

A automação não conhece Viagens: aqui ficam os ganchos (`registrar()`, no `ready`), as
rotinas diárias e as chamadas que os serviços de Viagens fazem na própria transação
(`oficio_cancelado`, `oficio_emitido`, `responsavel_do_diario`). Nada sai daqui para a
rede: `agendar` grava a comunicação e o worker envia depois.

Cada `preparar` relê o assunto **no momento do envio** e devolve a versão: mudou depois do
agendamento (outra saída, outro motorista, outra emissão, reativação), a mensagem antiga
fica obsoleta e não sai. O link de km é criado só no envio, pelo worker, depois de todas as
revalidações (`ganchos.PedidoLink`), e o token vive só no texto da mensagem — a cópia
guardada sai mascarada (`entrega.sem_credencial`).

Tudo é simulação: os textos dizem que os dados são fictícios.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.db.models import Max, Min
from django.urls import reverse
from django.utils import timezone

from gestao.automacao import comunicacoes as automacao
from gestao.automacao import ganchos

from . import diario as servico_diario
from . import km_link
from .models import DiarioBordo, Documento, Historico, Oficio, Viajante

LINK_KM = "viagens.link_km"
LEMBRETE_KM = "viagens.lembrete_km"
CANCELAMENTO = "viagens.aviso_cancelamento"
REAGENDAMENTO = "viagens.aviso_reagendamento"
SUBSTITUICAO = "viagens.aviso_substituicao"
RETIRADA = "viagens.aviso_retirada"
FLUXO_KM = "km_vespera"
FLUXO_LEMBRETES_KM = "km_lembretes"
FLUXO_AVISOS = "avisos_viagem"
RECURSO_OFICIO = "viagens.oficio"
CANAL = "whatsapp"
HORA_DO_ENVIO = time(9, 0)  # D−1 às 09:00 (decisão pendente no 10-4, item 3)


def _hash(*partes) -> str:
    return hashlib.sha256("|".join(str(p) for p in partes).encode()).hexdigest()[:16]


def _primeiro_nome(servidor) -> str:
    return (getattr(servidor, "nome", "") or "").split(" ")[0].title()


def _hora(dia: date) -> datetime:
    return timezone.make_aware(datetime.combine(dia, HORA_DO_ENVIO))


def _quando(dia: date) -> datetime:
    """O envio do dia: às 09:00, ou já, se a rotina rodou depois disso."""
    return max(timezone.now(), _hora(dia))


def _registrado(tipo: str) -> bool:
    """Sem o tipo registrado (automação fora do ar neste processo), os serviços seguem
    normalmente e nada é agendado."""
    return ganchos.tipo(tipo) is not None


def _quem_emitiu(oficio: Oficio):
    """Quem age pelo link e responde pelos avisos: quem emitiu o ofício (o histórico diz);
    sem registro, quem o criou."""
    h = (Historico.objects.filter(oficio=oficio, acao=Historico.Acao.EMITIDO)
         .exclude(usuario=None).select_related("usuario").order_by("-em", "-pk").first())
    return h.usuario if h else oficio.criado_por


def _comunicacao(contexto: dict):
    from gestao.automacao.models import Comunicacao

    pk = contexto.get("_comunicacao")
    return (Comunicacao.objects.select_related("contato").filter(pk=pk).first()
            if isinstance(pk, int) else None)


def _unidade(oficio: Oficio) -> str:
    return oficio.unidade.sigla or oficio.unidade.nome


# ================================================================== link de km na véspera
def _diario(contexto: dict) -> DiarioBordo | None:
    pk = contexto.get("diario")
    if not isinstance(pk, int):
        return None
    return (DiarioBordo.objects.select_related("prestacao__oficio__unidade",
                                               "motorista_servidor").filter(pk=pk).first())


def _preparar_link(contexto: dict) -> ganchos.Preparo:
    d = _diario(contexto)
    if d is None:
        return ganchos.Preparo(False, "O diário de bordo não existe mais.")
    if motivo := km_link.motivo_inelegivel(d):
        return ganchos.Preparo(False, motivo)
    pessoa = km_link.responsavel(d)
    if pessoa is None or pessoa.pk != contexto.get("servidor"):
        return ganchos.Preparo(False, "O responsável pelo diário mudou.")
    versao = km_link.versao(d)
    c = _comunicacao(contexto)
    if c is not None and c.versao and c.versao != versao:
        # Antes de criar o link: a versão antiga não pode revogar o link de ninguém.
        return ganchos.Preparo(False, "A viagem mudou depois do agendamento (outra versão).")
    datas = km_link.periodo(d)
    if datas is None:
        return ganchos.Preparo(False, "A viagem não tem mais datas.")
    ate = km_link.valido_ate(datas[1])
    url = ganchos.PLACEHOLDER_LINK  # o worker cria o link só se a mensagem for sair
    oficio = d.prestacao.oficio
    texto = (f"[TESTE — dados fictícios] Olá, {_primeiro_nome(pessoa)}. Este é o link para "
             f"lançar a quilometragem da sua próxima viagem com viatura:\n{url}\n\nAbra uma "
             "vez com internet antes de sair. Em cada trecho, anote o km do painel na saída "
             "e na chegada. Sem sinal, o que você digitar fica guardado no celular e é "
             "enviado quando a internet voltar. O link é pessoal, só dá acesso a este "
             f"diário e vale até {timezone.localtime(ate):%d/%m/%Y}. "
             f"Setor de viagens — {_unidade(oficio)}.")
    # Variáveis do contrato (VariaveisLinkKm): sem placa, horário, local ou nº do ofício.
    return ganchos.Preparo(True, versao=versao, texto=texto, parametros=(
        _primeiro_nome(pessoa), url, f"{timezone.localtime(ate):%d/%m/%Y}", _unidade(oficio)),
        link=ganchos.PedidoLink(escopo=km_link.ESCOPO, recurso=km_link.recurso(d.pk),
                                servidor_id=pessoa.pk, valido_ate=ate))


def _assunto_diario(recurso: str) -> ganchos.Assunto | None:
    d = km_link.diario_do_recurso(recurso)
    if d is None:
        return None
    return ganchos.Assunto(f"Diário de bordo — Ofício {d.prestacao.oficio.numero_formatado}",
                           reverse("viagens:diario", args=[d.prestacao_id]))


def _agendar_link(d: DiarioBordo, dia: date, autor=None, sufixo: str = "",
                  quando: datetime | None = None) -> bool:
    if not _registrado(LINK_KM) or km_link.motivo_inelegivel(d):
        return False
    pessoa = km_link.responsavel(d)
    if pessoa is None:
        return False  # sem cadastro não há contato: o setor entrega o link à mão
    oficio = d.prestacao.oficio
    versao = km_link.versao(d)
    automacao.agendar(tipo=LINK_KM, servidor_id=pessoa.pk, recurso=km_link.recurso(d.pk),
                      chave=f"{LINK_KM}:{d.pk}:{versao}{':' + sufixo if sufixo else ''}",
                      unidade_id=oficio.unidade_id,
                      criada_por=autor or _quem_emitiu(oficio),
                      contexto={"diario": d.pk, "servidor": pessoa.pk}, versao=versao,
                      agendada_para=quando or _quando(dia))
    return True


def _inicio(dia: date) -> datetime:
    return timezone.make_aware(datetime.combine(dia, time.min))


@transaction.atomic
def agendar_links_km(hoje: date | None = None) -> int:
    """Rotina diária: viagens de viatura que saem amanhã recebem o link do diário às 09:00
    de hoje (uma comunicação por diário e versão — rodar de novo não duplica). Pré-cria o
    diário (a primeira visita da folha faria o mesmo)."""
    if not _registrado(LINK_KM):
        return 0
    hoje = hoje or timezone.localdate()
    amanha = hoje + timedelta(days=1)
    oficios = (Oficio.objects.filter(situacao=Oficio.Situacao.EMITIDO,
                                     tipo_transporte=Oficio.TipoTransporte.VIATURA,
                                     prestacao__isnull=False)
               .annotate(_saida=Min("trechos__saida_em"))
               .filter(_saida__gte=_inicio(amanha),
                       _saida__lt=_inicio(amanha + timedelta(days=1)))
               .select_related("prestacao", "unidade"))
    total = 0
    for oficio in oficios:
        d = servico_diario.obter(oficio.prestacao)
        total += _agendar_link(d, hoje)
    return total


# ================================================================== lembrete de km
def _link_vigente(d: DiarioBordo, servidor_id: int):
    from gestao.automacao.models import LinkAcesso

    return (LinkAcesso.objects.filter(escopo=km_link.ESCOPO, recurso=km_link.recurso(d.pk),
                                      servidor_id=servidor_id, revogado_em__isnull=True,
                                      expira_em__gt=timezone.now())
            .order_by("-criado_em").first())


def _preparar_lembrete(contexto: dict) -> ganchos.Preparo:
    d = _diario(contexto)
    if d is None:
        return ganchos.Preparo(False, "O diário de bordo não existe mais.")
    if motivo := km_link.motivo_inelegivel(d):
        return ganchos.Preparo(False, motivo)
    pessoa = km_link.responsavel(d)
    if pessoa is None or pessoa.pk != contexto.get("servidor"):
        return ganchos.Preparo(False, "O responsável pelo diário mudou.")
    linhas = list(d.linhas.all())
    faltam = sum(1 for lin in linhas if lin.km_inicial is None or lin.km_final is None)
    if linhas and not faltam:
        return ganchos.Preparo(False, "Os km do diário já estão completos.")
    link = _link_vigente(d, pessoa.pk)
    if link is None:
        return ganchos.Preparo(False, "O link de km não vale mais (o setor gera um novo).")
    ate = f"{timezone.localtime(link.expira_em):%d/%m/%Y}"
    enviado = f"{timezone.localtime(link.criado_em):%d/%m}"
    total = len(linhas)
    texto = (f"[TESTE — dados fictícios] Olá, {_primeiro_nome(pessoa)}. Ainda faltam os km "
             f"de {faltam} de {total} trecho{'s' if total != 1 else ''} da sua última viagem "
             f"com viatura. Use o link que você recebeu em {enviado} — ele vale até {ate}. "
             "O que ficou guardado no celular é enviado quando você abrir o link com "
             "internet.")
    # Sem link novo: um link novo revogaria o do celular, com o que ainda não foi enviado.
    return ganchos.Preparo(True, versao=km_link.versao(d), texto=texto, parametros=(
        _primeiro_nome(pessoa), str(faltam), enviado, ate))


@transaction.atomic
def agendar_lembretes_km(hoje: date | None = None) -> int:
    """Rotina diária: no dia seguinte à chegada, diário com km faltando e link enviado
    recebe um lembrete (um por diário e versão). Quem age é quem agendou o link."""
    from gestao.automacao.models import Comunicacao

    if not _registrado(LEMBRETE_KM):
        return 0
    hoje = hoje or timezone.localdate()
    ontem = hoje - timedelta(days=1)
    oficios = (Oficio.objects.filter(situacao=Oficio.Situacao.EMITIDO,
                                     tipo_transporte=Oficio.TipoTransporte.VIATURA,
                                     prestacao__diario__isnull=False)
               # Janela larga pela chegada PREVISTA; a decisão é pela chegada EFETIVA abaixo
               # (`km_link.periodo`: os trechos realizados, se a viagem foi ajustada).
               .annotate(_chegada=Max("trechos__chegada_em"))
               .filter(_chegada__gte=_inicio(hoje - timedelta(days=30)),
                       _chegada__lt=_inicio(hoje + timedelta(days=30)))
               .select_related("prestacao__diario"))
    total = 0
    for oficio in oficios:
        d = oficio.prestacao.diario
        datas = km_link.periodo(d)
        if datas is None or timezone.localtime(datas[1]).date() != ontem:
            continue
        if servico_diario.preenchido(oficio.prestacao) or km_link.motivo_inelegivel(d):
            continue
        enviado = (Comunicacao.objects.filter(
            tipo=LINK_KM, recurso=km_link.recurso(d.pk),
            situacao__in=(Comunicacao.Situacao.ENVIADA, Comunicacao.Situacao.MANUAL))
            .exclude(criada_por=None).order_by("-criada_em").first())
        pessoa = km_link.responsavel(d)
        if enviado is None or pessoa is None or enviado.servidor_id != pessoa.pk:
            continue
        versao = km_link.versao(d)
        automacao.agendar(tipo=LEMBRETE_KM, servidor_id=pessoa.pk,
                          recurso=km_link.recurso(d.pk),
                          chave=f"{LEMBRETE_KM}:{d.pk}:{versao}:d+1",
                          unidade_id=oficio.unidade_id, criada_por=enviado.criada_por,
                          contexto={"diario": d.pk, "servidor": pessoa.pk}, versao=versao,
                          agendada_para=_quando(hoje))
        total += 1
    return total


# ================================================================== responsável trocado
def responsavel_do_diario(d: DiarioBordo, usuario) -> None:
    """Na transação de `diario.trocar_motorista_e_viatura`: outro responsável, os links do
    anterior caem (`responsavel_trocado`) e, se a viagem é de amanhã ou já começou, o novo
    responsável recebe o link. Só a viatura mudou: nada muda. O que estava agendado para o
    anterior fica obsoleto no envio (`preparar` confere o responsável)."""
    from gestao.automacao import links
    from gestao.automacao.models import Comunicacao, LinkAcesso

    S = Comunicacao.Situacao
    pessoa = km_link.responsavel(d)
    ativos = LinkAcesso.objects.filter(escopo=km_link.ESCOPO, recurso=km_link.recurso(d.pk),
                                       revogado_em__isnull=True)
    if pessoa is not None:
        ativos = ativos.exclude(servidor_id=pessoa.pk)
    havia = ativos.exists()
    if havia:
        links.revogar_do_recurso(km_link.recurso(d.pk), LinkAcesso.Motivo.RESPONSAVEL_TROCADO,
                                 km_link.ESCOPO)
    datas = km_link.periodo(d)
    if pessoa is None or datas is None:
        return
    hoje = timezone.localdate()
    if timezone.localtime(datas[0]).date() > hoje + timedelta(days=1):
        return  # a rotina da véspera cuida
    # Link a caminho conta; link já ENVIADO só conta se ainda vale (a troca de motorista revoga
    # o do anterior — quem volta a dirigir precisa de um novo).
    ja_tem = Comunicacao.objects.filter(
        tipo=LINK_KM, recurso=km_link.recurso(d.pk), servidor_id=pessoa.pk,
        situacao__in=(S.AGUARDANDO_APROVACAO, S.AGENDADA, S.RESERVADA)
    ).exists() or (_link_vigente(d, pessoa.pk) is not None and Comunicacao.objects.filter(
        tipo=LINK_KM, recurso=km_link.recurso(d.pk), servidor_id=pessoa.pk,
        situacao__in=(S.ENVIADA, S.MANUAL)).exists())
    if not ja_tem or havia:
        # Chave própria da troca: quem dirigia antes pode voltar e precisa de link novo.
        _agendar_link(d, hoje, autor=usuario,
                      sufixo=f"troca:{int(timezone.now().timestamp())}")


# ================================================================== avisos à equipe
def _recurso_oficio(pk: int) -> str:
    return f"{RECURSO_OFICIO}:{pk}"


def _oficio(contexto: dict) -> Oficio | None:
    pk = contexto.get("oficio")
    return (Oficio.objects.select_related("unidade").filter(pk=pk).first()
            if isinstance(pk, int) else None)


def _na_equipe(oficio: Oficio, servidor_id) -> bool:
    return Viajante.objects.filter(oficio=oficio, servidor_id=servidor_id).exists()


def _equipe_com_contato(oficio: Oficio) -> list[int]:
    """Quem está no ofício e tem WhatsApp verificado (só para essa pessoa há aviso)."""
    return _com_contato(list(Viajante.objects.filter(oficio=oficio).order_by("ordem", "pk")
                             .values_list("servidor_id", flat=True)))


def _ultimo_documento(oficio: Oficio) -> int:
    return (Documento.objects.filter(oficio=oficio, tipo=Documento.Tipo.OFICIO)
            .aggregate(m=Max("versao"))["m"] or 0)


def _periodo_texto(oficio: Oficio) -> tuple[str, str]:
    trechos = list(oficio.trechos.order_by("ordem"))
    if not trechos:
        return "", ""
    saida = timezone.localtime(min(t.saida_em for t in trechos))
    chegada = timezone.localtime(max(t.chegada_em for t in trechos))
    return f"{saida:%d/%m/%Y} às {saida:%H:%M}", f"{chegada:%d/%m/%Y} às {chegada:%H:%M}"


def _versao_cancelamento(oficio: Oficio) -> str:
    return _hash("cancelado", oficio.pk, oficio.cancelado_em.isoformat()
                 if oficio.cancelado_em else "")


def _versao_emissao(oficio: Oficio, documento: int) -> str:
    return _hash("emitido", oficio.pk, documento)


def _preparar_cancelamento(contexto: dict) -> ganchos.Preparo:
    from gestao.cadastros.models import Servidor

    oficio = _oficio(contexto)
    if oficio is None:
        return ganchos.Preparo(False, "O ofício não existe mais.")
    if oficio.situacao != Oficio.Situacao.CANCELADO:
        return ganchos.Preparo(False, "O ofício foi reativado.")
    versao = _versao_cancelamento(oficio)
    if versao != contexto.get("versao"):
        return ganchos.Preparo(False, "O ofício foi reativado e cancelado de novo.")
    servidor_pk = contexto.get("servidor")
    # pk nunca é nulo: sem o id no contexto, o filtro não acharia ninguém.
    servidor = (Servidor.objects.filter(pk=servidor_pk).first()
                if servidor_pk is not None else None)
    if servidor is None or not _na_equipe(oficio, servidor.pk):
        return ganchos.Preparo(False, "A pessoa não está mais na equipe.")
    saida, _ = _periodo_texto(oficio)
    data = saida.split(" ")[0] if saida else "-"
    texto = (f"[TESTE — dados fictícios] Olá, {_primeiro_nome(servidor)}. A viagem do Ofício "
             f"{oficio.numero_formatado} (saída em {data}) foi cancelada. O ofício que você "
             "recebeu não vale mais. Em caso de dúvida, fale com o setor de viagens.")
    return ganchos.Preparo(True, versao=versao, texto=texto, parametros=(
        _primeiro_nome(servidor), oficio.numero_formatado, data))


def _preparar_emissao(contexto: dict, reagendada: bool) -> ganchos.Preparo:
    from gestao.cadastros.models import Servidor

    oficio = _oficio(contexto)
    if oficio is None:
        return ganchos.Preparo(False, "O ofício não existe mais.")
    if oficio.situacao != Oficio.Situacao.EMITIDO:
        return ganchos.Preparo(False, "O ofício não está mais emitido (reaberto ou cancelado).")
    documento = contexto.get("documento")
    if _ultimo_documento(oficio) != documento:
        return ganchos.Preparo(False, "Saiu uma versão mais nova do ofício.")
    servidor_pk = contexto.get("servidor")
    # pk nunca é nulo: sem o id no contexto, o filtro não acharia ninguém.
    servidor = (Servidor.objects.filter(pk=servidor_pk).first()
                if servidor_pk is not None else None)
    if servidor is None or not _na_equipe(oficio, servidor.pk):
        return ganchos.Preparo(False, "A pessoa não está mais na equipe.")
    nome, numero = _primeiro_nome(servidor), oficio.numero_formatado
    if reagendada:
        saida, chegada = _periodo_texto(oficio)
        texto = (f"[TESTE — dados fictícios] Olá, {nome}. As datas da viagem do Ofício "
                 f"{numero} mudaram: saída em {saida} e chegada de volta em {chegada}. O "
                 f"ofício foi reemitido (versão {documento}); a versão anterior não vale mais.")
        parametros: tuple[str, ...] = (nome, numero, saida, chegada, str(documento))
    else:
        texto = (f"[TESTE — dados fictícios] Olá, {nome}. O Ofício {numero} foi corrigido "
                 f"e reemitido (versão {documento}). A versão anterior não vale mais; use a "
                 "nova. As datas da viagem não mudaram.")
        parametros = (nome, numero, str(documento))
    return ganchos.Preparo(True, versao=_versao_emissao(oficio, documento), texto=texto,
                           parametros=parametros)


def _preparar_retirada(contexto: dict) -> ganchos.Preparo:
    """Quem saiu da equipe na reemissão: o ofício que recebeu não vale mais para ela."""
    from gestao.cadastros.models import Servidor

    oficio = _oficio(contexto)
    if oficio is None:
        return ganchos.Preparo(False, "O ofício não existe mais.")
    if oficio.situacao != Oficio.Situacao.EMITIDO:
        return ganchos.Preparo(False, "O ofício não está mais emitido (reaberto ou cancelado).")
    documento = contexto.get("documento")
    if _ultimo_documento(oficio) != documento:
        return ganchos.Preparo(False, "Saiu uma versão mais nova do ofício.")
    servidor_pk = contexto.get("servidor")
    # pk nunca é nulo: sem o id no contexto, o filtro não acharia ninguém.
    servidor = (Servidor.objects.filter(pk=servidor_pk).first()
                if servidor_pk is not None else None)
    if servidor is None:
        return ganchos.Preparo(False, "O servidor não existe mais.")
    if _na_equipe(oficio, servidor.pk):
        return ganchos.Preparo(False, "A pessoa voltou para a equipe.")
    nome, numero = _primeiro_nome(servidor), oficio.numero_formatado
    texto = (f"[TESTE — dados fictícios] Olá, {nome}. Você não faz mais parte da equipe desta "
             f"viagem (teste): o Ofício {numero} foi reemitido (versão {documento}) sem o seu "
             "nome. O ofício que você recebeu não vale mais para você. Em caso de dúvida, fale "
             "com o setor de viagens.")
    return ganchos.Preparo(True, versao=_versao_emissao(oficio, documento), texto=texto,
                           parametros=(nome, numero, str(documento)))


def _preparar_reagendamento(contexto: dict) -> ganchos.Preparo:
    return _preparar_emissao(contexto, reagendada=True)


def _preparar_substituicao(contexto: dict) -> ganchos.Preparo:
    return _preparar_emissao(contexto, reagendada=False)


def _assunto_oficio(recurso: str) -> ganchos.Assunto | None:
    _, _, pk = recurso.partition(":")
    oficio = Oficio.objects.filter(pk=int(pk)).first() if pk.isdigit() else None
    if oficio is None:
        return None
    return ganchos.Assunto(f"Ofício {oficio.numero_formatado}",
                           reverse("viagens:resumo", args=[oficio.pk]))


def _com_contato(ids: list[int]) -> list[int]:
    from gestao.automacao.models import ContatoVerificado

    com_contato = set(ContatoVerificado.objects.filter(
        servidor_id__in=ids, canal=CANAL, revogado_em__isnull=True,
        verificado_em__isnull=False).values_list("servidor_id", flat=True))
    return [pk for pk in ids if pk in com_contato]


def _avisar_equipe(oficio: Oficio, tipo: str, marca: str, contexto: dict, versao: str,
                   autor, servidores: list[int] | None = None) -> int:
    total = 0
    for servidor_id in (_equipe_com_contato(oficio) if servidores is None else servidores):
        automacao.agendar(tipo=tipo, servidor_id=servidor_id,
                          recurso=_recurso_oficio(oficio.pk),
                          chave=f"{tipo}:{oficio.pk}:{marca}:{servidor_id}",
                          unidade_id=oficio.unidade_id, criada_por=autor,
                          contexto={**contexto, "servidor": servidor_id}, versao=versao)
        total += 1
    return total


def oficio_cancelado(oficio: Oficio, usuario, anterior: str) -> None:
    """Na transação de `services.cancelar`: os links de km do ofício caem, o que ainda não
    saiu sobre ele fica obsoleto e, se ele estava emitido, a equipe é avisada (sem o
    motivo — 10-2, D-13)."""
    from gestao.automacao import links
    from gestao.automacao.models import LinkAcesso

    d = DiarioBordo.objects.filter(prestacao__oficio=oficio).first()
    if d is not None:
        links.revogar_do_recurso(km_link.recurso(d.pk), LinkAcesso.Motivo.OFICIO_CANCELADO,
                                 km_link.ESCOPO)
        automacao.encerrar_relacionadas(km_link.recurso(d.pk), (LINK_KM, LEMBRETE_KM),
                                        "O ofício foi cancelado.")
    automacao.encerrar_relacionadas(_recurso_oficio(oficio.pk),
                                    (REAGENDAMENTO, SUBSTITUICAO, RETIRADA),
                                    "O ofício foi cancelado.")
    if anterior != Oficio.Situacao.EMITIDO or not _registrado(CANCELAMENTO):
        return
    versao = _versao_cancelamento(oficio)
    _avisar_equipe(oficio, CANCELAMENTO, versao, {"oficio": oficio.pk, "versao": versao},
                   versao, usuario)


def _periodo_do_documento(dados: dict) -> tuple:
    trechos = (dados or {}).get("trechos") or []
    if not trechos:
        return ()
    return (trechos[0].get("saida"), trechos[-1].get("chegada"))


def _link_na_primeira_emissao(oficio: Oficio, usuario) -> None:
    """Ofício de viatura emitido pela 1ª vez DEPOIS da rotina da véspera, saindo hoje ou
    amanhã: a rotina não o veria mais (só procura saídas de amanhã), então o link de km é
    agendado aqui. A chave por diário e versão impede duplicar com a rotina."""
    if oficio.tipo_transporte != Oficio.TipoTransporte.VIATURA:
        return
    prestacao = getattr(oficio, "prestacao", None)
    saida = oficio.trechos.aggregate(m=Min("saida_em"))["m"]
    if prestacao is None or saida is None:
        return
    hoje = timezone.localdate()
    if hoje <= timezone.localtime(saida).date() <= hoje + timedelta(days=1):
        _agendar_link(servico_diario.obter(prestacao), hoje, autor=usuario)


def oficio_emitido(oficio: Oficio, usuario, documento: Documento) -> None:
    """Na transação de `services.emitir`: reemissão (versão 2 em diante) avisa a equipe —
    "datas mudaram" se a saída ou a chegada mudou, senão "use a versão nova". O aviso de
    uma versão anterior que ainda não saiu fica obsoleto."""
    if documento.versao <= 1:
        _link_na_primeira_emissao(oficio, usuario)
        return
    automacao.encerrar_relacionadas(_recurso_oficio(oficio.pk),
                                    (REAGENDAMENTO, SUBSTITUICAO, RETIRADA),
                                    "Saiu uma versão mais nova do ofício.")
    anterior = (Documento.objects.filter(oficio=oficio, tipo=documento.tipo,
                                         versao__lt=documento.versao)
                .order_by("-versao").first())
    if anterior is None:
        return
    contexto = {"oficio": oficio.pk, "documento": documento.versao, "de": anterior.versao}
    versao = _versao_emissao(oficio, documento.versao)
    _quem_saiu(oficio, usuario, anterior, contexto, versao)
    mudou = _periodo_do_documento(anterior.dados) != _periodo_do_documento(documento.dados)
    tipo = REAGENDAMENTO if mudou else SUBSTITUICAO
    if not _registrado(tipo):
        return
    _avisar_equipe(oficio, tipo, f"v{documento.versao}", contexto, versao, usuario)


def _quem_saiu(oficio: Oficio, usuario, anterior: Documento, contexto: dict,
               versao: str) -> None:
    """Quem estava na versão anterior e não está nesta: os links de km de quem não é mais o
    responsável caem (`responsavel_trocado`, a mesma regra da troca de motorista) e quem saiu,
    com WhatsApp verificado, é avisado de que não faz mais parte da equipe."""
    from gestao.automacao.models import LinkAcesso

    antes = [v.get("id") for v in (anterior.dados or {}).get("viajantes") or []
             if isinstance(v.get("id"), int)]
    agora = set(Viajante.objects.filter(oficio=oficio).values_list("servidor_id", flat=True))
    sairam = [pk for pk in dict.fromkeys(antes) if pk not in agora]
    d = (DiarioBordo.objects.filter(prestacao__oficio=oficio)
         .select_related("prestacao__oficio", "motorista_servidor").first())
    if d is not None:
        pessoa = km_link.responsavel(d)
        de_outros = LinkAcesso.objects.filter(
            escopo=km_link.ESCOPO, recurso=km_link.recurso(d.pk), revogado_em__isnull=True)
        if pessoa is not None:
            de_outros = de_outros.exclude(servidor_id=pessoa.pk)
        if de_outros.exists():
            responsavel_do_diario(d, usuario)
    if sairam and _registrado(RETIRADA):
        _avisar_equipe(oficio, RETIRADA, f"v{contexto['documento']}", contexto, versao,
                       usuario, servidores=_com_contato(sairam))


# ================================================================== registro
def registrar() -> None:
    from gestao.automacao import links

    from . import views_km_link

    ganchos.registrar_tipo(ganchos.TipoComunicacao(
        chave=LINK_KM, rotulo="Link de km na véspera", fluxo=FLUXO_KM,
        preparar=_preparar_link, validade=timedelta(days=2), assunto=_assunto_diario))
    ganchos.registrar_tipo(ganchos.TipoComunicacao(
        chave=LEMBRETE_KM, rotulo="Lembrete de km do diário", fluxo=FLUXO_LEMBRETES_KM,
        preparar=_preparar_lembrete, validade=timedelta(hours=20), assunto=_assunto_diario))
    ganchos.registrar_tipo(ganchos.TipoComunicacao(
        chave=CANCELAMENTO, rotulo="Aviso de viagem cancelada", fluxo=FLUXO_AVISOS,
        preparar=_preparar_cancelamento, validade=timedelta(days=3), assunto=_assunto_oficio))
    ganchos.registrar_tipo(ganchos.TipoComunicacao(
        chave=REAGENDAMENTO, rotulo="Aviso de viagem reagendada", fluxo=FLUXO_AVISOS,
        preparar=_preparar_reagendamento, validade=timedelta(days=3),
        assunto=_assunto_oficio))
    ganchos.registrar_tipo(ganchos.TipoComunicacao(
        chave=SUBSTITUICAO, rotulo="Aviso de ofício reemitido", fluxo=FLUXO_AVISOS,
        preparar=_preparar_substituicao, validade=timedelta(days=3),
        assunto=_assunto_oficio))
    ganchos.registrar_tipo(ganchos.TipoComunicacao(
        chave=RETIRADA, rotulo="Aviso de saída da equipe", fluxo=FLUXO_AVISOS,
        preparar=_preparar_retirada, validade=timedelta(days=3), assunto=_assunto_oficio))
    links.registrar_pagina(links.PaginaDeLink(
        escopo=km_link.ESCOPO, rotulo="Lançar a quilometragem", view=views_km_link.pagina))
