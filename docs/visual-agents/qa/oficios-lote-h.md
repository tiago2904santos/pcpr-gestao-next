# Lote H — auditoria de retomada, 07/10/2026

## Fonte e ambiente

- Base verificada: `8d1d77efb1e5785553fd74b9906bddc6369207c9`, branch
  `viagens/reconstrucao`. `origin/main` e `origin/viagens/reconstrucao` apontavam para
  o mesmo commit após fetch. A transferência relata implementação posterior, mas
  ela não está disponível nesta fonte. Não considerar o lote aprovado.
- Checkout limpo; nenhum lock; um worktree. Main preservada. Sem push ou merge.
- Primeiro teste de serviços bloqueado por falta de CREATEDB do usuário local.
  Docker Desktop indisponível. Laboratório independente inicializado com PostgreSQL
  18.3, somente `127.0.0.1:55432`, usuário/banco `pcpr_lab`; testes usam
  `test_pcpr_lab`. Não foi alterado o PostgreSQL da aplicação em 5432.

## OBSERVAR / ENTENDER

- H-01: `FormularioOficio` remove a opção vazia do motorista externo. Um details
  fechado continua enviando os campos; o primeiro valor `servidor` chega ao serviço,
  que desmarca o motorista da equipe. Fonte: paridade G1 e código atual.
- H-02: o assinante grava FALHOU dentro do savepoint da outbox e relança a exceção;
  rollback desfaz o status. Não há rota, serviço ou botão de nova tentativa.
- H-03: a folha diz detalhe opcional, mas prontidão exige descrição. A seleção de
  `transporte_meio` já alimenta o documento. Fonte: paridade G3.
- H-04: emissão não atualiza a data. D13 é decisão de orquestrador, sem confirmação
  humana encontrada; preservar a regra enquanto se verifica a decisão institucional.
- Recuperação: nenhum comando correspondente no código disponível.

## PROJETAR

Corrigir primeiro a perda de seleção e o estado de falha com regressões executáveis.
A normalização deve respeitar o modo escolhido; formulário com motorista externo
inativo deve enviar valor vazio, inclusive sem JavaScript. Campos fechados devem
estar desabilitados no navegador. Nova tentativa deve reutilizar documento e mensagem,
autorizar pelo ofício e manter snapshot, número e versão. A falha precisa ser registrada
após rollback do processamento, preservando a política de backoff da outbox.

Resultados, críticas, correções, capturas e pendências serão acrescentados aqui.

## IMPLEMENTAR / TESTAR / COMPARAR / CRITICAR

- Baseline real no Chromium: `test_operador_cria_preenche_e_emite_um_oficio` falhou
  na seleção do motorista após Enter (45,61 s). Quatro regressões HTTP/worker também
  falharam: salvamento explícito, autosave, estado após rollback e outro meio.
  Logs locais: `var/lote-h-baseline.log`, `var/lote-h-regressoes-antes.log`.
- Após primeira correção: 9 testes passaram (72,40 s), incluindo emissão no Chromium
  e suíte de outbox. Tipos Python, 16 fronteiras e lint passaram.
- Nova tentativa reutiliza PK, snapshot, número, versão e mensagem. Arquivo servido
  e SHA foram conferidos com bytes sintéticos. Perfis de consulta e outra unidade
  recebem 403/404. Falha controlada foi injetada no worker real.
- Data: **usuário confirmou D13 neste chat em 07/10**. Domínio puro: 3 passaram.
  Revisão, GET sem escrita e snapshot: teste passou após corrigir propagação do
  contexto pelo `_dialogo_resumo.html`. Migração 0049 conserva documentos emitidos
  e datas existentes distintas do dia de criação. Não foi aplicada em banco remoto.
- Revisão independente de código encontrou e corrigiu: retry sem change_oficio;
  autosave de data inválida mudando modo para manual; documento citando motorista
  de viatura com outro transporte. Acrescentadas regressões correspondentes.
- Recuperação: comando simula por padrão; restaura seleção somente com prova ligada
  à requisição de auditoria; sem prova, pede escolha manual. Rodada combinada:
  **36 passed / 2 failed** (891,72 s, com disputa de recursos da suíte completa).
  As duas falhas eram fixtures de estados protegidos sem data de emissão ou motivo
  de cancelamento; corrigidas, reexecução focada pendente. Não reduziram asserções.
- Capturas reais ANTES: árvore extraída de `git archive 8d1d77e`, separada em
  AppData/Local/pcpr-codex-lab/baseline; banco test_pcpr_lab_baseline. DEPOIS usa
  o checkout ativo e banco test_pcpr_lab. Cinco larguras: 360/390/768/1024/1440.
  Inspeção independente encontrou compressão da data em 768: checkbox movido para
  linha própria. Capturas precisam ser refeitas com relógio fixo e animações desativadas.
