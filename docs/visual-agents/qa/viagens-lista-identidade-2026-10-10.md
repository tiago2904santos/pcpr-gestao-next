# Lista de Viagens — identidade vigente

Candidato sobre `3a8b5a7`, branch `codex/oficios-transporte-cartoes`.
Contrato em docs/product/propagacao-identidade.md; funcionalidade em
 docs/migration/viagem.md. DEMO existente preservado, zero seed/reset, mídia intacta.

## Implementação e revisão

Hero compacto, filtros temporais horizontais, busca HTMX/OOB, registros canônicos com
placa data/ID, título/destinos completos no DOM e nome acessível, estado separado de
prazo, período/unidade e contagens de vínculos. Não criou número oficial, menu,
exportação ou download. Criação POST/CSRF/permissão preservada. Barra no fragmento
atualiza junto dos resultados; no fluxo para uma página e acompanha só paginação.

Segunda passagem: imagens integrais em360/390/768/1024/1440, busca por teclado e Enter
para abrir Folha em altura500. Dados atuais têm cinco registros, três futuros e um
cancelado. Títulos históricos contendo cidade/data foram preservados como dados,
sem renomeação heurística. Revisão independente de código não encontrou bloqueante.
Sem versão antiga exclusiva de CSS/JS comprovadamente removível. Wrappers substituídos
no template e preload do seletor ausente na Lista retirados; bases compartilhadas e
botão POST continuam. Não apagar apenas por falta de uso nesta captura.

## Evidências

20pares reais antes/depois: `antes/depois-viagens-lista-{todas,futuras,canceladas,vazio}-{width}.png`.
JSON depois:20HTTP200, axe0, console0, overflow false. Antes390/todas tinha target-size
no último registro próximo da barra fixa; achado anterior registrado sem rebaseline.
`viagens-lista-revisao.json`: foco na busca/Enter e UI Lab axe0 nas três larguras/altura500.
UI Lab com variante canônica e três capturas do exemplo. Galeria existente reutilizada.

## Desempenho

`sql-peso-viagens-lista.json`:20/20/16/19 consultas nos quatro estados antes/depois;
zero mutações DEMO. HTML26798→33171(todas),24423→28335(futuras),21182→21426(vazio),
21713→23152(canceladas). ComponentesCSS LF +943bytes, gzip+94; JS inalterado.
Sem medição de latência/HTTP nesta unidade; não alegar ganho de carregamento.
Folha aberta pelos testes já excedia orçamento SQL antes desta mudança (66/62); é
outra página na próxima unidade, não nova consulta na Lista. Budgets preservados.

## Testes e limites

Resultados finais serão registrados abaixo antes do commit. Primeira rodada mostrou
cenário de cancelamento com operador sem permissão sobre Ofício emitido e teste antigo
que não abria seletor de tipo. Corrigidos os testes, regras e Folha sem alteração.
A Folha é idêntica ao commit de base nesta unidade, comprovando origem anterior do
seletor fechado. Log inicial preservado. Acessibilidade automatizada não equivale a
conformidade completa; verificações manuais realizadas são as descritas acima.

Avaliação estética pelo usuário pendente; gate global atualizado ainda pendente.
Legado possui combinações temporais/25por página/protocolo/ações por linha que não
fazem parte do contrato implementado. Lacunas anteriores explícitas, sem prometer
migração integral dos recursos inexistentes. Próxima unidade: Folha de Viagens e lote.


Fechamento: **94 HTTP/domínio/tokens verdes (79,69s), cinco E2E de fluxos (112,39s),
três E2E finais (82,83s: vinte registros/paginação + dois UI Lab)**. Ruff e TypeScript
verdes. Cenário com 21 registros: vinte na página inicial e um na seguinte, busca
preservada, foco no último registro acima da barra em390/500 e axe zero. Captura real
TEST em viagens-lista-vinte-registros-390.png. Testes mutáveis usaram banco UUID/mídia
isolados por execução. Logs iniciais preservados; falhas foram cenários incorretos,
sem flexibilização de permissão nem exclusão de regra do axe. Galeria165pares/330imagens
carregadas e filtro1440 conferidos. Nenhuma regressão bloqueante conhecida.
