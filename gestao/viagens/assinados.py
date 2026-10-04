"""Vias assinadas dos documentos de Viagens (paridade com `anexar_arquivo_assinado` /
`remover_arquivo_assinado` da referência, para ofício, justificativa, termo e OS).

A via assinada é o PDF que voltou assinado (escaneado ou com assinatura digital). Cada
anexo é uma versão nova e imutável; "remover" revoga a vigente — o arquivo fica guardado
como prova e no histórico, e o PDF gerado volta a valer. Enquanto houver uma via vigente,
ela prevalece em todo download do PDF daquele documento (`?versao=original` dá o gerado).

Termo e OS são gerados na hora, do estado atual: a via guarda a impressão (SHA-256) dos
dados que o documento tinha quando foi anexada; se os dados mudarem depois, a tela avisa
"Assinado, mas os dados mudaram". O ofício emitido já é congelado (versões PDF/A); a via
aponta para a versão que foi assinada e é revogada quando o ofício é reaberto.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from . import policies
from .models import Documento, Oficio, OrdemServico, TermoAutorizacao, ViaAssinada

TAMANHO_MAXIMO = 15 * 1024 * 1024  # referência: "Arquivo maior que 15MB."
TIPOS = {t.value for t in ViaAssinada.Tipo}


Dono = Oficio | TermoAutorizacao | OrdemServico


class ArquivoAssinadoInvalido(Exception):
    pass


def _campo(dono: Dono) -> str:
    if isinstance(dono, Oficio):
        return "oficio"
    return "termo" if isinstance(dono, TermoAutorizacao) else "ordem"


@dataclass
class Alvo:
    """O documento que recebe a via: o tipo, o registro dono e (no termo) qual dos
    documentos dele — o de um servidor, o genérico ou o da viatura."""

    tipo: str
    dono: Dono
    chave: str = ""

    @property
    def filtro(self) -> dict[str, Any]:
        return {"tipo": self.tipo, _campo(self.dono): self.dono, "chave": self.chave}

    @property
    def rotulo(self) -> str:
        if self.tipo == ViaAssinada.Tipo.TERMO:
            from . import termos
            doc = next((d for d in termos.documentos_do_termo(self.dono)  # type: ignore[arg-type]
                        if d["chave"] == self.chave), None)
            return f"{self.dono} — {doc['titulo']}" if doc else str(self.dono)
        if self.tipo == ViaAssinada.Tipo.JUSTIFICATIVA:
            return f"Justificativa do {self.dono}"
        return str(self.dono)


# ---------------------------------------------------------------- validação e impressão
def validar(nome: str, tamanho: int, inicio: bytes) -> None:
    """As três conferências da referência, na mesma ordem e com as mesmas mensagens."""
    if not (nome or "").lower().endswith(".pdf"):
        raise ArquivoAssinadoInvalido("Envie um arquivo PDF.")
    if tamanho > TAMANHO_MAXIMO:
        raise ArquivoAssinadoInvalido("Arquivo maior que 15MB.")
    if not inicio.startswith(b"%PDF-"):
        raise ArquivoAssinadoInvalido("O arquivo não parece ser um PDF válido.")


# Fora da impressão: a marca de prévia e o que é da unidade, não do documento (cabeçalho,
# rodapé, sede, Delegado-Geral) — mudar a configuração da unidade não "desatualiza" as vias.
FORA_DA_IMPRESSAO = {"previa", "sigla", "unidade_nome", "cabecalho_unidade", "rodape",
                     "delegado_geral", "sede"}


def impressao(dados: dict) -> str:
    """SHA-256 dos dados de um documento: muda quando o que o documento diz muda."""
    limpos = {k: v for k, v in dados.items() if k not in FORA_DA_IMPRESSAO}
    texto = json.dumps(limpos, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(texto.encode()).hexdigest()


def documento_emitido(oficio: Oficio, tipo: str) -> Documento | None:
    """A versão PDF/A pronta mais recente do ofício (ou da justificativa)."""
    return (oficio.documentos.filter(tipo=tipo, situacao=Documento.Situacao.PRONTO)
            .order_by("-versao").first())


def impressao_atual(alvo: Alvo) -> str:
    """A impressão dos dados de hoje (termo e OS); vazia para o ofício, que é congelado."""
    if alvo.tipo == ViaAssinada.Tipo.TERMO:
        from . import termos
        try:
            return impressao(termos.dados_do_documento(alvo.dono, alvo.chave))  # type: ignore[arg-type]
        except termos.TermoInvalido:
            return ""
    if alvo.tipo == ViaAssinada.Tipo.ORDEM:
        from . import ordens
        try:
            return impressao(ordens.dados_do_documento(alvo.dono, fixar=False))  # type: ignore[arg-type]
        except ordens.OrdemInvalida:
            return ""
    return ""


# ---------------------------------------------------------------- permissões
def pode_anexar(usuario, alvo: Alvo) -> bool:
    dono = alvo.dono
    if alvo.tipo in (ViaAssinada.Tipo.OFICIO, ViaAssinada.Tipo.JUSTIFICATIVA):
        assert isinstance(dono, Oficio)  # nosec B101 - estreita o tipo
        return (dono.situacao == Oficio.Situacao.EMITIDO and not dono.arquivado
                and policies.pode_ver(usuario, dono) and usuario.has_perm("viagens.change_oficio"))
    if alvo.tipo == ViaAssinada.Tipo.TERMO:
        return policies.pode_editar_termo(usuario, dono)  # type: ignore[arg-type]
    # OS: só depois de gerada (a referência deixa "Anexar assinado" inativo até haver PDF).
    return (policies.pode_editar_ordem(usuario, dono)  # type: ignore[arg-type]
            and dono.documento_gerado_em is not None)  # type: ignore[union-attr]


def pode_abrir(usuario, via: ViaAssinada) -> bool:
    if via.oficio is not None:
        return policies.pode_ver(usuario, via.oficio)
    # Termo e OS: a mesma régua do documento gerado (registro ativo, quem os prepara) — o
    # termo traz RG e CPF da equipe.
    if via.termo is not None:
        return policies.pode_ver_documento_termo(usuario, via.termo)
    return via.ordem is not None and policies.pode_ver_documento_ordem(usuario, via.ordem)


# ---------------------------------------------------------------- leitura
def vigente(alvo: Alvo) -> ViaAssinada | None:
    return (ViaAssinada.objects.filter(**alvo.filtro, revogada_em__isnull=True)
            .select_related("enviado_por").order_by("-enviado_em").first())


def vigentes_do(dono: Dono) -> dict[tuple[str, str], ViaAssinada]:
    """Uma consulta: {(tipo, chave): via vigente} de todos os documentos do registro."""
    vias = (ViaAssinada.objects.filter(**{_campo(dono): dono}, revogada_em__isnull=True)
            .select_related("enviado_por").order_by("enviado_em"))
    return {(v.tipo, v.chave): v for v in vias}  # a mais recente vence


def dados_mudaram(via: ViaAssinada, alvo: Alvo | None = None) -> bool:
    if not via.impressao_dos_dados:
        return False
    atual = impressao_atual(alvo or alvo_da_via(via))
    return bool(atual) and atual != via.impressao_dos_dados


def alvo_da_via(via: ViaAssinada) -> Alvo:
    dono = via.oficio or via.termo or via.ordem
    assert dono is not None  # nosec B101 - a constraint garante um dono
    return Alvo(via.tipo, dono, via.chave)


def situacao(via: ViaAssinada | None, alvo: Alvo) -> dict[str, Any]:
    """O que a tela mostra de um documento: sem via, assinado, ou assinado com dados que
    mudaram depois."""
    if via is None:
        return {"via": None, "mudou": False}
    return {"via": via, "mudou": dados_mudaram(via, alvo)}


# ---------------------------------------------------------------- escrita
class ViaJaRemovida(Exception):
    pass


def _travar_dono(alvo: Alvo) -> Alvo:
    """O registro travado até o fim da transação: a permissão é conferida nele, e não no
    que a tela carregou (uma reabertura ou um cancelamento ao mesmo tempo esperam)."""
    travado = type(alvo.dono).objects.select_for_update().get(pk=alvo.dono.pk)
    return Alvo(alvo.tipo, travado, alvo.chave)


@transaction.atomic
def anexar(usuario, alvo: Alvo, *, nome: str, conteudo: bytes) -> ViaAssinada:
    validar(nome, len(conteudo), conteudo[:5])
    alvo = _travar_dono(alvo)
    policies.exigir(pode_anexar(usuario, alvo),
                    "Você não pode anexar a via assinada deste documento.")
    documento = None
    impressao_dos_dados = ""
    if alvo.tipo in (ViaAssinada.Tipo.OFICIO, ViaAssinada.Tipo.JUSTIFICATIVA):
        documento = documento_emitido(alvo.dono, alvo.tipo)  # type: ignore[arg-type]
        if documento is None:
            raise ArquivoAssinadoInvalido("Gere o PDF do documento primeiro.")
    else:
        impressao_dos_dados = impressao_atual(alvo)
    via = ViaAssinada(**alvo.filtro, documento=documento, nome_original=(nome or "")[:255],
                      sha256=hashlib.sha256(conteudo).hexdigest(), tamanho=len(conteudo),
                      impressao_dos_dados=impressao_dos_dados, enviado_por=usuario)
    anteriores = list(ViaAssinada.objects.select_for_update()
                      .filter(**alvo.filtro, revogada_em__isnull=True))
    via.arquivo.save(f"assinado-{alvo.tipo}-{alvo.dono.pk}.pdf", ContentFile(conteudo),
                     save=False)
    try:  # se a gravação falhar, o arquivo não fica órfão no disco
        # Trocar = a anterior sai de uso (fica no histórico); remover a nova depois volta ao
        # PDF gerado, nunca a uma via antiga (referência: remover limpa a via em vigor).
        for anterior in anteriores:
            _revogar(anterior, usuario, "Substituída por uma via nova.")
        via.save()
        _registrar(alvo, "anexada", usuario, via)
    except Exception:
        via.arquivo.delete(save=False)
        raise
    return via


@transaction.atomic
def revogar(usuario, via_pk: int, *, motivo: str = "", conferir: bool = True) -> ViaAssinada:
    """Revoga a via (nunca apaga o arquivo). `conferir=False` é para o próprio sistema
    (reabertura do ofício), que já conferiu quem pede."""
    via = ViaAssinada.objects.select_related("oficio", "termo", "ordem").get(pk=via_pk)
    alvo = _travar_dono(alvo_da_via(via))
    via = ViaAssinada.objects.select_for_update().get(pk=via_pk)
    if conferir:
        policies.exigir(pode_revogar(usuario, alvo),
                        "Você não pode remover a via assinada deste documento.")
    if via.revogada_em is not None:
        raise ViaJaRemovida("Esta via assinada já tinha sido removida.")
    _revogar(via, usuario, motivo)
    _registrar(alvo, "revogada", usuario, via)
    return via


def _revogar(via: ViaAssinada, usuario, motivo: str) -> None:
    via.revogada_em = timezone.now()
    via.revogada_por = usuario if getattr(usuario, "is_authenticated", False) else None
    via.motivo_revogacao = (motivo or "").strip()[:300]
    via.save(update_fields=["revogada_em", "revogada_por", "motivo_revogacao"])


def pode_revogar(usuario, alvo: Alvo) -> bool:
    """Remover a via: quem pode anexar; no ofício, também depois de arquivado não."""
    return pode_anexar(usuario, alvo)


def revogar_do_oficio(usuario, oficio: Oficio, motivo: str) -> int:
    """Reabrir/retificar o ofício revoga as vias vigentes (referência: o ofício corrigido
    tem de ser assinado de novo)."""
    vias = list(ViaAssinada.objects.filter(oficio=oficio, revogada_em__isnull=True)
                .values_list("pk", flat=True))
    for pk in vias:
        revogar(usuario, pk, motivo=motivo, conferir=False)
    return len(vias)


def _registrar(alvo: Alvo, evento: str, usuario, via: ViaAssinada) -> None:
    """O ofício tem histórico de negócio próprio; no termo e na OS a linha do tempo lê as
    próprias vias (`linha_do_tempo._com_vias`), e a tabela é auditada pelo banco."""
    if isinstance(alvo.dono, Oficio):
        from .models import Historico
        doc = "da justificativa" if alvo.tipo == ViaAssinada.Tipo.JUSTIFICATIVA else "do ofício"
        if evento == "anexada":
            texto = f"Via assinada {doc} anexada ({via.nome_original})."
        else:
            texto = f"Via assinada {doc} removida" + (
                f": {via.motivo_revogacao}" if via.motivo_revogacao else ".")
        Historico.objects.create(oficio=alvo.dono, acao=Historico.Acao.ASSINADO,
                                 descricao=texto[:300],
                                 usuario=usuario if getattr(usuario, "is_authenticated",
                                                            False) else None,
                                 dados={"via": via.pk, "evento": evento})
