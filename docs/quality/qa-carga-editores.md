# Carga do índice e das miniaturas dos editores

## OBSERVAR / ENTENDER

Fonte: base `36d4acd`, `docs/product/documents.md`, ADR 0018, ADR 0021 e
`docs/quality/performance-budgets.md`. A tarefa de 07/10/2026 determina que visitar
a folha e usar o menu não carregue as miniaturas; aproximar a seção Documentos
carrega índice, miniaturas e editor. Os orçamentos permanecem os existentes.

O relatório `recursos-desempenho-viagens_oficios_733_editar.json` do checkout
principal identifica as folhas das miniaturas e seus recursos na navegação inicial.
`app.js` importava `[data-editores]` na lista imediata. `editores.js` iniciava o
bloco ao importar e colocava endereço nas duas miniaturas. O editor principal já
usava IntersectionObserver com margem de 400 px.

Também foi encontrado um problema de reposição: a lista de visibilidade marcava o
seletor carregado antes de seu alvo entrar na tela. Um alvo substituído por HTMX
antes disso poderia deixar o módulo esperando uma caixa desconectada.

## PROJETAR

- Reutilizar a carga por visibilidade, inclusive margem de 400 px e fallback sem
  IntersectionObserver, para o índice e as miniaturas.
- Inicializar cada bloco uma só vez; o cache de módulos não pode impedir a ligação
  de um bloco novo. Reobservar alvos atuais após reposição HTMX.
- Não inicializar uma caixa que foi removida durante o import assíncrono.
- Preservar troca de página, modo PDF, índice, atualização de miniaturas e gravação.

## IMPLEMENTAR

`static/js/app.js` move `[data-editores]` para a observação com margem de 400 px.
Os alvos atuais são reobservados após HTMX e reposição pelo autosave. Uma importação
pendente confere se a caixa continua conectada antes de inicializá-la. Cada caixa
tem sua própria marca de inicialização, mesmo quando o módulo já está em cache.

`static/js/componentes/editores.js` exporta `iniciarBloco`; importar o módulo não
carrega miniaturas automaticamente. Repetir a chamada para o mesmo conteúdo é
idempotente. Trocar os membros da caixa religa o controlador e desliga handlers e
observadores anteriores. A recarga por gravação só alcança caixas já inicializadas.
Um `beforeSwap` com `shouldSwap: false` não desliga o bloco. Sem IntersectionObserver,
a inicialização imediata preserva os comandos de navegação e o editor.

## TESTAR / COMPARAR

Executados em 07/10/2026, no checkout isolado
`C:/Users/tiago/.codex/worktrees/viagens-tempo-legado/pcpr-gestao-next`:

- `tsc -p jsconfig.json`: saída 0, sem diagnósticos (runtime Node do checkout principal).
- `ruff check tests/e2e/test_editor_carga.py`: todos os checks passaram.
- `python -m py_compile tests/e2e/test_editor_carga.py`: saída 0.
- `git diff --check`: saída 0.

O novo `tests/e2e/test_editor_carga.py` prepara quatro casos (o primeiro em duas
larguras, total de cinco execuções): navegação e menu sem miniaturas em 360/1440,
rolagem com índice e gravação do texto, reposição externa/interna e módulo em cache,
troca durante importação pendente, e fallback sem IntersectionObserver. O caso de
reposição também verifica uma nova caixa fora da tela com o módulo já carregado e
um pedido HTMX sem troca. As reposições são fragmentos equivalentes disparados
com eventos HTMX; o teste não alega validar uma resposta HTTP HTMX real.

Comandos preparados para execução sequencial pelo agente principal, usando o
ambiente DEV fictício e as configurações de teste do projeto:

```powershell
& 'C:/Users/tiago/OneDrive/Documentos/pcpr-gestao-next/.venv/Scripts/python.exe' -m pytest tests/e2e/test_editor_carga.py tests/e2e/test_editor.py -q
& 'C:/Users/tiago/OneDrive/Documentos/pcpr-gestao-next/.venv/Scripts/python.exe' -m pytest tests/e2e/test_desempenho.py -q
```

A primeira suíte gera `artifacts/qa-carga-editores/editor-360.png` e
`editor-1440.png` para revisão do índice e do editor depois da rolagem. A segunda
deve comparar recursos da navegação inicial com a coleta anterior, mantendo todos
os orçamentos existentes. Ainda não há nova medição ou capturas nesta entrega.

## CRITICAR / CORRIGIR

A análise encontrou e corrigiu dois riscos além da carga imediata: perder a
observação ao substituir um alvo antes de ele aparecer, e duplicar handlers ao
repor o conteúdo dentro da mesma raiz com o módulo já importado. AbortController
e a identidade dos membros evitam a ligação duplicada; a observação usa as caixas
atuais. Trocas canceladas ou sem conteúdo novo não desmontam o índice.

