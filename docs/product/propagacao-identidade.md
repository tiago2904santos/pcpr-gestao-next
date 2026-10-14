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

Justificativas — refinamento de12/10: a barra de contagem e nota informativa
permanece no fluxo mesmo com paginação. Não contém ação que justifique acompanhar
a rolagem. Preservar contagem, paginação, filtros e HTMX; variante sticky permanece
disponível para consumidores com ações, sem mudança global de comportamento.

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

Refinamento de 12/10: controles de origem e tratamento da coordenação precisam
mostrar rótulos e escolha atual completos no celular. A variante compartilhada
campos--coordenacao passa a uma coluna abaixo de768px, duas no tablet e mantém
a distribuição proporcional desktop. Consumidores atuais: coordenação
administrativa e operacional da Folha/Novo Plano. Campos condicionais e regras
de tratamento documental permanecem iguais.

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
com poucos registros e acompanhando apenas quando paginada e com ação de criação.
Na consulta sem permissão de criar, permanece no fluxo e a contagem continua visível
inclusive no celular; não usar o status de salvamento que se oculta nessa largura.
Sem grandes alturas.
Legado tem filtros combináveis,25por página, busca por protocolo e ações de linha;
lacunas/diferenças já levantadas ficam explícitas, não são ampliadas por uma missão visual.


## Viagens — Folha e geração em lote

Refinamento de leitura (12/10): consulta e cancelada apresentam Tipo, Período
e Destinos como metadados canônicos do Resumo, com rótulo discreto e valor íntegro.
Sem formulário desabilitado, novo dado ou alteração de permissão. Tipo e destinos
longos devem quebrar naturalmente sem truncamento; motivo mantém leitura textual.
Na conferência, cada divergência é uma frase contínua com link e valores atual e
esperado; a composição não pode distribuir cada fragmento como coluna independente.
Preservar a ação de aplicar coerência e a indicação de correção no documento.

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

Na janela de resumo da Viagem, o bloco Registro mostra somente período, tipos e motivo:
unidade e situação já aparecem no contexto da lista e do cabeçalho e não devem ser
repetidas. Quando a conferência não tem pendências, “Tudo pronto” é uma confirmação
neutra, sem contorno nem filete lateral; pendências continuam usando o destaque de aviso.
No desktop, a janela acompanha a altura do conteúdo até o limite da tela; somente o que
ultrapassar esse limite ganha rolagem, sem reservar uma altura vazia. Depois de Destinos,
mostrar “Equipe da ordem de serviço” com os servidores das OS vinculadas à Viagem,
sem repetir quem participa de mais de uma OS. Documentos da viagem permanece em seguida.

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

## PR02 — Diário de Bordo

Rota `/viagens/prestacoes/equipe/<pk>/diario/`. Fonte funcional: ficha de Prestação,
serviços `diario` e `realizado`. Diário compartilhado; trava com toda a equipe
finalizada. Motorista e viatura possuem três modos cada, válidos somente no Diário.
Viagem realizada permite editar saída **e chegada**, recalcular e desfazer sem
alterar o Ofício emitido. Hodômetro e abastecimento têm autosave; km final menor
que inicial impede gravação, demais divergências são avisos. PDF/XLSX permanecem
com conteúdo e regras atuais. Finalizar aguarda salvamentos e volta à Lista,
sem finalizar a prestação. Consulta mantém leitura e downloads disponíveis.

Preservar formulários separados, nomes dos campos, `#form-diario`, os IDs por linha,
`data-vivo` em frase/estado/conferência, `data-modo`, confirmação ao desfazer e
`data-esperar-salvamento`. GET editável pode criar/sincronizar linhas: capturas apenas
de registros existentes cuja sequência de chaves/ordem foi conferida, com snapshot
antes/depois de Diário e linhas; nenhum seed/reset. Cenários DEMO211/190/201/199.

Composição: hero documental canônico, seções contínuas de preparação, modos de
motorista/viatura agrupados, linha de percurso com campos curtos proporcionais,
conferência por metadados e feedback de salvamento visível. A linha do Diário é um
componente operacional existente, também no UI Lab §15: melhorar sua origem em
vez de criar cópia por página. A chegada realizada não é resultado calculado.
Não remover `.modos` ou antigas bases globais ainda consumidas pelo Relatório.
## Contrato PR03 — Relatório Técnico, 12/10/2026

