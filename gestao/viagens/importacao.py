"""Fila de importação: extração isolada, identificação pura e aplicação pelos serviços."""

from __future__ import annotations

import hashlib
import time
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from . import anexos, assinados, policies, termos
from .documentos.importador import LeituraInvalida, analisar
from .dominio.importacao import TIPOS, Destino, Parte, identificar_conjunto
from .models import (
    AnexoPrestacao,
    ArquivoImportado,
    Oficio,
    OrdemServico,
    ParteImportada,
    PrestacaoContas,
    PrestacaoServidor,
    TermoAutorizacao,
)


def exigir(usuario):
    policies.exigir(
        usuario.is_active and policies.edita_oficios(usuario),
        "Você precisa de permissão para editar documentos e importar arquivos.",
    )


def destinos_do_usuario(usuario) -> list[Destino]:
    exigir(usuario)
    destinos = []
    oficios = list(policies.oficios_visiveis(usuario).exclude(situacao="cancelado"))
    for o in oficios:
        for tipo in ("oficio", "justificativa", "despacho", "db_assinado"):
            destinos.append(
                Destino(
                    f"{tipo}:{o.pk}:", tipo, f"{TIPOS[tipo]} · {o}", o.numero, o.ano, o.protocolo
                )
            )
    por_id = {o.pk: o for o in oficios}
    pessoas = PrestacaoServidor.objects.filter(
        prestacao__oficio_id__in=por_id, removida_em__isnull=True
    ).select_related("servidor", "prestacao")
    for ps in pessoas:
        o = por_id[ps.prestacao.oficio_id]
        for tipo in ("rt_assinado", "comprovante"):
            destinos.append(
                Destino(
                    f"{tipo}:{o.pk}:{ps.pk}",
                    tipo,
                    f"{TIPOS[tipo]} · {ps.servidor.nome} · {o}",
                    o.numero,
                    o.ano,
                    o.protocolo,
                    ps.servidor.nome,
                    ps.servidor.cpf,
                )
            )
    for t in termos.com_dados(TermoAutorizacao.objects.filter(situacao="ativo")):
        if not policies.pode_editar_termo(usuario, t):
            continue
        ef = termos.efetivo(t)
        ligados: list[Oficio | None] = list(termos.oficios_do_termo(t))
        if not ligados:
            ligados.append(None)
        for doc in termos.documentos_do_termo(t, ef):
            pessoa = next((s for s in ef.servidores if str(s.pk) == doc["chave"]), None)
            for ligado in ligados:
                destinos.append(
                    Destino(
                        f"termo:{t.pk}:{doc['chave']}",
                        "termo",
                        f"{t} · {doc['titulo']}" + (f" · {ligado}" if ligado else ""),
                        ligado.numero if ligado else 0,
                        ligado.ano if ligado else 0,
                        ligado.protocolo if ligado else "",
                        pessoa.nome if pessoa else "",
                        pessoa.cpf if pessoa else "",
                        ef.inicio.strftime("%d/%m/%Y") if ef.inicio else "",
                        ef.periodo_extenso,
                    )
                )
    for ordem in OrdemServico.objects.filter(situacao="ativa"):
        if policies.pode_editar_ordem(usuario, ordem):
            destinos.append(
                Destino(f"ordem:{ordem.pk}:", "ordem", str(ordem), ordem.numero, ordem.ano)
            )
    return destinos


def _destino_permitido(usuario, chave: str) -> Destino | None:
    """Revalidação pontual: anexar N partes não relê o catálogo inteiro N vezes."""
    pedacos = chave.split(":", 2)
    if len(pedacos) != 3 or not pedacos[1].isdecimal() or pedacos[0] not in TIPOS:
        return None
    tipo, pk, pessoa = pedacos
    if tipo == "termo":
        t = TermoAutorizacao.objects.filter(pk=pk).first()
        if t and policies.pode_editar_termo(usuario, t):
            doc = next((d for d in termos.documentos_do_termo(t) if d["chave"] == pessoa), None)
            if doc:
                return Destino(chave, tipo, f"{t} · {doc['titulo']}")
    elif tipo == "ordem":
        ordem = OrdemServico.objects.filter(pk=pk).first()
        if ordem and not pessoa and policies.pode_editar_ordem(usuario, ordem):
            return Destino(chave, tipo, str(ordem))
    else:
        o = policies.oficios_visiveis(usuario).filter(pk=pk).exclude(situacao="cancelado").first()
        if o:
            if tipo in {"rt_assinado", "comprovante"}:
                if not pessoa.isdecimal():
                    return None
                ps = (
                    PrestacaoServidor.objects.filter(
                        pk=pessoa, prestacao__oficio=o, removida_em__isnull=True
                    )
                    .select_related("servidor")
                    .first()
                )
                if ps:
                    return Destino(chave, tipo, f"{TIPOS[tipo]} · {ps.servidor.nome} · {o}")
            elif not pessoa:
                return Destino(chave, tipo, f"{TIPOS[tipo]} · {o}")
    return None


