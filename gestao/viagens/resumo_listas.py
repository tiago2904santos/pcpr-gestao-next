"""O conteúdo da janela de resumo das listas de OS, termos, planos, viagens e roteiros.

Todas usam o mesmo esqueleto (componentes/resumo_documento.html), no contrato de
`docs/visual-agents/resumos/README.md`: cabeçalho, avisos, narrativa, documentos, blocos
numerados (o último são os vínculos) e rodapé. Aqui cada tipo diz o que entra em cada
região; o que não se aplica fica de fora (None ou lista vazia) e não deixa vão. Lê o que a
linha da lista já carregou (`_linha_da_lista` de cada view) e as relações pré-carregadas.

As chaves de `r`:
- cabeçalho: em destaque, rotulo + numero, titulo (o destino) e periodo, com o tempo até a
  saída (inicio/fim) ou a urgencia ({nivel, dias}); no pé, situacao (rascunho|emitido|
  cancelado, a forma do selo), situacao_texto, assinatura (OS: "Assinada" para quem não vê
  os documentos) e detalhes ([{rotulo, valor}]: o que não se repete nos cartões do corpo);
- narrativa: o porquê, em texto corrido ([{rotulo, texto} | {rotulo, fichas}]): motivo,
  justificativa, observações, atividades;
- avisos: cancelamento ({titulo, motivo}) ou pendencias ([{mensagem, url}]) e falta_para;
- documentos: None (não emite ou quem vê não pode abrir) ou {nota, pecas, minuta};
- blocos: [{titulo, nota, cartoes, vazio} | {percurso: True, ...} | {diarias: True, nota}];
- rodapé: ler ({url, rotulo, icone}), menu_template, abrir_url, abrir_rotulo, editavel, nome.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.urls import reverse
from django.utils import timezone

from gestao.plataforma.templatetags.ui import formatar_moeda

from . import planos as planos_mod
from . import policies
from . import termos as termos_mod
from .templatetags.viagens import periodo_do_resumo


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _contagem(n: int, singular: str, plural: str, nenhum: str) -> str:
    """Contagem do cabeçalho: sem itens, diz o que falta em vez de "0 …"."""
    return _plural(n, singular, plural) if n else nenhum


def _servidores(servidores) -> list[dict]:
    return [{"avatar": s.iniciais, "nome": s.nome,
             "meta": getattr(getattr(s, "cargo", None), "nome", "") or "Sem cargo"}
            for s in servidores]


def _equipe_das_ordens(ordens) -> list[dict]:
    """Servidores das OS da viagem, uma única vez mesmo quando estão em mais de uma OS."""
    unicos: dict[int, object] = {}
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


def _viatura(viatura, meta_extra: str = "") -> dict:
    """A viatura como mais um cartão da equipe (o mesmo desenho do resumo do ofício)."""
    meta = viatura.placa_formatada + (f" · {viatura.get_tipo_display().lower()}"
                                      if viatura.tipo else "")
    return {"icone": "car", "nome": viatura.modelo or "Viatura",
            "meta": meta + (f" · {meta_extra}" if meta_extra else "")}


def _quando(momento) -> str:
    return f"{timezone.localtime(momento):%d/%m/%Y}" if momento else ""


def _cancelamento(obj, rotulo: str) -> dict | None:
    """"Cancelada em 28/09/2026" e o motivo — o mesmo aviso do resumo do ofício."""
    cancelado_em = getattr(obj, "cancelado_em", None)
    titulo = f"{rotulo} em {_quando(cancelado_em)}" if cancelado_em else rotulo
    return {"titulo": titulo, "motivo": getattr(obj, "motivo_cancelamento", "")}


def _urgencia(tempo: dict) -> dict | None:
    return {"nivel": tempo["urgencia"], "dias": tempo["dias"]} if tempo.get("urgencia") else None


def _minuta(url: str, nota: str) -> dict:
    return {"url": url, "nota": nota}


def _periodo(inicio, fim) -> str:
    return periodo_do_resumo(inicio, fim) or "Sem período"


def _detalhes(obj, *pares: tuple[str, str], sem: tuple[str, ...] = ()) -> list[dict]:
    """O sub-header: os dados próprios do tipo e, por último, os comuns a todos (unidade,
    viagem, quem criou, última atualização). Só o que tem valor — o que falta aparece na
    conferência."""
    viagem = getattr(obj, "viagem", None)
    criado_por = getattr(obj, "criado_por", None)
    comuns = (("Unidade", str(obj.unidade) if obj.unidade_id else ""),
              ("Viagem", (viagem.titulo or f"#{viagem.pk}") if viagem else ""),
              ("Criado por", getattr(criado_por, "nome", "")),
              ("Atualizado em", f"{timezone.localtime(obj.atualizado_em):%d/%m/%Y %H:%M}"
               if obj.atualizado_em else ""))
    return [{"rotulo": rotulo, "valor": str(valor)} for rotulo, valor in (*pares, *comuns)
            if valor and rotulo not in sem]


ICONES_DOS_BLOCOS = {
    "Equipe": "users", "Equipe e transporte": "users", "Equipe da ordem de serviço": "users",
    "Efetivo": "users", "Roteiro": "route", "Ofícios vinculados": "file-text",
    "Documentos da viagem": "files",
}


def _icones(r: dict) -> dict:
    """Cada bloco com o ícone do que mostra — o mesmo título de Documentos e Diárias, em
    vez de numerar uns e não outros."""
    for bloco in r["blocos"]:
        bloco.setdefault("icone", ICONES_DOS_BLOCOS.get(bloco.get("titulo", ""), ""))
    return r


def _distancia(trechos) -> str:
    total = sum((t.distancia_km or 0) for t in trechos)
    return f"{total:,.0f} km".replace(",", ".") if total else ""


def _origem_do_periodo(fonte: str) -> str:
    """"Período do evento — Plano de Trabalho 01/2026/ASCOM" → "Plano de Trabalho
    01/2026/ASCOM": de onde vem o período do termo, curto, no pé do cabeçalho."""
    _, _, origem = fonte.partition(" — ")
    return origem or fonte


