# Propagação da identidade vigente — 10/10/2026

Fonte: pedido explícito do usuário e cinco capturas anexadas em 10/10/2026.
Ofícios atuais substituem referências estéticas anteriores conflitantes.
Interface clara, navegação superior, grafite, dourado discreto, tipografia legível,
filtros integrados, conteúdo independente de painéis laterais e poucas superfícies.
Lista, formulário e consulta compartilham linguagem, sem impor a mesma composição.
Regras, permissões, dados, auditoria e conteúdo oficial dos documentos permanecem.
Uma página/conjunto diretamente relacionado em implementação; revisão visual do
usuário é distinta da conclusão técnica. Não resetar banco/mídia para capturas.

## Primeiro conjunto: Roteiros

- Objetivo: preparar percurso reutilizável e estimativa de diárias, depois copiar
  para Ofícios. Contrato funcional: ADR 0015, `migration/roteiros.md`,
  `product/modules.md`, `product/permissions.md`, `views_roteiros.py` e seus testes.
- Rotas: `/viagens/roteiros/`, `/novo/`, `/<id>/editar/`; não há detalhe/documento
  oficial próprio. Edição contém os Ofícios vinculados e suas ações existentes.
- Lista: busca por sede, destinos, observações/número; abas temporais, cancelados
  e contas prestadas; ordenação atual por primeira saída/criação; paginação.
- Campos editáveis: sede, destinos ordenados, bate-volta, saída, duração/adicional
  e chegada calculada. Mapa e totais preservados. O formulário atual tem
  `FormularioRoteiro.Meta.fields=[]`: efetivo/observações persistidos aparecem na
  consulta, mas não são editados na folha. A ficha histórica descrevia esses campos
  como editáveis; esta missão não adiciona controles ou altera a estimativa vigente.
- Ações: salvar, autosave, cancelar/reativar, excluir se não utilizado, criar
  Ofício, consultar Ofícios vinculados. Formulários e confirmações preservados.
- Permissões: visibilidade por unidade; criação/edição/exclusão conforme políticas;
  roteiro cancelado não editável. Nenhuma autorização nova.
- Salvamento: autosave cria na primeira gravação; salvar manual retorna à lista.
  Validação de sequência e diárias compartilhada com Ofícios; sem novas regras.
- Migração visual: arquétipo de lista com `registro_hero`, coleção de consulta,
  placa/identidade documental, registros operacionais, filtros horizontais e barra
  proporcional aos resultados. Folha reutiliza itinerário operacional, painel de
  rota, trechos e Diárias existentes, além de header e ações canônicos.
- Legado: ficha de migração existente contém leitura de `viagens_roteiros` e da
  documentação de paridade. Inconsistências históricas sobre Finalizados devem ser
  resolvidas pelo código/teste atual; não criar recurso durante esta rodada.

## Limpeza

Somente consumidores substituídos e verificados podem ser removidos. Estilos de
outras listas/formulários continuam até migração comprovada; nenhum reset ou mídia
removida. Compatibilidade é registrada na matriz da missão.

## Próximo conjunto: Termos de Autorização (contrato observado)

- Objetivo: preparar autorizações por servidor, genérica e de viatura; vinculadas
  a um ou mais Ofícios compatíveis, ou avulsas. Lista e folha concentram detalhe,
  documentos e ações. Fontes: `views_termos.py`, `FormularioTermo`, políticas,
  `migration/termos.md`, testes de Termos e paridade legada de lista/form/documentos
  em `Solicitações de eventos/docs/paridade/termos-*.md` (somente leitura).
- Rotas: `/viagens/termos/`, `/novo/`, `/<pk>/`; busca por destino, número de
  Ofício, protocolo, servidor, placa/modelo/evento. Filtro por Ofício, abas temporais,
  Finalizados e Cancelados. Ordem por criação descendente, paginação existente.
- Campos: Ofícios vinculados; evento; período único; destinos ordenados com UF,
  sede institucional fixa; servidores; viatura. Herança e união dos Ofícios são
  regras existentes; apenas registros da mesma viagem/roteiro podem ser associados.
