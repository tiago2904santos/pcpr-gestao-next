"""O conteúdo da janela de resumo das listas de OS, termos, planos e viagens.

As quatro usam o mesmo desenho (componentes/resumo_documento.html, no padrão do resumo do
ofício); aqui cada tipo diz o que entra em cada bloco. Lê só o que a linha da lista já
carregou (`_linha_da_lista` de cada view) e as relações pré-carregadas do registro.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Servidor
from gestao.plataforma.templatetags.ui import formatar_moeda

from . import planos as planos_mod
from . import termos as termos_mod


def _servidores(servidores) -> list[dict]:
    return [{"avatar": s.iniciais, "nome": s.nome,
             "meta": getattr(getattr(s, "cargo", None), "nome", "") or "Sem cargo"}
            for s in servidores]


def _equipe_das_ordens(ordens) -> list[dict]:
    """Servidores das OS da viagem, uma única vez mesmo quando estão em mais de uma OS."""
    unicos: dict[int, Servidor] = {}
    for ordem in ordens:
        for servidor in ordem.servidores.all():
            unicos.setdefault(servidor.pk, servidor)
    return _servidores(unicos.values())


def _oficios(oficios) -> list[dict]:
    lista = reverse("viagens:oficios")
    return [{"icone": "file-text", "escuro": o.situacao == "emitido",
             "nome": f"Ofício {o.numero_formatado}", "meta": o.get_situacao_display(),
             "url": f"{lista}?{urlencode({'q': o.numero_formatado, 'resumo': o.pk})}"}
            for o in oficios]


def _quando(momento) -> str:
    return f"{timezone.localtime(momento):%d/%m/%Y}" if momento else ""


def _selos_de_tempo(selos: list[dict], tempo: dict, acao: str) -> list[dict]:
    if tempo.get("urgencia"):
        dias = tempo["dias"]
        quando = "sai hoje" if dias == 0 else "sai amanhã" if dias == 1 else f"sai em {dias} dias"
        selos.append({"texto": f"{quando} · {acao}",
                      "tom": "perigo" if tempo["urgencia"] == "perigo" else "aviso"})
    elif tempo.get("progresso") is not None:
        selos.append({"texto": "Em andamento", "tom": "info"})
    return selos


def da_ordem(o, linha: dict) -> dict:
    gerada = o.documento_gerado_em is not None
    servidores = list(o.servidores.all())
    oficios = list(o.oficios.all())
    selos = [{"texto": "Cancelada", "tom": "perigo"} if o.cancelada else
             {"texto": f"Gerada em {_quando(o.documento_gerado_em)}", "tom": "sucesso"}
             if gerada else {"texto": "Rascunho", "tom": "neutro"}]
    if o.via_vigente:
        selos.append({"texto": "Assinada", "tom": "sucesso"})
    destinos = ", ".join(str(d.municipio) for d in o.destinos.all())
    return {
        "rotulo": "OS", "numero": o.numero_formatado,
        "situacao": "cancelado" if o.cancelada else "emitido" if gerada else "rascunho",
        "contexto": "Resumo da ordem de serviço", "titulo": destinos or "Sem destino",
        "complemento": linha["periodo"] or "Sem período",
        "selos": _selos_de_tempo(selos, linha["tempo"], "gerar"),
        "dados": [{"rotulo": "Período", "valor": linha["periodo"]},
                  {"rotulo": "Tipo de necessidade", "valor": o.get_tipo_display()},
                  {"rotulo": "Documento", "valor": f"Gerado em {_quando(o.documento_gerado_em)}"
                   if gerada else "Ainda não gerado"},
                  {"rotulo": "Motivo", "valor": o.motivo, "linha": True}],
        "equipe_titulo": "Equipe", "equipe": _servidores(servidores),
        "equipe_nota": f"{len(servidores)} servidor{'es' if len(servidores) != 1 else ''}",
        "equipe_vazio": "Ninguém na equipe ainda.",
        "vinculos_titulo": "Ofícios vinculados", "vinculos": _oficios(oficios),
        "vinculos_vazio": "OS avulsa: nenhum ofício vinculado.",
        "pendencias": [] if o.cancelada else linha["pendencias"],
        "pronto": "Pronta" if gerada else "Pronta para gerar",
        "menu_template": "viagens/ordens/_menu_linha.html",
        "abrir_url": linha["url_folha"], "abrir_rotulo": "Abrir a OS", "nome": str(o)}


def _viaturas_com_quem_vai(ef) -> str:
    """"ZZA6A38 · Renault Duster (2), ZZF1J03 · Chevrolet S10 (8)" — com uma viatura só,
    sem a conta (todos vão nela)."""
    if len(ef.viaturas) < 2:
        return ", ".join(str(g.viatura) for g in ef.viaturas)
    contas = {g.viatura.pk: 0 for g in ef.viaturas}
    for s in ef.servidores:
        v = ef.viatura_de(s)
        if v is not None and v.pk in contas:
            contas[v.pk] += 1
    return ", ".join(f"{g.viatura} ({contas[g.viatura.pk]})" for g in ef.viaturas)


def do_termo(t, linha: dict) -> dict:
    ef = linha["ef"]
    docs = linha["docs"]
    vias = t.vias_vigentes or 0
    selos = [{"texto": "Cancelado", "tom": "perigo"} if t.cancelado else
             {"texto": "Assinado" if docs and vias >= len(docs) else
              f"{vias} de {len(docs)} assinados" if vias else "Sem via assinada",
              "tom": "sucesso" if docs and vias >= len(docs) else "neutro"}]
    oficios = termos_mod.oficios_do_termo(t)
    numero = f"#{t.pk}"
    return {
        "rotulo": "Termo", "numero": numero,
        "situacao": "cancelado" if t.cancelado else "emitido" if vias else "rascunho",
        "contexto": "Resumo do termo de autorização", "titulo": ef.destino_texto or "Sem destino",
        "complemento": ef.periodo_curto or "Sem período",
        "selos": _selos_de_tempo(selos, linha["tempo"], "assinar"),
        "dados": [{"rotulo": "Data do evento", "valor": ef.periodo_curto},
                  {"rotulo": "De onde vem a data", "valor": ef.fonte_periodo},
                  {"rotulo": "Viaturas" if len(ef.viaturas) > 1 else "Viatura",
                   "valor": _viaturas_com_quem_vai(ef)},
                  {"rotulo": "Documentos",
                   "valor": f"{len(docs)} termo{'s' if len(docs) != 1 else ''}"
                            f" · {vias} assinado{'s' if vias != 1 else ''}"},
                  {"rotulo": "Destinos", "valor": ef.destino_texto, "largo": True}],
        "equipe_titulo": "Equipe", "equipe": _servidores(ef.servidores),
        "equipe_nota": f"{len(ef.servidores)} servidor{'es' if len(ef.servidores) != 1 else ''}",
        "equipe_vazio": "Sem servidores: sai só o termo genérico.",
        "vinculos_titulo": "Ofícios vinculados", "vinculos": _oficios(oficios),
        "vinculos_vazio": "Termo avulso: nenhum ofício vinculado.",
        "pendencias": [] if t.cancelado else linha["pendencias"],
        "pronto": "Pronto para assinar" if vias < len(docs) else "Tudo assinado",
        "menu_template": "viagens/termos/_menu_linha.html",
        "abrir_url": linha["url_folha"], "abrir_rotulo": "Abrir o termo", "nome": str(t)}


def do_plano(p, linha: dict) -> dict:
    gerado = p.documento_gerado_em is not None
    estado, tom = linha["estado"]
    coordenador = planos_mod.coordenador(p, "adm")
    atividades = list(p.atividades.all())
    efetivo = [{"icone": "users", "nome": f"{e.quantidade} × {e.cargo.nome}",
                "meta": getattr(e.unidade, "sigla", "") or "Qualquer unidade"}
               for e in p.efetivo.all()]
    return {
        "rotulo": "Plano", "numero": f"{p.numero:02d}/{p.ano}",
        "situacao": "cancelado" if p.cancelado else "emitido" if gerado else "rascunho",
        "contexto": "Resumo do plano de trabalho",
        "titulo": ", ".join(str(d.municipio) for d in p.destinos.all()) or "Sem destino",
        "complemento": linha["periodo"] or "Sem período",
        "selos": _selos_de_tempo([{"texto": estado, "tom": tom}], linha["tempo"], "gerar"),
        "dados": [{"rotulo": "Período", "valor": linha["periodo"]},
                  {"rotulo": "Horário", "valor": p.horario},
                  {"rotulo": "Programa", "valor": p.programa_nome if hasattr(p, "programa_nome")
                   else ""},
                  {"rotulo": "Diárias", "valor": formatar_moeda(linha["diarias"])
                   if linha["diarias"] is not None else ""},
                  {"rotulo": "Coordenação", "valor": getattr(coordenador, "nome", "")},
                  {"rotulo": "Atividades", "valor": ", ".join(a.nome for a in atividades),
                   "largo": True}],
        "equipe_titulo": "Efetivo", "equipe": efetivo,
        "equipe_nota": f"{linha['efetivo'] or 0} no efetivo",
        "equipe_vazio": "Sem efetivo informado.",
        "vinculos_titulo": "Ofícios vinculados", "vinculos": _oficios(p.oficios.all()),
        "vinculos_vazio": "Plano avulso: nenhum ofício vinculado.",
        "pendencias": linha["pendencias"],
        "pronto": "Gerado" if gerado else "Pronto para gerar",
        "menu_template": "viagens/planos/_menu_linha.html",
        "abrir_url": linha["url_folha"], "abrir_rotulo": "Abrir o plano", "nome": str(p)}


def da_viagem(v, linha: dict, documentos: dict) -> dict:
    selos = [{"texto": "Cancelada", "tom": "perigo"} if v.cancelada else
             {"texto": v.get_situacao_display(), "tom": "neutro"}]
    periodo = (f"{v.data_inicio:%d/%m/%Y}" + (f" a {v.data_fim:%d/%m/%Y}"
               if v.data_fim and v.data_fim != v.data_inicio else "")) if v.data_inicio else ""
    vinculos = [{"icone": icone, "nome": f"{n} {nome}", "meta": meta}
                for icone, n, nome, meta in (
                    ("file-text", documentos["oficios"], "ofício(s)", "com a equipe de cada um"),
                    ("clipboard-list", documentos["ordens"], "OS", "ordens de serviço"),
                    ("list-checks", documentos["planos"], "plano(s)", "planos de trabalho"),
                    ("file-signature", documentos["termos"], "termo(s)", "autorizações"),
                    ("route", documentos["roteiros"], "roteiro(s)", "percursos"))
                if n]
    equipe_os = _equipe_das_ordens(v.ordens.all())
    return {
        "rotulo": "Viagem", "numero": f"#{v.pk}",
        "situacao": "cancelado" if v.cancelada else "rascunho",
        "contexto": "Resumo da viagem", "titulo": v.titulo or "Viagem sem tipo",
        "complemento": linha["destinos"] or "Sem destino",
        "selos": _selos_de_tempo(selos, linha["tempo"], "gerar os documentos"),
        "dados": [{"rotulo": "Período", "valor": periodo},
                  {"rotulo": "Tipos", "valor": ", ".join(str(t) for t in v.tipos.all())},
                  {"rotulo": "Motivo", "valor": v.motivo, "largo": True}],
        "equipe_titulo": "Destinos",
        "equipe": [{"icone": "map-pin", "nome": str(d.municipio), "meta": ""}
                   for d in v.destinos.all()],
        "equipe_nota": "", "equipe_vazio": "Sem destino informado.",
        "equipe_os_titulo": "Equipe da ordem de serviço", "equipe_os": equipe_os,
        "equipe_os_nota": (f"{len(equipe_os)} servidor"
                           f"{'es' if len(equipe_os) != 1 else ''}"),
        "equipe_os_vazio": "Nenhum servidor nas ordens de serviço.",
        "vinculos_indice": "03",
        "vinculos_titulo": "Documentos da viagem", "vinculos": vinculos,
        "vinculos_vazio": "Nenhum documento ainda: gere os documentos da viagem.",
        "pendencias": linha["pendencias"], "pronto": "Tudo pronto", "pronto_neutro": True,
        "menu_template": "viagens/viagem/_menu_linha.html",
        "abrir_url": linha["url_folha"], "abrir_rotulo": "Abrir a viagem",
        "nome": f"Viagem #{v.pk}"}
