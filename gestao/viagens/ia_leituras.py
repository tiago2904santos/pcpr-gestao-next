"""Usos de LEITURA de Viagens (proposta para conferência; nada é gravado no registro):

- AUT-76 `viagens.leitura_programacao` — programação em texto livre → destinos, datas e
  horários. O sistema confere o município no cadastro (IBGE) e exige que cada data, horário e
  município estejam no texto; a IA nunca estima distância (o esquema não tem esse campo) nem
  define diária;
- AUT-57 `viagens.importacao_tipo` — tipo e destino de uma parte importada, só na revisão;
- AUT-58 `viagens.leitura_comprovante` — número, data e valor de comprovante/NFS-e.

57 e 58 leem texto de DOCUMENTO: pela ADR 0041 não vão a provedor externo de IA
(`envolve_documento=True`; o adaptador real recusa). Funcionam com a regra local, o simulado
e o gravado; ligar um provedor real para eles exige uma ADR nova.
"""

from __future__ import annotations

import re

from django.urls import reverse

from gestao.assistencia.dominio import leitura
from gestao.assistencia.dominio.validacao import normalizar
from gestao.assistencia.ganchos import (
    Assunto,
    Contexto,
    Item,
    OpcaoPedido,
    RecursoInexistente,
    UsoIA,
    registrar_uso,
)
from gestao.cadastros.models import Municipio
from gestao.integracoes.ia.protecao import mascarar

from . import importacao, leitura_anexos, policies
from .dominio.importacao import TIPOS, Parte, identificar, tipo_do_texto
from .ia_usos import EXCLUIDOS_COMUNS, _exemplo, _fato, _fatos, _oficio
from .models import AnexoPrestacao, Oficio, ParteImportada

# ------------------------------------------------------------------ AUT-76 · programação
LACUNAS_PROGRAMACAO = {
    "sem_data": "O texto não traz datas: informe o dia de cada destino.",
    "sem_horario": "O texto não traz horários de saída.",
    "sem_municipio": "Nenhum município reconhecido: escreva o nome da cidade (ex.: "
                     "Maringá/PR).",
}
ESQUEMA_PROGRAMACAO = {
    "type": "object", "additionalProperties": False, "required": ["paradas", "lacunas"],
    "properties": {
        "paradas": {"type": "array", "maxItems": 12, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["municipio", "uf", "data", "hora", "trecho"],
            "properties": {
                "municipio": {"type": "string", "maxLength": 80},
                "uf": {"type": "string", "maxLength": 2},
                "data": {"type": "string", "maxLength": 10},
                "hora": {"type": "string", "maxLength": 5},
                "trecho": {"type": "string", "maxLength": 200},
            }}},
        "lacunas": {"type": "array", "maxItems": 3,
                    "items": {"type": "string", "enum": list(LACUNAS_PROGRAMACAO)}},
    },
}


def _indice_municipios() -> dict[str, list[tuple[str, str]]]:
    indice: dict[str, list[tuple[str, str]]] = {}
    for nome, uf in Municipio.objects.values_list("nome", "uf"):
        indice.setdefault(normalizar(nome), []).append((nome, uf))
    return indice


def municipio_do_cadastro(nome: str, uf: str = "") -> tuple[str, str] | None:
    candidatos = list(Municipio.objects.filter(nome__unaccent__iexact=nome.strip())
                      .values_list("nome", "uf"))
    if uf:
        candidatos = [c for c in candidatos if c[1] == uf.upper()] or []
    if not candidatos:
        return None
    return next((c for c in candidatos if c[1] == "PR"), candidatos[0])


def _municipios_na_linha(linha: str, indice) -> list[tuple[str, str]]:
    palavras = re.findall(r"[\wÀ-ÿ']+", linha)
    achados: list[tuple[str, str]] = []
    i = 0
    while i < len(palavras):
        feito = False
        for n in range(min(5, len(palavras) - i), 0, -1):
            pedaco = palavras[i:i + n]
            if not pedaco[0][:1].isupper():
                break  # nome de município começa com maiúscula no texto
            chave = normalizar(" ".join(pedaco))
            if chave in indice and (n > 1 or len(chave) >= 5):
                opcoes = indice[chave]
                resto = linha[linha.find(pedaco[-1]) + len(pedaco[-1]):][:6]
                uf = re.match(r"\s*[/-]\s*([A-Z]{2})\b", resto)
                escolha = next((o for o in opcoes if uf and o[1] == uf.group(1)), None) \
                    or next((o for o in opcoes if o[1] == "PR"), opcoes[0])
                achados.append(escolha)
                i += n
                feito = True
                break
        if not feito:
            i += 1
    return achados


