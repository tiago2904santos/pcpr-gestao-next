# Workflows n8n para a API de automação REAL do PCPR (n8n 2.43.7)

Estes sete arquivos foram **exportados do próprio n8n 2.43.7** depois de rodarem contra a
**implementação real** da API de automação (`/api/automacao/v1`, `gestao/automacao/api/`), e não
mais contra `simulador_pcpr.py`. Todos têm `"active": false` e nenhum segredo: as credenciais são
referenciadas só por `{id, name}`. A Graph API do WhatsApp continuou **simulada**
(`docs/automacao/prototipo/simulador_graph.py`): nenhuma chamada à Meta, nenhum número real.

- Gerador: `docs/automacao/prototipo/construir_workflows.py --alvo pcpr` (não edite os JSON à mão).
- Suíte: `docs/automacao/prototipo/testar_pcpr_real.py` → `prototipo/resultados/resultados-pcpr-real.json`.
- Os fluxos do protótipo (contra simuladores) continuam em `docs/automacao/n8n/*.json`.

## Resultado atual (18/10/2026, tarde): todos os aplicáveis passaram

Depois das correções de D1–D4 e O1 na implementação (abaixo), a suíte completa saiu com código
0: **25 cenários passaram, nenhum falhou**; T6, T9, T11 e TW4 não se aplicam à API real. Os
workflows desta pasta foram reexportados dessa rodada, com `"active": false`. A chave bruta só
vale se for ASCII imprimível e até 200 caracteres; fora disso, sai a forma `…#sha256:…`, igual
no PCPR (`dominio.chave_recebimento`) e no n8n.

## 1ª rodada (18/10/2026, 08:41–08:51, horário de Brasília)

`testar_pcpr_real.py` completo, saída 1 (há falhas por defeitos reais da API, listados abaixo).
Código do PCPR que rodou: worktree `piloto-whatsapp-ia` sobre o commit `716e9ef`, impressão
SHA-256 `a02ced18…` de 59 arquivos (`gestao/automacao`, `gestao/integracoes/whatsapp`, avisos de
diárias); migrações aplicadas do zero (85 s). Export com `"active": false`, credenciais só por
referência, nenhum segredo no relatório (`segredos_no_relatorio: []`); contêineres, volume,
processos e portas removidos no fim. A guarda de rede do PCPR bloqueou `graph.facebook.com`
(download V2 da mídia pelo próprio PCPR); o log do n8n não menciona `facebook`.

