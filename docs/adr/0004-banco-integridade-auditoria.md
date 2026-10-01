# ADR 0004 — PostgreSQL como guardião de integridade e auditoria

- **Status:** aceito · **Data:** 2026-10-01

## Contexto
A referência registra auditoria pela aplicação (`LogAuditoria`, `HistoricoSolicitacao`),
o que deixa de fora alterações feitas por scripts, shell ou bugs que esquecem de logar.

## Decisão
1. **Trilha técnica pelo banco**: trigger genérico `auditoria_registrar()` em toda tabela de
   negócio grava INSERT/UPDATE/DELETE em `auditoria_evento` com `antes`, `depois`, colunas
   alteradas, usuário, IP e id da requisição (contexto via `set_config('app.*')` pelo
   middleware). Senhas/tokens removidos.
2. **Imutável**: UPDATE/DELETE/TRUNCATE em `auditoria_evento` bloqueados por trigger; em
   produção o papel da aplicação também não tem esses privilégios (`docs/ops/banco.md`).
3. **Evidência de adulteração**: cadeia SHA-256 (`hash = sha256(hash_anterior || conteúdo)`),
   serializada por *advisory lock*; `manage.py verificar_auditoria` recalcula.
4. **Histórico de negócio** (o que o usuário vê: "Emitido por Fulano") é tabela própria do
   contexto, gravada na mesma transação pelo serviço.
5. **Invariantes como constraints**: número de ofício único por ano, valores ≥ 0, datas
   coerentes, um motorista por ofício — o banco recusa estados inválidos mesmo fora da app.
6. Testes rodam em **PostgreSQL real** (nunca SQLite).

## Consequências
Escritas auditadas ficam serializadas (aceitável: dezenas por minuto). Toda nova tabela de
negócio precisa de `auditar_tabela()` na migração (checklist do PR).
