# Fase 11 — Revisão crítica multipapel · Viagens → Ofícios

> As evidências citadas (`scratchpad/…`, capturas e scripts) ficaram fora do repositório.
> Para reproduzir: `scripts/capturar.py` (capturas) e `tests/e2e/` (teclado, axe, desempenho).

## Situação das correções (commit `e77e154`)

| Top-10 | Situação | Prova (teste que reprova sem a correção) |
|---|---|---|
| 1. Enter salva | ✅ Corrigido — botão de envio padrão oculto no início de `#form-oficio` | e2e `test_enter_salva_e_alteracao_nao_salva_e_avisada` |
| 2. Perda de dados | ✅ Corrigido — `protecao.js`: "Alterações não salvas" na barra, confirmação ao sair, estado sujo mantido após "Adicionar destino" e erro 422 | e2e acima (diálogo `beforeunload`); `test_adicionar_destino_e_erro_marcam_alteracoes_nao_salvas` |
| 3. Foco coberto pela barra | ✅ Barra compacta < 768 px + rolagem no `focusin` + `scroll-padding` | e2e `test_campo_focado_nunca_fica_atras_do_topo_ou_da_barra` (360/768/1440; reprova sem a correção) |
| 4. Ações por permissão | ✅ "Continuar edição" só com permissão de editar; mensagem correta para quem só consulta | `test_consulta_nao_ve_continuar_edicao_e_recebe_mensagem_certa` |
| 5. Abas + busca | ✅ Abas atualizadas por OOB no swap HTMX, preservando `q` e `ordem` | `test_busca_ao_vivo_atualiza_abas_preservando_busca_e_ordem` |
| 6. Foco no resumo de erros | ✅ `foco="resumo-erros"` após salvar inválido | e2e `test_erro_de_validacao_aparece_no_resumo_e_no_campo` (`to_be_focused`) |
| 7. Datas do roteiro | ⏳ Pendente — validar no navegador institucional ou campo mascarado | — |
| 8. Etapas / beco sem saída | 🟡 Parcial — "Revisar e emitir" com pendências salva e volta à seção 7 com aviso | `test_revisar_e_emitir_com_pendencias_volta_para_a_secao`, e2e `test_emissao_bloqueada…` |
| 9. Velocidade do operador | 🟡 Parcial — Ctrl+S feito; duplicar, sugestões de viatura e adicionar vários servidores pendentes | e2e `test_ctrl_s_salva_o_rascunho` |
| 10. Placeholder real / SQL | ✅ Placeholder do protocolo removido (a ajuda mostra o formato); dados reais trocados por fictícios no código atual; consultas repetidas resolvidas (P-1): editar 18, revisar 16, detalhe 17, salvar 25 | `TestOrcamentoDeConsultas` (≤ 20 nas páginas com equipe de 5 e 4 trechos; ≤ 25 no POST) |

**Auditoria final do Ofício (01/10/2026, após o merge do PR 1)** — defeitos visuais
encontrados nas capturas de 360/768/1024/1440 e corrigidos:
- busca do cabeçalho espremida ("B.") a 360 px — regra CSS corrompida na faixa < 768 px;
- nome do produto por baixo do selo "DEV" a 768 px;
- opções de custeio coladas ("Outra instituição◯ Ônus…") — novo grupo `.escolhas` (UI Lab);
- barra de ações quebrando em duas linhas a 768 px;
- no celular, o véu escuro cobria o próprio menu aberto (links impossíveis de tocar);
- tablet (768–1023 px) usava gaveta lateral: agora menu superior horizontal (ADR 0006);
  no celular, gaveta lateral temporária (decisão D9).
O teste responsivo passou a verificar o cabeçalho (sobreposição e busca espremida) e os
links do menu superior; `tests/e2e/test_navegacao_superior.py` mede a geometria do menu.

> Nota: as seções abaixo foram escritas antes da ADR 0006 revisada; menções a "barra
> lateral", "Recolher menu" e gaveta no tablet referem-se à versão anterior do shell.

Também corrigidos: **QA-5** (`scripts/capturar.py` aceita `--saida` fora do repositório) e
**assunto** — deixou de ser campo de texto: agora é calculado (Autorização/Convalidação) com
marcador Retificado/Complementar (ver `docs/parity/oficio.md`, R1).


Data: 01/10/2026 · Servidor DEV `http://127.0.0.1:8000` (dados fictícios) · Repositório lido sem alterações.

## Como a revisão foi feita
- **Capturas** 390 e 1440 px, página inteira, das 10 rotas pedidas → `scratchpad/review/{390,1440}/*.png`, recortes ≤1400 px em `scratchpad/review/crops/`. (`scripts/capturar.py` quebra com `--saida` fora do repositório — ver QA-5 — então usei um script equivalente, `scratchpad/cap.py`.)
- **Axe-core 4.x** (wcag2a/aa, 21aa, 22aa, best-practice) em 8 rotas × 2 larguras + login → **0 violações** (`scratchpad/a11y.py`). A CSP estrita bloqueou a injeção do axe; foi preciso `bypass_csp` (ponto positivo).
- **Fluxos de teclado com Playwright** (`scratchpad/kb.py`, `kb2.py`, `err.py`): Tab até o fim do editor, foco coberto pela barra fixa, Enter dentro de campo, Ctrl+K, busca ao vivo, abas, ordenação, papéis `operador` e `consulta`, erro de validação.
- **Consultas SQL** por página via `CaptureQueriesContext` (Django shell).
- **Comparação** com a referência (`ref/crops/p-viagens-oficios-161-editar-0.png`, foto 1 do usuário) e com `docs/reviews/visual-review.md`.

