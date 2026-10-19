"""Etapa 1 — cadastros: municípios (só o mapa), unidades, cargos, combustíveis, servidores,
viaturas e motoristas, tabela de diárias, usuários (papéis e lotação), configuração
institucional (com as assinaturas), catálogos do plano e de Eventos, textos prontos.

Regras (docs da migração, 01-cadastros):

* O Eventos Sociais (EV) é a base. Do Gerenciador de Viagens (GV) entra só o que não tem
  linha no `migracao_legado_registro` do EV nem casa por chave natural; o resto é só mapeado
  para a linha correspondente (cada linha do GV ganha a sua correspondência).
* Linha editada nos dois sistemas (mesmo registro com valores diferentes): vale a edição mais
  recente; a outra versão vai para a conferência (só ids e nomes de campos).
* O que já existe no destino (sementes das migrações) casa por chave natural e é mapeado com
  `criado=False`. Semente de catálogo sem correspondente no legado é INATIVADA, nunca apagada.
* Usuários: o hash da senha é copiado como está (nunca `set_password`); a mesma pessoa nos
  dois sistemas vira um usuário só.
* Nada de dado pessoal no relatório nem na saída: só ids, contagens e motivos.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.contrib.auth.hashers import is_password_usable
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Min, Q

from gestao.cadastros.dominio_catalogo import codigo_da_atividade
from gestao.cadastros.models import (
    AtividadePlano,
    Cargo,
    Combustivel,
    ConfiguracaoInstitucional,
    HorarioAtendimento,
    Lotacao,
    ModeloTexto,
    Municipio,
    PresetAtividades,
    ProgramaSolicitante,
    Servidor,
    SubstituicaoAssinante,
    TabelaDiaria,
    TipoViagem,
    Unidade,
    Viatura,
)
from gestao.cadastros.validacoes import (
    RG_NAO_POSSUI,
    cpf_valido,
    espacos,
    normalizar_placa,
    normalizar_rg,
    placa_valida,
    sem_acentos,
    somente_digitos,
)
from gestao.eventos.models import (
    Equipe,
    OrgaoResponsavel,
    TextoDespacho,
    TipoEvento,
    TipoEventoEquipe,
    UnidadeMovel,
)
from gestao.identidade.models import Usuario

from ..contexto import Contexto
from ..fonte import Fonte
from ..models import MapaLegado

LOGIN_MIGRACAO = "migracao"
DOMINIO_PROVISORIO = "migracao.invalid"

# Mesma regra de `cadastros/0017.ligar_tipos` (texto copiado: migrações não são importáveis).
MOTIVO_OPERACAO = ("Acompanhar a operação policial, prestando assessoria de imprensa, atendimento "
                   "aos veículos de comunicação e suporte de comunicação.")

# Tabelas de origem de cada cadastro: (EV, GV).
T = {
    "municipio": ("cadastros_municipio", "cadastros_cidade"),
    "unidade": ("viagens_cadastros_unidade", "cadastros_unidade"),
    "cargo": ("viagens_cadastros_cargo", "cadastros_cargo"),
    "combustivel": ("viagens_cadastros_combustivel", "cadastros_combustivel"),
    "servidor": ("viagens_cadastros_servidor", "cadastros_servidor"),
    "viatura": ("viagens_cadastros_viatura", "cadastros_viatura"),
    "diaria": ("viagens_cadastros_tabeladiaria", "cadastros_tabeladiaria"),
    "configuracao": ("viagens_cadastros_configuracaosistema", "cadastros_configuracaosistema"),
    "assinatura": ("viagens_cadastros_assinaturaconfiguracao",
                   "cadastros_assinaturaconfiguracao"),
    "atividade": ("viagens_planos_atividadeplanotrabalho",
                  "planos_trabalho_atividadeplanotrabalho"),
    "programa": ("viagens_planos_programasolicitante", "planos_trabalho_programasolicitante"),
    "horario": ("viagens_planos_horarioatendimento", "planos_trabalho_horarioatendimento"),
    "preset": ("viagens_planos_presetatividadesplanotrabalho",
               "planos_trabalho_presetatividadesplanotrabalho"),
    "tipo_viagem": ("viagens_viagem_tipoviagem", "eventos_tipoevento"),
    "motivo": ("viagens_oficios_modelomotivooficio", "oficios_modelomotivooficio"),
    "justificativa": ("viagens_oficios_modelojustificativa", "justificativas_modelojustificativa"),
    "usuario": ("accounts_user", "auth_user"),
}

PAPEL_DO_GRUPO_EV = {"VIAGENS_GESTOR": "GESTOR_VIAGENS", "VIAGENS_OPERADOR": "OPERADOR_VIAGENS",
                     "GESTOR_DG": "GESTOR_DG"}
PAPEL_DO_MODULO_EV = {"VIAGENS": "OPERADOR_VIAGENS",
                      "ASCOM_ATENDIMENTO_IMPRENSA": "ASCOM_IMPRENSA",
                      "ASCOM_PUBLICACOES": "ASCOM_PUBLICACOES",
                      "ASCOM_COFFEE_BREAK": "ASCOM_COFFEE_BREAK",
                      "ASCOM_DEMANDAS_EVENTOS": "ASCOM_PALESTRAS"}
PAPEL_DO_VINCULO_GV = {"ADMIN": "GESTOR_VIAGENS", "EDITOR": "OPERADOR_VIAGENS"}
CAMPO_RT = {"atividade": "rt_atividade", "conclusao": "rt_conclusao", "medidas": "rt_medidas",
            "info_complementares": "rt_info", "motivo": "rt_motivo"}

CONFLITO = object()   # chave natural aponta para mais de uma linha do destino


# ---------------------------------------------------------------------------- utilitários
def _tab(fonte: Fonte | None, nome: str | None) -> list[dict]:
    return fonte.tabela(nome) if fonte is not None and nome else []


def _ci(texto: Any) -> str:
    return espacos(str(texto or "")).lower()


def _ai(texto: Any) -> str:
    """Chave sem acento e sem diferença de maiúsculas."""
    return sem_acentos(_ci(texto))


def _datas(linha: dict) -> tuple[datetime | None, datetime | None]:
    criado = linha.get("criado_em") or linha.get("created_at")
    atualizado = linha.get("atualizado_em") or linha.get("updated_at") or criado
    return criado, atualizado


def _tem_campo(modelo: type[models.Model], nome: str) -> bool:
    return any(f.name == nome for f in modelo._meta.get_fields())


def _rotulo(modelo: type[models.Model]) -> str:
    return f"{modelo._meta.app_label}.{modelo.__name__}"


def _registro(ctx: Contexto, tabela_gv: str) -> dict[str, str]:
    """GV origem_pk → EV destino_pk, pela carga que o EV já fez do GV."""
    chave = ("registro", tabela_gv)
    if chave not in ctx.memo:
        ctx.memo[chave] = {str(r["origem_pk"]): str(r["destino_pk"])
                           for r in _cache_tab(ctx, "ev", "migracao_legado_registro")
                           if r["tabela"] == tabela_gv}
    return ctx.memo[chave]


def _fk(ctx: Contexto, sistema: str, entidade: str, pk: Any, notas: list[str],
        campo: str) -> int | None:
    if pk is None:
        return None
    tabela = T[entidade][0 if sistema == "ev" else 1]
    alvo = ctx.destino_int(sistema, tabela, pk)
    if alvo is None:
        notas.append(f"{campo}: referência sem correspondente ({tabela}:{pk})")
    return alvo


# ---------------------------------------------------------------------------- carga genérica
Valores = Callable[[Contexto, str, dict, list[str]], "dict[str, Any] | None"]


@dataclass
class Carga:
    """Uma tabela do legado (EV e/ou GV) para um modelo do destino.

    `valores` devolve os campos do modelo (FKs como `<campo>_id`; M2M em `_m2m`) ou None para
    ignorar a linha (o motivo vai em `notas`). `chaves` devolve as chaves naturais (Q) para
    casar com o que já existe no destino.
    """

    entidade: str
    modelo: type[models.Model]
    ev: str | None
    gv: str | None
    valores: Valores
    chaves: Callable[[dict[str, Any]], list[Q]]
    comparar: bool = True
    atualizar_ao_casar: tuple[str, ...] = ()
    escopo_padrao: tuple[str, ...] | None = None    # None: o modelo não tem "padrão"
    # Obrigatórios só no formulário (o banco aceita vazio) que o legado pode não ter.
    nao_validar: tuple[str, ...] = ()
    # Campos sem coluna de origem num dos lados (diferença de esquema, não edição).
    nao_comparar: tuple[str, ...] = ()
    _ev_por_pk: dict[str, dict] = field(default_factory=dict)


def carregar(ctx: Contexto, c: Carga) -> None:
    linhas_ev = _tab(ctx.ev, c.ev)
    if c.ev:
        ctx.precarregar("ev", c.ev)
    c._ev_por_pk = {str(r["id"]): r for r in linhas_ev}
    for linha in linhas_ev:
        _uma(ctx, c, "ev", c.ev or "", linha)
    if not c.gv or ctx.gv is None:
        return
    linhas_gv = _tab(ctx.gv, c.gv)
    ctx.precarregar("gv", c.gv)
    registro = _registro(ctx, c.gv)
    for linha in linhas_gv:
        _uma(ctx, c, "gv", c.gv, linha, registro.get(str(linha["id"])))


def _uma(ctx: Contexto, c: Carga, sistema: str, tabela: str, linha: dict,
         ev_pk: str | None = None) -> None:
    pk = linha["id"]
    rel = ctx.relatorio
    if ctx.destino(sistema, tabela, pk) is not None:
        rel.conta(c.entidade, "ja_mapeado")
        return
    notas: list[str] = []
    if sistema == "gv" and ev_pk is not None and c.ev:
        alvo = ctx.destino("ev", c.ev, ev_pk)
        if alvo is not None:
            obj = c.modelo._default_manager.get(pk=alvo)
            ctx.mapear(sistema, tabela, pk, obj, criado=False)
            rel.conta(c.entidade, "mapeado_pelo_registro_ev")
            ev_linha = c._ev_por_pk.get(ev_pk)
            vals_gv = c.valores(ctx, sistema, linha, notas) if c.comparar else None
            if vals_gv is not None and ev_linha is not None:
                _comparar(ctx, c, obj, ev_linha, linha, vals_gv, ev_pk)
            return
    vals = c.valores(ctx, sistema, linha, notas)
    if vals is None:
        rel.conta(c.entidade, "ignorado")
        rel.revisar(c.entidade, "; ".join(notas) or "linha ignorada", sistema=sistema,
                    tabela=tabela, origem_pk=pk)
        return
    if sistema == "gv" and ev_pk is not None and c.ev:
        # O alvo do registro não chegou ao destino (excluído no EV, ou recusado): não se
        # recria pelo GV.
        obj_ou_nada = _por_chave(ctx, c, vals, sistema, tabela, pk)
        if obj_ou_nada is CONFLITO:
            return
        if isinstance(obj_ou_nada, models.Model):
            ctx.mapear(sistema, tabela, pk, obj_ou_nada, criado=False)
            rel.conta(c.entidade, "casado_por_chave")
            return
        rel.conta(c.entidade, "ignorado")
        rel.revisar(c.entidade, "o registro do EV aponta para uma linha sem correspondente "
                    "no destino; não recriada pelo GV",
                    sistema=sistema, tabela=tabela, origem_pk=pk, ev_pk=ev_pk)
        return
    existente = _por_chave(ctx, c, vals, sistema, tabela, pk)
    if existente is CONFLITO:
        return
    if isinstance(existente, models.Model):
        ctx.mapear(sistema, tabela, pk, existente, criado=False)
        rel.conta(c.entidade, "casado_por_chave")
        _atualizar_ao_casar(c, existente, vals)
        return
    _criar(ctx, c, sistema, tabela, linha, vals, notas)


def _por_chave(ctx: Contexto, c: Carga, vals: dict[str, Any], sistema: str, tabela: str,
               pk: Any) -> Any:
    alvos: set[Any] = set()
    for q in c.chaves(vals):
        alvos.update(c.modelo._default_manager.filter(q).values_list("pk", flat=True))
    if not alvos:
        return None
    if len(alvos) > 1:
        ctx.relatorio.conta(c.entidade, "conflito")
        ctx.relatorio.revisar(c.entidade, "chaves naturais apontam para linhas diferentes do "
                              "destino; nada criado nem alterado", sistema=sistema,
                              tabela=tabela, origem_pk=pk, destinos=sorted(alvos))
        return CONFLITO
    return c.modelo._default_manager.get(pk=alvos.pop())


def _atualizar_ao_casar(c: Carga, obj: models.Model, vals: dict[str, Any]) -> None:
    campos = {k: vals[k] for k in c.atualizar_ao_casar if k in vals and k != "_m2m"}
    if campos:
        c.modelo._default_manager.filter(pk=obj.pk).update(**campos)
    if "_m2m" in c.atualizar_ao_casar:
        for nome, ids in vals.get("_m2m", {}).items():
            if ids:
                getattr(obj, nome).add(*ids)


def _criar(ctx: Contexto, c: Carga, sistema: str, tabela: str, linha: dict,
           vals: dict[str, Any], notas: list[str]) -> models.Model | None:
    rel = ctx.relatorio
    vals = dict(vals)
    m2m = vals.pop("_m2m", {})
    if c.escopo_padrao is not None and vals.get("padrao"):
        filtro = {"padrao": True, **{k: vals[k] for k in c.escopo_padrao}}
        if c.modelo._default_manager.filter(**filtro).exists():
            vals["padrao"] = False
            notas.append("o destino já tem um padrão: entrou como não padrão")
    obj = c.modelo(**vals)
    try:
        obj.full_clean(exclude=list(c.nao_validar) or None)
    except ValidationError as erro:
        rel.conta(c.entidade, "invalido")
        rel.revisar(c.entidade, "não passa na validação do modelo", sistema=sistema,
                    tabela=tabela, origem_pk=linha["id"],
                    campos=sorted(getattr(erro, "message_dict", {"__all__": []})))
        return None
    try:
        with transaction.atomic():
            obj.save()
    except IntegrityError:
        rel.conta(c.entidade, "invalido")
        rel.revisar(c.entidade, "restrição do banco recusou a linha", sistema=sistema,
                    tabela=tabela, origem_pk=linha["id"])
        return None
    for nome, ids in m2m.items():
        if ids:
            getattr(obj, nome).add(*ids)
    _preservar_datas(c.modelo, obj.pk, linha)
    ctx.mapear(sistema, tabela, linha["id"], obj, criado=True)
    rel.conta(c.entidade, "criado")
    for nota in notas:
        rel.revisar(c.entidade, nota, sistema=sistema, tabela=tabela, origem_pk=linha["id"],
                    destino_pk=obj.pk)
    return obj


def _preservar_datas(modelo: type[models.Model], pk: Any, linha: dict,
                     so_atualizado: bool = False) -> None:
    criado, atualizado = _datas(linha)
    datas: dict[str, Any] = {}
    if criado and not so_atualizado and _tem_campo(modelo, "criado_em"):
        datas["criado_em"] = criado
    if atualizado and _tem_campo(modelo, "atualizado_em"):
        datas["atualizado_em"] = atualizado
    if datas:
        modelo._default_manager.filter(pk=pk).update(**datas)


def _comparar(ctx: Contexto, c: Carga, obj: models.Model, ev_linha: dict, gv_linha: dict,
              vals_gv: dict[str, Any], ev_pk: str) -> None:
    """Mesmo registro nos dois sistemas: se os valores diferem, vale o mais recente."""
    vals_ev = c.valores(ctx, "ev", ev_linha, [])
    if vals_ev is None:
        return
    diferentes = sorted(
        k for k in set(vals_ev) | set(vals_gv)
        if k != "_m2m" and k not in c.nao_comparar and vals_ev.get(k) != vals_gv.get(k))
    m2m_ev, m2m_gv = vals_ev.get("_m2m", {}), vals_gv.get("_m2m", {})
    diferentes += sorted(k for k in set(m2m_ev) | set(m2m_gv)
                         if sorted(m2m_ev.get(k, [])) != sorted(m2m_gv.get(k, [])))
    if not diferentes:
        return
    ev_em, gv_em = _datas(ev_linha)[1], _datas(gv_linha)[1]
    gv_venceu = bool(gv_em and ev_em and gv_em > ev_em)
    ctx.relatorio.conta(c.entidade, "editado_nos_dois")
    if gv_venceu:
        simples = {k: vals_gv[k] for k in diferentes if k in vals_gv and k not in m2m_gv}
        try:
            with transaction.atomic():
                if simples:
                    c.modelo._default_manager.filter(pk=obj.pk).update(**simples)
                for k in diferentes:
                    if k in m2m_gv:
                        getattr(obj, k).set(m2m_gv[k])
                _preservar_datas(c.modelo, obj.pk, gv_linha, so_atualizado=True)
        except IntegrityError:
            ctx.relatorio.revisar(c.entidade, "versão do GV (mais recente) recusada pelo banco; "
                                  "ficou a do EV", ev_pk=ev_pk, gv_pk=gv_linha["id"],
                                  destino_pk=obj.pk, campos=diferentes)
            return
    vencedor, outro = ("GV", "EV") if gv_venceu else ("EV", "GV")
    ctx.relatorio.revisar(
        c.entidade, f"editado nos dois sistemas: valeu o {vencedor} (edição mais recente); "
        f"conferir a versão do {outro}", ev_pk=ev_pk, gv_pk=gv_linha["id"],
        destino_pk=obj.pk, campos=diferentes)


# ---------------------------------------------------------------------------- municípios
def _municipios(ctx: Contexto) -> None:
    por_ibge = dict(Municipio.objects.values_list("codigo_ibge", "pk"))
    for sistema, fonte, tabela in (("ev", ctx.ev, T["municipio"][0]),
                                   ("gv", ctx.gv, T["municipio"][1])):
        if fonte is None:
            continue
        pares, faltam = [], []
        linhas = _tab(fonte, tabela)
        for r in linhas:
            alvo = por_ibge.get(str(r["codigo_ibge"])) if r["codigo_ibge"] is not None else None
            if alvo is None:
                faltam.append(r["id"])
            else:
                pares.append((r["id"], alvo))
        novos = ctx.mapear_lote(sistema, tabela, _rotulo(Municipio), pares, criado=False)
        ctx.relatorio.conta("municipio", "casado_por_chave", novos)
        ctx.relatorio.conta("municipio", "ja_mapeado", len(pares) - novos)
        for pk in faltam:
            ctx.relatorio.conta("municipio", "ignorado")
            ctx.relatorio.revisar("municipio", "código IBGE ausente ou desconhecido",
                                  sistema=sistema, tabela=tabela, origem_pk=pk)


# ---------------------------------------------------------------------------- cadastros base
def _v_unidade(ctx: Contexto, sistema: str, r: dict, notas: list[str]) -> dict[str, Any]:
    return {"nome": espacos(r["nome"])[:255], "sigla": espacos(r["sigla"])[:50]}


def _v_nome_padrao(ctx: Contexto, sistema: str, r: dict, notas: list[str]) -> dict[str, Any]:
    return {"nome": espacos(r["nome"])[:120], "padrao": bool(r["is_padrao"])}


def _k_nome(vals: dict[str, Any]) -> list[Q]:
    return [Q(nome__iexact=vals["nome"])]


def _cpf(bruto: Any, notas: list[str]) -> str:
    cpf = somente_digitos(bruto)
    if not cpf:
        return ""
    if len(cpf) == 10 and cpf_valido(cpf.zfill(11)):
        notas.append("CPF com 10 dígitos completado com zero à esquerda")
        return cpf.zfill(11)
    if len(cpf) != 11:
        notas.append(f"CPF com {len(cpf)} dígitos não recuperável: ficou vazio")
        return ""
    if not cpf_valido(cpf):
        notas.append("CPF com dígito verificador inválido (mantido)")
    return cpf


def _v_servidor(ctx: Contexto, sistema: str, r: dict, notas: list[str]) -> dict[str, Any] | None:
    nome = espacos(r["nome"])[:255]
    if not nome:
        notas.append("servidor sem nome")
        return None
    if r.get("sem_rg"):
        rg = RG_NAO_POSSUI
    else:
        rg = normalizar_rg(r.get("rg"))
        if rg and rg != RG_NAO_POSSUI and not any(ch.isdigit() for ch in rg):
            notas.append("RG sem nenhum dígito (marcador?): ficou vazio")
            rg = ""
        rg = rg[:30]
    telefone = somente_digitos(r.get("telefone"))
    if len(telefone) > 11:
        notas.append("telefone com mais de 11 dígitos: ficou vazio")
        telefone = ""
    return {"nome": nome, "cpf": _cpf(r.get("cpf"), notas), "rg": rg, "telefone": telefone,
            "cargo_id": _fk(ctx, sistema, "cargo", r.get("cargo_id"), notas, "cargo"),
            "unidade_id": _fk(ctx, sistema, "unidade", r.get("unidade_id"), notas, "unidade")}


def _k_servidor(vals: dict[str, Any]) -> list[Q]:
    chaves = [Q(nome__iexact=vals["nome"])]
    if vals["cpf"]:
        chaves.append(Q(cpf=vals["cpf"]))
    if vals["telefone"]:
        chaves.append(Q(telefone=vals["telefone"]))
    if vals["rg"] and vals["rg"] != RG_NAO_POSSUI:
        chaves.append(Q(rg=vals["rg"]))
    return chaves


def _v_viatura(ctx: Contexto, sistema: str, r: dict, notas: list[str]) -> dict[str, Any] | None:
    placa = normalizar_placa(r["placa"])
    if not placa_valida(placa):
        notas.append("placa fora do formato")
        return None
    tipo = (r.get("tipo") or "").strip().lower()
    if tipo not in Viatura.Tipo.values:
        if tipo:
            notas.append("tipo de viatura desconhecido: ficou vazio")
        tipo = ""
    return {"placa": placa, "modelo": espacos(r.get("modelo"))[:120], "tipo": tipo, "porte": "",
            "combustivel_id": _fk(ctx, sistema, "combustivel", r.get("combustivel_id"), notas,
                                  "combustível"),
            "unidade_id": _fk(ctx, sistema, "unidade", r.get("unidade_id"), notas, "unidade")}


def _motoristas(ctx: Contexto) -> None:
    pares = (("ev", ctx.ev, "viagens_cadastros_viatura_motoristas"),
             ("gv", ctx.gv, "cadastros_viatura_motoristas"))
    Through = Viatura.motoristas.through
    for sistema, fonte, tabela in pares:
        for r in _tab(fonte, tabela):
            notas: list[str] = []
            v = _fk(ctx, sistema, "viatura", r["viatura_id"], notas, "viatura")
            s = _fk(ctx, sistema, "servidor", r["servidor_id"], notas, "servidor")
            if v is None or s is None:
                ctx.relatorio.conta("viatura_motorista", "ignorado")
                ctx.relatorio.revisar("viatura_motorista", "; ".join(notas), sistema=sistema,
                                      tabela=tabela, origem_pk=r["id"])
                continue
            _, criado = Through.objects.get_or_create(viatura_id=v, servidor_id=s)
            ctx.relatorio.conta("viatura_motorista", "criado" if criado else "ja_existia")


def _v_diaria(ctx: Contexto, sistema: str, r: dict, notas: list[str]) -> dict[str, Any] | None:
    faixa = (r["faixa"] or "").strip().lower()
    if faixa not in TabelaDiaria.Faixa.values:
        notas.append("faixa de diária desconhecida")
        return None
    return {"faixa": faixa, "vigente_desde": r["vigencia_inicio"], "valor_24h": r["valor_24h"],
            "norma": ""}


def _k_diaria(vals: dict[str, Any]) -> list[Q]:
    return [Q(faixa=vals["faixa"], vigente_desde=vals["vigente_desde"])]


# ---------------------------------------------------------------------------- usuários
@dataclass
class Pessoa:
    ev: dict | None = None
    gv: dict | None = None

    @property
    def lados(self) -> list[tuple[str, dict]]:
        return [(s, u) for s, u in (("ev", self.ev), ("gv", self.gv)) if u is not None]


def parear_usuarios(ev: list[dict], gv: list[dict]) -> list[Pessoa]:
    """A mesma pessoa nos dois sistemas: mesmo login; senão, mesmo e-mail (não vazio)."""
    pessoas = [Pessoa(ev=u) for u in ev]
    for g in gv:
        livres = [p for p in pessoas if p.ev is not None and p.gv is None]
        par = next((p for p in livres if p.ev and _ci(p.ev["username"]) == _ci(g["username"])),
                   None)
        if par is None and _ci(g.get("email")):
            par = next((p for p in livres
                        if p.ev and _ci(p.ev.get("email")) == _ci(g.get("email"))), None)
        if par is not None:
            par.gv = g
        else:
            pessoas.append(Pessoa(gv=g))
    return pessoas


def _mais_recente_primeiro(lados: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Os lados da pessoa pelo último login, do mais recente; quem nunca entrou fica no fim."""
    com = sorted((su for su in lados if su[1].get("last_login")),
                 key=lambda su: su[1]["last_login"], reverse=True)
    return com + [su for su in lados if not su[1].get("last_login")]


