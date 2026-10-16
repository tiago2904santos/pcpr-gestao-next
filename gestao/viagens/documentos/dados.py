"""Instantâneo imutável dos dados impressos no documento.

Gravado em `Documento.dados` no momento da emissão: o PDF é sempre gerado a
partir do instantâneo, nunca do ofício "vivo" — assim uma versão emitida
continua idêntica mesmo que cadastros mudem depois.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Prefetch, prefetch_related_objects
from django.utils import timezone

from gestao.cadastros.models import SubstituicaoAssinante
from gestao.cadastros.services import assinante
from gestao.plataforma.templatetags.ui import formatar_moeda

from ..dominio.extenso import reais_por_extenso
from ..models import Oficio, PrestacaoServidor
from ..prestacao import ativos
from ..queries import trechos_de, viajantes_de


def _dt(valor) -> dict[str, str]:
    local = timezone.localtime(valor)
    return {"data": f"{local:%d/%m/%Y}", "hora": f"{local:%H:%M}"}


def dados_do_oficio(oficio: Oficio) -> dict[str, Any]:
    from ..services import (
        assunto_do_oficio,
        avaliar_prazo_do_oficio,
        configuracao_da_unidade,
        nome_do_motorista,
    )

    config = configuracao_da_unidade(oficio)
    # A configuração pode sobreviver entre montagens na mesma instância de ofício.
    # Renove apenas esta relação: novas substituições não podem ficar ocultas no cache.
    cache = getattr(config, "_prefetched_objects_cache", None)
    if cache is not None:
        cache.pop("substituicoes", None)
    # Ofício e justificativa usam a mesma lista; o cargo do substituto vem junto.
    prefetch_related_objects([config], Prefetch(
        "substituicoes", queryset=SubstituicaoAssinante.objects.select_related("servidor__cargo")))
    viajantes = viajantes_de(oficio)
    trechos = trechos_de(oficio)
    # O nº da solicitação (Central de Viagens) nasce na prestação de contas, depois da emissão:
    # a coluna do documento sai preenchida quando a prestação já o tem (nova versão/retificação).
    # Carregado uma vez por instância, como a equipe: montar de novo não repete a consulta.
    prefetch_related_objects([oficio], Prefetch(
        "prestacao__servidores", queryset=ativos(PrestacaoServidor.objects.all()),
        to_attr="linhas_ativas"))
    try:
        linhas = getattr(oficio.prestacao, "linhas_ativas", [])
    except Oficio.prestacao.RelatedObjectDoesNotExist:
        linhas = []
    solicitacoes = {ps.servidor_id: ps.numero_solicitacao for ps in linhas}
    destinos = []
    for t in trechos:
        rotulo = f"{t.destino.nome}/{t.destino.uf}"
        if t.destino_id != oficio.sede_id and rotulo not in destinos:
            destinos.append(rotulo)
    volta = trechos[-1:] if trechos and trechos[-1].destino_id == oficio.sede_id else []
    ida = trechos[:-1] if volta else trechos
    # Decisão D7: com volta intermediária à sede (bate-volta), o roteiro sai por trechos
    # numerados, na ordem em que acontecem, em vez de ida/retorno.
    bate_volta = any(t.destino_id == oficio.sede_id for t in ida)
    if oficio.tipo_transporte == Oficio.TipoTransporte.VIATURA and oficio.viatura:
        transporte = {
            "meio": oficio.viatura.modelo, "placa": oficio.viatura.placa_formatada,
            "combustivel": getattr(oficio.viatura.combustivel, "nome", ""),
            "viatura": oficio.viatura.get_tipo_display(), "oficial": True,
            "viatura_id": oficio.viatura_id,
        }
    else:
        # Fora da viatura oficial, o meio é o escolhido na lista; o detalhe (livre) vem
        # entre parênteses, quando a pessoa escreveu algo.
        transporte = {
            "meio": oficio.transporte_texto,
            "placa": oficio.transporte_placa,
            "combustivel": str(oficio.transporte_combustivel or ""), "viatura": "",
            "oficial": False,
        }
    prazo = avaliar_prazo_do_oficio(oficio)
    assunto = assunto_do_oficio(oficio)

    def linha_trecho(t):
        return {"ordem": t.ordem, "origem": f"{t.origem.nome}/{t.origem.uf}",
                "destino": f"{t.destino.nome}/{t.destino.uf}",
                "saida": _dt(t.saida_em), "chegada": _dt(t.chegada_em)}

    return {
        "numero": oficio.numero_formatado,
        "ano": oficio.ano,
        "data_oficio": f"{oficio.data_oficio:%d/%m/%Y}",
        "protocolo": oficio.protocolo_formatado,
        "assunto": assunto.linha,
        "assunto_rotulo": assunto.rotulo,
        "assunto_termo": assunto.termo,
        "origem": config.nome_extenso,
        "unidade_sigla": oficio.unidade.sigla or oficio.unidade.nome,
        "destinatario": {
            "tratamento": config.destinatario_tratamento, "nome": config.destinatario_nome,
            "cargo": config.destinatario_cargo, "orgao": config.destinatario_orgao,
            "cidade": config.destinatario_cidade,
        },
        # Quem assina: substituto do período, titular do tipo ou a chefia (Cadastros).
        "chefia": dict(zip(("nome", "cargo"),
                           assinante(config, "oficio", oficio.data_oficio), strict=True)),
        "assina_justificativa": dict(zip(
            ("nome", "cargo"), assinante(config, "justificativa", oficio.data_oficio),
            strict=True)),
        "cabecalho_unidade": config.nome_extenso.upper(),
        "rodape": config.rodape,
        "viajantes": [
            {"id": v.servidor_id, "nome": v.servidor.nome, "cpf": v.servidor.cpf_formatado,
             "rg": v.servidor.rg, "cargo": getattr(v.servidor.cargo, "nome", ""),
             "motorista": v.motorista,
             "solicitacao": solicitacoes.get(v.servidor_id, "")}
            for v in viajantes
        ],
        "destinos": destinos,
        "ida": [linha_trecho(t) for t in ida],
        "volta": [linha_trecho(t) for t in volta],
        "bate_volta": bate_volta,
        "trechos": [linha_trecho(t) for t in trechos],
        "transporte": transporte,
        # Da equipe ou de fora (D3): o documento cita quem dirige.
        "motorista": nome_do_motorista(oficio, viajantes),
        "porte_arma": oficio.porte_arma,
        "custeio": oficio.custeio,
        "custeio_instituicao": oficio.custeio_instituicao,
        "motivo": oficio.motivo,
        "diarias": {
            "resumo": oficio.diarias_resumo,
            "total": formatar_moeda(oficio.diarias_total),
            "total_decimal": str(oficio.diarias_total),
            "extenso": reais_por_extenso(oficio.diarias_total),
            "calculo": oficio.diarias_calculo,
        },
        "justificativa": oficio.justificativa,
        "prazo": {"dias": prazo.dias_antecedencia, "prazo": prazo.prazo_dias,
                  "obrigatoria": prazo.justificativa_obrigatoria},
        "emitido_em": f"{timezone.localtime():%d/%m/%Y %H:%M}",
    }
