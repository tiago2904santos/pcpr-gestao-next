# RS-02 — adaptador independente e migração dos consumidores

Data: 07/10/2026. Fontes lidas no worktree `viagens-tempo-legado`, HEAD `c3ae40a`.
Linhas abaixo são do checkpoint congelado; conferir novamente antes da integração.
Contrato: `docs/product/oficios-documentos-versoes.md`; domínio: ADR 0025.

## Implementação independente

`gestao/viagens/documentos_versoes.py.projetar_documentos` recebe ofício autorizado
pelo chamador e listas/tuplas obrigatórias de documentos/vias carregados. Não existe
fallback ORM. Apenas os campos locais em `__dict__` são lidos: campo deferred não
dispara descritor/consulta. Queryset/generator é recusado antes de ser iterado.

Documentos/vias de outro ofício e vias sem documento/tipo correspondentes são
excluídos dos mapas. Documentos com metadados incompletos ou identidade duplicada
impedem a seleção, com aviso, em vez de promover um registro antigo. Vias
incompletas impedem a escolha de assinatura corrente; o original exato ainda pode
estar disponível. Mapas `MappingProxyType` preservam os modelos por ID, sem copiar
nem reconstruir seus snapshots. O adaptador não serializa modelos ao navegador.

`por_tipo` devolve geração/identidade/histórico do domínio. `pdf_original` exige
identidade corrente pronta e caminho do arquivo preenchido. `via_assinada` exige
via corrente exata não revogada com caminho; `pdf_efetivo` prefere essa via.
`pdf_disponivel(id)`/`via_disponivel(id)` permitem checar caminhos históricos
sem transformá-los em correntes. Via revogada com arquivo permanece consultável
por ID, submetida à política de leitura existente.

`docx_corrente` preserva somente a identidade corrente pronta: é composto do
snapshot e não abre o PDF. Um caminho vazio bloqueia o link do PDF original,
sem criar nova exportação para gerando/falhou. Caminho preenchido não prova
existência dos bytes; storage e resposta HTTP continuam responsabilidade do download.
`arquivado` não altera identidade; o adaptador não decide permissão de mutação.

## Plano mínimo de migração — oito consumidores

1. **Anotações da lista e menus por linha.** `queries.py:77`/`:80` filtram pronto;
   `com_dados_de_lista`, `queries.py:90`, anota PDF e existência de via por tipo.
   Trocar o recorte por última identidade sem filtro de geração e anotar estado,
   versão/ID, caminho preenchido e presença de justificativa do snapshot do último
   ofício. Correlacionar assinatura ao ID exato, não só tipo. Alimentar o domínio
   puro com as anotações; não fabricar models `Documento` para satisfazer o adaptador
   nem buscar cada documento por linha. A lista continua com o layout aprovado.
   Testes atuais: `test_views.py:169` (19 consultas) e `:1614` (20 consultas com
   20/200 ofícios, filtros e busca); exportação nesse cenário tem teto 12.

2. **Menu canônico/fallbacks.** `policies.py:170`, `:231` e `:239` escolhem último
   pronto ou recebem PDF/justificativa selecionados pelo resumo. Fazer o menu consumir
   a mesma identidade/projeção fornecida, mantendo autorizações atuais; evitar nova
   seleção por tipo ou existência de assinatura sem versão. Consumidores sem listas
   carregadas precisam centralizar uma leitura de metadados, após autorização, e
   passar o resultado às políticas; o adaptador não fará essa consulta. Validar
   ambos os caminhos (anotações e listas completas) sem N+1 nem limite aumentado.

3. **Resumo, vias e polling.** `_contexto_resumo`, `views.py:872`, já tem a lista
   documental em `:879` e uma consulta de vias em vigor em `:886`. Reutilizar documentos;
   para exibir vias revogadas/histórico, ampliar a mesma leitura de vias, sem adicionar
   outra consulta nem iterar relações por item. `_vias_do_oficio`, `:940`, deve usar
   a associação de versão, não o primeiro pronto por tipo/chave. `_resumo.html:160`
   faz polling só do bloco Documentos; o rodapé `:214–230` e menu/Word também precisam
   acompanhar a identidade e disponibilidade, sem oferecer v1/minuta viva como
   corrente de v2 pendente. Rascunho conserva minuta principal e PDFs históricos
   explícitos. Teto atual resumo: 20 consultas rascunho/15 emitido
   (`test_views.py:514`); folha/revisão: 32 (`:629`). Medir leitura de vias com/sem
   PDFs e vários históricos, sem duplicar a consulta para o mesmo render.