def _narrativa(*itens: tuple[str, str]) -> list[dict]:
    return [{"rotulo": rotulo, "texto": texto} for rotulo, texto in itens if texto]


def da_ordem(o, linha: dict, usuario) -> dict:
    gerada = o.documento_gerado_em is not None
    servidores = list(o.servidores.all())
    oficios = list(o.oficios.all())
    destinos = ", ".join(str(d.municipio) for d in o.destinos.all())
    documentos: dict | None = None
    ler = None
    if policies.pode_ver_documento_ordem(usuario, o):
        pdf = reverse("viagens:documento_ordem", args=[o.pk, "pdf"])
        if gerada:
            via = linha.get("via")
            documentos = {"pecas": [{"titulo": "Ordem de serviço", "url": pdf,
                                     "meta": f"PDF · {_quando(o.documento_gerado_em)}",
                                     "via": via}]}
            # Como no ofício: o rodapé lê o documento atual; a via abre na própria peça
            # (e pode estar desatualizada — "dados mudaram").
            ler = {"url": pdf, "rotulo": "Ver o PDF", "icone": "file-text"}
        else:
            documentos = {"minuta": _minuta(pdf + "?previa=1", "Ainda não gerada. A minuta "
                                            "mostra os dados salvos, sem fixar a data.")}
            ler = {"url": pdf + "?previa=1", "rotulo": "Ver minuta", "icone": "printer"}
    return _icones({
        "rotulo": "OS", "numero": o.numero_formatado, "nome": str(o),
        "situacao": "cancelado" if o.cancelada else "emitido" if gerada else "rascunho",
        "situacao_texto": "Cancelada" if o.cancelada else
                          f"Gerada em {_quando(o.documento_gerado_em)}" if gerada else "Rascunho",
        # Quem não abre os documentos (só lê) ainda vê que há via assinada, como na lista.
        "assinatura": "Assinada" if getattr(o, "via_vigente", None) and documentos is None
        and not o.cancelada else "", "titulo": destinos or "Sem destino",
        "periodo": _periodo(o.data_inicio, o.data_fim),
        "detalhes": _detalhes(o, ("Necessidade", o.get_tipo_display()),
                              ("Documento de", f"{o.data_documento:%d/%m/%Y}"
                               if gerada and o.data_documento else "")),
        "narrativa": _narrativa(("Motivo", o.motivo)),
        "inicio": o.data_inicio, "fim": o.data_fim, "urgencia": _urgencia(linha["tempo"]),
        "cancelamento": _cancelamento(o, "Cancelada") if o.cancelada else None,
        "pendencias": [] if o.cancelada else linha["pendencias"],
        "falta_para": "o texto sair completo", "acao": "gerar",
        "documentos": documentos,
        "blocos": [
            {"titulo": "Equipe", "nota": _contagem(len(servidores), "servidor", "servidores", ""),
             "cartoes": _servidores(servidores), "vazio": "Ninguém na equipe ainda."},
            {"titulo": "Ofícios vinculados", "cartoes": _oficios(oficios),
             "vazio": "OS avulsa: nenhum ofício vinculado."}],
        "ler": ler, "menu_template": "viagens/ordens/_menu_linha.html",
        "abrir_url": linha["url_folha"], "abrir_rotulo": "Abrir a OS",
        "editavel": linha["editavel"]})