- Indicador de salvamento voltou a ser visível. Conflito de autosave agora mostra
  a orientação real do servidor para recarregar, em vez da mensagem genérica.

## Ambiente e incidente de mídia

O primeiro `semear_demo --sem-documentos --se-vazio` foi executado no banco recém-criado
pcpr_lab_demo, mas o comando existente limpa `var/media/documentos` e `assinados`:
o MEDIA_ROOT padrão era compartilhado com DEV. Não houve inventário prévio desses arquivos;
não é possível afirmar que nenhum arquivo anterior foi removido. O usuário foi informado.
Copiada a mídia restante para AppData/Local/pcpr-codex-lab/media-snapshot; preview passa
a usar wrapper local `var/preview_lote_h.py` com MEDIA_ROOT separado em preview-media.
O banco DEMO próprio foi semeado novamente com essa separação. Nenhum banco remoto tocado.

DEMO atual: 258 ofícios, 174 servidores, 49 viaturas, 25 unidades, 294 documentos.
Worker gera os arquivos somente em preview-media. Não há validação externa de PDF/A.

## Validação ainda em execução

- `scripts/verificar.sh`, 4 workers, bancos exclusivos test_pcpr_lab_verificar_gw*;
  log `var/lote-h-verificar.log`. Uma falha registrada; diagnóstico final pendente.
- `var/lote-h-regressao-final.log`: correções de fixtures, concorrência real do retry,
  falha no callback, fuso, e2e da folha e capturas.
- Preview local porta 8010, wrapper com mídia isolada; worker próprio.
- Falta: resultado completo, capturas finais/comparações, axe/teclado dos estados,
  medição com condições registradas, paridade e checkpoint Git. Lote NÃO aprovado.

## Checkpoint implementado — 07/10, 16:16

Código preservado em commits locais: `057b154` (domínio da data), `608b903` (callback
de falha), `45d20fd` (recuperação), `44cf5fe` (isolamento do teste de settings),
`44b3186` (fluxos H e redução de consultas). HEAD `b0829d6` também contém a base
pura RS-01, sem tela. Main continua `8d1d77e`; nenhum push/merge.

- Primeira verificação completa: **1873 passaram / 6 falharam**, 3082,04 s.
  Não é verde. Duas fixtures de recuperação já foram corrigidas e passaram na
  rodada final; expectativa antiga de revisão bloqueada foi atualizada para
  provar motivo visível, botão desativado e ofício ainda rascunho sem documento.
- A falha de settings vinha do `.env` de DEV recolocando POSTGRES_DB no subprocesso
  depois da limpeza do ambiente. O teste agora ignora somente a presença de `.env`
  durante importação, sem modificar o arquivo. Defaults continuam verificados.
  Rodada correspondente: 24 passaram, somente os dois budgets SQL ainda falharam.
- Budgets falharam com 33/34 consultas, acima do teto **32** existente na integração
  (métrica diferente do teto HTTP). SQL detalhado mostrou consultas duplicadas dos
  substitutos e do cargo padrão. Lista de substituições agora é carregada uma vez
  com servidor/cargo; catálogo de cargos serve também para achar o padrão.
  **31 testes passaram em 45,21 s**, incluindo os quatro budgets folha/revisão,
  cadastro/edição de servidor, padrão, assinantes e budgets dos cadastros.
- Rodada do navegador anterior: 31 passaram / 2 falharam em 1066,66 s. Uma falha
  era expectativa desatualizada de botão que a tela só mostra quando pronta.
  Teste verifica agora o atalho da pendência e emissão bloqueada na revisão.
  A falha do seletor de módulo não se reproduziu no preview real nem isoladamente;
  **não foi apagada do registro**, causa intermitente ainda não identificada.
  Nova jornada completa no checkpoint está em execução para confirmar o conjunto.
- Teste novo no Chromium: falha → retry por Enter → worker real → polling até link
  pronto → download do PDF e SHA → Escape. Passou; **axe sem violações** no estado
  de falha; nenhum documento/mensagem/número/versão duplicados. Rodada: 3 passaram
  em 149,30 s (incluiu os dois testes antigos corrigido/investigado).
- Ruff e mypy (299 arquivos) verdes após ajustes de tipagem. Não equivalem à
  verificação completa final, que ainda precisa ser executada no checkpoint.

### Evidência visual

Pasta `../evidencias/lote-h/`: antes, depois e comparação das folhas e resumo falho
com Documentos à vista em **360/390/768/1024/1440**. São 30 PNGs reais, mesmo cenário
sintético e relógio local fixo em 12:00, animações finitas desativadas. Bancos distintos
reproduzem o mesmo ofício; PKs de laboratório podem diferir.

