# LAB do WhatsApp (Cloud API) e da IA — ativar, operar, desligar e reverter

> Sistema de testes independente, dados fictícios (ADR 0046). Tudo nasce **simulado e
> desligado**. Nada abaixo foi executado contra a Meta ou a Anthropic: os passos são o roteiro
> para quem for ligar o LAB, com as credenciais e as autorizações próprias.

## 0. O que existe sem ligar nada

- **Simulador** (padrão em todo ambiente): `WHATSAPP_MODO` vazio = simulado. O worker
  `processar_automacao` "envia" com o adaptador simulado (wamid `wamid.SIM.…`), e as telas em
  `/automacao/` têm o simulador (entrega, leitura, falha, resposta com arquivo, mensagem de
  número desconhecido, processar a fila na hora).
- **PREVIEW/DEMO público:** sempre simulado. O startup **recusa** `WHATSAPP_MODO=cloud_api`
  com `APP_ENV=preview` (check `automacao.E001`) e `DEMO_MODE` com canal real
  (`automacao.E002`); a API de automação fica desligada (`AUTOMACAO_API_LIGADA=False`).
- **IA:** `IA_MODO` vazio = simulado (determinístico, sem rede, sem custo).

## 1. Pré-requisitos do LAB (portão de ativação)

| Item | Como conferir |
|---|---|
| Ambiente LAB dedicado, autenticado, fora do PREVIEW | `APP_ENV=lab`, URL própria com HTTPS válido, login obrigatório |
| Conta WhatsApp Business do responsável real (identidade correta, sem vínculo policial) | Painel da Meta (onboarding) |
| Número de teste ou número próprio e WABA | Painel da Meta → *API Setup* |
| Token de **usuário de sistema** com `whatsapp_business_messaging` e `whatsapp_business_management` | Painel → *System users* (não o token temporário de poucas horas) |
| App Secret (HMAC do webhook e `appsecret_proof`) | Painel → *App settings → Basic* |
| Modelos (templates) **aprovados** para cada tipo que inicia conversa | Painel → *Message templates*; ver tabela da seção 3 |
| Lista de testadores com autorização de cada pessoa | Tela `/automacao/testadores/` |
| Contato verificado + opt-in de cada testador | Tela `/automacao/contatos/` (ou a pessoa manda `ACEITO`) |
| Backup do banco do LAB e plano de reversão | seção 6 |

## 2. Configuração (variáveis de ambiente do LAB; nunca no repositório)

```bash
APP_ENV=lab
WHATSAPP_MODO=cloud_api
WHATSAPP_GRAPH_VERSION=v25.0
WHATSAPP_PHONE_NUMBER_ID=<id do número>
WHATSAPP_WABA_ID=<id da conta>
WHATSAPP_ACCESS_TOKEN=<token do usuário de sistema>
WHATSAPP_APP_SECRET=<app secret>
WHATSAPP_VERIFY_TOKEN=<texto aleatório longo, só para a verificação do webhook>
WHATSAPP_LIMITE_POR_HORA=30
WHATSAPP_REMETENTE="Sistema de testes de <responsável> (dados fictícios)"
WHATSAPP_MODELOS="viagens.diarias_liberadas=diarias_teste:pt_BR;viagens.lembrete_comprovante=lembrete_teste:pt_BR;viagens.link_km=km_vespera_teste:pt_BR"
AUTOMACAO_TRANSPORTE=interno        # ou n8n (seção 5)
AUTOMACAO_RETENCAO_DIAS=30
# IA (opcional, só com autorização de custo):
IA_MODO=anthropic
IA_API_KEY=<chave>
IA_MODELO=claude-haiku-5-5          # o mais barato; o padrão do código é claude-opus-5-5
```

Conferir sem enviar nada:

```bash
python manage.py whatsapp_check
python manage.py whatsapp_check --ping   # GET do número na Graph API (leitura, sem custo)
python manage.py ia_check
```

`whatsapp_check` mostra o modo, a versão, os ids mascarados e "configurado" no lugar de
token e segredos. Nunca imprime o valor.

## 3. Webhook (variante V2: a Meta chama o PCPR direto)

1. No painel da Meta → *Webhooks*: URL `https://<lab>/integracoes/whatsapp/webhook/` e o
   mesmo `WHATSAPP_VERIFY_TOKEN`. A Meta faz o GET de verificação; o PCPR devolve o
   `hub.challenge` só com o token certo (`/automacao/canal/` mostra a URL exata).
2. Assinar o campo **messages**.
3. Proxy: a rota não exige login; o corpo é limitado a 3 MB (`LIMITES_DO_CORPO_POR_CAMINHO`).
   **Ajuste o log de acesso** (nginx/gunicorn) para não gravar a query string nem o caminho
   `/p/<token>/` dos links pessoais (o filtro do Django já mascara; os logs de acesso não).

Tipos que precisam de modelo aprovado (iniciam conversa fora da janela de 24 h):

| Tipo (`WHATSAPP_MODELOS`) | Parâmetros do corpo, na ordem |
|---|---|
| `viagens.diarias_liberadas` | primeiro nome, nº do ofício, data da liberação, prazo de saque |
| `viagens.lembrete_comprovante` | primeiro nome, nº do ofício, prazo de saque |
| `viagens.link_km` e os avisos de viagem | ver `gestao/viagens/comunicacoes_viagem.py` (`parametros` de cada `preparar`) |

