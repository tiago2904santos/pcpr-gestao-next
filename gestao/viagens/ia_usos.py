"""Usos de assistência (IA ou regra) do contexto Viagens, registrados na assistência.

A assistência descobre este módulo no `ready()` dela (`autodiscover_modules("ia_usos")`) e
não importa Viagens. Aqui ficam, por uso: os fatos que podem sair (e só eles), o texto por
regra (a alternativa sem IA), o validador de fatos e a aplicação pelo serviço do contexto,
com trava, revalidação da versão e sem sobrescrever texto escrito por pessoa.

- AUT-50 `viagens.rt_rascunho` — descrição, objetivo e conclusão do relatório técnico;
- AUT-81 `viagens.oficio_textos` — motivo do ofício e justificativa de antecedência;
- AUT-80 `viagens.plano_textos` — contextualização e considerações do plano de trabalho;
- AUT-89 `viagens.explicar_pendencias` — o que falta na viagem, em linguagem simples;
- AUT-76, 57 e 58 em `ia_leituras.py`; a "minha situação" em `situacao_servidor.py`.

O que nunca sai: nomes de pessoas, CPF, RG, telefone, e-mail, placa, valores e diárias,
protocolo, coordenação e assinatura. A IA nunca escolhe equipe, motorista ou viatura, nunca
inventa km, pagamento, atividade ou valor e nunca calcula diária: os esquemas não têm campo
para isso e o validador recusa o texto que fala disso sem o dado.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from gestao.assistencia.dominio import textos as redacao
from gestao.assistencia.ganchos import (
    AplicacaoRecusada,
    Assunto,
    Contexto,
    Fato,
    Item,
    Obsoleta,
    OpcaoPedido,
    RecursoInexistente,
    TextoHumano,
    UsoIA,
    registrar_uso,
)
from gestao.cadastros.models import AtividadePlano, ModeloTexto, Municipio
from gestao.integracoes.ia.protecao import mascarar

from . import diario, planos, policies, relatorio, services
from .dominio import relatorio as dominio_rt
from .dominio.relatorio import frase, listar
from .models import Oficio, PlanoTrabalho, PrestacaoContas, RelatorioTecnico, Viagem
from .viagem import periodo_curto

EXCLUIDOS_COMUNS = ("nomes de servidores e de motoristas", "CPF e RG", "telefone e e-mail",
                    "placa e viatura", "valores, diárias e cálculo", "protocolo",
                    "coordenação e assinatura")


# ------------------------------------------------------------------ apoio
def _livre(texto: str, limite: int = 600) -> str:
    return mascarar(" ".join((texto or "").split())[:limite])


def _destinos_do_oficio(oficio: Oficio, trechos) -> list[str]:
    return list(dict.fromkeys(str(t.destino) for t in trechos if t.destino_id != oficio.sede_id))


def _periodo_dos_trechos(trechos) -> str:
    if not trechos:
        return ""
    return periodo_curto(timezone.localtime(trechos[0].saida_em).date(),
                         timezone.localtime(trechos[-1].chegada_em).date())


def _nomes_da_equipe(oficio: Oficio) -> list[str]:
    nomes = [v.servidor.nome for v in oficio.viajantes.select_related("servidor")]
    if oficio.motorista_externo_servidor is not None:
        nomes.append(oficio.motorista_externo_servidor.nome)
    if oficio.motorista_externo_nome:
        nomes.append(oficio.motorista_externo_nome)
    return nomes


def catalogo() -> list[str]:
    """Entidades que o texto só pode citar se estiverem nos fatos: municípios do PR (nomes
    longos o bastante para não confundir com palavras comuns) e atividades do catálogo."""
    municipios = [n for n in Municipio.objects.filter(uf="PR").values_list("nome", flat=True)
                  if len(n) >= 6]
    return municipios + list(AtividadePlano.objects.values_list("nome", flat=True))


def _fato(chave: str, rotulo: str, valor: str, *, livre: bool = False,
          do_pedido: bool = False) -> Fato | None:
    valor = " ".join(str(valor or "").split())
    return Fato(chave, rotulo, valor, livre, do_pedido) if valor else None


def _fatos(*fatos: Fato | None) -> tuple[Fato, ...]:
    return tuple(f for f in fatos if f is not None)


def _itens_de_textos(dados: dict, ctx: Contexto, rotulos: dict[str, str]) -> list[Item]:
    itens = []
    for t in dados.get("textos", []):
        campo = t.get("campo", "")
        atual = (ctx.textos_atuais.get(campo) or "").strip()
        nota = ("O campo já tem texto: aceitar substitui só com a sua confirmação."
                if atual and not ctx.extras.get(f"{campo}_automatico") else "")
        itens.append(Item(campo, rotulos.get(campo, campo), t.get("texto", ""),
                          tuple(ctx.rotulos(t.get("fontes", []))), True, nota))
    return itens


def _validar_textos(dados: dict, ctx: Contexto, campos: tuple[str, ...]) -> list[str]:
    return redacao.validar_textos(
        dados, fatos_texto=redacao.serializar_fatos(ctx.fatos),
        chaves=[f.chave for f in ctx.fatos], campos_alvo=campos,
        nomes_proibidos=ctx.extras.get("nomes", ()), catalogo=catalogo())


def _humano(atual: str, automatico: bool, substituir: bool, novo: str) -> None:
    if atual.strip() and not automatico and not substituir and atual.strip() != novo.strip():
        raise TextoHumano("O campo já tem texto escrito por uma pessoa. Marque “Substituir o "
                          "texto atual” para trocar.")


def _exemplo(modelo, filtro: dict, permissao: str):
    from gestao.identidade.models import Usuario

    obj = modelo.objects.filter(**filtro).order_by("-pk").first()
    if obj is None:
        return None
    unidade = getattr(obj, "unidade_id", None) or getattr(
        getattr(obj, "oficio", None), "unidade_id", None)
    if unidade is None:
        return None
    usuario = (Usuario.objects.filter(is_active=True, lotacao__unidade_id=unidade,
                                      groups__permissions__codename=permissao)
               .order_by("pk").first())
    return (usuario, str(obj.pk), {}) if usuario else None


# ------------------------------------------------------------------ AUT-50 · RT
CAMPOS_RT = ("motivo", "atividade", "conclusao")
FATOS_RT = ("evento", "descricao_viagem", "motivo_oficio", "destinos", "periodo", "atividades",
            "realizados", "relato")
LACUNAS_RT = {
    "resultados_do_plano": "Lance os resultados no plano de trabalho (quantos atendimentos, "
                           "por atividade) para a conclusão citar números.",
    "plano_de_trabalho": "A viagem não tem plano de trabalho: o objetivo fica genérico.",
    "objetivo_da_viagem": "Escreva a descrição/objetivo da viagem (na folha da viagem).",
    "relato_da_equipe": "Conte em poucas linhas o que aconteceu (campo “Relato da equipe”).",
}


def _prestacao(recurso_id: str) -> PrestacaoContas:
    p = (PrestacaoContas.objects.select_related("oficio__unidade", "oficio__viagem",
                                                "oficio__sede")
         .filter(pk=int(recurso_id) if str(recurso_id).isdigit() else 0).first())
    if p is None:
        raise RecursoInexistente(recurso_id)
    return p


def _contexto_rt(p: PrestacaoContas, opcoes: dict) -> Contexto:
    from . import resultados

    oficio = p.oficio
    trechos = list(oficio.trechos.select_related("destino").order_by("ordem"))
    viagem = oficio.viagem if oficio.viagem_id else None
    plano = relatorio.plano_da_viagem(p)
    atividades, realizados = [], []
    if plano is not None:
        for linha in resultados.linhas(plano):
            atividades.append(linha.atividade.nome)
            if linha.realizado is not None:
                realizados.append(f"{linha.atividade.nome}: {linha.realizado}")
    rt = RelatorioTecnico.objects.filter(prestacao=p).first()
    fatos = _fatos(
        _fato("evento", "Viagem · título", viagem.titulo if viagem else ""),
        _fato("descricao_viagem", "Viagem · descrição/objetivo",
              _livre(viagem.descricao) if viagem else "", livre=True),
        _fato("motivo_oficio", "Ofício · motivo da viagem", _livre(oficio.motivo), livre=True),
        _fato("destinos", "Ofício · destinos dos trechos",
              listar(_destinos_do_oficio(oficio, trechos), maximo=6)),
        _fato("periodo", "Ofício · período dos trechos", _periodo_dos_trechos(trechos)),
        _fato("atividades", "Plano de trabalho · atividades", "; ".join(atividades)),
        _fato("realizados", "Plano de trabalho · resultados lançados", "; ".join(realizados)),
        _fato("relato", "Relato da equipe (escrito no pedido)", opcoes.get("relato", ""),
              livre=True, do_pedido=True))
    lacunas = []
    if plano is None:
        lacunas.append("plano_de_trabalho")
    elif not realizados:
        lacunas.append("resultados_do_plano")
    if not (viagem and viagem.descricao.strip()) and not atividades:
        lacunas.append("objetivo_da_viagem")
    if not opcoes.get("relato"):
        lacunas.append("relato_da_equipe")
    return Contexto(
        recurso_rotulo=f"Relatório técnico · Ofício {oficio.numero_formatado}", fatos=fatos,
        textos_atuais={c: (getattr(rt, c) if rt else "") for c in CAMPOS_RT},
        lacunas=tuple(lacunas), extras={"nomes": _nomes_da_equipe(oficio)})


def _montar_rt(usuario, recurso_id: str, opcoes: dict) -> Contexto:
    p = _prestacao(recurso_id)
    if not policies.pode_ver_equipe_prestacao(usuario, p):
        raise RecursoInexistente(recurso_id)
    return _contexto_rt(p, opcoes)


def _onde_quando(ctx: Contexto) -> tuple[str, list[str]]:
    partes, fontes = [], []
    if ctx.valor("destinos"):
        partes.append(f"em {ctx.valor('destinos')}")
        fontes.append("destinos")
    if ctx.valor("periodo"):
        p = ctx.valor("periodo")
        partes.append(("no período de " if " a " in p else "no dia ") + p)
        fontes.append("periodo")
    return ", ".join(partes), fontes


def _deterministico_rt(ctx: Contexto) -> dict:
    onde, f_onde = _onde_quando(ctx)
    textos = []
    # Descrição do evento: o motivo do ofício (ou o evento), com onde e quando.
    if ctx.valor("motivo_oficio"):
        abertura, fontes = frase(ctx.valor("motivo_oficio")), ["motivo_oficio"]
    elif ctx.valor("evento"):
        abertura, fontes = frase(f"participação no evento “{ctx.valor('evento')}”"), ["evento"]
    else:
        abertura, fontes = "", []
    descricao = " ".join(t for t in (abertura, frase(f"a viagem ocorreu {onde}") if onde else "")
                         if t)
    if descricao:
        textos.append({"campo": "motivo", "texto": descricao, "fontes": fontes + f_onde})
    # Objetivo: a descrição da viagem; sem ela, o evento/destino e as atividades do plano.
    if ctx.valor("descricao_viagem"):
        textos.append({"campo": "atividade", "texto": frase(ctx.valor("descricao_viagem")),
                       "fontes": ["descricao_viagem"]})
    elif ctx.valor("atividades") or ctx.valor("evento"):
        alvo = (f"no evento “{ctx.valor('evento')}”" if ctx.valor("evento")
                else f"em {ctx.valor('destinos')}" if ctx.valor("destinos") else "na ação")
        texto = f"participar {alvo}"
        fontes = ["evento" if ctx.valor("evento") else "destinos"]
        if ctx.valor("atividades"):
            texto += (", com as atividades previstas no plano de trabalho: "
                      + listar(ctx.valor("atividades").split("; ")))
            fontes.append("atividades")
        textos.append({"campo": "atividade", "texto": frase(texto), "fontes": fontes})
    # Conclusão: só o que o sistema registra (resultados lançados); sem eles, não afirma.
    if onde:
        conclusao = [frase(f"a viagem {onde} foi realizada")]
        fontes = list(f_onde)
        if ctx.valor("realizados"):
            conclusao.append(frase("resultados lançados no plano de trabalho: "
                                   + ctx.valor("realizados")))
            fontes.append("realizados")
        textos.append({"campo": "conclusao", "texto": " ".join(conclusao), "fontes": fontes})
    return {"textos": textos, "lacunas": [c for c in ctx.lacunas if c in LACUNAS_RT]}


def _aplicar_rt(usuario, recurso_id: str, textos: dict[str, str], versao: str,
                substituir: bool) -> None:
    # Trava as linhas que compõem a versão (prestação, ofício, viagem e plano) e SÓ ENTÃO
    # relê tudo: a conferência da versão usa os dados de depois das travas, não a cópia lida
    # antes (um ofício ou plano editado no meio não passa com fatos velhos).
    p = _prestacao(recurso_id)
    PrestacaoContas.objects.select_for_update().get(pk=p.pk)
    Oficio.objects.select_for_update().filter(pk=p.oficio_id).first()
    if p.oficio.viagem_id:
        Viagem.objects.select_for_update().filter(pk=p.oficio.viagem_id).first()
    plano = relatorio.plano_da_viagem(p)
    if plano is not None:
        PlanoTrabalho.objects.select_for_update().filter(pk=plano.pk).first()
    p = _prestacao(recurso_id)  # releitura depois das travas
    if _contexto_rt(p, {}).versao != versao:
        raise Obsoleta("O relatório ou os dados da viagem mudaram desde a sugestão.")
    existia = RelatorioTecnico.objects.filter(prestacao=p).first()
    if existia is not None:
        existia = RelatorioTecnico.objects.select_for_update().get(pk=existia.pk)
        for campo, texto in textos.items():
            _humano(getattr(existia, campo, ""), False, substituir, texto)
    try:
        rt = existia or relatorio.obter(p)
        erros = relatorio.salvar(usuario, rt.pk, {c: t for c, t in textos.items()
                                                  if c in CAMPOS_RT})
    except (relatorio.RelatorioInvalido, PermissionDenied) as exc:
        raise AplicacaoRecusada(str(exc)) from exc
    if erros:
        raise AplicacaoRecusada(" ".join(erros.values()))


def _versao_rt(recurso_id: str) -> str:
    return _contexto_rt(_prestacao(recurso_id), {}).versao


registrar_uso(UsoIA(
    chave="viagens.rt_rascunho", codigo="AUT-50", rotulo="Rascunho do relatório técnico",
    descricao="Descrição do evento, objetivo e conclusão do RT a partir da viagem, do ofício, "
              "do plano de trabalho e do relato da equipe.",
    versao_prompt="rt-textos-v1",
    instrucoes=(
        "Redija até três textos do relatório técnico de uma viagem: `motivo` (descrição do "
        "evento: o que foi, onde e quando), `atividade` (objetivo da participação) e "
        "`conclusao` (o que se realizou). A conclusão só cita números de `realizados`; sem "
        "eles, diga apenas que a viagem foi realizada. Não afirme ausência de problemas. "
        "Tom formal e objetivo, até 4 frases por texto."),
    esquema=redacao.esquema_textos(CAMPOS_RT, FATOS_RT, LACUNAS_RT, 1200),
    campos_permitidos=FATOS_RT, dados_excluidos=EXCLUIDOS_COMUNS,
    lacunas_conhecidas=LACUNAS_RT, montar=_montar_rt, deterministico=_deterministico_rt,
    validar=lambda d, c: _validar_textos(d, c, CAMPOS_RT),
    itens=lambda d, c: _itens_de_textos(d, c, dominio_rt.ROTULOS),
    pode_pedir=lambda u, r: diario.pode_editar(u, _prestacao(r)),
    pode_ver=lambda u, r: policies.pode_ver_equipe_prestacao(u, _prestacao(r)),
    descrever=lambda r: Assunto(f"RT · Ofício {_prestacao(r).oficio.numero_formatado}",
                                reverse("viagens:relatorio", args=[int(r)])),
    aplicar=_aplicar_rt, versao_atual=_versao_rt,
    opcoes=(OpcaoPedido("relato", "Relato da equipe (opcional)",
                        "O que aconteceu na viagem, em poucas linhas. Não escreva nomes, CPF "
                        "nem dados de saúde.", 800),),
    acao="Pedir rascunho do relato",
    exemplo_demo=lambda: _exemplo(PrestacaoContas, {"oficio__situacao": "emitido"},
                                  "change_prestacaoservidor"),
))


# ------------------------------------------------------------------ AUT-81 · ofício
CAMPOS_OFICIO = ("motivo", "justificativa")
FATOS_OFICIO = ("evento", "tipos", "descricao_viagem", "destinos", "periodo", "data_oficio",
                "primeira_saida", "antecedencia_dias", "prazo_dias", "situacao_prazo",
                "orientacao")
LACUNAS_OFICIO = {
    "motivo_da_urgencia": "Informe por que o pedido chegou com pouca antecedência (campo "
                          "“Orientação”): convocação de última hora, mudança de agenda…",
    "destinos": "Informe os trechos do ofício (destinos e datas).",
    "evento": "Ligue o ofício a uma viagem com título, para o motivo citar o evento.",
}
ROTULOS_OFICIO = {"motivo": "Motivo da viagem", "justificativa": "Justificativa de prazo"}


def _oficio(recurso_id: str) -> Oficio:
    o = (Oficio.objects.select_related("unidade", "sede", "viagem", "motorista_externo_servidor")
         .filter(pk=int(recurso_id) if str(recurso_id).isdigit() else 0).first())
    if o is None:
        raise RecursoInexistente(recurso_id)
    return o


def _contexto_oficio(o: Oficio, opcoes: dict) -> Contexto:
    trechos = list(o.trechos.select_related("destino").order_by("ordem"))
    prazo = services.avaliar_prazo_do_oficio(o)
    viagem = o.viagem if o.viagem_id else None
    tipos = ", ".join(viagem.tipos.values_list("nome", flat=True)) if viagem else ""
    fatos = _fatos(
        _fato("evento", "Viagem · título", viagem.titulo if viagem else ""),
        _fato("tipos", "Viagem · tipos", tipos),
        _fato("descricao_viagem", "Viagem · descrição/objetivo",
              _livre(viagem.descricao) if viagem else "", livre=True),
        _fato("destinos", "Ofício · destinos dos trechos",
              listar(_destinos_do_oficio(o, trechos), maximo=6)),
        _fato("periodo", "Ofício · período dos trechos", _periodo_dos_trechos(trechos)),
        _fato("data_oficio", "Ofício · data", f"{o.data_oficio:%d/%m/%Y}"),
        _fato("primeira_saida", "Ofício · primeira saída",
              f"{prazo.primeira_saida:%d/%m/%Y}" if prazo.primeira_saida else ""),
        _fato("antecedencia_dias", "Prazo · dias de antecedência",
              "" if prazo.dias_antecedencia is None else str(prazo.dias_antecedencia)),
        _fato("prazo_dias", "Prazo · antecedência exigida (regra do sistema)",
              f"mais de {prazo.prazo_dias} dias"),
        _fato("situacao_prazo", "Prazo · situação", prazo.situacao.value),
        _fato("orientacao", "Orientação de quem pediu", opcoes.get("orientacao", ""),
              livre=True, do_pedido=True))
    padrao = ModeloTexto.objects.filter(tipo=ModeloTexto.Tipo.MOTIVO, ativo=True,
                                        padrao=True).values_list("texto", flat=True).first()
    lacunas = []
    if prazo.justificativa_obrigatoria and not opcoes.get("orientacao"):
        lacunas.append("motivo_da_urgencia")
    if not trechos:
        lacunas.append("destinos")
    if viagem is None or not viagem.titulo:
        lacunas.append("evento")
    return Contexto(
        recurso_rotulo=f"Ofício {o.numero_formatado}", fatos=fatos,
        textos_atuais={"motivo": o.motivo, "justificativa": o.justificativa},
        lacunas=tuple(lacunas),
        extras={"nomes": _nomes_da_equipe(o), "justificativa_obrigatoria":
                prazo.justificativa_obrigatoria,
                "motivo_automatico": bool(padrao) and o.motivo.strip() == (padrao or "").strip()})


def _montar_oficio(usuario, recurso_id: str, opcoes: dict) -> Contexto:
    o = _oficio(recurso_id)
    if not policies.pode_ver(usuario, o):
        raise RecursoInexistente(recurso_id)
    return _contexto_oficio(o, opcoes)


def _deterministico_oficio(ctx: Contexto) -> dict:
    onde, f_onde = _onde_quando(ctx)
    textos = []
    if ctx.valor("evento"):
        motivo = f"participação no evento “{ctx.valor('evento')}”"
        fontes = ["evento"]
    elif ctx.valor("destinos"):
        motivo, fontes = "deslocamento a serviço", []
    else:
        motivo, fontes = "", []
    if motivo:
        texto = frase(f"{motivo}{', ' + onde if onde else ''}")
        if ctx.valor("descricao_viagem"):
            texto += " " + frase(ctx.valor("descricao_viagem"))
            fontes.append("descricao_viagem")
        textos.append({"campo": "motivo", "texto": texto, "fontes": fontes + f_onde})
    if ctx.extras.get("justificativa_obrigatoria") and ctx.valor("primeira_saida"):
        if ctx.valor("situacao_prazo") == "retroativa":
            base = (f"A viagem teve início em {ctx.valor('primeira_saida')}, antes da data do "
                    f"ofício ({ctx.valor('data_oficio')}).")
        else:
            dias = ctx.valor("antecedencia_dias")
            base = (f"A viagem tem saída prevista para {ctx.valor('primeira_saida')}, com "
                    f"{dias} dia{'s' if dias != '1' else ''} de antecedência em relação à data "
                    f"do ofício ({ctx.valor('data_oficio')}), abaixo da antecedência de "
                    f"{ctx.valor('prazo_dias')} adotada pelo sistema.")
        fontes = ["primeira_saida", "data_oficio", "antecedencia_dias", "prazo_dias",
                  "situacao_prazo"]
        if ctx.valor("orientacao"):
            base += " " + frase(ctx.valor("orientacao"))
            fontes.append("orientacao")
        textos.append({"campo": "justificativa", "texto": base,
                       "fontes": [f for f in fontes if ctx.valor(f)]})
    return {"textos": textos, "lacunas": [c for c in ctx.lacunas if c in LACUNAS_OFICIO]}


def _validar_oficio(dados: dict, ctx: Contexto) -> list[str]:
    alvo = CAMPOS_OFICIO if ctx.extras.get("justificativa_obrigatoria") else ("motivo",)
    return _validar_textos(dados, ctx, alvo)


def _aplicar_oficio(usuario, recurso_id: str, textos: dict[str, str], versao: str,
                    substituir: bool) -> None:
    o = _oficio(recurso_id)
    atual = Oficio.objects.select_for_update(of=("self",)).get(pk=o.pk)
    ctx = _contexto_oficio(atual, {})
    if ctx.versao != versao:
        raise Obsoleta("O ofício mudou desde a sugestão.")
    dados = {}
    for campo, texto in textos.items():
        if campo not in CAMPOS_OFICIO:
            continue
        _humano(getattr(atual, campo), bool(ctx.extras.get(f"{campo}_automatico")),
                substituir, texto)
        dados[campo] = texto
    try:
        services.salvar_dados(atual, usuario, dados)
    except (services.RegraViolada, PermissionDenied) as exc:
        raise AplicacaoRecusada(str(exc)) from exc


registrar_uso(UsoIA(
    chave="viagens.oficio_textos", codigo="AUT-81",
    rotulo="Motivo do ofício e justificativa de antecedência",
    descricao="Rascunho do motivo da viagem e, quando a antecedência é insuficiente, da "
              "justificativa — com as datas do próprio ofício.",
    versao_prompt="oficio-textos-v1",
    instrucoes=(
        "Redija o `motivo` do ofício (uma ou duas frases: o que é a viagem, onde e quando) e, "
        "se `situacao_prazo` for fora_do_prazo ou retroativa, a `justificativa` (por que o "
        "pedido saiu com pouca antecedência, citando as datas dos fatos). O motivo da "
        "urgência só vem de `orientacao`; sem ele, aponte a lacuna motivo_da_urgencia. A "
        "antecedência é regra do sistema: não cite decreto."),
    esquema=redacao.esquema_textos(CAMPOS_OFICIO, FATOS_OFICIO, LACUNAS_OFICIO, 1200),
    campos_permitidos=FATOS_OFICIO, dados_excluidos=EXCLUIDOS_COMUNS,
    lacunas_conhecidas=LACUNAS_OFICIO, montar=_montar_oficio,
    deterministico=_deterministico_oficio, validar=_validar_oficio,
    itens=lambda d, c: _itens_de_textos(d, c, ROTULOS_OFICIO),
    pode_pedir=lambda u, r: policies.pode_editar(u, _oficio(r)),
    pode_ver=lambda u, r: policies.pode_ver(u, _oficio(r)),
    descrever=lambda r: Assunto(str(_oficio(r)), reverse("viagens:editar", args=[int(r)])),
    aplicar=_aplicar_oficio,
    versao_atual=lambda r: _contexto_oficio(_oficio(r), {}).versao,
    opcoes=(OpcaoPedido("orientacao", "Orientação (opcional)",
                        "Ex.: por que o pedido chegou tarde. Não escreva nomes nem CPF.", 500),),
    acao="Pedir rascunho do motivo e da justificativa",
    exemplo_demo=lambda: _exemplo(Oficio, {"situacao": "rascunho"}, "change_oficio"),
))


# ------------------------------------------------------------------ AUT-80 · plano
CAMPOS_PLANO = ("contextualizacao", "consideracoes")
FATOS_PLANO = ("evento", "descricao_viagem", "destinos", "programas", "periodo", "atividades",
               "orientacao")
LACUNAS_PLANO = {
    "objetivo_do_evento": "Escreva a descrição/objetivo da viagem para o texto dizer o que o "
                          "evento pretende.",
    "programa": "Escolha o programa solicitante no plano.",
    "atividades": "Marque as atividades do plano.",
    "destinos": "Informe os destinos do plano.",
}
ROTULOS_PLANO = {"contextualizacao": "Breve contextualização",
                 "consideracoes": "Considerações finais"}


def _plano(recurso_id: str) -> PlanoTrabalho:
    p = (PlanoTrabalho.objects.select_related("unidade", "viagem", "programa")
         .filter(pk=int(recurso_id) if str(recurso_id).isdigit() else 0).first())
    if p is None:
        raise RecursoInexistente(recurso_id)
    return p


def _contexto_plano(p: PlanoTrabalho, opcoes: dict) -> Contexto:
    viagem = p.viagem if p.viagem_id else None
    destinos = planos.todos_os_destinos(p)
    programas = planos.todos_os_programas(p)
    atividades = list(p.atividades.values_list("nome", flat=True))
    fatos = _fatos(
        _fato("evento", "Viagem · título", viagem.titulo if viagem else ""),
        _fato("descricao_viagem", "Viagem · descrição/objetivo",
              _livre(viagem.descricao) if viagem else "", livre=True),
        _fato("destinos", "Plano · destinos", listar(destinos, maximo=6)),
        _fato("programas", "Plano · programas solicitantes", listar(programas, maximo=4)),
        _fato("periodo", "Plano · período", periodo_curto(p.data_inicio, p.data_fim)),
        _fato("atividades", "Plano · atividades", "; ".join(atividades)),
        _fato("orientacao", "Orientação de quem pediu", opcoes.get("orientacao", ""),
              livre=True, do_pedido=True))
    lacunas = []
    if not (viagem and viagem.descricao.strip()):
        lacunas.append("objetivo_do_evento")
    if not programas:
        lacunas.append("programa")
    if not atividades:
        lacunas.append("atividades")
    if not destinos:
        lacunas.append("destinos")
    return Contexto(
        recurso_rotulo=f"Plano de trabalho {p}", fatos=fatos,
        textos_atuais={c: getattr(p, c) for c in CAMPOS_PLANO}, lacunas=tuple(lacunas),
        extras={"nomes": [], **{f"{c}_automatico": getattr(p, f"{c}_auto")
                                for c in CAMPOS_PLANO}})


def _montar_plano(usuario, recurso_id: str, opcoes: dict) -> Contexto:
    p = _plano(recurso_id)
    if not policies.pode_ver_plano(usuario, p):
        raise RecursoInexistente(recurso_id)
    return _contexto_plano(p, opcoes)


def _deterministico_plano(ctx: Contexto) -> dict:
    onde, f_onde = _onde_quando(ctx)
    textos = []
    if onde:
        partes = [f"o plano de trabalho organiza a ação {onde}"]
        fontes = list(f_onde)
        if ctx.valor("evento"):
            partes[0] += f", no âmbito de “{ctx.valor('evento')}”"
            fontes.append("evento")
        if ctx.valor("programas"):
            partes.append(f"a ação atende à solicitação de {ctx.valor('programas')}")
            fontes.append("programas")
        if ctx.valor("descricao_viagem"):
            partes.append(ctx.valor("descricao_viagem"))
            fontes.append("descricao_viagem")
        if ctx.valor("atividades"):
            partes.append("estão previstas as atividades: "
                          + listar(ctx.valor("atividades").split("; ")))
            fontes.append("atividades")
        textos.append({"campo": "contextualizacao",
                       "texto": " ".join(frase(x) for x in partes), "fontes": fontes})
        textos.append({"campo": "consideracoes",
                       "texto": frase(f"os resultados da ação {onde} serão registrados no "
                                      "relatório final deste plano de trabalho"),
                       "fontes": f_onde})
    return {"textos": textos, "lacunas": [c for c in ctx.lacunas if c in LACUNAS_PLANO]}


@transaction.atomic
def aplicar_texto_do_plano(usuario, recurso_id: str, textos: dict[str, str], versao: str,
                           substituir: bool) -> None:
    """Grava só os campos de texto (não usa `planos.salvar`, que reescreve tudo): o campo,
    com o interruptor do automático desligado, como quando a pessoa escreve na folha."""
    p = PlanoTrabalho.objects.select_for_update().get(pk=_plano(recurso_id).pk)
    if not policies.pode_editar_plano(usuario, p):
        raise AplicacaoRecusada("Este plano de trabalho não pode ser alterado.")
    ctx = _contexto_plano(p, {})
    if ctx.versao != versao:
        raise Obsoleta("O plano mudou desde a sugestão.")
    campos = []
    for campo, texto in textos.items():
        if campo not in CAMPOS_PLANO:
            continue
        _humano(getattr(p, campo), getattr(p, f"{campo}_auto"), substituir, texto)
        setattr(p, campo, texto.strip())
        setattr(p, f"{campo}_auto", False)
        campos += [campo, f"{campo}_auto"]
    if campos:
        p.save(update_fields=[*campos, "atualizado_em"])


registrar_uso(UsoIA(
    chave="viagens.plano_textos", codigo="AUT-80",
    rotulo="Contextualização e considerações do plano de trabalho",
    descricao="Rascunho dos dois textos livres do plano a partir dos destinos, programas, "
              "período, atividades escolhidas e da descrição da viagem.",
    versao_prompt="plano-textos-v1",
    instrucoes=(
        "Redija a `contextualizacao` (até 3 frases: a ação, onde, quando, quem pediu e as "
        "atividades já escolhidas) e as `consideracoes` (1 ou 2 frases de fechamento) de um "
        "plano de trabalho. Não descreva o público nem a região (rural, ribeirinha, "
        "vulnerável…) se isso não estiver nos fatos. Não prometa resultados."),
    esquema=redacao.esquema_textos(CAMPOS_PLANO, FATOS_PLANO, LACUNAS_PLANO, 1500),
    campos_permitidos=FATOS_PLANO, dados_excluidos=(*EXCLUIDOS_COMUNS, "efetivo"),
    lacunas_conhecidas=LACUNAS_PLANO, montar=_montar_plano,
    deterministico=_deterministico_plano,
    validar=lambda d, c: _validar_textos(d, c, CAMPOS_PLANO),
    itens=lambda d, c: _itens_de_textos(d, c, ROTULOS_PLANO),
    pode_pedir=lambda u, r: policies.pode_editar_plano(u, _plano(r)),
    pode_ver=lambda u, r: policies.pode_ver_plano(u, _plano(r)),
    descrever=lambda r: Assunto(f"Plano de trabalho {_plano(r)}",
                                reverse("viagens:editar_plano", args=[int(r)])),
    aplicar=aplicar_texto_do_plano,
    versao_atual=lambda r: _contexto_plano(_plano(r), {}).versao,
    opcoes=(OpcaoPedido("orientacao", "Orientação (opcional)",
                        "Ex.: destaque para a emissão de documentos. Não escreva nomes.", 500),),
    acao="Pedir rascunho dos textos",
    exemplo_demo=lambda: _exemplo(PlanoTrabalho, {"cancelado": False},
                                  "change_planotrabalho"),
))


# ------------------------------------------------------------------ AUT-89 · pendências
ETAPAS = ("dados", "roteiro", "oficios", "equipe", "ordem", "termos", "assinaturas",
          "protocolo")


def _viagem(recurso_id: str) -> Viagem:
    v = Viagem.objects.filter(pk=int(recurso_id) if str(recurso_id).isdigit() else 0).first()
    if v is None:
        raise RecursoInexistente(recurso_id)
    return v


def _contexto_pendencias(v: Viagem) -> Contexto:
    from .models import Viajante
    from .viagem_conferencia import quadro

    q = quadro(v)
    nomes = list(Viajante.objects.filter(oficio__viagem=v)
                 .values_list("servidor__nome", flat=True).distinct())

    def sem_nomes(texto: str) -> str:
        for nome in sorted(nomes, key=len, reverse=True):
            texto = texto.replace(nome, "[servidor da equipe]")
        return mascarar(texto)

    fatos = _fatos(*(_fato(e.chave, f"Conferência · {e.titulo}",
                           "; ".join(sem_nomes(i.mensagem) for i in e.itens))
                     for e in q.etapas if e.itens))
    titulos = {e.chave: e.titulo for e in q.etapas}
    return Contexto(recurso_rotulo=f"Viagem {v.titulo or v.pk}", fatos=fatos,
                    extras={"nomes": nomes, "titulos": titulos,
                            "links": {e.chave: (e.itens[0].link if e.itens else "")
                                      for e in q.etapas}},
                    lacunas=() if fatos else ("nada_pendente",))


def _montar_pendencias(usuario, recurso_id: str, opcoes: dict) -> Contexto:
    v = _viagem(recurso_id)
    if not policies.pode_ver_viagem(usuario, v):
        raise RecursoInexistente(recurso_id)
    return _contexto_pendencias(v)


def _deterministico_pendencias(ctx: Contexto) -> dict:
    textos = []
    for f in ctx.fatos:
        titulo = ctx.extras["titulos"].get(f.chave, f.chave)
        itens = [x.strip().rstrip(".") for x in f.valor.split("; ") if x.strip()]
        corpo = "; ".join(itens)
        textos.append({"campo": f.chave, "fontes": [f.chave],
                       "texto": f"Em “{titulo}”, falta: {corpo}. Abra a etapa para resolver."})
    return {"textos": textos, "lacunas": list(ctx.lacunas)}


def _itens_pendencias(dados: dict, ctx: Contexto) -> list[Item]:
    links = ctx.extras.get("links", {})
    return [Item(t["campo"], ctx.extras["titulos"].get(t["campo"], t["campo"]), t["texto"],
                 tuple(ctx.rotulos(t.get("fontes", []))), False, links.get(t["campo"], ""))
            for t in dados.get("textos", [])]


registrar_uso(UsoIA(
    chave="viagens.explicar_pendencias", codigo="AUT-89",
    rotulo="O que falta na viagem, em linguagem simples",
    descricao="Reescreve o quadro de prontidão da viagem para quem opera: o que falta em cada "
              "etapa e onde resolver. Só leitura: não grava nada.",
    versao_prompt="pendencias-v1",
    instrucoes=(
        "Para cada etapa com pendências nos fatos, escreva uma explicação curta em linguagem "
        "simples (até 2 frases): o que falta e o que a pessoa faz para resolver. Não "
        "acrescente pendência que não esteja nos fatos."),
    esquema=redacao.esquema_textos(ETAPAS, ETAPAS, ("nada_pendente",), 600),
    campos_permitidos=ETAPAS, dados_excluidos=EXCLUIDOS_COMUNS,
    lacunas_conhecidas={"nada_pendente": "Nada pendente na conferência da viagem."},
    montar=_montar_pendencias, deterministico=_deterministico_pendencias,
    validar=lambda d, c: _validar_textos(d, c, tuple(f.chave for f in c.fatos))
    if c.fatos else [],
    itens=_itens_pendencias,
    pode_pedir=lambda u, r: policies.pode_ver_viagem(u, _viagem(r)),
    pode_ver=lambda u, r: policies.pode_ver_viagem(u, _viagem(r)),
    descrever=lambda r: Assunto(f"Viagem {_viagem(r).titulo or r}",
                                reverse("viagens:editar_viagem", args=[int(r)])),
    versao_atual=lambda r: _contexto_pendencias(_viagem(r)).versao,
    acao="Explicar o que falta",
    exemplo_demo=lambda: _exemplo(Viagem, {}, "view_viagem"),
))


from . import ia_leituras, situacao_servidor  # noqa: E402,F401  (registram os demais usos)
