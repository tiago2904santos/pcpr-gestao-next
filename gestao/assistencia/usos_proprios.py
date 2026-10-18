"""Usos que não dependem de registro de negócio (a própria assistência registra):

- AUT-88 `assistencia.reformular_resposta` — reescreve em linguagem simples a resposta
  DETERMINÍSTICA do assistente, sem acrescentar fato (número, data, regra, link). Tem chave,
  modo e orçamento próprios: desligada a IA, vale a resposta determinística;
- AUT-93 `assistencia.triagem_modulo` — para uma demanda em texto livre que nenhum sinal
  determinístico classificou, sugere o módulo de destino. Só sugestão, sem efeito.

O "recurso" desses usos é a própria pessoa que pediu (`<id do usuário>:<hash>`): só ela vê.
"""

from __future__ import annotations

import hashlib
import re

from .dominio import textos as redacao
from .dominio.validacao import normalizar
from .ganchos import (
    Assunto,
    Contexto,
    Fato,
    Item,
    OpcaoPedido,
    RecursoInexistente,
    UsoIA,
    registrar_uso,
)

EXCLUIDOS = ("nomes de pessoas", "CPF, RG, telefone e e-mail (mascarados)",
             "dados de saúde, vítimas e ocorrências (a pergunta é recusada antes)")


def recurso_da_pessoa(usuario, texto: str) -> str:
    resumo = hashlib.sha256(normalizar(texto).encode()).hexdigest()[:16]
    return f"{usuario.pk}:{resumo}"


def _dono(usuario, recurso_id: str) -> bool:
    dono, _, resto = str(recurso_id).partition(":")
    if not resto or not dono.isdigit():
        raise RecursoInexistente(recurso_id)
    return bool(getattr(usuario, "is_authenticated", False)) and int(dono) == usuario.pk


def _montar_simples(chaves_rotulos: tuple[tuple[str, str], ...]):
    def montar(usuario, recurso_id: str, opcoes: dict) -> Contexto:
        if not _dono(usuario, recurso_id):
            raise RecursoInexistente(recurso_id)
        fatos = tuple(Fato(c, r, opcoes[c], livre=True, do_pedido=False)
                      for c, r in chaves_rotulos if opcoes.get(c))
        return Contexto(recurso_rotulo="Pedido pessoal", fatos=fatos)
    return montar


# ------------------------------------------------------------------ AUT-88 · reformular
def _montar_reformular(usuario, recurso_id: str, opcoes: dict) -> Contexto:
    """A resposta a reformular é recalculada aqui, pelo assistente determinístico, a partir
    da pergunta: o cliente não manda texto próprio para a IA."""
    from .assistente import responder

    pergunta = str(opcoes.get("pergunta") or "")
    # A Central de ajuda (usuários do sistema) é quem oferece a reformulação: mesmo público.
    resposta = responder(pergunta, None, publico="usuario").texto if pergunta else ""
    return _montar_simples((("resposta", "Resposta do assistente"),
                            ("pergunta", "Pergunta (mascarada)")))(
        usuario, recurso_id, {"pergunta": pergunta, "resposta": resposta})


def _versao_reformular(recurso_id: str) -> str | None:
    """A fonte é a Central de ajuda aprovada: a resposta determinística é refeita com a
    pergunta guardada no pedido. Mudou um artigo (texto, versão, aprovação), a resposta muda e a
    reformulação fica obsoleta. Sem a pergunta (passou a retenção), não há o que comparar."""
    from gestao.identidade.models import Usuario

    from .models import ConteudoPedido

    dono, _, _ = str(recurso_id).partition(":")
    conteudo = (ConteudoPedido.objects.filter(pedido__uso="assistencia.reformular_resposta",
                                              pedido__recurso_id=str(recurso_id))
                .order_by("-pedido_id").first())
    usuario = Usuario.objects.filter(pk=int(dono)).first() if dono.isdigit() else None
    if conteudo is None or usuario is None or not conteudo.opcoes.get("pergunta"):
        return None
    return _montar_reformular(usuario, recurso_id,
                              {"pergunta": conteudo.opcoes["pergunta"]}).versao


