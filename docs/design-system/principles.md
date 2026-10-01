# Princípios do Design System

> O sistema de referência é **referência**; este Design System é a **evolução**.
> Meta: o usuário abre o sistema e pensa "é o meu sistema — e está muito mais refinado".

## 1. Identidade institucional, uso contido
O DNA que funciona no sistema atual é **grafite + filete dourado + branco/cinzas quentes**.
O grafite ancora a marca (cabeçalho, ação primária); o dourado **assina** (filete do
cabeçalho, item ativo, ação de destaque, números de atenção) — nunca pinta grandes áreas.
Regra prática: **no máximo um botão dourado por tela** (a ação institucional decisiva:
"Emitir", "Entrar").

## 2. Densidade de trabalho, não de vitrine
Usuários operacionais preenchem ofícios o dia todo. Corpo de texto em 14px, controles de
40px, tabelas com linhas de ~48px, cartões com respiro de 20px. Informação primeiro,
decoração por último. Indicadores (KPIs) só onde orientam uma decisão.

## 3. Hierarquia evidente em três níveis
1. **Página**: sobretítulo em caixa alta → título → descrição → ações.
2. **Seção**: cartão com número/ícone e título.
3. **Campo**: rótulo sempre visível, ajuda abaixo, erro ligado ao campo.

## 4. Um padrão por problema
Cada problema de interface tem **um** componente: um botão primário, um selo de status,
uma lista de registros, uma tabela. O sistema de referência chegou a ter `components.css`,
`components-v2.css`, `-v3`, `-v3-1`, `-v3-2` e uma ponte `ds-v32-bridge.css` — essa
sobreposição de gerações é exatamente o que evitamos (ver `docs/product/legacy-lessons.md`).

## 5. O servidor é a fonte da verdade
HTML renderizado no servidor; HTMX troca fragmentos; Web Components só para comportamento
reutilizável (combobox, menu, diálogo, gaveta, paleta de comandos). Todas as páginas
funcionam sem JavaScript no fluxo essencial (progressive enhancement).

## 6. Acessível por construção (WCAG 2.2 AA)
Contraste medido a partir dos tokens (`scripts/contraste.py`), foco visível em tudo,
alvos ≥ 24px, rótulos reais, erros anunciados, teclado completo, movimento reduzido.

## 7. Rápido é bonito
Sem bibliotecas visuais pesadas. CSS e JS sem bundler, cacheáveis, com orçamentos medidos
em CI (`docs/quality/performance-budgets.md`). Uma fonte variável (Inter, 48 KB),
ícones em um único sprite SVG.

## 8. Linguagem do usuário
Português claro e institucional, sem jargão técnico: "Emitir ofício", não "Gerar PDF";
mensagens de erro dizem **o que aconteceu e como resolver** ("A viagem começa em 3 dias e
o prazo mínimo é de 10: preencha a justificativa").

## 9. Somente tema claro (sem modo escuro)
Decisão do dono do produto: o sistema **não tem modo escuro**. A página declara
`color-scheme: light` (CSS e `<meta>`), não existe `prefers-color-scheme: dark` em nenhum
CSS e o navegador/SO em modo escuro não altera nada — inclusive campos nativos, barras de
rolagem e seletores de data continuam claros. Verificado por
`tests/test_design_tokens.py::test_sem_modo_escuro` e
`tests/e2e/test_fluxo_oficio.py::test_sistema_nao_muda_com_sistema_operacional_em_modo_escuro`.

## 10. Tokens como contrato
Nenhum valor visual solto: cor, espaço, raio, sombra e tipografia vêm de
`static/css/tokens.css`. Um teste (`tests/test_design_tokens.py`) reprova CSS com hex,
`rgb()` ou `px` de espaçamento fora dos tokens.
