# Movimento

Movimento só para **explicar mudança de estado** — nunca decorativo. A diferença entre
"sistema administrativo" e "produto" costuma estar aqui: entradas que orientam, saídas que
confirmam, uma única ênfase reservada ao momento institucional (emitir).

## Tokens (`static/css/tokens.css`)
| Token | Valor | Uso |
|---|---|---|
| `--duracao-instantanea` | 90ms | pressionar botão (`--escala-pressao`), foco |
| `--duracao-rapida` | 140ms | hover, troca de cor, menus, saída de toast/diálogo |
| `--duracao-media` | 220ms | entrada de diálogo, toast, abas, gaveta |
| `--duracao-lenta` | 360ms | cascata de página, troca de lista, linha do tempo |
| `--duracao-enfase` | 640ms | carimbo (emissão), confirmações |
| `--curva-padrao` | cubic-bezier(0.2, 0, 0, 1) | entradas (desacelera) |
| `--curva-saida` | cubic-bezier(0.4, 0, 1, 1) | saídas (acelera) |
| `--curva-suave` | cubic-bezier(0.65, 0, 0.35, 1) | troca de estado simétrica (pulso, barra) |
| `--curva-expressiva` | cubic-bezier(0.34, 1.35, 0.64, 1) | ênfase com leve ultrapassagem (diálogo, carimbo) |
| `--escala-pressao` | 0.985 | botão pressionado (`:active`) |

## Vocabulário (`static/css/base.css`)
| Keyframe | O que faz | Onde |
|---|---|---|
| `aparecer` | sobe 6px e aparece | conteúdo da página em cascata (`.conteudo__interno > *`, 0/40/80/120ms), `.htmx-added/.htmx-settling` |
| `brotar` | cresce a partir da origem | menus suspensos, paleta de comandos |
| `recolher` | encolhe e some | saída de diálogo (`.dialogo--saindo`) |
| `filete-crescer` | o filete dourado cresce da esquerda | item ativo da navegação, aba ativa, foco de seção |
| `carimbar` | entra grande, girado, assenta | selo "Emitido" recém-emitido (`.selo--carimbo`), botão concluído |
| `pulsar` | opacidade 1 → .35 → 1 | "gerando documento" (`.selo--processo`), status sujo da barra |
| `girar` | rotação contínua | `.girando` (indicadores de carregamento) |
| `esqueleto` | brilho horizontal | `.esqueleto` |
| `deslizar-indeterminado` | barra que corre | lista atualizando por HTMX (`.lista-resultados.htmx-request::before`) |
| `toast-entrar/sair/tempo` | sobe e aparece / desce e some / barra encolhe em 6s | `<pc-toasts>` |

## Regras
- **Entrada ≠ saída**: entradas usam `--curva-padrao`, saídas `--curva-saida` e são ~35% mais curtas.
- **Uma ênfase por fluxo**: `carimbar` só na emissão; nada mais "salta".
- **Movimento explica**: a lista esmaece e mostra a barra dourada enquanto o HTMX troca o
  fragmento (`hx-indicator=".lista-resultados"`), em vez de "piscar".
- **Sem animação de layout** (CLS = 0): esqueletos reservam o espaço final; `transform` e
  `opacity` apenas; nunca `height`/`top`.
- **Saídas no JS esperam `animationend`** com fallback por `setTimeout` (toasts 400ms,
  diálogos 300ms), para que `prefers-reduced-motion` ou animação ausente nunca travem o
  fechamento.
- **Pausa com foco**: o toast pausa a barra e o cronômetro em `mouseenter` **e** `focusin`.
- `prefers-reduced-motion: reduce` zera todos os tokens de duração, `--escala-pressao` vira 1
  e um bloco global força `animation-duration: 0.01ms` — inclusive `pulsar` e `girar`.
