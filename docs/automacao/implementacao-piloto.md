# Implementação do piloto WhatsApp + IA (18/10/2026)

> Sistema de testes independente, dados fictícios (ADR 0046). Esta página diz, item a item, o
> que está **implementado**, o que foi **testado com simulador**, o que foi **validado com o
> provedor real** e o que **ainda não foi validado**. Nada foi ligado contra a Meta nem contra
> a Anthropic: **nenhum item está validado com provedor real** — isso depende do LAB
> ([roteiro](../ops/lab-whatsapp-ia.md)).

Decisões: [ADR 0047](../adr/0047-contexto-de-automacao-e-transporte.md) (contexto `automacao`,
transporte, API, links, ferramentas) e [ADR 0048](../adr/0048-ia-porta-orcamento-e-sugestoes.md)
(IA). Referência da Cloud API: [whatsapp-cloud-api-referencia.md](../integrations/whatsapp-cloud-api-referencia.md).

Legenda: **I** implementado · **S** testado com simulador/adaptador gravado (pytest) ·
**N** testado no navegador (Playwright) · **R** validado com o provedor real · — não feito.

## Primeira entrega (ponta a ponta)

| Passo | Estado | Onde |
|---|---|---|
| Liberação fictícia de diárias registrada na prestação | I S N | `viagens/prestacao.py` → `viagens/comunicacoes.py` |
| Comunicação criada na mesma transação (evento transacional) | I S | `automacao/comunicacoes.agendar` |
| Envio pelo WhatsApp simulado com reserva atômica e revalidação | I S N | `automacao/entrega.py` |
| Identificador (wamid) e status de entrega (enviada/entregue/lida/falhou), sem regredir | I S N | `entrada.registrar_status`, `dominio.proxima_entrega` |
| Comprovante sintético recebido, conferido (bytes, tamanho, sha256) | I S N | `recebimentos.baixar` |
| Associado à prestação certa (a comunicação citada), em nome de quem originou | I S N | `recebimentos.tentar_associar`, `viagens/comunicacoes._associar` |
| Confirmação ao servidor | I S | tipo `automacao.confirmacao` |
| Lembretes relacionados encerrados | I S | `encerrar_relacionadas` + `preparar` dos lembretes |
| Tela utilizável (painel, comunicação, recebido, exceções, simulador) | I S N | `/automacao/` |
| Envio real pela Cloud API | I S (gravado) | **R: não** |

## Fundação

| Requisito | Estado | Observação |
|---|---|---|
| Comunicação com tentativas e resultados | I S | `Comunicacao`, `TentativaEntrega`, `StatusEntrega` |
| Contato verificado com opt-in revogável, ligado ao servidor | I S N | `ContatoVerificado`; `SAIR` revoga; o número do cadastro é reconferido no envio |
| Lista fechada de testadores do LAB | I S N | fora de produção é sempre ligada; fora da lista = zero chamada |
| LinkAcesso (hash, escopo, validade, revogação individual/por recurso/em massa) | I S N | criado só no envio, depois de todas as recusas |
| Recebimento com identificação do remetente e quarentena | I S | desconhecido não é baixado nem respondido |
| Fila de exceções com responsável e ações | I S N | assumir, resolver, descartar; ações no próprio assunto |
| Chave geral, por canal e por fluxo; modos sombra/assistido/automático | I S N | o modo vale na hora do envio |
| Eventos transacionais + worker com lease | I S | `processar_automacao`; eventos ao n8n com HMAC (`eventos.py`) |
| API de automação v1 conforme o contrato | I S | desvios: e-mail (`/entradas`, `/assistente/mensagens`) = 501 |
| Credenciais por integração com escopos mínimos e rotação | I S | ambiente no token; emergência; só hash |
| Idempotency-Key + controle de versão | I S | chave reservada antes do efeito; 423 não guardado; `X-PCPR-Versao-Esperada` |
| Reserva atômica antes do envio | I S | `select_for_update(skip_locked)` + lease |
| Resultados e recebimentos idempotentes | I S | chave por tentativa; `receb:<canal>:<wamid>:<anexo>` |
| Reconciliação das comunicações devidas | I S | `GET /comunicacoes/devidas`; órfãos viram exceção |
| Retentativas limitadas | I S | 3 rodadas com espera 2/8/32 min |
| Resultado desconhecido → revisão humana, nunca reenvio às cegas | I S N | reserva vencida = incerta; a Meta resolve pela referência |
| Desligar bloqueia efeitos novos e ainda registra resultados | I S | status, mensagens e `/resultado` seguem aceitos |
| Desconhecido da lista = zero chamada à Meta | I S | teste com espião do adaptador |