def ler_programacao(texto: str, ano_base: int, sede: str = "") -> list[dict]:
    """A leitura por regra (a alternativa sem IA): por linha, os municípios citados, com a
    data e o horário da linha (ou a última data vista)."""
    indice = _indice_municipios()
    paradas: list[dict] = []
    ultima_data = ""
    for numero, linha in enumerate((texto or "").splitlines()):
        datas = [a.valor for a in leitura.datas(linha, ano_base)]
        horas = [a.valor for a in leitura.horas(linha)]
        if datas:
            ultima_data = datas[0]
        for nome, uf in _municipios_na_linha(linha, indice):
            if normalizar(nome) == normalizar(sede.split("/")[0]):
                continue
            paradas.append({"municipio": nome, "uf": uf, "data": datas[0] if datas else
                            ultima_data, "hora": horas[0] if horas else "",
                            "trecho": " ".join(linha.split())[:200]})
        del numero
    return paradas[:12]


def _contexto_programacao(o: Oficio, opcoes: dict) -> Contexto:
    texto = mascarar(opcoes.get("texto", ""))
    fatos = _fatos(
        _fato("sede", "Ofício · cidade sede", str(o.sede)),
        _fato("ano", "Ofício · ano", str(o.data_oficio.year)),
        _fato("texto", "Programação (texto colado no pedido)", texto, livre=True,
              do_pedido=True))
    return Contexto(recurso_rotulo=f"{o} · programação", fatos=fatos,
                    extras={"texto": texto, "ano": o.data_oficio.year, "sede": str(o.sede)})


def _montar_programacao(usuario, recurso_id: str, opcoes: dict) -> Contexto:
    o = _oficio(recurso_id)
    if not policies.pode_ver(usuario, o):
        raise RecursoInexistente(recurso_id)
    return _contexto_programacao(o, opcoes)


def _deterministico_programacao(ctx: Contexto) -> dict:
    # O texto com as quebras de linha (o fato, que vai ao modelo, tem espaços normalizados).
    texto = ctx.extras["texto"]
    paradas = ler_programacao(texto, ctx.extras["ano"], ctx.extras.get("sede", ""))
    lacunas = []
    if not paradas:
        lacunas.append("sem_municipio")
    if paradas and not any(p["data"] for p in paradas):
        lacunas.append("sem_data")
    if paradas and not any(p["hora"] for p in paradas):
        lacunas.append("sem_horario")
    return {"paradas": paradas, "lacunas": lacunas}


def _validar_programacao(dados: dict, ctx: Contexto) -> list[str]:
    texto = ctx.extras["texto"]
    erros = []
    for i, p in enumerate(dados.get("paradas", []), 1):
        if not leitura.termo_no_texto(p.get("municipio", ""), texto):
            erros.append(f"parada_{i}:municipio_fora_do_texto")
        if p.get("data") and not leitura.data_no_texto(p["data"], texto):
            erros.append(f"parada_{i}:data_fora_do_texto")
        if p.get("hora") and not leitura.hora_no_texto(p["hora"], texto):
            erros.append(f"parada_{i}:hora_fora_do_texto")
        if p.get("trecho") and not leitura.trecho_no_texto(p["trecho"], texto):
            erros.append(f"parada_{i}:trecho_fora_do_texto")
    return erros


def _itens_programacao(dados: dict, ctx: Contexto) -> list[Item]:
    itens = []
    for i, p in enumerate(dados.get("paradas", []), 1):
        cadastro = municipio_do_cadastro(p.get("municipio", ""), p.get("uf", ""))
        nome = f"{cadastro[0]}/{cadastro[1]}" if cadastro else p.get("municipio", "")
        partes = [nome]
        if p.get("data"):
            ano, mes, dia = p["data"].split("-")
            partes.append(f"{dia}/{mes}/{ano}")
        if p.get("hora"):
            partes.append(p["hora"])
        nota = ("Município conferido no cadastro (IBGE)." if cadastro
                else "Município não encontrado no cadastro: confira o nome.")
        itens.append(Item(f"parada_{i}", f"Parada {i}", " · ".join(partes),
                          ("Programação (texto colado no pedido)",), False, nota))
    return itens


