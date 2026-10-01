"""Usuário do sistema e controle de tentativas de acesso."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class GerenciadorUsuarios(BaseUserManager["Usuario"]):
    use_in_migrations = True

    def create_user(self, login: str, email: str, password: str | None = None, **extra):
        usuario = self.model(login=login, email=self.normalize_email(email).lower(), **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, login: str, email: str, password: str | None = None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self.create_user(login, email, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Pessoa que acessa o sistema.

    Entra com o login (ex.: `ana.lima`) ou com o e-mail institucional. O
    vínculo com um servidor (cadastro de Viagens) é opcional e fica no
    contexto de Cadastros, para não acoplar identidade a regra de negócio.
    """

    login = models.CharField("login", max_length=60, unique=True)
    email = models.EmailField("e-mail institucional", unique=True)
    nome = models.CharField("nome completo", max_length=150)
    unidade_sigla = models.CharField("unidade", max_length=40, blank=True)
    is_active = models.BooleanField("ativo", default=True)
    is_staff = models.BooleanField("acesso administrativo", default=False)
    criado_em = models.DateTimeField(default=timezone.now)
    deve_trocar_senha = models.BooleanField(default=False)

    USERNAME_FIELD = "login"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email", "nome"]

    objects = GerenciadorUsuarios()

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        constraints = [
            models.UniqueConstraint(Lower("login"), name="usuario_login_ci_unico"),
            models.UniqueConstraint(Lower("email"), name="usuario_email_ci_unico"),
        ]

    def __str__(self) -> str:
        return self.nome or self.login

    @property
    def primeiro_nome(self) -> str:
        return (self.nome or self.login).split()[0]

    @property
    def iniciais(self) -> str:
        partes = (self.nome or self.login).split()
        return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()


class TentativaAcesso(models.Model):
    """Tentativas de login malsucedidas, para bloqueio progressivo."""

    identificador = models.CharField(max_length=150)
    ip = models.GenericIPAddressField(null=True)
    ocorrida_em = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["identificador", "ocorrida_em"])]

    def __str__(self) -> str:
        return f"{self.identificador} em {self.ocorrida_em:%d/%m/%Y %H:%M}"
