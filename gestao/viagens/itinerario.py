"""Itinerário 2.0 (ofício e roteiro cadastrado): formulários, leitura do POST e cálculo dos
trechos (ADR 0016).

A pessoa informa, para cada trecho, só a **saída**; o tempo de estrada vem da rota (ou do que
ela ajustar) e o tempo adicional da sugestão (ou do que ela informar). A chegada é calculada:
saída + tempo de estrada + tempo adicional.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.http import QueryDict

from gestao.cadastros.models import Municipio
from gestao.plataforma.widgets import EntradaDataHora

from . import rotas
from .forms import ConjuntoDestinos, FormularioRetorno, FormularioSede, iniciais_de_trechos
from .services import TrechoInformado

_LEITOR_DATA_HORA = EntradaDataHora()
CAMPOS_DESTINO = ("uf", "cidade", "saida", "tempo_viagem", "tempo_adicional")
CAMPOS_RETORNO = ("saida", "tempo_viagem", "tempo_adicional")


def _cru(dados: QueryDict, nome: str) -> str:
    """Valor como digitado (data e hora chegam em dois campos: nome_0 e nome_1)."""
    if nome.endswith("-saida"):
        return _LEITOR_DATA_HORA.value_from_datadict(dados, None, nome) or ""
    return dados.get(nome, "")


def _ordem(valor) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return float("inf")


@dataclass
class Itinerario:
    sede: FormularioSede
    destinos: Any  # ConjuntoDestinos (classe gerada por formset_factory)
    retorno: FormularioRetorno
    form_id: str

    def formularios_em_ordem(self) -> list:
        """Destinos na ordem do arrastar e soltar (campo ORDER), sem os removidos."""
        vivos = [f for f in self.destinos
                 if not (f["DELETE"].value() if "DELETE" in f.fields else False)]
        return sorted(vivos, key=lambda f: _ordem(f["ORDER"].value()))

    def paradas(self) -> tuple[list[tuple], str]:
        """[(formulário, ponto de onde o trecho sai)], e o último ponto antes da volta."""
        anterior = str(self.sede["cidade"].value() or "sede")
        resultado = []
        for i, f in enumerate(self.formularios_em_ordem(), start=1):
            resultado.append((f, anterior))
            anterior = str(f["cidade"].value() or f"destino {i}")
        return resultado, anterior

    def contexto(self) -> dict:
        paradas, ultima = self.paradas()
        return {"itinerario": self, "sede_form": self.sede, "destinos": self.destinos,
                "retorno": self.retorno, "paradas": paradas, "ultima_parada": ultima,
                "form_id": self.form_id, "mapa_tiles": settings.MAPA_TILES_URL,
                "mapa_atribuicao": settings.MAPA_ATRIBUICAO}

    def valido(self) -> bool:
        return all([self.sede.is_valid(), self.destinos.is_valid(), self.retorno.is_valid()])

    def vazio(self, dados: QueryDict) -> bool:
        """Nenhum destino nem volta informados (rascunho pode ficar sem roteiro)."""
        total = int(dados.get("destino-TOTAL_FORMS") or 0)
        return not any(_cru(dados, f"destino-{i}-{c}") for i in range(total)
                       for c in ("cidade", "saida")) and not _cru(dados, "retorno-saida")


def montar(form_id: str, *, dados: QueryDict | None = None, sede: Municipio | None = None,
           trechos=None) -> Itinerario:
    """Formulários vinculados ao POST (`dados`) ou iniciais a partir dos trechos gravados."""
    kw = {"form_id": form_id}
    if dados is not None:
        return Itinerario(
            FormularioSede(dados, prefix="sede", **kw),
            ConjuntoDestinos(dados, prefix="destino", form_kwargs=kw),
            FormularioRetorno(dados, prefix="retorno", **kw), form_id)
    iniciais, inicial_retorno = iniciais_de_trechos(trechos or [], sede.pk if sede else None)
    inicial_sede = {"cidade": f"{sede.nome}/{sede.uf}", "uf": sede.uf} if sede else {}
    return Itinerario(
        FormularioSede(initial=inicial_sede, prefix="sede", **kw),
        ConjuntoDestinos(initial=iniciais, prefix="destino", form_kwargs=kw),
        FormularioRetorno(initial=inicial_retorno, prefix="retorno", **kw), form_id)


def com_iniciais(form_id: str, dados: QueryDict, *, mais_um: bool = False,
                 destinos: list[dict] | None = None, retorno: dict | None = None,
                 sede: Municipio | None = None) -> Itinerario:
    """Reexibe o que foi digitado (sem validar): "Adicionar destino" sem JavaScript, ou
    `destinos`/`retorno` vindos de um roteiro cadastrado."""
    kw = {"form_id": form_id}
    inicial_sede = ({"cidade": f"{sede.nome}/{sede.uf}", "uf": sede.uf} if sede else
                    {c: _cru(dados, f"sede-{c}") for c in ("uf", "cidade")})
    if destinos is None:
        total = int(dados.get("destino-TOTAL_FORMS") or 0)
        linhas = [
            ({c: _cru(dados, f"destino-{i}-{c}") for c in CAMPOS_DESTINO},
             _ordem(dados.get(f"destino-{i}-ORDER")))
            for i in range(total) if not dados.get(f"destino-{i}-DELETE")
        ]
        destinos = [d for d, _ in sorted(linhas, key=lambda x: x[1])]
        for i, d in enumerate(destinos, start=1):
            d["ORDER"] = i
        if mais_um or not destinos:
            # O novo destino começa na UF do anterior (o caso comum: interior do mesmo estado).
            uf = (destinos[-1] if destinos else inicial_sede).get("uf", "")
            destinos.append({"ORDER": len(destinos) + 1, "uf": uf})
    if retorno is None:
        retorno = {c: _cru(dados, f"retorno-{c}") for c in CAMPOS_RETORNO}
    return Itinerario(
        FormularioSede(initial=inicial_sede, prefix="sede", **kw),
        ConjuntoDestinos(initial=destinos[:10], prefix="destino", form_kwargs=kw),
        FormularioRetorno(initial=retorno, prefix="retorno", **kw), form_id)


def _perna(origem: Municipio, destino: Municipio, saida, viagem: int | None,
           adicional: int | None) -> TrechoInformado:
    rota = rotas.calcular(origem, destino)
    viagem = rota.minutos if viagem is None else viagem
    adicional = rota.adicional_sugerido if adicional is None else adicional
    return TrechoInformado(origem.pk, destino.pk, saida,
                           saida + timedelta(minutes=viagem + adicional),
                           rota.km if rota.km else None, viagem, adicional)


def trechos(itin: Itinerario) -> list[TrechoInformado]:
    """Trechos na ordem informada, com chegada calculada. Exige `itin.valido()`."""
    sede = itin.sede.cleaned_data["cidade"]
    resultado = []
    origem = sede
    for f in itin.formularios_em_ordem():
        dados = f.cleaned_data
        if not dados or not dados.get("cidade"):
            continue
        resultado.append(_perna(origem, dados["cidade"], dados["saida"],
                                dados.get("tempo_viagem"), dados.get("tempo_adicional")))
        origem = dados["cidade"]
    volta = itin.retorno.cleaned_data
    resultado.append(_perna(origem, sede, volta["saida"], volta.get("tempo_viagem"),
                            volta.get("tempo_adicional")))
    return resultado
