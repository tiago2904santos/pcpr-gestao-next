# Planos — Resultados, 10/10/2026

Base f94b312, branch codex/oficios-transporte-cartoes. Contrato prévio em product.
DEMO e mídia preservados; gravações de testes exclusivamente em banco/media isolados.

## Observar, implementar e comparar

20 capturas anteriores, quatro estados (principal, multievento, cancelado, incompleto)
em360/390/768/1024/1440. Cabeçalho antigo, cartões e barra fixa foram substituídos
por hero com número/sufixo, preparação contínua, tabela de lançamentos e barra no fluxo.
Quantidade e observação continuam campos manuais; zero, erro digitado e atividade
retirada têm representação explícita. Relatório conserva texto salvo, sem geração nova.

Componente compartilhado lancamento_quantitativo recebe prefixos/IDs do consumidor;
UI Lab prova segundo uso. Meta permanece legível, tabela de comparação no desktop,
atividade/meta/edição em sequência no mobile/tablet. Nenhum cálculo/política alterado.

## Segunda crítica, correções e investigação

Primeira revisão visual encontrou rótulos sobrepostos mesmo com axe verde: sr-only
força position absolute !important. Corrigido na origem por classe responsiva própria,
sem alterar a utilidade global. E2E mede separação entre label e entrada.
Duas expectativas iniciais do teste estavam erradas: o relatório existente mostra
atividade zero sem total agregado zero; razão HTTP422 é Unprocessable Content.
Testes corrigidos conforme contrato existente, preservando assertions de gravação.

Contraste intermitente na primeira consulta cancelada ocorreu durante animação finita
de entrada (mesmo problema já identificado na Lista). O teste aguarda promises das
animações finitas reais, sem desabilitar CSS/axe ou excluir regras. Cinco E2E passaram
após a correção; logs anteriores com falhas preservados. Capturas após networkidle
passaram todos os critérios axe nas20 combinações. Não é declaração de conformidade
completa de acessibilidade: verificações manuais incluem Tab, Ctrl+S e altura500.

## Limpeza comprovada

Revisão independente e busca nas fontes/templates/scripts/testes comprovam dois
seletores exclusivos: tabela--resultados e relatorio-final. Consumidor Resultados
migrou para tabela--lancamentos/lancamento_quantitativo e leitura-textual; UI Lab é
novo consumidor. Sem construção dinâmica, hooks JS, fragmentos HTMX ou uso PDF.
Documento oficial usa documentos/plano_trabalho.html. Somente o bloco exclusivo
final de documento.css foi removido; bases ainda utilizadas foram preservadas.
Retestes sem implementação antiga são obrigatórios antes do commit.

## Desempenho e limites

SQL antes/depois:17/21/17/17 nas quatro consultas; nenhuma mutação DEMO.
HTML+1067 a1271 bytes conforme estado. CSS UTF8/LF: components+1693 (+333 gzip),
documento−1421 (−327 gzip), conjunto+6 gzip. JS proteção idêntico, nenhuma dependência.
POST do cenário E2E anterior excede budgetSQL25; não houve mudança de serviço/view
nem queries nesta unidade. Budget não aumentado. Não alegar ganho de latência ou
medição HTTP que não foi feita.

## Fechamento técnico

72 HTTP/tokens verdes; cinco E2E antes da remoção; sete E2E pós-limpeza
(cinco Resultados e dois UI Lab) verdes149,57s. Ruff/typecheck verdes.20capturas
finais verdes e UI Lab real360/1440 sem alterações CSS/axe. Galeria125pares250
imagens testada com carregamento integral/filtro, sem erros.

Concluída tecnicamente; avaliação visual pelo usuário pendente. Gate global desta
propagação permanece obrigatório antes da entrega consolidada;2295em9963f71
não é resultado integral deste candidato. Lacuna anterior de numeração manual do
Plano mantida. Nenhuma funcionalidade nova, documento oficial ou dado real alterado.
