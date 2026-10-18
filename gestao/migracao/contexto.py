"""O que toda etapa recebe: as duas fontes, o mapa (com cache), o relatório e o lote."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.db import models

from .fonte import Fonte
from .models import MapaLegado


@dataclass
class Relatorio:
    """Contagens por entidade e itens para uma pessoa conferir — SEM dados pessoais (só ids,
    tabelas e motivos). Vai para o arquivo do relatório, nunca para o log do servidor."""

    contagens: dict[str, dict[str, int]] = field(default_factory=dict)
    conferir: list[dict[str, Any]] = field(default_factory=list)

    def conta(self, entidade: str, situacao: str, n: int = 1) -> None:
        linha = self.contagens.setdefault(entidade, {})
        linha[situacao] = linha.get(situacao, 0) + n

    def revisar(self, entidade: str, motivo: str, **ids: Any) -> None:
        self.conferir.append({"entidade": entidade, "motivo": motivo, **ids})


@dataclass
class Contexto:
    ev: Fonte
    gv: Fonte | None
    lote: str
    relatorio: Relatorio
    midia_ev: Path | None = None
    midia_gv: Path | None = None
    usuario_migracao: Any = None      # usuário técnico inativo, autor do que não tem autor
    _cache: dict[tuple[str, str, str], str] = field(default_factory=dict)
    memo: dict[Any, Any] = field(default_factory=dict)   # tabelas do legado já lidas (por etapa)

    # ------------------------------------------------------------------ mapa
    def destino(self, sistema: str, tabela: str, origem_pk: Any) -> str | None:
        if origem_pk is None:
            return None
        chave = (sistema, tabela, str(origem_pk))
        if chave not in self._cache:
            alvo = (MapaLegado.objects.filter(sistema=sistema, tabela=tabela,
                                              origem_pk=str(origem_pk))
                    .values_list("destino_pk", flat=True).first())
            if alvo is None:
                return None
            self._cache[chave] = alvo
        return self._cache[chave]

    def precarregar(self, sistema: str, tabela: str) -> dict[str, str]:
        """Traz de uma vez o mapa de uma tabela de origem (evita uma consulta por linha)."""
        mapa = dict(MapaLegado.objects.filter(sistema=sistema, tabela=tabela)
                    .values_list("origem_pk", "destino_pk"))
        for origem, alvo in mapa.items():
            self._cache[(sistema, tabela, origem)] = alvo
        return mapa

    def mapear_lote(self, sistema: str, tabela: str, modelo: str,
                    pares: list[tuple[Any, Any]], *, criado: bool) -> int:
        """Grava muitas correspondências (origem_pk, destino_pk) de uma vez; as que já existem
        ficam como estão. Devolve quantas eram novas."""
        ja = self.precarregar(sistema, tabela)
        novos = [MapaLegado(sistema=sistema, tabela=tabela, origem_pk=str(o), modelo=modelo,
                            destino_pk=str(d), criado=criado, lote=self.lote)
                 for o, d in pares if str(o) not in ja]
        MapaLegado.objects.bulk_create(novos, batch_size=1000)
        for m in novos:
            self._cache[(sistema, tabela, m.origem_pk)] = m.destino_pk
        return len(novos)

    def destino_int(self, sistema: str, tabela: str, origem_pk: Any) -> int | None:
        alvo = self.destino(sistema, tabela, origem_pk)
        return int(alvo) if alvo is not None else None

    def mapear(self, sistema: str, tabela: str, origem_pk: Any, obj: models.Model, *,
               criado: bool = True) -> None:
        modelo = f"{obj._meta.app_label}.{obj.__class__.__name__}"
        MapaLegado.objects.update_or_create(
            sistema=sistema, tabela=tabela, origem_pk=str(origem_pk),
            defaults={"modelo": modelo, "destino_pk": str(obj.pk), "criado": criado,
                      "lote": self.lote})
        self._cache[(sistema, tabela, str(origem_pk))] = str(obj.pk)
