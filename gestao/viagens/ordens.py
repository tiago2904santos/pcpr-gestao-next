"""Ordens de Serviço: numeração, escrita, cópia do ofício e documento.

Paridade com `viagens_ordens` da referência:
- numeração anual própria ("OS 001/2026"): a menor lacuna liberada por exclusão, senão o
  maior número + 1 (`dominio.numeracao.proximo_numero`, a mesma regra do ofício);
- ao ligar ofícios, a OS **copia** deles o que estiver em branco — destinos, período, equipe
  e motivo (na referência, a tela copiava ao vincular);
- o texto do documento depende do tipo de necessidade (`dominio.ordem_servico`); nos tipos
  com função, cada um da equipe recebe a sua (condução, técnico, apoio…);
- quem assina: o assinante desta OS; senão o substituto do período ou a chefia da unidade;
- a data do documento nasce na primeira geração e vale para todas as vias.

Toda gravação passa por aqui; a auditoria é do banco (trigger).
"""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.db.models import Prefetch, prefetch_related_objects
from django.utils import timezone

from gestao.cadastros.models import ConfiguracaoInstitucional, Municipio, Servidor
from gestao.cadastros.services import quem_assina

from . import policies
from .dominio import ordem_servico as dominio
from .dominio.numeracao import proximo_numero
from .models import (
    LacunaOrdemServico,
    NumeracaoOrdemServico,
    Oficio,
    OrdemServico,
    OrdemServicoDestino,
    Trecho,
    Viajante,
)


class OrdemInvalida(Exception):
    """Erro com mensagem pronta para o usuário."""


MAX_SERVIDORES = 60
MAX_DESTINOS = 30
MAX_OFICIOS = 20

PREFETCH_ORDENS = (
    Prefetch("destinos", queryset=OrdemServicoDestino.objects.select_related("municipio")),
    Prefetch("servidores", queryset=Servidor.objects.select_related("cargo", "unidade")
             .order_by("nome")),
    Prefetch("oficios", queryset=Oficio.objects.order_by("-ano", "-numero")),
)


def com_dados(qs):
    return qs.select_related("unidade", "assinante__cargo").prefetch_related(*PREFETCH_ORDENS)


def carregar(ordem: OrdemServico) -> OrdemServico:
    if not hasattr(ordem, "_prefetched_objects_cache"):
        prefetch_related_objects([ordem], *PREFETCH_ORDENS)
    return ordem


# ---------------------------------------------------------------- numeração
def reservar_numero(ano: int) -> int:
    """Próximo número do ano; trava a linha do ano; a lacuna usada deixa de existir."""
    linha, _ = NumeracaoOrdemServico.objects.get_or_create(ano=ano)
    NumeracaoOrdemServico.objects.select_for_update().get(pk=linha.pk)
    ocupados = OrdemServico.objects.filter(ano=ano).values_list("numero", flat=True)
    lacunas = LacunaOrdemServico.objects.filter(ano=ano).values_list("numero", flat=True)
    numero = proximo_numero(ocupados, 1, lacunas)
    LacunaOrdemServico.objects.filter(ano=ano, numero=numero).delete()
    return numero


def proximo_numero_do_ano(ano: int) -> int:
    """O número que a próxima OS do ano receberia (para mostrar; não reserva)."""
    ocupados = OrdemServico.objects.filter(ano=ano).values_list("numero", flat=True)
    lacunas = LacunaOrdemServico.objects.filter(ano=ano).values_list("numero", flat=True)
    return proximo_numero(ocupados, 1, lacunas)


# ---------------------------------------------------------------- cópia do ofício
def dados_dos_oficios(oficios: list[Oficio]) -> dict:
    """Destinos (na ordem, sem repetir), período (primeira saída a última chegada), equipe e
    o motivo do primeiro ofício — o que a OS em branco copia."""
    prefetch_related_objects(
        oficios, Prefetch("trechos", queryset=Trecho.objects.select_related("destino")
                          .order_by("ordem")),
        Prefetch("viajantes", queryset=Viajante.objects.select_related("servidor")))
    destinos: list[Municipio] = []
    servidores: list[Servidor] = []
    inicio = fim = None
    motivo = ""
    for o in oficios:
        trechos = list(o.trechos.all())
        for t in trechos:
            if t.destino_id != o.sede_id and t.destino not in destinos:
                destinos.append(t.destino)
        if trechos:
            saida = timezone.localdate(trechos[0].saida_em)
            chegada = timezone.localdate(trechos[-1].chegada_em)
            inicio = min(inicio, saida) if inicio else saida
            fim = max(fim, chegada) if fim else chegada
        for v in o.viajantes.all():
            if v.servidor not in servidores:
                servidores.append(v.servidor)
        motivo = motivo or (o.motivo or "").strip()
    return {"destinos": destinos, "inicio": inicio, "fim": fim, "servidores": servidores,
            "motivo": motivo}


