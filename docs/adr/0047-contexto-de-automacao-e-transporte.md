# ADR 0047 — Criar o contexto `automacao` para comunicações, contatos e recebimentos

- **Status:** aceito
- **Data:** 2026-10-18

## Contexto
O piloto de testes (ADR 0046) precisa enviar avisos pelo WhatsApp Cloud API, receber mensagens e
documentos sintéticos, acompanhar entrega e encaminhar exceções a uma pessoa, com o n8n como
orquestrador opcional (ADR 0020) e as integrações atrás de portas (ADR 0019). O desenho está em
`docs/automacao/arquitetura.md` e nos contratos `docs/automacao/contratos/`. Fatos do código
(18/10/2026, base `origin/main` 716e9ef): a outbox tem um assinante por tópico e segura a transação
durante o assinante; servidores viajantes não são usuários e só têm `Servidor.telefone` (10/11
dígitos, sem DDI, sem opt-in); `gestao.integracoes` e `gestao.plataforma` não podem importar
contextos de negócio; não existe nenhuma API para máquina nem `csrf_exempt` no repositório.

## Decisão
Criar o app `gestao/automacao` (contexto próprio) com os modelos e serviços da fundação:
`ChaveAutomacao` (geral, por fluxo e por canal), `ContatoVerificado` (servidor, canal, endereço
E.164, verificação, opt-in revogável), `DestinatarioAutorizado` (lista fechada de testadores do
LAB), `Comunicacao` + `TentativaEntrega` + `StatusEntrega`, `Recebimento` e `ExcecaoAutomacao`;
nas entregas seguintes `LinkAcesso`, `CredencialIntegracao`, `Delegacao`, registro de idempotência,
eventos de integração e o registro de ferramentas.

- **Fronteiras:** `automacao` pode importar `plataforma`, `integracoes`, `identidade` e `cadastros`;
  nunca `viagens`, `eventos`, `coffee`, `painel`, `imprensa`, `publicacoes` ou `palestras`
  (contrato novo no import-linter). Os contextos de negócio registram **ganchos** no `ready()`:
  tipo de comunicação (rótulo, texto, revalidação no momento do envio) e destino de recebimento
  (como associar um arquivo ao registro). Mesmo padrão de `plataforma.rotinas`/`conflitos`.
- **Portas:** `gestao/integracoes/whatsapp/` (simulado, gravado para testes e Cloud API) recebe só
  primitivos (endereço, texto, ids); nunca conhece `Servidor` nem `Usuario`.
- **Transporte:** a comunicação é estado do PCPR. Quem leva ao canal é configurável por canal:
  `interno` (padrão: worker `processar_automacao` do PCPR, com lease, fora de transação) ou `n8n`
  (o n8n reserva e devolve o resultado pela API v1). Desligado o n8n, o transporte interno e a
  contingência manual continuam.
- **Reserva:** transição atômica `agendada → enviando` com prazo; revalida chave, contato, opt-in,
  lista do LAB, versão do recurso e a regra do tipo **antes** de qualquer chamada externa. Resultado
  desconhecido nunca reenvia: vai para a fila de exceções. Falha temporária volta à fila com
  backoff e limite de rodadas.
- **Entrada:** o webhook do WhatsApp chega direto no PCPR (variante V2 do protótipo): assinatura
  `X-Hub-Signature-256` sobre o corpo bruto, registro durável e só então `200`; o processamento
  (download de mídia, associação) roda no worker. O n8n não vê o conteúdo de entrada.
- **Quem age na associação automática:** o arquivo devolvido em resposta a uma comunicação é
  associado em nome do usuário que originou a comunicação (ex.: o operador que registrou a
  liberação), sob `auditoria.contexto(..., requisicao_id="recebimento:<id>")`; as policies do
  contexto continuam valendo (perdeu a permissão → exceção). Não existe usuário "de sistema"
  com poderes amplos.
- **Ambientes:** simulado é o padrão em todos os ambientes; o adaptador real só carrega com
  configuração explícita e nunca no PREVIEW (`APP_ENV=preview` recusa o modo real no startup);
  fora de produção, envio real exige destinatário na lista fechada.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Modelos de comunicação em `plataforma` | `plataforma` não pode depender de `cadastros` (contato do servidor); misturaria núcleo técnico com regra de canal |
| Contatos e comunicações dentro de `viagens` | Eventos, Coffee e ASCOM também comunicam; duplicaria o canal em cada contexto |
| Assinante da outbox chamando a Meta | O worker da outbox segura a transação durante o assinante; HTTP lento travaria escritas auditadas |
| Só o n8n enviando | Sem n8n o sistema ficaria mudo; regras de revalidação iriam para workflows |
| Usuário de sistema com permissões amplas para associar arquivos | Contorna as policies; a trilha perderia o responsável |

## Consequências
Nova app em `INSTALLED_APPS`, migrações com trigger de auditoria em todas as tabelas, contrato de
import-linter novo, worker `processar_automacao` nos compose (PREVIEW com adaptador simulado), e
telas de operação (canal e chaves, contatos, testadores, comunicações, recebimentos, exceções).
Toda comunicação nova de um contexto passa por um tipo registrado com revalidação.

## Complemento (18/10/2026, na implementação)
- **Modo do fluxo na hora do envio.** `sombra`/`assistido`/`automatico` são lidos na reserva,
  não no agendamento: trocar o modo vale também para o que já está na fila.
- **Conteúdo fora da trilha.** Texto enviado e recebido, nome de perfil, corpo bruto do webhook
  e a resposta guardada da reserva pela API (que leva o link pessoal) ficam em tabelas sem
  trigger e com retenção (`AUTOMACAO_RETENCAO_DIAS`; a resposta da reserva, 1 h). A cópia
  guardada da mensagem mascara `/p/<token>`.
- **API v1** em `/api/automacao/v1/` (`gestao/automacao/api/`): credencial por integração
  (transporte, IA, pessoal) só em hash e com ambiente no próprio token; `Idempotency-Key`
  obrigatória com impressão da requisição (2xx e 409 guardados; 423 não); 423 só no que cria
  efeito novo; reserva com chave única por execução e token de reserva; `X-PCPR-Delegacao`
  emitida pelo PCPR (≤ 15 min, uso único, nunca para perfil administrativo). Desligada no
  PREVIEW. Desvios do contrato: `/entradas` e `/assistente/mensagens` (e-mail) respondem 501
  `integracao_inexistente` (e-mail é opcional no piloto); `/recebimentos` (V1) só aceita
  `canal=whatsapp` e associa pelo mesmo caminho da V2, não pela importação documental.
- **Eventos PCPR → n8n** (`eventos.py`) só com `N8N_EVENTOS_URL` e segredo; entregues pelo
  mesmo worker, com lease, HMAC e repetição limitada.
- **Ferramentas tipadas** (`ferramentas.py`): leitura executa; preparação respeita chave e
  modo do fluxo `ferramentas`; irreversível vira `PedidoAprovacao` e quem aprova executa com a
  própria permissão. Nomes que sugerem equipe, motorista, viatura, km, pagamento, diária,
  emissão, assinatura, aprovação, despacho ou finalização são recusados no registro.
- **Links pessoais** (`links.py`, `/p/<token>/`): escopo e recurso fixos, hash, validade,
  revogação individual, por recurso e em massa; a página de cada escopo é registrada pelo
  contexto dono (o km do diário, em Viagens).
- **Assistente no WhatsApp:** texto livre de contato verificado é respondido pelo mesmo
  assistente determinístico do portal (ADR 0048) quando o fluxo `assistente_whatsapp` está
  ligado; sem resposta segura, também vai para a equipe.
