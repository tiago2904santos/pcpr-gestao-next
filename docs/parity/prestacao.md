# Prestação de contas — acompanhamento da migração visual

Fonte funcional: `docs/migration/prestacao.md`, levantamento da referência de
05/10/2026. Esta rodada não redefine prazos, permissões, finalização nem documentos.

## Lista — PR01, 12/10/2026

Preservados: agrupamento por ofício; 25 equipes por página; contadores por servidor;
busca; abas de situação e atenção; edição e autosave por servidor; ações individuais
e de equipe; justificativa de finalização; envio, aprovação, devolução, arquivamento;
exportação filtrada; acesso a Diário, Relatório e Documentos; consulta sem edição.

Três defeitos demonstrados antes da correção e cobertos por regressão:

- A busca perdia abas combinadas: conserva todos os valores `aba` na URL e no formulário.
- A apresentação das ações de equipe usava apenas o recorte da busca: calcula o estado
  com a equipe ativa completa, exibindo somente as linhas do recorte. Os serviços
  continuam sendo a autoridade das ações e permissões.
- A substituição HTMX dos resultados perdia os diálogos de envio: os diálogos e o
  rodapé pertencem ao fragmento substituído; IDs e seletores OOB foram preservados.

Evidências e verificações: `docs/visual-agents/qa/prestacao-lista-2026-10-12.md`.
PR03 Relatório e PR04 Documentos ainda exigem migração própria; sua
compatibilidade com os estilos compartilhados não equivale a migração concluída.

Lacunas funcionais históricas devem ser conferidas por fluxo (por exemplo, cadastro
de feriados e histórico dedicado por servidor, citados no levantamento original).
Não foram supridas por alterações visuais nem declaradas concluídas nesta rodada.

## Diário de Bordo — PR02, concluído tecnicamente, 12/10/2026

Mantidos os três modos de motorista e de viatura, campos condicionais, aplicação
somente ao Diário/RT, horários realizados editáveis com recálculo e desfazer,
km e abastecimento com autosave, bloqueio de km final inferior ao inicial,
avisos não bloqueantes do hodômetro, consulta sem edição e trava de equipe
finalizada. PDF paisagem e XLSX não tiveram templates oficiais modificados.

O novo resultado por trecho usa a distância já calculada no domínio. Sua região
`data-vivo` atualiza depois do autosave preservando o foco nos campos. A barra
final mantém o estado de gravação em todas as larguras; Finalizar continua
retornando à Lista filtrada sem finalizar prestações. Evidências e revisão em
`docs/visual-agents/qa/diario-2026-10-12.md`.
## Relatório Técnico — PR03, concluído tecnicamente, 12/10/2026

Mantidos cinco textos da equipe, sugestões, copiar relatório, textos prontos,
custeio com Outro, valores individuais com observação e limite liberado,
autosave e Finalizar aguardando gravação. Leitura/equipe finalizada e travas
individuais preservadas. PDF e DOCX por servidor mantêm fontes documentais.
O componente de valor associa a referência liberada ao input por aria-describedby.
Texto pronto usa o componente compartilhado sem duplicação de JS.

Evidências: qa/relatorio-2026-10-12.md, 15 capturas finais, nove consumidores
de texto pronto, 92 testes iniciais e 78 pós-limpeza finais. Removida apenas
grade-campos, cujo consumidor foi migrado. PR04 Documentos/Anexos continua
pendente naquele checkpoint; fechamento posterior abaixo.

## Documentos da prestação — PR04, 12/10/2026

Preservados anexação, correção de valor/data/operação, remoção lógica, restauração,
versões e travas por equipe/servidor. Carimbo mantém o PDF original, comprovado
por hash antes/depois. Forms multipart, CSRF, IDs e âncoras permanecem.
Regressão integrada de Lista, Diário, Relatório e Documentos:38 testes aprovados.
QA em `docs/visual-agents/qa/anexos-2026-10-12.md`, cinco larguras e correções abertas.
Não houve mudança nos documentos oficiais nem implementação das lacunas históricas.

## Recomposição integral solicitada — 15/10/2026

Melhoria intencional de apresentação, mantendo os contratos funcionais anteriores:
lista com cartões de solicitação por servidor e resumo canônico do Ofício, navegação
entre as folhas, Diário começando pelos quilômetros, RT em pares de campos e
Documentos com anexos individuais organizados em blocos. Configuração do carimbo
fica em divulgação, sem ocultar documentos nem alterar a posição gravada.

Não há cadastro manual novo, novo resumo/endpoint nem outro componente visual.
Os campos de cadastro continuam sendo os da solicitação, Diário, RT e anexos.
Mantidos filtros combinados, paginação por 25 equipes, exportação, edição por
pessoa, autosave e trava, envio/aprovação/devolução, diário realizado, limites de
diárias, arquivos originais, pacotes e versões. CSS específico antigo removido
após migrar seu último consumidor no UI Lab; componentes compartilhados mantidos.

