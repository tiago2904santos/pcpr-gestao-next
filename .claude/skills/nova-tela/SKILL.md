---
name: nova-tela
description: Receita para criar uma tela nova no sistema PCPR a partir de um arquétipo, com testes de navegador, acessibilidade e responsividade.
---
1. Identifique o arquétipo (LIST, FORM, DETAIL…) em `docs/design-system/page-archetypes.md`.
2. Documente a regra de negócio em `docs/product/` (se ainda não estiver).
3. Domínio → serviço → policy → query → view → template (estende `arquetipos/<tipo>.html`).
4. Use só componentes existentes; se faltar, use a skill `novo-componente` primeiro.
5. Estados: vazio, sem resultado, erro de validação, sem permissão (403).
6. Testes: unidade (domínio), integração (view + policy), E2E do fluxo, axe, larguras 360–1440.
7. `uv run python scripts/capturar.py <rota> --pagina-inteira` e revise as capturas.
8. Atualize `docs/parity/` se a tela existir na referência.
