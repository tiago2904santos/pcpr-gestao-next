# Mudança de hospedagem e automação com n8n — registro da missão (17/10/2026)

Missão em duas fases pedida em 17/10/2026: (1) cópia completa e restaurável dos sistemas hospedados na
VPS antes de uma possível mudança de hospedagem; (2) auditoria de automação com n8n e IA. A mudança da
VPS e a ativação de automações reais são **decisões posteriores**, fora desta missão.

## Documentos

| Documento | Conteúdo |
|---|---|
| [backup-e-recuperacao.md](backup-e-recuperacao.md) | Método do backup, ponto de corte, restauração testada, as cinco situações, download e conferência no Windows, cópia final do dia da mudança |
| [capacidade-vps.md](capacidade-vps.md) | CPU, memória, disco e rede medidos (sysstat 09–17/10) |
| [hospedagem-n8n.md](hospedagem-n8n.md) | Alternativas de hospedagem com n8n, comparação e recomendação |
| [`../../automacao/`](../../automacao/README.md) | Fase 2: inventário, matriz de oportunidades, fichas, fluxos, contratos, protótipo e plano |

Fora do repositório (público): o pacote cifrado, a senha, o inventário com achados de segurança da
infraestrutura (`INVENTARIO-E-ACHADOS.md`, dentro do pacote) e os scripts com caminhos de produção
(também dentro do pacote, em `ferramentas/`).

## Registro de progresso (para retomar)

| Quando (UTC) | O que | Situação |
|---|---|---|
| 17/10 04:10–04:30 | Inventário somente leitura por SSH (serviços, nginx, bancos, Redis, mídia, Git, cron, certificados) | ✅ |
| 17/10 04:41–04:45 | Backup com snapshots exportados + hardlinks; pacote cifrado de 1,56 GB | ✅ |
| 17/10 05:01–05:04 | Restauração-teste isolada a partir dos arquivos finais | ✅ (ressalvas preexistentes) |
| 17/10 05:20–05:30 | Relatório, instruções e ferramentas no pacote; texto claro apagado da VPS | ✅ |
| 17/10 05:10–07:00 | Fase 2: leitura do código (sistema novo + referências implantadas), pesquisa em fontes oficiais | ✅ |
| 17/10 06:53–06:59 (03:53–03:59 em Brasília) | Protótipo local n8n 2.43.7 com simuladores: T1–T12 passaram | ✅ |
| 17/10 06:00–08:00 e 00:45– (18/10) | Fluxos, matriz, fichas, custos, revisão adversarial e correções | ✅ |
| — | Cópia externa do backup (computador e HD) | registrada no inventário privado |

Nenhum serviço de produção foi parado, reiniciado ou alterado. Nenhuma mensagem foi enviada a servidores.
