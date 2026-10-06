"""Cadastros mantidos em tela: servidores, viaturas, unidades, cargos, combustíveis, tabela
de diárias e configuração da unidade.

Mesma forma dos textos prontos: uma lista com busca e abas, um registro por linha com o
menu de ações, e novo/editar numa janela (`?novo=1`, `?editar=<pk>`; com erro, a janela
volta aberta com o que foi digitado). Quem grava é `services.py`; quem decide o que cada
perfil vê é `policies.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from urllib.parse import urlsplit

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import policies, services
from .forms import (
    FormularioAtividade,
    FormularioCatalogo,
    FormularioConfiguracao,
    FormularioHorario,
    FormularioPreset,
    FormularioPrograma,
    FormularioServidor,
    FormularioSubstituicao,
    FormularioUnidade,
    FormularioViatura,
    FormularioVigencia,
)
from .models import (
    AtividadePlano,
    Cargo,
    Combustivel,
    ConfiguracaoInstitucional,
    HorarioAtendimento,
    Lotacao,
    PresetAtividades,
    ProgramaSolicitante,
    Servidor,
    SubstituicaoAssinante,
    TabelaDiaria,
    TipoViagem,
    Unidade,
    Viatura,
)


def _migalhas(rotulo: str):
    return [("Início", reverse("painel:inicio")), ("Viagens", reverse("viagens:painel")),
            ("Cadastros", reverse("cadastros:indice")), (rotulo, "")]


@dataclass(frozen=True)
class Catalogo:
    """Um cadastro simples (só nome, ou nome e sigla) que usa a lista genérica."""

    modelo: Any
    titulo: str
    singular: str
    artigo: str  # "o" ou "a": "Novo cargo", "Nova unidade"
    icone: str
    descricao: str
    formulario: Any
    busca: tuple[str, ...] = ("nome",)
    com_padrao: bool = False
    nota_padrao: str = ""
    vazio: str = ""
    por_pagina: int = 25
    contar: tuple[tuple[str, str], ...] = field(default=())  # (relação, rótulo)
    # Para catálogos com mais que o nome (atividades, conjuntos, horários):
    salvar: Any = None  # serviço (usuario, pk=…, **dados); padrão: services.salvar_catalogo
    campos: str = ""  # parcial com os campos da janela; padrão: só o nome
    detalhe: Any = None  # obj → texto da linha (ex.: o código, as atividades)
    prefetch: tuple[str, ...] = ()
    extras: Any = None  # obj em edição → kwargs do formulário (ex.: as atividades atuais)
    placeholder: str = "Nome"
    grupo: str = ""  # onde o cadastro mora na entrada (ex.: "plano")

    @property
    def novo(self) -> str:
        return f"Nov{self.artigo} {self.singular}"


CATALOGOS: dict[str, Catalogo] = {
    "unidades": Catalogo(
        Unidade, "Unidades", "unidade", "a", "building-2",
        "Unidades administrativas: lotação dos servidores, dona das viaturas e emissora "
        "dos ofícios.", FormularioUnidade, busca=("nome", "sigla"), por_pagina=15,
        vazio="Nenhuma unidade cadastrada ainda.",
        contar=(("servidores", "servidor,servidores"), ("viaturas", "viatura,viaturas"),
                ("oficios", "ofício,ofícios"), ("roteiros", "roteiro,roteiros"),
                ("lotacoes", "usuário lotado,usuários lotados"),
                ("configuracao", "configuração de documentos,configurações de documentos"))),
    "cargos": Catalogo(
        Cargo, "Cargos", "cargo", "o", "id-card",
        "Cargos usados no cadastro de servidores (aparecem na lista da equipe do ofício).",
        FormularioCatalogo, com_padrao=True,
        nota_padrao="O cargo padrão já vem escolhido em todo servidor novo.",
        vazio="Nenhum cargo cadastrado ainda.",
        contar=(("servidores", "servidor,servidores"),)),
    "combustiveis": Catalogo(
        Combustivel, "Combustíveis", "combustível", "o", "fuel",
        "Tipos de combustível das viaturas (e do veículo informado à mão no ofício).",
        FormularioCatalogo, com_padrao=True,
        nota_padrao="O combustível padrão já vem escolhido em toda viatura nova.",
        vazio="Nenhum combustível cadastrado ainda.",
        contar=(("viaturas", "viatura,viaturas"),)),
    # Plano de trabalho (referência: viagens_planos/catalogos).
    "tipos": Catalogo(
        TipoViagem, "Tipos de viagem", "tipo de viagem", "o", "route",
        "Nome do tipo; uma viagem pode ter mais de um, e o título dela nasce deles.",
        FormularioCatalogo, vazio="Nenhum tipo de viagem cadastrado ainda.",
        contar=(("viagens", "viagem,viagens"),)),
    "programas": Catalogo(
        ProgramaSolicitante, "Programas solicitantes", "programa", "o", "landmark",
        "Quem pede a ação itinerante; sai na contextualização do plano de trabalho "
        "(“solicitação formulada pelo …”).", FormularioPrograma,
        vazio="Nenhum programa cadastrado ainda.", grupo="plano"),
    "horarios": Catalogo(
        HorarioAtendimento, "Horários de atendimento", "horário", "o", "clock",
        "Faixas de atendimento ao público nos eventos do plano de trabalho.",
        FormularioHorario, campos="cadastros/_campos_horario.html",
        vazio="Nenhum horário cadastrado ainda.", grupo="plano"),
    "atividades": Catalogo(
        AtividadePlano, "Atividades do plano", "atividade", "a", "list-checks",
        "Serviços oferecidos nas ações. A meta e o recurso de cada atividade marcada compõem "
        "o plano de trabalho; planos já criados não mudam.", FormularioAtividade,
        busca=("nome", "codigo", "meta"), salvar=services.salvar_atividade,
        campos="cadastros/_campos_atividade.html", placeholder="Nome, código ou meta",
        detalhe=lambda o: o.codigo, vazio="Nenhuma atividade cadastrada ainda.",
        contar=(("presets", "conjunto,conjuntos"),), grupo="plano"),
    "conjuntos": Catalogo(
        PresetAtividades, "Conjuntos de atividades", "conjunto", "o", "layers",
        "Atividades que se aplicam de uma vez no plano de trabalho.", FormularioPreset,
        com_padrao=True, nota_padrao="O conjunto padrão já vem marcado em todo plano novo.",
        salvar=services.salvar_preset, campos="cadastros/_campos_conjunto.html",
        prefetch=("atividades",), detalhe=lambda o: _atividades_do_conjunto(o),
        extras=lambda e: {"atuais": [a.pk for a in e.atividades.all()] if e else []},
        vazio="Nenhum conjunto cadastrado ainda.", grupo="plano"),
}


def _atividades_do_conjunto(conjunto) -> str:
    nomes = [a.nome for a in conjunto.atividades.all()]
    if len(nomes) <= 3:
        return ", ".join(nomes)
    return f"{', '.join(nomes[:3])} e mais {len(nomes) - 3}"


# O que as ações comuns (ativar, excluir) alcançam, por endereço.
MODELOS: dict[str, Any] = {
    "unidades": Unidade, "cargos": Cargo, "combustiveis": Combustivel,
    "servidores": Servidor, "viaturas": Viatura,
    **{slug: cat.modelo for slug, cat in CATALOGOS.items()},
}

ABAS_ATIVOS = [("", "Ativos", "ativos"), ("inativos", "Inativos", "inativos")]


def _url_lista(slug: str) -> str:
    return reverse(f"cadastros:{slug}")


def _voltar(request: HttpRequest, slug: str) -> str:
    """Depois de uma ação, a lista como estava (aba, busca, página) — só se for a mesma
    lista; senão, a lista limpa."""
    voltar = request.POST.get("voltar") or ""
    base = _url_lista(slug)
    if (urlsplit(voltar).path == base
            and url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()})):
        return voltar
    return base


def _inteiro(texto: str | None) -> int | None:
    """Número de um parâmetro, ou None. `isdigit()` aceitaria "²" (e int() estouraria)."""
    texto = (texto or "").strip()
    if texto.isascii() and texto.isdecimal() and len(texto) <= 18:
        return int(texto)
    return None


def _depois_de_salvar(request: HttpRequest, slug: str) -> str:
    """A lista como estava; com "Cadastrar e incluir outro", já com a janela de novo aberta."""
    destino = _voltar(request, slug)
    if request.POST.get("outro") == "1":
        destino += ("&" if "?" in destino else "?") + "novo=1"
    return destino


def _parametros(request: HttpRequest, *chaves: str) -> dict[str, str]:
    return {c: v for c in chaves if (v := (request.GET.get(c) or "").strip())}


def _querystring(parametros: dict[str, str]) -> str:
    return f"{urlencode(parametros)}&" if parametros else ""


def _busca(qs, termo: str, campos: tuple[str, ...]):
    if not termo:
        return qs
    filtro = Q()
    for campo in campos:
        filtro |= Q(**{f"{campo}__unaccent__icontains": termo})
    return qs.filter(filtro)


def _abrir(request: HttpRequest, pode: bool) -> tuple[int | None, bool]:
    """(pk a editar, pediu novo) — só para quem pode escrever."""
    if not pode:
        return None, False
    return _inteiro(request.GET.get("editar")), request.GET.get("novo") == "1"


# ---------------------------------------------------------------- índice
@require_GET
def indice(request: HttpRequest) -> HttpResponse:
    usuario = request.user
    cartoes = [
        ("Servidores", "Pessoas que compõem as equipes, dirigem e assinam.", "users",
         "cadastros:servidores", Servidor),
        ("Viaturas", "Veículos oficiais e seus motoristas habituais.", "car",
         "cadastros:viaturas", Viatura),
        ("Unidades", "Lotação dos servidores e unidade emissora dos ofícios.", "building-2",
         "cadastros:unidades", Unidade),
        ("Cargos", "Cargos usados no cadastro de servidores.", "id-card",
         "cadastros:cargos", Cargo),
        ("Combustíveis", "Tipos de combustível das viaturas.", "fuel",
         "cadastros:combustiveis", Combustivel),
        ("Tabela de diárias", "Valor da diária de 24 h por faixa e vigência.", "banknote",
         "cadastros:diarias", TabelaDiaria),
        ("Tipos de viagem", "O título da viagem nasce deles.", "route",
         "cadastros:tipos", TipoViagem),
    ]
    # Catálogos do plano de trabalho: um grupo próprio na entrada.
    textos = {"programas": "Quem pede a ação (sai na contextualização).",
              "horarios": "Faixas de atendimento ao público nos eventos.",
              "atividades": "Serviços da ação, com a meta e o recurso de cada um.",
              "conjuntos": "Atividades aplicadas de uma vez; o padrão vem marcado."}
    plano = [{"titulo": cat.titulo, "texto": textos.get(slug, ""), "icone": cat.icone,
              "url": reverse(f"cadastros:{slug}")}
             for slug, cat in CATALOGOS.items()
             if cat.grupo == "plano" and policies.pode_ver_cadastro(usuario, cat.modelo)]
    pendencias = _pendencias_dos_cadastros()
    visiveis = []
    for titulo, texto, icone, rota, modelo in cartoes:
        if policies.pode_ver_cadastro(usuario, modelo):
            resumo, pendencia = pendencias.get(modelo, ("", None))
            visiveis.append({"titulo": titulo, "texto": texto, "icone": icone,
                             "url": reverse(rota), "resumo": resumo, "pendencia": pendencia})
    apoio = []
    if policies.pode_ver_configuracao(usuario):
        apoio.append({"titulo": "Configuração da unidade", "icone": "landmark",
                      "texto": "Cabeçalho, rodapé, quem assina e o destinatário dos ofícios.",
                      "url": reverse("cadastros:configuracao")})
    if policies.pode_ver_textos(usuario):
        apoio.append({"titulo": "Textos prontos", "icone": "text-quote",
                      "texto": "Motivos, justificativas e trechos reaproveitados.",
                      "url": reverse("cadastros:textos")})
    if not visiveis and not apoio and not plano:
        raise PermissionDenied
    return render(request, "cadastros/indice.html", {
        "cartoes": visiveis, "apoio": apoio, "plano": plano,
        "migalhas": [("Início", reverse("painel:inicio")), ("Viagens", reverse("viagens:painel")),
                     ("Cadastros", "")]})


def _pendencias_dos_cadastros() -> dict:
    """{modelo: (resumo, (texto, url) | None)} — o que a entrada mostra em cada cartão:
    quantos ativos e, quando há, o que falta resolver (com o link que resolve)."""
    servidores = Servidor.objects.filter(ativo=True)
    viaturas = Viatura.objects.filter(ativo=True)
    inc_s = servidores.filter(INCOMPLETO).count()
    inc_v = viaturas.filter(INCOMPLETA).count()
    sem_config = Unidade.objects.filter(ativo=True, configuracao__isnull=True).count()

    def plural(n: int, formas: str) -> str:
        um, varios = formas.split(",")
        return f"{n} {um if n == 1 else varios}"

    lista_s, lista_v = reverse("cadastros:servidores"), reverse("cadastros:viaturas")
    return {
        Servidor: (plural(servidores.count(), "ativo,ativos"),
                   (plural(inc_s, "incompleto,incompletos"), f"{lista_s}?aba=incompletos")
                   if inc_s else None),
        Viatura: (plural(viaturas.count(), "ativa,ativas"),
                  (plural(inc_v, "incompleta,incompletas"), f"{lista_v}?aba=incompletas")
                  if inc_v else None),
        Unidade: (plural(Unidade.objects.filter(ativo=True).count(), "ativa,ativas"),
                  (plural(sem_config, "sem configuração (não emite ofício),sem configuração "
                                      "(não emitem ofício)"), reverse("cadastros:configuracao"))
                  if sem_config else None),
    }


def _contagem(modelo, relacao: str):
    """Quantos registros de `relacao` apontam para cada linha — uma subconsulta por relação
    (vários Count() juntos multiplicariam as linhas do JOIN)."""
    reversa = modelo._meta.get_field(relacao)
    campo = reversa.field.name
    sub = (reversa.related_model.objects.filter(**{campo: OuterRef("pk")}).order_by()
           .values(campo).annotate(n=Count("pk")).values("n"))
    return Coalesce(Subquery(sub, output_field=IntegerField()), 0)


# ---------------------------------------------------------------- catálogos simples
def _catalogo_ou_404(slug: str) -> Catalogo:
    if slug not in CATALOGOS:
        raise Http404("Cadastro não encontrado.")
    return CATALOGOS[slug]


def _lista_catalogo(request: HttpRequest, slug: str, *, form=None, editando=None,
                    status: int = 200) -> HttpResponse:
    cat = _catalogo_ou_404(slug)
    policies.exigir(policies.pode_ver_cadastro(request.user, cat.modelo))
    acoes = policies.acoes_do_cadastro(request.user, cat.modelo)
    parametros = _parametros(request, "q", "aba")
    termo, aba = parametros.get("q", ""), parametros.get("aba", "")
    if aba not in ("", "inativos"):
        aba = ""
        parametros.pop("aba", None)
    todos = cat.modelo.objects.all()
    contagens = {"ativos": todos.filter(ativo=True).count(),
                 "inativos": todos.filter(ativo=False).count()}
    qs = _busca(todos.filter(ativo=(aba != "inativos")), termo, cat.busca)
    for relacao, _rotulo in cat.contar:
        qs = qs.annotate(**{f"n_{relacao}": _contagem(cat.modelo, relacao)})
    if cat.prefetch:
        qs = qs.prefetch_related(*cat.prefetch)
    pagina = Paginator(qs.order_by(*cat.modelo._meta.ordering), cat.por_pagina).get_page(
        request.GET.get("pagina"))
    for obj in pagina.object_list:
        obj.usos = [(getattr(obj, f"n_{rel}"), rotulo) for rel, rotulo in cat.contar
                    if getattr(obj, f"n_{rel}")]
        obj.detalhe = cat.detalhe(obj) if cat.detalhe else ""
    pk, novo = _abrir(request, acoes["alterar"] or acoes["criar"])
    if form is None and pk and acoes["alterar"]:
        editando = cat.modelo.objects.filter(pk=pk).first()
        form = cat.formulario.de(editando) if editando else None
    abrir = form is not None or (novo and acoes["criar"])
    if form is None:
        form = cat.formulario(**(cat.extras(None) if cat.extras else {}))
    return render(request, "cadastros/catalogo.html", {
        "cat": cat, "slug": slug, "page_obj": pagina, "termo": termo, "aba": aba,
        "abas": ABAS_ATIVOS, "contagens": contagens, "acoes": acoes,
        "querystring_base": _querystring(parametros), "voltar": request.get_full_path(),
        "form": form, "editando": editando, "abrir_dialogo": abrir,
        "migalhas": _migalhas(cat.titulo)}, status=status)


@require_GET
def catalogo(request: HttpRequest, slug: str) -> HttpResponse:
    return _lista_catalogo(request, slug)


def _pk_do_post(request: HttpRequest) -> int | None:
    texto = (request.POST.get("pk") or "").strip()
    pk = _inteiro(texto)
    if texto and pk is None:
        raise Http404
    return pk


@require_POST
def salvar_catalogo(request: HttpRequest, slug: str) -> HttpResponse:
    cat = _catalogo_ou_404(slug)
    pk = _pk_do_post(request)
    editando = get_object_or_404(cat.modelo, pk=pk) if pk else None
    form = cat.formulario(request.POST, **(cat.extras(editando) if cat.extras else {}))
    if form.is_valid():
        dados = getattr(form, "cleaned_para_salvar", form.cleaned_data)
        try:
            if cat.modelo is Unidade:
                obj = services.salvar_unidade(request.user, pk=pk, **dados)
            elif cat.salvar is not None:
                obj = cat.salvar(request.user, pk=pk, **dados)
            else:
                obj = services.salvar_catalogo(request.user, cat.modelo, pk=pk, **dados)
        except services.CadastroInvalido as exc:
            form.add_error("nome" if "nome" in form.fields else None, str(exc))
        else:
            # Chamada de dentro de outro formulário (o "+" ao lado de Cargo/Unidade): volta
            # o registro criado para a escolha receber a opção nova sem recarregar a página
            # — recarregar perderia o que já estava digitado no formulário de trás.
            if _quer_json(request):
                novo = {"id": obj.pk, "nome": str(obj)}
                if isinstance(obj, PresetAtividades):  # o plano aplica o conjunto por elas
                    novo["ids"] = ",".join(str(a.pk) for a in obj.atividades.all())
                return JsonResponse(novo)
            feito = ("atualizad" if pk else "criad") + cat.artigo
            messages.success(request, f"{cat.singular.capitalize()} “{obj}” {feito}.")
            return redirect(_voltar(request, slug))
    if _quer_json(request):
        erros = [str(e) for lista in form.errors.values() for e in lista]
        return JsonResponse({"erro": " ".join(erros) or "Não foi possível cadastrar."},
                            status=422)
    return _lista_catalogo(request, slug, form=form, editando=editando, status=422)


def _quer_json(request: HttpRequest) -> bool:
    return "application/json" in request.headers.get("Accept", "")


def _erros_em_texto(form) -> str:
    """Erros do formulário numa frase — o cadastro rápido só tem uma linha para mostrá-los."""
    erros = [str(e) for lista in form.errors.values() for e in lista]
    return " ".join(erros) or "Não foi possível cadastrar."


# ---------------------------------------------------------------- ações comuns
def _modelo_ou_404(slug: str) -> Any:
    if slug not in MODELOS:
        raise Http404("Cadastro não encontrado.")
    return MODELOS[slug]


def _acao(request: HttpRequest, slug: str, executar) -> HttpResponse:
    modelo = _modelo_ou_404(slug)
    try:
        mensagem = executar(modelo)
    except modelo.DoesNotExist as exc:
        raise Http404 from exc
    except (services.CadastroInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, mensagem)
    return redirect(_voltar(request, slug))


@require_POST
def alternar_ativo(request: HttpRequest, slug: str, pk: int) -> HttpResponse:
    def executar(modelo):
        obj = services.alternar_ativo(request.user, modelo, pk)
        if obj.ativo:
            return f"“{obj}” reativado: volta a aparecer nas escolhas."
        return (f"“{obj}” desativado: não aparece mais nas escolhas; o que já o usa não "
                "muda. Para desfazer, use Reativar na aba de inativos.")
    return _acao(request, slug, executar)


@require_POST
def definir_padrao(request: HttpRequest, slug: str, pk: int) -> HttpResponse:
    cat = _catalogo_ou_404(slug)
    if not cat.com_padrao:
        raise Http404

    def executar(modelo):
        atual = modelo.objects.get(pk=pk)
        obj = services.definir_padrao(request.user, modelo, pk, padrao=not atual.padrao)
        if obj.padrao:
            return f"“{obj}” agora é o {cat.singular} padrão."
        return f"“{obj}” deixou de ser o padrão."
    return _acao(request, slug, executar)


@require_POST
def excluir(request: HttpRequest, slug: str, pk: int) -> HttpResponse:
    return _acao(request, slug,
                 lambda modelo: f"Cadastro “{services.excluir(request.user, modelo, pk)}” "
                 "excluído.")


# ---------------------------------------------------------------- servidores
ABAS_SERVIDORES = [("", "Ativos", "ativos"), ("incompletos", "Incompletos", "incompletos"),
                   ("inativos", "Inativos", "inativos")]
INCOMPLETO = Q(cargo__isnull=True) | ~Q(cpf__regex=r"^\d{11}$")


def _lista_servidores(request: HttpRequest, *, form=None, editando=None,
                      status: int = 200) -> HttpResponse:
    policies.exigir(policies.pode_ver_cadastro(request.user, Servidor))
    acoes = policies.acoes_do_cadastro(request.user, Servidor)
    parametros = _parametros(request, "q", "aba", "cargo")
    termo, aba, cargo = (parametros.get(c, "") for c in ("q", "aba", "cargo"))
    todos = Servidor.objects.all()
    contagens = {"ativos": todos.filter(ativo=True).count(),
                 "incompletos": todos.filter(INCOMPLETO, ativo=True).count(),
                 "inativos": todos.filter(ativo=False).count()}
    qs = todos.filter(ativo=(aba != "inativos"))
    if aba == "incompletos":
        qs = qs.filter(INCOMPLETO)
    if termo:
        digitos = "".join(c for c in termo if c.isdigit())
        filtro = (Q(nome__unaccent__icontains=termo) | Q(cargo__nome__unaccent__icontains=termo)
                  | Q(unidade__sigla__unaccent__icontains=termo)
                  | Q(unidade__nome__unaccent__icontains=termo))
        if len(digitos) >= 3:
            filtro |= Q(cpf__contains=digitos) | Q(rg__contains=digitos) | Q(
                telefone__contains=digitos)
        qs = qs.filter(filtro)
    # Filtro por cargo, com contagem que respeita a busca e a aba (referência).
    total_filtro = qs.count()
    por_cargo = services.contagem_por(qs, "cargo")
    cargos = [(c, por_cargo.get(c.pk, 0)) for c in Cargo.objects.filter(pk__in=por_cargo)]
    if (cargo_pk := _inteiro(cargo)) is not None:
        qs = qs.filter(cargo_id=cargo_pk)
    qs = qs.annotate(n_oficios=_contagem(Servidor, "viagens"))
    pagina = Paginator(qs.select_related("cargo", "unidade").order_by("nome"), 25).get_page(
        request.GET.get("pagina"))
    pk, novo = _abrir(request, acoes["alterar"] or acoes["criar"])
    if form is None and pk and acoes["alterar"]:
        editando = Servidor.objects.filter(pk=pk).first()
        form = FormularioServidor.de(editando) if editando else None
    abrir = form is not None or (novo and acoes["criar"])
    if form is None:
        form = FormularioServidor()
    return render(request, "cadastros/servidores.html", {
        "page_obj": pagina, "termo": termo, "aba": aba, "cargo": cargo,
        "cargos": cargos, "total_filtro": total_filtro,
        "abas": ABAS_SERVIDORES, "contagens": contagens, "acoes": acoes,
        "querystring_base": _querystring(parametros), "voltar": request.get_full_path(),
        "form": form, "editando": editando, "abrir_dialogo": abrir,
        "migalhas": _migalhas("Servidores")}, status=status)


@require_GET
def servidores(request: HttpRequest) -> HttpResponse:
    return _lista_servidores(request)


@require_POST
def salvar_servidor(request: HttpRequest) -> HttpResponse:
    pk = _pk_do_post(request)
    editando = get_object_or_404(Servidor, pk=pk) if pk else None
    form = FormularioServidor(request.POST, instancia=editando)
    if form.is_valid():
        try:
            servidor = services.salvar_servidor(request.user, pk=pk, **form.cleaned_data)
        except services.CadastroInvalido as exc:
            form.add_error(None, str(exc))
        else:
            if servidor.completo:
                messages.success(request, f"Servidor “{servidor}” "
                                          f"{'atualizado' if pk else 'cadastrado'}.")
            else:
                falta = servidor.faltando_texto
                messages.warning(request, f"Servidor “{servidor}” salvo com cadastro "
                                          f"incompleto: falta {falta}.")
            # Chamado de dentro de outra folha (o "+" ao lado da busca de servidores, na
            # folha do ofício): devolve quem foi criado para a escolha receber a opção nova
            # sem recarregar — recarregar levaria junto o que já estava preenchido.
            if _quer_json(request):
                return JsonResponse({"id": servidor.pk, "nome": servidor.nome,
                                     "meta": servidor.descricao})
            return redirect(_depois_de_salvar(request, "servidores"))
    if _quer_json(request):
        return JsonResponse({"erro": _erros_em_texto(form)}, status=422)
    return _lista_servidores(request, form=form, editando=editando, status=422)


@require_GET
def buscar_servidores(request: HttpRequest) -> JsonResponse:
    """Busca de servidores ativos (nome, cargo, CPF) para as escolhas — ex.: motoristas."""
    policies.exigir(policies.pode_ver_cadastro(request.user, Servidor))
    termo = (request.GET.get("q") or "").strip()
    digitos = "".join(c for c in termo if c.isdigit())
    filtro = Q(nome__unaccent__icontains=termo) | Q(cargo__nome__unaccent__icontains=termo)
    if len(digitos) >= 3:
        filtro |= Q(cpf__contains=digitos)
    resultados = (Servidor.objects.filter(ativo=True).filter(filtro)
                  .select_related("cargo", "unidade").order_by("nome"))
    # `?excluir=1,2,3`: quem já está escolhido (a equipe) sai da lista.
    excluir = [int(i) for i in (request.GET.get("excluir") or "").split(",")[:200]
               if i.isascii() and i.isdecimal() and len(i) <= 18]
    if excluir:
        resultados = resultados.exclude(pk__in=excluir)
    return JsonResponse({"resultados": [
        {"id": str(s.pk), "titulo": s.nome, "meta": s.descricao,
         "cargo": s.cargo.nome if s.cargo is not None else "",
         "unidade": str(s.unidade_id or "")} for s in resultados[:15]]})


# ---------------------------------------------------------------- viaturas
ABAS_VIATURAS = [("", "Ativas", "ativos"), ("incompletas", "Incompletas", "incompletos"),
                 ("inativas", "Inativas", "inativos")]
INCOMPLETA = Q(modelo="") | Q(combustivel__isnull=True) | Q(tipo="")


def _form_viatura(*args, **kwargs) -> FormularioViatura:
    return FormularioViatura(*args, fonte_motoristas=reverse("cadastros:buscar_servidores"),
                             **kwargs)


def _lista_viaturas(request: HttpRequest, *, form=None, editando=None,
                    status: int = 200) -> HttpResponse:
    policies.exigir(policies.pode_ver_cadastro(request.user, Viatura))
    acoes = policies.acoes_do_cadastro(request.user, Viatura)
    parametros = _parametros(request, "q", "aba", "combustivel")
    termo, aba, combustivel = (parametros.get(c, "") for c in ("q", "aba", "combustivel"))
    todas = Viatura.objects.all()
    contagens = {"ativos": todas.filter(ativo=True).count(),
                 "incompletos": todas.filter(INCOMPLETA, ativo=True).count(),
                 "inativos": todas.filter(ativo=False).count()}
    qs = todas.filter(ativo=(aba != "inativas"))
    if aba == "incompletas":
        qs = qs.filter(INCOMPLETA)
    if termo:
        placa = "".join(c for c in termo.upper() if c.isalnum())
        filtro = (Q(modelo__unaccent__icontains=termo)
                  | Q(unidade__sigla__unaccent__icontains=termo)
                  | Q(unidade__nome__unaccent__icontains=termo)
                  | Q(motoristas__nome__unaccent__icontains=termo))
        if placa:
            filtro |= Q(placa__contains=placa)
        qs = qs.filter(filtro).distinct()
    total_filtro = qs.count()
    por_combustivel = services.contagem_por(qs, "combustivel")
    combustiveis = [(c, por_combustivel.get(c.pk, 0))
                    for c in Combustivel.objects.filter(pk__in=por_combustivel)]
    if (combustivel_pk := _inteiro(combustivel)) is not None:
        qs = qs.filter(combustivel_id=combustivel_pk)
    qs = qs.annotate(n_oficios=_contagem(Viatura, "oficios"))
    pagina = Paginator(qs.select_related("combustivel", "unidade")
                       .prefetch_related("motoristas").order_by("placa"), 25).get_page(
        request.GET.get("pagina"))
    pk, novo = _abrir(request, acoes["alterar"] or acoes["criar"])
    if form is None and pk and acoes["alterar"]:
        editando = Viatura.objects.filter(pk=pk).first()
        form = FormularioViatura.de(
            editando, fonte_motoristas=reverse("cadastros:buscar_servidores")) \
            if editando else None
    abrir = form is not None or (novo and acoes["criar"])
    if form is None:
        form = _form_viatura()
    return render(request, "cadastros/viaturas.html", {
        "page_obj": pagina, "termo": termo, "aba": aba, "combustivel": combustivel,
        "combustiveis": combustiveis, "total_filtro": total_filtro,
        "abas": ABAS_VIATURAS, "contagens": contagens, "acoes": acoes,
        "querystring_base": _querystring(parametros), "voltar": request.get_full_path(),
        "form": form, "editando": editando, "abrir_dialogo": abrir,
        "migalhas": _migalhas("Viaturas")}, status=status)


@require_GET
def viaturas(request: HttpRequest) -> HttpResponse:
    return _lista_viaturas(request)


@require_POST
def salvar_viatura(request: HttpRequest) -> HttpResponse:
    pk = _pk_do_post(request)
    editando = get_object_or_404(Viatura, pk=pk) if pk else None
    form = _form_viatura(request.POST, instancia=editando)
    if form.is_valid():
        try:
            viatura = services.salvar_viatura(request.user, pk=pk, **form.cleaned_data)
        except services.CadastroInvalido as exc:
            form.add_error("placa", str(exc))
        else:
            if viatura.completo:
                messages.success(request, f"Viatura {viatura.placa_formatada} "
                                          f"{'atualizada' if pk else 'cadastrada'}.")
            else:
                falta = viatura.faltando_texto
                messages.warning(request, f"Viatura {viatura.placa_formatada} salva com "
                                          f"cadastro incompleto: falta {falta}.")
            if _quer_json(request):
                return JsonResponse({"id": viatura.pk, "nome": str(viatura)})
            return redirect(_depois_de_salvar(request, "viaturas"))
    if _quer_json(request):
        return JsonResponse({"erro": _erros_em_texto(form)}, status=422)
    return _lista_viaturas(request, form=form, editando=editando, status=422)


# ---------------------------------------------------------------- tabela de diárias
def _percentual(valor: Decimal, pct: int) -> Decimal:
    return (valor * pct / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _lista_diarias(request: HttpRequest, *, form=None, editando=None,
                   status: int = 200) -> HttpResponse:
    policies.exigir(policies.pode_ver_cadastro(request.user, TabelaDiaria))
    acoes = policies.acoes_do_cadastro(request.user, TabelaDiaria)
    hoje = timezone.localdate()
    tabelas = list(TabelaDiaria.objects.order_by("-vigente_desde", "faixa"))
    vigentes: dict[str, int] = {}
    for t in tabelas:  # a mais recente de cada faixa que já começou
        if t.vigente_desde <= hoje:
            vigentes.setdefault(t.faixa, t.pk)
    linhas = [{"tabela": t, "p15": _percentual(t.valor_24h, 15),
               "p30": _percentual(t.valor_24h, 30), "vigente": vigentes.get(t.faixa) == t.pk}
              for t in tabelas]
    pk, novo = _abrir(request, acoes["alterar"] or acoes["criar"])
    if form is None and pk and acoes["alterar"]:
        editando = TabelaDiaria.objects.filter(pk=pk).first()
        form = FormularioVigencia.de(editando) if editando else None
    abrir = form is not None or (novo and acoes["criar"])
    if form is None:
        form = FormularioVigencia()
    return render(request, "cadastros/diarias.html", {
        "linhas": linhas, "acoes": acoes, "form": form, "editando": editando,
        "abrir_dialogo": abrir, "voltar": request.get_full_path(),
        "migalhas": _migalhas("Tabela de diárias")}, status=status)


@require_GET
def diarias(request: HttpRequest) -> HttpResponse:
    return _lista_diarias(request)


@require_POST
def salvar_vigencia(request: HttpRequest) -> HttpResponse:
    pk = _pk_do_post(request)
    editando = get_object_or_404(TabelaDiaria, pk=pk) if pk else None
    form = FormularioVigencia(request.POST)
    if form.is_valid():
        try:
            vigencia = services.salvar_vigencia(request.user, pk=pk, **form.cleaned_data)
        except services.CadastroInvalido as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Vigência “{vigencia}” "
                                      f"{'atualizada' if pk else 'cadastrada'}.")
            return redirect("cadastros:diarias")
    return _lista_diarias(request, form=form, editando=editando, status=422)


@require_POST
def excluir_vigencia(request: HttpRequest, pk: int) -> HttpResponse:
    get_object_or_404(TabelaDiaria, pk=pk)
    try:
        nome = services.excluir_vigencia(request.user, pk)
    except (services.CadastroInvalido, PermissionDenied) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Vigência “{nome}” excluída.")
    return redirect("cadastros:diarias")


# ---------------------------------------------------------------- configuração da unidade
def _unidade_do_usuario(usuario) -> Unidade | None:
    try:
        return usuario.lotacao.unidade
    except Lotacao.DoesNotExist:
        return None


def _configuracao_pedida(request: HttpRequest) -> tuple[Unidade | None, list[Unidade]]:
    """A unidade cuja configuração se vê: a da lotação; quem altera escolhe entre as que a
    política permite (`?unidade=<pk>`)."""
    propria = _unidade_do_usuario(request.user)
    unidades = list(policies.unidades_configuraveis(request.user).order_by("sigla", "nome"))
    if not unidades:
        return propria, []
    pedida = _inteiro(request.GET.get("unidade") or request.POST.get("unidade"))
    if pedida is not None:
        escolhida = next((u for u in unidades if u.pk == pedida), None)
        if escolhida is None and propria is not None and propria.pk == pedida:
            escolhida = propria  # a própria, mesmo inativa
        if escolhida is None:
            raise Http404("Unidade não encontrada.")
        return escolhida, unidades
    return propria or unidades[0], unidades


def _tela_configuracao(request: HttpRequest, unidade, unidades, *, form=None,
                       form_sub=None, status: int = 200) -> HttpResponse:
    config = ConfiguracaoInstitucional.objects.filter(unidade=unidade).select_related(
        "sede").first() if unidade else None
    pode = unidade is not None and policies.pode_alterar_configuracao(request.user, unidade)
    if form is None:
        form = FormularioConfiguracao.de(config) if config else FormularioConfiguracao()
    if not pode:  # leitura: sem edição e sem a marca de obrigatório
        for campo in form.fields.values():
            campo.disabled, campo.required = True, False
    substituicoes = (list(config.substituicoes.select_related("servidor__cargo"))
                     if config else [])
    hoje = timezone.localdate()
    for sub in substituicoes:
        setattr(sub, "vigente", sub.vale_em(sub.tipo, hoje))  # noqa: B010
    hoje_assina = [(rotulo, services.quem_assina(config, tipo, hoje)) for tipo, rotulo in (
        ("oficio", "Ofícios"), ("justificativa", "Justificativas"),
        ("plano_trabalho", "Planos de trabalho"))] if config else []
    return render(request, "cadastros/configuracao.html", {
        "unidade": unidade, "unidades": unidades, "config": config, "form": form,
        "pode_alterar": pode, "substituicoes": substituicoes, "hoje_assina": hoje_assina,
        "form_sub": form_sub or FormularioSubstituicao(initial={"inicio": hoje}),
        "abrir_substituicao": form_sub is not None,
        "migalhas": _migalhas("Configuração da unidade")}, status=status)


def _na_configuracao(unidade) -> str:
    return f"{reverse('cadastros:configuracao')}?unidade={unidade.pk}"


@require_http_methods(["GET", "POST"])
def configuracao(request: HttpRequest) -> HttpResponse:
    policies.exigir(policies.pode_ver_configuracao(request.user))
    unidade, unidades = _configuracao_pedida(request)
    if request.method == "GET":
        return _tela_configuracao(request, unidade, unidades)
    if unidade is None:
        raise Http404("Sem unidade para configurar.")
    config = ConfiguracaoInstitucional.objects.filter(unidade=unidade).first()
    form = FormularioConfiguracao(request.POST, config=config)
    if form.is_valid():
        services.salvar_configuracao(request.user, unidade, **form.cleaned_data)
        messages.success(request, f"Configuração de {unidade} salva. Vale para os próximos "
                                  "documentos; os já emitidos não mudam.")
        return redirect(_na_configuracao(unidade))
    return _tela_configuracao(request, unidade, unidades, form=form, status=422)


@require_POST
def salvar_substituicao(request: HttpRequest) -> HttpResponse:
    policies.exigir(policies.pode_ver_configuracao(request.user))
    unidade, unidades = _configuracao_pedida(request)
    if unidade is None:
        raise Http404("Sem unidade para configurar.")
    form = FormularioSubstituicao(request.POST)
    if form.is_valid():
        try:
            sub = services.salvar_substituicao(request.user, unidade, **form.cleaned_data)
        except services.CadastroInvalido as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"{sub.servidor} assina {sub.get_tipo_display().lower()} "
                                      f"{sub.periodo}.")
            return redirect(_na_configuracao(unidade))
    return _tela_configuracao(request, unidade, unidades, form_sub=form, status=422)


@require_POST
def alternar_substituicao(request: HttpRequest, pk: int) -> HttpResponse:
    policies.exigir(policies.pode_ver_configuracao(request.user))
    unidade, _ = _configuracao_pedida(request)
    if unidade is None:
        raise Http404
    try:
        sub = services.encerrar_substituicao(request.user, unidade, pk)
    except SubstituicaoAssinante.DoesNotExist as exc:
        raise Http404 from exc
    if sub.ativo:
        messages.success(request, f"Substituição de {sub.servidor} reativada.")
    else:
        messages.success(request, f"Substituição de {sub.servidor} encerrada: os documentos "
                                  "voltam a sair com o titular.")
    return redirect(_na_configuracao(unidade))
