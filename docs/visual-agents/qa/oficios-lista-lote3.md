# QA — Lista de ofícios, Lote 3 (LP-30 menu ⋮, LP-31 barra com "Mais", LP-33 docs, saneamento e2e)

> Agente 3 — QA/Benchmark · 2026-10-07 · branch `viagens/reconstrucao` @ `864d7e7`.
> Bases: Lote 2 aprovado (`a10a831`, worktree `/home/claude/l2-wt`, `:8004` — subido para este
> QA com `/home/claude/tools/qa/l2_server.sh`), Lote 1 (`:8003`), `main` (`b47e2d5`, `:8002`),
> LEGADO (`:8001`, só contagens). Chromium 141. LP-32 (Numeração) **fora do escopo**: revertido
> pelo orquestrador (D9 revogada).
> Evidências: `/home/claude/caps/qa-l3/`. Scripts em `/home/claude/tools/qa/`: `l3_matriz.py`,
> `l3_acoes.py` (**escreve no PREVIEW**), `l3_post.py`, `l3_carga.py`, `l3_sessao.py`,
> `l3_toque.py`, `l3_menu_ui.py`, `l3_axe.py`, `l3_outros_menus.py`, `regressao_l3.py`,
> `consultas_l3.py`, `leg_menu_l3.py`, `e2e_l3.sh`, `e2e_motivos.sh`.
>
> **Dados alterados no PREVIEW por este QA** (todos fictícios): rascunho 148/2026 criado e
> excluído; rascunho duplicado de 147/2026 (cancelado, reativado, arquivado, desarquivado —
> ficou como rascunho); termo #8, OS 6 e plano 5 criados do Ofício 155/2026; via assinada do
> Ofício 103/2026 anexada; Ofício 09/2024 aberto para retificação (rascunho, "retificado").

## Veredito: **APROVADO** — com 1 IMPORTANTE a corrigir neste lote

O menu ⋮ canônico funciona de ponta a ponta: as 15 ações foram executadas pela interface e
conferidas no banco (15/15), o servidor recusa o que a política não libera (403/404 em todos os
desvios testados), o menu nunca sai da janela em 6 tamanhos de tela, o foco volta ao ⋮ depois
de cada janela, o axe não acusa nada com o menu aberto (68 execuções, 3 perfis) e não há
regressão nas outras listas. Os três e2e herdados estão verdes por correção legítima. O que
fica: com a **sessão expirada**, o ⋮ mostra a **tela de login inteira dentro do menu** (I1).

## 1. IMPORTANTE

### I1 — Sessão expirada: a página de login aparece dentro do menu ⋮
`static/js/componentes/menu.js` (`carregar()`): o `fetch` de `/oficios/<pk>/acoes/` segue o
redirecionamento para `/conta/entrar/?next=…`, recebe 200 e injeta o HTML da tela de login no
painel (`r.ok` é verdadeiro). Reproduzir: entrar, abrir `/viagens/oficios/`, deixar a sessão
expirar (no PREVIEW: apagar os cookies e criar `pcpr_demo_saiu=1` para desligar a entrada
automática da DEMO) e passar o mouse/abrir um ⋮ ainda não carregado
(`l3_sessao.py` → `qa-l3/menu-sessao-expirada-1440.png`: logotipo, "Acesso ao sistema", campos
de usuário e senha dentro do popover). Em produção, aba esquecida aberta = caso comum.
Sugestão: `fetch(..., {redirect: "manual"})` ou conferir `r.redirected`/o tipo da resposta; o
servidor responder 401 (ou `HX-Redirect`) a pedidos com `HX-Request`; o menu dizer "Sua sessão
terminou — entre de novo" com o link.

## 2. MENORES
- **M1 Pré-carga por "passar por cima"**: cada ⋮ tocado pelo ponteiro dispara um pedido
  (12 consultas, ~30 ms de CPU). Varrer a coluna de ⋮ de cima a baixo = 20 pedidos. Uma
  pequena espera de intenção (≈100 ms) evita isso.
- **M2 Fragmento `/acoes/`** faz 12 consultas para uma linha (reaproveita a consulta da lista
  inteira). Aceitável; vale enxugar.
