# ADR 0010 — Ambientes LAB / DEV / STAGING / PRODUCTION e segredos

- **Status:** aceito · **Data:** 2026-10-01

| Ambiente | Settings | Dados | Destrutivo? | Ferramentas do agente |
|---|---|---|---|---|
| LAB | `config.settings.lab` | sintéticos | **sim** (auditorias destrutivas, carga) | leitura e escrita |
| DEV | `config.settings.dev` | fictícios | sim (local) | leitura e escrita |
| TEST | `config.settings.test` | gerados por teste | sim (banco efêmero) | — |
| PREVIEW | `config.settings.preview` | fictícios (`semear_demo`) | só o dataset DEMO | leitura e escrita (ADR 0011) |
| STAGING | `config.settings.staging` | anonimizados | não | leitura |
| PRODUCTION | `config.settings.production` | reais | não | **somente leitura** |

- `gestao.plataforma.ambiente.exigir_ambiente_destrutivo()` protege comandos que apagam ou
  geram dados (`semear_dev`, `resetar_lab`).
- Cabeçalho mostra selo do ambiente fora de produção (evita operar no lugar errado).
- `manage.py check --deploy` falha com DEBUG, chave insegura ou APP_ENV inválido.
- **Segredos só por variável de ambiente**; `.env` ignorado pelo Git; `.env.example` sem
  valores. CI usa secrets do GitHub. Bancos: papel `pcpr_app` (escrita) e `pcpr_leitura`
  (somente SELECT) — o MCP do agente usa o segundo.
