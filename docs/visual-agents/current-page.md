# Página atual

| Campo | Valor |
|---|---|
| Módulo | Viagens → **Ofícios** |
| Página | **Folha do ofício — Lote H (correções urgentes)**, depois Resumo → Folha → Documentos |
| Agente responsável | Codex principal; paridade/recuperação e QA como revisões delimitadas |
| Análise do legado | **concluída** — `parity/oficios-folha.md`, `parity/oficios-resumo.md`, `parity/oficios-documentos.md` |
| Implementação | H implementado em commits locais até `44b3186`; domínio RS-01 em `b0829d6`. D13 confirmada pelo usuário em 07/10. H ainda em validação |
| Testes executados | 30 testes finais de navegador verdes; 31 testes de consultas/cadastros verdes; primeira suíte completa com 6 falhas corrigidas, nova suíte em execução. Desempenho: 3 falhas registradas |
| Problemas encontrados | G1 salvar desmarca o motorista (perda de dado, desde `afcf0dd`); F1 geração que falha fica "gerando" para sempre; G2 data do ofício na emissão; G3 "Outro meio"; 6 e2e vermelhos da folha |
| Problemas resolvidos | Lista de ofícios concluída (ver `completed-pages.md`) |
| Pendências | Lotes H, RS, FL, DC; perguntas ao dono no plano |
| Próximo passo | Concluir verificação completa, corrigir coletor de desempenho e medir excessos reais; então integrar RS |

## Checkpoint de execução — 07/10/2026 16:35

- HEAD `b0829d6`, seis commits locais na branch `viagens/reconstrucao`; main
  preservada em `8d1d77e`, nenhum push/merge. O checkpoint anterior abaixo é histórico.
- Chromium: **30 passaram em 384,93 s**, incluindo jornada de emissão, motorista,
  retry com PDF real, calendário, teclado, duas abas, cinco larguras e cadastro de
  servidor afetado pela redução de consultas. Log `var/lote-h-browser-checkpoint.log`.
- Capturas finais renovadas: 30 PNGs antes/depois/comparação em `evidencias/lote-h/`.
  Medições de servidor e limites metodológicos constam em `qa/oficios-lote-h.md`.
- Axe da folha: passou. Desempenho de lista, resumo e folha: três falhas,
  `var/lote-h-perf-axe.log`. Coletor de respostas também tem erro de ciclo de vida;
  isso não explica automaticamente os excessos medidos. Budgets mantidos.
- `scripts/verificar.sh` em execução, dois workers, banco independente
  `pcpr_lab_verificar`; log `var/lote-h-verificar-final.log`. Lint, 16 fronteiras,
  mypy (299 arquivos), bandit, migrações e tipos JS passaram; testes ainda pendentes.
- Produto congelado durante essa execução. RS-01 tem domínio puro testado e
  especificação em revisão, sem adaptador ou UI. Preview próprio continua em :8010
  com banco e mídia isolados. Incidente anterior de mídia descrito no relatório QA.

## Checkpoint de execução — 07/10/2026 15:38

- Branch `viagens/reconstrucao`, base `8d1d77efb1e5785553fd74b9906bddc6369207c9`.
  Main e remoto permaneceram nessa base nas consultas realizadas após a resposta do usuário.
  Alterações H ainda não commitadas; nenhum push/merge.
- Relatório detalhado e incidente de mídia: `qa/oficios-lote-h.md`.
  Regra vigente: `../product/oficios-lote-h.md`; ADR 0023 para falhas da outbox.
- LAB independente: PostgreSQL local `127.0.0.1:55432`, cluster em
  `%LOCALAPPDATA%/pcpr-codex-lab/pgdata`. Bancos de teste separados.
- Em execução: verificação completa (4 workers, `var/lote-h-verificar.log`, 91%,
  quatro falhas com diagnóstico final pendente); rodada focada + e2e da folha
  (`var/lote-h-regressao-final.log`). Novo teste de retry por teclado/axe ainda não executado.
- Capturas ANTES finais: reprodução em arquivo isolado do commit-base, 1 teste passou
  em 114,44 s; relógio fixo, cinco larguras. Capturas DEPOIS finais e comparações pendentes.
- Preview próprio: `http://127.0.0.1:8010/viagens/oficios/`, 258 ofícios fictícios.
  Mídia isolada em `%LOCALAPPDATA%/pcpr-codex-lab/preview-media`, wrapper local
  `var/preview_lote_h.py`; worker próprio interrompido após gerar o último ofício.
- RS investigado somente por leitura: eProtocolo, reabrir, histórico, versões documentais,
  atualização do rodapé e metadados ainda têm lacunas. Não aprovado nem implementado.

## Log
- 2026-10-06 — ambiente montado (NOVO :8000 PREVIEW semeado; LEGADO :8001 do backup de 05/10). Branch `viagens/reconstrucao` criado.
- 2026-10-06 — Agente 1 entregou paridade da lista e inventário de Ofícios; inventário de Viagens (288 itens) em `inventory.md`; Agente 2 entregou identidade de referência, catálogo de componentes e diagnóstico (P1–P14). Orquestrador aprovou o plano D1–D11.
- 2026-10-07 — Lote 1 implementado (19 commits), QA reprovou 2× (B1/B2 regressões em outras listas; RB1 target-size a 768), Designer corrigiu na origem, QA APROVOU (Re-QA 2, `34d8d1d`). Decisão: motorista primeiro na equipe com "(motorista)" visível.
- 2026-10-07 — Lote 2 implementado: abas temporais + filtro Documento, gaveta com fichas, busca (placa, destino ≠ sede, unaccent), vazios/erro, `voltar` vivo, contagens, XLSX. Relatório em `visual/oficios-lista-lote2.md`.
- 2026-10-07 — Lote 2: abas temporais com regra do legado (`dominio/recorte.py`), filtro Documento, contadores do recorte, gaveta/folha modal + fichas, Ano, busca placa/destino/acentos, erro HTMX. QA reprovou 1× (folha do celular cortava calendário; modal falso), corrigido, APROVADO (`651d666`).
- 2026-10-07 — Lote 3: ⋮ canônico com itens descritos (lista, painel e resumo; itens sob demanda; folha no celular; véu), "Mais" da barra, página Numeração (domínio explica o próximo; histórico da trilha), docs do DS, 3 e2e do main verdes, menores M5/M8/M-R1/M-R2/M-R4. Relatório em `visual/oficios-lista-lote3.md`.
- 2026-10-07 — Lote 3 (menu ⋮ canônico com grupos, carga sob demanda, 401 em pedidos assíncronos sem sessão, barra "Mais") aprovado; Numeração revertida por decisão anterior do dono (D9 revogada). **Lista de ofícios CONCLUÍDA.** Paridade de folha/resumo/documentos entregue; plano D12–D18.
