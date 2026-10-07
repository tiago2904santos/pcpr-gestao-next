# QA — Lista de ofícios, Lote 1 (LP-01 a LP-12, componentes compartilhados)

> Agente 3 — QA/Benchmark · 2026-10-06 · branch `viagens/reconstrucao` @ `72179cb`.
> Comparado com o `main` (`b47e2d5`) servido de um worktree em `:8002`, com o mesmo banco
> PREVIEW (o branch não tem migrações novas: `git diff main --stat -- '*/migrations/*'` vazio),
> e com o LEGADO em `:8001` (dados reais: **nenhum nome, número, placa ou protocolo do legado
> aparece aqui**; só contagens e medidas).
> Evidências fora do repositório: `/home/claude/caps/qa-l1/{main,novo}/<largura>/*.png`
> (26 rotas × 5 larguras × 2 sistemas), `/home/claude/caps/qa-l1/estados/*.png`,
> `/home/claude/caps/qa-l1/*.png`. Scripts: `/home/claude/tools/qa/*.py`
> (`regressao_listas.py`, `titulos.py`, `quebra_titulo.py`, `truncamento.py`, `axe_estados.py`,
> `teclado.py`, `abas.py`, `benchmark.py`, `consultas.py`, `consultas_cpu.py`, `peso.py`,
> `contraste.py`, `pousar.py`, `selos_todas.py`) e `/home/claude/tools/main_server.sh`.

## Veredito: **REPROVADO**

O Lote 1 cumpre bem o que prometeu **nas três listas-alvo** (Ofícios, Roteiros, Termos):
linhas de altura constante, colunas que se leem de cima para baixo, selo de tempo único,
orçamento de selos respeitado em 258 de 258 linhas, ⋮ com contraste cheio, axe limpo,
teclado correto, consultas iguais às do `main`. Mas os componentes são compartilhados e o
lote **quebrou duas telas que não foram medidas** — o painel de Viagens e as listas de
outros módulos (Usuários com rolagem horizontal de 310–566 px; Publicações, Coffee e
Eventos com títulos partidos em três linhas). "Sem nenhuma regressão" é critério de
concluído da missão; com B1 e B2 abertos o lote não pode ser aprovado. As correções são
localizadas (escopo de dois blocos de CSS) — o resto do lote pode ficar como está.

## 1. Achados BLOQUEANTES

### B1 — `.registro__titulo` sem quebra (≥ 768 px) vale para TODAS as listas e quebra quem não aderiu
`static/css/listas.css` l. 751–762: `.registro__titulo { flex-wrap: nowrap }` e
`.registro__titulo > .selo { flex: none }` estão sem escopo — valem para as 40 telas com
`.registro`, não só para as que usam `registro__meta--colunas`.
- **Usuários** (`/cadastros/usuarios/`, usuário DEMO com 8 perfis): selos inteiros não
  encolhem → saem da linha, passam por cima do ⋮ e do nome; **rolagem horizontal de 310 px
  a 1024 e 566 px a 768** (`main`: 0). A 1440 o selo já sai 90 px da linha.
  Evidência: `qa-l1/usuarios-novo-1024.png` × `usuarios-main-1024.png`.
- **Publicações** (`/publicacoes/pautas/`): a 768, **18 de 20** títulos espremidos em 3 linhas
  de ~170 px ao lado dos selos (`main`: 0); a 1024, 4 de 20. Linhas de 93 → 129 px.
  `qa-l1/pautas-768-8000-top.png` × `pautas-768-8002-top.png`.
- **Eventos** (`/eventos/solicitacoes/`, 768): "Palestra · Curitiba" vira três linhas
  ("Palestra" / "·" / "Curitiba") com os selos no meio. `qa-l1/eventos-768-r4-8000.png`.
- **Coffee** (`/coffee/`, 768): 5 de 20 títulos em duas linhas com os selos boiando à direita.
Reproduzir: `uv run python /home/claude/tools/qa/titulos.py 8000` (e `8002` para o main) e
`quebra_titulo.py`. Correção sugerida: restringir o bloco a
`.registro:has(> .registro__corpo > .registro__meta--colunas)` (como o LP-10 já faz no celular)
ou a `.registro__titulo:has(> .registro__selos)`.