# ---------------------------------------------------------------- escrita
def _funcoes_validas(tipo: str, funcoes: dict, servidores: list[Servidor]) -> dict[str, str]:
    permitidas = dominio.FUNCOES_DO_TIPO.get(tipo)
    if not permitidas:
        return {}
    ids = {str(s.pk) for s in servidores}
    saida = {}
    for sid, funcao in (funcoes or {}).items():
        if str(sid) not in ids or not funcao:
            continue
        if funcao not in permitidas:
            raise OrdemInvalida("Escolha uma função válida para cada servidor da equipe.")
        saida[str(sid)] = funcao
    return saida


@transaction.atomic
def salvar(usuario, *, pk: int | None = None, oficios=(), tipo: str = dominio.PADRAO,
           destinos=(), data_inicio: date | None = None, data_fim: date | None = None,
           servidores=(), motivo: str = "", funcoes: dict | None = None,
           assinante: Servidor | None = None,
           data_documento: date | None = None,
           versao: str = "") -> tuple[OrdemServico, list[str]]:
    """Cria (numera) ou altera. Devolve a OS e o que foi copiado dos ofícios.

    `versao` (o `atualizado_em` que a tela abriu) recusa gravar por cima de quem salvou
    depois. Os campos vazios recebem dos ofícios na criação e quando um ofício é ligado
    agora — não a cada gravação (com o autosave, apagar o motivo para reescrevê-lo não pode
    trazer de volta o do ofício)."""
    oficios, destinos, servidores = list(oficios), list(dict.fromkeys(destinos)), list(servidores)
    if pk:
        ordem = OrdemServico.objects.select_for_update().get(pk=pk)
        policies.exigir(policies.pode_editar_ordem(usuario, ordem),
                        "Esta Ordem de Serviço não pode ser alterada.")
        if versao and versao != versao_de(ordem):
            raise OrdemInvalida("Outra pessoa alterou esta OS depois que você abriu a tela. "
                         "Recarregue a página para ver a versão atual (o que você "
                         "digitou continua na tela até lá).")
    else:
        policies.exigir(policies.pode_criar_ordem(usuario),
                        "Você não pode criar Ordens de Serviço.")
        ano = timezone.localdate().year
        ordem = OrdemServico(unidade=policies.unidade_do_usuario(usuario), ano=ano,
                             numero=reservar_numero(ano), criado_por=usuario)
    if tipo not in dict(OrdemServico.TIPOS):
        raise OrdemInvalida("Tipo de necessidade desconhecido.")
    if len(oficios) > MAX_OFICIOS or len(servidores) > MAX_SERVIDORES \
            or len(destinos) > MAX_DESTINOS:
        raise OrdemInvalida(f"Limites: {MAX_OFICIOS} ofícios, {MAX_SERVIDORES} servidores e "
                            f"{MAX_DESTINOS} destinos por OS.")
    ja_ligados = set(ordem.oficios.values_list("pk", flat=True)) if pk else set()
    for o in oficios:
        policies.exigir(policies.pode_ver(usuario, o), "Ofício não encontrado.")
        if o.unidade_id != ordem.unidade_id:
            raise OrdemInvalida(f"O Ofício {o.numero_formatado} é de outra unidade.")
        if o.situacao == Oficio.Situacao.CANCELADO and o.pk not in ja_ligados:
            raise OrdemInvalida(f"O Ofício {o.numero_formatado} está cancelado.")
    if assinante is not None and assinante.unidade_id != ordem.unidade_id \
            and assinante.pk != ordem.assinante_id:
        raise OrdemInvalida("Quem assina a OS precisa ser da unidade da OS.")
    if data_inicio and data_fim and data_fim < data_inicio:
        raise OrdemInvalida("A data final não pode ser anterior à inicial.")
    if data_fim and not data_inicio:
        raise OrdemInvalida("Informe a data inicial.")
    copiados: list[str] = []
    if oficios and (not pk or any(o.pk not in ja_ligados for o in oficios)):
        base = dados_dos_oficios(oficios)
        if not destinos and base["destinos"]:
            destinos = base["destinos"]
            copiados.append("destinos")
        if not data_inicio and base["inicio"]:
            data_inicio, data_fim = base["inicio"], base["fim"]
            copiados.append("período")
        if not servidores and base["servidores"]:
            servidores = base["servidores"]
            copiados.append("equipe")
        if not motivo.strip() and base["motivo"]:
            motivo = base["motivo"]
            copiados.append("motivo")
        if len(destinos) > MAX_DESTINOS or len(servidores) > MAX_SERVIDORES:
            raise OrdemInvalida("Os ofícios somam destinos ou servidores demais para uma OS: "
                                f"no máximo {MAX_DESTINOS} destinos e {MAX_SERVIDORES} "
                                "servidores. Escolha-os à mão.")
    ordem.tipo = tipo
    ordem.data_inicio, ordem.data_fim = data_inicio, (data_fim or data_inicio)
    ordem.motivo = (motivo or "").strip()
    ordem.assinante = assinante
    ordem.data_documento = data_documento  # em branco: a da próxima geração
    if funcoes is None:  # a tela não mostrou as funções: valem as gravadas
        funcoes = ordem.funcoes if pk else {}
    ordem.funcoes = _funcoes_validas(tipo, funcoes, servidores)
    ordem.save()
    ordem.oficios.set(oficios)
    ordem.servidores.set(servidores)
    atuais = [d.municipio_id for d in ordem.destinos.order_by("posicao", "id")]
    if atuais != [m.pk for m in destinos]:
        ordem.destinos.all().delete()
        OrdemServicoDestino.objects.bulk_create(
            [OrdemServicoDestino(ordem=ordem, municipio=m, posicao=i)
             for i, m in enumerate(destinos)])
    return ordem, copiados


