"""PDFs da nota fiscal e da ordem bancária (CB5b; paridade com `coffee_break/services.py`
§4.1 e §4.4): anexar lê o texto e sugere o número, guarda valor/emissão/CNPJ para a
conferência (que só avisa); a OB vale para todas as OS do pagamento e, sendo o próximo
marco, registra a data lida. Mensagens da referência."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from . import conjunto, policies
from . import dominio_leitura as leitura
from . import dominio_pedido as regras
from .certidoes import texto_do_pdf
from .forms import conferir_pdf
from .models import Movimento, Solicitacao
from .pedidos import PedidoInvalido


@dataclass
class Resultado:
    mensagem: str
    aviso: bool = False


def _travar(usuario, pk: int) -> Solicitacao:
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    s = Solicitacao.objects.select_for_update().get(pk=pk)
    if s.bloqueada:
        raise PedidoInvalido(regras.MSG_BLOQUEADA)
    return s


def _conferir(arquivo) -> None:
    if not arquivo:
        raise PedidoInvalido("Envie o arquivo em PDF.")
    try:
        conferir_pdf(arquivo)
    except ValidationError as exc:
        raise PedidoInvalido(" ".join(exc.messages)) from None


def _mover(s: Solicitacao, usuario, texto: str) -> None:
    Movimento.objects.create(solicitacao=s, acao=Movimento.Acao.DOCUMENTO, texto=texto,
                             usuario=usuario)


def _apagar_se_orfao(nome: str | None, campo: str) -> None:
    """O arquivo só sai do disco quando nenhuma OS aponta mais para ele."""
    if not nome or Solicitacao.objects.filter(**{campo: nome}).exists():
        return
    storage = (Solicitacao.nota_pdf if campo == "nota_pdf" else Solicitacao.ob_pdf).field.storage
    transaction.on_commit(lambda: storage.delete(nome))


@transaction.atomic
def anexar_nota(usuario, pk: int, arquivo) -> Resultado:
    s = _travar(usuario, pk)
    _conferir(arquivo)
    nota = leitura.ler_nota(texto_do_pdf(arquivo))
    antigo = s.nota_pdf.name if s.nota_pdf else ""
    s.nota_pdf = arquivo
    s.nota_valor, s.nota_emissao, s.nota_cnpj = nota.valor, nota.emissao, nota.cnpj
    if not s.nota_fiscal and nota.numero:
        s.nota_fiscal = nota.numero
    s.save()
    _apagar_se_orfao(antigo, "nota_pdf")
    acao = "substituída" if antigo else "anexada"
    _mover(s, usuario, f"Nota fiscal (PDF) {acao}" + (
        f"; número {nota.numero} lido do PDF." if nota.numero else "."))
    if nota.numero:
        return Resultado(f"Nota fiscal {nota.numero} anexada — o número foi lido do PDF.")
    return Resultado("Nota fiscal anexada, mas não deu para ler o número no PDF: informe-o no "
                     "campo ao lado.", aviso=True)


@transaction.atomic
def remover_nota(usuario, pk: int) -> Resultado:
    s = _travar(usuario, pk)
    antigo = s.nota_pdf.name if s.nota_pdf else ""
    if not antigo:
        raise PedidoInvalido("Esta solicitação não tem o PDF da nota.")
    s.nota_pdf = None
    s.nota_valor, s.nota_emissao, s.nota_cnpj = None, None, ""
    s.save(update_fields=["nota_pdf", "nota_valor", "nota_emissao", "nota_cnpj",
                          "atualizado_em"])
    _apagar_se_orfao(antigo, "nota_pdf")
    _mover(s, usuario, "Nota fiscal (PDF) removida.")
    return Resultado("Nota fiscal removida.")


def avisos_da_nota(s: Solicitacao) -> list[str]:
    if not s.nota_pdf:
        return []
    fornecedor = s.lote.contrato.fornecedor
    repetida = (Solicitacao.objects.filter(nota_fiscal=s.nota_fiscal, cancelada=False,
                                           lote__contrato__fornecedor=fornecedor)
                .exclude(pk=s.pk).first() if s.nota_fiscal else None)
    return leitura.avisos_da_nota(
        leitura.Nota(s.nota_fiscal, s.nota_cnpj, s.nota_valor, s.nota_emissao),
        cnpj_fornecedor=fornecedor.cnpj, razao=fornecedor.razao_social,
        cnpj_formatado=fornecedor.cnpj_formatado, quantidade=s.quantidade_efetiva,
        unitario=s.valor_unitario, data_evento=s.data_evento,
        repetida_em=str(repetida) if repetida else "")


@transaction.atomic
def anexar_ob(usuario, pk: int, arquivo) -> Resultado:
    """A OB vale para todas as OS do pagamento; sendo o próximo marco, a data lida (ou
    hoje; se anterior ao atesto, hoje) entra — sem atesto, avisa."""
    s = _travar(usuario, pk)
    if not s.nota_fiscal:
        raise PedidoInvalido("Registre a nota fiscal antes da ordem bancária.")
    _conferir(arquivo)
    ob = leitura.ler_ob(texto_do_pdf(arquivo))
    antigos = {x.ob_pdf.name for x in conjunto.membros(s) if x.ob_pdf}
    s.ob_pdf = arquivo
    s.ob_numero, s.ob_valor = ob.numero, ob.valor
    hoje = timezone.localdate()
    texto_data = ""
    marco = regras.proximo_marco(s.valores_dos_marcos, s.cancelada)
    if marco and marco[0] == "ordem_bancaria_em" and s.atesto_em:
        data = ob.data or hoje
        if data < s.atesto_em:
            data = hoje
        s.ordem_bancaria_em = data
        origem = " (data lida do PDF)" if ob.data and data == ob.data else ""
        texto_data = f"; OB emitida em {data:%d/%m/%Y}{origem}"
    elif marco and marco[0] == "atesto_em":
        texto_data = "; registre o atesto para a data da OB entrar"
    s.save()
    for outra in conjunto.membros(s):
        if outra.pk != s.pk:
            Solicitacao.objects.filter(pk=outra.pk).update(
                ob_pdf=s.ob_pdf.name, ob_numero=s.ob_numero, ob_valor=s.ob_valor)
    conjunto.espelhar(s, usuario, ["ordem_bancaria_em"])
    for nome in antigos - {s.ob_pdf.name}:
        _apagar_se_orfao(nome, "ob_pdf")
    numero = f" — nº {ob.numero} lido do PDF" if ob.numero else ""
    _mover(s, usuario, f"Ordem bancária (PDF) anexada{numero}{texto_data}.")
    return Resultado(f"Ordem bancária anexada{numero}{texto_data}.",
                     aviso="registre o atesto" in texto_data)


@transaction.atomic
def remover_ob(usuario, pk: int) -> Resultado:
    s = _travar(usuario, pk)
    if not s.ob_pdf:
        raise PedidoInvalido("Esta solicitação não tem o PDF da ordem bancária.")
    nome = s.ob_pdf.name
    for x in conjunto.membros(s):
        Solicitacao.objects.filter(pk=x.pk).update(ob_pdf="", ob_numero="", ob_valor=None)
    _apagar_se_orfao(nome, "ob_pdf")
    _mover(s, usuario, "Ordem bancária (PDF) removida.")
    return Resultado("Ordem bancária removida.")


def aviso_da_ob(s: Solicitacao) -> str:
    if not s.ob_pdf or s.ob_valor is None:
        return ""
    grupo = conjunto.membros(s)
    valores = [x.nota_valor if x.nota_valor is not None else x.valor for x in grupo]
    if any(v is None for v in valores):
        return ""
    return leitura.aviso_da_ob(s.ob_valor, sum((v for v in valores if v is not None),
                                               Decimal("0")))
