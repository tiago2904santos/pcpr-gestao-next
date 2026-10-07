# Lista de ofícios — Lote 2 (LP-20 a LP-27): comportamento da lista

> Agente 2 — UI/UX Design Lead · 2026-10-07 · implementação do Lote 2 do plano aprovado
> (`oficios-lista-plano.md`, D1/D2/D6). Base de comparação: o estado aprovado do Lote 1
> (`ddc9daf`, servido de um worktree em `:8003`). Evidências fora do repositório (PREVIEW,
> dados fictícios): `/home/claude/caps/lote2/<estado>-<largura>.png` (14 estados × 1440, 1024,
> 768, 390, 360), `lab22-*.png`, `l1-*.png` (antes). Scripts: `/home/claude/tools/estados_lote2.py`,
> `interacoes_lote2.py`, `teclado_lote2.py`, `axe_lote2.py`, `benchmark_lote2.py`,
> `consultas_lote2.py`, `consultas_lentas.py`, `regressao_l1.py`, `lab22.py`.

## 1. O que mudou, por LP

Commits: `923d0e9` (LP-20 domínio) · `930c6a2` (LP-21/23 componentes na origem + UI Lab) ·
`4758843` (LP-20/21/22/25/26 lista) · `fc8d07f` (LP-24) · `117a387` (LP-27) · `cc82a05` (e2e/evidências).
Linha de base do Lote 1 para o QA: worktree `/home/claude/l1-wt` (`ddc9daf`), servidor
`bash /home/claude/tools/l1_server.sh` → `:8003`.

