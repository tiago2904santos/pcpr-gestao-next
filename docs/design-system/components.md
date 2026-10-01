# Catálogo de componentes

Todos vivem em `static/css/components.css` e são exercitados em **/ui-lab/** (estados:
padrão, hover, foco, ativo, desabilitado, carregando, erro, sucesso, vazio, conteúdo longo,
celular). Comportamentos em `static/js/componentes/*.js` (Web Components, sem framework).

| Componente | Classe / elemento | Variantes e estados | Acessibilidade |
|---|---|---|---|
| Botão | `.botao` | `--primario` (grafite), `--marca` (dourado, 1 por tela), padrão (contorno), `--sutil`, `--texto`, `--perigo`, `--perigo-contorno`, `--avancar`; `--sm/--lg/--bloco/--icone`; `disabled`; linguagem de ação: `aria-busy` (processando), `data-estado="concluido"` (carimba), `data-estado="erro"` (balança) | Botão-ícone exige `aria-label`; processando preserva largura; foco = anel do DS |
| Campo | `.campo` + `.entrada/.selecao/.area-texto` | "campo aceso": tingido em repouso, branco + borda grafite + halo dourado no foco (rótulo e ajuda acendem); erro (`.campo--erro` tinge de vermelho + `aria-invalid`), sucesso, desabilitado, estático (`.entrada--estatica`, linha pontilhada), composto (`.entrada-composta`) | Rótulo sempre visível; ajuda/erro via `aria-describedby` |
| Caixa / rádio | `.escolha input` | desenhados no DS (`appearance: none`): grafite ao marcar, marca que brota; desabilitado | Inputs nativos: rótulo, teclado e leitor de tela intactos |
| Escolha | `.escolha` (checkbox/rádio), `.interruptor` (`role="switch"`) | marcado, desabilitado, com descrição | Área de clique inclui o texto |
| Combobox | `<pc-combobox>` | local (aprimora `<select>`), remoto (`data-fonte`), com ação HTMX (`data-acao-url`) | WAI-ARIA combobox 1.2, `aria-activedescendant`, anúncio de resultados |
| Data/hora | `input[type=date/time]` nativo | — | Teclado do celular adequado; zero JS (ADR 0007) |
| Cartão/Seção | `.cartao` | `__cabecalho` com `__numero` ou `__titulo--institucional` (ícone dourado + caixa alta), `__rodape`, `--destaque`, `--interativo` | Título é heading real |
| Indicador (KPI) | `.indicador` | `--atencao`; pode ser link | Valor + rótulo legíveis por leitor de tela |
| Selo de status | `.selo` | tons `--neutro/info/sucesso/aviso/perigo/marca/forte`; **linguagem de estado** pela forma do marcador: `--situacao-rascunho` (anel vazio), `--situacao-emitido` (✓), `--situacao-cancelado` (×), `--processo` (pulso), `--carimbo`; `--sem-ponto` | Texto obrigatório (status nunca só por cor; a forma é reforço) |
| Alerta | `.alerta` | info, sucesso, aviso, perigo; com lista | `role="alert"` só para erro bloqueante |
| Toast | `<pc-toasts>` | sucesso/aviso/info somem em 6s com barra de tempo (`::after`), pausam no hover **e no foco** (`.toast--pausado`), saem animados (`.toast--saindo`); erro persiste; `--fixo` | `role="status"`, não rouba foco |
| Placa | `.placa` | `__rotulo` + `__numero`; `--grande` (detalhe), `--cancelada` (tachado) | Decorativa (`aria-hidden`): o link/heading ao lado já diz "Ofício N" |
| Trilho de processo | `ol.processo > li.processo__passo` | `--feito`, `--atual`, `--cancelado` | `aria-label="Etapas do ofício"`; texto em cada passo (nunca só cor) |
| Abas | `.abas` + `.aba` | links de filtro (`aria-current`) ou `<pc-abas>` (ARIA tabs) | Setas/Home/End em `<pc-abas>` |
| Sanfona | `details.sanfona` | aberta/fechada | Nativo |
| Etapas | `.etapas` | concluída, atual, pendente; vertical/horizontal (assistente de emissão) — em formulários longos use `.progresso` | `aria-current="step"` |
| Tabela | `.tabela` | `--compacta`, `--responsiva` (vira cartões <768px), `--linhas-clicaveis`, ordenação (`aria-sort`), rodapé de totais | `caption`, `scope`, números alinhados à direita |
| Lista de registros | `.registros > .registro` | placa + título + selos + metadados; equipe com 3 nomes e `+N`; **grupos por mês** (`.registros__grupo`, presos sob o topo); **expansão em linha** (`[data-expandir]` + `.registro__extra` carregado por HTMX de `viagens:resumo`, `.resumo` em 3 colunas); hover com trilho dourado; `data-vt` para a transição | Link cobre a linha; botão de expansão com `aria-expanded/aria-controls`; Esc fecha e devolve o foco; `.registro:has(:focus-visible)` desenha o foco na linha |
| Documento / seção | `.documento > .secao` | folha única com timbre dourado; `.secao__cabecalho` (`__numero` ou `__titulo--institucional`, `__estado` à direita); `--ok`; trilho dourado na margem em `:focus-within`; `--leitura` (64rem) | Cada seção é `<section aria-labelledby>`; `scroll-margin-top` respeita o topo fixo |
| Progresso de formulário | `nav.progresso` | `__etapa --ok/--pendente/--bloqueia` (forma do marcador), `__medida` com `<progress>` nativo | Substitui o índice lateral; links âncora; `<progress aria-label>` |
| Trilho de processo | `ol.processo` | `--feito` (✓ dourado), `--atual` (halo), `--cancelado` (×) | `aria-label`; texto em cada passo |
| Filtros | `.filtros`, `.filtros-ativos`, `.ficha` | busca, selects, fichas removíveis | `role="search"` |
| Paginação | `componentes/paginacao.html` | elipses, anterior/próxima desabilitadas | `aria-current="page"`, rótulos |
| Migalhas | `componentes/migalhas.html` | — | `nav[aria-label]`, último item `aria-current` |
| Diálogo | `dialog.dialogo` | confirmação, `--perigo`, gaveta (`.gaveta`); entra com `--curva-expressiva`, sai com `.dialogo--saindo` (`fecharDialogo()` em dialogo.js) | `<dialog>` nativo: foco preso, Esc, retorno do foco; Esc e botões `method=dialog` passam pela saída animada mantendo `returnValue` |
| Confirmação | `data-confirmar` / `hx-confirm` | destrutiva (`data-confirmar-perigo`) | Substitui `window.confirm` |
| Menu suspenso | `<pc-menu>` | item de perigo, separador | Padrão menu button; setas, Esc |
| Paleta de comandos | `<pc-comandos>` | navegação + busca no servidor | Ctrl+K ou "/"; combobox + listbox |
| Estado vazio | `componentes/vazio.html` | primeiro uso (ação), sem resultado (limpar filtros) | Heading + orientação |
| Carregando | `.esqueleto` (`--titulo/--linha/--curto/--bloco`, `.registro--esqueleto`), `.girando`, `.lista-resultados.htmx-request` (esmaece + barra dourada) | — | `aria-busy`, `role="status"` |
| Linha do tempo | `.linha-tempo` | `--colunas` (duas colunas em telas largas), `__item--marca`, disclosure `details > summary.linha-tempo__mais` | `<ol>` com `<time datetime>` |
| Tabela aberta | `.tabela--aberta` | dentro do documento: sem fundo no cabeçalho nem recuo | igual à tabela |
| Pessoa | `.pessoa`, `.avatar` | motorista (selo forte), com termo | Botão remover com nome no rótulo |
| Valor | `.valor-destaque`, `.por-extenso` | `--marca` | — |
| Prévia de documento | `.previa-documento` | iframe do PDF | Título no iframe |
