# Orquestração — n8n × alternativas

Comparação de 03/10/2026 para decidir **onde** cada tipo de automação mora.

| Opção | Bom para | Ruim para | Veredito |
|---|---|---|---|
| **Outbox + worker próprio** (já existe, ADR 0005) | efeitos da transação de negócio (PDF, eventos, abrir protocolo), idempotência, auditoria | fluxos visuais, integrações SaaS variadas | **Fica com tudo que é transacional e crítico** |
| **n8n** (auto-hospedado) | webhooks, notificações (e-mail, WhatsApp), integrações com serviços externos, rotinas agendadas, protótipos de fluxo com IA; tem *MCP Server Trigger* (expõe fluxos como ferramentas) e *MCP Client Tool* | regra de negócio transacional; aprovação humana dentro de chamada MCP **não é suportada** (documentação do n8n); versionamento/teste mais fraco que código | **Camada de orquestração periférica**, chamando o PCPR pela API |
| Celery + Redis | filas de tarefas Python em volume | duplicaria a outbox; mais um serviço | Desnecessário hoje |
| Temporal (workflow engine) | processos longos com estado durável e compensação (ex.: prestação de contas de semanas) | infraestrutura pesada para o porte atual | Reavaliar só se os fluxos longos crescerem muito |
| Framework de agente (SDK de agentes) | planejamento + chamadas de ferramenta pela IA | não é orquestrador de integrações | Usar **dentro** do assistente de IA, sobre a camada de ferramentas |
| Arquitetura própria (Tool/Policy Registry no Django) | política, autorização por objeto, aprovação, auditoria no banco | — | **Obrigatória**: é a fronteira de segurança, qualquer que seja o orquestrador |

## Decisão proposta (ADR 0020)

```
PCPR Gestão (Django + PostgreSQL) — fonte da verdade
  ├── outbox/worker ─ efeitos transacionais
  └── API de ferramentas (tipadas, com política, aprovação e auditoria)
          ▲
          │ HTTPS + token de serviço com escopo
  n8n ─── orquestração periférica (webhooks, notificações, agenda, IA de apoio)
          │
  LLM / assistente ─ planeja e chama ferramentas; ações críticas param no portão de aprovação
```

O n8n **nunca** grava direto no banco nem guarda regra de negócio. Se for desligado, o
sistema continua funcionando; só perde automações periféricas.
