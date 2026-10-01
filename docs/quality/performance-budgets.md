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
| CSS (bruto) | ≤ 140 KB | 4 arquivos, sem framework; ~17 KB são comentários do Design System (documentação no próprio CSS). Teto de segurança |
| CSS (gzip) | ≤ 30 KB | **O que de fato trafega** (WhiteNoise serve comprimido). Hoje ≈ 25 KB. É o orçamento que segura o crescimento: estourou, corta-se CSS, não se sobe o número |
| JS | ≤ 110 KB | htmx (52 KB) + Web Components (~20 KB) + página |
| Requisições | ≤ 25 | Sprite único de ícones, uma fonte |
| Consultas SQL por página | ≤ 25 | `select_related`/`prefetch_related`; alerta no log acima disso |
| Tempo de banco por página | ≤ 80 ms | Índices em busca e filtros |

Valores sem compressão: em produção o WhiteNoise serve Brotli/Gzip (≈ 25–30% do tamanho).

## Medições
Ver `docs/quality/performance-report.md` (gerado a partir de `artifacts/desempenho-*.json`).