def unificar_usuario(p: Pessoa) -> tuple[dict[str, Any], list[str]]:
    """Campos do usuário novo a partir de um ou dois usuários do legado (+ notas)."""
    notas: list[str] = []
    base = p.ev or p.gv
    assert base is not None
    login = espacos(base["username"])[:60]
    email = next((_ci(u.get("email")) for _, u in p.lados if _ci(u.get("email"))), "")
    if not email:
        email = f"{login.lower()}@{DOMINIO_PROVISORIO}"
        notas.append("sem e-mail no legado: endereço provisório, corrigir no cadastro")
    nome = next((espacos(f"{u.get('first_name', '')} {u.get('last_name', '')}")
                 for _, u in p.lados
                 if espacos(f"{u.get('first_name', '')} {u.get('last_name', '')}")), "")
    if not nome:
        nome = login
        notas.append("sem nome no legado: ficou o login, corrigir no cadastro")
    ordem = _mais_recente_primeiro(p.lados)
    usaveis = [(s, u) for s, u in ordem if is_password_usable(u.get("password"))]
    lado_senha, dono = usaveis[0] if usaveis else ordem[0]
    if usaveis and (lado_senha, dono) != ordem[0]:
        notas.append(f"senha do {lado_senha.upper()}: o sistema com o login mais recente não "
                     "tem senha utilizável")
    if len(usaveis) > 1 and usaveis[0][1]["password"] != usaveis[1][1]["password"]:
        notas.append(f"senhas diferentes nos dois sistemas: vale a do {lado_senha.upper()} "
                     "(login mais recente); a do outro deixa de valer")
    hash_senha = dono.get("password") or ""
    deve_trocar = bool(p.ev and p.ev.get("deve_trocar_senha")) or not is_password_usable(
        hash_senha)
    logins = [u["last_login"] for _, u in p.lados if u.get("last_login")]
    entradas = [u["date_joined"] for _, u in p.lados if u.get("date_joined")]
    campos: dict[str, Any] = {
        "login": login, "email": email, "nome": nome[:150], "password": hash_senha,
        "is_active": bool(base["is_active"]),
        "is_staff": any(bool(u["is_staff"]) for _, u in p.lados),
        # Superusuário: vem do EV (o sistema de referência); só do GV quando não há EV.
        "is_superuser": bool(base["is_superuser"]),
        "last_login": max(logins) if logins else None,
        "deve_trocar_senha": deve_trocar,
    }
    if entradas:
        campos["criado_em"] = min(entradas)
    return campos, notas