- Validação: sequência de datas, destinos/UF, compatibilidade dos Ofícios,
  unidade e permissões. Não modificar regras nem tornar campos novos obrigatórios.
- Salvamento: GET de novo apenas mostra o formulário; o botão Novo envia POST
  `acao=criar`, cria rascunho e abre a folha. Termo existente usa autosave/versionamento;
  erros/conflitos não anunciam sucesso. Finalizar aguarda gravação e retorna à lista.
- Permissões: leitura por unidade; documentos com dados pessoais somente para
  perfis permitidos; cancelado bloqueia edição/geração. Preservar fieldset disabled,
  políticas das rotas, CSRF e diálogos de confirmação.
- Documentos: página por servidor, genérica e de viatura; editor, Texto/PDF,
  PDF único, ZIP DOCX, seleção de downloads, assinados, versões e histórico.
  Nenhuma mudança de texto, margem ou paginação oficial.
- Componentes a substituir: cabeçalho/placa anteriores por `registro_hero` e
  identidade canônica; registros e barra da lista por coleção operacional;
  folha de cartões por preparação; mapa anterior por variante explícita do painel
  compartilhado; editor/histórico por variantes operacionais existentes.
- Compatibilidade: manter IDs `frase-termo`, `conferencia`, `estado-destinos`,
  `barra-pendencias`, formulário, `data-vivo`, `data-editores`, páginas/vias e
  endpoints. Não aplicar uma substituição global aos demais consumidores de destinos.

## Ordens de Serviço — contrato observado antes da migração

- Objetivo: determinar deslocamento e necessidade, com numeração anual própria e
  documento único. Rotas `/viagens/ordens/`, `/nova/`, `/<pk>/`. A edição também
  oferece detalhe, documento e histórico; não há modal de resumo separado.
- Lista: número/ano, destinos, período, equipe, tipos, Ofícios e assinatura;
  busca por número, destino, servidor, motivo/Ofício; filtro por Ofício; abas
  temporais, contas prestadas e canceladas; ordenação ano/número, paginação.
- Campos: Ofícios compatíveis, tipo, período, destinos/UF, servidores, funções
  individuais nos tipos caminhão/micro-ônibus/cerimonial, motivo/texto pronto e
  assinante. Vínculo novo preenche apenas campos vazios; não recriar dados apagados.
- Validação/salvamento: datas e unidade, funções por servidor, versão/autosave,
  recarga quando muda o conjunto de funções. **Pendências são avisos**; gerar e
  finalizar não recebem o bloqueio de emissão de Ofícios. Finalizar espera salvar.
- Permissões: consulta/edição/documento/cancelamento/exclusão nas políticas atuais.
  Excluir somente antes da primeira geração; cancelar mantém o número reservado.
- Documentos: único editor, Texto/PDF/DOCX, versões, via assinada, downloads e
  histórico. Prévia `?previa=1` não fixa data nem geração; geração efetiva fixa.
  Não alterar texto oficial, margens ou paginação para adaptar o visualizador.
- Migração: hero/identidade, registro operacional de relações sem coluna financeira,
  preparação, destinos/mapa operacionais, equipe compacta, editor/histórico/barra
  no fluxo. Manter `frase-ordem`, `conferencia`, `estado-destinos`, `estado-motivo`,
  `barra-pendencias`, `data-vivo`, `data-esperar-salvamento`, IDs/URLs/páginas da OS.
- Fontes: `migration/ordens.md`, `views_ordens.py`, `FormularioOrdem`, `ordens.py`,
  testes; referência `viagens_ordens/{forms,views,abas}.py` somente leitura.
- Lacunas funcionais preexistentes: número manual e aviso de conflito de agenda
  do legado. Não implementados nesta missão visual. Assinados e contas prestadas
  já existem; a ficha histórica não deve continuar marcando-os como ausentes.
# Próxima unidade: Lista de Planos (10/10/2026)

Objetivo: localizar planos, comparar destinos/programas, coordenação, efetivo e
diárias e acessar ações por permissão. Rota `/viagens/planos/`, busca `q`, abas
`aba`, filtro de Ofício e ordenação `ordem`: número/período ascendente ou descendente.
Agrupamentos ano/mês preservados; paginação e OOB mantêm filtros e foco.