### B2 — Painel de Viagens: colunas decididas pela largura da JANELA dentro de um cartão estreito
`/viagens/` inclui `oficios/_registro.html` num cartão de ~715 px (a 1024) / ~914 px (a 1440),
mas `.registro__meta--oficio` troca de grade por `@media (min-width: 1024px)` (l. 802).
Resultado a **1024: Equipe com 77 px e Transporte com 55 px — 10 de 10 cortados** ("Ren…",
"ZZG…", "Sem diárias c…"); a 1440, 8 de 10 cortados. No `main` o painel mostrava os nomes
inteiros. Evidência: `qa-l1/novo/1024/viagens.png` × `qa-l1/main/1024/viagens.png`,
`qa-l1/painel-lista-1440-top.png`; números em `truncamento.py`.
O mesmo defeito aparece no cartão do UI Lab (seção 21). Correção sugerida: container queries
(`container-type: inline-size` na `ul.registros` e `@container` nas variantes `--colunas`) —
é o que torna a linha realmente um componente; alternativa mínima: variante sem colunas no
painel.

## 2. Achados IMPORTANTES (corrigir neste lote)

### I1 — Roteiros no celular: a caixa "Usado em N ofícios" vaza 183 px para a direita
A 390, o item "Usado em" foi para a coluna da direita da grade do celular; o painel
`.menu__painel--esquerda` ancora a borda esquerda no botão (x = 211) e passa da tela: a página
ganha **183 px de rolagem horizontal** e o conteúdo fica cortado. No `main`, x = 28, sem
rolagem. Reproduzir: `/viagens/roteiros/` a 390, Tab até "Usado em 1 ofício" (ou toque).
`uv run python /home/claude/tools/qa/pousar.py 8000` × `8002`; `qa-l1/estados/pousar-390.png`.

