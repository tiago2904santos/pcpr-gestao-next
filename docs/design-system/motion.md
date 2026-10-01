# Movimento

Movimento só para **explicar mudança de estado** — nunca decorativo.

| Token | Valor | Uso |
|---|---|---|
| `--duracao-rapida` | 120ms | hover, foco, interruptor |
| `--duracao-media` | 200ms | entrada de diálogo, gaveta, toast |
| `--duracao-lenta` | 320ms | reservado (transições de página não são usadas) |
| `--curva-padrao` | cubic-bezier(0.2, 0, 0, 1) | entradas |
| `--curva-saida` | cubic-bezier(0.4, 0, 1, 1) | saídas |

- Diálogo: opacidade + 8px de deslocamento. Gaveta: desliza da borda. Toast: sobe 8px.
- Sem animação de layout (CLS = 0): esqueletos reservam o espaço final.
- `prefers-reduced-motion` desliga tudo (tokens viram 0ms).
- Indicadores de carregamento giram (exceção funcional) e também são desligados.