Rota `/viagens/prestacoes/equipe/<pk>/relatorio/`. Folha de relato da equipe,
cinco campos de texto, custeio com opções/Outro, diária recebida por servidor
e downloads PDF/DOCX por integrante. Base funcional: módulo9c em
`docs/migration/prestacao.md`, serviços `relatorio.py` e domínio correspondente.

Edição exige permissão e Ofício emitido; trava quando toda equipe ativa está
finalizada. Servidor individual finalizado conserva diária somente leitura.
`ativos()` exclui removidos, não arquivados. Valor recebido não pode superar
o liberado; erro financeiro não descarta textos válidos. Descrição, objetivo
e conclusão compõem a pendência. Sugestões vêm de Ofício/Viagem/Plano; textos
prontos, cópia, marcadores e guardar modelo preservam comportamento existente.

GET editável/download pode criar RT inexistente. Capturas usarão RTs existentes,
POST bloqueado e hash antes/depois de RT e prestações individuais. Não acionar
Sugerir/Copiar na base DEMO: essas ações disparam autosave. Testar em banco isolado.

Composição: hero documental e seções contínuas; relato com ferramentas junto
ao campo pertinente; custeio em modos proporcionais; diárias com nome separado
do rótulo curto do valor; documentos por servidor; status real de salvamento
e barra no fluxo. Reutilizar componentes atuais, sem novo editor/versão fictícia.

Preservar `form-rt`, `frase-rt data-vivo`, `rt-<campo>`, `ps-<pk>-diaria`,
`rts-para-copiar`, data-prefixo/alvo/form/sugerir/texto-pronto/guardar-texto,
diálogo e `finalizar-relatorio data-esperar-salvamento`. Finalizar só volta à
Lista filtrada. Documentos e diálogo continuam fora do formulário.

Limpeza candidata: `grade-campos` após verificar todos os consumidores e migrar
diárias individuais. Bases `modos`, `texto-pronto`, `registro`, `cartoes` e
`frase-oficio` continuam compartilhadas. Lacunas históricas de modelos repetidos
e política de cópia por unidade não serão alteradas pela migração visual.
# Contrato PR04 — Documentos da prestação, 12/10/2026

Página `/viagens/prestacoes/equipe/<pk>/documentos/`, templates de Anexos.
Via assinada do Ofício, despachos, Diário assinado, comprovantes/RT por servidor
e versões anteriores compõem um único fluxo. Referência funcional: ficha9d em
`docs/migration/prestacao.md`, views_anexos/anexos/carimbo/pacote_prestacao.

Preservar forms separados e CSRF, multipart, arquivo/tipo/servidor,
valor/data_operacao/operacao, pagina/x/y e todos os IDs/retornos com âncora.
Despacho/comprovante acumulam; Diário/RT substituem a versão vigente. Remoção
lógica recuperável em30dias; PDF/PNG/JPG até10MB conferidos por conteúdo.
Valor/data/operação opcionais, divergência pela soma. Trava de equipe ou pessoa
finalizada permanece no serviço. Carimbo não altera a via original.

A Folha não possui autosave nem escrita no GET. Pacote PDF/ZIP pode criar
RT/Diário ou sincronizar linhas por fallback: somente testar em banco/mídia
isolados, nunca acionar no DEMO para uma captura. Captura da Folha permite
leitura dos anexos existentes, sem enviar forms nem substituir mídia.

Direção: hero documental, seções contínuas, peças documentais com ações e
formulários proporcionais de envio/correção/carimbo. Sem estado falso de autosave.
Revisar anexo-campos nos três consumidores antes de qualquer remoção. Bases
prestacao-equipe/servidor/registro são compartilhadas e continuam necessárias.
Lacunas OCR, carimbo arrastável/automático, revisão de pacote e purga física
continuam funcionais e fora da migração visual; não serão simuladas.

## Contrato AS01 — Via assinada, 12/10/2026

