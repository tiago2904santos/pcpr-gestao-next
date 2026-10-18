"""O esqueleto de toda rota da API v1: autenticação pela credencial, escopo, limite de
concorrência por token, `Idempotency-Key` (com a impressão da requisição), desligamento (423
só nas operações que criam efeito novo) e o contexto de auditoria do usuário efetivo.

Erros sempre no formato `Erro` do contrato: `{"codigo", "mensagem"}` em português.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.db import IntegrityError, connection, transaction
from django.http import Http404, HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from gestao.plataforma import auditoria
from gestao.plataforma.middleware import ip_do_cliente

from .. import chaves
from ..models_api import CredencialIntegracao, RegistroIdempotencia
from . import credenciais

CONCORRENCIA_POR_TOKEN = 3
GUARDADOS = range(200, 300)
_MASCARAS = (
    (re.compile(r"https?://\S+"), "[url]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[e-mail]"),
    (re.compile(r"\b(pcpr|dlg)_[A-Za-z0-9_-]{8,}"), "[token]"),
    (re.compile(r"\+?\d[\d ()-]{9,}\d"), "[telefone]"),
)


def mascarar(texto: str, limite: int = 255) -> str:
    """Texto livre vindo do n8n (`detalhe`, `erro`): sem URL, e-mail, token nem telefone."""
    texto = str(texto or "")
    for padrao, troca in _MASCARAS:
        texto = padrao.sub(troca, texto)
    return " ".join(texto.split())[:limite]


def erro(status: int, codigo: str, mensagem: str, **extra) -> JsonResponse:
    return JsonResponse({"codigo": codigo, "mensagem": mensagem, **extra}, status=status)


class ErroApi(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str, **extra):
        super().__init__(mensagem)
        self.status, self.codigo, self.mensagem, self.extra = status, codigo, mensagem, extra

    def resposta(self) -> JsonResponse:
        return erro(self.status, self.codigo, self.mensagem, **self.extra)


@dataclass
class Chamada:
    request: HttpRequest
    credencial: CredencialIntegracao
    dados: dict
    correlacao: str


def _impressao(request: HttpRequest, sem: tuple[str, ...] = ()) -> str:
    """Impressão digital da requisição; `sem`: campos que não a distinguem (ex.: o horário de
    um status repetido pelo provedor — mesma chave, mesmo efeito)."""
    h = hashlib.sha256(f"{request.method} {request.path}\n".encode())
    tipo = (request.content_type or "").lower()
    if tipo.startswith("multipart/"):
        campos = sorted((k, v) for k, vs in request.POST.lists() for v in vs if k not in sem)
        h.update(json.dumps(campos, ensure_ascii=False).encode())
        for nome, arquivo in sorted(request.FILES.items()):
            if isinstance(arquivo, list):  # o stub admite []; o parser nunca grava lista vazia
                raise TypeError(f"Arquivo {nome!r} sem conteúdo no multipart.")
            conteudo = arquivo.read()
            arquivo.seek(0)
            h.update(f"\n{nome}:{hashlib.sha256(conteudo).hexdigest()}".encode())
    else:
        try:
            dados = json.loads(request.body or b"{}")
            if isinstance(dados, dict) and sem:
                dados = {k: v for k, v in dados.items() if k not in sem}
            canonico = json.dumps(dados, sort_keys=True, ensure_ascii=False,
                                  separators=(",", ":"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            canonico = hashlib.sha256(request.body).hexdigest()
        h.update(canonico.encode())
    return h.hexdigest()


def _dados(request: HttpRequest) -> dict:
    if request.method != "POST":
        return {}
    if (request.content_type or "").startswith("multipart/"):
        return {k: request.POST.get(k) for k in request.POST}
    try:
        dados = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ErroApi(422, "entrada_invalida", "O corpo não é JSON válido.") from e
    if not isinstance(dados, dict):
        raise ErroApi(422, "entrada_invalida", "O corpo precisa ser um objeto JSON.")
    return dados


def _vaga_trava(chave: str, i: int) -> int:
    return int.from_bytes(hashlib.sha256(f"{chave}:{i}".encode()).digest()[:8], "big",
                          signed=True)


def _entrar(chave: str) -> int | None:
    """Uma das `CONCORRENCIA_POR_TOKEN` vagas da credencial, como advisory lock de sessão do
    PostgreSQL: vale entre processos e réplicas (o cache local de cada processo não valia)."""
    with connection.cursor() as cursor:
        for i in range(CONCORRENCIA_POR_TOKEN):
            trava = _vaga_trava(chave, i)
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [trava])
            if cursor.fetchone()[0]:
                return trava
    return None


def _sair(trava: int) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_unlock(%s)", [trava])


def rota(escopo: str, *, metodo: str = "GET", desligamento: str = "aceita",
         impressao_sem: tuple[str, ...] = (),
         reuso_pelo_servico: Callable[[dict], str] | None = None):
    """`desligamento="recusa"`: com a chave geral desligada responde 423 (não guardado).
    `impressao_sem`: campos fora da impressão digital (repetição com outro horário = mesma).
    `reuso_pelo_servico(dados) -> chave de negócio`: mesma chave com outra requisição não é 422
    aqui SÓ quando o cabeçalho é a chave de negócio desta requisição (mesmo recebimento, outro
    arquivo) — o serviço decide
    (o recebimento responde 409 `conflito_de_versao` para outro arquivo, como o contrato)."""
    def decorar(funcao: Callable[[Chamada], JsonResponse]):
        @csrf_exempt  # máquina-a-máquina, autenticada pela credencial (Bearer)
        @login_not_required
        @never_cache
        @wraps(funcao)
        def view(request: HttpRequest, *args, **kwargs):
            if not getattr(settings, "AUTOMACAO_API_LIGADA", True):
                raise Http404
            if request.method != metodo:
                return erro(405, "entrada_invalida", f"Use {metodo} nesta rota.")
            c = credenciais.autenticar(request.headers.get("Authorization"))
            if c is None:
                return erro(401, "nao_autenticado", "Credencial ausente, inválida, revogada, "
                            "vencida, em emergência ou de outro ambiente.")
            if escopo not in (c.escopos or []):
                return erro(403, "negado", f"Esta credencial não tem o escopo {escopo}.")
            correlacao = (request.headers.get("X-PCPR-Correlacao") or "")[:120]
            vaga = _entrar(f"api-concorrencia:{c.pk}")
            if vaga is None:
                resposta = erro(429, "limite_excedido",
                                "Chamadas simultâneas demais para esta credencial.")
                resposta["Retry-After"] = "2"
                return resposta
            try:
                resposta = _executar(funcao, request, c, correlacao, metodo, desligamento,
                                     args, kwargs, impressao_sem, reuso_pelo_servico)
            finally:
                _sair(vaga)
            if correlacao:
                resposta["X-PCPR-Correlacao"] = correlacao
            return resposta
        return view
    return decorar


EM_ANDAMENTO = 0  # status do registro enquanto a primeira chamada executa


#: Mais que o tempo máximo de uma requisição (gunicorn): "em andamento" mais velho que isto é
#: de um processo que morreu entre reservar a chave e gravar a resposta.
PRAZO_EM_ANDAMENTO = timedelta(minutes=5)


def _assumir_abandonado(guardado: RegistroIdempotencia, impressao: str, request) -> bool:
    """Reserva "em andamento" abandonada (o processo saiu antes de gravar ou apagar o
    registro): a MESMA requisição assume a chave, renovando o prazo de forma atômica (só uma
    retentativa assume). É seguro executar de novo porque todo efeito da API é idempotente
    pela chave de negócio no serviço (reserva por tentativa, resultado por token, status por
    wamid+status, recebimento pela chave receb:, exceção pela chave, delegação de uso único):
    o que já tinha sido gravado volta como repetição, sem efeito novo."""
    if (guardado.status != EM_ANDAMENTO or guardado.impressao != impressao
            or guardado.rota != request.path[:120]):
        return False
    agora = timezone.now()
    return bool(RegistroIdempotencia.objects.filter(
        pk=guardado.pk, status=EM_ANDAMENTO, criado_em__lt=agora - PRAZO_EM_ANDAMENTO
    ).update(criado_em=agora))


def _repeticao(request, c, guardado: RegistroIdempotencia, impressao: str):
    if guardado.impressao != impressao or guardado.rota != request.path[:120]:
        return erro(422, "entrada_invalida", "Esta Idempotency-Key já foi usada com outra "
                    "requisição.")
    if guardado.status == EM_ANDAMENTO:
        resposta = erro(409, "ja_processada", "Uma chamada com esta Idempotency-Key ainda "
                        "está em andamento: repita em instantes.")
        resposta["Retry-After"] = "2"
        return resposta
    repetida: JsonResponse | None = None
    if isinstance(guardado.corpo, dict) and "_repetir" in guardado.corpo:
        from .views import repetir

        with auditoria.contexto(None, ip_do_cliente(request), f"api:{c.pk}"):
            repetida = repetir(guardado.corpo)
    if repetida is None:
        repetida = JsonResponse(guardado.corpo, status=guardado.status, safe=False)
    repetida["Idempotency-Replayed"] = "true"
    return repetida


def _executar(funcao, request, c, correlacao, metodo, desligamento, args, kwargs,
              impressao_sem: tuple[str, ...] = (),
              reuso_pelo_servico: Callable[[dict], str] | None = None):
    """A chave é RESERVADA antes do efeito (registro "em andamento", único por credencial e
    chave): duas chamadas simultâneas com a mesma chave não executam duas vezes. No fim, o
    registro guarda a resposta (2xx e 409) ou é apagado (423, 4xx, 5xx: repetir depois
    funciona)."""
    registro = None
    if metodo == "POST":
        chave = (request.headers.get("Idempotency-Key") or "").strip()
        if not 16 <= len(chave) <= 200:
            return erro(422, "entrada_invalida",
                        "Idempotency-Key é obrigatória (16 a 200 caracteres).")
        impressao = _impressao(request, impressao_sem)
        try:
            with transaction.atomic():
                registro = RegistroIdempotencia.objects.create(
                    credencial=c, chave=chave, rota=request.path[:120], impressao=impressao,
                    status=EM_ANDAMENTO, corpo={})
        except IntegrityError:
            guardado = RegistroIdempotencia.objects.get(credencial=c, chave=chave)
            outra = guardado.impressao != impressao and guardado.rota == request.path[:120]
            try:
                mesmo_recebimento = (reuso_pelo_servico is not None
                                     and reuso_pelo_servico(_dados(request)) == chave)
            except ErroApi:
                mesmo_recebimento = False
            if _assumir_abandonado(guardado, impressao, request):
                registro = guardado  # o processo da 1ª chamada morreu: esta chamada assume
            elif not (mesmo_recebimento and outra and guardado.status != EM_ANDAMENTO):
                return _repeticao(request, c, guardado, impressao)
            else:
                registro = None  # o serviço é idempotente pela própria chave e responde o 409
    try:
        if desligamento == "recusa" and not chaves.geral_ligada():
            resposta = erro(423, "desligada", "A automação está desligada: nada foi feito. O "
                            "processo segue manual até alguém religar.")
        else:
            usuario_id = c.usuario_id if c.tipo == CredencialIntegracao.Tipo.PESSOAL else None
            try:
                with auditoria.contexto(usuario_id, ip_do_cliente(request),
                                        getattr(request, "requisicao_id", "") or f"api:{c.pk}"):
                    chamada = Chamada(request, c, _dados(request), correlacao)
                    resposta = funcao(chamada, *args, **kwargs)
            except ErroApi as e:
                resposta = e.resposta()
    except Exception:
        if registro is not None:
            RegistroIdempotencia.objects.filter(pk=registro.pk).delete()
        raise
    if registro is not None:
        if resposta.status_code in GUARDADOS or resposta.status_code == 409:
            RegistroIdempotencia.objects.filter(pk=registro.pk).update(
                status=resposta.status_code,
                corpo=getattr(resposta, "corpo_guardado", None)
                or json.loads(resposta.content or b"{}"))
        else:
            RegistroIdempotencia.objects.filter(pk=registro.pk).delete()
    return resposta
