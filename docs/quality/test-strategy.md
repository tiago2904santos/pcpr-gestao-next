# Estratégia de testes

| Camada | Onde | Ferramenta | Roda no CI | O que garante |
|---|---|---|---|---|
| Domínio | `gestao/*/tests/test_dominio_*.py` | pytest + Hypothesis | job `testes` | Diárias (demonstrativos oficiais), prazos, numeração, valor por extenso |
| Integração | `gestao/*/tests/test_servicos.py`, `test_views.py` | pytest-django (PostgreSQL real) | `testes` | Serviços, permissões, constraints, auditoria, outbox, PDF/A |
| Design System | `tests/test_design_tokens.py` | pytest | `testes` | Tokens como fonte única e contraste WCAG |
| E2E | `tests/e2e/test_fluxo_oficio.py` | Playwright (Chromium) | `navegador` | Jornada completa, teclado, permissões, gaveta mobile |
| Acessibilidade | `tests/e2e/test_acessibilidade.py` | axe-core | `navegador` | WCAG 2.2 AA automático |
| Responsivo/visual | `tests/e2e/test_responsivo.py` | Playwright | `navegador` | 6 larguras: sem rolagem lateral, sobreposição, corte, erro de console; capturas em `artifacts/` |
| Desempenho | `tests/e2e/test_desempenho.py` | Playwright + Server-Timing | `navegador` | Orçamentos (Core Web Vitals, peso, SQL) |
| Segurança | CI `qualidade` | bandit, pip-audit, `check --deploy`, testes de CSP/cabeçalhos | `qualidade` | SAST, dependências, configuração |
| Arquitetura | CI `qualidade` | import-linter | `qualidade` | Fronteiras entre contextos |

Cobertura mínima no CI: **85%** (atual 95%).

Regra: bug encontrado → teste que o reproduz primeiro (exemplos: conflito de versão após
editar a equipe; rolagem fantasma a 1024 px; busca "001/" sem resultado).
