# Decisões

Registro curto e datado. Decisões estruturais também viram ADR em `docs/adr/`.

| Data | Página/Escopo | Decisão | Por quê |
|---|---|---|---|
| 2026-10-06 | Processo | Trabalho no branch `viagens/reconstrucao`; checkpoints por bundle no repositório local | Não tocar no `main` do usuário; recuperação garantida |
| 2026-10-06 | Processo | LEGADO observado rodando localmente a partir de backup; dados reais nunca saem do sandbox | Benchmark real sem expor dados pessoais |
| 2026-10-06 | Ofícios/lista | D1–D11 em `visual/oficios-lista-plano.md`: abas temporais canônicas + filtro Documento; selo de tempo único; orçamento de selos; título = destinos; filtros em gaveta + fichas; título abre resumo; ⋮ canônico; Numeração; importação eProtocolo como sub-projeto | Paridade com o legado + identidade de Roteiros/Termos + diagnóstico visual |
| 2026-10-06 | Ambiente | O LEGADO local é uma cópia descartável do backup (o GET de editar do legado grava snapshot de justificativa); pode ser recriado de `/tmp/legado.sql` | Benchmark sem risco ao sistema real |
