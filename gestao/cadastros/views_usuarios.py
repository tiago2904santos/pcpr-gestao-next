"""Usuários do sistema (paridade com a gestão de usuários da referência): lista com busca,
abas Ativos/Inativos, filtro por perfil e último acesso; cadastro em janela (nome, login,
e-mail, perfis, lotação, senha inicial); ativar/inativar (nunca a si mesmo).

A conta é de Identidade (`identidade.services`); a lotação é de Cadastros e é gravada na
mesma transação — Identidade não conhece unidades (import-linter).
"""

from __future__ import annotations

from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from gestao.identidade import policies as politica
from gestao.identidade import services as contas
from gestao.identidade.models import Usuario
from gestao.identidade.papeis import PAPEIS

from .forms import FormularioUsuario
from .models import Lotacao
from .views_crud import _abrir, _inteiro, _migalhas, _parametros, _querystring

ABAS = [("", "Ativos", "ativos"), ("inativos", "Inativos", "inativos")]
ROTULOS = {"OPERADOR_VIAGENS": "Operador de viagens", "GESTOR_VIAGENS": "Gestor de viagens",
           "CONSULTA": "Consulta", "ADMINISTRADOR": "Administrador",
           "ASCOM_IMPRENSA": "Atendimento à imprensa (ASCOM)",
           "ASCOM_PUBLICACOES": "Publicações (ASCOM)"}


def _voltar(request: HttpRequest) -> str:
    voltar = request.POST.get("voltar") or ""
    base = reverse("cadastros:usuarios")
    if (urlsplit(voltar).path == base
            and url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()})):
        return voltar
    return base


def _tela(request: HttpRequest, *, form=None, editando=None, status: int = 200) -> HttpResponse:
    politica.exigir(politica.pode_ver_usuarios(request.user))
    parametros = _parametros(request, "q", "aba", "perfil")
    termo, aba, perfil = (parametros.get(c, "") for c in ("q", "aba", "perfil"))
    todos = Usuario.objects.all()
    contagens = {"ativos": todos.filter(is_active=True).count(),
                 "inativos": todos.filter(is_active=False).count()}
    qs = todos.filter(is_active=(aba != "inativos"))
    if termo:
        qs = qs.filter(Q(nome__unaccent__icontains=termo) | Q(login__icontains=termo)
                       | Q(email__icontains=termo))
    por_perfil = dict(Group.objects.filter(name__in=PAPEIS, user__in=qs)
                      .annotate(n=Count("user", distinct=True)).values_list("name", "n"))
    perfis = [(nome, ROTULOS.get(nome, nome), por_perfil.get(nome, 0)) for nome in PAPEIS]
    total_filtro = qs.count()
    if perfil in PAPEIS:
        qs = qs.filter(groups__name=perfil)
    pagina = Paginator(qs.select_related("lotacao__unidade").prefetch_related("groups")
                       .order_by("nome", "login").distinct(), 25).get_page(
                           request.GET.get("pagina"))
    pode_criar = politica.pode_criar_usuario(request.user)
    pk, novo = _abrir(request, pode_criar or request.user.has_perm("identidade.change_usuario"))
    if form is None and pk:
        alvo = Usuario.objects.filter(pk=pk).select_related("lotacao").first()
        if alvo is not None and politica.pode_editar_usuario(request.user, alvo):
            editando, form = alvo, FormularioUsuario.de(alvo)
    abrir = form is not None or (novo and pode_criar)
    if form is None:
        form = FormularioUsuario()
    linhas = [{"u": u, "papeis": [ROTULOS.get(g.name, g.name) for g in u.groups.all()
                                  if g.name in PAPEIS],
               "unidade": u.lotacao.unidade if _tem_lotacao(u) else None,
               "editar": politica.pode_editar_usuario(request.user, u),
               "alternar": politica.pode_alternar_ativo(request.user, u)}
              for u in pagina.object_list]
    return render(request, "cadastros/usuarios.html", {
        "page_obj": pagina, "linhas": linhas, "termo": termo, "aba": aba, "perfil": perfil,
        "perfis": perfis, "total_filtro": total_filtro, "abas": ABAS, "contagens": contagens,
        "pode_criar": pode_criar, "querystring_base": _querystring(parametros),
        "voltar": request.get_full_path(), "form": form, "editando": editando,
        "abrir_dialogo": abrir, "migalhas": _migalhas("Usuários")}, status=status)


def _tem_lotacao(usuario) -> bool:
    try:
        return usuario.lotacao is not None
    except Lotacao.DoesNotExist:
        return False


@require_GET
def usuarios(request: HttpRequest) -> HttpResponse:
    return _tela(request)


@require_POST
def salvar_usuario(request: HttpRequest) -> HttpResponse:
    texto = (request.POST.get("pk") or "").strip()
    pk = _inteiro(texto)
    editando = get_object_or_404(Usuario.objects.select_related("lotacao"), pk=pk) if pk else None
    if editando is not None:
        politica.exigir(politica.pode_editar_usuario(request.user, editando),
                        "Você não pode alterar este usuário.")
    else:
        politica.exigir(politica.pode_criar_usuario(request.user),
                        "Você não pode criar usuários.")
    form = FormularioUsuario(request.POST, instancia=editando)
    if form.is_valid():
        dados = form.cleaned_data
        unidade = dados["unidade"]
        try:
            with transaction.atomic():
                usuario = contas.salvar(
                    request.user, pk=pk, nome=dados["nome"], login=dados["login"],
                    email=dados["email"], papeis=dados["papeis"], senha=dados["senha"],
                    unidade_sigla=getattr(unidade, "sigla", "") or "")
                if unidade is None:
                    Lotacao.objects.filter(usuario=usuario).delete()
                else:
                    Lotacao.objects.update_or_create(usuario=usuario,
                                                     defaults={"unidade": unidade})
        except contas.UsuarioInvalido as exc:
            form.add_error(None, str(exc))
        else:
            if pk:
                texto = f"Usuário “{usuario.login}” atualizado."
                if dados["senha"]:
                    texto += " A nova senha vale até a pessoa trocar por uma dela no acesso."
            else:
                texto = (f"Usuário “{usuario.login}” criado. No primeiro acesso a pessoa "
                         "define uma senha só dela.")
            messages.success(request, texto)
            destino = _voltar(request)
            if request.POST.get("outro") == "1":
                destino += ("&" if "?" in destino else "?") + "novo=1"
            return redirect(destino)
    return _tela(request, form=form, editando=editando, status=422)


@require_POST
def alternar_ativo_usuario(request: HttpRequest, pk: int) -> HttpResponse:
    politica.exigir(politica.pode_ver_usuarios(request.user))
    try:
        usuario = contas.alternar_ativo(request.user, pk)
    except contas.UsuarioInvalido as exc:
        messages.error(request, str(exc))
    except PermissionDenied as exc:
        messages.error(request, str(exc))
    except Usuario.DoesNotExist:
        messages.error(request, "Usuário não encontrado.")
    else:
        messages.success(request, f"Usuário “{usuario.login}” "
                                  f"{'ativado' if usuario.is_active else 'inativado'}.")
    return redirect(_voltar(request))
