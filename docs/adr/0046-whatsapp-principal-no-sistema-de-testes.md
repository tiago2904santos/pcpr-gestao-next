# ADR 0046 — Priorizar WhatsApp Business no sistema de testes independente

- **Status:** aceito
- **Data:** 2026-10-18

## Contexto

O plano de 17/10/2026 classificou o WhatsApp Business como bloqueado sob a premissa de uso
institucional policial. Em 18/10/2026, o usuário esclareceu: o site não é oficial da polícia,
não vai operar com policiais e é apenas um sistema de testes; pediu WhatsApp Business como
canal principal. Essa declaração substitui a premissa de implantação do piloto.

Evidências: [regra de produto](../product/automacao-whatsapp-testes.md),
[revisão documentada](../automacao/revisao-whatsapp-testes-2026-10-18.md) e
[protótipo sintético existente](../automacao/prototipo/README.md).

## Decisão

Planejar WhatsApp Business Platform (Cloud API oficial) como canal principal do piloto
independente, com dados administrativos fictícios e contatos de teste autorizados.

- Portal e notificações internas dão suporte; e-mail é alternativa opcional.
- Começar pelo simulador e evoluir para LAB dedicado conectado aos recursos de teste da Meta.
- PREVIEW/DEMO público continua simulado, sem segredos nem envio externo.
- O responsável real cadastra a conta com identidade correta, sem representar a PCPR.
- O estado inicial planejado é `desligado`, não `bloqueado` por presunção de uso policial.
- Manter opt-in, lista de destinatários, limites, assinatura de webhook, versionamento,
  idempotência, registro de resultados e chave de desligamento.
- Manter decisões e estado no PCPR; n8n como transporte; preferir entrada direta no PCPR
  para reduzir retenção de conteúdo no n8n (variante V2).
- Nenhuma conta, workflow ou canal externo é ativado por esta alteração documental.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Bloquear todo WhatsApp até autorização de órgão policial | Usa uma premissa substituída pelo usuário; o piloto não é institucional policial |
| Usar e-mail como principal e WhatsApp apenas manual | Não atende à prioridade e ao canal principal pedidos |
| Automatizar WhatsApp Web ou aplicativo por biblioteca não oficial | Não é a integração oficial escolhida para o piloto |
| Colocar credenciais no PREVIEW/DEMO público | Permitiria que visitantes disparassem mensagens externas |

## Consequências

Plano, resumo, viabilidade e contrato passam a distinguir piloto independente de implantação
institucional futura. A matriz de 174 itens e os relatórios de 17/10 permanecem como base
histórica; a revisão publica a reclassificação aplicável ao piloto sem falsear esses resultados.
Cloud API real exige onboarding e validação próprios; aprovação não é presumida. Custos do
canal são parte do orçamento do piloto, a confirmar pelos recursos e tarifas aplicáveis.

Uso oficial futuro, dados reais ou público policial exigem outra revisão de escopo e políticas;
esta decisão não muda as permissões dos agentes sobre os sistemas de referência em produção.
