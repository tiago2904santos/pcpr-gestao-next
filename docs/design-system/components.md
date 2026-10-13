# Catálogo de componentes

## Identidade de registro e equipes — 12/10/2026

`identidade_documental.html` aceita `placa=True` junto de `compacta=True` para
identificar um documento dentro de uma coleção clara. Reutiliza rótulo, número,
complemento e estado cancelado do componente; a variante fornece superfície
grafite e contraste inverso. Consumidores: Lista de Prestação e UI Lab §14.
O padrão sem `placa` permanece nos demais cabeçalhos e listas.

`prestacao-equipe--documento` organiza identidade, metadados e ações de uma equipe
vinculada ao documento. A base `prestacao-equipe` continua válida em Anexos por
servidor, onde a placa de ofício não representa o mesmo conceito. Os filtros
de atenção usam as abas canônicas; as classes antigas `atalhos-atencao*` foram
removidas, preservando os IDs de atualização HTMX. Ver QA PR01 de 12/10.

## Padrão documental de Ofícios — 08/10/2026

`componentes/identidade_documental.html` reúne rótulo e número editorial. Aceita
`rotulo`, `numero` e `situacao`; cancelado mantém o número tachado. Reutilizado
no cabeçalho da Folha, no Resumo e na vitrine de dossiês do UI Lab.

`componentes/conferencia_valores.html` apresenta total, destino e quantidade
com os mesmos valores do cálculo existente. `documental=True` produz a faixa
horizontal da Folha; `vertical=True` produz o painel lateral do Resumo.
`sempre_por_servidor=True` mantém a nota já existente no Resumo. Sem variante,
o componente preserva a grade clássica dos outros consumidores.

`dialogo--dossie` é variante do diálogo DETAIL: número e destino separados,
metadados legíveis, roteiro sem segunda rolagem, equipe em linhas, rodapé com
ações disponíveis. UI Lab demonstra dados longos, dados ausentes e ação
desabilitada; testes cobrem leitura, revisão de emissão, cancelamento e
estados de geração pelos fluxos reais existentes.

`pagina--documental`, `pagina-cabecalho--documental`, `documento--continuo`,
`pessoas--faixa` e `barra-acoes--documental` compõem o padrão da Folha.
`lista--documental`/`registro--documental` aplicam a mesma linguagem à Lista:
o destino ocupa uma linha própria no celular, sem truncamento estreito.
O arquétipo de Lista aceita `variante_cabecalho` sem alterar seu padrão.
`campos--legiveis` complementa `campos--iguais`: acima de 768 px, largura
mínima de composição faz a linha quebrar antes de cortar rótulos longos.
As linhas condicionais seguem inteiras e o celular conserva duas colunas.

`editores--documental` organiza a estação de documentos. O parcial existente
`viagens/oficios/_editor.html` aceita `ferramentas_recolhiveis=True`: disclosure
nativo “Formatar texto”, fechado inicialmente abaixo de 768 px, aberto acima.
Enter/Espaço alternam o estado; a toolbar continua com um único tabstop e
setas/Home/End. O observador acompanha `open` e exclui comandos recolhidos;
a troca de documento ativo conserva a tabulação. Outros consumidores não
ativam a variante. UI Lab usa o mesmo parcial, sem persistir dados.

Todas as variantes usam tokens existentes. Nenhuma folha oficial, regra de
cálculo, permissão ou API foi alterada. Evidências e limites:
`../visual-agents/qa/oficios-premium-2026-10-08.md`.

