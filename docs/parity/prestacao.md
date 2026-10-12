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
PR02 Diário, PR03 Relatório e PR04 Documentos ainda exigem migração própria; sua
compatibilidade com os estilos compartilhados não equivale a migração concluída.

Lacunas funcionais históricas devem ser conferidas por fluxo (por exemplo, cadastro
de feriados e histórico dedicado por servidor, citados no levantamento original).
Não foram supridas por alterações visuais nem declaradas concluídas nesta rodada.