registrar_uso(UsoIA(
    chave="viagens.leitura_programacao", codigo="AUT-76",
    rotulo="Leitura da programação (destinos, datas e horários)",
    descricao="Transforma a programação em texto livre numa proposta de destinos, datas e "
              "horários para conferir antes de montar o roteiro. Nada é gravado; distância e "
              "diárias continuam com o sistema.",
    versao_prompt="programacao-v1",
    instrucoes=(
        "Do bloco `texto`, liste as paradas na ordem: município, UF (se escrita), data "
        "(AAAA-MM-DD, só se o dia e o mês estiverem no texto; use o ano do bloco `ano` "
        "quando faltar), hora de saída (HH:MM, só se estiver no texto) e o trecho do texto "
        "de onde tirou. Não inclua a cidade sede. Não estime distância, tempo ou diária."),
    esquema=ESQUEMA_PROGRAMACAO, campos_permitidos=("sede", "ano", "texto"),
    dados_excluidos=EXCLUIDOS_COMUNS, lacunas_conhecidas=LACUNAS_PROGRAMACAO,
    montar=_montar_programacao, deterministico=_deterministico_programacao,
    validar=_validar_programacao, itens=_itens_programacao,
    pode_pedir=lambda u, r: policies.pode_ver(u, _oficio(r)) and policies.edita_oficios(u),
    pode_ver=lambda u, r: policies.pode_ver(u, _oficio(r)),
    # O texto colado é do pedido e não muda; a fonte do REGISTRO é a sede e o ano do ofício
    # (de onde vêm o "não incluir a sede" e o ano das datas sem ano).
    versao_atual=lambda r: _contexto_programacao(_oficio(r), {}).versao,
    descrever=lambda r: Assunto(f"{_oficio(r)} · programação",
                                reverse("viagens:editar", args=[int(r)])),
    opcoes=(OpcaoPedido("texto", "Programação em texto livre",
                        "Cole o trecho do pedido ou do e-mail com cidades, datas e horários. "
                        "Não cole dados pessoais.", 4000, obrigatorio=True),),
    acao="Ler a programação",
    exemplo_demo=lambda: _com_texto(_exemplo(Oficio, {"situacao": "rascunho"},
                                             "change_oficio")),
))


def _com_texto(exemplo):
    if exemplo is None:
        return None
    usuario, recurso, _ = exemplo
    return usuario, recurso, {"texto": "Programação do evento (fictícia):\n"
                                       "21/11 saída às 07:30 para Maringá/PR\n"
                                       "22/11 às 14h atendimento em Sarandi\n"
                                       "Retorno no dia 23/11."}


# ------------------------------------------------------------------ AUT-57 · importação
LACUNAS_IMPORTACAO = {"sem_texto": "A parte não tem texto (imagem ou digitalização): "
                                   "escolha o tipo e o destino na revisão."}
MAX_CANDIDATOS = 20


def _parte(recurso_id: str) -> ParteImportada:
    p = (ParteImportada.objects.select_related("importacao")
         .filter(pk=int(recurso_id) if str(recurso_id).isdigit() else 0).first())
    if p is None:
        raise RecursoInexistente(recurso_id)
    return p


def _texto_do_arquivo(arquivo, nome: str) -> str:
    try:
        with arquivo.open("rb") as f:
            dados = f.read(10 * 1024 * 1024)
    except (OSError, ValueError):
        return ""
    return leitura_anexos.extrair_texto(dados, nome)[:6000]


