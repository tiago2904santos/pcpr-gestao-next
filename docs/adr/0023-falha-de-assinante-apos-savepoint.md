# ADR 0023 — Registrar falha do assinante após rollback

- Status: aceito para correção F1 do Lote H; data: 07/10/2026.

## Contexto

ADR 0005 executa o assinante em savepoint. Gravar Documento.FALHOU dentro dele
e relançar apaga o estado na reversão, mantendo a tela em Gerando indefinidamente.
A plataforma não pode importar Viagens.

## Decisão

O registro `assinante` aceita callback opcional `ao_falhar(payload, erro)`. O worker
o chama após reverter o savepoint do processamento, dentro da transação da mensagem.
O callback tem seu próprio savepoint; falha nele é registrada em log, preservando
a tentativa e o backoff. Assinantes existentes mantêm contrato e comportamento.
Viagens registra seu estado de falha nesse callback, sem dependência inversa.

## Alternativas e consequências

Engolir a exceção marcaria a mensagem como processada e perderia o backoff automático.
Transação independente não participa atomicamente do registro da tentativa. O callback
preserva ambos, com teste de rollback pelo worker e regressão da outbox existente.