Severidade: **bloqueia** (não vai para piloto assim) · **importante** (corrigir antes de escalar) · **refinamento**.

---

## 1. Product Designer

**O que funciona e por quê**
- A tela de edição é **uma página com 7 seções numeradas + índice com estado** (`editar.html:45-57`). Isso preserva o modelo mental da referência (seções 1–7) e acrescenta o que faltava: saber o que está pronto sem rolar (✓ verde vs. número).
- A **regra de prazo virou produto**: aviso na seção 6, selo "Justificativa pendente" na lista, contagem "faltam 3 dias", item bloqueante no checklist e botão Emitir desabilitado (`revisar_emissao.html:32`). A regra de negócio mais cara (ofício fora do prazo) é impossível de ignorar.
- **Emissão com rede de segurança**: página de revisão com os dados que vão para o documento, confirmação com o valor total no texto (`revisar_emissao.html:33`), PDF/A versionado com hash e histórico (`1440-viagens-oficios-6-0.png`).

| # | Achado | Evidência | Sev. | Por que importa | Correção |
|---|---|---|---|---|---|
| PD-1 | **Três modelos de etapas para o mesmo fluxo.** Novo: 4 etapas ("Dados iniciais / Equipe e transporte / Roteiro e diárias / Revisar e emitir"); Edição: 7 seções; Emitir: 3 etapas ("Preencher / Revisar / Emitir (PDF/A)"). | `1440-viagens-oficios-novo-0.png`, `1440-viagens-oficios-7-editar-0.png`, `1440-viagens-oficios-7-emitir-0.png` | importante | O usuário perde a noção de "onde estou": a etapa 2 do Novo ("Equipe e transporte") não existe em lugar nenhum depois. Indicador de progresso que muda de forma ensina a ignorar indicadores. | Um único modelo: **Preencher (seções 1–6) → Revisar → Emitir**. No Novo, mostrar só "1 Preencher · 2 Revisar · 3 Emitir" com a etapa 1 ativa; remover o passo-a-passo de 4 itens. |
| PD-2 | **Página "Novo ofício" custa uma ida e volta para pedir 2 campos**, e o "Motivo" é "(opcional)" no Novo mas "(necessário para emitir)" na edição. | `novo.html`; NOVO fields = `data_oficio, motivo` (kb2.py); `1440-viagens-oficios-7-editar-0.png` | importante | A 20 ofícios/dia são 20 páginas e 20 cliques a mais só para reservar número; a divergência de rótulo faz o usuário pular o motivo e cair na pendência depois. | Botão "Novo ofício" faz POST direto (data = hoje) e abre a edição com foco no Motivo; ou manter a página e rotular o Motivo igual: "(necessário para emitir)". |
| PD-3 | **"Salvar e revisar emissão" leva a um beco sem saída** quando há bloqueante: a página de revisão abre com "Emitir ofício" desabilitado e só oferece "Voltar e corrigir". | `1440-viagens-oficios-7-emitir-0.png`; `editar.html:187` (o botão aparece mesmo com `prontidao.pode_emitir` falso, só depende da permissão) | importante | Uma viagem de página inteira para descobrir o que a seção 7 e a barra ("1 pendência") já diziam. | Quando há bloqueante, o botão dourado vira "Ver 1 pendência" e rola/foca a seção 7; "Salvar e revisar emissão" só com `pode_emitir`. |
| PD-4 | **Paridade com a referência não verificável**: `docs/product/` está **vazio**, embora `CLAUDE.md` diga para ler a especificação lá. Itens visíveis na referência e ausentes no novo: selo **"Com termo"** por servidor, **sugestões de viatura da unidade**, **modelo de motivo** (no novo só existe "texto pronto" para a justificativa). | `ls docs/product` → vazio; `ref/crops/p-viagens-oficios-161-editar-0.png`; `docs/design-system/components.md:33` cita "com termo", mas nenhum template usa | importante | Sem especificação, a "Fase 12 revisão visual" compara só aparência; cortes de escopo ficam implícitos e reaparecem no piloto como "faltou X". | Escrever `docs/product/oficios.md` com a lista de paridade (tem / não tem / fora do piloto, com decisão e responsável) antes do piloto. |
| PD-5 | **O mesmo estado tem três nomes**: "Fora do prazo" (cabeçalho da edição), "Justificativa pendente" (lista/painel), "Obrigatória" (seção 6), "Obrigatória e ausente" (revisão). | `editar.html:11`, `_registro.html:11`, `editar.html:159`, `revisar_emissao.html:24` | refinamento | Vocabulário instável atrapalha busca, suporte ("o meu está fora do prazo ou pendente?") e treinamento. | Um par de termos: estado do prazo = "Fora do prazo"; tarefa = "Justificativa pendente/preenchida". Usar os mesmos em todo lugar. |