def do_termo(t, linha: dict, usuario) -> dict:
    ef = linha["ef"]
    docs = linha["docs"]
    vias = t.vias_vigentes or 0
    assinado = bool(docs) and vias >= len(docs)
    oficios = termos_mod.oficios_do_termo(t)
    documentos: dict | None = None
    ler = None
    if policies.pode_ver_documento_termo(usuario, t):
        pecas = [{"titulo": d["titulo"], "meta": f"PDF · {d['descricao']}",
                  "url": reverse("viagens:documento_termo", args=[t.pk, d["chave"], "pdf"]),
                  "via": d.get("via")} for d in docs]
        documentos = {"nota": f"{_plural(len(docs), 'termo', 'termos')} · "
                              f"{_plural(vias, 'assinado', 'assinados')}", "pecas": pecas}
        ler = {"url": reverse("viagens:todos_termo", args=[t.pk, "pdf"]),
               "rotulo": "Ver todos em PDF", "icone": "file-text"}
    equipe = _servidores(ef.servidores)
    for grupo in ef.viaturas:
        quem = len(grupo.servidores) if len(ef.viaturas) > 1 else 0
        equipe.append(_viatura(grupo.viatura, _plural(quem, "servidor", "servidores")
                               if quem else ""))
    return _icones({
        "rotulo": "Termo", "numero": f"#{t.pk}", "nome": str(t),
        "situacao": "cancelado" if t.cancelado else "emitido" if assinado else "rascunho",
        "situacao_texto": "Cancelado" if t.cancelado else "Assinado" if assinado else
                          f"{vias} de {len(docs)} assinados" if vias else "Sem via assinada",
        "titulo": ef.destino_texto or "Sem destino",
        "periodo": _periodo(ef.inicio, ef.fim),
        "detalhes": _detalhes(t, ("Evento", t.evento),
                              ("Origem do período", _origem_do_periodo(ef.fonte_periodo))),
        "narrativa": [],
        "inicio": ef.inicio, "fim": ef.fim, "urgencia": _urgencia(linha["tempo"]),
        "cancelamento": _cancelamento(t, "Cancelado") if t.cancelado else None,
        "pendencias": [] if t.cancelado else linha["pendencias"],
        "falta_para": "o termo sair completo", "acao": "assinar",
        "documentos": documentos,
        "blocos": [
            {"titulo": "Equipe e transporte" if ef.viaturas else "Equipe",
             "nota": _contagem(len(ef.servidores), "servidor", "servidores", ""),
             "cartoes": equipe, "vazio": "Sem servidores: sai só o termo genérico."},
            {"titulo": "Ofícios vinculados", "cartoes": _oficios(oficios),
             "vazio": "Termo avulso: nenhum ofício vinculado."}],
        "ler": ler, "menu_template": "viagens/termos/_menu_linha.html",
        "abrir_url": linha["url_folha"], "abrir_rotulo": "Abrir o termo",
        "editavel": linha["editavel"]})


