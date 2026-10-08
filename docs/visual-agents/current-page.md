# Página atual

## Missão visual exclusiva de Ofícios — 08/10/2026

O pedido posterior substituiu o avanço visual anterior: Lista, Resumo, Folha
e painel Documentos redesenhados na branch `codex/viagens-piloto-resumo`,
base `fdc662f`. Identidade e conferência de valores compartilhadas; variantes
documentais, equipe em linhas, formatação recolhível e campos legíveis no
tablet. Nenhuma nova página de outro módulo neste bloco.

Estado: **bloco concluído, aprovado com ressalvas pelo agente**. Integral
verde (2.193 testes / zero falhas / 7 avisos / 47min58s), 16/16 casos finais
de navegador/UI Lab e revalidação 73/73 do último ajuste. Vinte relatórios
axe sem violações e manifesto de 19 fontes sem divergências.
Relatório: `qa/oficios-premium-2026-10-08.md`; imagens:
`qa/oficios-premium-evidencias.md`. Implementação validada em `e219222`;
documentação/evidências em commit seguinte. Próxima ação: revisão humana
das quatro áreas de Ofícios. Ressalvas: CSP/abort demonstrados na referência,
orçamentos anteriores de performance e leitura da folha A4 no celular.
Sem push, merge ou deploy. Termos permanece suspenso.

Histórico funcional anterior preservado abaixo.

| Campo | Valor |
|---|---|
| Módulo | Viagens → **Ofícios** |
| Página | **Fechamento do mesmo bloco H/tempo/Resumo/Documentos/Folha**; nenhuma nova página |
| Agente responsável | Codex principal; paridade/recuperação e QA como revisões delimitadas |
| Análise do legado | **concluída** — `parity/oficios-folha.md`, `parity/oficios-resumo.md`, `parity/oficios-documentos.md` |
| Implementação | Incorporada em `viagens/reconstrucao`: `feb35e2` domínio RS02 + `bea84e3` consumidores/guards/carga/foco. D13/D16 confirmadas e implementadas. CSS separado rejeitado/restaurado |
| Testes executados | Integral final 2187 verdes/zero falhas/7 avisos, 40min21s, todos os checks verdes. Focused/HTTP/Baixar/7 Resumo+guard, teclado/capturas360/1440 e performance por blocos no pacote final |
| Problemas encontrados | Primeiro integral 2184 verdes/3 falhas: codificação Windows (2) e contrato de tag (1), três focados posteriores verdes. Reuso do banco esvaziado interrompido; logs preservados |
| Problemas resolvidos | Bloco H/tempo/correções existentes Resumo/Documentos/Folha fechado: aprovado com ressalvas. Nenhum bloqueante funcional comprovado restante nas suítes executadas |
| Pendências | Performance anterior ao candidato, CSP intermitente sem origem confirmada, paridade editorial PDF/A/DOCX e incidente anterior de mídia explicitados; não implicam avanço automático |
| Próximo passo | Entregar/avaliar pacote final. Termos de Autorização suspenso; nenhuma nova página iniciada |

## Gate delimitado — 07/10/2026

Pacote final: `qa/fechamento-gate-final-2026-10-07.md`; histórico da
sequência/tests/falhas/correções em `../quality/fechamento-gate-2026-10-07.md`.
Main preservada; fontes validadas incorporadas no original depois da integral
verde. Manifesto43/zero divergências e árvores completas897fontes idênticas.
Decisão final aprovado com ressalvas, sem soma artificial de rodadas, sem dizer
CI global verde: performance continua3falhas. Histórico anterior abaixo permanece
datado e é substituído por este fechamento no escopo autorizado.

## Fechamento solicitado — 07/10/2026 19:09

