# Aprendizados — padrões já decididos

Consulte antes de desenhar uma tela. Cada item nasceu de uma correção do usuário ou de um
problema real; não redescubra. Formato: **padrão** — por quê / onde está.

## Listas

- **Clicar na linha abre a janela de resumo, não uma página de detalhe.** A página de detalhe
  do ofício foi apagada; a janela concentra leitura e ações (Editar, Ver PDF, Minuta). —
  ADR 0017, `oficios/_resumo.html`, `_dialogo_resumo.html`.
- **Sem expansão inline na linha.** Tentado e rejeitado.
- **Busca única e inteligente por "leituras"**: o termo é interpretado (número, protocolo,
  placa, destino, servidor) e a lista mostra fichas "Procurar 26 como: Número (3) ·
  Protocolo (12) …" em vez de despejar 50 resultados. — `viagens/dominio/busca.py`,
  `queries.contar_leituras` (um aggregate só), `oficios/_refino.html`.
- **Filtros avançados escondidos em "Mais filtros"**, botão na primeira linha com a mesma
  altura dos campos ao lado; dentro, **um único campo de período** (calendário de intervalo,
  igual ao de roteiros) em vez de "de/até" separados. Filtros que o usuário pediu:
  protocolo, valor de diária (faixa), veículo (viatura, ônibus, caminhão, unidade móvel…).
- **Abas: só a contagem anima (eixo Y) e a fita inferior (eixo X).** Nada de animar o rótulo
  inteiro; nunca barra de rolagem nas abas.
- **Separação por mês com faixa visível** entre grupos.
- **Fita lateral de hover acompanha a curva do cartão** (não reta).
- **Botão de criar nunca preso no topo**: barra de ações flutuante (`barra-acoes`) para
  "Novo ofício/roteiro" acessível em qualquer rolagem.
- **Mini-lista ao passar o mouse** ("usado em N ofícios"): comporta-se como o menu de ações,
  mas abre no hover com atraso (abre com `--duracao-lenta`, fecha com `--duracao-media`), só
  CSS (`:hover`/`:focus-within`). Nada de modal. Popover API para hover falhou. —
  `.menu--pousar` em `components.css`.
- **Ir de outra tela para um ofício** = lista de ofícios filtrada com a janela daquele ofício
  já aberta e carregada (`?q=<número>&resumo=<pk>`), com transição leve e carregamento
  curto. — `registro.js` (`dialog[data-abrir-ao-carregar]`).

## Janela de resumo (layout)

- Cabeçalho: título com chips ao lado dos destinos, centralizados na altura da placa; sem
  data de evento; sem "Assunto".
- Linhas: Roteiro | Diárias em **60/40**, **mesma altura**; se o roteiro for maior, ele trava
  na altura das diárias e rola por dentro. Com ≤ 3 trechos, roteiro ocupa a linha e as
  diárias vão para a linha seguinte em 3 cartões.
- Equipe + transporte em grade equilibrada: **no máximo 3 colunas, cada linha ocupa toda a
  largura** (2 servidores + viatura = 3 col.; 3 servidores + viatura = 2×2; 4 + viatura =
  3 + 2). — filtro `larguras_de_cartoes`.
- Valores grandes, **sem quebra de linha**; sem espaço em branco sobrando nos cartões.
- Barra de rolagem **dentro** da janela, com trilho invisível.

## Formulários

- **Autosave em toda folha de edição**; sem botão "Salvar" para atualizar a prévia — o editor
  de documento recarrega sozinho no evento `pcpr:dados-salvos`. Autosave não grava histórico
  (`registrar=False`) e devolve a nova `versao`. — `autosave.js`, `views.autosave`.
- **Editar um ofício emitido é permitido e o transforma em retificado** (não bloquear).
- **Sem h1 redundante** quando a placa/selo já identifica a página; o subtítulo alinha com a
  placa (h1 fica `sr-only`).
- **Sem stepper/índice lateral de seções** na folha do ofício (texto sobrepunha; removido).
- **Revisão antes de emitir na janela de resumo**, não em página própria: "Revisar e emitir"
  salva e volta com `?revisar=1`; a janela abre pronta (reaproveitando o contexto da folha, sem
  consultas a mais) e o **rodapé fica fixo** para a decisão nunca sumir em tela baixa.
- **Botão × de limpar** em campos de texto/busca e no combobox (`limpar.js`, um só para
  todos); nunca some no hover/foco.
- **Combobox: a primeira sugestão já vem marcada** — digitar + Enter escolhe.
- **Trocar para bate-volta preserva o destino**; a lixeira do bate-volta limpa datas/horas
  de ida e volta.
- **Calendário compacto**; período sempre pelo mesmo componente (`pc-data` com
  `data-periodo`).
- **Equipe em cartões de pessoa** (avatar, nome, cargo · unidade), sem rótulo "Motorista"
  escrito; ações discretas ao lado.
- Alertas nunca colados no bloco seguinte (margem), e ações do alerta centradas.
- Documento abre **em nova aba para visualizar**, sem baixar.

- **Texto pronto** em qualquer área de texto: `componentes/texto_pronto.html` +
  `SelecaoDeTexto` (opção leva `data-texto`); escolher preenche na hora e **pergunta antes de
  substituir** texto já escrito; "Guardar como texto pronto" grava pelo catálogo e já deixa
  escolhido. Sem JS, a escolha preenche o campo vazio no servidor.
- **Janela aberta pelo servidor** = `dialog[data-abrir-ao-carregar]` (tratado em `dialogo.js`,
  global): serve a resumo pedido, revisão e edição em cadastros (`?editar=<pk>`).

## Escala e visual

