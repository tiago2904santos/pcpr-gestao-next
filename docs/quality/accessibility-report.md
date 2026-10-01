# Relatório de acessibilidade — piloto (WCAG 2.2 AA)

## Automático
`tests/e2e/test_acessibilidade.py` — axe-core 4.13 com as regras WCAG 2.0/2.1/2.2 A e AA,
em 10 páginas autenticadas, no login e no UI Lab em 360 e 1440 px.
**Resultado: 13/13 sem violações *serious*/*critical*.**

Problemas que o axe encontrou e que foram corrigidos durante o piloto:
| Achado | Critério | Correção |
|---|---|---|
| Texto do rodapé a 4,3:1 sobre o fundo do login | 1.4.3 | Rodapé passa a usar `--cor-texto-secundario` (6,2:1) |
| Atalho "Ctrl K" claro sobre fundo claro do `kbd` | 1.4.3 | Fundo transparente e `--cor-texto-inverso-sutil` (7,6:1) |
| Links do resumo de erros com alvo < 24 px | 2.5.8 | `min-height: 1.5rem` nos links |
| `aria-label` em `div` sem papel | 4.1.2 | `role="status"` no esqueleto de carregamento |

## Tokens
`tests/test_design_tokens.py` calcula o contraste de 26 pares de cor diretamente de
`tokens.css` (ver `docs/design-system/colors.md`). Três tokens foram escurecidos antes das
telas existirem (texto terciário, borda de campo, indicador dourado).

## Teclado e leitores de tela (E2E)
`tests/e2e/test_fluxo_oficio.py`:
- "Pular para o conteúdo" é o primeiro foco e leva ao `main`;
- menu do usuário: ↓ abre e foca o 1º item, Esc fecha e devolve o foco ao botão;
- paleta de comandos: Ctrl+K abre, setas navegam, Esc fecha;
- gaveta de navegação (390 px): abre pelo botão, Esc fecha e devolve o foco, `aria-expanded` atualizado;
- erro de validação: resumo com link que foca o campo; campo com `aria-invalid` e `aria-describedby`;
- confirmação de emissão: `<dialog>` modal nativo (foco preso e retorno do foco).

## Manual (checklist do piloto)
| Item | Situação |
|---|---|
| Um `h1` por página, hierarquia de títulos | ✅ verificado nos templates de arquétipo |
| Landmarks: `header`, `nav[aria-label]`, `main`, `footer` | ✅ |
| Rótulo visível em todos os campos; obrigatório sinalizado com texto | ✅ ("necessário para emitir" / "opcional") |
| Status nunca só por cor (selos com texto) | ✅ |
| Combobox WAI-ARIA 1.2 (`aria-activedescendant`, anúncio de resultados) | ✅ |
| Tabelas com `caption`, `scope`; no celular viram cartões com rótulo por célula | ✅ |
| Foco não fica escondido atrás da barra fixa (2.4.11) | ✅ `scroll-padding-bottom` |
| `prefers-reduced-motion` | ✅ tokens de duração vão a 0 |
| Leitor de tela real (NVDA/VoiceOver) | ⏳ pendente — fazer com usuário na validação do piloto |
| Zoom 200%/400% | ⏳ coberto indiretamente pelo teste de 360 px (≈ 400% de 1440); validar manualmente |

## Documento PDF
PDF/A-**2a** exige estrutura marcada: o teste verifica `StructTreeRoot`, fontes embutidas e
metadados XMP (`pdfaid:part=2`, `conformance=A`). O `alt` do brasão vai para a árvore de tags.
