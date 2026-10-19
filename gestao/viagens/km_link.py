"""Link de km na véspera (fluxo 10-4): quem responde pelo km do diário, até quando o link
vale, o que a página pública mostra e como um lançamento feito no celular entra no diário.

Regras (docs/automacao/fluxos/10-4-link-de-km-na-vespera.md, "Implementação (18/10/2026)"):

- o responsável é o motorista que o diário reconhece **e que tem cadastro** (`Servidor`): o
  da equipe, o servidor de outro ofício ou o servidor trocado no diário. Pessoa não
  cadastrada e "motorista de outro ofício" (o km é o daquele diário) ficam sem link;
- a página mostra só os trechos deste diário: municípios, data da saída e distância
  prevista. Nada de placa, CPF, equipe ou outra viagem;
- cada lançamento leva um id gerado no aparelho e os valores que a pessoa via quando
  editou (`base`). Grava-se só se o valor do sistema ainda é o da base (ou já é o novo);
  senão é **conflito** e nada muda. O mesmo id de novo não grava outra vez: a alteração da
  linha fica na trilha de auditoria com `requisicao_id = "km:<diário>:<id>"`, e é ela que
  diz que aquele lançamento já entrou (a trilha é do banco e imutável — só lemos);
- quem age é a pessoa que agendou o envio do link (como no recebimento automático, ADR
  0047): as policies do diário valem para ela, e sem ela não se grava nada. Não existe
  usuário "de sistema". A IA nunca preenche km.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from gestao.plataforma import auditoria

from . import diario as servico_diario
from . import realizado
from .models import DiarioBordo, DiarioBordoTrecho, Oficio, Trecho, TrechoRealizado, Viajante

ESCOPO = "km"  # LinkAcesso.Escopo.KM
RECURSO = "viagens.diario"
KM_MAXIMO = 9_999_999
RODADO_MAXIMO = 5_000  # num trecho, por estrada: além disso é erro de digitação
DIAS_DEPOIS_DA_CHEGADA = 5
MAX_LANCAMENTOS = 50
CAMPOS = ("km_inicial", "km_final")
ID_VALIDO = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
ROTEIRO_MUDOU = "O roteiro desta viagem mudou: recarregue a página e confira o trecho."


class Bloqueio(Exception):
    """O link não aceita lançamento agora (travado, suspenso, sem quem responda)."""

    def __init__(self, codigo: str, mensagem: str):
        super().__init__(mensagem)
        self.codigo, self.mensagem = codigo, mensagem


# ------------------------------------------------------------------ recurso e responsável
def recurso(diario_pk: int) -> str:
    return f"{RECURSO}:{diario_pk}"


def diario_do_recurso(texto: str) -> DiarioBordo | None:
    prefixo, _, pk = str(texto or "").partition(":")
    if prefixo != RECURSO or not pk.isdigit():
        return None
    return (DiarioBordo.objects.select_related("prestacao__oficio__unidade",
                                               "motorista_servidor")
            .filter(pk=int(pk)).first())


def responsavel(diario: DiarioBordo):
    """O `Servidor` que responde pelo km deste diário, ou None (sem cadastro: o link, se
    houver, é entregue à mão pelo setor)."""
    if diario.motorista_modo == DiarioBordo.Motorista.OUTRO:
        return None  # o km é o do diário do outro ofício (que tem o seu próprio link)
    if diario.motorista_modo == DiarioBordo.Motorista.SERVIDOR:
        return diario.motorista_servidor
    oficio = diario.prestacao.oficio
    if oficio.motorista_externo == Oficio.MotoristaExterno.SERVIDOR:
        return oficio.motorista_externo_servidor
    if oficio.motorista_externo == Oficio.MotoristaExterno.MANUAL:
        return None
    v = (Viajante.objects.filter(oficio=oficio, motorista=True).select_related("servidor")
         .first())
    return v.servidor if v else None


# ------------------------------------------------------------------ tempo
def periodo(diario: DiarioBordo) -> tuple[datetime, datetime] | None:
    """(primeira saída, última chegada) pela fonte que o diário usa: os trechos realizados,
    se a viagem foi ajustada, senão os do ofício."""
    fontes: list[TrechoRealizado] | list[Trecho] = realizado.trechos(diario.prestacao) or list(
        diario.prestacao.oficio.trechos.order_by("ordem"))
    if not fontes:
        return None
    return min(t.saida_em for t in fontes), max(t.chegada_em for t in fontes)


def valido_ate(chegada: datetime) -> datetime:
    """Até 23:59:59 (local) do 5º dia depois da chegada final."""
    dia = timezone.localtime(chegada).date() + timedelta(days=DIAS_DEPOIS_DA_CHEGADA)
    return timezone.make_aware(datetime.combine(dia, time(23, 59, 59)))


def versao(diario: DiarioBordo) -> str:
    """Mudou o responsável, a saída ou a chegada: é outra mensagem (a anterior, se ainda
    não saiu, fica obsoleta no envio)."""
    pessoa = responsavel(diario)
    datas = periodo(diario)
    base = (f"{diario.pk}|{getattr(pessoa, 'pk', '')}|"
            f"{datas[0].isoformat() if datas else ''}|{datas[1].isoformat() if datas else ''}")
    return hashlib.sha256(base.encode()).hexdigest()[:16]


def motivo_inelegivel(diario: DiarioBordo, agora: datetime | None = None) -> str:
    """Vazio se o diário pode receber o link agora; senão, o motivo (vira "obsoleta")."""
    agora = agora or timezone.now()
    oficio = diario.prestacao.oficio
    if oficio.situacao != Oficio.Situacao.EMITIDO:
        return "O ofício não está emitido."
    if oficio.tipo_transporte != Oficio.TipoTransporte.VIATURA:
        return "A viagem não é de viatura."
    if responsavel(diario) is None:
        return "O diário não tem motorista com cadastro."
    if servico_diario.equipe_finalizada(diario.prestacao):
        return "A prestação de contas já foi finalizada."
    datas = periodo(diario)
    if datas is None:
        return "O ofício não tem trechos."
    if agora > valido_ate(datas[1]):
        return "A viagem terminou há mais tempo do que o link vale."
    return ""


# ------------------------------------------------------------------ a página
def chave_da_linha(linha: DiarioBordoTrecho) -> str:
    return f"r:{linha.realizado_id}" if linha.realizado_id else f"t:{linha.trecho_id}"


def _quando(momento: datetime | None) -> str:
    if momento is None:
        return ""
    local = timezone.localtime(momento)
    if local.date() == timezone.localdate():
        return f"às {local:%H:%M}"
    return f"em {local:%d/%m} às {local:%H:%M}"


@dataclass(frozen=True)
class LinhaPublica:
    pk: int
    chave: str
    numero: int
    rota: str
    data: str              # dd/mm/aaaa da saída (sem horário)
    prevista: int | None   # referência; nunca vira km
    km_inicial: int | None
    km_final: int | None
    salvo: str             # "às 14:05" / "em 09/11 às 14:05" — vazio se não há km

    @property
    def completa(self) -> bool:
        return self.km_inicial is not None and self.km_final is not None


def projecao(diario: DiarioBordo) -> list[LinhaPublica]:
    """O que a página mostra, só lendo (o GET não sincroniza nem grava)."""
    saida = []
    for linha in servico_diario.linhas(diario):
        fonte = servico_diario.fonte(linha)
        origem = f"{fonte.origem.nome}/{fonte.origem.uf}" if fonte else ""
        destino = f"{fonte.destino.nome}/{fonte.destino.uf}" if fonte else ""
        tem_km = linha.km_inicial is not None or linha.km_final is not None
        saida.append(LinhaPublica(
            pk=linha.pk, chave=chave_da_linha(linha), numero=linha.ordem + 1,
            rota=f"{origem} → {destino}" if fonte else f"Trecho {linha.ordem + 1}",
            data=f"{timezone.localtime(fonte.saida_em):%d/%m/%Y}" if fonte else "",
            prevista=servico_diario.prevista(linha), km_inicial=linha.km_inicial,
            km_final=linha.km_final, salvo=_quando(linha.atualizado_em) if tem_km else ""))
    return saida


@dataclass(frozen=True)
class Situacao:
    disponivel: bool                # False: a página "Link indisponível" (404)
    somente_leitura: str = ""       # motivo, quando abre mas não grava
    codigo: str = ""                # "suspenso" | "travado" (para o JSON)


def situacao(link, diario: DiarioBordo | None) -> Situacao:
    """Ofício cancelado, diário inexistente ou link de outra pessoa: indisponível (a mesma
    resposta de link vencido). Ofício em correção ou prestação finalizada: só leitura."""
    if diario is None:
        return Situacao(False)
    oficio = diario.prestacao.oficio
    if oficio.situacao == Oficio.Situacao.CANCELADO:
        return Situacao(False)
    pessoa = responsavel(diario)
    if pessoa is None or pessoa.pk != link.servidor_id:
        return Situacao(False)
    if oficio.situacao != Oficio.Situacao.EMITIDO:
        return Situacao(True, "A viagem está sendo corrigida pelo setor. Os km digitados "
                              "ficam guardados neste aparelho; tente enviar mais tarde.",
                        "suspenso")
    if servico_diario.equipe_finalizada(diario.prestacao):
        return Situacao(True, "A prestação de contas desta viagem já foi finalizada. Para "
                              "corrigir algum km, fale com o setor de viagens.", "travado")
    return Situacao(True)


# ------------------------------------------------------------------ lançamentos
def quem_age(link):
    """A pessoa que agendou o envio do link (ou que o gerou à mão)."""
    comunicacao = getattr(link, "comunicacao", None)
    usuario = getattr(comunicacao, "criada_por", None) or getattr(link, "criado_por", None)
    return usuario if getattr(usuario, "is_active", False) else None


def km_digitado(valor) -> tuple[bool, int | None]:
    """(válido, número). Vazio = apagar. Só dígitos (o ponto de milhar é aceito); nada de
    sinal, vírgula, letra ou mais de 7 dígitos."""
    if valor is None:
        return True, None
    if isinstance(valor, bool):
        return False, None
    if isinstance(valor, int):
        return (0 <= valor <= KM_MAXIMO), valor
    texto = str(valor).strip().replace(".", "").replace(" ", "")
    if texto == "":
        return True, None
    if not texto.isdigit() or len(texto) > 7:
        return False, None
    numero = int(texto)
    return numero <= KM_MAXIMO, numero


@dataclass
class Resultado:
    id: str
    situacao: str                    # gravado | recusado | conflito
    mensagem: str
    linha: int | None = None
    servidor: dict = field(default_factory=dict)   # o que está no sistema agora
    seu: dict = field(default_factory=dict)        # o que a pessoa mandou (conflito)
    salvo: str = ""

    def como_dict(self) -> dict:
        return {"id": self.id, "situacao": self.situacao, "mensagem": self.mensagem,
                "linha": self.linha, "servidor": self.servidor, "seu": self.seu,
                "salvo": self.salvo}


def _ja_entrou(linha_pk: int, requisicao: str) -> bool:
    from gestao.plataforma.models import EventoAuditoria

    return EventoAuditoria.objects.filter(
        tabela=DiarioBordoTrecho._meta.db_table, registro_id=str(linha_pk),
        requisicao_id=requisicao).exists()


def _valores(linha: DiarioBordoTrecho) -> dict:
    return {"km_inicial": linha.km_inicial, "km_final": linha.km_final}


def _aplicar_um(diario: DiarioBordo, usuario, item: dict, ip: str | None,
                recusa: str = "") -> Resultado:
    ident = str(item.get("id") or "")
    if not ID_VALIDO.match(ident):
        return Resultado(ident[:64], "recusado", "Lançamento sem identificação válida.")
    linha_bruta = item.get("linha")
    if linha_bruta is None:  # int(None) cairia no TypeError abaixo
        return Resultado(ident, "recusado", ROTEIRO_MUDOU)
    try:
        linha_pk = int(linha_bruta)
    except (TypeError, ValueError):
        return Resultado(ident, "recusado", ROTEIRO_MUDOU)
    linha = (DiarioBordoTrecho.objects.select_for_update()
             .filter(diario=diario, pk=linha_pk).first())
    if linha is None or str(item.get("chave") or "") != chave_da_linha(linha):
        return Resultado(ident, "recusado", ROTEIRO_MUDOU, linha_pk)
    requisicao = f"km:{diario.pk}:{ident}"
    if _ja_entrou(linha.pk, requisicao):
        return Resultado(ident, "gravado", "Já estava salvo no sistema.", linha.pk,
                         _valores(linha), salvo=_quando(linha.atualizado_em))
    campos_brutos, base_bruta = item.get("campos"), item.get("base")
    campos: dict = campos_brutos if isinstance(campos_brutos, dict) else {}
    base: dict = base_bruta if isinstance(base_bruta, dict) else {}
    novos: dict[str, int | None] = {}
    for nome in CAMPOS:
        if nome not in campos:
            continue
        ok, numero = km_digitado(campos[nome])
        ok_base, numero_base = km_digitado(base.get(nome))
        if not ok or not ok_base:
            return Resultado(ident, "recusado", "Use só números no km (até 9.999.999), "
                             "sem vírgula nem letras.", linha.pk, _valores(linha))
        if numero != numero_base:  # igual à base: a pessoa não mexeu neste campo
            novos[nome] = numero
            base[nome] = numero_base
    if not novos:
        return Resultado(ident, "recusado", "Nada mudou neste trecho.", linha.pk,
                         _valores(linha))
    aplicar: dict[str, int | None] = {}
    conflito = False
    for nome, numero in novos.items():
        atual = getattr(linha, nome)
        if atual == numero:
            continue
        if atual == base.get(nome):
            aplicar[nome] = numero
        else:
            conflito = True
    if conflito:
        return Resultado(ident, "conflito", "Este trecho foi alterado no sistema depois que "
                         "você digitou. Escolha qual valor fica.", linha.pk, _valores(linha),
                         dict(novos), _quando(linha.atualizado_em))
    inicial = aplicar.get("km_inicial", linha.km_inicial)
    final = aplicar.get("km_final", linha.km_final)
    if inicial is not None and final is not None:
        if final < inicial:
            return Resultado(ident, "recusado", "O km de chegada não pode ser menor que o "
                             "de saída.", linha.pk, _valores(linha))
        if final - inicial > RODADO_MAXIMO:
            return Resultado(ident, "recusado", "Mais de 5.000 km num só trecho: confira "
                             "os números.", linha.pk, _valores(linha))
    if not aplicar:
        return Resultado(ident, "gravado", "Já estava salvo no sistema.", linha.pk,
                         _valores(linha), salvo=_quando(linha.atualizado_em))
    if recusa:
        return Resultado(ident, "recusado", recusa, linha.pk, _valores(linha))
    try:
        # O diário já está travado e conferido por `aplicar`: grava só esta linha (antes
        # cada lançamento travava, conferia e relia o diário inteiro de novo).
        with transaction.atomic(), auditoria.contexto(usuario.pk, ip, requisicao):
            if servico_diario.gravar_linha(linha, {
                    nome: "" if numero is None else str(numero)
                    for nome, numero in aplicar.items()}):
                diario.save(update_fields=["atualizado_em"])
    except servico_diario.DiarioInvalido as erro:
        linha.refresh_from_db()
        return Resultado(ident, "recusado", str(erro), linha.pk, _valores(linha))
    return Resultado(ident, "gravado", "Salvo no sistema.", linha.pk, _valores(linha),
                     salvo=_quando(linha.atualizado_em))


def aplicar(link, lancamentos: list, *, ip: str | None = None) -> list[Resultado]:
    """Aplica até 50 lançamentos do aparelho, cada um num savepoint. Repetir a mesma lista
    devolve o mesmo resultado sem gravar de novo. `Bloqueio` quando nada pode entrar."""
    if not isinstance(lancamentos, list) or len(lancamentos) > MAX_LANCAMENTOS:
        raise Bloqueio("formato", f"Mande até {MAX_LANCAMENTOS} lançamentos por vez.")
    with transaction.atomic():
        diario = diario_do_recurso(link.recurso)
        if diario is not None:
            diario = (DiarioBordo.objects.select_for_update(of=("self",))
                      .select_related("prestacao__oficio", "motorista_servidor")
                      .get(pk=diario.pk))
        estado = situacao(link, diario)
        if not estado.disponivel or diario is None:
            raise Bloqueio("indisponivel", "Link indisponível.")
        if estado.somente_leitura:
            raise Bloqueio(estado.codigo, estado.somente_leitura)
        usuario = quem_age(link)
        if usuario is None:
            raise Bloqueio("sem_responsavel", "O setor de viagens precisa enviar um link "
                           "novo para este diário.")
        try:  # uma vez por lote: prestação aberta e permissão de quem o link representa
            servico_diario.conferir_edicao(usuario, diario)
            recusa = ""
        except servico_diario.DiarioInvalido as erro:
            recusa = str(erro)
        except PermissionDenied:
            recusa = "O setor de viagens precisa enviar um link novo para este diário."
        if not recusa:  # sincronizar MUDA as linhas: só para quem ainda pode editar
            with auditoria.contexto(usuario.pk, ip, f"km:{diario.pk}:sincronizar"):
                servico_diario.sincronizar(diario)  # no POST, nunca no GET
        resultados = [_aplicar_um(diario, usuario, item if isinstance(item, dict) else {}, ip,
                                  recusa) for item in lancamentos]
        if any(r.situacao == "gravado" for r in resultados):
            from gestao.automacao import links

            links.registrar_uso(link, lancamento=True)
    return resultados
