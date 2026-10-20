"""Correção pontual de um ofício já migrado: a versão do GV entra por cima da que valeu na carga.

Caso de uso: o ofício foi emitido no Gerenciador de Viagens (GV), mas a cópia em rascunho do
Eventos Sociais (EV), editada depois, venceu pela regra "a edição mais recente vale". A regra da
etapa já foi corrigida (`Carga.emitido`); aqui se corrige um ofício que já está em produção, sem
recarregar nada. Dois passos, porque a produção não tem acesso aos bancos antigos:

1. LOCAL, com as fontes à mão (`exportar_oficio_legado`): monta o agregado do GV com o próprio
   código da etapa (`viagens._construir_oficio`, tradução pelo `MapaLegado`), escolhe os PDFs
   como a etapa escolhe (`viagens.documentos_escolhidos`) e grava um JSON com os ids do destino
   e os valores — fora do Git: ele tem dados pessoais — mais a lista dos arquivos de mídia, que
   são copiados com o nome endereçado pelo conteúdo (`legado/gv/<sha[:2]>/<sha>.pdf`).
2. PRODUÇÃO (`corrigir_oficio_legado --arquivo <json> [--gravar]`): confere que o ofício alvo
   continua como na exportação (número, situação, versão, última alteração e quantos filhos),
   que todos os ids citados existem e que os PDFs estão no MEDIA_ROOT com o SHA-256 certo; e
   aplica numa transação só, sob o contexto de auditoria do usuário técnico "migracao": os
   campos, a equipe e os trechos do GV, a versão emitida (situação + emitido_em), os
   `Documento`s apontando para os PDFs do GV, o mapa da migração e uma linha no histórico.
   Sem `--gravar`, tudo roda e é desfeito no fim (ensaio). Aplicar de novo não faz nada.

Nada de dado pessoal na saída: só ids, nomes de campos e contagens.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from django.apps import apps
from django.core.files.storage import default_storage
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.utils import timezone

from gestao.plataforma import auditoria
from gestao.viagens.models import Documento, Historico, Oficio, Trecho, Viajante

from .contexto import Contexto
from .etapas import viagens
from .etapas.cadastros import LOGIN_MIGRACAO
from .etapas.comum import FUSO, datas, por_id
from .models import MapaLegado

FORMATO = 1
# Campos do agregado que a correção não troca: o número é o do alvo (conferido) e a versão é a
# da concorrência otimista do sistema novo (sobe 1).
FORA = ("ano", "numero", "versao")
CAMPOS_VIAJANTE = ("servidor_id", "motorista", "ordem")
CAMPOS_TRECHO = ("ordem", "origem_id", "destino_id", "saida_em", "chegada_em", "distancia_km",
                 "tempo_viagem_min", "tempo_adicional_min")
ESTADO_LEGADO = {"FINALIZADO": "finalizada", "GERADO": "gerada", "ARQUIVADO": "arquivada"}


class CorrecaoRecusada(Exception):
    """O alvo mudou, falta um id ou um arquivo: nada é gravado."""


# ============================================================================ exportação (local)
def exportar(ctx: Contexto, gv_pk: int | str) -> dict[str, Any]:
    """O agregado do ofício `gv_pk` do GV, traduzido para o destino, pronto para o JSON."""
    t_oficio = viagens.t("oficio", "gv")
    linha = por_id(ctx, "gv", t_oficio).get(str(gv_pk))
    if linha is None:
        raise CorrecaoRecusada(f"ofício {gv_pk} não existe no GV")
    alvo_pk = ctx.destino_int("gv", t_oficio, gv_pk)
    if alvo_pk is None:
        raise CorrecaoRecusada(f"ofício {gv_pk} do GV sem correspondente no destino")
    alvo = Oficio.objects.get(pk=alvo_pk)
    ag = viagens._construir_oficio(ctx, "gv", linha)
    if ag is None:
        raise CorrecaoRecusada("o agregado do GV não pôde ser montado")
    if (ag.campos["ano"], ag.campos["numero"]) != (alvo.ano, alvo.numero):
        raise CorrecaoRecusada("o número do ofício no GV difere do alvo")
    status = str(ag.extra.get("status") or "")
    emitido = ag.campos["situacao"] == Oficio.Situacao.EMITIDO
    documentos = []
    midia = []
    for tipo, s, a, versao in viagens.documentos_escolhidos(ctx, alvo.pk, emitido):
        tabela = viagens.t("artefato", s)
        if ctx.destino(s, tabela, a["id"]) is not None:
            raise CorrecaoRecusada(f"PDF {s}:{a['id']} já mapeado para outro registro")
        campos, arq = viagens.campos_documento(ctx, alvo.numero, tipo, s, a, versao)
        if arq is None or not arq.existe:
            raise CorrecaoRecusada(f"PDF {s}:{a['id']} ausente do backup")
        raiz = ctx.midia_gv if s == "gv" else ctx.midia_ev
        documentos.append({"campos": campos, "origem": [s, tabela, str(a["id"])]})
        midia.append({"sistema": s, "origem": arq.origem, "raiz": str(raiz),
                      "destino": arq.nome, "sha256": arq.sha256, "tamanho": arq.tamanho})
    ev_pk = viagens._par(ctx, "oficio", "gv", gv_pk)[0]
    quando = datas(linha)[1]
    estado = ESTADO_LEGADO.get(status.upper(), "emitida")
    descricao = (f"Corrigido para a versão emitida no Gerenciador de Viagens ({estado} em "
                 f"{quando.astimezone(FUSO):%d/%m/%Y}); a cópia em rascunho do Eventos Sociais, "
                 "editada depois, não era o documento real." if quando else
                 "Corrigido para a versão emitida no Gerenciador de Viagens; a cópia em rascunho "
                 "do Eventos Sociais, editada depois, não era o documento real.")
    campos = {k: v for k, v in ag.campos.items() if k not in FORA}
    viajantes = [{k: r[k] for k in CAMPOS_VIAJANTE} for r in ag.filhos["viajantes"]]
    trechos = [{k: r[k] for k in CAMPOS_TRECHO} for r in ag.filhos["trechos"]]
    chave = f"correcao-oficio-{alvo.numero}"
    return {
        "formato": FORMATO, "chave": chave, "exportado_em": timezone.now(),
        "origem": {"sistema": "gv", "tabela": t_oficio, "pk": str(gv_pk),
                   "ev_tabela": viagens.t("oficio", "ev"), "ev_pk": ev_pk,
                   "status_legado": status},
        "alvo": _estado(alvo),
        "campos": campos, "viajantes": viajantes, "trechos": trechos,
        "documentos": documentos, "midia": midia,
        "referencias": _referencias(campos, viajantes, trechos, documentos),
        "historico": {"descricao": descricao[:300]},
        "conferir": _conferir_roteiro(ctx, linha, trechos) + list(ag.notas),
    }


def _estado(o: Oficio) -> dict[str, Any]:
    """O que precisa continuar igual entre a exportação e a aplicação."""
    return {"id": o.pk, "ano": o.ano, "numero": o.numero, "situacao": o.situacao,
            "versao": o.versao, "atualizado_em": o.atualizado_em,
            "viajantes": o.viajantes.count(), "trechos": o.trechos.count(),
            "documentos": o.documentos.count()}


def _referencias(campos: dict[str, Any], viajantes: list[dict], trechos: list[dict],
                 documentos: list[dict]) -> dict[str, list[int]]:
    """{rótulo do modelo: ids} de tudo o que a correção vai apontar (inclui o cargo de cada
    servidor da equipe, que o documento imprime)."""
    refs: dict[str, set[int]] = {}

    def juntar(modelo: type[models.Model], nome: str, valor: Any) -> None:
        if valor is None:
            return
        campo = modelo._meta.get_field(nome)
        if campo.is_relation and campo.related_model is not None:
            rel = campo.related_model
            refs.setdefault(rel._meta.label, set()).add(int(valor))

    for k, v in campos.items():
        juntar(Oficio, k, v)
    for r in viajantes:
        juntar(Viajante, "servidor_id", r["servidor_id"])
    for r in trechos:
        juntar(Trecho, "origem_id", r["origem_id"])
        juntar(Trecho, "destino_id", r["destino_id"])
    for d in documentos:
        juntar(Documento, "emitido_por_id", d["campos"]["emitido_por_id"])
    from gestao.cadastros.models import Servidor

    servidores = refs.get(Servidor._meta.label, set())
    cargos = {c for c in Servidor.objects.filter(pk__in=servidores)
              .values_list("cargo_id", flat=True) if c is not None}
    if cargos:
        refs.setdefault("cadastros.Cargo", set()).update(cargos)
    return {k: sorted(v) for k, v in sorted(refs.items())}


def _conferir_roteiro(ctx: Contexto, linha: dict, trechos: list[dict]) -> list[str]:
    """Os trechos do ofício vêm do roteiro do destino (como na etapa); avisa se eles diferem dos
    trechos do roteiro do GV (só o aviso, sem valores)."""
    if linha.get("roteiro_id") is None:
        return []
    notas: list[str] = []
    do_gv = viagens._trechos_legado(ctx, "trecho", "gv", linha["roteiro_id"], notas)
    iguais = [{k: r[k] for k in CAMPOS_TRECHO} for r in do_gv] == trechos
    return [] if iguais else ["trechos do roteiro do destino diferem dos do roteiro do GV"]


def copiar_midia(dados: dict[str, Any], saida: Path) -> list[Path]:
    """Copia os PDFs para `saida/<nome endereçado pelo conteúdo>`, conferindo o SHA-256."""
    copiados = []
    for m in dados["midia"]:
        origem = Path(m["raiz"]) / m["origem"]
        if not origem.is_file():
            origem = Path(m["raiz"]) / "media" / m["origem"]
        destino = saida / m["destino"]
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem, destino)
        if _sha256(destino.read_bytes()) != m["sha256"]:
            raise CorrecaoRecusada(f"cópia de {m['destino']} com SHA-256 diferente")
        copiados.append(destino)
    return copiados


def _sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


class _Codificador(DjangoJSONEncoder):
    """Como o do Django, mas sem cortar os microssegundos (a conferência do alvo compara a
    última alteração exata, e as datas do legado entram como estavam)."""

    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def serializar(dados: dict[str, Any]) -> str:
    return json.dumps(dados, cls=_Codificador, ensure_ascii=False, indent=2, sort_keys=True)


# ============================================================================ aplicação (produção)
@dataclass
class Plano:
    alvo: Oficio
    ja_aplicada: bool = False
    antes: dict[str, int] = field(default_factory=dict)        # filhos do alvo antes
    campos: dict[str, Any] = field(default_factory=dict)       # valores já convertidos
    mudam: list[str] = field(default_factory=list)             # nomes de campos
    viajantes: list[dict[str, Any]] = field(default_factory=list)
    trechos: list[dict[str, Any]] = field(default_factory=list)
    filhos_mudam: list[str] = field(default_factory=list)
    documentos: list[dict[str, Any]] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)          # recusam o --gravar


def _campo(modelo: type[models.Model], nome: str) -> models.Field:
    campo = modelo._meta.get_field(nome)
    if not isinstance(campo, models.Field):
        raise CorrecaoRecusada(f"{modelo.__name__}.{nome} não é um campo")
    return campo


def _converter(modelo: type[models.Model], valores: dict[str, Any]) -> dict[str, Any]:
    """Valores do JSON (texto ISO, decimais em texto…) → valores do campo."""
    return {k: _campo(modelo, k).to_python(v) for k, v in valores.items()}


def _linhas(qs: Any, campos: tuple[str, ...]) -> list[dict[str, Any]]:
    return [dict(zip(campos, r, strict=True)) for r in qs.values_list(*campos)]


def planejar(dados: dict[str, Any]) -> Plano:
    """Confere o JSON contra o banco e diz o que muda. Não grava nada."""
    if dados.get("formato") != FORMATO:
        raise CorrecaoRecusada(f"formato do arquivo desconhecido ({dados.get('formato')})")
    esperado = dados["alvo"]
    alvo = Oficio.objects.select_for_update().filter(pk=esperado["id"]).first()
    if alvo is None:
        raise CorrecaoRecusada(f"ofício {esperado['id']} não existe")
    plano = Plano(alvo=alvo, antes={"viajantes": alvo.viajantes.count(),
                                    "trechos": alvo.trechos.count()})
    plano.campos = _converter(Oficio, dados["campos"])
    plano.viajantes = [_converter(Viajante, r) for r in dados["viajantes"]]
    plano.trechos = [_converter(Trecho, r) for r in dados["trechos"]]
    plano.documentos = [{**d, "campos": _converter(Documento, d["campos"])}
                        for d in dados["documentos"]]
    plano.ja_aplicada = Historico.objects.filter(oficio=alvo,
                                                 dados__correcao=dados["chave"]).exists()
    plano.mudam = sorted(k for k, v in plano.campos.items()
                         if getattr(alvo, _campo(Oficio, k).attname) != v)
    if _linhas(alvo.viajantes.order_by("ordem", "pk"), CAMPOS_VIAJANTE) != plano.viajantes:
        plano.filhos_mudam.append("viajantes")
    if _linhas(alvo.trechos.order_by("ordem"), CAMPOS_TRECHO) != plano.trechos:
        plano.filhos_mudam.append("trechos")
    if plano.ja_aplicada:
        return plano
    atual = _estado(alvo)
    for k, v in esperado.items():
        valor = _campo(Oficio, k).to_python(v) if k == "atualizado_em" else v
        if atual[k] != valor:
            plano.problemas.append(f"o alvo mudou desde a exportação: {k}")
    for rotulo, ids in dados["referencias"].items():
        existentes = set(apps.get_model(rotulo)._default_manager.filter(pk__in=ids)
                         .values_list("pk", flat=True))
        faltam = sorted(set(ids) - existentes)
        if faltam:
            plano.problemas.append(f"{rotulo}: ids inexistentes {faltam}")
    for d in plano.documentos:
        c = d["campos"]
        if Documento.objects.filter(oficio=alvo, tipo=c["tipo"], versao=c["versao"]).exists():
            plano.problemas.append(f"documento {c['tipo']} v{c['versao']} já existe no alvo")
        s, tabela, pk = d["origem"]
        if MapaLegado.objects.filter(sistema=s, tabela=tabela, origem_pk=pk).exists():
            plano.problemas.append(f"PDF {s}:{pk} já está no mapa da migração")
    for m in dados["midia"]:
        if not default_storage.exists(m["destino"]):
            plano.problemas.append(f"arquivo ausente no MEDIA_ROOT: {m['destino']}")
            continue
        with default_storage.open(m["destino"], "rb") as f:
            if _sha256(f.read()) != m["sha256"]:
                plano.problemas.append(f"arquivo com SHA-256 diferente: {m['destino']}")
    return plano


def aplicar(dados: dict[str, Any], plano: Plano, usuario_id: int) -> list[int]:
    """Grava a correção (dentro da transação de quem chama). Devolve os ids dos documentos."""
    if plano.ja_aplicada or plano.problemas:
        raise CorrecaoRecusada("correção já aplicada ou com problemas: nada gravado")
    alvo = plano.alvo
    antes = plano.antes
    agora = timezone.now()
    Oficio.objects.filter(pk=alvo.pk).update(
        **plano.campos, versao=models.F("versao") + 1, atualizado_em=agora)
    if "viajantes" in plano.filhos_mudam:
        alvo.viajantes.all().delete()
        Viajante.objects.bulk_create([Viajante(oficio_id=alvo.pk, **r) for r in plano.viajantes])
    if "trechos" in plano.filhos_mudam:
        alvo.trechos.all().delete()
        Trecho.objects.bulk_create([Trecho(oficio_id=alvo.pk, **r) for r in plano.trechos])
    lote = dados["chave"]
    origem = dados["origem"]
    docs: list[int] = []
    for d in plano.documentos:
        campos = dict(d["campos"])
        emitido_em = campos.pop("emitido_em")
        doc = Documento.objects.create(oficio_id=alvo.pk, **campos)
        Documento.objects.filter(pk=doc.pk).update(emitido_em=emitido_em)
        s, tabela, pk = d["origem"]
        MapaLegado.objects.create(sistema=s, tabela=tabela, origem_pk=pk,
                                  modelo="viagens.Documento", destino_pk=str(doc.pk),
                                  criado=True, lote=lote)
        docs.append(doc.pk)
    # O ofício passa a vir do GV; a cópia do EV fica só mapeada.
    MapaLegado.objects.filter(sistema=origem["sistema"], tabela=origem["tabela"],
                              origem_pk=origem["pk"], destino_pk=str(alvo.pk)).update(criado=True)
    if origem.get("ev_pk"):
        MapaLegado.objects.filter(sistema="ev", tabela=origem["ev_tabela"],
                                  origem_pk=str(origem["ev_pk"]),
                                  destino_pk=str(alvo.pk)).update(criado=False)
    Historico.objects.create(
        oficio_id=alvo.pk, acao=Historico.Acao.ALTERADO,
        descricao=dados["historico"]["descricao"][:300], usuario_id=usuario_id,
        dados={"correcao": lote, "origem": origem["sistema"], "pk": origem["pk"],
               "ev_pk": origem.get("ev_pk"), "status_legado": origem.get("status_legado"),
               "campos": plano.mudam, "filhos": plano.filhos_mudam,
               "viajantes": [antes["viajantes"], len(plano.viajantes)],
               "trechos": [antes["trechos"], len(plano.trechos)], "documentos": docs})
    return docs


def usuario_tecnico() -> int:
    from gestao.identidade.models import Usuario

    pk = Usuario.objects.filter(login__iexact=LOGIN_MIGRACAO).values_list("pk", flat=True).first()
    if pk is None:
        raise CorrecaoRecusada(f'usuário técnico "{LOGIN_MIGRACAO}" não existe')
    return int(pk)


class Ensaio(Exception):
    """Desfaz a transação do ensaio."""


def executar(dados: dict[str, Any], gravar: bool) -> tuple[Plano, list[int]]:
    """Uma transação só: confere, aplica e (sem `gravar`) desfaz."""
    usuario_id = usuario_tecnico()
    resultado: dict[str, Any] = {}
    try:
        with transaction.atomic(), auditoria.contexto(usuario_id, None, dados["chave"]):
            plano = planejar(dados)
            resultado["plano"] = plano
            docs: list[int] = []
            if not plano.ja_aplicada and not plano.problemas:
                docs = aplicar(dados, plano, usuario_id)
            resultado["docs"] = docs
            if not gravar:
                raise Ensaio
    except Ensaio:
        pass
    return resultado["plano"], resultado["docs"]


def resumo(dados: dict[str, Any], plano: Plano) -> list[str]:
    """O que a correção faz, sem valores (nomes de campos e contagens)."""
    a = plano.alvo
    linhas = [f"alvo: ofício {a.pk} ({a.numero:02d}/{a.ano}), origem "
              f"{dados['origem']['sistema']}:{dados['origem']['pk']}"]
    if plano.ja_aplicada:
        linhas.append(f"correção '{dados['chave']}' já aplicada: nada a fazer")
        if plano.mudam or plano.filhos_mudam:
            linhas.append("  (o ofício foi alterado depois dela: "
                          + ", ".join(plano.mudam + plano.filhos_mudam) + ")")
        return linhas
    linhas.append(f"campos que mudam ({len(plano.mudam)}): " + ", ".join(plano.mudam))
    linhas.append(f"viajantes: {plano.antes['viajantes']} → {len(plano.viajantes)}"
                  + (" (substituídos)" if "viajantes" in plano.filhos_mudam else " (iguais)"))
    linhas.append(f"trechos: {plano.antes['trechos']} → {len(plano.trechos)}"
                  + (" (substituídos)" if "trechos" in plano.filhos_mudam else " (iguais)"))
    for d in plano.documentos:
        c = d["campos"]
        linhas.append(f"documento a criar: {c['tipo']} v{c['versao']} ({c['situacao']}, PDF "
                      f"{d['origem'][0]}:{d['origem'][2]})")
    linhas.append("versão do ofício: +1; histórico: 1 linha 'alterado'; mapa: ofício passa a "
                  f"vir do GV, {len(plano.documentos)} PDF(s) mapeado(s)")
    linhas.append("referências conferidas: " + ", ".join(
        f"{k} {len(v)}" for k, v in dados["referencias"].items()))
    linhas.append(f"mídia: {len(dados['midia'])} arquivo(s)")
    for p in plano.problemas:
        linhas.append(f"PROBLEMA: {p}")
    return linhas
