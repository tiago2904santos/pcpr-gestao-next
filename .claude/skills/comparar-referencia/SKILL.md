---
name: comparar-referencia
description: Compara uma funcionalidade do sistema novo com o sistema de referência (somente leitura) e registra a paridade.
---
1. Credenciais da referência **só** por ambiente: `REF_USER`, `REF_PASS` (nunca em arquivo versionado).
2. `uv run python scripts/referencia/capturar_referencia.py <rotas>` — navega apenas com GET,
   ignora links de ação (excluir, emitir, gerar…) e salva em `artifacts/referencia/`.
3. Capture a tela equivalente no sistema novo com `scripts/capturar.py`.
4. Compare resultado, cálculo, documento, permissão, estado, erro e comportamento.
5. Classifique cada diferença: melhoria intencional | mudança necessária | comportamento
   legado | regressão | decisão pendente — e registre em `docs/parity/<funcionalidade>.md`.