---

## 2. UX Designer

**O que funciona e por quê**
- **Checklist de prontidão com links para a seção** (`_prontidao.html:6-9`), separando "bloqueia" de "não impede a emissão". Transforma validação em lista de tarefas, em vez de erro na hora de emitir.
- **Resumo de erros com âncoras** após salvar inválido ("Há 2 campos para corrigir… Protocolo: tem 9 dígitos; você informou 3"), mensagens que dizem o que fazer (`err.py`).
- **Equipe salva na hora com HTMX** e recálculo das diárias por evento (`editar.html:151`): adicionar o motorista e ver o valor mudar sem recarregar é exatamente o feedback que o operador precisa.

| # | Achado | Evidência | Sev. | Por que importa | Correção |
|---|---|---|---|---|---|
| UX-1 | **Modelo de salvamento misto e não sinalizado.** Equipe salva na hora; todo o resto só com "Salvar rascunho"; "Adicionar destino" **não salva** (só reexibe com linha a mais, `views.py:167-181`). A barra continua dizendo "última alteração 01/10/2026 13:26" depois de mudanças não salvas. Não há aviso ao sair (`grep beforeunload static/js` → nada). | `_equipe.html:4` ("alterações salvas na hora"), `views.py:167`, `enter-assunto.png` | **bloqueia** | O operador aprende "aqui salva sozinho" na Equipe e generaliza; ao sair pela lateral perde Assunto/Roteiro sem aviso. Perda silenciosa de dados é o pior erro possível num formulário de 7 seções. | (a) Marcar o formulário como "sujo" ao digitar e trocar o status da barra para "Alterações não salvas" (texto + ícone); (b) `beforeunload` + interceptar links da lateral quando sujo; (c) "Adicionar destino" deve salvar o rascunho antes (ou ser só cliente, via `<template>`). |
| UX-2 | **Enter em qualquer campo de texto dispara "Adicionar destino"**, não "Salvar". O primeiro botão submit de `form-oficio` na ordem do documento é o do Roteiro (`editar.html:115`), anterior ao "Salvar rascunho" (`editar.html:186`). Teste: Enter no Assunto → nenhuma gravação, surge "Destino 2" vazio, foco salta para a Cidade, rolagem muda; ao recarregar, o Assunto voltou ao valor antigo. | `kb.py` (fieldsets 2→3, foco `id_destino-1-cidade`, valor não persistido), `enter-assunto.png` | **bloqueia** | Enter é o gesto mais comum de quem digita rápido. O resultado é o oposto do esperado e ainda perde a edição se o usuário sair. | Colocar um `<button type="submit" form="form-oficio" hidden>` (salvar) **antes** de qualquer outro submit — ou dentro do `<form id="form-oficio">` vazio — para que a submissão implícita seja "Salvar rascunho". Teste e2e: Enter no Assunto grava. |
| UX-3 | **Busca ao vivo e abas/ordenação não conversam.** Ao digitar "Maring" a lista filtra via HTMX (URL `?q=Maring`), mas as abas continuam com `href="?situacao=rascunho"` e contadores globais; clicar numa aba **apaga a busca**. A ordenação, ao contrário, só aplica com o botão "Aplicar". | `kb2.py` (tab hrefs sem `q`, busca vazia depois do clique; ordenar sem Aplicar não muda); `lista.html:10-22` (abas fora de `#resultados`) | importante | Dois comportamentos de filtro na mesma barra (um ao vivo, um com botão) e um filtro que se desfaz sozinho geram desconfiança no resultado. | Incluir as abas no alvo do swap (`hx-select="#resultados, nav.abas"` com `hx-swap-oob`) ou montá-las a partir de `request.GET`; aplicar a ordenação no `change` do select e remover "Aplicar" (manter para sem-JS em `<noscript>`). |
| UX-4 | **Sem navegação por seções abaixo de 1024 px.** O índice é `display:none` (`layout.css:698`) e a página de edição tem **4254 px** de altura a 390 px. | `cap.json` (altura 4254), `390-viagens-oficios-7-editar-*.png` | importante | No celular/tablet o usuário rola às cegas por 7 seções; o checklist só aparece no fim. | Transformar o índice em barra horizontal fixa sob o cabeçalho (chips 1–7 com ✓) ou num `<details>` "Seções (5/7 prontas)" no topo. |
| UX-5 | **Na revisão, a pendência que bloqueia vem depois do aviso** e o campo "Justificativa: Obrigatória e ausente" aparece no cinza terciário (`.vazio-inline`, `components.css:1408`). | `1440-viagens-oficios-7-emitir-0.png`, `390-viagens-oficios-7-emitir-0.png` | refinamento | O que impede a emissão deve ser o primeiro e o mais forte visualmente; hoje é o mais fraco. | Ordenar pendências por `bloqueia` desc.; usar `--cor-perigo` + ícone no "Obrigatória e ausente". |