Preservar IDs filtros-planos/busca-planos/ordem-planos/resultados/abas-filtro,
querystrings, menus Abrir/PDF/DOCX/cancelar/reativar/excluir, confirmações e criação
avulsa ou do Ofício. Lista não salva nem gera automaticamente. Pendências do Plano
bloqueiam finalização/geração; não aplicar o comportamento permissivo de OS.
Diárias e efetivo da lista são totais por evento, não equipe única. Número/sufixo,
programas, coordenador, período, vínculos e estado não podem desaparecer.

Substituir header/lista/placa/filtro/barra antigos pelas variantes canônicas de
coleção, registro operacional, identidade documental, agenda/recursos/valor e
ações no fluxo. Sem CSS/JS novo inicialmente. Folha, evento e Resultados serão
unidades seguintes; preservar suas classes até migrar consumidores e validar.
Lacuna anterior: número manual do legado. Não criar essa regra nesta missão.

Lista de Planos: links de paginação devem preservar busca, aba, ordenação e Ofício,
como as outras listas. Falha antiga reproduzida e corrigida nesta página; sem regra
nova de negócio ou alteração da numeração. Identificação e complemento editorial
do hero têm contextos separados; sufixo documental é explícito.


## Planos — Folha e eventos adicionais

Contrato atual: /viagens/planos/novo/, /<id>/ e ?evento=novo/id. Preparação com
Ofícios, programas múltiplos/Outro, período/horário, destinos, coordenadores
cadastrados ou manuais e tratamento explícito; efetivo por cargo/unidade/quantidade,
saída/chegada, cálculo do evento principal, atividades/metas/recursos. Identificação
mantém as âncoras de validação. Eventos adicionais possuem próprio efetivo,
deslocamento, atividades e diárias; totais gerais somam eventos (ADR 0047).
Formulário do evento fora do principal, salvamento manual e prefixos únicos.
Não substituir quantitativos por nomes de servidores nem criar composição geral
única de diárias. Autosave, versão/conflito, data-vivo e espera antes de finalizar
permanecem. Geração bloqueada pelas pendências existentes, prévia não gera nem
fixa data. Permissões, cancelamento, downloads PDF/DOCX e documento oficial intactos.

Composição: hero de preparação, superfície única e divisores; agenda proporcional,
destinos/mapa operacional, coordenação compacta com campos condicionais, efetivo
existente com saída/chegada próximas, conferência financeira serena do evento,
conferência documental com links das pendências, editor e histórico canônicos.
Âncora #conferencia será restaurada: views já redirecionam para ela, mas o template
anterior não a contém. Nenhuma regra institucional será criada. Resultados têm
salvamento próprio e serão tratados na unidade seguinte.

Planos: fechar/cancelar evento após erro POST422 deve retornar à Folha, nunca fazer
GET na rota de salvar evento. Defeito anterior de URL relativa corrigido, sem regra nova.


## Planos — Resultados, unidade seguinte

Objetivo: lançar quantitativos por atividade após a ação e consultar relatório final.
Rota /viagens/planos/<id>/resultados/. Sem busca/filtro/paginação ou geração própria.
Atividades previstas são união dos eventos; resultados de atividades retiradas
continuam visíveis como fora do plano. Ordenação existente preservada. Campos
realizado_<atividade> e observacao_<atividade>, salvo por POST manual/Ctrl+S, sem
autosave. Inteiro não negativo, zero válido, ponto como milhar, vazio sem observação
apaga o registro. Observação até500 caracteres; erro422 preserva digitado e não
salva parcialmente. Consultas por mesma unidade/permissão; cancelado bloqueia escrita.
Relatório mostra dados SALVOS, não calcula instantaneamente o digitado. Sugestão para
Relatório Técnico já implementada; não descrevê-la como recurso futuro nem alterar
seu texto oficial. Sem alteração de documento, auditoria ou cálculos nesta página.