def _deterministico_reformular(ctx: Contexto) -> dict:
    return {"textos": [{"campo": "resposta", "texto": ctx.valor("resposta"),
                        "fontes": ["resposta"]}] if ctx.valor("resposta") else [],
            "lacunas": []}


registrar_uso(UsoIA(
    chave="assistencia.reformular_resposta", codigo="AUT-88",
    rotulo="Assistente: resposta em linguagem simples",
    descricao="Reescreve a resposta do assistente (que já sai dos dados e da Central de "
              "ajuda) em linguagem mais simples, sem acrescentar nenhum fato.",
    versao_prompt="reformular-v1",
    instrucoes=("Reescreva o bloco `resposta` em português simples e cordial, em até 4 "
                "frases, mantendo todas as datas, prazos e números exatamente como estão e "
                "sem acrescentar nada. Use `pergunta` só para o tom."),
    esquema=redacao.esquema_textos(("resposta",), ("resposta", "pergunta"), (), 900),
    campos_permitidos=("resposta", "pergunta"), dados_excluidos=EXCLUIDOS,
    lacunas_conhecidas={}, montar=_montar_reformular,
    deterministico=_deterministico_reformular,
    validar=lambda d, c: redacao.validar_textos(
        d, fatos_texto=c.valor("resposta"), chaves=("resposta", "pergunta"),
        campos_alvo=("resposta",), max_caracteres=900),
    itens=lambda d, c: [Item("resposta", "Resposta", t["texto"], tuple(c.rotulos(t["fontes"])),
                             False) for t in d.get("textos", [])],
    pode_pedir=_dono, pode_ver=_dono, versao_atual=_versao_reformular,
    descrever=lambda r: Assunto("Pergunta ao assistente"),
    opcoes=(OpcaoPedido("pergunta", "Pergunta", max_caracteres=500, obrigatorio=True),
            OpcaoPedido("resposta", "Resposta (recalculada no servidor)", max_caracteres=1500)),
    acao="Explicar em linguagem simples",
))


# ------------------------------------------------------------------ AUT-93 · triagem
MODULOS = {
    "viagens": ("Viagens e diárias", r"\b(viage\w*|oficio\w*|diari\w*|deslocament\w*|"
                                     r"roteiro\w*|prestacao de contas|plano de trabalho)\b"),
    "eventos": ("Eventos (solicitações)", r"\b(evento\w*|solicitac\w*|feira\w*|"
                                          r"exposic\w*|unidade movel)\b"),
    "imprensa": ("Atendimento à imprensa", r"\b(imprensa|jornalist\w*|entrevist\w*|"
                                           r"reportage\w*|nota oficial)\b"),
    "publicacoes": ("Publicações", r"\b(publicac\w*|post\w*|rede\w* socia\w*|instagram|"
                                   r"divulga\w*|arte\w*)\b"),
    "palestras": ("Palestras", r"\b(palestr\w*|escola\w*|seminari\w*|orientacao a alunos)\b"),
    "coffee": ("Coffee break", r"\b(coffee|lanche\w*|cafe|buffet|coquetel)\b"),
}
LACUNAS_TRIAGEM = {"sem_sinal": "Nenhum sinal claro no texto: escolha o módulo à mão."}


def triar(texto: str) -> list[tuple[str, int]]:
    """Pontuação por sinais (regra): quantos termos de cada módulo aparecem."""
    t = normalizar(texto)
    pontos = [(m, len(re.findall(padrao, t))) for m, (_, padrao) in MODULOS.items()]
    return sorted([p for p in pontos if p[1]], key=lambda p: -p[1])


def sinais(texto: str, modulo: str, limite: int = 3) -> list[str]:
    """Os termos do texto que apontam o módulo (o que a sugestão cita como evidência)."""
    if modulo not in MODULOS:
        return []
    achados = [m.group(0) for m in re.finditer(MODULOS[modulo][1], normalizar(texto))]
    return list(dict.fromkeys(achados))[:limite]


