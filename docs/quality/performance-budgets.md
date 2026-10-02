# Orçamentos de desempenho

Medidos por `tests/e2e/test_desempenho.py` (Chromium real, servidor de teste local,
usuário logado, cenário fictício). Estourar qualquer orçamento reprova o CI.

| Métrica | Orçamento | Por quê |
|---|---:|---|
| TTFB | ≤ 300 ms | Página renderizada no servidor com ≤ 25 consultas |
| FCP | ≤ 1,2 s | CSS crítico pequeno, fonte com `swap` |
| LCP | ≤ 1,8 s | "Bom" do Core Web Vitals é 2,5 s; margem para rede institucional |
| CLS | ≤ 0,05 | Esqueletos reservam espaço; imagens com dimensão |
| INP | ≤ 200 ms | Limite "bom" do Core Web Vitals |
| HTML | ≤ 120 KB | Listas paginadas (20 por página) |
| CSS (bruto) | ≤ 140 KB | Sem framework; ~17 KB são comentários do Design System (documentação no próprio CSS). Teto de segurança |
| CSS (gzip) | ≤ 30 KB por rota | **O que de fato trafega** (WhiteNoise serve comprimido). O compartilhado (`tokens` + `base` + `layout` + `components`) fica em ≈ 21,5 KB; cada tela soma só os pacotes que usa (`formulario` 4,9 · `documento` 3,2 · `listas` 3,5 · `painel` 1,6 · `assistente` 1,1 KB), via `{% block estilos %}` — `tests/test_css_por_pagina.py` garante que nenhuma tela usa classe de pacote que não carregou. A edição do ofício, a mais pesada, fica em ≈ 29,4 KB. Estourou: corta-se ou reparte-se CSS, não se sobe o número |
| JS bruto | ≤ 130 KB | htmx (52 KB) + Web Components (~72 KB, inclui calendário, relógio e lista própria — ADR 0014) |
| JS gzip | ≤ 45 KB | o que o navegador baixa de fato (WhiteNoise comprime). Só o que toda tela usa entra sempre (shell, menus, diálogos, toasts, paleta, ações HTMX); combobox, abas, máscara, proteção, registros, progresso e seletores entram por `import()` quando a tela tem o elemento (`static/js/app.js`), pré-carregados no bloco `modulos` da tela que os usa |
| Requisições | ≤ 25 | por rota, fora o mapa (orçamento próprio). Central 16, listas 19, detalhe 18, edição do ofício 25 (no limite: o próximo módulo ou folha de estilo da edição precisa tirar outro) |
| Consultas SQL por página | ≤ 25 | `select_related`/`prefetch_related`; alerta no log acima disso |
| Tempo de banco por página | ≤ 80 ms | Índices em busca e filtros |

Valores sem compressão: em produção o WhiteNoise serve Brotli/Gzip (≈ 25–30% do tamanho).

## Medições
Ver `docs/quality/performance-report.md` (gerado a partir de `artifacts/desempenho-*.json`).
