# ADR 0003 — Design System com tokens como fonte única e UI Lab antes das telas

- **Status:** aceito · **Data:** 2026-10-01

## Contexto
A referência acumulou `components.css`, `-v2`, `-v3`, `-v3-1`, `-v3-2` e uma ponte
`ds-v32-bridge.css`; cores e espaçamentos soltos geram inconsistência.

## Decisão
- `static/css/tokens.css` é a **única** fonte de cor, tipografia, espaço, raio, sombra,
  movimento e camadas. Demais CSS usam `var(--…)`.
- Testes: `tests/test_design_tokens.py` reprova cor literal fora dos tokens, espaçamento em
  px, token inexistente e contraste abaixo do mínimo WCAG.
- Quatro arquivos: `tokens.css`, `base.css`, `layout.css`, `components.css` (+ `ui-lab.css`
  só na vitrine). BEM em português (`bloco__elemento--modificador`).
- Todo componente nasce no **UI Lab** (`/ui-lab/`) com todos os estados e passa por axe e
  capturas em 6 larguras antes de entrar numa tela.

## Alternativas
| Alternativa | Por que não |
|---|---|
| Tailwind | Exige build; dispersa decisões em classes utilitárias nos templates |
| Bootstrap | Visual genérico; sobrescrever para o DNA PCPR custa mais que escrever |
| Tokens em JSON + gerador | Útil com várias plataformas; hoje só há web e PDF (que reusa o CSS) |

## Consequências
Mudar a cor de marca é editar uma linha; o teste de contraste avisa se quebrar a acessibilidade.
