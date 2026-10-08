# Propostas delimitadas de desempenho — Viagens

## Encerramento do candidato — 07/10/2026

Histórico abaixo preserva a proposta e suas medições anteriores. No gate final,
a separação CSS foi rejeitada por regressão visual do Resumo; formulario.css e
44 links voltaram ao original. Somente os candidatos JS de filtros/cadastro/
Baixar permanecem, com HTTP/E2E reexecutados. Comparação fresca baseline08 versus
candidato final, mesmos budgets/coletor: recursos/requisições melhoraram ou ficaram
iguais, mas três cenários ainda falham nos budgets preexistentes. Sem elevar teto
ou continuar novas otimizações neste bloco. Evidência e decisão de entrega em
`../visual-agents/qa/fechamento-gate-final-2026-10-07.md`; integral final pendente.

## Estado e fontes — 07/10/2026

Este documento começou como proposta com o produto congelado durante a suíte de
14 casos do agente principal. Depois da medição fresca, o candidato 1 foi
autorizado e implementado; os resultados estáticos e as pendências estão ao fim.
Os números das primeiras seções são da coleta original anterior à carga adiada.
Ainda não há medição de navegador do candidato 1.
Não se alteram os tetos: lista/resumo CSS 140 KB e 25 pedidos; folha HTML 120 KB,
JS 130 KB, 32 pedidos e SQL 25. Os testes usam bytes / 1024; números abaixo em KB
seguem essa unidade. Mantêm-se também os demais budgets, inclusive gzip e tempo.

Fontes primárias locais:

- Checkout original, `artifacts/recursos-desempenho-viagens_oficios.json`,
  `recursos-desempenho-viagens_oficios__resumo_727.json` e
  `recursos-desempenho-viagens_oficios_733_editar.json`, coletados em 07/10.
- `docs/quality/performance-budgets.md`, ADR 0002, ADR 0018, ADR 0021 e
  `tests/e2e/test_desempenho.py`.
- `static/css/formulario.css`, `templates/base_documento.html`,
  `templates/arquetipos/lista.html`, `viagens/oficios/lista.html` e `editar.html`.
- `templates/componentes/dialogos_cadastro.html`, os diálogos de servidor,
  viatura, catálogos, download e guardar texto; `gestao/cadastros/forms.py`,
  `gestao/viagens/views.py`, `gestao/cadastros/urls.py` e `views_crud.py`.
- `static/js/app.js`, componentes de seletores, cadastro rápido, download,
  texto pronto e `tests/test_css_por_pagina.py`.

## OBSERVAR / ENTENDER

Lista e resumo têm **153.099 bytes de CSS minificado (149,5 KB), 28 pedidos** e
126.041 bytes de JS (123,1 KB). HTML: lista 51.106 bytes; resumo 65.598. SQL do
documento inicial: 12 e 18 respectivamente. São contagens dos recursos registrados,
não uma duplicação das amostras posteriores do servidor.

A composição de CSS é igual nas duas rotas: compartilhado `tokens/base/layout/
components` **92.447 bytes**, `listas.css` **34.938**, `formulario.css` **25.714**.
Só `formulario.css` acrescenta 25,1 KB. A lista precisa dos seletores da gaveta;
não precisa das seções posteriores de progresso, conferência, transporte, equipe
e atividades do plano. O resumo usa os mesmos recursos da lista nesse relatório.

Na folha 733: documento principal **138.181 bytes (134,9 KB)**, HTML somado
**150.351 (146,8 KB)**, CSS **165.636 (161,8 KB)**, JS **161.498 (157,7 KB)**,
**52 pedidos comuns**, 3 do itinerário e SQL **26** no documento inicial. Duas
miniaturas acrescentam documentos de 8.437 e 3.733 bytes e seus CSS/imagens/fontes.
A correção de visibilidade em andamento deve ser medida antes de outra mudança;
ela ainda não autoriza chamar esses números de resultado atual do worktree.

Fontes continuam contando como pedidos e mantendo status/falhas na coleta. Seus
bytes de rede, inclusive valores negativos reportados pelo CDP, não são tamanho
de código fonte nem justificativa para retirar pedidos do orçamento.

## PROJETAR — proposta 1: recursos dos filtros conforme a gaveta

Substituir, somente na lista de ofícios e no resumo aberto sobre essa lista, o
pacote completo de formulário pelo trecho canônico de seletores; carregar os
controladores de `pc-select` e `pc-data` da gaveta quando ela abre ou recebe foco.
Busca, Documento, abas, fichas, OOB, resultados e menus continuam imediatos.

