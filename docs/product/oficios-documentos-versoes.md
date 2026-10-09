# Ofícios — seleção de versões e reabertura (RS-02)

## Erro visível ao baixar pacote incompleto

07/10/2026, teste real do candidato: pacote com justificativa esperada ausente
deve ser recusado sem arquivo/minuta/versão nova. O motivo precisa aparecer na
janela Baixar. Para o POST fetch existente (X-Requested-With: fetch), responder
422 JSON com erro, sem redirecionar/consumir mensagem numa navegação intermediária.
POST de formulário normal mantém mensagem e redirecionamento. A janela conserva
as escolhas e exibe o erro em seu role=alert existente; permite fechar ou tentar
depois de corrigir o documento. Não criar nova UI nem mudar seleção de documentos.

Registro iniciado por investigação de código local em 07/10/2026, sem banco,
navegador, produção ou arquivo documental. As etapas de domínio, adaptador e
integração incremental autorizadas depois estão registradas abaixo; a validação
HTTP/browser da integração é conduzida pelo coordenador, separada dos testes puros.

## Fontes e força das regras

Referência local, somente leitura:
`C:/Users/tiago/OneDrive/Documentos/Solicitações de eventos/`.

- `documentos/services/emissao.py`: `vias_emitidas`/`via_emitida` (linhas 53–69),
  `registrar_emissao` (109–144), `emitir` (177–214) e `resumo_da_via` (216–225).
  A via emitida é a de maior versão; guarda conteúdo e identificação da emissão.
  A via assinada prevalece sobre o original quando solicitada. Geração é síncrona,
  portanto não comprova o comportamento desejado para `gerando`/`falhou` no novo.
- O mesmo arquivo, `emitir`, na ausência de via assinada solicitada, promove uma nova
  versão quando detecta alterações posteriores do próprio documento; sem alterações
  retorna a via congelada. Isso
  complementa a docstring de `viagens_oficios/views.py.nova_versao_pedida` (863–866):
  a docstring isolada não descreve toda a regra implementada no serviço legado.
- `templates/pages/viagens_oficios/_documento_inline.html` (19–29): versão e data,
  selo de assinado, PDF da via emitida e ação de nova versão.
- `viagens_oficios/services.py.reabrir_oficio` (466–503): motivo obrigatório,
  volta de Finalizado para Gerado, revogação da via assinada, retenção do arquivo
  e registro da reabertura. `templates/pages/viagens_oficios/form.html` (71–82)
  mostra o formulário existente; `views.py.acao` (806–828) exige operador no legado.

Fontes do produto novo:

- `docs/product/documents.md`, seção Formato: Documento imutável por ofício/tipo/versão,
  snapshot, geração assíncrona, minuta não arquivada e nova versão após reabrir/emitir.
- `docs/product/workflows.md`: gestor reabre emitido com motivo; versões anteriores
  permanecem. O documento ainda contém descrições antigas de cancelamento terminal
  e ausência de arquivamento; elas divergem dos serviços/policies atuais. Este estudo
  não usa esses trechos antigos para restringir leitura de históricos.
- `docs/product/permissions.md`: `reabrir_oficio` do gestor; leitura pelo escopo da
  política, inclusive leitores. Não copiar a autorização de operador do legado.
- `docs/visual-agents/visual/oficios-detalhe-plano.md`: **D14** aprova tornar a
  reabertura alcançável no menu canônico e no resumo com motivo; **D17** deixa nova
  emissão sem retificação pendente de decisão humana. São direções registradas pelo
  orquestrador; este estudo não afirma uma confirmação humana adicional de D14.
- `docs/product/oficios-lote-h.md`: repetir geração mantém documento, snapshot,
  versão e mensagem; cancelado/arquivado não regeneram pelo fluxo.
- `docs/product/oficios-eprotocolo.md`: RS-01 usa a maior versão de ofício mesmo
  quando gerando/falhou, sem reconstrução silenciosa com dados vivos.

## Constatações no código atual

