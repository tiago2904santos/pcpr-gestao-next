# PCPR — Gestão de Eventos e Viagens (nova implementação)

Nova versão, **greenfield**, do sistema de Gestão de Eventos Sociais / Central de Viagens
da Polícia Civil do Paraná. O sistema atual (https://eventos.gerenciadorviagens.tech) é
**referência funcional e visual**; nenhuma linha de código, template, CSS ou JS dele é
reaproveitada. Regras de negócio, fluxos e documentos foram redescobertos e reimplementados
(ver `docs/product/` e `docs/parity/`).

## Stack
| Camada | Escolha | Por quê (ADR) |
|---|---|---|
| Aplicação | Python 3.13 + Django 6.1, monólito modular por contexto | `docs/adr/0001` |
| Interface | HTML no servidor + HTMX + Web Components (sem bundler) | `docs/adr/0002` |
| Design System | Tokens CSS (fonte única) + componentes + UI Lab | `docs/adr/0003`, `docs/design-system/` |
| Banco | PostgreSQL 16; auditoria e integridade por triggers/constraints | `docs/adr/0004` |
| Efeitos colaterais | Outbox transacional + worker com `SKIP LOCKED` | `docs/adr/0005` |
| Documentos | WeasyPrint → **PDF/A-2a** (fontes embutidas, estrutura marcada) | `docs/adr/0008` |

## Começando (DEV)
```bash
uv sync                                  # dependências Python (3.13)
npm ci && npm run vendor                 # opcional: re-vendoriza htmx, ícones, fonte, axe
cp .env.example .env                     # ajuste POSTGRES_PASSWORD
uv run python manage.py migrate
uv run python manage.py semear_dev       # usuários, cadastros e ofícios fictícios (DEV/LAB)
uv run python manage.py runserver
uv run python manage.py processar_outbox # outro terminal: worker (PDF, notificações)
```
Acesse http://127.0.0.1:8000 — usuário `operador` / senha `senha-local-123` (só DEV/LAB).

## Ver o sistema no navegador (PREVIEW, sem senha)
Ambiente `preview` com base fictícia populosa (~260 ofícios) e entrada DEMO: na tela de login,
deixe usuário e senha em branco e clique em **Entrar**. Só existe com `APP_ENV=preview` e
`DEMO_MODE=true`; produção recusa essa combinação (ADR 0011).
```bash
scripts/preview.sh subir     # Docker → http://localhost:8000
scripts/preview.sh local     # sem Docker (PostgreSQL local, banco pcpr_preview)
```
Ou **Code → Codespaces → Create codespace** no GitHub (URL privada `…-8000.app.github.dev`).
Detalhes, reset e verificação: `docs/ops/preview.md`.

## Abrir no celular (URL pública HTTPS)
```powershell
.\scripts\tunnel.ps1     # Windows: instala o devtunnel, sobe o DEV e publica https://…devtunnels.ms
```
Alternativas (mesma rede Wi-Fi, Codespaces, Cloudflare) e as variáveis que o Django precisa
atrás de um tunnel: `docs/ops/tunnel.md`.

## Qualidade
```bash
uv run python manage.py doctor           # diagnóstico do ambiente
scripts/verificar.sh                     # lint + tipos + fronteiras + testes rápidos
uv run pytest -m "e2e or visual or a11y or perf"   # navegador (Playwright + axe)
```

## Estrutura
```
config/                 settings por ambiente (lab, dev, preview, staging, production, test)
gestao/plataforma/      núcleo técnico: auditoria, outbox, navegação, UI, erros, saúde
gestao/identidade/      usuários, login, papéis
gestao/cadastros/       servidores, viaturas, unidades, cargos, municípios, tabela de diárias
gestao/viagens/         ofícios: domínio puro (diárias, regras), serviços, documentos, telas
gestao/painel/          central de módulos, painel, busca global
gestao/ui_lab/          vitrine do Design System
static/                 tokens.css, CSS, Web Components, vendor (htmx), ícones, fontes
templates/              shell, arquétipos, componentes de template, erros
docs/                   produto, design system, ADRs, paridade, revisões, qualidade
tests/                  E2E, acessibilidade, visual, responsivo, desempenho
```
