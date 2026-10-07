# Decisões

Registro curto e datado. Decisões estruturais também viram ADR em `docs/adr/`.

| Data | Página/Escopo | Decisão | Por quê |
|---|---|---|---|
| 2026-10-06 | Processo | Trabalho no branch `viagens/reconstrucao`; checkpoints por bundle no repositório local | Não tocar no `main` do usuário; recuperação garantida |
| 2026-10-06 | Processo | LEGADO observado rodando localmente a partir de backup; dados reais nunca saem do sandbox | Benchmark real sem expor dados pessoais |
| 2026-10-06 | Ofícios/lista | D1–D11 em `visual/oficios-lista-plano.md`: abas temporais canônicas + filtro Documento; selo de tempo único; orçamento de selos; título = destinos; filtros em gaveta + fichas; título abre resumo; ⋮ canônico; Numeração; importação eProtocolo como sub-projeto | Paridade com o legado + identidade de Roteiros/Termos + diagnóstico visual |
| 2026-10-06 | Ambiente | O LEGADO local é uma cópia descartável do backup (o GET de editar do legado grava snapshot de justificativa); pode ser recriado de `/tmp/legado.sql` | Benchmark sem risco ao sistema real |
| 2026-10-07 | Listas | Motorista primeiro na equipe, com "(motorista)" visível (ícone removido); `title` mantém a ordem do ofício | QA: ícone não comunicava; marca precisa aparecer inteira em todas as larguras |
| 2026-10-07 | Listas | Metadados em colunas por *container queries* (largura do cartão, não da janela); sem suporte → fluxo antigo sem colunas | Painel e UI Lab truncavam com media queries |
| 2026-10-07 | Ofícios/lista | Parâmetros `aba=` (futuros, andamento, prestadas, cancelados) e `documento=` (rascunho, emitido, arquivado); `?situacao=` antigo redireciona (302) para o equivalente — lista e Exportar; links de outras telas por `enderecos.url_na_lista` | D1 sem quebrar favoritos, painel, Ctrl+K e testes |
| 2026-10-07 | Listas | Erro da busca ao vivo no arquétipo LIST (`componentes/erro_lista.html` + `filtros.js`): aviso no lugar de #resultados com "Tentar de novo"; URL da busca ao vivo sem campos vazios | Componente compartilhado melhorado na origem (LP-23) |
| 2026-10-07 | Roteiros/Termos | Não ganham a barra D6 agora (só têm busca + abas: sem Documento, gaveta ou fichas); contadores que ignoram a busca e "Que vão acontecer" sem os sem-data ficam registrados para o próximo lote | Ver `visual/oficios-lista-lote2.md` §5 |
| 2026-10-07 | Ofícios/lista | Segmento "Todos" do filtro Documento sem contagem (inclui cancelados; evita sugerir soma) | QA I3 |
| 2026-10-07 | Listas | Folha de filtros no celular é modal (foco preso, fundo inerte); gaveta no desktop não modal (a lista atualiza ao vivo atrás) | QA I1 |