## WhatsApp (`gestao/integracoes/whatsapp/`)

| Requisito | Estado | Observação |
|---|---|---|
| Adaptador simulado e Cloud API real (versão fixa v25.0, `appsecret_proof`) | I S | real só com credenciais e fora do PREVIEW |
| Configuração validada, segredos fora do repositório | I S | `settings.WHATSAPP` ← `WHATSAPP_*`; check E001/E002/E003 |
| Texto e modelo (template); links pessoais; mídia recebida; mensagens recebidas | I S | envio de documento como mídia: **não** (o link do portal é preferido) |
| Status sem regressão com eventos fora de ordem | I S | `delivered` prevalece sobre `failed` |
| Correlação mensagem do provedor ↔ comunicação | I S | `biz_opaque_callback_data` = `com:<id>:t<n>` |
| GET de verificação e assinatura sobre o corpo bruto | I S | `X-Hub-Signature-256`; filtro por `phone_number_id` |
| Deduplicação; 2xx só depois do registro durável | I S | `EntradaWebhook` (sha256 único) antes do 200 |
| Arquivo malformado, grande, repetido ou malicioso | I S | bytes mágicos, teto, sha256, nome seguro, host da Meta |
| Encaminhamento humano | I S N | texto livre → equipe; assistente determinístico opcional |
| Nós nativos do n8n | avaliado | presos na Graph v13.0/v19.0 (ver referência §9) → HTTP Request |
| Workflows versionados, exportados desligados | I S (n8n real × API real) | `docs/automacao/n8n/pcpr/` (W1–W3, W5–W8, `active: false`) |

## Fluxos ampliados

| Fluxo | Estado | Observação |
|---|---|---|
| Aviso de liberação e lembretes de comprovante | I S N | |
| Link de km na véspera, formulário offline (sincronização idempotente, conflito, "neste aparelho" × "no sistema") | I S N | e2e `test_km_offline.py` |
| Avisos de cancelamento, remarcação, substituição e retirada da equipe | I S | |
| Documentos disponíveis por destinatário | — | depende do envio de documentos (10-2), não implementado |
| DB/RT para assinatura de teste com versão congelada e devolução por versão | — | não implementado nesta rodada |
| Confirmações do portal e resumos de outros módulos | — | não implementado |

## IA (`gestao/integracoes/ia/` + `gestao/assistencia/`)

Ver [ia-usos.md](ia-usos.md): porta independente do fornecedor (simulado, gravado, Anthropic
desligado), chamadas só no worker, saída validada, limites, versão de prompt/modelo/contexto,
custo **estimado** separado da cobrança, teto de orçamento com trava concorrente, minimização,
caminho sem IA. Usos: AUT-50, 57, 58, 76, 80, 81, 86, 88, 89, 93, 94 implementados e testados
com simulador; AUT-92 e AUT-171 **não** (dependem do leitor por regras e da consulta real ao
eProtocolo).

## Ferramentas, delegação e aprovações