`gestao/viagens/models.py.Documento` tem tipo, versão por tipo, estado de geração,
snapshot, arquivo/hash, data e autor da emissão. `ViaAssinada.documento_id` identifica
a versão PDF/A assinada; `revogada_em` distingue uma via em vigor de uma revogada.
São três dimensões distintas: situação do ofício, estado de geração e assinatura.

Os seguintes caminhos selecionam somente documentos **prontos antes de escolher a
maior versão**. Com ofício v1 pronto e v2 gerando/falhou, escolhem v1:

- `queries.py._pdf_do_oficio` e `_pdf_da_justificativa`, usados nas anotações de
  `com_dados_de_lista`: `pdf_oficio_id`, `pdf_oficio_versao`,
  `pdf_justificativa_versao`.
- `policies.py._pdf_do_oficio` e `_justificativa_emitida`, fallback de leitura do
  menu quando não recebeu seleção anotada ou explícita.
- `views.py._contexto_resumo`: `pdf_oficio` é o primeiro ofício pronto da lista;
  a seleção de justificativa para o menu faz o mesmo. `_vias_do_oficio` também
  escolhe primeiro pronto de cada tipo e agrupa a via por tipo/chave.
- `assinados.py.documento_emitido`, usado por anexação e pacotes; `views.py.baixar_docx`
  e `pacotes.py._itens_do_oficio_proprio`.
- `_lista_justificativas` prefetches somente justificativas prontas. É um consumidor
  a auditar na integração futura, sem redesenhar sua lista nesta etapa.

Não foi observada ocorrência concreta em dados de produção: a divergência acima
é demonstrável pelas condições das consultas. RS-01 já escolhe v2 no mesmo cenário,
logo os textos de cópia e o PDF principal podem representar versões diferentes.

O menu canônico `policies.menu_do_oficio` já força `minuta=True` no rascunho, mesmo
havendo PDF antigo. Porém o rodapé de `_resumo.html` usa diretamente `pdf_oficio`:
um rascunho reaberto com v1 pronta oferece “Ver o PDF” do histórico como ação principal.
Para emitido sem PDF pronto, tanto menu quanto rodapé podem oferecer a minuta viva,
sem identificar que ela não é o snapshot emitido. Isso exige tratamento de apresentação.

`baixar_documento(documento_id)` já endereça uma versão exata, exige `pode_ver` e
estado pronto; prefere a via não revogada **vinculada àquele documento**. `?versao=original`
pede o PDF/A gerado. Esse acesso explícito pode servir ao histórico, inclusive
cancelados autorizados. `views_assinados.abrir` usa `assinados.pode_abrir`; para ofício
ela delega a `policies.pode_ver`, sem proibir cancelado ou via revogada. Não remover
essas possibilidades de leitura ao corrigir a seleção principal.

## Proposta de projeção única, sem Django

Proposta de domínio puro futuro: receber situação/arquivamento do ofício, descrições
imutáveis de documentos e descrições de vias assinadas já selecionadas pelo adaptador.
Não receber models, querysets, usuário, arquivos abertos ou URLs; não consultar
storage, decidir permissão ou executar serviço.

Entradas mínimas por documento: `id`, `tipo`, `versao`, `situacao`, indicação de
arquivo/hash registrados, `emitido_em` e identificação já formatada de `emitido_por`.
Por via: `id`, `tipo`, `documento_id`, data/autor do envio e revogação quando houver.
O adaptador mantém a propriedade do ofício autorizado e exclui registros de outros
objetos antes de chamar o domínio. Metadado de arquivo registrado não prova que os
bytes existem; a leitura efetiva continua validada pelo download existente.

Saída por tipo: `ultima_emissao` (máxima versão sem filtro de pronto), `corrente`
(aplicável ao estado do ofício), `estado_geracao`, `pdf_original_corrente`,
`via_assinada_corrente`, `historico` e avisos de inconsistência. Nenhum booleano
“assinado” substitui o estado de geração. O histórico guarda cada versão exata,
original pronto e vias vinculadas, incluindo revogadas com identificação histórica.
Versões antigas continuam alcançáveis por ID e rotuladas como versões anteriores.

Regras propostas, deduzidas dos contratos acima, ainda sem validação de tela:

- **Rascunho:** nenhum documento anterior é corrente. A ação principal continua
  minuta dos dados atuais; emissões anteriores ficam no histórico, sem serem
  chamadas de minuta nem de PDF da edição atual.
- **Emitido:** corrente é a maior versão do tipo, inclusive gerando/falhou.
  Original corrente só está disponível se essa mesma versão estiver pronta.
  v1 pronta fica no histórico quando v2 ainda não tem PDF; não promovê-la ao
  lugar de v2. Gerando informa espera; falhou oferece retry apenas pela política
  existente. Não gerar minuta viva como fallback da emissão oficial.
- **Assinado:** via corrente precisa ser não revogada e ter `documento_id` igual
  ao documento corrente do mesmo tipo. Uma via de v1 nunca assina v2 por coincidência
  de tipo/chave. Vias de outra versão ficam identificadas com aquela versão.
- **Cancelado:** documentos são históricos da emissão cancelada; os prontos e
  assinados continuam legíveis se a política autoriza. Não apresentar cancelamento
  como arquivo apagado, nem criar reabertura/retry permitidos por esse estado.
- **Arquivado:** não muda a versão selecionada da situação subjacente, mas preserva
  as restrições atuais de mutação. Um emitido arquivado continua legível.
- Ordem da projeção: ofício, justificativa, demais tipos reconhecidos. Termos são
  registros de outro modelo/serviço; incluí-los na apresentação unificada não os
  transforma em `Documento` versionado nem exige migração de modelo nesta etapa.

### Limite real: versão por tipo não identifica o lote de emissão

`services.emitir` incrementa a versão separadamente para cada tipo. Sempre cria
ofício e só cria justificativa se há texto. Não existe um ID comum de emissão.
Assim, ofício v2 sem justificativa deixa justificativa v1 no banco; simplesmente
escolher `max(versao)` por tipo não comprova que v1 acompanha a emissão atual.

Proposta mínima sem mudar o modelo: o adaptador lê o campo `justificativa` do
snapshot do último ofício para informar quais tipos aquela emissão contém.
Vazio torna justificativas anteriores históricas. Texto presente acompanha a
invariante de `emitir`, que cria a justificativa na mesma transação, mas registros
importados ou incompletos ainda podem violá-la. Snapshot ausente/inválido ou falta
da justificativa esperada produz estado indeterminado com aviso; não adivinhar
correspondência por proximidade de timestamps, número igual ou versões iguais.
Essa classificação é proposta técnica, não uma nova regra humana confirmada.

## Pontos canônicos e integração futura

O resumo deve adaptar sua lista atual de documentos/vias uma vez e passar a mesma
projeção à lista de Documentos, rodapé, menu e metadados; não repetir `first(PRONTO)`.
O menu mantém suas permissões em `policies`, recebendo a seleção explícita da projeção.
RS-01 deve usar a mesma identidade de última emissão, preservando seu snapshot.

Na lista, preservar as anotações constantes de `com_dados_de_lista`: escolher o
último documento sem filtrar pronto e anotar seu estado/versão/ID; derivar o PDF
disponível dessa mesma identidade. A assinatura precisa corresponder a esse ID,
em vez de `Exists` somente por tipo. Evitar prefetch ou consulta adicional por linha;
medir custo/plano das subconsultas antes de decidir detalhes da consulta. Nada aqui
autoriza aumentar budgets existentes ou redesenhar as listas aprovadas.

Anexação, DOCX e pacote devem consultar a mesma seleção em seus adaptadores.
DOCX preserva o contrato atual: somente uma versão pronta permite exportação emitida,
e essa versão deve ser a última identidade. Não habilitar DOCX de gerando/falhou.
Pacote não deve substituir silenciosamente uma versão em falha por PDF antigo ou
minuta; o erro do item já aborta o pacote por contrato. Downloads explícitos de
histórico mantêm a rota/política atuais.

O polling do resumo hoje troca só `resumo-documentos-area`. Quando a geração
termina, o rodapé e o menu também precisam receber a nova disponibilidade corrente;
a troca deve preservar divulgação/foco e reutilizar o resumo autorizado. O escopo
de DOM e a forma mínima da atualização ficam para a implementação, sem redesenho.