- **M3 Falha ao carregar**: o texto "Não deu para carregar as ações. Feche e abra de novo." troca
  dentro do item focado, sem `aria-live` nem botão "Tentar de novo" (reabrir tenta de novo —
  conferido). Leitor de tela pode não ouvir a troca.
- **M4 Celular, toque no véu**: fecha sem acionar a linha de trás (conferido), mas o foco vai
  para o `BODY` (no desktop volta ao ⋮).
- **M5 "Termos / Ordens / Planos deste ofício"** no "Mais ações" do resumo aparecem mesmo sem
  nenhum (a condição é a permissão, não a existência) — levam a uma lista vazia. Já era assim
  no Lote 2.
- **M6 Saneamento dos e2e**: (a) `test_operador_cria_preenche_e_emite_um_oficio` ainda clica
  "Salvar rascunho" — a mesma causa corrigida nos outros dois ficou num terceiro; (b) o
  `test_preview_demo` deixou de conferir "Rascunho salvo às" na folha do ofício (a gravação
  automática da folha do ofício perdeu cobertura e2e; Roteiros/Termos/OS ainda conferem a deles);
  (c) o teto de 32 consultas na folha no e2e é o mesmo de `test_views` (legítimo), mas o
  middleware do produto continua avisando acima de 25 (folha com 26–29 no log) — dívida a
  registrar, não mascaramento.
- **M7 Menu longo**: 14–15 itens no rascunho/emitido do gestor (577 px a 1440; folha de 643 px
  a 390, com rolagem interna a 360×640) contra 8 no legado. A divisão em grupos e as descrições
  ajudam; o custo de varredura existe.
- **M8 Vermelhos fora do lote** (ver §7): 11 e2e de folhas + 6 de a11y das folhas, iguais no
  `main`, no mesmo passo — precisam de dono (próximas páginas da missão).

## 3. Itens do ⋮ por estado × perfil (`l3_matriz.py`, fragmento `/acoes/`)
Perfis: `demo` (gestor + admin), `gestor.1` (só gestor), `operador.l3` (ASCOM), `leitor.l3`
(Consulta), `op.dpc` (operador de outra unidade). Casos: rascunho 147/2026, emitido 155/2026
(com via), emitido 103/2026 (com justificativa), cancelado 104/2026, arquivado 03/2024 (SDP-GPV),
outra unidade 158/2026 (SDP-TOL).

| Estado | Gestor | Operador | Consulta | Outra unidade |
|---|---|---|---|---|
| Rascunho | Ver resumo · Abrir · Ver minuta · Baixar… · *Anexar (inativo: "Emita o ofício primeiro")* · Novo termo · Nova OS · Novo plano · Duplicar · Marcar retificado · Marcar complementar · Cancelar… · Arquivar · Excluir rascunho | igual, **sem Cancelar** (sem a permissão) | Ver resumo · Ver minuta | 404 |
| Emitido (com via) | Ver resumo · Editar (retificar) · Ver PDF v1 · Baixar… · **Trocar via assinada…** · Novo termo/OS/plano · Duplicar · Cancelar… · Arquivar | igual, sem Cancelar | Ver resumo · Ver PDF | 404 |
| Emitido + justificativa | … · **Anexar ofício assinado… · Anexar justificativa assinada…** · … | igual, sem Cancelar | Ver resumo · Ver PDF | 404 |
| Cancelado | Ver resumo · Ver PDF · Duplicar · Arquivar · Reativar… | sem Reativar | Ver resumo · Ver PDF | 404 |
| Arquivado | Ver resumo · Ver PDF · Baixar… · *Anexar (inativo: "Desarquive…")* · Novo termo · Duplicar · Desarquivar | (fora da unidade: 404) | Ver resumo · Ver PDF | 404 |
| Outra unidade (gestor vê todas) | sem Nova OS e Novo plano (regra da unidade) | 404 | Ver resumo · Ver PDF | 404 |

Bate com a tabela do relatório do Designer e com `policies.menu_do_oficio`. **Contra o legado
(§1.6 do parity)**: o legado tinha 8 itens para operador e gestor e nada para o leitor; o novo
mantém Abrir, Baixar, Anexar (inativo com o motivo, como lá), as marcas com exclusão mútua,
Cancelar e Excluir, e acrescenta Ver resumo, Ver minuta/PDF, criar termo/OS/plano, Duplicar,
Arquivar, Reativar com justificativa e a leitura para a Consulta. Diferenças conscientes:
Excluir só para rascunho sem documento (o legado oferecia sempre — F15), Cancelar pede motivo,
marcas só no rascunho, "Importar processo" fora (D10).

