# Aprovação final — página "Lista de ofícios" (`/viagens/oficios/`)

> Agente 3 — QA/Benchmark · 2026-10-07 · branch `viagens/reconstrucao` @ `9f08506`.
> Base: QAs dos Lotes 1–3 (`qa/oficios-lista-lote1.md`, `-lote2.md`, `-lote3.md`, com os re-QAs)
> e as medições finais deste documento (`/home/claude/tools/qa/final_checks.py`; capturas lado a
> lado em `/home/claude/caps/qa-final/`). Legenda: ✅ paridade (ou melhor) · ➕ superação ·
> ⛔ fora por decisão do dono do produto · ⏳ depende da importação do eProtocolo (D10) ·
> ⚠️ pendência consciente (listada no fim).

## Veredito: **PÁGINA CONCLUÍDA — APROVADA**, com as pendências conscientes do §5

Dos 80 itens da matriz, 75 estão em ✅/➕, 1 em ⛔ (Numeração), 2 em ⏳ (importar processo) e
2 em ⚠️ (L9 a confirmar com o dono, L49 acabamento — nenhuma perda de função em relação ao legado). Os 16 defeitos
(F1–F16) estão fechados ou não se reproduzem no novo. Não há regressão conhecida: cada lote foi
medido contra o anterior (26 rotas × 5–6 larguras, 0 diferenças a não ser melhoras).

## 1. Definição de concluído (`mission.md`)
| Critério | Situação | Evidência |
|---|---|---|
| Paridade funcional com o legado | ✅ menos L6 (⛔) e L7/L54 (⏳) | §2 |
| Melhorias planejadas aplicadas | ✅ LP-01…LP-31 e LP-33; LP-32 revertida (D9 revogada) | relatórios dos lotes |
| Revisão visual | ✅ três QAs com capturas 360–1440 e §4 abaixo | `caps/qa-l1`, `qa-l2`, `qa-l3`, `qa-final` |
| Testes funcionais | ✅ testes de domínio/views/menu/sessão verdes; 15/15 ações do ⋮ executadas no PREVIEW | `qa-lote3 §4` |
| Teste visual 360–1440 | ✅ 0 px de rolagem lateral na lista em todas as larguras e estados (gaveta, folha, menu) | lotes 1–3 |
| Acessibilidade | ✅ axe 0 violações (lista, abas, Documento, gaveta, folha, fichas, refino, vazio, erro, menu aberto, resumo, painel; 3 perfis; 360–1440); teclado e contraste conferidos | lotes 1–3 |
| Desempenho | ✅ 16–18 consultas constantes; 119 KiB (legado 279 KB/12 linhas); menu sob demanda (12 consultas por menu) | `qa-lote3 §6` |
| Benchmark com o legado | ✅ o novo vence nas tarefas da lista, perde em densidade no desktop por ~0,4 linha e em velocidade de cancelar (pede motivo) | `qa-lote1 §6`, `qa-lote2 §9`, `qa-lote3 §8` |
| Comparação com Roteiros e Termos | ✅ com pendências de padronização nas duas outras listas | §4 |
| Aprovação do QA | ✅ Lote 1 (re-QA 2), Lote 2 (re-QA), Lote 3 (re-QA) | `qa/*.md` |
| Sem regressão conhecida | ✅ | regressões medidas a cada lote |
| Autocrítica | ✅ duas rodadas por lote (Designer) | `visual/oficios-lista-lote*.md` |
| Documentado em `completed-pages.md` | ⏳ **cabe ao orquestrador** registrar a página como concluída | — |
| `scripts/verificar.sh` | ruff, lint-imports, mypy, bandit, migrações e tsc verdes nesta revisão; a suíte rápida não foi rodada pelo QA (roda em paralelo no ambiente) | `/home/claude/tools/qa/verificar.txt` |