### I2 — Detalhe das diárias cortado no meio da conta ("10 × 1…", "18 × …")
≥ 1280 px a coluna de 11rem mostra "R$ 12.790,68 · 10 × 1…": em Ofícios 6 de 20 linhas, em
Roteiros 8 de 20, no painel 2 de 10. Um número truncado no meio é pior que nenhum
("10 × 1" lê-se como uma conta completa). É justamente a coluna da tarefa "ler as diárias".
Sugestão: o detalhe só aparece quando cabe inteiro (ou vira "· 12 diárias"); o completo já
está no `title` e no resumo. Evidência: `qa-l1/novo/1440/viagens-oficios.png` (159/2026,
156/2026), `viagens-roteiros.png` (#67, #58).

### I3 — Motorista: o ícone `circle-dot` não diz "motorista"
Quem enxerga perdeu o "(motorista)" por extenso do `main` e ganhou um círculo com ponto que
lembra um botão de opção ou "gravando"; o significado só existe no `title` (mouse) e no texto
para leitor de tela (que está correto: "Nádia … (motorista)"). No legado o texto é explícito
— nesta tarefa o legado vence. Sugestão: símbolo próprio de volante no sprite
(`vendor_assets.py`), ou manter o ícone com uma marca visível curta ("mot.") até haver o
símbolo; decidir com o dono do produto, como o próprio Designer registrou.

## 3. Achados MENORES (podem ir para lotes seguintes)
- **M1 Hover pinta botões de texto de outras listas**: `.registro:hover .registro__acoes
  .botao--sutil:not(:hover)` (`listas.css` l. 840) dá fundo a "Despachar", "Abrir",
  "Andamento" etc. em Eventos/Coffee/Publicações — parece botão pressionado. Restringir a
  `.botao--icone`.
- **M2 Fonte da meta no celular subiu em todas as listas** (10,8 → 11,7 px, D11): correto,
  mas linhas de Eventos/Palestras/Publicações cresceram 3–20 px a 360–390 por quebra extra.
  Registrar como efeito aceito ou ajustar nessas telas.
- **M3 Rótulos de vazio cortados**: "Sem diárias calculadas" na coluna de 7,5rem (768–1279)
  e no celular; "Sem servidor (só o genérico)" em Termos a 390. Usar rótulos curtos
  ("Sem diárias", "Só o genérico").
- **M4 Termos: "Sem destino" no título** em estilo normal, enquanto "Sem período" ao lado é
  itálico de vazio.
- **M5 Tipo × situação**: "○ Rascunho" e "↻ Convalidação" são dois selos neutros cinza
  colados — o tipo não se distingue da situação de relance.
- **M6 Roteiro cancelado**: o título estático (`registro__link--estatico`) fica escuro no
  hover (rgb 31,30,27) sem ser clicável; Ofícios/Termos ficam dourados porque são link.
- **M7 UI Lab, seção 21**: a linha "Ofício 126/2026 cancelado" não tem `registro--inativo`,
  ao contrário do que o produto faz depois da autocrítica (cancelado sempre recua) — a vitrine
  contradiz a regra. Também herda B2 (colunas por largura de janela dentro do cartão).
- **M8 axe a 390 com o ⋮ aberto em Termos**: `target-size` no título da 4ª linha, coberto
  pelo painel do menu. Transitório (popup aberto pelo usuário), mas sai no relatório do axe.
- **M9 1ª tela a 390×844**: 2,55 ofícios (meta do plano: ≥ 3). Rolando, 6,17. Depende da
  gaveta de filtros (Lote 2, LP-21).
- **M10 Ícone de transporte**: "Aeronave comercial" com ônibus quando `transporte_meio` está
  vazio (dados DEMO; pendência declarada).
- **M11 Peso do HTML**: Ofícios 125,6 → 152,2 KiB (+21%), parcial HTMX 93 → 120 KiB (+29%),
  painel +28% — por `title`/`sr-only` por linha. Comprimido: +1,8 KiB. Aceitável.
- **M12 Relatório do Designer**: §2 diz "0 de rolagem no UI Lab" — há 77 px a 1024 e 257 px a
  768 (a navegação global dos módulos; **pré-existente**, igual no `main`, idem em
  `/notificacoes/`). §6 diz que o resultado do navegador e do `verificar.sh` está no Log de
  `current-page.md` — o Log não tem entrada do Lote 1 e a página ainda diz "Lote 1 em
  andamento".

## 4. Verificação item a item (LP-01…LP-12)

| LP | Implementado como descrito? | Evidência | Situação |
|---|---|---|---|
| 01 | Sim: título inativo `--cor-texto-terciario` (rgb 111,107,100, 5,30:1); hover devolve o dourado em Ofícios/Termos | `inativo.py`, `estados/inativo-*.png` | OK (M6) |
| 02 | Sim: `--z-grupo-lista: 2` > `--z-linha-acoes: 1`; ao rolar, nenhum ⋮ pinta sobre o cabeçalho de mês (1440 e 390) | `estados.py`, `estados/lp02-sticky-*.png` | OK |
| 03 | Sim: opacidade 1, ícone rgb(95,91,84) = 6,75:1; axe com menu aberto passou a 0 (o `main` tinha `target-size` no ⋮ em Ofícios, Roteiros e Termos) | `medir_lista.py`, `axe_estados.py` | OK — melhora |
| 04 | Sim: `.selo--neutro` declarado; 5,72:1 | `contraste.py` | OK |
| 05 | Sim: rótulo 9,9 px (5,84:1); cancelada risca só o número | `estados/lab21-*.png`, Termos #6 | OK |
| 06 | Sim, nas três listas e no painel; 0 "há N dias" em 258 linhas; vocabulário igual em Ofícios/Roteiros/Termos/resumo | `selos_todas.py` (faltam N dias 34, amanhã 3, começa hoje 2, em andamento · até 2, volta hoje 2) | OK |
| 07 | Sim: máximo 3 selos (situação + tipo incomum + 1 alerta), nunca 2 alertas (258/258); tipo: Convalidação 26, Complementar 9, Retificado 7, Convalidação · Complementar 1; resumo com Tipo + porquê | `selos_todas.py`, `estados/kb-resumo-1440.png` | OK (M5) |
| 08 | Sim: destinos ≤ 3 + "+N" visível fora do corte; `title` com a lista; leitor ouve "Ofício 144/2026 · A, B, C e mais 1 destino" | `mais_n.py`, `estados/maisN-*.png` | OK |
| 09 | Sim nas três listas: ≥ 1024 altura 71–72 (Termos 70–72), 768: 92–93; colunas no mesmo x nas três listas | `medir_lista.py` | OK nas listas; **falha no painel (B2)**; I2 |
| 10 | Sim: placa, título e ⋮ na mesma linha; 109–110 px (133 com 3 selos); 6,17 ofícios/tela rolando | `medir_lista.py` | OK (M9); **I1** |
| 11 | Sim: anel interno `--anel-foco-interno` arredondado nas abas; `summary` com `--anel-foco`; `data-rola` + máscara; aba ativa centralizada a 360/390/768 (Arquivados, Cancelados); reaplica após HTMX | `abas.py`, `estados/abas-foco-*.png`, `htmx_console.py` | OK |
| 12 | Seção 21 existe, cobre selo de tempo (9 casos), tipos, alerta, linhas e abas | `estados/lab21-*.png` | OK com M7 e B2 |

**Rolagem horizontal** (página, 1440/1024/768/390/360): Ofícios, Roteiros, Termos = 0 em
todas. Fora delas: Usuários 310/566 (B1, regressão), Roteiros 390 com "Usado em" aberto 183
(I1, regressão), UI Lab e Notificações 77/257 a 1024/768 (pré-existente).

**Regressões fora das três listas** (main × novo, 26 rotas × 5 larguras, `regressao_listas.py`):
além de B1/B2/M1/M2, nenhuma — Ordens, Planos, Viagens, Justificativas, Prestações,
Cadastros (exceto Usuários), Imprensa, Palestras, Agenda e Notificações sem diferença de
rolagem nem de quebra de título; as alturas que mudaram mudaram para menos ou por M2.

## 5. Acessibilidade
- **axe** (wcag2a/aa, 2.1, 2.2aa + best-practice), novo, 1440 e 390: Ofícios (normal,
  cancelados, menu ⋮ aberto, resumo aberto), Roteiros e Termos (normal, menu aberto), UI Lab
  → **0 violações**, exceto M8. O `main` tinha 5 `target-size` sérios com menu aberto; o novo,
  1 (M8). `tests/e2e/test_acessibilidade.py -k "oficios or roteiros or termos or ui_lab or
  foco or usuarios or viagens"`: **23 passed**.
- **Teclado** (`teclado.py`): Busca → Ordenar → Mais filtros → [título, ⋮] por linha
  (Roteiros: título → "Usado em" → ⋮); Shift+Tab volta; Enter no título abre o resumo com o
  foco em "Fechar o resumo"; Esc fecha e devolve o foco ao título; Enter no ⋮ abre com foco no
  1º item; ↓, End, Home percorrem; Esc fecha e devolve ao ⋮. Foco visível em todos os passos
  (anel da linha inteira + anel próprio).
- **Contraste** dos novos elementos (`contraste.py`): selos info 6,87 · aviso 6,61 · neutro
  5,72 · perigo 6,59 · sucesso 6,92; rótulo da placa 5,84; "+N" 14,12; ícone do motorista 6,75;
  vazio/inativo 5,30; ícones da meta 5,30. Nada abaixo de 4,5:1.
- **Leitor de tela**: título "Ofício N · destinos e mais N destinos"; meta com rótulos
  ("Período:", "Equipe:", "Transporte:", "Diárias:"); motorista "(motorista)" e "(motorista
  de fora da equipe)"; ⋮ "Ações do Ofício N". Detalhe: o selo de tempo não tem prefixo
  ("faltam 41 dias" solto) e há um espaço antes da vírgula após "(motorista)" — cosméticos.