O compartilhado vive em `static/css/components.css` (botões, campos, selos, alertas, toasts, tabelas, diálogos, menus, paleta); o que só algumas telas usam vai em pacotes carregados por `{% block estilos %}`: `formulario.css` (seletores de data/hora/lista, combobox, progresso, cartões de escolha, conferência), `documento.css` (folha única e seções, trilho de processo, histórico, definições, pessoa), `listas.css` (registros, filtros, paginação, abas), `painel.css` (central e coluna de contexto), `assistente.css` (etapas) e `itinerario.css`. Controles nativos neutralizados em `base.css`.
sem o "x" do campo de busca, sem setas no campo numérico, sem o amarelo do preenchimento
automático, barras de rolagem finas) e são exercitados em **/ui-lab/** (estados:
padrão, hover, foco, ativo, desabilitado, carregando, erro, sucesso, vazio, conteúdo longo,
celular). Comportamentos em `static/js/componentes/*.js` (Web Components, sem framework).

| Componente | Classe / elemento | Variantes e estados | Acessibilidade |
|---|---|---|---|
| Botão | `.botao` | `--primario` (grafite), `--marca` (dourado, 1 por tela), padrão (contorno), `--sutil`, `--texto`, `--perigo`; `--perigo-contorno` e `--avancar` só no catálogo (ui-lab.css); `--sm/--lg/--bloco/--icone`; `disabled`; linguagem de ação: `aria-busy` (processando), `data-estado="concluido"` (carimba), `data-estado="erro"` (balança) | Botão-ícone exige `aria-label`; processando preserva largura; foco = anel do DS |
| Campo de senha | `componentes/campo_senha.html` (`.entrada-composta--senha`) | botão mostrar/ocultar dentro da caixa (`.entrada-composta__botao`); some sem JS | `aria-pressed` + `aria-controls`; rótulo do botão muda ("Mostrar/Ocultar senha") |
| Campo | `.campo` + `.entrada/.selecao/.area-texto` | caixa branca com borda e **rótulo na borda** (como no sistema de referência; `--fundo-rotulo`/`--fundo-entrada` para fundos cinzas); foco = borda grafite + halo dourado (rótulo e ajuda acendem); erro (`.campo--erro` tinge de vermelho + `aria-invalid`), sucesso, desabilitado, composto (`.entrada-composta`) | Rótulo sempre visível (`<label for>`); ajuda/erro via `aria-describedby` |
| Caixa / rádio | `.escolha input` | desenhados no DS (`appearance: none`): grafite ao marcar, marca que brota; desabilitado | Inputs nativos: rótulo, teclado e leitor de tela intactos |
| Escolha | `.escolha` (checkbox/rádio), `.interruptor` (`role="switch"`) | marcado, desabilitado, com descrição | Área de clique inclui o texto |
| Combobox | `<pc-combobox>` | local (aprimora `<select>`), remoto (`data-fonte`), com ação HTMX (`data-acao-url`) | WAI-ARIA combobox 1.2, `aria-activedescendant`, anúncio de resultados |
| Data | `<pc-data class="seletor">` (widget `EntradaData`) | texto dd/mm/aaaa com máscara; botão de calendário dentro do campo; calendário com hoje (aro dourado), escolhido (grafite), dias de fora do mês esmaecidos, "Hoje" e "Limpar" | WAI-ARIA APG Date Picker Dialog: `role=dialog` + `role=grid`; setas, Home/End, PageUp/PageDown (Shift = ano), Enter, Esc devolve o foco ao botão; mês em `aria-live` |
| Hora | `<pc-hora class="seletor">` (widget `EntradaHora`) | texto hh:mm com máscara; relógio com duas colunas (horas; minutos de 5 em 5) | Duas `listbox` com `aria-activedescendant`; ↑/↓ mudam o valor, ←/→ trocam de coluna, Enter confirma |
| Data + hora | `.data-hora` (widget `EntradaDataHora`) | data e hora lado a lado; chegam como "dd/mm/aaaa hh:mm" | Nome de cada parte: rótulo do campo + "(data)"/"(hora)" via `aria-labelledby` |
| Lista | `<pc-select class="seletor">` (widget `Selecao`) | botão com a cara do campo + lista do combobox; opção atual com ✓ dourado; vazio em cinza | WAI-ARIA APG Select-Only Combobox; salto por letra; o `<select>` oculto continua sendo o valor (e o que funciona sem JS) |
| Cartão/Seção | `.cartao` | `__cabecalho` com `__numero` ou `__titulo--institucional` (ícone dourado + caixa alta), `__rodape` | Título é heading real |
| Indicador (KPI) | `.indicador` em `.grade--kpi` | `--atencao`; pode ser link; 4 por linha ≥1280px, **2 a 2 abaixo** (no celular compactos, sem a nota) | Valor + rótulo legíveis por leitor de tela |
| Módulo (central) | `.modulos > .modulo` | console: ícone + título + descrição, números (`__numeros`, `--destaque`), ação principal e **atalhos** (`__atalho`, os itens do menu do módulo que o usuário pode ver) | Cada módulo é `<section aria-labelledby>`; números em `<dl>` |
| Atalhos e lembrete (painel) | `.atalhos > li > .atalho`, `.lembrete` | linhas de lista com ícone e seta (link ou botão), em vez de botões em bloco; lembrete como nota dourada tracejada | `aria-label` no lembrete |
| Selo de status | `.selo` | tons `--neutro/info/sucesso/aviso/perigo/marca/forte`; **linguagem de estado** pela forma do marcador: `--situacao-rascunho` (anel vazio), `--situacao-emitido` (✓), `--situacao-cancelado` (×), `--processo` (pulso), `--carimbo`; `--sem-ponto` | Texto obrigatório (status nunca só por cor; a forma é reforço) |
| Alerta | `.alerta` | info, sucesso, aviso, perigo; com lista | `role="alert"` só para erro bloqueante |
| Toast | `<pc-toasts>` | sucesso/aviso/info somem em 6s com barra de tempo (`::after`), pausam no hover **e no foco** (`.toast--pausado`), saem animados (`.toast--saindo`); erro persiste; `--fixo` | `role="status"`, não rouba foco |
| Placa | `.placa` | `__rotulo` + `__numero`; `--grande` (detalhe), `--cancelada` (tachado) | Decorativa (`aria-hidden`): o link/heading ao lado já diz "Ofício N" |
| Trilho de processo | `ol.processo > li.processo__passo` | `--feito`, `--atual`, `--cancelado` | `aria-label="Etapas do ofício"`; texto em cada passo (nunca só cor) |
| Abas | `.abas` + `.aba` | links de filtro (`aria-current`) ou `<pc-abas>` (ARIA tabs) | Setas/Home/End em `<pc-abas>` |
| Sanfona | `details.sanfona` | aberta/fechada | Nativo |
| Etapas | `.etapas` | concluída, atual, pendente; vertical (índice) e **horizontal** (assistente de emissão: marcadores ligados por um fio, dourado no trecho percorrido, halo na atual; empilha abaixo de 480px) — em formulários longos use `.progresso` | `aria-current="step"` |
| Tabela | `.tabela` | `--compacta`, `--responsiva` (<768px cada linha vira um **cartão**: célula principal no alto, demais colunas duas a duas com rótulo em micro-caixa-alta), rodapé de totais; `--linhas-clicaveis`, ordenação (`aria-sort`) e `__secundario` só no catálogo (ui-lab.css) até terem uso | `caption`, `scope`, números alinhados à direita |
| Lista de registros | `.registros > .registro` (`viagens/oficios/_registro.html`) | Variante vigente `registros--operacionais` + `registro-operacional`: número em placa, destino/status, agenda, equipe/transporte e conferência; índice temporal lateral no desktop e horizontal no celular. O título abre Resumo por HTMX; sem JS abre a Folha. Grupos por mês, cancelado recua, destaque do recém-alterado e menu canônico carregado ao chegar ao botão permanecem. Ver Coleção operacional abaixo. | Link do título é alvo de teclado; foco do registro visível; motorista por extenso; texto truncado com `title`; metadados e ações preservados nas cinco larguras |
| Documento / seção | `.documento > .secao` | folha única com timbre dourado; `.secao__cabecalho` (`__numero` ou `__titulo--institucional`, `__estado` à direita); `--ok`; trilho dourado na margem em `:focus-within`; `--leitura` (64rem) | Cada seção é `<section aria-labelledby>`; `scroll-margin-top` respeita o topo fixo |
| Progresso de formulário | `nav.progresso` | `__etapa --ok/--pendente/--bloqueia/--atual` (forma do marcador, tons de aviso), `__medida` com `<progress>` nativo; `--fixo` fica sob o topo com "você está aqui" (`progresso.js`, IntersectionObserver) e sombra ao flutuar; no celular só a barra; com `span` em vez de links vira prévia de etapas (novo ofício) | Substitui o índice lateral; links âncora com estado em `sr-only`; `<progress aria-label>` |
| Cartões de escolha | `fieldset.opcoes > label.opcao` (+ `__icone`, `__titulo`, `__descricao`) | `--compactas`; marcado (borda grafite + ✓ dourado no canto), hover, foco (anel no cartão via `:has(:focus-visible)`), desabilitado; `.condicional` revela um campo colado à escolha | Rádio nativo escondido visualmente: setas, rótulo e leitor de tela intactos; `legend` obrigatória |
| Itinerário 2.0 | `<pc-itinerario class="itin">` (`static/css/itinerario.css`, ADR 0016) | três blocos: sede e destinos (UF filtra, arrastar e soltar pela alça), rota (mapa Leaflet + resumo) e trechos (cards dourados: só a saída; chegada calculada); calendário único das saídas | Alça com setas ↑/↓ e `aria-live`; grupos com `role=group`; sem JS continua um formulário comum |
| Conferência | `.conferencia` | `--pronta` (carimbo dourado); seções ✓/○, pendências como links, próxima ação | Itens com estado em `sr-only` |
| Divulgação | `details.divulgacao` | summary com "+" que gira; corpo aparece sem caixa | Nativo |
| Frase do ofício | `p.frase-oficio` | itens vazios em itálico; valor em dourado | Prefixo `sr-only` "Resumo do ofício" |
| Trilho de processo | `ol.processo` | `--feito` (✓ dourado), `--atual` (halo), `--cancelado` (×) | `aria-label`; texto em cada passo |
| Barra de filtros (D6) | `form.filtros.filtros--barra` (`viagens/oficios/lista.html`) | Busca (dica curta `data-dica-curta` quando a caixa estreita) · **Segmentado** com contagem · botão **Filtros (n)**; Segmentado e Filtros andam juntos (`.filtros__lado`); busca ao vivo por HTMX com contadores fora de banda; erro de rede no lugar dos resultados com "Tentar de novo" (`componentes/erro_lista.html`) | `role="search"`; foco não se perde na troca ao vivo |
| Segmentado | `.segmentado` (+ `--contagem`, `data-rola-lado`) | rádios nativos com rótulo em pílula; contagem em `.segmentado__conta`; opção desabilitada recua; no celular rola de lado com a borda esmaecida | `fieldset` + `legend` ("Documento"); setas trocam a opção (nativo) |
| Gaveta / folha de filtros | `details.filtros__mais > .filtros__avancados--rodape` (`filtros.js`) | ≥768px: gaveta **não modal** sob o botão (a lista atualiza ao vivo atrás), fecha com Esc, clique fora e "Fechar"; <768px: **folha inferior modal** sobre véu (resto `inert`, rolagem presa, Tab cicla, foco no 1º campo; calendários e listas sobem para a camada de topo — `data-camada-topo`) | Esc e "Fechar" devolvem o foco ao botão; título `h2` da gaveta rotula o grupo |
| Fichas de filtro | `.filtros-ativos > .ficha.ficha--filtro` (`viagens/oficios/_fichas.html`) | uma ficha por filtro que vale (inclui ordem não padrão e escopo da busca), × remove só ela; "Limpar tudo" tira os filtros e o Documento e mantém busca e aba; abaixo de 1280px o trilho rola de lado (borda esmaecida) com "Limpar tudo" **no começo** (no DOM também — um por largura) | × com `aria-label="Remover …"` e alvo de 24px; quem chega pelo Tab vê o item inteiro (abas-rolagem.js rola com folga do esmaecido) |
| Paginação | `componentes/paginacao.html` | elipses, anterior/próxima desabilitadas | `aria-current="page"`, rótulos |
| Migalhas | `componentes/migalhas.html` | — | `nav[aria-label]`, último item `aria-current` |
| Diálogo | `dialog.dialogo` | confirmação, `--perigo`, gaveta (`.gaveta`); entra com `--curva-expressiva`, sai com `.dialogo--saindo` (`fecharDialogo()` em dialogo.js) | `<dialog>` nativo: foco preso, Esc, retorno do foco; Esc e botões `method=dialog` passam pela saída animada mantendo `returnValue` |
| Confirmação | `data-confirmar` / `hx-confirm` | destrutiva (`data-confirmar-perigo`) | Substitui `window.confirm` |
| Menu suspenso | `<pc-menu>` | item de perigo, separador; **item descrito** (`.menu__item--descrito` > `.menu__item-texto` > título + `.menu__item-descricao`: o que a ação faz ou por que está inativa); **inativo** (`aria-disabled="true"`, recebe foco, não age); **flutuante** (linhas de lista ou `data-menu-flutuante`: painel na camada de topo sobre véu que fecha ao toque fora sem acionar o que está atrás; abre abaixo, acima ou ao lado do botão e nunca sai da janela — o que sobrar rola dentro; <768px vira **folha inferior** com o nome do registro em `.menu__folha-titulo`); **carregado ao chegar** (`data-menu-carregar="<url>"`: itens pedidos ao servidor no foco ou no toque na hora, e com o mouse parado ~120 ms sobre o botão; "Carregando as ações…" enquanto isso; falha anunciada em região viva; sessão expirada vira o item "Entrar de novo" com volta para a página); **grupo recolhido** (`[data-menu-grupo]` com `aria-expanded`/`aria-controls` + `.menu__grupo[role=group][hidden]`: abre no lugar, sem submenu voando — Enter/Espaço/→ abrem e levam ao 1º item, ← recolhe; usado para o que se faz uma vez por registro) | Padrão menu button (WAI-ARIA): Enter/Espaço/↓ abrem, ↑/↓/Home/End navegam, Esc fecha; o menu tem nome (o do botão); escolher um item flutuante fecha o menu e devolve o foco ao botão — inclusive depois da janela que o item abriu; descrição fora do nome (`aria-hidden`) e dentro de `aria-describedby` |
| Menu ⋮ canônico do ofício (D7) | `viagens/oficios/_menu_oficio.html` + `policies.menu_do_oficio` | grupos: Ver resumo · Abrir/Editar (retificar) · Ver minuta ou Ver PDF vN · Baixar documentos… · Anexar assinado… — Novo termo / OS / plano · Duplicar — Marcar como retificado/complementar (rascunho; exclusão mútua do domínio) — Cancelar… · Arquivar/Desarquivar · Reativar… — Excluir; o mesmo na lista, no painel e na janela de resumo ("Mais ações", sem o que já está no rodapé dela) | Quem só consulta vê só leitura (resumo, minuta/PDF) |
| Barra fixa da lista (D8) | `.barra-acoes` + `componentes/menu_mais.html` | contagem do recorte ("42 de 255 ofícios" filtrado; "Página 1 de 13" sem filtro) · Exportar planilha (o recorte da tela) · **Mais** (ações raras por permissão, ex.: Importar processo do eProtocolo quando existir; nunca vazio, nunca item inativo de algo que não existe) · ação primária ("Novo ofício"); no celular os botões dividem a linha e a contagem some | `role="status"` na contagem; "Mais" é um menu flutuante (abre para cima) |
| Selo de tempo | `{% selo_tempo inicio fim %}` (`dominio/tempo.py`) | "faltam N dias" (aviso se ≤ prazo) · "amanhã" · "começa hoje" · "em andamento · até dd/mm" · "volta hoje"; passado e sem data → sem selo; o mesmo em Ofícios, Roteiros e Termos | Texto sempre (nunca só cor) |
| Selo de contorno | `.selo--contorno` | característica do registro (tipo do ofício: Convalidação, Retificado, Complementar) — sem fundo, ao lado do selo de situação (cheio) | `title` com o porquê; o resumo diz por escrito |
| Paleta de comandos | `<pc-comandos>` | navegação + busca no servidor | Ctrl+K ou "/"; combobox + listbox |
| Estado vazio | `componentes/vazio.html` | primeiro uso (ação), sem resultado (limpar filtros) | Heading + orientação |
| Carregando | `.esqueleto` (`--titulo/--linha/--curto/--bloco`, `.registro--esqueleto`), `.girando`, `.lista-resultados.htmx-request` (esmaece + barra dourada) | — | `aria-busy`, `role="status"` |
| Linha do tempo | `.linha-tempo` | `--colunas` (duas colunas em telas largas), `__item--marca`, disclosure `details > summary.linha-tempo__mais` | `<ol>` com `<time datetime>` |
| Tabela aberta | `.tabela--aberta` | dentro do documento: sem fundo no cabeçalho nem recuo | igual à tabela |
| Pessoa | `.pessoa`, `.avatar` | motorista (selo forte), com termo | Botão remover com nome no rótulo |
| Valor | `.valor-destaque`, `.por-extenso` | `--marca` | — |
| Prévia de documento | `.previa-documento` | iframe do PDF | Título no iframe |
| Sessão expirada (pedidos assíncronos) | `identidade.middleware.EntradaObrigatoriaMiddleware` + `app.js` + `pc-toasts` | Navegação sem sessão → tela de login; HTMX/fetch/JSON sem sessão → **401** com `X-Sessao-Expirada` e `{"mensagem","entrar"}` (volta para a página de origem, nunca para o fragmento); HTMX recarrega no login (`HX-Redirect`); qualquer `fetch` dispara `pcpr:sessao-expirada` → aviso persistente "Sua sessão terminou — entre de novo." com o link "Entrar de novo" | Aviso de erro não some sozinho (WCAG 2.2.1); link real, focável |

## Leitura operacional de documentos — 08/10/2026

**Avaliação posterior:** o usuário reprovou visualmente a composição desta entrega.
Os contratos funcionais permanecem; a reconstrução abaixo substitui o padrão do piloto.

- `identidade_documental.html`: `compacta=True` adapta a assinatura ao registro de lista;
  mantém a variante de cabeçalho e o estado cancelado. Número acessível pertence ao link.
- `metadado.html`: par `dt/dd` escapado, para uso dentro de `dl`. Parâmetros `rotulo`,
  `valor`, `titulo`, `ausente`, `classe`; valor zero é válido. Ausência tem orientação textual.
  `.metadados` apresenta os itens por filetes, sem caixas adicionais. Resumo e UI Lab usam.
- `cabecalho_registros.html`: régua visual opcional de `.registro--documental`; rótulos
  configuráveis `identidade`, `descricao`, `participantes`, `valores`. Não cria papel de
  tabela: cada registro preserva seus próprios rótulos acessíveis, link e menu.
- Variante documental: >=1024 organiza identidade/viagem/equipe/valor; 768 conserva
  metadados em faixas; celular mostra protocolo e dedica linhas inteiras a equipe/transporte.
  Diárias completas no desktop, dinheiro alinhado à direita, sem novos scripts/requisições.
  Vitrine na seção 21 e nos dossiês do UI Lab. Comparações em
  `docs/visual-agents/evidencias/oficios-leitura-operacional/`.

## Mesa de registro oficial — piloto após reprovação

- `registro_hero.html`: identidade, título, contexto, complemento e situação recebidos
  pelo chamador. Superfície grafite, filete institucional, número forte. Não infere status.
- `bloco_registro.html`: seção com heading e `aria-labelledby`, índice opcional e parcial
  de conteúdo. Reúne roteiro, equipe, conferência e registro sem duplicar contêineres.
- `.mesa-registro`: estação documental seguida de missão/contexto em duas colunas largas;
  tablet usa leitura principal inteira e contexto em duas colunas; celular ocupa a tela
  e mantém uma rolagem e dock de ações. Ordem DOM começa pelos documentos em todas as larguras.
- `.estacao-documental`, `.peca-documental` e `documento_assinatura.html`: arquivo e
  assinatura na mesma peça. Disponibilidade, versão, metadados, avisos e permissões vêm
  da projeção existente. Menu canônico da via, nomes acessíveis e forms preservados.
- `.percurso-registro`: lista ordenada de trechos com data, origem/saída e destino/chegada.
  Virada de dia explícita; textos completos; sem rolagem interna ou mapa decorativo.
- `conferencia_valores.html`, `serena=True`: leitura financeira aberta sobre superfície
  clara, com total, por servidor, tipo e quantidade integrais. Outras variantes mantidas.
- UI Lab: dossiês vazio/conteúdo longo e documentos gerando/falhou; exploração A/B/C
  por `?oficio-direcao=documento|mesa|registro`. Nenhuma operação nos protótipos.

Uso limitado ao Resumo até aprovação visual do usuário. CSS na origem, tokens existentes,
sem biblioteca ou JavaScript novo. Evidências: `oficios-resumo-reconstrucao/`.

Campos `.entrada[readonly]` continuam focáveis para seleção/cópia: a variante preserva
o halo de teclado e o fundo de foco. Não tratar campo somente leitura como desabilitado.

### Refinamento da mesa — feedback humano

- Modal da mesa: `.dialogo__conteudo` é coluna; somente `.dialogo__corpo` rola.
  Identidade e ações ficam fora do scroll. A barra começa abaixo do cabeçalho;
  foco de campos precisa permanecer entre cabeçalho e rodapé.
- `dados_eprotocolo.html`, `compacto=True`: `.dados-copiaveis` usa duas colunas
  acima de 768 px, descrição inteira na linha final e ações de cópia em cada dado.
  A seleção nativa e todos os IDs/avisos permanecem. A variante padrão da Folha
  continua disponível. Não simular um input com texto solto ou remover seu foco.
- `.equipe-transporte`: servidores e transporte em cartões iguais (superfície sutil),
  logo abaixo do roteiro, na mesma coluna de leitura da viagem; acima de 768 px os
  servidores ocupam duas colunas (`auto-fit`, mínimo 15rem) e a contagem mora no
  cabeçalho do bloco (`bloco_registro.html`, parâmetro `nota`), não como rótulo solto.
- O motivo abre a coluna do roteiro e da equipe. O painel de conferência ocupa uma
  célula independente, com altura de conteúdo; não distribui as linhas da coluna de
  leitura nem tem uma segunda scrollbar (ADR 0033).
- Conferência serena usa total e `dl` financeiro, sem os filetes herdados da
  variante de indicadores. O UI Lab também usa a mesma variante de conferência.
- Registro institucional traz só os dados do documento (data, protocolo, custeio,
  porte): tipo é selo no cabeçalho e prazo pendente é alerta — não repetir em texto.
- `.registro-hero__linha`: selos ao lado do título, sem filete separando. Sobre o
  cabeçalho escuro só a SITUAÇÃO tem contorno; prazo, tipo e arquivado viram texto com
  ícone em tom sutil — informam sem disputar com o número e o destino.
- `.estacao-documental__peca` é uma linha só: documento à esquerda, estado da via ao lado
  do nome e as ações na outra ponta; detalhes da anexação e notas de conferência descem
  em faixa inteira. O hover acende a peça inteira (`:has`), não a metade esquerda.
- Estado e leitura da via são o MESMO controle: um selo clicável (`a.selo`), com alvo de
  toque mínimo (`--alvo-minimo`) e sem comportamento de link (nem sublinhado nem realce).
- A janela mostra só a emissão corrente. As versões anteriores e vias revogadas
  continuam acessíveis em "Mais ações → Histórico de documentos", em diálogo
  secundário. "Baixar documentos…" mantém o pacote da emissão corrente.
- `.dado-copiavel`: ficha, não formulário. Rótulo em caixa-alta miúda, valor sem moldura de
  input e o filete fechando a linha inteira (valor + botão). O detalhamento é bloco de
  texto (`field-sizing: content`, sem alça de redimensionar) e "Copiar tudo" permanece.

As cinco larguras e as provas de interação estão na galeria de refinamento.

## Coleção operacional e cabeçalho de página — 08/10/2026

`registro_hero.html` aceita `pagina=True` (h1), identidade opcional e uma parcial de
ações. A variante de página mantém o grafite e o filete dourado do Resumo aprovado.
O comportamento padrão do componente no modal permanece intacto.

`colecao-operacional` organiza índice, filtros e painel de resultados. Acima de
1024 px o índice temporal ocupa a lateral; abaixo permanece horizontal. Os links,
contadores OOB e filtros continuam nos mesmos componentes funcionais.

`registros--operacionais` + `registro-operacional` apresentam quatro grupos:
identidade, missão/agenda, recursos e conferência. Não combinar esta variante com
`registro--documental`, que usa outra definição de áreas de grid. Período e protocolo
não herdam áreas de grid nos agrupamentos internos. No celular, os estados ficam
em faixa própria abaixo do título, sem disputar largura com a placa; as diárias
ficam ao lado da agenda; equipe e transporte encerram o
registro. O detalhe do valor permanece visível nas cinco larguras.

Exemplos preenchido e cancelado em `/ui-lab/#operacional-lab`. Evidências reais em
`docs/visual-agents/evidencias/oficios-lista-cadastro/`. A adoção não aprova
automaticamente a estética das páginas: Lista e Cadastro aguardam revisão do usuário.

`indice_preparacao.html` recebe `itens` (chave, rótulo e estado da prontidão existente)
e `pronto`; navega por âncoras e não calcula novas etapas de negócio.
`documento--preparacao` coloca a identificação da seção à esquerda no desktop e
acima do conteúdo no celular. `secao__conteudo` preserva os invólucros HTMX internos.
`campos--registro` dimensiona número, data, protocolo, tipo e custeio por significado.
`pessoas--compactas` reaproveita o acabamento dos cartões do Resumo, mantendo ações
de motorista e remoção. `conferencia_valores.html` aceita `serena=True operacional=True`
para preparação; a mesma variante vertical permanece no Resumo. O fragmento de
diárias da Folha mantém essa apresentação depois das atualizações de equipe.

`barra-acoes--registro` oferece acabamento compacto. Em formulários longos, combinar
com `barra-acoes--fluxo`: o fechamento ocupa o fluxo normal e não intercepta campos
durante a rolagem. Salvar/minuta ficam no cabeçalho e o índice oferece acesso direto
à revisão. A Lista mantém sua barra de paginação/exportação no comportamento existente.

`historico_documental.html` recebe `prefixo`, `identificador`, `contexto` e uma parcial
`conteudo` com a projeção autorizada pelo chamador. É leitura secundária: versões
históricas não ocupam a estação corrente. O controlador nativo de diálogos coloca
a janela secundária fora da ancestral enquanto aberta, evitando herança visual e
devolve o foco ao controle existente ao fechar. Não gera, altera ou promove arquivos.
Exemplo sintético no mesmo bloco operacional do UI Lab.

## Refinamento dos componentes operacionais — 09/10/2026

- `.selo` não encolhe como item flex: é uma unidade de estado, de uma linha. Uma
  instrução longa usa `pendencia.html` (`mensagem`, `bloqueante`), com ícone, filete
  e texto que pode quebrar sem perder orientação. Não truncar instruções de erro.
- `.registro-operacional` centraliza placa e ações no desktop. A placa mantém
  número tabular e a mesma identidade em todas as situações. `.botao--menu-registro`
  tem alvo próprio, realce discreto e foco visível; no mobile usa
  `--altura-controle-lg` (2,75rem; 39,6px na escala atual de 90%).
- `.filtros__avancados--organizados` distribui campos semânticos: ordem e dois
  períodos na primeira fila; ano, protocolo, veículo e faixa de valores na segunda.
  Em tablet usa duas colunas e em mobile mantém a folha inferior original.
- `.indice-preparacao` usa trilho cinza, texto grafite, check para completo, círculo
  para conferir e `aria-current="location"` para posição de leitura. Reaproveita
  `progresso.js` sob demanda; o foco não se confunde com o item atual. Sem JS,
  âncoras e informações de prontidão permanecem disponíveis.
- `pessoa_externa.html` recebe `titulo`, `descricao`, `aberto`, `classe` opcional e
  `corpo_template`. Disclosure nativo com identificação e campos do chamador.
  Não decide vínculo, motorista, diárias ou permissão. O componente de transporte
  mantém habilitação/fechamento anteriores; os campos são extraídos sem alterações.
- `.campos.transporte` coloca meio e viatura lado a lado, com largura proporcional;
  detalhe de outro meio entra em faixa inteira. `.motorista-externo__campos` agrupa
  pessoa e referências de origem em duas colunas, uma no celular.
- `.pessoas--compactas` integra controles à lateral do cartão, visíveis em toque
  e mouse. Nome e descrição em uma linha cada, com reticências e título completo;
  mantém botões nomeados; não imita o card só de leitura.
- A divulgação gira somente o ícone de expansão `plus`; ícones de cópia ou pessoa
  permanecem na orientação correta. UF do itinerário reserva largura para duas letras.
- Checkbox e radio em `.escolha` têm alvo físico de 24px, independente da escala
  tipográfica. A preparação usa o `scroll-padding` global do cabeçalho; suas seções
  não repetem esse desconto com `scroll-margin`.

Estados em `/ui-lab/#componentes-oficios-lab`; evidências e críticas em
`docs/visual-agents/qa/oficios-componentes-2026-10-09.md`.

## Seleção em cartão — transporte

`pc-combobox[data-escolha-em-cartao]` mantém o `<select>` como valor real e deixa
a busca vazia depois de escolher. Digitar, apagar ou abandonar uma consulta não
remove a seleção existente; somente selecionar outra opção ou remover o cartão
altera o valor. Sem JS, o select nativo continua disponível.

`recurso_selecionado.html` reaproveita avatar/texto/ação dos cartões compactos;
aceita `titulo`, `meta`, `automatico`, `desabilitado` para estados no UI Lab.
Na Folha, `pc-transporte` preenche o cartão com rótulo e `data-meta` já fornecidos
pelo widget de viatura. A remoção devolve foco à busca. Escolha automática pelo
motorista mantém o toast e realça o cartão por `--duracao-enfase`; movimento
reduzido desliga a animação, preservando o texto “Selecionada pelo motorista”.

`pessoa_externa.html` também aceita `descricao_template` para metadados do vínculo.
O motorista externo existente apresenta seu nome e origem; quando a equipe tem
motorista, a opção externa fica oculta e desabilitada, em concordância com a
substituição já feita no servidor. Desmarcar disponibiliza a opção novamente.

O `pc-select` sincroniza o botão visual quando o select nativo é habilitado ou
desabilitado por uma seção condicional. O observador acompanha somente o atributo
`disabled`, é desligado ao remover o componente e retomado ao reconectá-lo.
A busca em cartão anuncia seleção/remoção na região de leitura assistiva existente.
Na busca remota, iniciar o componente retoma a consulta digitada enquanto o módulo
carregava, se o campo continua focado e não possui identificação já selecionada.
Não exige apagar e redigitar; seleção preexistente continua preservada.
Uma cópia de DOM não é uma instância inicializada: ao clonar, o componente refaz
referências, eventos e controles gerados a partir do select nativo, sem duplicá-los.
Reconectar a mesma instância preserva seus controles. Cobertura por teclado,
valor nativo, disabled e ausência de erros em `test_ui_lab.py`.

## Folha do ofício em largura inteira — 09/10/2026

A folha deixou de se dividir em duas colunas (explicação à esquerda, conteúdo à direita):
título e nota abrem a seção na largura toda e o conteúdo usa a linha inteira. A nota fica
em linha própria sob o título, limitada à largura de leitura; o selo de estado vai para a
direita. Campos, mapa, trechos e dados copiáveis rendem muito mais assim.

- Equipe em duas colunas; quem sobra numa linha ímpar ocupa a linha inteira, em vez de
  deixar um vão ao lado (`.pessoas--compactas > .pessoa:last-child:nth-child(odd)`).
- Equipe e transporte andam lado a lado: os cabeçalhos dos dois blocos têm a mesma altura
  mínima (um traz selo, o outro um interruptor), senão os cartões saem do eixo.
- O cartão de viatura tem a altura do cartão de servidor e não realça no hover: ele não é
  um alvo clicável inteiro, diferente do cartão de equipe.
- **Quem dirige se marca clicando no cartão**: o botão cobre a peça (sem desenho próprio) e
  só o X de remover fica por cima; o avatar troca as iniciais pelo ícone `volante`. O nome
  acessível ("Marcar/Desmarcar fulano como motorista") e o `aria-pressed` continuam no
  botão, então teclado e leitor de tela seguem iguais.
- Ícones próprios: `scripts/vendor_assets.py` tem `PROPRIOS`, para o que o Lucide não cobre.
  `volante` nasceu daí — o `ship-wheel` do Lucide é timão e não lê como carro.
- Histórico: linhas no mesmo ritmo dos cartões (padding `--esp-3/--esp-4`) e respiro maior
  entre a minuta e o bloco.
- Saíram da tela: o checkbox "Manter esta data na emissão" (a regra continua em
  `forms.clean` — data alterada vale como digitada; senão a emissão usa a data de hoje) e a
  ajuda do campo "Usar um roteiro cadastrado", com o `aria-describedby` que a referenciava.

## Preparação operacional — Roteiro até conclusão, 09/10/2026

Contrato em `product/oficios-cadastro-inferior.md`, ADR 0031. Variantes ativadas na
Folha e demonstradas no UI Lab; os consumidores sem a variante mantêm a composição.

- `selecao_roteiro.html`: divulgação nativa com busca, origem e POST existente.
  Aberta para registro sem origem de roteiro; escolha aplicada mantém o aviso.
- `_itinerario.html` com `operacional=True`: sequência numerada, destinos e mapa
  lado a lado no desktop, percurso antes do mapa no celular; trechos em largura
  inteira. `_parada.html` mantém os controles de ordem, exclusão, UF e município.
- `.itin__ajustes`: durações agrupadas com chegada calculada como resultado.
  `.conferencia-serena--operacional`: total, metadados e composição de diárias em
  faixa compacta, sem criar uma nova fórmula ou esconder o cálculo.
- `formulario_contextual.html`: slots de contexto e campos. Obrigatória, dispensada
  com texto preservado, erro e desabilitado aparecem no UI Lab. Na Folha, utiliza
  os campos e os modelos de texto existentes da justificativa.
- `prontidao_documental.html`: recebe prontidão já calculada, pendências e ação
  da revisão; aceita `conferencia_id` para múltiplos exemplos. Não decide emissão.
  A faixa antecede os dados copiáveis existentes, preservando os campos individuais
  e o conjunto do eProtocolo.
- `modos_documento.html` e `.editor--operacional`: modos Texto/PDF, ações e grupos
  de ferramentas identificados. Mantêm ids, toolbar, comandos, versões e carregamento
  sob demanda. Hover selecionado usa contraste inverso coerente. Nenhuma alteração
  no HTML oficial, PDF, conteúdo ou paginação institucional.
- `.historico__linhas--operacional`: data completa, horário, evento e autoria.
  Desktop com autoria em coluna; celular com autoria sob o evento. Histórico
  completo continua acessível por divulgação nativa; nenhuma consulta nova.
- `estado_salvamento.html` e `.barra-acoes--preparacao`: região única de feedback,
  visível e anunciada, com Finalizar, Voltar e Ações. A variante mantém o status
  no fluxo em todos os estados para evitar deslocamento durante cliques. Barra
  estática; não cobre campos. `rodape_documento.html` aceita `finalizar_primario`.

O índice lateral do UI Lab limita a própria altura e permite rolagem, mantendo
alvos inteiros abaixo do cabeçalho mesmo ao chegar ao fim da vitrine.
Evidências reais, críticas e logs em `visual-agents/qa/oficios-cadastro-inferior-2026-10-09.md`.

## Resumo alinhado à folha — 09/10/2026

A mesa do Resumo passou a falar o mesmo vocabulário da folha de cadastro:

- Diárias: o total é o bloco escuro centrado com tipografia fluida (`clamp`), os dados
  centrados embaixo — o mesmo desenho do bloco de diárias da folha. O painel perdeu a fita
  dourada e ganhou moldura sutil com raio (`--raio-lg`).
- Documentos: largura inteira, com o cabeçalho dos demais blocos (`bloco-registro__cabecalho`:
  título em caixa-alta e a nota "Arquivo da viagem" ao lado), sem a coluna lateral de rótulo.
- Equipe e Transporte: dois sub-blocos com rótulo em caixa-alta; cartões em duas colunas, o
  ímpar ocupando a linha inteira; o cartão da viatura é idêntico ao do servidor (43px).
- Aviso de data na revisão: sem referência ao checkbox "Manter esta data na emissão", que saiu
  da folha — a instrução agora é alterar a data do ofício ali (a data informada passa a valer).
- Roteiro cadastrado (`selecao_roteiro.html`): sem gaveta — o `details`/`summary` repetia o
  rótulo do campo. Virou a linha inteira da seção: a origem (ou o convite) em cima e, embaixo,
  o campo de busca com o botão "Usar este roteiro" na mesma altura (36px os dois). No celular
  o botão desce e alinha à direita; sem rolagem horizontal.
- Consulta do registro (ADR 0033): Motivo, Roteiro e Equipe fluem juntos em
  `.mesa-registro__principal`. A lateral tem altura de conteúdo, sem `100cqb`, distribuição
  em frações ou rolagem própria. O corpo concentra a rolagem e mantém header/ações fora dela.
- `conferencia_valores.html`, `consulta=True`: total grafite principal, valor por servidor
  secundário, destino e composição como metadados. A variante operacional do Cadastro é
  preservada. O dossiê do UI Lab usa a mesma composição de consulta.
- `.estado-documental`: vazio informativo compacto com ação disponível. Não confunde
  minuta com emissão; peças correntes mantêm versão, assinatura, falha e retry.
- `.colecao-operacional--consulta`: header compacto limitado ao header da página,
  recortes temporais horizontais e resultados em fluxo natural. Barra `--colecao` acompanha
  apenas resultados paginados (`--acompanha`); listas curtas encerram sem altura artificial.
- Registro operacional: largura estável da placa e da coluna financeira por breakpoint;
  dinheiro integral, composição como metadado. Quinas independentes de listas embutidas em
  cartões. Situação, condição e tempo têm pesos distintos.
- Dados para o eProtocolo novamente no Resumo, conforme a missão de consulta de 09/10:
  divulgação compacta com cinco campos da projeção autorizada. Protocolo também no header;
  o poll continua limitado a documentos/rodapé, preservando foco e a divulgação da cópia.
- Roteiro da mesa (`percurso-registro`) como cartão de embarque: a saída à esquerda (hora
  grande, lugar embaixo), a chegada à direita alinhada ao fim da linha, e entre as duas o fio
  dourado com o carro e a duração do trecho (`duracao_curta`: "9h30", "45 min"). Chegada em
  outro dia leva a data pequena ao lado da hora. O dia mora na margem; filete sutil entre
  trechos, sem cartão nem fita lateral. No celular o fio encurta e a hora desce um degrau.


## Cadastro inferior — variantes revisadas em 09/10/2026 (ADR 0032)

- `selecao_roteiro.html`, `compacto=True`: recurso integrado, contexto/origem ao lado
  da busca no desktop, controles proporcionais no celular. A ação mantém o nome
  acessível Usar este roteiro, mesmo quando o rótulo visível é Aplicar.
- `painel_rota.html`: mapa, enquadramento, fonte e métricas Ida/Ida e volta;
  consumido pelo itinerário operacional. Sem cálculo ou requisição própria.
- Itinerário operacional: percurso identificado à esquerda no desktop; saída,
  duração e chegada calculada à direita. No mobile a chegada separa dia e hora;
  sem JS a chegada calculada continua mostrando a data/hora integral.
- `formulario_contextual.html`, `classe="formulario-contextual--redacao"`: contexto
  do prazo, redação e texto pronto. Estado obrigatório/dispensado pertence ao fluxo.
- `preparacao-documental--conferencia`: decisão de emissão antes da transferência
  de dados, sem coluna vazia ou cartões por pendência.
- `dados_eprotocolo.html`, `compacto=True`: cinco campos readonly, cópia individual
  e `acao_copiar_tudo.html` no cabeçalho. Fallback de seleção e IDs preservados.
  A divulgação abre por solicitação, evitando uma área longa de transferência
  antes do editor. Autosave e HTMX preservam a escolha do usuário.
- Editor operacional: grupos Formatação/Fonte/Parágrafo/Inserir/Versões nomeados,
  estado e identidade no cabeçalho, controles recolhíveis em telas estreitas.
  Não modifica o papel oficial, geração de PDF ou histórico de versões.
- Histórico operacional: trilho, data/hora, fato e autoria; mobile com data acima
  do fato. A barra de preparação permanece no fluxo, sem encobrir campos.

Vitrines existentes do itinerário, editor, cópia e Preparação documental usam as
variantes reais. Capturas e resultados desta rodada em
`../visual-agents/qa/cadastro-inferior-r2-2026-10-09.md`.
## Propagação de 10/10/2026

Roteiros reutiliza `colecao-operacional--consulta`, `registro-operacional`,
`identidade_documental`, `registro_hero`, `painel_rota`, itinerário operacional e
conferência horizontal. Mantém a busca, OOB de abas, menus, popover de vínculos,
formulários e endpoints. O rodapé passa a integrar o fragmento de resultados.

`registro-hero__metadados`/`__metadado`: grupo flexível de metadados sobre grafite,
com contraste inverso e ícones institucionais. Primeiro consumidor: folha de
Roteiros. `estado_salvamento` aceita `sem_emissao=True` para registros reutilizáveis;
o padrão de Ofícios continua anunciando suas pendências documentais.

A seção de Diárias sob `[data-previa-diarias]` mantém o mesmo alinhamento após
troca assíncrona. `_diarias.html` aceita a variante operacional também na seção
numerada; novo/edição e endpoint de prévia de Roteiros passam a mesma variante.
Variantes não operacionais permanecem enquanto houver consumidores reais.

`registro-operacional__conferencia`: sem contenção intrínseca que anule a largura
da coluna financeira. Mobile usa duas colunas proporcionais para agenda/valores;
valor alto e composição longa possuem verificação de overflow interno, além do
overflow da página. Consumidores: Ofícios, Roteiros e exemplos do UI Lab.
O exemplo antigo de Roteiro e as regras exclusivas `registro__meta--roteiro` foram
substituídos; estilos de Termos e demais listas permanecem até sua migração.

### Termos — composição documental e relações

- `registro-operacional--relacoes`: identificação, destino/agenda, relações e menu;
  não reserva coluna financeira. Consumidores: lista de Termos e vitrine do UI Lab.
- `campos--conteudo-periodo`: texto/tipo e período, com largura útil para o calendário;
  duas colunas a partir de 768px, uma no celular.
- `preparacao-relacoes`: equipe e transporte integrados, duas colunas a partir de
  1024px. Não substitui semânticas diferentes de motorista nos Ofícios.
- `_campo_equipe(compacta=True)`: cartões em uma/duas colunas, nome e cargo sem
  quebra, conteúdo integral no DOM/title e remoção pelo botão existente. Variante
  explícita vence a antiga grade de seis colunas sem alterar outros consumidores.
- `_campo_viatura(cartao=True)`: cartão canônico dentro do controlador quando não
  estiver envolvido pelo controlador de Ofícios. Evita cartões ou controles duplicados.
- `campo_destinos(..., operacional=True)`: destinos numerados, UF/município e
  `painel_rota`. OS, Planos e Viagens mantêm compatibilidade anterior até migrarem.
- Editor/histórico/barra de preparação: mesmas variantes operacionais de Ofícios,
  com documentos individuais, genérico e viatura preservados; barra no fluxo.

Vitrine de Termos substitui o registro anterior. Removidas quatro regras exclusivas
`registro__meta--termo`, após migrar ambos os consumidores, testar e retestar.
Contrato, capturas e limitações em `../visual-agents/qa/termos-identidade-2026-10-10.md`.

### Ordens de Serviço — consumidor seguinte

OS usa `registro-operacional--relacoes`, `campos--conteudo-periodo`,
`campo_destinos(operacional=True)`, equipe compacta, preparação, editor e histórico
operacionais. Mantém funções individuais por servidor e seu único documento;
não força transporte ou painel financeiro sem significado. Identidade documental
usa a numeração anual própria. A barra final permanece no fluxo, com estado real
salvo; menu e confirmações continuam nos componentes existentes.

Não há CSS/JS novo nem implementação exclusiva removível nesta página. As bases
antigas compartilhadas continuam para consumidores ainda não migrados. Evidências
em `../visual-agents/qa/ordens-identidade-2026-10-10.md`.
# Identidade documental: complemento e observação de registro

`identidade_documental.html` aceita `complemento` opcional: sufixo institucional
apresentado abaixo do número, sem cortá-lo nem ampliar a coluna. Consumidor atual:
Lista de Planos; exemplo UI Lab com `1250/2026` e `ASCOM`. Sem alteração para
Ofícios/Roteiros/Termos/OS que não enviam complemento. Número completo permanece
no texto acessível do link. Usa tokens, contraste inverso e quebra segura do sufixo.

`registro-operacional` distribui `.registro__texto` na largura do registro: útil
para motivo de cancelamento, sem ocupar a célula da placa quando corpo é contents.
Consumidores diretamente migrados: Planos; todos os registros canônicos recebem
compatibilidade sem mudar campos, ações ou os grid areas principais.


## Preparação de Planos e eventos — 10/10/2026

- `registro_hero(complemento_numero=...)`: sufixo institucional explícito, secundário;
  identificação completa no h1 acessível. Auxiliar editorial não é sufixo documental.
- `registro-hero__metadado`: ícone/texto/ligação com contraste inverso, usado em Planos,
  Termos, OS e Roteiros. Variante `--vazio` discreta sem reduzir contraste por opacity.
- `campos--agenda`: conteúdo, período e horário; escolha livre na linha seguinte.
  Folha e diálogo de evento compartilham a composição; exemplo interativo no UI Lab.
- `campos--coordenacao`: origem/tratamento proporcionais e pessoa ou campos manuais;
  uma coluna no celular, duas no tablet; desktop reserva largura para ler origem
  e tratamento completos. Preserva controles condicionais existentes. Não define
  gênero ou regras novas.
- `secao__bloco--integrado`: tira divisão/margem duplicada de agrupamentos internos
  numa preparação contínua. Consumidor atual: Planos.
- `conferencia_preparacao`: recebe pendências calculadas e ação ligada a formulário
  externo. Não calcula políticas. ID configurável para não colidir com o UI Lab.
- Eventos usam `registro-operacional`, com destinos completos no title e nome
  acessível, diárias próprias e menu existente. Não agregam composições financeiras.
- `linhas__linha`: coluna quantitativa móvel ampliada para acomodar controles e 999.
  Consumidores reais: efetivo do Plano, diálogo de evento e UI Lab; desktop preservado.
- Editor usa `operacional` e `ferramentas_recolhiveis`, histórico e barra no fluxo.
  Miniaturas, Texto/PDF, versões, downloads e documento oficial preservados.

Nenhuma base genérica antiga removida: ainda há consumidores em Viagens e Resultados.


## Lançamentos quantitativos — 10/10/2026

`lancamento_quantitativo.html` apresenta atividade, referência/meta, quantidade e
observação. Recebe identificador e prefixos do formulário consumidor; distingue
valor ausente, zero e texto inválido devolvido pelo servidor. Não calcula nem salva.
Consumidores: Resultados de Planos e UI Lab. `tabela--lancamentos` permite comparação
em colunas no desktop e agrupa rótulos/campos no celular e tablet. O cabeçalho segue
acessível. Rótulos responsivos usam classe própria, sem reaproveitar `sr-only` para
conteúdo que precisa aparecer. `leitura-textual` limita largura de leitura sem nova
caixa. Barra manual usa o padrão no fluxo, sem cobrir relatório.

Implementação exclusiva antiga: `tabela--resultados` e `relatorio-final`, substituídas
por esses dois padrões; removidas após prova de consumidores e sete E2E pós-limpeza verdes, registrados em QA.


## Coleção de Justificativas — 10/10/2026

A variante `abas--conteudo` usa largura intrínseca dentro do índice da coleção de
consulta para dimensões com poucas alternativas. Consumidores: Justificativas e
UI Lab (Todas/Pendentes/Preenchidas). Não é o componente ARIA de painéis: são links
GET, com estado `aria-current`, busca HTMX e contadores OOB existentes.

Registros reaproveitam identidade documental compacta e variante de relações;
estado do texto (Pendente/Preenchida) é separado do estado documental e do prazo.
Diálogo conserva gravação manual, texto pronto, versão e erros; metadados usam
`metadados`. Não cria entidade ou editor de justificativa novos.

`paginacao.html` aceita `paginacao_destino` opcional: prefixo de rota para páginas
que também renderizam em uma URL de POST/erro. Ausente, conserva o contrato
relativo anterior. Justificativas informa sua lista; demais consumidores mantêm
seus endereços. IDs e querystring_base continuam do consumidor.


## Registro operacional sem menu de linha — 10/10/2026

`registro-operacional--sem-acoes` é uma variante de `registro-operacional--relacoes`
para registros cuja única ação é abrir o detalhe. Consumidores: Lista de Viagens e
UI Lab `_registro_viagem.html`. Retira a coluna reservada ao menu nas três composições
responsivas; não esconde controles existentes. Placa data/ID usa identidade documental
compacta, sem atribuir número oficial ao agrupador Viagem. Situação é badge e tempo é
metadado com relógio. Vínculos de Ofícios, OS e Planos ficam em grupo secundário.
Busca/abas são os mesmos componentes canônicos; barra de criação dentro do fragmento
HTMX atualiza contagem e permanece no fluxo nas listas curtas.

## Preparação e documentos relacionados — Viagens, 10/10/2026

`documento--preparacao` aceita seções dentro do formulário `formulario--secoes`,
sem trocar IDs, nomes, CSRF ou regiões de salvamento. Consumidor novo: Folha de
Viagens; o lote usa seções diretamente no formulário. O hero recebe a identidade
data/ID e contexto da Viagem; seu contêiner `data-vivo` mantém o título atualizado
depois do autosave, junto da frase de contexto existente.

`campo--documentos` especializa as opções `caixas` para vínculos de documentos:
lista compacta com divisórias sutis, seleção neutra e foco preservado. Consumidores:
Folha de Viagens e UI Lab. Não altera a busca nem o limite de candidatos do servidor.

`relacoes-documentais` reaproveita `peca-documental` para abrir registros vinculados,
com estado e período, inclusive relações indiretas pelo Ofício. Não representa um
download nem declara um arquivo corrente. `secao__grupo--relacoes` distribui grupos
em duas colunas a partir de768px; o último grupo ímpar ocupa a linha toda. Cada lista
interna mantém largura integral, sem reservar meia coluna para um único documento.

`conferencia_etapas.html` recebe etapas/itens/links já calculados pelo domínio.
Não define regras de prontidão; `conferencia-etapas` agrupa as pendências sem um
cartão por mensagem e mantém o alvo mínimo de toque nos links. Consumidores: Folha
de Viagens e exemplo do UI Lab. Histórico operacional e barra de ações no fluxo
usam os padrões já migrados. Equipe compacta e cartão de viatura no lote usam os
mesmos seletores de Ofícios, preservando campos e comportamento.

## Diário de Bordo e cabeçalho documental — 12/10/2026

O Diário usa `registro_hero`, `documento--preparacao`, `metadados`, `pc-select`
e `barra-acoes--preparacao barra-acoes--fluxo`. A barra mantém o estado real de
salvamento também no celular. `Finalizar` aguarda a gravação e retorna à lista;
não finaliza prestações de contas.

`diario-linha` continua sendo a implementação única de linha de percurso no
Diário e no UI Lab §15. A variante `diario-linha--hodometro` agrupa km de saída,
km de chegada e abastecimento, com `diario-linha__resultado` para a distância
rodada. Apenas o resultado tem `data-vivo`: atualizar o cálculo não substitui
o input com foco. Horários realizados preservam saída e chegada editáveis;
na consulta, a mesma linha usa metadados de saída/chegada.

`modos--recurso` organiza opções de motorista e viatura em colunas paralelas.
Os campos condicionais usam duas colunas, primeiro campo completo e último
campo isolado completo. A classe base `modos` permanece necessária no Relatório
Técnico, com fallback sem `:has`; a variante não altera seus consumidores.

Entre768 e1023px, cabeçalhos de página com identidade e múltiplas ações distribuem
as ações numa segunda linha. Um único menu permanece ao lado do conteúdo.
Isso preserva a largura do título e metadados sem criar uma linha só para um menu.
Consumidores: Ofícios, Roteiros, Termos, OS, Planos, Viagens e Diário. Resumos
em modal e listas sem identidade não entram nesse contrato. Não há JS novo.

## Registro de valor individual e texto pronto por opções — PR03

`registro_valor.html` mantém título e referência fora do rótulo flutuante curto.
Aceita `titulo`, `referencia_rotulo`, `referencia`, `rotulo`, `ident`, `valor`,
`editavel`, `travado` e `estado_leitura`. Não calcula nem mascara moeda: o RT
aceita observação textual. Referência tem ID e `aria-describedby` no campo;
o nome acessível inclui a pessoa. Variante de leitura não renderiza input.
Consumidores: Relatório Técnico e UI Lab16. A antiga grade de inputs com nomes
longos no label foi substituída; `grade-campos` não tinha outros consumidores.

`texto_pronto.html` continua aceitando campo Django; alternativamente recebe
`opcoes` em tuplas `(pk,nome,texto)` e `rotulo`, reutilizando seletor, ações,
marcadores data-* e diálogo existentes. Não cria novo comportamento JS.
Consumidores da alternativa: RT; contrato original: Ofícios, OS, Justificativas.

`peca-documental--acoes` apresenta arquivo individual e múltiplos formatos de
download. Ícone/nome ocupam a primeira linha no celular e ações continuam
visíveis abaixo. Não representa versão, assinatura ou geração assíncrona.
Consumidores: documentos do RT e UI Lab16; base documental permanece a mesma.

`peca-documental__edicao` reserva uma linha completa para divulgação de
metadados editáveis. Consumidor inicial: comprovantes em Documentos da prestação;
UI Lab16 demonstra a expansão. Não usar registro__corpo/registro__link na peça:
essas classes carregam grid-area mobile e área de clique de outro componente.
Links de arquivo são explícitos e ações permanecem operáveis fora deles.

`barra-acoes--confirmacao` usa distribuição flexível para retorno e confirmação
sem status de salvamento entre eles. Combinar com preparação/fluxo em formulários
de envio nativo. Não reserva uma coluna de autosave nem estica o botão principal.
Consumidores: fallback de via assinada e demonstração no UI Lab.

### Painel operacional — composição de filas

O arquétipo `arquetipos/painel.html` permite sobrescrever
`classe_layout_painel` e `classe_contexto_painel`. Os valores padrão mantêm
a composição com lateral dos consumidores anteriores. Viagens utiliza
`pilha-lg` e `pilha`: filas em largura inteira e contexto no fluxo.
Cada fila reutiliza `colecao-operacional` e `registros--operacionais`, sem
cartão externo. Não omitir a classe operacional ao incluir `_registro.html`:
ela participa do contrato visual de placa, recursos e conferência.
Atalhos podem usar `grade grade--2` para duas colunas responsivas, mantendo
links/botões e nomes acessíveis. Não há script nem folha de estilo adicional.

`componentes/vazio.html` aceita `compacto=True` para filas secundárias.
A variante preserva título, texto, ícone e ações; usa ícone menor sem brilho,
mensagem alinhada à esquerda e altura pelo conteúdo. Consumidores iniciais:
duas filas do Painel de Viagens e demonstrações do UI Lab, com e sem ação.
O padrão centralizado continua inalterado para listas vazias de página inteira.

### Folha documental larga em tela

`folha.css` mantém a largura mínima intrínseca do papel para acomodar pares
indivisíveis do modelo oficial. Não reduz a tipografia nem quebra esses pares.
`data-folha-inteira` conserva rolagem horizontal no iframe e delega a vertical
à página externa. A altura vem do corpo e da margem inferior, reservando a barra
horizontal; não deve acumular altura ao recalcular. O PDF não carrega essa folha
de estilo de apresentação. Consumidores: Ofícios/Justificativa, Termos, Ordens
e Planos; a apresentação do aviso sem documento também usa `folha.css`.