## 2. Matriz L1–L80 — situação final
| # | Item | Final | Como ficou (evidência) |
|---|---|---|---|
| L1 | Rota e título | ✅ | migalhas, descrição |
| L2 | Exportar | ✅ | barra fixa, leva o recorte da tela |
| L3 | 14 colunas do XLSX | ✅ ➕ | conferido abrindo o arquivo (tipos reais) |
| L4 | Situação "Arquivado" no XLSX | ✅ | LP-27 |
| L5 | Destinos no XLSX | ✅ | sem a sede |
| L6 | Numeração (piso) | ⛔ | página excluída a pedido (4a3f835); D9 revogada |
| L7 | Importar processo do eProtocolo | ⏳ | D10; entra no "Mais" da barra |
| L8 | Novo ofício | ✅ | barra fixa + vazio |
| L9 | Reaproveitar rascunho vazio (> 30 min) | ⚠️ | o novo sempre cria; excluir o rascunho libera o número — confirmar com o dono |
| L10 | Abas temporais | ✅ | conjuntos idênticos à regra do legado, ofício por ofício |
| L11 | "Que vão acontecer" com rascunho sem data | ✅ | 13 sem data na aba |
| L12 | "Em andamento e realizados" | ✅ | inclui a 1ª saída de hoje |
| L13 | Contas prestadas | ✅ | |
| L14 | Cancelados | ✅ | |
| L15 | Arquivados | ➕ | Documento = Arquivados, fora de "Todos" |
| L16 | Contadores com busca/filtros | ✅ | 14 recortes, 0 divergências |
| L17 | Várias situações juntas | ✅ | aba × Documento combináveis (o legado só no backend) |
| L18 | Busca por número | ✅ | |
| L19 | Busca por protocolo | ✅ ➕ | refino |
| L20 | Busca no motivo | ✅ | `unaccent` (F4) |
| L21 | Busca por destino | ✅ | sem a volta à sede (F2) |
| L22 | Busca por servidor | ✅ ➕ | |
| L23 | Busca sem acento | ➕ | |
| L24 | Busca por placa | ✅ ➕ | com/sem hífen, minúscula (F1) |
| L25 | Busca ao vivo | ✅ ➕ | erro de rede e sessão expirada tratados |
| L26 | Refino da busca | ➕ | também com uma leitura só |
| L27 | Placeholder | ✅ | os seis campos; dica curta em tela estreita |
| L28 | Período da viagem | ✅ | calendário na folha do celular 46/46 alvos |
| L29 | Data do ofício | ✅ | |
| L30 | Ano | ✅ | "Ano do número", só anos existentes |
| L31 | Protocolo / veículo / diárias | ➕ | |
| L32 | Ordenações | ✅ | 6, rótulos honestos |
| L33 | Ordem anunciada = real | ➕ | |
| L34 | Fichas de filtros ativos | ✅ | remoção individual, ordem fora do padrão, "Limpar tudo" que não apaga busca/aba |
| L35 | Agrupamento por mês | ➕ | com contagem |
| L36 | Número | ✅ | placa |
| L37 | Protocolo | ✅ | coluna própria; no celular, no resumo e na busca |
| L38 | Destinos | ✅ | até 3 + "+N", lista no `title`/leitor |
| L39 | Situação do documento | ➕ | sempre |
| L40 | Selo de tempo | ✅ | vocabulário único das três listas; nunca "há N dias" |
| L41 | Tipo do ofício | ✅ | incomum na linha (contorno), completo com o porquê no resumo e no XLSX (D4) |
| L42 | Justificativa | ✅ ➕ | só pendente, prioridade no orçamento de selos |
| L43 | Servidores | ✅ | 3 + "+N" |
| L44 | Motorista de fora da equipe | ➕ | aparece, "(motorista)" visível |
| L45 | Viatura/transporte | ✅ | |
| L46 | Diárias | ✅ | coluna alinhada, nunca truncada |
| L47 | "Sem …" | ✅ | rótulos curtos |
| L48 | Clique abre | ➕ | janela de resumo |
| L49 | Ctrl/clique do meio | ⚠️ | funciona no título (abre a folha em nova aba); a área da linha fora do título não é clicável |
| L50 | Atalho ao editor | ✅ | ⋮ → Abrir o ofício (2 cliques; legado 1) |
| L51 | Menu: Abrir | ✅ | |
| L52 | Menu: Baixar documentos | ✅ | ZIP baixado |
| L53 | Menu: Anexar assinado | ✅ ➕ | ofício e justificativa; inativo explicado |
| L54 | Menu: Importar processo | ⏳ | D10 |
| L55 | Menu: Retificar | ✅ ➕ | emitido → "Editar (retificar)"; rascunho → marca |
| L56 | Menu: Complementar | ✅ | exclusão mútua conferida no banco |
| L57 | Menu: Cancelar | ✅ ➕ | motivo obrigatório |
| L58 | Menu: Reativar | ✅ ➕ | justificativa |
| L59 | Arquivar/Desarquivar | ➕ | |
| L60 | Excluir | ✅ ➕ | só rascunho sem documento |
| L61 | Ver minuta/PDF | ✅ | |
| L62 | Duplicar | ➕ | na lista |
| L63 | Leitor vê menu | ➕ | só leitura |
| L64 | Retorno após ação | ✅ | `voltar` vivo (F3) |
| L65 | Janela Baixar | ✅ | |
| L66 | Paginação | ✅ | 20 por página |
| L67 | Contagem total | ✅ | sem repetição (LP-26) |
| L68 | Vazio sem filtros | ✅ ➕ | |
| L69 | Vazio com filtros | ✅ | ações que tiram só o que dizem (F5, F8) |
| L70 | Carregando | ➕ | |
| L71 | Erro | ✅ ➕ | erro da busca com "Tentar de novo"; sessão expirada sem tela de login dentro de nada |
| L72 | Escopo por unidade | ➕ | 404 fora da unidade (inclusive no menu) |
| L73 | Persistência/voltar | ✅ | voltar do navegador devolve a busca |
| L74 | Atalhos | ➕ | |
| L75 | Responsivo | ➕ | 0 px |
| L76 | Acessibilidade | ➕ | |
| L77 | Consultas | ➕ | 16–18 |
| L78 | Peso | ➕ | 119 KiB |
| L79 | Barra fixa | ➕ | contagem · Exportar · (Mais, sem itens) · Novo |
| L80 | Destaque do recém-salvo | ➕ | conferido depois de "Finalizar" |