## 6. Benchmark LEGADO × NOVO (lista de ofícios; `benchmark.py`, somente leitura)
O legado tem 12 ofícios; o novo, 255 (os tempos de servidor estão sob carga — load ≈ 8 em 2
CPUs — e servem só para ordem de grandeza).

| Tarefa | Legado | Novo | Vence |
|---|---|---|---|
| Achar por número (completo e curto) | 1 resultado, 1º lugar | 1 resultado, 1º lugar; refino "26 pode ser…" | empate (novo um pouco melhor pelo refino) |
| Achar por destino, sem acento e minúsculo | encontra (4 resultados) | encontra (1 resultado, preciso) | empate |
| Achar por servidor (sobrenome) | encontra, mas a busca não anuncia "servidor" | encontra e o campo diz "…destino ou servidor" | **novo** (descoberta) |
| O que vai acontecer | aba "Que vão acontecer" a 1 clique; selo de tempo em 4/12 linhas, 2 com "há N dias" (ruído) | "faltam N dias / amanhã / começa hoje / em andamento · até" em 15/20 linhas, passado sem selo; mas a aba temporal só chega no Lote 2 | **novo na linha**, legado na aba (até o LP-20) |
| Tipo (Convalidação/Complementar/Retificado) | explícito em 12/12 linhas, inclusive Autorização | só o incomum (4/20), Autorização por ausência; resumo com tipo + porquê | **legado** para "ver de relance"; novo para explicar e para ruído |
| Ler diárias de várias linhas | valor em 4 posições x diferentes (desvio 148 px), no fim de cada meta | 1 só posição x (desvio 0), algarismos tabulares — mas I2 | **novo** (claramente) |
| Linhas por tela 1440×900 | 7,2 (11,6 rolando); 1ª linha em y = 380 | 6,3 (10,7 rolando); 1ª linha em y = 451 (migalhas, descrição, cabeçalho de mês) | **legado** (≈ 1 linha a mais) |
| Linhas por tela 390×844 | ≈ 1,3 cartão de ~280 px e 170 px de rolagem lateral | 3,1 (6,5 rolando), 0 de rolagem lateral | **novo** (claramente) |
| Cliques até cancelar | 3 (⋮ → Cancelar → confirmar no próprio item), sem motivo | 3 (⋮ → Cancelar → confirmar) + motivo obrigatório, com a consequência explicada | legado em velocidade, **novo** em segurança/auditoria |
| Rolagem lateral 1024 | 524 px | 0 | **novo** |

