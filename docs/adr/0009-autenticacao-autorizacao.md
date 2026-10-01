# ADR 0009 — Autenticação e autorização

- **Status:** aceito · **Data:** 2026-10-01

## Autenticação
- Usuário próprio (`identidade.Usuario`): login **ou** e-mail institucional, sem diferenciar
  caixa; senhas com Argon2; mínimo 10 caracteres.
- `LoginRequiredMiddleware` (Django 5.1+): tudo exige login, exceções explícitas
  (`@login_not_required`: entrar, saúde).
- Bloqueio progressivo: 5 falhas em 15 min por identificador.
- Sessão de 10h (um turno), cookies `HttpOnly`, `SameSite=Lax`, `Secure` em STAGING/PROD.
- Futuro: SSO institucional (OIDC) como backend adicional, sem mudar o modelo.

## Autorização
- **Papéis** = `Group` gerados de `gestao/identidade/papeis.py` (fonte única, versionada).
- **Permissões** do Django (`viagens.emitir_oficio`, `viagens.ver_todas_unidades`…).
- **Regras por objeto** em `policies.py` de cada contexto: ex. operador só vê/edita ofícios
  da própria unidade; ofício emitido não é editável; cancelar exige permissão própria.
- Views usam `policies` (nunca `if user.groups…` espalhado); o menu usa as mesmas permissões.
- Matriz documentada em `docs/product/permissions.md` e testada (`gestao/viagens/tests/test_servicos.py` e `test_views.py`: papéis, unidade e 404 para outra unidade).
