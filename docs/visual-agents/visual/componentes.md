# Catálogo de componentes — NOVO × LEGADO, com recomendação

> Agente 2 — UI/UX Design Lead · 2026-10-06 · etapa de estudo (nenhum código alterado).
> Fontes: `/ui-lab/` (`gestao/ui_lab/templates/ui_lab/indice.html`), `templates/componentes/`,
> `templates/arquetipos/`, `static/css/*.css`, `static/js/componentes/*.js` (NOVO);
> `templates/components/`, `templates/components/v32/`, `static/js/` (LEGADO, só leitura).
> Legenda da recomendação: **USAR** (canônico) · **CONSOLIDAR** (juntar variantes / tirar do
> template) · **CORRIGIR** (defeito) · **TRAZER** (existe no legado, falta no novo) ·
> **ELIMINAR** · **DOCUMENTAR** (existe e é usado, mas falta no UI Lab ou nos docs).

## 1. Estrutura de página (arquétipos e parciais)
| Componente | Onde | Situação | Recomendação |
|---|---|---|---|
| Arquétipo LIST | `templates/arquetipos/lista.html` | base de Ofícios, Roteiros, Termos, Ordens, Planos, Viagens, cadastros | **USAR**. Escreve o cabeçalho à mão em vez de incluir `componentes/pagina_cabecalho.html` |
| Cabeçalho de página | `componentes/pagina_cabecalho.html`, `.pagina-cabecalho` (`layout.css` l. 496) | o parcial existe mas o arquétipo e as folhas (roteiro, termo, ofício) repetem o HTML | **CONSOLIDAR**: um parcial com variantes "lista" (h1 visível + descrição) e "folha" (placa grande + h1 sr-only + frase + ações) |
| Arquétipos FORM/DETAIL/… | `templates/arquetipos/*.html` | o produto usa a folha `.documento` + barra; `formulario.html` (índice lateral) só no catálogo | **DOCUMENTAR** que a folha é o arquétipo real das edições |
| Migalhas | `componentes/migalhas.html` | ok | **USAR** |
| Barra de ações | `.barra-acoes` (`layout.css` l. 590–700); `componentes/rodape_documento.html` | listas de Viagens e todas as folhas | **USAR**. `docs/design-system/page-archetypes.md` ainda diz "ação primária no cabeçalho, nunca flutuante" — **DOCUMENTAR** a decisão nova (Novo… na barra) ou revertê-la; outros módulos (Eventos, Imprensa, Palestras, Publicações, Coffee, Cadastros) ainda põem a ação no cabeçalho (`block acoes_lista`) |
| Estado vazio | `componentes/vazio.html` | 3 variantes + `acao_template` | **USAR** |
| Paginação | `componentes/paginacao.html`, `.paginacao` | ok; alvos 33×29px | **USAR** |
| Resumo de erros | `componentes/resumo_erros.html` | ok | **USAR** |
| Voltar à tarefa | `componentes/voltar_tarefa.html` | atalho flutuante canto inferior esquerdo | **USAR** |