Sem o modelo configurado, a comunicação **não sai** (fica "falhou" com exceção "fora da
janela de 24 h e sem modelo aprovado") — zero chamada, zero custo.

## 4. Ligar (na tela `/automacao/canal/`, como administrador)

1. Chave **geral** → Ligada.
2. Chave **canal WhatsApp** → Ligada.
3. Cada **fluxo** → Ligado, começando em **Sombra** (prepara e registra, não envia), depois
   **Assistido** (cada envio é aprovado em `/automacao/comunicacoes/`), e só então
   **Automático**. Fluxos: `diarias_liberadas`, `lembretes_comprovante`, `km_vespera`,
   `km_lembretes`, `avisos_viagem`, `respostas_automaticas`, `recebimento_automatico`,
   `atendimento`, `assistente_whatsapp`, `ferramentas`.
4. Subir o worker: `python manage.py processar_automacao` (e `processar_ia` se a IA estiver
   ligada). Ver os compose do PREVIEW como modelo de serviço.
5. Ensaio ponta a ponta com um testador: registrar a liberação fictícia de diárias → a
   mensagem chega → responder com um PDF fictício → ver o arquivo em `/automacao/recebidos/`
   associado à prestação → confirmação no WhatsApp → `/automacao/comunicacoes/` com
   "entregue/lida".

## 5. Transporte pelo n8n (opcional)

`AUTOMACAO_TRANSPORTE=n8n`: o worker do PCPR para de enviar; o n8n reserva pela API v1.

1. Em `/automacao/credenciais/`, criar a credencial **Transporte (n8n)** (o valor aparece uma
   vez; guardar no cofre do n8n, nunca no workflow exportado).
2. `N8N_EVENTOS_URL=http://n8n:5678/webhook/pcpr-eventos` (rede interna) e
   `N8N_EVENTOS_SEGREDO=<segredo HMAC>` no PCPR; o mesmo segredo numa credencial *Crypto* do n8n.
3. Importar os workflows de `docs/automacao/n8n/pcpr/` (exportados com `active: false`),
   criar as credenciais pelo nome, revisar e só então ativar.
4. A API **não** deve ser publicada no proxy público: só a rede do n8n alcança
   `/api/automacao/v1/`.

## 6. Desligar e reverter

| Situação | O que fazer | Efeito |
|---|---|---|
| Parar tudo agora | `/automacao/` → **Desligar tudo agora** (chave geral) | Nenhum envio, associação ou ferramenta nova; status e mensagens que chegarem continuam sendo registrados |
| Parar um fluxo | `/automacao/canal/` → fluxo Desligado | Só aquele fluxo para |
| Conta/token com problema | O worker **bloqueia o canal** sozinho (erros 190, 368, 131042…) e abre exceção | Nada sai até alguém religar |
| Vazamento de link | `/automacao/links/` → **Revogar os links do período** (últimas N horas, com motivo) | Links emitidos no período param de valer |
| Credencial do n8n exposta | `/automacao/credenciais/` → Emergência ou Revogar; trocar `N8N_EVENTOS_SEGREDO` | 401 em toda chamada daquela credencial |
| Voltar ao simulador | Remover `WHATSAPP_MODO` (ou `=simulado`) e reiniciar web + worker | Nada mais sai para a Meta |
| Desfazer o LAB | Desligar as chaves, remover as variáveis, remover a assinatura do webhook no painel da Meta, revogar o token de sistema no painel | A Meta deixa de chamar; nada sai |

O banco do LAB não precisa ser apagado para reverter: a trilha e o histórico ficam.

## 7. Custos — como ficar sem custo extra

- **Simulador e PREVIEW:** custo zero (sem rede).
- **WhatsApp (Meta):** cobrança por mensagem desde 01/07/2025, por categoria do modelo e país.
  A documentação oficial está **divergente** sobre mensagens de serviço dentro da janela
  (referência, seção 8). O PCPR registra `pricing.category` e `pricing.type` de cada status
  (`/automacao/comunicacoes/<id>/`), sem presumir gratuidade. Para custo zero: não ligar o
  modo `cloud_api`; no LAB, usar só o número de teste do onboarding (a Meta diz que não exige
  forma de pagamento — **não confirmado** se é cobrado), manter `WHATSAPP_LIMITE_POR_HORA`
  baixo e a lista de testadores curta.
- **IA (Anthropic):** só com `IA_MODO=anthropic` e chave. Teto mensal por uso e global em
  `/assistencia/` (bloqueia ao atingir e cai no caminho sem IA). Valores estimados por tokens
  (ex.: `claude-haiku-5-5` US$ 0,10/0,50 por milhão de tokens de entrada/saída;
  `claude-opus-5-5` US$ 4/20) — **estimativa**, não a fatura. Para custo zero: não definir
  `IA_API_KEY`.
- **n8n Community self-hosted:** sem licença; usa a VPS existente (capacidade em
  `docs/ops/mudanca-hospedagem/capacidade-vps.md`).

Nenhuma contratação, cartão ou upgrade foi feito; qualquer ativação paga depende de
autorização explícita do responsável.
