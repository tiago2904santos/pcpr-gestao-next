# Campos de duração nos trechos estreitos

## OBSERVAR / ENTENDER — 07/10/2026

Regra: `docs/product/tempos-de-rota.md` e ADR 0016. O usuário autorizou a regra
da referência; o caso sintético 300 km/180 min da API gera viagem 04:00 e
adicional 00:45. O agente principal informou dois testes de navegador verdes
em 25,51 s e disponibilizou `artifacts/rota-legado/rota-360-detalhe.png`.

Revisão direta dessa imagem: os dois controles de duração dividem a linha do
card estreito. O último dígito de 04:00 e 00:45 fica cortado, e os rótulos têm
reticências. O campo de data também corta o ano; esse achado é distinto e fica
fora desta alteração, limitada aos campos de duração.

O CSS confirma a causa: `.itin__tempos` tem duas colunas de largura livre, mas
cada `.itin__passo` reserva dois botões sem encolhimento de 1,75 rem, suas
margens e o padding do input. O espaço que sobra para o valor não comporta
todos os caracteres no card visto em 360 px. Não é falha da regra de cálculo.
Os botões existentes têm 28 px em uma raiz de 16 px; esta correção preserva
esses alvos e a altura do controle, sem diminuir fontes ou esconder comandos.

## PROJETAR

Usar o contêiner nomeado `itin` já existente: até 20 rem, cada campo de duração
ocupa a linha inteira. Com essa largura, o input ganha o espaço consumido pela
outra metade e continua ao lado dos botões de menos/mais. A ordem DOM continua
saída → viagem → adicional → chegada. Data/hora de saída e demais campos não
recebem nova regra. Acima desse limite, a grade e o desktop ficam como antes.

## IMPLEMENTAR

`static/css/itinerario.css` recebeu uma única regra de layout:
`@container itin (max-width: 20rem)` aplica `grid-column: 1 / -1` a
`.itin__duracao`. Os seletores, templates, entradas, botões, valores e scripts
permanecem os existentes. O limite é do contêiner, não da janela, para também
proteger um card estreito quando ele aparecer em outra folha.

## TESTAR / COMPARAR

Checks locais sem navegador ou banco:

- `tinycss2.parse_stylesheet`, incluindo tokens de blocos aninhados: nenhum
  erro sintático; processo encerrou com código 0.
- `git diff --check`: código 0.
- Diff revisado: apenas oito linhas adicionadas ao CSS; a regra depende
  exclusivamente da largura do contêiner e alcança somente `.itin__duracao`.

Evidência antes: `artifacts/rota-legado/rota-360-detalhe.png`, revisada diretamente.
Evidência depois ainda pendente: repetir captura do mesmo trecho em 360/390 e
1440 px, com 04:00 e 00:45, mantendo viewport/fontes/dados para comparação.

## CRITICAR / CORRIGIR

A causa visual é a divisão rígida dos controles de duração em duas colunas,
apesar da largura reservada aos botões. Empilhar somente as durações corrige
essa restrição sem reduzir os alvos. O custo previsto é uma linha adicional
por trecho estreito e mais rolagem; deve ser confirmado nas capturas.

A data de saída já corta o ano na imagem original; a nova regra não muda seu
layout. O rodapé fixo também cobre parte do retorno na captura completa, de
modo que a inspeção final precisa enquadrar esse controle fora do rodapé.
Não há evidência para atribuir os cortes a valores ou recálculo de domínio.

## VALIDAR — pendente pelo agente principal

O agente principal deve executar novamente os testes de navegador da regra de
rota e revisar as capturas, verificando valores completos, edição por teclado,
botões de ±15 minutos e ausência de mudança no desktop. A validação funcional
e visual da nova regra CSS não foi executada nesta tarefa; não se infere
aprovação estética do usuário. Nenhum commit foi criado.

## Validação do principal — 07/10/2026 17:37

`test_rota_legado.py`: **2 passaram em 29,70 s**, log
`var/rota-legado-layout-valores.log` no checkout original. O teste confere
salvamento/reabertura e edição manual; mede largura do texto contra a área útil
dos inputs de duração nas cinco larguras. Todos os valores cabem integralmente.
Capturas duráveis antes/depois em `docs/visual-agents/evidencias/rota-legado/`.
Revisão direta da captura 360 confirma rótulos e valores completos, preservando
comandos de menos/mais e o aspecto do card. O custo é uma linha adicional por
trecho estreito. O ano cortado permanece visível como achado separado.

A primeira repetição após o CSS teve 1 aprovado/1 falha de salvamento HTTP 422,
preservada em `var/rota-legado-layout-final.log`; a causa intermitente não foi
demonstrada. A rodada final passou após tornar explícita a espera pelo POST e
redirecionamento. Não foi usado clique forçado, teto ampliado ou erro ignorado.
