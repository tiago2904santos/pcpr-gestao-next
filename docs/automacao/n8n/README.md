# Workflows n8n do PCPR (protótipo · n8n 2.43.7)

> **Escopo revisado em 18/10/2026:** [regra vigente do piloto](../../product/automacao-whatsapp-testes.md). Este site é um sistema
> de testes independente, não oficial da polícia e sem operação com policiais. WhatsApp Business
> Cloud API é o canal principal planejado; portal é apoio e e-mail opcional. As classificações e
> restrições policiais de 17/10 abaixo são histórico do cenário institucional, sem bloquear
> automaticamente o piloto. Não houve implementação ou ativação real nesta revisão.

Estes oito arquivos foram **exportados do próprio n8n 2.43.7** ao fim das baterias de teste do
protótipo (`docs/automacao/prototipo/`). Todos têm `"active": false`. Só rodaram contra os
**simuladores locais** (PCPR, canal fictício e Graph API do WhatsApp, dados sintéticos): a API de
automação do PCPR ainda não existe, então nada aqui foi testado contra o sistema real.

- W1, W3, W4 e W5: exportados pela suíte principal (`testar_prototipo.py`, 18/10/2026 03:33,
  rodada com T11, T20 + 18 cenários passando).
- W2, W6, W7 e W8: exportados pela suíte do WhatsApp oficial (`testar_whatsapp.py`, 18/10/2026
  03:44, TW0–TW16 passando). O W2 tem o desvio por canal (WhatsApp → W6). W6–W8 são a
  frente **WA-3 — prontos e DESLIGADOS** (seção própria no fim): não publicar nem cadastrar
  credencial real antes do portão de ativação.
