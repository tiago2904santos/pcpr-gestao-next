"""WhatsApp Business Platform (Cloud API oficial) atrás de uma porta (ADR 0019, ADR 0046).

Recebe e devolve só primitivos (endereço E.164, texto, ids): não conhece servidor, usuário
nem prestação — quem decide para quem e por quê é o contexto `gestao.automacao`.
Referência da API: docs/integrations/whatsapp-cloud-api-referencia.md.
"""
