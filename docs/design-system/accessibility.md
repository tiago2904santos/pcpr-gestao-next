# Acessibilidade — WCAG 2.2 AA

| Critério | Como atendemos | Verificação |
|---|---|---|
| 1.1.1 Conteúdo não textual | Ícones decorativos `aria-hidden`; ícones de ação com `aria-label` | axe |
| 1.3.1 Info e relações | Landmarks, headings em ordem, `label`/`fieldset`/`legend`, `th scope`, `caption` | axe + revisão |
| 1.4.3 / 1.4.11 Contraste | Pares calculados dos tokens; bordas de campo ≥ 3:1 | `test_design_tokens.py` + axe |
| 1.4.4 / 1.4.10 Redimensionar e refluxo | `rem`; sem rolagem horizontal a 320 CSS px | Testes responsivos (360) |
| 1.4.12 Espaçamento de texto | Sem alturas fixas em contêineres de texto | Revisão |
| 2.1.1 Teclado | Tudo operável por teclado; Web Components seguem padrões WAI-ARIA | E2E de teclado |
| 2.4.1 Pular blocos | Link "Pular para o conteúdo" | E2E |
| 2.4.3 Ordem do foco | DOM na ordem visual; diálogos devolvem o foco | E2E |
| 2.4.7 / 2.4.11 Foco visível e não obscurecido | Anel azul 2px; cabeçalho sticky com `scroll-padding-top` | Visual |
| 2.5.8 Tamanho do alvo | ≥ 24px (40px padrão, 44px no celular) | Revisão |
| 3.2.2 Na entrada | Nada muda de contexto ao focar/alterar sem aviso | Revisão |
| 3.3.1 / 3.3.3 Identificação e sugestão de erro | Resumo de erros + erro no campo com solução | E2E |
| 3.3.7 Entrada redundante | Dados já informados são reaproveitados (ex.: retorno = sede) | Revisão |
| 3.3.8 Autenticação acessível | Login com gerenciador de senhas (autocomplete), sem CAPTCHA | Revisão |
| 4.1.2 Nome, função, valor | `aria-expanded`, `aria-current`, `aria-selected`, `aria-busy` | axe |
| 4.1.3 Mensagens de status | Toasts `role="status"`, contagem de resultados no combobox | E2E |

## Foco (assinatura própria, não o anel do navegador)
Tokens em `tokens.css`: `--foco-cor` (grafite-900), `--foco-contraste` (branco),
`--foco-cor-inverso` (dourado-300) e `--foco-contraste-inverso` (grafite-950) para
superfícies escuras, `--foco-espessura` (2px) e `--foco-offset` (2px).

- Regra global `:focus-visible`: `outline` de 2px na cor de foco, afastado 2px, com um
  halo claro (`box-shadow`) preenchendo o vão — lê-se sobre branco, sobre superfícies
  tingidas e sobre o dourado (1.4.11 e 2.4.11/2.4.13: ≥ 3:1, nunca obscurecido).
- `.cabecalho` e `.acesso__marca` invertem o par (`.superficie-escura`, só no catálogo, idem) (dourado sobre grafite).
- Campos não ganham anel externo: acendem (fundo branco, borda grafite-800 ≥ 3:1, halo
  dourado). Registros de lista desenham o anel na linha inteira (`.registro:has(:focus-visible)`).
- Só `:focus-visible` (teclado); o clique do mouse não deixa anel.
- Verificado por `tests/test_design_tokens.py` (tokens e regra global) e por
  `tests/e2e/test_acessibilidade.py::test_foco_por_teclado_e_a_assinatura_do_sistema_nao_o_anel_do_navegador`
  (estilos computados no Chromium, inclusive sobre o cabeçalho).

## Movimento
`prefers-reduced-motion: reduce` zera durações (tokens) e animações (base.css).

## Testes automáticos
`tests/e2e/test_acessibilidade.py` roda axe-core (WCAG 2.0/2.1/2.2 A e AA) em todas as
páginas do piloto e no UI Lab; qualquer violação *serious/critical* reprova.
