"""Etapa 5 — coffee break: fornecedores, contratos, termos aditivos, lotes (com os municípios),
a configuração do ofício, certidões, solicitações (as ordens de serviço) e o histórico.

Regras (docs da migração, 04-eventos-coffee; decisões do usuário em 18/10/2026):

* Só o EV tem o coffee break. Contrato, termo, lote e fornecedor casam por chave natural com o
  que já estiver no destino; a configuração do ofício ATUALIZA o registro único.
* G1: o número da OS é por lote (como no legado): "1/2025" pode existir em dois lotes. O zero
  à esquerda sai ("01/2025" → "1/2025", G14), como o formulário faria na primeira edição.
* G2: o município da OS é opcional nos pedidos antigos. Vazio no legado → procura-se, no local
  de entrega, na descrição e no endereço, o nome de um município do PRÓPRIO lote; um só achado
  → preenchido, com nota nas observações. Ambíguo ou nenhum → fica vazio e vai à conferência.
  Nunca se presume a capital.
* G3: o período original (fim diferente do início, texto do período) vai para as observações.
* A OS preserva o id do legado (#170–#344) quando livre; `setval` no fim. O pagamento conjunto
  (`pagamento_com`) entra numa segunda passada; a origem "evento" aponta para a solicitação de
  evento já migrada.
* Nada de dado pessoal no relatório: só ids, contagens, nomes de campos e motivos.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from django.db.models import Q

from gestao.cadastros.validacoes import sem_acentos, somente_digitos
from gestao.coffee import dominio_pedido
from gestao.coffee.models import (
    Certidao,
    ConfiguracaoOficio,
    Contrato,
    Fornecedor,
    Lote,
    Movimento,
    Solicitacao,
    TermoAditivo,
)

from ..contexto import Contexto
from .comum import FUSO, arquivo, fk, preservar_datas, tab, texto, usuario
from .eventos import TE, _criar, _novo, conferir_assinatura, setval

TC = {
    "fornecedor": "coffee_break_fornecedor",
    "contrato": "coffee_break_contratocoffeebreak",
    "aditivo": "coffee_break_aditivocontrato",
    "certidao": "coffee_break_certidaofornecedor",
    "lote": "coffee_break_lotecoffeebreak",
    "lote_municipios": "coffee_break_lotecoffeebreak_municipios",
    "configuracao": "coffee_break_configuracaocoffeebreak",
    "solicitacao": "coffee_break_solicitacaocoffeebreak",
    "historico": "coffee_break_historicocoffeebreak",
}
# Tabelas sem linhas hoje: se aparecerem na virada, vão para a conferência.
VAZIAS = ("coffee_break_linkfornecedor", "coffee_break_enviofornecedor",
          "coffee_break_ocorrenciaentrega")

ACAO = {"CRIACAO": "criada", "ATUALIZACAO": "atualizada", "CANCELAMENTO": "cancelada",
        "REATIVACAO": "reativada", "EMAIL": "email", "FORNECEDOR": "fornecedor"}
TIPO_CERTIDAO = {"FEDERAL": "federal", "ESTADUAL": "estadual", "MUNICIPAL": "municipal",
                 "TRABALHISTA": "trabalhista", "FGTS": "fgts"}
CONFIGURACAO = {"oficio_vocativo": ("vocativo", 150), "oficio_assinante": ("assinante", 150),
                "oficio_cargo_assinante": ("cargo_assinante", 150),
                "oficio_destinatario": ("destinatario", None),
                "eprotocolo_assunto": ("assunto_protocolo", 120),
                "eprotocolo_palavras_chave": ("palavras_chave", 200),
                "despacho_destino": ("destino_despacho", 120),
                "email_copia": ("emails_ascom", 500),
                "email_os_assunto": ("assunto_email_os", 200),
                "email_os_texto": ("texto_email_os", None),
                "email_ob_assunto": ("assunto_email_ob", 200),
                "email_ob_texto": ("texto_email_ob", None)}
NOTA_MUNICIPIO = ("Município preenchido na migração: o nome dele (um dos municípios do lote) "
                  "aparece no local de entrega ou na descrição; o sistema anterior não o "
                  "registrou.")


# ---------------------------------------------------------------------------- regras puras
def normalizar_numero(numero: Any, ano: int) -> str:
    """G14: "01/2025" → "1/2025"; vazio fica vazio; o que não é "N/AAAA" fica como está."""
    bruto = texto(numero)
    try:
        return dominio_pedido.formatar_numero(bruto, ano) if "/" in bruto else bruto
    except ValueError:
        return bruto


def dobrar(t: Any) -> str:
    """Minúsculas, sem acento, espaços simples."""
    return " ".join(sem_acentos(str(t or "")).lower().split())


def municipios_no_texto(textos: list[Any], candidatos: dict[int, str]) -> list[int]:
    """Municípios do lote (id → nome) cujo nome aparece no texto (sem acento nem caixa)."""
    alvo = dobrar(" ".join(str(t or "") for t in textos))
    return sorted(pk for pk, nome in candidatos.items() if dobrar(nome) and dobrar(nome) in alvo)


def periodo_original(inicio: date | None, fim: date | None, texto_periodo: Any) -> str:
    """G3: "Período original: dd/mm/aaaa a dd/mm/aaaa; <texto>" (vazio se nada a guardar)."""
    partes = []
    if fim is not None and fim != inicio:
        partes.append(f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}" if inicio else f"até {fim:%d/%m/%Y}")
    if texto(texto_periodo):
        partes.append(texto(texto_periodo))
    return ("Período original: " + "; ".join(partes)) if partes else ""


def juntar(*partes: str) -> str:
    return "\n\n".join(p for p in (x.strip() for x in partes) if p)


# ---------------------------------------------------------------------------- utilitários
def _casar(ctx: Contexto, entidade: str, tabela: str, pk: Any, existente: Any) -> bool:
    """Casou por chave natural com o que já está no destino: só mapeia."""
    if existente is None:
        return False
    ctx.mapear("ev", tabela, pk, existente, criado=False)
    ctx.relatorio.conta(entidade, "casado_por_chave")
    return True


def _arquivo(ctx: Contexto, relativo: Any, entidade: str, tabela: str, pk: Any) -> str:
    arq = arquivo(ctx, "ev", relativo, entidade=entidade, tabela=tabela, origem_pk=pk)
    if arq is None:
        return ""
    if arq.existe:
        conferir_assinatura(ctx, arq.origem, entidade, tabela, pk)
    return arq.nome


def _ref(ctx: Contexto, chave: str, pk: Any) -> int | None:
    return ctx.destino_int("ev", TC[chave], pk) if pk is not None else None


# ---------------------------------------------------------------------------- cadastros
def _fornecedores(ctx: Contexto) -> None:
    t = TC["fornecedor"]
    ctx.precarregar("ev", t)
    for r in tab(ctx, "ev", t):
        if not _novo(ctx, "fornecedor", t, r["id"]):
            continue
        razao = texto(r.get("razao_social"), 200)
        cnpj = somente_digitos(r.get("cnpj") or "")[:14]
        chave = Q(razao_social__iexact=razao) | (Q(cnpj=cnpj) if cnpj else Q(pk__in=[]))
        if _casar(ctx, "fornecedor", t, r["id"], Fornecedor.objects.filter(chave).first()):
            continue
        _criar(ctx, "fornecedor", t, r["id"], Fornecedor, {
            "razao_social": razao, "nome_curto": texto(r.get("nome_curto"), 60), "cnpj": cnpj,
            "contato": texto(r.get("contato"), 150), "telefone": texto(r.get("telefone"), 30),
            "email": texto(r.get("email"), 254),
            "portal_certidao_municipal": texto(r.get("url_certidao_municipal"), 300)},
            criado_em=r.get("criado_em"), atualizado_em=r.get("atualizado_em"))


def _contratos(ctx: Contexto) -> None:
    rel = ctx.relatorio
    t = TC["contrato"]
    ctx.precarregar("ev", t)
    for r in tab(ctx, "ev", t):
        if texto(r.get("arquivo_termo_aditivo")):
            rel.revisar("contrato", "PDF do termo aditivo no contrato do legado: não migrado "
                        "(cadastre o termo aditivo)", sistema="ev", tabela=t,
                        origem_pk=str(r["id"]))
        if not _novo(ctx, "contrato", t, r["id"]):
            continue
        numero = texto(r.get("numero"), 30)
        if _casar(ctx, "contrato", t, r["id"], Contrato.objects.filter(numero=numero).first()):
            continue
        fornecedor = _ref(ctx, "fornecedor", r.get("fornecedor_id"))
        if fornecedor is None:
            rel.conta("contrato", "sem_fornecedor")
            rel.revisar("contrato", "fornecedor sem correspondente", sistema="ev", tabela=t,
                        origem_pk=str(r["id"]))
            continue
        campos: dict[str, Any] = {
            "fornecedor_id": fornecedor, "numero": numero,
            "numero_gms": texto(r.get("numero_gms"), 30),
            "termo_aditivo": texto(r.get("termo_aditivo"), 30),
            "fiscal": texto(r.get("fiscal_responsavel"), 150),
            "cargo_fiscal": texto(r.get("cargo_fiscal"), 120),
            "clausula_pagamento": texto(r.get("clausula_pagamento"), 120),
            "arquivo": _arquivo(ctx, r.get("arquivo_contrato"), "contrato", t, r["id"]),
            "vigencia_inicio": r.get("vigencia_inicio"), "vigencia_fim": r.get("vigencia_fim"),
            "vigencia_estimada": bool(r.get("vigencia_estimada")),
            "quantidade_contratada": r.get("quantidade_contratada"),
            "valor_unitario": r.get("valor_unitario"), "valor_total": r.get("valor_total"),
            "objeto": r.get("objeto") or "", "observacoes": r.get("observacoes") or ""}
        if r.get("antecedencia_minima_dias") is not None:
            campos["antecedencia_minima_dias"] = r["antecedencia_minima_dias"]
        _criar(ctx, "contrato", t, r["id"], Contrato, campos, criado_em=r.get("criado_em"),
               atualizado_em=r.get("atualizado_em"))


def _aditivos(ctx: Contexto) -> None:
    t = TC["aditivo"]
    ctx.precarregar("ev", t)
    for r in tab(ctx, "ev", t):
        if not _novo(ctx, "termo_aditivo", t, r["id"]):
            continue
        contrato = _ref(ctx, "contrato", r.get("contrato_id"))
        if contrato is None:
            ctx.relatorio.conta("termo_aditivo", "sem_contrato")
            continue
        numero = texto(r.get("numero"), 30)
        if _casar(ctx, "termo_aditivo", t, r["id"], TermoAditivo.objects.filter(
                contrato_id=contrato, numero=numero).first()):
            continue
        _criar(ctx, "termo_aditivo", t, r["id"], TermoAditivo, {
            "contrato_id": contrato, "numero": numero,
            "arquivo": _arquivo(ctx, r.get("arquivo"), "termo_aditivo", t, r["id"]),
            "vigencia_inicio": r.get("vigencia_inicio"), "vigencia_fim": r.get("vigencia_fim")},
            criado_em=r.get("criado_em"), atualizado_em=r.get("criado_em"))


def _lotes(ctx: Contexto) -> None:
    rel = ctx.relatorio
    t = TC["lote"]
    ctx.precarregar("ev", t)
    municipios: dict[int, list[int]] = {}
    for x in tab(ctx, "ev", TC["lote_municipios"]):
        municipios.setdefault(x["lotecoffeebreak_id"], []).append(x["municipio_id"])
    for r in tab(ctx, "ev", t):
        if not _novo(ctx, "lote", t, r["id"]):
            continue
        contrato = _ref(ctx, "contrato", r.get("contrato_id"))
        if contrato is None:
            rel.conta("lote", "sem_contrato")
            continue
        exercicio = texto(r.get("exercicio"), 9)
        if _casar(ctx, "lote", t, r["id"], Lote.objects.filter(
                contrato_id=contrato, numero=r["numero"], exercicio=exercicio).first()):
            continue
        notas: list[str] = []
        ids = sorted({m for m in (fk(ctx, "ev", "municipio", pk, notas, "municipios")
                                  for pk in municipios.get(r["id"], [])) if m})
        obj = _criar(ctx, "lote", t, r["id"], Lote, {
            "contrato_id": contrato, "numero": r["numero"], "exercicio": exercicio,
            "quantidade_total": r["quantidade_total"], "empenho": texto(r.get("empenho"), 60),
            "valor_empenho": r.get("valor_empenho"),
            "municipios_texto": r.get("municipios_texto") or "",
            "orientacoes": r.get("orientacoes") or "",
            "especificacoes": r.get("especificacoes_tecnicas") or "",
            "observacoes": r.get("observacoes") or "", "ativo": bool(r.get("ativo"))},
            criado_em=r.get("criado_em"), atualizado_em=r.get("atualizado_em"))
        if isinstance(obj, Lote) and ids:
            obj.municipios.add(*ids)
            rel.conta("lote_municipio", "criado", len(ids))
        for nota in notas:
            rel.revisar("lote", nota, sistema="ev", tabela=t, origem_pk=str(r["id"]))


def _configuracao(ctx: Contexto) -> None:
    """O registro único: atualiza (nunca um segundo)."""
    t = TC["configuracao"]
    for r in tab(ctx, "ev", t):
        if not _novo(ctx, "configuracao_oficio", t, r["id"]):
            continue
        conf = ConfiguracaoOficio.atual()
        valores = {campo: (texto(r.get(origem), limite) if limite else (r.get(origem) or ""))
                   for origem, (campo, limite) in CONFIGURACAO.items()}
        ConfiguracaoOficio.objects.filter(pk=conf.pk).update(**valores)
        preservar_datas(ConfiguracaoOficio, conf.pk, atualizado_em=r.get("atualizado_em"))
        ctx.mapear("ev", t, r["id"], conf, criado=False)
        ctx.relatorio.conta("configuracao_oficio", "atualizada")


def _certidoes(ctx: Contexto) -> None:
    rel = ctx.relatorio
    t = TC["certidao"]
    ctx.precarregar("ev", t)
    for r in tab(ctx, "ev", t):
        if not _novo(ctx, "certidao", t, r["id"]):
            continue
        fornecedor = _ref(ctx, "fornecedor", r.get("fornecedor_id"))
        tipo = TIPO_CERTIDAO.get(texto(r.get("tipo")).upper())
        if fornecedor is None or tipo is None:
            rel.conta("certidao", "sem_fornecedor_ou_tipo")
            rel.revisar("certidao", "fornecedor sem correspondente ou tipo desconhecido",
                        sistema="ev", tabela=t, origem_pk=str(r["id"]))
            continue
        _criar(ctx, "certidao", t, r["id"], Certidao, {
            "fornecedor_id": fornecedor, "tipo": tipo, "validade": r["validade"],
            "arquivo": _arquivo(ctx, r.get("arquivo"), "certidao", t, r["id"]),
            "enviada_por_id": usuario(ctx, "ev", r.get("enviada_por_id"))},
            criada_em=r.get("criado_em"))


# ---------------------------------------------------------------------------- solicitações
def _candidatos_do_lote(ctx: Contexto, lote_id: int) -> dict[int, str]:
    chave = ("coffee_municipios_do_lote", lote_id)
    if chave not in ctx.memo:
        lote = Lote.objects.get(pk=lote_id)
        ctx.memo[chave] = dict(lote.municipios.values_list("pk", "nome"))
    return ctx.memo[chave]


def _municipio(ctx: Contexto, r: dict, lote_id: int,
               notas: list[str]) -> tuple[int | None, str]:
    """(município, nota para as observações)."""
    rel, t = ctx.relatorio, TC["solicitacao"]
    if r.get("municipio_id") is not None:
        return fk(ctx, "ev", "municipio", r["municipio_id"], notas, "municipio"), ""
    achados = municipios_no_texto([r.get("local_entrega"), r.get("descricao_evento"),
                                   r.get("endereco")], _candidatos_do_lote(ctx, lote_id))
    if len(achados) == 1:
        rel.conta("solicitacao_coffee", "municipio_pelo_texto")
        return achados[0], NOTA_MUNICIPIO
    if achados:
        rel.conta("solicitacao_coffee", "municipio_ambiguo")
        rel.revisar("solicitacao_coffee", f"sem município no legado; {len(achados)} municípios "
                    "do lote aparecem no texto: ficou sem município", sistema="ev", tabela=t,
                    origem_pk=str(r["id"]))
    else:
        rel.conta("solicitacao_coffee", "municipio_nao_informado")
        rel.revisar("solicitacao_coffee", "sem município no legado e nenhum município do lote "
                    "no texto: ficou sem município", sistema="ev", tabela=t,
                    origem_pk=str(r["id"]))
    return None, ""


def _origem(ctx: Contexto, r: dict, notas: list[str]) -> tuple[str, int | None]:
    if r.get("solicitacao_evento_id") is not None:
        alvo = ctx.destino_int("ev", TE["solicitacao"], r["solicitacao_evento_id"])
        if alvo is None:
            notas.append("origem: solicitação de evento sem correspondente")
            return "", None
        return "evento", alvo
    if r.get("demanda_evento_id") is not None:
        notas.append("origem: demanda de palestra do legado não migrada")
    return "", None


def _campos_os(ctx: Contexto, r: dict, lote_id: int, notas: list[str]) -> dict[str, Any]:
    rel = ctx.relatorio
    municipio, nota_municipio = _municipio(ctx, r, lote_id, notas)
    ano = r["data_solicitacao"].year
    numero = normalizar_numero(r.get("numero"), ano)
    if numero != texto(r.get("numero")):
        rel.conta("solicitacao_coffee", "numero_sem_zero_a_esquerda")
    periodo = periodo_original(r.get("data_inicio_evento"), r.get("data_fim_evento"),
                               r.get("periodo_evento_texto"))
    if periodo:
        rel.conta("solicitacao_coffee", "periodo_original_nas_observacoes")
    origem_tipo, origem_id = _origem(ctx, r, notas)
    envio_os = r.get("data_envio_ordem_servico")
    return {
        "lote_id": lote_id, "municipio_id": municipio,
        "data_solicitacao": r["data_solicitacao"], "numero": numero,
        "descricao": r.get("descricao_evento") or "", "quantidade": r["quantidade"],
        "data_evento": r.get("data_inicio_evento"), "horario": r.get("horario_evento"),
        "local_entrega": texto(r.get("local_entrega"), 255),
        "endereco": texto(r.get("endereco"), 255), "bairro": texto(r.get("bairro"), 120),
        "cep": texto(r.get("cep"), 9),
        "responsavel": texto(r.get("responsavel_recebimento"), 200),
        "valor_unitario": r.get("valor_unitario"),
        "quantidade_faturada": r.get("quantidade_faturada"),
        "nota_fiscal": texto(r.get("numero_nota_fiscal"), 60),
        "nota_pdf": _arquivo(ctx, r.get("arquivo_nota_fiscal"), "solicitacao_coffee",
                             TC["solicitacao"], r["id"]),
        "nota_valor": r.get("valor_nota_fiscal"), "nota_emissao": r.get("data_emissao_nf"),
        "nota_cnpj": somente_digitos(r.get("cnpj_emitente_nf") or "")[:14],
        "protocolo_pagamento": texto(r.get("protocolo_pagamento"), 20),
        "numero_oficio": texto(r.get("numero_oficio"), 20), "data_oficio": r.get("data_oficio"),
        "protocolo_pcpr": texto(r.get("protocolo_pcpr_oficio"), 30),
        "atesto_em": r.get("data_atesto_gaf"),
        "ordem_bancaria_em": r.get("data_ordem_bancaria"),
        "envio_empresa_em": r.get("data_envio_empresa"),
        "ob_pdf": _arquivo(ctx, r.get("arquivo_ordem_bancaria"), "solicitacao_coffee",
                           TC["solicitacao"], r["id"]),
        "ob_numero": texto(r.get("numero_ordem_bancaria"), 30),
        "ob_valor": r.get("valor_ordem_bancaria"),
        "os_enviada_em": (datetime.combine(envio_os, time(12, 0), tzinfo=FUSO)
                          if envio_os else None),
        "observacoes": juntar(r.get("observacoes") or "", periodo, nota_municipio),
        "em_correcao": bool(r.get("em_correcao")), "cancelada": bool(r.get("cancelada")),
        "cancelada_em": r.get("cancelada_em"),
        "cancelada_por_id": (usuario(ctx, "ev", r["cancelada_por_id"])
                             if r.get("cancelada_por_id") is not None else None),
        "motivo_cancelamento": texto(r.get("motivo_cancelamento"), 255),
        "criado_por_id": usuario(ctx, "ev", r.get("criado_por_id")),
        "origem_tipo": origem_tipo, "origem_id": origem_id, "email_impressao": "",
    }


def _solicitacoes(ctx: Contexto) -> None:
    rel = ctx.relatorio
    t = TC["solicitacao"]
    ctx.precarregar("ev", t)
    preservados = 0
    linhas = tab(ctx, "ev", t)
    for r in linhas:
        if not _novo(ctx, "solicitacao_coffee", t, r["id"]):
            continue
        lote = _ref(ctx, "lote", r.get("lote_id"))
        if lote is None:
            rel.conta("solicitacao_coffee", "sem_lote")
            rel.revisar("solicitacao_coffee", "lote sem correspondente", sistema="ev", tabela=t,
                        origem_pk=str(r["id"]))
            continue
        notas: list[str] = []
        campos = _campos_os(ctx, r, lote, notas)
        if Solicitacao.objects.filter(pk=r["id"]).exists():
            rel.conta("solicitacao_coffee", "id_do_legado_ocupado")
            rel.revisar("solicitacao_coffee", "id do legado já ocupado no destino: entrou com "
                        "id novo", sistema="ev", tabela=t, origem_pk=str(r["id"]))
        else:
            campos["id"] = r["id"]
            preservados += 1
        obj = _criar(ctx, "solicitacao_coffee", t, r["id"], Solicitacao, campos,
                     criado_em=r.get("criado_em"), atualizado_em=r.get("atualizado_em"))
        for nota in notas:
            rel.revisar("solicitacao_coffee", nota, sistema="ev", tabela=t,
                        origem_pk=str(r["id"]), destino_pk=getattr(obj, "pk", None))
    rel.conta("solicitacao_coffee", "id_preservado", preservados)
    setval(Solicitacao)
    # Segunda passada: pagamento conjunto (aponta para a principal, que pode vir depois).
    for r in linhas:
        if r.get("pagamento_com_id") is None:
            continue
        pk = _ref(ctx, "solicitacao", r["id"])
        alvo = _ref(ctx, "solicitacao", r["pagamento_com_id"])
        if pk is None or alvo is None:
            rel.revisar("solicitacao_coffee", "pagamento conjunto sem correspondente",
                        sistema="ev", tabela=t, origem_pk=str(r["id"]))
            continue
        if Solicitacao.objects.filter(pk=pk).exclude(pagamento_com_id=alvo).update(
                pagamento_com_id=alvo):
            rel.conta("solicitacao_coffee", "pagamento_conjunto_ligado")


def _movimentos(ctx: Contexto) -> None:
    rel = ctx.relatorio
    t = TC["historico"]
    ctx.precarregar("ev", t)
    for r in tab(ctx, "ev", t):
        if not _novo(ctx, "movimento_coffee", t, r["id"]):
            continue
        sol = _ref(ctx, "solicitacao", r.get("solicitacao_id"))
        acao = ACAO.get(texto(r.get("acao")).upper())
        if sol is None or acao is None:
            rel.conta("movimento_coffee", "sem_pai_ou_acao")
            rel.revisar("movimento_coffee", "solicitação sem correspondente ou ação "
                        "desconhecida", sistema="ev", tabela=t, origem_pk=str(r["id"]))
            continue
        _criar(ctx, "movimento_coffee", t, r["id"], Movimento, {
            "solicitacao_id": sol, "acao": acao, "texto": r.get("descricao") or "",
            "usuario_id": (usuario(ctx, "ev", r["usuario_id"])
                           if r.get("usuario_id") is not None else None)},
            em=r.get("criado_em"))


def _vazias(ctx: Contexto) -> None:
    for nome in VAZIAS:
        n = len(tab(ctx, "ev", nome))
        if n:
            ctx.relatorio.conta("nao_migrado", nome, n)
            ctx.relatorio.revisar("coffee", "o legado tem linhas que esta etapa não traz",
                                  sistema="ev", tabela=nome, linhas=n)
    if ctx.ev.tem_tabela("documentos_documentoartefato"):
        n = sum(1 for a in tab(ctx, "ev", "documentos_documentoartefato")
                if a.get("coffee_break_solicitacao_id") is not None)
        if n:
            ctx.relatorio.conta("nao_migrado", "documentos_do_coffee", n)
            ctx.relatorio.revisar("coffee", "documentos emitidos do coffee no legado não "
                                  "migrados", sistema="ev",
                                  tabela="documentos_documentoartefato", linhas=n)


# ---------------------------------------------------------------------------- etapa
def executar(ctx: Contexto) -> None:
    _fornecedores(ctx)
    _contratos(ctx)
    _aditivos(ctx)
    _lotes(ctx)
    _configuracao(ctx)
    _certidoes(ctx)
    _solicitacoes(ctx)
    _movimentos(ctx)
    _vazias(ctx)
