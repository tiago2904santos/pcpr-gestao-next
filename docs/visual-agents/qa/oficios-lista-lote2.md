# QA — Lista de ofícios, Lote 2 (LP-20 a LP-27, comportamento da lista)

> Agente 3 — QA/Benchmark · 2026-10-07 · branch `viagens/reconstrucao` @ `5c777af`.
> Bases: Lote 1 aprovado (`ddc9daf`, worktree `/home/claude/l1-wt`, `:8003`), `main`
> (`b47e2d5`, `/home/claude/main-wt`, `:8002`), LEGADO (`:8001`; nenhum dado real aqui,
> só contagens). Chromium 141. Evidências fora do repositório: `/home/claude/caps/qa-l2/`
> (`{l1,novo}/<largura>/*.png`, `estados/*.png`). Scripts em `/home/claude/tools/qa/`:
> `abas_legado.py`, `contadores.py`, `links_xlsx.py`, `l2_interacoes.py`, `voltar.py`,
> `gaveta_teclado.py`, `gaveta_mouse.py`, `cal390b.py`, `pickers390.py`, `erro_foco.py`,
> `exportar_oob.py`, `axe_l2.py`, `contraste_l2.py`, `regressao_l2.py`, `consultas_l2.py`,
> `l2_telas.py`, `e2e_tres.sh`.

## Veredito: **REPROVADO** (1 bloqueante)

O comportamento da lista está correto e bem feito: as abas batem **ofício por ofício** com a
regra do legado, os contadores conferem com o que cada clique mostra (14 recortes, 0
divergências), os endereços antigos e os links de outras telas chegam onde devem, a planilha
leva o recorte da tela, F1–F8 estão fechados e o axe está limpo em 95 execuções. O que
reprova é a **gaveta como folha inferior no celular**: os calendários de período e a lista de
Veículo ficam cortados e não dá para escolher pelo toque — uma regressão funcional em
relação ao Lote 1 em filtros que este lote acabou de promover.

## 1. BLOQUEANTE

### B1 — Folha inferior (< 768 px): calendários e "Veículo" cortados, sem alvo para o toque
A 390/360, ao abrir "Período de saída" ou "Data do ofício", o calendário abre **para cima** e
é recortado pelo topo da folha: só a última semana e "Hoje/Limpar" aparecem — **16 de 46
alvos clicáveis**, sem as setas de mês (`cal390b.py 8000`). No Lote 1 (`:8003`), na mesma
largura: **46 de 46**. A lista de "Veículo" abre para baixo e sai da tela: **3 de 8** opções
ao alcance (`pickers390.py`). "Ordenar por" (6/6) e "Ano" (4/4) funcionam. Pelo teclado
funciona, pelo toque não — e o celular é o lugar da folha.
Reproduzir: `/viagens/oficios/` a 390×844 → Filtros → ícone do calendário de "Período de
saída" (`estados/cal-390.png`); "Veículo" (`estados/picker-veiculo-390.png`).
Correção sugerida: dentro de `.filtros__avancados--rodape`, os painéis de `pc-data` e
`pc-select` abrem para baixo/acima conforme o espaço **da folha** (ou viram painel em tela
cheia), e a folha não corta o que transborda.

## 2. IMPORTANTES (corrigir neste lote)

- **I1 — A folha inferior parece modal, mas não é.** Com a folha aberta a 390: Tab sai dela
  e o foco vai para as fichas e as linhas **por trás do véu**, invisível (Tab 13–16;
  WCAG 2.2 — 2.4.11 Foco não encoberto); a página rola por trás (600 px com a roda); e, ao
  abrir, o foco fica no botão "Filtros" — o relatório diz que vai ao 1º campo, mas o código
  procura `.filtros__avancados select`, que é o `<select>` escondido do `pc-select`.
  `gaveta_teclado.py`. Sugestão: `inert` no resto da página (ou fechar ao sair o foco),
  travar a rolagem do fundo e focar o 1º controle visível.
- **I2 — "Tentar de novo" perde o foco.** Depois do erro de rede, Enter em "Tentar de novo"
  devolve a lista, mas o foco cai no `BODY` (o botão some). `erro_foco.py`. Levar o foco ao
  título dos resultados ou à busca.
- **I3 — Documento "Todos" não fecha a conta.** "Todos 41 · Rascunhos 5 · Emitidos 35" (ano
  2025), "Todos 158 · 29 · 120" (ano 2026): a diferença são os cancelados, que contam em
  Todos e não têm opção própria. Coerente com D1, mas os números à vista não somam — quem
  confere acha erro. Decidir com o orquestrador: excluir cancelados de "Todos" do Documento
  (eles têm a aba), ou dizer isso no rótulo/descrição acessível.
