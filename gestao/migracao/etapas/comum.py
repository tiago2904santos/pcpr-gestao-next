"""Peças comuns às etapas de viagens e de prestação de contas.

* O EV (Eventos Sociais) é a base; ele já trouxe o GV (Gerenciador de Viagens) uma vez, em
  21/09/2026 — o `migracao_legado_registro` do EV diz qual linha do GV virou qual linha do EV e
  guarda a impressão digital (SHA-256) da linha do GV naquele momento. Recalcular a impressão
  da linha atual do GV diz, sem depender de `updated_at`, se ela mudou depois da carga.
* Um documento com os seus filhos (roteiro + trechos, ofício + equipe…) é um AGREGADO: monta-se
  o agregado dos dois lados, e o lado que vence (a edição mais recente) entra inteiro. O que
  perde vai para a conferência (só ids e nomes de campos — nunca valores).
* Arquivos: aqui só se grava a referência, endereçada pelo conteúdo:
  `legado/<ev|gv>/<2 primeiros do sha256>/<sha256>.<ext>` (cabe nos 100 caracteres do
  FileField; os caminhos do legado não cabem). A cópia dos binários (passo seguinte) percorre
  `--midia-ev`/`--midia-gv`, calcula o SHA-256 de cada arquivo e o copia para
  `MEDIA_ROOT/<esse nome>` — sem precisar de tabela de correspondência. O hash e o tamanho já
  saem do arquivo do backup; arquivo ausente do backup vai para a conferência.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from django.db import IntegrityError, models, transaction

from gestao.cadastros.models import ConfiguracaoInstitucional, Municipio
from gestao.cadastros.validacoes import espacos, sem_acentos

from ..contexto import Contexto
from .cadastros import T as T_CADASTROS

FUSO = ZoneInfo("America/Sao_Paulo")
# Momento da carga GV → EV (lote ef419af8…); lido do próprio EV quando a tabela existe.
LOTE_EV_PADRAO = datetime(2026, 9, 21, 0, 7, 45, 850881, tzinfo=UTC)

T_EXTRA = {
    "tipo_viagem": ("viagens_viagem_tipoviagem", "eventos_tipoevento"),
    "modelo_justificativa": ("viagens_oficios_modelojustificativa",
                             "justificativas_modelojustificativa"),
}


# ---------------------------------------------------------------------------- leitura
def tab(ctx: Contexto, sistema: str, nome: str | None) -> list[dict]:
    """Tabela inteira do legado (uma leitura por etapa)."""
    fonte = ctx.ev if sistema == "ev" else ctx.gv
    if fonte is None or not nome:
        return []
    chave = ("tabela", sistema, nome)
    if chave not in ctx.memo:
        ctx.memo[chave] = fonte.tabela(nome)
    return ctx.memo[chave]


def por_id(ctx: Contexto, sistema: str, nome: str | None) -> dict[str, dict]:
    chave = ("por_id", sistema, nome)
    if chave not in ctx.memo:
        ctx.memo[chave] = {str(r["id"]): r for r in tab(ctx, sistema, nome)}
    return ctx.memo[chave]


def agrupar(ctx: Contexto, sistema: str, nome: str | None, coluna: str) -> dict[str, list[dict]]:
    """Linhas de uma tabela agrupadas por uma coluna (ex.: trechos por roteiro), na ordem do id."""
    chave = ("agrupar", sistema, nome, coluna)
    if chave not in ctx.memo:
        grupos: dict[str, list[dict]] = {}
        for r in tab(ctx, sistema, nome):
            if r.get(coluna) is not None:
                grupos.setdefault(str(r[coluna]), []).append(r)
        ctx.memo[chave] = grupos
    return ctx.memo[chave]


def lote_ev(ctx: Contexto) -> datetime:
    if "lote_ev" not in ctx.memo:
        lotes = [r["criado_em"] for r in tab(ctx, "ev", "migracao_legado_lote")
                 if r.get("criado_em") and not r.get("desfeito_em")]
        ctx.memo["lote_ev"] = min(lotes) if lotes else LOTE_EV_PADRAO
    return ctx.memo["lote_ev"]


def fim_da_carga(ctx: Contexto) -> datetime:
    """Fim da carga GV → EV: o que o EV gravou até aqui foi a própria carga (filhos sem data no
    GV ganharam a hora da carga), não edição de alguém."""
    if "fim_da_carga" not in ctx.memo:
        fins = [r["concluida_em"] for r in tab(ctx, "ev", "migracao_legado_etapa")
                if r.get("concluida_em")]
        ctx.memo["fim_da_carga"] = max([lote_ev(ctx), *fins])
    return ctx.memo["fim_da_carga"]


def depois_da_carga(ctx: Contexto, *quando: datetime | None) -> bool:
    """Editado no EV depois da carga do GV."""
    fim = fim_da_carga(ctx)
    return any(q is not None and q > fim for q in quando)


# ---------------------------------------------------------------------------- registro do EV
def _valor_impressao(v: Any) -> Any:
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, datetime) and v.tzinfo is not None:
        return v.astimezone(UTC).isoformat()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def impressao(linha: dict) -> str:
    """A mesma impressão digital que a carga do EV gravou (jsonb como texto, decimais como
    texto, data/hora em ISO UTC, sem colunas de token)."""
    dados = {}
    for k, v in linha.items():
        if k in ("link_token", "link_token_hash"):
            continue
        dados[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, dict | list) else v
    texto = json.dumps(dados, default=_valor_impressao, sort_keys=True)
    return hashlib.sha256(texto.encode()).hexdigest()


def registro(ctx: Contexto, tabela_gv: str) -> dict[str, tuple[str, str]]:
    """GV origem_pk → (EV destino_pk, impressão da linha do GV na carga)."""
    chave = ("registro_fp", tabela_gv)
    if chave not in ctx.memo:
        ctx.memo[chave] = {str(r["origem_pk"]): (str(r["destino_pk"]), r.get("fingerprint") or "")
                           for r in tab(ctx, "ev", "migracao_legado_registro")
                           if r["tabela"] == tabela_gv}
    return ctx.memo[chave]


def inverso(ctx: Contexto, tabela_gv: str) -> dict[str, str]:
    """EV pk → GV pk (a linha do GV que o EV trouxe)."""
    chave = ("registro_inverso", tabela_gv)
    if chave not in ctx.memo:
        ctx.memo[chave] = {ev: gv for gv, (ev, _) in registro(ctx, tabela_gv).items()}
    return ctx.memo[chave]


def mudou_no_gv(ctx: Contexto, tabela_gv: str, linha: dict) -> bool:
    """Linha do GV ausente do registro, ou diferente do que o EV trouxe."""
    reg = registro(ctx, tabela_gv).get(str(linha["id"]))
    return reg is None or impressao(linha) != reg[1]


def pais_alterados_no_gv(ctx: Contexto, filho_gv: str, col_pai_gv: str, filho_ev: str,
                         col_pai_ev: str, pai_gv: str) -> set[str]:
    """Ids (GV) dos pais cujos filhos mudaram no GV depois da carga: filho novo, filho
    alterado ou filho apagado no GV (achado pelo pai da cópia no EV)."""
    chave = ("pais_alterados", filho_gv)
    if chave in ctx.memo:
        return ctx.memo[chave]
    pais: set[str] = set()
    atuais = por_id(ctx, "gv", filho_gv)
    for r in atuais.values():
        if r.get(col_pai_gv) is not None and mudou_no_gv(ctx, filho_gv, r):
            pais.add(str(r[col_pai_gv]))
    ev_filhos = por_id(ctx, "ev", filho_ev)
    pai_inv = inverso(ctx, pai_gv)
    for gv_pk, (ev_pk, _) in registro(ctx, filho_gv).items():
        if gv_pk in atuais:
            continue
        ev_linha = ev_filhos.get(ev_pk)
        if ev_linha is not None and ev_linha.get(col_pai_ev) is not None:
            gv_pai = pai_inv.get(str(ev_linha[col_pai_ev]))
            if gv_pai is not None:
                pais.add(gv_pai)
    ctx.memo[chave] = pais
    return pais


def json_legado(valor: Any) -> Any:
    """Coluna jsonb do legado. A carga do EV gravou o JSON do GV como STRING JSON (dupla
    codificação): decodifica até chegar ao valor."""
    for _ in range(3):
        if not isinstance(valor, str):
            return valor
        try:
            valor = json.loads(valor)
        except ValueError:
            return valor
    return valor


# ---------------------------------------------------------------------------- mapas
def tabela_de(entidade: str, sistema: str) -> str:
    par = T_EXTRA.get(entidade) or T_CADASTROS[entidade]
    return par[0 if sistema == "ev" else 1]


def fk(ctx: Contexto, sistema: str, entidade: str, pk: Any, notas: list[str] | None = None,
       campo: str = "") -> int | None:
    if pk is None:
        return None
    tabela = tabela_de(entidade, sistema)
    alvo = ctx.destino_int(sistema, tabela, pk)
    if alvo is None and notas is not None:
        notas.append(f"{campo or entidade}: referência sem correspondente ({tabela}:{pk})")
    return alvo


def usuario(ctx: Contexto, sistema: str, pk: Any) -> int:
    """Autor do legado → usuário novo; sem correspondente, o usuário técnico da migração."""
    alvo = fk(ctx, sistema, "usuario", pk) if pk is not None else None
    if alvo is not None:
        return alvo
    return ctx.usuario_migracao.pk


def municipio_por_nome(ctx: Contexto, nome: Any, uf: Any) -> int | None:
    """Destino em texto ({cidade, uf}) → município, por nome sem acento + UF."""
    if "municipios_nome" not in ctx.memo:
        ctx.memo["municipios_nome"] = {
            (sem_acentos(espacos(n)).lower(), u.upper()): pk
            for pk, n, u in Municipio.objects.values_list("pk", "nome", "uf")}
    return ctx.memo["municipios_nome"].get(
        (sem_acentos(espacos(str(nome or ""))).lower(), espacos(str(uf or "")).upper()))


def configuracao(ctx: Contexto) -> ConfiguracaoInstitucional:
    """A unidade emissora e a sede padrão (o legado não tem unidade nos documentos)."""
    if "configuracao" not in ctx.memo:
        conf = ConfiguracaoInstitucional.objects.order_by("pk").first()
        if conf is None:
            raise RuntimeError("Sem configuração institucional: rode a etapa de cadastros antes.")
        ctx.memo["configuracao"] = conf
    return ctx.memo["configuracao"]


def aware(data: date | None, hora: time | None) -> datetime | None:
    """Par data + hora ingênuos do legado (horário de Brasília) → instante."""
    if data is None:
        return None
    return datetime.combine(data, hora or time(0, 0), tzinfo=FUSO)


def data_local(quando: datetime | None) -> date | None:
    return quando.astimezone(FUSO).date() if quando is not None else None


def datas(linha: dict) -> tuple[datetime | None, datetime | None]:
    criado = linha.get("criado_em") or linha.get("created_at")
    atualizado = linha.get("atualizado_em") or linha.get("updated_at") or criado
    return criado, atualizado


def texto(valor: Any, limite: int | None = None) -> str:
    t = str(valor or "").strip()
    return t[:limite] if limite else t


# ---------------------------------------------------------------------------- arquivos
@dataclass
class Arquivo:
    nome: str            # o que vai no FileField ("" se o arquivo não está no backup)
    sha256: str
    tamanho: int
    existe: bool
    origem: str = ""     # caminho no media do sistema antigo


def caminho_no_backup(raiz: Path | None, relativo: str) -> Path | None:
    if raiz is None:
        return None
    for base in (raiz, raiz / "media"):
        p = base / relativo
        if p.is_file():
            return p
    return None


def arquivo(ctx: Contexto, sistema: str, relativo: str | None, *, entidade: str,
            tabela: str, origem_pk: Any) -> Arquivo | None:
    """Referência ao arquivo do legado. None se o caminho está vazio. Arquivo ausente do backup
    vai para a conferência (o chamador decide se a linha entra sem o binário)."""
    relativo = (relativo or "").strip().lstrip("/")
    if not relativo:
        return None
    chave = ("arquivo", sistema, relativo)
    if chave in ctx.memo:
        return ctx.memo[chave]
    raiz = ctx.midia_ev if sistema == "ev" else ctx.midia_gv
    origem = f"{sistema}:{relativo}"
    p = caminho_no_backup(raiz, relativo)
    if p is None:
        res = Arquivo(nome="", sha256="", tamanho=0, existe=False, origem=relativo)
        ctx.relatorio.conta("arquivo", "ausente_no_backup")
        ctx.relatorio.revisar(entidade, "arquivo referenciado não existe no backup",
                              sistema=sistema, tabela=tabela, origem_pk=str(origem_pk),
                              arquivo=origem)
    else:
        h = hashlib.sha256()
        with p.open("rb") as f:
            for bloco in iter(lambda: f.read(1 << 20), b""):
                h.update(bloco)
        sha = h.hexdigest()
        ext = Path(relativo).suffix.lower()[:8]
        res = Arquivo(nome=f"legado/{sistema}/{sha[:2]}/{sha}{ext}", sha256=sha,
                      tamanho=p.stat().st_size, existe=True, origem=relativo)
        ctx.relatorio.conta("arquivo", "conferido")
        # Cópia do GV no EV: o nome é o SHA-256 do conteúdo.
        base = Path(relativo).stem
        if relativo.startswith("legado/") and len(base) == 64 and base != res.sha256:
            ctx.relatorio.revisar(entidade, "o conteúdo não bate com o SHA-256 do nome",
                                  sistema=sistema, tabela=tabela, origem_pk=str(origem_pk),
                                  arquivo=origem)
    ctx.memo[chave] = res
    return res


# ---------------------------------------------------------------------------- agregados
@dataclass
class Agregado:
    """Um documento e os seus filhos, já traduzidos para ids do destino."""

    campos: dict[str, Any]
    filhos: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    m2m: dict[str, list[int]] = field(default_factory=dict)
    notas: list[str] = field(default_factory=list)
    quando: datetime | None = None          # última edição (decide quem vence)
    extra: dict[str, Any] = field(default_factory=dict)  # dados para o `criar`


def _sem_internos(linhas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in linhas]


def diferencas(a: Agregado, b: Agregado, ignorar: Iterable[str] = ()) -> list[str]:
    fora = set(ignorar)
    campos = sorted(k for k in set(a.campos) | set(b.campos)
                    if k not in fora and a.campos.get(k) != b.campos.get(k))
    filhos = sorted(k for k in set(a.filhos) | set(b.filhos)
                    if k not in fora and _sem_internos(a.filhos.get(k, []))
                    != _sem_internos(b.filhos.get(k, [])))
    m2m = sorted(k for k in set(a.m2m) | set(b.m2m)
                 if k not in fora and sorted(a.m2m.get(k, [])) != sorted(b.m2m.get(k, [])))
    return campos + filhos + m2m


@dataclass
class Carga:
    """Uma entidade raiz (EV e GV) → um modelo do destino, por agregados."""

    entidade: str
    modelo: type[models.Model]
    ev: str
    gv: str | None
    construir: Callable[[Contexto, str, dict], Agregado | None]
    criar: Callable[[Contexto, str, dict, Agregado], models.Model | None]
    # O GV mudou o agregado depois da carga (além da própria linha): filhos, M2M…
    gv_alterado: Callable[[Contexto, dict], bool] | None = None
    ev_alterado: Callable[[Contexto, dict], bool] | None = None
    # Linha só do GV que já existe no destino por chave natural (devolve o objeto).
    chave_natural: Callable[[Contexto, dict, Agregado], models.Model | None] | None = None
    # Casou por chave natural com uma linha que já está no destino: junta as duas versões.
    fundir: Callable[[Contexto, models.Model, dict, Agregado], None] | None = None
    ignorar_na_comparacao: tuple[str, ...] = ()
    # Campo vazio do lado que venceu é preenchido com o do outro ("vazio não apaga").
    preencher_vazios: bool = False
    # Entidade "raiz" (viagem, documento…): linha do GV apagada no EV vai à conferência.
    conferir_apagados: bool = True


def executar_carga(ctx: Contexto, c: Carga) -> None:
    rel = ctx.relatorio
    ctx.precarregar("ev", c.ev)
    inv = inverso(ctx, c.gv) if c.gv else {}
    gv_linhas = por_id(ctx, "gv", c.gv) if c.gv and ctx.gv is not None else {}
    if c.gv:
        ctx.precarregar("gv", c.gv)
    pares_agora: set[str] = set()     # linhas do GV mapeadas junto com o par do EV, agora
    for linha in tab(ctx, "ev", c.ev):
        pk = str(linha["id"])
        gv_pk = inv.get(pk)
        gv_linha = gv_linhas.get(gv_pk) if gv_pk else None
        if ctx.destino("ev", c.ev, pk) is not None:
            rel.conta(c.entidade, "ja_mapeado")
            continue
        ag_ev = c.construir(ctx, "ev", linha)
        if ag_ev is None:
            continue
        sistema, origem, ag = "ev", linha, ag_ev
        if gv_linha is not None:
            sistema, origem, ag = _decidir(ctx, c, linha, ag_ev, gv_linha)
        obj = _criar(ctx, c, sistema, origem, ag)
        if obj is None:
            continue
        rel.conta(c.entidade, "criado")
        ctx.mapear("ev", c.ev, pk, obj, criado=sistema == "ev")
        if gv_linha is not None and c.gv:
            ctx.mapear("gv", c.gv, gv_linha["id"], obj, criado=sistema == "gv")
            pares_agora.add(str(gv_linha["id"]))
            rel.conta(c.entidade, "mapeado_pelo_registro_ev")
    if not c.gv or ctx.gv is None:
        return
    reg = registro(ctx, c.gv)
    ev_ids = por_id(ctx, "ev", c.ev)
    for linha in gv_linhas.values():
        pk = str(linha["id"])
        if pk in pares_agora:
            continue
        if ctx.destino("gv", c.gv, pk) is not None:
            rel.conta(c.entidade, "ja_mapeado")
            continue
        if pk in reg:
            ev_pk = reg[pk][0]
            alvo = ctx.destino("ev", c.ev, ev_pk)
            if alvo is not None:
                ctx.mapear("gv", c.gv, pk, c.modelo._default_manager.get(pk=alvo),
                           criado=False)
                rel.conta(c.entidade, "mapeado_pelo_registro_ev")
            elif ev_pk not in ev_ids:
                # Apagado no EV depois da carga: não se ressuscita pelo GV.
                rel.conta(c.entidade, "apagado_no_ev_nao_recriado")
                if c.conferir_apagados:
                    rel.revisar(c.entidade, "apagado no EV depois da carga do GV: não recriado",
                                sistema="gv", tabela=c.gv, origem_pk=pk, ev_pk=ev_pk)
            else:
                rel.conta(c.entidade, "ignorado")
                rel.revisar(c.entidade, "a cópia do EV não entrou no destino; o GV não a "
                            "substitui", sistema="gv", tabela=c.gv, origem_pk=pk, ev_pk=ev_pk)
            continue
        ag_so_gv = c.construir(ctx, "gv", linha)
        if ag_so_gv is None:
            continue
        ag = ag_so_gv
        existente = c.chave_natural(ctx, linha, ag) if c.chave_natural else None
        if existente is not None:
            ctx.mapear("gv", c.gv, pk, existente, criado=False)
            rel.conta(c.entidade, "casado_por_chave")
            if c.fundir is not None:
                c.fundir(ctx, existente, linha, ag)
            continue
        obj = _criar(ctx, c, "gv", linha, ag)
        if obj is not None:
            ctx.mapear("gv", c.gv, pk, obj, criado=True)
            rel.conta(c.entidade, "criado_so_no_gv")


def _decidir(ctx: Contexto, c: Carga, ev_linha: dict, ag_ev: Agregado,
             gv_linha: dict) -> tuple[str, dict, Agregado]:
    """Mesma linha nos dois sistemas: vale a edição mais recente; a outra vai à conferência."""
    ag_gv = c.construir(ctx, "gv", gv_linha)
    if ag_gv is None:
        return "ev", ev_linha, ag_ev
    campos = diferencas(ag_ev, ag_gv, c.ignorar_na_comparacao)
    if not campos:
        return "ev", ev_linha, ag_ev
    gv_mudou = (mudou_no_gv(ctx, c.gv or "", gv_linha)
                or bool(c.gv_alterado and c.gv_alterado(ctx, gv_linha))
                or any(sorted(ag_ev.m2m.get(k, [])) != sorted(ag_gv.m2m.get(k, []))
                       for k in set(ag_ev.m2m) | set(ag_gv.m2m)))
    ev_mudou = (depois_da_carga(ctx, datas(ev_linha)[1])
                or bool(c.ev_alterado and c.ev_alterado(ctx, ev_linha)))
    ids = {"ev_pk": ev_linha["id"], "gv_pk": gv_linha["id"]}
    sistema, linha, ag = _vencedor(ctx, c, ev_linha, ag_ev, gv_linha, ag_gv, campos, gv_mudou,
                                   ev_mudou, ids)
    if c.preencher_vazios:
        outro = ag_gv if ag is ag_ev else ag_ev
        preencher_vazios(ag, outro)
    return sistema, linha, ag


def vazio(v: Any) -> bool:
    return v is None or v == "" or v == {} or v == []


def preencher_vazios(ag: Agregado, outro: Agregado) -> list[str]:
    """Vazio não apaga preenchido: campos do agregado e dos filhos com "ordem" (linhas do
    diário…) que ficaram vazios na versão que valeu recebem o valor da outra."""
    preenchidos = [k for k, v in ag.campos.items()
                   if vazio(v) and not vazio(outro.campos.get(k))]
    for k in preenchidos:
        ag.campos[k] = outro.campos[k]
    for nome, linhas in ag.filhos.items():
        outras = {r.get("ordem"): r for r in outro.filhos.get(nome, []) if "ordem" in r}
        for r in linhas:
            par = outras.get(r.get("ordem"))
            if par is None:
                continue
            for k, v in list(r.items()):
                if not k.startswith("_") and vazio(v) and not vazio(par.get(k)):
                    r[k] = par[k]
                    preenchidos.append(f"{nome}.{k}")
    if preenchidos:
        ag.notas.append("campos vazios na versão que valeu preenchidos com a outra: "
                        + ", ".join(sorted(set(preenchidos))))
    return preenchidos


def _vencedor(ctx: Contexto, c: Carga, ev_linha: dict, ag_ev: Agregado, gv_linha: dict,
              ag_gv: Agregado, campos: list[str], gv_mudou: bool, ev_mudou: bool,
              ids: dict[str, Any]) -> tuple[str, dict, Agregado]:
    rel = ctx.relatorio
    if gv_mudou and ev_mudou:
        q_ev, q_gv = ag_ev.quando or datas(ev_linha)[1], ag_gv.quando or datas(gv_linha)[1]
        gv_vence = bool(q_ev and q_gv and q_gv > q_ev)
        rel.conta(c.entidade, "editado_nos_dois")
        vencedor, outro = ("GV", "EV") if gv_vence else ("EV", "GV")
        rel.revisar(c.entidade, f"editado nos dois sistemas: valeu o {vencedor} (edição mais "
                    f"recente); conferir a versão do {outro}", campos=campos, **ids)
        return ("gv", gv_linha, ag_gv) if gv_vence else ("ev", ev_linha, ag_ev)
    if gv_mudou:
        rel.conta(c.entidade, "versao_do_gv_mais_recente")
        return "gv", gv_linha, ag_gv
    if not ev_mudou:
        # Diferença sem edição registrada em nenhum lado (tradução da carga do EV): vale o EV.
        rel.conta(c.entidade, "diferenca_sem_edicao")
        rel.revisar(c.entidade, "EV e GV diferem sem edição registrada depois da carga: "
                    "valeu o EV", campos=campos, **ids)
    return "ev", ev_linha, ag_ev


def _criar(ctx: Contexto, c: Carga, sistema: str, linha: dict,
           ag: Agregado) -> models.Model | None:
    rel = ctx.relatorio
    tabela = c.ev if sistema == "ev" else c.gv
    try:
        with transaction.atomic():
            obj = c.criar(ctx, sistema, linha, ag)
    except IntegrityError as erro:
        rel.conta(c.entidade, "invalido")
        rel.revisar(c.entidade, "restrição do banco recusou o registro",
                    sistema=sistema, tabela=tabela, origem_pk=linha["id"],
                    restricao=_restricao(erro))
        return None
    if obj is None:
        rel.conta(c.entidade, "ignorado")
        rel.revisar(c.entidade, "; ".join(ag.notas) or "registro ignorado", sistema=sistema,
                    tabela=tabela, origem_pk=linha["id"])
        return None
    for nota in ag.notas:
        rel.revisar(c.entidade, nota, sistema=sistema, tabela=tabela, origem_pk=linha["id"],
                    destino_pk=obj.pk)
    return obj


def _restricao(erro: Exception) -> str:
    causa = getattr(erro, "__cause__", None)
    diag = getattr(causa, "diag", None)
    return getattr(diag, "constraint_name", None) or type(causa or erro).__name__


def preservar_datas(modelo: type[models.Model], pk: Any, **datas_: datetime | None) -> None:
    """auto_now/auto_now_add: grava as datas do legado depois de criar."""
    valores = {k: v for k, v in datas_.items() if v is not None}
    if valores:
        modelo._default_manager.filter(pk=pk).update(**valores)


def criar_filhos(modelo: type[models.Model], dono: dict[str, Any],
                 linhas: list[dict[str, Any]], ctx: Contexto | None = None) -> list[Any]:
    """Cria filhos simples; `_origem` = [(sistema, tabela, pk)] a mapear para cada um;
    `_datas` = datas do legado a preservar; `_m2m` = {campo: ids}."""
    objs = []
    for r in linhas:
        campos = {k: v for k, v in r.items() if not k.startswith("_")}
        obj = modelo._default_manager.create(**dono, **campos)
        for nome, ids in r.get("_m2m", {}).items():
            if ids:
                getattr(obj, nome).add(*ids)
        if r.get("_datas"):
            preservar_datas(modelo, obj.pk, **r["_datas"])
        if ctx is not None:
            for sistema, tabela, pk in r.get("_origem", []):
                if ctx.destino(sistema, tabela, pk) is None:
                    ctx.mapear(sistema, tabela, pk, obj, criado=True)
        objs.append(obj)
    return objs


def mais_recente(*quando: datetime | None) -> datetime | None:
    validos = [q for q in quando if q is not None]
    return max(validos) if validos else None


# ---------------------------------------------------------------------------- vias assinadas
MOTIVO_SUBSTITUIDA = "Substituída no sistema anterior"


def inserir_via(ctx: Contexto, entidade: str, *, dono: dict[str, Any], arq: Arquivo | None,
                nome_original: str, enviado_em: datetime | None, enviado_por_id: int,
                origem: list[tuple[str, str, Any]], revogada_em: datetime | None = None,
                documento_id: int | None = None) -> Any:
    """Uma via assinada (ofício, justificativa, termo, OS). Mesmo arquivo (SHA-256) do mesmo
    documento = a mesma via; arquivo diferente = versão nova: só a mais recente fica em vigor,
    as outras ficam revogadas ("Substituída no sistema anterior")."""
    from gestao.viagens.models import ViaAssinada

    rel = ctx.relatorio
    for sistema, tabela, pk in origem:
        alvo = ctx.destino(sistema, tabela, pk)
        if alvo is not None:
            rel.conta(entidade, "ja_mapeado")
            return ViaAssinada.objects.get(pk=alvo)
    if arq is None or not arq.existe:
        rel.conta(entidade, "sem_arquivo_no_backup")
        return None
    dono = {"chave": "", "oficio_id": None, "termo_id": None, "ordem_id": None, **dono}
    mesma = ViaAssinada.objects.filter(**dono, sha256=arq.sha256).order_by("pk").first()
    if mesma is not None:
        for sistema, tabela, pk in origem:
            ctx.mapear(sistema, tabela, pk, mesma, criado=False)
        rel.conta(entidade, "mesmo_arquivo_de_outra_via")
        return mesma
    tecnico = ctx.usuario_migracao.pk
    motivo = MOTIVO_SUBSTITUIDA if revogada_em is not None else ""
    vigente = ViaAssinada.objects.filter(**dono, revogada_em__isnull=True).first()
    if revogada_em is None and vigente is not None:
        if enviado_em is not None and vigente.enviado_em > enviado_em:
            revogada_em, motivo = vigente.enviado_em, MOTIVO_SUBSTITUIDA
        else:
            ViaAssinada.objects.filter(pk=vigente.pk).update(
                revogada_em=enviado_em or vigente.enviado_em, revogada_por_id=tecnico,
                motivo_revogacao=MOTIVO_SUBSTITUIDA)
            rel.conta(entidade, "via_anterior_revogada")
    via = ViaAssinada.objects.create(
        **dono, documento_id=documento_id, arquivo=arq.nome, nome_original=nome_original[:255],
        sha256=arq.sha256, tamanho=arq.tamanho, conferencia={}, impressao_dos_dados="",
        enviado_por_id=enviado_por_id, revogada_em=revogada_em,
        revogada_por_id=tecnico if revogada_em is not None else None,
        motivo_revogacao=motivo)
    preservar_datas(ViaAssinada, via.pk, enviado_em=enviado_em)
    for sistema, tabela, pk in origem:
        ctx.mapear(sistema, tabela, pk, via, criado=True)
    rel.conta(entidade, "criado" if revogada_em is None else "criado_revogada")
    return via


def destino_com_modelo(sistema: str, tabela: str, pk: Any) -> tuple[str, int] | None:
    """(rótulo do modelo, pk) do destino de uma linha já mapeada."""
    from ..models import MapaLegado

    par = (MapaLegado.objects.filter(sistema=sistema, tabela=tabela, origem_pk=str(pk))
           .values_list("modelo", "destino_pk").first())
    return (par[0], int(par[1])) if par else None
