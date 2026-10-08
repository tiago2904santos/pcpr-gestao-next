# QA — seletores canônicos e carga da gaveta

Data: 07/10/2026. Worktree:
`C:/Users/tiago/.codex/worktrees/viagens-tempo-legado/pcpr-gestao-next`.
Decisão estrutural: [ADR 0026](../adr/0026-separar-seletores-e-adiar-controladores.md).

## OBSERVAR / ENTENDER — primeira rodada real reprovada

O coordenador executou 11 casos sequencialmente. Resultado:
**8 falhas / 3 passaram / 156,13 s**. Fonte primária:
`C:/Users/tiago/OneDrive/Documentos/pcpr-gestao-next/var/cadastro-filtros-adiados-browser.log`.
Essa rodada inclui cadastro rápido do ADR 0027, seis casos novos de filtros e
um teste HTTP. Não é uma validação aprovada do candidato.

- Quatro casos frios de filtros falharam porque os pedidos registrados já
  incluíam `seletor.js`, `seletor-data.js`, `seletor-base.js` e
  `painel-flutuante.js` com a gaveta fechada. Os únicos consumidores desses
  seletores no template da lista estão dentro de `#filtros-mais`.
- Dois casos de corrida do import falharam dentro do handler: o select nativo
  estava oculto quando o import foi interceptado, antes da abertura pretendida.
  A antecipação real invalidou a premissa da corrida, em vez de comprovar um
  defeito independente de foco. Conservar a expectativa e repetir após corrigir
  a carga inicial.
- Cadastro 1440 terminou suas operações, mas console apresentou CSP de estilos
  inline e 404 em `/viagens/oficios/<pk>/editar/seletores.css` durante axe.
  Cadastro 360 apresentou também `target-size` em `#id_marcador-gatilho`,
  parcialmente encoberto pelo cabeçalho; o coordenador investiga esse alvo e
  foco/layout em recorte separado. Não foi alterado por esta correção.

A geometria usada sozinha pela função de disponibilidade não cumpriu o contrato
de conteúdo fechado nessa rodada. Não se afirma que todo `getClientRects` de
todo elemento oculto tenha o mesmo comportamento. A correção identifica o estado
semântico de `details`, conhecido e reproduzido pelos casos reais.

Leitura de `tests/_vendor/axe.min.js` (linha 12): `_f` lê regras de tipo 3
(`CSSImportRule`) e passa seu `href` para `Mf`. `Mf` chama
`XMLHttpRequest.open("GET", href)` sem resolver pela URL do stylesheet.
O href relativo `seletores.css` é, então, solicitado em relação à página. Esse
ramo também chama `convertDataToStylesheet` para as regras restantes e para o
CSS importado; `ff` cria elementos style. A CSP existente não permite esses
estilos inline. Hash/WhiteNoise corretos da tentativa anterior não evitam esse
caminho de análise CSSOM. Corrigir apenas o href não resolve a segunda causa.

## PROJETAR / IMPLEMENTAR / CORRIGIR

Correção autorizada pelo coordenador depois da rodada, com ADR atualizado antes
de editar os fontes:

- `app.js`: dentro de raízes optantes, um ancestral `details` fechado bloqueia
  controles descendentes. Descendentes de seu summary continuam disponíveis;
  a própria raiz details permanece disponível ao controlador da gaveta. A
  verificação percorre ancestrais, incluindo details aninhados. Fora do opt-in,
  a carga por presença continua igual. Mantêm-se toggle, foco, HTMX, cache e
  restauração do foco nativo.
- `formulario.css`: sem import. As regras extraídas continuam somente em
  `seletores.css`.
- Novo `componentes/estilos_formulario.html`: dois links com a tag `static`,
  **seletores antes de formulário**, na ordem antiga das regras. Prefixos de
  STATIC_URL e hashes continuam pertencendo ao storage canônico.
- Busca identificou **44 consumidores** de `css/formulario.css`. Substituição
  mecânica exclusiva desse link pelo include em todos eles, incluindo os
  arquétipos formulário/assistente/cadastro de nomes e folhas/listas de Viagens,
  Cadastros, Coffee, Eventos, Palestras, Imprensa, Publicações, Painel e UI Lab.
  Não houve mudança de markup funcional, query, endpoints ou estilos visuais.
