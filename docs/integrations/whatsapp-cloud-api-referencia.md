# WhatsApp Business Platform — Cloud API: referência para o adaptador

Pesquisa feita em **18/10/2026** só em documentação oficial (Meta for Developers, repositório
público do n8n e docs.n8n.io). Não criamos conta, não chamamos nenhuma API e não enviamos nada.

A Meta mudou a documentação de `developers.facebook.com/docs/whatsapp/...` para
`developers.facebook.com/documentation/business-messaging/whatsapp/...`. As URLs antigas
redirecionam (HTTP 200 depois do redirect, conferido em 18/10/2026). Cada página também existe
em Markdown: é só acrescentar `.md` ao fim da URL. O índice completo está em
`https://developers.facebook.com/documentation/business-messaging/whatsapp/llms.txt`.

**Como citamos as fontes.** Cada fato traz um rótulo `[Fn]`. A tabela abaixo dá a URL de cada
rótulo. Todas foram **consultadas em 18/10/2026**.

| Rótulo | URL (base `https://developers.facebook.com`) |
|---|---|
| F1 | `/docs/graph-api/changelog/versions` |
| F2 | `/docs/graph-api/guides/versioning` |
| F3 | `/documentation/business-messaging/whatsapp/messages/send-messages` |
| F4 | `/documentation/business-messaging/whatsapp/messages/text-messages` |
| F5 | `/documentation/business-messaging/whatsapp/messages/document-messages` |
| F6 | `/documentation/business-messaging/whatsapp/messages/interactive-reply-buttons-messages` |
| F7 | `/documentation/business-messaging/whatsapp/reference/whatsapp-business-phone-number/message-api` |
| F8 | `/documentation/business-messaging/whatsapp/templates/overview` |
| F9 | `/documentation/business-messaging/whatsapp/templates/components` |
| F10 | `/documentation/business-messaging/whatsapp/templates/template-media` |
| F11 | `/documentation/business-messaging/whatsapp/templates/template-categorization` |
| F12 | `/documentation/business-messaging/whatsapp/getting-opt-in` |
| F13 | `/documentation/business-messaging/whatsapp/business-phone-numbers/media` |
| F14 | `/documentation/business-messaging/whatsapp/reference/media/media-api` e `/reference/media/media-download-api` e `/reference/whatsapp-business-phone-number/media-upload-api` |
| F15 | `/documentation/business-messaging/whatsapp/webhooks/overview` |
| F16 | `/documentation/business-messaging/whatsapp/webhooks/create-webhook-endpoint` |
| F17 | `/documentation/business-messaging/whatsapp/webhooks/reference/messages/status` |
| F18 | `/documentation/business-messaging/whatsapp/webhooks/reference/messages/text`, `.../document`, `.../image`, `.../interactive`, `.../errors` |
| F19 | `/documentation/business-messaging/whatsapp/support/error-codes` |
| F20 | `/documentation/business-messaging/whatsapp/throughput` |
| F21 | `/documentation/business-messaging/whatsapp/messaging-limits` |
| F22 | `/documentation/business-messaging/whatsapp/about-the-platform` |
| F23 | `/documentation/business-messaging/whatsapp/get-started` |
| F24 | `/documentation/business-messaging/whatsapp/access-tokens` |
| F25 | `/documentation/business-messaging/whatsapp/permissions` |
| F26 | `/documentation/business-messaging/whatsapp/pricing` |
| F27 | `/documentation/business-messaging/whatsapp/pricing/non-template-messages` |
| F28 | `/documentation/business-messaging/whatsapp/pricing/ai-providers` |
| F29 | `/documentation/business-messaging/whatsapp/changelog` |
| F30 | `/docs/graph-api/webhooks/getting-started` (mTLS e assinatura, Graph API genérica) |
| F31 | `/docs/graph-api/guides/secure-requests` (`appsecret_proof`) |
| F32 | `/documentation/business-messaging/whatsapp/support` |
| F33 | `/documentation/business-messaging/whatsapp/business-scoped-user-ids` |
| F34 | `/documentation/business-messaging/whatsapp/data-privacy-and-security` |
| N1 | `https://github.com/n8n-io/n8n/tree/n8n@2.43.7/packages/nodes-base/nodes/WhatsApp` (+ `credentials/WhatsAppApi.credentials.ts`) e o mesmo caminho em `master` |
| N2 | `https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.whatsapp/` (+ `/common-issues/`) |
| N3 | `https://docs.n8n.io/integrations/builtin/trigger-nodes/n8n-nodes-base.whatsapptrigger/` |
| N4 | `https://docs.n8n.io/integrations/builtin/credentials/whatsapp/` |
| N5 | `https://api.github.com/repos/n8n-io/n8n/releases/latest` |

---

## 1. Versão da Graph API, política de versão e URL base

- **URL base:** `https://graph.facebook.com/{versão}/…` [F7].
- **Versão nos exemplos atuais da documentação do WhatsApp: `v25.0`.** Usada nos exemplos de
  envio, mídia, limites e tokens [F3][F4][F5][F6][F13][F21][F24]. Algumas páginas ainda trazem
  versões antigas nos exemplos: `v23.0` em get-started e templates, `v17.0` em about-the-platform
  [F22][F23][F8]. Isso é desatualização dos exemplos, não recomendação.