**O servidor confere de novo** (`l3_post.py`): marcar num emitido → 403 (nada muda); Consulta
→ marcar/arquivar/excluir/cancelar 403, duplicar 302 com mensagem (nada criado); operador de
outra unidade → 404 em `/acoes/`, `/marcar/`, `/arquivar/`; operador cancelando → 403.

## 4. Cada ação, executada (`l3_acoes.py`, gestor DEMO a 1440, conferida no banco)
| Ação | Resultado |
|---|---|
| Duplicar | rascunho novo (148/2026) e abre a folha |
| Marcar como complementar | marcador = complementar; histórico "Marcado como complementar…"; lista volta como estava |
| Marcar como retificado (com complementar ligado) | marcador = retificado; histórico "… A marca de complementar saiu." — **exclusão mútua confirmada** |
| Deixar de ser retificado | marcador vazio |
| Excluir rascunho | ofício some; número volta a ficar livre |
| Cancelar… (motivo) / Reativar… (justificativa) | cancelado com o motivo / volta a rascunho |
| Arquivar (confirmação) / Desarquivar | arquivado / volta às abas |
| Novo termo de autorização | termo #8 ligado ao ofício, abre nos documentos |
| Nova ordem de serviço / Novo plano (confirmação) | OS 6 e plano 5 criados, abrem a folha deles |
| Baixar documentos… | janela com os documentos marcados → `oficio-103-2026-documentos.zip` |
| Anexar ofício assinado… | via criada (3 → 4), item passa a "Trocar ofício assinado…" |
| Editar (retificar) | emitido 09/2024 volta a rascunho "retificado" e abre a folha |
**15 de 15.**

## 5. Comportamento do menu
- **Carga sob demanda** (`l3_carga.py`, `l3_toque.py`): 0 pedidos ao carregar a lista; 1 ao
  passar o mouse (itens prontos no clique); teclado puro (Tab até o ⋮, Enter) já abre com os
  itens e o foco em "Ver resumo"; ↓/End/Esc certos, Esc devolve o foco ao ⋮; toque mostra
  "Carregando as ações…" e os itens em < 1 s; rede caída e HTTP 500 → aviso no menu, reabrir
  carrega (M3); **sessão expirada → I1**.
- **Véu e posição** (`l3_menu_ui.py`, 1440×900, 1024×768, 768×1024, 390×844, 360×640,
  1024×600; 1ª, 5ª e última linha): painel sempre dentro da janela; a 360×640 a folha rola por
  dentro; clicar fora fecha **sem abrir o resumo nem navegar** e devolve o foco ao ⋮ no desktop
  (M4 no celular).
- **Foco devolvido**: Ver resumo → Esc, Baixar → Esc, Cancelar… → Esc, Arquivar → Voltar:
  sempre no ⋮ de origem; nenhum véu sobra. HTMX trocando a lista com o menu aberto: véu e
  popover saem juntos; os ⋮ das linhas novas funcionam.
- **Outras listas** (`l3_outros_menus.py`, Lote 2 × agora): Roteiros, Termos, OS, Planos e
  Servidores com os **mesmos itens**, agora flutuantes (camada de topo), dentro da janela, Esc
  devolve o foco.

## 6. Acessibilidade, regressão, desempenho
- **axe** com o menu aberto (`l3_axe.py`): Ofícios (Todos, Arquivados, Cancelados), painel
  `/viagens/`, "Mais ações" do resumo, Termos, Roteiros, OS × 1440/1024/768/390/360 (gestor) e
  1440/390 (Consulta, Operador) = **68 execuções, 0 violações** (o M8 dos lotes anteriores
  sumiu na origem).
- **Regressão** (`regressao_l3.py`, 26 rotas × 5 larguras, Lote 2 × agora): 0 diferenças, só
  melhoras — UI Lab e Notificações perderam a rolagem lateral de 77/257 px (navegação de módulos
  agora rola de lado).
