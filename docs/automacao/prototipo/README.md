# Protótipo de automação PCPR × n8n (dados 100% sintéticos)

Prova local, de 17/10/2026, de que os fluxos desenhados em `docs/automacao/` (arquitetura,
contratos `evento-integracao.schema.json` e `api-automacao.v1.yaml`, ADRs 0005 e 0020) funcionam
num **n8n 2.43.7 de verdade**, contra **simuladores** do PCPR e de um canal de mensagens. Nada
real foi tocado: nenhum e-mail/WhatsApp, nenhum serviço externo, nenhuma VPS, nenhum banco do
sistema. Tudo roda em `127.0.0.1` e é removido no fim.

A frente **WA-3 (WhatsApp oficial pronto e desligado)** tem simulador da Graph API, workflows
W6–W8 e suíte próprios (`testar_whatsapp.py`, TW0–TW13), na seção
[WhatsApp oficial (WA-3)](#whatsapp-oficial-wa-3--pronto-e-desligado) no fim deste arquivo.

## Executado de fato × só desenhado

| Item | Situação |
|---|---|
| Simulador do PCPR (API v1 em memória: `/estado`, `/comunicacoes/devidas`, `reservar`, `resultado`, `entrega`, `/recebimentos`, `/recebimentos/{id}`, `/excecoes`; Bearer; `Idempotency-Key` real; 423; 409; lease com varredura) | **Executado** (`simulador_pcpr.py`) |
| Emissor de eventos assinados (HMAC-SHA256 de `t + "." + corpo_bruto`, `X-PCPR-Assinatura: t=…,v1=…`, `X-PCPR-Evento-Id`) e envelopes validados contra o schema | **Executado** |
| Regra da véspera (função pura + 18 testes) e uso dela no simulador (confirmação, reagendamento, cancelamento) | **Executado** (`regra_vespera.py`, `test_regra_vespera.py`) |
| Simulador de canal (caixa de saída com falha injetável, `provedor_mensagem_id`, inbound com PDF sintético) | **Executado** (`simulador_canal.py`; desde o WA-3 as comunicações e o T9 levam o rótulo `email`) |
| n8n 2.43.7 em contêiner descartável, credenciais e workflows importados e publicados pela CLI, W1–W5 | **Executado** (`n8n_local.py`, `construir_workflows.py`) |
| Testes T1–T13 com asserções no estado dos simuladores e no banco do n8n + métricas | **Executado** (`testar_prototipo.py` → `resultados/resultados.json`) |
| Export dos workflows com `"active": false` e reimportação num n8n limpo sem ativar nada | **Executado** (`docs/automacao/n8n/`) |
| API real no PCPR, emissor real a partir da outbox, modelo de comunicação, fila de exceções, chave geral | **Só desenhado** — não existe no sistema |
| Canal real (e-mail institucional: envio SMTP e recebimento por caixa IMAP com dedup por Message-ID), PWA do link de KM, importação documental real | **Só desenhado** — o T9 usou um canal fictício em formato de webhook (rótulo `whatsapp` até o WA-3, `email` depois; o WhatsApp está **bloqueado**, ver `../whatsapp-viabilidade.md`) |
| WhatsApp oficial contra **simulador** da Graph API (W6–W8, TW0–TW13, retenção V1 × V2) | **Executado** — seção WA-3 abaixo; contra a Meta, **nada** (proibido até o portão) |
| n8n com PostgreSQL, task runner externo, TLS, proxy, backup e restauração | **Só desenhado** (o protótipo usa SQLite e runner interno) |

## Como reproduzir

Requisitos: Docker com a imagem `docker.n8n.io/n8nio/n8n:2.43.7` já baixada; Python ≥ 3.13 com
base de fusos IANA (no Windows, o pacote `tzdata` — o `.venv` do projeto já tem; os scripts não
usam mais nada fora da biblioteca padrão); portas 5678, 8765 e 8766 livres.

```sh
# a partir da raiz do repositório
.venv/Scripts/python.exe -m unittest docs/automacao/prototipo/test_regra_vespera.py -v   # T11 sozinho
.venv/Scripts/python.exe docs/automacao/prototipo/testar_prototipo.py                    # tudo (~7 min)
#   --sem-exportar   não sobrescreve docs/automacao/n8n/*.json
#   --manter         deixa contêiner e simuladores no ar para inspeção (limpar à mão depois)
#   --apenas T4,T9   só alguns cenários (LAT = medição de latência)
#   --relatorio X    grava o relatório em X (regressão sem sobrescrever resultados.json)
.venv/Scripts/python.exe docs/automacao/prototipo/testar_whatsapp.py                     # WA-3 (~5 min)
```

O script gera segredos sintéticos novos a cada execução, sobe os simuladores, cria o volume
`pcpr-prototipo-n8n-dados`, importa credenciais e workflows pela CLI do n8n
(`import:credentials`, `import:workflow --separate`, `publish:workflow --id`), sobe o contêiner
`pcpr-prototipo-n8n` só em `127.0.0.1:5678`, roda os cenários, mede, para o n8n, despublica,
exporta (`export:workflow --backup`) e remove contêiner, volume, processos e a pasta
temporária. O relatório fica em `resultados/resultados.json` (sem segredos: o script confere e
registra `segredos_no_relatorio: []`).

Arquivos:

| Arquivo | Papel |
|---|---|
| `regra_vespera.py` / `test_regra_vespera.py` | regra pura + T11 |
| `comum.py` | assinatura HMAC, leitura de multipart sem `cgi`, base HTTP |
| `simulador_pcpr.py` | API v1 + emissor de eventos + controles `/_sim/*` |
| `simulador_canal.py` | caixa de saída, falhas injetáveis, inbound e arquivos |
| `simulador_graph.py` | **WA-3**: Graph API do WhatsApp simulada (envio, mídia, webhooks assinados, verificação) |
| `construir_workflows.py` | **fonte** dos workflows W1–W8 (JSON do n8n gerado por código; W6–W8 com `--whatsapp`) |
| `n8n_local.py` | contêiner, variáveis de ambiente, import/publish/export, `docker stats`, cópia de `~/.n8n` |
| `testar_prototipo.py` | orquestração, cenários, métricas, export e limpeza (suíte principal) |
| `testar_whatsapp.py` | **WA-3**: TW0–TW13, varredura de retenção, export de W2/W6–W8 → `resultados/resultados-whatsapp.json` |
| `ruff.toml` | herda o `pyproject.toml`; libera `print`/`subprocess`/`urllib` só nesta pasta |

## Resultados da suíte principal

**Rodada final: 17/10/2026, 23:31–23:36 (horário de Brasília) — 13 de 13 passaram, saída 0**
(`resultados/resultados.json`). É a primeira rodada com todas as mudanças: retenção zero nos
workflows sensíveis (W2/W4), remoção física das execuções apagadas a cada 1 min
(`EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL=1`), desvio do W2 para o W6 (WhatsApp oficial,
desligado), T9 com `canal: email` e o **T13**.

| Rodada (−03:00) | Resultado | O que mudou |
|---|---|---|
| 03:53–03:59 | T1–T12: 12/12 | primeira rodada completa (tabela de evidências abaixo) |
| 21:47–21:54 | T1–T12 passaram; T13 (novo) falhou | W2/W4 sem guardar execuções; T13 achou destino e nomes de campo |
| 22:00–22:05 | T1–T12 passaram; T13 falhou | T13 passou a buscar valores, não nomes: 2 ocorrências do telefone em execuções de webhook do W4 (`running`) |
| 23:10–23:15 | T1–T12 passaram; T13 falhou | regressão depois da WA-3; causa achada no código do n8n (ver WA-3) |
| **23:31–23:36** | **13/13** | mitigação `EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL=1` |

**T13 na rodada final:** zero ocorrências de destino, link-credencial (`example.invalid/km/`) e
valor do token de reserva nas tabelas de execução do n8n já na primeira varredura, logo depois dos
cenários (27 execuções restantes, todas de erro salvas por W1/W3/W5, sem esses dados). Sem a
mitigação, o n8n grava a execução com a entrada ao iniciar e, com "não salvar", só a marca como
apagada; a remoção física roda a cada 15 min por padrão — durante esse tempo a entrada fica no
banco e nos backups. Por isso a recomendação para produção é a mitigação **mais** receber
webhooks com dado pessoal direto no PCPR (variante V2 da WA-3).

A tabela abaixo é a evidência detalhada da primeira rodada completa (03:53–03:59); as rodadas
seguintes repetiram os mesmos cenários com o mesmo resultado (T9 com `canal: email`).

"Envio" = registro **aceito** na caixa de saída do canal simulado, que **não** deduplica
(um envio repetido apareceria como dois).

| ID | Cenário | Resultado | Evidência (execução final) |
|---|---|---|---|
| T1 | Evento válido → 1 envio e 1 resultado | **Passou** | 2 eventos → n8n 202/202; 1 reserva (`reserva:2:v1:exec4`), 1 envio no canal, 1 resultado `enviada`; os 2 envelopes emitidos validados contra `evento-integracao.schema.json` |
| T2 | Mesmo evento reenviado → continua 1 envio | **Passou** | (a) 2 reentregas em série → 202, **0** chamadas novas ao PCPR (barradas na dedup do n8n), 1 envio; (b) 5 entregas simultâneas → 1 passou pela dedup, 1 reserva 200, 1 envio; (c) evento com **outro id** para a mesma comunicação (dedup contornada) → reservar **409 `ja_processada`**, continua 1 envio |
| T3 | Assinatura inválida → 401 e 0 envio | **Passou** | segredo errado, `t` de 10 min atrás, corpo com 1 espaço a mais depois de assinado, sem assinatura e `ambiente: producao` → **401** nos 5; 0 tentativas no canal e 0 chamadas ao PCPR; controle positivo (o mesmo evento assinado certo) → 202 e 1 envio |
| T4 | Evento obsoleto → 409 e 0 envio | **Passou** | (a) evento antigo de comunicação substituída por reagendamento, entregue fora de ordem → reservar **409 `obsoleta`**, 0 envio; a nova (para 26/10 09:00 −03:00) segue agendada e não foi reservada; (b) evento v1 depois de a comunicação ir para v2 → **409 `conflito_de_versao`**; evento v2 → 1 envio |
| T5 | Automação desligada → 423, 0 envio, segue agendada | **Passou** | (a) chave desligada: W2 lê `/estado` e encerra, 0 reservas; (b) desligada entre `/estado` e `reservar` → **423**, 0 envio, segue `agendada`; (c) religada → reconciliação `{"devidas": 2}` → 1 envio de cada |
| T6 | Canal falha 1x e aceita → 1 envio e 1 resultado | **Passou** | tentativas no canal `[500, 200]` com 1,03 s de intervalo; 1 envio efetivo; 1 resultado `enviada` |
| T7 | Canal sempre falha → exceção, sem loop | **Passou** | exatamente 3 tentativas (500) e parou; exceção `limite_tentativas` (origem n8n, execução 41); estado `falhou`; reconciliação depois → `{"devidas": 0}` e as tentativas continuam 3 |
| T8 | Evento perdido → reconciliação envia 1 vez | **Passou** | evento nunca entregue; reconciliação `{"devidas": 1}` → 1 envio; 2ª reconciliação `{"devidas": 0}`; total 1 |
| T9 | Arquivo devolvido 2x (mesmo id) → 1 recebimento | **Passou** | 2 webhooks do canal com o mesmo `mensagem_id` → 2 `POST /recebimentos` com a mesma chave `recebimento:whatsapp:<id>`; a 2ª é repetição idempotente; 1 recebimento `aceito_para_processamento`; SHA-256 conferido (PDF sintético de 636 bytes) |
| T10 | Reinício do n8n no meio → nada duplicado, reconciliação completa | **Passou** | lease 15 s, canal lento (8 s); `docker kill` com 4 comunicações (A) em `enviando`; 2 eventos (B) perdidos com o n8n fora; n8n voltou em 30,5 s; reentrega de um evento A → 202 sem novo envio (dedup ou reservar; o teste não distingue); reconciliação `{"devidas": 2}` → as 2 B enviadas 1x; as 4 A: reserva venceu → `falhou/resultado_desconhecido` + 1 exceção cada (o canal tinha recebido 1 vez cada); **0 duplicados**; nenhuma agendada vencida sobrando |
| T11 | Regra da véspera (unitário) | **Passou** | 18 testes: caso normal, início à meia-noite, 00:30 confirmado às 23:50, data local × data UTC, em cima da hora, fronteira 09:00 exata/−1 µs, já iniciada (aviso), resultado no fuso de SP, horário de verão de 2018, datetime sem fuso recusado, reagendamento (recalcula e invalida por versão; para dentro da janela; depois de enviada), cancelamento, evento fora de ordem, mesma versão |
| T12 (extra) | Erro inesperado → W5 abre exceção | **Passou** | `/estado` devolvendo 500 → W2 falha no nó *Consultar estado* (após 2 tentativas) → W5 abre **1** exceção (`fluxo: n8n:PCPR · Entregar comunicação`, execução 71); 0 envio; normalizado, reconciliação `{"devidas": 1}` → 1 envio |

Rodadas anteriores (desenvolvimento) que falharam e o que mudou: T9 falhou na 1ª rodada (422
por *boundary* do multipart — ver "Descobertas"); a medição de latência falhou uma vez com um
evento "imediato" não enviado em 60 s (relógio do contêiner atrás do host); W4 falhava no
primeiro teste manual (nó Crypto descartando o binário).

## Métricas

A coluna "Execução final" é da primeira rodada completa (03:53–03:59); a coluna "faixa" junta as
rodadas completas feitas na mesma máquina (notebook Windows + Docker Desktop, compartilhado com
outra sessão de trabalho — os números variam e não representam a VPS). **Rodada final de
23:31–23:36 (13/13):** evento → envio em série p50 189 ms · p95 238 ms; 20 simultâneos p50 2,9 s ·
p95 3,3 s; n8n em repouso 396 MiB, pico 856 MiB — dentro das faixas abaixo.

| Métrica | Execução final | Faixa nas rodadas |
|---|---|---|
| Latência evento → envio, 20 em série | **p50 314 ms · p95 403 ms** (mín. 291, máx. 541) | p50 166–361 ms · p95 214–490 ms |
| ↳ até o 202 do n8n (verificação HMAC) | p50 128 ms · p95 151 ms | — |
| ↳ até a reserva chegar ao PCPR | p50 265 ms · p95 343 ms | — |
| Latência evento → envio, 20 simultâneos | **p50 5,1 s · p95 6,6 s** (mín. 2,5, máx. 6,8) | p50 2,5–6,1 s · p95 3,4–13,7 s |
| ↳ até o 202 / até a reserva | p50 1,4 s / 4,9 s · p95 2,4 s / 6,5 s | — |
| Memória do contêiner n8n em repouso (antes), `docker stats` | **391 MiB** (após 45 s parado; inclui o runner JS) | 390–400 MiB com 45 s de espera (450–781 MiB nas rodadas que mediam só 20 s após subir) |
| Memória durante os testes | mediana 472 MiB · **máx. 884 MiB** (na rajada; T10 713 MiB) | máx. 670–1 036 MiB |
| Memória em repouso depois dos testes | **407 MiB** | 382–632 MiB |
| Banco do n8n (SQLite) após a bateria | `database.sqlite` 4,8 MiB + WAL 4,0 MiB + shm 32 KiB ≈ **8,8 MiB** | 7,9–8,9 MiB |
| Import + publicação pela CLI (contêiner descartável) | 68 s | 68–93 s |
| Subida do n8n até o webhook responder | 15,8 s; após `docker kill`: 30,5 s | 15,8–19,8 s; 27,6–30,5 s |

Leitura: em série, o caminho evento → envio fica em ~0,3 s. Em rajada de 20, a fila está no
próprio n8n (o 202 já demora 1,4 s e a reserva chega ao PCPR 5 s depois), não nos simuladores:
um processo `main` com SQLite e runner de código interno processa W1 + W2 de 20 eventos ao
mesmo tempo. Para o volume do PCPR (dezenas de comunicações por dia, picos às 09:00) isso
sobra; com PostgreSQL e runner externo deve melhorar, mas **não foi medido**. Na primeira
rodada todas as execuções ficaram salvas (padrão `all`); a revisão de segurança apontou que a
execução do W2 guarda destino, link-credencial e token de reserva. Desde a segunda rodada W2 e W4
não guardam execução nenhuma e W1/W3 só guardam erros — o **T13** varre as tabelas de execução
do n8n e exige zero ocorrências desses dados.

## Descobertas sobre o n8n 2.43.7 (conferidas na imagem, não supostas)

1. **Ativar virou publicar.** `update:workflow --active` está obsoleto; usa-se
   `publish:workflow --id=…` / `unpublish:workflow --id=…|--all`. `import:workflow` **nunca ativa**
   por padrão (`--activeState=false`; só `fromJson` respeita o campo). Pela CLI, a mudança só vale
   depois de reiniciar o n8n (o comando avisa). Sub-workflow chamado por Execute Workflow e o
   workflow de erro também foram publicados; publicar o de Error Trigger funcionou.
2. **HMAC sem expor segredo e sem `$env`.** O Webhook não verifica HMAC; `$env` em nós vem
   bloqueado (`N8N_BLOCK_ENV_ACCESS_IN_NODE=true` é o padrão) e `$vars` é recurso pago. Solução
   usada: opção **Raw Body** do Webhook (corpo em binário, base64) → Code node monta
   `t + "." + corpo` sem re-serializar → nó **Crypto v2 (HMAC)**, cujo segredo fica numa
   **credencial do tipo `crypto`** (`hmacSecret`, criptografada no banco) → Code node compara em
   tempo constante e checa frescor, ambiente e `X-PCPR-Evento-Id`. Não foi preciso
   `NODE_FUNCTION_ALLOW_BUILTIN=crypto` nem `require` no Code node.
3. **Dedup entre execuções** = nó *Remove Duplicates* v2, operação "Remove Items Processed in
   Previous Executions", escopo do workflow, histórico de 10 000 chaves, guardado no banco do
   n8n (tabela `processed_data`), portanto vale entre execuções e reinícios. Implementação
   (`deduplication-helper.js`): **ler-alterar-gravar de uma linha JSON, sem trava nem
   transação** — é economia, não garantia. Na execução final, de 5 entregas simultâneas do mesmo
   evento só 1 passou (a corrida não apareceu nesta rodada); a garantia de "1 envio" foi provada
   no PCPR (T2c: evento com outro id → 409 no reservar). No T10 a reentrega pós-queda não gerou
   envio, mas o teste não distingue se foi barrada pela dedup ou pelo reservar.
4. **O nó Crypto v2 descarta o binário que resume** (`CryptoV2.node.js`: só repassa
   `item.binary` se não processou binário). Achado no W4 (o upload multipart ficava sem arquivo);
   corrigido com um Code node que reanexa o binário do nó anterior.
5. **Execute Workflow "Run once for each item" está obsoleto** — usar *Loop Over Items* (lote 1)
   + "Run once with all items" (W3). Erro dentro do sub-workflow dispara o `errorWorkflow` **do
   sub-workflow** (T12: exceção com `fluxo = n8n:PCPR · Entregar comunicação`); com
   `onError: continueRegularOutput` no chamador, não sai uma segunda exceção duplicada.
6. **Retentativa nativa**: `retryOnFail` + `maxTries` (≤ 5) + `waitBetweenTries` (≤ 5 s) com
   `onError: continueErrorOutput` dá exatamente N tentativas e uma saída de erro tratável (T6/T7:
   500 → 200 com ~1 s de intervalo; 3 × 500 → saída de erro → exceção, sem laço).
7. **Schedule de 15 min** vira cron `S */15 * * * *` com um segundo fixo `S` derivado do nó
   (`GenericFunctions.js`): dispara em :00/:15/:30/:45 — as 09:00 da véspera são cobertas em
   menos de 1 min mesmo só pela reconciliação.
8. **Queda abrupta**: depois do `docker kill`, o n8n voltou em 27,6–30,5 s; no log de uma das
   rodadas registrou "Found unfinished executions: …" e "[Recovery] … amended execution" e **não
   retomou** as execuções cortadas (nenhuma das 4 reservas órfãs recebeu resultado) — por isso a
   reconciliação e o lease do PCPR são obrigatórios (T10).
9. **Padrões da imagem chamam a internet**: telemetria (`telemetry.n8n.io`, PostHog), versões e
   novidades, templates, banners dinâmicos (`api.n8n.io`) e renovação de licença vêm ligados. Todos
   desligados por variável e **conferidos lendo a configuração efetiva dentro do contêiner**
   (`GlobalConfig` do `@n8n/config`). O 2.43.7 também imprime depreciações relevantes: runner
   `internal` será removido (usar `external` + `n8nio/runners`), `N8N_RUNNERS_TASK_TIMEOUT` cairá
   de 300 para 60 s, e tenta subir runner Python que a imagem não tem (`N8N_PYTHON_ENABLED=false`).
10. **Proteção SSRF** (`N8N_SSRF_PROTECTION_ENABLED=true`) funciona com lista de hosts liberados
    (`N8N_SSRF_ALLOWED_HOSTNAMES=host.docker.internal`): todas as chamadas aos simuladores
    passaram com ela ligada. Em produção, liberar só o host da API do PCPR (e do canal).

## Descobertas sobre o desenho (viraram ajustes)

- **Chave de idempotência do reservar** precisa incluir a execução
  (`reserva:<id>:v<versao>:exec<id_execução>`). Com `reserva:<id>:<versao>` puro, uma segunda
  execução (evento + reconciliação ao mesmo tempo, ou reentrega que escapou da dedup) receberia a
  resposta repetida — com o mesmo token de reserva — e enviaria de novo.
- **Relógios diferentes**: na 2ª rodada, um evento "imediato" caiu em "ainda não é hora" porque o
  relógio do contêiner estava ~0,2 s atrás do host (execução inspecionada no banco do n8n:
  `enviar_em` 03:32:52 × execução às 03:32:51,95). O W1 agora antecipa com tolerância de 2 min
  (`imediato` ou `enviar_em ≤ agora + 2 min`) e o PCPR decide no reservar (409 `regra_violada` se
  cedo).
- **Idempotência com multipart**: o mesmo arquivo reenviado vem com outro *boundary*; comparar
  bytes daria 422 "chave reutilizada com outra requisição". A impressão da requisição passou a
  ser campos + SHA-256 do arquivo (T9 falhou antes da correção e passou depois).
- **Reserva vencida sem resultado** vira exceção `resultado_desconhecido`, nunca reenvio
  automático: no T10 o canal tinha de fato recebido as 4 mensagens cortadas pela queda — reenviar
  às cegas duplicaria.

## Extensões ao contrato usadas pelo protótipo (incorporadas ao rascunho.2 do YAML, exceto a regra do 423)

- `X-PCPR-Versao-Esperada` no POST `reservar` → 409 `conflito_de_versao` (T4b). O contrato não
  dá ao n8n como dizer "qual versão eu vi no evento".
- `recurso: {tipo, id}` opcional no corpo de `POST /excecoes` (liga a exceção ao registro).
- Cabeçalho de resposta `Idempotency-Replayed: true` em repetições.
- Regra de impressão da requisição para multipart (campos + SHA-256).
- Respostas guardadas por `Idempotency-Key`: 2xx e 409 (desfechos de negócio); **423 não é
  guardado** (nada aconteceu; repetir depois de religar deve funcionar).

## Limitações

- **Simuladores em memória**, não o PCPR: a API v1 ainda não existe. Nada foi testado contra o
  sistema real, contra a outbox real nem contra um canal real.
- **n8n com SQLite** (padrão da imagem). Produção deve usar **PostgreSQL** próprio (plano de
  implantação); a corrida da dedup e a latência em rajada podem mudar com ele.
- **Runner de código `internal`** (obsoleto no 2.x); produção deve usar runner externo.
- **Uma máquina só** (Windows + Docker Desktop, notebook compartilhado com outra sessão de
  trabalho): latências e memória variam entre rodadas (tabela acima) e não representam a VPS.
- **Fuso**: `zoneinfo` no Windows precisa do pacote `tzdata` (o `.venv` do projeto tem).
- Remetente de recebimento: a verificação de contato é simulada (prefixo `+5500999` →
  quarentena); a importação documental não é exercitada.
- `POST /comunicacoes/{id}/entrega`: a suíte principal não o usa (o canal simulado não manda
  status de entrega); desde o WA-3 o W8 o usa contra o simulador da Graph API (TW5).
- T10 derruba o n8n com `docker kill` (pior caso). Desligamento gracioso (`docker stop`, 30 s)
  não foi testado separadamente.

## WhatsApp oficial (WA-3) — pronto e desligado

Frente WA-3 do [plano de implantação](../plano-implantacao.md), executada em 17/10/2026
(rodada final 23:21–23:27, `resultados/resultados-whatsapp.json`, saída 0). A política oficial
proíbe órgãos policiais na WhatsApp Business Platform ([viabilidade](../whatsapp-viabilidade.md),
seção 1): o objetivo foi deixar a integração **pronta e comprovada contra um simulador**, exportada
**desligada**. Nenhuma chamada à Meta (Graph API simulada em `127.0.0.1:8767`; dentro do contêiner,
`graph.facebook.com`, `graph.whatsapp.com`, `lookaside.fbsbx.com` e `facebook.com` apontavam para
`127.0.0.1`; o SSRF do n8n só liberava `host.docker.internal`; o log do n8n não menciona
"facebook"), nenhuma conta, nenhum número real (só `+5500…`, DDD 00 inexistente), nenhuma
biblioteca não oficial. Segredos sintéticos gerados a cada execução e ausentes do relatório.

### Executado × só desenhado

| Item | Situação |
|---|---|
| Simulador da Graph API: `POST /v21.0/{id}/messages` (template, text, document), Bearer obrigatório (190), modelo só `APPROVED` (132001/132000), janela de 24 h (131047 **síncrono ou assíncrono**, configurável), `POST /{id}/media`, `GET /{media_id}` com URL que expira (300 s, configurável) e download só com Bearer (404 vencida), webhooks oficiais assinados `X-Hub-Signature-256`, reentrega idêntica, status fora de ordem, lote misto, verificação GET | **Executado** (`simulador_graph.py`; conferido pelo TW0) |
| PCPR simulado: canal `whatsapp` ligado/desligado/**bloqueado (padrão)** em `/estado` e `canais_entrada`; `aguardando_envio_manual` + "enviado por outro meio" (WA-1); contato verificado com opt-in; `mensagem.whatsapp` na reserva; URL assinada do anexo; wamid → comunicação; `/entrega` idempotente sem regressão; `GET /comunicacoes?provedor_mensagem_id=`; `/recebimentos/sem-arquivo`; webhook direto (V2) com HMAC, fila de download e dedup | **Executado** (`simulador_pcpr.py`) |
| W2 com desvio por canal; W6 (envio), W7 (webhook, V1), W8 (status), gerados por código, importados e publicados num n8n 2.43.7 descartável | **Executado** (`construir_workflows.py --whatsapp`) |
| TW0–TW13 com asserções no estado dos simuladores e varredura do banco/disco do n8n | **Executado** (`testar_whatsapp.py`) |
| Export de W2, W6, W7 e W8 com `"active": false`, sem segredo e sem `facebook.com` | **Executado** (`docs/automacao/n8n/`) |
| Meta real: app, WABA, número, verificação de empresa, modelos aprovados, preços, limites (*tiers*), qualidade, mTLS, tempo-limite real do webhook | **Não feito** — proibido até o portão de ativação |
| Porta `gestao/integracoes/whatsapp`, `ContatoVerificado` com opt-in, renderizador `para_whatsapp` no PCPR | **Só desenhado** (o simulador do PCPR é a referência executável) |

```sh
.venv/Scripts/python.exe docs/automacao/prototipo/testar_whatsapp.py      # ~5 min
#   --sem-exportar | --manter | --apenas TW1,TW8 (TW13 precisa da bateria inteira)
```

Portas 5678, 8765 e 8767 livres; o script recusa rodar se o contêiner `pcpr-prototipo-n8n` já
existir. Mesmos contêiner, volume e ambiente do n8n da suíte principal, mais `--add-host` para o
sumidouro dos domínios da Meta.

### Resultados TW0–TW13 (rodada final)

"Mensagem" = registro na Graph API simulada (aceita ou recusada). V1 = webhook da Meta no n8n
(W7); V2 = webhook da Meta direto no PCPR.

| ID | Cenário | Resultado | Evidência |
|---|---|---|---|
| TW0 (extra) | O simulador aplica as regras | **Passou** | sem Bearer → 401/190; texto e documento fora da janela → 400/131047; modelo `PENDING` → 132001; parâmetros errados → 132000; modelo aprovado → 200 + wamid; upload → id; `GET /{media_id}` com SHA-256 certo; download sem Bearer 401, com Bearer 200 e bytes iguais, URL vencida 404; assinatura `sha256=` conferida de forma independente |
| TW1 | Modelo enviado 1× e wamid registrado | **Passou** | 1 mensagem `template` `pcpr_km_vespera_v1` com 2 variáveis (nome, link do km), `biz_opaque_callback_data: com:<id>`; 1 reserva, 1 resultado; `provedor_mensagem_id` = wamid e mapeamento wamid → comunicação no PCPR |
| TW2 | Evento duplicado → 1 mensagem | **Passou** | mesmo evento 2× → 202/202, continua 1 mensagem; 5 entregas simultâneas → 1 mensagem; evento com outro id → reservar 409 `ja_processada`, 1 mensagem |
| TW3 | Fora da janela: modelo, nunca 131047 em laço | **Passou** | (a) pedido de texto, janela fechada → só 1 modelo, nenhum texto tentado; (b) PCPR achava a janela aberta, Meta não (síncrono) → 1 texto recusado 131047 → 1 modelo aceito, `enviada`; (c) variante assíncrona → texto aceito, `failed`/131047 por webhook → W7 → W8 → PCPR marca `falhou` e agenda **uma** substituta por modelo → enviada; (d) sem modelo → **0 chamada** à Graph API, `falhou` + exceção "fora da janela de 24 h e sem modelo aprovado (evita o erro 131047)"; (e) modelo não aprovado → 1 recusa 132001, exceção, sem repetição. 131047 na bateria: **2** (uma em b, uma em c) |
| TW4 | Dentro da janela: documento por id de mídia | **Passou** | janela aberta por mensagem de texto recebida (V2 → PCPR); W6 baixou o PDF pela URL assinada do PCPR, SHA-256 conferido, 1 upload (SHA-256 = o do PCPR), 1 mensagem `document` com o id do upload; 0 modelo |
| TW5 | Status fora de ordem e duplicado → lida | **Passou** V1 e V2 | V1: `read`, `delivered`, `read` repetido, `sent` atrasado, reentrega idêntica do `delivered` → 6 webhooks 200; final **`lida`**, `entregue_em` e `lida_em` registrados, sem `falhou`; 4 `POST /entrega` = 2 novos + 2 repetições idempotentes; status **sem** `biz_opaque_callback_data` resolvido pelo wamid (`GET /comunicacoes?provedor_mensagem_id=`). V2: final `lida`; duplicatas contadas no PCPR (`read` 2×, `delivered` 2×) e ignoradas |
| TW6 | Assinatura inválida → 401, nada gravado | **Passou** V1 e V2 | segredo errado, sem assinatura, corpo alterado depois de assinado, formato `sha1=` → 401 nos 4; 0 recebimento, janela não aberta, 0 chamada ao PCPR (V1), 0 pedido de URL/download; controle positivo assinado certo → 200 e 1 recebimento. Ressalva V1: o n8n **gravou** os 4 corpos recusados no banco (ver TW13) |
| TW7 | Verificação GET | **Passou** V1 e V2 | token certo → 200, desafio ecoado em `text/plain`; token errado, `hub.mode` errado e desafio não alfanumérico → 403 |
| TW8 | Documento recebido → 1 recebimento | **Passou** V1 e V2 | 1 recebimento `aceito_para_processamento`, SHA-256 = o da mídia, 1 pedido de URL + 1 download, todos com Bearer; resposta ligada à comunicação pelo `context.id` (wamid); (b) mídia corrompida → SHA-256 diverge → 0 recebimento + exceção; (c) lote misto (documento + status no mesmo POST) → 200; no V1 os dois já estavam registrados quando o 200 voltou |
| TW9 | Reentrega do mesmo webhook → 1 recebimento | **Passou** V1 e V2 | 3 entregas idênticas → 200/200/200, **1** recebimento. V1: 3 `POST /recebimentos` (2 repetições idempotentes) e **3 downloads**; V2: o PCPR barrou na entrada → **1 download** |
| TW10 | URL de mídia vencida → pede nova | **Passou** V1 e V2 | 2 pedidos de URL, downloads `[404, 200]`, 1 recebimento |
| TW11 | Canal bloqueado → 0 chamada à Graph API (WA-1) | **Passou** | (a) padrão do simulador `whatsapp: bloqueado` (saída e entrada) → comunicação nasce `aguardando_envio_manual`, 0 evento, reconciliação `{"devidas": 0}`; tela WA-1 devolve texto + link `wa.me`; "enviado por outro meio" → `feita_a_mao`, `origem: outro_meio`; (b) bloqueado depois do evento → reservar **409 `canal_bloqueado`** → `aguardando_envio_manual`, sem resultado; (c) entrada bloqueada → webhook V2 403 e API 409, nada gravado; (d) `desligado` ≠ bloqueado → 423, segue `agendada`; religado → reconciliação `{"devidas": 1}` → 1 mensagem. Total de mensagens com o canal bloqueado: **0** |
| TW12 | Contato sem opt-in → não envia | **Passou** | sem opt-in, opt-in revogado, não verificado → reservar 409 `regra_violada` (`motivo: contato_nao_verificado`), estado `sem_contato`, 1 exceção `contato_nao_verificado` cada, 0 mensagem |
| TW13 | Retenção no n8n: V1 × V2 | **Passou** (as asserções abaixo) | ver a próxima tabela |

**Asserções do TW13**: (1) nenhuma credencial que o n8n usa para falar com alguém (token da API,
segredo HMAC dos eventos, chave do n8n, chave do canal, token da Graph API, App Secret, chave do
verify token) em execução ou disco, em nenhuma varredura; (2) **0** ocorrência de dado de entrada
V2 no n8n; (3) controle positivo: a rodada M1 deixou rastro antes do *hard-delete* (a varredura
enxerga o que procura); (4) depois do *hard-delete* de 1 min, **nada** sobrou; (5) com
`EXECUTIONS_DATA_PRUNE=false`, nada da rodada M2 ficou.

### V1 × V2: o que ficou no n8n

Método: depois de cada bloco, cópia de `~/.n8n` do contêiner; contagem de marcadores sintéticos
(prefixos de telefone por variante, wamids, tokens de URL, ids de mídia, nome do perfil, texto
dos PDFs, credenciais) nas tabelas de execução **sem** a coluna `workflowData`, nas demais tabelas
(sem definições de workflow), nos arquivos (`storage/`, logs; sem o banco e o `config`) e dentro
de trechos **base64 decodificados** (o Raw Body do webhook fica inline no banco em base64). O n8n
serializa a execução com deduplicação de strings, então uma ocorrência ≈ uma execução que guardou
o dado. Varreduras a 54 s, 75 s e 93 s da subida — antes do 1º ciclo de *hard-delete* (15 min).
Números = o que **cada bloco acrescentou** (texto / base64).

| Dado | Bloco V1 (webhook no n8n, W7/W8) | Bloco V2 (webhook no PCPR) |
|---|---|---|
| Telefone do remetente (wa_id) | **12 / 24** | **0 / 0** |
| wamid da mensagem recebida | **12 / 12** + 8 no disco (texto dos PDFs) | **0 / 0** |
| URL de mídia (lookaside, com token) | **11 / 11** | **0 / 0** |
| id de mídia | **23 / 23** | **0 / 0** |
| Nome do perfil | **12 / 12** | **0 / 0** |
| Documento recebido (PDF) | **8 arquivos** no disco (`storage/workflows/pcprWhatsWebhk01/…`) | **0** |
| Status de mensagens enviadas: wamid / telefone do destinatário | 15 / 18 (+ 8 / 7 em base64) | **0** (os status vão ao PCPR) |
| Verify token (query do GET de verificação) | **3** | **0** |
| Envio pelo W6, comum às duas: destino / link do km / token de reserva | 18 / 8 / 4 | 3 / 6 / 3 |
| Demais tabelas (fora de `execution_*`) | 0 | 0 |

Linhas de execução no fim do bloco V2 (todas `status = running` **e** `deletedAt` preenchido):
W1 29, W7 24, W2 23, W6 17, W8 8, W3 2. O bloco de envio (W6) deixou 12 destinos, 12 links do
km, 10 tokens de reserva, 1 URL assinada e 1 PDF no disco; e o W3 deixou **o token do disparo
manual** (2), que chega em cabeçalho do webhook — achado também para a suíte principal.

**O "running" se repete — e a causa foi achada no código do n8n 2.43.7** (lido na imagem, não
suposto): `active-executions.js` cria a execução no banco **ao começar**, com os dados de entrada
(corpo do webhook; itens passados a sub-workflow), e marca `running`; no fim, com
`saveData…="none"`, `execution-lifecycle-hooks.js` chama `deleteInFlightExecution`, que, com
`EXECUTIONS_DATA_PRUNE=true` (padrão), só grava `deletedAt = agora − buffer` (soft delete: dados
e binários ficam, status continua `running`); a exclusão física (`executions-pruning.service.js`)
roda a cada `EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL` = **15 min**. Com a poda desligada, o
mesmo método apaga na hora. Não depende do modo de resposta: W4 (`onReceived`, T13) e W7
(`responseNode`) ficaram iguais. W2 não tinha aparecido no T13 só porque sua entrada (vinda do W1)
tem apenas ids; o destino nasce dentro da execução e não é gravado com `saveExecutionProgress=false`.

**Mitigação medida** (mesmo volume, contêiner recriado só com a variável trocada):

| Configuração | Logo após uma rodada V1 + 1 envio | Depois |
|---|---|---|
| `EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL=1` (M1) | presente (22 s após subir: tudo dos blocos anteriores + a rodada M1, 5 + 7 em base64 no banco e 2 no disco) | **0 em tudo, banco, base64 e disco** (varredura a 101 s) |
| `EXECUTIONS_DATA_PRUNE=false` (M2) | **0** (varredura a 21 s) | — |

### Recomendação

1. **Recebimento pela V2** (Meta → PCPR). Evidência: 0 ocorrência de dado de entrada no n8n
   contra dezenas na V1, inclusive os documentos no disco e até os corpos **recusados** por
   assinatura inválida; o PCPR registra de forma durável antes do 200 e baixa a mídia uma vez
   só (TW9: 1 download × 3 na V1); o n8n não precisa de webhook público. Custo: o PCPR guarda o
   token da Graph API (para a mídia) e o App Secret — os dois já seriam segredos do PCPR em
   produção (ADR 0010) — e o código de verificação/download sai do n8n para o PCPR. W7/W8 ficam
   exportados como alternativa testada.
2. **No n8n de produção**: `EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL=1` (poda continua para o
   que é salvo; retenção do que não é salvo ≤ ~1–2 min), porque o **envio** (W6, sub-workflow do
   W2) continua no n8n nas duas variantes e grava destino, link-credencial e token de reserva.
   `EXECUTIONS_DATA_PRUNE=false` zera na hora, mas desliga a poda dos erros salvos de W1/W3 e
   deixa para sempre o que já estava marcado — só com limpeza externa. Vale também para a suíte
   principal: com essa variável o T13 passou na rodada final (23:31–23:36).
3. Não confiar só em `saveData…="none"`: no T13 e no TW13, as tabelas de execução e a pasta
   `storage/` entram na varredura de segurança antes de qualquer ativação.

### Achados do n8n 2.43.7 e de desenho (WA-3)

- **Nós oficiais do WhatsApp não servem aqui** (código da imagem): o Trigger usa o id do nó como
  verify token, compara a assinatura com `!==`, quando ela não confere só deixa de rodar o fluxo
  (sem recusa explícita; resposta HTTP não medida) e, ao publicar, chama
  `/{app-id}/subscriptions` na Graph API; o nó de envio fixa `graph.facebook.com/v13.0`. Usados
  Webhook + Crypto + HTTP Request.
- **Verify token derivado**: Code node não lê credencial e o Webhook não autentica por query →
  `verify_token = hex(HMAC-SHA256(chave da credencial, "pcpr-whatsapp-verify-token-v1"))`
  calculado pelo nó Crypto; nada em texto no workflow.
- **HMAC do webhook sobre o binário** do Raw Body (Crypto v2 aceita `binaryData` em `hmac`):
  bytes exatos, inclusive com acentos no nome do perfil.
- **200 só depois do PCPR** (Merge de 4 entradas → Respond, testado com lote misto): como o n8n
  não guarda a execução, a reentrega da Meta é a única retentativa possível na V1.
- **Remove Duplicates antes do passo durável perde mensagem** (grava a chave ao passar): a dedup
  da entrada é a `Idempotency-Key` por wamid no PCPR.
- **Sem retentativa no `POST /messages`** (a Cloud API não tem chave de idempotência); upload de
  mídia pode repetir.
- **131047 síncrono ou assíncrono**: a documentação consultada não deixa claro; o desenho cobre os
  dois (troca única por modelo no W6; `failed` → o PCPR agenda substituta por modelo).
- **Formato do `sha256` da Meta** (hex ou base64) não está fixado na documentação consultada: W7 e
  PCPR aceitam os dois.
- Erro de desenvolvimento achado pelos testes: um nó **Set sem "incluir outros campos"** antes do
  Code descartava os status no W8 (TW3c e TW5-V1 falharam numa rodada parcial; corrigido lendo
  do gatilho).

### Rodadas e o que falhou no caminho

Rodadas parciais: TW3 e TW5-V1 falharam (bug do W8 acima). 1ª rodada completa (≈22:55–23:00):
tudo passou **exceto TW9-V1** — a 3ª entrega ficou sem resposta: o `POST /recebimentos` do W7
esperou 60 s (log do n8n: conexão abortada e depois `timeout of 60000ms exceeded`) e o simulador
desistiu junto. Não se repetiu em 75 entregas seguidas (25 × 3) nem nas rodadas seguintes;
suspeita de conexão presa na ponte do Docker Desktop, **não confirmada**. Mudança: esse nó passou
a 20 s × 3 tentativas (a Meta não espera 60 s por um webhook) e o simulador espera até 120 s.
2ª rodada completa (23:05–23:10): TW0–TW13 passaram. 3ª (≈23:16–23:21): TW13 **falhou por defeito
da varredura** — a busca por base64 via "núcleos" de codificação confundiu `SINTETICA-V2` com
`SINTETICA-V1` (os núcleos cortam o último caractere); trocada por decodificação dos trechos
base64. Rodada final (23:21–23:27): TW0–TW13 passaram.

### Suíte principal depois do WA-3

Mudanças que tocam a suíte principal: o simulador do PCPR passou a rotular as comunicações dela
como `email` (antes, rótulo fictício `whatsapp`) e o WhatsApp do simulador nasce **bloqueado**; o
T9 usa `canal: email` (chave `recebimento:email:<id>`; o remetente continua telefone sintético,
que é o marcador do T13); o W2 ganhou o desvio para o W6; `testar_prototipo.py` ganhou
`--relatorio` (regressão sem sobrescrever `resultados/resultados.json`).

Regressão (17/10/2026 23:10–23:15, depois de todas as mudanças nos arquivos que a suíte
principal usa; `testar_prototipo.py --sem-exportar --relatorio <temporário>`; resumo em
`resultados-whatsapp.json` › `regressao_suite_principal`): **T1–T12 passaram** (T11: 18 testes;
T9 com chave `recebimento:email:<id>`); **T13 continua falhando** pelo achado conhecido
(`destino: 2` em `pcprRecebimento1|running|webhook`) — não foi mascarado; a causa está explicada
acima. Depois, com `EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL=1` no ambiente do protótipo, a
rodada completa de 23:31–23:36 deu **13/13** (ver "Resultados da suíte principal").

### Extensões ao contrato usadas pela WA-3 (propostas; o YAML não foi alterado nesta frente)

- `mensagem.whatsapp` na reserva: `forma` (`modelo`/`texto`/`documento`), `janela_aberta_ate`
  (o que o PCPR sabe da janela de 24 h), `modelo {nome, idioma, categoria, parametros}`, `texto`,
  `legenda`; `anexos[].url_assinada` curta para o documento.
- Estado `aguardando_envio_manual` (canal bloqueado; WA-1) ao lado de `feita_a_mao` com
  `origem: outro_meio`, `registrado_por`, `registrado_em`.
- 409 `regra_violada` com `motivo: contato_nao_verificado` no reservar (sem opt-in, revogado ou
  não verificado) e estado `sem_contato`; exceção aberta pelo PCPR.
- `GET /comunicacoes?provedor_mensagem_id=<wamid>` (status sem `biz_opaque_callback_data`).
- Impressão da requisição de `/comunicacoes/{id}/entrega` = (mensagem, status), sem
  `ocorrido_em`: a Meta repete status com outro horário e a repetição não pode virar 422.
- `failed` com 131047 numa mensagem livre → o PCPR agenda **uma** substituta por modelo
  (`substitui`).
- Variante V2: rota pública do PCPR `GET|POST /canais/whatsapp/webhook` (fora de
  `/api/automacao/v1`, sem token de serviço; autenticação = `X-Hub-Signature-256`).

### Limitações (WA-3)

- **Simulador ≠ Meta.** Formatos e códigos seguem a documentação resumida na viabilidade (§6);
  o comportamento real (131047 síncrono × assíncrono, formato do `sha256`, tempo-limite e
  política de reentrega do webhook, ordem de status, `biz_opaque_callback_data`) não foi
  confirmado contra a Meta.
- **Preços, limites (*tiers*), vazão, qualidade e aprovação de modelos** não foram exercitados.
- Um processo só, SQLite, runner interno, notebook Windows + Docker Desktop (o mesmo da suíte
  principal); o tempo-limite do webhook da Meta não é conhecido — o simulador espera até 120 s.
- A V2 foi provada no **simulador** do PCPR; no PCPR real ela exige endpoint público com TLS
  válido, fila durável (outbox) para o download e antivírus antes da importação (10-6).
- Mensagens com mais de um anexo, mídia acima de 25 MiB (`/recebimentos/sem-arquivo`
  `acima_do_limite`), mídia vencida (> 7 dias) e áudio/vídeo/localização não foram exercitados.
- Execução cortada por queda do n8n no meio de um W6/W7 não foi medida no TW13.
