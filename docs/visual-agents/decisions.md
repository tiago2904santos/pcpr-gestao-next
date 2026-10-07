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
| 2026-10-07 | Ofícios/lista | ⋮: "Retificar" aparece uma vez — "Editar (retificar)" no emitido (volta a rascunho), "Marcar como retificado" no rascunho (a marca); marcas só no rascunho, exclusão mútua no domínio | Um item repetido no 1º e no 3º grupo; marca num emitido dessincronizava o PDF (defeito do legado) |
| 2026-10-07 | Listas | Menu de linha flutuante: camada de topo + véu (toque fora só fecha), abre abaixo/acima/ao lado e nunca sai da janela; <768 vira folha inferior; itens do ⋮ do ofício carregados ao chegar ao botão | Menus de 9–15 itens: peso da lista (263 → 122 KB) e alvos meio cobertos (M8) |
| 2026-10-07 | Ofícios/lista | "Mais" da barra só com item (Numeração do gestor); eProtocolo entra quando existir, nunca inativo | D8/D10 |
| 2026-10-07 | Ofícios/numeração | Página recriada por D9 (`56a17ff`); a anterior foi excluída a pedido em `4a3f835` — **a confirmar com o dono do produto** | Paridade (L6) × pedido anterior |
| 2026-10-07 | Ofícios | **D9 revogada**: a página Numeração NÃO volta. O dono do produto a excluiu "a pedido" em 4a3f835 (06/10), pouco antes da missão; o piso segue só no serviço. Recriação do Lote 3 revertida (revert de 56a17ff; item do "Mais" removido). A paridade L6 fica como "removida por decisão do dono". | Decisão explícita do usuário prevalece sobre a paridade com o legado |