Composição: hero/identificação com sufixo, superfície contínua de preparação, tabela
de lançamentos proporcional no desktop e registros com rótulos explícitos no celular/
tablet. Quantidade compacta, observação com largura útil, meta secundária sem ocultá-la.
Relatório de leitura em largura confortável, sem cartão extra. Ação no fluxo e
feedback verdadeiro de salvamento MANUAL. Estados vazio, erro e consulta preservados.
Código exclusivo antigo só será removido após testar a substituição e consumidores.


## Justificativas — lista, diálogo e downloads

Rota /viagens/justificativas/, Todas/Pendentes/Preenchidas; abre em pendentes quando
existirem. Busca por dados do Ofício/texto, paginação20; pendentes por saída próxima,
demais por número. Lista exclui cancelados/arquivados, mesma unidade/view_oficio.
Grava texto no Ofício rascunho editável, change_oficio, CSRF e versão; sem autosave.
Texto até4000, texto pronto; apagar exige intenção explícita no menu. Erro/conflito422
preserva digitado. Emitidos/consulta não editam diretamente; PDF corrente permitido
quando disponível. Baixar existente usa justificativa antes do Ofício, formatos/vias
já vigentes; documento histórico nunca corrente. Nenhuma entidade/regra nova.

Composição: hero proporcional, abas horizontais, busca integrada, registros canônicos
com número/destino, estado da justificativa separado de situação documental, período,
data/antecedência institucional e trecho do texto. Diálogo existente com metadados e
campos proporcionais; ação manual clara. Não criar folha/editor próprios.
Defeito anterior identificado: após422 links relativos apontam para /salvar/ (GET405)
e contexto voltar não é recuperado. Corrigir rota explícita e manter busca/aba no
erro/retorno, com testes; não alterar regra de prazo nem permissão.


## Viagens — Lista, unidade seguinte

Rota /viagens/viagens/. Hub dos documentos, sem número oficial: placa é data de início
ou ID local. Título vem dos tipos; destinos, período, situação, indicador temporal,
unidade e contagens Ofícios/OS/Planos. Abas Todas/Futuras/Atuais/Prestadas/Canceladas,
exclusivas; sem data entra em futuras; prestadas saem de futuras/atuais. Busca por
título/motivo/destino/servidor/placa/número-ano de Ofício, não protocolo.20por página;
futuras por início, demais por criação. Mesma unidade/permissão view_viagem;
Nova viagem depende add_viagem/lotação, POST/CSRF, reaproveita rascunho vazio pela regra.
Lista somente abre Folha: não inventar menu, exportação ou downloads nesta migração.
GET de lista não grava. Preservar IDs/HTMX/OOB/querystring e botão POST separado da busca.

Composição: hero compacto, filtros temporais integrados, busca, registros de relações
sem coluna de ação fictícia. Título e destino legíveis; situação documental e tempo
separados; documentos agrupados como metadados. Barra dentro do fragmento, no fluxo
com poucos registros e acompanhando apenas quando paginada. Sem grandes alturas.
Legado tem filtros combináveis,25por página, busca por protocolo e ações de linha;
lacunas/diferenças já levantadas ficam explícitas, não são ampliadas por uma missão visual.


## Viagens — Folha e geração em lote

Rotas /viagens/viagens/<pk>/ e /<pk>/gerar-documentos/. Folha agrupa identificação,
tipos→título, período/destinos/motivo/descrição, vínculos atuais+40 livres por tipo,
conferência em nove etapas/coerência, cinco grupos documentais e histórico. Consulta
ou cancelada são leitura sem formulário. Preservar permissões distintas para editar,
repetir, cancelar/reativar/excluir. Sem regra nova de emissão: prontidão da Viagem
não significa emitir um documento. Cada Novo conserva semeadura, vínculo e bloqueio
sem período/destino para OS/Plano/Termo. Coerência protege via assinada.

