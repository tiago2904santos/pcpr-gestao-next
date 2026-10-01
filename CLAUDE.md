# CLAUDE.md — instruções para agentes neste repositório

Leia também `AGENTS.md` (regras gerais para qualquer agente).

## Contexto
Nova implementação (greenfield) do sistema PCPR de Gestão de Eventos e Viagens.
O sistema antigo é **REFERÊNCIA**, nunca código-base: não copie código, templates, CSS ou
JS dele. Para entender um comportamento, leia a especificação em `docs/product/` e os
testes de caracterização em `gestao/*/tests/`; para ver a tela de referência use
`scripts/referencia/capturar_referencia.py` (somente leitura, credenciais via ambiente).

## Comandos
- Testes rápidos: `uv run pytest -m "not e2e and not visual and not a11y and not perf" -n auto`
- Navegador: `uv run pytest -m "e2e or a11y or visual or perf"` (servidor sobe sozinho)
- Lint/tipos/fronteiras: `scripts/verificar.sh`
- Capturas: `uv run python scripts/capturar.py /viagens/oficios/ --larguras 360,1440`
- Diagnóstico: `uv run python manage.py doctor`

## Regras de arquitetura (verificadas por import-linter)
- `gestao/viagens/dominio/` é Python puro (sem Django): regras de diárias, prazos, estados.
- `gestao/plataforma` não importa contextos de negócio.
- Escritas de negócio passam por `services.py` (transação + outbox + histórico).
- Autorização em `policies.py` do contexto; views nunca checam papel "na mão".
- Auditoria é do banco (trigger); não escreva em `auditoria_evento`.

## Regras de interface
- Valores visuais só via tokens (`static/css/tokens.css`); `tests/test_design_tokens.py` reprova hex soltos.
- Novo componente → primeiro no UI Lab (`/ui-lab/`), depois nas telas.
- Sem estilos/scripts inline (CSP estrita com nonce).
- Toda tela nova: estados vazio/erro, 360–1440px sem rolagem horizontal, axe sem violações.

## Segurança
- Nunca commitar segredos (`.env` é ignorado). Credenciais do sistema de referência só em variáveis de ambiente.
- Operações destrutivas apenas com `APP_ENV` em lab/dev/test (`gestao.plataforma.ambiente`).
- Em PRODUCTION, ferramentas do agente são somente leitura (`.mcp.json` usa papel `pcpr_leitura`).