def _contexto_importacao(parte: ParteImportada, usuario) -> Contexto:
    bruto = _texto_do_arquivo(parte.arquivo, parte.arquivo.name or "")
    destinos = importacao.destinos_do_usuario(usuario)
    palpite = tipo_do_texto(bruto)
    texto_norm = re.sub(r"\s+", "", bruto)

    def citado(d) -> bool:
        return bool((d.numero and f"{d.numero}/{d.ano}" in texto_norm)
                    or (d.protocolo and d.protocolo in texto_norm))

    # Os citados no texto (número/ano ou protocolo) primeiro; no máximo MAX_CANDIDATOS.
    candidatos = sorted((d for d in destinos if not palpite or d.tipo == palpite),
                        key=lambda d: not citado(d))[:MAX_CANDIDATOS]
    linhas = [f"{d.chave} | {TIPOS.get(d.tipo, d.tipo)} | "
              f"{d.numero or '-'}/{d.ano or '-'}" for d in candidatos]
    fatos = _fatos(
        _fato("texto", "Parte importada · texto extraído (mascarado)", mascarar(bruto),
              livre=True),
        _fato("candidatos", "Destinos que você pode usar (chave | tipo | número/ano)",
              "\n".join(linhas)))
    return Contexto(recurso_rotulo=f"Importação · páginas {parte.inicio}–{parte.fim}",
                    fatos=fatos, contem_documento=True,
                    # A revisão da parte (tipo, destino, estado) também é fonte: aplicada ou
                    # corrigida pela pessoa, a sugestão fica obsoleta.
                    textos_atuais={"estado": parte.estado, "tipo": parte.tipo,
                                   "destino": parte.destino},
                    lacunas=() if bruto.strip() else ("sem_texto",),
                    extras={"bruto": bruto, "destinos": destinos,
                            "chaves": [d.chave for d in candidatos],
                            "parte": (parte.inicio, parte.fim)})


def _pode_importacao(usuario, recurso_id: str) -> bool:
    parte = _parte(recurso_id)
    return (policies.edita_oficios(usuario) and parte.importacao.usuario_id == usuario.pk)


def _versao_importacao(recurso_id: str) -> str:
    parte = _parte(recurso_id)
    return _contexto_importacao(parte, parte.importacao.usuario).versao


def _montar_importacao(usuario, recurso_id: str, opcoes: dict) -> Contexto:
    if not _pode_importacao(usuario, recurso_id):
        raise RecursoInexistente(recurso_id)
    return _contexto_importacao(_parte(recurso_id), usuario)


def _deterministico_importacao(ctx: Contexto) -> dict:
    bruto = ctx.extras["bruto"]
    tipo = tipo_do_texto(bruto)
    inicio, fim = ctx.extras["parte"]
    decisao = identificar(Parte(inicio, fim, tipo, bruto), ctx.extras["destinos"])
    destino = decisao.chave if decisao.chave in ctx.extras["chaves"] else ""
    return {"tipo": tipo, "destino": destino, "evidencias": [], "lacunas": list(ctx.lacunas)}


ESQUEMA_IMPORTACAO = {
    "type": "object", "additionalProperties": False,
    "required": ["tipo", "destino", "evidencias", "lacunas"],
    "properties": {
        "tipo": {"type": "string", "enum": ["", *TIPOS]},
        "destino": {"type": "string", "maxLength": 120},
        "evidencias": {"type": "array", "maxItems": 3,
                       "items": {"type": "string", "maxLength": 160}},
        "lacunas": {"type": "array", "maxItems": 1,
                    "items": {"type": "string", "enum": list(LACUNAS_IMPORTACAO)}},
    },
}


def _validar_importacao(dados: dict, ctx: Contexto) -> list[str]:
    erros = []
    destino = dados.get("destino", "")
    if destino and destino not in ctx.extras["chaves"]:
        erros.append("destino_fora_da_lista")
    tipos = {d.chave: d.tipo for d in ctx.extras["destinos"]}
    if destino and tipos.get(destino) != dados.get("tipo"):
        erros.append("destino_de_outro_tipo")
    texto = ctx.valor("texto")
    erros.extend("evidencia_fora_do_texto" for e in dados.get("evidencias", [])
                 if not leitura.trecho_no_texto(e, texto))
    return erros


def _itens_importacao(dados: dict, ctx: Contexto) -> list[Item]:
    rotulos = {d.chave: d.rotulo for d in ctx.extras["destinos"]}
    fontes = ("Parte importada · texto extraído (mascarado)",)
    itens = [Item("tipo", "Tipo do documento",
                  TIPOS.get(dados.get("tipo", ""), "Não reconhecido"), fontes, False,
                  "Escolha o tipo na revisão da importação.")]
    if dados.get("destino"):
        itens.append(Item("destino", "Destino sugerido", rotulos.get(dados["destino"],
                                                                      dados["destino"]),
                          (*fontes, "Destinos que você pode usar"), False,
                          "Aplique na revisão da importação: a sugestão não anexa nada."))
    for i, e in enumerate(dados.get("evidencias", []), 1):
        itens.append(Item(f"evidencia_{i}", f"Evidência {i}", e, fontes, False))
    return itens