- **I4 — 1ª tela a 390×844 abaixo da meta nos estados mais usados.** Normal 3,42 ✓, mas com
  **busca 2,75** e com **Rascunhos 2,83** (`l2_telas.py`). Com busca, o cabeçalho "Resultados
  para … · 28 ofícios" repete o 28 que já está na aba e no Documento (três vezes na tela).
- **I5 — Barra entre ~800 e ~1000 px.** A 900, Busca + Documento ocupam a 1ª linha e o botão
  "Filtros" fica **sozinho numa 2ª linha** (barra 120 px); com filtros valendo, 3,23 ofícios
  na 1ª tela contra 4,15 no Lote 1. A 768 a quebra é outra (Busca / Documento + Filtros).
  `estados/8000-fichas-900.png`. Uma regra só: Documento e Filtros sempre juntos.

## 3. MENORES
- Com a gaveta aberta no desktop, as fichas recém-criadas ficam por baixo dela até fechar
  (`estados/gaveta-aberta-fichas-1440.png`); o número no botão avisa.
- Documento escolhido aparece duas vezes (segmentado marcado + ficha "Documento: …").
- Painel: "Viagens em 30 dias: 32" leva a "Que vão acontecer" (46, inclui sem data e além de
  30 dias). Já era desigual no Lote 1 (38); agora que há filtro de período, o link pode ser
  exato (`saida_de=hoje&saida_ate=hoje+30`).
- `ordem=-numero` entra na URL depois de qualquer busca ao vivo (inofensivo, polui o link).
- Excluir rascunho com `voltar` contendo `q=` volta à lista sem a busca (pré-existente no
  `main`, `views.py` l. 800).
- Links `?resumo=pk` de Roteiros/Termos/Pacotes/Conferência para um ofício **arquivado** abrem
  a janela sobre uma lista onde ele não aparece (`url_na_lista` resolve; esses quatro não
  usam).
- Busca ao vivo no celular: o fade lateral das fichas esconde "Limpar tudo" sem indício além
  do esmaecido.
- CPU de renderização de `/viagens/oficios/` +24 % (96 → 119 ms, mediana de processo) e
  `?documento=rascunho` +45 % — dentro do aceitável; vale um olhar no custo das opções da
  gaveta.
- Pendências herdadas: RM1/RM2 do Lote 1, M5, M10.

## 4. Funcional, item a item

| LP / defeito | Verificação | Resultado |
|---|---|---|
| LP-20 abas × legado | `abas_legado.py`: regra do legado (`abas.py` q_da_aba) reescrita à parte e aplicada aos 258 ofícios do PREVIEW, comparada com **todas as páginas** de cada aba | futuros 46 = 46, andamento 189 = 189, prestadas 2 = 2, cancelados 18 = 18 — **conjuntos idênticos**; 1ª saída hoje (3) em "andamento"; sem data (13) em "futuros"; aba × documento (4 combinações) idênticos |
| LP-20 Documento | rascunho 42, emitido 195, arquivado 3 — conjuntos idênticos; arquivado fora de "Todos" | OK (I3) |
| F7 contadores | `contadores.py`: 14 recortes (busca, placa, acento, documento, ano, diárias, período, protocolo, combinações) × 9 contadores = clique a clique | **0 divergências** |
| Endereços antigos | `?situacao=` × 9 valores × 3 variações → 302 para o equivalente, preservando busca/ordem/página; `documento=` explícito vale sobre a tradução; Exportar aceita os antigos | OK |
| Links para a lista | painel (4 destinos), Ctrl+K (emitido, cancelado, **arquivado → `documento=arquivado`**), `url_na_lista` | OK (menores acima) |
| LP-21 gaveta (desktop) | fechada ao carregar com filtro; Enter abre; Esc fecha e devolve o foco; clique fora fecha; "Fechar" devolve o foco; ordem/ano/período por mouse e teclado sem fechar; digitar diárias não perde o foco nem o texto | OK |
| LP-21 gaveta (celular) | ver **B1** e **I1** | **falha** |
| F8 fichas/limpar | remover uma ficha tira só ela; "Limpar tudo" mantém busca e aba; "Limpar filtros" da gaveta mantém busca, aba e Documento | OK |
| LP-22 busca | F1 placa (com e sem hífen, minúscula): 3/3; F2 "curitiba" 156 → 1; F4 "reuniao" acha "reunião" (28); refino de uma leitura ("1234": "Nada na busca geral. Procure só em: Protocolo com 1234") | OK |
| LP-23 / F5 | vazio com só filtro da gaveta: "Nenhum ofício combina com todos os filtros juntos"; com busca + filtro + aba: "Limpar filtros" (fica busca e aba), "Limpar busca", "Ver todos"; erro de rede e 500: alerta no lugar da lista, texto certo para cada caso, "Tentar de novo" refaz | OK (I2) |
| LP-24 / F3 | POST interceptado e abortado (nada gravado): Cancelar e Arquivar, pelo ⋮ e pela janela de resumo, depois de busca HTMX → `voltar=/viagens/oficios/?q=reuniao&documento=emitido&…` | OK |
| LP-25 consultas | 16 sem busca; 18 com busca, placa e com **todos** os filtros juntos; Exportar 12 (10 com busca); `TestConsultasDaListaLote2` (20 e 200 ofícios) verde | OK (≤ 20) |
| LP-26 contagens | "Página 1 de 13" sem filtro; "41 de 255 ofícios" filtrado; mês com contagem ("20 nesta página"); h2 só para leitor sem busca | OK (I4: repetição com busca) |
| LP-27 XLSX | 14 colunas, datas e valor como tipos reais; Situação "Arquivado" (3); Tipo com marca ("Autorização · Complementar", "Convalidação · Complementar"); recorte = tela (todos 255, arquivados 3, "reuniao" 28, cancelados 18, rascunho+futuros 23); link de Exportar acompanha a busca ao vivo | OK |