## Reabrir gestor: somente ligar UI ao serviço existente

Direção D14: a ação deve surgir no mesmo menu canônico da lista e no “Mais ações”
do resumo, quando `policies.pode_reabrir` autoriza. A política já exige Emitido,
não arquivado, permissão `reabrir_oficio` e visibilidade do objeto. Operador e leitor
não ganham a ação pela capacidade de baixar documentos.

Lacuna exata: `policies.acoes_do_oficio` não devolve `reabrir`; `_acoes_ciclo.html`
não desenha o item. A rota POST `oficios/<pk>/reabrir/`, `views.reabrir` e
`services.reabrir` já existem. Proposta: acrescentar a chave ao ciclo e usar o
`dialogo_motivo` existente (`data-pedir-motivo`, campo `motivo`) com a explicação:
“Volta a rascunho. As versões emitidas permanecem no histórico; as vias assinadas
são revogadas e o documento corrigido precisa ser assinado de novo.”

O serviço já trava o ofício, valida motivo, registra histórico, revoga vias e
preserva PDFs. A UI não deve copiar essas escritas, mudar marcador para retificado,
gerar versão no GET ou substituir a ação “Editar ofício”/retificação. Manter retorno
da view e diálogo acessível; nenhuma alteração de serviço ou modelo é necessária.

## Decisões pendentes e verificação futura

- D17 permanece pendente: emitir nova versão sem reabrir/retificar e a geração
  automática por mudanças do próprio documento do legado não estão autorizadas
  para inclusão nesta reconstrução.
- O tratamento visual de emissões inconsistentes ainda depende de validação de tela.
  DOCX de gerando/falhou permanece fora do contrato desta etapa.
- Validar o reconhecimento de justificativa da última emissão contra fixtures de
  ciclos com e sem texto; não usar heurística de data ou inventar vínculo estrutural.
- Testes puros: v1 pronta/v2 gerando e falhou; tipos fora de ordem; rascunho reaberto;
  cancelado/arquivado; via v1 versus v2; via revogada; ausência/shape inválido e
  justificativa antiga após nova emissão sem texto.
- Integração: menu/lista/resumo/DOCX/pacote concordam na identidade; downloads
  históricos exatos continuam autorizados; reabrir só gestor com motivo e CSRF;
  revogação e snapshots preservados; polling atualiza disponibilidade sem perder foco;
  SQL dentro dos budgets atuais, sem N+1; navegador/capturas nos fluxos tocados.

Evidência desta etapa: fontes e pontos de seleção acima foram lidos no checkout
local. Não houve implementação nem execução de teste, banco ou navegador; nenhuma
lacuna é declarada corrigida por este documento.

## Base pura RS-02 — contrato antes da implementação

Em 07/10/2026 o coordenador aprovou tecnicamente a classificação de justificativa
pelo snapshot do último ofício: presente/vazio/indeterminado, sem promover uma
justificativa antiga nem reconstituir conteúdo. A implementação independente não
altera as aplicações, listas aprovadas ou a geração/documentos existentes.
Decisão estrutural registrada no ADR 0025, em revisão.

O domínio recebe DTOs mínimos de documento (`id`, `tipo`, `versao`, `situacao`,
`tem_justificativa` opcional no ofício) e via (`id`, `tipo`, `documento_id`,
`revogada`). O adaptador futuro deve classificar apenas o valor do campo
`snapshot["justificativa"]`: string não vazia após strip é presente; string vazia
é ausente; outro tipo/campo ausente é indeterminado. Nenhum snapshot completo,
model, URL, autor ou data é necessário à seleção pura.

A saída por tipo contém última emissão, corrente, estado de geração, disponibilidade
PDF/DOCX, via assinada corrente, histórico de versões/vias e aviso. A maior versão
é escolhida sem filtro pronto; PDF e DOCX correntes exigem essa mesma identidade
pronta. Rascunho/cancelado não têm corrente e preservam todas as emissões no
histórico. Arquivamento é ortogonal à seleção. Vias não revogadas só valem para o
ID/tipo exatos; as revogadas permanecem no histórico da versão correspondente.
Identidades empatadas na maior versão ou múltiplas vias vigentes exatas produzem
indisponibilidade da seleção ambígua com aviso, nunca desempate arbitrário.