O trecho medido vai do início de `formulario.css` até antes de “Progresso de
preenchimento”, linha 257. Inclui calendário, relógio e `.data-hora`: é um recorte
contido, não CSS de componentes novos. Seus **6.268 bytes de fonte viram 4.285
minificados e aproximadamente 1.211 gzip**, contra 25.714 minificados do pacote
completo. A minificação foi executada isolando do AST somente as funções puras
reais de `gestao/plataforma/estaticos.py`; não se importou Django nessa estimativa.

Estimativa aritmética: CSS de lista/resumo **131.670 bytes (128,6 KB)**, redução
de 21.429 bytes, abaixo de 140 KB. Os quatro módulos de seletores e dependências
(`seletor.js`, `seletor-data.js`, `seletor-base.js`, `painel-flutuante.js`) somam
**19.450 bytes** no relatório. Se não houver outro consumidor antes da gaveta,
a carga inicial passaria de **28 para 24 pedidos**, JS de 126.041 para 106.591.
Isso é estimativa por dependências, não uma medição de candidato.

Cuidados concretos:

- `arquetipos/lista.html` pré-carrega `seletor.js`; adiamento só funciona se a
  lista de ofícios substituir esse preload. Outras listas não devem mudar por
  consequência acidental. `app.js` também precisa respeitar seletores dentro
  da gaveta fechada; remover só o preload não resolve.
- O CSS dos controles fechados precisa existir desde o primeiro desenho. Não
  esperar a gaveta abrir para estilizar campos já no HTML.
- Manter uma única fonte do Design System. Uma opção é gerar o recorte da
  seção canônica para esta rota, com teste de equivalência, sem cópia mantida à
  mão. Se se escolher separar os fontes em dois arquivos, todos os formulários
  precisam dos dois links: isso acrescenta um pedido nas folhas e pode estourar
  32. A estratégia de geração/split requer ADR antes da implementação.
- Componentes registrados anteriormente na mesma navegação e substituições
  HTMX devem continuar operantes. A primeira interação após abrir a gaveta não
  pode exigir um segundo clique. Calendários/combobox não podem surgir sem CSS.
- `tests/test_css_por_pagina.py` atualmente exige `formulario` para `pc-data`;
  o contrato deve reconhecer o pacote de seletores e conferir equivalência das
  regras, preservando a detecção de CSS faltante e os elementos criados pelo JS.

## PROJETAR — proposta 2: diálogos secundários somente quando solicitados

Servir sob demanda os mesmos templates de cadastro rápido, download e guardar
texto, em vez de seus corpos completos no HTML inicial da folha. Reutilizar os
formulários de Cadastros; nenhum formulário paralelo e nenhum endpoint de POST
novo. Os endpoints existentes continuam gravando, validando e retornando JSON.

Para o GET do fragmento, preferir um modo explícito no endpoint existente da
folha, autorizado pelo mesmo ofício/unidade e pela permissão de cada cadastro.
Ele retorna o template canônico solicitado e evita montar todo `_contexto`.
Esse modo **ainda não existe**: não se deve alegar que basta consumir um endpoint
de fragmentos pronto. As listas GET de servidores/viaturas atualmente montam
contagens, paginação e a página inteira; buscar essa tela inteira só para extrair
um diálogo troca bytes iniciais por trabalho desnecessário.

Estimativa isolada de HTML, sem banco: Django renderizou os templates atuais
com token CSRF fictício e catálogos vazios; os construtores reais de formulários
foram usados com QuerySets sintéticos vazios. `ensure_connection` foi bloqueado
para falhar se algum código tentasse acessar banco. Resultado:

- Cadastro rápido completo (5 diálogos): **13.720 bytes**. Inclui o widget remoto
  de motoristas da viatura. Catálogos reais acrescentam opções a esse volume.
- Diálogo de download: **3.840 bytes**.
- Guardar texto pronto: **1.997 bytes**.

Cadastro rápido sozinho deixaria o documento principal, por subtração, em
**124.461 bytes (121,5 KB)**, ainda acima de 120. O conjunto de 19.557 bytes
deixaria **118.624 bytes (115,8 KB)**, antes do markup substituto necessário.
São estimativas com opções vazias, não extração do HTML real da folha 733 nem
garantia de tamanho com todos os estados/erros. O novo fragmento tem de voltar
a ser contabilizado quando a interação o solicita.