## 5. Regressões nos componentes compartilhados
`regressao_l2.py`, 26 rotas × 1440/1024/768/390/360, Lote 1 (`:8003`) × agora: **0
diferenças** de status, rolagem, nº de linhas, alturas e fontes nas 130 combinações. A
gaveta das outras listas (Coffee, Eventos, Imprensa, Palestras, Publicações) continua
abrindo sozinha com filtro, agora com Esc/clique fora; erro da busca ao vivo também em
Roteiros (axe limpo).

## 6. Acessibilidade
- axe (wcag2a/aa, 2.1, 2.2aa, best-practice) — `axe_l2.py`: 19 estados (normal, as 4 abas,
  Rascunhos, Arquivados, gaveta aberta, fichas, refino, refino de uma leitura, vazio
  filtrado, erro, ⋮ aberto, resumo, Roteiros com erro, gaveta do Coffee, Eventos, UI Lab) ×
  1440/1024/768/390/360 = **95 execuções, 0 violações** (o M8 do Lote 1 sumiu).
  axe não vê I1.
- Teclado: Busca → Documento (uma parada; setas trocam, o foco fica no rádio após o HTMX) →
  Filtros → fichas → linhas; gaveta como no §4.
- Contraste (`contraste_l2.py`): aba vazia 4,86:1; contagem do Documento 5,72 (não
  marcado) / 10,16 (marcado); rótulo "Documento" 6,47; ficha 16,67; × da ficha 6,75;
  contagem do mês 6,75; alerta 6,59. Nada abaixo de 4,5:1.

## 7. Desempenho (`consultas_l2.py`, PREVIEW; CPU de processo, mediana de 9)
| Rota | Consultas L1 → L2 | CPU L1 → L2 | HTML L1 → L2 |
|---|---|---|---|
| `/viagens/oficios/` | 16 → 16 | 96 → 119 ms | 153,7 → 156,6 KiB |
| `?q=curitiba` | 17 → 18 | 94 → 64 ms (F2: 1 resultado) | 153,2 → 42,9 KiB |
| `?q=reuniao` | 14 → 18 | 40 → 108 ms (F4: 0 → 28 resultados) | 34,1 → 153,6 KiB |
| todos os filtros + busca | 17 → 18 | 50 → 91 ms | 43,3 → 47,1 KiB |
| `?documento=rascunho` | 16 → 16 | 87 → 126 ms | 154,6 → 159,2 KiB |
| Exportar (255 linhas) | 11 → 12 | 236 → 256 ms | — |
| Roteiros / Termos / painel / Coffee / Eventos | iguais | iguais (ruído) | iguais |