---

## 3. UI Designer

**O que funciona e por quê**
- **DNA da referência mantido com disciplina**: cabeçalho grafite com filete dourado de 3 px, micro-rótulos em caixa alta (`--texto-2xs` 11 px), item ativo da lateral com barra dourada (`1440-viagens-oficios-0.png` vs. foto 1 do usuário). Fica reconhecível como PCPR sem copiar o CSS antigo.
- **Hierarquia tipográfica clara**: título 28 px, corpo 14 px, valores 36 px; o card "Valor total" em fundo dourado-50 com texto dourado-700 (5,46:1) destaca o número que importa.
- **Tokens de verdade**: nenhum hex solto; contrastes conferidos — botão marca 6,43:1, texto terciário 5,3:1, borda de campo 3,43:1 (≥3:1 de componente).

| # | Achado | Evidência | Sev. | Por que importa | Correção |
|---|---|---|---|---|---|
| UI-1 | **Barra de ações fixa ocupa 169 px no celular** (20% de uma tela de 844 px), com botões empilhados de larguras diferentes e alinhados à esquerda, e o status em 2 linhas. | `err.py` (altura 169), `390-viagens-oficios-7-editar-0.png` | importante | Esconde conteúdo, compete com o teclado virtual e parece improvisada. | < 480 px: status vira uma linha curta ("1 pendência") ou some; dois botões lado a lado em grade 1fr/1fr com rótulos curtos ("Salvar" / "Revisar"); padding `--esp-2`. |
| UI-2 | **Selos dentro do `<h1>`** ("Ofício 002/2026 Rascunho Fora do prazo"); a 390 px "Fora do prazo" quebra sozinho para a linha de baixo, desalinhado. | `editar.html:10-11`; `390-viagens-oficios-7-editar-0.png`; nome acessível do h1 em `a11y.py` | refinamento | O título fica com três pesos visuais concorrentes e leitores de tela leem o status como parte do título. | Mover os selos para uma linha de metadados abaixo do título (`pagina-cabecalho__meta`), com `gap` e `flex-wrap`. |
| UI-3 | **Largura de conteúdo inconsistente entre telas irmãs**: lista/edição/detalhe usam a largura toda (até 1408 px); Novo e Emitir são centralizados mais estreitos (≈ 896 px), então o breadcrumb e o título "pulam" de posição ao navegar Lista → Novo → Edição → Emitir. | `1440-viagens-oficios-novo-0.png` (título em x≈460) vs. `1440-viagens-oficios-0.png` (x≈280) | refinamento | Saltos de alinhamento entre passos do mesmo fluxo parecem troca de sistema. | Manter o breadcrumb e o cabeçalho alinhados à esquerda da área de conteúdo em todos os arquétipos; estreitar só o corpo do assistente. |
| UI-4 | **Botão motorista é um bloco grafite sólido só com ícone**, mais pesado que o nome do servidor e igual ao selo "Motorista". | `1440-viagens-oficios-7-editar-0.png` (cartão Carla), `_equipe.html:22` | refinamento | Peso visual alto para uma ação secundária; o estado "pressionado" só aparece pela cor. | Interruptor com rótulo visível "Motorista" (`.interruptor`, já no DS) ou botão contorno com texto; manter `aria-pressed`. |
| UI-5 | **Tela 404 sem identidade no ambiente DEV**: com `DEBUG=True` aparece a página técnica do Django ("Page not found", `lang="en"`), embora `handler404` exista. | `390-nao-existe-0.png`; `a11y.py` (`lang: en`) | refinamento | A rota foi listada para revisão e não pode ser avaliada; quem testa em DEV nunca vê a tela real. | Rota `/__erro/404/` só em DEV que renderiza `erros/erro.html`, e incluí-la nas capturas. |

---

## 4. Acessibilidade

**O que funciona e por quê**
- **Axe 0 violações** em todas as rotas, 390 e 1440 px, incluindo regras WCAG 2.2 AA. `lang="pt-BR"`, um `h1` por página, seções com `aria-labelledby`, títulos de página únicos ("Ofício 002/2026 — edição · PCPR…").
- **Primeiro Tab = "Pular para o conteúdo"**; botões-ícone com nome contextual ("Ações do Ofício 002/2026", "Remover Carla Regina Duarte da equipe"); `aria-pressed` no motorista; campos com `aria-describedby` para ajuda e erro (`ui.py:62-74`).
- **Paleta de comandos acessível**: `role=combobox`, `aria-activedescendant`, setas/Enter/Esc anunciados no rodapé (`ctrlk.png`); Enter abriu o Ofício 002 corretamente.