def _papeis_e_lotacao(ctx: Contexto, p: Pessoa) -> tuple[set[str], str, list[str]]:
    papeis: set[str] = set()
    notas: list[str] = []
    sigla = ""
    if p.ev is not None:
        grupos = {g["id"]: g["name"] for g in _cache_tab(ctx, "ev", "auth_group")}
        for ug in _cache_tab(ctx, "ev", "accounts_user_groups"):
            if ug["user_id"] == p.ev["id"]:
                nome = grupos.get(ug["group_id"], "")
                if nome in PAPEL_DO_GRUPO_EV:
                    papeis.add(PAPEL_DO_GRUPO_EV[nome])
                else:
                    notas.append(f"grupo do EV sem papel correspondente (grupo {ug['group_id']})")
        modulos = {m["id"]: m["codigo"] for m in _cache_tab(ctx, "ev", "accounts_modulo")}
        setores = {us["setor_id"] for us in _cache_tab(ctx, "ev", "accounts_user_setores")
                   if us["user_id"] == p.ev["id"]}
        for ms in _cache_tab(ctx, "ev", "accounts_modulo_setores"):
            if ms["setor_id"] in setores and modulos.get(ms["modulo_id"]) in PAPEL_DO_MODULO_EV:
                papeis.add(PAPEL_DO_MODULO_EV[modulos[ms["modulo_id"]]])
    if p.gv is not None:
        areas = {a["id"]: a["sigla"] for a in _cache_tab(ctx, "gv", "usuarios_areatrabalho")}
        vinculos = [v for v in _cache_tab(ctx, "gv", "usuarios_vinculousuarioarea")
                    if v["usuario_id"] == p.gv["id"] and v.get("ativo", True)]
        for v in vinculos:
            papel = PAPEL_DO_VINCULO_GV.get(v["papel"])
            if papel is None:
                notas.append(f"papel do GV sem correspondente (vínculo {v['id']})")
                continue
            papeis.add(papel)
            if v["papel"] == "ADMIN" and p.gv.get("is_superuser"):
                papeis.add("ADMINISTRADOR")
        padrao = next((v for v in vinculos if v.get("area_padrao")), vinculos[0] if vinculos
                      else None)
        if padrao is not None:
            sigla = espacos(areas.get(padrao["area_id"], ""))
    return papeis, sigla, notas