Justificativa esperada mas ausente, snapshot indeterminado e justificativa sem
último ofício identificável produzem aviso e nenhuma justificativa corrente.
Tipo com versão anterior omitida da última emissão permanece histórico.
Tipo desconhecido preserva ordenação estável após ofício/justificativa; isso
não autoriza adaptar Termo/OS de outros modelos como `Documento` fictício.

## Evidência da base independente — 07/10/2026

Implementação em `gestao/viagens/dominio/documentos_versoes.py`; testes em
`gestao/viagens/tests/test_documentos_versoes.py`. API: `presenca_justificativa`
classifica o campo do snapshot; `selecionar_versoes` retorna tupla de
`SelecaoPorTipo`. `corrente` contém a descrição da versão e todas as vias vinculadas,
inclusive revogadas para consulta histórica; `historico` contém as outras versões,
ou todas quando nenhuma é corrente. `via_assinada_corrente` só devolve uma via
não revogada, exata e única, de documento pronto. Estado pronto indica disponibilidade
registrada, sem afirmar existência dos bytes em storage.

**39 testes puros passaram em 0,17 s.** Execução com
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `python -m pytest --noconftest -o addopts=''`
e somente `gestao/viagens/tests/test_documentos_versoes.py`. O aviso de opção
`DJANGO_SETTINGS_MODULE` desconhecida decorre da desativação do plugin Django;
nenhum conftest, fixture de aplicação ou banco foi carregado.

Ruff dos dois arquivos: `All checks passed!`. Mypy do domínio, isolado com
`--config-file nul --check-untyped-defs`, sem plugin Django: `Success: no issues
found in 1 source file`; aviso do arquivo vazio de configuração sem seção mypy.
Essas verificações não usam o verificador completo da aplicação.

Cobertura: maior identidade durante geração/falha; mesma identidade para PDF/DOCX;
rascunho reaberto/cancelado com históricos legíveis; arquivamento ortogonal;
assinatura exata, revogada, de outro tipo, sem vínculo, ambígua ou incompatível
com PDF pronto; presença/vazio/shape inválido de justificativa; falta de tipo
esperado; versões independentes por tipo; identidade ambígua; estado desconhecido;
ordenação sob permutações; DTOs imutáveis e inputs preservados.

Não houve integração em views/models/queries/policies, alteração de aplicação
congelada, browser ou acesso ao banco. Nenhuma seleção existente no sistema
foi corrigida por executar estes testes. O coordenador ainda precisa revisar,
reexecutar e autorizar a conexão posterior aos adaptadores e telas.

## Adaptador independente RS-02 — contrato antes do código

O chamador autoriza o ofício antes de `projetar_documentos` e fornece documentos
e vias já carregados como listas/tuplas, inclusive listas vazias. Não existe
fallback de consulta. O adaptador lê metadados locais, não relações, storage,
URLs ou campos deferred. Metadados documentais necessários ausentes impedem a
seleção com aviso; não ignorar o registro incompleto e promover um antigo.
Vias com metadados incompletos não são promovidas a assinadas correntes.

Modelos de outro ofício são excluídos dos mapas e da seleção. DTOs ficam no domínio;
os modelos originais permanecem em mapas de leitura por ID para o consumidor
obter snapshot, autor/data ou arquivo sem reconstrução e sem consultas por item.
O consumidor continua responsável por carregar previamente os campos/relações
que apresentar; a ausência de SQL do adaptador não valida consultas do template.

São disponibilidades distintas: estado registrado pronto, original com caminho
de arquivo preenchido, via assinada exata com caminho preenchido e PDF efetivo
(assinado quando disponível, senão original). Não verificar bytes em storage.
Documento pronto sem caminho não recebe link de PDF original. Via sem caminho
recebe aviso e não é usada como PDF; o original exato pode continuar disponível.
DOCX preserva a última identidade pronta e usa o snapshot, sem exigir leitura do
arquivo PDF; nunca habilita gerando/falhou nem promove v1 por falta de v2.
Históricos são endereçados por ID, com disponibilidade original/assinada separada.

