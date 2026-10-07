"""Dados copiáveis do ofício, sem consultas ou integração com o eProtocolo.

Contrato e fonte: docs/product/oficios-eprotocolo.md. O chamador resolve assunto,
formata número e converte as datas para o dia local antes de chamar este domínio.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CampoCopiavel:
    rotulo: str
    valor: str


@dataclass(frozen=True)
class DadosEprotocolo:
    campos: tuple[CampoCopiavel, ...]

    @property
    def detalhamento(self) -> str:
        return self.campos[-1].valor

    @property
    def copiar_tudo(self) -> str:
        return "\n".join(f"{campo.rotulo}: {campo.valor}" for campo in self.campos)


def _protocolo(valor: str) -> str:
    if len(valor) == 9 and valor.isascii() and valor.isdecimal():
        return f"{valor[:2]}.{valor[2:5]}.{valor[5:8]}-{valor[8]}"
    return valor


def _periodo(saida: date | None, retorno: date | None) -> str:
    if saida is None:
        return ""
    if retorno is None or retorno == saida:
        return f"{saida:%d/%m/%Y}"
    return f"{saida:%d/%m/%Y} a {retorno:%d/%m/%Y}"


def dados_eprotocolo(*, numero: str = "", protocolo: str = "", assunto_linha: str = "",
                    assunto_rotulo: str = "", destinos: Sequence[str] = (),
                    saida: date | None = None, retorno: date | None = None,
                    servidores: Sequence[str] = (), motivo: str = "") -> DadosEprotocolo:
    """Cinco campos na ordem do legado, mais texto para Copiar tudo.

    Campos ausentes continuam vazios. Destinos chegam sem o retorno à sede;
    nomes homônimos e destinos repetidos não são deduplicados.
    """
    nomes = sorted(nome.strip() for nome in servidores if nome.strip())
    interessados = ", ".join(nomes)
    assunto = f"{assunto_linha} {assunto_rotulo}".strip()
    destino = ", ".join(nome.upper() for nome in destinos[:100])
    if len(destinos) > 100:
        destino += f" +{len(destinos) - 100}"
    periodo = _periodo(saida, retorno)
    partes = [f"OFÍCIO Nº {numero}" if numero else "OFÍCIO"]
    linha = assunto_linha.rstrip(".").upper()
    if linha:
        partes.append(linha)
    if destino:
        partes.append(f"DESTINO: {destino}")
    if periodo:
        partes.append(f"PERÍODO: {periodo}")
    if interessados:
        partes.append(f"SERVIDORES: {interessados}")
    detalhamento = " - ".join(partes)
    if motivo:
        detalhamento += f"\n{motivo}"
    return DadosEprotocolo(campos=(
        CampoCopiavel("Interessados", interessados),
        CampoCopiavel("Assunto", assunto),
        CampoCopiavel("Nº/Ano do ofício", numero),
        CampoCopiavel("Protocolo", _protocolo(protocolo)),
        CampoCopiavel("Detalhamento", detalhamento),
    ))
