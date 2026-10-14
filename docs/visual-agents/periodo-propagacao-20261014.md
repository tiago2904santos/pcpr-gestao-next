# Propagação do calendário aprovado — 14/10/2026

Ambiente PREVIEW fictício local, `127.0.0.1:8000`. Alterações somente locais,
sem commit/push. Todos os prints gerados/enviados em 1440 × 900, conforme o usuário.

## Observar e entender

Mapeados períodos de início/fim em Viagem, OS, Plano, evento adicional, Termos,
Solicitação de Evento e Palestra. Preservadas as datas únicas de outras etapas.
Baselines reais salvos em `evidencias/periodo-propagacao-20261014/antes/1440/`.
Casos diferentes enviados ao usuário em pergunta estruturada: filtros de Ofícios,
substituições de chefia e saída/chegada com horário. Não receberam alteração.

## Projetar e implementar

Contrato atualizado antes da edição em `docs/product/calendario-periodo-teclado.md`.
ADR 0036 documenta apresentação pura na Plataforma e template/tag compartilhado.
Aplicada a receita `.claude/skills/novo-componente/SKILL.md`: reuso do `pc-data`,
CSS com tokens, UI Lab com estados e documentação no Design System.

Folhas clicáveis com canto dobrado, frase próxima, duração inclusiva entre folhas
e antecedência separada à direita. Natureza viagem em Viagem/OS; evento nos demais.
Layouts de identificação preservam tipo/programa/horário em linha anterior.
Tag mantém os IDs e nomes dos campos originais, valores inválidos, erros e consulta.
Termos mantém período efetivo/herdado e seus IDs vivos. Sem JS há dois campos de
texto de fallback. JS atualiza a apresentação imediatamente sem trocar botão/painel.

## Testar, comparar, criticar, corrigir e validar

Gates finais do `scripts/verificar.sh` executados em PowerShell (Bash indisponível):
Ruff, fronteiras (16 contratos), Bandit, migrações e tipos JS passaram. Mypy apontou
tipagem dos atributos do widget; corrigida e módulo revalidado sem erros. Ruff
apontou espaçamento de import e linhas do script de evidência; corrigidos e
revalidados. 415 testes de períodos/antecedência, tokens e comentários passaram.
Suíte geral e pytest a11y/visual do UI Lab pararam no setup porque a conta local
não pode criar `test_pcpr_gestao`; não são considerados aprovados.

Navegador exercitou sete superfícies: Viagem #1, OS #2, Plano #1, diálogo novo evento
desse plano, Termo #8, nova Solicitação de Evento e nova Palestra. Campos/IDs do
calendário sem duplicação; abertura, Escape/foco, escolha da primeira/segunda data,
marcador de dois dias, atualização imediata e limpeza passaram. ALTURAS: 97,9 px
preenchidos e 79,5 px vazios. Sem overflow horizontal nos cenários exercitados.
POSTs de edição foram interceptados para não alterar o dataset; capturas mostram
GETs reais antes dessas interações. Isso não valida gravação real no banco.

UI Lab mostra futuro, hoje/um dia, iniciado, vazio, consulta desabilitada e erro.
Axe no componente compartilhado retornou zero violações; zero erros JS nessa rodada.
A primeira injeção do Axe como script foi barrada pela CSP; adotado o método por
avaliação já usado em `tests/e2e/conftest.py`, sem alterar a política do aplicativo.
Uma navegação foi interrompida pelo autoreload do PREVIEW; retomadas somente páginas
pendentes. A checagem inicial de IDs globais encontrou duplicações preexistentes na
OS, fora do calendário; a checagem final focou os IDs da peça compartilhada.

## Capturas revisadas e enviadas

Pasta final: `evidencias/periodo-propagacao-20261014/depois/1440/`.

- `viagem.png` — cadastro de Viagem.
- `ordem.png` — cadastro de OS.
- `plano.png` — cadastro de Plano.
- `evento-plano.png` — diálogo de evento adicional.
- `termo.png` — cadastro de Termo com o template compartilhado.
- `eventos.png` — nova Solicitação de Evento.
- `palestras.png` — nova Palestra.
- `ui-lab-periodo.png` e `ui-lab-estados.png` — vitrine e estados.

