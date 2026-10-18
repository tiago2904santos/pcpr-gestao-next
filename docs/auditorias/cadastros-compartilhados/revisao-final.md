# Revisão cética independente — cadastros compartilhados

Data: 17/10/2026. Escopo: diff corrente e arquivos novos de catálogo, fonte,
configuração da unidade, seleção remota e cadastro rápido. Revisão por agente
independente; sem deploy, acesso à produção ou execução de suíte ampla.

## Base e método

Foram lidos `AGENTS.md`, as orientações de revisão cética/segurança em
`.claude/agents/`, os contratos `docs/product/cadastros-compartilhados.md` e
`dados-da-unidade.md` e os ADRs 0044/0045. Os resultados abaixo decorrem da
inspeção do código existente; descrições de trabalho planejado não foram usadas
como prova de funcionamento. A suíte geral e o navegador ficam registrados nos
logs próprios desta missão, executados pelos responsáveis por essas validações.

## Achado corrigido durante a revisão

**P2 — seleção remota perdia o estado de leitura.** A configuração desabilita
seus campos para o operador em `views_crud._tela_configuracao`. O novo widget
renderiza esse estado no `select`, mas o método
`PcCombobox.criarEntradaParaSelect` inicialmente não copiava `select.disabled`
para o campo de texto criado. Assim, os quatro assinantes aparentavam permitir
edição/busca numa tela de consulta. O backend continuava impedindo gravação;
o problema era interação enganosa e perda visual do titular consultado.

O achado foi comunicado antes de qualquer alteração. A correção aplicada pelo
responsável foi observada em `static/js/componentes/combobox.js`:
`entrada.disabled = select.disabled`. Não houve alteração de código por este
revisor.

Validação dirigida após a correção: Node 24.21.0 carregou o arquivo real em VM,
substituindo somente as APIs de DOM por um modelo mínimo, e chamou o método com
`select.disabled=true` e o titular atual. Resultado, com saída 0:

```json
{"selectDisabled":true,"inputDisabled":true,"inputValue":"Titular atual"}
```

Esta prova confirma a cópia do estado no método; não substitui o teste da tela
em navegador. A primeira tentativa do executor mínimo precisou acrescentar um
stub de `customElements.define`; esse erro de preparação não foi tratado como
falha da aplicação.

## Pontos de risco conferidos sem novo achado acionável

- **Identidades e migração:** `eventos/migrations/0008_catalogo_compartilhado.py`
  mantém os IDs de `AtividadePlano`, preserva os serviços legados com FK e mapa
  dos usos originais e migra FKs/M2M por campos temporários. Homônimos não são
  mesclados pelo nome. A equivalência CIN exige código, conteúdo completo e
  situação da carga. O rollback destrutivo não é anunciado como disponível.
- **ContentType e permissões:** `preservar_permissoes` restaura o ContentType
  `eventos.servico` após a operação automática de RenameModel; o proxy conserva
  o app/model usado nas políticas de Eventos. O teste de migração inspecionado
  injeta o hook real de ContentTypes e confere IDs de CT, permissões de grupo e
  autorização efetiva do usuário. Não foi reexecutado nesta revisão.
- **Histórico:** a migração preenche `nome_registrado` com o nome legado e
  preserva observações. Novos usos capturam o nome no `save`; alterações de
  observação não substituem o nome já capturado. A folha de consulta e a
  exportação usam esse snapshot. A migração não reescreve arquivos/documentos.
- **Exclusão:** os dois contextos verificam usos do catálogo comum, inclusive
  M2M sem relação reversa pública, vínculos externos e legado protegido. A
  retirada de usos futuros ocorre por inativação, preservando vínculos atuais.
- **Fonte dedicada:** `fontes.py` mantém IDs locais e contrato explícito de
  campos, valida as permissões e o payload, normaliza identificadores e usa
  transação/locks. `reconciliar` compara base/local/recebido e recusa conflito
  divergente. O CRUD local consulta ownership, inclusive pelo proxy de Eventos.
  Fonte real, transporte e ordenação de revisões permanecem dependências
  documentadas da integração futura.
