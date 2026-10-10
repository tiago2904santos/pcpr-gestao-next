# Estado da propagação — 10/10/2026

Branch inicial: `codex/oficios-transporte-cartoes`; HEAD `722198f`.
Trabalho local e index anteriores preservados em
`var/migracao-visual-20261010-baseline/`. Nenhum push/merge/deploy autorizado.
Referência vigente: cinco capturas do usuário, Ofícios atuais; contrato em
`docs/product/propagacao-identidade.md`. Não é aprovação automática das próximas telas.

## Matriz inicial (aprofundada ao entrar em cada página)

| Módulo/página | Estados | Situação | Componentes | Antigos/compatibilidade | Testes/evidência | Commit/pendência |
|---|---|---|---|---|---|---|
| Ofícios: Lista/Resumo/Folha | consulta, filtros, vazio, geração, falha, equipe, trechos | referência técnica consolidada; passada curta validada | hero, coleção consulta, mesa registro, itinerário operacional, conferência, editor | variantes anteriores para consumidores ainda não migrados | QA anterior: integral 2291, navegador 32+10, HTTP 27; nova compatibilidade 5 E2E e revisão financeira nas 3 larguras | a675739; identidade vigente das capturas do usuário |
| Roteiros: lista | busca, abas, vazio, cancelado, paginação, menu, vínculos | concluída tecnicamente; avaliação visual pendente | hero/coleção/registro operacional | regras exclusivas antigas removidas; bases de outras listas preservadas | 89 focados, 9 E2E compatibilidade, 25 pares, teclado/HTMX/axe/UI Lab, SQL equivalente | gate 2295 verde; manifesto candidato-roteiros.json |
| Roteiros: novo/edição | vazio, preenchido, erro, autosave, bate-volta | concluída tecnicamente; avaliação visual pendente | itinerário/rota/trechos/Diárias canônicos, salvamento sem emissão | mapa alternativo sem consumidores removido | 7 E2E de fluxo, compatibilidade após remoção, 68 tokens, cinco larguras | gate 2295 verde; sem documento/resumo próprio |
| Termos: lista/folha/documentos | busca, filtro por Ofício, avulso/vinculado, novo, documentos, cancelado | concluída tecnicamente; avaliação visual pendente | hero, coleção/registro de relações, preparação, destinos/mapa, equipe compacta, viatura/cartão, editor/histórico | quatro regras exclusivas antigas removidas; mapa mantido para OS/Planos/Viagens | 69 HTTP pós-limpeza; 8 E2E compatíveis; 25 cenários reais verdes; 3 Baixar/documentos e 2 paginação/consulta/assinado verdes | manifesto candidato-termos.json; avaliação estética pendente |
| OS: lista/folha/documentos | busca, vazio, avulsa/vinculada, funções, cancelada, consulta, documentos | concluída tecnicamente; avaliação visual pendente | coleção, registros de relações, preparação, destinos, equipe compacta, editor/histórico | bases compartilhadas mantidas para Planos/Viagens | 81 focados, 6 E2E, 25 capturas e interações cinco larguras | manifesto candidato-ordens.json; HTTP antes/depois inconclusivo |
| Planos: lista | busca, ordem, Ofício, grupos, vazio, cancelados, paginação, consulta | concluída tecnicamente; avaliação visual pendente | coleção, identidade com complemento, registro operacional financeiro, observação larga | bases antigas mantidas para demais consumidores | 47 HTTP, 79 focados, 9 E2E compatíveis, cinco larguras; paginação antiga corrigida | candidato-planos-lista.json; achado de rolagem global não bloqueante registrado |
| Planos: folha/multievento/documentos | incompleto, pronto, novo, gerado, evento adicional | concluída tecnicamente; avaliação visual pendente | hero/preparação/agenda/destinos/financeiro/conferência/editor/histórico | bases genéricas mantidas para consumidores reais | 143 focados, 20 E2E integrados +5 finais, 2 UI Lab, 25 capturas e teclado/diálogo | candidato-planos-folha.json; SQL anterior classificado |
| Planos: Resultados | atividades previstas/retiradas, erro, vazio, cancelado/consulta | concluída tecnicamente; avaliação visual pendente | hero/preparação/lançamentos/leitura/barra no fluxo | duas variantes CSS exclusivas removidas |72HTTP/tokens,5E2E+7pós-limpeza,20capturas cinco larguras | gate global final pendente |
| Justificativas | lista/diálogo/editor | não iniciada | idem | idem | idem | após Planos |
| Viagens/Prestação | fluxos implementados | não iniciada | idem | idem | idem | não criar lacunas funcionais |
| Cadastros/configuração/auxiliares | aprofundar por rota | não iniciada | idem | idem | inventário existente | após fluxos principais |