4. **Documento alvo da anexação.** `assinados.documento_emitido`, `assinados.py:95`,
   seleciona pronto; `anexar`, `:212`, usa essa identidade após travar o dono.
   Fornecer a seleção da versão atual pronta/com caminho, preservando o lock e as
   políticas; não anexar a v1 enquanto v2 está gerando/falhou. A mesma projeção pode
   alimentar a conferência para evitar seleções divergentes no pedido. Manter
   transação/revogação existentes. Não foi encontrado teto SQL específico deste
   endpoint nesta investigação: medir baseline e depois, exigindo quantidade fixa
   independente do número de versões; não prometer zero consultas da escrita.

5. **DOCX.** `baixar_docx`, `views.py:1050`/`:1058`, filtra pronto e pode usar v1.
   Ler os metadados/snapshots necessários em consulta constante autorizada (último
   ofício e tipo solicitado), projetar uma vez e obter o modelo por ID. Rascunho
   continua DOCX minuta; emitido usa apenas última identidade pronta e não promove
   antiga nem gera minuta viva em falha. A indisponibilidade precisa de orientação
   HTTP compreensível; DOCX não exige abrir o arquivo PDF. Medir endpoint antes/depois
   e casos de emissão sem justificativa; não aumentar budgets das páginas por isso.

6. **Pacote.** `_itens_do_oficio_proprio`, `pacotes.py:52`/`:69`, usa
   `documento_emitido` por tipo e decide justificativa pelo texto vivo do ofício.
   Preparar documentos/vias uma vez e usar a presença congelada da última emissão.
   Manter ordem/formatos/termos existentes, sem transformar termos em Documento.
   Item emitido com geração pendente/falha ou arquivo ausente deve informar a
   indisponibilidade; não produzir minuta ou v1 no seu lugar. Preservar o contrato
   de que erro de um item aborta o pacote. Medir consultas/arquivos por lote e testar
   PDF original/assinado/DOCX; nenhum storage é acessado na etapa de projeção.

7. **Lista de justificativas.** `_lista_justificativas`, `views.py:1138`, usa
   `com_dados_de_lista` em `:1152` e prefetch somente pronto em `:1153–1156`.
   Alinhar as anotações do último ofício e a última justificativa de cada linha,
   inclusive geração pendente/falha, sem usar “última pronta”. Guardar histórico
   fora da identidade corrente quando snapshot da emissão não tem justificativa.
   Preservar lista, filtros, autorização e links existentes; testar quantidade
   constante sob várias linhas/versões. Não foi identificado um teto específico
   desta lista no arquivo de testes consultado; medir baseline, sem inventar limite.

8. **Downloads exatos/históricos.** `baixar_documento`, `views.py:996`, já recebe
   documento por ID e a via exata; `views_assinados.abrir`, `:124`, também recebe ID.
   Não substituir esses endereços por seleção da versão corrente nem proibir histórico
   cancelado/revogado que `pode_ver`/`pode_abrir` permite. Acrescentar guardas de caminho
   vazio e preservar `?versao=original`; falta física de arquivo deve ser tratada no
   download, sem fallback silencioso. A projeção pode alimentar links/metadados,
   mas não impõe que o histórico seja corrente. Validar respostas de bytes,
   SHA-256, original/assinado, scope 404 e GET sem escrita. Não foi encontrado teto
   específico para esses downloads; medir baseline/after e manter consultas fixas.

Orçamentos gerais em `docs/quality/performance-budgets.md` não substituem os limites
específicos dos testes acima. Subconsultas extras podem manter a quantidade SQL e
ainda piorar tempo/plano: validar também o custo do banco e carga do cenário grande.
Estas são propostas para o coordenador implementar após o ensaio de desempenho,
sem alterar o código congelado nesta subtarefa.

