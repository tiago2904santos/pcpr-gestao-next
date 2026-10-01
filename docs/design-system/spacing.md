# Espaçamento, raios e sombras

Grade de **4px**. Tokens `--esp-*` em `rem` (respeitam o zoom do navegador).

| Token | px | Uso típico |
|---|---|---|
| `--esp-1` | 4 | Ícone ↔ texto em selos; gaps mínimos |
| `--esp-2` | 8 | Ícone ↔ rótulo em botões; entre botões |
| `--esp-3` | 12 | Padding de itens de menu/listas; gap de filtros |
| `--esp-4` | 16 | Gap da grade de campos; padding horizontal no celular |
| `--esp-5` | 20 | Padding de cartões |
| `--esp-6` | 24 | Espaço entre seções; padding da página (tablet) |
| `--esp-8` | 32 | Padding horizontal da página (desktop) |
| `--esp-12` | 48 | Estado vazio; final da página |

## Ritmo vertical
- Entre cartões/seções: `--esp-6` (`.pilha-lg`).
- Dentro de um cartão: `--esp-4` (`.pilha`).
- Rótulo ↔ campo ↔ ajuda: `--esp-1`.

## Raios
`--raio-xs` 4 (kbd, selos quadrados) · `--raio-sm` 6 (opções) · `--raio-md` 8 (controles) ·
`--raio-lg` 12 (cartões, diálogos) · `--raio-pilula` (selos, avatares).

## Sombras
`--sombra-1` cartões em repouso · `--sombra-2` hover/destaque · `--sombra-3` sobreposições
(menus, diálogos, toasts, barra de ações fixa). Profundidade vem sobretudo das bordas.

## Dimensões de controle
40px padrão (`--altura-controle`), 32px compacto, 44px em toque/celular. Todos os alvos
interativos ≥ 24×24px (WCAG 2.5.8).