def _cache_tab(ctx: Contexto, sistema: str, nome: str) -> list[dict]:
    chave = ("tabela", sistema, nome)
    if chave not in ctx.memo:
        ctx.memo[chave] = _tab(ctx.ev if sistema == "ev" else ctx.gv, nome)
    return ctx.memo[chave]


def garantir_usuario_migracao(ctx: Contexto) -> Usuario:
    """Usuário técnico, inativo e sem senha utilizável: autor do que não tem autor."""
    usuario = Usuario.objects.filter(login__iexact=LOGIN_MIGRACAO).first()
    if usuario is None:
        usuario = Usuario(login=LOGIN_MIGRACAO, email=f"{LOGIN_MIGRACAO}@{DOMINIO_PROVISORIO}",
                          nome="Migração dos sistemas antigos", is_active=False)
        usuario.set_unusable_password()
        usuario.save()
        ctx.relatorio.conta("usuario_migracao", "criado")
    else:
        ctx.relatorio.conta("usuario_migracao", "ja_existia")
    ctx.usuario_migracao = usuario
    return usuario


def _usuarios(ctx: Contexto) -> None:
    rel = ctx.relatorio
    t_ev, t_gv = T["usuario"]
    ev = _tab(ctx.ev, t_ev)
    gv = _tab(ctx.gv, t_gv)
    for p in parear_usuarios(ev, gv):
        ids = [(s, t_ev if s == "ev" else t_gv, u["id"]) for s, u in p.lados]
        if p.ev is not None and p.gv is not None:
            rel.conta("usuario", "pessoa_nos_dois_sistemas")
        ja = next((d for d in (ctx.destino_int(s, t, pk) for s, t, pk in ids) if d), None)
        if ja is not None:
            usuario = Usuario.objects.get(pk=ja)
            for s, t, pk in ids:
                if ctx.destino(s, t, pk) is None:
                    ctx.mapear(s, t, pk, usuario, criado=False)
            rel.conta("usuario", "ja_mapeado")
            continue
        campos, notas = unificar_usuario(p)
        papeis, sigla, notas_papel = _papeis_e_lotacao(ctx, p)
        notas += notas_papel
        existentes = set(Usuario.objects.filter(
            Q(login__iexact=campos["login"]) | Q(email__iexact=campos["email"]))
            .values_list("pk", flat=True))
        ref = {f"{s}_pk": pk for s, _, pk in ids}
        tecnico = ctx.usuario_migracao.pk if ctx.usuario_migracao is not None else None
        if len(existentes) > 1 or (tecnico is not None and tecnico in existentes):
            rel.conta("usuario", "conflito")
            rel.revisar("usuario", "login/e-mail coincidem com usuários diferentes do destino "
                        "(ou com o usuário técnico); nada criado", **ref)
            continue
        if existentes:
            usuario = Usuario.objects.get(pk=existentes.pop())
            for s, t, pk in ids:
                ctx.mapear(s, t, pk, usuario, criado=False)
            rel.conta("usuario", "casado_por_chave")
            continue
        usuario = Usuario(unidade_sigla=sigla[:40], **campos)
        try:
            # A senha é o hash do legado, copiado como está (nunca set_password).
            usuario.full_clean()
            with transaction.atomic():
                usuario.save()
        except (ValidationError, IntegrityError) as erro:
            rel.conta("usuario", "invalido")
            rel.revisar("usuario", "não passa na validação do modelo",
                        campos=sorted(getattr(erro, "message_dict", {"__all__": []})), **ref)
            continue
        grupos = list(Group.objects.filter(name__in=papeis))
        if len(grupos) != len(papeis):
            notas.append("papel sem grupo no destino (rode as migrações)")
        usuario.groups.add(*grupos)
        rel.conta("usuario_papel", "criado", len(grupos))
        if sigla:
            unidades = list(Unidade.objects.filter(sigla__iexact=sigla)[:2])
            if len(unidades) == 1:
                Lotacao.objects.create(usuario=usuario, unidade=unidades[0])
                rel.conta("lotacao", "criado")
            else:
                notas.append("área do GV sem unidade única com a mesma sigla: sem lotação")
                rel.conta("lotacao", "ignorado")
        for s, t, pk in ids:
            ctx.mapear(s, t, pk, usuario, criado=True)
        rel.conta("usuario", "criado")
        for nota in notas:
            rel.revisar("usuario", nota, destino_pk=usuario.pk, **ref)


