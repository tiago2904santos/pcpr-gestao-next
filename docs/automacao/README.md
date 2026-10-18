# Automação com n8n e IA — auditoria e plano (17/10/2026)

Fase 2 da missão de mudança de hospedagem ([registro da missão](../ops/mudanca-hospedagem/README.md)).
Objetivo operacional: progressivamente, o usuário **seleciona o evento, informa quem vai e confere uma
proposta consolidada**, enquanto o sistema organiza o resto — preservando decisões, conferências e
assinaturas humanas. Nada aqui foi ativado com efeito real: é desenho revisável, contratos, protótipo
local testado e um plano em etapas.

## Conclusões

1. **O PCPR é o dono do estado; o n8n trabalha nas bordas; a IA só propõe.** O sistema já tem outbox
   transacional, rotinas diárias, importação documental com OCR (que lê e direciona documentos) e
   conferência de vias assinadas. A orquestração interna (o que é devido, para quem, em que versão) fica
   no PCPR; o n8n transporta para canais, agenda, consulta integrações externas e roteia alertas. Isso
   evita regras duplicadas em workflows e mantém tudo testável. — [arquitetura.md](arquitetura.md)
2. **Falta a fundação, não a ferramenta.** Não existe hoje nenhuma API para máquina (só JSON de tela com
   sessão), a outbox tem um assinante por tópico e segura a transação durante o assinante, servidores
   viajantes não são usuários e não têm e-mail cadastrado. A etapa 1 do plano (API de automação v1,
   eventos de integração com worker de entregas, `Comunicacao`, `ContatoVerificado`, `LinkAcesso`, fila de
   exceções) destrava quase tudo.
3. **WhatsApp é prioridade, com a plataforma oficial ainda bloqueada.** A política oficial do WhatsApp
   Business (atualizada em 23/09/2026, consultada em 17/10/2026) proíbe autoridades policiais na
   plataforma, sem exceção; provedores também recusam. Por decisão do usuário, o WhatsApp entra como
   prioridade em três frentes: envio assistido pelo aparelho institucional com registro no sistema (já),
   consulta formal à Meta/provedor e integração oficial construída, testada contra simulador e exportada
   desligada, presa a um portão de autorização. Os fluxos são independentes de canal (portal, notificações
   internas, e-mail institucional), então ligar o WhatsApp não muda estados nem regras. —
   [whatsapp-viabilidade.md](whatsapp-viabilidade.md) · [plano](plano-implantacao.md)
4. **Hospedagem:** instalar o n8n no Ubuntu atual (Docker já existe); **não** reinstalar pela template —
   ela apaga a VPS e traz Traefik disputando 80/443. A VPS medida comporta n8n em modo normal com swap e
   limites de memória; IA local não cabe. — [hospedagem-n8n.md](../ops/mudanca-hospedagem/hospedagem-n8n.md)
5. **"Mensagem de saque"** = aviso de liberação de diárias. O gatilho real é o operador registrar nº da
   solicitação, liberação e prazo (dado externo); hoje sai por link wa.me manual, sem registro. Vira
   comunicação determinística com lembretes até o comprovante entrar — sem IA. — [10-3](fluxos/10-3-prestacao-e-mensagem-de-saque.md)
6. **Link de KM na véspera** não existe no sistema novo, mas o Eventos Sociais em produção já tem o
   desenho (link pessoal, PWA offline, lançamentos idempotentes). O fluxo especifica a versão segura
   (token só em hash, escopo, revogação, pré-visualização inofensiva, D−1 09:00 America/Sao_Paulo com
   regras de cima da hora, reagendamento e silêncio durante o deslocamento). — [10-4](fluxos/10-4-link-de-km-na-vespera.md)

## Números

| | |
|---|---|
| Processos examinados (sistema novo + 2 sistemas em produção) | 164 — [inventário](inventario-processos.md) |
| Oportunidades levantadas → itens consolidados | 337 → 171, mais 3 frentes de WhatsApp (AUT-172…174) = **174** — [matriz](matriz-oportunidades.md) |
| Por classificação | n8n 25 · IA 13 · determinística 51 · próprio sistema 27 · desenvolvimento 16 · integração externa 15 · inadequada 27 |
| Por maturidade | 1: 4 · 2: 91 · 3: 40 · 4: 11 · 5: 28 |
| Fichas implementáveis | 174 em 3 arquivos — [fichas/](fichas/) |
| Fluxos detalhados | 10 (10.1–10.6, 11.1–11.3, 13) — [fluxos/](fluxos/) |
| Protótipo local | n8n 2.43.7 + simuladores do PCPR, do canal e da Graph API (dados sintéticos): suíte principal **T1–T13: 13/13** na rodada final; WhatsApp oficial **TW0–TW13** passaram — [prototipo/](prototipo/README.md) |