- **Versão mais nova da Graph API: `v26.0`**, lançada em 29/07/2026, com expiração "TBD" [F1].
  O changelog da v26.0 só lista mudanças de anúncios (Ads in WhatsApp Status). Não encontramos
  mudança na Cloud API.
- **Datas de expiração** [F1]:

  | Versão | Lançamento | Expiração |
  |---|---|---|
  | v25.0 | 18/02/2026 | 29/07/2028 |
  | v24.0 | 08/10/2025 | 18/02/2028 |
  | v23.0 | 29/05/2025 | 08/10/2027 |
  | v22.0 | 21/01/2025 | 20/05/2027 |
  | v21.0 | 02/10/2024 | 21/01/2027 |
  | v20.0 | — | 24/09/2026 (já expirou) |
  | v19.0 | — | 21/05/2026 (já expirou) |
  | v13.0 | 08/02/2022 | 28/05/2024 (já expirou) |

- **Política de versão** [F2]:
  - Cada versão vale **no mínimo 2 anos**.
  - Uma versão deixa de funcionar 2 anos depois do lançamento da versão *seguinte*.
  - Uma chamada a uma versão expirada é encaminhada para a **versão mais antiga ainda
    disponível**.
  - Uma chamada **sem versão** usa a versão configurada no App Dashboard (Settings > Advanced).
    A Meta recomenda sempre informar a versão.
- **Versão dos webhooks é independente da versão das chamadas.** A forma do payload muda com
  ela. Exemplo: a partir de v24.0, o webhook de status não traz mais o objeto `conversation`
  [F17][F29].

## 2. Envio — `POST /{versão}/{phone-number-id}/messages`

### Cabeçalhos [F7]

- `Authorization: Bearer <token>` (obrigatório).
- `Content-Type: application/json` (obrigatório). A referência também aceita form-urlencoded e
  multipart.
- `User-Agent` (opcional).

### Envelope comum [F3][F7]

```json
{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "+5541999999999",
  "type": "<tipo>",
  "<tipo>": { },
  "context": { "message_id": "wamid...." }
}
```

- `recipient_type` aceita `individual` ou `group` [F3][F7].
- `context.message_id` é opcional. Serve para responder citando uma mensagem anterior [F7].
- **Formato do telefone:** aceita `+`, hífens, parênteses e espaços. A Meta recomenda **sempre
  enviar `+` e o código do país**. Sem o `+`, ela prefixa o código do país do número da empresa
  [F3].
- **Brasil e México:** a Cloud API pode alterar o prefixo extra do número (o 9º dígito no
  Brasil). Por isso `wa_id` pode ser diferente de `input` [F3].
- **Novidade de 2026 — BSUID (ID de usuário por portfólio):** "coming soon" para envio. O corpo
  passa a aceitar `recipient` (o BSUID) no lugar de `to`, ou junto com ele; se vierem os dois,
  `to` tem precedência [F33]. Novo erro `131062`: BSUID não suportado para esse tipo de mensagem
  [F33].

### Texto [F4]

```json
{ "messaging_product": "whatsapp", "recipient_type": "individual", "to": "+5541999999999",
  "type": "text",
  "text": { "preview_url": true, "body": "Texto até 4096 caracteres https://exemplo" } }
```

- `body` tem no máximo 4096 caracteres.
- `preview_url` é opcional. A prévia usa a primeira URL do texto, que precisa começar com
  `http(s)://`. Sem `preview_url`, a URL aparece como link clicável.

### Documento [F5]

```json
{ "messaging_product": "whatsapp", "recipient_type": "individual", "to": "+5541999999999",
  "type": "document",
  "document": { "id": "<MEDIA_ID>", "filename": "oficio_123.pdf", "caption": "Ofício (PDF)" } }
```

- Por link: troque `id` por `"link": "https://…/arquivo.pdf"`. A Meta **não recomenda** link:
  `id` tem melhor desempenho.
- `caption` tem no máximo 1024 caracteres.
- `filename` deve ter extensão; o app escolhe o ícone por ela.
- Mídia por `link` fica em cache na Meta por **10 minutos** para a mesma URL. Para forçar nova
  busca, acrescente uma query string aleatória [F3].

### Template [F8][F9][F10]

```json
{ "messaging_product": "whatsapp", "recipient_type": "individual", "to": "+5541999999999",
  "type": "template",
  "template": {
    "name": "nome_do_template",
    "language": { "code": "pt_BR" },
    "components": [
      { "type": "header", "parameters": [ { "type": "document",
          "document": { "id": "<MEDIA_ID>", "filename": "oficio.pdf" } } ] },
      { "type": "body", "parameters": [
          { "type": "text", "text": "Fulano" },
          { "type": "text", "text": "123/2026" } ] },
      { "type": "button", "sub_type": "url", "index": "0",
        "parameters": [ { "type": "text", "text": "abc%20123" } ] }
    ] } }
```

**Parâmetros do corpo:**

- Formato **posicional** (`{{1}}`, `{{2}}`, …): os valores vão na ordem dos marcadores. É o
  padrão quando o template não define formato [F8].
- Formato **nomeado** (`{{primeiro_nome}}`): cada valor leva `"parameter_name"`, em qualquer
  ordem [F8].
- Também existem os tipos `currency` e `date_time` [F10].

**Botão URL** [F9]:

- No máximo 2 botões URL por template.
- Cada URL aceita 1 variável, sempre **no final**, e tem no máximo 2000 caracteres. O rótulo tem
  no máximo 25.
- No envio, o componente é `type: button`, `sub_type: url`, com `index` em string.
- **O valor precisa ir percent-encoded** (espaço → `%20`, `ç` → `%C3%A7`). Sem isso, o envio
  falha.

**Cabeçalho de documento:** o exemplo oficial de cabeçalho de mídia usa `image` [F10]. O
cabeçalho de `document` vem da mesma estrutura, por analogia. Os tipos `IMAGE`, `VIDEO`, `GIF` e
`DOCUMENT` são aceitos na criação [F9]. Ver "Não confirmado".

**Para criar** um template com cabeçalho de mídia, o exemplo precisa ser enviado pela Resumable
Upload API (`header_handle`), não por `/media` [F8][F9].

### Botões de resposta (interactive) [F6]

```json
{ "messaging_product": "whatsapp", "recipient_type": "individual", "to": "+5541999999999",
  "type": "interactive",
  "interactive": { "type": "button",
    "header": { "type": "document", "document": { "id": "<MEDIA_ID>" } },
    "body": { "text": "até 1024 caracteres" },
    "footer": { "text": "até 60 caracteres" },
    "action": { "buttons": [
      { "type": "reply", "reply": { "id": "confirmar:123", "title": "Confirmar" } },
      { "type": "reply", "reply": { "id": "corrigir:123", "title": "Corrigir" } } ] } } }
```

- No máximo **3 botões**.
- `id` tem no máximo 256 caracteres.
- `title` tem no máximo 20 caracteres e precisa ser único.
- O cabeçalho pode ser `text`, `image`, `video` ou `document`.
- A resposta do usuário chega no webhook como `interactive.button_reply.{id,title}` [F18].

### `biz_opaque_callback_data`

- **Existe.** É uma string livre que a Meta não processa: só a devolve no webhook de **status**
  (`statuses[].biz_opaque_callback_data`) [F17].
- **Limite: 512 caracteres.** O changelog de 26/01/2024 registra a mudança "de 256 para 512"
  [F29].
- Vale para mensagens livres desde 14/11/2023 [F29]; antes valia só para templates.
- **Posição no corpo:** nível superior, irmão de `type`. Isso é inferência: o esquema publicado
  em [F7] não lista o campo. Ver "Não confirmado".

### Resposta de sucesso [F3][F4]

```json
{ "messaging_product": "whatsapp",
  "contacts": [ { "input": "+5541999999999", "wa_id": "5541999999999" } ],
  "messages": [ { "id": "wamid.HBgL...", "message_status": "accepted" } ] }
```

- **A resposta só significa "aceito", não "entregue".** A entrega chega pelo webhook [F3].
- `messages[].id` é o **wamid**, que aparece depois nos webhooks [F3].
- `contacts[].wa_id` pode ser diferente de `input` [F3]. Com BSUID, `wa_id` pode faltar e passa a
  vir `user_id` [F33].
- `message_status` só aparece em templates sob *pacing*. Valores: `accepted`,
  `held_for_quality_assessment`, `paused` [F3][F7].
- **A ordem de entrega não é garantida.** Para garantir a sequência, espere o status `delivered`
  antes de mandar a próxima mensagem [F3][F8].
- **TTL (tempo de tentativa de entrega):**
  - 30 dias por padrão; 10 minutos para templates de autenticação.
  - Dá para personalizar o TTL de templates de autenticação e utility.
  - Sem `delivered` dentro do TTL, considere a mensagem descartada [F3].

## 3. Regras: janela de 24 h, templates, categorias e opt-in

- **Janela de atendimento (customer service window):**
  - Abre por 24 h quando o usuário manda mensagem (ou liga) para a empresa.
  - Cada nova mensagem do usuário reinicia a contagem de 24 h.
  - Com a janela aberta, pode-se enviar qualquer mensagem livre (texto, documento, interativa…).
  - **Fechada a janela, só template aprovado.**
  - Problema conhecido: "em casos raros" não é possível responder mesmo com a janela aberta [F3].
- **Template é obrigatório** fora da janela; é o único tipo que pode iniciar a conversa [F8][F22].
- Só templates `APPROVED` podem ser enviados. A revisão leva até 24 h. Mudanças de status chegam
  pelo webhook `message_template_status_update` [F8].
- **Categorias:** `authentication`, `marketing` e `utility` [F8][F11].
  - **Utility** precisa ser não promocional **e** específico do usuário (pedido, conta,
    transação) ou essencial/crítico [F11].
  - Os casos "essencial/crítico" incluem segurança pública, serviço público e
    conformidade legal [F11].
- **Como a mudança de categoria afeta:**
  - A Meta reclassifica templates aprovados que estão na categoria errada. De utility para
    marketing, o aviso prévio é de 1 dia [F11].
  - Desde 16/04/2025, se a empresa já foi advertida por categorizar errado, a mudança é
    **instantânea**. O status continua `APPROVED`, mas **o preço passa a ser o da nova
    categoria** [F11][F26].
  - Desde 09/04/2025, mudar para `marketing` na criação é o comportamento padrão.
    `allow_category_change` deixou de existir [F11].
  - O aviso chega pelo webhook `template_category_update` (`new_category`, `previous_category`,
    `correct_category`) e por e-mail. Há 60 dias para recorrer [F11].
  - Abuso recorrente leva a restrição: todos os utility viram marketing por 7 a 30 dias. O
    portfólio também pode ser restringido, e o erro `131064` aparece no envio [F11][F19].
  - **A empresa aceita a cobrança da categoria vigente no momento do uso** [F26].
