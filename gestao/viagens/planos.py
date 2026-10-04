"""Planos de trabalho (paridade com `viagens_planos` da referência): numeração anual com
lacunas e sufixo, criação a partir de ofícios (destino, datas, efetivo e deslocamento),
textos automáticos com a regra de "voltar ao automático", diárias de um trecho (cópia
gravada), ciclo de vida e o documento.

As regras e os textos estão em `dominio/plano_trabalho.py`; aqui, o banco e a transação.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime

from django.db import transaction
from django.db.models import Prefetch, prefetch_related_objects
from django.utils import timezone

from gestao.cadastros.models import (
    AtividadePlano,
    Cargo,
    ConfiguracaoInstitucional,
    Municipio,
    ProgramaSolicitante,
    Servidor,
    Unidade,
)
from gestao.cadastros.services import quem_assina

from . import policies
from .dominio import plano_trabalho as dominio
from .dominio.escrita import data_por_extenso, legivel
from .dominio.numeracao import proximo_numero
from .models import (
    EfetivoPlano,
    EventoDestino,
    EventoPlano,
    LacunaPlano,
    NumeracaoPlano,
    Oficio,
    PlanoDestino,
    PlanoTrabalho,
    Trecho,
    Viajante,
)
from .queries import buscar_tabelas_vigentes

MAX_OFICIOS, MAX_DESTINOS, MAX_LINHAS, MAX_EVENTOS = 20, 30, 50, 20


class PlanoInvalido(Exception):
    """Erro com mensagem pronta para o usuário."""


@dataclass(frozen=True)
class LinhaInformada:
    cargo: Cargo
    quantidade: int
    unidade: Unidade | None = None


PREFETCH_PLANOS = (
    Prefetch("destinos", queryset=PlanoDestino.objects.select_related("municipio")),
    Prefetch("efetivo", queryset=EfetivoPlano.objects.select_related("cargo", "unidade")),
    Prefetch("atividades", queryset=AtividadePlano.objects.order_by("nome")),
    Prefetch("oficios", queryset=Oficio.objects.order_by("-ano", "-numero")),
    Prefetch("eventos", queryset=EventoPlano.objects.select_related(
        "programa", "coordenador_op__cargo").prefetch_related(
        Prefetch("destinos", queryset=EventoDestino.objects.select_related("municipio")),
        Prefetch("atividades", queryset=AtividadePlano.objects.order_by("nome")))),
)


def com_dados(qs):
    return qs.select_related(
        "unidade", "programa", "assinante__cargo", "coordenador_adm__cargo",
        "coordenador_op__cargo").prefetch_related(*PREFETCH_PLANOS)


def carregar(plano: PlanoTrabalho) -> PlanoTrabalho:
    if not hasattr(plano, "_prefetched_objects_cache"):
        prefetch_related_objects([plano], *PREFETCH_PLANOS)
    return plano


def versao_de(plano: PlanoTrabalho) -> str:
    """A versão que a tela guarda para não gravar por cima de outra pessoa."""
    return plano.atualizado_em.isoformat() if plano.atualizado_em else ""


# ---------------------------------------------------------------- numeração
def reservar_numero(ano: int) -> int:
    """Próximo número do ano (menor lacuna liberada por exclusão, senão o maior + 1); trava
    a linha do ano; a lacuna usada deixa de existir."""
    linha, _ = NumeracaoPlano.objects.get_or_create(ano=ano)
    NumeracaoPlano.objects.select_for_update().get(pk=linha.pk)
    ocupados = PlanoTrabalho.objects.filter(ano=ano).values_list("numero", flat=True)
    lacunas = LacunaPlano.objects.filter(ano=ano).values_list("numero", flat=True)
    numero = proximo_numero(ocupados, 1, lacunas)
    LacunaPlano.objects.filter(ano=ano, numero=numero).delete()
    return numero


def proximo_numero_do_ano(ano: int) -> int:
    ocupados = PlanoTrabalho.objects.filter(ano=ano).values_list("numero", flat=True)
    lacunas = LacunaPlano.objects.filter(ano=ano).values_list("numero", flat=True)
    return proximo_numero(ocupados, 1, lacunas)


def configuracao(unidade: Unidade | None) -> ConfiguracaoInstitucional | None:
    if unidade is None:
        return None
    return ConfiguracaoInstitucional.objects.filter(unidade=unidade).select_related(
        "sede", "coordenador_plano").first()


def sufixo_da_unidade(unidade: Unidade) -> str:
    """O da configuração ("Sufixo da numeração do plano"); vazio, a sigla da unidade."""
    config = configuracao(unidade)
    return (config.sufixo_plano if config and config.sufixo_plano else unidade.sigla).upper()


# ---------------------------------------------------------------- cópia dos ofícios
def dados_dos_oficios(oficios: list[Oficio]) -> dict:
    """O que o plano em branco recebe dos ofícios: destinos (na ordem, sem a sede), período,
    efetivo (a equipe contada por unidade e cargo) e o deslocamento (a primeira saída e a
    última chegada dos trechos)."""
    prefetch_related_objects(
        oficios, Prefetch("trechos", queryset=Trecho.objects.select_related("destino")
                          .order_by("ordem")),
        Prefetch("viajantes", queryset=Viajante.objects.select_related(
            "servidor__cargo", "servidor__unidade")))
    destinos: list[Municipio] = []
    servidores: list[Servidor] = []
    inicio = fim = None
    saida: datetime | None = None
    chegada: datetime | None = None
    for o in oficios:
        trechos = list(o.trechos.all())
        for t in trechos:
            if t.destino_id != o.sede_id and t.destino not in destinos:
                destinos.append(t.destino)
        if trechos:
            s, c = trechos[0].saida_em, trechos[-1].chegada_em
            saida = min(saida, s) if saida else s
            chegada = max(chegada, c) if chegada else c
            ini, f = timezone.localdate(s), timezone.localdate(c)
            inicio = min(inicio, ini) if inicio else ini
            fim = max(fim, f) if fim else f
        for v in o.viajantes.all():
            if v.servidor not in servidores:
                servidores.append(v.servidor)
    contagem: Counter = Counter((s.unidade, s.cargo) for s in servidores if s.cargo_id)
    efetivo = [LinhaInformada(cargo=cargo, quantidade=n, unidade=unidade)
               for (unidade, cargo), n in sorted(
                   contagem.items(), key=lambda par: (getattr(par[0][0], "nome", ""),
                                                      par[0][1].nome))]
    return {"destinos": destinos, "inicio": inicio, "fim": fim, "efetivo": efetivo,
            "saida": saida, "chegada": chegada}


# ---------------------------------------------------------------- leitura para as regras
def coordenador(plano, qual: str) -> dominio.Coordenador | None:
    """O coordenador ("adm" ou "op") do plano ou de um evento: o do cadastro (nome e cargo de
    lá) ou o escrito à mão."""
    servidor = getattr(plano, f"coordenador_{qual}")
    genero = getattr(plano, f"coordenador_{qual}_genero")  # vazio: ainda não escolhido
    if servidor is not None:
        return dominio.Coordenador(servidor.nome, getattr(servidor.cargo, "nome", ""), genero)
    nome = getattr(plano, f"coordenador_{qual}_nome").strip()
    if not nome:
        return None
    return dominio.Coordenador(nome, getattr(plano, f"coordenador_{qual}_cargo"), genero)


def destinos_texto(plano: PlanoTrabalho) -> list[str]:
    carregar(plano)
    return [f"{d.municipio.nome}/{d.municipio.uf}" for d in plano.destinos.all()]


def _destinos_do_evento(evento: EventoPlano) -> list[str]:
    return [f"{d.municipio.nome}/{d.municipio.uf}" for d in evento.destinos.all()]


def todos_os_destinos(plano: PlanoTrabalho) -> list[str]:
    """Os destinos do evento 1 e dos demais, sem repetir (na ordem dos eventos)."""
    carregar(plano)
    saida = destinos_texto(plano)
    for e in plano.eventos.all():
        saida += _destinos_do_evento(e)
    return list(dict.fromkeys(saida))


def todos_os_programas(plano: PlanoTrabalho) -> list[str]:
    carregar(plano)
    return [p for p in [plano.programa_nome, *[e.programa_nome for e in plano.eventos.all()]] if p]


def periodo_geral(plano: PlanoTrabalho):
    """Do início mais cedo ao fim mais tarde entre os eventos."""
    carregar(plano)
    inicios = [d for d in [plano.data_inicio, *[e.data_inicio for e in plano.eventos.all()]] if d]
    fins = [e.data_fim or e.data_inicio for e in plano.eventos.all() if e.data_inicio]
    if plano.data_inicio:
        fins.append(plano.data_fim or plano.data_inicio)
    return (min(inicios) if inicios else None, max(fins) if fins else None)


def linhas_do_efetivo(plano: PlanoTrabalho) -> list[dominio.LinhaEfetivo]:
    carregar(plano)
    return [dominio.LinhaEfetivo(e.quantidade, e.cargo.nome, getattr(e.unidade, "sigla", ""),
                                 getattr(e.unidade, "nome", ""))
            for e in plano.efetivo.all()]


def dados_do_dominio(plano: PlanoTrabalho) -> dominio.DadosPlano:
    return dominio.DadosPlano(
        destinos=destinos_texto(plano), inicio=plano.data_inicio, fim=plano.data_fim,
        programa=plano.programa_nome, coordenador_adm=coordenador(plano, "adm"),
        coordenador_op=coordenador(plano, "op"), efetivo=linhas_do_efetivo(plano),
        diarias_total=plano.diarias_total,
        tem_deslocamento=bool(plano.saida_em and plano.chegada_em),
        tem_atividades=bool(plano.atividades.all()) or any(
            e.atividades.all() for e in plano.eventos.all()),
        eventos_extras=[(i + 2, bool(e.destinos.all()), bool(e.data_inicio))
                        for i, e in enumerate(plano.eventos.all())])


def pendencias(plano: PlanoTrabalho) -> list[dominio.Pendencia]:
    return dominio.pendencias(dados_do_dominio(plano))


def avisos(plano: PlanoTrabalho) -> list[dominio.Pendencia]:
    return dominio.avisos(dados_do_dominio(plano))


def estado(plano: PlanoTrabalho, falta: list | None = None) -> tuple[str, str]:
    """(rótulo, tom do selo) — o mesmo na lista e na folha."""
    if plano.cancelado:
        return "Cancelado", "perigo"
    if plano.documento_gerado_em:
        return f"Gerado em {timezone.localtime(plano.documento_gerado_em):%d/%m}", "sucesso"
    falta = pendencias(plano) if falta is None else falta
    if falta:
        n = len(falta)
        return f"{n} pendência{'s' if n != 1 else ''}", "aviso"
    return "Pronto para gerar", "info"


def conjunto_padrao() -> list[AtividadePlano]:
    """As atividades do conjunto padrão (gravadas em todo plano novo)."""
    from gestao.cadastros.models import PresetAtividades
    padrao = PresetAtividades.objects.filter(padrao=True, ativo=True).first()
    return list(padrao.atividades.filter(ativo=True)) if padrao else []


def calculo(plano: PlanoTrabalho):
    """(cálculo, mensagens): as diárias do plano agora, ou o que falta para calcular."""
    carregar(plano)
    config = configuracao(plano.unidade)
    if config is None or not config.sede_id:
        return None, ["A unidade ainda não tem sede na configuração: peça ao gestor."]
    primeiro = next(iter(plano.destinos.all()), None)
    try:
        resultado = dominio.calcular_diarias(
            saida=timezone.localtime(plano.saida_em) if plano.saida_em else None,
            chegada=timezone.localtime(plano.chegada_em) if plano.chegada_em else None,
            destino=(primeiro.municipio.nome, primeiro.municipio.uf) if primeiro else None,
            servidores=dominio.efetivo_total(linhas_do_efetivo(plano)),
            sede=(config.sede.nome, config.sede.uf), buscar_tabelas=buscar_tabelas_vigentes)
    except dominio.PlanoIncalculavel as exc:
        return None, exc.mensagens
    return resultado, []


def textos_automaticos(plano: PlanoTrabalho) -> dict[str, str]:
    """Com vários eventos: todos os destinos e programas (na referência, só os do rascunho —
    que podia sair com "________"), e só o coordenador administrativo é designado."""
    destinos = todos_os_destinos(plano)
    varios = bool(plano.eventos.all())
    return {
        "contextualizacao": dominio.contextualizacao(destinos, todos_os_programas(plano)),
        "coordenacao": dominio.coordenacao(coordenador(plano, "adm"), coordenador(plano, "op"),
                                           varios_eventos=varios),
        "consideracoes": dominio.consideracoes_finais(destinos),
    }


def _textos_das_atividades(atividades) -> dict[str, str]:
    return dominio.textos_das_atividades(
        [dominio.Atividade(a.codigo, a.nome, a.meta, a.recurso) for a in atividades])


def _refazer(plano: PlanoTrabalho) -> None:
    """Textos automáticos (os com o interruptor ligado), textos das atividades e a cópia das
    diárias — refeitos a cada gravação, como na referência."""
    for campo, texto in textos_automaticos(plano).items():
        if getattr(plano, f"{campo}_auto"):
            setattr(plano, campo, texto)
    textos = _textos_das_atividades(plano.atividades.all())
    plano.atividades_texto, plano.metas = textos["atividades"], textos["metas"]
    plano.recursos, plano.unidade_movel_texto = textos["recursos"], textos["unidade_movel"]
    for evento in plano.eventos.all():
        t = _textos_das_atividades(evento.atividades.all())
        novos = (t["atividades"], t["metas"], t["recursos"], t["unidade_movel"])
        if novos != (evento.atividades_texto, evento.metas, evento.recursos,
                     evento.unidade_movel_texto):
            (evento.atividades_texto, evento.metas, evento.recursos,
             evento.unidade_movel_texto) = novos
            evento.save(update_fields=["atividades_texto", "metas", "recursos",
                                       "unidade_movel_texto", "atualizado_em"])
    resultado, _ = calculo(plano)
    if resultado is None:  # cálculo inválido apaga a cópia (vira pendência de diárias)
        plano.diarias_composicao, plano.diarias_unitario, plano.diarias_total = "", None, None
    else:
        plano.diarias_composicao = resultado.resumo
        plano.diarias_unitario, plano.diarias_total = resultado.por_servidor, resultado.total


def _texto_escrito(plano: PlanoTrabalho, campo: str, escrito: str | None,
                   automatico: str) -> None:
    """Texto escrito na tela: vazio ou igual ao automático religa o automático; diferente
    desliga e fica como escrito (referência: editor da folha)."""
    if escrito is None:  # a tela não mandou: fica como está
        return
    limpo = escrito.strip()
    if not limpo or limpo == automatico.strip():
        setattr(plano, f"{campo}_auto", True)
    else:
        setattr(plano, f"{campo}_auto", False)
        setattr(plano, campo, limpo)


# ---------------------------------------------------------------- escrita
@transaction.atomic
def salvar(usuario, *, pk: int | None = None, versao: str = "", oficios=(),
           programa: ProgramaSolicitante | None = None, programa_outros: str = "",
           data_inicio: date | None = None, data_fim: date | None = None, horario: str = "",
           destinos=(), coordenador_adm: Servidor | None = None, coordenador_adm_nome: str = "",
           coordenador_adm_cargo: str = "", coordenador_adm_genero: str = "",
           coordenador_op: Servidor | None = None, coordenador_op_nome: str = "",
           coordenador_op_cargo: str = "", coordenador_op_genero: str = "",
           saida_em: datetime | None = None, chegada_em: datetime | None = None,
           efetivo: list[LinhaInformada] | None = None, atividades=None,
           contextualizacao: str | None = None, coordenacao: str | None = None,
           consideracoes: str | None = None, assinante: Servidor | None = None,
           data_documento: date | None = None) -> tuple[PlanoTrabalho, list[str]]:
    """Cria (numera) ou altera. Devolve o plano e o que veio dos ofícios.

    `efetivo`/`atividades`/textos `None`: a tela não os mandou — ficam como estão. Os campos
    vazios recebem dos ofícios na criação e quando um ofício é ligado agora."""
    oficios, destinos = list(oficios), list(dict.fromkeys(destinos))
    if pk:
        plano = PlanoTrabalho.objects.select_for_update().get(pk=pk)
        policies.exigir(policies.pode_editar_plano(usuario, plano),
                        "Este plano de trabalho não pode ser alterado.")
        if versao and versao != versao_de(plano):
            raise PlanoInvalido("Outra pessoa alterou este plano depois que você abriu a tela. "
                                "Recarregue a página para ver a versão atual (o que você "
                                "digitou continua na tela até lá).")
    else:
        policies.exigir(policies.pode_criar_plano(usuario),
                        "Você não pode criar planos de trabalho.")
        unidade = policies.unidade_do_usuario(usuario)
        if unidade is None:
            raise PlanoInvalido("Seu usuário não está lotado numa unidade.")
        ano = timezone.localdate().year
        config = configuracao(unidade)
        plano = PlanoTrabalho(unidade=unidade, ano=ano, numero=reservar_numero(ano),
                              sufixo=sufixo_da_unidade(unidade), criado_por=usuario)
        if coordenador_adm is None and not coordenador_adm_nome.strip() and config:
            coordenador_adm = config.coordenador_plano  # sugerido em todo plano novo
            if coordenador_adm is not None and not coordenador_adm_genero:
                coordenador_adm_genero = config.coordenador_plano_genero
        if atividades is None:
            atividades = conjunto_padrao()  # o padrão já nasce gravado (não só na tela)
    if (len(oficios) > MAX_OFICIOS or len(destinos) > MAX_DESTINOS
            or (efetivo is not None and len(efetivo) > MAX_LINHAS)):
        raise PlanoInvalido(f"Limites: {MAX_OFICIOS} ofícios, {MAX_DESTINOS} destinos e "
                            f"{MAX_LINHAS} linhas de efetivo por plano.")
    ja_ligados = set(plano.oficios.values_list("pk", flat=True)) if pk else set()
    for o in oficios:
        policies.exigir(policies.pode_ver(usuario, o), "Ofício não encontrado.")
        if o.unidade_id != plano.unidade_id:
            raise PlanoInvalido(f"O Ofício {o.numero_formatado} é de outra unidade.")
        if o.situacao == Oficio.Situacao.CANCELADO and o.pk not in ja_ligados:
            raise PlanoInvalido(f"O Ofício {o.numero_formatado} está cancelado.")
    if data_inicio and data_fim and data_fim < data_inicio:
        raise PlanoInvalido("A data final não pode ser anterior à data inicial.")
    if saida_em and chegada_em and chegada_em <= saida_em:
        raise PlanoInvalido("A chegada na sede deve ser depois da saída.")

    copiados: list[str] = []
    if oficios and (not pk or any(o.pk not in ja_ligados for o in oficios)):
        base = dados_dos_oficios(oficios)
        if not destinos and base["destinos"]:
            destinos = base["destinos"][:MAX_DESTINOS]
            copiados.append("destinos")
        if not data_inicio and base["inicio"]:
            data_inicio, data_fim = base["inicio"], base["fim"]
            copiados.append("período")
        if not efetivo and base["efetivo"] and not (pk and plano.efetivo.exists()):
            efetivo = base["efetivo"]
            copiados.append("efetivo")
        if not saida_em and not chegada_em and base["saida"]:
            saida_em, chegada_em = base["saida"], base["chegada"]
            copiados.append("deslocamento")

    plano.programa = programa
    plano.programa_outros = "" if programa else " ".join(programa_outros.split())
    plano.data_inicio, plano.data_fim = data_inicio, (data_fim or data_inicio)
    plano.horario = horario or dominio.HORARIO_PADRAO
    for qual, servidor, nome, cargo, genero in (
            ("adm", coordenador_adm, coordenador_adm_nome, coordenador_adm_cargo,
             coordenador_adm_genero),
            ("op", coordenador_op, coordenador_op_nome, coordenador_op_cargo,
             coordenador_op_genero)):
        setattr(plano, f"coordenador_{qual}", servidor)
        # Do cadastro valem nome e cargo de lá; à mão, o nome fica em maiúsculas.
        setattr(plano, f"coordenador_{qual}_nome", "" if servidor else nome.strip().upper())
        setattr(plano, f"coordenador_{qual}_cargo", "" if servidor else cargo.strip())
        setattr(plano, f"coordenador_{qual}_genero", genero if genero in ("M", "F") else "")
    plano.saida_em, plano.chegada_em = saida_em, chegada_em
    plano.assinante = assinante
    if data_documento is not None or plano.documento_gerado_em is None:
        # Depois da primeira geração, "em branco" não apaga a data fixada (uma aba aberta
        # antes da geração mandaria o campo vazio e as vias sairiam com datas diferentes).
        plano.data_documento = data_documento
    if plano.pk is None:
        plano.save()  # o novo precisa existir para receber as relações; o resto, no fim

    plano.oficios.set(oficios)
    atuais = [d.municipio_id for d in plano.destinos.order_by("posicao", "id")]
    if atuais != [m.pk for m in destinos]:
        plano.destinos.all().delete()
        PlanoDestino.objects.bulk_create(
            [PlanoDestino(plano=plano, municipio=m, posicao=i) for i, m in enumerate(destinos)])
    if efetivo is not None:
        _gravar_efetivo(plano, efetivo)
    if atividades is not None:
        plano.atividades.set(atividades)

    # Relê as relações gravadas e refaz o que deriva delas.
    if hasattr(plano, "_prefetched_objects_cache"):
        del plano._prefetched_objects_cache
    carregar(plano)
    automaticos = textos_automaticos(plano)
    _texto_escrito(plano, "contextualizacao", contextualizacao, automaticos["contextualizacao"])
    _texto_escrito(plano, "coordenacao", coordenacao, automaticos["coordenacao"])
    _texto_escrito(plano, "consideracoes", consideracoes, automaticos["consideracoes"])
    _refazer(plano)
    plano.save()
    return plano, copiados


def _gravar_efetivo(plano: PlanoTrabalho, linhas: list[LinhaInformada]) -> None:
    """Regrava as linhas só quando mudaram (a trilha de auditoria não registra o que não
    mudou a cada gravação automática)."""
    atuais = [(e.unidade_id, e.cargo_id, e.quantidade) for e in plano.efetivo.order_by(
        "posicao", "id")]
    novas = [(getattr(lin.unidade, "pk", None), lin.cargo.pk, lin.quantidade) for lin in linhas]
    if atuais == novas:
        return
    plano.efetivo.all().delete()
    EfetivoPlano.objects.bulk_create([
        EfetivoPlano(plano=plano, unidade=lin.unidade, cargo=lin.cargo,
                     quantidade=lin.quantidade, posicao=i) for i, lin in enumerate(linhas)])


@transaction.atomic
def salvar_evento(usuario, plano_pk: int, *, evento_pk: int | None = None,
                  programa: ProgramaSolicitante | None = None, programa_outros: str = "",
                  data_inicio: date | None = None, data_fim: date | None = None,
                  horario: str = "", destinos=(), coordenador_op: Servidor | None = None,
                  coordenador_op_nome: str = "", coordenador_op_cargo: str = "",
                  coordenador_op_genero: str = "", atividades=()) -> EventoPlano:
    """Cria ou altera um evento adicional e refaz o plano (textos, metas, diárias)."""
    plano = PlanoTrabalho.objects.select_for_update().get(pk=plano_pk)
    policies.exigir(policies.pode_editar_plano(usuario, plano),
                    "Este plano de trabalho não pode ser alterado.")
    destinos = list(dict.fromkeys(destinos))
    if len(destinos) > MAX_DESTINOS:
        raise PlanoInvalido(f"No máximo {MAX_DESTINOS} destinos por evento.")
    if data_inicio and data_fim and data_fim < data_inicio:
        raise PlanoInvalido("A data final não pode ser anterior à data inicial.")
    if evento_pk:
        evento = plano.eventos.get(pk=evento_pk)
    else:
        if plano.eventos.count() >= MAX_EVENTOS - 1:
            raise PlanoInvalido(f"No máximo {MAX_EVENTOS} eventos por plano.")
        ultima = plano.eventos.order_by("-posicao").values_list("posicao", flat=True).first()
        evento = EventoPlano(plano=plano, posicao=(ultima + 1) if ultima is not None else 0)
    evento.programa = programa
    evento.programa_outros = "" if programa else " ".join(programa_outros.split())
    evento.data_inicio, evento.data_fim = data_inicio, (data_fim or data_inicio)
    evento.horario = horario or dominio.HORARIO_PADRAO
    evento.coordenador_op = coordenador_op
    evento.coordenador_op_nome = "" if coordenador_op else coordenador_op_nome.strip().upper()
    evento.coordenador_op_cargo = "" if coordenador_op else coordenador_op_cargo.strip()
    evento.coordenador_op_genero = coordenador_op_genero if coordenador_op_genero in (
        "M", "F") else ""
    evento.save()
    atuais = [d.municipio_id for d in evento.destinos.order_by("posicao", "id")]
    if atuais != [m.pk for m in destinos]:
        evento.destinos.all().delete()
        EventoDestino.objects.bulk_create(
            [EventoDestino(evento=evento, municipio=m, posicao=i) for i, m in enumerate(destinos)])
    evento.atividades.set(list(atividades))
    _refazer_e_gravar(plano)
    return evento


@transaction.atomic
def remover_evento(usuario, plano_pk: int, evento_pk: int) -> PlanoTrabalho:
    plano = PlanoTrabalho.objects.select_for_update().get(pk=plano_pk)
    policies.exigir(policies.pode_editar_plano(usuario, plano),
                    "Este plano de trabalho não pode ser alterado.")
    plano.eventos.filter(pk=evento_pk).delete()
    _refazer_e_gravar(plano)
    return plano


def _refazer_e_gravar(plano: PlanoTrabalho) -> None:
    """Relê as relações e refaz textos automáticos, metas e diárias (toca a versão: a folha
    aberta noutra aba fica sabendo)."""
    if hasattr(plano, "_prefetched_objects_cache"):
        del plano._prefetched_objects_cache
    carregar(plano)
    _refazer(plano)
    plano.save()


@transaction.atomic
def finalizar(usuario, pk: int) -> PlanoTrabalho:
    """Finalizar e gerar (uma ação só — ↔ referência, onde finalizar e gerar eram dois
    passos e a lista pulava o primeiro): só sem pendências; marca GERADO, fixa a data do
    documento e trava a exclusão (o número sai num documento oficial)."""
    plano = PlanoTrabalho.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_editar_plano(usuario, plano),
                    "Este plano de trabalho não pode ser alterado.")
    falta = pendencias(carregar(plano))
    if falta:
        raise PlanoInvalido("Falta: " + "; ".join(p.mensagem.rstrip(".") for p in falta) + ".")
    fixar_geracao(plano)
    return plano


@transaction.atomic
def cancelar(usuario, pk: int, motivo: str) -> PlanoTrabalho:
    plano = PlanoTrabalho.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_cancelar_plano(usuario, plano),
                    "Você não pode cancelar este plano de trabalho.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise PlanoInvalido("Informe o motivo do cancelamento.")
    if len(motivo) > 1000:
        raise PlanoInvalido("O motivo passa de 1000 caracteres: resuma.")
    if plano.cancelado:
        raise PlanoInvalido("O plano já está cancelado.")
    plano.cancelado, plano.motivo_cancelamento = True, motivo
    plano.cancelado_em = timezone.now()
    plano.save(update_fields=["cancelado", "motivo_cancelamento", "cancelado_em",
                              "atualizado_em"])
    return plano


@transaction.atomic
def reativar(usuario, pk: int) -> PlanoTrabalho:
    plano = PlanoTrabalho.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_cancelar_plano(usuario, plano),
                    "Você não pode reativar este plano de trabalho.")
    if not plano.cancelado:
        raise PlanoInvalido("O plano não está cancelado.")
    plano.cancelado, plano.motivo_cancelamento, plano.cancelado_em = False, "", None
    plano.save(update_fields=["cancelado", "motivo_cancelamento", "cancelado_em",
                              "atualizado_em"])
    return plano


@transaction.atomic
def excluir(usuario, pk: int) -> str:
    """Exclui e libera o número para o próximo plano do ano — só enquanto o documento nunca
    foi gerado (depois, o número já saiu num documento oficial: cancele)."""
    plano = PlanoTrabalho.objects.select_for_update().get(pk=pk)
    if plano.documento_gerado_em is not None:
        raise PlanoInvalido("O documento deste plano já foi gerado: o número já saiu num "
                            "documento oficial. Cancele em vez de excluir.")
    policies.exigir(policies.pode_excluir_plano(usuario, plano),
                    "Você não pode excluir este plano de trabalho.")
    nome, ano, numero = str(plano), plano.ano, plano.numero
    plano.delete()
    LacunaPlano.objects.get_or_create(ano=ano, numero=numero)
    return nome


# ---------------------------------------------------------------- documento
@transaction.atomic
def fixar_geracao(plano: PlanoTrabalho) -> date:
    """A primeira geração fixa a data do documento e marca GERADO; a data não muda mais
    sozinha (todas as vias saem com a mesma). Trava a linha (excluir no meio liberaria um
    número que já saiu) e toca a versão (a aba aberta antes passa a ouvir "outra pessoa
    alterou")."""
    if not PlanoTrabalho.objects.select_for_update().filter(pk=plano.pk).exists():
        raise PlanoInvalido("Este plano de trabalho não existe mais.")
    agora = timezone.now()
    campos: dict[str, object] = {}
    if plano.data_documento is None:
        plano.data_documento = campos["data_documento"] = timezone.localdate()
    if plano.documento_gerado_em is None:
        plano.documento_gerado_em = campos["documento_gerado_em"] = agora
    if plano.situacao != PlanoTrabalho.Situacao.GERADO:
        plano.situacao = campos["situacao"] = PlanoTrabalho.Situacao.GERADO
    if campos:
        plano.atualizado_em = campos["atualizado_em"] = agora
        PlanoTrabalho.objects.filter(pk=plano.pk).update(**campos)
    return plano.data_documento or timezone.localdate()


def assinatura_prevista(plano: PlanoTrabalho) -> str:
    """Quem assina se o campo ficar em branco (a tela diz antes de gerar)."""
    config = configuracao(plano.unidade)
    if config is None:
        return ""
    nome, cargo, origem = quem_assina(config, "plano_trabalho",
                                      plano.data_documento or timezone.localdate())
    if origem == "assinante escolhido":
        origem = "o assinante dos planos na configuração"
    return f"{nome}{', ' + cargo if cargo else ''} ({origem})" if nome else ""


def dados_do_documento(plano: PlanoTrabalho, *, fixar: bool = True) -> dict:
    """Os dados do documento. `fixar=False` (a prévia na tela): sem fixar a data nem marcar
    como gerado, e com a marca MINUTA."""
    carregar(plano)
    config = configuracao(plano.unidade)
    if config is None:
        raise PlanoInvalido("A unidade ainda não tem configuração (cabeçalho, sede, quem "
                            "assina): peça ao gestor para cadastrá-la.")
    if fixar and plano.documento_gerado_em is None:
        raise PlanoInvalido("Use “Finalizar e gerar o plano”: é ele que confere e fixa a "
                            "data do documento.")
    data_doc = fixar_geracao(plano) if fixar else (plano.data_documento or timezone.localdate())
    if plano.assinante is not None:
        nome, cargo = plano.assinante.nome, getattr(plano.assinante.cargo, "nome", "")
    else:
        nome, cargo, _ = quem_assina(config, "plano_trabalho", data_doc)
    valor = ""
    if plano.diarias_total is not None and plano.diarias_unitario is not None:
        valor = dominio.texto_do_valor(plano.diarias_composicao, plano.diarias_unitario,
                                       plano.diarias_total)
    sede = config.sede
    local = (f"{config.cidade_endereco}/{config.uf}" if config.cidade_endereco and config.uf
             else f"{sede.nome}/{sede.uf}" if sede else "")
    inicio, fim = periodo_geral(plano)
    eventos = eventos_para_documento(plano)
    return {
        "titulo": str(plano),
        "numero": plano.numero_formatado,
        "unidade_nome": config.nome_extenso,
        "cabecalho_unidade": config.nome_extenso.upper(),
        "rodape": config.rodape,
        "previa": not fixar,
        "contextualizacao": plano.contextualizacao,
        "datas": dominio.periodo_por_extenso(inicio, fim),
        "local": ", ".join(todos_os_destinos(plano)),
        # Vários eventos: atuação, atividades, metas e recursos por evento; o valor é o
        # combinado da viagem (um trecho, a mesma equipe), com o rótulo do período todo.
        "eventos": eventos if len(eventos) > 1 else [],
        "valor_rotulo": dominio.rotulo_do_total(inicio, fim) if len(eventos) > 1 else "",
        "horario": plano.horario,
        "efetivo": dominio.texto_do_efetivo(linhas_do_efetivo(plano)),
        "unidade_movel": plano.unidade_movel_texto,
        "atividades": plano.atividades_texto,
        "metas": plano.metas,
        "recursos": plano.recursos,
        "valor": valor,
        "valor_resto": valor.removeprefix("Valor total:"),
        "coordenacao": plano.coordenacao,
        "consideracoes": plano.consideracoes,
        "local_data": f"{local}, {data_por_extenso(data_doc)}" if local else "",
        "assina": {"nome": legivel(nome) if nome else "", "cargo": legivel(cargo) if cargo else ""},
    }


def eventos_para_documento(plano: PlanoTrabalho) -> list[dict]:
    """O evento 1 (os campos do plano) e os demais, no formato do documento."""
    carregar(plano)
    saida = [{"cabecalho": dominio.cabecalho_do_evento(plano.data_inicio, plano.data_fim),
              "programa": plano.programa_nome, "local": ", ".join(destinos_texto(plano)),
              "horario": plano.horario, "atividades": plano.atividades_texto,
              "metas": plano.metas, "recursos": plano.recursos,
              "unidade_movel": plano.unidade_movel_texto}]
    for e in plano.eventos.all():
        saida.append({"cabecalho": dominio.cabecalho_do_evento(e.data_inicio, e.data_fim),
                      "programa": e.programa_nome, "local": ", ".join(_destinos_do_evento(e)),
                      "horario": e.horario, "atividades": e.atividades_texto, "metas": e.metas,
                      "recursos": e.recursos, "unidade_movel": e.unidade_movel_texto})
    return saida


def html_do_documento(dados: dict, *, folha: bool = False, nonce: str = "") -> str:
    from django.template.loader import render_to_string

    from .documentos.pdf import _recursos
    return render_to_string("viagens/documentos/plano_trabalho.html",
                            {"d": dados, "folha": folha, "nonce": nonce, **_recursos(folha)})


def pdf_do_documento(dados: dict) -> bytes:
    import hashlib

    from weasyprint import HTML

    from .documentos.pdf import ASSETS, buscar_recurso
    html = html_do_documento(dados)
    return HTML(string=html, base_url=str(ASSETS), url_fetcher=buscar_recurso()).write_pdf(
        pdf_variant="pdf/a-2a", pdf_identifier=hashlib.sha256(html.encode()).digest()[:16],
        pdf_tags=True, custom_metadata=True, presentational_hints=True)


def docx_do_documento(dados: dict) -> bytes:
    from .documentos.docx import docx_do_html
    from .documentos.pdf import ASSETS
    return docx_do_html(html_do_documento(dados), base_imagens=ASSETS)
