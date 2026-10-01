# ADR 0012 — Visual Overdrive: assinatura visual, motion e componentes reinventados

- **Status:** aceito · **Data:** 2026-10-01

## Contexto
O sistema estava correto, acessível e rápido, mas visualmente parecia "mais um painel
administrativo": bordas cinzas de 1px em tudo, status como pílulas coloridas, login em
cartão genérico, nenhuma linguagem de movimento. O dono do produto pediu um redesign
profundo com identidade própria, mantendo regras de negócio, WCAG 2.2 AA, orçamentos de
desempenho, navegação superior (nunca sidebar permanente) e somente tema claro.

## Decisão
1. **Direção de arte: "papel timbrado digital".** O produto emite documentos oficiais; a
   interface herda o timbre: grafite ancora, o **dourado é linha e selo, nunca tinta**
   (`docs/design-system/visual-language.md`, seção "A assinatura visual").
2. **Cinco gestos de assinatura**, todos em `components.css`/`layout.css` e documentados:
   filete dourado (`--filete`, `filete-crescer`), **placa** com o número do ofício
   (`.placa`), **trilho de processo** (`.processo`), **carimbo** na emissão (`carimbar`) e
   **papel quente** (`--fundo-pagina`).
3. **Profundidade por sombras em camadas e tokens translúcidos** (`--tinta-*`, `--luz-*`,
   `--brilho-dourado-*`, `--sombra-cartao`) em vez de bordas cinzas. Gradientes só tonais,
   dentro de uma família; desfoque só no véu.
4. **Sistema de movimento** com cinco durações, quatro curvas e um vocabulário de nove
   keyframes (`docs/design-system/motion.md`). Saídas no JS esperam `animationend` com
   fallback; `prefers-reduced-motion` zera tudo.
5. **Login em duas peças** (painel grafite com marca + formulário em papel) — a primeira
   tela é a mais forte do produto. Mantém o mesmo formulário, DEMO e testes.
6. **Listas**: o número vira placa (visível também no celular), a equipe mostra 3 nomes e
   `+N`, a atualização HTMX esmaece e mostra a barra dourada (`hx-indicator`).
7. **Detalhe**: placa grande + trilho Rascunho → Emitido / Cancelado sob o título.
8. **Central de módulos**: módulos futuros viram uma faixa discreta, não cartões vazios.

## Consequências
- `tests/test_design_tokens.py` continua a única guarda de valores visuais; as variáveis
  locais de componente (`--botao-sombra`, `--toast-cor`) entram na lista de exceções.
- O invólucro `.lista-resultados` do arquétipo de lista deixou de ter `id="resultados"`
  (o id pertence ao fragmento HTMX); nenhum template de cadastros dependia dele.
- O UI Lab ganhou placa, trilho de processo e os novos estados de selo (`--processo`,
  `--carimbo`); novas peças continuam entrando primeiro lá.
- `PREVIEW_ESTATICOS_AO_VIVO=true` (só PREVIEW) serve estáticos sem manifest para iterar
  CSS sem `collectstatic`; nunca em produção.
- Nada muda em regras de negócio, autorização, CSP (sem estilos/scripts inline) ou
  navegação (`tests/test_navegacao_superior.py` e o e2e correspondente seguem iguais).
