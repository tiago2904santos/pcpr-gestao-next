# Página atual

| Campo | Valor |
|---|---|
| Módulo | Viagens → **Ofícios** |
| Página | **Lista de ofícios** (`/viagens/oficios/`) |
| Agente responsável | 3 — QA (Lote 3) |
| Análise do legado | **concluída** — `parity/oficios-lista.md` (matriz L1–L80, defeitos F1–F16) |
| Implementação | plano aprovado (`visual/oficios-lista-plano.md`, LP-01…LP-33); **Lote 1 APROVADO pelo QA** (LP-01…LP-12 + correções pós-QA); **Lote 2 APROVADO**; **Lote 3 implementado** (LP-30…LP-33 + saneamento dos 3 e2e + menores M5/M8/M-R1/M-R2/M-R4, `visual/oficios-lista-lote3.md`) — aguardando QA |
| Testes executados | QA do Lote 1: 26 rotas × 6 larguras contra o main, axe 11 larguras, benchmark legado × novo, consultas SQL (`qa/oficios-lista-lote1.md`) |
| Problemas encontrados | ver `parity/oficios-lista.md` e `visual/oficios-lista.md` |
| Problemas resolvidos | P2–P5, P9, P10, P12, P13 (parcial) do diagnóstico; B1, B2, I1–I3, RB1 do QA |
| Pendências | QA do Lote 3; **confirmar com o dono do produto a página Numeração** (excluída a pedido em `4a3f835`, recriada por D9); importação do eProtocolo (sub-projeto); e2e vermelhos das folhas (não da lista, iguais em `a10a831`) |
| Próximo passo | QA do Lote 3 → fechar a lista (completed-pages) → resumo/detalhes |

## Log
- 2026-10-06 — ambiente montado (NOVO :8000 PREVIEW semeado; LEGADO :8001 do backup de 05/10). Branch `viagens/reconstrucao` criado.
- 2026-10-06 — Agente 1 entregou paridade da lista e inventário de Ofícios; inventário de Viagens (288 itens) em `inventory.md`; Agente 2 entregou identidade de referência, catálogo de componentes e diagnóstico (P1–P14). Orquestrador aprovou o plano D1–D11.
- 2026-10-07 — Lote 1 implementado (19 commits), QA reprovou 2× (B1/B2 regressões em outras listas; RB1 target-size a 768), Designer corrigiu na origem, QA APROVOU (Re-QA 2, `34d8d1d`). Decisão: motorista primeiro na equipe com "(motorista)" visível.
- 2026-10-07 — Lote 2 implementado: abas temporais + filtro Documento, gaveta com fichas, busca (placa, destino ≠ sede, unaccent), vazios/erro, `voltar` vivo, contagens, XLSX. Relatório em `visual/oficios-lista-lote2.md`.
- 2026-10-07 — Lote 2: abas temporais com regra do legado (`dominio/recorte.py`), filtro Documento, contadores do recorte, gaveta/folha modal + fichas, Ano, busca placa/destino/acentos, erro HTMX. QA reprovou 1× (folha do celular cortava calendário; modal falso), corrigido, APROVADO (`651d666`).
- 2026-10-07 — Lote 3: ⋮ canônico com itens descritos (lista, painel e resumo; itens sob demanda; folha no celular; véu), "Mais" da barra, página Numeração (domínio explica o próximo; histórico da trilha), docs do DS, 3 e2e do main verdes, menores M5/M8/M-R1/M-R2/M-R4. Relatório em `visual/oficios-lista-lote3.md`.
