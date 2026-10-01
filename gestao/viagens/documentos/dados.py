"""Instantâneo imutável dos dados impressos no documento.

Gravado em `Documento.dados` no momento da emissão: o PDF é sempre gerado a
partir do instantâneo, nunca do ofício "vivo" — assim uma versão emitida
continua idêntica mesmo que cadastros mudem depois.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from gestao.plataforma.templatetags.ui import formatar_moeda

from ..dominio.extenso import reais_por_extenso
from ..models import Oficio


def _dt(valor) -> dict[str, str]:
    local = timezone.localtime(valor)
    return {"data": f"{local:%d/%m/%Y}", "hora": f"{local:%H:%M}"}


def dados_do_oficio(oficio: Oficio) -> dict[str, Any]:
    from ..services import assunto_do_oficio, avaliar_prazo_do_oficio, configuracao_da_unidade

    config = configuracao_da_unidade(oficio)
    viajantes = list(oficio.viajantes.select_related("servidor__cargo", "servidor__unidade"))
    trechos = list(oficio.trechos.select_related("origem", "destino").order_by("ordem"))
    motorista = next((v.servidor for v in viajantes if v.motorista), None)
    destinos = []
    for t in trechos:
        rotulo = f"{t.destino.nome}/{t.destino.uf}"
        if t.destino_id != oficio.sede_id and rotulo not in destinos:
            destinos.append(rotulo)
    volta = trechos[-1:] if trechos and trechos[-1].destino_id == oficio.sede_id else []
    ida = trechos[:-1] if volta else trechos
    if oficio.tipo_transporte == Oficio.TipoTransporte.VIATURA and oficio.viatura:
        transporte = {
            "meio": oficio.viatura.modelo, "placa": oficio.viatura.placa_formatada,
            "combustivel": str(oficio.viatura.combustivel),
            "viatura": oficio.viatura.get_tipo_display(), "oficial": True,
        }
    else:
        transporte = {
            "meio": oficio.transporte_descricao, "placa": oficio.transporte_placa,
            "combustivel": str(oficio.transporte_combustivel or ""), "viatura": "",
            "oficial": False,
        }
    prazo = avaliar_prazo_do_oficio(oficio)
    assunto = assunto_do_oficio(oficio)

    def linha_trecho(t):
        return {"origem": f"{t.origem.nome}/{t.origem.uf}",
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
        "unidade_sigla": oficio.unidade.sigla,
        "destinatario": {
            "tratamento": config.destinatario_tratamento, "nome": config.destinatario_nome,
            "cargo": config.destinatario_cargo, "orgao": config.destinatario_orgao,
            "cidade": config.destinatario_cidade,
        },
        "chefia": {"nome": config.chefia_nome, "cargo": config.chefia_cargo},
        "cabecalho_unidade": config.nome_extenso.upper(),
        "rodape": config.endereco_rodape,
        "viajantes": [
            {"nome": v.servidor.nome, "cpf": v.servidor.cpf_formatado,
             "rg": v.servidor.rg, "cargo": str(v.servidor.cargo),
             "motorista": v.motorista}
            for v in viajantes
        ],
        "destinos": destinos,
        "ida": [linha_trecho(t) for t in ida],
        "volta": [linha_trecho(t) for t in volta],
        "transporte": transporte,
        "motorista": motorista.nome if motorista else "",
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