Nenhum consumidor muda nesta etapa. O plano de migração dos oito caminhos e as
verificações independentes ficam em `docs/quality/oficios-documentos-projecao.md`.

O adaptador independente e seus **42 testes com objetos em memória** passaram em
0,13 s, sem Django/conftest/banco. Ruff e mypy isolado (imports pulados, sem plugin
Django) verdes. A evidência detalhada inclui limites, correções de fixture/tipagem
e plano de validação real. Isso não liga a projeção ao produto nem comprova budgets
das views: a integração e a execução HTTP/SQL/browser continuam pendentes.

## Integração RS-02 autorizada em 07/10/2026

A seleção nos consumidores usa a maior versão por tipo, sem filtro prévio de pronto.
O menu oferece minuta apenas no rascunho; emitido gerando/falhou não oferece v1 nem
reconstitui documento vivo. A justificativa corrente deriva da presença textual no
snapshot do último ofício; valor vazio remove a ação corrente, inválido/ausente
impede promovê-la. Arquivamento não altera essa seleção. Downloads por identidade
exata e vias revogadas continuam regidos pelas políticas existentes.

As listas anotam identidade, versão, situação, caminho e presença de justificativa
na consulta existente, passando os metadados ao mesmo domínio puro. A via assinada
precisa do ID exato da versão corrente, tipo e caminho preenchido. Detalhes recebem
projeção explícita de listas carregadas; nenhum consumidor consulta por item.

Anexar mantém a transação e bloqueio do dono, porém exige a versão corrente pronta
com arquivo. Pacotes leem os documentos de uma vez: minuta somente rascunho,
snapshot emitido somente pronto; item indisponível aborta quando solicitado com
mensagem em português. DOCX pronto pode usar o snapshot mesmo sem caminho PDF;
gerando/falhou não pode. A rota DOCX de cancelado preserva leitura histórica da
maior identidade pronta, sem promover versão anterior se a última falhou/gera.
Não há alteração de permissões, locks, outbox, formato de pacote, emissão automática
(D17), modelos, termos ou layout nesta integração.

Testes de integração serão entregues para execução pelo coordenador em LAB.
Validação estática desta etapa não comprova budgets, navegador ou banco.

## Resumo RS-02 — contrato antes da conexão à tela

O resumo materializa os documentos e todas as vias do ofício uma vez, com autores
carregados, e fornece uma única ProjecaoDocumentos às ações, menu e apresentação.
Correntes e históricos têm listas identificadas separadamente. Rascunho reaberto
tem minuta e conserva PDFs/vias antigos no histórico; cancelado conserva leitura
por identidade exata conforme políticas. Via antiga, revogada ou de outro ID não
sela a versão corrente. Caminho vazio não cria link de PDF.

PDF, DOCX e anexação exigem a disponibilidade definida acima. eProtocolo conserva
RS-01: snapshot válido da maior emissão mesmo gerando/falhou, sem promover anterior
ou reconstruir dado vivo. Rascunho/revisão conservam dados vivos e preparação D13.
Documento histórico gerando não aciona polling. Só correntes relevantes gerando
mantêm a atualização automática, que troca Documentos e os wrappers de rodapé/cópia.
A divulgação e foco da cópia são preservados pelos handlers OOB existentes.

Markup HTMX autorizado: `#resumo-documentos-area[data-resumo-poll]`, seletor principal
igual ao ID, `hx-select-oob="#resumo-rodape,#resumo-copia-area"`, troca outerHTML e
GET da rota existente resumo. Nenhum endpoint novo ou script inline. HTMX está com
allowEval=false; portanto filtro JavaScript no hx-trigger não seria solução válida.
O coordenador assume o pequeno hook em dialogo.js para cancelar polling com diálogo
fechado/saindo e abortar pedido em voo no close. Essa dependência precisa de teste
real de foco/cópia/menu, polling em andamento e cessação ao fechar o diálogo.