| # | Achado | Evidência | Sev. | Por que importa | Correção |
|---|---|---|---|---|---|
| A-1 | **Foco coberto pela barra fixa (WCAG 2.2 — 2.4.11) a 390 px**, apesar do `scroll-padding-bottom: 7rem` (112 px). A barra tem 169 px, e o navegador não rola um elemento que já está "na viewport" atrás de um sticky: 11 paradas de Tab ficaram cobertas (Assunto, Instituição, Retorno). Também a 1440 px: "Justificativa" e "Recolher menu". | `kb.py` (lista "obscured"); `layout.css:565-567` | importante | Quem usa teclado ou ampliação não vê onde está digitando. A revisão anterior declara este item como corrigido (`visual-review.md`). | Diminuir a barra (UI-1) e definir `scroll-padding-bottom` a partir da altura real (`--altura-barra-acoes`, medida por JS/ResizeObserver); em `focusin`, `scrollIntoView({block:"nearest"})` quando o retângulo cruza a barra. Teste e2e por largura. |
| A-2 | **Resumo de erros não recebe foco** após salvar inválido: `document.activeElement` = `<body>`, `scrollY = 0`. O componente tem `tabindex="-1"` e `role="alert"` mas nada o foca; `role=alert` presente no carregamento não é anunciado de forma confiável. | `err.py`; `resumo_erros.html:2` | importante | Usuário de leitor de tela submete e "nada acontece". | Reaproveitar o mecanismo `foco` já existente (`editar.html:189`): quando há erros, `contexto["foco"] = "resumo-erros"`; e `<title>` com prefixo "Erro: ". |
| A-3 | **Nomes acessíveis colados**: os títulos das seções são lidos "1Dados do ofício", "2Equipe"… (span numérico sem separação), e o h1 da edição inclui "Rascunho Fora do prazo". | `a11y.py` (headings), `editar.html:62` | refinamento | Leitura estranha e navegação por títulos poluída. | `<span class="cartao__numero" aria-hidden="true">` + texto "Seção 1 de 7" em `sr-only`, ou só `aria-hidden`; selos fora do h1 (UI-2). |
| A-4 | **Alvos pequenos nas migalhas**: "Início" 32×20, "Viagens" 50×20 (abaixo de 24 px de altura, WCAG 2.5.8), presentes em todas as telas; o celular é onde mais se usa a migalha para voltar. | `a11y.py` (`small`) | refinamento | Toque impreciso a 390 px. | `padding-block: 2px` + `min-height: 24px` nos links de `.migalhas`. |
| A-5 | **Links que abrem nova aba sem aviso** ("Ver minuta", "Ver minuta (PDF)" com `target="_blank"`). | `editar.html:15`, `_registro.html:33`, `revisar_emissao.html:31` | refinamento | Muda o contexto sem avisar (WCAG 3.2.5, boa prática); usuário de leitor de tela "perde" o botão Voltar. | Ícone de saída + `<span class="sr-only">(abre em nova aba)</span>`. |

---

## 5. Frontend

**O que funciona e por quê**
- **HTML-first com melhoria progressiva**: formulários funcionam sem JS (`<noscript>` na busca de servidor, `_equipe.html:17`), HTMX só onde dá retorno; Web Components pequenos (`static/js/componentes/*.js`, 4,1 mil linhas no total).
- **CSP estrita com nonce** de fato aplicada (bloqueou a injeção do axe) e scripts inline só com `nonce` (`editar.html:189`).
- **Concorrência pensada**: campo `versao` + `ConflitoDeEdicao` (`views.py:194-197`) e OOB do `versao` quando a equipe muda (`_equipe.html:2`), evitando que o salvar sobrescreva a equipe gravada pelo HTMX.

| # | Achado | Evidência | Sev. | Por que importa | Correção |
|---|---|---|---|---|---|
| F-1 | **Submissão implícita aponta para o botão errado** (causa técnica de UX-2): campos ligados a um `<form>` vazio por atributo `form=`; o primeiro `type=submit` com `form="form-oficio"` em ordem de documento é `acao=adicionar_destino` (`formnovalidate`). | `editar.html:33-37, 115, 186` | **bloqueia** | Bug determinístico e silencioso; nenhum teste e2e cobre Enter em campo. | Botão padrão oculto dentro de `#form-oficio` (`<button type="submit" hidden tabindex="-1">`) + teste e2e. |
| F-2 | **Links de edição dependem só do estado, não da permissão.** `o.editavel` (`_registro.html:7, 32`) faz o usuário `consulta` ver "Continuar edição" e ir para `/editar/`, que redireciona com a mensagem **falsa** "O Ofício 002/2026 não está em rascunho" (`views.py:159-161`) — ele está em rascunho; o motivo é permissão. | `kb2.py` (consulta: menu com "Continuar edição"; `/7/editar/` → `/7/`) | importante | Interface que oferece o que não pode fazer e depois mente sobre o motivo; viola a regra "autorização em policies.py". | Anotar `pode_editar` por linha via `policies` (ou `o|pode_editar:request.user`); na view, mensagem distinta para "sem permissão" vs. "não está em rascunho". |
| F-3 | **Abas fora do alvo do HTMX** (causa de UX-3): `hx-select="#resultados"` atualiza a lista e o total, mas não `nav.abas`, cujos `href` são calculados no servidor com o `termo` antigo. | `lista.html:10-22` | importante | Estado da URL e estado da UI divergem. | `hx-swap-oob` nas abas no parcial, ou parcial `resultados` incluir as abas. |
| F-4 | **`datetime-local` nativo para todos os horários do roteiro**: 5–6 paradas de Tab por campo (o retorno somou 6 paradas no teste), formato decidido pelo idioma do navegador/SO, AM/PM no Chromium sem pt-BR (`roteiro-ptbr.png`, mesmo com `--lang=pt-BR`). | `kb.py` (`id_retorno-saida` ×6), `roteiro-ptbr.png` | importante | 4 campos de data/hora × 5 segmentos = 20+ Tabs por ofício; e risco de "10/04" ser lido como 10 de abril em máquinas com Windows em inglês. | Campos de texto com máscara `dd/mm/aaaa hh:mm` (já há `mascara.js`) + `inputmode="numeric"`, validação no servidor; ou ao menos validar no Chrome/Edge institucional antes do piloto (já registrado como aberto em `visual-review.md`). |
| F-5 | **Exclusão de destino adiada** por checkbox "Remover este destino ao salvar" (`editar.html:136`). | `enter-assunto.png` | refinamento | Padrão incomum; o usuário marca, não salva, e o destino continua no PDF. | Botão "Remover" que tira a linha imediatamente (cliente) e grava no salvar, com desfazer. |