def _grupos_ev(ctx: Contexto) -> None:
    """Grupos do EV → papéis do sistema novo (só o mapa; papéis vêm do código)."""
    for g in _cache_tab(ctx, "ev", "auth_group"):
        papel = PAPEL_DO_GRUPO_EV.get(g["name"])
        grupo = Group.objects.filter(name=papel).first() if papel else None
        if grupo is None:
            ctx.relatorio.conta("grupo", "ignorado")
            ctx.relatorio.revisar("grupo", "grupo do EV sem papel correspondente",
                                  sistema="ev", tabela="auth_group", origem_pk=g["id"])
        elif ctx.destino("ev", "auth_group", g["id"]) is None:
            ctx.mapear("ev", "auth_group", g["id"], grupo, criado=False)
            ctx.relatorio.conta("grupo", "casado_por_chave")
        else:
            ctx.relatorio.conta("grupo", "ja_mapeado")


# ---------------------------------------------------------------------------- configuração
def _assinaturas(ctx: Contexto, sistema: str) -> list[dict]:
    return _cache_tab(ctx, sistema, T["assinatura"][0 if sistema == "ev" else 1])


def _v_configuracao(ctx: Contexto, sistema: str, r: dict,
                    notas: list[str]) -> dict[str, Any] | None:
    unidade = _fk(ctx, sistema, "unidade", r.get("unidade_id"), notas, "unidade")
    sede = _fk(ctx, sistema, "municipio", r.get("cidade_sede_padrao_id"), notas, "sede")
    if unidade is None or sede is None:
        notas.append("configuração sem unidade ou sem cidade sede: não migrada")
        return None
    nome_extenso = espacos(r.get("ascom_cabecalho_unidade") or r.get("nome_orgao"))
    rodape = " - ".join(p for p in (espacos(r.get("ascom_rodape_endereco")),
                                    espacos(r.get("ascom_rodape_contato"))) if p)
    if len(rodape) > 255:
        notas.append("rodapé com mais de 255 caracteres: ficou vazio (montado do endereço)")
        rodape = ""
    elif rodape:
        notas.append("rodapé = endereço + ' - ' + contato do legado: conferir o layout")
    chefia_nome, chefia_cargo = espacos(r.get("nome_chefia")), espacos(r.get("cargo_chefia"))
    if not chefia_nome or not chefia_cargo:
        notas.append("sem chefia (nome/cargo) no legado: preencher na configuração")
    vals: dict[str, Any] = {
        "unidade_id": unidade, "sede_id": sede, "nome_extenso": nome_extenso[:160],
        "endereco_rodape": rodape, "chefia_nome": chefia_nome[:150],
        "chefia_cargo": chefia_cargo[:150],
        "destinatario_nome": espacos(r.get("destinatario_oficio_nome"))[:150],
        "destinatario_cargo": espacos(r.get("destinatario_oficio_cargo"))[:150],
        "destinatario_orgao": espacos(r.get("destinatario_oficio_unidade"))[:160],
        "prazo_justificativa_dias": r.get("prazo_justificativa_dias") or 10,
        "delegado_geral_nome": espacos(r.get("delegado_geral_nome"))[:120],
        "coordenador_plano_id": _fk(ctx, sistema, "servidor",
                                    r.get("coordenador_adm_plano_trabalho_id"), notas,
                                    "coordenador"),
        "sufixo_plano": espacos(r.get("pt_sufixo_numero"))[:20],
        "cep": somente_digitos(r.get("cep"))[:8], "logradouro": espacos(r.get("logradouro"))[:160],
        "numero": espacos(r.get("numero"))[:20], "bairro": espacos(r.get("bairro"))[:120],
        "cidade_endereco": espacos(r.get("cidade_endereco"))[:120],
        "uf": espacos(r.get("uf")).upper()[:2], "email": _ci(r.get("email")),
        "telefone": somente_digitos(r.get("telefone"))[:11],
        "ramal": espacos(r.get("ramal"))[:20],
    }
    if not vals["nome_extenso"]:
        notas.append("sem nome da unidade no cabeçalho: usar o nome da unidade")
        unidade_obj = Unidade.objects.filter(pk=unidade).first()
        vals["nome_extenso"] = (unidade_obj.nome if unidade_obj else "")[:160]
    campos = {"OFICIO": "assina_oficio_id", "JUSTIFICATIVA": "assina_justificativa_id",
              "PLANO_TRABALHO": "assina_plano_id"}
    for campo in campos.values():
        vals[campo] = None
    por_tipo: dict[str, list[dict]] = {}
    for a in _assinaturas(ctx, sistema):
        if a["configuracao_id"] == r["id"] and a.get("ativo", True):
            por_tipo.setdefault(a["tipo"], []).append(a)
    for tipo, lista in por_tipo.items():
        lista.sort(key=lambda a: a.get("ordem") or 0)
        if len(lista) > 1:
            notas.append(f"assinatura {tipo}: mais de um assinante; ficou o de menor ordem")
        if tipo in campos:
            vals[campos[tipo]] = _fk(ctx, sistema, "servidor", lista[0].get("servidor_id"),
                                     notas, f"assinatura {tipo}")
        elif tipo == "ORDEM_SERVICO":
            notas.append("assinatura ORDEM_SERVICO sem campo na configuração nova (lacuna: a "
                         "OS tem assinante por documento)")
        elif tipo != "DESTINATARIO_OFICIO_GERAL":   # o destinatário fica como texto
            notas.append(f"assinatura {tipo} sem correspondente")
    return vals


