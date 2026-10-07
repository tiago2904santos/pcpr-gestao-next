# Lista de ofícios — Lote 1 (LP-01 a LP-12): componentes compartilhados

> Agente 2 — UI/UX Design Lead · 2026-10-06 · implementação do Lote 1 do plano aprovado
> (`oficios-lista-plano.md`). Afeta Ofícios, Roteiros, Termos (e o painel de Viagens, que usa
> a linha do ofício). Evidências fora do repositório (PREVIEW, dados fictícios):
> `/home/claude/caps/antes-lote1/<larg>/` e `/home/claude/caps/depois-lote1/<larg>/`
> (1440, 1024, 768, 390), estados em `/home/claude/caps/novo/estados/l1-*.png`,
> `lp11-*.png`, `lab21-*.png`. Medições: `/home/claude/tools/medir_lista.py`,
> `consultas_lista.py`, `estados_lote1.py`, `abas_lp11.py`, `lab21.py`.

## 1. O que mudou, por LP

| LP | O quê | Arquivos | Commit |
|---|---|---|---|
| LP-01 | Seletor órfão `.registro--inativo .registro__link` (estava emendado a `.registro__notas`): o título inativo agora recua para o terciário e não vira grid com margem | `static/css/listas.css` | `6757560` |
| LP-02 | Tokens de camada `--z-linha-acoes` (1) e `--z-grupo-lista` (2): o cabeçalho de mês preso fica acima do ⋮ das linhas | `tokens.css`, `listas.css` | `4c9b53d` |
| LP-03 | ⋮ sem `opacity: .6`; o hover da linha só dá fundo ao botão | `listas.css` | `4c9b53d` |
| LP-04 | `.selo--neutro` declarado (era usado por 19 telas e pelos tons "neutro" do domínio, sem existir) | `components.css` | `783b874` |
| LP-05 | Rótulo da placa em `var(--texto-2xs)` (token já existia: 11px nominal → 9,9px efetivos); `placa--cancelada` risca só o número | `components.css` | `48a7967` |
| LP-06 | Domínio puro `dominio/tempo.py` (`selo_tempo`) + tag `{% selo_tempo inicio fim %}`; aplicado em Ofícios, Roteiros (substitui "faltam/em andamento" próprios) e Termos (substitui "Previsto/Em andamento/Realizado/Sem período"); janela de resumo usa o mesmo selo (sai "Fora do prazo") | `dominio/tempo.py`, `templatetags/viagens.py`, `oficios/_registro.html`, `oficios/_resumo.html`, `roteiros/_registro.html`, `termos/lista.html`, testes `test_dominio_tempo.py`, `test_views.py::TestSelosDasListas` | `1dd35dd` |
| LP-07 | `dominio/selos.py` (`alerta_da_linha`: Justificativa pendente > prazo ≤ 10d > tempo; "Justificativa preenchida" sai da linha); `dominio/assunto.py::tipo_do_oficio` (Autorização × Convalidação + Retificado/Complementar, com o porquê); selo de tipo só quando incomum (`selo_tipo`), calculado da 1ª saída já anotada/pré-carregada — **nenhuma consulta a mais**; resumo mostra o tipo completo (inclusive Autorização) com o porquê e o prazo por escrito | mesmos + `test_dominio_prazos.py` | `1dd35dd` |
| LP-08 | Título = destinos (≤ 3 + "+N"; lista inteira no `title` e "e mais N destinos" para leitor de tela) em Ofícios e Termos; período é o 1º item do meta; Roteiros mantém "Sede → destinos" (uma linha, com reticências e `title`) | `oficios/_registro.html`, `termos/lista.html`, `roteiros/_registro.html`, filtros `lista_destinos`/`resumir` | `0131d99` |
| LP-09 | Variante `.registro__meta--colunas` (+ `--oficio`, `--termo`, `--roteiro`): ≥ 1024 uma faixa de colunas fixas — Ofícios: Período 9,5rem · Protocolo 7,25rem · Equipe 1,4fr · Transporte 1fr · Diárias 11rem (7,5rem e só o valor de 1024 a 1279); Termos: Período · Ofício · Equipe · Viatura; Roteiros: Período · Trechos · Uso · Diárias · Observações. Cada item numa linha, reticências + `title`, item ausente no lugar (inclusive "Sem protocolo", "Avulso", "Sem viatura"). 768–1023: duas faixas. Diárias com `tabular-nums` e valor em destaque. Motorista com ícone `circle-dot` (o sprite Lucide não tem volante) + "(motorista)" só para leitor de tela; **motorista de fora da equipe aparece** (servidor de outro ofício ou pessoa não cadastrada; `select_related` novo, sem N+1); ícone do transporte pelo modal (avião/ônibus/carro) | `listas.css`, `queries.py`, templates acima | `0131d99` |
| LP-10 | Celular (linhas com meta em colunas): placa, título e ⋮ na **mesma linha**; selos agrupados em `.registro__selos` descem juntos para a 2ª linha; meta em duas faixas de `--texto-sm` (Período · Diárias / Equipe · Transporte; o protocolo fica no resumo e na busca). Listas que não aderiram (Ordens, Planos, Viagens, Coffee…) mantêm o layout anterior | `listas.css`, templates acima | `0131d99` |
| LP-11 | Abas: foco com o anel do DS por dentro (novo token `--anel-foco-interno`, pois a fileira rola e cortaria o anel de fora) e cantos `--raio-md`; `summary` "Mais filtros" com `--anel-foco`; `abas-rolagem.js` (sob demanda em `.abas`) marca `data-rola="inicio|fim"` → máscara esmaece a borda que esconde abas, e centraliza a aba ativa fora da vista (também após a troca por HTMX) | `tokens.css`, `components.css`, `listas.css`, `static/js/componentes/abas-rolagem.js`, `app.js` | `642f1e2` |
| LP-12 | UI Lab seção 21 "Linha das listas de Viagens": todos os casos do selo de tempo (datas relativas a hoje), tipos do ofício, alerta de justificativa, linhas normal/alerta/em andamento/sem dados/cancelada/inativa com grupo de mês e colunas, abas que rolam; índice ganha 20 e 21 | `ui_lab/views.py`, `ui_lab/indice.html`, `ui-lab.css` | `f62c02f` |
| — | Autocrítica: cancelado recua nas três listas; resumo sem repetir o prazo; respiro do ícone do motorista | `oficios/_registro.html`, `roteiros/_registro.html`, `_resumo.html`, `listas.css` | `32fd6b9` |