| LP | O quê | Arquivos principais |
|---|---|---|
| LP-20 | **Abas temporais** canônicas — Todos · Que vão acontecer · Em andamento e realizados · Contas prestadas · Cancelados — com a regra exata do legado (`abas.py:73-85`): cancelado vence tudo; depois contas prestadas; o resto pela 1ª saída — depois do fim de hoje **ou sem data** → "Que vão acontecer"; até o fim de hoje → "Em andamento e realizados". Regra em **domínio puro** (`dominio/recorte.py`: `aba_do_oficio`, `documento_do_oficio`, `no_recorte`) e a mesma conta em SQL (`queries.q_da_aba`/`q_do_documento`, 1ª saída por subconsulta). **Documento** (Todos · Rascunhos · Emitidos · Arquivados) é um segmentado de rádios sempre visível, um clique, com contagem; arquivado fica fora de "Todos" até ser pedido e continua no seu tempo (arquivado + "Que vão acontecer" funciona). **Contadores** das abas e do Documento acompanham busca e filtros, ignorando só a própria dimensão, numa agregação condicional (`contagens_do_recorte`). Parâmetros novos `aba=` e `documento=`; **endereços antigos** (`?situacao=rascunho|emitido|arquivado|cancelado|proximos|prestadas`) redirecionam (302) para o equivalente, preservando o resto — na lista e no Exportar. Links de outras telas migrados: painel (Rascunhos → `?documento=rascunho`; "Viagens em 30 dias" → `?aba=futuros&ordem=saida`; o indicador de rascunhos deixou de contar arquivados), busca global Ctrl+K, conflitos, vias assinadas e o retorno das ações, todos por `enderecos.url_na_lista` (arquivado já leva `documento=arquivado` — antes caía numa lista onde ele não aparecia) | `dominio/recorte.py`, `queries.py`, `views.py`, `enderecos.py`, `busca.py`, `conflitos.py`, `views_assinados.py`, `painel.html`, `oficios/_abas.html` |
| LP-21 | **Barra = Busca · Documento · Filtros (n)**. "Ordenar por" saiu da barra para a **gaveta**, que nunca abre sozinha e reúne Ordenar por (rótulos honestos: "Saída, mais antiga primeiro" no lugar de "Data de saída (próximas)"), Período de saída, Data do ofício, **Ano do número** (opções = anos que existem; outro ano é ignorado sozinho), Protocolo, Veículo, Diárias (fieldset/legend com o rótulo na borda, as duas pontas numa caixa só). Rodapé "Limpar filtros" (tira só o que mora na gaveta) · "Fechar". Esc e "Fechar" fecham e devolvem o foco ao botão; clique fora fecha; Esc dentro do calendário/seleção fecha só o painel interno. No celular a gaveta é uma **folha inferior** sobre véu, com título e rodapé presos. **Fichas** removíveis para cada filtro valendo (Documento, período, ano, protocolo, veículo, diárias, **escopo da busca** e **ordem fora do padrão**) + "Limpar tudo" — que, como todo "Limpar", **não apaga a busca nem a aba** (F8). Um campo inválido não derruba mais os outros (`FiltrosOficio.validos`). Contadores do Documento, do botão Filtros e o "Limpar" da gaveta são atualizados fora de banda sem trocar o controle (o foco fica onde está). URL da busca ao vivo **sem os campos vazios** | `forms.py`, `views.py` (`_fichas`, `_sem`, `_trocar`), `oficios/lista.html`, `_fichas.html`, `_conta_filtros.html`, `_limpar_gaveta.html`, `static/js/componentes/filtros.js`, `listas.css`, `components.css` |
| LP-22 | Busca: **placa** na busca ampla ("ABC1D23", "abc-1d23") — F1; **destino sem a volta à sede** — F2 (na ampla e no refino "Destino"); **motivo com `unaccent`** — F4; refino aparece **com uma leitura só quando a ampla vem vazia** ("1234": "Nada na busca geral. Procure só em: Protocolo com 1234 (1)"); refino conta dentro do recorte de agora (aba, documento e filtros); placeholder "Número, protocolo, destino, servidor, placa ou motivo". Destino/servidor por **subconsulta não correlacionada** (sem junção, sem DISTINCT) | `services.buscar_por_texto`, `queries.q_destino/q_servidor/q_placa`, `dominio/busca.py` (`parece_placa`, `placa_normalizada`), `_refino.html` |
| LP-23 | **Vazio certo** para qualquer recorte (F5): nunca "Crie o primeiro" com filtro valendo; ações que tiram só o que dizem — "Limpar filtros" (fica busca e aba), "Limpar busca" (ficam os filtros), "Ver todos". **Erro da busca ao vivo**: sem rede ou com erro do servidor, um alerta `role="alert"` aparece **no lugar de #resultados** com "Tentar de novo" (refaz o mesmo pedido). O aviso mora no **arquétipo LIST** (`componentes/erro_lista.html`): todas as listas com busca ao vivo ganham o mesmo tratamento | `_vazio_filtrado.html`, `templates/componentes/erro_lista.html`, `templates/arquetipos/lista.html`, `filtros.js` |
| LP-24 | **`voltar` vivo** (F3): na hora do envio, o campo `voltar` marcado com `data-voltar-vivo` recebe o endereço atual (a busca HTMX muda a URL sem recarregar). Vale para o diálogo de motivo (cancelar/reativar) e para os formulários do ciclo de vida, inclusive os que vêm dentro da janela de resumo (antes voltavam para "?q=número") | `static/js/componentes/dialogo.js`, `componentes/dialogo_motivo.html`, `oficios/_acoes_ciclo.html` |
| LP-25 | Consultas constantes: **16** na lista (igual ao Lote 1) com 20 e 200 ofícios, inclusive com busca, documento, aba e todos os filtros (teste com teto de 20); os contadores novos são uma agregação condicional (+1 consulta só quando há busca/filtro, para o "de M"); +1 consulta para os anos do número. Exportar: 11 → 12 consultas (anos), sem N+1 com 200 ofícios (teste). Período de saída por EXISTS (sem DISTINCT) | `queries.py`, `test_views.py::TestConsultasDaListaLote2` |
| LP-26 | Contagens não repetidas: sem busca, o h2 "Ofícios" é só para leitor de tela (a aba já diz o total); com busca, "Resultados para “x” · N ofícios". Barra fixa: "N de M ofícios" quando filtrado (M = a aba sem busca nem filtros), "Página 1 de 13" sem filtro. Cabeçalho de mês com a **contagem do grupo na página** ("4", ou "20 nesta página" quando o mês continua na página vizinha; leitor ouve "Outubro de 2026: 4 ofícios"). Barra (contagem + Exportar) atualizada fora de banda — antes ficava com o número e o link da carga | `lista.html`, `_barra_status.html`, `views._grupos_por_mes`, `layout.css` (`.barra-acoes__conteudo`) |
| LP-27 | XLSX: Situação **"Arquivado"** quando for o caso (L4); Tipo com a marca, igual à tela e ao resumo ("Convalidação · Complementar"; a marca de retificado que não vale na convalidação não aparece); o recorte é o mesmo da tela (aba, documento, busca, filtros, ordem) e aceita os endereços antigos | `exportacao.py`, `views.exportar` |

