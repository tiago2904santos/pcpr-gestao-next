# Termo de autorização — calendário como botão

14/10/2026, PREVIEW local em `127.0.0.1:8000`, dados fictícios. Alterações locais,
sem commit/push, conforme a preferência atual do usuário. Capturas somente 1440 × 900.

## Observação, entendimento e desenho

O Termo #11 apresentava duas folhas pequenas junto da data por extenso e um botão
separado no extremo direito, deixando a maior parte do card desocupada. O usuário
pediu folhas clicáveis, canto levantando e uma composição que preencha melhor o card.
Contrato documentado antes da edição em `docs/product/calendario-periodo-teclado.md`.

## Implementação e comparação

Calendário ampliado com início/fim e ano, data por extenso central e duração lateral.
O botão nativo engloba as próprias folhas e apresenta “Escolher período”. A animação
levanta a folha levemente e expande uma dobra no canto inferior direito, revelando
o papel inferior. O layout empilha em telas estreitas. Movimento reduzido desativa
as transições específicas; a regra global limita todas as transições a 0,01 ms.

Preservados campos ocultos, seletor compartilhado, origem das datas e autosave.
`periodo-evento-folhas` e `periodo-evento` são regiões vivas separadas, sem conter
o gatilho como descendente, preservando botão/foco durante substituições.

## Validação final e correções

Rodada de gates do `scripts/verificar.sh` reproduzida em PowerShell (Bash indisponível):
Ruff, 16 contratos de imports, Bandit, migrações e tipos JS passaram. Mypy encontrou
uma anotação faltante em `resumo_listas.py`, introduzida no ajuste anterior da equipe
da OS; corrigida para `dict[int, Servidor]` e verificada novamente no módulo, sem erro.
Pytest parou no primeiro setup: a conta local não possui permissão de criar
`test_pcpr_gestao`. A suíte integral não está validada.

Navegador: folhas são o único gatilho; card contém os 67 dias reais do Termo #11;
clique, Enter/Espaço, Escape com retorno de foco, escolha de duas datas e de um só
dia, continuidade de foco após primeira escolha, substituição da região de folhas,
movimento reduzido, ausência de overflow horizontal e zero erros JS passaram.
As escolhas foram exercitadas no GET do novo cadastro sem salvar/criar registro.

A primeira navegação coincidiu com o reinício automático da prévia e recebeu
`ERR_EMPTY_RESPONSE`; a prévia se recuperou. A primeira asserção de movimento
reduzido exigia `0s`, mas a regra global define `0.01ms !important`; a expectativa
foi corrigida para essa regra real, sem mudança do componente.

## Evidência revisada

Pasta: `evidencias/termo-periodo-folhas-20261014/1440/`.

- `antes.png`: baseline do cadastro do Termo #11.
- `cadastro-termo.png`: tela inicial com a nova composição.
- `periodo.png`: componente centralizado, em repouso.
- `periodo-canto-levantado.png`: canto dobrado em hover.
- `periodo-calendario-aberto.png`: edição ancorada nas folhas, após a animação de entrada.

Revisão: espaço ocupado pelo calendário, descrição e duração; nenhuma data truncada
no cenário exercitado. Não comprova autosave real de uma nova data nem todos os
perfis/estados da aplicação, e não representa aprovação visual do usuário.

## Refinamento compacto

Feedback do usuário: componente grande, direção visual aprovada parcialmente.
Reduzidos padding, largura/altura das folhas, tipografia e espaçamentos. Card do
Termo #11 mediu 153,8 px de altura (versão anterior na captura: aproximadamente
204 px), mantendo a largura disponível, distribuição, clique e dobra de canto.
Validação pontual final: sem overflow horizontal, calendário abre e Escape devolve
foco às folhas. Captura revisada: `1440/periodo-compacto.png` na mesma pasta.
Nenhuma suíte repetida, commit ou push nesta iteração somente de dimensões CSS.

## Segunda redução

Pedido: ainda grande, remover “Escolher período”. Texto removido do template;
folhas reduzidas para 3,5 rem, altura/spacing e tipografia compactados. Card agora
mede 97,9 px no mesmo cenário (153,8 px anterior). Mantidos nome acessível, dobra,
clique e Escape com retorno de foco; nenhum overflow horizontal no viewport 1440.
Captura revisada: `1440/periodo-reduzido.png`. Alteração permanece somente local.

## Marcador antigo e distribuição horizontal

A seta entre folhas foi substituída pelo marcador arredondado “67 dias” com fio
discreto; retirado o número duplicado à direita. O número preserva o cálculo de
duração do evento e não representa dias até o início. Durante o ajuste, o usuário
esclareceu que deseja compactar apenas a vertical. A faixa do calendário ganhou
346,8 px na horizontal, com folhas afastadas e descrição maior; altura permanece
97,9 px. Clique, Escape/foco, ausência de overflow e marcador único verificados.
Captura final revisada: `1440/periodo-horizontal-amplo.png`. Apenas arquivos locais.

## Folhas próximas

Removida a expansão do conector: ele agora ocupa apenas 4 rem. Distância entre
folhas medida em 72 px; altura preservada em 97,9 px. Marcador “67 dias”, abertura
do calendário, Escape/foco e ausência de overflow verificados em 1440 × 900.
Captura: `1440/periodo-folhas-proximas.png`. Ajuste somente local.

## Antecedência na lateral

Referência visual enviada pelo usuário: número, legenda e marcas douradas da antiga
duração à direita. Restaurada essa composição, agora com antecedência ao início:
início menos hoje no fuso local. Mantida a duração inclusiva entre as folhas.
Futuro usa “dias de antecedência”; hoje usa “0 / começa hoje”; passado usa “dias
desde o início”; ausência de período usa “— / defina o período”.

Regra pura acrescentada a `dominio/prazos.py`, sem interferir na avaliação de prazo
institucional. Sete casos passaram (ausência de início, futuro, singular, hoje,
passado e virada do ano); Ruff e Mypy dos arquivos alterados sem erros.
Navegador: Termo #8 mostrou 13 dias de antecedência; #11 mostrou 2 dias desde o
início; novo cadastro sem datas mostrou o estado vazio. Altura permaneceu 97,9 px;
clique, Escape/foco, zero erros JS e ausência de overflow passaram. Nenhum registro
alterado. A primeira leitura do campo oculto pressupôs formato brasileiro; ajustada
para o formato ISO real antes de concluir a validação.

Capturas revisadas: `1440/periodo-antecedencia-futuro.png` e
`1440/periodo-antecedencia-iniciado.png`. Todos os ajustes seguem locais.

## Texto próximo e antecedência maior

Retirada a coluna proporcional vazia do calendário: a descrição fica a 21,6 px da
folha final. Número de antecedência ampliado para 32,4 px, legenda também maior.
Altura preservada em 97,9 px no Termo #8; contagens 13/8 corretas, sem overflow,
clique e Escape/foco preservados. Captura: `1440/periodo-texto-proximo-antecedencia-maior.png`.
Alteração somente local; validação visual pontual, sem repetição da suíte.

## Legenda da duração

Marcador entre folhas agora mostra “8 dias de evento”, conforme solicitado.
Largura do grupo acompanha o conteúdo para caber a legenda sem colisão, mantendo
14,4 px até a descrição e altura de 97,9 px. Verificados texto, ausência de overflow,
clique e Escape/foco. Captura: `1440/periodo-dias-de-evento.png`. Somente local.
