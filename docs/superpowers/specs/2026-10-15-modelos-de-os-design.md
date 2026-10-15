# Modelos de Ordem de Serviço — desenho (15/10/2026)

## Objetivo

Os tipos de OS deixam de ser constantes no código e viram **modelos cadastráveis** pelo gestor
(criar, alterar, desativar, excluir). Cada modelo define as **funções** que o formulário ativa
na equipe (ex.: Operação policial pede motorista e fotógrafo; Caminhão pede condução, técnico
e apoio) e o **texto do documento**, no formato da OS real: `Ref.:`, parágrafo de autoridade,
`DETERMINO` e itens `I - …`, `II - …`, um por dia/etapa. As datas dos itens vêm do vínculo:
período da **viagem** (trechos do ofício) e período do **evento** (Viagem do ofício).

A **OS padrão** (texto livre, parágrafo único) continua no código, intocada.

Fora do escopo: consertar o texto da operação policial (o gestor faz no cadastro); modelos
por unidade; mudar o visual das telas.

## Decisões tomadas com o usuário

- Etapas estruturadas com texto editável e marcadores (não texto livre nem fixo no código).
- No documento: primeiro um item por **função**, depois os itens por **dia**, tudo numerado
  em sequência (I, II, III = funções; IV em diante = etapas).
- A OS ganha **período do evento**, copiado da Viagem do ofício ao ligar, editável.
- **Horário** (`{hora}`, o do briefing da operação policial): campo opcional na OS, visível só
  quando o texto do modelo usa o marcador.
- Quem gere é o gestor; os 4 tipos atuais viram modelos do sistema; modelo em uso desativa em
  vez de excluir; justificativas e finalidade são opcionais no modelo.

## Dados (`gestao/viagens/models.py`)

### `ModeloOS`

| campo | tipo | notas |
|---|---|---|
| `nome` | char 60 | "Caminhão" — único |
| `referencia` | char 120 | "Deslocamento - Caminhão de apoio" (o `Ref.:`) |
| `ida`, `ida_e_antes`, `antes`, `evento`, `depois`, `depois_e_volta`, `volta` | text | textos das etapas; os dois combinados são opcionais |
| `justificativas` | text | opcional; um parágrafo por linha |
| `finalidade` | text | opcional |
| `ativo` | bool | inativo some das opções; OS antigas continuam gerando |
| `ordem` | smallint | ordem nas opções (menor primeiro; empate pelo nome) |
| `padrao_sistema` | bool | vem com o sistema: desativa, não apaga |

Propriedade `usa_hora`: algum texto contém `{hora}`.

### `FuncaoOS`

| campo | tipo | notas |
|---|---|---|
| `modelo` | FK ModeloOS (cascade) | |
| `codigo` | slug 30 | estável; é o que `OrdemServico.funcoes` grava. Único por modelo |
| `nome` | char 40 | "Fotógrafo" |
| `icone` | char 40 | nome de ícone do sprite (lista fechada) |
| `texto` | text | a atribuição: "conduza a Unidade Móvel…"; usa `{servidores}` |
| `ordem` | smallint | |

### `OrdemServico`

- Sai `tipo`. Entra `modelo = FK(ModeloOS, null, PROTECT)`; nulo = padrão.
- Entram `data_evento_inicio`, `data_evento_fim` (datas, nulas) e `hora` (time, nula).
- `funcoes` continua `{"<id do servidor>": "<código>"}`.
- Constraint: `data_evento_fim >= data_evento_inicio` quando ambos existem.

### Migração (uma, com dados)

1. Cria tabelas e campos.
2. Semeia os 4 modelos do sistema (operação policial — sem função —, caminhão, micro-ônibus,
   cerimonial) com os textos atuais reescritos em etapas e funções (ver "Modelos do sistema").
3. Liga cada OS ao modelo do seu `tipo` (`padrao` → nulo) e remove a coluna `tipo`.

## Marcadores