def _mapear_assinaturas(ctx: Contexto) -> None:
    for sistema in ("ev", "gv"):
        fonte = ctx.ev if sistema == "ev" else ctx.gv
        if fonte is None:
            continue
        t_conf = T["configuracao"][0 if sistema == "ev" else 1]
        t_ass = T["assinatura"][0 if sistema == "ev" else 1]
        for a in _assinaturas(ctx, sistema):
            if ctx.destino(sistema, t_ass, a["id"]) is not None:
                ctx.relatorio.conta("assinatura", "ja_mapeado")
                continue
            conf = ctx.destino_int(sistema, t_conf, a["configuracao_id"])
            if conf is None:
                ctx.relatorio.conta("assinatura", "ignorado")
                continue
            obj = ConfiguracaoInstitucional.objects.get(pk=conf)
            ctx.mapear(sistema, t_ass, a["id"], obj, criado=False)
            ctx.relatorio.conta("assinatura", "na_configuracao")


SUBSTITUICAO = {"OFICIO": "oficio", "JUSTIFICATIVA": "justificativa",
                "PLANO_TRABALHO": "plano_trabalho", "TODOS": "todos"}


def _v_substituicao(ctx: Contexto, sistema: str, r: dict,
                    notas: list[str]) -> dict[str, Any] | None:
    conf = _fk(ctx, sistema, "configuracao", r["configuracao_id"], notas, "configuração")
    serv = _fk(ctx, sistema, "servidor", r["servidor_id"], notas, "servidor")
    tipo = SUBSTITUICAO.get((r.get("tipo") or "").upper())
    if conf is None or serv is None or tipo is None:
        notas.append("substituição sem configuração, servidor ou tipo válido")
        return None
    return {"configuracao_id": conf, "servidor_id": serv, "tipo": tipo, "inicio": r["inicio"],
            "fim": r.get("fim"), "motivo": espacos(r.get("motivo"))[:120],
            "ativo": bool(r.get("ativo", True))}


# ---------------------------------------------------------------------------- catálogos
def _k_atividade_nome(vals: dict[str, Any]) -> list[Q]:
    alvo = _ai(vals["nome"])
    ids = [pk for pk, nome in AtividadePlano.objects.values_list("pk", "nome")
           if _ai(nome) == alvo]
    return [Q(pk__in=ids)] if ids else []


def _k_atividade(vals: dict[str, Any]) -> list[Q]:
    # Código primeiro; o nome só quando o código não casa (o código manda).
    if AtividadePlano.objects.filter(codigo=vals["codigo"]).exists():
        return [Q(codigo=vals["codigo"])]
    return _k_atividade_nome(vals)


