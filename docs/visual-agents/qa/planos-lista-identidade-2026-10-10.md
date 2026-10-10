# Lista de Planos — propagação visual, 10/10/2026

Base `5d3d845`, branch `codex/oficios-transporte-cartoes`. Unidade ativa somente
lista: folha/multievento/Resultados ainda não migrados. Contrato em product.

## Observação e projeto

25 capturas anteriores, mesmos quatro registros DEMO: lista, filtro, vazio,
ordenação por período e cancelados nas cinco larguras. Sem reset/seed/salvamento.
Antes: placa antiga, metadados com pesos iguais, barra fora do fragmento HTMX.
Axe target-size em 360/período; console/overflow sem falhas. Fonte JSON preservada.

Coleção/hero/filtros horizontais; registro operacional com identidade, destino,
agenda/programa, coordenação/efetivo/vínculos, diárias e ações. Número anual/sufixo,
grupos ano/mês, ordenação/querystrings, ações/permissões mantidos. Barra no fragmento
atualiza contagem e acompanha apenas lista paginada.

## Segunda crítica e correções

Primeira versão cortava `/ASCOM` e distribuía motivo do cancelamento sob a placa.
Identidade documental ganhou `complemento` opcional, sem mudar consumidores que
não o enviam. Número e sufixo separados hierarquicamente, completo no link acessível.
Observação ocupa largura do registro. Variante de período permite leitura inteira
no celular; valor usa a variante financeira já existente.

Contraste do complemento foi regressão desta rodada, encontrada pelo axe e corrigida
na origem com token inverso. JSON da falha conservado. UI Lab inclui número de quatro
dígitos/sufixo/cancelamento. Testes de interação em cinco larguras concluídos;
ordenação aguarda a resposta HTMX antes de avaliar o menu (sem espera arbitrária).

## Verificação e custo

47 testes HTTP/domínio/serviço verdes; 79 focados (TestTelas, tokens e contrato de identificação) após alterações
compartilhadas. Primeira suíte compatível: cinco Ofícios verdes, quatro novos Planos
falharam (três por assertiva `junho`/`Junho`, um contraste durante entrada na leitura).
Quatro E2E próprios passaram, mas compatibilidade repetida encontrou contraste
intermitente novamente: oito verdes/um vermelho. Investigação comprovou a animação
global de entrada, não o complemento final: opacity 0 antes → 1 depois, duração
360 ms + 80 ms de atraso. Cores amostradas pelo axe eram intermediárias. Teste agora
aguarda `finished` das animações finitas pertinentes, sem desativar movimento ou
excluir regras/controles. Prova em planos-animacao-prova.json; nove E2E passaram após a espera real.
Reteste adicional da paginação corrigida: nove E2E verdes (224,96 s),
incluindo Ofícios, busca/ordenação, paginação pelo link, cancelamento e consulta.
Logs anteriores preservados.

SQL antes/depois 27 com quatro registros, 23 com um, 16 vazio; ordenação 27.
Zero mutações nas medições. 24 requisições iniciais em todos os estados/larguras,
HTML lista 37.521 → 43.371 bytes. CSS normalizado LF +364 bytes/+32 gzip; JS e
listas.css idênticos. Normalização evita confundir checkout CRLF com adição de código;
não representa bytes HTTP. Nenhum ganho de latência alegado/budget ampliado.

## Limpeza e limites

Estrutura anterior desta lista substituída no próprio template. Nenhum arquivo,
dependência ou regra genérica removida: bases antigas ainda possuem consumidores.
Classes programa/coordenador/atividades/evento/resultados continuam necessárias.
Número manual é lacuna anterior. Migração integral de Planos não concluída.
Gate anterior 2295 em 9963f71; novo gate necessário antes do fechamento global.
Aprovação estética do usuário pendente.

## Ressalva da rolagem

25 estados iniciais finais: axe zero, console zero, sem overflow. A inspeção extra
com altura 500 e scroll até registro/aba encontrou target-size em links globais
parcialmente recortados pelo cabeçalho fixo (e inicialmente em abas parcialmente
visíveis). Não é contraste na versão final. A aba focada foi trazida à área visível,
com nome/Enter/Escape preservados. Não foram ocultados controles ou excluídas regras
do axe; resultados adicionais completos em planos-lista-interacoes-qa.json e imagens.
Base/layout do topo global não foram alterados; o comportamento precisa de revisão
transversal posterior, sem afirmar que esta rodada provou conformidade completa.
Achado não bloqueante para navegação validada; não classificá-lo como ganho ou
ausência universal de problemas. A galeria permite avaliação visual do usuário.


## Revisão independente e paginação

Vazamento do complemento do hero para a identificação corrigido com contexto `only`.
Duas verificações de contrato e renderização real do UI Lab confirmam um único texto
auxiliar, fora da identificação. Nenhum texto institucional alterado.

Paginação perdia filtros na implementação anterior: prova somente leitura com
POR_PAGINA=1 no processo, registros DEMO existentes, links ?pagina=2. Corrigida
em views_planos com o mesmo contrato das demais listas: excluir apenas pagina da
querystring. Prova posterior preserva q/ordem; HTTP também verifica aba/Ofício e
navegação real à página 2. Não é regressão visual; defeito preexistente corrigido.
Nenhuma mutação de dados DEMO nessas provas. E2E percorre o link com busca/aba/ordem.

Conclusão técnica: página concluída com ressalva não bloqueante da varredura extra
de rolagem global. Aprovação visual continua pendente do usuário. Ruff e mypy
sem erros no candidato atual (291 arquivos na chamada gestao).