Status de entrega H: reprovado no gate final; funcionais focados verdes, integral
não reexecutado após correção. D16 implementada/validada/commitada. Resumo/Docs/
Folha candidatos em validação. Relatório final: qa/fechamento-bloco-2026-10-07.md.
User pediu entregar pacote antes de avançar, sem novas frentes. Worktree HEAD
e5e48cc (domínio RS02 commitado), integração/JS/CSS/testes pendentes preservados.
HTTP95passaram/1fixture corrigida não reexecutada; Baixar6pass/5fail/3errors;
baseline original1pass/2fail. Últimos fixes/7E2EResumo/11Baixar/leitura pendentes.
Nenhum teste mutável ativo. Preview8010original/8011candidato próprios mantidos.
Próxima ação: fechar este bloco, verificar integral, só depois próxima página.

## Continuidade — 07/10/2026 18:50

- Original `viagens/reconstrucao`/HEAD`d5663f2`, candidatos somente no worktree
  `viagens-tempo-legado`. Main preservada e sem push. D16 já implementada/validada.
- CSS: @import retirado em44consumidores; dois links static canônicos mantêm
  regras minificadas idênticas. Filtros fechados não carregam seletores antes de
  abrir. Calendário de período corrigido: foco volta à célula após primeiro Enter.
- Cadastro: última rodada2passaram/47,63s360/1440; anterior8passaram/2falhas
  de auditoria inicial/121s. Relatórios e falhas preservados em
  `docs/quality/qa-cadastro-adiado.md`, novas evidências duráveis. Metodologia axe
  modal confirmada pelo Chromium AX; falta cobertura teclado/cadastro sobreposto.
- RS02 conectado a listas, assinatura, pacotes, DOCX e Resumo: correntes máximas
  separadas do histórico, sem usar v1pronto quando v2falhou/gera. Cópia preserva
  RS01snapshotmesmo sem PDF. Hook root interrompe polling fechado/saindo, aborta
  em voo e preserva foco do rodapé. Retry histórico foi retirado18:49:44 e novo
  caso precisa executar depois da collection atual.
- Root reexecutou81testes puros/0,27s e mypy303arquivos verde. Suíte HTTP ativa
  sessão50924/`var/rs02-cadastros-css-http.log`, ownLAB `pcpr_lab_rs02`/gw0/gw1.
  BrowserBaixar+assinados ativo92264/`var/baixar-assinados-carga-browser.log`, banco
  distinto `pcpr_lab_ui_isolado`. Sem medir desempenho durante as suítes.
- Baixar candidato carrega no primeiro uso, cancela GET e descarta respostas
  antigas; congelado18:45:53, ADR0028.11casos novos e fluxos existentes em teste.
- Preview próprio8010reiniciado18:25:34, sessão6071, emd5663f2. OwnDEMO/mídia
  isolados;8000do usuário preservado. Novo candidato ainda não está nesse preview.
- Próxima ação: concluir HTTP/browser, focused retry novo, regressões dos44
  consumidores e polling/cópia, medidas frescas, capturas5larguras e verificar.sh.
  LoteH ainda não integralmente aprovado: última suíte1falha corrigida/1897passaram.

## Continuidade — 07/10/2026 18:23

- Checkout original `viagens/reconstrucao` em `d5663f2`, após incorporar por
  fast-forward os commits locais `39355b1` (barra), `c3ae40a` (editor adiado) e
  `d5663f2` (cópia eProtocolo). Main preservada, sem push. Worktree com candidatos
  ainda não incorporados; alterações locais de documentação/coletor preservadas.
- D16 implementada: domínio 68, integração total 101 testes verdes; navegador da
  rota final 2 passaram em 29,70 s, capturas/valores manuais conferidos. Evidência
  `docs/quality/qa-rota-legado-layout.md`. Preserva documentos e trechos existentes.
- Verificador integral anterior terminou: **1 falhou/1897 passaram em 2935,54 s**.
  Falha no cache de assinantes corrigida em `d8cbb97`; **53 testes posteriores
  passaram em 383,60 s**. Isso não torna a suíte integral verde sem nova execução.