Há economia provável de consultas iniciais: `_contexto` instancia
`FormularioServidor` e `FormularioViatura`; o primeiro materializa cargos,
o segundo procura combustível padrão e os templates percorrem escolhas de
unidade/combustível. Basta eliminar uma consulta para baixar o máximo 26 a 25,
mas o ganho exato precisa de medição real. Não atribuir tempo de banco ou TTFB
a esta simulação, que não acessou banco.

O JS pode adiar `cadastro-rapido.js` (2.843 bytes), `multiescolha.js` (5.332, se
seu único consumidor continuar sendo o diálogo de viatura) e `baixar.js`
(6.589). **Não** contar como economia `combobox.js` (a equipe e a viatura usam
combobox no formulário principal), `mascara.js` (há protocolo no principal)
ou `texto-pronto.js` (já atende motivo/justificativa na folha).

Uma subtração prudente da antiga coleta — retirando o módulo de miniaturas
(5.999) e os três controladores acima (14.764) — ainda deixa JS em
**140.735 bytes (137,4 KB)**, acima de 130. Essas duas propostas não comprovam
o atendimento desse teto; depois da nova coleta será preciso localizar os
recursos restantes. Não mudar seu enquadramento para o orçamento do itinerário
ou retirar fontes/erros apenas para fazer o teste passar.

Na coleta antiga, as duas miniaturas têm 16 pedidos identificáveis
(2 HTML, 4 CSS, 2 imagens, 8 fontes), mais o módulo de índice. Retirá-los dá
**35 pedidos comuns estimados**; adiar os três controladores secundários pode
dar **32**. Mais um CSS ou um carregador JS novo quebra essa margem. Deduplicar
somente o que efetivamente não for solicitado; a coleta seguinte deve confirmar
o efeito com o menu, com caches e com as interações previstas no teste.

Cuidados concretos:

- O carregador precisa deduplicar pedidos/cliques, indicar carregamento/falha,
  manter o botão que abriu como origem e abrir o diálogo depois de ligar seus
  handlers. Preservar foco, Escape, retorno de foco e diálogos de catálogos
  sobrepostos; não inserir formulários dentro do formulário do ofício.
- `cadastro-rapido.js` liga somente os diálogos existentes ao importar;
  `texto-pronto.js` captura o diálogo ao carregar. Ambos precisam iniciar
  instâncias inseridas posteriormente sem handlers duplicados. Custom elements
  em cache devem reconhecer widgets novos.
- Conservar CSRF, expiração de sessão, erros de validação, autorização por usuário
  e unidade, valores digitados e versão do autosave. O criado deve entrar na
  equipe correta ou na seleção que abriu o cadastro, como atualmente.
- Delimitar fallback sem JS sem regredir o comportamento existente. GET de
  leitura nunca grava cadastros; POSTs e suas políticas permanecem os atuais.
- Download/guardar texto são parte desta estimativa de HTML; se forem deixados
  inline, registrar o déficit restante em vez de anunciar 120 KB atendidos.

## TESTAR / COMPARAR / CRITICAR — exigências antes de implementação/entrega

A suíte de 14 casos terminou, conforme informação do agente principal:
**11 passaram / 3 falharam**, com os **5 casos novos de carga adiada passando**.
As três falhas são de expectativas em outros testes (Clipboard CRLF no Windows
e ordem da toolbar); o agente principal ajustou somente esses testes e iniciou
a repetição dos três. Isso valida aspectos da carga já implementada, não os
candidatos deste documento. Não foi produzida nova medição de desempenho ainda.

Aguardar essa repetição e a nova coleta do worktree. Só então fixar o baseline
e escolher o menor recorte necessário. A análise acima é aritmética sobre fontes
e relatórios anteriores; nenhum candidato foi executado em navegador.

Validação transversal necessária, sem aumentar qualquer budget:

- CSS por página e minificação, incluindo calendário/relógio/painéis produzidos
  pelo JS; testar que o pacote derivado corresponde à fonte canônica.
- Lista/resumo: busca, Documento, abas, filtros e ordem, datas/períodos, fichas,
  URL, paginação/OOB, menu, abrir/fechar filtros e retorno de foco; teclado,
  toque, axe e capturas 360/390/768/1440.