def versao_de(ordem: OrdemServico) -> str:
    """A versão que a tela guarda para não gravar por cima de outra pessoa."""
    return ordem.atualizado_em.isoformat() if ordem.atualizado_em else ""


def assinatura_prevista(ordem: OrdemServico | None, unidade) -> str:
    """Quem assina se o campo ficar em branco (para a tela dizer antes de gerar)."""
    config = ConfiguracaoInstitucional.objects.filter(unidade=unidade).first()
    if config is None:
        return ""
    data = (ordem.data_documento if ordem and ordem.data_documento else timezone.localdate())
    nome, cargo, origem = quem_assina(config, "ordem_servico", data)
    return f"{nome}{', ' + cargo if cargo else ''} — {origem}" if nome else ""


@transaction.atomic
def cancelar(usuario, pk: int, motivo: str) -> OrdemServico:
    ordem = OrdemServico.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_cancelar_ordem(usuario, ordem),
                    "Você não pode cancelar esta Ordem de Serviço.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise OrdemInvalida("Informe o motivo do cancelamento.")
    if len(motivo) > 1000:
        raise OrdemInvalida("O motivo passa de 1000 caracteres: resuma.")
    if ordem.cancelada:
        raise OrdemInvalida("A Ordem de Serviço já está cancelada.")
    ordem.situacao, ordem.motivo_cancelamento = OrdemServico.Situacao.CANCELADA, motivo
    ordem.cancelado_em = timezone.now()
    ordem.save(update_fields=["situacao", "motivo_cancelamento", "cancelado_em",
                              "atualizado_em"])
    return ordem


@transaction.atomic
def reativar(usuario, pk: int) -> OrdemServico:
    ordem = OrdemServico.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_cancelar_ordem(usuario, ordem),
                    "Você não pode reativar esta Ordem de Serviço.")
    if not ordem.cancelada:
        raise OrdemInvalida("A Ordem de Serviço não está cancelada.")
    ordem.situacao, ordem.motivo_cancelamento = OrdemServico.Situacao.ATIVA, ""
    ordem.cancelado_em = None
    ordem.save(update_fields=["situacao", "motivo_cancelamento", "cancelado_em",
                              "atualizado_em"])
    return ordem


@transaction.atomic
def excluir(usuario, pk: int) -> str:
    """Exclui e libera o número para a próxima OS do ano (referência)."""
    ordem = OrdemServico.objects.select_for_update().get(pk=pk)
    if ordem.documento_gerado_em is not None:  # antes da permissão: a mensagem diz o porquê
        raise OrdemInvalida("O documento desta OS já foi gerado: o número já saiu num "
                            "documento oficial. Cancele em vez de excluir.")
    policies.exigir(policies.pode_excluir_ordem(usuario, ordem),
                    "Você não pode excluir esta Ordem de Serviço.")
    nome, ano, numero = str(ordem), ordem.ano, ordem.numero
    ordem.delete()
    LacunaOrdemServico.objects.get_or_create(ano=ano, numero=numero)
    return nome


# ---------------------------------------------------------------- leitura e documento
def faltando(ordem: OrdemServico) -> list[str]:
    """O que falta para a OS sair completa (régua da referência: período, destino, equipe e
    motivo). Não bloqueia: sinaliza."""
    carregar(ordem)
    falta = []
    if not ordem.data_inicio:
        falta.append("período")
    if not list(ordem.destinos.all()):
        falta.append("destino")
    if not list(ordem.servidores.all()):
        falta.append("equipe")
    if not ordem.motivo.strip():
        falta.append("motivo")
    if dominio.faltam_funcoes(dados_do_dominio(ordem)):
        falta.append("função da equipe")
    return falta