| ID | Cenário | Resultado | Evidência |
|---|---|---|---|
| TW0 | Simulador da Graph API aplica as regras | **PASSOU** | sem Bearer 401/190; texto fora da janela 400/131047; modelo aprovado 200 + wamid; modelo `PENDING` 132001 |
| T1 | Evento válido → 1 envio e 1 resultado | **FALHOU (D1)** | o fluxo passou (evento entregue 1×, 1 reserva `reserva:<id>:v1:exec<n>`, 1 resultado, 1 modelo na Graph API, wamid registrado), mas os envelopes REAIS violam `evento-integracao.schema.json` |
| T2 | Mesmo evento reenviado → 1 envio | **PASSOU** | 2 reentregas pelo emissor real → 202/202 e 0 chamada nova ao PCPR; 5 simultâneas → 1 reserva 200; evento com outro id → reservar 409 `ja_processada`; sempre 1 mensagem |
| T3 | Assinatura inválida → 401, 0 envio | **PASSOU** | segredo errado, `t` de 10 min, corpo alterado, sem assinatura, `ambiente: producao`, `X-PCPR-Evento-Id` divergente → 401 nos 6; emissor real com segredo errado → evento `configuracao` + exceção `eventos-n8n:401`, sem repetir; controle positivo 202 e 1 envio; UTF-8: 401 sobre re-serialização, 202 sobre os bytes |
| T4 | Evento obsoleto → 409, 0 envio | **PASSOU** | nova versão da liberação → evento antigo: reservar 409 `obsoleta`; agendada para +3 dias não é antecipada nem aparece nas devidas; modo assistido + aprovação humana (revisão 2) → evento v1: 409 `conflito_de_versao`; v2 sai pela reconciliação |
| T5 | Automação desligada | **PASSOU** | chave geral desligada → W2 lê `/estado` e não reserva; canal desligado (geral ligada) → reservar **423** `desligada`, não guardado pela idempotência, segue agendada; religado → `{"devidas": 2}` → 1 mensagem cada |
| T6 | Canal recusa 1× e aceita | **NÃO APLICÁVEL** | o PCPR real só tem o canal WhatsApp (W6), que por desenho não repete `POST /messages`; o caminho de 3 tentativas do canal genérico não existe no alvo pcpr |
| T7 | Sempre recusa → rodadas do PCPR | **PASSOU** (adaptado ao W6) | Graph API 503/131000 nas 3 rodadas → `falha_temporaria` → o PCPR reagenda em 120 s e 480 s (relógio avançado no banco descartável) → 3ª rodada `falhou` + 1 exceção `falha_definitiva` do PCPR; 0 aceita; reconciliação final `{"devidas": 0}` |
| T8 | Evento perdido → reconciliação | **PASSOU** | evento retido; reconciliação → 1 envio; 2ª → `{"devidas": 0}`; o evento atrasado chega depois → reservar 409 |
| T9 | Arquivo devolvido 2× (W4) | **NÃO APLICÁVEL** | W4 é o canal genérico (e-mail): a API real responde 501 `integracao_inexistente` (conferido no X1); a idempotência do canal WhatsApp está no TW9 e no X1 |
| T10 | Queda do n8n no meio | **PASSOU** | `docker kill` com 4 envios aceitos na Graph API e sem resposta; 2 eventos novos falham com o n8n fora (`URLError`, pendentes); n8n volta em 43 s; reentrega de evento antigo → 202 sem efeito; reconciliação `{"devidas": 2}`; as 4 cortadas: reserva vencida (relógio avançado) → `incerta` + exceção `resultado_incerto` cada; **0 duplicado** |
| T11 | Regra da véspera | **NÃO APLICÁVEL** | função pura do protótipo; não passa pela API |
| T12 | Erro inesperado → W5 | **PASSOU** | 2× HTTP 500 no `/estado` (injetado no espião; a API não mudou) → W2 falha → W5 → `POST /excecoes` 201 no PCPR; reconciliação → 1 envio |
| T13 | Nada sensível retido no n8n | **PASSOU** | logo depois: 1 destino e 1 token de reserva nas execuções; após o *hard-delete* (247 s da subida): 0; credenciais nunca |
| TW1 | Modelo 1× e wamid registrado | **PASSOU** | `pcpr_diarias_liberadas_v1` com 4 variáveis, `biz_opaque_callback_data` `com:<id>:t1`; `GET /comunicacoes?provedor_mensagem_id=` → `{id, versao}` |
| TW2 | Evento duplicado → 1 mensagem | **PASSOU** | série 2×, paralelo 3×, outro id → 1 mensagem |
| TW3 | Fora da janela: modelo; 131047 nunca em laço | **PASSOU** | (a) janela fechada → só modelo; (b) PCPR com janela aberta (mensagem recebida pelo webhook V2) e Meta fechada → 1 texto recusado 131047 → `falhou` + exceções, sem nova tentativa; (c) 131047 assíncrono → `failed` pelo webhook V2 → `falhou`; (d) sem modelo → 0 chamada à Graph API, 409 `regra_violada`; (e) modelo não aprovado → 1 recusa 132001. Troca automática por modelo e substituta: não aplicáveis (extensões do protótipo fora do contrato) |
| TW4 | Documento por id de mídia | **NÃO APLICÁVEL** | a reserva real não traz `anexos`/`url_assinada` |
| TW5 | Status fora de ordem/duplicado → lida | **FALHOU (D2)** na V1 · **PASSOU** na V2 | V1: `read`, `delivered`, `sent` e reentrega idêntica → 200, final `lida`; o mesmo `read` com outro horário → `POST /entrega` 422 (3×) → W8 falha → **500** para a Meta (reentregaria até desistir). V2: final `lida`, duplicatas ignoradas |
| TW6 | Assinatura inválida → 401 | **PASSOU** V1 e V2 | 4 modos → 401, nada gravado, nenhuma mídia tocada; controle positivo → 1 recebimento |
| TW7 | Verificação GET | **PASSOU** V1 · **FALHOU (O1)** V2 | V1: certo 200 `text/plain`, errado/modo 403, desafio hostil 403. V2 (PCPR): certo 200, errado/modo 403, **desafio `<script>…` ecoado com 200** — critério do protótipo, não do contrato |
| TW8 | Documento recebido → 1 recebimento | **PASSOU** V1 e V2 | V1: 1 recebimento, SHA-256 igual ao da mídia, Bearer nos 2 passos, ligado à comunicação pelo `context.id`; mídia corrompida → 0 recebimento + exceção; lote misto → 200 com os dois registrados. V2: recebimento registrado e ligado; o download é do PCPR (base fixa, bloqueado pela guarda) |
| TW9 | Reentrega do webhook → 1 recebimento | **PASSOU** V1 e V2 | V1: 3 `POST /recebimentos` (2 repetições idempotentes); V2: 1 entrada (dedup por SHA-256 do corpo) |
| TW10 | URL de mídia vencida | **PASSOU** V1 · **NÃO APLICÁVEL** V2 | V1: downloads `[404, 200]`, 2 pedidos de URL, 1 recebimento. V2: o PCPR baixa de `graph.facebook.com` fixo |
| TW11 | Canal bloqueado | **FALHOU (D3)** | saída OK: `/estado` `bloqueado`, reservar 409 `canal_bloqueado`, 0 chamada à Graph API; desligado ≠ bloqueado (423; religado → 1 mensagem). Entrada: `POST /recebimentos` com o canal bloqueado → **202** (contrato: 409 `canal_bloqueado`); o webhook V2 também grava (200) |
| TW12 | Sem opt-in/verificação → não envia | **PASSOU** | sem contato, não verificado, opt-in revogado (pendente cancelada) e agendada depois da revogação → reservar 409, 0 mensagem, exceções de contato |
| TW13 | Retenção no n8n: V1 × V2 | **PASSOU** | V1 deixa rastro logo depois (wamid 35, perfil 26, URL 24, id de mídia 50, documento 9) e 0 após o *hard-delete*; **V2: 0 em todas as varreduras**; credenciais nunca. Achado corrigido no caminho: o W5 guardava as próprias execuções com o erro do fluxo (o wamid sobrevivia à poda) — agora sai com `saveData*=none` |
| X1 | `/recebimentos`: mesma chave, outro arquivo | **FALHOU (D4)** | 1º 202, repetição idêntica 202 `Idempotency-Replayed`, 1 recebimento; outro arquivo com a mesma chave → **422** (contrato: 409 `conflito_de_versao`); `canal=email` → 501 |
| X2 | Idempotency-Key > 200 | **PASSOU** | o PCPR recusa chave de 216 caracteres (422); webhook V1 com wamid de 250 → W7 → `POST /recebimentos/sem-arquivo` 202 com `receb#sha256:whatsapp:<hex>:0` (88 caracteres) |

