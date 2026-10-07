# Página atual

| Campo | Valor |
|---|---|
| Módulo | Viagens → **Ofícios** |
| Página | **Folha do ofício — Lote H (correções urgentes)**, depois Resumo → Folha → Documentos |
| Agente responsável | 2 — Design Lead (implementação do Lote H) |
| Análise do legado | **concluída** — `parity/oficios-folha.md`, `parity/oficios-resumo.md`, `parity/oficios-documentos.md` |
| Implementação | plano aprovado (`visual/oficios-detalhe-plano.md`, D12–D18); Lote H em andamento |
| Testes executados | suíte rápida após a lista: 1837 ✓ / 1 ✗ de ambiente |
| Problemas encontrados | G1 salvar desmarca o motorista (perda de dado, desde `afcf0dd`); F1 geração que falha fica "gerando" para sempre; G2 data do ofício na emissão; G3 "Outro meio"; 6 e2e vermelhos da folha |
| Problemas resolvidos | Lista de ofícios concluída (ver `completed-pages.md`) |
| Pendências | Lotes H, RS, FL, DC; perguntas ao dono no plano |
| Próximo passo | Lote H → QA → Lote RS |

## Log
- 2026-10-06 — ambiente montado (NOVO :8000 PREVIEW semeado; LEGADO :8001 do backup de 05/10). Branch `viagens/reconstrucao` criado.
- 2026-10-06 — Agente 1 entregou paridade da lista e inventário de Ofícios; inventário de Viagens (288 itens) em `inventory.md`; Agente 2 entregou identidade de referência, catálogo de componentes e diagnóstico (P1–P14). Orquestrador aprovou o plano D1–D11.
- 2026-10-07 — Lote 1 implementado (19 commits), QA reprovou 2× (B1/B2 regressões em outras listas; RB1 target-size a 768), Designer corrigiu na origem, QA APROVOU (Re-QA 2, `34d8d1d`). Decisão: motorista primeiro na equipe com "(motorista)" visível.
- 2026-10-07 — Lote 2 implementado: abas temporais + filtro Documento, gaveta com fichas, busca (placa, destino ≠ sede, unaccent), vazios/erro, `voltar` vivo, contagens, XLSX. Relatório em `visual/oficios-lista-lote2.md`.
- 2026-10-07 — Lote 2: abas temporais com regra do legado (`dominio/recorte.py`), filtro Documento, contadores do recorte, gaveta/folha modal + fichas, Ano, busca placa/destino/acentos, erro HTMX. QA reprovou 1× (folha do celular cortava calendário; modal falso), corrigido, APROVADO (`651d666`).
- 2026-10-07 — Lote 3: ⋮ canônico com itens descritos (lista, painel e resumo; itens sob demanda; folha no celular; véu), "Mais" da barra, página Numeração (domínio explica o próximo; histórico da trilha), docs do DS, 3 e2e do main verdes, menores M5/M8/M-R1/M-R2/M-R4. Relatório em `visual/oficios-lista-lote3.md`.
- 2026-10-07 — Lote 3 (menu ⋮ canônico com grupos, carga sob demanda, 401 em pedidos assíncronos sem sessão, barra "Mais") aprovado; Numeração revertida por decisão anterior do dono (D9 revogada). **Lista de ofícios CONCLUÍDA.** Paridade de folha/resumo/documentos entregue; plano D12–D18.