- `test_css_por_pagina.py`: exige uso do componente nos consumidores, ordem dos
  links na renderização das telas, prefixo STATIC_URL alternativo, ausência de
  imports e ausência de regras de seletor duplicadas no restante do formulário.
  O mapa continua exigindo seletores para calendário/relógio gerados pelo JS.

Nenhuma alteração em helper axe, CSP, filtros de console, coletor ou budgets.
`test_filtros_carga.py` mantém integralmente suas seis expectativas. Cadastro
rápido, diálogo core e serviços/HTTP não foram editados neste recorte.

## TESTAR / COMPARAR — evidência estática da correção

Executado pelo agente de filtros, sem banco nem navegador:

- `tsc --noEmit -p jsconfig.json`: exit 0.
- Ruff em `test_css_por_pagina.py` e `test_filtros_carga.py`: All checks passed.
- `git diff --check`: exit 0.
- Três testes estáticos do arquivo CSS chamados diretamente com
  `BaseDatabaseWrapper.ensure_connection` bloqueado por AssertionError:
  regras separadas/sem import, consumidores canônicos, links/ordem/prefixo.
  **Todos passaram.** Não executar o pytest inteiro marcado django_db nessa etapa.
- Compilação pelo loader Django dos 44 consumidores: **sem erros**, com conexão
  bloqueada. O componente foi renderizado com STATIC_URL alternativo
  `/prefixo-de-teste/estaticos/`; emitiu exatamente os dois links esperados,
  nessa ordem.
- Comparação minificada com `git show HEAD:static/css/formulario.css`:
  `minificar_css(seletores + formulario) == minificar_css(anterior)`, **verdadeiro**.
  SHA256 comum: `cd9b0dc76025d16ce710d593bf68b4c8254618e637c82a4641bb855e7e6a3214`.
  Seletores: **4.285 bytes**; restante: **21.427 bytes**, soma **25.712**.
  O texto minificado concatenado anterior tem **25.714 bytes**: os dois bytes
  de diferença são espaços entre seções, ausentes ao minificar os arquivos
  individualmente. A igualdade canônica acima compara o texto concatenado.
- Os dois testes puros de minificação CSS já passaram antes da rodada real:
  **2 passaram / 0,46 s**. A comparação canônica foi repetida depois de remover
  a diretiva de import. Isso não é evidência de navegador da correção.

## CRITICAR / VALIDAR — pendente com o coordenador

Todos os formulários que carregavam um pacote passam a pedir dois: **+1 pedido
real de CSS**, agora por link explícito. Mesmo peso de regras não implica mesmo
gzip ou mesma sequência de rede. Registrar esse custo na medição da folha e dos
consumidores; não excluí-lo do orçamento nem inferir aprovação.

Obrigatórios: repetir os seis casos de filtros e os casos de cadastro relevantes,
sem ignorar console; abrir calendário, verificar ordem, período, URL, teclado,
foco durante import, HTML reposto e cache; axe e capturas 360/1440. Revisar os
artefatos produzidos, e não afirmar aprovação visual antes da leitura.

Executar `tests/test_css_por_pagina.py`, o fluxo existente da gaveta por protocolo
e regressões de seletores/calendário em formulário, roteiro, termo, OS, plano,
Cadastros e UI Lab, além das telas de outros contextos que usam o componente.
Confirmar outras listas sem opt-in. Nova medição de lista/resumo/folha com o
mesmo coletor e budgets, seguida de `scripts/verificar.sh` e paridade aplicável.

**A correção ainda não foi validada em navegador por este agente.** A rodada
reprovada permanece registrada; o ciclo de entrega não está declarado completo.

## Decisão final do candidato CSS — 07/10/2026

Separação CSS NÃO incorporada: revisão de capturas revelou divulgação eProtocolo
sem estilo no Resumo. Equivalência de concatenação não atendia o consumidor que
carregava só seletores.css. Formulario.css original e 44 links restaurados;
seletores.css/estilos_formulario.html retirados, eliminando também +1 pedido por
formulário. Mantido só carregamento JS opt-in dos filtros, validado novamente nos
seis E2E com CSS aprovado. Guard computado summary inline-flex passou 360/1440.
HTTP canônico de pacotes CSS passou. Histórico acima registra tentativa rejeitada.
Fechamento atual e medições em fechamento-gate-2026-10-07.md; não inferir aprovação
integral por este relatório, pois o verificador ainda está em execução.