### Defeitos da API real achados na 1ª rodada — todos corrigidos depois, com teste

As correções:
- D1: `contrato.py` traduz tipo e fluxo; os eventos de chave levam só `fluxo`;
- D2: `impressao_sem=("ocorrido_em",)` na rota de entrega;
- D3: 409 com o canal bloqueado e 423 com ele desligado;
- D4: `reuso_pelo_servico`, e o serviço responde 409;
- O1: `hub.challenge` só alfanumérico.

Os testes estão em `gestao/viagens/tests/test_automacao_garantias.py`.

- **D1 — envelopes de evento fora do esquema** (`gestao/automacao/eventos.py` e quem publica).
  `comunicacao.agendada`: `dados.fluxo = "diarias_liberadas"` não casa com `^[a-z0-9-]{1,64}$`;
  `dados.tipo_comunicacao = "viagens.diarias_liberadas"` fora do enum (o par do contrato é
  `mensagem_saque`, que a API já usa em `/reservar`). `automacao.religada`/`desligada`:
  `dados = {"motivo": …}` — falta `fluxo` (nulo = chave geral) e `motivo` é campo extra;
  `recurso.tipo = "chave_automacao"`. Contrato: `evento-integracao.schema.json`,
  `$defs/dados.comunicacao.agendada` e `$defs/dados.automacao.religada`.
