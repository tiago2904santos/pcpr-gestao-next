# Cadastro rápido sob demanda — checkpoint 07/10/2026

## Observar / entender / projetar

ADR 0027 documenta a decisão antes do código: Folha inicialmente sem os cinco
formulários completos; GET autorizado retorna os mesmos formulários canônicos.
Demais telas mantêm seus contratos. Sem novo POST, sem validação simplificada.

## Implementar / testar

Domínio/permissão dos cadastros permanece existente. HTTP inicial: 4 passaram,
1 falha por expectativa incorreta de input (widget vazio usa data-nome), corrigida.
Caso GET reexecutado na primeira rodada conjunta: passou. Suíte HTTP final em curso.

Navegador conjunto inicial: 8 falharam/3 passaram em156,13s, log original
`var/cadastro-filtros-adiados-browser.log`. Falhas CSS via import e filtro fechado
tratadas no QA seletores. Cadastros reais e associação já funcionaram antes do axe.
Rodada seguinte: 3 falharam/6 passaram/2 erros em108,19s,
`var/cadastro-filtros-correcoes.log`: campo ao fundo sob cabeçalho no axe modal,
foco removido após primeiro Enter no calendário, deadlock de limpeza de fixture
com pedido da folha em andamento. Não foram aprovadas por repetir sem investigação.

Diagnóstico isolado: 2 falharam em42,71s, `var/cadastro-filtros-diagnostico.log`.
Árvore Chromium demonstrou que o campo ao fundo era ignored por activeModalDialog.
O foco da célula após Enter falhou explicitamente; correção e regra própria em
`product/calendario-periodo-teclado.md`.

Nova rodada: 2 falharam/8 passaram em121s,
`var/cadastro-filtros-foco-salvamento.log`. Todos os seis filtros e dois casos de
falha de carga/fechamento passaram; auditoria inicial de contraste antes de
assentar recursos falhou. Nenhuma atribuição causal específica de fonte provada.
Auditoria inicial agora espera networkidle e document.fonts.ready, grava relatório
sem retirar regras. Auditoria do modal abrange a superfície operável mantendo
mesmas tags WCAG e exige via CDP que o controle de fundo esteja realmente excluído
da árvore acessível. O helper geral do axe e a CSP continuam intactos.

Rodada dos dois cadastros: **2 passaram em47,63s**,
`var/cadastro-axe-estavel.log`, 360/1440. Criou servidor e viatura pelos endpoints
reais, vinculou equipe/seleção, conservou motivo, reabriu diálogo, verificou todos
os campos, axe e console, enviou Finalizar real e confirmou motivo persistido.
Finalizar espera autosave e termina fora da folha antes da limpeza da fixture.
Caso de falha503 orientou retry; fechar antes de GET retornar preservou foco e
não reabriu. Os arquivos de artefatos de mesma rodada são renovados; os logs
históricos são preservados. JSON antigo sobrescrito não é evidência durável atual.

## Comparar / criticar / validar

Capturas reais após animations.finished e JSON da árvore/axe copiados para
`visual-agents/evidencias/cadastro-adiado/`. Faltam comparação equivalente com
checkpoint anterior, capturas390/768/1024, inspeção completa das imagens, Tab/
ShiftTab/Escape, cadastro sobreposto de Cargo/Unidade/Combustível e validação
inválida/viatura. Revisão cética do QA sustenta escopo modal com limitações.
Nenhuma aprovação estética do usuário ou aprovação geral de acessibilidade.

Ruff dos testes e TypeScript passaram; mypy integral posterior passou em303
arquivos. Código candidato não foi incorporado à branch original. Suíte HTTP,
regressões de componentes, nova medida de desempenho e verificar.sh permanecem
necessários antes da entrega; budgets não foram alterados.

## Reexecução do coordenador no fechamento

Dez casos de cadastro/filtros passaram juntos em101,77s, com Tab/ShiftTab e
Cargo/Unidade/Combustível sobrepostos por teclado nas duas larguras, Escape e
origem, cadastro servidor/viatura, 503/retry e GET tardio. Após retirar candidato
CSS, os dez passaram novamente na rodada35pass/1falha; a falha era outro teste
(cópia Resumo/CSP), não cadastro. JSON axe/Chromium AX atualizado preservado em
visual-agents/evidencias/gate-final. Escopo de axe segue superfície operável;
não é aprovação geral do sistema. Integral ainda em curso no fechamento-gate.