## Checkpoint de referência

Fontes confirmadas: `oficios/lista.html` → `colecao-operacional--consulta`, filtros
temporais horizontais; `_resumo.html` → leitura independente/contexto; Cadastro →
`_itinerario.html` operacional, `painel_rota`, `_trecho_campos`, `conferencia_valores`.
O gate anterior terminou verde, associado ao manifesto local da rodada, sem novo
commit. Reutilizar resultados apenas onde os hashes permanecem iguais.
Prévia local retomada em :8017, banco LAB existente :55432, mídia isolada existente.
Sem seed/reset. Implementação ativa segue a matriz atual; descoberta paralela
somente leitura, sem edição ou suíte mutável.

## Checkpoint e próxima ação

Referência: `a675739`. Roteiros fechados tecnicamente: 89 focados, 9 E2E ampliados,
7 E2E novamente após remoção, 68 tokens e gate integral 2295/code 0.
SHA final e manifesto em `evidencias/migracao-identidade-20261010/commit-roteiros.json`.
Prévia :8017; galeria :8021; comparação :8023 encerrada; LAB :55432 preservado.

Termos fechados com 69 HTTP pós-limpeza, 8 E2E de compatibilidade, 3 documentais,
3 de geometria após a correção e 2 de paginação/consulta/assinados. Capturas finais
nas cinco larguras, comparação de SQL/recursos e galeria de 40 pares validadas.
SHA e hashes no candidato-termos.json/commit-termos.json.

Ordens de Serviço fechadas tecnicamente: 81 focados e seis E2E, 25 capturas,
funções por servidor, teclado/HTMX/consulta/assinados. SQL e CSS/JS sem aumento;
comparação HTTP controlada inconclusiva por renderização da cópia anterior.
Nenhum código exclusivo antigo removido sem prova. Manifesto candidato-ordens.json.

Lista de Planos concluída tecnicamente; próxima página ativa: Folha/multievento.
Resultados ficam na fila seguinte; contratos distintos de OS: pendências bloqueiam geração/finalização e
efetivo/diárias pertencem a cada evento. DEMO preservado, sem reset/seed.
Não refazer snapshot nem usar git add indiscriminado.


Folha de Planos: 143 focados e 20 E2E integrados verdes. Revisão independente
identificou destinos truncados sem texto integral acessível no novo registro do evento;
corrigidos title e nome do link. Reteste específico: cinco E2E finais verdes, incluindo HTTP422/retorno e geração real.
SQL idêntico nos cinco estados, JS idêntico, CSS gzip +358/-3 bytes por arquivo.
Galeria 105 pares/210 originais conferidos. Ferramentas recolhíveis e diálogo em altura
500 testados por teclado. Resultados continua sem alteração até este fechamento.

Folha fechada: cinco E2E finais, dois UI Lab automatizados e axe real360/1440 zero,
sem alterar estilos. Próxima unidade: Resultados, cujos20 estados anteriores já existem.


Resultados fechado tecnicamente:72HTTP/tokens, cinco E2E e sete pós-limpeza verdes.
20pares nas cinco larguras; rótulos móveis corrigidos com classe própria; tabela
cancelada não exige rolagem horizontal/foco inexistente.66linhas CSS exclusivas
removidas com revisão de consumidores. SQL17/21/17/17 idêntico, JS idêntico,
CSS conjunto+6gzip. Galeria125pares250originais. Próxima unidade:Justificativas,
lista/diálogo/exclusão/download; preservação do contexto após422 é defeito anterior
já identificado em leitura. Não abrir outra implementação em paralelo.
