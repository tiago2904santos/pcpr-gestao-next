# Paridade — Lista de ofícios (`/viagens/oficios/`)

> Agente 1 — Legacy/Parity Analyst · 06/10/2026 · ponto de partida: `docs/parity/oficio.md`
> (matriz do recorte vertical; a linha "Lista / busca" de lá está **desatualizada** — o NOVO já
> tem filtros de período e ordenação; ver §3).
>
> **Privacidade:** o LEGADO roda com backup de dados reais. Nenhum nome, CPF, RG, placa ou
> protocolo real aparece aqui; exemplos usam valores fictícios (`05/2026`, `12.345.678-9`,
> `ABC1D23`, "Fulano"). Os PNGs em `/home/claude/caps/` ficam fora do repositório.

Caminhos abreviados:
- **LEG** = `/home/claude/legado` (somente leitura). Arquivos principais:
  `viagens_oficios/views.py` (`lista` 150-228, `exportar` 231-293, `acao` 806-860),
  `viagens_oficios/selectors.py`, `viagens_oficios/abas.py`, `viagens_oficios/presenters.py`,
  `templates/pages/viagens_oficios/{lista,_linha,_acoes_linha}.html`, `static/js/app.js`,
  `static/js/viagens-filtros-cadastros.js`.
- **NOVO** = `gestao/viagens/` deste repositório: `views.py` (`_recorte_da_lista` 129,
  `exportar` 147, `lista` 162), `queries.py`, `services.py:1010` (`buscar_por_texto`),
  `dominio/busca.py`, `exportacao.py`, `forms.py:52` (`FiltrosOficio`), `policies.py`,
  `templates/viagens/oficios/{lista,_abas,_refino,_registro,_acoes_ciclo,_resumo,_dialogo_resumo}.html`,
  `templatetags/viagens.py`.

Legenda: ✅ paridade · ⚠️ parcial / diferente · ❌ falta no NOVO · ➕ só no NOVO · 🐞 defeito
(em qualquer um dos dois).

---

## 1. O que o LEGADO faz (fonte de verdade)

### 1.1 Cabeçalho da página
| Elemento | Regra | Evidência |
|---|---|---|
| Sobretítulo "VIAGENS" + H1 "Ofícios" | sempre | `lista.html:19-23` |
| **Exportar Excel** | sempre visível (qualquer um com o módulo); leva o recorte atual (`q`, `situacao`, filtros, `sort`) | `lista.html:26`, `views.py:223` |
| **Numeração** | só gestor (`eh_gestor_viagens`) → `/viagens/oficios/numeracao/` (piso anual) | `lista.html:27`, `views.py:972-991` |
| **Importar processo do eProtocolo** | só operador/gestor; abre modal de upload (PDF/PNG/JPG, vários, limite `importacao_limite_mb`, padrão 25 MB) que descobre o ofício pelo conteúdo | `lista.html:28-31`, `pages/viagens_prestacoes/_importar_dialogo.html` |
| **Novo ofício** (botão flutuante fixo no canto inferior direito) | só operador/gestor; `POST /viagens/oficios/criar/` com `next` → cria rascunho **já numerado** e abre o cadastro. Reaproveita rascunho vazio abandonado há > 30 min | `lista.html:33-40`, `views.py:348-359`, `services.py:63-106` |
| Soltar arquivo sobre a lista | operador/gestor: faixa "Solte o PDF do processo…"; soltar **sobre uma linha** importa direto naquele ofício | `lista.html:46-53, 96, 117` |

### 1.2 Situações (abas/"trilha")
Chips com ícone e contador; renderizados como links (`?situacao=<slug>`), um ativo por vez na
UI, mas o backend aceita **várias** (`getlist('situacao')`, OR entre elas — `abas.py:88-95`).

| Chip | Regra exata (`abas.py:73-85`) | Ícone |
|---|---|---|
| Todos | sem filtro de situação | checklist |
| Que vão acontecer (`futuras`) | `cancelado=False` **e** não "finalizado" **e** (`_saida > fim de hoje` **ou** `_saida IS NULL`) — rascunho sem data entra aqui | calendar |
| Em andamento e realizados (`atuais`) | `cancelado=False` **e** não finalizado **e** `_saida ≤ fim de hoje` | clock |
| Contas prestadas (`finalizados`) | `cancelado=False` **e** tem `PrestacaoServidor` **e** nenhuma pendente (`finalizada=False`) | check-circle |
| Cancelados | `cancelado=True` | ban |

- `_saida` = `roteiro.saida_dt` ou, na falta, a menor `saida_dt` dos trechos (`abas.py:39-65`).
- **Contadores reagem à busca e aos filtros** (só ignoram a própria situação):
  `base = _oficios_filtrados(pedido, com_situacoes=False)` (`views.py:167, 195-199`).