@transaction.atomic
def receber(usuario, nome: str, dados: bytes) -> tuple[ArquivoImportado, bool]:
    exigir(usuario)
    if not dados or len(dados) > 25 * 1024 * 1024:
        raise LeituraInvalida("Envie arquivos de até 25 MB.")
    digest = hashlib.sha256(dados).hexdigest()
    registro, criado = ArquivoImportado.objects.get_or_create(
        usuario=usuario, sha256=digest, defaults={"nome": Path(nome).name[:255]}
    )
    if criado:
        registro.original.save(f"{digest}{Path(nome).suffix.lower()[:12]}", ContentFile(dados))
    else:
        registro = ArquivoImportado.objects.select_for_update().get(pk=registro.pk)
        if registro.estado == "erro":
            # Reenvio explícito permite tentar após corrigir conversor/permissão;
            # reutiliza o original e as partes já aplicadas, sem duplicá-las.
            registro.estado, registro.erro, registro.tentativas = "fila", "", 0
            registro.iniciado_em = registro.concluido_em = None
            registro.save(
                update_fields=["estado", "erro", "tentativas", "iniciado_em", "concluido_em"]
            )
    return registro, criado


@transaction.atomic
def reservar() -> int | None:
    limite = timezone.now() - timedelta(minutes=8)
    elegiveis = Q(estado="fila") | Q(estado="lendo", iniciado_em__lt=limite)
    # Uma entrada esgotada não pode esconder o restante da fila no modo --uma-vez.
    for esgotado in ArquivoImportado.objects.select_for_update(skip_locked=True).filter(
        elegiveis, tentativas__gte=3
    ):
        esgotado.estado = "erro"
        esgotado.erro = "A leitura foi interrompida três vezes. Exporte em PDF e reenvie."
        esgotado.save(update_fields=["estado", "erro"])
    registro = (
        ArquivoImportado.objects.select_for_update(skip_locked=True)
        .filter(elegiveis, tentativas__lt=3)
        .order_by("pk")
        .first()
    )
    if registro is None:
        return None
    registro.estado, registro.iniciado_em = "lendo", timezone.now()
    registro.tentativas += 1
    registro.save(update_fields=["estado", "iniciado_em", "tentativas"])
    return registro.pk


def atualizar_estado(pk: int):
    r = ArquivoImportado.objects.get(pk=pk)
    r.estado = "revisao" if r.partes.filter(estado="revisao").exists() else "concluido"
    r.concluido_em = timezone.now()
    r.save(update_fields=["estado", "concluido_em"])


def processar(pk: int):
    inicio = time.monotonic()
    registro = ArquivoImportado.objects.select_related("usuario").get(pk=pk)
    try:
        exigir(registro.usuario)
        if not registro.partes.exists():
            with registro.original.open("rb") as f:
                resultado, convertido, conteudos = analisar(f.read(), registro.nome)
            destinos = destinos_do_usuario(registro.usuario)
            with transaction.atomic():
                registro = ArquivoImportado.objects.select_for_update().get(pk=pk)
                if not registro.partes.exists():
                    registro.convertido.save("convertido.pdf", ContentFile(convertido), save=False)
                    registro.paginas, registro.paginas_ocr = resultado["paginas"], resultado["ocr"]
                    registro.save(update_fields=["convertido", "paginas", "paginas_ocr"])
                    decisoes = identificar_conjunto(
                        [
                            Parte(p["inicio"], p["fim"], p["tipo"], p["texto"])
                            for p in resultado["partes"]
                        ],
                        destinos,
                    )
                    for p, conteudo, decisao in zip(
                        resultado["partes"], conteudos, decisoes, strict=True
                    ):
                        parte = ParteImportada(
                            importacao=registro,
                            inicio=p["inicio"],
                            fim=p["fim"],
                            tipo=p["tipo"],
                            destino=decisao.chave,
                            motivo=decisao.motivo,
                            candidatos=list(decisao.candidatos),
                            sha256=hashlib.sha256(conteudo).hexdigest(),
                        )
                        parte.arquivo.save("documento.pdf", ContentFile(conteudo), save=False)
                        parte.save()
        for parte in registro.partes.filter(estado="revisao").exclude(destino=""):
            try:
                aplicar(registro.usuario, parte.pk, parte.destino)
            except (LeituraInvalida, PermissionDenied) as exc:
                ParteImportada.objects.filter(pk=parte.pk).update(motivo=str(exc)[:500])
        atualizar_estado(pk)
    except (LeituraInvalida, PermissionDenied) as exc:
        ArquivoImportado.objects.filter(pk=pk).update(estado="erro", erro=str(exc)[:500])
    finally:
        ArquivoImportado.objects.filter(pk=pk).update(
            duracao_ms=max(0, int((time.monotonic() - inicio) * 1000))
        )