- Folha: cadastro de servidor/viatura, cargo/unidade/combustível sobrepostos,
  motoristas habituais, validações/erros/permissões/CSRF/sessão, autosave com
  edição pendente e reposição HTMX, duas aberturas seguidas e retorno à origem.
- Download: primeira abertura fria, seleção/formato/versão/PDF único, falhas e
  arquivo entregue. Guardar texto: uso pelo campo e pelo editor, retorno à escolha
  correta, histórico/edição sem perda do texto corrente.
- Outras folhas que compartilham diálogos e seletores: roteiro, termo, OS, plano,
  viagem e Cadastros, além do UI Lab. Não generalizar mudanças na base sem esses
  testes. Reutilização de templates não substitui essa cobertura.
- Desempenho real nas três rotas com os mesmos cenários/interações/collector:
  tamanhos completos, fontes/pedidos, falhas HTTP e SQL; comparar inicial frio e
  ações diferidas. A economia inicial não isenta o custo ao abrir o recurso.

## OBSERVAR — baseline fresco após adiar miniaturas

A rodada sequencial do coordenador terminou em **3 falhas / 62,47 s**, sem erros
de coleta. Relatórios locais do worktree:

- `artifacts/desempenho-viagens_oficios.json`: CSS 149,5 KB, JS 124,1 KB,
  28 pedidos, HTML 49,9 KB, SQL 12.
- `artifacts/desempenho-viagens_oficios__resumo_6.json`: CSS 149,5 KB,
  JS 126,5 KB, 29 pedidos, HTML 69,3 KB, SQL 18.
- `artifacts/desempenho-viagens_oficios_12_editar.json`: HTML 139,9 KB,
  CSS 139,5 KB, JS 155,3 KB / gzip 54,7 KB, 36 pedidos, SQL 26,
  banco 106,8 ms. TTFB 234 ms, FCP 404 ms, LCP 892 ms, CLS 0, INP 16 ms.

A folha passou de 52 para 36 pedidos e de CSS 161,8 para 139,5 KB com a carga
adiada de editor/miniaturas já validada. Esse baseline continua reprovado;
não confundir os testes funcionais passados com atendimento dos tetos.

## PROJETAR / IMPLEMENTAR — candidato 1 autorizado

Decisão registrada **antes do código** no
[ADR 0026](../adr/0026-separar-seletores-e-adiar-controladores.md). A função de
filtros/períodos/ordem existente em `docs/product/modules.md`, no contrato do
template de Ofícios e no código do DS é preservada.

- A seção inicial canônica de `formulario.css` foi movida para `seletores.css`.
  `estilos_formulario.html` emite os dois links, seletores antes de formulário;
  não há duplicação de regras. Lista e resumo de
  Ofícios carregam diretamente seletores/listas/core.
- Um bloco específico do arquétipo permite retirar o preload de seletor apenas
  em Ofícios. O padrão das demais listas continua carregando-o.
- `data-controladores-adiados` na gaveta permite adiar imports quando seus
  elementos não têm caixa visível. Abertura (`toggle`), foco, reposição HTMX
  e `pcpr:controladores-repostos` reavaliam os controles. Elementos fora da
  marca continuam com carga imediata por presença; a lista mantém o controlador
  de filtros, busca e menu disponível desde o início.
- Se o usuário focar o select nativo enquanto seu import ainda está em curso,
  o app transfere o foco para o controle que o substituiu, quando a ocultação
  tiver deixado o foco no body. Trocar o foco para outro campo não o sequestra.
- A raiz é reutilizável nos diálogos adiados do ADR 0027. Este recorte não altera
  endpoints, views, querysets, cadastro rápido ou diálogos.

O segundo link adiciona **um pedido real de CSS** em formulários, incluindo a folha.
Não interpretar cache, hash ou separação como retirada desse pedido do orçamento.
Seu impacto e o overhead gzip devem aparecer na próxima coleta. O pedido
adicional não está aprovado apenas por esta implementação.

## TESTAR / COMPARAR — evidência estática, sem banco ou navegador

Execução no worktree isolado, usando os runtimes do checkout principal:

- TypeScript: `tsc --noEmit -p jsconfig.json`, **exit 0**.
- Ruff nos dois arquivos de teste tocados: **All checks passed**.
- `pytest gestao/plataforma/tests/test_estaticos.py -k 'tira_comentarios or
  pacotes_reais' -q`: **2 passed, 3 deselected / 0,46 s**. Esses dois casos
  são puros, sem fixture de banco.