- O status do documento (Rascunho/Gerado/Finalizado/**Arquivado**) **não** vira aba; `ARQUIVADO`
  continua aparecendo nas abas temporais.

### 1.3 Busca
- Campo único "Buscar por número, protocolo, motivo ou destino"; envia sozinho **1 s** após parar
  de digitar (recarrega a página inteira) e devolve o foco ao campo via `sessionStorage`
  (`viagens-filtros-cadastros.js`); Enter envia na hora (`app.js:2268-2280`).
- Campos pesquisados (`selectors.py:40-58`): `motivo icontains` · destinos do roteiro
  (`roteiro.destinos`) · destino de **qualquer trecho** (inclui o trecho de volta à sede) ·
  nome dos servidores · `protocolo icontains <dígitos do termo>` (qualquer quantidade de dígitos) ·
  `numero = N` se o termo é só dígitos · `numero/ano` se "N/AAAA".
- **Sem normalização de acentos**: medido — "maringa" → 0, "maringá" → 1; caixa é ignorada (ILIKE).
- Termo "5" casa nº 5 de qualquer ano **e** todo protocolo que contém "5" (ruído alto).
- `distinct()` por causa das junções.

### 1.4 "Filtros e ordem" (`<details>`, abre sozinho quando há filtro ativo)
Campos (aplicam ao mudar — `data-auto-enviar` → `form.submit()`):
| Campo | Regra |
|---|---|
| Viagem a partir de / até (`viagem_de`, `viagem_ate`) | `_saida__date` ≥ / ≤ (data ISO; inválida é ignorada) |
| Ofício a partir de / até (`criacao_de`, `criacao_ate`) | `data_criacao` (= data do ofício) ≥ / ≤ |
| Ano (`ano`) | `ano = AAAA` (só 4 dígitos); opções = anos existentes, desc |
| Ordenar por (`sort`) | `numero_desc` "Número: maior" · `numero_asc` · `criacao_desc` "Criação: mais recente" · `criacao_asc` · `viagem_asc` "Viagem: mais próxima" (nulos no fim) · `viagem_desc` (`selectors.py:13-21`) |

- **Chips de filtros ativos**, cada um com X para remover só ele (inclui "Ordem: …") e contador
  no resumo do `<details>` (`views.py:200-210`, `lista.html:77-83`).
- 🐞 **Ordem padrão incoerente**: sem `sort`, a lista usa o `Meta.ordering` do modelo
  (`-data_criacao, -criado_em`, `models.py:308`), mas o seletor mostra "Número: maior" como
  placeholder; ordem real ≠ ordem anunciada (confirmado na tela: 900014, —, 900013, 900012,
  900010, 900006, 900011…).

### 1.5 Linha (tabela de 1 coluna no desktop; "Data List" no celular)
Título `<h2>` (`_linha.html`; `presenters.py:392-406`):
- `Nº 05/2026 · Protocolo 12.345.678-9 · CIDADE/PR, OUTRA/PR +1 · 25/08 a 30/08/2026`
  (até 2 destinos em CAIXA ALTA + "+N"; período curto; sem número: "Nº —").
- **Selo** (`selo_do_cartao`, `presenters.py:88-96`): Cancelado → "Cancelado"; senão **selo
  temporal** do roteiro (`viagens_roteiros/presenters.py:58-83`): "falta 1 dia"/"faltam N dias"
  (tom aguardando), "começa hoje"/"em andamento" (tom em_andamento), "foi hoje"/"foi ontem"/
  "há N dias" (tom atendido); sem data → status do documento (Rascunho/Gerado/Finalizado/Arquivado).
  ⇒ um ofício **Finalizado/Arquivado com datas não mostra o status** — só o tempo.
- **Tipo** (`tipo_do_oficio`, `presenters.py:99-152`): "Autorização" (neutro) ou "Convalidação"
  (aguardando) + " · Retificado"/" · Complementar"; **tooltip** com o porquê ("A viagem começa
  em …, depois da data do ofício…" + regra da justificativa com dias e prazo).
- **Justificativa**: para todo não cancelado, "Justificativa preenchida" (verde) ou
  "Justificativa pendente" (amarelo) — 🐞 mostra "pendente" mesmo quando a justificativa é
  **dispensada** (não consulta a regra de prazo).

Fatos com ícone (`fatos_do_oficio`, `presenters.py:324-342`), uma linha só com reticências e
`title` com o texto inteiro:
- "Sem roteiro" (apagado) quando não há período/destino;
- Servidores: **todos**, na ordem, "Fulano (motorista)"; ou "Sem servidores";
- Viatura: "modelo · placa" (viatura cadastrada ou placa/modelo manuais) ou "Sem viatura";
- Diárias: "R$ 1.234,56 · 2 x 100% + 1 x 30%" ou "Sem diárias" (aparece "R$ 0,00" sem equipe).

Ícone de documento na 1ª coluna → **editor do documento** (`documentos:editor_pagina 'oficio'`).
Linha cancelada recebe `tm-linha--cancelada`.

**Clique na linha** (`app.js:1997-2015`): vai para `/viagens/oficios/<pk>/editar/?next=<lista>`;
Ctrl/⌘/botão do meio abrem em nova aba; ignora cliques em links/botões/menu e seleção de texto.
🐞 o leitor (sem grupo) cai em 403 — `editar` exige operador (`views.py:575`). 🐞 o GET de
`editar` **grava** (atualiza o snapshot da justificativa, `justificativas_services.py:143-168`).

### 1.6 Menu ⋮ da linha (`_acoes_linha.html`) — só operador/gestor (leitor não vê o menu)
| Item (título · descrição) | Quando | Efeito |
|---|---|---|
| Abrir ofício · "Dados, equipe, roteiro e justificativa" | sempre | link `editar?next=` |
| Reativar ofício · "Retomar o fluxo do documento" | só cancelado | POST `acao/reativar` (sem confirmação, sem justificativa) |
| Baixar documentos · "Ofício, justificativa e termos" | não cancelado | modal (§1.7) |
| Anexar assinado · "Escolher o documento e enviar o PDF assinado" | não cancelado e há PDF gerado; senão item **inativo** "Gere o PDF de um documento primeiro" | modal de anexar |
| Importar processo · "O PDF do eProtocolo: cada documento no seu lugar" | não cancelado | modal de importação com a URL do ofício |
| Retificar ofício / Desfazer retificação · "Atualizar o estado de retificação" | não cancelado | **liga/desliga** a marca (não muda status; exclusiva com complementar) |
| Ofício complementar / Deixar de ser complementar | não cancelado | liga/desliga a marca |
| Cancelar ofício · "Interromper o fluxo mantendo o histórico" | não cancelado | confirmação em 2 cliques ("Cancelar o ofício 05/2026?"); motivo **não** é pedido (fica vazio) |
| Excluir ofício · "Remover permanentemente quando permitido" | **sempre** (inclusive finalizado/cancelado) | 2 cliques ("Confirmar exclusão?"); bloqueia só por `ProtectedError` (prestação/documentos); número vira lacuna |

Não estão no menu: arquivar (rota existe — `views.py:829-832` — mas nenhuma UI chama), reabrir
(fica no formulário), finalizar. As mensagens de retorno (toasts) estão em `views.py:806-860`
("Ofício 05/2026 cancelado. O histórico foi mantido.", "…excluído. O número volta para a
sequência.", "…tem prestação de contas ou documentos vinculados e não pode ser excluído.").
Todas as ações voltam para a lista como estava (`next=url_atual`).

Confirmação "em duas etapas" (`app.js:1736-1795`): 1º clique arma o botão (troca o título,
desarma em 4 s ou no blur), 2º envia; trava duplo envio; o menu fica aberto entre os cliques.

### 1.7 Modais da lista
- **Baixar documentos** (`components/v32/dialogo_baixar.html`): lista marcável (Ofício; Justificativa
  se há texto; um Termo por servidor), estado de cada um ("Sem PDF", "PDF gerado", "Assinado",
  "Assinado, mas os dados mudaram"), "Desmarcar todos", Formato PDF/DOCX, Versão
  Assinado/Arquivo original (só com PDF e algum assinado), Saída Separados/Um PDF só (só PDF e ≥ 2);
  aviso "estão sendo gerados"; POST `/<pk>/baixar/` → arquivo, ZIP ou PDF único (`views.py:296-345`).
- **Anexar assinado** (`components/v32/dialogo_assinado.html`): escolher o documento, PDF, leitura
  das assinaturas do PDF ("quem assinou"), remover versão assinada.
- **Importar processo do eProtocolo** (`_importar_dialogo.html`, origem "oficios").

### 1.8 Paginação, estados, responsivo, desempenho
- 25 por página (`core/listagens.py:11`), `?pagina=N`, faixa elidida (1 de cada lado), "Anterior"/
  "Próxima" com texto, "Mostrando X a Y de N ofícios" só com > 1 página. Página inválida → última.
- Vazio: "Nenhum ofício registrado ainda." / com filtro: "Nenhum ofício encontrado com os filtros
  aplicados." (sem ação). Sem estado de erro/carregamento próprio (recarga de página inteira).
- Responsivo: tabela no desktop, `article.m-item` no celular. **Rolagem horizontal medida**:
  1440 → 108 px, 768 → 780 px, 390 → 170 px (menu do módulo e barra de botões do cabeçalho
  estouram; "Importar p…" cortado em 390).
- Acessibilidade (axe 4.x, wcag2a/aa + best-practice): 2 nós `color-contrast` (sério) em 1440 e 390.
  Linha clicável não é focável (só o ícone e o ⋮ entram no Tab).
- Desempenho (Django test client, `ref_local`, 12 ofícios): **28 consultas**, ~110-170 ms,
  **279 KB de HTML** (≈ 23 KB por linha: JSON dos modais em `data-*` e formulários por item);
  1ª requisição do processo: 298 consultas (caches frios). Busca: 27 consultas. Exportar: 18.
- Atalhos: só Esc fecha o menu; Enter envia a busca. Sem atalho global.

### 1.9 Exportar Excel (`views.py:231-293`)
Arquivo `oficios-AAAA-MM-DD.xlsx`, aba "Ofícios", cabeçalho em negrito com fundo cinza, painel
congelado em A2, largura automática (máx. 60). Mesmo recorte da tela (situações, busca, filtros,
ordem). 14 colunas:

| # | Coluna | Conteúdo / formato |
|---|---|---|
| 1 | Nº | `05/2026` |
| 2 | Data do ofício | data `DD/MM/YYYY` |
| 3 | Protocolo | `12.345.678-9` |
| 4 | Situação | "Cancelado" ou status (Rascunho/Gerado/Finalizado/Arquivado) |
| 5 | Tipo | "Autorização" / "Convalidação" + " (Retificado|Complementar)" |
| 6 | Destinos | destinos do roteiro (até 100) |
| 7 | Saída | data-hora local `DD/MM/YYYY HH:MM` |
| 8 | Retorno | idem |
| 9 | Servidores | nomes separados por vírgula |
| 10 | Motorista | servidor motorista ou nome manual |
| 11 | Viatura | "modelo · placa" |
| 12 | Diárias (R$) | número `#,##0.00` (vazio se não calcula) |
| 13 | Quantidade de diárias | "2 x 100% + 1 x 30%" |
| 14 | Justificativa | "Preenchida" / "Pendente" (se obrigatória) / vazio |

### 1.10 Permissões (LEG)
Módulo `VIAGENS` (middleware + `acesso_ao_modulo`); leitor = módulo sem grupo; operador
(`VIAGENS_OPERADOR`) e gestor (`VIAGENS_GESTOR`) editam; administrador/superusuário passam por
tudo (`viagens_cadastros/permissions.py`). **Sem escopo por unidade**: todos veem todos os ofícios.

| Quem | Vê lista | Exportar | Numeração | Novo / Importar / menu ⋮ | Clique na linha |
|---|---|---|---|---|---|
| Leitor | ✓ | ✓ | — | — | 🐞 403 |
| Operador | ✓ | ✓ | — | ✓ | editar |
| Gestor | ✓ | ✓ | ✓ | ✓ | editar |

---

## 2. O que o NOVO faz hoje

- Arquétipo `arquetipos/lista.html`: migalhas, H1 + descrição, abas, cartão com filtros, resultados,
  barra fixa no rodapé com contagem, **Exportar planilha** (só com resultado) e **Novo ofício**.
- **Abas** (`queries.py:83-111`): Todos (sem arquivados) · Rascunhos · Emitidos · Próximas viagens
  (rascunho/emitido com saída do 1º trecho ≥ agora) · Contas prestadas (emitido + prestação de
  todos finalizada) · Cancelados · Arquivados (só aqui). Contadores **ignoram busca e filtros**
  (`views.py:193`, `contagens(base)`). Abas preservam os demais parâmetros e voltam à página 1.
- **Busca ao vivo por HTMX** (350 ms, `lista.html:17`), troca só `#resultados`, `hx-push-url`,
  abas atualizadas OOB; sem JS há botão "Aplicar". Campos (`services.py:1010-1035`): motivo
  (`icontains`, **com** acento), destino de qualquer trecho e servidor (**`unaccent`**), `N` ou
  `N/AAAA` (`N` sem ano casa qualquer ano), protocolo `contains` só com ≥ 5 dígitos.
  **Refino** (`dominio/busca.py`, `_refino.html`): o termo é lido em leituras (Ofício N/AAAA,
  Protocolo com …, Placa …, Destino "…", Servidor "…") com a contagem de cada uma; um clique
  restringe (`escopo=`), com ficha "Buscando em … ×".
- **Ordenar por** (sempre à vista): Número (mais recente/antigo), Data de saída (próximas/
  recentes, nulos no fim), Data do ofício (mais recente/antiga). Padrão real = `-numero`
  (coerente com o rótulo).
- **Mais filtros** (gaveta, abre sozinha com filtro ativo; selo com a quantidade; "Limpar
  filtros"): Período de saída (calendário de intervalo, 1º trecho), Data do ofício (intervalo),
  Protocolo, Veículo (unidade móvel, ônibus, caminhão, van, caracterizada, descaracterizada,
  sem transporte), Diárias de/até (R$). Pontas invertidas são trocadas; valor inválido é ignorado.
- **Agrupamento por mês** (cabeçalho "OUTUBRO DE 2026"): pela data de saída quando a ordem é por
  saída; senão pela data do ofício.
- **Registro** (`_registro.html`): placa "OFÍCIO 160/2026"; título-link "Destinos · período"
  ("Sem destino"); selo da situação (Rascunho/Emitido/Cancelado); selo de justificativa **só
  quando exigida pelo prazo e só no rascunho**; contagem "faltam N dias" (tom aviso ≤ 10 dias) /
  "amanhã" / "hoje" / "há N dias"; meta: Protocolo, até 3 servidores + "+N" com "(motorista)",
  viatura (placa · modelo) ou descrição do transporte ou "Sem transporte", diárias
  "R$ … · resumo" ou "Sem diárias calculadas". Destaque dourado do registro recém-salvo.
- **Clique** no título → **janela de resumo** (HTMX `viagens:resumo`, 22 consultas): pendências,
  dados, roteiro, diárias, equipe e transporte, documentos e vias assinadas; rodapé com Ver
  PDF/minuta, "Mais ações" (Word, Baixar documentos, termo/OS/plano a partir do ofício, ciclo de
  vida) e "Abrir o ofício"/"Editar ofício" (retificar). Sem JS → folha de edição. `?resumo=<pk>`
  abre a janela já desenhada.
- **Menu ⋮** (`_registro.html:35-50` + `_acoes_ciclo.html`, tudo de `policies.acoes_do_oficio`):
  rascunho → Abrir o ofício · Cancelar · Arquivar · Excluir rascunho (sem documento);
  emitido → Editar (retificar) · Cancelar · Arquivar; cancelado → Ver a minuta (PDF) · Reativar
  (gestor, justificativa obrigatória) · Arquivar; arquivado → Ver a minuta · Desarquivar.
  Cancelar pede motivo obrigatório em janela; confirmações em diálogo próprio.
- **Paginação**: 20 por página, ícones ‹ ›, faixa elidida (±2), "Mostrando 1–20 de 255".
- **Vazios**: arquivados; busca/situação sem resultado (com "Limpar filtros"); lista vazia com CTA
  "Novo ofício" (ou texto para quem não cria). Erro do resumo tem mensagem própria (`registro.js`).
- **Permissões**: `view_oficio` + escopo por unidade de lotação (`policies.oficios_visiveis`);
  Novo exige `add_oficio` + lotação; menu por objeto; 404 para ofício de outra unidade.
- **Desempenho medido** (255 ofícios, gestor, test client): **16-19 consultas constantes**,
  45-160 ms (445 ms a frio), 127 KB por página de 20 (≈ 6 KB/linha); HTMX `#resultados` 94 KB;
  Exportar 255 linhas em **12 consultas**.
- **Responsivo/a11y**: rolagem horizontal **0 px** em 1440/768/390 (abas rolam dentro da faixa);
  axe sem violações em 1440 e 390. Menu com teclado completo (↑/↓/Home/End/Esc). Paleta global
  **Ctrl+K** ou **/** ("131/2026" abre o ofício).

---

## 3. Matriz LEGADO × NOVO

| # | Item | LEGADO (evidência) | NOVO (evidência) | Status |
|---|---|---|---|---|
| L1 | Rota e título | `/viagens/oficios/` "Ofícios" (`lista.html:16-23`) | idem + migalhas + descrição (`lista.html:4-6`) | ✅ |
| L2 | Exportar Excel | botão no topo, sempre (`lista.html:26`) | barra do rodapé, só com resultado (`lista.html:128`) | ✅ |
| L3 | Colunas do XLSX | 14 colunas (`views.py:245-246`) | as mesmas 14 (`exportacao.py:22-24`) + autofiltro + anti-injeção de fórmula | ✅ ➕ |
| L4 | Situação no XLSX | Rascunho/Gerado/Finalizado/Arquivado/Cancelado (`views.py:267`) | Rascunho/Emitido/Cancelado; **arquivado não aparece** (`exportacao.py:77`) | ⚠️ |
| L5 | Destinos no XLSX | `roteiro.destinos` (`views.py:269`) | destinos dos trechos, sem a sede (`exportacao.py:30-36`) | ✅ |
| L6 | Numeração (piso) | botão p/ gestor + tela (`lista.html:27`, `views.py:972-991`) | serviço `definir_piso` existe (`services.py:131`), **sem tela nem URL** | ⛔ removida por decisão do dono (4a3f835) |
| L7 | Importar processo do eProtocolo (topo, por linha, arrastar-soltar) | `lista.html:28-31, 46-53`, `_acoes_linha.html:196` | inexistente | ❌ |
| L8 | Novo ofício | botão flutuante, POST `criar` (`lista.html:33-40`) | barra fixa do rodapé + CTA no vazio, POST `novo` (`_botao_novo.html`, `views.py:219-239`) | ✅ |
| L9 | Reaproveitar rascunho vazio (> 30 min) | `services.py:63-106` | sempre cria; rascunho se exclui e libera o número | ⚠️ (decisão anterior: comportamento legado) |
| L10 | Abas de situação | 4 temporais/prestação + Todos (`abas.py:28-33`) | 6 por situação do documento + Todos (`queries.py:83-94`) | ⚠️ |
| L11 | "Que vão acontecer" inclui rascunho sem data | `abas.py:82-84` | "Próximas viagens" exige saída ≥ agora (`queries.py:208-209`) | ⚠️ |
| L12 | "Em andamento e realizados" | `abas.py:85` | não existe recorte equivalente | ❌ |
| L13 | Contas prestadas | prestação de todos finalizada (`abas.py:36`) | idem, só emitidos (`queries.py:89-90`) | ✅ |
| L14 | Cancelados | flag `cancelado` | situação `cancelado` | ✅ |
| L15 | Arquivados | status existe mas sem aba e sem UI | aba própria; arquivado sai das outras (`queries.py:93, 201-204`) | ➕ |
| L16 | Contadores refletem busca/filtros | sim (`views.py:167, 195`) | **não** — sempre o total da base (`views.py:193`) | ❌ |
| L17 | Várias situações ao mesmo tempo | backend sim (`getlist`, `abas.py:88-95`); UI não | não | ⚠️ (só backend no LEG) |
| L18 | Busca: número `N` e `N/AAAA` | `selectors.py:52-57` | `services.py:1027-1032` (+ `N/`) | ✅ |
| L19 | Busca: protocolo | qualquer dígito (ruidoso) | ≥ 5 dígitos; refino "Protocolo com …" | ✅ ➕ |
| L20 | Busca: motivo | `icontains` | `icontains` (sem `unaccent`) | ✅ (🐞 acento, ver F4) |
| L21 | Busca: destino | destinos + trechos (inclui volta à sede) | trechos (inclui volta à sede) com `unaccent` | ⚠️ 🐞 F2 nos dois |
| L22 | Busca: servidor | `icontains` | `unaccent__icontains` | ✅ ➕ |
| L23 | Busca sem acento | não (medido) | sim (medido: "maringa" = "maringá") | ➕ |
| L24 | Busca: placa | não | só via refino; **busca ampla não procura placa** | ⚠️ 🐞 F1 |
| L25 | Busca ao vivo | recarga 1 s + foco restaurado | HTMX 350 ms, sem recarga, URL atualizada | ✅ ➕ |
| L26 | Refino da busca (leituras com contagem) | — | `dominio/busca.py`, `_refino.html` | ➕ |
| L27 | Placeholder da busca | "número, protocolo, motivo ou destino" (omite servidor) | "Número (131/2026), protocolo, destino ou servidor" (omite motivo) | ⚠️ |
| L28 | Filtro período da viagem | `viagem_de/ate` sobre `_saida` | `saida_de/ate` sobre 1º trecho, calendário de intervalo | ✅ |
| L29 | Filtro data do ofício | `criacao_de/ate` | `criacao_de/ate` | ✅ |
| L30 | Filtro **Ano** | select com anos existentes | inexistente | ❌ |
| L31 | Filtros protocolo / veículo / faixa de diárias | — | `forms.py:71-88`, `queries.py:150-198` | ➕ |
| L32 | Ordenações | 6 (`selectors.py:13-21`) | as mesmas 6 (`views.py:120-127`) | ✅ |
| L33 | Ordem padrão anunciada = real | 🐞 não (anuncia número, ordena por data) | sim (`-numero`) | ➕ |
| L34 | Chips de filtros ativos com remoção individual (inclui ordem) | `views.py:200-210`, `lista.html:77-83` | só selo com a quantidade + "Limpar filtros" (tudo) | ❌ |
| L35 | Agrupamento | nenhum | por mês (saída ou data do ofício) | ➕ |
| L36 | Linha: número | no título "Nº 05/2026" | placa "OFÍCIO 05/2026" | ✅ |
| L37 | Linha: protocolo | no título | na meta | ✅ |
| L38 | Linha: destinos · período | até 2 destinos + "+N" | todos os destinos (sem limite) | ⚠️ (linhas longas) |
| L39 | Selo da situação do documento | só sem datas (`presenters.py:88-96`) | sempre | ➕ |
| L40 | Selo temporal | 7 estados incl. **"em andamento"/"começa hoje"/"foi ontem"** pelo período inteiro | 4 estados só pela 1ª saída: viagem em curso mostra "há N dias" (`templatetags/viagens.py:60-71`) | ⚠️ |
| L41 | Selo **Tipo** Autorização/Convalidação + Retificado/Complementar + tooltip do porquê | `presenters.py:99-152`, `_linha.html` | **ausente** na lista e no resumo | ❌ |
| L42 | Selo justificativa | sempre (🐞 "pendente" mesmo dispensada) | só quando exigida, só rascunho (`templatetags/viagens.py:143-159`) | ✅ ➕ |
| L43 | Servidores na linha | todos, corte com "…" + tooltip | 3 + "+N" | ✅ |
| L44 | Motorista de fora da equipe na linha | nome manual não aparece na linha (só XLSX) | não aparece | ✅ (ambos omitem) |
| L45 | Viatura / transporte | modelo · placa | placa · modelo ou descrição do transporte | ✅ |
| L46 | Diárias | valor · quantidade (R$ 0,00 sem equipe) | valor · resumo ou "Sem diárias calculadas" | ✅ |
| L47 | Ausentes apagados ("Sem …") | sim | sim | ✅ |
| L48 | Clique na linha | página de edição (`app.js:1997-2015`) | janela de resumo (`_registro.html:13`) | ➕ (decisão de produto) |
| L49 | Ctrl/clique do meio = nova aba | sim (linha inteira) | sim no link do título (alvo é só o título) | ⚠️ |
| L50 | Atalho direto ao editor do documento | ícone da 1ª coluna | não (o editor fica na folha) | ⚠️ baixo |
| L51 | Menu: Abrir | sempre | rascunho editável | ✅ |
| L52 | Menu: Baixar documentos | sim | só dentro da janela de resumo | ⚠️ |
| L53 | Menu: Anexar assinado | sim (inativo explicado sem PDF) | só no resumo ("vias assinadas") | ⚠️ |
| L54 | Menu: Importar processo | sim | — | ❌ |
| L55 | Menu: Retificar | liga/desliga marca | emitido → volta a rascunho como retificado (confirmação explica) | ⚠️ ➕ (semântica melhor) |
| L56 | Menu: Complementar | liga/desliga marca | só no campo "marcador" da folha | ⚠️ |
| L57 | Menu: Cancelar | 2 cliques, motivo vazio | janela com motivo obrigatório; dica "prefira excluir o rascunho" | ✅ ➕ |
| L58 | Menu: Reativar | operador, sem justificativa | gestor, justificativa obrigatória | ✅ ➕ |
| L59 | Menu: Arquivar / Desarquivar | sem UI | sim | ➕ |
| L60 | Menu: Excluir | sempre (falha por proteção) | só rascunho sem documento | ✅ ➕ |
| L61 | Menu: Ver minuta / PDF emitido | — | minuta (cancelado/arquivado); emitido: só "Editar (retificar)" | ⚠️ |
| L62 | Menu: Duplicar | — | só na folha (`editar.html:349`) | ➕ (não na lista) |
| L63 | Leitor (sem edição) vê menu | não | sim, só "Ver a minuta" | ➕ |
| L64 | Retorno após ação | lista como estava (`next`) | lista como estava (`voltar`) — 🐞 F3 após busca HTMX | ⚠️ |
| L65 | Modal Baixar documentos | `dialogo_baixar.html` | `componentes/dialogo_baixar.html` (lembra escolhas) | ✅ |
| L66 | Paginação | 25, texto Anterior/Próxima | 20, ícones + rótulos sr-only | ✅ |
| L67 | Contagem total | só com > 1 página | sempre (cabeçalho + barra, `role=status`) | ➕ |
| L68 | Vazio sem filtros | texto | ícone, texto, CTA | ✅ ➕ |
| L69 | Vazio com filtros | texto | busca/situação ✓; **só "Mais filtros" → mostra "Nenhum ofício ainda / Crie o primeiro"** | 🐞 F5 |
| L70 | Carregando | recarga | `hx-indicator`; esqueleto no resumo | ➕ |
| L71 | Erro | página de erro | erro do resumo tratado; erro da busca HTMX sem mensagem dedicada | ⚠️ |
| L72 | Escopo por unidade | não | sim (`policies.py:38-45`) | ➕ |
| L73 | Persistência | querystring (+ foco por sessionStorage) | querystring (`hx-push-url`); voltar do navegador reusa a URL (`vary_on_headers`) | ✅ |
| L74 | Atalhos | Esc no menu | Ctrl+K e "/" globais; menu com setas/Home/End | ➕ |
| L75 | Responsivo | rolagem horizontal 108/780/170 px | 0/0/0 px | ➕ |
| L76 | Acessibilidade (axe) | 2× color-contrast sério | 0 violações | ➕ |
| L77 | Consultas por página | 28 (12 linhas); 298 a frio | 16-19 constantes (20 linhas) | ➕ |
| L78 | Peso da página | 279 KB / 12 linhas | 127 KB / 20 linhas | ➕ |
| L79 | Barra de ações fixa | só o botão flutuante | barra fixa com contagem, Exportar e Novo | ➕ |
| L80 | Destaque do recém-salvo | — | `registro.js` | ➕ |

**Lacunas ❌ (falta no NOVO):**
L6 Numeração · L7/L54 Importar processo · L12 "Em andamento" · L16 contadores com filtro ·
L30 Ano · L34 chips de filtro · L41 Tipo Autorização/Convalidação.

---

## 4. Defeitos e fragilidades encontrados

| ID | Onde | Defeito | Evidência / como reproduzir |
|---|---|---|---|
| F1 | NOVO | Buscar uma **placa** completa (`?q=ABC1D23`) devolve **0** e nenhum refino: a busca ampla não procura placa e a ficha "Placa …" só aparece quando há **mais de uma** leitura com resultado; com `&escopo=placa` vêm 3 ofícios | `services.py:1024-1035` (sem placa), `_refino.html:16` (`refinos|length > 1`); medido no PREVIEW com uma placa da frota fictícia |
| F2 | AMBOS | Busca por destino casa o **trecho de volta à sede**: "curitiba" traz 156 de 258 ofícios, 155 só porque voltam a Curitiba (sede) | NOVO `services.py:1024`, `queries.py:126`; LEG `selectors.py:46` |
| F3 | NOVO | `voltar` da janela de motivo (cancelar/reativar) é fixado no carregamento da página (`componentes/dialogo_motivo.html:12`); depois de uma busca HTMX a ação volta para a lista **antes** da busca | leitura de código; `dialogo.js` não atualiza `voltar` |
| F4 | NOVO | Motivo pesquisado sem `unaccent` (destino/servidor com) — "reuniao" não acha "reunião" no motivo | `services.py:1024` |
| F5 | NOVO | Filtro só da gaveta sem resultado mostra o vazio de lista nova ("Nenhum ofício ainda — Crie o primeiro") | `lista.html:111` testa só `termo or situacao`; `?diarias_de=99999999` |
| F6 | NOVO | Selo temporal não distingue **viagem em andamento**: viagem de 05/10 a 15/10 aparece "há 1 dia" em 06/10 | `templatetags/viagens.py:60-71` (usa só a 1ª saída) |
| F7 | NOVO | Contadores das abas não acompanham busca/filtros: "Cancelados 18" com uma busca que só tem 1 cancelado | `views.py:193` |
| F8 | NOVO | "Limpar filtros" (gaveta e vazio) também apaga a **busca** e a ordem; o vazio apaga até a situação | `lista.html:80, 112` |
| F9 | NOVO | Exportar com motorista externo servidor faz consulta por linha (N+1) — `motorista_externo_servidor` fora do `select_related` | `exportacao.py:72`, `services.py:553-556`, `queries.py:72` |
| F10 | NOVO | Título com todos os destinos sem limite: ofícios com 4+ destinos quebram em 2-3 linhas | `templatetags/viagens.py:96-103` |
| F11 | LEG | Ordem padrão anunciada ("Número: maior") ≠ ordem real (data do ofício) | `selectors.py:103-104`, `models.py:308`, `lista.html:73` |
| F12 | LEG | "Justificativa pendente" em ofício cuja justificativa é dispensada | `_linha.html` (não usa `tipo.justificativa_obrigatoria`) |
| F13 | LEG | Leitor clica na linha e recebe 403; GET de editar grava | `views.py:575`; `justificativas_services.py:143-168` |
| F14 | LEG | Status Finalizado/Arquivado invisível quando há datas | `presenters.py:88-96` |
| F15 | LEG | Excluir oferecido para finalizado/cancelado; Cancelar sem motivo | `_acoes_linha.html:204-211`, `views.py:823-825` |
| F16 | LEG | Rolagem horizontal em todas as larguras; contraste insuficiente | §1.8 |

---

## 5. Como o NOVO pode fazer MELHOR (priorizado)

### P0 — fechar lacunas funcionais e defeitos visíveis
1. **Tipo do ofício na linha** (L41): selo "Autorização"/"Convalidação" (+ "Retificado"/
   "Complementar") calculado no domínio (`dominio/assunto.py` já existe) e anotado em lote (a data
   da 1ª saída já vem em `primeira_saida`). Melhor que o legado: em vez de *tooltip* (inacessível no
   toque), texto curto visível + explicação no resumo ("A viagem começa em 11/10, 5 dias depois do
   ofício; prazo exige 10 → justificativa obrigatória"). Mostrar também na janela de resumo, que
   hoje ignora `assunto`.
2. **Contadores com o recorte** (L16/F7): `contagens()` sobre `buscar_por_texto + filtros
   avançados` (uma agregação, como hoje). Melhor: aba com 0 fica apagada mas clicável e o rótulo
   ganha `aria-label` "Cancelados: 1 com esta busca".
3. **Busca de placa e refino** (F1): incluir placa na busca ampla quando `PLACA` casar, e mostrar a
   ficha mesmo com **uma** leitura útil quando a busca ampla vier vazia ("Nenhum resultado em
   tudo — Placa ABC1D23 (3)"). Teste: `?q=<placa>` ≥ 1.
4. **Destino sem a sede** (F2): filtrar `trechos__destino` excluindo `destino = sede` (como já faz
   o filtro `destinos` de exibição). Melhor que o legado, que tem o mesmo defeito.
5. **Vazio certo para filtros da gaveta** (F5) e "Limpar" que limpa só o que diz (F8): três
   ações — "Limpar filtros" (mantém busca, situação e ordem), "Limpar busca" e "Ver todos".
6. **Selo temporal completo** (L40/F6): usar `primeira_saida` e `ultima_chegada` (anotar `Max`
   em `com_dados_de_lista`): "faltam N dias" · "amanhã" · "começa hoje" · **"em andamento
   (até 15/10)"** · "volta hoje" · "foi ontem" · "há N dias". Domínio puro + teste por fronteira.
7. **Numeração** (L6): tela do gestor para o piso do ano (serviço `definir_piso` já existe), mostrando
   o próximo número, lacunas registradas (liberadas por exclusão) e o último ocupado —
   mais que o legado, que só mostrava o formulário do piso. Link na lista só com
   `pode_gerir_numeracao`.

### P1 — paridade de produtividade
8. **Chips de filtros ativos** (L34) acima dos resultados, cada um com ×, incluindo período, ano,
   protocolo, veículo, diárias, escopo da busca e ordem não padrão; atualizados por HTMX.
9. **Ano** (L30): seletor de ano **do número** (≠ data do ofício: rascunho de dezembro emitido em
   janeiro), opções a partir dos anos existentes; combina com as abas.
10. **"Em andamento e realizados"** (L12): oferecer o recorte temporal que o legado tinha — como
    filtro "Quando" na gaveta (Que vão acontecer · Em andamento · Realizados) ou como abas
    secundárias dentro de Emitidos. "Que vão acontecer" deve incluir rascunhos **sem data**
    (L11), ou a tela deve dizer que eles estão em Rascunhos.
11. **Ações de documento no ⋮** (L52/L53/L61): para emitido, "Ver o PDF (vN)", "Baixar
    documentos…" e "Anexar assinado…" direto no menu (hoje exigem abrir o resumo); para rascunho,
    "Ver a minuta". Mesmo modal `dialogo_baixar` já existente.
12. **Importar processo do eProtocolo** (L7/L54): decisão de produto; se entrar, com a moldura do
    novo (diálogo + arrastar-soltar com alvo visível e teclado), relatório por arquivo e
    "desfazer" — o legado já tinha conferência/aplicar/descartar/desfazer (`viagens_prestacoes`).
13. **`voltar` vivo** (F3): o diálogo de motivo deve usar `location.href` no momento da abertura
    (ou o `hx-push-url` atualizar o campo).
14. **Complementar** (L56): item "Marcar como complementar" no ⋮ do rascunho (hoje só no campo
    da folha), com a mesma exclusão mútua do domínio.

### P2 — acabamento e superação
15. Título com no máximo 3 destinos + "+N" e `title`/resumo com todos (F10).
16. Linha inteira clicável (como o legado) mantendo o link do título como alvo de teclado
    (`data-linha` delegando ao link; respeitar seleção de texto e Ctrl/clique do meio — L49).
17. `unaccent` também no motivo (F4) e placeholder com os 5 campos (L27).
18. `select_related("motorista_externo_servidor")` em `com_dados_de_lista` (F9) e motorista de
    fora da equipe visível na meta da linha (L44).
19. Erro de rede/servidor na busca HTMX: alerta no lugar de `#resultados` com "Tentar de novo"
    (L71).
20. Seleção múltipla de situações via URL mantida compatível (L17) — não precisa de UI.

---

## 6. Critérios de aceite para o QA (lista)
- Todos os itens ❌ e P0 com teste: `test_views.py` (contadores com busca; vazio com filtro da
  gaveta; placa; destino ≠ sede; selo "em andamento"; tipo na linha) e domínio puro para os selos.
- Consultas da lista **constantes** (≤ 20) com 20 e com 200 ofícios (`CaptureQueriesContext`);
  Exportar ≤ 15 consultas para 255 linhas.
- 360-1440 px sem rolagem horizontal; axe sem violações (lista, gaveta aberta, menu aberto,
  resumo aberto, vazios).
- XLSX com as 14 colunas, datas/números reais, e Situação dizendo "Arquivado" quando for o caso.
- Benchmark contra o legado: mesmas buscas de §1.3 com resultado igual ou melhor (acentos).

## 7. Evidências desta análise
- Capturas: `/home/claude/caps/{legado,novo}/{1440,768,390}/viagens-oficios.png`,
  `/home/claude/caps/interacoes/{legado,novo}-*.png` (menu, filtros, baixar, importar, resumo,
  refino, vazio) — fora do repositório (dados do legado).
- Scripts (somente leitura): `/home/claude/tools/cap.py`, `/home/claude/tools/interacoes_lista.py`,
  `/home/claude/tools/axe_lista.py`; medições de consultas com `CaptureQueriesContext` pelo
  `manage.py shell` de cada sistema (só GET).
