"""Configuração do eProtocolo, lida em um lugar só.

O resto do pacote pergunta aqui se a chamada vai à rede ou é simulada; a falta de credencial
nunca vira exceção no meio de um caso de uso — vira modo simulado, dito com todas as letras.
Valores vêm de `settings.EPROTOCOLO` (montado das variáveis de ambiente em
`config/settings/base.py`); nada de segredo em código ou documento.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.conf import settings

SIMULADO = "simulado"
DESENVOLVIMENTO = "desenvolvimento"
HOMOLOGACAO = "homologacao"
TREINAMENTO = "treinamento"
PRODUCAO = "producao"
AMBIENTES = (SIMULADO, DESENVOLVIMENTO, HOMOLOGACAO, TREINAMENTO, PRODUCAO)
REAIS = (DESENVOLVIMENTO, HOMOLOGACAO, TREINAMENTO, PRODUCAO)

#: URLs públicas oficiais (rota de internet). A rota de intranet (`celepar.parana`) entra
#: por `EPROTOCOLO_BASE_URL` quando o servidor estiver na rede do Estado.
URLS_OFICIAIS = {
    HOMOLOGACAO: ("https://hml-apigateway.paas.pr.gov.br/seap/spi-servicos/api-hml",
                  "https://auth-cs-hml.identidadedigital.pr.gov.br/centralautenticacao/api/v1/token/jwt"),
    TREINAMENTO: ("https://hml-apigateway.paas.pr.gov.br/seap/spi-servicos/api-tre",
                  "https://auth-cs-hml.identidadedigital.pr.gov.br/centralautenticacao/api/v1/token/jwt"),
    PRODUCAO: ("https://apigateway.paas.pr.gov.br/seap/spi-servicos/api",
               "https://auth-cs.identidadedigital.pr.gov.br/centralautenticacao/api/v1/token/jwt"),
}

#: Sem estes valores o modo real não tem como operar.
OBRIGATORIOS_REAL = ("client_id", "client_secret", "consumer_id")
#: Exigidos pelo eProtocolo para abrir processo (códigos institucionais).
OBRIGATORIOS_ABERTURA = ("cod_orgao", "cod_local_origem", "cod_assunto_viagem",
                         "cod_especie_oficio")


@dataclass(frozen=True)
class Configuracao:
    ambiente: str = SIMULADO
    base_url: str = ""
    token_url: str = ""
    client_id: str = ""
    client_secret: str = field(default="", repr=False)
    consumer_id: str = ""
    escopos: tuple[str, ...] = ("spiserv.protocolos.consultar",)
    timeout: float = 15.0
    #: Trava: no modo real, só consulta. Abrir protocolo exige destravar explicitamente.
    somente_leitura: bool = True
    cod_orgao: str = ""
    cod_local_origem: str = ""
    cod_assunto_viagem: str = ""
    cod_especie_oficio: str = ""

    @property
    def real(self) -> bool:
        return self.ambiente in REAIS and not self.faltantes()

    @property
    def oficial(self) -> bool:
        """Número aberto aqui vale como protocolo oficial? Só em produção, de verdade."""
        return self.ambiente == PRODUCAO and self.real

    def faltantes(self) -> list[str]:
        return [c for c in OBRIGATORIOS_REAL if not getattr(self, c)]

    def faltantes_para_abrir(self) -> list[str]:
        return [c for c in OBRIGATORIOS_ABERTURA if not getattr(self, c)]

    @property
    def escrita_liberada(self) -> bool:
        return self.real and not self.somente_leitura

    def urls(self) -> tuple[str, str]:
        padrao = URLS_OFICIAIS.get(self.ambiente, ("", ""))
        return (self.base_url or padrao[0]).rstrip("/"), self.token_url or padrao[1]

    def descricao(self) -> str:
        """Frase curta do estado da integração, para tela e diagnóstico."""
        if self.ambiente == SIMULADO:
            return "Modo simulado (sem integração real)"
        if not self.real:
            return (f"Modo simulado — credenciais ausentes para {self.ambiente} "
                    f"({', '.join(self.faltantes())})")
        if self.somente_leitura:
            return f"Integração ativa ({self.ambiente}, somente consulta)"
        if not self.oficial:
            return f"Integração ativa ({self.ambiente}) — números de teste, não oficiais"
        return "Integração ativa (produção)"


def carregar() -> Configuracao:
    bruto = dict(getattr(settings, "EPROTOCOLO", {}) or {})
    ambiente = str(bruto.get("ambiente") or SIMULADO).strip().lower()
    if ambiente not in AMBIENTES:
        ambiente = SIMULADO
    escopos = bruto.get("escopos") or ("spiserv.protocolos.consultar",)
    if isinstance(escopos, str):
        escopos = tuple(e for e in escopos.replace(",", " ").split() if e)
    return Configuracao(
        ambiente=ambiente,
        base_url=str(bruto.get("base_url") or ""),
        token_url=str(bruto.get("token_url") or ""),
        client_id=str(bruto.get("client_id") or ""),
        client_secret=str(bruto.get("client_secret") or ""),
        consumer_id=str(bruto.get("consumer_id") or ""),
        escopos=tuple(escopos),
        timeout=float(bruto.get("timeout") or 15),
        somente_leitura=bool(bruto.get("somente_leitura", True)),
        cod_orgao=str(bruto.get("cod_orgao") or ""),
        cod_local_origem=str(bruto.get("cod_local_origem") or ""),
        cod_assunto_viagem=str(bruto.get("cod_assunto_viagem") or ""),
        cod_especie_oficio=str(bruto.get("cod_especie_oficio") or ""),
    )


def mascarar(valor: str, visiveis: int = 4) -> str:
    """`abcd****` — nunca o valor inteiro; vazio vira "(não configurado)"."""
    texto = (valor or "").strip()
    if not texto:
        return "(não configurado)"
    if len(texto) <= visiveis:
        return "*" * len(texto)
    return f"{texto[:visiveis]}{'*' * min(4, len(texto) - visiveis)}"