def _v_atividade(nomes_servico: dict[str, str]) -> Valores:
    def valores(ctx: Contexto, sistema: str, r: dict, notas: list[str]) -> dict[str, Any] | None:
        codigo = espacos(r.get("codigo")).upper()[:40]
        nome = espacos(r.get("nome"))
        if not nome:
            notas.append("atividade sem nome")
            return None
        # O legado guarda o nome em maiúsculas; o serviço do EV tem a grafia de leitura.
        nome = nomes_servico.get(_ai(nome), nome)[:255]
        if not codigo:
            codigo = codigo_da_atividade(nome, set(AtividadePlano.objects.values_list(
                "codigo", flat=True)))
        return {"codigo": codigo, "nome": nome, "meta": r.get("meta") or "",
                "recurso": r.get("recurso_necessario") or "",
                "ativo": bool(r.get("ativo", True))}
    return valores


def _v_servico(ctx: Contexto, sistema: str, r: dict, notas: list[str]) -> dict[str, Any] | None:
    nome = espacos(r["nome"])[:255]
    if not nome:
        return None
    codigo = codigo_da_atividade(nome, set(AtividadePlano.objects.values_list("codigo",
                                                                               flat=True)))
    return {"codigo": codigo, "nome": nome, "ativo": bool(r.get("ativo", True))}


def _v_programa(ctx: Contexto, sistema: str, r: dict, notas: list[str]) -> dict[str, Any] | None:
    nome = espacos(r["nome"])[:200]
    return {"nome": nome, "ativo": bool(r.get("ativo", True))} if nome else None


def _v_horario(ctx: Contexto, sistema: str, r: dict, notas: list[str]) -> dict[str, Any] | None:
    nome = espacos(r["faixa"])[:60]
    return {"nome": nome, "ativo": bool(r.get("ativo", True))} if nome else None


def _v_preset(m2m: dict[tuple[str, Any], list[Any]]) -> Valores:
    def valores(ctx: Contexto, sistema: str, r: dict, notas: list[str]) -> dict[str, Any] | None:
        nome = espacos(r["nome"])[:200]
        if not nome:
            return None
        atividades = sorted({a for a in (_fk(ctx, sistema, "atividade", pk, notas, "atividade")
                                         for pk in m2m.get((sistema, r["id"]), [])) if a})
        return {"nome": nome, "descricao": espacos(r.get("descricao"))[:255],
                "padrao": bool(r.get("is_padrao")), "ativo": bool(r.get("ativo", True)),
                "_m2m": {"atividades": atividades}}
    return valores


def tipo_os_do_nome(nome: str) -> tuple[str, str]:
    """(tipo_os, motivo) pela regra de `cadastros/0017.ligar_tipos`."""
    chave = " ".join(sem_acentos(nome).lower().replace("-", " ").split())
    if "operacao policial" in chave:
        return TipoViagem.TipoOS.OPERACAO_POLICIAL, MOTIVO_OPERACAO
    if "unidade movel" in chave:
        return TipoViagem.TipoOS.UNIDADE_MOVEL, ""
    if "cerimonial" in chave:
        return TipoViagem.TipoOS.CERIMONIAL, ""
    return "", ""


def _v_tipo_viagem(ctx: Contexto, sistema: str, r: dict,
                   notas: list[str]) -> dict[str, Any] | None:
    nome = espacos(r["nome"])[:120]
    if not nome:
        return None
    tipo_os, motivo = tipo_os_do_nome(nome)
    return {"nome": nome, "tipo_os": tipo_os, "motivo": motivo,
            "ativo": bool(r.get("ativo", True))}


def _v_modelo(tipo: str) -> Valores:
    def valores(ctx: Contexto, sistema: str, r: dict, notas: list[str]) -> dict[str, Any] | None:
        nome = espacos(r["nome"])[:120]
        if not nome or not (r.get("texto") or "").strip():
            notas.append("modelo de texto sem nome ou sem texto")
            return None
        return {"tipo": tipo, "nome": nome, "texto": r["texto"], "ordem": 100,
                "padrao": bool(r.get("is_padrao")), "padrao_sistema": False,
                "ativo": bool(r.get("ativo", True))}
    return valores


def _v_modelo_rt(ctx: Contexto, sistema: str, r: dict, notas: list[str]) -> dict[str, Any] | None:
    tipo = CAMPO_RT.get((r.get("campo") or "").strip().lower())
    nome = espacos(r.get("nome"))[:120]
    if tipo is None or not nome or not (r.get("texto") or "").strip():
        notas.append("texto do RT com campo desconhecido, sem nome ou sem texto")
        return None
    ordem = r.get("ordem")
    return {"tipo": tipo, "nome": nome, "texto": r["texto"],
            "ordem": min(max(int(ordem), 0), 32767) if ordem is not None else 100,
            "padrao": False, "padrao_sistema": False, "ativo": True}


def _k_modelo(vals: dict[str, Any]) -> list[Q]:
    return [Q(tipo=vals["tipo"], nome__iexact=vals["nome"])]


def _v_catalogo(com_texto: bool = False) -> Valores:
    def valores(ctx: Contexto, sistema: str, r: dict, notas: list[str]) -> dict[str, Any] | None:
        nome = espacos(r["nome"])[:150]
        if not nome:
            return None
        vals: dict[str, Any] = {"nome": nome, "ativo": bool(r.get("ativo", True))}
        if com_texto:
            vals["texto"] = r.get("texto") or ""
        return vals
    return valores


def _v_tipo_evento(ctx: Contexto, sistema: str, r: dict,
                   notas: list[str]) -> dict[str, Any] | None:
    nome = espacos(r["nome"])[:150]
    if not nome:
        return None
    orgao = r.get("orgao_padrao_id")
    orgao_id = (ctx.destino_int("ev", "cadastros_orgaoresponsavel", orgao)
                if orgao is not None else None)
    if orgao is not None and orgao_id is None:
        notas.append("órgão padrão sem correspondente")
    servicos = sorted({s for s in (
        ctx.destino_int("ev", "cadastros_servico", x["servico_id"])
        for x in _cache_tab(ctx, "ev", "cadastros_tipoevento_servicos_sugeridos")
        if x["tipoevento_id"] == r["id"]) if s})
    return {"nome": nome, "ativo": bool(r.get("ativo", True)),
            "solicitante_padrao": espacos(r.get("solicitante_padrao"))[:150],
            "cargo_padrao": espacos(r.get("cargo_padrao"))[:255],
            "orgao_padrao_id": orgao_id, "_m2m": {"servicos_sugeridos": servicos}}


def _v_tipo_evento_equipe(ctx: Contexto, sistema: str, r: dict,
                          notas: list[str]) -> dict[str, Any] | None:
    tipo = ctx.destino_int("ev", "cadastros_tipoevento", r["tipo_evento_id"])
    equipe = ctx.destino_int("ev", "cadastros_equipe", r["equipe_id"])
    if tipo is None or equipe is None:
        notas.append("equipe do modelo sem tipo de evento ou equipe correspondente")
        return None
    return {"tipo_evento_id": tipo, "equipe_id": equipe, "quantidade": r.get("quantidade")}


# Catálogos que as migrações do sistema novo semeiam: a semente sem correspondente no legado
# é inativada (nunca apagada).
CATALOGOS_SEMEADOS: tuple[type[models.Model], ...] = (
    AtividadePlano, ProgramaSolicitante, HorarioAtendimento, PresetAtividades, TipoViagem,
    ModeloTexto, Equipe, OrgaoResponsavel, UnidadeMovel, TextoDespacho, TipoEvento,
)


