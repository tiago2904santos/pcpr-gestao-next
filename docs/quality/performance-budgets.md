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
| Requisições | ≤ 25 (folhas de edição: ≤ 40 provisório, ADR 0021) | por rota, fora o mapa (orçamento próprio). Sem empacotador (ADR 0002) cada componente é um arquivo; as folhas de edição usam quase todos |
| Consultas SQL por página | ≤ 25 | `select_related`/`prefetch_related`; alerta no log acima disso |
| Tempo de banco por página | ≤ 80 ms | Índices em busca e filtros |

Os tamanhos são os de **produção**: CSS e JS saem minificados do `collectstatic`
(`gestao/plataforma/estaticos.py` — CSS por um analisador próprio, JS pelo `rjsmin`, cada
módulo continua um arquivo) e o teste aplica a mesma minificação ao que o servidor de teste
serve. "gzip" é o que trafega (WhiteNoise serve Brotli/Gzip).

### Rodada de 03/10/2026 (depois da minificação e do editor sob demanda)

| Rota | TTFB | FCP | LCP | CLS | INP | CSS KB (gzip) | JS KB (gzip) | Req. | SQL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `/` | 44 | 120 | 476 | 0 | 40 | 71,8 (16,1) | 70,8 (24,1) | 15 | 9 |
| `/viagens/` | 99 | 244 | 676 | 0 | 64 | 88,3 (19,3) | 73,0 (25,0) | 17 | 15 |
| `/viagens/oficios/` | 92 | 216 | 608 | 0 | 48 | 98,7 (21,3) | 89,7 (31,3) | 22 | 11 |
| lista + janela de resumo | 96 | 288 | 760 | 0 | 96 | 98,7 (21,3) | 89,7 (31,3) | 22 | 16 |
| folha do ofício | 218 | 344 | 836 | 0 | 40 | 108,3 (25,0) | 113,1 (40,5) | 37 | 18 |
| folha do roteiro | 56 | 180 | 672 | 0 | 48 | 94,0 (20,6) | 105,6 (37,5) | 26 | 9 |

Antes desta rodada a folha do ofício estava em CSS 165,9 KB (43,5), JS 195,1 KB (65,4) e 43
requisições.

## Medições
Ver `docs/quality/performance-report.md` (gerado a partir de `artifacts/desempenho-*.json`).