- Revisão do PR #23 (18/10/2026): W2, W4, W6, W7 e W8 mudaram de comportamento em retentativa e
  confirmação — ver "Retentativa e confirmação" abaixo e a
  [seção da revisão no README do protótipo](../prototipo/README.md#revisão-do-pr-23-codex--o-que-mudou).
  Na segunda verificação mudaram de novo W4 (desfecho final por anexo; recusa permanente vira
  exceção, não reentrega), W5 (não guarda execuções), W6 (5xx genérico da Graph API não é
  temporário), W7 e W8 (status órfão antigo vira exceção; corpo estável sob chave estável) —
  [segunda verificação](../prototipo/README.md#segunda-verificação--o-que-mudou). Na terceira,
  só o W4: chave da exceção por classe de recusa e exceção `fila_parada` para falha transitória
  persistente (mensagem com mais de 4 h) —
  [terceira verificação](../prototipo/README.md#terceira-verificação--o-que-mudou).

> Fonte revisável: `docs/automacao/prototipo/construir_workflows.py` gera os JSON; o teste
> importa, publica só no contêiner local, testa, despublica e exporta para cá. Para mudar um
> fluxo, mude o gerador e rode o teste de novo — não edite estes JSON à mão.

## O que cada workflow faz

| Arquivo | ID | Nome | Gatilho | O que faz |
|---|---|---|---|---|
| `w1-entrada-de-eventos.json` | `pcprEntradaEvt01` | PCPR · Entrada de eventos | Webhook `POST /webhook/pcpr-eventos` (corpo bruto) | Verifica `X-PCPR-Assinatura` (HMAC-SHA256 sobre `t + "." + corpo_bruto`, segredo numa credencial *Crypto*), frescor ±5 min, ambiente e `X-PCPR-Evento-Id`; **401** se algo falhar; **202** logo em seguida; deduplica por `id` do evento entre execuções; roteia por `tipo`; `comunicacao.agendada` já devida (ou `imediato`) → chama o W2 |
| `w2-entregar-comunicacao.json` | `pcprEntregaCom01` | PCPR · Entregar comunicação | Chamado por outro workflow (W1/W3) | `GET /estado` → se ligada, `POST /comunicacoes/{id}/reservar` (`Idempotency-Key: reserva:<id>:v<versao>:exec<execução>`, `X-PCPR-Versao-Esperada`) → 409/423 encerra sem enviar → envia ao canal em até 3 tentativas **controladas** (sem `retryOnFail`; repete só recusa comprovada, ver abaixo) → `POST …/resultado` → `POST /excecoes` só para falha definitiva ou resultado desconhecido (a falha temporária é do PCPR, que reagenda) |
| `w3-reconciliacao.json` | `pcprReconcilia01` | PCPR · Reconciliação | Schedule a cada 15 min **e** webhook `POST /webhook/pcpr-reconciliar` (Header Auth; disparo manual/teste) | `GET /comunicacoes/devidas` → uma por vez (Loop Over Items) → W2. Responde `{"devidas": N}`. É também quem faz as rodadas seguintes de uma comunicação que o PCPR reagendou por falha temporária |
| `w4-recebimento-de-arquivo.json` | `pcprRecebimento1` | PCPR · Recebimento de arquivo | Webhook `POST /webhook/canal-recebimento` (Header Auth do canal; responde pelo nó *Responder*, não ao receber) | Um anexo por vez (*Loop Over Items*) → baixa do canal → SHA-256 → `POST /recebimentos` multipart com `Idempotency-Key: receb:<canal>:<mensagem_id_canal>:<anexo_indice>` e `anexo_indice`/`total_anexos`/`nome_arquivo`. Cada anexo termina num **desfecho**: aceito; registrado sem arquivo (`POST /recebimentos/sem-arquivo`: sem anexo, anunciado acima de 25 MiB, 413 do PCPR, download 404/410); **exceção** para recusa permanente do PCPR (409, 422, outro 4xx; chave `excecao:recebimento-canais:receb:<canal>:<mensagem>:<anexo>:<classe da recusa>:<motivo>`, corpo função só da chave); ou `reentregar` para falha transitória (rede, 5xx, 408, 423, 425, 429, 401/403). **200 só se todos os desfechos são finais**; algum `reentregar` → **503**, e se a mensagem chegou ao canal há mais de `cfg_fila_parada_s` (4 h) abre também uma exceção `fila_parada` (uma por mensagem) e continua 503 |
| `w5-erros.json` | `pcprErros0000001` | PCPR · Erros | Error Trigger (é o `errorWorkflow` de W1–W4 e W6–W8) | `POST /excecoes` (`motivo: outro`, nó e mensagem do erro com sequências de token mascaradas, id da execução); **não guarda execuções** (`saveData…="none"`) |
| `w6-enviar-por-whatsapp.json` | `pcprWhatsEnvio01` | PCPR · Enviar por WhatsApp (oficial) | Chamado pelo W2 quando o canal **da reserva** é `whatsapp` | **WA-3, desligado.** Modelo *utility* fora da janela de 24 h; documento por id de mídia dentro dela; registra resultado e exceção |
| `w7-webhook-whatsapp.json` | `pcprWhatsWebhk01` | PCPR · Webhook WhatsApp | Webhook `GET` e `POST /webhook/whatsapp` | **WA-3, desligado; variante V1** (a recomendação é a V2). Verificação GET, HMAC `X-Hub-Signature-256`, mídia em 2 passos, `/recebimentos`; 503 quando o W8 adia um status |
| `w8-status-whatsapp.json` | `pcprWhatsStatus1` | PCPR · Status WhatsApp | Chamado pelo W7 | **WA-3, desligado.** `delivered`/`read`/`failed` → `POST /comunicacoes/{id}/entrega`; status de mensagem ainda sem resultado registrado → **adiado** (o W7 responde 503 e a Meta reentrega) enquanto tiver até 1 h; mais velho → exceção e 200 |

Pontos de projeto que os testes confirmaram (detalhes e evidências no README do protótipo):

- **O PCPR decide; o n8n transporta.** Toda garantia de "uma vez só" está no PCPR (reserva com
  lease + `Idempotency-Key`); a deduplicação do n8n é só uma economia.
- **A chave do reservar inclui o id da execução.** É estável dentro da execução (retentativa HTTP
  devolve a mesma reserva) e diferente entre execuções: se duas execuções usassem a mesma chave
  (`reserva:<id>:<versao>`), a segunda receberia a *mesma* reserva repetida e também enviaria.
- **W2 processa um item por execução** (W3 usa *Loop Over Items* com lote 1; o modo "Run once for
  each item" do Execute Workflow está obsoleto no 2.x).
- **Chamadas ao W2 não derrubam o chamador** (`onError: continueRegularOutput` no Execute
  Workflow): o erro do W2 vai para o W5 uma vez, pela execução do próprio W2.
- **W1 antecipa com tolerância de 2 min** (`imediato` ou `enviar_em <= agora + 2 min`): o relógio
  de duas máquinas nunca bate no milissegundo. Se for cedo, o PCPR responde 409 e a
  reconciliação envia depois.

### Retentativa e confirmação (mudou na revisão do PR #23)

- **Envio (W2): o `retryOnFail` nativo do n8n não é usado no nó que fala com o canal.** Ele repete
  qualquer erro — inclusive tempo esgotado ou conexão derrubada **depois** de o canal aceitar — e
  duplicaria a mensagem (no 2.43.7, com `continueErrorOutput`, o núcleo reexecuta o nó quando o
  1º item sai com `json.error`: `workflow-execute.js`). O W2 tem 3 nós de envio em sequência; um
  Code node classifica cada resposta e **só repete o que prova que o canal não aceitou**:
  conexão recusada/DNS antes de enviar, ou HTTP 429/503 com corpo de recusa (`"aceita": false`),
  com 1 s de espera. Tempo esgotado, ECONNRESET/"socket hang up" e respostas ambíguas
  (500/502/504, 503 sem corpo de recusa) vão direto para **`resultado_desconhecido` + exceção,
  sem reenvio** (T14). 4xx (exceto 408/429) = `falha_definitiva` + exceção.
- **Recusas esgotadas = `falha_temporaria`, não definitiva.** O PCPR volta a comunicação para
  `agendada` com backoff e uma nova rodada sai pela reconciliação (W3); esgotadas as rodadas, o
  **PCPR** marca `falhou` e abre **uma** exceção `limite_tentativas` (T7: 3 rodadas × 3
  tentativas, depois nada; T15: canal fora do ar e de volta → 1 envio). O n8n não abre exceção
  para falha temporária.
- **Recebimento (W4): 2xx ao canal só depois de cada anexo ter desfecho final no PCPR** (antes
  era `onReceived`: o 200 saía antes do download e do `POST /recebimentos`, e uma falha perdia o
  arquivo). Sem retentativa interna para falha **transitória**: a **reentrega do canal** é a
  retentativa; o que já foi aceito repete a mesma `Idempotency-Key` (T16, T17). Falha
  **permanente** não é reentregue (2ª verificação): exceção humana com chave e corpo estáveis e
  resposta final; 413 e anexo sem bytes vão a `/recebimentos/sem-arquivo` (T19). A chave inclui a
  classe da recusa (operação, HTTP, código): se o motivo muda entre entregas (422 e depois 409),
  abre outra exceção em vez de reusar a chave com outro corpo (T19f). Falha **transitória** que
  persiste numa mensagem com mais de `cfg_fila_parada_s` (4 h) → exceção `fila_parada` e 503: a
  pessoa é avisada e o canal continua reentregando (T19g, 3ª verificação). Cuidado do modo
  `responseNode` no 2.43.7: se a execução terminar sem passar por um nó *Responder*, o n8n
  responde **200 vazio** (`webhook-helpers.js`) — por isso todo caminho do W4, inclusive dentro
  do laço, termina num desfecho e num *Responder*.
- **Status (W7/W8): status que chega antes do `resultado` não é engolido.** Sem
  `biz_opaque_callback_data`, o W8 procura o wamid no PCPR; não achou → adia, e o W7 responde 503
  para a Meta reentregar (TW14). Com `biz_opaque_callback_data`, o PCPR já guarda a marca pelo
  wamid e a aplica quando o resultado chegar. Status órfão com mais de `cfg_adiar_max_s` (3600 s)
  não é mais adiado: exceção e 200 (TW14c), em vez de 7 dias de reentrega do lote.

## Credenciais exigidas (criar ANTES de importar; os IDs precisam bater)

Nenhum segredo está nos JSON — só referências `{id, name}`. Crie as credenciais com estes IDs
(pela CLI, como abaixo, ou pela interface trocando a referência em cada nó):

| ID | Tipo n8n | Campos | Usada em |
|---|---|---|---|
| `pcprApiToken0001` | Header Auth (`httpHeaderAuth`) | `name: Authorization`, `value: Bearer <token de serviço do PCPR>` | W2, W3, W4, W5 |
| `pcprHmacEventos1` | Crypto (`crypto`) | `hmacSecret: <segredo HMAC dos eventos>` | W1 |
| `pcprCanalApi0001` | Header Auth | cabeçalho de autenticação do provedor do canal | W2, W4 |
| `pcprCanalWebhk01` | Header Auth | cabeçalho que o canal envia no webhook de entrada | W4 |
| `pcprWebhookInt01` | Header Auth | cabeçalho do disparo manual da reconciliação | W3 |
| `pcprWaToken00001` | Header Auth | `name: Authorization`, `value: Bearer <token permanente do usuário de sistema da Meta>` | W6, W7 — **só no portão da WA-3** |
| `pcprWaAppSecret1` | Crypto | `hmacSecret: <App Secret do app da Meta>` (HMAC do `X-Hub-Signature-256`) | W7 — **só no portão da WA-3** |
| `pcprWaVerifyTok1` | Crypto | `hmacSecret: <chave aleatória>`; o *verify token* cadastrado na Meta é `hex(HMAC-SHA256(chave, "pcpr-whatsapp-verify-token-v1"))` | W7 — **só no portão da WA-3** |

Modelo do arquivo para `n8n import:credentials` (os valores vêm de um cofre, o arquivo é
criado fora do repositório e apagado logo depois; o n8n grava os dados **criptografados** com a
`N8N_ENCRYPTION_KEY` — conferido no protótipo exportando as credenciais e procurando os
segredos no arquivo):

```json
[
  {"id": "pcprApiToken0001", "name": "PCPR · token da API de automação", "type": "httpHeaderAuth",
   "data": {"name": "Authorization", "value": "Bearer <TROCAR>"}},
  {"id": "pcprHmacEventos1", "name": "PCPR · segredo HMAC dos eventos", "type": "crypto",
   "data": {"hmacSecret": "<TROCAR>"}},
  {"id": "pcprCanalApi0001", "name": "Canal · chave de envio", "type": "httpHeaderAuth",
   "data": {"name": "<CABECALHO>", "value": "<TROCAR>"}},
  {"id": "pcprCanalWebhk01", "name": "Canal · token do webhook de entrada", "type": "httpHeaderAuth",
   "data": {"name": "<CABECALHO>", "value": "<TROCAR>"}},
  {"id": "pcprWebhookInt01", "name": "PCPR · token do disparo da reconciliação", "type": "httpHeaderAuth",
   "data": {"name": "X-Disparo-Token", "value": "<TROCAR>"}}
]
```

## Como importar no servidor real SEM ativar

Pré-requisitos: backup do n8n feito e `N8N_ENCRYPTION_KEY` guardada fora da VPS (plano de
implantação, etapa 0).

1. **Ajustar o que é por instância** (no gerador, ou depois na interface — não são segredos):
   - nós **Configuração** de W2, W3, W4 e W5: `cfg_pcpr` (ex.: `https://<host>/api/automacao/v1`)
     e `cfg_canal` (no W4 também `cfg_limite_bytes`, 25 MiB, e `cfg_fila_parada_s`, 14400 s; no W8
     `cfg_adiar_max_s`, 3600 s);
   - W1 › **Preparar verificação**: `AMBIENTE_ESPERADO = 'producao'` (ou `treinamento`).
2. **Credenciais**: `n8n import:credentials --input=/tmp/credenciais.json` e apagar o arquivo.
3. **Workflows** (copie os 8 `.json` para uma pasta vazia dentro do contêiner; sem as
   credenciais do WhatsApp, W6–W8 entram só como definição e ficam parados):
   ```sh
   n8n import:workflow --separate --input=/tmp/pcpr-workflows/
   n8n list:workflow --active=true --onlyId   # deve sair vazio
   ```
   No 2.x o import **não ativa nada** por padrão (`--activeState` vale `false`; só
   `--activeState=fromJson` respeitaria o campo `active`). Conferido no protótipo: importados
   num n8n 2.43.7 limpo, os 5 entraram e a lista de ativos ficou vazia.
4. **Ativar (somente quando a API do PCPR existir e for aprovado)**: no 2.x "ativar" virou
   **publicar** — `n8n publish:workflow --id=<id>` (o `update:workflow --active` está obsoleto)
   ou o botão *Publish* na interface. Ordem: W5, W2, W1, W3, W4. Pela CLI, a mudança só vale
   depois de reiniciar o n8n (o próprio comando avisa). Para desligar:
   `n8n unpublish:workflow --id=<id>` (ou `--all`). **W6, W7 e W8 ficam de fora** até o portão
   da WA-3 (seção no fim).

## Ambiente do n8n usado no protótipo (conferido no `@n8n/config` da imagem 2.43.7)

`GENERIC_TIMEZONE=America/Sao_Paulo`, `TZ=America/Sao_Paulo`, `N8N_ENCRYPTION_KEY=<gerada>`,
`N8N_DIAGNOSTICS_ENABLED=false` (+ `N8N_DIAGNOSTICS_CONFIG_FRONTEND/BACKEND=""`),
`N8N_VERSION_NOTIFICATIONS_ENABLED=false`, `N8N_VERSION_NOTIFICATIONS_WHATS_NEW_ENABLED=false`,
`N8N_TEMPLATES_ENABLED=false`, `N8N_PERSONALIZATION_ENABLED=false`,
`N8N_HIRING_BANNER_ENABLED=false`, `N8N_DYNAMIC_BANNERS_ENABLED=false`,
`N8N_LICENSE_AUTO_RENEW_ENABLED=false`, `N8N_AI_ENABLED=false`,
`N8N_COMMUNITY_PACKAGES_ENABLED=false`, `N8N_PUBLIC_API_DISABLED=true`,
`EXECUTIONS_DATA_PRUNE=true`, `EXECUTIONS_DATA_MAX_AGE=168`,
`EXECUTIONS_DATA_PRUNE_MAX_COUNT=5000`, `N8N_SSRF_PROTECTION_ENABLED=true` +
`N8N_SSRF_ALLOWED_HOSTNAMES=<host da API do PCPR>`, `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`
(já é o padrão no 2.x), `N8N_PYTHON_ENABLED=false` (a imagem não traz Python),
`N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true`; porta publicada só em `127.0.0.1`.

**Retenção de execuções (segurança).** O W2 recebe na reserva o destino e a mensagem com o
link-credencial (KM, assinatura) e o token de reserva; o W4 recebe o arquivo e o remetente. Por
isso W2, W4 e W5 saem com `saveDataSuccessExecution`, `saveDataErrorExecution` = `"none"`,
`saveManualExecutions=false` e `saveExecutionProgress=false` (W1 e W3 só guardam erros; o
diagnóstico vai pelo W5, com metadados). O W5 entrou na lista na 2ª verificação: o Error Trigger
recebe a mensagem de erro do fluxo que falhou, que pode citar o token de reserva (o T13 achou 2
ocorrências numa execução do W5). Em produção, além disso: `EXECUTIONS_DATA_SAVE_ON_SUCCESS=none`,
`EXECUTIONS_DATA_SAVE_ON_PROGRESS=false` e `EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS=false`; e o PCPR
mascara URLs, e-mails e tokens no `detalhe` de `/excecoes` antes de gravar (a mensagem de erro do
nó pode conter a URL). O cenário **T13** do protótipo varre as tabelas de execução do n8n e exige
zero ocorrências de destino, link e `reserva_token` — e **falha** no 2.43.7: "não salvar" só
marca a execução como apagada e a exclusão física espera o ciclo de *hard-delete* (15 min). Causa
medida e mitigação (`EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL=1`) em "Retenção", na seção WA-3. A edição Community não tem redação por campo:
não guardar é a única proteção disponível.

Os padrões da imagem, sem essas variáveis, **ligam** telemetria (`telemetry.n8n.io`, PostHog),
consulta de versões/novidades, templates e banners dinâmicos (`api.n8n.io`) e renovação de
licença. Avisos de depreciação que o 2.43.7 imprime e que valem para produção: modo `internal`
do task runner será removido (usar `N8N_RUNNERS_MODE=external` + imagem `n8nio/runners`);
`N8N_RUNNERS_TASK_TIMEOUT` cairá de 300 para 60 s; `N8N_UNVERIFIED_PACKAGES_ENABLED` passará a
`false`. A 3.0 (anunciada) também **liga por padrão a rotação de chaves de dados** (chaves no banco,
protegidas pela `N8N_ENCRYPTION_KEY`): antes de subir para 3.x, backup do banco + chave mestra e
leitura das breaking changes; manter 2.43.x fixada até lá
([v3.0 breaking changes](https://docs.n8n.io/changelog/v30-breaking-changes),
[rotação de chaves](https://docs.n8n.io/deploy/host-n8n/configure-n8n/security/rotate-encryption-keys.md),
consultados em 17/10/2026). Em produção, banco **PostgreSQL** próprio (o protótipo usou o SQLite padrão).

## O que estes fluxos exigem do PCPR e ainda não existe

1. **API de automação v1** (`api-automacao.v1.yaml`): `/estado`, `/comunicacoes/devidas`,
   `GET /comunicacoes?provedor_mensagem_id=` (W8; no contrato desde 18/10/2026),
   `/comunicacoes/{id}/reservar|resultado|entrega`, `/recebimentos` (com `anexo_indice`,
   `total_anexos` e chave por anexo), `/recebimentos/sem-arquivo`, `/recebimentos/{id}`,
   `/excecoes`, com token de serviço por integração (hash, escopos, rotação), `Idempotency-Key`
   obrigatório e persistido, 423 com a chave desligada, eco de `X-PCPR-Correlacao`.
2. **Emissor de eventos** a partir da outbox (ADR 0005): envelope
   `evento-integracao.schema.json`, assinatura `X-PCPR-Assinatura: t=<unix>,v1=<hex>`,
   `X-PCPR-Evento-Id`, corpo **byte a byte igual** ao assinado, reentrega com o mesmo `id`.
3. **Modelo de comunicação** com versão (da comunicação e da viagem), estados
   `agendada → enviando → enviada/falhou/cancelada`, reserva com prazo (lease) e **varredura de
   reservas vencidas** que abre exceção `resultado_desconhecido` (sem reenviar às cegas); e
   `falha_temporaria` → de volta a `agendada` com backoff, até um limite de rodadas, depois
   `falhou` + exceção `limite_tentativas` aberta pelo próprio PCPR.
4. **Regra da véspera** no domínio (`gestao/viagens/dominio/`) — a referência executável e os
   19 testes estão em `docs/automacao/prototipo/regra_vespera.py`.
5. **Fila de exceções** visível a humanos, **chave geral** (e por fluxo) da automação.
6. **Importação documental** recebendo `POST /recebimentos` (quarentena para contato não
   verificado; duplicado = mesmo SHA-256 **do mesmo servidor**, resolvido pelo contato — dois
   servidores com o mesmo arquivo são dois recebimentos).
7. Extensões que o protótipo precisou — **já incorporadas ao contrato (rascunho.2)**:
   `X-PCPR-Versao-Esperada` no reservar (409 `conflito_de_versao`), `recurso {tipo, id}` no corpo
   de `/excecoes`, cabeçalho `Idempotency-Replayed: true`, impressão da requisição multipart sobre
   campos + SHA-256 do arquivo e chave de reserva única por tentativa. Pendente no contrato: a regra
   de que respostas 423 (automação desligada) **não** são guardadas pela idempotência (religada, a
   mesma chave precisa poder executar).
8. **Canal real**: o nó *Enviar ao canal* (W2) e o *Webhook do canal*/*Baixar arquivo* (W4)
   falam com um canal **simulado** (desde o WA-3 o simulador do PCPR rotula essas comunicações
   como `email`; antes usava o rótulo fictício `whatsapp`). O canal real previsto é o **e-mail
   institucional** (envio por SMTP; recebimento por caixa postal IMAP com deduplicação por
   Message-ID) — só desenhado, não testado. **WhatsApp está BLOQUEADO** pela política oficial
   ([whatsapp-viabilidade.md](../whatsapp-viabilidade.md)): W6–W8 existem e foram testados só
   contra simulador; **não publicar nem cadastrar credencial real de WhatsApp** antes do portão.

## WhatsApp oficial (WA-3) — pronto e desligado

Frente WA-3 do [plano de implantação](../plano-implantacao.md): a integração com a **WhatsApp
Business Platform (Cloud API)** construída e testada **só contra um simulador local da Graph
API** (`docs/automacao/prototipo/simulador_graph.py`), nunca contra a Meta. A política oficial
hoje proíbe órgãos policiais na plataforma ([whatsapp-viabilidade.md](../whatsapp-viabilidade.md),
seção 1): **nada aqui pode ser ativado**. Evidência dos testes TW0–TW16 e medição de retenção:
[README do protótipo](../prototipo/README.md#whatsapp-oficial-wa-3--pronto-e-desligado) e
`docs/automacao/prototipo/resultados/resultados-whatsapp.json`.

### O que cada workflow faz

**W6 · Enviar por WhatsApp (oficial)** — chamado pelo W2 depois do `reservar` (o PCPR já
revalidou canal `ligado`, contato verificado com **opt-in** e horário). Decide a forma com o que
o PCPR mandou em `mensagem.whatsapp` (forma pedida, `janela_aberta_ate`, modelo e variáveis):

- fora da janela de 24 h (ou a menos de 10 min de fechar) → **modelo *utility* aprovado**;
- dentro da janela, documento → baixa o anexo pela URL assinada curta do PCPR, confere o SHA-256,
  faz **upload** (`POST /{phone_number_id}/media`) e envia `type: document` **por id de mídia**;
- dentro da janela, texto → `type: text`;
- sem forma possível (fora da janela e sem modelo) → **não chama a Graph API**: resultado
  `falha_definitiva` e exceção clara ("evita o erro 131047");
- 131047 síncrono numa mensagem livre → troca **uma vez** por modelo (nós separados, sem ciclo no
  grafo); nunca repete o livre;
- **sem retentativa automática do `POST /messages`** (a Cloud API não tem chave de idempotência:
  repetir depois de tempo esgotado duplicaria); só **limite de taxa** (HTTP 429 ou códigos 4,
  80007, 130429, 131048, 131056, aplicados antes do aceite) → `falha_temporaria` (o PCPR reagenda;
  TW16b); 5xx com erro genérico (1, 2, 131000, 131016…; TW16a), tempo esgotado, conexão caída ou
  resposta **sem** erro estruturado (ex.: 502 de um proxy depois de a Meta aceitar; TW15) →
  `resultado_desconhecido` e exceção, nunca temporária;
- envia `biz_opaque_callback_data: "com:<id>"` (volta nos status) e registra
  `POST /comunicacoes/{id}/resultado` com o **wamid** como `provedor_mensagem_id`.

**W7 · Webhook WhatsApp** (variante V1) — a Meta aceita um webhook por app, então mensagens e
status chegam no mesmo `GET|POST /webhook/whatsapp`:

- **GET** (verificação): `hub.mode=subscribe` e `hub.verify_token` comparado em tempo constante
  com o valor derivado da credencial `pcprWaVerifyTok1` (Code node não lê credencial e o Webhook
  não autentica por query; assim o esperado nunca fica em texto no workflow); ecoa `hub.challenge`
  (só se curto e alfanumérico) em `text/plain`; senão 403;
- **POST**: HMAC-SHA256 do **corpo bruto** (opção Raw Body + nó Crypto sobre o binário, bytes
  exatos) com o App Secret, comparado com `X-Hub-Signature-256` em tempo constante → 401 se não
  bater;
- separa os eventos (`entry[].changes[].value.messages|statuses`): mídia em **2 passos com
  Bearer** (`GET /{media_id}` → URL de 5 min → download; 404/URL vencida → pede **outra URL uma
  vez**), confere o SHA-256 (aceita hex ou base64) e faz `POST /recebimentos` com
  `Idempotency-Key: receb:whatsapp:<wamid>:0`; texto → `POST /recebimentos/sem-arquivo`
  (`sem_anexo`, abre a janela no PCPR); status → W8;
- responde **200 só depois** de o PCPR aceitar (Merge de todos os ramos → Respond). Falha → 500 →
  a Meta reentrega (até 7 dias). Status adiado pelo W8 → **503** (sem exceção no W5) → a Meta
  reentrega o lote; o que já foi gravado repete sem efeito. A deduplicação por id de mensagem é a do PCPR
  (`Idempotency-Key` por wamid). **Não há Remove Duplicates** antes do passo durável: ele grava a
  chave ao passar, e uma reentrega depois de falha seria descartada (mensagem perdida).

**W8 · Status WhatsApp** — `sent` → nada; `delivered` → `entregue`; `read` → `lida`;
`failed` → `falhou` (com o código, ex. 131047). Acha a comunicação pelo
`biz_opaque_callback_data` ou, sem ele, pelo mapeamento wamid → comunicação do PCPR
(`GET /comunicacoes?provedor_mensagem_id=`, resposta só `{id, versao}`). Lista vazia = o
`resultado` ainda não foi registrado (o status chegou antes): o item é **adiado** e o W7
responde 503, em vez de descartar com 200 (TW14) — enquanto o status tiver até 1 h
(`cfg_adiar_max_s`); mais velho → `POST /excecoes` (`excecao:whatsapp-status:<wamid>:<status>`)
e 200 (TW14c). `POST /comunicacoes/{id}/entrega` com
`Idempotency-Key: entrega:<id>:<wamid>:<status>`; o PCPR nunca regride (lida não volta a
entregue). `failed`/131047 numa mensagem livre → o **PCPR** agenda uma substituta por modelo.

Os três: `saveDataSuccessExecution` e `saveDataErrorExecution` = `"none"`,
`saveExecutionProgress=false`, `errorWorkflow` = W5. **Isso não basta** para o n8n 2.43.7 não
reter dado pessoal — ver "Retenção" abaixo.

### Credenciais (só no portão; nunca em texto no workflow)

`pcprWaToken00001` (Header Auth, `Authorization: Bearer <token permanente de usuário de
sistema>`), `pcprWaAppSecret1` (Crypto, App Secret) e `pcprWaVerifyTok1` (Crypto, chave do verify
token) — ver a tabela de credenciais acima. Por instância, sem segredo: nós **Configuração** de
W6 e W7 (`cfg_graph` = `https://graph.facebook.com/v<versão vigente>`; `cfg_numero_id` =
phone_number_id da conta institucional) e `N8N_SSRF_ALLOWED_HOSTNAMES`. Os arquivos exportados
apontam para o **simulador** (`host.docker.internal:8767`): uma publicação acidental não alcança a
Meta (e, no protótipo, `graph.facebook.com` e afins apontavam para 127.0.0.1 dentro do contêiner).

Por que não os nós oficiais do n8n (lidos na imagem 2.43.7, `n8n-nodes-base`): o **WhatsApp
Trigger** usa o **id do nó como verify token** (fica em texto no workflow), compara a assinatura
com `!==` (não é tempo constante), quando a assinatura não confere só deixa de rodar o fluxo
(`return {}`, sem recusa explícita; a resposta HTTP não foi medida) e, ao ser **publicado, chama
a Graph API** para criar a assinatura do webhook
(`/{app-id}/subscriptions`) — publicar já falaria com a Meta. O nó **WhatsApp Business Cloud**
fixa a base `https://graph.facebook.com/v13.0/` (não aponta para simulador nem para versão
vigente). Por isso HTTP Request + Webhook genérico + Crypto.

### Portão de ativação (todos obrigatórios)

1. **Autorização escrita** da Meta ou de provedor autorizado, declarando a PCPR elegível pela
   política vigente na data (frente WA-2), arquivada e citada numa ADR.
2. **Conta empresarial verificada em nome da instituição** (business portfolio, WABA pelo
   provedor, número institucional dedicado — nunca pessoal), app em modo Live, token de usuário
   de sistema.
3. **Decisão formal da PCPR e avaliação de LGPD**: base legal, opt-in registrado no
   `ContatoVerificado` (`consentimento_em`, `revogado_em`, `metodo`, `origem`), retenção,
   relatório de impacto.
4. **Modelos aprovados** (*utility*), com o mapeamento `tipo → modelo@versão` versionado no PCPR.
5. Preços, limites (*tiers*) e volume reais conferidos — o protótipo não exercitou nenhum deles.

### Como ligar sem mudar estados nem regras

O canal é **atributo** da comunicação, escolhido na reserva; a máquina de estados não muda.

1. PCPR: `canais.whatsapp` `bloqueado → desligado` por **configuração versionada + ADR**.
   Desligado, nada sai (a reserva dá 423 e a comunicação segue `agendada`).
2. n8n: importar as 3 credenciais, ajustar os nós **Configuração**, publicar **W8, W6 e W7**
   (W7 só na variante V1) e reiniciar. Na Meta, cadastrar o callback **do PCPR** (variante V2,
   recomendada) ou do W7 (V1) com o verify token derivado.
3. PCPR: `whatsapp` → `ligado` **por fluxo**, começando por um fluxo e poucos contatos com opt-in.
   Enquanto `bloqueado`, as comunicações vão para `aguardando_envio_manual` e seguem pela WA-1
   (o operador envia do aparelho institucional e marca "enviado por outro meio" → `feita_a_mao`).
4. Desligar a qualquer momento: `whatsapp` → `desligado` (reservas dão 423; nada se perde) e
   `n8n unpublish:workflow --id=…`.

### Retenção — o que o n8n guarda mesmo com "não salvar" (medido no TW13)

No n8n 2.43.7 a execução é **gravada no banco ao começar**, com os dados de entrada (o corpo do
webhook, ou os itens passados a um sub-workflow), e os binários vão para o disco (`storage/`,
modo `filesystem`, padrão). No fim, com `saveData…="none"` **e** `EXECUTIONS_DATA_PRUNE=true`
(padrão), a execução só é **marcada como apagada** (`deletedAt`), com `status` ainda `running`;
a exclusão física (banco e disco) só vem no ciclo de *hard-delete*, a cada **15 min** por padrão
(`execution-persistence.js` › `deleteInFlightExecution`). É a causa do achado do T13 da suíte
principal, e o modo de resposta do webhook não interfere (medido com o W4 ainda em `onReceived` e
o W7 em `responseNode`: os dois ficaram; desde 18/10 o W4 também usa `responseNode` e o T13
seguiu achando o telefone nas execuções `running` do W4 até o *hard-delete*). Medido: a variante V1 deixou telefone, wamid, URL de mídia, id
de mídia, nome do perfil e o verify token no banco (em texto e, de novo, dentro do Raw Body
guardado inline em base64), os **documentos recebidos** no disco e até os corpos recusados por
assinatura inválida; o W6 (comum às duas variantes) deixou destino, link do km e token de
reserva. Para o dia da ativação:

- **Recebimento pela variante V2** (webhook da Meta direto no PCPR): o n8n não vê telefone, wamid
  nem mídia de entrada (medido: 0 ocorrências) e deixa de precisar de webhook público.
- No n8n de produção, **`EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL=1`** (medido: tudo some no
  primeiro ciclo, ~1 min após a subida) — ou `EXECUTIONS_DATA_PRUNE=false` (exclusão física
  imediata no fim da execução; medido: 0), que porém desliga a poda do que **é** salvo (erros de
  W1/W3) e não limpa o que já estava marcado.
- Execução cortada por queda do n8n não chega ao fim nem é marcada: depende da recuperação e da
  poda — não medido.