- **D2 — `/entrega` com status repetido em outro horário → 422.** Requisição: 2º
  `POST /comunicacoes/<id>/entrega`, `Idempotency-Key: entrega:<id>:<wamid>:lida`, corpo com outro
  `ocorrido_em`. Resposta: 422 `entrada_invalida` (3 tentativas do W8); o W7 responde 500.
  Contrato (`/comunicacoes/{id}/entrega`): chave `entrega:<comunicacao>:<provedor_mensagem_id>:<status>`,
  `ocorrido_em` obrigatório e a regra geral "mesma chave com outra requisição → 422" — o próprio
  contrato se contradiz nesse caso. Esperado: 200 sem efeito (impressão sem `ocorrido_em`).
- **D3 — entrada com o canal bloqueado é aceita.** `POST /recebimentos` (canal whatsapp, chave
  `canal:whatsapp` bloqueada) → 202 `identificado`. Contrato (`/recebimentos`): "Canal `bloqueado`
  em `/estado.canais_entrada` → 409 `canal_bloqueado`". O webhook V2 também grava (fora do
  contrato v1).
- **D4 — mesma chave de recebimento com outro SHA-256 → 422.** Resposta: 422 "Esta
  Idempotency-Key já foi usada com outra requisição." Contrato (`/recebimentos`): "mesma chave com
  SHA-256 diferente → 409 `conflito_de_versao` … em vez do 422 genérico". Causa provável:
  `api/base.py` compara a impressão antes da rota; o 409 de `recebimentos.receber_arquivo` nunca
  é alcançado.
- **O1 (observação; não é contrato)** — o webhook V2 ecoa `hub.challenge` não alfanumérico
  (200, `text/plain`). O protótipo recusava (403). Risco baixo.

Lacunas (não violam o contrato): a reserva não traz o **idioma do modelo** (o W6 usa
`cfg_idioma_modelo`); a base da Graph API do PCPR é constante (o download V2 não pode ser testado
contra simulador); a comunicação recusada com `canal_bloqueado` continua `agendada` e sai sozinha
na primeira reconciliação depois do desbloqueio; o padrão da credencial de transporte não inclui
`recebimentos:criar` (a V1 precisa pedir).

### Como rodar de novo

```sh
# na raiz do worktree; Docker com postgres:16 e n8nio/n8n:2.43.7; portas 5679, 8770, 8775,
# 8777 e 55439 livres (a suíte recusa rodar se estiverem ocupadas)
PYTHONUTF8=1 .venv/Scripts/python.exe docs/automacao/prototipo/testar_pcpr_real.py   # ~10 min
#   --apenas T1,TW5 | --sem-exportar | --manter | --relatorio <arquivo>
.venv/Scripts/python.exe docs/automacao/prototipo/construir_workflows.py <pasta> --alvo pcpr
```

## O que cada workflow faz

