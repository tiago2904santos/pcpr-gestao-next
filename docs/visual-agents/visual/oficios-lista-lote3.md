# Lista de ofícios — Lote 3 (ações): relatório do Designer

> Agente 2 — UI/UX Design Lead · 07/10/2026 · branch `viagens/reconstrucao` a partir de
> `a10a831` (Lote 2 aprovado). Plano: `oficios-lista-plano.md` (D7, D8, D9; LP-30…LP-33).
> **Privacidade:** capturas do LEGADO ficam em `/home/claude/caps/l3/` (fora do repositório);
> nenhum dado real aqui. As do NOVO são da base DEMO (fictícia).

## 1. O que mudou

### LP-30 — Menu ⋮ canônico da linha do ofício (D7)
**Componente na origem (UI Lab, seção 8, antes das telas)** — `<pc-menu>` ganhou:
- `.menu__item--descrito`: título + linha que diz o que a ação faz (ou por que está
  inativa). A descrição fica **fora do nome** do item (`aria-hidden`) e entra como
  **descrição** (`aria-describedby`): o leitor ouve "Arquivar, item de menu, Sai das abas de
  trabalho; nada é apagado". Itens de leitura (Ver resumo, Abrir, Ver minuta/PDF) sem descrição.
- **Inativo** (`aria-disabled`): recebe o foco pelas setas (padrão WAI-ARIA) e não age —
  "Anexar assinado…" sem PDF diz por quê, como no legado.
- **Menu flutuante** (toda linha `.registro__acoes` e quem tem `data-menu-flutuante`): o
  painel sobe para a **camada de topo** (popover) sobre um **véu** — invisível no desktop,
  escuro no celular — que fecha ao toque fora **sem acionar o que está atrás**. Posição:
  abaixo do botão; sem espaço, acima; sem espaço nos dois, **ao lado** do botão, deslizado até
  caber; o que sobrar rola dentro do painel. **Nunca sai da janela** e nenhum alvo vizinho fica
  meio coberto (o M8 do QA some na origem — vale para Termos e Roteiros também).
