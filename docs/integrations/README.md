# Integrações

| Documento | Conteúdo |
|---|---|
| [eprotocolo.md](eprotocolo.md) | Documentação oficial, credenciamento, comportamento da referência, arquitetura e fases |
| [central-de-viagens.md](central-de-viagens.md) | Sistema estadual; sem API pública; canal institucional |
| [hostinger.md](hostinger.md) | Infraestrutura atual, necessidade estimada, desenho com n8n |
| [orquestracao.md](orquestracao.md) | n8n × outbox × Celery × Temporal × agentes; onde cada um entra |

Mapa geral das integrações do produto: [`docs/product/integrations.md`](../product/integrations.md).

## Regras da camada (`gestao/integracoes/`, ADR 0019)

Cada integração tem: cliente (transporte), autenticação, **porta tipada** + adaptadores
(`Simulado`, real, gravado para teste), mapeamento domínio ↔ externo, erros próprios, timeout,
retentativa com backoff (via outbox quando é escrita), logs com dados mascarados, métricas
(duração, status), diagnóstico por comando de gestão e **modo simulado por padrão**.
Nunca chamar serviço externo de view ou do domínio; nunca segredo fora de variável de ambiente.