## Evidência de testes independentes

`gestao/viagens/tests/test_documentos_projecao.py`: **42 passaram em 0,13 s**, com
plugins desativados (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`), `--noconftest` e addopts
vazios. Nenhum model Django/configuração de banco foi carregado. Objetos carregados
têm armadilhas em relações/descritores; arquivos têm armadilhas em nome por descritor,
URL e abertura. Elas não foram acionadas; campos locais e caminho registrado são
lidos sem I/O. Isso demonstra o contrato com objetos em memória, não uma medição
SQL HTTP de uma view conectada.

Cobertura: mesma identidade/modelo por ID; maior versão gerando/falhou; original
pronto sem caminho; assinado disponível sem original; assinado sem arquivo com
aviso; histórico cancelado/reaberto/revogado; arquivado; exclusão de outro ofício;
tipo/ID exatos; metadados deferred sem consulta/promover v1; snapshot inválido;
justificativa presente/vazia/indeterminada; preservação dos inputs/snapshots;
mapas de leitura; ausência explícita; recusa de queryset/generator; identidade
duplicada e situação não carregada.

Primeira coleta falhou porque a armadilha do objeto também interceptava `__name__`
usado pelo pytest para nomear parâmetros; a fixture passou a devolver AttributeError
em introspecção dunder, mantendo as armadilhas de negócio. Mypy apontou a necessidade
de anotar a tupla de seleções nos ramos; a anotação foi incluída antes da execução
final acima. Não foi removida asserção de negócio para obter resultado verde.

Ruff dos dois arquivos: verde. Mypy isolado do adaptador, `--config-file nul
--follow-imports=skip --check-untyped-defs`: sem erros; aviso de configuração vazia.
Esse mypy não é a validação completa com django-stubs. O aviso pytest de
`DJANGO_SETTINGS_MODULE` desconhecido é esperado com plugin Django desligado.

Nenhum DB/browser foi executado e nenhum consumidor congelado foi alterado.
Não há afirmação de integração aplicada, budgets SQL reais medidos ou links
documentais já corrigidos no sistema. Commit e conexão ao produto ficam pendentes
da revisão/validação do coordenador.

## Integração incremental autorizada — 07/10/2026

Depois da base independente acima, o coordenador reexecutou 81 casos (39 domínio
+ 42 adaptador): 81 passaram em 0,13 s. Autorizou então os consumidores abaixo.
Esta seção substitui a indicação anterior de consumidores ainda congelados apenas
para estes arquivos/funções; telas e validação do banco continuam sob coordenação.

Implementado no worktree:

- `queries.com_dados_de_lista`: maior identidade por tipo sem filtrar pronto;
  versão/situação/caminho e campo JSON justificativa anotados na consulta existente.
  `selecao_documental_da_lista` executa o domínio puro sem relação Django/SQL.
  `pdf_corrente_da_lista` exige estado pronto e caminho preenchido.
- `policies.menu_do_oficio(..., projecao=...)`: projeção explícita tem precedência;
  a lista usa as anotações equivalentes. Minuta somente rascunho. Falha, espera
  e arquivo ausente têm motivos claros; não há promoção de v1. Nenhuma permissão
  foi adicionada. A expectativa antiga de minuta do emitido pendente em
  `test_menu_oficio.py` exige ajuste pelo coordenador para a regra RS-02.
- `assinados.documento_emitido`: projeção de todas versões em uma montagem, sem
  guardar cache de seleção entre montagens. `vigente/vigentes_do` para ofício
  exigem ID/tipo/dono exatos, última identidade pronta, ofício emitido, caminho
  da via e justificativa presente no snapshot. Subconsultas mantêm uma consulta
  de vias por dono; termo/OS mantêm regra. Bloqueios/transações/escrita intactos.
- `pacotes._itens_do_oficio_proprio`: monta documentos/vias uma vez. Justificativa
  corrente pelo snapshot; minuta somente rascunho. PDF exige caminho; DOCX pronto
  usa snapshot mesmo sem caminho PDF. Gerando/falhou não exportam v1 nem dados
  vivos; item solicitado indisponível lança PacoteInvalido e aborta o pacote.
  Tipos, ordem, formatos, termos e parâmetros de montar permanecem existentes.
- `views.baixar_docx`: seleção corrente ou maior identidade histórica de cancelado,
  somente pronta; falha/espera/ausência retornam 422 em português sem minuta viva.
  `views._lista_justificativas`: prefetch inclui todos os estados e filtra os links
  pela projeção anotada, sem consulta por linha. Outras funções de views, templates,
  JavaScript, modelos, migrações e emissão automática não foram editados aqui.

Novo `test_documentos_correntes.py` contém casos com modelos/DB para execução pelo
coordenador: última falha/pendente, justificativa vazia/shape inválido/presente,
assinatura antiga/exata/revogada/sem caminho, equivalência anotação/projeção sem SQL,
uma consulta de vias para dois tipos, anexação recusada sem mutação, reader/scope,
DOCX pronto sem PDF, snapshot após alteração viva, GET sem escrita de negócio,
reabertura e arquivo, PDF exato e via revogada do cancelado, lista justificativa sem
promover histórico, budgets 19/20/12 incluindo listas de 20/200 ofícios.

Evidência executada nesta subtarefa: Ruff verde nos 6 arquivos de código/teste;
mypy com configuração real do projeto verde nos mesmos 6 arquivos (sem issues);
`git diff --check` verde no worktree. O primeiro mypy apontou estreitamentos opcionais
e lambda append no teste, corrigidos sem alterar asserções de negócio. Ruff apontou
ordem de import, comprimentos e regex literal, corrigidos antes da checagem final.

Nenhum teste DB/browser nem worker foi executado pelo subagente. Os budgets são
asserções entregues, ainda não medições desta integração. Downloads por identidade
exata não foram modificados e seguem sob a validação do coordenador. Mais campos
anotados podem mudar custo do plano SQL apesar da quantidade constante; validar o
ensaio de desempenho e a suíte HTTP antes de declarar a integração concluída.

## Resumo conectado e congelado para validação — 07/10/2026

_contexto_resumo materializa documentos com emitido_por e anota Exists das vias
na mesma consulta. Sem vias, fornece lista vazia sem pagar consulta vazia; quando
existem, lê TODAS com enviado_por uma vez, inclusive revogadas. Passa uma única
projeção ao menu e _vias_do_oficio; apresentação separa correntes/históricos, usa
arquivos preenchidos para links e ignora gerações históricas no gerando/polling.
EProtocolo conserva RS-01 e revisão/D13; PDF/Word/anexação têm readiness separado.

_resumo_documentos, _resumo_documento e _resumo_rodape são parciais do layout existente.
Wrappers estáveis resumo-documentos-area/data-resumo-poll, resumo-rodape e
resumo-copia-area; hx-select-oob atualiza ações e mensagem de cópia. Rodapé tem
role group, label Ações do ofício e tabindex=-1 para fallback de foco. Não há minuta
emitida como fallback, link PDF sem arquivo ou Word corrente gerando/falhou.
O coordenador implementou o hook de fechamento em dialogo.js; arquivo não alterado
por este subagente. HTMX vendorizado confirma OOB antes da seleção principal.

Novo test_resumo_documentos cobre corrente/histórico, snapshot sem prontidão,
assinaturas exatas/revogadas e original ausente, justificativa antiga, cancelado,
reabertura, projeção uma vez/zeroSQL, transição GET gen→ready, IDs, autorização,
GET sem escrita e budgets resumo 20/15. Não executado pelo subagente.

Correções posteriores à collection da rodada HTTP ativa precisam de focused novo:
18:49:44 Brasília — retry só not historico, comentário do PDF corrente, E501 e caso
retry corrente falha versus antiga falha. 18:53:30 — historico=False explícito na
linha corrente e dois casos de render com lista Historico legítima herdada (pronto
/falhou), que não deve trocar rótulo nem suprimir retry. Código/templates/HTTP
congelados após essas correções; não atribuir sua validação à collection anterior.

Novo tests/e2e/test_resumo_versoes_documentais.py tem 5 casos para o coordenador:
transição real de ORM worker→GET HTMX com PDF/Word/menu corretos e cópia/foco/details
preservados em 360/1440, axe/capturas; close durante GET real em voo (route.fetch
recebe HTML real, fecha antes de entregar), sem reaparecer/furtar foco/novo HTTP;
histórico gerando sem polling; reaberto com minuta e assinatura revogada histórica.
Não usa mock de XMLHttpRequest e não foi executado pelo subagente. Capturas serão
escritas em artifacts/rs02-resumo/corrente-pronta-{360,1440}.png apenas na execução.

Ruff verde para views, HTTP e E2E novos. Mypy views/HTTP foi verde antes dos últimos
dois casos; rechecagem final em andamento na entrega incremental. Mypy direto com
E2E também carrega conftest.py: 4 erros preexistentes de generators/callbacks nele,
nenhum no E2E novo, sem alteração fora ownership. Validação normal do projeto exclui
esses E2E; não afirmar mypy geral E2E verde. git diff --check verde. Nenhum DB/browser
executado aqui; execução, budgets medidos e análise das imagens ficam com root.

Rechecagem após o último freeze: mypy real do projeto views + test_resumo_documentos
verde (2 arquivos, sem issues), Ruff dos 3 arquivos verde e git diff --check verde.
Essa evidência estática inclui os dois casos de contexto herdado e retry; não
substitui o focused LAB que o coordenador executará após a rodada em andamento.

## Regressão QA — foco do menu após OOB

Acrescentados dois casos parametrizados ao E2E próprio:
test_polling_justificativa_preserva_foco_operavel_em_mais_acoes[word_com_id/item_sem_id].
Ofício v2 pronto mantém Word disponível; seu snapshot contém justificativa e a
justificativa v1 está gerando, mantendo polling real. O menu é aberto e o teste
foca Word com ID ou item operável sem ID; conclusão ORM da justificativa é lida
pelo próximo GET HTMX. Aceita foco no gatilho do menu novo fechado, ou item visível
em menu novo aberto com aria-controls/expanded coerentes. Depois verifica teclado:
fechar se necessário, abrir com Enter, Word visível/focado, Esc volta ao gatilho.
Um item Word existente porém oculto não satisfaz a verificação de operabilidade.

Fonte do achado: root/QA observou foco OOB em Mais ações; menu.js.connectedCallback
inicia o painel fechado e disconnectedCallback recolhe o antigo. O hook anterior de
dialogo.js restaurava ID sem verificar visibilidade. Root assume sua correção;
nenhum JS, view, template ou HTTP foi editado nesta subtarefa complementar.
BeforeRequest guard conhecido cancela HTTP com diálogo fechado/saindo; não remove
a definição every 2s no markup, logo registrar cessação de pedidos, não afirmar
eliminação do timer. Lista/selecao corrente continua domínio+snapshot: histórico
gerando não deve ativar polling; justificativa corrente gerando deve ativá-lo.

Ruff do E2E e git diff --check verdes. Agora 7 casos no arquivo E2E (5 anteriores
+ 2 novos); nenhum E2E/DB/browser executado pelo subagente nesta subtarefa. Arquivo
congelado para validação do coordenador. Não reexecutado mypy E2E completo, conforme
limite combinado e erros preexistentes documentados de conftest.py.

## Reexecução pelo principal — gate delimitado de 07/10/2026

Os sete cenários passaram juntos em 75,05 s, inclusive os dois de foco operável.
O oitavo guard acrescentado depois (via cruzada/pacote indisponível) passou com
upload OS em 23,12 s; todos os oito Resumo passaram nas duas consolidações de
navegador. Após restaurar CSS, a projeção 360/1440 também verifica estilo real
inline-flex da divulgação eProtocolo. 64 consumidores/guards HTTP passaram em
103,39 s; pacote PDF/DOCX normal/fetch em 13,61 s. Esses resultados substituem o
"não executado" histórico acima; não aprovam critérios de paridade ainda fora
do bloco. Relatório/evidências em
`../visual-agents/qa/fechamento-gate-final-2026-10-07.md`; integral final pendente.