Limite existente: depois de registrar `pc-editor-documento`, o connectedCallback
desse componente inicia seus próprios iframes quando uma nova instância é inserida.
Esta correção preserva esse comportamento e adia as miniaturas do índice; não
altera `editor-documento.js`. A primeira visita à folha, antes do registro, continua
adiando também a importação do editor. Não houve mudança de CSS, endpoints ou budgets.

## VALIDAR — pendente de execução sequencial

Não foi executado navegador nem banco nesta tarefa, conforme coordenação com o
agente principal. Faltam as suítes acima, revisão das duas capturas e o verificador
geral para concluir a validação funcional, visual e de desempenho. Não há aprovação
estética do usuário inferida destes checks estáticos. Nenhum commit foi criado.

## Rodada real e correções — 07/10/2026

O agente principal executou as duas suítes no worktree: **5 passaram e 4 falharam
em 158,75 s**, log no checkout original `var/editor-carga-navegador-final.log`.
Falhas registradas antes da correção:

- Em 360 px, clicar no índice da barra fixa do ofício falhou por botão invisível.
  `editor.css` esconde a barra dos editores inativos (`.editor:not(.editor--ativo)`);
  o teste deve operar a barra ativa realmente visível, sem `force=True`.
- O teste de corrida deixou uma Route fora do callback e chamou `continue_` após
  `unroute`: **Route is already handled**, seguido de coroutine pendente. A próxima
  versão fará a reposição dentro do callback enquanto a resposta do import está
  interceptada, obtendo a fonte com `route.fetch` e liberando com `fulfill` em
  `finally`, sem transferir ou retomar a Route posteriormente.
- O fallback encontrou **IntersectionObserver is not defined**. Além do editor,
  `progresso.js` e `mapa-rota.js` usam esse construtor sem guarda. Serão guardados:
  os links de progresso continuam nativos e o mapa carrega imediatamente sem IO.
- A suíte anterior de editor esperou um iframe individual de PDF visível. A
  implementação do bloco usa PDF conjunto. Essa falha permanece para comparação
  pelo agente principal; não será alterada nesta correção delimitada.

As asserções de console vazio continuam obrigatórias. A rodada anterior não é
declarada verde; nova execução e captura 360 px ainda são necessárias.

Correções implementadas e verificadas estaticamente nesta rodada:

- O teste busca `.editor--ativo [data-alternar-indice]:visible` e exige visibilidade
  antes de clicar. Não muda a política responsiva ou a barra do produto.
- O callback intercepta apenas uma importação (`times=1`), chama `route.fetch`
  com timeout de 15 s, repõe a caixa e faz `fulfill(response=...)` antes de retornar.
  Um `finally` libera a resposta (ou aborta caso fetch falhe) e descarta o APIResponse.
  Não há rota guardada para `continue_`, `unroute` ou espera com threading.Event.
  O teste exige uma caixa removida e nenhuma miniatura iniciada dentro dela.
- API conferida no Playwright 1.56.0 instalado: `RouteHandler._handle_internal`
  executa callbacks sync em `RouteGreenlet`; `Page._on_route` atualiza os padrões
  após o handler; `Route.fulfill(response=...)` reaproveita status/headers e a fonte
  obtida pelo fetch; `APIResponse.dispose()` é suportado após a liberação.
- `progresso.js` evita criar observadores quando IO está ausente; seus hrefs
  continuam funcionando nativamente. `mapa-rota.js` marca o mapa visível nesse caso,
  desenha a rota/sede disponível e mantém o ResizeObserver de enquadramento.
  O teste de fallback também exige um painel Leaflet criado.
- `tsc -p jsconfig.json`, Ruff, py_compile e diff --check passaram novamente.

Não houve nova execução de navegador ou banco por este agente. O resultado
**5 passed / 4 failed** acima continua sendo a última rodada funcional conhecida.

## Execução pelo principal após correções — 07/10/2026

Na rodada conjunta `var/eprotocolo-editor-navegador.log` (checkout original),
**os cinco casos de `test_editor_carga.py` passaram**. Rodada total: 11 passaram,
3 falharam em 241,94 s. As falhas foram duas comparações CRLF/LF do Clipboard e
um teste antigo do teclado; não ocorreram nos cinco casos de carga adiada.
Casos anteriores de escrita, campo vivo e restauração também passaram.

Capturas editor-360/1440 copiadas para
`docs/visual-agents/evidencias/eprotocolo-editor/` e revisadas pelo principal.
Índice e barra disponíveis; documento ainda recortado em tela estreita, questão
de acabamento existente. Correção posterior da barra em
`docs/product/editor-documental-acessibilidade.md`, teste navegador passou em
32,25 s e `tsc -p jsconfig.json` verde. O fallback IO testado inclui o mapa real
Leaflet, com console limpo. Trocas de caixas são eventos HTMX sintéticos; não
se afirmam como requisições HTTP reais (essas existem nos testes de RS-01).

Medição de desempenho posterior em andamento. Nenhum teto foi alterado; este
resultado funcional não prova budgets ou verificador geral completos.
