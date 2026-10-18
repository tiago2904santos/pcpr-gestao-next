# Plano de implantação da automação — ordem por valor e dependência

Revisado em **18/10/2026** para um **sistema de testes independente, sem uso oficial policial e
sem operação com policiais**, conforme esclarecimento do usuário. Regra vigente:
[WhatsApp principal no piloto](../product/automacao-whatsapp-testes.md) e
[ADR 0046](../adr/0046-whatsapp-principal-no-sistema-de-testes.md).

Base histórica de 17/10/2026: a lista ordenada da
[matriz de oportunidades, seção 9](matriz-oportunidades.md#9-lista-ordenada-por-valor-e-dependência-alimenta-o-plano-de-implantação)
(174 itens AUT-01…AUT-174; as frentes de WhatsApp são AUT-172 a AUT-174; detalhes em [`fichas/`](fichas/) e [`fluxos/`](fluxos/)). Regras do plano:

- uma etapa só começa quando o aceite da anterior foi cumprido;
- toda automação nasce **desligada** e é ligada por fluxo (chave em `/api/automacao/v1/estado`), com
  continuação manual sempre disponível na tela;
- ações irreversíveis (emitir, cancelar, retificar, assinar, abrir protocolo, aprovar prestação) continuam
  humanas — a máquina prepara, a pessoa decide;
- **nenhuma ativação com efeito real e nenhuma mudança na VPS faz parte desta missão**: cada etapa abaixo é
  uma decisão posterior do usuário.

## Canal principal definido pelo usuário: WhatsApp Business (18/10/2026)

O usuário esclareceu que o site **não é oficial da polícia, não vai operar com policiais e é
apenas um sistema de testes**. WhatsApp Business Platform, pela **Cloud API oficial**, passa a
ser o canal principal de comunicação do piloto: avisos, lembretes, links, recebimento de mensagens
e documentos sintéticos e acompanhamento da entrega. Portal é apoio para formulários e arquivos;
notificações internas atendem o operador; e-mail é opcional, sem dependência de SMTP institucional.

A conclusão policial de 17/10 não é aplicada automaticamente ao piloto independente. Não se
exige decisão da PCPR nem consulta excepcional sobre elegibilidade policial. A conta deve
representar o responsável real pelo teste, com onboarding normal da Meta; isso não significa
conta já aprovada. Começar com os recursos de teste disponíveis no painel e conferir seus limites.

| Frente | O que é | Quando | Depende de | Aceite |
|---|---|---|---|---|
| **WA-3. Cloud API como canal principal** | Adaptadores simulado e Cloud API, contato verificado com opt-in, envio por modelo ou na janela de atendimento, links de KM/documentos, recebimento e status. Preferir webhook direto no PCPR (V2); W6 no transporte de saída e W7/W8 como referência do protótipo | etapas 1–2, prioridade | fundação mínima de comunicações; conta, recursos de teste e credenciais Meta; LAB isolado | ensaio ponta a ponta no LAB; envio, entrada e status registrados; duplicidade sem novo efeito; canal inicialmente `desligado` |
| **WA-1. Contingência manual registrada** | Copiar mensagem ou abrir `wa.me`, enviar manualmente e registrar quem e quando, quando a Cloud API estiver indisponível | etapa 1 | `Comunicacao` e contato do testador | nada é marcado como enviado apenas por abrir o link; operador confirma |
| **WA-2. Onboarding normal do piloto** | Configurar a conta do responsável real, recursos de teste da Meta, destinatários autorizados e requisitos normais de acesso. Consulta policial histórica fica fora do piloto | etapa 0, em paralelo ao simulador | acesso do responsável ao painel Meta | recursos e limites conferidos; sem exigência de exceção policial ou aprovação da PCPR |

**Sequência do primeiro fluxo:** registrar uma liberação fictícia → criar `Comunicacao` → reservar
e enviar pelo WhatsApp ao testador → gravar id e status → receber comprovante sintético →
associar à prestação fictícia → confirmar recebimento e encerrar os lembretes. Em seguida,
estender a link de KM, documentos disponíveis, DB/RT e dúvidas com link ao portal. IA não é
pré-requisito dessa comunicação.

**Aceite para ligar a WA-3 no LAB:** conta e recursos de teste disponíveis; identificação clara
de sistema de testes; contatos verificados e opt-in; lista de destinatários permitidos validada
no servidor; credenciais isoladas; HTTPS, assinatura do webhook e verificação GET; modelos
aprovados quando exigidos e respeito à janela de atendimento; envio, recebimento, status,
idempotência, desligamento e retenção testados. O modo `bloqueado` só se aplica a impedimento
realmente identificado; o padrão do piloto é `desligado` até cumprir o aceite.

**Isolamento:** ensaio externo em LAB dedicado com dados administrativos fictícios e contatos
autorizados. PREVIEW/DEMO público permanece simulado, sem credenciais nem envio externo.
Os workflows exportados continuam desligados; a integração real no PCPR ainda será construída.
Custos de mensagens, provedor eventual e limites entram no orçamento do piloto, a confirmar.

## Decisões do usuário

| # | Decisão | Antes de | Recomendação |
|---|---|---|---|
| D1 | Destino da cópia externa do backup (computador e HD) e conferência dos SHA-256 | **qualquer mudança na VPS** | pasta local fora do OneDrive + HD exFAT/NTFS |
| D2 | Hospedagem do n8n | etapa 0 | instalar no Ubuntu atual (Alternativa A); não reinstalar por template — [hospedagem-n8n.md](../ops/mudanca-hospedagem/hospedagem-n8n.md) |
| D3 | Fila `drive` da referência em produção | fora do piloto | pendência histórica AUT-116; não alterar a referência para iniciar os testes |
| D4 | Canal principal do piloto | **decidido em 18/10/2026** | **WhatsApp Business Cloud API**; portal e notificações internas de apoio; e-mail opcional |
| D4a | Conta, número/recursos de teste e responsável pelo onboarding | etapa 0 | identidade real do responsável pelo projeto; conferir recursos disponíveis no painel; nenhum vínculo policial presumido |
| D5 | Destinatários do piloto e autorização de contato | etapa 1 | testadores com contato verificado, opt-in e lista fechada; dados administrativos sintéticos (AUT-02) |
| D6 | Uso de eProtocolo e demais sistemas institucionais | eventual mudança de escopo | fora do piloto conectado: manter simulados; uso oficial futuro exige nova revisão |
| D7 | Parâmetros fictícios do teste (horário da véspera, janela de envio, responsável pelo KM, assinantes de teste, validade dos links, destinatários) | etapas 2–3 | configurar os cenários marcados `[decisão]` sem depender de órgão público |
| D8 | Provedor de IA, modelo, orçamento mensal e política de dados | etapa 4 | avaliar `claude-haiku-5-5` e `claude-sonnet-5-5` no gabarito e escolher o mais barato que passar — [desempenho-e-custos.md](desempenho-e-custos.md) |
| D9 | Credenciais e autorização do eProtocolo e da Central de Viagens | fora do piloto; eventual uso institucional futuro | no teste usar simuladores; [histórico do fluxo 13](fluxos/13-integracoes-institucionais.md) |

Na etapa 0, preparar onboarding Meta e lista de testadores. SMTP/IMAP institucionais,
credenciais eProtocolo/Central e decisões de órgãos públicos **não bloqueiam o piloto**.
D1–D3 referem-se à infraestrutura compartilhada e às referências históricas: continuam exigíveis
se essas máquinas forem alteradas, mas não exigem mudança nos sistemas de produção para um LAB isolado.
D7 usa regras fictícias do cenário; D9 só se aplica a futura implantação institucional.

## Etapas

Na etapa 0, usar LAB isolado; não alterar referências de produção para começar o piloto.
Nas etapas 1–2, antecipar AUT-174 e o onboarding do piloto (WA-2), com AUT-172 como contingência.
**As entregas e aceites de transporte abaixo passam a usar WhatsApp como principal**, e-mail apenas
como alternativa. No piloto, a etapa 6 usa simuladores; credenciais institucionais são escopo futuro.

| Etapa | Itens | Entrega | Aceite | Recursos |
|---|---|---|---|---|
| **0. Pré-requisitos do LAB** | AUT-99; WA-2 / AUT-173 no recorte do piloto | LAB autenticado e isolado, dados fictícios, n8n com banco próprio e retenção controlada; onboarding Meta, recursos de teste e lista de contatos autorizados; workflows desligados; backup/restauração do LAB | reinício sem perda; isolamento do DEMO; nenhuma mudança nas referências de produção; backup conferido se for alterar a VPS compartilhada | ambiente de teste; custos e recursos Meta a confirmar |
| **1. Fundação no PCPR** | AUT-102, 01, 02, 100, 101, 103, 104, 108, 110, 03, 105, 106, 05, 109 | Retentativa/reprocessamento da outbox; `Comunicacao`; `ContatoVerificado`; catálogo de eventos + worker de entregas com lease e HMAC; tela de saúde e fila de exceções; API de automação v1 (token de serviço, escopos, delegação `X-PCPR-Delegacao` emitida pelo PCPR — nunca um usuário escolhido pelo chamador —, `Idempotency-Key`, chave geral); salvaguardas; `LinkAcesso` e portal mínimo; ferramentas de leitura e portão de aprovação; e-mail individual; rotinas com horário próprio | contrato v1 coberto por testes; evento duplicado/fora de ordem sem efeito; chave desligada → 423; reinício do worker sem perda; os cenários T1–T13 do protótipo repetidos contra o PCPR real em ambiente de teste; reserva WhatsApp com opt-in e lista de testadores | desenvolvimento no PCPR (maior esforço do plano) |
| **2. Comunicação e avisos — WhatsApp principal** | AUT-174, AUT-172, AUT-111, 21, 36, 04, 06, 22, 31, 23, 37, 38, 24, 30, 07, 39, 113, 136, 144, 145, 150, 153, 157, 162, 164, 154 | Alertas operacionais pelo n8n; versões congeladas de termo/OS/plano; aviso de liberação de diárias e lembretes; envio de documentos sintéticos por link autenticado e WhatsApp Cloud API; avisos de retificação/cancelamento/reagendamento; resumos diários; comunicações de teste de Eventos, ASCOM e Coffee pelo WhatsApp; e-mail opcional | nenhum rascunho enviado; retificação invalida a versão anterior e avisa quem recebeu; lembrete cessa quando o comprovante entra; alerta dispara com fila parada simulada | PCPR + n8n + Cloud API em LAB; SMTP opcional |
| **3. Campo, prestação e entrada de documentos — WhatsApp principal** | AUT-53, 97, 40, 132, 41, 112, 52, 08, 43, 44, 46, 47, 55, 48, 133, 143, 151, 155, 09, 148, 141, 156 | Conferência de assinatura estendida; Central de ajuda e "Minha situação"; link de KM por trecho (offline) e envio na véspera por WhatsApp; caixa de entrada única; antivírus em toda entrada; recebimento de devolvidos sintéticos pelo WhatsApp/portal na importação documental; DB/RT prontos para assinatura com versão congelada | ver aceite dos fluxos 10-4, 10-5 e 10-6 (pré-visualização do link não consome; KM parcial não conclui; devolvido duplicado não duplica anexo; remetente não verificado vai para quarentena) | PCPR + n8n |
| **4. IA assistiva** | AUT-96, 91, 50, 76, 80, 81, 92, 88, 107, 86, 94, 57, 58, 89, 93 | Porta única de IA com validador; conjunto de avaliação; rascunhos de RT, Plano e justificativa ancorados em dados; leitura de programação; assistente dos servidores (só leitura) | gabarito sintético aprovado; zero fato fora dos dados; zero vazamento entre servidores; custo por tarefa medido | provedor de IA (D8) |
| **5. Autonomia progressiva** | AUT-118, AUT-16 (+ AUT-14/15 da trilha paralela) | Autorização por fluxo (sombra → assistido → automático), painel "o que a automação fez", desfazer; proposta consolidada "selecionar evento → informar quem vai → conferir" | conferência única substitui as etapas repetitivas; nada emitido sem aprovação; número só reservado ao aprovar | PCPR |
| **6. Integrações institucionais — simulado no piloto** | AUT-120, 119, 122, 125, 32, 121, 123, 159, 160, 115, 171, 117 | simuladores de eProtocolo/Central, cadastros fictícios e identidade do piloto; conexão institucional futura depende de revisão de escopo | zero chamada a sistemas estaduais reais; origem simulada explícita nos dados | simuladores locais; sem credenciais institucionais |

**Trilha paralela** (melhorias no próprio sistema, sem n8n nem fundação — 52 itens, matriz §9.2): pode
avançar a qualquer momento, inclusive a semente da viagem a partir da solicitação (AUT-15) e a proposta
consolidada em modo prévia (AUT-14). **Fora do plano** (maturidade 5, matriz §9.3): integração não oficial de WhatsApp, robôs de navegador em portais institucionais e decisões de mérito por IA. O WhatsApp **oficial** não está fora do plano: é prioridade (frentes WA-1 a WA-3 / AUT-172 a AUT-174 acima), como **canal principal do piloto**, com ativação após onboarding normal e aceite no LAB descritos acima; não depende de autorização policial.

## Cenários de falha exigidos (seção E da missão) e onde estão cobertos

| Cenário | Desenho | Comprovado no protótipo |
|---|---|---|
| Evento duplicado | arquitetura §3.3; fluxos 10-2…10-6 §9 | T2 (reentregas e 5 simultâneas → 1 envio) |
| Serviço indisponível (n8n, SMTP, provedor) | arquitetura §3.7–3.11 | T6 (falha e retentativa), T7 (exceção sem laço), T8 (evento perdido → reconciliação) |
| Viagem reagendada | 10-4 §8; 10-2 §9 | T4 (comunicação obsoleta → 409, nova agendada) |
| Link expirado | 10-4 §9; 10-5 §9 | regra coberta por T11 (validade); fluxo de UI ainda só desenhado |
| KM parcial | 10-4 §3 e §9; 10-5 §3 | só desenhado |
| Documento duplicado ou incorreto | 10-6 §9 | T9 (devolvido 2× → 1 recebimento); identificação incorreta → revisão humana (desenhado) |
| Destinatário sem autorização / sem contato verificado | arquitetura §4; 10-2 §6 (reserva revalida) | só desenhado (a reserva do simulador recusa) |
| Retentativa após sucesso parcial | arquitetura §3.6 | T10 (n8n morto no meio → 0 duplicados; cortados viram "resultado desconhecido") |
| Reinício do n8n | arquitetura §3.8 | T10 |
| Correção de dados após envio para assinatura | 10-5 §9; 10-2 (retificação) | só desenhado |
| Automação desligada | arquitetura §3.10 | T5 (423, comunicação segue agendada; religada → 1 envio) |

## O que continua humano

Escolher quem participa; emitir, retificar, cancelar; assinar; aprovar ou devolver prestação; registrar a
liberação das diárias (dado de fonte externa); decidir despacho; aprovar ações irreversíveis do assistente.
