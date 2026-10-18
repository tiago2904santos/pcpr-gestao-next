# Planos — migração visual por unidade, 10/10/2026

## Refinamento de preparação — 15/10/2026

Comparação visual com Ofícios, Roteiros, Termos e OS em 360/1440 px. A preparação
ganha índice compacto e separa Efetivo/diárias e Outros eventos em etapas próprias.
Âncoras e regiões vivas preservadas. Coordenação administrativa e operacional em
grupos paralelos no desktop; nomes de atividades e metas visíveis, sem truncamento,
com nome acessível e descrição separados. Busca/conjuntos continuam nos controles
existentes. A lista mostra a coordenação com dados já carregados pelo queryset.

Regras, cálculos, efetivo por evento, autosave/versão, formulários externos,
permissões, cancelamento, geração e documentos oficiais mantidos. Resultados
conservam salvamento manual. Decisão visual: ADR 0038; contrato: produto
`planos-refinamento.md`. Evidências em
`../visual-agents/evidencias/planos-refino-20261015/`.
Homologação visual do usuário permanece distinta da validação técnica.

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

## Cadastros compartilhados — 17/10/2026

Atividades passam a compartilhar identidade com Serviços de Eventos, preservando
os IDs dos planos, conjuntos, usos e resultados. O aviso de meta ausente respeita
a regra existente; não inventa conteúdo nem impede emissão já permitida.
No celular, Cargo e Unidade do efetivo usam a linha inteira, e remover acompanha
a quantidade. A regra substitui o nth-child genérico que encobria parte da lixeira.
O diálogo de evento usa corpo rolável, ações acessíveis, cabeçalho com espaço para
fechar e cadastro auxiliar de horário sem empilhar duas superfícies modais.

Identidade comum e histórico passaram em 360/1440; quantidade/calendário/conferência
e axe móvel foram revalidados após o ajuste final. Evidências e limites em
`../auditorias/cadastros-compartilhados/relatorio.md`, `catalogo-ui-final.log`,
`ui-encerramento.log` e `consumidores-finais.log` (neste último, o caso de Plano
passou; os dois casos de Certidões são tentativas de localizador, reexecutadas no
log próprio). Nenhuma regra de cálculo ou documento foi alterada por esse CSS.
