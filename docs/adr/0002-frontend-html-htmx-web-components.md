# ADR 0002 — Front-end: HTML no servidor + HTMX + Web Components, sem bundler

- **Status:** aceito · **Data:** 2026-10-01

## Contexto
Telas são formulários e listas densas. A referência mistura JS ad-hoc por página
(`static/js/*.js`, dezenas de arquivos) com HTML do servidor.

## Decisão
- Páginas renderizadas pelo Django; **HTMX 2** para atualizações parciais (recalcular
  diárias, adicionar viajante, filtrar listas). Fragmentos via *template partials* do Django 6.
- **Web Components** nativos para comportamento reutilizável: `pc-shell`, `pc-menu`,
  `pc-combobox`, `pc-comandos`, `pc-toasts`, `pc-abas`. Sem Shadow DOM (o CSS do Design
  System se aplica), com aprimoramento progressivo.
- **Sem bundler**: módulos ES servidos direto, `modulepreload`, cache longo via
  `CompressedManifestStaticFilesStorage`. Tipos verificados com `tsc --checkJs` (JSDoc):
  TypeScript só como verificador, não como etapa de build — "TS apenas onde traz benefício".
- htmx vendorizado em `static/vendor/` (sem CDN; CSP `script-src 'self' 'nonce-…'`).

## Alternativas
| Alternativa | Por que não |
|---|---|
| React/Vue SPA | Peso (≥ 100 KB), duplicação de regras, SEO/acessibilidade a reconstruir |
| Alpine.js | Atributos com expressões exigem `unsafe-eval` ou build CSP; Web Components bastam |
| Lit | Útil, mas +6 KB e Shadow DOM por padrão; componentes atuais são pequenos |

## Exceções previstas (documentar em ADR próprio quando usadas)
- **Mapa de rota** (Leaflet, ~40 KB) carregado só na seção de roteiro.
- **Editor rico de documento**: se o "Editar documento completo" da referência for
  necessário, avaliar um editor isolado (ex.: ProseMirror) só nessa tela.

## Consequências
JS total do shell ≈ 70 KB (htmx 52 KB + componentes ~18 KB) antes de compressão.
Telas funcionam sem JS no caminho essencial.
