"""Sugestões para preencher a solicitação (só leitura; nada grava):

- pelo tipo de evento: o modelo do tipo (Cadastros › Tipos de evento) e, se o modelo não diz
  serviços nem equipes, o que se repete nas últimas solicitações daquele tipo;
- pelos solicitantes de antes: o nome com o cargo, o contato e o órgão do último pedido.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from django.db.models import Count, Max

from . import dominio, policies
from .models import Solicitacao, TipoEvento

ULTIMAS = 20  # solicitações do tipo olhadas quando o modelo está vazio
FREQUENCIA = 0.5  # o item entra se aparece em pelo menos metade delas
MAX_SOLICITANTES = 8


@dataclass
class SugestaoDoTipo:
    fonte: str
    servicos: list[dict] = field(default_factory=list)  # {id, nome}
    equipes: list[dict] = field(default_factory=list)  # {id, nome, quantidade}
    solicitante: str = ""
    cargo: str = ""
    orgao: dict | None = None  # {id, nome}

    @property
    def vazia(self) -> bool:
        return not (self.servicos or self.equipes or self.solicitante or self.cargo
                    or self.orgao)

    def como_dict(self) -> dict:
        return {"fonte": self.fonte, "servicos": self.servicos, "equipes": self.equipes,
                "solicitante": self.solicitante, "cargo": self.cargo, "orgao": self.orgao,
                "vazia": self.vazia}


def _quantidade_mais_comum(valores: list[int | None]) -> int | None:
    """A quantidade que mais aparece; no empate, a maior."""
    contagem = Counter(v for v in valores if v)
    if not contagem:
        return None
    return max(contagem.items(), key=lambda par: (par[1], par[0]))[0]


def do_tipo(usuario, tipo: TipoEvento) -> SugestaoDoTipo:
    modelo_servicos = [{"id": s.pk, "nome": s.nome}
                       for s in tipo.servicos_sugeridos.filter(ativo=True).order_by("nome")]
    modelo_equipes = [{"id": e.equipe_id, "nome": e.equipe.nome, "quantidade": e.quantidade}
                      for e in tipo.equipes_padrao.select_related("equipe")
                      .filter(equipe__ativo=True).order_by("equipe__nome")]
    sugestao = SugestaoDoTipo(
        fonte="o modelo do tipo", servicos=modelo_servicos, equipes=modelo_equipes,
        solicitante=tipo.solicitante_padrao, cargo=tipo.cargo_padrao,
        orgao=({"id": tipo.orgao_padrao_id, "nome": tipo.orgao_padrao.nome}
               if tipo.orgao_padrao_id and tipo.orgao_padrao else None))
    if modelo_servicos or modelo_equipes:
        return sugestao
    ultimas = list(policies.solicitacoes_visiveis(usuario)
                   .filter(tipo_evento=tipo).exclude(status=dominio.RASCUNHO)
                   .prefetch_related("servicos__servico", "equipes__equipe")
                   .order_by("-data_solicitacao", "-pk")[:ULTIMAS])
    if not ultimas:
        return sugestao
    minimo = len(ultimas) * FREQUENCIA
    servicos: Counter = Counter()
    equipes: Counter = Counter()
    nomes: dict[tuple[str, int], str] = {}
    quantidades: dict[int, list[int | None]] = {}
    for s in ultimas:
        for x in s.servicos.all():
            if x.servico.ativo:
                servicos[x.servico_id] += 1
                nomes[("s", x.servico_id)] = x.servico.nome
        for e in s.equipes.all():
            if e.equipe.ativo:
                equipes[e.equipe_id] += 1
                nomes[("e", e.equipe_id)] = e.equipe.nome
                quantidades.setdefault(e.equipe_id, []).append(e.quantidade_servidores)
    sugestao.servicos = sorted(({"id": pk, "nome": nomes[("s", pk)]}
                                for pk, n in servicos.items() if n >= minimo),
                               key=lambda d: d["nome"])
    sugestao.equipes = sorted(({"id": pk, "nome": nomes[("e", pk)],
                                "quantidade": _quantidade_mais_comum(quantidades[pk])}
                               for pk, n in equipes.items() if n >= minimo),
                              key=lambda d: d["nome"])
    if sugestao.servicos or sugestao.equipes:
        total = len(ultimas)
        sugestao.fonte = ("a última solicitação deste tipo" if total == 1
                          else f"as últimas {total} solicitações deste tipo")
    return sugestao


def solicitantes(usuario, termo: str) -> list[dict]:
    """Quem já pediu, pelo começo ou pedaço do nome: até 8 nomes (caixa e espaços juntos),
    do mais recente ao mais antigo, com os dados do último pedido de cada um."""
    termo = " ".join(termo.split())
    if len(termo) < 2:
        return []
    qs = (policies.solicitacoes_visiveis(usuario)
          .filter(solicitante_nome__unaccent__icontains=termo)
          .exclude(solicitante_nome=""))
    grupos: dict[str, dict] = {}
    for nome, ultimo, total in (qs.values_list("solicitante_nome")
                                .annotate(ultimo=Max("pk"), total=Count("pk"))
                                .order_by("-ultimo")):
        chave = " ".join(nome.split()).casefold()
        g = grupos.setdefault(chave, {"ultimo": ultimo, "total": 0})
        g["total"] += total
        g["ultimo"] = max(g["ultimo"], ultimo)
    escolhidos = sorted(grupos.values(), key=lambda g: -g["ultimo"])[:MAX_SOLICITANTES]
    pedidos = Solicitacao.objects.select_related("orgao_responsavel").in_bulk(
        [g["ultimo"] for g in escolhidos])
    resultado = []
    for g in escolhidos:
        s = pedidos[g["ultimo"]]
        nome = " ".join(s.solicitante_nome.split())
        orgao = s.orgao_responsavel
        detalhe = " · ".join(t for t in (s.solicitante_cargo_unidade, s.contato,
                                          orgao.nome if orgao else "") if t)
        vezes = f"{g['total']} pedido{'s' if g['total'] != 1 else ''}"
        resultado.append({
            "id": nome, "titulo": nome, "meta": f"{detalhe} · {vezes}" if detalhe else vezes,
            "cargo": s.solicitante_cargo_unidade, "contato": s.contato,
            "orgao": orgao.pk if orgao and orgao.ativo else None})
    return resultado
