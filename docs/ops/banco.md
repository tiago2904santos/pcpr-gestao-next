# Banco de dados (PostgreSQL 16)

## Papéis
| Papel | Uso | Privilégios |
|---|---|---|
| `pcpr_owner` | Migrações (deploy) | Dono do schema; cria extensões (`unaccent`) |
| `pcpr_app` | Aplicação e worker | SELECT/INSERT/UPDATE/DELETE nas tabelas de negócio; **apenas INSERT/SELECT** em `auditoria_evento` |
| `pcpr_leitura` | Ferramentas do agente (MCP), relatórios | Somente SELECT |

```sql
REVOKE UPDATE, DELETE, TRUNCATE ON auditoria_evento FROM pcpr_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pcpr_leitura;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO pcpr_leitura;
```
Além dos privilégios, o trigger `auditoria_evento_imutavel` bloqueia UPDATE/DELETE/TRUNCATE
mesmo para quem tiver privilégio (defesa em profundidade). Verificação periódica:
`manage.py verificar_auditoria` (cron diário; falha = alerta).

## Extensões
`unaccent` (busca sem acento). Criada pela migração `plataforma.0002`; em produção, se o
papel da aplicação não puder criar extensões, o DBA executa `CREATE EXTENSION unaccent;` antes.

## Backups
`pg_dump` diário + WAL contínuo (PITR). Os PDFs emitidos (`MEDIA_ROOT/documentos/`) entram
no mesmo backup; o SHA-256 gravado em `viagens_documento` permite verificar integridade.