- **Desempenho** (`consultas_l3.py`, Lote 2 → Lote 3): lista 156,2 → **119,2 KiB** (16
  consultas, iguais); Rascunhos 158,4 → 118,2 KiB; busca 153,8 → 118,1 KiB; painel 59 → 69 KiB
  (ganhou as janelas do menu; 20 consultas); resumo 15 consultas; fragmento `/acoes/` 12
  consultas, 3–9 KiB, ~30 ms de CPU por menu aberto.
- **"Mais" e Numeração**: nenhuma página mostra "Mais" vazio (lista, painel, resumo,
  Roteiros, Termos); `/viagens/oficios/numeracao/` → 404; nenhum link para ela; docs do DS sem
  menção (o UI Lab tem o exemplo do componente "Mais", sem Numeração).
- **M-R1/M-R2/M-R4 do Lote 2**: × da ficha "Veículo" inteiro ao focar (314–335 px, trilho até
  376); "Limpar tudo" primeiro no Tab; dica da busca cabe em 1440 → 360.

## 7. E2E (`e2e_l3.sh`, `e2e_motivos.sh`)
| Conjunto | Branch (`864d7e7`) | `main` (`b47e2d5`) |
|---|---|---|
| fluxo do ofício, termos, OS, planos, assinados, baixar, preview DEMO, menu (novo) | 11 falham · 38 passam | 20 falham · 19 passam |
| a11y das folhas (termo/OS/plano, termo salvo, via assinada) | 6 falham | 6 falham |
- **Os 3 herdados agora verdes**: `test_registro_da_lista_abre_resumo…`, `test_erro_de_validacao…`
  e `test_fluxo_demo_com_base_populosa` (6 larguras). Correções **legítimas**: o produto diz "Ver
  minuta" e grava a folha sozinho com "Finalizar" como envio (rodapé padrão `45c0ae2`, já no
  `main`; o "Salvar rascunho" é um botão invisível para o Enter); a rolagem lateral era do
  produto e foi corrigida no produto. Ressalvas em M6.
- **Os 11 + 6 vermelhos restantes falham igual no `main`, no mesmo passo** (mesma linha e
  mensagem): termo sem links "Gerar … (PDF)", OS sem "Salvar", plano sem "Programa", via da OS
  sem `#via-assinada`, baixar do termo sem `#lista-documentos`, folha do ofício com "Salvar
  rascunho", minuta emoldurada invisível, contraste nas folhas. Nenhum passa pelo menu ⋮ —
  **pré-existentes, das folhas**, não do Lote 3.
- `test_menu_oficio.py` (11 novos): verdes.

## 8. Benchmark legado × novo (cliques até a ação; `leg_menu_l3.py`, somente leitura)
| Tarefa | Legado | Novo | Vence |
|---|---|---|---|
| Baixar documentos | ⋮ → Baixar → Baixar = 3 | ⋮ → Baixar documentos… → Baixar = 3 | empate (o painel do novo nunca sai da tela) |
| Anexar assinado | ⋮ → Anexar → escolher o documento (4 opções) → arquivo → Anexar PDF = 4 + arquivo | ⋮ → Anexar ofício assinado… → arquivo → Anexar = 3 + arquivo | **novo** |
| Marcar complementar | ⋮ → item = 2 (também no emitido, que fica diferente do PDF) | ⋮ → item = 2, só no rascunho | **novo** (mesmos cliques, sem dessincronizar o PDF) |
| Cancelar | ⋮ → Cancelar → confirmar no item = 3, sem motivo | ⋮ → Cancelar… → motivo → Cancelar = 3 + texto | legado em rapidez, **novo** em auditoria |
| Duplicar / novo termo, OS, plano do ofício / arquivar | não estão no menu | 2 cliques (OS/plano/arquivar: 3, com confirmação) | **novo** |
| Ver o que um item faz antes de clicar | descrição em todos | descrição nos que mudam algo; leitura sem descrição | empate |
| Tamanho do menu | 8 itens | 11–15 itens (M7) | legado em concisão |

## 9. Para fechar o lote
Corrigir I1 e mostrar `l3_sessao.py` sem a tela de login dentro do menu (com o aviso de sessão
encerrada). Os menores vão para as pendências; M6(a) é uma linha de teste.

---

## Re-QA — `9f08506` · veredito: **APROVADO**