Revisão visual: peças com largura total, folhas próximas, descrição ao lado,
antecedência destacada, sem aumentar altura. Diálogo preserva programação/horário
e seus campos com horário. Script reproduzível: `scripts/evidencias_periodo.py`.
Paridade/documentação atualizadas; sem aprovação automática de todas as permissões,
estados do legado ou casos pendentes de escopo.

## Prints para decisão

Usuário excluiu explicitamente os filtros da propagação. Os nove prints finais
foram reenviados diretamente na conversa. Aberto “Nova substituição” em Configuração
para captura em 1440 × 900, sem preencher/salvar ou alterar o formulário.
Imagem: `evidencias/periodo-propagacao-20261014/decisao/1440/substituicao-chefia-atual.png`.
Substituições permanecem com os campos originais até a decisão do usuário.

## Substituição aprovada — versão compacta

O usuário autorizou o calendário na substituição da chefia e pediu remover a
antecedência da variante compacta. Aplicados `compacto=True` e `fim_aberto=True`
no diálogo, com folhas menores e sem o indicador de antecedência.
Fim vazio permanece indefinido: “A partir de…” e “até encerrar”, sem tratá-lo
como um dia. O seletor oferece “Sem data final” mantendo o início escolhido.
Nomes/IDs dos campos, erros e POST manual de cadastro permanecem os originais.

Validação final: Ruff/Mypy/tipos JS passaram; 84 testes de períodos/tokens passaram.
No navegador, fim aberto inicial, intervalo de dois dias, remoção do fim mantendo
início, Escape/foco e ausência de overflow passaram; zero erros JS e nenhuma
gravação real. Revisão visual encontrou padding residual, corrigido somente na
variante; altura final 87,2 px. Capturas finais 1440 × 900:
`substituicao/1440/substituicao-compacta-aberta.png` e
`substituicao/1440/substituicao-compacta-com-fim.png` dentro da pasta de evidências.
UI Lab recebeu exemplo compacto/aberto. Sem repetição da suíte geral, commit ou push.

## Refinamento compacto — sem dia da semana e rótulos

Pedidos do usuário: remover dia da semana, depois “Início”/“Fim” das folhas.
Ocultadas essas linhas somente na variante compacta, preservando descrição,
campos e acessibilidade do seletor. Altura observada: 87,2 → 70,3 → 60,7 px.
Checagem pontual no navegador: linhas invisíveis, fim vazio preservado,
calendário abre e Escape devolve foco. Nenhuma gravação de dados.
Captura final revisada em 1440 × 900:
`evidencias/periodo-propagacao-20261014/substituicao/1440/substituicao-sem-rotulos.png`.
Sem repetição da suíte geral, commit ou push.

## Marcador centralizado na variante compacta

Pedido do usuário: alinhar “até encerrar” verticalmente às folhas. A margem
superior herdada deslocava o marcador; removida apenas na variante compacta.
Checagem visual/geométrica em 1440 px: centro do marcador em 471,977 px e
centro das duas folhas em 471,984 px (diferença inferior a 0,01 px).
Captura revisada: `evidencias/periodo-propagacao-20261014/substituicao/1440/substituicao-marcador-centralizado.png`.
Sem gravar registros, repetir suíte geral, commit ou push.

## Integração autorizada no main

Usuário aprovou publicar todas as alterações. Integrado `origin/main` (6628a61),
preservando os ajustes de OS/resumo e a divisão recente do CSS. Resolvido conflito
por movimentação: calendário compartilhado e layout da agenda ficam no Design
System; removido o calendário antigo de `operacional.css` para não sobrescrever
o componente aprovado. Nenhum force-push.

Conferência pós-integração: sete páginas com abertura, seleção, atualização,
limpeza e Escape/foco aprovados; UI Lab com Axe sem violações e nenhum erro JS.
Nova substituição conferida em 1440 e 360 px; sete cadastros capturados em 360 px
e verificados sem overflow interno do calendário. Prints públicos só em 1440 px,
conforme pedido do usuário. Capturas internas em `evidencias/periodo-propagacao-20261014/integracao/`.

Para superar a limitação de CREATEDB do banco habitual, criado PostgreSQL 16
temporário, descartável, isolado em `127.0.0.1:55433`, sem volumes persistentes.
Nenhuma alteração de permissões ou de dados no banco habitual/PREVIEW.