Revisão independente: checkbox legível e data completa em 768; retry inteiro nas
cinco larguras; nenhuma nova regressão visual encontrada. Diárias truncadas no resumo
768 já existiam antes e ficam para RS. O rodapé fixo aparece na posição da viewport
inicial nas capturas full_page e encobre pontos diferentes após a mudança de altura;
não foi removido para favorecer a comparação. Fluxos/visibilidade foram testados no
navegador. **Aprovação estética do usuário não foi presumida.**

### Medição do DEMO

Dados sintéticos: **258 ofícios / 294 documentos**, mesmo banco isolado e ofício 117.
Test client Django, um aquecimento e cinco amostras por rota, antes (`8d1d77e`) e
depois (implementação de `44b3186`), relógio fixo. JSONs `medicao-antes-final.json` e
`medicao-depois-final.json` registram amostras, SQL, tempo SQL e bytes de HTML.

- Lista: SQL **16 → 16**; HTML **122364 → 122364 bytes**; mediana **99,24 → 105,01 ms**.
- Folha: SQL **31 → 30**; HTML **165844 → 166395 bytes**; mediana **233,03 → 210,86 ms**.
- Revisão: SQL **33 → 31**; HTML **174448 → 175040 bytes**; mediana **200,94 → 221,51 ms**.
- Resumo: SQL **20 → 20**; HTML **15335 → 15366 bytes**; mediana **69,16 → 71,77 ms**.

Consultas incluem sessão/autorização/contexto de auditoria; middleware conta um
recorte menor. Medição de servidor local, sem compressão: não é tempo de navegador,
tráfego HTTP, INP real nem comparação de arquitetura com servidor remoto. Não há
ganho consistente de latência comprovado. Aviso SQL >25 já ocorre no baseline;
otimização completa da folha pertence a FL. Primeira medição sob disputa de recursos
também foi preservada, sem substituir resultado inconveniente.

## Validação do checkpoint — 07/10/2026 16:35

- **30 testes de navegador passaram em 384,93 s (6:24)** no HEAD `b0829d6`:
  `test_fluxo_oficio.py`, `test_lote_h_visual.py` e jornada de cadastro de servidor.
  Log `var/lote-h-browser-checkpoint.log`. A falha anterior do seletor de módulo não
  voltou nessa rodada completa; a causa da falha anterior continua não demonstrada.
- Capturas DEPOIS e 30 evidências duráveis foram renovadas após essa execução.
  Revisão direta da comparação 360 confirma botão de nova tentativa inteiro e
  motorista preservado, sem inferir aprovação estética do usuário.
- Axe da folha passou. Três testes de desempenho falharam em 62,30 s:
  lista/resumo CSS 149,5 KiB (teto 140), 28 requisições (25); folha HTML 146,8 KiB
  (120), CSS 161,8 (140), JS 159,3 (130), CSS gzip 35,7 (30), JS gzip 56,1 (45),
  50 requisições (32), SQL 26 (25), mediana de banco 82,9 ms (80).
  Log `var/lote-h-perf-axe.log`. Esses números ainda exigem diagnóstico da coleta.
- O callback de respostas chama `body()` durante o evento e permanece ativo nas
  duas navegações adicionais de amostragem, ocasionando `ProtocolError`. Os totais
  são calculados antes dessas navegações: **não há prova de que todos os excessos
  sejam erro do coletor**. Correção delimitada da coleta e discriminação dos
  recursos em andamento; nenhum teto foi aumentado.
- Segunda execução integral de `scripts/verificar.sh` iniciada às 16:33, dois
  workers, banco `pcpr_lab_verificar`, produto estável em `b0829d6`. Etapas até
  tipos JavaScript passaram. Resultado da suíte ainda pendente; não declarar verde.

### Crítica do coletor de desempenho — 16:46

As primeiras tentativas de corrigir o coletor também falharam e foram preservadas:
`var/lote-h-perf-coleta-corrigida.log` (handlers `list.append` incompatíveis com
o wrapper do Playwright, antes da navegação) e `var/lote-h-perf-recursos.log`
(corpo da fonte WOFF2 indisponível via CDP, mesmo depois de concluído). Nenhuma
dessas rodadas aprovou o desempenho. Handlers Python foram conferidos com Chromium
real e requisição roteada localmente, sem banco. Relatórios individuais preservam
CSS/JS/HTML obtidos, requisições e erros: não apagar resultados nem aumentar limites.

Fonte não possui orçamento próprio de tamanho; sua requisição e resposta precisam
continuar contadas. A correção em andamento separa tamanhos da rede dos tamanhos de
conteúdo/minificação/gzip, preservando a métrica dos recursos de itinerário. A
validação integral continua sobre produto `b0829d6`, sem integração da nova regra
de rota ainda. D16 foi respondida pelo usuário: reproduzir fórmulas do legado.