registrar_uso(UsoIA(
    chave="viagens.importacao_tipo", codigo="AUT-57",
    rotulo="Tipo e destino na revisão da importação",
    descricao="Sugere o tipo e o destino de uma parte importada que o classificador local "
              "não resolveu. Só sugestão: quem aplica é a pessoa, na revisão.",
    versao_prompt="importacao-v1",
    instrucoes=(
        "Diga o `tipo` do documento do bloco `texto` (lista fechada) e, se houver um único "
        "destino compatível em `candidatos`, a chave dele em `destino`; senão, deixe vazio. "
        "Em `evidencias`, até 3 trechos copiados do texto que justificam."),
    esquema=ESQUEMA_IMPORTACAO, campos_permitidos=("texto", "candidatos"),
    dados_excluidos=(*EXCLUIDOS_COMUNS, "o arquivo original"),
    lacunas_conhecidas=LACUNAS_IMPORTACAO, montar=_montar_importacao,
    deterministico=_deterministico_importacao, validar=_validar_importacao,
    itens=_itens_importacao, pode_pedir=_pode_importacao, pode_ver=_pode_importacao,
    versao_atual=lambda r: _versao_importacao(r),
    descrever=lambda r: Assunto("Revisão da importação", reverse("viagens:importacoes")),
    envolve_documento=True, acao="Sugerir tipo e destino",
))


# ------------------------------------------------------------------ AUT-58 · comprovante
TIPOS_COMPROVANTE = ("comprovante_saque", "comprovante_transferencia", "nfse", "outro")
ROTULOS_COMPROVANTE = {"comprovante_saque": "Comprovante de saque",
                       "comprovante_transferencia": "Comprovante de transferência/PIX",
                       "nfse": "NFS-e", "outro": "Outro documento"}
LACUNAS_COMPROVANTE = {"sem_texto": "O arquivo não tem texto (imagem ou digitalização): "
                                    "confira à mão."}
ESQUEMA_COMPROVANTE = {
    "type": "object", "additionalProperties": False,
    "required": ["tipo_documento", "numero", "data", "valor", "evidencias", "lacunas"],
    "properties": {
        "tipo_documento": {"type": "string", "enum": list(TIPOS_COMPROVANTE)},
        "numero": {"type": "string", "maxLength": 60},
        "data": {"type": "string", "maxLength": 10},
        "valor": {"type": "string", "maxLength": 20},
        "evidencias": {"type": "array", "maxItems": 4,
                       "items": {"type": "string", "maxLength": 160}},
        "lacunas": {"type": "array", "maxItems": 1,
                    "items": {"type": "string", "enum": list(LACUNAS_COMPROVANTE)}},
    },
}


def _anexo(recurso_id: str) -> AnexoPrestacao:
    a = (AnexoPrestacao.objects.select_related("prestacao__oficio")
         .filter(pk=int(recurso_id) if str(recurso_id).isdigit() else 0,
                 tipo=AnexoPrestacao.Tipo.COMPROVANTE).first())
    if a is None:
        raise RecursoInexistente(recurso_id)
    return a


def _contexto_comprovante(a: AnexoPrestacao) -> Contexto:
    bruto = _texto_do_arquivo(a.arquivo, a.nome_original or a.arquivo.name or "")
    return Contexto(
        recurso_rotulo=f"Comprovante · {a.prestacao.oficio}",
        fatos=_fatos(_fato("texto", "Comprovante · texto extraído (mascarado)",
                           mascarar(bruto), livre=True)),
        contem_documento=True, lacunas=() if bruto.strip() else ("sem_texto",),
        extras={"bruto": bruto})


def _montar_comprovante(usuario, recurso_id: str, opcoes: dict) -> Contexto:
    a = _anexo(recurso_id)
    if not policies.pode_ver_equipe_prestacao(usuario, a.prestacao):
        raise RecursoInexistente(recurso_id)
    return _contexto_comprovante(a)


def _moeda(valor) -> str:
    if valor is None:
        return ""
    inteiro, centavos = f"{valor:.2f}".split(".")
    return f"{int(inteiro):,}".replace(",", ".") + f",{centavos}"