- **Componentes a 90% sem estreitar o shell**: `html { font-size: 90% }` e larguras do layout
  recalculadas em rem para manter a largura em px. — `base.css`, `tokens.css`.
- Linha entre cabeçalho e cartão: removida.
- `pc-select` próprio com seta em ícone do sprite (a seta de fundo sumia no hover).

## Armadilhas técnicas (já custaram tempo)

- Comentário `{# #}` do Django é de **uma linha**; multilinha vaza na página → `{% comment %}`.
- `display` num `<dialog>` vence o `display:none` do navegador quando fechado → aplicar só em
  `dialog[open]` (senão fica "fantasma").
- Elemento customizado é `inline` por padrão: margem não funciona → `display:block`.
- `background:` (atalho) apaga `background-image` → usar `background-color`.
- `overflow:hidden` quebra `position: sticky` → recortar com `clip-path`.
- `z-index` do campo em foco cobria o botão × → botão com `z-index: 3`.
- Dois inputs com o mesmo `name/id` (sede duplicada) perdem edição → um campo só, movido
  por JS.
- O navegador guarda CSS em cache no preview: forçar `?v=` ao conferir.
- Rodar testes enquanto edita arquivos gera falhas falsas; rode de novo sem editar.
- Contêiner de teste `pcpr-testdb` parado → centenas de erros de conexão: `docker start pcpr-testdb`.
- Banco do preview precisa de `migrate` depois de puxar migrações de outro agente.

- **Autosave × envio pelo botão**: o beacon de `pagehide` e um autosave em voo competiam com o
  POST do "Salvar"/"Usar roteiro" e geravam falso "outra pessoa salvou". Regra: envio
  explícito cancela o agendado, desliga o beacon e espera o autosave em voo (`autosave.js`).
- **Nada abre por baixo da barra flutuante**: menus de ação e seletores usam `abrirEspaco`/
  `limiteInferior` (em `menu.js`, carregado sempre) e abrem para cima quando não há espaço.
- **Alvo de toque em px**: com `html {font-size: 90%}`, rem encolhe; o mínimo WCAG 2.5.8 é
  o token `--alvo-minimo: 24px`.
- **Janela aberta pelo servidor vem com `open`** (funciona sem JS) e o JS a reabre modal.
- **A janela de revisão é a confirmação**: sem segunda janela "Tem certeza?" por cima; avisos
  não bloqueantes (conflito de agenda) aparecem nela.
- **Detector de sobreposição dos testes ignora o que está sob uma janela modal** (inerte).
- **Barra flutuante × axe `target-size`**: numa lista longa, a barra "Novo…" fixa no pé cobre
  o menu da linha que está embaixo dela e o axe reprova. Em lista, a ação vai no fim
  (`barra-acoes--rodape`, como na referência); barra flutuante só em formulário.
- **Trocar o widget de um `ModelMultipleChoiceField` depois de criado** perde as opções:
  `campo.widget.choices = campo.choices` (senão o widget não acha os escolhidos).
- **`%` em `error_messages`** de campo: a mensagem passa por `%`-formatação (`%(limit_value)s`);
  "15% ficaria" quebra com TypeError → escrever `15%%`.
- **Template de widget** usa o renderizador de formulários, sem os `builtins`: precisa de
  `{% load ui %}` para `{% icone %}`.
- **`isdigit()` aceita "²"** e `int("²")` estoura: parâmetro numérico com
  `isascii() and isdecimal()`; `\D` em regex aceita dígitos de outros alfabetos → `[^0-9]`.
- **Contagem de várias relações reversas**: vários `Count()` juntos multiplicam as linhas do
  JOIN; usar uma subconsulta por relação (`views_crud._contagem`).
- **Teste de propriedade (Hypothesis) do domínio de diárias** falhou uma vez sob `-n auto`
  com a máquina carregada e passou sozinho: tratar como intermitente, conferir antes de culpar
  a mudança.
- **`URLFetcher` do WeasyPrint 70**: `url_fetcher` passou a ser uma instância de
  `weasyprint.urls.URLFetcher` (não mais função); um novo por renderização (guarda estado).
- **Variáveis passadas uma a uma num `include`** (`_dialogo_resumo.html`): contexto novo na
  view não chega ao template incluído — conferir os `with` ao acrescentar algo.
- **Ações com texto numa linha de registro** esmaecem com `.registro__acoes` (opacidade) e
  reprovam contraste: usar `.registro__acoes--fixas`.
- **Orçamento de tempo (TTFB) na suíte de navegador com `-n 4`** estoura de vez em quando
  (máquina carregada); rodado sozinho passa. Antes de culpar a mudança, rodar
  `tests/e2e/test_desempenho.py` isolado.
- **Vínculos que impedem excluir**: `_meta.related_objects` ignora relações com
  `related_name="+"`; usar `get_fields(include_hidden=True)`.

## Processo

- **Checkpoint só com `scripts/checar_rapido.sh` verde** (para no primeiro erro). Encadear
  `uv run ruff … | tail -1 && git commit` não falha: o `tail` sempre sai 0 — dois commits de
  03/10 passaram assim e precisaram de correção.

- O usuário prefere ver a tela funcionando no navegador do app antes do relatório.
- Mudança de componente compartilhado: procurar todos os usos (`grep` no nome do elemento/
  classe) e rodar os testes das páginas afetadas.
- Pedir revisão aos agentes `revisor-ux` e `revisor-seguranca` ao fim de cada bloco: na rodada
  de 03/10 acharam um laço de confirmação, ampliação de privilégio (padrão global editável
  por operador) e vazamento potencial de credencial em redirecionamento.
- Testes de navegador demoram ~17 min: rodar a suíte rápida primeiro e o navegador sem editar
  código durante a execução.
