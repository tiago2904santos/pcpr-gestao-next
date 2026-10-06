# Diagnóstico visual — Lista de ofícios (`/viagens/oficios/`)

> Agente 2 — UI/UX Design Lead · 2026-10-06 · etapa de diagnóstico (nenhum código alterado).
> Comparada com o padrão aprovado (`identidade-referencia.md`: Roteiros e Termos) e com a lista
> do LEGADO. Larguras: 1440, 1024, 768, 390. PREVIEW com 258 ofícios fictícios (255 em "Todos").
> Evidências (fora do repositório): `/home/claude/caps/novo/{1440,1024,768,390}/viagens-oficios.png`,
> `/home/claude/caps/novo/estados/*.png` (menu ⋮, Mais filtros, foco, hover, resumo, refino,
> filtro ativo, sem resultados, cancelados, rolagem com mês preso), capturas do legado em
> `/home/claude/caps/legado/` (dados reais — não versionar). Scripts:
> `/home/claude/tools/estados_oficios.py`, `sonda.py`, `foco_linha.py`.
>
> Pergunta de controle aplicada a cada item: **isto está realmente excepcional?** A resposta
> hoje é "não": a lista é limpa e coerente com a identidade, mas é a mais ruidosa e a menos
> escaneável das três, e diverge do padrão aprovado em comportamento e vocabulário.

## 1. Arquivos envolvidos
`gestao/viagens/templates/viagens/oficios/lista.html`, `_abas.html`, `_registro.html`,
`_acoes_ciclo.html`, `_refino.html`, `_dialogo_resumo.html`, `_resumo.html`, `_botao_novo.html`;
view `gestao/viagens/views.py::lista` (l. 186–216) e `ORDENS_DA_LISTA` (l. 120);
tags `gestao/viagens/templatetags/viagens.py` (`contagem_dias` l. 60, `selo_justificativa` l. 143,
`tom_situacao`); CSS `static/css/listas.css`, `components.css` (selo, placa, abas, menu),
`layout.css` (cabeçalho, barra); JS `registro.js`, `menu.js`, `seletor*.js`.

## 2. Medições
| Medida | 1440 | 1024 | 768 | 390 |
|---|---|---|---|---|
| Rolagem horizontal da página | 0 | 0 | 0 | 0 |
| Altura das linhas (20 primeiras) | 72 / **93** (2 de 20) | **93** (15 de 20), 72, 117 | 93–**134** | 121–**198** (média ≈180) |
| Linhas visíveis na 1ª tela (abaixo dos filtros, acima da barra) | ≈5 | ≈4 | — | **≈1,5** |
| Abas: largura necessária × disponível | 894 × 1208 | 894 × 966 | **894 × 725** (169px escondidos) | 894 × 361 |
| Corpo / título da linha / meta / selo / rótulo da placa (px efetivos) | 12,6 / 12,6 / 11,7 / 10,8 / **8,1** | = | = | 12,6 / 12,6 / **10,8** / 10,8 / 8,1 |
| Botão ⋮ | 36×36, opacidade .6 (≈2,6:1) | = | = | 36×36, opacidade 1 |
| Contagem "255" repetida na tela | 4× (aba, h2, paginação, barra) | | | |

Comparativo de altura com o padrão: Roteiros 72/95px e Termos 71–77px a 1440 — Ofícios tem o
mesmo ritmo a 1440, mas **perde o ritmo a partir de 1024** (93px vira o normal e há 117px).

## 3. O que já está bom (manter)
- Mesmo esqueleto do padrão: cabeçalho com filete, abas com contador, cartão com busca ao vivo,
  placa, selos com forma, meta com ícones e item ausente no lugar, ⋮, barra fixa, vazio distinto
  para "sem resultados" (com "Limpar filtros"), "nenhum arquivado" e "primeiro uso".
- Refino da busca ("26" pode ser Ofício 26/2026 · Protocolo com 26) — melhor que o legado e que
  Roteiros/Termos; é candidato a virar padrão.
- Exportar leva o recorte exato da tela; "N ofícios no filtro de agora" na barra.
- Teclado: ordem de tabulação lógica (pular conteúdo → topo → menu → migalhas → abas → busca →
  ordenar → mais filtros → [título, ⋮] por linha); ⋮ abre com Enter, setas percorrem, Esc devolve
  o foco. Foco da linha desenhado na linha inteira.