## 2. Listas (`static/css/listas.css`)
| Componente | Classe / arquivo | Uso | Recomendação |
|---|---|---|---|
| Registro (linha-cartão) | `.registros > .registro` (+ `.placa`, `__corpo`, `__titulo`, `__link`, `__meta`, `__meta-item`, `__acoes`) | 40 templates em 11 apps | **USAR + CORRIGIR** (abaixo) |
| Registro: defeito de seletor | `listas.css` l. 596: `.registro--inativo .registro__link,` emendado ao bloco `.registro__notas` | 22 templates (cadastros ×6, coffee ×3, eventos ×3, imprensa, painel ×2, palestras, publicações, viagens: ordens, termos, viagem, planos, anexos) | **CORRIGIR**: título inativo vira `display:grid` + margem 7,2px e não recua de cor |
| Registro: ⋮ esmaecido | `.registro__acoes { opacity: .6 }` | todas as listas | **CORRIGIR**: ícone fica ≈2,6:1 sobre branco (< 3:1, WCAG 1.4.11). Opacidade 1 sempre; o realce do hover pode ficar no fundo do botão |
| Registro: celular | `@media (max-width:767.98px)` l. 693 | todas as listas | **CORRIGIR**: placa + ⋮ ocupam uma linha própria (~36px perdidos por linha) — ver `oficios-lista.md` P10 |
| Registro: estático | `.registro__link--estatico` | Roteiros sem permissão/cancelado | **USAR** |
| Registro: item-ação | `.registro__meta-item--acao` + `.menu--pousar` | Roteiros "Usado em N ofícios" | **USAR**; **DOCUMENTAR** no UI Lab |
| Registro: expansão em linha | `[data-expandir]`, `.registro__extra` | **não existe mais** no código; `components.md` e `explorations.md` ainda a descrevem | **ELIMINAR** do doc (o resumo virou janela `dialogo--resumo`) |
| Grupo por mês | `.registros__grupo` (preso ao topo) | Ofícios, Planos | **CORRIGIR**: `z-index:1` empata com `.registro__acoes` (`z-index:1`) — os ⋮ das linhas que passam por baixo pintam **por cima** do cabeçalho preso (visto a 1440 e 390). **DOCUMENTAR** no UI Lab (não está) |
| Cabeçalho da lista | `.lista-cabecalho` (+ `__total`, `__nota`) | todas | **USAR**; o h2 repete o h1 ("Ofícios" · "Ofícios") — tornar `sr-only` quando não há busca |
| Filtros (barra) | `.filtros`, `.filtros__busca`, `.filtros__campo`, `.filtros__acoes[data-so-sem-js]` | todas | **USAR** |
| Mais filtros (gaveta) | `details.filtros__mais` + `.filtros__avancados` (flutuante) | Ofícios e 5 listas fora de Viagens | **CORRIGIR + DOCUMENTAR**: abre sozinha quando há filtro ativo e cobre a lista; não está no UI Lab |
| Fichas | `.ficha`, `.ficha--ativa`, `.ficha__remover`, `.ficha__contagem` | refino da busca (Ofícios), filtro "Ofício N" (Termos) | **USAR** para **filtros ativos** (hoje só no catálogo: `.filtros-ativos` em `ui-lab.css`) — ver `oficios-lista.md` P1 |
| Refino da busca | `.refino` + `_refino.html` | Ofícios | **USAR**; candidato a todas as listas com número (Termos, Ordens, Planos) |
| Faixa de valores | `.filtros__faixa` | Ofícios (Diárias) | **CORRIGIR**: rótulo `span` acima do campo, fora do padrão "rótulo na borda" (desalinha a linha do painel) → `fieldset` com `legend` na borda, como `.opcoes` |
| Carregando lista | `.lista-resultados.htmx-request` | todas | **USAR** |
| Resumo (janela) | `.resumo*`, `viagens/oficios/_resumo.html`, `_dialogo_resumo.html` | Ofícios (lista, roteiros) | **USAR**; candidato para Termos/Roteiros se a regra "título abre o resumo" for adotada |
| Prestação, atalhos de atenção | `.prestacao-*`, `.atalhos-atencao*` | Prestação de contas | específico; **mover** para um CSS de página (não é "lista") |