| Requisito | Estado |
|---|---|
| Ferramentas tipadas com policy do contexto e registro de execução (inclusive negações) | I S |
| Delegação emitida pelo PCPR (tela `/automacao/delegar/`), ≤ 15 min, uso único, nunca perfil administrativo | I S |
| Token de transporte sem poder de ferramenta; credenciais separadas (transporte, IA, pessoal) | I S |
| Portão de aprovação para irreversível (quem pede não aprova; desligada não aprova) | I S |
| Nada de cabeçalho livre de "usuário representado" | I S |
| Proibições por desenho (equipe, motorista, viatura, km, pagamento, diária, emitir, assinar, aprovar, despacho, finalizar) | I S |
| Proposta consolidada: escolher a viagem, informar quem vai, prévia sem gravar nem reservar número | I S N (temporário) |
| Autorização por fluxo sombra → assistido → automático | I S |
| eProtocolo e Central de Viagens simulados | inalterados (simulados) |

## Revisões aplicadas (18/10, manhã)

- **UX (P1):** o aviso do painel diz quais fluxos estão desligados (não só um); aba
  "Aguardando aprovação" com indicador no painel e aprovação em lote confirmada; revogar links
  em massa mostra quantos estão vigentes, pede motivo e confirma; aprovações confirmam antes
  de executar e a recusa pede o motivo; a proposta trava o passo 1 depois da prévia
  ("Alterar escolhas"); a página de km mostra cada situação com um selo próprio; a revisão de
  sugestão de IA preserva o texto editado e mostra "Atual" × "Sugerido".
- **Desempenho:** salvar km trava e confere o diário uma vez por lote (antes, ~20 consultas
  por lançamento); a reconciliação não repete os mesmos órfãos nem reabre exceção resolvida;
  índices de limpeza e do limite por hora (migração `automacao.0006`); página de km sem o CSS
  das telas internas e com um cache de estáticos por versão no service worker; sem N+1 nos
  detalhes e em `/assistencia/usos/`; GET da assistência não grava mais.
- **Tipos:** `mypy gestao config` sem erros, sem `type: ignore` novo.
- Paridade: [docs/parity/automacao-whatsapp-ia.md](../parity/automacao-whatsapp-ia.md).
- **Acessibilidade (altos e médios):**
  - página de km: uma única região viva, só o trecho salvo é anunciado e o texto só muda se
    mudou; a frase de situação quebra linha a 360 px; Enter salva o trecho; o foco volta ao
    trecho depois do conflito;
  - o diálogo de motivo só lê o erro quando ele aparece;
  - tokens e URL quebram linha; os escopos das credenciais não são cortados;
  - os obrigatórios têm `*`;
  - toda ação irreversível pede confirmação;
  - a prévia da proposta e a resposta da central recebem o foco.
- **n8n × API real** (`testar_pcpr_real.py`): a 1ª rodada achou D1–D4 e O1, todos corrigidos
  com teste:
  - D1: envelopes fora do esquema;
  - D2: status repetido com outro horário dava 422;
  - D3: canal de entrada bloqueado → agora 409;
  - D4: mesma chave com outro arquivo → agora 409;
  - O1: `hub.challenge` só alfanumérico.

  Na rodada final, **todos os aplicáveis passaram**. Os ids do canal vão até 300 caracteres
  sem truncar (migração `automacao.0007`), e a chave do recebimento acima de 200 caracteres, ou
  com algo fora do ASCII imprimível, vira `receb#sha256:<canal>:<hex>:<anexo>`.

## Limites conhecidos (não escondidos)

- **Main com marcadores de conflito** (716e9ef, 10 arquivos de Eventos/Coffee/CSS): este ramo
  roda localmente com a versão do PR #22 desses arquivos, **que não entra no commit**. A
  correção do main é outra tarefa. Atenção nessa correção: a versão local de
  `static/css/components.css` não tem as regras `.dialogo--cadastro*` (usadas por 8 telas de
  Cadastros, Coffee e Planos); o merge certo precisa manter as duas metades.
- Aprovar a proposta consolidada numera os rascunhos (ofício, OS, plano) como o lote já faz:
  a prévia não reserva número, a criação sim.
- Rate limit dos links e da API usa o cache por processo (sem Redis no PREVIEW).
- Logs de acesso do proxy precisam do modelo atualizado (`deploy/proxy/*.modelo`) para mascarar
  `/p/<token>`.