def do_plano(p, linha: dict, usuario) -> dict:
    gerado = p.documento_gerado_em is not None
    coordenador = planos_mod.coordenador(p, "adm")
    atividades = list(p.atividades.all())
    inicio, fim = planos_mod.periodo_geral(p)
    # A quantidade no lugar do avatar: "2×" diz mais que o mesmo ícone repetido.
    efetivo = [{"avatar": f"{e.quantidade}×", "nome": e.cargo.nome,
                "meta": getattr(e.unidade, "sigla", "") or "Qualquer unidade"}
               for e in p.efetivo.all()]
    documentos: dict | None = None
    ler = None
    if policies.pode_ver_documento_plano(usuario, p):
        pdf = reverse("viagens:documento_plano", args=[p.pk, "pdf"])
        if gerado:
            documentos = {"pecas": [{"titulo": "Plano de trabalho", "url": pdf,
                                     "meta": f"PDF · {_quando(p.documento_gerado_em)}"}]}
            ler = {"url": pdf, "rotulo": "Ver o PDF", "icone": "file-text"}
        else:
            documentos = {"minuta": _minuta(pdf + "?previa=1", "Ainda não gerado. A minuta "
                                            "mostra os dados salvos, sem fixar a data.")}
            ler = {"url": pdf + "?previa=1", "rotulo": "Ver minuta", "icone": "printer"}
    n_efetivo = linha["efetivo"] or 0
    return _icones({
        "rotulo": "Plano", "numero": f"{p.numero:02d}/{p.ano}", "nome": str(p),
        "situacao": "cancelado" if p.cancelado else "emitido" if gerado else "rascunho",
        "situacao_texto": "Cancelado" if p.cancelado else
                          f"Gerado em {_quando(p.documento_gerado_em)}" if gerado else "Rascunho",
        "titulo": ", ".join(str(d.municipio) for d in p.destinos.all()) or "Sem destino",
        "periodo": _periodo(inicio, fim),
        "detalhes": _detalhes(
            p, ("Horário", p.horario), ("Programa", p.programa_nome),
            ("Coordenação", getattr(coordenador, "nome", "")),
            ("Coordenação operacional",
             getattr(planos_mod.coordenador(p, "op"), "nome", "")),
            ("Eventos", _contagem(len(p.eventos.all()) + 1, "evento", "eventos", "")
             if p.eventos.all() else ""),
            sem=("Unidade", "Viagem")),
        "narrativa": [{"rotulo": "Atividades", "fichas": [a.nome for a in atividades]}]
        if atividades else [],
        "inicio": inicio, "fim": fim, "urgencia": _urgencia(linha["tempo"]),
        "cancelamento": _cancelamento(p, "Cancelado") if p.cancelado else None,
        "pendencias": [] if p.cancelado else linha["pendencias"],
        "falta_para": "gerar", "acao": "gerar",
        "documentos": documentos,
        "blocos": [
            {"titulo": "Efetivo", "nota": f"{n_efetivo} no efetivo" if n_efetivo else "",
             "cartoes": efetivo,
             "vazio": "Sem efetivo informado."},
            # As diárias no mesmo painel do ofício e do roteiro (o cálculo do evento 1).
            {"diarias": True, "nota": _nota_diarias(p, linha["diarias"])},
            {"titulo": "Ofícios vinculados", "cartoes": _oficios(p.oficios.all()),
             "vazio": "Plano avulso: nenhum ofício vinculado."}],
        "ler": ler, "menu_template": "viagens/planos/_menu_linha.html",
        "abrir_url": linha["url_folha"], "abrir_rotulo": "Abrir o plano",
        "editavel": linha["editavel"]})


def _nota_diarias(p, total_geral) -> str:
    """Com eventos adicionais, o painel mostra o evento 1; a nota dá o total do plano."""
    if not p.eventos.all():
        return ""
    if total_geral is None:
        return "Evento 1 · o total do plano sai quando todos os eventos fecharem"
    return f"Evento 1 · plano inteiro: {formatar_moeda(total_geral)}"


def diarias_do_plano(p) -> tuple[dict, str]:
    """(cálculo, erro) do painel de diárias do plano — o mesmo formato do ofício."""
    resultado, mensagens = planos_mod.calculo(p)
    if resultado is None:
        return {}, " ".join(mensagens)
    return resultado.como_dict(), ""