---

## 6. Performance

**O que funciona e por quê**
- **Servidor rápido e previsível**: 15–25 consultas por página, 15–94 ms no shell; tempo até `networkidle` ≈ 30 ms + 500 ms de ociosidade em todas as rotas (`cap.json`).
- **Peso pequeno**: HTML 8–34 KB; 17 requisições por página, uma fonte variável de 48 KB, brasão WebP de 5,4 KB; produção com `CompressedManifestStaticFilesStorage` (`config/settings/base.py:160`).
- **Orçamentos escritos e testados no CI** (`docs/quality/performance-budgets.md`), o que torna regressões visíveis.

| # | Achado | Evidência | Sev. | Por que importa | Correção |
|---|---|---|---|---|---|
| P-1 | **`/emitir/` já está no teto do orçamento (25 consultas de ≤25)** e `/editar/` em 24; a tabela `viagens_trecho` é lida **6×** em `/emitir/`, 4× em `/editar/` e 3× no detalhe (prontidão, prazo, diárias e documento recalculam cada um). | Shell: `/viagens/oficios/7/emitir/ 25 queries`, repetição de `SELECT "viagens_trecho"…` | importante | Com 3 destinos e 5 servidores (cenário real), passa do orçamento e o CI reprova; cada recálculo também é um risco de divergência. | Carregar trechos/viajantes uma vez (`prefetch_related` + passar listas para `verificar_prontidao`, `prazo`, `diarias`) ou memorizar no objeto por requisição. |
| P-2 | **10 scripts separados em toda página** (8 componentes + htmx + app) e 4 CSS, inclusive em telas que não usam combobox/abas/máscara. | `cap.json` (lista de URLs do `/viagens/oficios/`) | refinamento | Em HTTP/1.1 na rede institucional cada arquivo é uma ida e volta; dentro do orçamento hoje, mas cresce a cada componente. | Carregar componentes sob demanda (`import()` quando o elemento existe) ou concatenar no build do `collectstatic`. |
| P-3 | **Lista sem medição de escala**: 15 consultas com 4 linhas; o orçamento assume 20 por página, mas nenhum cenário com 20 ofícios × N viajantes foi medido. | `cenarios.py` (4 ofícios), `docs/quality/performance-report.md` | refinamento | Busca por texto + `prefetch` de viajantes/trechos precisa ser comprovada com volume do ano (o número 131/2026 da referência sugere centenas). | Semear 300 ofícios e medir lista, busca "Maringá" e paleta Ctrl+K; adicionar ao `test_desempenho.py`. |
| P-4 | **Paleta Ctrl+K e busca ao vivo sem medição de latência**; a busca dispara a cada 350 ms de digitação (`lista.html:22`). | `lista.html:22` | refinamento | No volume real, cada tecla vira consulta com `icontains` em vários campos. | Índice trigram (pg_trgm) nos campos buscados e medir p95. |

---

## 7. QA

**O que funciona e por quê**
- **Cobertura séria**: domínio de diárias/prazos/extenso testado, e2e da jornada, axe em 6 larguras, orçamentos de desempenho (`tests/e2e/*`, git log "95% de cobertura").
- **Papéis respeitados no servidor**: `consulta` recebe **403** em `/novo/` e `/emitir/`, sem botão "Novo ofício" (`kb2.py`).
- **Validação útil**: protocolo com 3 dígitos → "O protocolo tem 9 dígitos; você informou 3." (mensagem que diz o que fazer).

