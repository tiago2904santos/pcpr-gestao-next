# Tabelas e listas

## Quando usar cada uma
| Padrão | Use quando | Exemplo |
|---|---|---|
| **Lista de registros** (`.registro`) | Itens heterogêneos, muitos metadados, leitura vertical | Lista de Ofícios |
| **Tabela** (`.tabela`) | Comparar colunas, ordenar, totais, dados numéricos | Cadastros, cálculo de diárias, relatórios |

## Regras de tabela
- Cabeçalho em micro-rótulo caixa alta, fundo `--cor-superficie-sutil`, *sticky*.
- Números (`.num`) à direita com `tabular-nums`; datas no formato `dd/mm/aaaa`.
- Coluna principal com link (`.tabela__principal`) e linha secundária (`.tabela__secundario`).
- Ações por linha: botão ⋮ (`<pc-menu>`) na última coluna; nunca mais de 2 botões visíveis.
- Ordenação por link no cabeçalho com `aria-sort` no `th`.
- `caption` (visível ou `.sr-only`) sempre.
- **Celular (<768px)**: `.tabela--responsiva` transforma linhas em cartões, com rótulo de cada
  célula vindo de `data-rotulo` — sem rolagem horizontal.
- Totais em `tfoot`.

## Densidade
Linha ≈ 48px (padding 12px), compacta ≈ 36px (`.tabela--compacta`) para tabelas de
cálculo dentro de cartões.

## Estados
Vazio (primeiro uso, com ação), sem resultados (com "Limpar filtros"), carregando
(`.esqueleto`), erro (alerta no lugar da tabela).