| Arquivo | ID | Nome | O que muda em relação ao protótipo |
|---|---|---|---|
| `w1-entrada-de-eventos.json` | `pcprEntradaEvt01` | PCPR · Entrada de eventos | Webhook `POST /webhook/pcpr-eventos` com corpo bruto; confere `X-PCPR-Assinatura` (HMAC-SHA256 de `t + "." + corpo`, segredo numa credencial *Crypto*), frescor ±5 min, `ambiente` (`teste` no LAB) e `X-PCPR-Evento-Id`; 401 se algo falhar, 202 em seguida; deduplica por id; `comunicacao.agendada` devida → W2. **Novo:** passa ao W2 o `dados.fluxo` do evento |
| `w2-entregar-comunicacao.json` | `pcprEntregaCom01` | PCPR · Entregar comunicação | `GET /estado` → `POST /comunicacoes/{id}/reservar` (`Idempotency-Key: reserva:<id>:v<versao>:exec<execução>`, `X-PCPR-Versao-Esperada`) → 409/423 encerram sem enviar → canal da reserva `whatsapp` → W6. **Novo:** confere a chave do fluxo **da comunicação** em `/estado.fluxos`; canal que não seja WhatsApp não é enviado (falha definitiva + exceção) — o PCPR real só tem o WhatsApp; não há o caminho de 3 tentativas do canal genérico |
| `w3-reconciliacao.json` | `pcprReconcilia01` | PCPR · Reconciliação | A cada 15 min e por `POST /webhook/pcpr-reconciliar` (Header Auth): `GET /comunicacoes/devidas` → uma por vez → W2. **Novo:** passa o `fluxo` de cada item |
| `w5-erros.json` | `pcprErros0000001` | PCPR · Erros | Error Trigger de W1–W3 e W6–W8 → `POST /excecoes` (`motivo: outro`) |
| `w6-enviar-por-whatsapp.json` | `pcprWhatsEnvio01` | PCPR · Enviar por WhatsApp (oficial) | **Reescrito para o contrato.** Lê a reserva real (`ComunicacaoReservada`): `mensagem.modelo` preenchido = o PCPR acha a janela de 24 h fechada → modelo aprovado com `variaveis` p1..pN na ordem; vazio = texto livre (`mensagem.texto`), com `context.message_id` = `responder_a` quando houver. `biz_opaque_callback_data` = `idempotencia_canal` (`com:<id>:t<n>`, o formato que o webhook do PCPR reconhece). Sem documento (a reserva real não traz `anexos`) e sem troca por modelo após 131047 (dentro da janela a reserva não traz modelo). Nunca repete `POST /messages`; erro estruturado temporário → `falha_temporaria` (o PCPR reagenda); resposta ambígua → `resultado_desconhecido` + exceção |
| `w7-webhook-whatsapp.json` | `pcprWhatsWebhk01` | PCPR · Webhook WhatsApp | **Variante V1** (a recomendada é a V2, webhook direto no PCPR). Verificação GET, HMAC `X-Hub-Signature-256`, mídia em 2 passos com Bearer — **novo (13ª revisão):** acima do limite pelo `file_size` dos metadados (`--limite-midia`, padrão 10 MB como o PCPR) não é baixada e vai para `/recebimentos/sem-arquivo` com `acima_do_limite` (nós sincronizados do gerador, ainda não reexportados de uma rodada no n8n) —, `POST /recebimentos` (multipart) e `/recebimentos/sem-arquivo`, status → W8; 200 só depois do PCPR |
| `w8-status-whatsapp.json` | `pcprWhatsStatus1` | PCPR · Status WhatsApp | `delivered`/`read`/`failed` → `POST /comunicacoes/{id}/entrega`; acha a comunicação por `biz_opaque_callback_data` (**novo:** aceita `com:<id>:t<n>`) ou por `GET /comunicacoes?provedor_mensagem_id=`; sem achar → adia (o W7 responde 503) |

Fora deste conjunto: **W4** (recebimento do canal genérico/e-mail). A API real responde **501
`integracao_inexistente`** para `canal` diferente de `whatsapp` (piloto WhatsApp; conferido no X1).

### Idempotency-Key sempre ≤ 200 caracteres

O PCPR recusa chave com mais de 200 caracteres (422; conferido no X2). Toda `Idempotency-Key`
destes fluxos é uma expressão que devolve a chave legível quando cabe e, quando não cabe:

- recebimento (W7): a regra do contrato e de `gestao/automacao/dominio.chave_recebimento` —
  `receb:<canal>:<mensagem_id_canal>:<anexo_indice>` até 200; acima,
  `receb#sha256:<canal>:<hex do SHA-256 do mensagem_id_canal>:<anexo_indice>`;
- as demais (exceção com wamid, entrega, resultado, reserva, erro): até 200 como sempre; acima,
  `<1º segmento>#sha256:<resto do prefixo><hex>` da parte variável (ex.:
  `excecao#sha256:whatsapp-sha256:<hex>`, `entrega#sha256:<hex>`). O `#` no 1º segmento impede
  que um id curto parecido com `sha256:<hex>` colida com a forma com hash.

Corpo de exceção = função só da chave: a exceção do W7 cuja chave vem do wamid (a Meta reentrega
em outra execução) não leva `execucao_orquestrador`, senão a repetição seria 422 (chave reusada
com outra requisição). As exceções de W2/W6 têm o token da reserva na chave (uma por execução).

O hash é a extensão de expressão `String.hash('sha256')` do n8n (`string-extensions.js` da
2.43.7). É estável: a reentrega gera a mesma chave e o PCPR devolve a resposta guardada.

## Como importar e ativar no LAB (passo a passo manual)

Pré-requisitos: backup do n8n e `N8N_ENCRYPTION_KEY` guardada fora da máquina; PCPR do LAB com a
API publicada só para a rede do n8n.

### 1. PCPR (variáveis de ambiente)

| Variável | Valor no LAB |
|---|---|
| `APP_ENV` | `lab` |
| `AUTOMACAO_TRANSPORTE` | `n8n` (o worker interno para de enviar; só vence reservas e entrega eventos) |
| `N8N_EVENTOS_URL` | URL do W1 na rede interna, ex. `http://n8n:5678/webhook/pcpr-eventos` |
| `N8N_EVENTOS_SEGREDO` | segredo HMAC dos eventos (o mesmo da credencial `pcprHmacEventos1`) |
| `WHATSAPP_MODO`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN` | só no portão da WA-3; com `cloud_api` e os quatro preenchidos o webhook V2 confere `X-Hub-Signature-256` |
| `WHATSAPP_MODELOS` | `tipo=modelo:idioma;…` (ex. `viagens.diarias_liberadas=pcpr_diarias_liberadas_v1:pt_BR`). Fora da janela, sem modelo, nada sai |
| `WHATSAPP_LIMITE_POR_HORA` | limite de envios por hora (padrão 30) |

E o processo `manage.py processar_automacao` no ar (entrega os eventos ao n8n e vence reservas).

No PCPR (telas ou serviços): chave geral, canal `whatsapp` e cada fluxo `ligada`/modo
`automatico`; contatos verificados com opt-in; números na lista de testadores; e a credencial de
transporte do n8n (`gestao.automacao.api.credenciais.emitir`, tipo `transporte`). **Atenção:** o
padrão do transporte não inclui `recebimentos:criar` — só peça esse escopo se for usar a variante
V1 (W7 entregando arquivos); com a V2 ele não é necessário.

### 2. n8n: credenciais (criar ANTES de importar; os ids precisam bater)

| ID | Nome | Tipo | Campos | Usada em |
|---|---|---|---|---|
| `pcprApiToken0001` | PCPR · token da API de automação | Header Auth | `Authorization` = `Bearer <token de transporte do PCPR>` | W2, W3, W5, W6, W7, W8 |
| `pcprHmacEventos1` | PCPR · segredo HMAC dos eventos | Crypto | `hmacSecret` = `N8N_EVENTOS_SEGREDO` | W1 |
| `pcprWebhookInt01` | PCPR · token do disparo da reconciliação | Header Auth | `X-Disparo-Token` = valor aleatório | W3 |
| `pcprWaToken00001` | WhatsApp · token de acesso (usuário de sistema) | Header Auth | `Authorization` = `Bearer <token de sistema da Meta>` | W6, W7 — só no portão |
| `pcprWaAppSecret1` | WhatsApp · App Secret (assinatura dos webhooks) | Crypto | `hmacSecret` = App Secret | W7 — só no portão, só V1 |
| `pcprWaVerifyTok1` | WhatsApp · chave do verify token | Crypto | `hmacSecret` = chave aleatória; verify token = `hex(HMAC-SHA256(chave, "pcpr-whatsapp-verify-token-v1"))` | W7 — só no portão, só V1 |

Pela CLI: `n8n import:credentials --input=<arquivo fora do repositório>` e apagar o arquivo.

### 3. n8n: importar sem ativar

1. Ajustar o que é por instância (no gerador ou na interface; não são segredos): nós
   **Configuração** de W2, W3, W5, W7, W8 (`cfg_pcpr` = `https://<host interno>/api/automacao/v1`;
   os arquivos apontam para o espião do teste, `host.docker.internal:8775`), W6/W7 (`cfg_graph`,
   `cfg_numero_id`, `cfg_idioma_modelo`); W1 › *Preparar verificação* › `AMBIENTE_ESPERADO`.
