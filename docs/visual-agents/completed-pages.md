# Páginas concluídas

## Reabertura integral — 12/10/2026

As conclusões abaixo são históricas. O usuário exige revalidação de todas as
páginas; a situação atual está em `matriz-migracao.json`. As cinco capturas mais
recentes de Ofícios substituem referências anteriores conflitantes. Nenhuma
aprovação estética do usuário é inferida de teste ou avaliação de agente.

Só entra aqui o que cumpriu a Definição de concluído (`mission.md`).

## Estado visual vigente — decisão do usuário em 08/10/2026

**Somente o Resumo/Detalhe do Ofício está aprovado como referência visual.**
Lista e Cadastro/Edição/Folha anteriores foram **REPROVADOS VISUALMENTE**. As novas
candidatas foram reconstruídas nesta ordem e aguardam revisão estética do usuário;
estado e evidências em `current-page.md`. Avaliações anteriores abaixo permanecem
como histórico; não autorizam tratar essas duas páginas como concluídas.
Não avançar para Termos, OS, Planos ou outros módulos antes de fechar ambas.

## Decisão posterior do usuário — 08/10/2026

As mudanças da entrega visual anterior foram **reprovadas pelo usuário** por impacto
insuficiente. Os registros abaixo preservam resultados técnicos históricos e avaliações
do agente; não significam aprovação estética atual. O novo piloto está em
`current-page.md`, com propagação suspensa até aprovação visual do usuário.

## Piloto de leitura operacional de Ofícios — 08/10/2026

Lista e Resumo: **aprovados com ressalvas pelo agente**, na branch
`codex/oficios-leitura-operacional`, implementação `a2c5e42`, base `0213d75`.
Identidade compacta, régua de colunas e metadados compartilhados demonstrados
na segunda tela e no UI Lab. Gate integral 2.197 verdes / zero falhas; HTTP31,
navegador, teclado/foco e axe nas cinco larguras. 25 comparações reais revisadas.
Folha e Documentos revalidados, sem nova frente de desenho nesta rodada.
Ressalvas/medições/limites: `qa/oficios-leitura-operacional-2026-10-08.md`.
Imagens: `qa/oficios-leitura-operacional-evidencias.md`. Não presume aprovação
estética do usuário nem conclusão de toda a missão de Viagens. Sem push/merge/deploy.

## Bloco visual de Ofícios — 08/10/2026

Lista, Resumo, Folha e painel Documentos redesenhados e componentizados.
**Aprovado com ressalvas pelo agente**, sem presumir aprovação estética do
usuário. Gate integral verde (2.193 testes), navegador, teclado/foco, tokens
e axe validados; antes/depois nas cinco larguras. Implementação `e219222`.
Resultado e limites: `qa/oficios-premium-2026-10-08.md`. Imagens reais:
`qa/oficios-premium-evidencias.md`. Registros anteriores abaixo são históricos.

| Página | Data | Parity | Visual | QA | Observações |
|---|---|---|---|---|---|
| Ofícios › Lista (`/viagens/oficios/`) | 2026-10-07 | `parity/oficios-lista.md` (L1–L80: 75 ✅/➕, 1 ⛔ decisão do dono, 2 ⏳ importação eProtocolo, 2 ⚠️ L9/L49) | `visual/oficios-lista-plano.md`, `-lote1/2/3.md` | `qa/oficios-lista-lote1/2/3.md`, `qa/oficios-lista-final.md` — APROVADO | Suíte rápida: 1837 ✓, 1 ✗ de ambiente (`test_demo` lê o `.env` local do sandbox). Pendências conscientes: pontos de entrada da importação do eProtocolo; L9 e L49 a decidir; fichas/gaveta nas listas de outros módulos |
