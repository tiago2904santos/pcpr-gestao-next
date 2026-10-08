# ADR 0026 — Adiar controladores de filtros; separação CSS rejeitada

- **Status:** aceito somente para controladores JS; separação CSS rejeitada no gate
- **Data:** 2026-10-07

## Contexto

Fechamento de 07/10/2026: a captura do Resumo comprovou perda do estilo da
divulgação eProtocolo ao carregar somente seletores.css. A concatenação igual
não validava esse consumidor. CSS original e todos os links foram restaurados;
seletores.css/componente canônico não entram. Mantém-se apenas o opt-in dos
filtros fechados, sem preload local e sem importar controladores antecipadamente.
Decisões e evidências abaixo referentes ao CSS descrevem o candidato rejeitado.

Medição fresca após adiar miniaturas: lista de ofícios CSS 149,5 KB / 28 pedidos;
lista com resumo CSS 149,5 KB / 29 pedidos. Tetos: 140 KB e 25 pedidos.
Os filtros de períodos e ordem ficam na gaveta fechada, mas o arquétipo pré-carrega
o seletor e app.js importa controles apenas pela presença dos elementos.
`formulario.css` também traz progresso, equipe, transporte e atividades ausentes
na lista. Fontes e proposta: `docs/quality/viagens-desempenho-proposta.md`.

## Decisão originalmente proposta (separação CSS rejeitada no gate)

Extraia a seção canônica de data/hora/lista de `formulario.css` para `seletores.css`,
sem cópia das regras. `componentes/estilos_formulario.html` emite dois links static,
seletores antes de formulário, preservando a ordem anterior das regras. Todos os
consumidores do pacote formulário usam esse componente. Só a lista de ofícios e o resumo sobre ela
carregam diretamente o pacote de seletores, além de listas/core.

O arquétipo oferece bloco específico para o preload do seletor; o padrão das
outras listas permanece igual. Ofícios sobrescreve esse bloco sem preload.

Raízes marcadas `[data-controladores-adiados]` permitem ao app adiar imports de
controles indisponíveis. Um ancestral `details` fechado bloqueia seus controles,
exceto o próprio summary; a raiz details continua disponível ao controlador da
gaveta. Abrir/focar a raiz, repor HTML por HTMX ou emitir
`pcpr:controladores-repostos` reavalia os componentes. Fora da marca, a carga
continua pela presença. A marca é reutilizável nos diálogos secundários, cuja
implementação pertence ao ADR 0027; este ADR não cria nem altera esses diálogos.
Manter foco quando o registro assíncrono substitui um select nativo focado.

## Alternativas consideradas

- Gerar uma cópia parcial do CSS na build: introduz regra de extração no pipeline
  para este pacote. A separação explícita é menor e mantém fonte única.
- Retirar CSS/seletores de todas as listas: algumas usam controles à vista; o
  comportamento muda somente mediante opt-in.
- Adiar cliques por replay: requer coordenação de comandos e duplicação segura.
  Esta decisão adia controles antes da interação, sem replay de ações.
- Elevar budgets ou excluir fontes/pedidos: não resolve a carga desnecessária e
  contradiz o orçamento aprovado.
- `@import` relativo foi implementado primeiro, mas reprovou no navegador: a
  análise CSSOM do axe solicita o href relativo em relação à página e cria
  estilos inline incompatíveis com a CSP. Os links explícitos evitam esse ramo,
  mantendo `static`, prefixos e hashes sem relaxar CSP ou filtrar console.

## Consequências

Lista troca um pacote por outro, sem acrescentar pedido de CSS. Formulários que
carregam `formulario.css` ganham **um pedido real de CSS** pelo segundo link. Os bytes
das regras não duplicam; o overhead gzip e a ordem de carregamento devem ser
medidos. A folha estava em 36 pedidos antes deste candidato e continua exigindo
outras economias para 32. Não se declara aprovação desse custo.

`test_css_por_pagina.py` deve verificar consumidores/ordem dos links e reconhecer os componentes
de seletores, incluindo painéis gerados por JavaScript. A proteção contra CSS
ausente permanece ativa. O pacote novo deve corresponder à seção extraída sem
perder regras de calendário, relógio ou data-hora.

Obrigatórios antes de entrega: CSS/minificação, TypeScript/lint, navegador de
filtros em 360/1440, teclado/foco, períodos, HTMX, resumo, outras listas com padrão
inalterado, capturas e nova medição completa. Análise estática não substitui esses
checks e não autoriza aumentar ou reinterpretar budgets.

## Evidência da correção

Rodada anterior real: **8 falhas / 3 passaram / 156,13 s** no log
`var/cadastro-filtros-adiados-browser.log` do checkout principal. Quatro casos
frios importaram seletores apesar da gaveta fechada; dois testes de corrida
interceptaram esse import antes da abertura. A geometria usada sozinha não
cumpriu o contrato observado, razão para a guarda explícita de details fechado.
Dois casos de cadastro apontaram axe/CSP/404 e um deles também target-size sob
o cabeçalho; esse último é investigação separada do coordenador.

Correção autorizada após a rodada: guarda de details e componente de estilos em
todos os consumidores necessários. Evidências e pendências em
`docs/quality/qa-seletores-gaveta.md`; sem aprovação inferida de navegador ou custo.