@transaction.atomic
def aplicar(
    usuario, pk: int, destino: str, *, confirmar: bool = False, revisao: bool = False
) -> ParteImportada:
    exigir(usuario)
    parte = (
        ParteImportada.objects.select_for_update()
        .select_related("importacao")
        .get(pk=pk, importacao__usuario=usuario)
    )
    if parte.estado in {"anexado", "repetido", "ignorado"}:
        return parte
    permitido = _destino_permitido(usuario, destino)
    if permitido is None:
        raise LeituraInvalida(
            "O destino não está disponível. Atualize a página e escolha novamente."
        )
    tipo, registro_id, chave = destino.split(":", 2)
    with parte.arquivo.open("rb") as f:
        conteudo = f.read()
    nome = f"{Path(parte.importacao.nome).stem}-p{parte.inicio}-{parte.fim}.pdf"
    try:
        if tipo in {"oficio", "justificativa", "termo", "ordem"}:
            modelo = (
                TermoAutorizacao if tipo == "termo" else OrdemServico if tipo == "ordem" else Oficio
            )
            dono = modelo.objects.select_for_update().get(pk=registro_id)
            alvo = assinados.Alvo(tipo, dono, chave)
            policies.exigir(
                assinados.pode_anexar(usuario, alvo),
                "Gere o documento e confira a permissão antes de anexar a via.",
            )
            vigente = assinados.vigente(alvo)
            if vigente and vigente.sha256 == parte.sha256:
                parte.via, parte.estado = vigente, "repetido"
            elif vigente and not confirmar:
                raise LeituraInvalida(
                    "Já existe uma via diferente. Confira e confirme a substituição."
                )
            else:
                parte.via = assinados.anexar(usuario, alvo, nome=nome, conteudo=conteudo)
                parte.estado = "anexado"
        else:
            prestacao = (
                PrestacaoContas.objects.select_for_update().filter(oficio_id=registro_id).first()
            )
            if prestacao is None:
                raise LeituraInvalida(
                    "Este ofício ainda não tem prestação. Emita o ofício primeiro."
                )
            ps = PrestacaoServidor.objects.filter(pk=chave or 0, prestacao=prestacao).first()
            anexos._conferir_dono(usuario, prestacao, ps)
            vigentes = anexos.ativos(
                AnexoPrestacao.objects.filter(prestacao=prestacao, tipo=tipo, servidor=ps)
            )
            igual = vigentes.filter(sha256=parte.sha256).first()
            if igual:
                parte.anexo, parte.estado = igual, "repetido"
            elif tipo in anexos.UNICOS and vigentes.exists() and not confirmar:
                raise LeituraInvalida(
                    "Já existe uma via diferente. Confira e confirme a substituição."
                )
            else:
                parte.anexo = anexos.anexar(
                    usuario,
                    prestacao.pk,
                    tipo,
                    nome=nome,
                    conteudo=conteudo,
                    servidor_pk=ps.pk if ps else None,
                )
                parte.estado = "anexado"
    except (assinados.ArquivoAssinadoInvalido, anexos.AnexoInvalido) as exc:
        raise LeituraInvalida(str(exc)) from exc
    parte.destino, parte.tipo, parte.rotulo = destino, tipo, permitido.rotulo
    parte.aplicado_em = timezone.now()
    if confirmar or revisao:
        parte.revisado_por = usuario
        parte.motivo = "Destino confirmado na revisão."
    parte.save()
    return parte