def da_viagem(v, linha: dict, documentos: dict) -> dict:
    vinculos = [{"icone": icone, "nome": _plural(n, um, varios), "meta": meta}
                for icone, n, um, varios, meta in (
                    ("file-text", documentos["oficios"], "ofício", "ofícios",
                     "com a equipe de cada um"),
                    ("clipboard-list", documentos["ordens"], "OS", "OS", "ordens de serviço"),
                    ("list-checks", documentos["planos"], "plano", "planos", "planos de trabalho"),
                    ("file-signature", documentos["termos"], "termo", "termos", "autorizações"),
                    ("route", documentos["roteiros"], "roteiro", "roteiros", "percursos"))
                if n]
    destinos = [{"icone": "map-pin", "nome": str(d.municipio), "meta": ""}
                for d in v.destinos.all()]
    equipe_os = _equipe_das_ordens(v.ordens.all())
    blocos: list[dict] = []
    if equipe_os:
        blocos.append({"titulo": "Equipe da ordem de serviço",
                       "nota": _plural(len(equipe_os), "servidor", "servidores"),
                       "cartoes": equipe_os})
    blocos.append({"titulo": "Documentos da viagem", "cartoes": vinculos,
                   "vazio": "Nenhum documento gerado." if v.cancelada else
                            "Nenhum documento ainda: gere os documentos da viagem."})
    gerados = v.situacao == "gerados"
    nome = v.titulo or ", ".join(str(t) for t in v.tipos.all())
    return _icones({
        "rotulo": "Viagem", "numero": f"#{v.pk}", "nome": f"Viagem #{v.pk}",
        "situacao": "cancelado" if v.cancelada else "emitido" if gerados else "rascunho",
        "situacao_texto": v.get_situacao_display(),
        "titulo": ", ".join(d["nome"] for d in destinos) or "Sem destino",
        "periodo": _periodo(v.data_inicio, v.data_fim),
        # O título é o destino (como nos outros resumos); o nome da viagem desce para o pé.
        "detalhes": _detalhes(
            v, ("Viagem", nome if nome and not any(d["nome"] in nome for d in destinos) else ""),
            ("Descrição", v.descricao)),
        "narrativa": _narrativa(("Motivo", v.motivo)),
        "inicio": v.data_inicio, "fim": v.data_fim, "urgencia": _urgencia(linha["tempo"]),
        "cancelamento": _cancelamento(v, "Cancelada") if v.cancelada else None,
        "pendencias": [] if v.cancelada else linha["pendencias"],
        "falta_para": "gerar os documentos", "acao": "gerar os documentos",
        "documentos": None,
        "blocos": blocos,
        "ler": None, "menu_template": "viagens/viagem/_menu_linha.html",
        "abrir_url": linha["url_folha"], "abrir_rotulo": "Abrir a viagem",
        "editavel": linha["editavel"]})


def do_roteiro(roteiro, trechos: list, oficios: list, pode_editar: bool) -> dict:
    """O roteiro no mesmo esqueleto: registro, percurso com diárias e os ofícios que o usaram.
    Não emite documento nem tem conferência. `pode_editar` = quem gere os roteiros (menu);
    a folha só abre no roteiro ativo (o cancelado não tem leitura: reativa-se pelo menu)."""
    cancelado = roteiro.situacao == "cancelado"
    inicio, fim = (trechos[0].saida_em, trechos[-1].chegada_em) if trechos else (None, None)
    lista = reverse("viagens:oficios")
    vinculos = [{"icone": "file-text", "escuro": o.situacao == "emitido",
                 "nome": f"Ofício {o.numero_formatado}",
                 "meta": o.get_situacao_display() + (f" · {p}" if (p := _periodo_trechos(o))
                                                     else ""),
                 "url": f"{lista}?{urlencode({'q': o.numero_formatado, 'resumo': o.pk})}"}
                for o in oficios]
    editavel = pode_editar and not cancelado
    return _icones({
        "rotulo": "Roteiro", "numero": f"#{roteiro.pk}", "nome": f"Roteiro #{roteiro.pk}",
        "situacao": "cancelado" if cancelado else "",
        "situacao_texto": "Cancelado" if cancelado else "",
        "titulo": ", ".join(_destinos_do_roteiro(roteiro, trechos)) or "Sem destino",
        "periodo": _periodo(inicio, fim),
        "detalhes": _detalhes(
            roteiro, ("Distância", _distancia(trechos)),
            ("Formato", "Bate-volta" if roteiro.bate_volta else "")),
        "narrativa": _narrativa(("Observações", roteiro.observacoes)),
        "inicio": None if cancelado else inicio, "fim": fim, "urgencia": None,
        # O roteiro não guarda data nem motivo do cancelamento; o aviso diz o efeito.
        "cancelamento": {"titulo": "Roteiro cancelado",
                         "motivo": "Não aparece mais para uso nos ofícios."}
        if cancelado else None,
        "pendencias": [], "documentos": None,
        "blocos": [{"percurso": True, "titulo": "Roteiro"},
                   {"titulo": "Ofícios vinculados",
                    "nota": _contagem(len(oficios), "ofício", "ofícios", ""),
                    "cartoes": vinculos,
                    "vazio": "Este roteiro ainda não foi usado em nenhum ofício."}],
        "ler": None, "menu_template": "viagens/roteiros/_menu_linha.html" if pode_editar else "",
        "abrir_url": reverse("viagens:editar_roteiro", args=[roteiro.pk]) if editavel else "",
        "abrir_rotulo": "Abrir o roteiro", "editavel": editavel})