- RS-01: HTTP 25 passaram/1 falha de fixture corrigida e caso reexecutado verde;
  browser conjunto 11 passaram/3 falhas, Clipboard 2 casos corrigidos/verdes;
  barra dinâmica depois 1 verde/32,25 s; resumo fallback/capturas 1 verde/32,38 s.
  Cinco casos de carga adiada do editor passaram. Evidências duráveis e limitações
  em `docs/quality/oficios-eprotocolo-integracao.md` e `qa-carga-editores.md`.
- Medição fresca sem erro de coleta: **3 falharam em 62,47 s**,
  `var/viagens-perf-lazy-eprotocolo.log`. Folha 52→36 requisições, CSS161,8→139,5 KB;
  HTML139,9, JS155,3/gzip54,7, SQL26/DB106,8 ms ainda excedem budgets.
  Lista CSS149,5/28 req, resumo149,5/29 req. Nenhum teto alterado.
- Worktree: ADR0026 recursos de filtros + ADR0027 cadastros ao abrir. HTTP do
  cadastro 4 passaram/1 falha (teste esperava input quando widget vazio usa
  data-nome), corrigido. **11 casos HTTP/browser agora em execução**, sessão71683,
  log `var/cadastro-filtros-adiados-browser.log`; sem outro teste mutável concorrente.
- RS-02: domínio/adaptador revistos e **81 testes puros reexecutados verdes em
  0,13 s**. Integração de menus/listas/anexação/pacotes/DOCX em andamento no
  worktree; Resumo/rodapé/polling ainda precisam ser alinhados pelo principal.
- Preview próprio :8010 ainda necessita reinício para carregar as views novas;
  banco `pcpr_lab_demo`/55432 e mídia isolados. :8000 do usuário preservado.

## Checkpoint de execução — 07/10/2026 16:35

- HEAD `b0829d6`, seis commits locais na branch `viagens/reconstrucao`; main
  preservada em `8d1d77e`, nenhum push/merge. O checkpoint anterior abaixo é histórico.
- Chromium: **30 passaram em 384,93 s**, incluindo jornada de emissão, motorista,
  retry com PDF real, calendário, teclado, duas abas, cinco larguras e cadastro de
  servidor afetado pela redução de consultas. Log `var/lote-h-browser-checkpoint.log`.
- Capturas finais renovadas: 30 PNGs antes/depois/comparação em `evidencias/lote-h/`.
  Medições de servidor e limites metodológicos constam em `qa/oficios-lote-h.md`.
- Axe da folha: passou. Desempenho de lista, resumo e folha: três falhas,
  `var/lote-h-perf-axe.log`. Coletor de respostas também tem erro de ciclo de vida;
  isso não explica automaticamente os excessos medidos. Budgets mantidos.
- `scripts/verificar.sh` em execução, dois workers, banco independente
  `pcpr_lab_verificar`; log `var/lote-h-verificar-final.log`. Lint, 16 fronteiras,
  mypy (299 arquivos), bandit, migrações e tipos JS passaram; testes ainda pendentes.
- Produto congelado durante essa execução. RS-01 tem domínio puro testado e
  especificação em revisão, sem adaptador ou UI. Preview próprio continua em :8010
  com banco e mídia isolados. Incidente anterior de mídia descrito no relatório QA.

## Continuidade — 07/10/2026 17:05

- HEAD ativo `36d4acd`: domínio de tempos da referência e ADR 0024 commitados.
  Domínio: 68 testes puros reexecutados pelo principal; mypy e ruff verdes.
  D16 respondida por Tiago: “pode copiar a regra do legado”. Sem nova pergunta.
- Verificação H continua no checkout original, produto ainda em `b0829d6`:
  `var/lote-h-verificar-final.log`, 41%, dois workers, sem falha registrada até aqui.
  Arquivos novos de domínio/adaptador não estavam na coleta dessa execução.
