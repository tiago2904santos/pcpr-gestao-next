"""Configuração do canal WhatsApp, lida em um lugar só (`settings.WHATSAPP`, montado das
variáveis de ambiente em `config/settings/base.py`). Nada de segredo em código ou documento.

- `modo`: `simulado` (padrão em todo ambiente; não sai nada para a rede) ou `cloud_api`.
- O modo real só vale com todas as credenciais **e** fora do PREVIEW: no PREVIEW/DEMO público
  o canal é sempre simulado (ADR 0046) — o check `automacao.E001` recusa o startup se alguém
  tentar.
- `lista_fechada`: fora de PRODUCTION é sempre ligada (só os testadores autorizados recebem);
  em PRODUCTION fica ligada a menos que se escreva "false".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.conf import settings

from gestao.plataforma import ambiente

SIMULADO = "simulado"
CLOUD_API = "cloud_api"
MODOS = (SIMULADO, CLOUD_API)

VERSAO_PADRAO = "v25.0"  # vale até 29/07/2028 (referência, seção 1)
BASE_URL = "https://graph.facebook.com"
OBRIGATORIOS_REAL = ("phone_number_id", "access_token", "app_secret", "verify_token")
TAMANHO_MAXIMO_MIDIA = 10 * 1024 * 1024  # o mesmo teto dos anexos da prestação
REMETENTE_PADRAO = "Sistema de testes (dados fictícios)"


@dataclass(frozen=True)
class Modelo:
    """Um modelo (template) aprovado na Meta, para mensagens fora da janela de 24 h."""

    nome: str
    idioma: str = "pt_BR"


@dataclass(frozen=True)
class Configuracao:
    modo: str = SIMULADO
    versao: str = VERSAO_PADRAO
    phone_number_id: str = ""
    waba_id: str = ""
    access_token: str = field(default="", repr=False)
    app_secret: str = field(default="", repr=False)
    verify_token: str = field(default="", repr=False)
    lista_fechada: bool = True
    limite_por_hora: int = 30
    timeout_envio: float = 30.0
    timeout_midia: float = 60.0
    tamanho_maximo_midia: int = TAMANHO_MAXIMO_MIDIA
    remetente: str = REMETENTE_PADRAO
    modelos: dict[str, Modelo] = field(default_factory=dict)
    bloqueado_no_ambiente: bool = False  # pediram cloud_api onde não pode (PREVIEW)

    @property
    def real(self) -> bool:
        return (self.modo == CLOUD_API and not self.faltantes()
                and not self.bloqueado_no_ambiente)

    def faltantes(self) -> list[str]:
        return [c for c in OBRIGATORIOS_REAL if not getattr(self, c)]

    def modelo_de(self, tipo: str) -> Modelo | None:
        return self.modelos.get(tipo)

    def descricao(self) -> str:
        if self.bloqueado_no_ambiente:
            return "Simulado — o PREVIEW público nunca usa a Cloud API"
        if self.modo == SIMULADO:
            return "Simulado (nada sai para a Meta)"
        if not self.real:
            return f"Simulado — faltam credenciais da Cloud API ({', '.join(self.faltantes())})"
        lista = "só testadores autorizados" if self.lista_fechada else "lista aberta"
        return f"Cloud API {self.versao} ({lista})"


def _modelos(bruto: object) -> dict[str, Modelo]:
    """`tipo=nome:idioma;tipo2=nome2` (variável de ambiente) ou um dict já pronto."""
    saida: dict[str, Modelo] = {}
    if isinstance(bruto, dict):
        itens = [(str(k), str(v)) for k, v in bruto.items()]
    else:
        itens = []
        for parte in str(bruto or "").split(";"):
            tipo, _, alvo = parte.partition("=")
            if tipo.strip() and alvo.strip():
                itens.append((tipo.strip(), alvo.strip()))
    for tipo, alvo in itens:
        nome, _, idioma = alvo.partition(":")
        if nome.strip():
            saida[tipo] = Modelo(nome.strip(), (idioma or "pt_BR").strip())
    return saida


def _inteiro(valor: object, padrao: int) -> int:
    try:
        return max(1, int(str(valor)))
    except (TypeError, ValueError):
        return padrao


def _real(valor: object, padrao: float) -> float:
    try:
        return max(1.0, float(str(valor)))
    except (TypeError, ValueError):
        return padrao


def carregar() -> Configuracao:
    bruto = dict(getattr(settings, "WHATSAPP", {}) or {})
    modo = str(bruto.get("modo") or SIMULADO).strip().lower()
    if modo not in MODOS:
        modo = SIMULADO
    bloqueado = modo == CLOUD_API and ambiente.atual() == "preview"
    fechada = bruto.get("lista_fechada", True)
    if isinstance(fechada, str):
        fechada = fechada.strip().lower() not in {"false", "0", "no", "nao", "não"}
    if not ambiente.eh_producao():
        fechada = True  # fora de produção, só a lista fechada de testadores
    versao = str(bruto.get("versao") or VERSAO_PADRAO).strip()
    if not (versao.startswith("v") and versao[1:].replace(".", "").isdigit()):
        versao = VERSAO_PADRAO
    return Configuracao(
        modo=modo,
        versao=versao,
        phone_number_id=str(bruto.get("phone_number_id") or "").strip(),
        waba_id=str(bruto.get("waba_id") or "").strip(),
        access_token=str(bruto.get("access_token") or "").strip(),
        app_secret=str(bruto.get("app_secret") or "").strip(),
        verify_token=str(bruto.get("verify_token") or "").strip(),
        lista_fechada=bool(fechada),
        limite_por_hora=_inteiro(bruto.get("limite_por_hora"), 30),
        timeout_envio=_real(bruto.get("timeout_envio"), 30.0),
        timeout_midia=_real(bruto.get("timeout_midia"), 60.0),
        tamanho_maximo_midia=min(_inteiro(bruto.get("tamanho_maximo_midia"),
                                          TAMANHO_MAXIMO_MIDIA), 100 * 1024 * 1024),
        remetente=str(bruto.get("remetente") or REMETENTE_PADRAO).strip()[:80],
        modelos=_modelos(bruto.get("modelos")),
        bloqueado_no_ambiente=bloqueado,
    )


def mascarar(valor: str, visiveis: int = 4) -> str:
    """`abcd****` — nunca o valor inteiro; vazio vira "(não configurado)"."""
    texto = (valor or "").strip()
    if not texto:
        return "(não configurado)"
    if len(texto) <= visiveis:
        return "*" * len(texto)
    return f"{texto[:visiveis]}{'*' * min(4, len(texto) - visiveis)}"


def mascarar_telefone(e164: str) -> str:
    """`+55 •• ••••-1234`: o bastante para a pessoa reconhecer, sem expor o número."""
    digitos = "".join(c for c in (e164 or "") if c.isdigit())
    if len(digitos) < 4:
        return "(sem número)"
    return f"+{digitos[:2]} •• ••••-{digitos[-4:]}"