def _periodo_trechos(oficio) -> str:
    trechos = list(oficio.trechos.all())
    return periodo_do_resumo(trechos[0].saida_em, trechos[-1].chegada_em) if trechos else ""


def _destinos_do_roteiro(roteiro, trechos) -> list[str]:
    vistos: list[str] = []
    for t in trechos:
        if t.destino_id != roteiro.sede_id:
            rotulo = f"{t.destino.nome}/{t.destino.uf}"
            if rotulo not in vistos:
                vistos.append(rotulo)
    return vistos


def vinculos_do_oficio(usuario, oficio) -> list[dict]:
    """Termos, OS e planos que nasceram do ofício e que quem olha vê — cartões que levam
    à folha de cada um (o caminho inverso dos "Ofícios vinculados" desses resumos). Uma
    consulta só (UNION): o resumo do ofício tem orçamento de consultas."""
    from django.db.models import BooleanField, Case, CharField, F, IntegerField, Q, Value, When

    from .models import TermoAutorizacao

    def linha(qs, tipo: str, cancelado: Q, gerado: Q, numerado: bool = True,
              sufixo: bool = False):
        def sim(q: Q) -> Case:
            return Case(When(q, then=True), default=False, output_field=BooleanField())
        return qs.order_by().annotate(
            v_tipo=Value(tipo, CharField()),
            v_numero=F("numero") if numerado else Value(0, IntegerField()),
            v_ano=F("ano") if numerado else Value(0, IntegerField()),
            v_sufixo=F("sufixo") if sufixo else Value("", CharField()),
            v_cancelado=sim(cancelado), v_gerado=sim(gerado),
        ).values_list("v_tipo", "pk", "v_numero", "v_ano", "v_sufixo", "v_cancelado",
                      "v_gerado")

    termos = policies.termos_visiveis(usuario).filter(
        Q(oficio=oficio) | Q(pk__in=TermoAutorizacao.objects.filter(
            oficios=oficio).values("pk")))
    linhas = linha(termos, "termo", Q(situacao="cancelado"), Q(pk__isnull=False),
                   numerado=False).union(
        linha(policies.ordens_visiveis(usuario).filter(oficios=oficio), "ordem",
              Q(situacao="cancelada"), Q(documento_gerado_em__isnull=False)),
        linha(policies.planos_visiveis(usuario).filter(oficios=oficio), "plano",
              Q(cancelado=True), Q(documento_gerado_em__isnull=False), sufixo=True),
        all=True).order_by()
    ordem_tipo = {"termo": 0, "ordem": 1, "plano": 2}
    cartoes: list[dict] = []
    for tipo, pk, numero, ano, sufixo, cancelado, gerado in sorted(
            linhas, key=lambda r: (ordem_tipo[r[0]], r[3], r[2], r[1])):
        if tipo == "termo":
            nome, icone, rota = f"Termo #{pk}", "file-signature", "viagens:editar_termo"
            situacao = "Cancelado" if cancelado else "Termo de autorização"
        elif tipo == "ordem":
            nome, icone, rota = f"OS {numero:03d}/{ano}", "clipboard-list", "viagens:editar_ordem"
            situacao = "Cancelada" if cancelado else "Gerada" if gerado else "Rascunho"
        else:
            nome = f"Plano de Trabalho {numero:02d}/{ano}{'/' + sufixo if sufixo else ''}"
            icone, rota = "list-checks", "viagens:editar_plano"
            situacao = "Cancelado" if cancelado else "Gerado" if gerado else "Rascunho"
        cartoes.append({"tipo": tipo, "icone": icone, "escuro": gerado and not cancelado,
                        "nome": nome, "meta": situacao, "url": reverse(rota, args=[pk])})
    return cartoes