- Worktree gerenciado isolado, base `36d4acd`:
  `C:/Users/tiago/.codex/worktrees/viagens-tempo-legado/pcpr-gestao-next`.
  Integração de tempos/cache/migração 0050 e carga de miniaturas foram implementadas
  nele, **ainda sem commit ou incorporação** ao checkout original.
- Banco LAB próprio para esse checkout: `pcpr_lab_rotas` na porta 55432.
  **101 testes de domínio/integração passaram em 98,08 s**; cache antigo, provedor,
  API, chegada, degrau de diárias e preservação de snapshot. Migrações sem diferença,
  ruff e mypy dos dois arquivos de produto verdes.
- Testes `test_editor_carga.py` + `test_editor.py` em execução nesse banco.
  Não iniciar teste concorrente mutável no mesmo banco. Logs continuam no `var/`
  do checkout original. Tipo JS já passou; navegador e nova medição pendentes.
- Coletor de desempenho corrigido e executado: três reprovações de orçamento,
  `var/lote-h-perf-medicao.log`, sem erro de coleta. CPU/RAM disputados pela suíte
  geral: não inferir latência estável dessa rodada. CSS/bytes/contagens detalhados.
- Adaptador RS-01 novo no checkout original, não conectado a views/templates:
  `gestao/viagens/eprotocolo.py`, 28 testes com mocks reexecutados, ruff/mypy verdes.
  Medição real de consultas e browser dependem da integração. Não incluído na suíte H.

## Checkpoint de execução — 07/10/2026 15:38

- Branch `viagens/reconstrucao`, base `8d1d77efb1e5785553fd74b9906bddc6369207c9`.
  Main e remoto permaneceram nessa base nas consultas realizadas após a resposta do usuário.
  Alterações H ainda não commitadas; nenhum push/merge.
- Relatório detalhado e incidente de mídia: `qa/oficios-lote-h.md`.
  Regra vigente: `../product/oficios-lote-h.md`; ADR 0023 para falhas da outbox.
- LAB independente: PostgreSQL local `127.0.0.1:55432`, cluster em
  `%LOCALAPPDATA%/pcpr-codex-lab/pgdata`. Bancos de teste separados.
- Em execução: verificação completa (4 workers, `var/lote-h-verificar.log`, 91%,
  quatro falhas com diagnóstico final pendente); rodada focada + e2e da folha
  (`var/lote-h-regressao-final.log`). Novo teste de retry por teclado/axe ainda não executado.
- Capturas ANTES finais: reprodução em arquivo isolado do commit-base, 1 teste passou
  em 114,44 s; relógio fixo, cinco larguras. Capturas DEPOIS finais e comparações pendentes.
- Preview próprio: `http://127.0.0.1:8010/viagens/oficios/`, 258 ofícios fictícios.
  Mídia isolada em `%LOCALAPPDATA%/pcpr-codex-lab/preview-media`, wrapper local
  `var/preview_lote_h.py`; worker próprio interrompido após gerar o último ofício.
- RS investigado somente por leitura: eProtocolo, reabrir, histórico, versões documentais,
  atualização do rodapé e metadados ainda têm lacunas. Não aprovado nem implementado.

## Log

### Continuidade ativa — 07/10/2026 17:55

- Checkout original na branch `viagens/reconstrucao`, HEAD `d8cbb97`:
  regra do legado incorporada em `df93e90`; renovação dos assinantes em `d8cbb97`.
  Fetch às 17:47 ainda mostrou `origin/main` em `8d1d77e`; nenhum push/merge na main.
- Regra de tempo: 101 testes de domínio/integração e 2 Chromium em 29,70 s;
  valores completos medidos nas cinco larguras; 10 capturas duráveis antes/depois
  do ajuste de duração. Um 422 intermitente anterior foi preservado, sem causa
  demonstrada. Data de saída corta o ano em 360: achado separado ainda aberto.
