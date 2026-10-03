# ADR 0020 — Automação (IA e n8n) só por ferramentas com política, aprovação e auditoria

- **Status:** proposto (implementação a partir da fase A — leitura)
- **Data:** 2026-10-03

## Contexto
O objetivo de longo prazo é um agente operacional de IA que faça a maior parte do trabalho
repetitivo (preparar ofício, consultar protocolo, conferir prestação), e o n8n na VPS Hostinger
é candidato a orquestrador de webhooks, notificações e rotinas. Sem fronteira, uma IA ou um
fluxo do n8n acabariam com acesso direto ao banco ou a views, sem política nem trilha.
Estudo: `docs/ai/README.md`, `docs/integrations/orquestracao.md`.

## Decisão
1. O PCPR Gestão é a fonte da verdade; a outbox fica com os efeitos transacionais.
2. Automação externa (assistente de IA, n8n, clientes MCP) acessa o sistema **apenas** por um
   registro de ferramentas tipadas (`gestao/automacao/`), cada uma com classe de risco,
   política (as mesmas `policies.py`, avaliadas para o usuário representado), idempotência,
   timeout e auditoria.
3. Ferramentas `irreversivel` (emitir, cancelar, retificar emitido, abrir protocolo oficial,
   assinar, encaminhar, excluir) **nunca executam direto**: criam um pedido de aprovação que um
   humano com permissão aprova na tela.
4. MCP é um transporte possível, como fachada fina sobre o registro.
5. n8n é periférico: chama a API de ferramentas com token de serviço; não grava no banco, não
   guarda regra de negócio. Desligado o n8n, o sistema funciona.
6. Loop de desenvolvimento (agentes de código) e loop operacional (agente do produto) são
   separados: credenciais, ferramentas e ambientes distintos.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| IA com acesso SQL de leitura e escrita | sem política por objeto, sem aprovação, auditoria fraca |
| n8n como núcleo de processos | regra de negócio fora do código testado; aprovação humana dentro de MCP não suportada |
| Temporal/Celery agora | infraestrutura além da necessidade; outbox cobre os efeitos atuais |

## Consequências
Cada módulo migrado ganha, além das telas, ferramentas de leitura correspondentes. Novos
modelos `PedidoAprovacao` e `ExecucaoFerramenta` quando a fase A começar. O assistente só
evolui para ações críticas depois do portão de aprovação testado.
