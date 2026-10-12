# Prestação de contas — acompanhamento da migração visual

Fonte funcional: `docs/migration/prestacao.md`, levantamento da referência de
05/10/2026. Esta rodada não redefine prazos, permissões, finalização nem documentos.

## Lista — PR01, 12/10/2026

Preservados: agrupamento por ofício; 25 equipes por página; contadores por servidor;
busca; abas de situação e atenção; edição e autosave por servidor; ações individuais
e de equipe; justificativa de finalização; envio, aprovação, devolução, arquivamento;
exportação filtrada; acesso a Diário, Relatório e Documentos; consulta sem edição.

Três defeitos demonstrados antes da correção e cobertos por regressão:

- A busca perdia abas combinadas: conserva todos os valores `aba` na URL e no formulário.
- A apresentação das ações de equipe usava apenas o recorte da busca: calcula o estado
  com a equipe ativa completa, exibindo somente as linhas do recorte. Os serviços
  continuam sendo a autoridade das ações e permissões.
- A substituição HTMX dos resultados perdia os diálogos de envio: os diálogos e o
  rodapé pertencem ao fragmento substituído; IDs e seletores OOB foram preservados.

Evidências e verificações: `docs/visual-agents/qa/prestacao-lista-2026-10-12.md`.
PR03 Relatório e PR04 Documentos ainda exigem migração própria; sua
compatibilidade com os estilos compartilhados não equivale a migração concluída.

Lacunas funcionais históricas devem ser conferidas por fluxo (por exemplo, cadastro
de feriados e histórico dedicado por servidor, citados no levantamento original).
Não foram supridas por alterações visuais nem declaradas concluídas nesta rodada.

## Diário de Bordo — PR02, concluído tecnicamente, 12/10/2026

Mantidos os três modos de motorista e de viatura, campos condicionais, aplicação
somente ao Diário/RT, horários realizados editáveis com recálculo e desfazer,
km e abastecimento com autosave, bloqueio de km final inferior ao inicial,
avisos não bloqueantes do hodômetro, consulta sem edição e trava de equipe
finalizada. PDF paisagem e XLSX não tiveram templates oficiais modificados.

O novo resultado por trecho usa a distância já calculada no domínio. Sua região
`data-vivo` atualiza depois do autosave preservando o foco nos campos. A barra
final mantém o estado de gravação em todas as larguras; Finalizar continua
retornando à Lista filtrada sem finalizar prestações. Evidências e revisão em
`docs/visual-agents/qa/diario-2026-10-12.md`.
## Relatório Técnico — PR03, concluído tecnicamente, 12/10/2026

Mantidos cinco textos da equipe, sugestões, copiar relatório, textos prontos,
custeio com Outro, valores individuais com observação e limite liberado,
autosave e Finalizar aguardando gravação. Leitura/equipe finalizada e travas
individuais preservadas. PDF e DOCX por servidor mantêm fontes documentais.
O componente de valor associa a referência liberada ao input por aria-describedby.
Texto pronto usa o componente compartilhado sem duplicação de JS.

Evidências: qa/relatorio-2026-10-12.md, 15 capturas finais, nove consumidores
de texto pronto, 92 testes iniciais e 78 pós-limpeza finais. Removida apenas
grade-campos, cujo consumidor foi migrado. PR04 Documentos/Anexos continua
pendente; este fechamento não significa conclusão do submódulo inteiro.