| # | Achado | Evidência | Sev. | Por que importa | Correção |
|---|---|---|---|---|---|
| QA-1 | **Enter no campo não salva e adiciona destino** (UX-2/F-1) — reproduzível 100%. | `kb.py`, `enter-assunto.png` | **bloqueia** | Perda de dados no fluxo principal. | Corrigir + teste e2e "Enter em Assunto grava e mostra toast". |
| QA-2 | **Placeholder do protocolo é um protocolo real de outro ofício** (um protocolo real no campo vazio do 002 = protocolo do 001), em cinza-claro parecido com valor preenchido; ao mesmo tempo o checklist diz "Protocolo… não informado". | `1440-viagens-oficios-7-editar-0.png`, `1440-viagens-oficios-0.png` (001 com o mesmo protocolo) | importante | Na captura parece preenchido; usuários e testadores vão ler como dado. Exemplo também na ajuda logo abaixo (duplicado). | Remover o placeholder (a ajuda já dá o exemplo) ou usar um formato neutro "00.000.000-0". |
| QA-3 | **Usuário `consulta` vê "Continuar edição" e recebe mensagem falsa** (F-2). | `kb2.py` | importante | Teste de permissão cobre a URL mas não o que a UI oferece. | Teste e2e por papel verificando ausência de ações de escrita no menu da linha. |
| QA-4 | **Abas descartam a busca** (UX-3). | `kb2.py` | importante | Resultado de filtro incorreto = retrabalho e erro de conferência. | Teste e2e: buscar, trocar aba, conferir `q` mantido e contadores. |
| QA-5 | **Ferramenta de captura quebra fora do repositório**: `scripts/capturar.py:61` usa `destino.relative_to(RAIZ)` e lança `ValueError` com `--saida` em outro diretório (a captura do 1º arquivo é salva e o resto não). Além disso as capturas mostram datas em `mm/dd/aaaa` e AM/PM, o oposto do que o usuário verá. | Execução inicial desta revisão; `roteiro-ptbr.png` | refinamento | Evidência visual enganosa e ferramenta do time frágil. | `print(destino)` sem `relative_to`; marcar nas capturas que campos nativos estão em en-US, ou trocar por campo mascarado (F-4). |
| QA-6 | **Afirmações da revisão anterior não se sustentam no teste**: "barra fixa podia cobrir o campo focado — corrigido" (`visual-review.md`) ainda falha (A-1). | `kb.py` | importante | Itens fechados sem teste automatizado reabrem no piloto. | Todo "corrigido" com teste que reprova sem a correção. |

---

## 8. Usuário operacional (20 ofícios/dia)

**O que funciona e por quê**
- **Ctrl+K "002" + Enter abre o rascunho direto na edição** (`kb2.py`) — o jeito mais rápido de voltar a um ofício, sem passar pela lista.
- **Diárias calculadas e por extenso automaticamente**, "Como foi calculado" sob demanda — elimina a conta manual e a digitação do extenso, que é onde mais se erra.
- **Lista legível**: destino, período, equipe, viatura e valor numa linha; "faltam 3 dias" em âmbar e "Justificativa pendente" mostram o que precisa de atenção hoje.

| # | Achado | Evidência | Sev. | Por que importa | Correção |
|---|---|---|---|---|---|
| OP-1 | **76 Tabs do topo até "Salvar rascunho"** (63 no celular) e nenhum atalho de salvar. | `kb.py` | importante | Com 20 ofícios/dia, salvar é o gesto mais repetido; hoje exige mouse ou rolar até a barra. | Ctrl+S / Cmd+S = Salvar rascunho (anunciado no botão com `<kbd>`), e Enter em campo = salvar (QA-1). |
| OP-2 | **Densidade menor que a referência**: na referência Nº/Protocolo/Custeio/Data cabem numa linha e servidores + viatura aparecem na primeira dobra; no novo a primeira dobra (1440×900) mostra só a seção 1, e o custeio virou 3 rádios longos. | `ref/crops/p-viagens-oficios-161-editar-0.png` vs. `1440-viagens-oficios-7-editar-0.png` | importante | Mais rolagem por ofício; o operador conferia tudo de relance. | Custeio como `select`/segmentado compacto; Protocolo + Data + Nº numa linha; Assunto com valor padrão recolhido ("Solicitação de autorização…" é sempre igual). |
| OP-3 | **Sem sugestão de viatura e sem "Com termo"** (ver PD-4): na referência a viatura da unidade aparece pronta para clicar. | `ref/crops/p-viagens-oficios-161-editar-0.png` | importante | Digitar placa a cada ofício é retrabalho. | Chips "Viaturas da ASCOM" acima do combobox; último motorista/viatura usados. |
| OP-4 | **Não há "duplicar ofício"** (menu da linha: Ver detalhes / Continuar edição / Ver minuta). | `kb2.py` (itens do menu) | importante | Muitos ofícios repetem equipe, viatura e destino (eventos recorrentes); duplicar economiza a maior parte do preenchimento. | Ação "Duplicar como novo rascunho" (nova numeração, datas vazias). |
| OP-5 | **Adicionar servidor exige digitar + escolher, um por vez**; o painel mostra o mesmo 002 duas vezes ("Para concluir" e "Próximas viagens"). | `combo-390.png`; `1440-viagens-0.png` | refinamento | Equipes de 3–5 pessoas = 3–5 ciclos; duplicação no painel ocupa a primeira dobra. | Manter o combobox aberto após escolher (adicionar vários); no painel, não repetir em "Próximas" o que já está em "Para concluir" (ou mostrar só selo). |