Vocabulário do selo de tempo (D3), regra em `dominio/tempo.py`:
"faltam N dias" (info; **aviso** quando N ≤ prazo da unidade, padrão 10) · "amanhã" · "hoje"
(viagem de um dia) · "começa hoje" (vários dias) — os três em aviso · "em andamento · até dd/mm"
· "volta hoje" (os dois com o ponto que pulsa) · passado e sem data → sem selo.

## 2. Medições antes × depois (PREVIEW, 258 ofícios fictícios)

**Altura das linhas (20 primeiras; px: quantidade)**

| Lista | Largura | Antes | Depois |
|---|---|---|---|
| Ofícios | 1440 | 71–93 (72:17, 93:2) | **71–72** (72:19) |
| Ofícios | 1024 | 72–117 (93:15, 117:1) | **71–72** (72:19) |
| Ofícios | 768 | 72–134 (114:12, 134:1) | **92–93** (93:19) |
| Ofícios | 390 | 121–198 (média ≈ 180) | **109–133** (109/110: 18, 133: 2 — três selos) |
| Roteiros | 1440 / 1024 / 768 / 390 | 71–95 / 92–95 / 92–155 / 154–216 | 71–72 / 71–72* / 92–95 / 108–111 |
| Termos | 1440 / 1024 / 768 / 390 | 71–77 / 72–92 / 72–114 / 103–178 | 70–72 / 70–72 / 91–93 / 85–109 |

\* Roteiros a 1024 medido 71–74 antes do ajuste do botão "Usado em N ofícios" (padding do
`<button>` somava 2px); depois do ajuste, 71–72.

**Ofícios por tela a 390×844** (área útil entre o topo e a barra fixa): primeira tela
**1,48 → 2,55**; rolando (lista sob o cabeçalho de mês) **3,74 → 6,17** (≥ 3 exigido).
Roteiros 2,46 → 3,77 / 4,2 → 6,64; Termos 2,75 → 3,85 / 4,89 → 7,0.

**Contraste do ⋮**: antes opacidade .6 sobre branco ≈ 2,6:1 (abaixo de 3:1, WCAG 1.4.11);
depois `--neutro-600` cheio = **6,75:1** sobre a superfície e 5,72:1 sobre o fundo do hover
(`scripts/contraste.py`). Título inativo (`--neutro-500`) 5,30:1. Rótulo da placa
(`--dourado-700`, 9,9px efetivos, antes 8,1px) 5,84:1.

**Consultas SQL** (`CaptureQueriesContext`, gestor, PREVIEW): `/viagens/oficios/` **19 → 19**,
página 2 **16 → 16**, `/viagens/roteiros/` **18 → 18**, `/viagens/termos/` **22 → 22**;
painel `/viagens/` 20 depois. Tipo, alerta e selo de tempo saem dos trechos já pré-carregados;
o motorista de fora vem no mesmo `select_related`. `test_lista_tem_orcamento_de_consultas`
(≤ 16 no cenário de teste) continua verde.

**Rolagem horizontal**: 0 em 1440/1024/768/390/360 nas três listas e no UI Lab (uma regressão
de 95px a 390 — o texto só para leitor de tela "(motorista)" posicionado fora do corte — foi
achada na medição e corrigida com `position: relative` no span que corta).

## 3. Autocrítica 1 — "se fosse para produção hoje, o que me incomodaria?"
1. **Resumo repetia o prazo três vezes** (alerta de pendências, linha "Prazo" e o porquê do
   tipo). → A linha "Prazo" só aparece quando o alerta não diz a mesma coisa. Corrigido.