| marcador | onde | sai como |
|---|---|---|
| `{equipe}` | etapas | "do agente de polícia judiciária Fulano e os escrivães A e B" (como hoje) |
| `{servidores}` | só nas funções | nomes de quem tem a função, "A, B e C" |
| `{destino}` | ambos | "o município de A" / "os municípios de A e B" |
| `{data}` | etapas | "no dia 4 de maio de 2026" / "nos dias 5 e 6 de maio de 2026" / "nos dias 5 a 7 de maio de 2026" |
| `{motivo}` | ambos | o motivo no meio da frase (minúscula, sem ponto), como hoje |
| `{hora}` | etapas | "às 05h00min"; vazio se a OS não tem hora |
| `{sede}` | ambos | a sede da configuração ("Curitiba/PR") |

Marcador desconhecido, ou `{servidores}` fora de função, é erro de validação ao salvar o modelo.

## Domínio puro (`gestao/viagens/dominio/ordem_servico.py` e `modelo_os.py`)

Dataclasses `Modelo` (textos + lista de `Funcao(codigo, nome, texto)`) e `Etapa(nome, inicio,
fim)`. `DadosOS` ganha `evento_inicio`, `evento_fim`, `hora`, `sede`.

### `distribuir_etapas(saida, chegada, evento_inicio, evento_fim) -> list[Etapa]`

Com viagem 3–8 e evento 5–6: ida 3 · antes 4 · evento 5–6 · depois 7 · volta 8.

- Sem período do evento: a viagem inteira é evento (ida no 1.º dia, evento do 1.º ao último,
  volta no último).
- Saída na véspera do evento → `ida_e_antes` no dia da saída; chegada no dia seguinte ao
  evento → `depois_e_volta` no dia da chegada. Se o modelo não tiver o texto combinado, saem
  `ida`/`volta` sozinhos (sem o "antes"/"depois").
- Saída no 1.º dia do evento → sem `ida`; chegada no último dia → sem `volta`; ida, evento e
  volta no mesmo dia → só `evento`.