## 3. Defeitos F1–F16
| # | Situação final |
|---|---|
| F1 placa | ✅ corrigido |
| F2 destino casava a volta à sede | ✅ "curitiba" 156 → 1 |
| F3 `voltar` velho após busca HTMX | ✅ conferido por POST interceptado |
| F4 motivo sem acento | ✅ |
| F5 vazio errado com filtro da gaveta | ✅ |
| F6 "há N dias" em viagem em curso | ✅ selo de tempo único |
| F7 contadores sem busca/filtros | ✅ |
| F8 "Limpar" apagava a busca | ✅ |
| F9 N+1 do motorista externo | ✅ consultas constantes, Exportar 12 |
| F10 título com todos os destinos | ✅ |
| F11–F16 (legado: ordem anunciada errada, justificativa "pendente" dispensada, 403 ao clicar, situação invisível, Excluir sempre/cancelar sem motivo, rolagem e contraste) | ✅ não se reproduzem no novo |

## 4. Ofícios × Roteiros × Termos (última comparação, 1440 e 390)
Mesma identidade: cabeçalho com filete, abas temporais com o mesmo vocabulário, placa
("OFÍCIO 160/2026", "ROTEIRO #60", "TERMO #8"), selo de tempo único, metadados em colunas com o
período na 1ª, "(motorista)", vazios em itálico, ⋮ flutuante com o mesmo comportamento, barra
fixa com "Novo …". Diferenças que restam (pendências das outras duas páginas, não desta):
Roteiros e Termos ainda mostram o título "Roteiros · 71 roteiros" / "Termos · 8 termos" visível
(a lista de ofícios o deixou só para leitor de tela), os contadores das abas delas ignoram a
busca e "Que vão acontecer" delas não inclui o que não tem data; a descrição de Termos ocupa
duas linhas a 1440 e desloca as abas (P13). Ofícios tem o filtro Documento e a gaveta porque as
outras não têm situação de documento nem filtros finos (decisão registrada no Lote 2).

## 5. Pendências conscientes
**Desta página**
1. ⏳ **Importar processo do eProtocolo** (L7/L54, D10) — o "Mais" da barra existe e aparece
   quando houver item.
2. ⛔ **Numeração** (L6) — excluída a pedido do dono; o piso segue só no serviço.
3. ⚠️ **L9** reaproveitar rascunho vazio — confirmar com o dono (hoje: sempre cria; excluir libera).
4. ⚠️ **L49** linha clicável só no título (Ctrl/meio funcionam nele).
5. Menores registrados: no celular o nome do motorista corta cedo (RM1/RM2); ícone do
   transporte por modal depende do cadastro trazer o meio (M10); link "Viagens em 30 dias" do
   painel leva a "Que vão acontecer" (inclui sem data); `ordem=-numero` na URL; `?resumo=` de
   outras telas para ofício arquivado; com a sessão expirada a busca volta ao login sem o termo
   digitado; grupo do ⋮ continua aberto ao reabrir; fragmento do ⋮ com 12 consultas.

**De outras páginas, achadas no caminho**
6. **Folhas** (ofício, termo, OS, plano, via da OS): 11 e2e + 6 de acessibilidade vermelhos,
   iguais no `main` — e um **provável defeito de produto** apontado pelo Designer: salvar a folha
   do ofício parece desmarcar o motorista (`test_operador_cria_preenche_e_emite_um_oficio`).
   A folha do ofício passa de 25 consultas (26–29, aviso do middleware). Próxima página da missão.
7. **Roteiros e Termos**: contadores com a busca, "sem data" em "Que vão acontecer", título
   visual e contagem repetida, descrição de Termos em duas linhas.
8. **Coffee, Eventos, Imprensa, Palestras, Publicações**: gaveta que abre sozinha, sem fichas.
9. **`completed-pages.md`**: registrar a conclusão (orquestrador).