- Sem rolagem horizontal em nenhuma largura (o legado tem 108px a 1440 e 780px a 768).
- Cancelado: placa tachada + selo "× Cancelado" (gramática de Roteiros).

## 4. Problemas, severidade e proposta

Severidade: **alta** = atrapalha a tarefa principal (achar e agir num ofício) ou viola WCAG;
**média** = inconsistência com o padrão aprovado ou atrito frequente; **baixa** = acabamento.
"Escopo" diz se a solução é da página ou de um componente compartilhado (e quem mais o usa).

### P1 — Filtros avançados: a gaveta abre sozinha sobre a lista e os filtros ativos não aparecem fora dela · **ALTA**
Evidência: `estados/filtro-ativo-1440.png`. Com `?diarias_de=1000`, a página carrega com
`details.filtros__mais[open]` — o painel flutuante (`.filtros__avancados`, absoluto, `z-index
--z-painel-campo`) cobre o cabeçalho da lista e a 1ª linha. Fechado, a única pista é o número "1"
no botão; o que está filtrado não é dito. A gaveta também não tem "Fechar"/"Aplicar"; fecha só no
próprio botão. No painel, "Diárias (R$)" é um `span` acima dos campos (fora do padrão rótulo-na-
borda; a linha fica com dois alinhamentos) e o placeholder do Protocolo ("00.366.136-8") parece um
valor preenchido.
Proposta (componente compartilhado `.filtros__mais` + `.ficha`):
1. Gaveta **sempre fechada** ao carregar; abaixo da barra de filtros, uma linha
   `.filtros-ativos` com uma `.ficha` removível por filtro ("Diárias ≥ R$ 1.000 ×",
   "Saída 01/10–31/10 ×") e "Limpar tudo" — padrão já catalogado no UI Lab e usado pelo legado.
2. Rodapé no painel: "Limpar" (texto) + "Fechar" (Esc e clique fora fecham; foco volta ao botão).
3. "Diárias" como `fieldset` com `legend` na borda (mesma gramática dos campos); placeholders
   como exemplo explícito ("ex.: 00.000.000-0").
Escopo: **compartilhado** — `filtros__mais` também em Coffee, Eventos/Solicitações, Imprensa,
Palestras e Publicações (`*/lista.html`). Entra antes no UI Lab (não está lá).

### P2 — Selos: até três pílulas por linha, três vocabulários de tempo e "há 1 dia" em viagem em andamento · **ALTA**
Evidência: 1440/1024/768. A linha do título junta situação ("○ Rascunho") + justificativa
("● Justificativa pendente", âmbar) + tempo ("🕓 faltam 5 dias", âmbar) — dois âmbares colados
competem; a 768 a terceira pílula quebra para uma linha só dela. O selo de tempo:
- diz **"há 1 dia"/"há 2 dias"** para viagens **em andamento** (05/10–15/10 e 04/10–06/10 com hoje
  = 06/10) — Roteiros mostra "em andamento" (pulso) e Termos "Em andamento" para o mesmo caso;
- diz **"há 671 dias"** em ofícios emitidos de 2024 — ruído sem ação possível;
- Termos usa "Previsto/Em andamento/Realizado"; Roteiros "faltam N dias/em andamento"; Ofícios
  "faltam N dias/há N dias" → três vocabulários para o mesmo fato.
A janela de resumo chama o mesmo caso de "Fora do prazo" enquanto a linha diz "faltam 5 dias".
Proposta (componente compartilhado — tag `{% selo_tempo inicio fim %}` em
`templatetags/viagens.py` + regras no UI Lab):
1. Um vocabulário só, para Ofícios, Roteiros, Termos, Ordens, Planos e Viagens: **"faltam N
   dias"** (info; âmbar se ≤ prazo), **"hoje/amanhã"** (âmbar), **"em andamento"** (info +
   `selo--processo`), **realizada** → sem selo (o passado não pede ação; a data já está na linha).
2. Orçamento de selos no título: **no máximo dois** — situação + o alerta mais grave. Prioridade:
   "Justificativa pendente" > prazo ≤10d > tempo. "Justificativa preenchida" sai da linha (é o
   estado normal; aparece no resumo).
3. Mesmo termo na linha e na janela de resumo ("Justificativa pendente" nos dois).