## O que foi executado × o que é desenho

| Executado (com evidência) | Só desenhado |
|---|---|
| Leitura do código do sistema novo e das duas referências implantadas (commits identificados) | API de automação, eventos de integração, worker de entregas, `Comunicacao`, `ContatoVerificado`, `LinkAcesso`, fila de exceções |
| Pesquisa em fontes oficiais (WhatsApp/Meta, n8n, Hostinger, preços de IA, mapas, e-mail) com data | Link de KM, DB/RT para assinatura, recebimento por portal/e-mail, assistente, textos de Plano por IA, proposta consolidada |
| Medição da VPS (sysstat) e dos tempos do PREVIEW | Integrações com eProtocolo e Central de Viagens |
| Protótipo: 8 workflows n8n (exportados com `"active": false`) contra simuladores; T1–T13 (duplicidade, assinatura inválida, versão obsoleta, desligamento, falha de canal, evento perdido, reinício do n8n, arquivo duplicado, regra da véspera, retenção de dados no n8n) | Execução contra o PCPR real (a API ainda não existe) |
| WhatsApp oficial (WA-3) contra um simulador da Graph API: templates, janela de 24 h, mídia com URL que expira, status fora de ordem, `X-Hub-Signature-256`, canal bloqueado → envio manual, contato sem opt-in; recebimento pelo n8n × direto no PCPR (retenção medida) | Qualquer contato com a Meta; ativação (presa ao portão de autorização) |

## Mapa dos documentos

- **Base:** [arquitetura.md](arquitetura.md) · [contratos/](contratos/) (OpenAPI da API de automação, JSON
  Schema do evento, exemplos sintéticos) · [plano-implantacao.md](plano-implantacao.md)
- **Levantamento:** [inventario-processos.md](inventario-processos.md) ·
  [matriz-oportunidades.md](matriz-oportunidades.md) · [fichas/](fichas/)
- **Fluxos (seções 10, 11 e 13 da missão):**
  [10-1 assistente](fluxos/10-1-assistente-dos-servidores.md) ·
  [10-2 envio de documentos](fluxos/10-2-envio-de-documentos.md) ·
  [10-3 prestação e saque](fluxos/10-3-prestacao-e-mensagem-de-saque.md) ·
  [10-4 link de KM](fluxos/10-4-link-de-km-na-vespera.md) ·
  [10-5 DB/RT para assinatura](fluxos/10-5-db-e-rt-para-assinatura.md) ·
  [10-6 recebimento](fluxos/10-6-recebimento-de-documentos.md) ·
  [11-1 rotas](fluxos/11-1-rotas-e-roteiros.md) ·
  [11-2 textos de Plano](fluxos/11-2-textos-de-plano-de-trabalho.md) ·
  [11-3 autonomia](fluxos/11-3-autonomia-progressiva.md) ·
  [13 eProtocolo e Central de Viagens](fluxos/13-integracoes-institucionais.md)
- **Canais, desempenho e custos:** [whatsapp-viabilidade.md](whatsapp-viabilidade.md) ·
  [desempenho-e-custos.md](desempenho-e-custos.md)
- **Protótipo e workflows:** [prototipo/README.md](prototipo/README.md) · [n8n/README.md](n8n/README.md)
- **Hospedagem:** [../ops/mudanca-hospedagem/](../ops/mudanca-hospedagem/README.md)

## Dependências e bloqueios

Cópia externa do backup (bloqueia qualquer mudança na VPS) · SMTP e caixa postal institucionais · base
legal do contato dos servidores (LGPD) · leitura do Decreto PR 7.304/2021 (complemento, não substituto, do
eProtocolo) · regras institucionais marcadas `[decisão]` nos fluxos · provedor e orçamento de IA ·
credenciais e API do eProtocolo e da Central de Viagens · WhatsApp oficial (prioridade; ativação presa à autorização formal da Meta/provedor e à decisão da PCPR).
