"""Apresentação do domínio Viagens em templates (situação, prazo, faixas)."""

from __future__ import annotations

from datetime import date, datetime

from django import template
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.utils.html import format_html

from gestao.plataforma.templatetags.ui import icone

from ..dominio import tempo as dominio_tempo
from ..dominio.assunto import TipoOficio, tipo_do_oficio
from ..dominio.prazos import avaliar_prazo
from ..dominio.selos import TipoAlerta, alerta_da_linha
from ..dominio.tempo import PRAZO_PADRAO, Momento, SeloTempo

register = template.Library()

TOM_SITUACAO = {"rascunho": "neutro", "emitido": "sucesso", "cancelado": "perigo"}
ICONE_SITUACAO = {"rascunho": "file-pen-line", "emitido": "file-check-2", "cancelado": "ban"}


@register.filter
def itens(texto: str) -> list[str]:
    """Texto de uma linha por item ("• Meta…") em itens, sem o marcador — para mostrar
    como lista na tela (as metas e os recursos do plano)."""
    return [linha.strip().removeprefix("•").strip()
            for linha in (texto or "").splitlines() if linha.strip()]


@register.filter
def tom_situacao(situacao: str) -> str:
    return TOM_SITUACAO.get(situacao, "neutro")


@register.filter
def icone_situacao(situacao: str) -> str:
    return ICONE_SITUACAO.get(situacao, "file-text")


