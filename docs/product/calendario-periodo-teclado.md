# Calendário de período — continuidade do foco

Regra documentada antes da correção em 07/10/2026. O componente compartilhado
`seletor-data.js` define que Enter/Espaço escolhem a data e que o primeiro dia
mantém o calendário aberto para escolher a segunda ponta. Recriar as células
após essa primeira escolha deve preservar o foco no dia ativo, para as setas e
Enter seguintes continuarem operando a grade.

Evidência: `var/cadastro-filtros-diagnostico.log`, cenário real da Lista de Ofícios
em 360 px, falha em `td[tabindex=0]` focado após o primeiro Enter. O método
`escolher` renderiza a grade e remove a célula focada sem focar sua substituta.
O teste anterior também falhava em fechar o período nos dois tamanhos.

Correção deve usar o método `focarInicial` existente após renderizar a primeira
ponta. Preserva eventos dos valores/HTMX, escolha invertida, clique, navegação de
mês e Escape. Validar filtro por teclado e consumidores compartilhados.

Validação posterior: seis cenários da gaveta passaram na rodada conjunta de
121s (outros dois casos de cadastro falharam no axe inicial, não no calendário).
O teste mantém asserção de foco na célula ativa após primeiro Enter, duas datas
diferentes, URL atualizada, Escape/retorno de foco e uma carga por módulo.
Log: `var/cadastro-filtros-foco-salvamento.log`. Regressões transversais pendentes.

## Termo de autorização — calendário como gatilho (14/10/2026)

Pedido do usuário: as próprias folhas de início e fim abrem a edição do período,
sem botão de ícone separado à direita. O calendário é um botão nativo, acessível por
clique, Enter e Espaço, com retorno de foco após Escape ou escolha do intervalo.
As folhas ganham um canto dobrado ao hover/foco; movimento reduzido remove a animação.
O card distribui calendário, data por extenso/origem e duração pela largura disponível.
Período de um dia e ausência de datas continuam legíveis, sem informação inventada.
Datas ocultas, seletor `pc-data`, origem do período e autosave são preservados.
O gatilho fica fora das regiões substituídas pelo autosave; folhas e texto têm regiões
vivas próprias, para atualizar o conteúdo sem perder o botão nem o foco.
Refinamento solicitado na mesma data: reduzir altura, folhas e espaçamentos para
uma apresentação compacta, mantendo o card na largura disponível e a dobra de canto.
Segundo refinamento: remover o texto visível “Escolher período” e reduzir mais as
folhas e a altura do card. O nome acessível do botão e o clique nas folhas permanecem.
Terceiro refinamento: substituir a seta entre início/fim pelo marcador arredondado
original de duração (“X dias”), ligado por um fio discreto. Retirar a duração
duplicada à direita. Este número continua sendo a duração inclusiva do período,
sem mudar o cálculo para antecedência em relação à data atual.
Correção de direção pelo usuário: compactar somente a vertical; a distribuição
horizontal pode ser ampla, com maior distância entre folhas e data por extenso.
Refinamento seguinte: aproximar as folhas, reservando entre elas apenas o espaço
necessário para o marcador de dias. Manter a altura baixa e a largura total do card.

Indicador solicitado com referência visual enviada: restaurar na direita o número
em destaque, legenda e pequenas marcas douradas, agora para antecedência até o
início do evento. Calcular início menos hoje no fuso local da aplicação (dias de
calendário, sem contar hoje). No dia inicial: “0 / começa hoje”; se já começou,
mostrar dias desde o início, sem chamar um valor negativo de antecedência.
Sem início: “— / defina o período”. A duração entre as folhas permanece separada.
Manter o card compacto na vertical e as folhas próximas.
Refinamento: data por extenso deve ficar logo ao lado das folhas, sem coluna vazia
entre eles. Aumentar o destaque do número de antecedência sem aumentar a altura do card.
O marcador entre folhas deve explicitar a duração como “X dias de evento”,
distinguindo-a do indicador de antecedência à direita.

## Propagação aprovada (14/10/2026)

Aplicar a mesma peça aos cadastros de Viagem, OS, Plano de Trabalho, evento adicional
do plano, Solicitação de Evento e Palestra; manter Termos com sua fonte de datas.
Viagem e OS usam “dias de viagem”; os cadastros de evento usam “dias de evento”.
Usar largura total em uma linha própria, após os demais campos de identificação/
agenda, preservando rótulos, horários, âncoras, permissões, POST e autosave.
IDs de campos e erros continuam associados. Uma data representa um dia; início
vazio mantém o estado “defina o período”; datas inválidas não são descartadas.
Ao escolher as datas, atualizar folhas, frase, duração e antecedência imediatamente.
Sem JS, os campos de início/fim continuam disponíveis por fallback de texto.
O UI Lab usa o mesmo template, com estados vazio, um dia, futuro, passado e consulta.
Casos diferentes (filtros, substituições e datas com horário) foram apresentados
ao usuário para definição de escopo, sem substituição automática.
Decisão posterior do usuário: filtros de busca ficam fora deste componente.
Substituição da chefia aguarda decisão após visualizar o formulário atual em 1440 px.

## Substituição da chefia — versão compacta aprovada

Aplicar no diálogo Nova substituição uma variante menor do mesmo calendário.
Início permanece obrigatório; fim vazio significa vigência até ser encerrada,
e não substituição de um só dia. Mostrar “A partir de…” e folha de fim aberto.
No seletor, permitir “Sem data final” mantendo o início escolhido. Preservar
nomes/IDs, valores inválidos, erros e fluxo manual de cadastro; não criar registros
durante a validação visual. Filtros continuam fora da propagação.
Na variante compacta, omitir o indicador de dias de antecedência, conforme
refinamento do usuário; a versão normal continua apresentando esse indicador.
Remover a linha do dia da semana na variante compacta para encurtar as folhas;
o período aberto continua identificado pelo marcador “até encerrar” e pelo símbolo ∞.
Omitir também os rótulos “Início” e “Fim” nas folhas da variante compacta;
manter a descrição textual do período e os rótulos do seletor acessível.
Centralizar verticalmente o marcador “até encerrar” entre as folhas compactas,
sem o deslocamento superior necessário na versão com rótulos.