---

## 9. Revisor cético

**O que funciona e por quê**
- A base técnica é **verificável**: tokens testados, axe no CI, orçamentos com números, ADRs para cada decisão grande. Dá para discordar com dados, o que é raro em piloto.
- Regras de negócio no domínio puro (`gestao/viagens/dominio/`) com testes — o cálculo de diárias bate com a referência (R$ 2.411,56 · 4 × 100% + 1 × 15%).

| # | Achado | Evidência | Sev. | Por que importa | Correção |
|---|---|---|---|---|---|
| C-1 | **"Axe 0 violações" não significa acessível nem usável**: os dois piores problemas (Enter adiciona destino; foco coberto) passaram por todos os testes verdes. | QA-1, A-1 | importante | A suíte mede o que é fácil de medir; os fluxos de teclado reais não são testados. | Teste e2e "operador só com teclado": criar → preencher → salvar com Enter/Ctrl+S → revisar → emitir. |
| C-2 | **Os dados fictícios são pequenos demais para provar a UI**: 4 ofícios, 1 destino, ≤2 servidores. Nenhuma captura mostra 5 servidores, 3 destinos, nome longo, 20 linhas ou paginação. | `cenarios.py`, capturas | importante | Barra fixa, grades e selos quebram justamente com volume; o piloto vai encontrar isso primeiro. | Cenário "estresse" no `semear_dev` e capturas dele em 360/390/1440. |
| C-3 | **Paridade declarada sem especificação** (`docs/product/` vazio; PD-4). A "revisão visual" compara aparência, não funcionalidade. | `ls docs/product` | importante | Risco de rejeição no piloto por "falta o que eu usava". | Matriz de paridade assinada pelo dono do produto. |
| C-4 | **Datas nativas "validadas" só por suposição** ("em navegadores pt-BR aparece dd/mm/aaaa — validar no Chrome/Edge institucional") e ainda abertas. | `visual-review.md`, `roteiro-ptbr.png` | importante | Erro de dia/mês num ofício de diárias é erro financeiro. | Validar na máquina institucional antes do piloto ou trocar por campo mascarado (F-4). |
| C-5 | **Modelo de salvamento misto foi escolha de implementação, não de produto** (equipe por HTMX porque é fácil; resto por POST). | UX-1 | importante | A inconsistência vai gerar chamados "perdi o que digitei". | Decidir em ADR: tudo autosave (com indicador) ou tudo manual com aviso de sujo. |

---

## Top-10 correções priorizadas

1. **Enter em campo deve salvar, não "Adicionar destino"** — botão submit padrão oculto dentro de `#form-oficio` + teste e2e (UX-2, F-1, QA-1). *bloqueia*
2. **Proteção contra perda de dados**: estado "Alterações não salvas" na barra, `beforeunload`/interceptar navegação, "Adicionar destino" sem descartar silenciosamente (UX-1, C-5). *bloqueia*
3. **Foco nunca coberto pela barra**: barra compacta < 480 px (UI-1) + `scroll-padding` pela altura real + `scrollIntoView` em `focusin`; teste por largura (A-1, QA-6). *importante*
4. **Ações por permissão, não por estado**: esconder "Continuar edição" do `consulta` e corrigir a mensagem falsa em `views.py:159` (F-2, QA-3). *importante*
5. **Abas + busca coerentes**: abas atualizadas no swap HTMX e preservando `q`; ordenação aplicada no `change` (UX-3, F-3, QA-4). *importante*
6. **Focar o resumo de erros após salvar inválido** usando o mecanismo `foco` existente (A-2). *importante*
7. **Datas do roteiro**: campo mascarado `dd/mm/aaaa hh:mm` ou validação documentada no navegador institucional (F-4, C-4). *importante*
8. **Unificar o modelo de etapas e evitar o beco sem saída da revisão**: Preencher → Revisar → Emitir; "Salvar e revisar" só com `pode_emitir`, senão "Ver pendências" (PD-1, PD-3). *importante*
9. **Velocidade do operador**: Ctrl+S, "Duplicar ofício", sugestões de viatura, combobox de servidores que aceita vários seguidos (OP-1, OP-3, OP-4, OP-5). *importante*
10. **Remover o placeholder com protocolo real e alinhar vocabulário de prazo** ("Fora do prazo"/"Justificativa pendente") + reduzir consultas repetidas de trechos antes do teto de 25 (QA-2, PD-5, P-1). *importante/refinamento*

Arquivos de evidência: `scratchpad/review/{390,1440}/`, `scratchpad/review/crops/`, `scratchpad/review/{enter-assunto,ctrlk,roteiro-ptbr,menu-linha,erro-390,combo-390,lista-vazia}.png`, scripts `scratchpad/{cap,a11y,kb,kb2,err}.py`, métricas `scratchpad/cap.json`.