> Agente 3 · 2026-10-07. Scripts: `l3r_sessao_real.py` (porta 8000 × 8004), `l3r_termo.py`,
> `l3r_grupos.py`, `l3r_menores.py`, mais `l3_axe.py`, `regressao_l3.py` reexecutados. Sessão
> "expirada" simulada como na vida real: só o cookie `pcpr_sessao` sai (o `pcpr_csrf` fica) e
> `pcpr_demo_saiu=1` desliga a entrada automática da DEMO.

**I1 corrigido.**
| Pedido sem sessão | Antes (Lote 2/3, `:8004`) | Agora |
|---|---|---|
| Navegação comum (`/viagens/oficios/`, `/viagens/oficios/exportar/`, `Sec-Fetch-Dest: document`) | 302 → login | **302 → login** (inalterado) |
| Busca ao vivo (HTMX) | 302 seguido; página ia ao login | **401 + `HX-Redirect`** → login com `next` da lista |
| Janela de resumo (HTMX) | **tela de login dentro da janela** | 401 → login com `next=/viagens/oficios/` |
| ⋮ (`fetch`) | tela de login dentro do menu | item "Entrar de novo" focado e anunciado + aviso com link |
| Autosave da folha do ofício | "Não foi possível salvar agora" sem dizer por quê | o mesmo texto **+ aviso "Sua sessão terminou — Entrar de novo"** (`next` = a folha) |
| Autosave da folha do termo | idem, via 302 | 401 + aviso com "Entrar de novo" |
| `/busca/` (JSON), `X-Requested-With`, `Sec-Fetch-Dest: empty` | 302 | 401 JSON com `entrar` |
| Rotas públicas: `/conta/entrar/`, `/saude/` (também com `Accept: application/json`), `/agenda/ics/<token>.ics`, `/static/…`; entrada DEMO | — | **inalteradas** (200 / 404 do token desconhecido / DEMO entra). Não há `/pedido/` nem `/fornecedor/` públicos no novo; os únicos `@login_not_required` são login, saúde e o feed ICS |
| POST sem sessão (form comum) | 403 do CSRF | 403 do CSRF (inalterado, anterior ao lote) |
O middleware novo herda o `LoginRequiredMiddleware` e só troca a resposta do pedido assíncrono;
`test_sessao_expirada.py` + identidade: 50 verdes (a falha de `test_demo` é a de sempre:
nome do banco no `.env`, igual no `main`).

**Menores**: M1 varrer 6 ⋮ rapidamente = 0 pedidos, parar 300 ms = 1 · M3 região viva
`aria-live=polite` com o texto da falha · M4 toque no véu: fecha, nada por trás é acionado,
foco volta ao ⋮ · M5 "… deste ofício" só quando existem (104/2026: nenhum; 155/2026: os três) ·
M6 conferido no relatório do Designer (o teste agora para na folha — ver final).

**Menu agrupado** (`l3r_grupos.py`): com os grupos fechados, ↓ percorre 10 itens e pula o
conteúdo recolhido; no título do grupo `aria-expanded=false`; → e Enter/Espaço abrem e focam o 1º
item; ↓ anda dentro; ← recolhe e volta ao título; Esc fecha o menu e devolve o foco ao ⋮. Leitor:
`menuitem "Criar a partir deste ofício"` (descrição "Termo, ordem de serviço, plano, cópia") e
`group "Retificado ou complementar"` com os dois itens; a descrição do grupo das marcas diz a de
hoje ("Hoje sai sem marca"). Toque a 390/360 abre o grupo; painel dentro da tela (rola por dentro
a 360). axe com grupo aberto a 1440/768/390/360: 0. Perfis: operador vê 9 itens (sem Cancelar),
Consulta 2, nenhum grupo vazio. `l3_axe.py` (68 execuções): 0 violações. Regressão 26 rotas ×
1440/768/390 contra o Lote 2: 0 diferenças (só a rolagem de UI Lab/Notificações que sumiu).

Menores novos: (a) com a sessão expirada, a busca ao vivo volta ao login com o `next` de **antes**
do termo digitado (o Lote 2 levava o termo); (b) um grupo aberto continua aberto ao reabrir o
mesmo menu (o padrão anunciado é recolhido).