- **Opt-in é obrigatório antes de enviar** [F12][F22]:
  - Precisa dizer com clareza que é opt-in e o **nome da empresa**, e seguir a lei local.
  - Desde a política de novembro de 2024, o opt-in pode ser genérico (não precisa citar o
    WhatsApp).
  - Meios aceitos: SMS, site, telefone (URA), presencial ou papel.

## 4. Mídia [F13][F14]

- **Upload:** `POST /{versão}/{phone-number-id}/media` em multipart, com `messaging_product=whatsapp`
  e `file=@arquivo;type=<MIME>`. Resposta: `{"id": "<MEDIA_ID>"}`.
  - O texto da página lista `type` como parâmetro obrigatório, mas o exemplo põe o MIME dentro
    da parte `file` [F13]. Mande os dois.
- **Tamanho máximo e tipos:**

  | Tipo | Formatos | Máximo |
  |---|---|---|
  | Documento | `.pdf` (`application/pdf`), txt, doc/docx, xls/xlsx, ppt/pptx | **100 MB** |
  | Imagem | JPEG, PNG (8 bits, RGB/RGBA) | 5 MB |
  | Áudio | aac, amr, mp3, m4a, ogg/opus mono | 16 MB |
  | Vídeo | mp4, 3gp (H.264 + AAC) | 16 MB |
  | Figurinha | webp | 100 KB (estática) / 500 KB (animada) |

  - Outros tipos de arquivo "podem ser enviados, mas não são suportados".
  - MIME que não confere com o arquivo dá erro `131053`.
- **Validade:**
  - Mídia enviada pela API dura **30 dias** (salvo se apagada antes).
  - **Media id recebido por webhook vale 7 dias** (antes eram 30; mudou em 09/10/2025)
    [F13][F29].
- **Consultar:** `GET /{versão}/{media-id}[?phone_number_id=…]` devolve
  `{messaging_product, url, mime_type, sha256, file_size, id}`.
  - `file_size` é **string**, segundo o esquema [F14].
  - Com `phone_number_id`, a Meta só processa o pedido se a mídia for daquele número.
- **A URL vale só 5 minutos.** Depois disso, é preciso pedir o ID de novo [F13][F14].
- **Webhooks de mídia já trazem `url`** desde 16/10/2025 [F29][F13].
- **Download:** `GET <url>` com `Authorization: Bearer <token>`. Sem o token, falha.
  - Devolve o binário, e o tipo vem em `Content-Type`.
  - Em caso de `404`: obtenha nova URL e tente de novo; se continuar, renove o token [F13][F14].
- **Formato do `sha256`:** os exemplos de webhook trazem **base64** de 44 caracteres (ex.:
  `SfInY0gGKTsJlUWbwxC1k+FAD0FZHvzwfpvO0zX0GUI=`) [F18]. Não há exemplo para o `GET /{media-id}`.
  Ver "Não confirmado".
- **Apagar:** `DELETE /{versão}/{media-id}[?phone_number_id=…]` devolve `{"success": true}`.
  Precisa da permissão `whatsapp_business_messaging` [F14].
- **Mídia recebida acima de 100 MB:** chega webhook com erro `131052` [F13].

## 5. Webhooks

### Verificação (GET) [F16]

- A Meta chama `?hub.mode=subscribe&hub.challenge=<x>&hub.verify_token=<seu>`.
- Se `verify_token` conferir: responda **200 com o `hub.challenge`** no corpo.
- Senão: responda 4xx.
- A verificação acontece sempre que alguém altera a Callback URL ou o Verify token no
  App Dashboard.

### Eventos (POST) [F16]

- Cabeçalho `X-Hub-Signature-256: sha256=<hex>`: HMAC-SHA256 do **corpo bruto**, com o
  **App Secret** como chave.
  - Compare com tudo o que vem depois de `sha256=`. O exemplo oficial está em hex minúsculo.
  - Válido → 200. Inválido → 4xx.
- O certificado TLS precisa ser válido; autoassinado não serve [F16].
- **Não existe API de histórico de webhooks.** Guarde o payload bruto [F16].
- O payload tem até **3 MB** [F15]. Um lote tem até **1000 atualizações**, mas lote não é
  garantido [F16].

### Estrutura [F15][F17][F18]

```text
object = "whatsapp_business_account"
entry[].id = WABA id
entry[].changes[].field = "messages"
entry[].changes[].value:
  messaging_product, metadata{display_phone_number, phone_number_id},
  contacts[]{profile{name[, username]}, wa_id[, user_id]},
  messages[]{from[, from_user_id], id(wamid), timestamp(string unix), type, context{from,id}?,
             text{body} | document{caption, filename, mime_type, sha256, id, url}
             | image{caption?, mime_type, sha256, id, url}
             | interactive{type: button_reply|list_reply, button_reply{id,title}}, errors[]?}
  statuses[]{id(wamid), status, timestamp, recipient_id[, recipient_user_id],
             biz_opaque_callback_data?, conversation? (<=v23 ou FEP), pricing?, errors[]?}
  errors[]? (erros de sistema/conta sem mensagem associada)
```

