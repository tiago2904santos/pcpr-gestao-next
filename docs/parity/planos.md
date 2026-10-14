# Planos — migração visual por unidade, 10/10/2026

## Calendário compartilhado — 14/10/2026

Folha e diálogo de evento adicional usam o calendário compacto de Termos, em
linha própria após Programa/Horário. Preservados campos/prefixos, eventos distintos,
valores/erros, horários e datas de saída/chegada com horário. Duração e antecedência
separadas, apresentação atualiza imediatamente. Não altera regra de emissão/cálculo.
Evidência: `../visual-agents/periodo-propagacao-20261014.md`.

Referência funcional consultada somente leitura; contrato vigente no código e
`docs/product/propagacao-identidade.md`. Ficha antiga `migration/planos.md` corrigida
para refletir efetivo/diárias por evento, programas múltiplos e Finalizados já existentes.
Isso não introduz decisão institucional nova.

Lista em fechamento: número/sufixo, destino, período, programas, coordenação,
efetivo, diárias gerais, vínculos, estado e motivo de cancelamento preservados.
Busca, quatro ordenações, grupos por ano/mês, filtro por Ofício, abas, paginação,
menus e criação dependem das mesmas permissões/endpoints. Documentos só aparecem
no menu quando gerados; minuta/finalização não são confundidas.

Folha/multievento migrados nesta unidade: quantitativos, diárias por evento,
programas/Outro, coordenadores, validação, autosave, geração e documento preservados.
Resultados migrados: edição manual, zero, milhar, linha vazia, observações,
erros agregados sem gravação parcial e leitura de cancelados preservados.
Lista/Folha/eventos/documentos/Resultados concluídos tecnicamente nesta rodada;
aprovação visual do usuário e gate global final continuam pendentes.
Número manual do legado continua lacuna anterior.

## Revisão da conferência operacional — 12/10/2026

Folha e diálogo multievento deixam de passar o parâmetro visual `horizontal`,
substituído pela variante compartilhada `operacional`. Nenhuma alteração em
quantitativos, cálculo, soma dos eventos, geração ou documento. A regressão do
fluxo multievento com erro, edição, exclusão e PDF passou nesta revisão.
A situação global vigente por página está em `docs/visual-agents/matriz-migracao.json`;
o fechamento da rodada anterior acima não representa aprovação nesta meta.
