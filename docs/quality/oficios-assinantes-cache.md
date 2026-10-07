# Substituições de assinante entre montagens de dados

Data: 2026-10-07. Correção no checkout original, sem alterar o worktree de integração RS.

## Observação e causa

`var/lote-h-verificar-final.log` registra a execução completa com **1 falha, 1897 testes
aprovados e 5 avisos**, em 2935,54 segundos. A falha de
`test_documentos_saem_com_o_assinante_de_cada_tipo` ocorre ao montar novamente os dados
do mesmo ofício depois de cadastrar uma substituição: permanece o nome da chefia,
quando deveria aparecer o nome do substituto.

`services.configuracao_da_unidade` retorna a relação `unidade.configuracao`, que pode ser
reutilizada na mesma instância de ofício. `dados_do_oficio` carrega as substituições com
`prefetch_related_objects`; uma relação já carregada não é consultada novamente. A lista
vazia da primeira montagem oculta a substituição criada depois.

## Regra e correção

A regra foi documentada antes da mudança em
`docs/product/workflows.md`, seção “Assinantes na montagem e nas versões emitidas”.
`dados_do_oficio` remove somente `substituicoes` do cache de relações prefetched antes
da montagem. O prefetch existente permanece, incluindo `servidor__cargo`: ofício e
justificativa leem a mesma lista atualizada e mantêm a seleção por tipo e período.
As demais relações, a configuração e os dados de equipe/roteiro não são recarregados.

Na primeira montagem sem cache de substituições, o caminho de consultas é o mesmo:
uma consulta compartilhada, com servidor e cargo por JOIN. Nas seguintes, uma nova
consulta substitui o reaproveitamento indevido da lista antiga. Não há consulta por
assinante ou por cargo. Essa análise é de código; a medição de páginas ainda depende
da validação LAB abaixo.

O código não atualiza `Documento` nem chama geração de PDF. O instantâneo emitido
permanece separado dos dados atuais.

## Regressões preparadas

Em `gestao/viagens/tests/test_servicos.py`:

- O teste existente verifica uma consulta de substituições já na primeira montagem;
  reutiliza a mesma instância ao criar uma substituição de ofício e depois outra de
  justificativa; confere nomes e cargos; desativa ambas e confere o retorno aos
  titulares/chefia. Cada montagem após aquecer as demais relações exige apenas uma
  consulta total, protegendo o compartilhamento e a ausência de N+1.
- `test_remontar_assinantes_atuais_nao_altera_snapshot_emitido` aquece a relação,
  cadastra um substituto e confirma a mudança nos dados atuais, preservando
  `Documento.dados` e a versão já emitida após leitura do banco.

## Estado da validação

Ruff sobre os dois arquivos Python alterados: `All checks passed!`. `git diff --check`
sobre os arquivos versionados do escopo: sem erros de whitespace. São verificações
estáticas, sem acesso ao banco.

Os testes de banco e navegador **não foram executados nesta correção**, por instrução
do coordenador enquanto o LAB estava em uso. A execução anterior falha e não constitui
validação desta mudança. A validação dos dois testes e dos orçamentos de consultas das
páginas fica a cargo do coordenador no banco `pcpr_lab`, seguida das verificações gerais
necessárias. Nenhum resultado verde de integração é alegado aqui.

## Validação do principal — 07/10/2026 17:35

Os dois testes foram executados no PostgreSQL LAB próprio, `pcpr_lab` porta
55432: **2 passaram em 19,45 s**, log `var/assinantes-editor-baseline.log`.
As asserções de consulta única e imutabilidade passaram. A seleção `-k assinante`
excluiu o teste de navegador que estava na mesma linha de comando; por isso este
log não valida navegador. A comparação do modo PDF foi executada separadamente.
Rodada dos serviços e orçamentos HTTP está em andamento; suíte integral anterior
continua registrada com exit 1 até nova execução integral concluir.
