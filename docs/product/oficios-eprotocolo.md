# Ofícios — dados copiáveis para o eProtocolo (RS-01)

Fonte funcional consultada somente por leitura de código local em 07/10/2026:
`C:/Users/tiago/OneDrive/Documentos/Solicitações de eventos/viagens_oficios/services.py`,
função `dados_eprotocolo` (linhas 409–448). Complementos: `campos_modelo.py`, funções
`_periodo` e `valores_do_oficio`; `presenters.py`, `destinos_resumidos`; template
`templates/components/v32/copiaveis.html`. Nenhum banco ou sistema publicado foi consultado.
Direção aprovada: D18 em `docs/visual-agents/visual/oficios-detalhe-plano.md`.

O domínio puro recebe valores já selecionados pelo chamador, sem consultar Django,
cadastros, documentos ou integrações. Produz cinco campos, nesta ordem:

1. **Interessados:** nomes em ordem alfabética, separados por vírgula e espaço.
2. **Assunto:** linha do assunto seguida do rótulo, separadas por um espaço.
3. **Nº/Ano do ofício:** número já formatado pelo sistema, por exemplo `01/2026`.
4. **Protocolo:** nove dígitos recebem a máscara `12.345.678-9`; valores já formatados
   permanecem iguais. Valor vazio fica vazio. Validação institucional pertence ao serviço.
5. **Detalhamento:** `OFÍCIO Nº <número> - <LINHA DO ASSUNTO EM MAIÚSCULAS>`, seguido,
   quando presentes, de `DESTINO: …`, `PERÍODO: …` e `SERVIDORES: …`, separados por
   ` - `. Sem número, começa por `OFÍCIO`. O motivo segue em uma nova linha quando presente.

O rótulo do assunto, como `(Autorização)`, integra o campo Assunto, mas não a linha
do assunto usada no Detalhamento. A pontuação final `.` da linha é retirada somente
no Detalhamento. A regra que decide autorização/convalidação permanece no domínio
existente de assunto; esta função não toma essa decisão novamente.

Destinos chegam como rótulos `Cidade/UF`, na ordem do roteiro, sem o retorno à sede.
O domínio usa maiúsculas, até 100 rótulos, e acrescenta ` +N` quando excedidos,
como a fonte local. Não remove destinos repetidos nem nomes homônimos. Nomes vazios
são ignorados e espaços externos são retirados. A ordenação determinística de nomes
usa a ordem Unicode do Python; não promete reproduzir uma collation PostgreSQL específica.

Datas são `date` já convertidas para o dia local pelo chamador. Saída ausente produz
período vazio. Sem retorno, ou com retorno no mesmo dia, usa `dd/mm/aaaa`; nos demais
casos, `dd/mm/aaaa a dd/mm/aaaa`, inclusive quando muda o ano. O domínio não converte fuso,
não valida cronologia e não considera uma data de retorno isolada como período completo.

O retorno imutável contém os cinco pares de rótulo/valor e **Copiar tudo**, composto
pelos mesmos valores, cada um precedido por seu rótulo, separados por quebras de linha.
Copiar tudo é a melhoria prevista em D18; não existia na função legada consultada.

Limites desta etapa: sem serviço, tela, área de transferência ou chamada ao eProtocolo.
A montagem dos dados de rascunho versus snapshot emitido, autorização e aviso sobre
protocolo simulado/treinamento ficam para a integração com a aplicação.

## Evidência da base pura — 07/10/2026

