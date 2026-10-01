# Segurança — piloto

| Controle | Implementação | Verificação |
|---|---|---|
| Autenticação | Argon2, mínimo 10 caracteres, bloqueio após 5 falhas em 15 min | `test_acesso.py` |
| Sessão | 10h, HttpOnly, SameSite=Lax, Secure em STAGING/PROD | `check --deploy` |
| Tudo exige login | `LoginRequiredMiddleware`; exceções explícitas | `test_paginas_exigem_login` |
| Autorização por papel e unidade | `viagens/policies.py`; ofício de outra unidade responde 404 (não revela existência) | `test_outra_unidade_*` |
| CSRF | Django + header do HTMX via `<meta>` | — |
| CSP | `script-src 'self' 'nonce-…'`, `style-src 'self'`, sem `unsafe-inline`/`unsafe-eval`; htmx com `allowEval=false` | `test_cabecalhos_de_seguranca` |
| Clickjacking | `X-Frame-Options: DENY`, `frame-ancestors 'none'` | idem |
| Auditoria | Trigger no banco, imutável, cadeia de hash | `test_auditoria.py`, `verificar_auditoria` |
| Documentos | Download só para quem vê o ofício; SHA-256 no cabeçalho `X-Content-SHA256` | `test_views.py` |
| Segredos | Só em variáveis de ambiente; `.env` ignorado; `check --deploy` recusa chave de DEV | `test_check_de_deploy_*` |
| Ambientes | Comandos destrutivos só em LAB/DEV/TEST | `test_operacao_destrutiva_*` |
| Dependências | `pip-audit --strict` | CI |
| SAST | `bandit` | CI |
| Credenciais do sistema de referência | Nunca versionadas; ferramenta lê de `REF_USER`/`REF_PASS` e só faz GET | `scripts/referencia/` |

Pendências para produção: SSO institucional (OIDC), política de retenção da trilha de
auditoria, varredura DAST (OWASP ZAP) no STAGING.
