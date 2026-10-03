# ADR 0019 — Integrações externas moram em `gestao/integracoes/`, atrás de portas

- **Status:** aceito
- **Data:** 2026-10-03

## Contexto
O roadmap de migração (`docs/migration/roadmap.md`) traz integrações reais: eProtocolo
(consulta, abertura de protocolo, importação de processo), e futuramente Central de Viagens,
WhatsApp, e-mail e um assistente de IA. A referência mostrou o que funciona (configuração em
um lugar só, modo simulado sem credencial, trava de somente leitura, falha vira aviso,
diagnóstico sem rede — `docs/integrations/eprotocolo.md`) e o que dói (chamadas espalhadas
dificultam teste e auditoria).

## Decisão
Toda integração externa é um subpacote de `gestao/integracoes/<nome>/` com:
`config.py` (única leitura de settings/variáveis), `porta.py` (Protocol tipado com as
operações), `adaptadores.py` (`Simulado` — padrão —, real, e um gravado para teste),
`erros.py`, `servico.py` (casos de uso que os contextos chamam) e comando de diagnóstico.
Regras:
1. Domínio (`*/dominio/`) não importa integrações; views não importam adaptadores.
2. Escrita em sistema externo nunca roda dentro da transação de negócio: vai pela outbox
   (ADR 0005), com idempotência.
3. Ambiente real exige configuração explícita; mutação real exige trava aberta explicitamente.
4. Logs mascaram segredos e dados pessoais; métricas de duração/status por operação.
5. `gestao.integracoes` não depende de contextos de negócio (import-linter); os contextos
   dependem dela.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Cliente HTTP chamado direto dos `services.py` | acopla regra de negócio a transporte; teste exige rede ou mock frágil |
| Integrações dentro de cada contexto (`viagens/eprotocolo.py`) | eProtocolo serve ofícios, prestação e eventos; duplicaria configuração e travas |
| Delegar integrações ao n8n | perde tipagem, teste e auditoria no núcleo; ver ADR 0020 |

## Consequências
Toda integração nasce testável e simulada; a primeira com credencial real (eProtocolo em
treinamento) troca só o adaptador. Novo contrato no import-linter.