### P3 — Metadados quebram de forma irregular; não há colunas para escanear · **ALTA**
Evidência: alturas 72/93/117 na mesma página; a 1440, ofício com equipe longa empurra só as
diárias para uma 2ª linha; a 1024, 15 de 20 linhas têm duas linhas de meta; "Sem diárias
calculadas" fica sozinho embaixo. O olho não encontra "o valor" ou "a viatura" na mesma coluna de
uma linha para a outra — numa lista de 255 itens, a leitura vertical é a tarefa principal.
Ainda: o título junta destinos **e** período (Roteiros põe o período no meta), e a equipe repete
"(motorista)" por extenso.
Proposta (componente compartilhado `.registro__meta`):
1. Variante `registro__meta--colunas` (≥1024): grade com faixas fixas e **uma linha por item**
   com reticências + `title`/dica: Protocolo (≈9rem) · Equipe (1fr) · Transporte (≈14rem) ·
   Diárias (≈11rem, `tabular-nums`, alinhado à direita). Linha fixa em **72px**.
2. 768–1023: duas faixas (Equipe | Transporte) e (Protocolo | Diárias).
3. <768: pilha com ícones, texto-sm (não xs).
4. Regra de título para as três listas: **título = destinos**; período é o 1º item do meta
   (ícone calendário), como em Roteiros — ou o inverso nas três; o que não pode é cada lista ter
   uma composição.
5. Motorista marcado por ícone/realce (volante) em vez de "(motorista)".
Escopo: **compartilhado** — Roteiros e Termos ganham o mesmo alinhamento (Roteiros já tem linhas
de 95px pelo mesmo motivo).

### P4 — ⋮ com opacidade .6: contraste do ícone ≈2,6:1 · **ALTA (WCAG 1.4.11)**
`listas.css` l. 669 `.registro__acoes { opacity: .6 }`. O ícone `--cor-texto-secundario`
esmaecido sobre branco fica abaixo de 3:1 até o ponteiro ou o foco chegar à linha — e é o único
caminho para Cancelar/Arquivar/Excluir/Retificar. No legado o ⋮ é um botão contornado sempre
visível. Proposta: opacidade 1 sempre; hover da linha só dá fundo ao botão. Escopo:
**compartilhado** — todas as listas com `.registro__acoes` (40 templates).

### P5 — Cabeçalho de mês preso fica por baixo dos ⋮ das linhas · **MÉDIA**
Evidência: `estados/lista-1440-rolada.png` e `lista-390-rolada.png` — ao rolar, o ⋮ da linha que
passa sob o cabeçalho "OUTUBRO DE 2026" aparece **sobre** ele. Causa: `.registros__grupo` e
`.registro__acoes` ambos `z-index: 1`; a linha vem depois no DOM. Proposta: grupo com
`z-index: 2` (ou token `--z-grupo`), abaixo de `--z-painel-campo`. Escopo: Ofícios e Planos.
Junto: o cabeçalho de mês não diz quantos ofícios tem ("Outubro de 2026 · 23") e, na ordem
padrão (por número, agrupando por data do ofício), aparece **um só grupo por página** (20 linhas)
— hoje é decoração. Manter a decisão registrada (grupo também na ordem por número), mas com a
contagem.