Resumo: o novo vence onde o Lote 1 atuou (leitura vertical, celular, tempo, valor); o legado
ainda vence em densidade no desktop e no tipo explícito. Para o legado não vencer mais nada:
reduzir o topo da página (Lote 2: gaveta, contagens repetidas) e reavaliar se "Autorização"
merece um marcador discreto em vez da ausência.

## 7. Desempenho (`consultas.py`, `consultas_cpu.py`, `peso.py`)
| Rota | Consultas main → novo | CPU por requisição (mediana, 2 rodadas) main → novo | HTML main → novo (gzip) |
|---|---|---|---|
| `/viagens/oficios/` | 16 → 16 | 69–80 → 83–84 ms | 125,6 → 152,2 KiB (11,5 → 13,3) |
| `/viagens/oficios/?pagina=13` | 16 → 16 | 60–68 → 68 ms | 102,5 → 119,8 KiB |
| `/viagens/oficios/?q=curitiba` | 17 → 17 | 75–80 → 87–88 ms | 124,5 → 151,8 KiB |
| `/viagens/roteiros/` | 18 → 18 | 70–75 → 68–76 ms | 109,1 → 126,0 KiB (8,4 → 8,9) |
| `/viagens/termos/` | 22 → 22 | 62–69 → 60–67 ms | 55,2 → 62,4 KiB (7,0 → 7,4) |
| `/viagens/` (painel) | 20 → 20 | 53–59 → 60–66 ms | 46,5 → 59,7 KiB (6,1 → 7,0) |
| resumo (`?resumo=1`) | 22 → 22 | 85–105 → 100–112 ms | 138,0 → 165,0 KiB |

Consultas idênticas (o tipo, o alerta e o motorista de fora não criam N+1). CPU de
renderização +5 a 10% em Ofícios/painel, dentro do ruído nas demais. Tempo de parede não é
comparável nesta máquina (load ≈ 8): as medianas variaram até 2× entre rodadas do mesmo
código. `test_dominio_tempo.py`, `test_dominio_prazos.py`, `TestSelosDasListas`,
`TestLinhaDaLista`: **83 passed**.

## 8. Crítica visual independente (o que ainda não é excepcional nas três listas)
- **Hierarquia**: o título (12,6 px semibold) e os selos (10,8 px) competem menos que antes,
  mas com 3 selos a 1440 a linha do título fica mais pesada que a do meta; o "+1" cinza
  repete a forma do selo neutro.
- **Densidade**: no desktop o novo mostra ~1 linha a menos que o legado por causa do topo
  (não do Lote 1). No celular, Roteiros e Termos gastam uma linha só para "faltam N dias".
- **Consistência Ofícios × Roteiros × Termos**: período no mesmo x nas três (217 px a 1440),
  mesma gramática de cancelado, mesmo selo de tempo — bom. Diferenças que sobram: Roteiros
  não é link quando cancelado (M6); Termos usa "Servidores:" e Ofícios "Equipe:" para o
  leitor de tela; vazio do título só em Ofícios/Termos.
- **Truncamento**: aceitável na Equipe (com "+N"), ruim em números (I2) e em rótulos de
  vazio (M3), inaceitável no painel (B2).
- **Selos**: "Justificativa pendente" com anel vazio âmbar ao lado de "○ Rascunho" (anel
  vazio cinza) — duas formas iguais em cores diferentes, legível; tipo cinza ao lado de
  rascunho cinza não (M5).

## 9. O que reavaliar após a correção
B1 e B2 com `titulos.py` + `quebra_titulo.py` + `truncamento.py` (main × novo, 1440/1280/
1024/768/390/360) em Usuários, Publicações, Eventos, Coffee e painel; I1 com `pousar.py`;
I2 em Ofícios/Roteiros a 1280 e 1440; e de novo `axe_estados.py` e `regressao_listas.py`
completos. O `main` sobe com `/home/claude/tools/main_server.sh` (worktree
`/home/claude/main-wt`, porta 8002).