- Comparação com `git show HEAD:static/css/formulario.css`: o CSS minificado
  resultante de seletores + restante do formulário é **exatamente idêntico**
  ao anterior. Anterior 25.714 bytes; seletores 4.285; formulário com import
  21.458 na primeira tentativa com import. Depois da correção sem import,
  formulário tem 21.427 bytes. A soma dos arquivos individuais é 25.712;
  o texto concatenado minificado mantém exatamente os 25.714 bytes originais
  (dois espaços entre seções explicam a diferença).
  Os efeitos da compressão separada ainda exigem medição real.
- Helpers de CSS executados isoladamente via AST, sem importar models/fixtures:
  na primeira tentativa o import resolvia `formulario → seletores`; calendário/relógio exigem seletores;
  `.css` da URL não vira classe por engano; regras canônicas não duplicam.
- Herança real dos templates renderizada com `base.html` mínima em loader
  `locmem` e `ensure_connection` bloqueado: Ofícios não pré-carrega seletor;
  o arquétipo padrão mantém o preload; CSS direto corresponde à decisão.
- Storage **WhiteNoise real** em diretório temporário, com conexão bloqueada:
  minificação, manifesto e compressão terminaram sem erro. O import foi
  reescrito para `css/seletores.f13006b78cae.css`, que existe no manifesto.
- Compilação Python dos testes e `git diff --check`: **exit 0**.

Sem o pacote inteiro de formulário, a estimativa CSS de lista/resumo continua
**128,6 KB**. Retirar os quatro módulos de seletor/data/base/painel dá a previsão
de **24 / 25 pedidos** respectivamente; o app um pouco maior entra no orçamento.
Esses resultados são aritmética e checks estáticos, **não medição do candidato**.

## CRITICAR / CORRIGIR / VALIDAR — pendências de entrega

Novo `tests/e2e/test_filtros_carga.py` entregue ao coordenador para execução
sequencial, **6 casos ainda não executados**: carga fria e menu em 360/1440;
ordem/URL/período real, Escape e retorno de foco; axe e capturas nessas larguras;
resumo frio; HTML reposto antes de importar e com módulos em cache; foco no
select nativo durante import em 360/1440. A interceptação conclui o próprio
`Route` no handler com `fetch/fulfill/finally`, sem manter uma rota pendente
fora do callback e sem espera sem prazo. Erros do console continuam reprovando.

Executar também o fluxo já existente
`test_fluxo_oficio.py::test_gaveta_de_filtros_filtra_por_protocolo`,
`tests/test_css_por_pagina.py`, formulários com seletores e outras listas do
arquétipo, seguido dos três orçamentos reais com o coletor aprovado. Revisar
as capturas 360/1440 e ampliar para larguras intermediárias quando necessário.
`scripts/verificar.sh` completo e paridade/validação visual continuam pendentes
com o coordenador. Não há aprovação estética inferida nem ciclo de entrega
declarado concluído.

`baixar.js` (6.589 bytes) e `copiar.js` (2.439 bytes) continuam oportunidades
**somente propostas**, sem mudança de carga neste recorte. Um candidato futuro
teria que iniciar pela abertura/foco antes do comando, guardar uma única ação
pendente com origem ainda conectada e preservar ativação de usuário, Escape,
foco, sessão e falhas. Replay automático de clique exige testar ausência de
duplo comando/download e não pode disparar a ação após cancelar o diálogo.
Não subtrair seus bytes ou pedidos até medir uma implementação validada.


## Correção após a primeira rodada do candidato

A execução real de 11 casos terminou em **8 falhas / 3 passaram / 156,13 s**.
Este resultado substitui o estado “6 casos ainda não executados” acima: os seis
casos novos falharam na carga inicial antecipada ou na corrida causada por ela.
Dois casos de cadastro também falharam; as causas e o recorte autorizado estão
em [qa-seletores-gaveta.md](qa-seletores-gaveta.md).

A correção substitui `@import` por dois links `static` em um componente canônico,
usado nos 44 consumidores encontrados, e acrescenta guarda explícita de
ancestral details fechado, preservando summary/raiz e o comportamento padrão
fora da marca. Mantêm-se as expectativas dos seis testes de navegador, axe,
console, budgets e CSP. As evidências da tentativa com import são históricas;
WhiteNoise/hash corretos não bastaram para compatibilidade com a análise CSSOM
do axe. A rodada de navegador da correção continua pendente com o coordenador.