def _deterministico_triagem(ctx: Contexto) -> dict:
    pontos = triar(ctx.valor("texto"))
    if not pontos or (len(pontos) > 1 and pontos[0][1] == pontos[1][1]):
        return {"modulo": "", "sinais": [], "lacunas": ["sem_sinal"]}
    modulo = pontos[0][0]
    return {"modulo": modulo, "sinais": sinais(ctx.valor("texto"), modulo), "lacunas": []}


def validar_triagem(dados: dict, ctx: Contexto) -> list[str]:
    """O módulo é da lista fechada e cita sinal: cada sinal está no texto e ao menos um é
    sinal DAQUELE módulo. Sem módulo, a lacuna precisa dizer que não há sinal."""
    modulo = dados.get("modulo", "")
    citados = dados.get("sinais", [])
    texto = ctx.valor("texto")
    if not modulo:
        return [] if "sem_sinal" in dados.get("lacunas", []) else ["sem_modulo_sem_lacuna"]
    if modulo not in MODULOS:
        return ["modulo_fora_da_lista"]
    if not citados:
        return ["sem_sinal_citado"]
    erros = ["sinal_fora_do_texto" for x in citados
             if normalizar(x) not in normalizar(texto)][:1]
    if not any(re.search(MODULOS[modulo][1], normalizar(x)) for x in citados):
        erros.append("sinal_de_outro_modulo")
    return erros


ESQUEMA_TRIAGEM = {
    "type": "object", "additionalProperties": False,
    "required": ["modulo", "sinais", "lacunas"],
    "properties": {"modulo": {"type": "string", "enum": ["", *MODULOS]},
                   "sinais": {"type": "array", "maxItems": 3,
                              "items": {"type": "string", "maxLength": 60}},
                   "lacunas": {"type": "array", "maxItems": 1,
                               "items": {"type": "string", "enum": list(LACUNAS_TRIAGEM)}}},
}


registrar_uso(UsoIA(
    chave="assistencia.triagem_modulo", codigo="AUT-93",
    rotulo="Triagem do módulo de uma demanda em texto livre",
    descricao="Sugere para que módulo vai uma demanda que chegou em texto livre, quando as "
              "regras não pontuaram. Só sugestão: nada é criado nem encaminhado.",
    versao_prompt="triagem-v1",
    instrucoes="Diga a que módulo da lista fechada a demanda do bloco `texto` pertence e, em "
               "`sinais`, até 3 palavras copiadas do texto que mostram isso; na dúvida, "
               "deixe o módulo vazio e aponte sem_sinal.",
    esquema=ESQUEMA_TRIAGEM, campos_permitidos=("texto",), dados_excluidos=EXCLUIDOS,
    lacunas_conhecidas=LACUNAS_TRIAGEM, montar=_montar_simples((("texto", "Demanda"),)),
    deterministico=_deterministico_triagem, validar=validar_triagem,
    itens=lambda d, c: [Item("modulo", "Módulo sugerido",
                             MODULOS.get(d.get("modulo", ""), ("Sem sugestão",))[0],
                             ("Demanda (mascarada)",), False,
                             ("Sinais no texto: " + ", ".join(d.get("sinais", [])) + ". "
                              if d.get("sinais") else "")
                             + "Encaminhe pelo módulo; a sugestão não cria nada.")],
    # Sem `versao_atual`, de propósito: não há registro de origem. O recurso é o hash do
    # próprio texto da demanda (outro texto = outro recurso), então a fonte não muda.
    pode_pedir=_dono, pode_ver=_dono, descrever=lambda r: Assunto("Triagem de demanda"),
    opcoes=(OpcaoPedido("texto", "Demanda em texto livre", "Cole o pedido recebido. Não "
                        "cole dados pessoais.", 3000, obrigatorio=True),),
    acao="Sugerir o módulo",
))