A ação Gerar de novo fica só na corrente falha: services.regenerar_documento
recusa versões superadas e não deve existir botão que sempre será recusado no
histórico. Continua reusando a mensagem/versão, sem nova emissão. O include da linha
corrente passa historico=False explicitamente, pois a folha pode herdar uma lista
Historico de negócio; essa lista não pode classificar uma versão corrente como
histórica nem retirar sua ação de retry.

## Foco no menu após OOB — regressão complementar

Com ofício corrente pronto e justificativa corrente gerando, Word está disponível
e o polling continua pela justificativa. Se Mais ações estiver aberto no momento
da troca OOB, o pc-menu anterior é desconectado e o novo painel nasce fechado.
Um item Word com ID estável não pode receber foco enquanto seu painel está oculto.
Restaurar foco só em controle operável; neste caso voltar ao gatilho Mais ações do
novo menu fechado, ou preservar um menu aberto válido. A mesma regra vale para um
item focado sem ID. Não tomar foco de outra ação que a pessoa escolheu enquanto
aguardava a resposta. Root é responsável pelo hook em dialogo.js.

Fonte local: dialogo.js registra htmx:beforeRequest em data-resumo-poll e impede
HTTP se o diálogo está fechado/saindo; close aborta pedidos em voo e beforeSwap
rejeita resposta tardia. Não há evidência de remoção do timer every 2s do HTMX:
o guard interrompe pedidos, mesmo que o timer conhecido permaneça agendado no DOM.
Files/lista documental usam seleção corrente do domínio/projeção; geração histórica
não mantém polling. _contexto_resumo gerando considera somente selecoes correntes,
cujo tipo justificativa é autorizado pela presença textual no snapshot do ofício.
Essas dimensões não dependem do foco nem do menu aberto.

## Fechamento — defesa da leitura exata e HTML

A crítica reproduziu menu com pdf=None/minuta=False que ainda oferecia Ver
minuta: o template deve respeitar a flag explícita. A leitura por ID de documento
preserva acesso ao histórico e opção versao=original. Via automática precisa ter
mesmo dono/tipo/documento, caminho preenchido e autorização da via; caso inválido
usa o original autorizado. Caminho original vazio ou arquivo ausente retorna404,
sem entregar outro arquivo ou produzir500. Não se modifica documento emitido.
Teste de regressão: test_leitura_documental.py, validação LAB pendente.

Após OOB, item equivalente oculto no menu fechado não recebe foco: o gatilho
Mais ações é a retomada operável, sem roubar foco escolhido fora do rodapé.
Esses pontos corrigem defeitos comprovados da conexão corrente/histórico e
permanecem dentro do fechamento, sem nova etapa visual.

Pacote: quando o snapshot corrente exige justificativa e o registro documental
está ausente, o item Justificativa permanece visível como PDF indisponível; o
pedido desse item aborta o pacote com orientação existente. Não gerar minuta nem
omitir silenciosamente o documento esperado. Snapshot vazio segue sem item;
shape indeterminado não autoriza associar histórico. Usa Item/closure existentes,
sem nova UI ou contrato. Caso real novo no teste de leitura, validação pendente.

## Acesso secundário ao histórico — 08/10/2026

O Resumo aprovado apresenta somente a emissão corrente na estação documental.
Versões anteriores e vias revogadas permanecem legíveis em **Mais ações → Histórico
de documentos**, em diálogo secundário. O conteúdo vem da projeção autorizada
existente e mantém links por identidade exata; não promove versões antigas nem
permite retry histórico. Ao fechar, o foco volta a Mais ações no Resumo.

O pacote **Baixar documentos…** contém a emissão corrente e não substitui essa
leitura histórica. Cancelados e rascunhos reabertos preservam seus links históricos
conforme as permissões existentes. Não há alteração de snapshots, hashes, arquivos,
geração ou regras de seleção. Testes: `test_resumo_documentos.py` e
`test_historico_secundario_preserva_corrente_e_devolve_foco`.