### Status [F17]

- **Valores:** `sent`, `delivered`, `read`, `failed`, e também `played` (áudio de voz).
- `read` implica `delivered`; o `delivered` pode nem vir.
- Em vários aparelhos, a mesma mensagem pode receber `delivered` **e** `failed`. Se veio
  `delivered`, ela chegou a pelo menos 1 aparelho [F32].
- **`pricing`:** campos `billable` (vai ser descontinuado), `pricing_model` (`PMP`), `type` e
  `category`.
  - `type` pode ser `regular`, `free_customer_service` ou `free_entry_point`.
  - `pricing` vem no `sent` e em **um só** dos dois, `delivered` ou `read`.
- **`errors[]`:** `{code, title, message, error_data.details, href}`.

### BSUID (2026) [F33]

- Desde abril de 2026, todos os webhooks trazem `user_id`, `from_user_id` e
  `recipient_user_id`, no formato `BR.<até 128 alfanuméricos>`.
- Se o usuário adotar *username*, **`from`, `wa_id` e `recipient_id` podem faltar**.
  - O telefone continua vindo se houve contato com aquele número nos últimos 30 dias, ou se ele
    está no *contact book*.
- **Suportar BSUID é "obrigatório"** para integrações diretas.

### Reentrega e desempenho

- Resposta diferente de 200 faz a Meta **tentar de novo por até 7 dias**: primeiro na hora,
  depois com frequência decrescente (backoff exponencial). Depois de 7 dias, o evento é
  descartado [F15][F16][F20].
- **Haverá duplicados**, inclusive para cada app inscrito no WABA. Deduplique [F15][F16].
- Divergência: a página genérica da Graph API fala em **36 h** [F30]. A página do WhatsApp diz
  7 dias, e é ela que vale aqui.
- **Latência exigida:** mediana ≤ **250 ms**; menos de 1% acima de **1 s** [F20].
- A Meta entrega webhooks **em paralelo**. Dimensione para 3× o tráfego de saída (status) mais
  1× o de entrada [F20].
- A ordem dos webhooks **não é garantida**. A doc não diz isso com essas palavras; concluímos
  pela entrega em paralelo e pelas regras de status acima.
- **Assinatura nas reentregas:** a sintaxe põe `X-Hub-Signature-256` em todo POST [F16]. Nada diz
  que a reentrega mude o corpo ou a assinatura. Ver "Não confirmado".

## 6. Erros [F19]

**Formato:**

```json
{ "error": { "message": "(#130429) Rate limit hit", "type": "OAuthException", "code": 130429,
  "error_data": { "messaging_product": "whatsapp", "details": "…" }, "fbtrace_id": "…" } }
```

- Monte a lógica em cima de `code` e `details`. **Não** use o código HTTP, o `error_subcode`
  (descontinuado desde v16.0) nem o título (vai ser removido).
- **Síncrono × assíncrono:** um erro pode vir na resposta do POST, pelo webhook, ou pelos dois.
  A Meta manda monitorar os dois.
  - No webhook, aparece em `value.errors`, `value.messages[].errors` ou `statuses[].errors` (em
    status `failed`).
  - **A doc não diz, código a código, qual canal cada erro usa.**

| Código | Significado oficial | Ação no adaptador |
|---|---|---|
| `131047` | Mais de 24 h desde a última resposta do destinatário (re-engagement) | Mandar template; não insistir com mensagem livre |
| `131026` | Mensagem não entregável: número sem WhatsApp, termos não aceitos ou app antigo | Sem retentativa; avisar por outro canal |
| `130429` | Limite de vazão (throughput) da Cloud API atingido | Retentar com backoff |
| `131056` | Limite por par empresa→mesmo destinatário (1 msg a cada 6 s; rajada de 45) | Retentar após 4^X s (X = 0, 1, 2…) [F22] |
| `131048` | Restrição por spam ou qualidade | Parar e alertar |
| `131049` | Não entregue "para manter o ecossistema saudável" (limite por usuário de marketing) | Esperar ≥ 24 h |
| `131050` | Usuário bloqueou marketing | Não retentar |
| `131051` | Tipo de mensagem não suportado | Erro de programação |
| `131052` / `131053` | Falha no download ou no upload de mídia | Ver `details` |
| `131057` | Conta em manutenção (ex.: upgrade de vazão, até 1 min) | Retentar |
| `131000` / `131016` / `1` / `2` | Erro desconhecido ou serviço indisponível; o `2` cobre até 5 min de manutenção [F32] | Retentar com backoff |
| `131008` / `131009` / `100` | Parâmetro faltando, inválido ou desconhecido | Erro de programação |
| `132000` | Quantidade de parâmetros diferente do template | Erro de programação |
| `132001` | Template não existe no idioma pedido ou não está aprovado | Configuração |
| `132005` | Texto traduzido longo demais | Configuração |
| `132007` | Template viola a política | Configuração |
| `132012` | Formato de parâmetro errado | Erro de programação |
| `132015` / `132016` | Template pausado / desativado por baixa qualidade | Configuração |
| `132018` | Erro de validação de parâmetros do template (v23.0+) | Erro de programação |
| `190` | Token expirado | Renovar token |
| `0` | Não autenticou | Renovar token |
| `10` / `3` / `200`–`299` / `131005` | Permissão ausente ou sem acesso ao ativo; `200` também = sem token | Revisar permissões |
| `368` | WABA restrito ou desativado por violação de política | Bloquear envios e alertar |
| `131031` | Conta bloqueada (ou PIN errado) | Bloquear envios e alertar |
| `130497` | Envio restrito a certos países | Configuração |
| `131042` | Problema de pagamento | Bloquear envios e alertar |
| `131064` | Limite por erro de categorização de template | Bloquear envios e alertar |
| `80007` / `4` | Limite de chamadas do WABA ou do app | Retentar com backoff |
| `131062` | BSUID não suportado para esse tipo de mensagem | Erro de programação [F33] |