- **Celular (<768 px): folha inferior** com o registro no alto ("Ofício 160/2026 · Salto do
  Itararé/PR"; em Termos/Roteiros o nome do botão), alvos de 44 px.
- Escolher um item fecha o menu e **devolve o foco ao ⋮** — inclusive depois da janela que
  o item abriu (resumo, motivo, baixar, confirmação).
- `data-menu-carregar`: os itens chegam do servidor quando o mouse ou o foco chega ao ⋮.

**Domínio → política → serviço → tela**
- `dominio/assunto.py`: `alternar_marcador` (o mesmo item liga/desliga; **Retificado e
  Complementar se excluem** — ligar um tira o outro) e `marcas_do_menu` ("Retificado" só se
  oferece na Autorização, onde muda o rótulo; desligar sempre). Semântica do campo
  `marcador` conferida: um campo único (`""|retificado|complementar`), a exclusão é estrutural.
- `policies.menu_do_oficio` é a fonte única; regras novas nomeadas: `pode_duplicar`,
  `pode_marcar` (= editar: só rascunho), `pode_baixar_documentos`, `pode_anexar_assinado`
  (agora usada também por `assinados.pode_anexar`).
- `services.alternar_marcador`: trava, versão, histórico ("Marcado como complementar… A marca
  de retificado saiu."). POST `/oficios/<pk>/marcar/` volta à lista como estava.
- Itens por estado (gestor+operador · operador · consulta):

| Grupo | Rascunho | Emitido | Cancelado | Arquivado |
|---|---|---|---|---|
| Ler / levar | Ver resumo · Abrir o ofício · Ver minuta · Baixar documentos… · Anexar assinado… *(inativo: "Emita o ofício primeiro")* | Ver resumo · Editar (retificar) · Ver PDF vN · Baixar documentos… · Anexar (ofício) assinado… · Anexar justificativa assinada… *(se houver)* | Ver resumo · Ver minuta ou PDF | Ver resumo · Ver PDF vN · Baixar… · Anexar… *(inativo: "Desarquive…")* |
| Criar | Novo termo · Nova OS · Novo plano · Duplicar | idem | Duplicar | Novo termo · Duplicar |
| Marcas | Marcar como retificado/complementar (ou "Deixar de ser…") | — (corrige-se por retificação) | — | — |
| Situação | Cancelar… *(gestor)* · Arquivar | Cancelar… · Arquivar | Arquivar · Reativar… *(gestor)* | Desarquivar |
| Excluir | Excluir rascunho *(sem documento)* | — | — | — |
| **Consulta** | Ver resumo · Ver minuta | Ver resumo · Ver PDF vN | idem | idem |

- **"Retificar" aparece uma vez só**: no emitido é "Editar (retificar)" (volta a rascunho
  como retificado, a semântica melhor do novo); no rascunho é "Marcar como retificado" (a
  marca, como no legado). Um "Retificar" no 3º grupo do emitido repetiria o 1º.
- **Peso**: com 9–15 itens descritos por linha a lista iria de 122 KB para **263 KB**; os
  itens vêm de `GET /oficios/<pk>/acoes/` ao chegar ao ⋮ (mouse por cima ou foco — já estão
  lá no clique; no toque, "Carregando as ações…" por um instante). A lista ficou **mais
  leve** que no Lote 2 (152 → 122 KB). A consulta da lista anota o PDF que vale e as vias em
  vigor; o fragmento faz ≤ 12 consultas.
- **Mesmo menu em toda parte**: lista, painel "Viagens" (que ganhou as janelas que o menu
  abre) e janela de resumo ("Mais ações" = o canônico sem o que o rodapé já mostra, mais
  Word e "Termos/OS/Planos deste ofício"). Resumo dentro do orçamento (19/14 consultas).

### LP-31 — Barra fixa da lista (D8)
Contagem do recorte · Exportar planilha · **Mais** · Novo ofício. `componentes/menu_mais.html`
(compartilhado; recebe a lista de itens da view): só aparece com item — **Numeração** para
quem gere a numeração. "Importar processo do eProtocolo" entra quando existir (D10); **nenhum
item inativo antes**. Outras listas (Roteiros, Termos, OS, Planos, Viagens, Prestação) usam a
mesma `.barra-acoes`; nenhuma tem ação rara hoje, então nenhuma ganhou "Mais" vazio.

### LP-32 — Página Numeração (D9) `/viagens/oficios/numeracao/`
- **Permissão**: `policies.pode_gerir_numeracao`; operador, consulta e outra unidade → **403**
  (padrão do legado e do `exigir`). Entrada: "Mais" da barra.
- **Por ano** (abas: atual, o próximo para preparar a virada, todo ano com ofício/piso/lacuna):
  **próximo número e de onde vem** (menor lacuna livre · número inicial · último + 1), último
  ocupado (cancelados contam), número inicial (piso), lacunas livres.
- **Regra real conferida** (`services.reservar_numero`, `dominio.numeracao.proximo_numero`;
  legado `core/numeracao.py:105-118` `proximo_do_livro` e `viagens_oficios/views.py:972-991`):
  só o número de **rascunho excluído** volta — o menor primeiro, nunca abaixo do piso; buraco
  de outra origem **não** volta; o piso **não renumera** e, se for ≤ último ocupado, **não
  muda nada agora**. `dominio.numeracao.explicar_proximo` explica isso; a tela e a mensagem
  depois de salvar dizem o efeito ("Nada muda agora: o último número usado é 160/2026, então o
  próximo continua 161/2026." · "A lacuna 03/2026 fica abaixo do piso e não será
  reaproveitada.").
- Formulário SETTINGS curto: rótulo na borda, mensagens que dizem como resolver ("Use só
  algarismos, sem ponto nem barra — ex.: 100." · "O número inicial começa em 1. Para voltar ao
  padrão, use 1." · "…vai até 99999. Confira se não sobrou um dígito."), resumo de erros com
  foco, 422; mesmo piso não grava; ano encerrado só consulta.
- **Histórico** do número inicial lido da **trilha do banco** (tabela auditada por trigger):
  `linha_do_tempo.do_piso` — quem, quando, de quanto para quanto.
- ⚠️ **Conflito a confirmar com o dono do produto**: uma página de numeração foi **excluída
  "a pedido"** em `4a3f835` (06/10, 18:48 — 35 min antes desta missão começar;
  `docs/migration/visual-viagens-progress.md`). D9 a recria. Está isolada no commit
  `56a17ff` (+ o item do "Mais" em `7cb7416`): reverter os dois tira a página e o "Mais" some
  sozinho.

### LP-33 — Docs do Design System
`components.md`: lista de registros sem a "expansão em linha" que não existe (P14), linha em
colunas, barra de filtros, segmentado, gaveta/folha, fichas, menu (descrito, inativo,
flutuante, folha, carregado ao chegar), ⋮ canônico, barra fixa com "Mais", selo de tempo,
selo de contorno. `page-archetypes.md`: LIST com a ação primária na barra fixa; SETTINGS com
a Numeração.

### Saneamento — os 3 e2e vermelhos do main
| Teste | Quem estava errado | Correção |
|---|---|---|
| resumo "Minuta" × "Ver minuta" | **teste** (o rodapé diz "Ver minuta" desde antes do main) | espera "Ver minuta" |
| "Salvar rascunho" (fluxo e preview DEMO) | **teste** — a folha grava sozinha e o envio é "Finalizar" (rodapé padrão, `45c0ae2`) | usa "Finalizar"; o preview usa o teto de consultas da folha (32, o de `test_views`), não o das listas (25) |
| rolagem lateral 257/78 px a 768/1024 | **produto** (Início, Notificações, UI Lab) | lista de módulos fora de um módulo rola de lado com borda esmaecida (`data-rola-lado`, como as abas); Tab mostra o item inteiro |
Os três estão **verdes** (preview DEMO nas 6 larguras).

### Menores do QA incluídos
- **M5** tipo × situação: o selo do tipo sai em **contorno** (`.selo--contorno`, sem fundo).
- **M8** / ⋮ cobrindo link vizinho a 390/360: resolvido na origem (véu + folha) — axe limpo
  com o menu aberto em Ofícios, Termos e Roteiros a 390/360.
- **M-R1** × da ficha sob o esmaecido a 390: quem chega pelo Tab vê o item inteiro (5/5 × com
  22/22 px fora do esmaecido).
- **M-R2** "Limpar tudo": no DOM onde aparece (um por largura) — o Tab segue o que se vê.
- **M-R4** busca curta a 768: dica curta medida pela fonte real ("Número, destino…" de 768 a
  900 e no celular; a longa ≥ 1024).

## 2. Autocrítica — rodada 1 (capturas em `/home/claude/caps/l3/menus/`, `numeracao/`)
1. **Menu longo demais** (12–14 itens, 600–700 px): o painel abria abaixo do botão e rolava por
   dentro. → descrições só onde há consequência (leitura sem descrição: −60 px) e 3ª posição
   **ao lado do botão**, deslizada até caber: 14 itens cabem inteiros a 900 px de altura.
2. **Lista 73 % mais pesada** (263 KB) com os menus em linha → itens sob demanda (122 KB).
3. **Orçamento do resumo estourado** (21/19): o menu consultava PDF e vias de novo → a janela
   passa o que já carregou.
4. **Placeholder curto ainda cortava a 390** ("Número, destino, servi") → dicas em camadas.
5. Numeração: margem fantasma no topo do formulário (campos ocultos antes do texto), tabela
   do celular com `th` fora do padrão `tabela--responsiva`, "0 ofícios (cancelados contam)",
   foco não ia ao resumo de erros, `selo--marca` (só existe no catálogo) → corrigidos.
6. Títulos dos itens descritos em peso médio (o legado usa negrito; a vista corre pelos títulos).

## 3. Autocrítica — rodada 2 (`/home/claude/caps/l3/menus2/`, `resumo-mais-*`, `justificativa-*`)
1. Folha de Termos/Roteiros sem título → o menu usa o nome do botão ("Ações do Termo #7").
2. **Paridade**: o legado anexava ofício, justificativa e termos por um seletor no mesmo
   modal; aqui só o ofício → "Anexar justificativa assinada…" quando a justificativa foi
   emitida (o ofício vira "Anexar ofício assinado…" para distinguir).
3. Teste e2e de "Baixar pelo resumo" esperava um botão que vive em "Mais ações" desde antes →
   corrigido (o teste; o produto já estava assim no Lote 2).
4. Conferido: Esc dentro do "Mais ações" do resumo fecha só o menu (a janela fica) e o foco
   volta ao botão; o toque fora na folha não aciona a linha de trás; HTMX trocando a lista com
   o menu aberto leva o véu junto.

**Medições finais** (`l3_menus.py --axe`, 11 estados × 1440/768/390/360 = 44 + resumo 4 +
Numeração 16): **0 violações axe**; painel sempre dentro da janela (ex.: rascunho do gestor
577 px de 315 a 892 a 1440; folha 643 px a 390); foco inicial em "Ver resumo" em todos.
Numeração: 0 rolagem lateral nas 4 larguras; operador e consulta 403.

## 4. Benchmark com o legado (cliques; legado em :8001, somente leitura)
| Tarefa | Legado | Novo — antes do Lote 3 | Novo — agora | Vence |
|---|---|---|---|---|
| Baixar documentos de um ofício | ⋮ → Baixar documentos → Baixar = **3** | título → Mais ações → Baixar documentos → Baixar = 4 | ⋮ → Baixar documentos… → Baixar = **3** | empate (e o menu nunca sai da tela; o do legado corta embaixo a 1440×900) |
| Anexar assinado (ofício) | ⋮ → Anexar → escolher o documento → arquivo → Enviar = **4** + arquivo | título → rolar até as vias → Anexar → arquivo → Anexar = 4 + arquivo | ⋮ → Anexar assinado… → arquivo → Anexar = **3** + arquivo | **novo** |
| Marcar complementar | ⋮ → Ofício complementar = **2** (também num emitido: o PDF já gerado fica diferente do dado) | abrir a folha → campo "marcador" → salvar ≥ 3 | ⋮ → Marcar como complementar = **2**, só no rascunho, com o efeito escrito e a exclusão avisada | **novo** (mesmos cliques, sem dessincronizar o PDF) |
| Definir o piso | Numeração (cabeçalho) → ano + número → Salvar = **2** + digitação; não mostra próximo nem lacunas | impossível (sem tela) | Mais → Numeração → número → Salvar = **3** + digitação; mostra o próximo e de onde vem, lacunas e histórico | legado por 1 clique; **novo** em informação (decisão D8: cabeçalho limpo) |

## 5. Testes executados
- Unitários novos: `test_dominio_marcador.py` (10), `test_dominio_numeracao.py` (10),
  `test_menu_oficio.py` (16: política por estado e perfil, justificativa, marcas, fragmento,
  404 de outra unidade, ≤ 12 consultas), `test_numeracao.py` (18: 403 para três perfis, "Mais"
  só do gestor, próximo e origem, efeito do piso, lacuna abaixo do piso, mesmo piso,
  validações, ano fora da faixa, ano encerrado, histórico da trilha, ≤ 14 consultas).
- Suítes tocadas: `test_views`, `test_assinados`, `test_servicos`, `test_pacotes`,
  `test_ordens`, `test_planos`, `test_termos`, UI Lab, tokens, comentários de template, CSS por
  página, navegação — **925 passed** (as 3 falhas da 1ª rodada — orçamento do resumo e regex
  das fichas — corrigidas e reexecutadas: verdes).
- E2E novos `tests/e2e/test_menu_oficio.py` (11): teclado (↓/↑/Home/End/volta, Esc devolve o
  foco), inativo focável que não age, nome × descrição, painel dentro da janela em 5
  larguras, toque fora só fecha, Baixar e Ver resumo pelo menu com o foco de volta ao ⋮,
  marcar complementar, consulta só lê, axe com o menu aberto (1440/390), operador sem "Mais"
  e 403, "Mais" → Numeração do gestor (erro com foco e axe, piso salvo, histórico).
- E2E de regressão: `test_preview_demo` (6 larguras), fluxo (resumo, gaveta, erro de
  validação), ordens/planos/termos (menu do resumo), baixar, assinados, UI Lab, a11y de
  ofícios/roteiros/termos/painel/UI Lab.
- `ruff check .`, `mypy gestao config`, `tsc -p jsconfig.json`: limpos.

**Vermelhos que não são deste lote** (falham igual em `a10a831`, rodados lado a lado num
worktree): 6 de `test_fluxo_oficio` (folha do ofício: "Salvar rascunho", "Descrição do
transporte", combustível, minuta emoldurada, barra de status) e 4+5 de folhas de termo/OS/
plano/via da OS (`test_termos`, `test_ordens`, `test_planos`, `test_assinados`,
`test_baixar::…do_termo`, `test_acessibilidade::folhas…/termo_salvo…` — contraste de
`.texto-terciario` na folha do termo). São das folhas (próximas páginas da missão), não da
lista.

## 6. Pendências e riscos
- **Confirmar LP-32 com o dono do produto** (ver ⚠️ em LP-32).
- No toque não há "passar o mouse": a folha abre com "Carregando as ações…" por um instante.
- Termos assinados não estão no ⋮ do ofício (no legado estavam no seletor do modal): ficam na
  lista de Termos e na folha do termo.
- O "Mais" tem um item só (Numeração) até o eProtocolo existir.
- Herdados: RM1/RM2/M10 (Lote 1), M2, M9/M11 (aceitos).

## 7. Commits
`c98aa59` saneamento · `54843d0` componente no UI Lab · `c6f7362` LP-30 · `56a17ff` LP-32 ·
`7cb7416` LP-31 · `398f252` menores · `f612836` LP-33 · `168cca0` autocrítica (rodada 2) · este relatório.


## Nota do orquestrador (2026-10-07)
LP-32 (Numeração) revertido: a página tinha sido excluída a pedido do dono do produto em `4a3f835`. O "Mais" da barra continua como componente (`componentes/menu_mais.html`) e hoje não aparece, porque não há item; entra "Importar processo do eProtocolo" quando existir. Os testes e2e de Numeração saíram; ficou `test_lista_sem_mais_vazio`.

## 8. Correções pós-QA (`qa/oficios-lista-lote3.md`, `a25b9c6`)
> A Numeração (LP-32) foi revertida pelo orquestrador (`1eee6fc`, `864d7e7`: a página fora
> excluída a pedido em `4a3f835`); o "Mais" fica sem item até o eProtocolo. O que este
> relatório diz da Numeração nas §§1–7 é histórico.

**I1 — sessão expirada no ⋮ (corrigido na origem, para todo pedido assíncrono).** Não havia
padrão no projeto. `identidade.middleware.EntradaObrigatoriaMiddleware` (substitui o
`LoginRequiredMiddleware` do Django): navegação sem sessão continua indo ao login; pedido
assíncrono (HTMX, `Sec-Fetch-Dest: empty`, `X-Requested-With`, `Accept: application/json`)
recebe **401** com `X-Sessao-Expirada` e `{"mensagem": "Sua sessão terminou — entre de novo.",
"entrar": "/conta/entrar/?next=<página de origem>"}` (origem = `HX-Current-URL`/`Referer` do
mesmo site, nunca o fragmento); HTMX ganha `HX-Redirect` (recarrega no login e volta). No
front, `app.js` envolve o `fetch`: qualquer componente que receba esse 401 dispara
`pcpr:sessao-expirada` → aviso persistente com o link "Entrar de novo" (`pc-toasts` ganhou
ação em aviso). O menu diz no próprio painel: item "Entrar de novo — Sua sessão terminou —
entre de novo e volte para esta página", focado e anunciado. `l3_sessao.py` (sem alteração):
`menu com sessão expirada: Entrar de novo …`, `formulário de login dentro do menu? False`
(`/home/claude/caps/qa-l3/menu-sessao-expirada-1440.png`). Testes:
`identidade/tests/test_sessao_expirada.py` (navegação 302; 4 tipos de pedido assíncrono 401
com a volta certa; `HX-Redirect`; Referer de outro site ignorado) e e2e
`test_sessao_expirada_avisa_no_menu_e_nao_mostra_o_login`.

**Menores.**
- M1: o mouse só pede os itens parado ~120 ms sobre o ⋮; foco e toque pedem na hora.
- M3: falha ao carregar anunciada numa região viva (além do texto no item).
- M4: toque no véu no celular — o véu fica, transparente, até o "click" de compatibilidade;
  o foco volta ao ⋮ (e2e `test_toque_no_veu_devolve_o_foco_ao_botao_no_celular`, `has_touch`).
- M5: "Termos / Ordens / Planos deste ofício" só quando existem para quem vê (uma consulta
  para os três; teto do resumo 19→20 / 14→15, comentado no teste).
- M6: `test_operador_cria_preenche_e_emite_um_oficio` salva com Enter (o botão "Salvar
  rascunho" só existe escondido como botão padrão) e acha "Revisar e emitir" no cartão
  Documentos; passa desse ponto e **para logo depois**: depois de salvar, "Desmarcar Isabela…
  como motorista" não existe mais — o motorista parece desmarcado ao salvar a folha. É da folha
  do ofício (próxima página), **provável defeito de produto**: fica para ela. `test_preview_demo`
  volta a conferir "Salvo automaticamente às" na folha do ofício.

**M7 — menu longo: decisão.** Agrupar o que se faz uma vez por ofício, no lugar, sem submenu:
"Criar a partir deste ofício" (termo, OS, plano, cópia — quando há 2 ou mais) e "Retificado ou
complementar" (diz a marca de hoje) abrem dentro do menu (Enter/Espaço/→; ← recolhe). Ler,
levar, anexar e mudar a situação — o dia a dia — continuam a um clique; submenu voando ao lado
seria pior no toque e no leitor. Resultado: rascunho do gestor **14 → 10** itens à vista
(577 → 480 px a 1440, abre abaixo do botão em vez de ao lado; folha 643 → 546 px a 390),
emitido 11 → 8; Novo termo passa de 2 para 3 cliques (a lista de Termos tem "Novo termo deste
ofício"). axe: 10 estados × 1440/390 com o menu aberto, **0 violações**
(`/home/claude/caps/l3/menus4/`); teclado no e2e (`Enter` abre e foca o 1º item, `←` recolhe e
volta ao título, ↑/↓ pulam o grupo fechado). UI Lab e `components.md` atualizados.

**Testes desta rodada.** `test_menu_oficio.py` (18), `test_sessao_expirada.py` (6),
`test_views` (resumo, ciclo, lista: 68), e2e `test_menu_oficio` (13), `test_preview_demo` (6
larguras), resumo/baixar, fluxo (resumo) — verdes. Vermelhos só das folhas (iguais antes):
`test_fluxo_oficio::test_operador_cria…` (ver M6), `test_termos/ordens/planos::…a_partir_do_
oficio` (o passo do menu, agora com o grupo, passa; param na folha do termo/OS/plano).
`ruff`, `mypy`, `tsc` limpos.
