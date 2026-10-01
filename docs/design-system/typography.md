# Tipografia

**Família:** Inter (variável, subconjunto latino, 48 KB, OFL) servida localmente em
`static/fonts/`, com `font-display: swap` e *preload*. Pilha de fallback:
`"Segoe UI Variable", "Segoe UI", system-ui…` — no Windows institucional a troca é quase
imperceptível. Números com `tabular-nums` em tabelas, valores e datas.

**Documentos oficiais (PDF):** Liberation Serif (métrica compatível com Times New Roman,
OFL) embutida no PDF/A — o ofício mantém a aparência tradicional do papel timbrado.

## Escala
| Token | Tamanho | Uso |
|---|---|---|
| `--texto-2xs` | 11px | Micro-rótulos em caixa alta (sobretítulo, cabeçalho de tabela, KPI) |
| `--texto-xs` | 12px | Ajuda de campo, metadados, selos |
| `--texto-sm` | 13px | Migalhas, metadados de registro, menus |
| `--texto-md` | 14px | **Corpo padrão**, campos e botões |
| `--texto-lg` | 16px | Título de cartão; campos no celular (evita zoom do iOS) |
| `--texto-xl` | 18px | Título de diálogo |
| `--texto-2xl` | 22px | Título de página no celular, valores de destaque |
| `--texto-3xl` | 28px | Título de página, valor de KPI |
| `--texto-4xl` | 36px | Código de erro |

## Pesos
400 corpo · 500 ênfase leve (links de navegação) · 600 títulos, rótulos, botões · 700 sigla
PCPR, micro-rótulos, números de seção.

## Regras
- **Caixa alta** só em micro-rótulos (com rastreio 0,06em) e no documento oficial.
  Nomes de pessoas aparecem como cadastrados (melhor leitura em listas longas).
- Altura de linha 1,5 no corpo; 1,25 em títulos.
- Títulos com `text-wrap: balance`; parágrafos com `text-wrap: pretty`.
- Nunca usar tamanho < 11px.