## 8. Os três e2e "pré-existentes" (pedido do orquestrador)
`e2e_tres.sh` rodou os mesmos testes em `main` (`b47e2d5`), Lote 1 (`ddc9daf`) e agora
(`5c777af`), em sequência: **as mesmas falhas nos três**.
- `test_registro_da_lista_abre_resumo_em_janela_e_fecha_com_esc`: espera "Minuta"; o rodapé
  diz "Ver minuta" desde antes do `main` (o `to_contain_text` diferencia maiúsculas).
- `test_erro_de_validacao_aparece_no_resumo_e_no_campo` e `test_preview_demo`: `Timeout` em
  `get_by_role("button", name="Salvar rascunho")` (ou `^Salvar( rascunho)?$`) — igual no `main`.
- `test_preview_demo`: rolagem lateral de 257/78 px da navegação de módulos a 768/1024 —
  igual no `main`.
Conclusão: **pré-existentes**, não introduzidos pelo Lote 1 nem pelo Lote 2. Não bloqueiam,
mas são testes vermelhos na suíte: alguém precisa consertá-los (ou o código, ou o teste).

## 9. Benchmark legado × novo (`benchmark_lote2.py` + `benchmark.py`)
| Tarefa | Legado | Novo | Vence |
|---|---|---|---|
| Ver rascunhos | sem filtro de situação na lista | 1 clique, sem recarga, 20/20 rascunhos | **novo** |
| Ver o que vai acontecer | 1 clique (recarga) | 1 clique; mesmo conjunto que a regra do legado | empate |
| Filtrar por ano | 3 cliques + recarga | 3 cliques, sem recarga, com ficha | **novo** |
| Remover um filtro | 1 clique (recarga) | 1 clique | empate |
| Achar por placa | 0 resultados | 3/3 | **novo** |
| Achar por número / destino / servidor | 1º lugar | 1º lugar | empate |
| Linhas na 1ª tela, 1440×900 | 7,2 | 6,8 (era 6,3 no Lote 1) | legado, por pouco |
| Linhas na 1ª tela, 390×844 | 1,39 | 3,42 (2,75 com busca) | **novo** |
| Período de saída no celular | calendário usável | **cortado (B1)** | **legado** |

## 10. Crítica visual independente
- **1ª tela a 390**: boa no estado normal (Busca e Filtros numa linha, Documento rolando de
  lado), abaixo da meta com busca/Rascunhos (I4).
- **Barra a 768/900**: duas formas diferentes de quebrar; a 900 o botão "Filtros" fica órfão (I5).
- **Fichas sob a gaveta aberta**: no desktop a gaveta é um painel sobre a lista e cobre as
  fichas; aceitável porque o contador muda, mas a ficha nova não é vista até fechar (menor).
- **Documento "Todos" com cancelados**: os números do segmentado não somam (I3).
- **Legenda "Documento"** encosta na opção marcada a 768 (o "Todos" escuro toca a borda) —
  ainda visível em `estados/8000-normal-768.png`; menor.
- A folha inferior em si é bem desenhada (título e rodapé presos, véu, rótulos na borda);
  o defeito é o que abre dentro dela (B1) e o que escapa dela (I1).

## 11. Para aprovar
B1 corrigido com `cal390b.py 8000` = 46/46 a 390/360 e `pickers390.py` com todas as opções
clicáveis; I1–I5 tratados (ou I3 decidido pelo orquestrador); reexecutar `axe_l2.py`,
`regressao_l2.py` e `l2_interacoes.py`.

---

## Re-QA — correções `adb04fd`, `cc759f8`, `f6d439f` · veredito: **APROVADO**

> Agente 3 · 2026-10-07 · branch @ `f6d439f`, Lote 1 em `:8003`. Medições próprias em
> `/home/claude/tools/qa/` (`alvos_folha.py`, `reqa_l2_modal.py`, `fichas390.py`,
> `l2_telas.py`, `axe_l2b.py`, `regressao_l2.py`, `outros_pickers.py`, `erro_msg.py`);
> capturas em `/home/claude/caps/qa-l2/reqa/`.

**Sobre a medição de B1.** O Designer tem razão num ponto: `cal390b.py`/`pickers390.py`
filtravam o painel por `offsetParent`, que é `null` em elemento `position: fixed` — na
versão nova (painel na camada de topo) eles não achariam o painel. A medição do QA original
continua válida para aquele código (o painel não era fixo; a captura `estados/cal-390.png`
mostra o calendário cortado). Para o re-QA não usei nenhum dos dois scripts: `alvos_folha.py`
acha o painel aberto por `:popover-open` (ou pelo `aria-controls` do gatilho), mede **cada
alvo** (dias, setas com `aria-label`, Hoje/Limpar, opções) por `elementFromPoint` no centro e
exige que esteja dentro da tela — e ainda faz **cliques reais**.

