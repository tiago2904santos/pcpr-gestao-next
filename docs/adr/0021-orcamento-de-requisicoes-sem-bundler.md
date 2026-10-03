# ADR 0021 — Requisições nas folhas de edição sem empacotador

- **Status:** proposto (decisão do dono do produto)
- **Data:** 2026-10-03

## Contexto
O orçamento de desempenho (`docs/quality/performance-budgets.md`, `tests/e2e/test_desempenho.py`)
limita cada página a 25 requisições. Em 03/10/2026, depois de minificar CSS e JS no
`collectstatic` (`gestao/plataforma/estaticos.py`) e de carregar o editor de documento só
quando ele entra na tela, **todas as métricas de peso e tempo ficaram dentro do orçamento**
(TTFB, FCP, LCP, CLS, INP, KB de HTML/CSS/JS, gzip, SQL). Só a contagem de requisições
continua acima nas folhas de edição: ofício 37, roteiro 27.

A causa é estrutural: o ADR 0002 escolheu módulos ES servidos direto, sem empacotador. Cada
componente é um arquivo (combobox, seletores de data/hora, transporte, autosave, texto
pronto…), e a folha do ofício é a tela que usa quase todos. A folha do documento (iframe,
ADR 0018) soma o próprio HTML, CSS e fontes.

Os arquivos têm hash no nome e cache de longo prazo (WhiteNoise): a partir da segunda
visita, essas requisições não saem da máquina. Sob HTTP/2, as da primeira visita vão em
paralelo numa só conexão.

## Opções
| Opção | Efeito | Custo |
|---|---|---|
| A. Orçamento próprio para folhas de edição (40 requisições), mantendo 25 nas demais telas | Reflete a arquitetura escolhida; o teste continua pegando crescimento | Nenhum código; aceita a primeira visita com mais pedidos |
| B. Concatenar no `collectstatic` os módulos sempre carregados (shell, menu, diálogo, toasts, comandos, ação) num arquivo só | −6 requisições em **toda** página | Passo de build novo; contraria em parte o ADR 0002; mapas de origem para depurar |
| C. Empacotador (esbuild) para os módulos das folhas | Menos requisições e árvore podada | Reabre o ADR 0002; ferramenta de build no deploy |

## Recomendação
**A agora** (o ganho real de B/C é pequeno com HTTP/2 + cache imutável, e o peso já está no
orçamento); reavaliar B se as medições em produção (Hostinger, HTTP/2 confirmado) mostrarem
primeira visita lenta.

## Consequências
Enquanto não houver decisão, o teste aplica 40 requisições só às duas folhas de edição
(com o comentário apontando para este ADR); qualquer crescimento além disso falha.