## 7. Limites, número de teste, tokens e permissões

- **Vazão (throughput):**
  - 80 msg/s por número, por padrão; sobe automaticamente até 1000 msg/s.
  - O total inclui mensagens de entrada e de saída.
  - Número usado também no app WhatsApp Business (coexistência): 20 msg/s fixos [F20].
- **Limite por par:** 1 mensagem a cada 6 s para o mesmo usuário (~600/h), com rajada de até 45.
  Acima disso, erro `131056` [F22].
- **Chamadas de gestão:** 200 chamadas/h por app por WABA; 5000/h se o WABA estiver ativo [F22].
- **Limite de envios (messaging limit):**
  - Conta destinatários únicos **fora da janela** em 24 h móveis.
  - Vale para o **portfólio**, desde 08/10/2025.
  - Níveis: 250 → 2.000 (verificação ou caminho de escala) → 10 mil → 100 mil → ilimitado.
  - O campo `whatsapp_business_manager_messaging_limit` (v24.0+) substitui
    `messaging_limit_tier` [F21][F29].
- **Número de teste:** o get-started cria um WABA de teste e um número de teste [F23].
  - Eles têm "limites relaxados" e **não exigem forma de pagamento** para enviar templates [F22].
  - **Quantos destinatários de teste?** A página atual de get-started **não diz** [F23]. O
    índice de busca ainda guarda um trecho da URL antiga dizendo "up to 5 in total", mas essa
    URL hoje redireciona para uma página sem o número. Ver "Não confirmado".
  - **Envio de teste é cobrado?** Também não está explícito. Ver "Não confirmado".
- **Tokens** [F24][F23]:
  - O token de usuário gerado em *API Setup* "expira rápido", e é preciso gerar outro "a cada
    poucas horas". **O prazo de 24 h não está escrito nas páginas atuais.**
  - Para produção: **token de usuário de sistema** (system user), de vida longa. Na geração
    você escolhe a expiração.
  - Permissões a marcar: `whatsapp_business_messaging`, `whatsapp_business_management` e
    `business_management`.
  - O token é **opaco e de tamanho variável**: não o interprete e guarde-o em campo sem tamanho
    máximo [F24].
- **Permissões** [F25][F15]:
  - `whatsapp_business_messaging`: enviar mensagens e receber webhooks `messages`.
  - `whatsapp_business_management`: metadados, templates, análises e os demais webhooks.
  - `business_management`: raramente necessária.
  - Desenvolvedor direto (só dados próprios) não precisa de App Review.
  - Para ver as permissões concedidas: `GET /debug_token?input_token=…` (campo `scopes`).

## 8. Preços

- **Modelo vigente: cobrança por mensagem** desde 01/07/2025 [F26][F29]. Varia com a categoria
  do template e o código do país do destinatário.
- Tabelas em CSV/PDF por moeda (BRL incluso) "efetivas em 01/07/2026" [F26]. Não copiamos
  valores daqui.
- **A Meta só muda preço no dia 1º de cada trimestre**, com aviso prévio de 1 a 6 meses [F26].
- **Divergência oficial: a mensagem de serviço é cobrada hoje?**
  - Página principal de preços [F26]: "All non-template messages are free" e "Utility templates
    delivered within an open customer service window are free".
  - Página "Pricing for non-template messages" [F27]: **desde 01/10/2026** a Meta cobra **cada
    mensagem de serviço** (mensagem livre, inclusive a gerada por IA de terceiros) e **cada
    utility dentro da janela**.
    - O preço da mensagem de serviço é o mesmo de utility/autenticação no mercado, sem faixas
      de volume.
    - Um exemplo da própria página cita 0,68 centavo de dólar por mensagem para o Brasil.
    - Ela também traz "Any non-template message is charged as of October 1, 2026".
  - A página de envio [F3] diz que a mensagem de serviço é cobrada na categoria `SERVICE`.
  - Hoje (18/10/2026), [F27] e [F3] indicam **cobrança já vigente**, mas [F26] ainda não foi
    atualizada.
  - **Tratamento:** registrar `pricing.category` e `pricing.type` de cada status e não presumir
    gratuidade.
- **Política "AI Providers"** [F28]:
  - Desde 11/03/2026, **mensagens livres de "AI Providers" para +55 (Brasil) são cobradas**
    (categoria `general_purpose_ai`).
  - A definição de AI Provider está nos Termos de 15/01/2026: provedores/desenvolvedores de IA
    (LLM, assistentes de uso geral etc.).
  - A página diz que **isso não muda a cobrança das demais empresas**.
  - Se um bot institucional se enquadra nessa definição é questão jurídica. **Não concluímos
    nada aqui.**

