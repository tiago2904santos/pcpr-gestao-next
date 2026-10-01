---
name: novo-componente
description: Receita para adicionar um componente ao Design System (CSS com tokens, Web Component se houver comportamento, UI Lab com todos os estados).
---
1. Confirme que nenhum componente existente resolve (`docs/design-system/components.md`).
2. CSS em `static/css/components.css` usando apenas tokens (o teste de tokens reprova literais).
3. Comportamento? `static/js/componentes/<nome>.js` com `// @ts-check`, padrão WAI-ARIA,
   aprimoramento progressivo; registre em `static/js/app.js` e no `modulepreload` de
   `templates/base_documento.html`.
4. Adicione ao UI Lab (`gestao/ui_lab/templates/ui_lab/indice.html`) em todos os estados.
5. Rode `npm run typecheck`, `uv run pytest tests/test_design_tokens.py` e
   `uv run pytest -m "a11y or visual" -k ui_lab`.
6. Documente em `docs/design-system/components.md`.