Componentes compartilhados melhorados **na origem** (e no UI Lab, seção 22 "Barra de filtros
das listas" + seção 7 com a ficha real):
- `.segmentado`: foco com o anel do DS por dentro (antes `outline` simples); variante
  `.segmentado--contagem` + `.segmentado__conta`; trilho que rola de lado (`data-rola-lado`).
- `abas-rolagem.js`: além de `.abas`, qualquer `[data-rola-lado]` (Documento e fichas no
  celular) ganha a borda esmaecida e centraliza o item marcado.
- `.aba--vazia`: aba com 0 no recorte recua (terciário, 5,3:1) mas continua clicável.
- `.filtros-ativos` / `.ficha--filtro` saíram do "catálogo" do `ui-lab.css` para `listas.css`
  (havia duas definições de `.ficha` brigando no UI Lab); "×" com alvo de 24 px e anel de foco.
- `filtros.js` (sob demanda em `.filtros__mais` ou `[data-erro-lista]`): gaveta (Esc, clique
  fora, Fechar, foco), erro da busca ao vivo, URL sem campos vazios, escopo do refino que
  volta à busca ampla ao digitar outro termo.
- `componentes/erro_lista.html` no arquétipo LIST; `.barra-acoes__conteudo` (grupo trocado
  por OOB sem quebrar o layout da barra).

## 2. Medições antes (Lote 1, `:8003`) × depois

**Ofícios na 1ª tela** (`estados_*.py`, entre o topo e a barra fixa):

| Largura | Antes | Depois | Observação |
|---|---|---|---|
| 1440 | 5,32 (lista em y = 451) | **5,88** (y = 410) | Ordenar saiu da barra; h2 visual só com busca |
| 1024 | 5,32 | **5,88** | idem |
| 768 | 4,15 | 4,01 | a barra quebra em 2 faixas (Busca / Documento + Filtros) — custo consciente do Documento sempre visível (busca ficaria com 133 px numa faixa só) |
| 390 | 2,56 | **3,42** | **M9 resolvido** (meta ≥ 3): Busca e Filtros na mesma linha, Documento rolando de lado |
| 360 | 2,56 | **3,42** | |
| 390 com 6 filtros valendo | — | 3,01 | fichas numa linha só, rolando de lado (antes de rolar: 1,3) |

**Rolagem horizontal**: 0 px nos 14 estados × 5 larguras (70 combinações).

**Consultas SQL** (`consultas_lote2.py`, gestor, PREVIEW 255 ofícios): lista 16 → **16**;
página 2 16 → 16; `?q=curitiba` 17 → 17; `?documento=rascunho` 16; `?aba=cancelados` 16;
Exportar 11 → 12. Tempo da consulta mais pesada com `?q=curitiba`: 106 ms (Lote 1, SELECT
DISTINCT) → **23 ms**. A primeira versão dos contadores (`pk IN (busca)` dentro de cada
contador) custava 627 ms; a agregação sobre o recorte + subconsultas não correlacionadas
derrubou para 12–23 ms (registrado no docstring de `contagens_do_recorte`).

**Defeitos do legado/novo fechados**: F1 (placa: 0 → 3 resultados com a placa), F2
("curitiba" deixa de casar a volta à sede), F3, F4, F5, F7 (contadores), F8, L4, L11, L12,
L16, L30, L34 (matriz `parity/oficios-lista.md`).

## 3. Benchmark legado × novo (`benchmark_lote2.py`; tempos com a suíte de testes rodando na mesma máquina de 2 núcleos — comparar cliques, não milissegundos)

| Tarefa | Legado | Novo | Veredito |
|---|---|---|---|
| Ver rascunhos | **impossível** (sem aba nem filtro; o selo só aparece em linha sem datas) | 1 clique (Documento: Rascunhos), sem recarga; 20/20 linhas rascunho; contagem visível antes do clique | **novo** |
| Ver o que vai acontecer | 1 clique (recarga) | 1 clique; inclui rascunho sem data, como o legado | empate (paridade) |
| Filtrar por ano | 3 cliques + recarga da página | 3 cliques (Filtros, Ano, opção), sem recarga, ficha criada, opções = anos existentes, ano **do número** | **novo** (sem recarga) |
| Remover um filtro | 1 clique no × do chip (recarga) | 1 clique no × da ficha (com a gaveta fechada) | empate |
| Achar por placa | **0 resultados** (legado não procura placa) | digitar a placa: 3/3 com a placa | **novo** |
| 1ª tela a 390×844 | 1,39 | 3,42 | **novo** |

## 4. Autocrítica

### 1ª revisão ("se fosse para produção hoje, o que me incomodaria?") — e o que foi corrigido
1. **Contadores lentos com busca** (627 ms): reescrito (§2). ✔
2. **Rótulo "Documento" encostando na opção marcada** a 768: altura da opção 1,75rem (alvo
   ainda ≥ 24 px) e trilho com contorno de campo. ✔
3. **Legenda de "Diárias (R$)" caindo dentro da caixa** (o `.campo` virava flex no fieldset):
   legenda própria na borda. ✔
4. **Fichas empilhadas no celular** (6 filtros = 6 linhas; 1,3 ofício na 1ª tela): linha
   única rolando de lado com borda esmaecida; "Filtrando por" escondido no celular. ✔
5. **Véu da folha inferior vazaria para Coffee/Eventos/Imprensa/Palestras/Publicações** (mesmo
   `.filtros__mais`): véu só na variante `--rodape`; Coffee com filtro aberto a 390 é
   **idêntico pixel a pixel** ao Lote 1. ✔
6. **URL da busca ao vivo com onze `campo=` vazios**: limpos no `htmx:configRequest`. ✔
7. **"Fechar" sem JavaScript não faz nada**: só aparece com JS. ✔
8. **Texto do refino de uma leitura** ("Em tudo, nada…") → "Nada na busca geral. Procure só em". ✔

### 2ª revisão (depois das correções)
- Teclado (`teclado_lote2.py`): Busca → Documento (uma parada; setas trocam e o foco fica no
  rádio depois do HTMX) → Filtros → cada × das fichas → Limpar tudo → linhas. ✔
- Gaveta (`interacoes_lote2.py`): fechada ao carregar; Esc fecha e devolve o foco; clique
  fora fecha; Fechar fecha e devolve o foco; Esc no calendário fecha só o calendário. ✔
- Erro (rota abortada no navegador): alerta no lugar dos resultados; "Tentar de novo" refaz
  e devolve a lista. ✔  `voltar` do diálogo = endereço da busca HTMX. ✔
- axe (wcag2a/aa, 2.1, 2.2aa, best-practice) a 1440 e 390: normal, cancelados, rascunhos,
  gaveta aberta, fichas, refino, vazio, erro, Roteiros, Termos, Coffee, UI Lab → **0 violações**.
- Regressão (`regressao_l1.py`, Lote 1 × agora): 16 rotas (Roteiros, Termos, painel, Ordens,
  Planos, Viagens, Justificativas, Prestações, Servidores, Coffee ×2, Eventos, Imprensa,
  Publicações, Palestras, UI Lab) × 5 larguras = 80 combinações: **0 diferenças** de status,
  rolagem, nº de linhas, alturas e fontes.

O que ainda me incomoda (não bloqueia; vai para as pendências):
- Documento "Todos 26" ≠ Rascunhos 9 + Emitidos 16: a diferença são os cancelados (contam em
  Todos, não são "rascunho" nem "emitido"). Coerente com D1, mas pode intrigar.
- Com a gaveta aberta no desktop, as fichas criadas ficam por baixo do painel até fechar (o
  número no botão muda na hora).
- 768: −0,14 ofício na 1ª tela (barra em duas faixas).
- Com Documento escolhido há duas indicações (o segmentado marcado e a ficha) — pedido do
  plano (D6); custa uma linha no celular (2,83 ofícios na 1ª tela com Rascunhos).
- `ordem=-numero` continua na URL depois de mexer na gaveta (inofensivo).

## 5. Roteiros e Termos (D6 como padrão do módulo)
Avaliado e **não aplicado agora**: as duas listas só têm Busca + abas — não têm situação de
documento nem filtros finos, então a barra D6 ficaria sem Documento, sem gaveta e sem fichas.
Já herdam, sem mudança de tela, o erro da busca ao vivo (arquétipo), a URL limpa e o
segmentado/abas compartilhados. Registro para um próximo lote:
- **contadores das abas de Roteiros e Termos ignoram a busca** (o mesmo F7 que a lista de
  ofícios tinha) — `contagens_roteiros(base)`;
- "Que vão acontecer" de Roteiros/Termos **não inclui o que não tem data** (Ofícios inclui,
  como o legado);
- quando ganharem filtros (período, ano), usar a mesma barra (`filtros--barra`, `_fichas`).
As outras listas com `.filtros__mais` (Coffee, Eventos, Imprensa, Palestras, Publicações)
mantêm a gaveta que abre sozinha com filtro valendo (sem fichas ainda) — ganharam só Esc,
clique fora e o erro da busca; migrar para fichas + gaveta fechada é o próximo passo natural.

## 6. Testes e verificação
- Domínio: `test_dominio_recorte.py` (20: fronteira do fim de hoje, sem data, prestadas,
  cancelado, arquivado × abas, tradução dos endereços antigos, rótulos da ordem).
- Views (`test_views.py`, novas classes): `TestAbasTemporaisEDocumento`, `TestGavetaEFichas`,
  `TestBuscaDaLista`, `TestVaziosEContagens`, `TestVoltarVivoEErroDaBusca`,
  `TestConsultasDaListaLote2` (20 e 200 ofícios), `TestPlanilhaLote2`; testes antigos
  migrados para `aba`/`documento` (os de `?situacao=` agora conferem o redirecionamento).
- E2E atualizados: `test_preview_demo.py` (Documento por um clique, ordem na gaveta, ficha) e
  `test_fluxo_oficio.py` (gaveta: ficha, contador, Esc devolve o foco); rotas de
  `tests/e2e/rotas.py` e `scripts/evidencias_visuais.py` no vocabulário novo.
- Resultado dos comandos: ver §7.

## 7. Resultado dos comandos
- `pytest gestao/viagens/tests/test_views.py test_prestacao.py test_dominio_recorte.py
  gestao/painel/tests/test_busca_global.py gestao/viagens/tests/test_servicos.py`:
  **257 passed** (2 testes que usavam os ajudantes antigos `FILTROS_SITUACAO` /
  `aplicar_filtro_situacao` migrados e reexecutados: 3 passed).
- `tests/test_design_tokens.py` 68 passed · `tests/test_css_por_pagina.py` 1 passed ·
  `tests/e2e/test_acessibilidade.py -k "oficios or roteiros or termos or ui_lab or foco or
  viagens"` **23 passed** · `tests/e2e/test_fluxo_oficio.py -k gaveta/agrupa` passed.
- `ruff` verde · `mypy gestao config` sem erros · `lint-imports` 16 contratos mantidos ·
  `bandit` sem achados · `tsc -p jsconfig.json` verde.
- **Falhas pré-existentes** (iguais no Lote 1, `ddc9daf`, rodando no worktree): e2e
  `test_registro_da_lista_abre_resumo_em_janela_e_fecha_com_esc` (rodapé diz "Ver minuta",
  o teste espera "Minuta") e `test_erro_de_validacao_aparece_no_resumo_e_no_campo` /
  `test_preview_demo` no passo "Salvar rascunho" da folha; `test_preview_demo` também mede a
  rolagem da navegação de módulos a 1024/768 (M12). A parte da lista do `test_preview_demo`
  (Documento por um clique, ordem na gaveta, ficha) passou.

## 8. Correções pós-QA (`qa/oficios-lista-lote2.md`, `027e55d`)

| Item | Correção (na origem) | Evidência medida |
|---|---|---|
| **B1** calendários e "Veículo" cortados na folha inferior | `painel-flutuante.js`: além de `dialog[open]`, qualquer contêiner `[data-camada-topo]` solta o painel do campo (calendário, relógio, `pc-select`) para a **camada de topo** (popover), posicionado abaixo ou acima conforme o espaço da tela, e acompanha a rolagem do contêiner enquanto aberto. A folha do celular ganha `data-camada-topo` ao abrir. Vale para todo campo flutuante dentro de qualquer folha futura | `tools/b1_folha.py` (alvos no ponto, dentro da tela): Período **46/46**, Data do ofício **46/46**, Veículo **8/8**, Ordenar 6/6, Ano 4/4 — a 390 e a 360 (antes 16/46 e 3/8); `caps/lote2/b1-*.png`. Obs.: `cal390b.py`/`pickers390.py` do QA filtram por `offsetParent`, que é `null` em todo popover (camada de topo, `position: fixed`) e, com a folha agora `role="dialog"`, pegam a própria folha — versões que usam `getClientRects()`: `tools/cal390_topo.py`, `tools/pickers390_topo.py` |
| **I1** folha não era modal | `filtros.js`: ao abrir no celular, a folha vira `role="dialog"` `aria-modal="true"` `aria-labelledby` (título "Filtros e ordem"); todo o resto da página (subindo até o `<body>`, inclusive o botão sob o véu) fica `inert`; `html.rolagem-presa` trava a rolagem; Tab/Shift+Tab ciclam dentro; foco inicial no 1º controle **visível** (o gatilho do `pc-select`, não o `<select>` escondido); Esc/Fechar/véu desfazem tudo e devolvem o foco a "Filtros"; girar para largura de desktop com a folha aberta desfaz o modal. **Desktop continua não modal** (decisão): é um painel de divulgação sobre a lista que muda ao vivo, compartilhado com Coffee/Eventos/Imprensa/Palestras/Publicações, que não mudam | `qa/gaveta_teclado.py`: 0 saídas da folha em 16 Tabs; foco ao abrir `#ordem-oficios-gatilho`; rolagem por trás **0** (era 600); Esc devolve a "Filtros". Shift+Tab: Fechar → Limpar → Diárias até (dentro); depois de fechar: 0 `[inert]`, `role="group"` |
| **I2** foco no BODY após "Tentar de novo" | `filtros.js`: depois da troca bem-sucedida, foco no `#titulo-resultados` (`tabindex=-1`), que diz "Resultados para “x”: N ofícios" — componente do arquétipo, vale para as outras listas | `qa/erro_foco.py`: foco `H2#titulo-resultados` |
| **I3** Documento "Todos" com número que não fecha a soma | "Todos" **sem contagem** (decisão do orquestrador); só Rascunhos/Emitidos/Arquivados mostram números (também no OOB) | `test_views.py` (`conta-doc-todos` ausente) |
| **I4** 1ª tela a 390 com busca/Rascunhos e total 3× | Título dos resultados **só para leitor de tela também com busca** ("Resultados para “x”: N ofícios"); o total fica na aba (e, no desktop, na barra "N de M"). Documento **não vira ficha** (o segmentado marcado já diz; "Limpar tudo" continua tirando o Documento). Refino e fichas numa linha só, rolando de lado, no celular | `qa/l2_telas.py` a 390: normal 3,42 · **busca 3,13** (era 2,75) · **Rascunhos 3,20** (era 2,83) · fichas 3,01; 360 igual |
| **I5** "Filtros" órfão a 900; 768 pior que o Lote 1 | Documento + Filtros num grupo (`.filtros__lado`) que nunca se separa; de 768 a 1023 o Documento fica compacto e a busca começa em 12rem → **uma linha só de 768 em diante** (busca 197 px a 768, 329 px a 900). Fichas numa linha só abaixo de 1280, com "Limpar tudo" no começo do trilho (sempre à vista; também resolve o menor do fade que o escondia) | `qa/l2_telas.py`, Lote 1 → agora: 900 normal **4,15 → 4,59**, 768 **4,15 → 4,59**; com 5 filtros valendo 900/768 **3,23 → 4,14**, 1024 4,77 → **5,30**; barra 73 px em 768–1440 (era 127 a 768/820) |

Também: busca (`?q=26`) a 390 com refino numa linha: 2,17 → 2,45 (3 resultados ao todo);
UI Lab seção 22 atualizado (grupo Documento+Filtros, "Todos" sem número, folha modal).

**Verificação depois das correções**
- axe (`tools/axe_l2_900.py`, cópia do `axe_l2.py` do QA com 900 e mais dois estados: folha
  com o calendário aberto e com "Veículo" aberto) — 21 estados × 1440/1024/900/768/390/360 =
  **126 execuções, 0 violações**.
- Regressão contra o Lote 1 (`:8003`): 18 rotas (Roteiros, Termos, painel, Ordens, Planos,
  Viagens, Justificativas, Prestações, Servidores, Usuários, Coffee ×2, Eventos, Imprensa,
  Publicações, Palestras, Agenda, Notificações) × 6 larguras = **108 combinações, 0
  diferenças**.
- `qa/l2_interacoes.py`: gaveta, fichas, Limpar, vazio, refino, Documento pelo teclado, erro
  (abort e 500) e "Tentar de novo" — como no QA.
- Testes: 73 do `test_views.py` (classes do Lote 2 + lista/ciclo/filtros) passed; e2e
  gaveta/agrupamento 3 passed; parte da lista do `test_preview_demo` passou (para no
  "Salvar rascunho" pré-existente); ruff, mypy, tsc, tokens verdes.

**Autocrítica dupla (pós-QA)**
1. *1ª revisão*: a folha modal prendia o foco, mas "Limpar tudo" das fichas, rolando de lado,
   ficava escondido pela máscara (menor do QA) → primeiro tentei prendê-lo à direita
   (`sticky`) — o axe acusou `target-size` (o botão encobria parte do "×" vizinho, 14×25 px a
   360 e no UI Lab a 390/768) → **"Limpar tudo" passou para o começo do trilho** (`order`),
   nada fica por cima de nenhum alvo. O refino ainda empilhava no celular (2,17) → linha única.
2. *2ª revisão*: a 768 a busca tem 197 px — cabe "131/2026", uma placa ou um sobrenome;
   termo longo rola dentro do campo. Aceito em troca de uma linha de lista (o Lote 1 a 768
   também tinha a busca dividindo a linha). O painel do calendário no celular aparece sobre
   o topo da folha (camada de topo) — é o comportamento dos diálogos do sistema. Na largura
   de desktop a gaveta segue cobrindo as fichas recém-criadas (menor; contador avisa).
   Continuam como menores registrados: link "Viagens em 30 dias" do painel, `ordem=-numero`
   na URL, `?resumo=` de outras telas para ofício arquivado.
