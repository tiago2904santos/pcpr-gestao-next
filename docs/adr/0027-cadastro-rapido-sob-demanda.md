# ADR 0027 — Buscar formulários de cadastro rápido ao abrir o diálogo

- Status: aceito para implementação local; validação pendente
- Data: 2026-10-07

## Contexto

Folha medida em `var/viagens-perf-lazy-eprotocolo.log`: HTML 139,9 KB e SQL 26,
acima dos tetos 120 KB/25. Renderiza formulários completos de servidor, viatura
e três catálogos em diálogos fechados. As ações/formulários canônicos já existem;
recriar um formulário simplificado perderia campos ou validação. Proposta em
`docs/quality/viagens-desempenho-proposta.md`, medidas são estimativas até novo teste.

## Decisão

Somente a Folha de ofício começa com diálogos leves. Primeiro clique abre o diálogo
nativo com estado de carregamento e busca os cinco formulários no mesmo endpoint
de edição, GET `?cadastros=1`, depois da autorização de objeto/edição existente.
Render reutiliza `componentes/dialogos_cadastro.html` e as mesmas classes de forms.
POST de cadastro mantém seus endpoints, serviços, permissões e resposta JSON.

Preencher o diálogo existente preserva identidade, origem do botão e foco da
janela nativa. Carregar uma vez por página; falha orienta fechar e abrir para
tentar novamente. Fechar durante a busca não reabre nem toma o foco. Cadastros
nested e escolha automática continuam iguais. Busca GET não altera negócio.
O JavaScript de cadastro entra no primeiro uso; componentes novos são ligados
pelo evento de reposição já usado na aplicação. Fora da Folha nada muda.

## Alternativas e consequências

Não duplicar formulários nem criar endpoint de escrita novo. Não aumentar budgets
ou retirar requisições da medição. Esta decisão reduz trabalho inicial e acrescenta
um GET no primeiro uso do cadastro; validar atraso/erro/sessão/permissão e todos os
campos, cadastro e associação de equipe em navegador real. Formulários com erro
na Folha não devem perder os valores já digitados. É necessário medir novamente;
o texto deste ADR não constitui resultado ou aprovação de desempenho.