Fallback `/viagens/assinados/<tipo>/<pk>/` e variante com chave de Termo.
Ofício, Justificativa, Termo e OS usam o mesmo template. GET exige permissão
de anexar; não converter acesso negado em formulário readonly. POST nativo,
multipart/CSRF, arquivo e voltar preservados; funciona sem JavaScript.
PDF até15MB validado por extensão/conteúdo, troca mantém histórico. Erro422
retorna à página com mensagem associada ao campo; retorno externo é rejeitado.
Não declarar verificação criptográfica de assinatura. Não alterar PDF gerado.

Antes capturado com Ofício159/2026 (pk258), sem POST nem abertura de PDF gerado.
Migrar cabeçalho, seção e barra para padrões canônicos; separar orientação de
arquivo e consulta às duas versões. IDs/names/rotas e selos permanecem.
Bases documento--cartoes/barra-acoes possuem outros consumidores: removê-las
desta página não autoriza exclusão global. Testar anexação/troca/erro sem JS.

## Contrato VG01 — Painel de Viagens, 12/10/2026

GET /viagens/, leitura de ofícios visíveis ao usuário. Quatro indicadores com
semântica preservada: mês, rascunhos, saídas30dias e diárias emitidas. Filas de
até5rascunhos e5próximas viagens mantêm ordem/recorte atuais. Links filtrados,
menus, resumo, assinatura/baixar e permissões permanecem. Referência funcional
docs/product/modules.md e legacy-lessons.md (painel é melhoria do sistema novo).
Antes360/768/1440 expõe registros quebrados: falta classe registros--operacionais
que ativa o grid/placa do componente compartilhado. Não é nova regra de negócio.
Usar hero e grid canônicos, filas com largura útil e atalhos de contexto fora
da coluna que comprime registros. Arquétipo continua fonte da estrutura.

## TE01 → TE03 — atalho de via assinada, 12/10/2026

O menu da Lista deve abrir a estação documental do Termo, mantendo geração,
versões, anexação e permissões. O href atual usa #lista-documentos, inexistente
na folha migrada. O alvo real é #previa. Corrigir a navegação sem alterar documento
oficial ou fluxo de anexação. Testar partindo do menu, incluindo celular, em vez
de entrar diretamente na URL da prévia; validar upload real em banco/mídia de teste.

## Editor de folha inteira — conteúdo largo no celular, 12/10/2026

Termos, Ofícios, Ordens e Planos usam a mesma variante de altura automática.
O visualizador deve permitir alcançar linhas indivisíveis por rolagem horizontal,
sem reduzir a fonte ou modificar HTML, margens e paginação do documento oficial.
A página externa continua responsável pela rolagem vertical. A altura acompanha
o conteúdo e reserva a barra horizontal quando presente, sem crescimento cíclico.
Validar leitura até o fim da linha, teclado, seleção, redimensionamento e edição.

## CD01 — Índice de Cadastros, 12/10/2026

Entrada de navegação sem gravação: três grupos condicionais (principais, plano,
configuração/textos), links e contadores fornecidos por views_crud.indice.
Permissões permanecem em policies; ausência total de acesso retorna403. Sem filtros,
documentos ou salvamento nesta página. Preservar atalhos de incompletos e quantidades.
Migrar cabeçalho para registro_hero compacto e distribuir grupos na grade canônica
de duas colunas, uma no celular. Extrair repetição de registros para lista_catalogo,
mantendo ícones, descrição, links e metadados opcionais. Sem CSS/JS novo ou mudança
das consultas. Capturas antes/depois com mesmos dados; teclado, axe, permissões e
navegação são o contrato de validação. Não eliminar estilos ainda usados em outras páginas.

## CD02 — Servidores, lista e diálogos

