# Refinamento de Planos de Trabalho — 15/10/2026

Pedido: aproximar Lista, preparação e componentes do acabamento vigente em Ofícios,
Roteiros, Termos e OS. Contrato funcional: `propagacao-identidade.md`, ficha
`../migration/planos.md`, `views_planos.py`, serviços e testes existentes.

## Observação e direção

Capturas anteriores em `../visual-agents/evidencias/planos-refino-20261015/antes/`,
360 e 1440 px, incluindo os quatro módulos de comparação. A Identificação acumula
agenda, percurso, coordenação, efetivo, deslocamento e cálculo; eventos adicionais
ficam dentro de Documento; etiquetas de atividade truncam nomes e escondem metas;
a lista não apresenta a coordenação administrativa. Há muito conteúdo sem etapas
intermediárias, principalmente no celular.

Preparação: manter a superfície contínua do arquétipo FORM com etapas numeradas e
índice de âncoras existente. Identificação conserva Ofícios, agenda, destinos e
coordenação; Efetivo e diárias recebe seção própria; Atividades oferece nome e meta
legíveis; Eventos adicionais ficam antes do Documento. Coordenações são grupos
paralelos no desktop, empilhados no celular. Campos condicionais continuam iguais.
Lista explicita a coordenação e melhora a leitura dos metadados, usando dados já
carregados. Resultados conserva tabela responsiva e salvamento manual.

## Contratos preservados

- IDs, nomes de campos, regiões `data-vivo`, versão e autosave.
- Âncoras de pendências `identificacao`, `efetivo`, `atividades`, `eventos`.
- Efetivo e diárias de cada evento; totais gerais não significam equipe única.
- Programa múltiplo/Outro, origem e tratamento dos coordenadores, conjuntos e busca.
- Cargo do coordenador acompanha a seleção/limpeza do combobox, em ajuda abaixo
  do campo; não encobre o nome e permanece disponível ao leitor de tela.
- Evento com formulário separado, cancelamento, permissões, geração e downloads.
- Prévia não gera documento; resultados só mudam por salvamento manual.
- Cadastros rápidos de horário/cargo/conjunto usam o módulo canônico, como em
  Ofícios, Termos e OS. Criar um conjunto não o aplica automaticamente nem sai
  da preparação. Corrigido o carregamento ausente desse módulo em Planos.
- Nenhum banco é resetado e nenhum documento oficial é alterado.

Validação exigida: verificação geral, testes dos fluxos de Planos e capturas
360/1440 revisadas; limites e resultados registrados no QA desta rodada.

## Revisão solicitada pelo usuário — 15/10/2026

- Retirar o índice de âncoras abaixo do cabeçalho; preservar IDs e atalhos de pendências.
- Atividades somente com o nome, sem a meta abaixo. Seleção compacta com marca clara,
  contraste, foco e nome integral. Metas continuam no documento, sem mudar o conteúdo.
- Efetivo em linhas agrupadas, com cargo destacado, unidade e quantidade bem separados;
  mesmos campos, limites, busca, adição/remoção e cálculo, inclusive no evento adicional.
- Minuta de plano salvo já aberta, mesmo com pendências. Carregar a folha imediatamente,
  sem aguardar o preenchimento ou o scroll. Pendências só impedem finalizar/gerar.
  Plano novo sem ID continua exigindo criação; cancelamento/permissões não mudam.
- Número editável na Identificação de Planos e OS, como em Ofícios. Campo vazio mantém
  o número existente (na criação, reserva automática); ano/sufixo não são editáveis.
  Inteiro de 1 a 999999, único por tipo e ano, incluindo outras unidades/cancelados.
  Mudança devolve o anterior à fila de lacunas e consome a lacuna do novo, como Ofício.
  Validação e trava anual no serviço; erro não grava parcialmente. Autosave e versão
  continuam obrigatórios, sem mexer em PDFs históricos ou criar migração.
