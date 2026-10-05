"""Relatório técnico da prestação de contas (módulo 9c, paridade com `rt_services` da
referência; ficha em docs/migration/prestacao.md).

O texto é da equipe (um relatório por prestação); o documento sai por servidor, com o nome,
o CPF e a diária dele (a recebida, quando difere da liberada — nunca acima dela). Trava
quando a equipe inteira está finalizada.
"""

from __future__ import annotations

import unicodedata
from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from gestao.cadastros.models import ModeloTexto

from . import diario, policies
from .dominio import relatorio as dominio
from .dominio.escrita import data_por_extenso
from .models import PlanoTrabalho, PrestacaoContas, PrestacaoServidor, RelatorioTecnico
from .viagem import periodo_curto

PENDENCIA = dominio.PENDENCIA


class RelatorioInvalido(Exception):
    pass


# ---------------------------------------------------------------- leitura
def plano_da_viagem(prestacao: PrestacaoContas) -> PlanoTrabalho | None:
    """O plano de trabalho da viagem do ofício (o mais recente, não cancelado)."""
    viagem_id = prestacao.oficio.viagem_id
    if not viagem_id:
        return None
    return (PlanoTrabalho.objects.filter(viagem_id=viagem_id, cancelado=False)
            .order_by("-pk").first())


def _trechos(prestacao: PrestacaoContas):
    return list(prestacao.oficio.trechos.select_related("destino").order_by("ordem"))


def retorno(prestacao: PrestacaoContas) -> date | None:
    trechos = _trechos(prestacao)
    return timezone.localtime(trechos[-1].chegada_em).date() if trechos else None


def valores_dos_marcadores(prestacao: PrestacaoContas) -> dict[str, str]:
    """{destino}, {periodo}, {motivo}, {servidores}, {atividades}, {metas} (referência m118)."""
    oficio = prestacao.oficio
    trechos = _trechos(prestacao)
    destinos = list(dict.fromkeys(str(t.destino) for t in trechos if t.destino != oficio.sede))
    periodo = (periodo_curto(timezone.localtime(trechos[0].saida_em).date(),
                             timezone.localtime(trechos[-1].chegada_em).date())
               if trechos else "")
    nomes = [v.servidor.nome for v in oficio.viajantes.select_related("servidor")
             .order_by("ordem")]
    plano = plano_da_viagem(prestacao)
    return {"destino": ", ".join(destinos), "periodo": periodo,
            "motivo": dominio.espacos(oficio.motivo), "servidores": ", ".join(nomes),
            "atividades": dominio.espacos(plano.atividades_texto) if plano else "",
            "metas": dominio.espacos(plano.metas) if plano else ""}


def sugestoes(prestacao: PrestacaoContas) -> dict[str, str]:
    """Valor inicial dos campos vazios (nada é gravado até a pessoa salvar): descrição = o
    motivo do ofício (sem ele, a contextualização do plano); objetivo = a descrição da
    viagem (sem ela, o que os resultados do plano dizem ou metas + atividades); conclusão =
    a dos resultados do plano (sem ela, as considerações finais)."""
    from . import resultados

    oficio = prestacao.oficio
    plano = plano_da_viagem(prestacao)
    viagem = oficio.viagem if oficio.viagem_id else None
    dos_resultados = resultados.sugestao_para_rt(plano) if plano else {}
    juntar = "\n\n".join
    s = {
        "motivo": (oficio.motivo or "").strip()
        or (plano.contextualizacao.strip() if plano else ""),
        "atividade": ((viagem.descricao or "").strip() if viagem else "")
        or dos_resultados.get("objetivo", "")
        or (juntar(t for t in (plano.metas.strip(), plano.atividades_texto.strip()) if t)
            if plano else ""),
        "conclusao": dos_resultados.get("conclusao", "")
        or (plano.consideracoes.strip() if plano else ""),
    }
    return {campo: texto for campo, texto in s.items() if texto}


def textos_prontos(prestacao: PrestacaoContas) -> dict[str, list[tuple[int, str, str]]]:
    """Por campo, os textos prontos ativos (id, nome, texto com os marcadores trocados)."""
    valores = valores_dos_marcadores(prestacao)
    por_tipo: dict[str, list[tuple[int, str, str]]] = {}
    for m in ModeloTexto.objects.filter(tipo__in=dominio.TIPO_DO_CAMPO.values(), ativo=True):
        por_tipo.setdefault(m.tipo, []).append(
            (m.pk, m.nome, dominio.aplicar_marcadores(m.texto, valores)))
    return {campo: por_tipo.get(tipo, []) for campo, tipo in dominio.TIPO_DO_CAMPO.items()}


