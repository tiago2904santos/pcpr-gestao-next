# ADR 0005 — Efeitos colaterais por outbox transacional

- **Status:** aceito · **Data:** 2026-10-01

## Contexto
Emitir um ofício gera PDF, notificações e (futuro) integração com eProtocolo. Fazer isso
dentro da requisição deixa o usuário esperando e perde efeitos se a requisição cair.

## Decisão
`plataforma.outbox.publicar(topico, payload, chave=…)` grava `MensagemOutbox` **na mesma
transação** da mudança de negócio (falha fora de transação). Worker
`manage.py processar_outbox` consome com `SELECT … FOR UPDATE SKIP LOCKED`, acorda por
`LISTEN/NOTIFY`, aplica backoff exponencial (5s→1h) e desiste após 8 tentativas
(situação `falhou`, visível ao administrador). Assinantes são idempotentes; a chave de
idempotência impede publicação duplicada.

## Alternativas
| Alternativa | Por que não |
|---|---|
| Celery + Redis | Mais uma infraestrutura; sem atomicidade com o banco |
| `django.tasks` (Django 6) | Interface boa, mas backends nativos não são persistentes; o worker próprio pode virar backend dele depois |
| Executar na requisição | Lento e frágil |

## Consequências
Precisa de um processo a mais em produção (systemd `pcpr-outbox.service`). O PDF do ofício
fica "Gerando…" por alguns segundos; a tela atualiza via HTMX.