- Evento fora da viagem → erro de validação da OS ("o período do evento precisa caber no
  período da OS"); o domínio recebe sempre dados válidos.

### `itens_da_os(dados, modelo) -> Textos`

`Textos(referencia, itens: list[str], justificativas: list[str], finalidade: str)`.
Itens, nesta ordem: um por função com alguém (texto da função com os marcadores); um por etapa
presente, na ordem ida → antes → evento → depois → volta. A numeração romana ("I - ", "II - ")
é do documento, não do domínio.

### Pendências (`faltam_para_o_modelo`)

Modelo com funções e ninguém com função; modelo usa `{hora}` e a OS não tem hora; modelo e
OS sem período da viagem. Entram na conferência da tela, como `faltam_funcoes` hoje.

## Formulário da OS (`forms.py`, `views_ordens.py`, `ordens/editar.html`)

- "Tipo de necessidade" vira **Modelo**: Padrão + modelos ativos (ordem do cadastro). Ajuda
  gerada do modelo ("Funções: condução, técnico e apoio · pede o horário do briefing").
- **Período do evento**: segundo calendário, visível só com modelo. Ao ligar ofício com Viagem,
  copia `data_inicio/fim` dela (entra em "copiados"). Validação: cabe no período da OS.
- **Horário**: visível só se `modelo.usa_hora`; obrigatório na conferência, não no rascunho.
- **Funções no cartão**: `data-funcoes` passa a ser chaveado pelo id do modelo, com nome, ícone
  e dica (início do texto) de cada `FuncaoOS`. Trocar o modelo mantém funções cujo código
  existe no novo e limpa as outras (`_funcoes_validas` usa as funções do modelo).
- Prévia e editor: os itens viram blocos `data-bloco="item-N"` dentro da região "corpo".
- Padrão: nada muda na tela.

## Cadastro dos modelos (`/viagens/ordens/modelos/`)

Mesma receita da tela de Textos prontos: lista + janela de novo/editar, link no índice de
Cadastros ("Configuração e textos").

- **Lista**: nome, referência, chips das funções, "em uso por N OS", ativo. Ações: editar,
  ativar/desativar, excluir (só sem OS; com OS, o botão vira desativar). Modelos do sistema
  não se excluem.
- **Janela**: nome, referência; os 7 textos com rótulo e exemplo; justificativas; finalidade;
  funções em linhas (nome, ícone de uma lista, texto; o código é slug do nome, editável até
  uma OS usá-lo). Legenda dos marcadores fixa na janela.
- **Ver exemplo**: monta a folha com uma OS fictícia (viagem 3–8, evento 5–6, três pessoas com
  funções) a partir dos campos como estão (POST sem gravar) e abre a folha.
- **Serviço** `modelos_os.py`: `salvar`, `ativar`, `excluir` (transação + histórico);
  `policies.pode_gerir_modelos_os` (= `pode_gerir_textos_prontos` + perms de `ModeloOS`).

## Documento (`viagens/documentos/ordem_servico.html`)

Com modelo: `Ref.: {referencia}` · autoridade · `DETERMINO` · `<ol>` com `I - …` (romanos) ·
justificativas e finalidade só se existirem. Sem modelo: o que existe hoje. PDF e DOCX saem do
mesmo HTML.

## Modelos do sistema (semeados)

Textos de hoje reescritos. Exemplo, caminhão:

- referência: "Deslocamento - Caminhão de apoio"
- funções: condução (`truck`), técnico (`wrench`), apoio (`hand-helping`), com os textos das
  competências atuais ("Que {servidores} conduza a Unidade Móvel (caminhão)…").
- ida: "O deslocamento {equipe} para {destino} {data}, para apoio logístico com caminhão em
  {motivo}."
- ida_e_antes: "O deslocamento {equipe} para {destino} {data}, com a descarga, montagem e
  conferência técnica da Unidade Móvel no mesmo dia, para apoio logístico com caminhão em
  {motivo}."
- antes: "Que a equipe realize {data} o traslado, descarga, montagem, conferência técnica e
  adequação dos materiais e equipamentos no local do evento."
- evento: "Que a equipe permaneça em {destino} {data} para a operação da Unidade Móvel durante
  {motivo}."
- depois: "Que a equipe realize {data} a desmontagem, conferência, acondicionamento e
  carregamento dos materiais."
- depois_e_volta: "Que a equipe realize {data} a desmontagem e o carregamento dos materiais e
  efetue o retorno à sede de lotação em {sede}."
- volta: "Que a equipe efetue o retorno à sede de lotação em {sede} {data}."
- justificativas e finalidade: as de hoje.

Micro-ônibus e cerimonial seguem o mesmo padrão com seus textos; operação policial sai como a
OS real (ida, evento com "acompanhe o briefing … {hora}" + permanência, volta), sem função.

## Demonstração e testes

- `demonstracao.py`: uma OS de cada modelo do sistema, com viagem e evento, no PREVIEW.
- Domínio: tabela de distribuição (3–8/5–6; 4–7/5–6 com e sem texto combinado; 17/18/19; tudo
  num dia; sem evento); marcadores; `{hora}` vazio.
- Documento: uma OS por modelo do sistema com texto fixado; a padrão com os testes atuais.
- Formulário/serviço: copiar evento do ofício; evento fora do período; hora só com `{hora}`;
  troca de modelo preservando funções válidas; autosave.
- Cadastro: criar/editar/desativar/excluir; marcador inválido; exclusão bloqueada com OS;
  exemplo sem gravar; permissões.
- Migração: OS de cada tipo aponta para o modelo certo; `padrao` fica nulo.
- E2E: cadastro da OS com modelo (modelo, evento, função, conferência) e cadastro de modelos;
  axe nas telas tocadas; 360–1440 sem rolagem horizontal.
