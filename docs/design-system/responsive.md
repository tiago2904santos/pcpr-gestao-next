# Responsividade

## Pontos de quebra (mobile-first nos componentes, desktop-first no shell)
| Nome | Largura | Mudanças principais |
|---|---|---|
| xs | < 480 | Sigla menor; sem selo de ambiente; diálogos com botões empilhados |
| sm | 480–767 | Grade de campos em 1 coluna; tabela vira cartões; filtros empilhados; campos 44px e 16px |
| md | 768–1023 | Lateral vira gaveta; detalhe em 1 coluna; índice de formulário oculto |
| lg | 1024–1279 | Lateral fixa; padding 24px |
| xl | ≥ 1280 | Conteúdo até 1280px; padding 32px |

## Larguras testadas em CI (Fase 12)
**360, 390, 768, 1024, 1280, 1440** — para cada página do piloto:
sem rolagem horizontal (`scrollWidth ≤ innerWidth`), sem sobreposição de elementos
interativos, nenhum texto cortado em botões/selos, captura salva em `artifacts/`.

## Regras
- Nada de largura fixa em px para conteúdo; `minmax(0, 1fr)` em grades para permitir encolher.
- Textos longos: `overflow-wrap: anywhere` em nomes e destinos; `.texto-truncado` só com
  o texto completo acessível (title/linha secundária).
- Alvos de toque 44px em <768px.
- Nenhum elemento flutuante sobre o conteúdo (lição do botão "+ Novo ofício" da referência).