## 9. Nós oficiais do n8n

- **Versão mais recente:** `n8n@2.43.7`, publicada em 16/10/2026 [N5].
- **WhatsApp Business Cloud (ação)** [N2][N1]:
  - Mensagem: `Send` (tipos áudio, contatos, documento, imagem, localização, texto e vídeo),
    `Send Template` e `Send and Wait for Response`.
  - Mídia: `Upload`, `Download` (URL) e `Delete`.
  - **Não envia mensagens `interactive`** nem `biz_opaque_callback_data`: nenhuma ocorrência no
    código [N1].
  - O `Send and Wait` manda **texto com links** (não botões nativos) e pode acrescentar
    atribuição ao n8n [N1].
  - Para o que falta, a doc manda usar o nó HTTP Request [N2].
- **WhatsApp Trigger** [N3][N1]:
  - Assina, via `/{app-id}/subscriptions`, os eventos `messages`, `account_update`,
    `template_category_update` e outros. Usa token de app (client_credentials com
    App ID e App Secret).
  - Valida `X-Hub-Signature-256` com HMAC-SHA256 do corpo bruto e App Secret.
  - Responde ao `hub.challenge`. O `verify_token` é o id do nó.
  - **Limitação documentada:** só **1 webhook por app**. Alternar entre a URL de teste e a de
    produção sobrescreve a assinatura [N3].
- **Credencial** [N4]: API key (Access Token + WABA ID) para o nó de ação; OAuth2 (App ID +
  App Secret) para o trigger.
- **Versão fixada no código — confirmado:** em `n8n@2.43.7`, e ainda em `master` hoje,
  `GenericFunctions.ts` define `WHATSAPP_BASE_URL = 'https://graph.facebook.com/v13.0/'`. O teste
  da credencial também usa `v13.0`. O trigger usa `v19.0` [N1].
  - A v13.0 expirou em 28/05/2024 e a v19.0 em 21/05/2026 [F1].
  - Pela política [F2], essas chamadas são encaminhadas para a versão mais antiga disponível:
    hoje a **v21.0**, que expira em 21/01/2027; depois disso, a v22.0.
  - Na prática, a versão efetiva do n8n **muda sozinha** e fica sempre perto do fim da vida.
    Esse é um motivo forte para o adaptador próprio fixar a versão.

## 10. Boas práticas oficiais de segurança

- **Assinatura:** valide `X-Hub-Signature-256` em todo POST [F16][F30].
- **mTLS (opcional)** [F15][F16][F30]:
  - A Meta apresenta certificado de cliente assinado pela CA própria
    (`meta-outbound-api-ca-2025-12.pem`, que substitui o certificado DigiCert expirado em
    15/04/2026), com CN `client.webhooks.fbclientcerts.com`.
  - O mTLS é ligado **por app**, não por WABA ou por número.
- **IPs da Meta:** não há lista fixa. A doc manda consultar o AS32934
  (`whois -h whois.radb.net -- '-i origin AS32934'`) ou o geofeed (`facebook.com/peering/geofeed`).
  Avisa que **os IPs mudam** e recomenda mTLS no lugar de lista de IPs [F15].
- **Token** [F24][F23][F31]:
  - Use token de usuário de sistema. Guarde em lugar seguro, trate como opaco e de tamanho
    variável.
  - **`appsecret_proof`** é recomendado: HMAC-SHA256 do token com o App Secret, enviado em toda
    chamada. Pode ser exigido no App Dashboard com *Require App Secret* (Settings > Advanced)
    [F31].
  - **A doc não traz política de rotação** com prazo. Ver "Não confirmado".
- **App Secret:** é a chave do HMAC do webhook e do `appsecret_proof` [F16][F31]. Nunca vai para
  o cliente.
- **TLS:** Graph API aceita TLS 1.2 e 1.3 [F31].
- **Dados na Meta:** mensagens ficam no máximo 30 dias. Identificadores são apagados até 30 dias
  depois do último status [F34]. Há opções de Local Storage e No Storage [F29].

---

## O que o adaptador deve fixar

1. **Versão:** configuração única, `WHATSAPP_GRAPH_VERSION = "v25.0"`.
   - É a versão de todos os exemplos atuais e vale até 29/07/2028 [F1][F3].
   - A v26.0 (expiração "TBD") pode ser adotada depois de testada; não há mudança de Cloud API
     listada para ela.
   - Nunca chamar sem versão. O mesmo vale para a **versão do webhook** no App Dashboard
     (assumir v24.0+: sem `conversation`).
2. **URL:** `https://graph.facebook.com/{versão}/{PHONE_NUMBER_ID}/messages` e `/media`.
   Cabeçalhos `Authorization: Bearer` e `Content-Type: application/json`.
3. **Campos enviados:**
   - Sempre: `messaging_product="whatsapp"`, `recipient_type="individual"`, `to` em E.164 com
     `+`, `type`.
   - Em toda mensagem: `biz_opaque_callback_data` (≤ 512 caracteres) com o id interno da
     mensagem no outbox.
   - Documento: `id` (upload antes, não `link`) mais `filename` e `caption` (≤ 1024).
   - Template: `name`, `language.code`, `components`. Parâmetros no formato do template.
     Botão URL com `index` em string e valor percent-encoded.
   - Interactive: até 3 botões, `id` ≤ 256 e `title` ≤ 20.