def _deterministico_comprovante(ctx: Contexto) -> dict:
    bruto = ctx.extras["bruto"]
    lido = leitura_anexos.ler_comprovante(bruto) if bruto else {}
    baixo = normalizar(bruto)
    if re.search(r"\bnfs-?e\b|nota fiscal de servic", baixo):
        tipo = "nfse"
    elif "saque" in normalizar(lido.get("operacao", "")) or "saque" in baixo:
        tipo = "comprovante_saque"
    elif re.search(r"transfer|\bpix\b|\bted\b|\bdoc\b", baixo):
        tipo = "comprovante_transferencia"
    else:
        tipo = "outro"
    data = lido.get("data")
    return {"tipo_documento": tipo, "numero": lido.get("autorizacao", "") or "",
            "data": data.isoformat() if data else "", "valor": _moeda(lido.get("valor")),
            "evidencias": [], "lacunas": list(ctx.lacunas)}


def _sem_espaco(texto: str) -> str:
    return re.sub(r"\s+", "", normalizar(texto))


def _validar_comprovante(dados: dict, ctx: Contexto) -> list[str]:
    texto = ctx.valor("texto")
    erros = []
    if dados.get("numero") and _sem_espaco(dados["numero"]) not in _sem_espaco(texto):
        erros.append("numero_fora_do_texto")
    if dados.get("data") and not leitura.data_no_texto(dados["data"], texto):
        erros.append("data_fora_do_texto")
    if dados.get("valor") and _sem_espaco(dados["valor"]) not in _sem_espaco(texto):
        erros.append("valor_fora_do_texto")
    erros.extend("evidencia_fora_do_texto" for e in dados.get("evidencias", [])
                 if not leitura.trecho_no_texto(e, texto))
    return erros


def _itens_comprovante(dados: dict, ctx: Contexto) -> list[Item]:
    fontes = ("Comprovante · texto extraído (mascarado)",)
    nota = "Confira com o arquivo: a leitura não grava nada nem aceita valor sem você."
    itens = [Item("tipo_documento", "Tipo",
                  ROTULOS_COMPROVANTE.get(dados.get("tipo_documento", ""), "—"), fontes,
                  False)]
    for campo, rotulo in (("numero", "Número/autorização"), ("data", "Data"),
                          ("valor", "Valor (R$)")):
        valor = dados.get(campo, "")
        if campo == "data" and valor:
            ano, mes, dia = valor.split("-")
            valor = f"{dia}/{mes}/{ano}"
        itens.append(Item(campo, rotulo, valor or "Não encontrado", fontes, False, nota))
    return itens


registrar_uso(UsoIA(
    chave="viagens.leitura_comprovante", codigo="AUT-58",
    rotulo="Leitura de comprovante e NFS-e",
    descricao="Sugere número, data e valor de um comprovante de layout que as regras não "
              "leem. Só sugestão: nenhum valor é aceito sem leitura humana.",
    versao_prompt="comprovante-v1",
    instrucoes=(
        "Do bloco `texto`, extraia o tipo do documento, o número (ou autorização), a data "
        "(AAAA-MM-DD) e o valor (como no texto, ex.: 377,72). Só o que estiver escrito; "
        "campo ausente fica vazio. Em `evidencias`, os trechos copiados de onde tirou."),
    esquema=ESQUEMA_COMPROVANTE, campos_permitidos=("texto",),
    dados_excluidos=(*EXCLUIDOS_COMUNS, "o arquivo original", "dados bancários (mascarados)"),
    lacunas_conhecidas=LACUNAS_COMPROVANTE, montar=_montar_comprovante,
    deterministico=_deterministico_comprovante, validar=_validar_comprovante,
    itens=_itens_comprovante,
    pode_pedir=lambda u, r: policies.pode_ver_equipe_prestacao(u, _anexo(r).prestacao),
    pode_ver=lambda u, r: policies.pode_ver_equipe_prestacao(u, _anexo(r).prestacao),
    descrever=lambda r: Assunto(f"Comprovante · {_anexo(r).prestacao.oficio}",
                                reverse("viagens:prestacao_equipe",
                                        args=[_anexo(r).prestacao_id])),
    versao_atual=lambda r: _contexto_comprovante(_anexo(r)).versao,
    envolve_documento=True, acao="Ler o comprovante",
))