Implementação: `gestao/viagens/dominio/eprotocolo.py`; testes:
`gestao/viagens/tests/test_eprotocolo.py`. A primeira execução ocorreu no workspace
derivado de `8d1d77e`; a base pura foi incorporada no commit **`b0829d6`**
(`feat(viagens): compor dados copiáveis do eProtocolo no domínio`).
Ruff dos dois arquivos: verde. Testes: **17 passaram em 0,15 s**.
Execução: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run python -m pytest --noconftest
-o addopts='' gestao/viagens/tests/test_eprotocolo.py -q`. Sem plugin Django, conftest,
fixtures de aplicação ou acesso ao banco. O aviso de configuração desconhecida
`DJANGO_SETTINGS_MODULE` é consequência da desativação deliberada do plugin Django.

Cobertura: cinco campos comparados integralmente com o formato da fonte, data única,
período entre anos, saída ausente, ordenação/homônimos, máscara do protocolo, texto e
quebras de linha do motivo, ausência de dados, assunto complementar, ordem/limite de
destinos e consistência de Copiar tudo. Integração visual e Clipboard não testados aqui.

## Proposta do adaptador de leitura — checkpoint `b0829d6`

Esta seção é uma proposta técnica fundamentada no código existente, ainda sem serviço
ou tela implementados. D18 autoriza o componente copiável; não constitui aprovação
humana das escolhas específicas abaixo. O legado consultado usa dados vivos em
`dados_eprotocolo`, enquanto o novo preserva a versão emitida em `Documento.dados`.
Usar esse snapshot no emitido é uma proposta para manter os textos copiáveis coerentes
com a via oficial, inclusive depois de alterações nos cadastros de pessoas e municípios.

### Seleção da fonte e estado

- **Rascunho:** usar o ofício e relações atuais, inclusive após retificação/reabertura.
  Nunca copiar dados da versão anterior como se fossem o rascunho atual. Identificar
  a fonte como “Dados do rascunho”. A revisão de emissão usa o ofício preparado por
  `services.preparar_data_emissao`/fluxo de revisão do Lote H, para que o assunto e a
  data concordem com a revisão. A folha normal usa a data gravada, sem antecipá-la
  silenciosamente. Identificar se os dados exibidos refletem o estado salvo.
- **Emitido:** selecionar a maior `versao` de `Documento` com `tipo="oficio"` e
  `oficio_id` igual ao ofício autorizado, sem filtrar `situacao="pronto"`. O snapshot
  nasce dentro da mesma transação de `services.emitir`, antes de o worker gerar o PDF.
  Assim, v2 gerando/falhou continua sendo a fonte v2, sem promover a v1 pronta.
  Identificar “Dados da emissão · versão N”, junto do estado documental existente.
  Geração pendente/falha não apaga o snapshot nem prova que o arquivo está pronto.
- **Cancelado:** se for exibido o bloco, usar a última emissão somente como informação
  histórica, identificada como cancelada; cancelado sem emissão não possui snapshot.
  A decisão de disponibilizar o bloco nesse estado não está comprovada por D18;
  a integração inicial pode limitar o bloco a rascunho/emitido, como a proposta R28.
- **Arquivado:** a seleção da fonte segue a situação subjacente, com identificação
  de arquivado; consultar não deve desarquivar nem preparar nova emissão.
- **Emitido sem snapshot, ou snapshot inválido:** não reconstruir a via oficial a
  partir de cadastros atuais nem mesclar dados históricos e vivos. Exibir estado
  indisponível com orientação “Os dados desta emissão estão indisponíveis. Confira
  o documento emitido.”; cópia de um conjunto incompleto precisa ser identificada
  como incompleta, sem anunciar fidelidade à emissão. Nenhum caso desses foi medido
  no banco nesta investigação; são contratos para tratar a ausência de dados.

### Mapeamento exato para a função pura

Fonte do schema: `gestao/viagens/documentos/dados.py`, `dados_do_oficio`; modelo:
`gestao/viagens/models.py`, `Documento`. Todos os campos seguintes já existem.

- `numero`: rascunho → `oficio.numero_formatado`; emitido → `dados["numero"]`.
- `protocolo`: rascunho → `oficio.protocolo_formatado`; emitido → `dados["protocolo"]`.
  O snapshot já armazena a máscara, aceita sem transformação pela base pura.
- `assunto_linha` e `assunto_rotulo`: rascunho → `services.assunto_do_oficio(oficio)`;
  emitido → `dados["assunto"]` e `dados["assunto_rotulo"]`. Não recalcular o assunto
  histórico usando a data atual ou novos trechos.
- `servidores`: rascunho → nomes dos `viajantes_de(oficio)`; emitido → os valores
  `nome` de `dados["viajantes"]`. Homônimos permanecem, pois representam pessoas
  distintas. Motorista de fora não entra nessa lista: o schema o armazena à parte
  em `dados["motorista"]`, e o legado usa apenas os servidores da equipe.
- `destinos`: rascunho → rótulos `nome/uf` dos destinos de `trechos_de(oficio)`,
  excluindo sede e mantendo a ordem; emitido → `dados["destinos"]`. A proposta do
  rascunho acompanha a mesma projeção do snapshot atual: destinos únicos na ordem
  da primeira ocorrência. **Diferença existente:** o snapshot atual deduplica
  destinos, mas o domínio copiável conserva a lista recebida e a referência local
  pode manter repetições. Não há decisão humana específica confirmada para essa
  diferença; documentar na paridade e não alterar o snapshot nesta integração.
- `saida`/`retorno`: rascunho → primeira saída e última chegada dos trechos ordenados,
  convertidas com `timezone.localtime(...).date()`; emitido → converter com formato
  explícito `%d/%m/%Y` os valores `dados["trechos"][0]["saida"]["data"]` e
  `dados["trechos"][-1]["chegada"]["data"]`. `_dt` já congelou esses dias no fuso
  local. Não tratá-los como instantes UTC ou convertê-los de fuso novamente.
  O retorno é a **chegada**, inclusive quando atravessa a meia-noite; usar a saída
  do último trecho reduziria o período em relação à referência `periodo_roteiro`.
- `motivo`: rascunho → `oficio.motivo`; emitido → `dados["motivo"]`.

O adaptador pode devolver o `DadosEprotocolo` mais metadados de apresentação:
fonte (`rascunho`/`emissao`), versão da emissão quando houver, estado do documento,
aviso de origem do protocolo e disponibilidade. Não devolver o JSON completo do
snapshot ao navegador: ele também contém CPF/RG, cargos e dados de assinantes,
desnecessários aos cinco campos copiáveis. Não gerar HTML a partir de valores nem
interpretar regiões de `dados["edicao"]` para obter campos estruturados.

### Consulta e orçamento

No resumo, `views._contexto_resumo` já carrega os documentos e seus snapshots numa
lista ordenada por tipo e versão. Passar essa lista ao adaptador e selecionar a
maior versão em memória evita consulta adicional. Não usar `pdf_oficio` como fonte:
ele atualmente seleciona a última versão pronta, que pode ser a versão anterior.

Na folha, reutilizar `viajantes`/`trechos` do contexto ou `queries.viajantes_de` e
`queries.trechos_de`, que compartilham o prefetch da requisição. Não chamar
`dados_do_oficio` só para montar eProtocolo: isso carrega configuração, assinantes,
substituições e informações documentais sem necessidade. Em outro consumidor sem
documentos já carregados, a consulta proposta é uma única busca do último ofício:
`oficio.documentos.filter(tipo="oficio").order_by("-versao").first()`; relações
devem permanecer vinculadas ao ofício autorizado.

Esta investigação não mediu consultas. Preservar os budgets atuais dos testes de
resumo (20 no rascunho, 15 no emitido), e justificar qualquer impacto com medição
depois da implementação; não aumentar limites apenas para acomodar consultas repetidas.

### Autorização e origem do protocolo

O bloco é uma projeção de leitura. Proposta: preservar a mesma autorização do resumo,
`policies.pode_ver`, aplicada por `views._oficio_visivel` antes de obter os campos.
`viagens.view_oficio` e escopo da unidade continuam necessários; outra unidade não
autorizada retorna 404. Não exigir edição só para copiar dados já visíveis e não
introduzir acesso direto por ID de documento que contorne o escopo do ofício.
Não chamar integração, salvar campos, gerar documento ou registrar emissão no GET.

Fontes do aviso: enum `Oficio.OrigemProtocolo` e
`docs/integrations/eprotocolo.md` (origem e avisos E2); referência local
`viagens_oficios/form_context.py`, `ajuda_do_protocolo`:

- `simulado`: “Número simulado. Confirme o protocolo real antes de protocolar.”
- `treinamento`: “Protocolo de treinamento. Não vale como protocolo oficial.”
- `eprotocolo`: “Aberto no eProtocolo”, sem acrescentar data que não esteja registrada.
- `manual`: “Protocolo digitado”; isso informa a origem, não valida existência externa.
- Vazio/desconhecido: não afirmar que o protocolo é oficial ou aberto externamente.

**Lacunas do schema:** o novo não armazena `protocolo_criado_em`; o snapshot de
`dados_do_oficio` não contém `protocolo_origem`. No emitido, a origem atual do cadastro
pode ser usada apenas como metadado claramente identificado e quando seu número
formatado coincide com o número do snapshot. Se divergir, tratar a origem histórica
como desconhecida e não substituir o protocolo congelado. A frase “aberto em…”
e a origem histórica exata não podem ser reproduzidas com fidelidade neste schema.
Adicionar origem a snapshots futuros é uma evolução possível, mas não integra
esta proposta de adapter mínimo e não autoriza regravar documentos antigos.

Mostrar o aviso junto ao campo e antes de Copiar tudo. A fonte consultada exige
avisar, mas não comprova decisão humana para bloquear a cópia de números simulados;
portanto não transformar o aviso em novo bloqueio institucional nesta etapa.

### Verificações a adicionar na integração

- Emissão v1: alterar depois nomes/municípios no cadastro; os cinco campos do emitido
  continuam reproduzindo o snapshot, enquanto novo rascunho usa cadastros atuais.
- Rascunho retificado com v1 antiga: copiar os dados atuais, nunca a antiga emissão.
- v1 pronta e v2 gerando/falhou: fonte é v2; aviso não promete PDF pronto.
- Primeira saída/última chegada perto da meia-noite e entre anos: dias iguais aos
  que foram congelados; não aplicar dupla conversão de fuso.
- Falta de snapshot ou data inválida: mensagem compreensível sem GET de escrita,
  fallback silencioso ou quebra da janela inteira.
- Leitor/operador/gestor com objeto visível; outra unidade negada; nenhum CPF/RG no
  payload do bloco; todas as origens do protocolo com os respectivos avisos.
- Cópia individual/Copiar tudo, anúncio acessível e fallback de Clipboard; resumo
  inserido por HTMX carrega o módulo existente `componentes/copiar.js`.

Até este checkpoint, essas verificações são propostas, **não resultados de testes**.
Esta atualização mudou somente este documento; não executou banco ou suíte e não
alterou o código congelado em `b0829d6` durante `scripts/verificar.sh`.

## Adaptador independente — 07/10/2026

`gestao/viagens/eprotocolo.py` implementa a projeção documentada. O chamador precisa
autorizar o objeto; listas já carregadas evitam fallback de consulta. Snapshot
ausente ou inválido produz indisponibilidade visível, sem reconstruir uma emissão
com cadastros atuais. O resultado inclui fonte, versão e estado do documento;
CPF/RG não são projetados. Cancelados sem snapshot não prometem dados de emissão.

**28 testes com objetos simulados passaram em 0,72 s**, reexecutados pelo principal
sem plugin Django, conftest ou banco. Ruff e mypy verdes. Cobrem fontes e versões,
snapshot invalidado, correspondência de protocolo/origem, dias locais e ausência
de consultas de fallback quando listas são fornecidas. Não estão conectados à
tela, não demonstram orçamento SQL real e não substituem testes de autorização.
Arquivos: `gestao/viagens/eprotocolo.py` e
`gestao/viagens/tests/test_eprotocolo_dados.py`.
