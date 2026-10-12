# Roteiros — preservação funcional na propagação visual

10/10/2026. Contrato detalhado e cobertura em `../migration/roteiros.md`.
Fontes da referência consultadas por leitura, sem copiar código; funcionalidades
vigentes confirmadas em views, formulários, políticas e testes do sistema novo.

Lista, busca, abas (incluindo Finalizados), paginação, ações, vínculos com Ofícios,
autosave, destinos ordenados, mapa, trechos, tempos/adicional, chegada e Diárias
mantêm o contrato anterior. Migração altera composição e componentes da interface.
Não há novo documento oficial, detalhe separado, campo obrigatório ou permissão.

Lacuna preexistente registrada: efetivo/observações persistidos não têm controles
na folha atual. Tipo de solicitação de evento permanece fora deste fluxo implementado.
Comparação da referência em execução permanece pendente; não declarar paridade nova
com base apenas em capturas do sistema alvo.

Evidência: `../visual-agents/qa/roteiros-identidade-2026-10-10.md` e galeria
`../visual-agents/evidencias/migracao-identidade-20261010/index.html`.

## Revalidação de 12/10/2026 — conferência compartilhada

A meta integral reabriu o fechamento anterior. Defeito reproduzido em Roteiros,
Ofícios e Planos: a classe horizontal antiga sobrescrevia a grade operacional.
O mesmo conjunto de dados, nas cinco larguras, foi capturado antes/depois.
Removidas cinco regras e o parâmetro antigo de todos os includes; consulta,
prévia HTMX, cálculos, retorno e condições de vazio/erro preservados.

Evidências atuais em `../visual-agents/evidencias/migracao-identidade-20261012/`.
As lacunas funcionais já descritas acima permanecem explícitas; esta alteração
não cria controles de efetivo/observações nem modifica o contrato do legado.