def preenchido(prestacao: PrestacaoContas) -> bool:
    rt = RelatorioTecnico.objects.filter(prestacao=prestacao).first()
    return bool(rt) and dominio.preenchido({c: getattr(rt, c) for c in dominio.CAMPOS_TEXTO})


def preenchidos(prestacao_ids) -> set[int]:
    """As prestações (dentre as dadas) com o RT preenchido, numa consulta só (lista)."""
    vazio = Q(motivo="") | Q(atividade="") | Q(conclusao="")
    return set(RelatorioTecnico.objects.filter(prestacao_id__in=list(prestacao_ids))
               .exclude(vazio).values_list("prestacao_id", flat=True))


def diaria_padrao(prestacao: PrestacaoContas) -> str:
    """A diária liberada por servidor, como o documento imprime ("R$ 377,72")."""
    from . import prestacao as servico
    ps = servico.ativos(prestacao.servidores.all()).first()
    valor = servico.diaria_liberada(ps) if ps else None
    return dominio.moeda(valor) if valor else ""


def diaria_do_servidor(rt: RelatorioTecnico, ps: PrestacaoServidor) -> str:
    """A recebida (com a observação) quando informada; senão a do relatório; senão a
    liberada."""
    if ps.diaria_valor_override:
        return " ".join(t for t in (dominio.moeda(ps.diaria_valor_override),
                                    ps.diaria_valor_override_observacao) if t)
    return dominio.espacos(rt.diaria) or diaria_padrao(rt.prestacao)


# ---------------------------------------------------------------- escrita
@transaction.atomic
def obter(prestacao: PrestacaoContas) -> RelatorioTecnico:
    """O relatório da prestação; o novo já nasce com o custeio padrão, a diária liberada,
    as trocas do diário nas informações complementares e os textos prontos padrão de cada
    campo (com os marcadores trocados) — referência m097/m118."""
    rt, novo = RelatorioTecnico.objects.get_or_create(prestacao=prestacao)
    rt.prestacao = prestacao
    if not novo:
        return rt
    for campo, (_, _, padrao) in dominio.CUSTEIO.items():
        setattr(rt, campo, padrao)
    rt.diaria = diaria_padrao(prestacao)
    d = diario.DiarioBordo.objects.filter(prestacao=prestacao).first()
    trocas = diario.alteracoes(d) if d else []
    if trocas:
        texto = "; ".join(trocas)
        rt.info_complementares = texto[:1].upper() + texto[1:] + "."
    valores = valores_dos_marcadores(prestacao)
    padroes = {m.tipo: m.texto for m in ModeloTexto.objects.filter(
        tipo__in=dominio.TIPO_DO_CAMPO.values(), padrao=True, ativo=True)}
    for campo, tipo in dominio.TIPO_DO_CAMPO.items():
        if tipo in padroes and not getattr(rt, campo):
            setattr(rt, campo, dominio.aplicar_marcadores(padroes[tipo], valores))
    rt.save()
    return rt


def _travar(usuario, rt_pk: int) -> RelatorioTecnico:
    rt = (RelatorioTecnico.objects.select_for_update()
          .select_related("prestacao__oficio").get(pk=rt_pk))
    if diario.equipe_finalizada(rt.prestacao):
        raise RelatorioInvalido("Prestação finalizada — reabra para editar.")
    policies.exigir(policies.pode_editar_equipe_prestacao(usuario, rt.prestacao),
                    "Você não pode alterar este relatório.")
    return rt