## 3. Componentes gerais (`static/css/components.css`)
| Componente | Classe / elemento | Recomendação |
|---|---|---|
| Botão | `.botao` (`--primario`, `--marca`, padrão, `--sutil`, `--texto`, `--perigo`, `--icone`, `--sm/--lg`) + `acao.js` | **USAR**. Regra: `--marca` (dourado) só para concluir ("Finalizar", "Emitir"), nunca para criar |
| Selo | `.selo` + tons + `--situacao-rascunho/emitido/cancelado`, `--processo`, `--sem-ponto` | **USAR + CONSOLIDAR**: `selo--neutro` é usado em 16 templates/tags mas **não existe** no CSS (cai no padrão por sorte); criar um tag `selo_situacao` e um `selo_tempo` para que nenhuma tela monte selo à mão |
| Placa | `.placa`, `--grande`, `--cancelada`, `--campo` | **USAR + CORRIGIR**: rótulo a 8,1px efetivos (literal `0.5625rem`, fora dos tokens de tipo); `--cancelada` tacha também o rótulo "OFÍCIO" |
| Abas | `.abas` / `.aba` / `.aba__contagem`; `<pc-abas>` (ARIA tabs) | **USAR + CORRIGIR**: sem indício de rolagem quando transbordam; foco é um retângulo de cantos vivos (`outline-offset` negativo), fora do anel do DS |
| Menu | `<pc-menu>` (`menu.js`), `.menu__painel` (`--esquerda`, `--acima`, `--forcar-*`), `.menu__item(--perigo)`, `.menu__separador`, `.menu__titulo`, `.menu--pousar` | **USAR**. **TRAZER** do legado o item com descrição (título + linha de ajuda) para ações de efeito não óbvio (retificar, arquivar, importar) |
| Diálogo / gaveta | `dialog.dialogo` (`dialogo.js`), `--resumo`, `.gaveta` | **USAR** |
| Diálogos prontos | `dialogo_motivo`, `dialogo_baixar` (+`baixar.js`), `dialogo_assinado` (+`assinado.js`), `dialogo_guardar_texto`, `dialogo_horario`, `dialogo_servidor`, `dialogo_viatura`, `dialogos_cadastro`, `cadastro_rapido` | **USAR**. Ofícios inclui `dialogo_baixar` e `dialogo_assinado` na lista mas o menu ⋮ não os abre |
| Alerta, toast | `.alerta`, `<pc-toasts>` | **USAR** |
| Campo | `.campo`, `.campo__rotulo` (na borda), `.entrada`, `.entrada-composta`, `.campos` + `campo--xs…lg`, `componentes/campo.html`, `campo_senha.html` | **USAR** |
| Seletores | `<pc-data>` (incl. `data-periodo`), `<pc-hora>`, `<pc-select>`, `<pc-combobox>`, `<pc-multiescolha>`, `<pc-escolhas>` | **USAR** |
| Cartões de escolha | `fieldset.opcoes > label.opcao` | **USAR** |
| Cartão | `.cartao` (+ `__cabecalho/__titulo/__corpo/__rodape`) | **USAR**; `cartao__numero` só no catálogo (folhas usam `secao__numero`) |
| Indicador (KPI) | `.indicador`, `.grade--kpi` | **USAR** |
| Tabela | `.tabela` (`--compacta`, `--responsiva`, `--aberta`) | **USAR** onde há colunas comparáveis (relatórios, diárias) |
| Paleta de comandos | `<pc-comandos>` | **USAR** |
| Pessoa / avatar | `.pessoa`, `.avatar` | **USAR** |
| Esqueleto | `.esqueleto*`, `.girando` | **USAR** |
| Segmentado | `.segmentado` | **USAR** (candidato a filtro "tempo da viagem", ver `oficios-lista.md` P6) |
| Dica | tooltip (`components.css` l. 2246) | **USAR** para metadados truncados (hoje truncamento não existe) |

## 4. Folha de documento (`documento.css`, `formulario.css`, `itinerario.css`, `editor.css`)
| Componente | Recomendação |
|---|---|
| `.documento` / `.documento--cartoes`, `.documento__guia` (`guia.js`) | **CONSOLIDAR** em `--cartoes` (Ofício e Termo já usam; Roteiro ainda é folha única) |
| `.secao`, `__cabecalho`, `__numero`, `__titulo(--institucional)`, `__estado`, `__nota`, `__bloco(-cabecalho/-titulo)`, `--ok` | **USAR** |
| `p.frase-oficio` (+ `__item`, `--vazio`, `__valor`) | **USAR**; nome é do ofício mas serve a roteiro e termo — renomear para `.frase` quando houver refatoração |
| `nav.progresso(--fixo)` (`progresso.js`) | **USAR** em folhas longas |
| `.conferencia`, `.checklist` | **USAR** |
| `<pc-itinerario>`, `<pc-destinos>`, `mapa-rota.js`, `<pc-transporte>` | **USAR** |
| Editor de documento (`<pc-editor-documento>`, `editores.js`) | **USAR** |
| `.linha-tempo`, `.historico__linhas` | **CONSOLIDAR**: o termo usa `historico__linhas` + `_evento.html` do ofício; documentar um só |

## 5. Comportamentos JS sem elemento próprio
`autosave.js`, `protecao.js` (sujo/saída), `registro.js` (resumo, destaque, continuidade da placa),
`limpar.js` (× na busca), `mascara.js`, `copiar.js`, `sugerir.js`, `texto-pronto.js`,
`baixar-arquivo.js`, `painel-flutuante.js`, `oficios-irmaos.js`, `termo.js`, `passos.js`,
`esvaziar.js`, `diaria.js`, `conjuntos.js`, `linhas.js` (`<pc-linhas>`), `shell.js`. → **USAR**.

