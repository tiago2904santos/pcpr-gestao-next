# CD04 — Tabela de diárias

Base190930f. Antes:12 capturas reais lista/nova/menu/editar em360/768/1440,
DEMO8017 somente GET/HEAD. Primeira automação selecionou menu global em vez do
menu da tabela; corrigido seletor para tbody. Nenhuma alteração do produto para
acomodar essa falha da automação.

Contrato consultado em entities.md/permissions.md, views_crud._lista_diarias,
TestDiarias e test_gestor_cadastra_vigencia_com_previa. Tabela comparativa é adequada
para faixas/percentuais/vigências; mantida com todos os dados. Sem busca ou paginação
no contrato atual; não inventadas durante migração.

Cabeçalho antigo substituído por registro_hero canônico; ação Nova vigência extraída
e reutilizada no cabeçalho/rodapé. Explicação dos percentuais preservada junto à
tabela. Grade--2 substitui campos--iguais no diálogo: Faixa/Data completas no celular,
duas colunas em desktop. Nenhum CSS/JS/dependência/consulta nova. Formulário, POST,
permissões, vigências e documentos intactos.

Segunda passagem: explicação inicialmente sem padding foi incorporada ao
lista-cabecalho, sem CSS local. Capturas finais12 concluídas. Escape e devolução
de foco reais. Testes25134 ativos; revisão independente solicitada. Ainda em validação.

## Fechamento

82 integrados +3 estados finais aprovados. Falha da primeira suíte de estados era
a troca de usuário ainda autenticado; automação passou a limpar cookies antes do
login do operador. Log original mantido. Dados financeiros/DEMO preservados.
Menu final recapturado após animações; revisão independente sem bloqueante.
Nenhum CSS/JS novo. Homologação visual e gate global pendentes.