Referência funcional é o levantamento documentado anterior, não uma nova auditoria
da referência. Lacunas históricas não foram implementadas nem simuladas. Evidências
da rodada, crítica e validação em `docs/visual-agents/qa/prestacao-refino-2026-10-15.md`.

## Organizada como a gestão de viagens — 16/10/2026 (ADR 0041)

- Lista: uma linha por equipe, como a das viagens — placa do ofício, destinos, "N de M
  finalizadas", enviadas/devolvidas, o selo mais urgente (saque ou prestação), período,
  unidade, "Prestar até", as pendências com o atalho de cada uma, servidores e diárias; o ⋮
  leva à prestação, às três folhas e ao resumo do ofício. Abas, "pedem atenção", busca,
  paginação por 25 equipes e exportação sem mudança.
- Folha da equipe (`/viagens/prestacoes/equipe/<pk>/`): etapas Solicitações → Diário →
  Relatório → Documentos → Finalização → Envio (a primeira que falta é a atual); 1
  Servidores com os cartões de sempre (autosave, finalizar com justificativa, arquivar,
  registrar envio, aprovar, devolver); 2 Diário, relatório e documentos, cada um com a
  situação e o que tem; 3 Conferência por servidor, cada pendência levando aonde se resolve.
  Barra: Voltar, Finalizar equipe (ou Registrar envio da equipe) e Ações (resumo do ofício,
  pacotes ZIP, planilha, reabrir, arquivar, desarquivar). Consulta vê tudo sem edição.
- Diário, RT e documentos: abas Equipe · Diário · Relatório · Documentos; Voltar e
  Finalizar voltam à folha da equipe; migalhas passam pelo ofício.
- Preservados: ids `ps-{pk}`, `form-ps-{pk}`, `equipe-{pk}`, `envio-{pk}[-equipe]`, nomes
  dos campos, regiões `data-vivo`, `data-esperar-salvamento`, regras e documentos oficiais.

## No padrão do sistema modelo, com as peças das folhas — 16/10/2026 (ADR 0042)

### Revisão visual do diário — ADR 0043

O diário mantém paridade funcional (hodômetro, abastecimento, sugestão pelas
distâncias, motorista/viatura, horários realizados, conferência e editor).
A apresentação deixa a tabela de sete colunas e passa a usar linhas responsivas
existentes, recursos lado a lado e ajuste excepcional de horários em divulgação.
O editor e os documentos oficiais não mudaram. Não se declara nova comparação
com o sistema de referência: a base é o contrato já registrado nesta matriz.
Evidências e resultados: `../qa/diario-refino-20261016.md`.

### Base anterior preservada

Revisão posterior por solicitação expressa: o Diário agora segue diretamente o
cadastro do Ofício (`documento--preparacao`): recursos abertos, roteiro/quilometragem
e documento em três seções numeradas. Substitui os cartões e etapas descritos na
revisão anterior. Editor e contratos preservados; evidências da implementação e
validação em `../qa/diario-base-oficio-20261016.md`.

- Lista: a linha operacional da lista de ofícios por ofício e, colada, uma linha de registro
  por servidor com o nº da solicitação e o prazo de saque gravando sozinhos na própria lista
  (como a lista real do sistema modelo), o que já foi feito (diário, relatório, comprovante,
  despacho), situação, prazos, pendências (pílula das listas) e as ações; as da equipe no ⋮
  do ofício. Atalhos de pendência: sem solicitação, sem despacho, sem comprovante, valor ≠
  diária, finalizadas no mês. Preservados: abas, busca HTMX, 25 ofícios por página,
  exportação, `ps-{pk}`, `form-ps-{pk}`, `equipe-{pk}`, `envio-{pk}[-equipe]`, nomes dos
  campos (`numero`, `liberacao`, `prazo`, `justificativa`), regiões `data-vivo`.
- Folhas com o `registro_hero`, a barra `etapas-progresso` (1 Diário → 2 RT → 3 Documentos →
  4 Leitura), os cartões `secao` e a barra do rodapé do termo/OS; o servidor da folha no
  cabeçalho (`?servidor=`); "Salvar e continuar" espera o autosave. O diário e os RTs saem no
  mesmo editor do ofício (texto por região com versões, EdicaoPrestacao) e o PDF/DOCX/pacote
  levam o texto editado. Leitura e conferência (nova): transcrição com "Copiar", nº de
  autorização/data/valor do comprovante conferidos com a diária do ofício e a do RT assinado.
- Documentos iguais aos do sistema modelo: diário de bordo em A4 deitado (doze colunas,
  motorista na tabela) e RT na folha ASCOM (tabelas, declaração, assinatura com CPF).
- Não regrediu: motorista/viatura (3 modos), viagem realizada, conferência do hodômetro,
  textos prontos, sugerir e copiar RT, limite da diária, carimbo do nº da solicitação,
  versões anteriores, pacotes, envio/aprovação/devolução, consulta sem edição, planilha.