2. `n8n import:workflow --separate --input=<pasta com os 7 JSON>`; conferir
   `n8n list:workflow --active=true --onlyId` vazio (no 2.x o import não ativa).
3. Variáveis do n8n (as mesmas do protótipo, ver `../README.md`), mais
   `N8N_SSRF_ALLOWED_HOSTNAMES=<host da API do PCPR>,<host da Graph API>` e
   `EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL=1`.

### 4. Ativar (publicar), quando aprovado

`n8n publish:workflow --id=<id>` (ou *Publish* na interface) e reiniciar o n8n. Ordem: W5, W8,
W6, W2, W1, W3 (W7 só na variante V1). Desligar: `n8n unpublish:workflow --id=<id>` ou `--all`;
no PCPR, a chave geral (reservas passam a 423, nada se perde).

## Nós oficiais do WhatsApp no n8n: por que HTTP Request

Conferido na imagem 2.43.7 durante a suíte (`nos_oficiais_whatsapp_na_imagem` no relatório) e na
referência `docs/integrations/whatsapp-cloud-api-referencia.md`, seção 9:

- o nó **WhatsApp Business Cloud** fixa `https://graph.facebook.com/v13.0/` (v13.0 expirou em
  28/05/2024; a Meta encaminha para a versão mais antiga disponível, que muda sozinha) e não
  envia `biz_opaque_callback_data` nem mensagens `interactive`;
- o **WhatsApp Trigger** usa o id do nó como verify token, assina `/{app-id}/subscriptions` ao ser
  publicado (publicar já falaria com a Meta) e só admite 1 webhook por app;
- nenhum dos dois aponta para um simulador nem permite fixar a versão vigente.

Por isso: **HTTP Request** (versão e base no nó Configuração) + **Webhook** com corpo bruto +
**Crypto** para HMAC. Recomendação mantida: recebimento pela **V2** (Meta → PCPR).

## Limitações do teste

- A Graph API é simulada; a Meta real (versões, códigos, reentrega) não foi exercitada.
- Na V2 quem baixa a mídia é o PCPR, de `https://graph.facebook.com` fixo
  (`gestao/integracoes/whatsapp/config.py`, `BASE_URL`): o download V2 não pôde ser apontado para
  o simulador. A suíte instala uma guarda de rede (`prototipo/guarda_rede/`) que bloqueia a
  resolução de qualquer host fora de 127.0.0.1 nos processos do PCPR; as tentativas bloqueadas
  aparecem em `guarda_de_rede_bloqueou` no relatório.
- T7 e T10 "avançam o relógio" no banco descartável (`proxima_tentativa_em`, `reservada_ate`) em
  vez de esperar 2/8/10 minutos; a espera calculada pelo PCPR fica registrada.
- n8n com SQLite e runner interno, numa máquina Windows com Docker Desktop.