def _inativar_sementes(ctx: Contexto) -> None:
    """Só o que existia ANTES da migração (criado antes do primeiro mapa) e não ganhou
    correspondência; o que alguém cadastrar depois da carga nunca é tocado."""
    marco = MapaLegado.objects.aggregate(m=Min("criado_em"))["m"]
    if marco is None:
        return
    for modelo in CATALOGOS_SEMEADOS:
        rotulo = _rotulo(modelo)
        mapeados = set(MapaLegado.objects.filter(modelo=rotulo)
                       .values_list("destino_pk", flat=True))
        candidatos = modelo._default_manager.filter(ativo=True, criado_em__lt=marco)
        if _tem_campo(modelo, "padrao"):
            candidatos = candidatos.exclude(padrao=True)
        ids = [pk for pk in candidatos.values_list("pk", flat=True) if str(pk) not in mapeados]
        if ids:
            modelo._default_manager.filter(pk__in=ids).update(ativo=False)
            ctx.relatorio.conta(modelo.__name__.lower(), "semente_inativada", len(ids))
            for pk in ids:
                ctx.relatorio.revisar(modelo.__name__.lower(), "semente sem correspondente no "
                                      "legado: inativada", destino_pk=pk)


# ---------------------------------------------------------------------------- etapa
def executar(ctx: Contexto) -> None:
    if ctx.usuario_migracao is None:
        garantir_usuario_migracao(ctx)

    # 1. Municípios: só o mapa (a lista do IBGE já está no destino).
    _municipios(ctx)

    def carga(entidade: str, modelo: type[models.Model], chave: str | None,
              valores: Valores, chaves: Callable[[dict[str, Any]], list[Q]],
              **extra: Any) -> None:
        ev, gv = T[chave] if chave else (extra.pop("ev"), extra.pop("gv"))
        carregar(ctx, Carga(entidade, modelo, ev, gv, valores, chaves, **extra))

    # 2–4. Unidade, cargo, combustível.
    carga("unidade", Unidade, "unidade", _v_unidade, _k_nome)
    carga("cargo", Cargo, "cargo", _v_nome_padrao, _k_nome, escopo_padrao=())
    carga("combustivel", Combustivel, "combustivel", _v_nome_padrao, _k_nome, escopo_padrao=())
    # 5. Servidores.
    carga("servidor", Servidor, "servidor", _v_servidor, _k_servidor)
    # 6. Viaturas e motoristas habituais.
    carga("viatura", Viatura, "viatura", _v_viatura, lambda v: [Q(placa=v["placa"])])
    _motoristas(ctx)
    # 7. Tabela de diárias.
    carga("tabela_diaria", TabelaDiaria, "diaria", _v_diaria, _k_diaria)
    # 8. Usuários (papéis e lotação).
    _grupos_ev(ctx)
    _usuarios(ctx)
    # 9. Configuração institucional (+ assinaturas e substituições).
    carga("configuracao", ConfiguracaoInstitucional, "configuracao", _v_configuracao,
          lambda v: [Q(unidade_id=v["unidade_id"])],
          nao_validar=("chefia_nome", "chefia_cargo"),
          nao_comparar=("nome_extenso", "endereco_rodape", "delegado_geral_nome"))
    _mapear_assinaturas(ctx)
    carga("substituicao_assinante", SubstituicaoAssinante, None, _v_substituicao,
          lambda v: [Q(configuracao_id=v["configuracao_id"], servidor_id=v["servidor_id"],
                       tipo=v["tipo"], inicio=v["inicio"])],
          ev="viagens_cadastros_assinaturasubstituicao", gv=None)
    # 10. Catálogos do plano e da viagem.
    nomes_servico = {_ai(r["nome"]): espacos(r["nome"])
                     for r in _cache_tab(ctx, "ev", "cadastros_servico")}
    carga("atividade_plano", AtividadePlano, "atividade", _v_atividade(nomes_servico),
          _k_atividade, comparar=False)
    carga("servico_eventos", AtividadePlano, None, _v_servico, _k_atividade_nome,
          atualizar_ao_casar=("ativo",), ev="cadastros_servico", gv=None)
    carga("programa_solicitante", ProgramaSolicitante, "programa", _v_programa, _k_nome)
    carga("horario_atendimento", HorarioAtendimento, "horario", _v_horario, _k_nome)
    m2m_preset: dict[tuple[str, Any], list[Any]] = {}
    for sistema, tabela, col in (
            ("ev", "viagens_planos_presetatividadesplanotrabalho_atividades",
             "presetatividadesplanotrabalho_id"),
            ("gv", "planos_trabalho_presetatividadesplanotrabalho_atividades",
             "presetatividadesplanotrabalho_id")):
        for x in _cache_tab(ctx, sistema, tabela):
            m2m_preset.setdefault((sistema, x[col]), []).append(x["atividadeplanotrabalho_id"])
    carga("preset_atividades", PresetAtividades, "preset", _v_preset(m2m_preset), _k_nome,
          escopo_padrao=())
    carga("tipo_viagem", TipoViagem, "tipo_viagem", _v_tipo_viagem, _k_nome)
    carga("modelo_texto_motivo", ModeloTexto, "motivo", _v_modelo("motivo"), _k_modelo,
          escopo_padrao=("tipo",))
    carga("modelo_texto_justificativa", ModeloTexto, "justificativa",
          _v_modelo("justificativa"), _k_modelo, escopo_padrao=("tipo",))
    carga("modelo_texto_rt", ModeloTexto, None, _v_modelo_rt, _k_modelo,
          escopo_padrao=("tipo",), ev=None,
          gv="prestacoes_contas_modelotextorelatoriotecnico")
    # 11. Catálogos do Eventos Sociais (só no EV).
    carga("orgao_responsavel", OrgaoResponsavel, None, _v_catalogo(), _k_nome,
          atualizar_ao_casar=("ativo",), ev="cadastros_orgaoresponsavel", gv=None)
    carga("equipe", Equipe, None, _v_catalogo(), _k_nome, atualizar_ao_casar=("ativo",),
          ev="cadastros_equipe", gv=None)
    carga("unidade_movel", UnidadeMovel, None, _v_catalogo(), _k_nome,
          atualizar_ao_casar=("ativo",), ev="cadastros_unidademovel", gv=None)
    carga("texto_despacho", TextoDespacho, None, _v_catalogo(com_texto=True), _k_nome,
          atualizar_ao_casar=("ativo", "texto"), ev="cadastros_textodespacho", gv=None)
    carga("tipo_evento", TipoEvento, None, _v_tipo_evento, _k_nome,
          atualizar_ao_casar=("ativo", "solicitante_padrao", "cargo_padrao", "orgao_padrao_id",
                              "_m2m"),
          ev="cadastros_tipoevento", gv=None)
    carga("tipo_evento_equipe", TipoEventoEquipe, None, _v_tipo_evento_equipe,
          lambda v: [Q(tipo_evento_id=v["tipo_evento_id"], equipe_id=v["equipe_id"])],
          ev="cadastros_tipoeventoequipe", gv=None)
    # Sementes de catálogo sem correspondente no legado: inativas (nunca apagadas).
    _inativar_sementes(ctx)