@transaction.atomic
def salvar(usuario, rt_pk: int, campos: dict[str, str]) -> dict[str, str]:
    """Textos e custeio (`<campo>` e `<campo>_outro`) e as diárias recebidas
    (`ps-<pk>-diaria`). Devolve os erros por campo — um valor recusado não derruba o resto
    (referência)."""
    rt = _travar(usuario, rt_pk)
    mudou = []
    for campo in dominio.CAMPOS_TEXTO:
        if campo in campos and getattr(rt, campo) != campos[campo].strip():
            setattr(rt, campo, campos[campo].strip())
            mudou.append(campo)
    if "diaria" in campos and rt.diaria != dominio.espacos(campos["diaria"]):
        rt.diaria = dominio.espacos(campos["diaria"])[:255]
        mudou.append("diaria")
    for campo in dominio.CUSTEIO:
        if campo not in campos:
            continue
        valor = dominio.custeio(campo, campos[campo], campos.get(f"{campo}_outro", ""))
        if valor is not None and getattr(rt, campo) != valor:
            setattr(rt, campo, valor[:255])
            mudou.append(campo)
    if mudou:
        rt.save(update_fields=[*mudou, "atualizado_em"])
    return _salvar_recebidas(rt, campos)


def _salvar_recebidas(rt: RelatorioTecnico, campos: dict[str, str]) -> dict[str, str]:
    from . import prestacao as servico

    erros: dict[str, str] = {}
    por_pk = {int(nome.split("-")[1]): valor for nome, valor in campos.items()
              if nome.startswith("ps-") and nome.endswith("-diaria")
              and nome.split("-")[1].isdigit()}
    for ps in servico.ativos(PrestacaoServidor.objects.filter(prestacao=rt.prestacao,
                                                              pk__in=por_pk)):
        chave = f"ps-{ps.pk}-diaria"
        try:
            valor, observacao = dominio.ler_valor(por_pk[ps.pk])
        except dominio.ValorInvalido as exc:
            erros[chave] = str(exc)
            continue
        if (erro := dominio.conferir_recebido(valor, servico.diaria_liberada(ps))):
            erros[chave] = erro
            continue
        if ps.finalizada:
            continue  # o do colega já finalizado não muda (a linha dele trava)
        if (ps.diaria_valor_override, ps.diaria_valor_override_observacao) != (
                valor, observacao[:255]):
            ps.diaria_valor_override, ps.diaria_valor_override_observacao = (
                valor, observacao[:255])
            ps.save(update_fields=["diaria_valor_override", "diaria_valor_override_observacao",
                                   "atualizado_em"])
    return erros


# ---------------------------------------------------------------- documento
def nome_do_arquivo(rt: RelatorioTecnico, ps: PrestacaoServidor, formato: str) -> str:
    nome = unicodedata.normalize("NFKD", ps.servidor.nome).encode("ascii", "ignore").decode()
    nome = "_".join(nome.upper().split())
    numero = rt.prestacao.oficio.numero_formatado.replace("/", "-")
    return f"RT_{nome}_OFICIO_{numero}.{'pdf' if formato == 'pdf' else 'docx'}"


def dados_do_documento(rt: RelatorioTecnico, ps: PrestacaoServidor) -> dict:
    from gestao.cadastros.models import ConfiguracaoInstitucional

    oficio = rt.prestacao.oficio
    config = (ConfiguracaoInstitucional.objects.filter(unidade=oficio.unidade)
              .select_related("sede").first())
    data = dominio.data_do_documento(timezone.localdate(), retorno(rt.prestacao))
    cpf = ps.servidor.cpf
    if len(cpf) == 11:
        cpf = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    return {
        "titulo": f"Relatório técnico – {ps.servidor.nome}",
        "unidade": (config.nome_extenso if config else oficio.unidade.nome).upper(),
        "rodape": config.rodape if config else "",
        "oficio": oficio.numero_formatado,
        "sede": str(config.sede.nome) if config else "",
        "data_extenso": data_por_extenso(data),
        "nome": ps.servidor.nome, "cpf": cpf,
        "diaria": diaria_do_servidor(rt, ps),
        "translado": rt.translado or dominio.CUSTEIO["translado"][2],
        "combustivel": rt.combustivel or dominio.CUSTEIO["combustivel"][2],
        "passagem": rt.passagem or dominio.CUSTEIO["passagem"][2],
        "secoes": [{"titulo": dominio.ROTULOS[c],
                    "texto": (rt.motivo or oficio.motivo) if c == "motivo"
                    else getattr(rt, c)} for c in dominio.CAMPOS_TEXTO],
    }


def html_do_documento(dados: dict) -> str:
    from django.template.loader import render_to_string

    from .documentos.pdf import _recursos
    return render_to_string("viagens/documentos/relatorio_tecnico.html",
                            {"d": dados, **_recursos(False)})


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