4. **Campos guardados:**
   - Da resposta: `messages[0].id` (wamid), `contacts[0].wa_id` (pode diferir do `to`; no
     Brasil, o 9º dígito) e `user_id` (BSUID) quando vier.
   - **Identidade do contato:** `user_id`/`from_user_id` como chave estável, com o telefone como
     atributo opcional (pode faltar) [F33].
5. **Webhook:**
   - Ler o corpo bruto e verificar o HMAC com `hmac.compare_digest`. Gravar o payload bruto e
     responder 200 **na hora**. Processar depois, de forma assíncrona (meta: mediana ≤ 250 ms,
     menos de 1% > 1 s) [F20].
   - Deduplicar pela chave `(wamid, status)` nos status e pelo `wamid` nas mensagens recebidas.
   - Aceitar status fora de ordem. Status nunca regride; `delivered` prevalece sobre `failed`.
   - Tolerar campos ausentes e campos novos.
6. **Janela de 24 h:** guardar o horário da última mensagem *recebida* de cada contato. Fora da
   janela, usar só template. Ainda assim, tratar `131047` como verdade final.
7. **Erros:** classificar por `code` (tabela da seção 6). Ler a resposta síncrona **e** os
   status `failed`.
   - Retentativa só para `130429`, `131056`, `131057`, `131000`, `131016`, `1`, `2`, `80007` e
     `4`, com backoff exponencial (para `131056`, 4^X s).
   - Para `0` e `190`: alerta de token. Para `368`, `131031`, `131042` e `131064`: bloquear
     envios.
8. **Mídia:**
   - Pedir a URL e baixar logo em seguida (a URL vale 5 min), com Bearer.
   - Se der 404, pedir nova URL uma vez.
   - Conferir o `sha256` aceitando base64 **ou** hex. Conferir também `file_size` e `mime_type`.
   - Limite de 100 MB para PDF. Media id de webhook vale 7 dias: baixar e guardar logo.
9. **Timeouts:** a doc **não fixa timeout de cliente** para a Graph API. Os valores abaixo são
   *sugestão nossa*, não da Meta:
   - Conexão de 5 s; leitura de 30 s para envio e de 60–120 s para upload ou download de até
     100 MB.
   - O que a doc fixa é: URL de mídia 5 min, cache de link 10 min, TTL de 30 dias, reentrega de
     webhook por 7 dias e manutenção de até 5 min (erro `2`) [F13][F3][F15][F32].
10. **Segurança:**
    - Token de usuário de sistema e App Secret só em variáveis de ambiente.
    - `appsecret_proof` em todas as chamadas, com *Require App Secret* ligado.
    - mTLS no proxy se possível. Nunca lista fixa de IPs.
    - Mascarar telefone e token nos logs.
11. **Custos:** registrar `pricing.{category,type,billable}` de cada status. Não presumir que
    mensagem de serviço ou utility dentro da janela é gratuita (ver seção 8).

## Não confirmado

- **Número máximo de destinatários do número de teste.** O "até 5" aparece só em trecho de busca
  da URL antiga; a página atual [F23] não traz o número. **Também não confirmado** se o envio
  com número de teste é cobrado. Só está escrito que ele não exige forma de pagamento [F22].
- **Validade do token temporário.** A doc atual diz "expira rápido / a cada poucas horas" [F24].
  O prazo de 24 h não aparece.
- **Política de rotação de token.** Não há recomendação oficial de prazo. As opções de
  expiração do token de sistema não estão listadas.
- **Posição de `biz_opaque_callback_data`.** O esquema publicado do Messages API [F7] não lista o
  campo; o limite de 512 vem do changelog [F29]. Assumimos o nível superior do corpo.
- **Formato do `sha256` no `GET /{media-id}`.** Os exemplos de webhook usam base64; para o GET não
  há exemplo. O hash que chega no webhook e o do GET podem ser codificados da mesma forma, mas
  isso não está escrito.
- **Template com cabeçalho `document`.** O exemplo oficial de envio usa `image`; `document`
  segue por analogia [F10].
- **Canal de cada erro.** A doc não diz, código a código, se o erro vem na resposta ou por
  webhook. Por exemplo, se `131047` e `131026` chegam na resposta ou só como status `failed`
  [F19].
- **Reentrega de webhook.** Não está escrito que a reentrega mantém o mesmo corpo e a mesma
  assinatura, nem que a ordem é sempre aleatória. Esta segunda conclusão nossa vem da entrega em
  paralelo.
- **Onde se escolhe a versão do webhook** (App Dashboard). As páginas citam "webhook v24.0", mas
  não mostram o controle.
- **Preço de mensagem de serviço e de utility dentro da janela a partir de 01/10/2026.** Há
  divergência entre [F26], que diz grátis, e [F27]/[F3], que dizem cobrado. Também não
  consultamos os valores em BRL.
- **Enquadramento como "AI Provider"** [F28]: questão jurídica, fora do escopo.
- **Envio por BSUID (`recipient`).** Está marcado "coming soon" [F33]; o formato pode mudar.