Autosave protegido por versão; salvar manual existente no contrato HTTP. Manter
#form-viagem/data-autosave/data-proteger, hidden versao/vinculos_presentes/conhecidos;
conhecidos protege vínculo criado após abertura. Regiões data-vivo frase-viagem,
estado-dados, nota-dados, conferencia, documentos devem manter IDs e não englobar
os campos editáveis. Âncoras dados/periodo/destinos/motivo/vinculos/conferencia/
coerencia/documentos/historico, forms externos e diálogos preservados.

Lote manual POST/CSRF/data-proteger, quantidade/acao adicionar-remover-gerar e
#oficio-N/equipe_N/motorista_N/viatura_N/data-equipe preservados. Adicionar/remover
não gera; limite 20, duplicações/servidor já vinculado validados. Motorista de fora
entra na equipe. Termos excluem unidade emissora; OS/Plano existentes não substituídos.
Tudo nasce em rascunho, sem protocolo/emissão automática. Não alterar mídia/documento.

Composição: hero canônico data/ID, preparação por seções, tipo/período proporcional,
destinos operacionais, vínculos legíveis recolhíveis, conferência própria compacta,
registros de documento sem recursos artificiais, histórico operacional e barra com
feedback verdadeiro de autosave. Lote com equipe compacta/viatura-cartão existentes.
Nenhum editor próprio ou novo módulo de negócio. Limpeza apenas após consumidores
migrados e provas; bases genéricas ainda necessárias em Prestação ficam preservadas.

## Prestação de Contas — Lista operacional

Rota /viagens/prestacoes/. Um grupo por Ofício e formulário por servidor;25Ofícios
por página, contadores por servidor. Busca servidor/solicitação/protocolo/OfícioN/ano.
Abas de situação e atenção aceitam múltiplos valores por OU via URL; preservar
querystring na busca, paginação, exportação e ações. Sem criação manual de prestação.
Visibilidade por unidade/Ofício emitido/equipe atual; consulta sem campos editáveis.
Permissões/arquivamento/finalização/envio/aprovação/devolução continuam nos serviços.

Preservar IDs abas-filtro/atalhos-atencao/busca-prestacoes/resultados/titulo-resultados;
ps-ID/form-ps-ID e regiões estado/nota/acoes/pend-ps-ID[data-vivo]. Cada cartão conserva
numero/liberacao/prazo/justificativa/CSRF/voltar/formaction/data-autosave; Enter salva
sem finalizar. Ações de equipe usam forms externos e data-esperar-salvamento. Envio
é registro interno por diálogo existente, sem nova integração. Exportação respeita
o recorte. Links para Ofício/Diário/RT/Documentos preservados; estas últimas páginas
ficam em unidades posteriores. GET da Lista não inicializa Diário/RT nem grava dados.

Composição: hero e coleção de consulta, filtros integrados com dimensões distintas,
identidade do Ofício/destinos/metadados e ações agrupadas, linhas de servidores com
campos proporcionais e estados legíveis, pendências próximas e rodapé no fluxo em
lista curta. Não converter uma lista editável em registros apenas de consulta nem
esconder ações para reduzir altura. Reutilizar a apresentação institucional atual.
CSS de equipe/servidor também atende Anexos/UI Lab: migrar consumidores de modo
explícito ou usar variante legítima; não apagar bases com uso comprovado.

## Reabertura de Roteiros — conferência de Diárias (12/10/2026)

A conferência operacional tem um único contrato responsivo: total em destaque;
por servidor e tipo de destino em duas colunas abaixo de1024px, composição na
linha seguinte; a partir de1024px, total ao lado dos três metadados. A variante
antiga `horizontal` não é um conceito diferente: todos os seus consumidores
já pedem `operacional`. Sua cascata posterior gera uma coluna em360 e quatro
em768, com altura e espaços artificiais. Migrar os dois includes do corpo de
Diárias, retirar a variante e suas regras, preservando consulta vertical e o
cálculo. Consumidores reais: Folha de Roteiros, Ofícios e Planos, incluindo
fragmentos de prévia; o Resumo usa `consulta` e deve ser conferido por regressão.
Prova anterior: `migracao-identidade-20261012/antes-diarias-geometria.json` e15
capturas nas cinco larguras. Nenhuma regra financeira ou conteúdo oficial muda.