| Item | Medição própria | Resultado |
|---|---|---|
| **B1** | 390 e 360: Período **46/46**, Data do ofício **46/46**, Veículo **8/8**, Ordenar 6/6, Ano 4/4 (no topo e na tela); clique real em 12 e 16 do calendário e na última opção de Veículo → `saida_de=12/10/2026&saida_ate=16/10/2026&veiculo=sem`, folha continua aberta. Coffee, Eventos e Imprensa (que não usam a folha) iguais ao Lote 1: 46/46 a 1440 e 390 | **corrigido** |
| **I1** folha modal | `role="dialog"`, `aria-modal`, rotulada por "Filtros e ordem"; 19 elementos `inert`; foco inicial no gatilho visível de "Ordenar por"; 30 Tab + 30 Shift+Tab sem sair e sem foco encoberto; rolagem por trás **0** (era 600); Esc com calendário aberto fecha só o calendário; Esc seguinte fecha a folha, devolve o foco a "Filtros" e tira todo `inert` e a trava; toque no véu idem; girar para 1280 com a folha aberta desfaz o modal | **corrigido** |
| **I2** | "Tentar de novo" → foco em `H2#titulo-resultados` ("Resultados para “reuniao”: 29 ofícios") | **corrigido** (ver M-R3) |
| **I3** | `#conta-doc-todos` ausente em todos os estados e larguras; Rascunhos/Emitidos/Arquivados com número | **corrigido** (decisão do orquestrador) |
| **I4** 1ª tela 390/360 | normal 3,42 · Rascunhos 3,20 · busca 3,13 · **busca + Rascunhos 3,00** · 6 filtros 3,01 | **corrigido** (no limite com busca + Rascunhos) |
| **I5** barra | Busca e Filtros na mesma linha em 1440/1280/1024/900/820/768 (barra 73 px); 900 com filtros 3,23 → **4,14**; 768 normal 4,15 → **4,59** | **corrigido** (ver M-R4) |
| Fichas < 1280 | 1024/768/390: as 6 fichas e "Limpar tudo" alcançáveis por Tab; "Limpar tudo" tira o Documento e mantém busca e aba | **ok** (ver M-R1, M-R2) |
| axe | 23 estados (os 19 do QA + folha com calendário aberto, folha com Veículo aberto, busca + Rascunhos, depois de "Tentar de novo") × 1440/1024/900/768/390/360 = **138 execuções, 0 violações** | **ok** |
| Regressões | 26 rotas × 1440/1024/900/768/390/360 contra o Lote 1 = **156 combinações, 0 diferenças** (status, rolagem, linhas, alturas, fontes); gaveta desktop, fichas, Limpar, vazio, refino, Documento pelo teclado, erro e "Tentar de novo" iguais ao QA (`l2_interacoes.py`) | **ok** |

### Menores novos (não bloqueiam)
- **M-R1** A 390, ao focar o × de uma ficha perto da borda ("Veículo: Sem transporte"), o
  trilho rola só o suficiente: o × fica com ~6 de 21 px à vista, sob o esmaecido
  (`reqa/ficha-foco-390.png`). Não é "foco totalmente encoberto" (2.4.11 passa), mas o anel
  quase não aparece. `scroll-padding-inline` no trilho resolve.
- **M-R2** "Limpar tudo" está no começo do trilho só visualmente (`order`): na ordem do
  Tab ele é o último, depois da última ficha — o foco salta do fim do trilho para o começo.
  Pôr o link no começo do DOM.
- **M-R3** Depois de "Tentar de novo" o foco vai para um título que só existe para leitor
  de tela: quem usa teclado sem leitor não vê onde o foco está (o próximo Tab segue certo).
- **M-R4** A 768 a busca fica com 178–207 px e o texto de ajuda corta ("Número, protocol").
  Troca consciente (uma linha a mais de lista); vale um placeholder curto nessa faixa.
- Continuam do QA: fichas sob a gaveta aberta no desktop, link "Viagens em 30 dias" do painel,
  `ordem=-numero` na URL, `?resumo=` de outras telas para arquivado, os 3 e2e vermelhos
  pré-existentes (iguais no `main`).

**Veredito do Lote 2: APROVADO.** Nenhum bloqueante nem importante em aberto; os menores
acima vão para a lista de pendências.
