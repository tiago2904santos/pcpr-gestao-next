# Viagens — refinamento profundo, 15/10/2026

Pedido explícito de recomposição de Lista, Folha e lote. Documentos antecipados
após Dados, em cinco grupos; vínculos recolhidos e filtráveis entre os candidatos
atuais, sem consulta remota ou mudança do limite de 40 livres/tipo. Conferência
mostra as nove etapas reais e mantém divergências distintas de prontidão.
Lote explicita período, roteiro e rascunhos, mantendo equipe/viatura compartilhadas.
CSS exclusivo `viagens.css`; filtro reaproveita `conjuntos.js`, com Enter impedindo
envio acidental do formulário (também válido em Planos).

Diferenças intencionais de composição em relação ao assistente legado; regras,
calendário, título pelos tipos, vínculos diretos/indiretos, autosave/versão,
conhecidos, datas, permissões, cancelamento em cascata, assinados e documentos
oficiais preservados. Busca por protocolo/filtros combináveis/paginação 25 e
histórico específico de vínculos continuam lacunas preexistentes: não se alega
que o refinamento as implemente. Evidências/resultado técnico no QA de 15/10;
homologação visual do usuário permanece separada.

Validação técnica: 24 cenários de navegador aprovados e 3 retestes finais do filtro;
411 testes de apresentação/tokens/templates aprovados; 14 capturas principais
360/1440 com HTTP 200 e overflow/JS/axe/POST zero. Suíte geral: 2.595 aprovados,
expectativa literal de um estado vazio atualizada e retestada; `verificar.sh`
incremental verde. Cadeia exata de execuções no QA, sem alegar segunda suíte integral.

## Calendário de período, 14/10/2026

Contrato: `docs/product/propagacao-identidade.md`, `gestao/viagens/viagem.py` e
`views_viagem.py`. O usuário aprovou o calendário compacto de Termos e sua propagação.
Na edição, o tipo permanece antes do calendário, que usa largura total. Conservados
âncora `periodo`, ID `viagem-periodo`, nomes/IDs de início/fim, versão e autosave.
Duração em dias de viagem e antecedência até início são indicadores de apresentação.
Não altera datas dos documentos, coerência, permissões ou geração em lote.
Consulta/cancelada com metadados e itinerários com horários não foram redesenhados.
Evidência/limites: `../visual-agents/periodo-propagacao-20261014.md`.

## Folha da viagem recomposta (15/10/2026, pedido do usuário)

- **Identificação**, um embaixo do outro e cada um na linha toda: tipo, **motivo igual ao do
  ofício e da OS** (bloco "Motivo" com o texto pronto e a caixa de texto), período e destinos.
  O campo **Descrição/objetivo saiu** da tela e da consulta (a coluna no banco fica, com o
  que já estava gravado; a gravação da tela não a mexe).
- **Documentos da viagem** como a **trilha da preparação** (escolhida pelo usuário entre três
  propostas; `viagem_trilha.py`): os cinco tipos lado a lado, ligados por um fio verde no
  trecho já percorrido; cada documento é um cartão com a folhinha na cor da situação
  (verde emitido/gerado, âmbar rascunho, vermelho cancelado), o número, a situação e o
  período; "Novo …" em cada passo. No celular os passos ficam um embaixo do outro.
- **Visualizador** (`_visualizador.html`, `visualizador.js`): clicar no cartão abre um modal.
  Documento **pronto** (ofício emitido; OS e plano gerados e sem pendência; termo com período
  e destino) mostra a folha — o documento como sai — ao lado do resumo com as ações (no
  celular, Documento × Resumo); com mais de uma página (ofício e justificativa, os termos de
  cada servidor), a escolha da página. O que não está pronto, tem pendência ou é roteiro abre
  só o resumo. Setas (e ← →) passam entre os documentos do mesmo tipo; Esc devolve o foco ao
  cartão; Ctrl/⌘-clique ou sem JavaScript, o cartão abre a folha de edição.
- **Vincular documentos existentes**: cada lista mostra no máximo três linhas e rola; o
  texto de cada opção fica centrado com a caixa de marcar.
- **Conferência**: resumo com barra das etapas concluídas; etapas com pendência em cartões
  com os atalhos; concluídas numa fileira de marcas; divergências com o que está no
  documento e o que a viagem diz, lado a lado.