def periodo_curto(ordem: OrdemServico) -> str:
    i, f = ordem.data_inicio, ordem.data_fim
    if not i:
        return ""
    if not f or f == i:
        return f"{i:%d/%m/%Y}"
    return f"{i:%d/%m} a {f:%d/%m/%Y}" if i.year == f.year else f"{i:%d/%m/%Y} a {f:%d/%m/%Y}"


def dados_do_dominio(ordem: OrdemServico) -> dominio.DadosOS:
    carregar(ordem)
    return dominio.DadosOS(
        tipo=ordem.tipo,
        destinos=[f"{d.municipio.nome}/{d.municipio.uf}" for d in ordem.destinos.all()],
        inicio=ordem.data_inicio, fim=ordem.data_fim, motivo=ordem.motivo,
        equipe=[dominio.Pessoa(s.pk, s.nome, getattr(s.cargo, "nome", ""))
                for s in ordem.servidores.all()],
        funcoes={int(k): v for k, v in (ordem.funcoes or {}).items() if str(k).isdecimal()})


@transaction.atomic
def fixar_data_do_documento(ordem: OrdemServico) -> date:
    """A data do documento nasce na primeira geração e não muda mais sozinha."""
    agora = timezone.now()
    if ordem.data_documento is None:
        ordem.data_documento = timezone.localdate()
        OrdemServico.objects.filter(pk=ordem.pk, data_documento__isnull=True).update(
            data_documento=ordem.data_documento)
    if ordem.documento_gerado_em is None:
        ordem.documento_gerado_em = agora
        OrdemServico.objects.filter(pk=ordem.pk, documento_gerado_em__isnull=True).update(
            documento_gerado_em=agora)
    return ordem.data_documento


def dados_do_documento(ordem: OrdemServico, *, fixar: bool = True) -> dict:
    """Dados do documento. `fixar=False` (a prévia na tela) não fixa a data do documento
    nem conta como geração: mostra a data que sairia hoje."""
    config = ConfiguracaoInstitucional.objects.filter(unidade=ordem.unidade).select_related(
        "sede").first()
    if config is None:
        raise OrdemInvalida("A unidade ainda não tem configuração (cabeçalho, quem assina): "
                            "peça ao gestor para cadastrá-la.")
    if fixar:
        data_doc = fixar_data_do_documento(ordem)
    else:
        data_doc = ordem.data_documento or timezone.localdate()
    if ordem.assinante is not None:
        nome, cargo = ordem.assinante.nome, getattr(ordem.assinante.cargo, "nome", "")
    else:
        nome, cargo, _ = quem_assina(config, "ordem_servico", data_doc)
    textos = dominio.textos_da_os(dados_do_dominio(ordem))
    return {
        "titulo": f"Ordem de Serviço {ordem.numero_formatado}",
        "numero": ordem.numero_formatado,
        "sigla": ordem.unidade.sigla or ordem.unidade.nome,
        "unidade_nome": config.nome_extenso,
        "cabecalho_unidade": config.nome_extenso.upper(),
        "rodape": config.rodape,
        "assina": {"nome": nome, "cargo": cargo},
        "delegado_geral": config.delegado_geral_nome,
        "sede": config.sede.nome if config.sede_id else "",
        "data_extenso": dominio.data_por_extenso(data_doc),
        # Prévia (tela, PDF com ?previa=1): sai com a marca MINUTA — não é a OS emitida e
        # não pode circular como se fosse (a trava de exclusão só conta a geração real).
        "previa": not fixar,
        **textos,
    }


def html_do_documento(dados: dict, *, folha: bool = False, nonce: str = "") -> str:
    """HTML do documento; `folha=True` é a versão de tela (dentro do visualizador)."""
    from django.template.loader import render_to_string

    from .documentos.pdf import _recursos
    return render_to_string("viagens/documentos/ordem_servico.html",
                            {"d": dados, "folha": folha, "nonce": nonce, **_recursos(folha)})


def pdf_do_documento(dados: dict) -> bytes:
    import hashlib

    from weasyprint import HTML

    from .documentos.pdf import ASSETS, buscar_recurso
    html = html_do_documento(dados)
    return HTML(string=html, base_url=str(ASSETS), url_fetcher=buscar_recurso()).write_pdf(
        pdf_variant="pdf/a-2a", pdf_identifier=hashlib.sha256(html.encode()).digest()[:16],
        pdf_tags=True, custom_metadata=True, presentational_hints=True)


def docx_do_documento(dados: dict) -> bytes:
    from .documentos.docx import docx_do_html
    from .documentos.pdf import ASSETS
    return docx_do_html(html_do_documento(dados), base_imagens=ASSETS)