@register.filter
def larguras_de_cartoes(total: int) -> list[int]:
    """Quantas colunas (de seis) cada cartão ocupa para as linhas ficarem sempre cheias:
    até três por linha e nunca uma linha com um cartão sozinho quando dá para repartir em
    duas — 4 cartões viram 2+2, e não 3+1."""
    restante, larguras = int(total or 0), []
    while restante > 0:
        por_linha = 2 if restante == 4 else min(3, restante)
        larguras += [6 // por_linha] * por_linha
        restante -= por_linha
    return larguras


CUSTEIO_CURTO = {"unidade": "Unidade", "outra_instituicao": "Outra instituição",
                 "onus_limitado": "Ônus limitado"}


@register.filter
def custeio_curto(custeio: str) -> str:
    """Só o nome do custeio. A explicação entre parênteses cabe na folha do ofício; num
    resumo, ela ocuparia três linhas para dizer "Unidade"."""
    return CUSTEIO_CURTO.get(custeio, custeio)


@register.filter
def periodo(trechos) -> str:
    trechos = list(trechos)
    if not trechos:
        return ""
    return formatar_periodo(trechos[0].saida_em, trechos[-1].chegada_em)


def formatar_periodo(saida: datetime | None, chegada: datetime | None) -> str:
    """"08/10 a 12/10/2026" (ou só a data, quando ida e volta são no mesmo dia)."""
    if not saida or not chegada:
        return ""
    ini = timezone.localtime(saida)
    fim = timezone.localtime(chegada)
    if ini.date() == fim.date():
        return f"{ini:%d/%m/%Y}"
    if ini.year == fim.year:
        return f"{ini:%d/%m} a {fim:%d/%m/%Y}"
    return f"{ini:%d/%m/%Y} a {fim:%d/%m/%Y}"


@register.filter
def lista_destinos(oficio) -> list[str]:
    """Destinos do ofício (ou roteiro), na ordem, sem repetir e sem a volta à sede."""
    vistos: list[str] = []
    for t in oficio.trechos.all():
        if t.destino_id != oficio.sede_id:
            rotulo = f"{t.destino.nome}/{t.destino.uf}"
            if rotulo not in vistos:
                vistos.append(rotulo)
    return vistos


@register.filter
def destinos(oficio) -> str:
    return ", ".join(lista_destinos(oficio))


@register.filter
def resumir(itens, maximo: int = 3) -> dict:
    """Até `maximo` itens à vista + quantos sobram (o "+N" da linha) + a lista inteira para
    o `title`. Aceita textos ou objetos (Municipio vira "Cidade/UF" pelo __str__)."""
    rotulos = [str(i) for i in (itens or [])]
    return {"visiveis": ", ".join(rotulos[:maximo]), "mais": max(0, len(rotulos) - maximo),
            "completo": ", ".join(rotulos)}


ICONE_MEIO = {"aereo": "plane", "onibus_linha": "bus", "onibus_fretado": "bus"}


@register.filter
def icone_transporte(oficio) -> str:
    """Ícone pelo modal: avião, ônibus ou carro (viatura e os demais rodoviários)."""
    if oficio.viatura_id:
        return "car"
    return ICONE_MEIO.get(oficio.transporte_meio, "car" if oficio.transporte_meio else "bus")


@register.filter
def motorista_de_fora(oficio) -> str:
    """Nome do motorista que não é da equipe deste ofício (servidor de outro ofício ou
    pessoa não cadastrada) — a lista precisa mostrá-lo, senão parece que ninguém dirige."""
    if oficio.motorista_externo == "servidor":
        servidor = oficio.motorista_externo_servidor
        return servidor.nome if servidor else ""
    if oficio.motorista_externo == "manual":
        return oficio.motorista_externo_nome.strip()
    return ""


@register.filter
def data_iso(valor: str) -> str:
    """'2026-10-08T09:00:00-03:00' → '08/10/2026 09:00' (memória de cálculo)."""
    try:
        return datetime.fromisoformat(valor).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return valor or ""


@register.filter
def data_curta_iso(valor: str) -> str:
    try:
        return datetime.fromisoformat(valor).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return valor or ""


@register.filter
def secao_ok(prontidao, secao: str) -> bool:
    """Seção sem pendências bloqueantes (para o índice do formulário)."""
    if not prontidao:
        return False
    return not any(p.bloqueia and p.secao == secao for p in prontidao.pendencias)


@register.filter
def pendencias_da_secao(prontidao, secao: str):
    return prontidao.da_secao(secao) if prontidao else []


@register.filter
def so_avisos(pendencias):
    """Só as pendências que não impedem a emissão (agrupadas numa nota só na tela)."""
    return [p for p in pendencias if not p.bloqueia]


# ---------------------------------------------------------------- selos das listas
# A regra é do domínio (dominio/tempo.py, dominio/selos.py, dominio/assunto.py); aqui só a
# forma do selo. Nenhuma tela monta selo de tempo, de justificativa ou de tipo à mão.
def _data_local(valor: date | datetime | None) -> date | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return timezone.localdate(valor)
    return valor


def _html_selo_tempo(selo: SeloTempo | None) -> str:
    if selo is None:
        return ""
    if selo.momento is Momento.EM_ANDAMENTO:  # o ponto pulsa: está acontecendo agora
        return format_html('<span class="selo selo--info selo--processo">{}</span>', selo.texto)
    return format_html('<span class="selo selo--{} selo--sem-ponto">{}{}</span>',
                       "aviso" if selo.aviso else "info",
                       icone("clock", classe="icone--sm"), selo.texto)


@register.simple_tag
def selo_tempo(inicio: date | datetime | None, fim: date | datetime | None = None,
               prazo: int = PRAZO_PADRAO, hoje: date | None = None) -> str:
    """`{% selo_tempo inicio fim %}`: "faltam 12 dias", "amanhã", "começa hoje",
    "em andamento · até 15/10", "volta hoje" — ou nada (passado, sem data)."""
    return _html_selo_tempo(dominio_tempo.selo_tempo(
        _data_local(inicio), _data_local(fim), hoje or timezone.localdate(), prazo))


def _prazo_da_unidade(oficio) -> int | None:
    try:
        return oficio.unidade.configuracao.prazo_justificativa_dias
    except ObjectDoesNotExist:  # unidade sem configuração: as pendências já avisam
        return None


def _periodo_do_oficio(oficio) -> tuple[date | None, date | None]:
    """Datas locais da 1ª saída e da última chegada. Na lista os trechos já vêm juntos
    (com_dados_de_lista); no resumo, do cache de trechos_de — nenhuma consulta por linha."""
    from ..queries import trechos_de

    trechos = trechos_de(oficio)
    if not trechos:
        return None, None
    return _data_local(trechos[0].saida_em), _data_local(trechos[-1].chegada_em)


def justificativa_pendente(oficio, inicio: date | None, prazo: int | None) -> bool:
    if (prazo is None or inicio is None or not oficio.editavel
            or oficio.situacao == "cancelado"):
        return False
    return (avaliar_prazo(oficio.data_oficio, inicio, prazo).justificativa_obrigatoria
            and not oficio.justificativa.strip())


@register.simple_tag
def alerta_oficio(oficio, hoje: date | None = None) -> str:
    """O único alerta do título do ofício (D4): Justificativa pendente > prazo > tempo."""
    if oficio.situacao == "cancelado":
        return ""
    inicio, fim = _periodo_do_oficio(oficio)
    prazo = _prazo_da_unidade(oficio)
    tempo = dominio_tempo.selo_tempo(inicio, fim, hoje or timezone.localdate(),
                                     PRAZO_PADRAO if prazo is None else prazo)
    alerta = alerta_da_linha(justificativa_pendente=justificativa_pendente(oficio, inicio, prazo),
                             tempo=tempo)
    if alerta is None:
        return ""
    if alerta.tipo is TipoAlerta.JUSTIFICATIVA:
        return selo_justificativa_pendente()
    return _html_selo_tempo(alerta.tempo)


@register.simple_tag
def selo_justificativa_pendente() -> str:
    """Anel vazio âmbar: falta algo para emitir (a mesma forma de "Falta destino")."""
    return format_html('<span class="selo selo--aviso selo--situacao-rascunho">{}</span>',
                       "Justificativa pendente")


ICONE_TIPO = {"Retificado": "file-pen-line", "Complementar": "file-plus-2"}


@register.simple_tag
def tipo_oficio(oficio) -> TipoOficio:
    """`{% tipo_oficio o as tipo %}` — Autorização × Convalidação + marca, com o porquê."""
    return tipo_do_oficio(oficio.data_oficio, _periodo_do_oficio(oficio)[0], oficio.marcador)


@register.simple_tag
def selo_tipo(oficio_ou_tipo) -> str:
    """Selo do tipo só quando foge do comum: Convalidação, Retificado, Complementar.
    Recebe o ofício ou um TipoOficio já resolvido (o UI Lab mostra os casos sem banco)."""
    tipo = (oficio_ou_tipo if isinstance(oficio_ou_tipo, TipoOficio)
            else tipo_oficio(oficio_ou_tipo))
    if not tipo.incomum:
        return ""
    return format_html('<span class="selo selo--neutro selo--sem-ponto" title="{}">{}{}</span>',
                       tipo.porque, icone(ICONE_TIPO.get(tipo.marca, "history"),
                                          classe="icone--sm"), tipo.selo)


@register.filter
def uf_de(cidade: object) -> str:
    """"Curitiba/PR" → "PR" (a UF de um destino escrito como Cidade/UF); vazio se não houver."""
    texto = str(cidade or "")
    return texto.rsplit("/", 1)[1].strip().upper() if "/" in texto else ""


@register.inclusion_tag("viagens/_destinos.html", takes_context=True)
def campo_destinos(context, campo, unidade=None, maximo: int = 10, titulo: str = "") -> dict:
    """O componente de destinos de todas as telas que pedem destino (termo, OS, plano,
    evento do plano, viagem): a lista "Sede e destinos" do roteiro — a sede da unidade
    fixa no topo e na volta, uma linha por destino (UF + cidade), "Adicionar destino" — e o
    painel Rota ao lado (mapa, km e tempo). A sede só desenha a rota: não vai ao formulário.

    `campo` é um CampoMunicipios (cada destino vai como "Cidade/UF", na ordem da tela);
    `unidade`, a da folha (na falta, a de quem está usando)."""
    from django.conf import settings

    from gestao.cadastros.models import ConfiguracaoInstitucional
    from gestao.viagens import policies
    from gestao.viagens.forms import UFS

    if not unidade and "request" in context:
        unidade = policies.unidade_do_usuario(context["request"].user)
    config = (ConfiguracaoInstitucional.objects.filter(unidade=unidade)
              .select_related("sede").first() if unidade else None)
    sede = f"{config.sede.nome}/{config.sede.uf}" if config else ""
    valores = [str(v) for v in (campo.value() or []) if str(v).strip()]
    return {"campo": campo, "valores": valores, "sede": sede, "sede_uf": uf_de(sede),
            "ufs": UFS, "maximo": maximo, "titulo": titulo or "Sede e destinos",
            "mapa_tiles": settings.MAPA_TILES_URL, "mapa_atribuicao": settings.MAPA_ATRIBUICAO,
            "csp_nonce": context.get("csp_nonce", "")}
