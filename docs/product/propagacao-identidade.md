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