## 6. O que o LEGADO tem e o NOVO não tem (candidatos a TRAZER)
Nomes de arquivos do legado só como referência de comportamento — nada é copiado.

| Legado | O que faz | Avaliação para o NOVO |
|---|---|---|
| Fichas de filtros ativos (`.chips.filtros-ativos` na lista de ofícios) | cada filtro aplicado vira ficha removível **fora** da gaveta | **TRAZER** (já há `.ficha`) — resolve P1 da lista |
| Item de menu com descrição (`<b>` + `<small>`) | "Retificar ofício — Atualizar o estado de retificação" | **TRAZER** como `.menu__item--descrito` para ações não triviais |
| Ícone-atalho da linha (`components/icone_documento.html`) | o quadrado à esquerda abre direto o editor do documento | **NÃO TRAZER**: a placa cumpre o papel de âncora visual; atalhos ficam no ⋮ |
| Importar processo do eProtocolo + faixa "solte o PDF aqui" sobre a lista | arrastar o PDF sobre a lista/linha | **TRAZER** (paridade; Agente 1 confirma) — exige componente novo de "zona de soltar" no UI Lab |
| "Numeração" (ação de gestor no cabeçalho) | ajustar a sequência de números | paridade a confirmar pelo Agente 1 |
| `filtro_fc` (botão "rótulo + valor atual") | filtro compacto que mostra o valor escolhido | **AVALIAR** para o celular (um botão "Situação: Todos" no lugar de 7 abas roladas) |
| `cad_rail` (trilho lateral de situações) | situações numa coluna à esquerda | **NÃO TRAZER** (ADR 0006: nada lateral permanente; abas cumprem) |
| `date_multi` (várias datas soltas num calendário) | datas não contíguas | **TRAZER** quando algum fluxo pedir (não é o caso da lista) |
| `endereco_campos`, `upload_anexos`, `copiaveis`, `preencher_por_email`, `triagem_email`, `andamento_*`, `historico_status` | formulários de outros módulos | fora de Viagens; avaliar por módulo |
| `lista_escolha`, `multi_pick`, `nome_sugerido`, `summary_card`, `avisos_conflito`, `historico_alteracoes`, `section_card`, `page_header`, `breadcrumb`, `paginacao`, `dialogo_*` | — | **já cobertos** no NOVO (`pc-multiescolha`, `pc-combobox`, `.indicador`, `.alerta--aviso`, `.linha-tempo`, `.secao`, cabeçalho, migalhas, paginação, diálogos) |

## 7. Lacunas do UI Lab (regra "componente nasce no UI Lab")
Usados no produto e **ausentes** de `/ui-lab/`: `filtros__mais` (gaveta), `registros__grupo`,
`lista-cabecalho`, barra de ações de lista (status + Exportar + Novo), `refino` + fichas de escopo,
`menu--pousar`/`registro__meta-item--acao`, `registro--inativo`, `registro--destaque`,
`frase-oficio`, `secao` numerada da folha, `rodape_documento`. As seções do UI Lab estão fora de
ordem (… 9, **12**, 10, 11, 13 …). O exemplo de registro do lab ainda mostra "Sem roteiro" com
`map-pin`, que a lista real não usa mais. → **DOCUMENTAR** antes de qualquer refinamento da lista.

## 8. Resumo das ações por prioridade
1. **CORRIGIR** (compartilhado, barato, alto alcance): seletor `registro--inativo`; z-index do
   grupo × ações; opacidade do ⋮; `selo--neutro` inexistente; rótulo da placa < 9px.
2. **CONSOLIDAR**: tags `selo_situacao`/`selo_tempo`; parcial único de cabeçalho; parcial de
   registro do termo; `documento--cartoes` no roteiro.
3. **TRAZER**: fichas de filtros ativos; item de menu com descrição; zona de soltar (eProtocolo).
4. **DOCUMENTAR**: UI Lab (seção 7) e docs desatualizados (`components.md` expansão em linha;
   `page-archetypes.md` ação primária).