Busca por nome/cargo/unidade/CPF/RG, abas ativos/incompletos/inativos, filtro cargo,
paginação, edição, ativação e exclusão condicionadas pelas permissões/vínculos.
Só nome obrigatório; CPF/RG/telefone com máscara; cargo/unidade com cadastro rápido.
Salvar mantém retorno/filtros. Sem autosave ou documento próprio neste cadastro.
Preservar dados, contadores, mensagens e POSTs. Contrato já explicado em test_crud.py
e test_cadastros.py a partir da referência funcional.
Aplicar hero compacto e filtros canônicos; manter registro denso. No diálogo compartilhado,
substituir campos--iguais por grade responsiva: campos completos no celular, duas/três
colunas em telas maiores. Antes360 comprova corte de CPF/cargo. Consumidores diretos:
Servidores e dialogos_cadastro (Termos, OS, lote de Viagens e carregamentos dinâmicos).
Validar criação, edição, máscaras, atalhos, erro, teclado e consumidores afetados.

## CD03 — Viaturas

Preservar busca por placa/modelo/unidade/motorista, filtro combustível, abas,
paginação, permissões, ativação e exclusão condicionada. Só placa obrigatória;
tipo/combustível iniciais e motoristas habituais mantidos. Diálogo compartilhado
com Termos/OS/lote e Ofícios sob demanda. Sem mudança de contrato de salvamento.
Cabeçalho compacto canônico; campos em duas colunas no desktop e uma no celular
para eliminar truncamento de Tipo/Combustível, mantendo cadastro auxiliar e busca
de motoristas. Não aplicar filtros--barra, pois reordena filtro simples no mobile.
Contrato funcional sustentado por test_crud.py/TestViatura e test_cadastros.py.

## CD04 — Tabela de diárias

Consulta de vigências por faixa, mais recentes primeiro; valores de 15% e 30%
derivados de 24 horas, arredondados ao centavo. Vigente é a última data já iniciada
de cada faixa. Apenas gestor cria/altera/exclui; última vigência não pode ser
excluída. Nova vigência preserva anteriores e documentos emitidos. Contratos:
entities.md, permissions.md, TestDiarias e test_gestor_cadastra_vigencia_com_previa.
Preservar tabela comparativa, estados vazio/erro, confirmação, norma e formulário
sem autosave. Reutilizar hero compacto, tabela responsiva, menus e diálogo.
Trocar somente a distribuição Faixa/Data por grade--2: uma coluna no celular,
eliminando quebra excessiva da ajuda e corte da data. Nenhuma alteração financeira.

## CD05 — Configuração institucional da unidade

Contrato de docs/migration/cadastros.md, TestConfiguracao/TestAssinantes e
views_crud._tela_configuracao. Gestor configura unidades permitidas; demais perfis
autorizados consultam campos desabilitados da própria lotação. Sem unidade e sem
configuração são estados distintos. POST manual, sem autosave; erros preservam
campos. Assinantes por tipo, chefia de fallback, endereço/rodapé, destinatário e
prazo permanecem integrais. Substituições têm formulário separado e alternam
encerrada/ativa; documentos anteriores não mudam. Sem integração nova de CEP.

Migrar cabeçalho e seções para folha de preparação, evitando cartões encaixados.
Preservar os IDs e agrupamentos funcionais; ampliar campos longos e datas móveis.
Barra final no fluxo da configuração, separada das ações de substituição. Revisar
todos os seletores e o diálogo, inclusive Escape primeiro na busca e depois no modal.
# CD06 — Textos prontos: contrato da migração

Rota /cadastros/textos-prontos/. Abas Motivos/Justificativas/Trechos, busca por
nome/conteúdo, ativos/inativos e padrão são preservados. Novo/editar usa diálogo
com nome, tipo e texto; salvamento POST manual, sem autosave. Padrão aplica-se
somente ao motivo; políticas distinguem gestor, operador e textos do sistema.
Desativar/reativar, excluir com confirmação e respostas JSON usadas pela Folha
permanecem intactos. Fontes: cadastros/views.py, textos.py, policies.py e
viagens/tests/test_textos_prontos.py. Sem regra nova ou alteração documental.
Substituições visuais: cabeçalho antigo por registro_hero, registro sem placa
por registro--catalogo, ação reutilizada no topo/rodapé. Explicação em bloco
único para não fragmentar palavras no flex. Diálogo conserva controles existentes.
# CD07 — Usuários e perfis