2. **Cancelado com pesos diferentes**: Termos recuava (inativo), Ofícios e Roteiros não. →
   As três listas: placa riscada + selo × + título recuado. Corrigido.
3. **1024 apertava a Equipe** (~170px) porque a coluna das diárias levava o detalhe. → De
   1024 a 1279 (e abaixo) as diárias mostram só o valor, coluna de 7,5rem; detalhe no `title`
   e no resumo. Corrigido.
4. **Termos cortava "Ofício 135/2…"** na coluna de 7,25rem. → 8,75rem. Corrigido.
5. **No celular os selos empilhavam um por linha** na coluna estreita ao lado da placa. →
   Grupo `.registro__selos` desce inteiro para a linha de baixo, na largura toda. Corrigido.
6. **Planos a 390 ficava espremido** com a placa larga ("PLANO · ASCOM 04/2026") quando o
   layout novo valia para toda linha com placa. → O layout novo só vale para linhas que
   aderiram (meta em colunas). Corrigido; Ordens/Planos/Viagens/Coffee iguais a antes.
7. **Linha de Roteiros 2px mais alta** com "Usado em N ofícios" (padding do botão). Corrigido.

## 4. Autocrítica 2 — olhar novo
- **Alinhamento**: as colunas começam no mesmo x em todas as linhas (placa com largura mínima
  fixa, ⋮ sempre presente nas três listas). Ícone do motorista colado ao nome → respiro
  `--esp-1`. Corrigido.
- **Densidade/hierarquia**: no máximo situação + tipo incomum + 1 alerta; com três selos a
  1440 o título ainda cabe (reticências no texto, nunca nos selos). Valor das diárias em
  texto principal e algarismos tabulares — a coluna se lê de cima para baixo.
- **Consistência Ofícios × Roteiros × Termos**: período sempre na 1ª coluna; mesma gramática
  de cancelado; mesmo selo de tempo; mesmo "+N". Roteiros mantém "Sede → destinos" (D5).
- **Teclado/foco**: Tab percorre link → ⋮ por linha (Roteiros: link → "Usado em" → ⋮); anel da
  linha inteira inalterado; abas com anel interno arredondado; `summary` com o anel do DS;
  aba ativa fora da vista é centralizada ao carregar (verificado com "Arquivados" a 390).
- **Contraste**: ver §2; nenhum par novo abaixo de 4,5:1 (texto) ou 3:1 (ícone).
- **360–1440**: sem rolagem horizontal; 360 com "Cancelados" ativa mostra a aba centrada.
- **axe**: `tests/e2e/test_acessibilidade.py` (inclui `/viagens/oficios/`, rascunhos, sem
  resultado, arquivados, resumo aberto, `/viagens/roteiros/`, termos) e `test_ui_lab.py` —
  ver §6.

## 5. Pendências e decisões para o QA / próximos lotes
- **Ícone de motorista**: o sprite Lucide 1.49 não tem volante; usei `circle-dot` (círculo
  com cubo) + texto acessível + "(motorista)" no `title`. Se o dono preferir, um símbolo
  próprio entra no `vendor_assets.py`.
- **Protocolo no celular** sai da linha (fica no resumo e na busca) para caber em duas faixas.
- **Ícone por modal** depende de `transporte_meio`; os dados DEMO não preenchem o meio, então
  "Aeronave comercial" ainda aparece com ônibus (P13 fica para quando o cadastro trouxer o meio).
- `registro__acoes--fixas` ficou sem regra (todas as ações agora têm contraste cheio); a
  classe continua em 10 templates de outros módulos, inofensiva — remover numa limpeza.
- Lote 2: gaveta que abre sozinha com filtro ativo (vista a 360), abas/contagens (LP-20),
  "255" repetido (LP-26), "no filtro de agora". Lote 3: menu ⋮.
- Listas de Ordens, Planos e Viagens ainda têm selo de tempo próprio (D3 diz "depois").

## 6. Verificação
- Domínio: `test_dominio_tempo.py` (fronteiras: 30/11/10/2 dias, amanhã, hoje, começa hoje,
  em andamento, volta hoje, passado, sem data, sem volta, volta < saída, prazo da unidade;
  orçamento de selos) e `test_dominio_prazos.py::test_tipo_do_oficio`/`test_tipo_explica_o_porque`.
- Telas: `test_views.py::TestSelosDasListas` (8) e `TestLinhaDaLista` (3): alerta único,
  "em andamento · até" e nunca "há N dias", passado sem selo, tipo só incomum (Convalidação ·
  Complementar, Retificado) com o porquê, resumo com o mesmo vocabulário e o tipo, Roteiros e
  Termos com o mesmo selo, título "+N" com `title` completo, período no meta, motorista
  marcado e motorista de fora.
- `test_views.py`, `test_termos.py`, `test_roteiros.py`, `test_viagem.py`: 220 verdes.
- Navegador e `scripts/verificar.sh`: resultado registrado no Log de `current-page.md`.