- **Autorização da unidade:** identificadores explícitos de GET/POST são
  validados e divergências são rejeitadas; o endpoint de busca aplica a mesma
  resolução contextual e política de consulta. Escritas verificam permissão
  antes de validar os campos. O catálogo de pessoas continua institucional,
  conforme contrato existente, sem conceder acesso a documentos/contas.
- **Seleção remota:** o HTML contém apenas o atual e a escolha vazia; validação
  usa o queryset completo autorizado e conserva o atual inativo. Digitar outro
  texto limpa o ID; selecionar um resultado acrescenta uma opção ao select.
  A busca limita 15 resultados e mascara o CPF. Sem JS o select preserva o atual.
- **Modais:** o auxiliar suspende e fecha o pai, preservando-o no DOM; o reset
  de cadastro rápido respeita `cadastroSuspenso`. Fechar o auxiliar reabre o pai
  e restaura foco no gatilho. Os listeners são de uma execução por abertura;
  erros de cadastro recebem foco e resposta redirecionada/sem ID é recusada.

## Resultado

Nenhum achado acionável permanece aberto dentro do escopo inspecionado após a
correção acima. Esta revisão não declara a missão inteira validada: o verde de
`scripts/verificar.sh`, E2E, capturas e revisão visual deve ser confirmado nos
respectivos logs e relatórios. Não foram iniciados novos processos de testes
com banco/navegador para evitar concorrência com as validações já em execução.

## Complemento — últimas alterações da missão

Nova leitura cética limitada aos diffs finais, em 17/10/2026. **Nenhum novo
achado acionável** foi identificado neste recorte:

- O motorista de Eventos usa `SelecaoRemota`, a fonte local e validação pelo
  queryset de ativos mais o atual inativo. O endpoint limita 15 resultados e,
  quando há solicitação explícita, resolve o objeto por
  `solicitacoes_visiveis` antes de exigir edição/reabertura. Sem solicitação,
  exige a política existente de criação. A possibilidade de escolher pessoas
  institucionais já existia no formulário anterior; o endpoint não concede CRUD.
- O atributo `form` do select também é copiado ao input criado pelo combobox,
  preservando sua associação à folha de Eventos. A cópia de `disabled` continua
  presente e o botão de limpar não é criado para input desabilitado/só leitura.
- As novas contagens de atividades reutilizam `_contagem`, com subconsulta
  independente por relação. Não introduzem JOIN simultâneo multiplicador de
  conjuntos/planos/solicitações nem consulta por registro ao montar `obj.usos`.
  O teste de regressão inspecionado usa múltiplos vínculos por relação.
- O botão de fechar dos cadastros é item flex estático do cabeçalho, com espaço
  próprio. O ajuste móvel de efetivo usa as classes semânticas dos campos,
  reservando linha inteira a cargo/unidade e colocando remover junto da
  quantidade. Não depende da posição genérica dos filhos no HTML.
- O `ANALYZE cadastros_municipio` foi localizado no arquivo efetivo
  `gestao/viagens/tests/cenarios.py`, após a carga sintética, condicionado ao
  backend PostgreSQL. O SQL é constante, não altera dados nem muda regras de
  consulta. Não foi introduzido no caminho HTTP da aplicação.

Limites deste complemento: inspeção estática apenas; não houve nova execução de
teste, perfil de SQL ou revisão independente de novas capturas. Os números de
testes e a melhora de desempenho relatados pela coordenação não foram
reexecutados por este revisor. A prova final de geometria/foco e o resultado da
suíte ampla permanecem nos logs de navegador/verificação da missão. Nenhum
arquivo de produto foi alterado por este revisor.

## Conferência conservadora da equivalência CIN

Leitura complementar do responsável pelo catálogo, sem alteração de código ou
nova execução de testes: `quantidade_cin` permanece campo independente da
solicitação, inclusive na cópia, formulário, CSV e consolidação. Vínculos e
resultados usam a PK; o domínio e `resultados.py` de Eventos permanecem iguais ao
estado inicial. Não foi encontrada regra operacional condicionada ao nome ou
código CIN. Assim, um serviço antigo inativo ou um CIN canônico com meta/recurso
editados pode permanecer separado como `EVENTO_<id>`, sem perder comportamento.
As referências específicas ao nome/código estão nas cargas e no cenário DEMO.
