# Plano de implantação da automação — ordem por valor e dependência

Sequência recomendada em 17/10/2026. Base: a lista ordenada da
[matriz de oportunidades, seção 9](matriz-oportunidades.md#9-lista-ordenada-por-valor-e-dependência-alimenta-o-plano-de-implantação)
(174 itens AUT-01…AUT-174; as frentes de WhatsApp são AUT-172 a AUT-174; detalhes em [`fichas/`](fichas/) e [`fluxos/`](fluxos/)). Regras do plano:

- uma etapa só começa quando o aceite da anterior foi cumprido;
- toda automação nasce **desligada** e é ligada por fluxo (chave em `/api/automacao/v1/estado`), com
  continuação manual sempre disponível na tela;
- ações irreversíveis (emitir, cancelar, retificar, assinar, abrir protocolo, aprovar prestação) continuam
  humanas — a máquina prepara, a pessoa decide;
- **nenhuma ativação com efeito real e nenhuma mudança na VPS faz parte desta missão**: cada etapa abaixo é
  uma decisão posterior do usuário.

## Prioridade definida pelo usuário: WhatsApp (17/10/2026)

O usuário pediu que as integrações com o WhatsApp sejam **prioridade**. A política oficial do WhatsApp
Business (atualizada em 23/09/2026) proíbe autoridades policiais na plataforma oficial, sem exceção — e
integração não oficial, número pessoal automatizado ou ocultar a identidade institucional estão fora de
cogitação ([whatsapp-viabilidade.md](whatsapp-viabilidade.md), seções 1, 2 e 4). A prioridade se traduz
em três frentes que começam já, sem esperar as outras etapas:

| Frente | O que é | Quando | Depende de | Aceite |
|---|---|---|---|---|
| **WA-1. WhatsApp assistido com registro** | Opção B da seção 7.3 da viabilidade: o sistema monta a mensagem mínima (função de domínio testada, sem dados além do necessário) e o link `wa.me`; o operador envia do aparelho institucional; ao voltar, o sistema registra "enviado por WhatsApp manual" (`Comunicacao` com `origem = outro_meio`), quem e quando. Vale para o aviso de liberação de diárias, link de KM, documentos disponíveis e lembretes | etapa 1 (junto com `Comunicacao` e `ContatoVerificado`) | decisão institucional sobre o aparelho/número usado (P3/P4 da viabilidade) | toda comunicação manual fica registrada; nenhum envio automático por esse caminho |
| **WA-2. Consulta formal de elegibilidade** | Enviar à Meta ou a um provedor autorizado as perguntas P1–P10 já redigidas (seção 3 da viabilidade), por canal oficial e com responsável designado pela PCPR | etapa 0 | a PCPR decidir quem envia e por qual canal (esta missão não envia contato) | resposta escrita arquivada; a classificação da frente WA-3 é revista com base nela |
| **WA-3. Integração oficial pronta e desligada** | Porta `gestao/integracoes/whatsapp` (adaptadores simulado e Cloud API), opt-in no `ContatoVerificado`, modelos *utility* redigidos para aprovação, webhook com `X-Hub-Signature-256` e verificação GET, mídia por id (URL de 5 min com token), status de entrega para `/entrega`, workflows n8n de envio/recebimento/status **exportados desligados** e testados contra um simulador da Graph API | etapas 1–2, em paralelo | fundação da etapa 1; simulador local | testes do protótipo passando; canal `whatsapp = bloqueado` em `/estado` até a ativação |

**Portão de ativação da WA-3** (todos obrigatórios): autorização escrita da Meta ou de provedor
autorizado compatível com a política vigente; conta empresarial verificada em nome da instituição;
decisão formal da PCPR e avaliação de LGPD (opt-in, base legal, retenção); modelos aprovados. Até lá, as
mesmas comunicações saem pelo portal, pelas notificações internas, pelo e-mail institucional e pela
WA-1 — os fluxos já são independentes de canal, então ligar o WhatsApp depois não muda estados nem regras.

## Decisões do usuário

| # | Decisão | Antes de | Recomendação |
|---|---|---|---|
| D1 | Destino da cópia externa do backup (computador e HD) e conferência dos SHA-256 | **qualquer mudança na VPS** | pasta local fora do OneDrive + HD exFAT/NTFS |
| D2 | Hospedagem do n8n | etapa 0 | instalar no Ubuntu atual (Alternativa A); não reinstalar por template — [hospedagem-n8n.md](../ops/mudanca-hospedagem/hospedagem-n8n.md) |
| D3 | Fila `drive` parada no sistema em produção desde 26/08 | etapa 0 | purgar e reconciliar pelo banco (AUT-116) |
| D4 | Canal com os servidores | etapa 1 | **WhatsApp é prioridade** (frentes WA-1 a WA-3 acima): já, o WhatsApp assistido com registro; a plataforma oficial só com autorização formal. Em paralelo, portal mínimo + notificações internas + e-mail institucional — [whatsapp-viabilidade.md](whatsapp-viabilidade.md) |
| D4a | Aparelho/número institucional para o WhatsApp assistido e quem envia a consulta à Meta | etapa 0 | número institucional, nunca pessoal; responsável designado pela PCPR |
| D5 | Base legal e origem do contato dos servidores viajantes (LGPD) | etapa 1 | ver AUT-02 |
| D6 | Decreto PR 7.304/2021: envio/recebimento pelo PCPR como complemento (não substituto) da tramitação no eProtocolo | etapa 2 | confirmar com a área jurídica/gestão |
| D7 | Regras institucionais em aberto (horário da véspera, janela de envio, quem preenche o KM com vários veículos, assinantes do DB/RT, validade dos links, quem recebe cada documento) | etapas 2–3 | propostas marcadas `[decisão]` em cada fluxo |
| D8 | Provedor de IA, modelo, orçamento mensal e política de dados | etapa 4 | avaliar `claude-haiku-5-5` e `claude-sonnet-5-5` no gabarito e escolher o mais barato que passar — [desempenho-e-custos.md](desempenho-e-custos.md) |
| D9 | Credenciais e autorização do eProtocolo e da Central de Viagens | etapa 6 (pedir na etapa 0) | [13-integracoes-institucionais.md](fluxos/13-integracoes-institucionais.md) |

Pedidos institucionais demorados saem **já na etapa 0**: SMTP e caixa postal (AUT-04, AUT-08),
credenciais do eProtocolo/Central (AUT-119, AUT-120, AUT-122, AUT-125) e a decisão sobre o contato dos
servidores (AUT-02).

## Etapas

| Etapa | Itens | Entrega | Aceite | Recursos |
|---|---|---|---|---|
| **0. Pré-requisitos** | AUT-99, AUT-116, AUT-12 | Cópia externa conferida; swap e firewall do host revisados; n8n em contêiner isolado (127.0.0.1, PostgreSQL próprio, poda, chave de criptografia fora da VPS), **sem nenhum fluxo publicado**; backup e restauração do n8n testados; decisão da fila `drive` | hashes do pacote conferidos no HD; n8n reinicia sem perda; restauração do n8n comprovada | VPS atual, sem custo novo |
| **1. Fundação no PCPR** | AUT-102, 01, 02, 100, 101, 103, 104, 108, 110, 03, 105, 106, 05, 109 | Retentativa/reprocessamento da outbox; `Comunicacao`; `ContatoVerificado`; catálogo de eventos + worker de entregas com lease e HMAC; tela de saúde e fila de exceções; API de automação v1 (token de serviço, escopos, delegação `X-PCPR-Delegacao` emitida pelo PCPR — nunca um usuário escolhido pelo chamador —, `Idempotency-Key`, chave geral); salvaguardas; `LinkAcesso` e portal mínimo; ferramentas de leitura e portão de aprovação; e-mail individual; rotinas com horário próprio | contrato v1 coberto por testes; evento duplicado/fora de ordem sem efeito; chave desligada → 423; reinício do worker sem perda; os cenários T1–T12 do protótipo repetidos contra o PCPR real em ambiente de teste | desenvolvimento no PCPR (maior esforço do plano) |
| **2. Comunicação e avisos** | AUT-111, 21, 36, 04, 06, 22, 31, 23, 37, 38, 24, 30, 07, 39, 113, 136, 144, 145, 150, 153, 157, 162, 164, 154 | Alertas operacionais pelo n8n; versões congeladas de termo/OS/plano; aviso de liberação de diárias e lembretes; envio de documentos emitidos por link autenticado e e-mail; avisos de retificação/cancelamento/reagendamento; resumos diários; e-mails de Eventos, ASCOM e Coffee | nenhum rascunho enviado; retificação invalida a versão anterior e avisa quem recebeu; lembrete cessa quando o comprovante entra; alerta dispara com fila parada simulada | PCPR + n8n; SMTP institucional (D4) |
| **3. Campo, prestação e entrada de documentos** | AUT-53, 97, 40, 132, 41, 112, 52, 08, 43, 44, 46, 47, 55, 48, 133, 143, 151, 155, 09, 148, 141, 156 | Conferência de assinatura estendida; Central de ajuda e "Minha situação"; link de KM por trecho (offline) e envio na véspera; caixa de entrada única; antivírus em toda entrada; recebimento de devolvidos pela importação documental; DB/RT prontos para assinatura com versão congelada | ver aceite dos fluxos 10-4, 10-5 e 10-6 (pré-visualização do link não consome; KM parcial não conclui; devolvido duplicado não duplica anexo; remetente não verificado vai para quarentena) | PCPR + n8n |
| **4. IA assistiva** | AUT-96, 91, 50, 76, 80, 81, 92, 88, 107, 86, 94, 57, 58, 89, 93 | Porta única de IA com validador; conjunto de avaliação; rascunhos de RT, Plano e justificativa ancorados em dados; leitura de programação; assistente dos servidores (só leitura) | gabarito sintético aprovado; zero fato fora dos dados; zero vazamento entre servidores; custo por tarefa medido | provedor de IA (D8) |
| **5. Autonomia progressiva** | AUT-118, AUT-16 (+ AUT-14/15 da trilha paralela) | Autorização por fluxo (sombra → assistido → automático), painel "o que a automação fez", desfazer; proposta consolidada "selecionar evento → informar quem vai → conferir" | conferência única substitui as etapas repetitivas; nada emitido sem aprovação; número só reservado ao aprovar | PCPR |
| **6. Integrações institucionais** | AUT-120, 119, 122, 125, 32, 121, 123, 159, 160, 115, 171, 117 | eProtocolo em treinamento → produção com portão; Central de Viagens se houver API oficial; fonte de cadastros; SSO | trava de mutação por ambiente; nenhuma mutação sem aprovação; tokens distintos por ambiente | credenciais institucionais (D9) |

**Trilha paralela** (melhorias no próprio sistema, sem n8n nem fundação — 52 itens, matriz §9.2): pode
avançar a qualquer momento, inclusive a semente da viagem a partir da solicitação (AUT-15) e a proposta
consolidada em modo prévia (AUT-14). **Fora do plano** (maturidade 5, matriz §9.3): integração não oficial de WhatsApp, robôs de navegador em portais institucionais e decisões de mérito por IA. O WhatsApp **oficial** não está fora do plano: é prioridade (frentes WA-1 a WA-3 / AUT-172 a AUT-174 acima), com a ativação da WA-3 presa ao portão de autorização formal.

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
