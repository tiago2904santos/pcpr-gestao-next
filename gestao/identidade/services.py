"""Escritas de usuários (paridade com a gestão de usuários da referência).

Senha definida por quem cadastra marca `deve_trocar_senha`: no próximo acesso a pessoa
escolhe uma só dela (TrocaDeSenhaObrigatoriaMiddleware). A trilha do banco registra tudo
(sem a senha). A lotação é de Cadastros (fronteira: identidade não conhece unidades): quem
chama grava a lotação na mesma transação.
"""

from __future__ import annotations

from django.contrib.auth.models import Group
from django.db import transaction

from . import policies
from .models import Usuario
from .papeis import PAPEIS


class UsuarioInvalido(Exception):
    pass


NOMES_DOS_PAPEIS = set(PAPEIS)


@transaction.atomic
def salvar(autor, *, pk: int | None, nome: str, login: str, email: str, papeis: list[str],
           senha: str = "", unidade_sigla: str = "") -> Usuario:
    if pk:
        usuario = Usuario.objects.select_for_update().get(pk=pk)
        policies.exigir(policies.pode_editar_usuario(autor, usuario),
                        "Você não pode alterar este usuário.")
    else:
        policies.exigir(policies.pode_criar_usuario(autor), "Você não pode criar usuários.")
        usuario = Usuario()
        if not senha:
            raise UsuarioInvalido("Defina a senha inicial do usuário.")
    desconhecidos = set(papeis) - NOMES_DOS_PAPEIS
    if desconhecidos:
        raise UsuarioInvalido("Perfil desconhecido.")
    if (pk and usuario.pk == autor.pk and "ADMINISTRADOR" not in papeis
            and not autor.is_superuser):
        raise UsuarioInvalido("Você não pode tirar o seu próprio perfil de administrador.")
    usuario.nome = " ".join(nome.split())
    usuario.login = login.strip()
    usuario.email = email.strip().lower()
    usuario.unidade_sigla = unidade_sigla
    if senha:
        usuario.set_password(senha)
        usuario.deve_trocar_senha = True
    usuario.save()
    # Os papéis do sistema são trocados; outros grupos (se houver) ficam como estão.
    outros = list(usuario.groups.exclude(name__in=NOMES_DOS_PAPEIS))
    usuario.groups.set(outros + list(Group.objects.filter(name__in=papeis)))
    return usuario


@transaction.atomic
def alternar_ativo(autor, pk: int) -> Usuario:
    usuario = Usuario.objects.select_for_update().get(pk=pk)
    if usuario.pk == autor.pk:
        raise UsuarioInvalido("Você não pode inativar o seu próprio usuário.")
    policies.exigir(policies.pode_alternar_ativo(autor, usuario),
                    "Você não pode alterar este usuário.")
    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=["is_active"])
    return usuario