- Último `scripts/verificar.sh` H: 1 falha/1.897 aprovados em 2.935,54 s,
  `var/lote-h-verificar-final.log`. Falha dos assinantes corrigida; 2 testes focados
  passaram, depois **53 serviços/orçamentos passaram em 383,60 s**. Nova execução
  integral ainda necessária; não declarar script verde.
- Worktree gerenciado `viagens-tempo-legado` agora base `d8cbb97`, alterações ainda
  não incorporadas: eProtocolo na folha/resumo/revisão/OOB, carga adiada do editor,
  correções de fallback sem IntersectionObserver e coletor de desempenho.
- HTTP eProtocolo: 25 aprovados/1 falha de fixture em 249,21 s; cenário corrigido
  com nomes únicos passou isolado em 9,98 s. Projeção exige listas explícitas e
  zero SQL; budgets da folha/revisão32 e resumo20/15 passaram. Mypy2/ruff/JS verdes.
- Browser desses dois lotes: 14 casos em execução, banco LAB `pcpr_lab_rotas`,
  `var/eprotocolo-editor-navegador.log`. Clipboard falhou em 360/1440; diagnóstico
  final pendente. Fallback Ctrl+C, autosave, foco OOB e 5 casos de carga do editor
  passaram até aqui. Não começar outra suíte mutável nesse banco até terminar.
- Preview próprio reiniciado, sessão31367, `http://127.0.0.1:8010/viagens/oficios/`,
  saúde200; migração0050 aplicada apenas ao LAB DEMO na porta55432. Mídia isolada,
  sem nova semeadura. Servidor do usuário em :8000 não foi reiniciado pelo agente.
- Próximos agentes: `paridade_lote_h` prepara domínio puro RS02 (versões, sem
  alterar arquivos congelados); `qa_lote_h` investiga desempenho por leitura e
  documenta propostas. Nenhum desses resultados ainda comprova UI integrada.

- 2026-10-06 — ambiente montado (NOVO :8000 PREVIEW semeado; LEGADO :8001 do backup de 05/10). Branch `viagens/reconstrucao` criado.
- 2026-10-06 — Agente 1 entregou paridade da lista e inventário de Ofícios; inventário de Viagens (288 itens) em `inventory.md`; Agente 2 entregou identidade de referência, catálogo de componentes e diagnóstico (P1–P14). Orquestrador aprovou o plano D1–D11.
- 2026-10-07 — Lote 1 implementado (19 commits), QA reprovou 2× (B1/B2 regressões em outras listas; RB1 target-size a 768), Designer corrigiu na origem, QA APROVOU (Re-QA 2, `34d8d1d`). Decisão: motorista primeiro na equipe com "(motorista)" visível.
- 2026-10-07 — Lote 2 implementado: abas temporais + filtro Documento, gaveta com fichas, busca (placa, destino ≠ sede, unaccent), vazios/erro, `voltar` vivo, contagens, XLSX. Relatório em `visual/oficios-lista-lote2.md`.
- 2026-10-07 — Lote 2: abas temporais com regra do legado (`dominio/recorte.py`), filtro Documento, contadores do recorte, gaveta/folha modal + fichas, Ano, busca placa/destino/acentos, erro HTMX. QA reprovou 1× (folha do celular cortava calendário; modal falso), corrigido, APROVADO (`651d666`).
- 2026-10-07 — Lote 3: ⋮ canônico com itens descritos (lista, painel e resumo; itens sob demanda; folha no celular; véu), "Mais" da barra, página Numeração (domínio explica o próximo; histórico da trilha), docs do DS, 3 e2e do main verdes, menores M5/M8/M-R1/M-R2/M-R4. Relatório em `visual/oficios-lista-lote3.md`.
- 2026-10-07 — Lote 3 (menu ⋮ canônico com grupos, carga sob demanda, 401 em pedidos assíncronos sem sessão, barra "Mais") aprovado; Numeração revertida por decisão anterior do dono (D9 revogada). **Lista de ofícios CONCLUÍDA.** Paridade de folha/resumo/documentos entregue; plano D12–D18.