Lista com busca nome/login/e-mail, abas de acesso e filtro por perfil; paginação25.
Administrador cria/edita, ativa/inativa com confirmação, sem exclusão. Cadastro:
nome, login, e-mail institucional, múltiplos perfis, unidade e senha confirmada.
Primeiro acesso exige troca; edição permite conservar senha vazia. Proteções de
auto-inativação e retirada do próprio administrador permanecem. Fontes:
cadastros/views_usuarios.py, tests/test_usuarios.py e tests/e2e/test_usuarios.py.
Migração sem regra nova: hero canônico, registro de catálogo e campos proporcionais.
Correção compartilhada: campo.html deve distinguir CheckboxSelectMultiple de
checkbox simples, usando fieldset/legend com ajuda/erro associados ao grupo;
nunca envolver uma coleção de labels por outro label.

## CD08–CD15 — Catálogos compartilhados

Unidades, Cargos, Combustíveis, Tipos de viagem, Programas, Horários, Atividades
e Conjuntos compartilham catalogo.html. Fontes funcionais: views_crud.CATALOGOS,
docs/migration/cadastros.md, test_crud.TestCatalogos e test_catalogos_plano.
Preservar busca, ativos/inativos, paginação (15 unidades; 25 demais), vínculos,
padrão único quando aplicável, permissões e POST com CSRF/voltar. Sem autosave.
Horário exige fim posterior ao início; Atividade exige meta e mantém código
imutável; Conjunto exige atividade e conserva vínculos desativados na edição.

Substituir cabeçalho antigo por registro_hero e registros sem placa pela variante
registro--catalogo. Extrair apenas a ação repetida de criação. Unidade passa a
grade responsiva para Nome/Sigla, empilhando no celular. Demais parciais conservam
seus controles específicos. Sem CSS/JS adicional ou mudança das consultas.
Validar cada rota separadamente, inclusive diálogo e estados condicionais;
herança do template compartilhado não conclui automaticamente as oito páginas.

## GL01 — Central de módulos

GET / é uma entrada de navegação sem salvamento próprio. Preservar módulos,
grupos, itens e permissões de navegacao_para; indicadores de Viagens respeitam
oficios_visiveis, e Coffee mantém saldo/pendências/alertas calculados na origem.
Fontes: painel.views.inicio, plataforma.navegacao e coffee/test_integracoes.
Autenticação e troca obrigatória de senha não mudam.

Cabeçalho passa ao hero. Atalhos diretos permanecem visíveis; grupos em_menu
usam o menu canônico, como na navegação superior, sem retirar links. Extrair
acessos de módulo para parcial reutilizável. Simplificar ícone e métricas na
origem, testando também Eventos/painel e Eventos/cadastros, consumidores reais
de modulo__*. Somente regras de atalhos comprovadamente substituídas podem sair.
FUTUROS é estado condicional legítimo e permanece mesmo vazio no DEMO.


## GL02 — Agenda: contrato antes da edição

GET `/agenda/`: mês, semana, dia e lista. Preservar parâmetros mes/dia/vista,
fonte (múltiplo), encerrados e meus; navegação anterior/seguinte/hoje, fontes
filtradas por permissão, dossiê e retorno, pauta PDF e escala. Assinatura é POST
com CSRF, geração/rotação/revogação de token; o token só aparece uma vez.
Não alterar conteúdo da pauta oficial nem lógica de autorização.
Fontes: painel/views_agenda.py, plataforma/agenda.py, testes/test_agenda e
painel/tests/test_assinatura_agenda.py. A referência funcional já está documentada
nesses módulos; nenhuma decisão institucional nova é necessária.

Diagnóstico com quatro vistas em360/768/1440: controles de anterior/seguinte
se separam no celular; filtros de fontes ocupam quase toda primeira dobra;
checkbox azul nativo difere do sistema; descrição antiga e divisor dourado
isolado; dossiê requer revisão junto das vistas. Preservar calendário servidor
sem adicionar biblioteca. Direção: hero compacto, navegação do período inseparável,
ações e vistas agrupadas; filtros em painel integrado explícito e opções canônicas;
lista/dia com registros canônicos. Assinatura permanece segura e identificável.
