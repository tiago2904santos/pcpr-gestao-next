# Barra de ferramentas do editor documental

Regra documentada antes da correção em 07/10/2026. O contrato de teclado já consta
em `tests/e2e/test_editor.py` e no comentário de `prepararBarra` em
`static/js/componentes/editor-documento.js`: um ponto de tabulação na barra e
setas entre seus controles. Isso também precisa valer depois de o seletor gerar
seu botão e o servidor inserir pendências. O menu aberto mantém seu próprio
teclado; itens de menus e seletores fechados não entram nas setas da barra.

Home/End levam ao primeiro/último controle visível habilitado. Esquerda/direita
seguem a ordem visível com retorno à extremidade. Texto/PDF conserva a seleção
do modo; apenas focar por seta não dispara a ação. Links de ações participam
da mesma tabulação. Inserções não devem mover o foco de quem está fora da barra.

Reprodução real: `var/editor-teclado-final.log`, no checkout original, terminou
com **1 falha em 31,53 s**: após Home e ArrowRight, a ordem visível foi respeitada,
mas três botões tinham tabindex=0. Os controles do seletor são inseridos depois
da configuração inicial. A correção ainda precisa ser testada no navegador;
o registro da reprodução não é uma aprovação visual ou resultado verde.

Correção: observar inserções/visibilidade na barra, manter um controle tabulável
e incluir links de ações; setas usam só controles visíveis habilitados. Menus e
listboxes preservam seu próprio teclado. O observer é desconectado ao remover
o editor. Nenhuma alteração de desenho ou geração documental.

Validação pelo principal: **1 teste de navegador passou em 32,25 s**, log
`var/editor-teclado-correcao.log` no checkout original. Confirma PDF conjunto,
retorno ao texto, Home/End, retorno à primeira extremidade, Texto/PDF por setas,
um botão tabulável após a inserção de controles e axe sem violações sérias/críticas.
`tsc -p jsconfig.json` passou. Não substitui a verificação geral do repositório.