### P6 — Abas: vocabulário diferente do padrão, dimensões misturadas e transbordo sem aviso · **MÉDIA**
Ofícios: Todos · Rascunhos · Emitidos · Próximas viagens · Contas prestadas · Cancelados ·
Arquivados (7). Roteiros/Termos **e o legado de Ofícios**: Todos · Que vão acontecer · Em
andamento e realizados · (Finalizados | Contas prestadas) · Cancelados. A fileira mistura ciclo do
documento (rascunho/emitido/cancelado), tempo da viagem (próximas) e arquivo — "Próximas viagens"
se sobrepõe a Rascunhos/Emitidos. As 7 abas precisam de 894px: a 768 escondem 169px (Cancelados
cortado, Arquivados invisível) sem nenhum indício de rolagem. As contagens não acompanham a busca
nem os filtros ("Todos 255" ao lado de "157 ofícios no filtro de agora").
Proposta: (a) Agente 1 confirma as abas de paridade; sugestão: abas = **ciclo do documento**
(Todos · Rascunhos · Emitidos · Cancelados · Arquivados) e o **tempo da viagem** como controle
próprio e igual nas três listas (`.segmentado` "Qualquer · Que vão acontecer · Em andamento ·
Realizadas"), o que alinha com Roteiros/Termos sem perder a função; (b) componente `.abas`
compartilhado: máscara de esmaecimento na borda que rola + `scrollIntoView` da aba ativa; abaixo
de 480px virar um `pc-select` "Situação: Todos (255)"; (c) contagens do recorte atual (ou o rótulo
deixa claro que é o total). Escopo do (b): todas as listas com abas.

### P7 — Clicar no título abre uma janela; em Roteiros/Termos abre a folha. Menu ⋮ pobre · **MÉDIA**
Ofícios: título → `dialogo-resumo` (janela rica e boa), "Abrir o ofício" é o 1º item do ⋮.
Roteiros e Termos: título → folha de edição. O mesmo gesto faz coisas diferentes em três telas
vizinhas. O ⋮ da linha tem só Abrir/Retificar/Ver minuta + Cancelar/Arquivar/Excluir; o legado
oferece Baixar documentos, Anexar assinado, Importar processo, Retificar, Complementar. A página já
inclui `dialogo_baixar` e `dialogo_assinado`, mas o menu da linha não os abre (estão só no "Mais
ações" da janela).
Proposta: regra única para as listas de documento — **título abre o resumo** (Ofícios) e o resumo
passa a existir para Termos/Roteiros, **ou** título abre a folha em todas e o resumo vira o 1º
item do ⋮ ("Ver resumo", também por Espaço na linha focada). Recomendo a 1ª (o resumo é a
melhor peça da lista e evita sair dela). Menu ⋮ canônico: Abrir · Ver minuta · Baixar documentos
· Anexar assinado — separador — Novo termo/OS/plano — separador — Retificar · Cancelar · Arquivar —
separador — Excluir; itens não triviais com linha de descrição (`.menu__item--descrito`, a criar).

### P8 — "Ordenar por" só em Ofícios, com rótulo enganoso · **MÉDIA**
"Data de saída (próximas)" (`ordem=saida`) começa em **maio de 2024** — é "mais antigas
primeiro", não "próximas". A ordem e o agrupamento mudam juntos sem aviso (grupo por saída × por
data do ofício). Roteiros e Termos não têm ordenação; o legado de Ofícios tinha "Filtros e ordem"
numa gaveta. Proposta: rótulos honestos ("Saída: mais antiga primeiro / mais recente primeiro") ou
"próximas" de verdade (a partir de hoje, crescente — Agente 1 decide); a ordenação entra na gaveta
de filtros como no legado **ou** vira padrão das três listas — não só desta. No celular a
"Ordenar por" ocupa uma linha inteira acima da lista (ver P10).

### P9 — Tipografia efetiva miúda para uma lista de trabalho diário · **MÉDIA**
Com a raiz a 90%: rótulo da placa **8,1px** (literal `0.5625rem`, fora dos tokens), selos 10,8px,
meta 11,7px (10,8px no celular), contador das abas 10,8px. O contraste passa (5,3–6,9:1), a
legibilidade não: 8px está abaixo de qualquer mínimo razoável e o rótulo "OFÍCIO" é repetido 20×
por página sem informar nada novo. Proposta (compartilhado): rótulo da placa em `--texto-2xs`
(9,9px efetivos) ou removido na lista (a coluna já é de ofícios; fica na `placa--grande`); meta no
celular em `--texto-sm`; avaliar com o dono do produto subir a raiz para 93,75% (15px) só no
`<main>` de listas.

### P10 — Celular (390): ~1,5 ofício por tela; placa e ⋮ gastam uma linha; filtros em três linhas · **MÉDIA**
Evidência: `estados/lista-390-viewport.png`, `lista-390-rolada.png`. Antes da 1ª linha:
cabeçalho (≈110px) + abas cortadas + **busca, Ordenar por e Mais filtros empilhados (≈170px)**.
Cada linha ≈180px: placa+⋮ (36px) numa linha própria, título, selos em até duas linhas, meta em 3.
O doc de explorações prometia "~2,5 ofícios por tela".
Proposta (compartilhado `.registro` no celular): placa como selo **dentro** da linha do título
(primeiro item do flex) e ⋮ ancorado no canto superior direito ocupando a altura do título;
máximo de 2 selos (P2) numa linha; meta em duas linhas (Equipe · Transporte+Diárias) com
reticências. Filtros: busca + um botão "Filtros (n)" que abre gaveta (`.gaveta`, já existe) com
Ordenar e os avançados; abas como `pc-select` (P6b). Meta: ≥3 ofícios por tela a 390×844.
Escopo: todas as listas `.registro` (Roteiros e Termos têm o mesmo desperdício da linha da placa).

### P11 — Contagem repetida quatro vezes e h2 que repete o h1 · **BAIXA**
"Todos 255" (aba) · "Ofícios 255 ofícios" (h2) · "Mostrando 1–20 de 255" · "255 ofícios" (barra).
Proposta (compartilhado, arquétipo LIST): h2 `sr-only` quando não há busca (com busca vira
"Resultados para “x” · N"); a barra mostra só o recorte quando filtrado ("157 de 255 ofícios") e,
sem filtro, nada ou "Página 1 de 13". Trocar "no filtro de agora" por "de 255".

### P12 — Foco das abas e da gaveta fora do anel do DS · **BAIXA**
Aba focada = retângulo de cantos vivos (`.aba:focus-visible { outline-offset: negativo }`);
`summary` de "Mais filtros" usa `outline` simples. O DS define anel grafite + halo claro
(`--anel-foco`). Proposta: `box-shadow: var(--anel-foco)` com `--raio-md` nas duas. Escopo: abas
de todo o sistema.

### P13 — Detalhes de acabamento · **BAIXA**
- `placa--cancelada` tacha também o rótulo "OFÍCIO" (só o número deveria ser riscado).
- "Veículo da instituição organizadora" usa ícone de ônibus; "Aeronave comercial" também — ícone
  por modal (`bus`, `plane`, `car`).
- Linha recém-hover a 768/1024 troca o título para dourado-700 **e** acende o trilho — com o
  resumo abrindo em janela, o hover poderia indicar a placa (continuidade) em vez de colorir o
  texto longo.
- Descrição do cabeçalho de Termos quebra em duas linhas e desloca as abas 18px em relação a
  Ofícios/Roteiros ao alternar entre as telas — limitar descrições a uma linha a 1440.

### P14 — Documentação e UI Lab desatualizados · **BAIXA (processo)**
`docs/design-system/components.md` descreve expansão em linha (`data-expandir`) que não existe;
`page-archetypes.md` manda a ação primária no cabeçalho (as listas de Viagens a puseram na barra);
o UI Lab não tem gaveta de filtros, grupo por mês, barra de lista, refino. Atualizar antes de
implementar P1–P10 (regra do CLAUDE.md: componente nasce no UI Lab).

## 5. Comparação com o LEGADO (sem dados reais)
| Aspecto | Legado | Novo | Veredito |
|---|---|---|---|
| Rolagem horizontal | 108px (1440), 524 (1024), 780 (768) | 0 em todas | novo melhor |
| Abas | chips com ícone e contador, 5 situações (mesmas de Roteiros/Termos) | 7 abas sublinhadas, vocabulário próprio | legado mais consistente (P6) |
| Busca | uma caixa | caixa + refino por leitura | novo melhor |
| Filtros/ordem | gaveta "Filtros e ordem" + **fichas de filtros ativos** | ordem sempre visível + gaveta flutuante sem fichas | legado melhor em clareza (P1, P8) |
| Linha | ícone de documento, título com nº+destino+período, selos (situação, tipo Autorização/Convalidação·Complementar, justificativa), fatos com ícone | placa, título destino+período, selos (situação, justificativa, tempo), meta | novo mais elegante; falta o **tipo** (convalidação/complementar/retificado) — paridade para o Agente 1 |
| ⋮ | botão contornado, sempre visível; itens com descrição; baixar, anexar, importar, retificar, complementar | botão sutil esmaecido; menu curto | legado melhor (P4, P7) |
| Ação principal | botão flutuante sobre as linhas (cobria ⋮) | barra fixa com Exportar + Novo | novo melhor |
| Cabeçalho | Exportar, Numeração, Importar processo do eProtocolo | — (Exportar na barra) | Numeração e Importar: paridade a confirmar |
| Celular | cartões altos (~270px), cabeçalho com 3 botões rolando | ≈180px por linha | novo melhor, ainda longe do excelente (P10) |

## 6. Ordem sugerida de execução
1. Correções compartilhadas baratas: P4, P5, seletor `registro--inativo` (ver `componentes.md`),
   `selo--neutro`. 2. UI Lab: P14 + protótipos de P1, P2, P3, P10. 3. Tag `selo_tempo` + orçamento
   de selos (P2) nas três listas. 4. Meta em colunas (P3). 5. Filtros ativos/gaveta (P1) e abas
   (P6) com o Agente 1 fechando o vocabulário. 6. Título/menu (P7), ordenação (P8). 7. Tipografia
   (P9) com decisão do dono do produto. 8. Acabamento (P11–P13).
