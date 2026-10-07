# Fechamento do bloco — 07/10/2026 19:09

## 1. Status final

**Lote H: REPROVADO no gate final de entrega.** Não é indicação de que motorista,
retry, data ou transporte continuam falhando: os cenários focados passaram. A
aprovação exige verificar.sh integral verde e navegador do último candidato;
nenhum dos dois está concluído. Não declarei aprovado com ressalvas para ocultar
uma exigência de entrega ainda pendente.

**Tempo/adicional do legado: implementado, commitado e validado.** D16 e D13
confirmadas pelo usuário. Não há nova decisão institucional necessária para elas.

**Resumo/Documentos/Folha: parcialmente validados; fechamento pendente.** RS01
cópia e carga do editor estão commitados. RS02 domínio/adaptador tem checkpoint
próprio; integração, cadastros, CSS e Baixar permanecem candidatos no worktree.
Últimos ajustes de leitura/pacote/foco e correções de fixture não foram reexecutados.
Nenhuma nova página/etapa visual será aberta antes deste fechamento.

## 2. Correções por área

- Motorista/autosave: preservação da escolha, gravação explícita/automática,
  conflito entre abas e recuperação auditada com simulação/idempotência.
- Geração/retry: falha registrada depois do rollback, status visível e repetição
  da mesma mensagem/versão, sem duplicar número/documento. Histórico substituído
  não oferece retry no candidato; teste novo ainda pendente.
- Data: hoje em Brasília na emissão, exceção manual preservada; revisão informa
  efeitos sobre tipo/justificativa. Limites de data e ano cobertos.
- Outro transporte: interpretação/persistência unificada entre formulário,
  domínio e documento; campos condicionais e comportamento sem JavaScript.
- Tempo/adicional: fórmula e arredondamento da referência; 240 min→45 adicionais,
  cache versionado, rotas novas calibradas e tempos manuais preservados. Não
  recalcular automaticamente trechos/documentos antigos. Campos de duração cabem
  integralmente em cards estreitos.
- Resumo/documentos: cópia de campos do eProtocolo por snapshot da emissão máxima;
  candidato separa corrente/histórico, evita promover v1 quando v2 falha/gera,
  assinatura pelo ID/tipo exatos, DOCX/pacote sem reconstruir minuta viva.
  Rodapé/cópia por OOB, polling fechado cancelado e via inválida não substitui
  original. Justificativa esperada ausente aparece indisponível no pacote.
- Performance/carga: editor/índice por visibilidade; cadastros por primeiro uso;
  filtros fechados sem seletores; CSS canônico separado sem import; Baixar por
  primeiro clique, cancelamento e descarte de resposta antiga. Últimos candidatos
  ainda não medidos. Não aumentei budgets.
- Acessibilidade/teclado: um tab stop na barra dinâmica, navegação Home/End/setas;
  calendário conserva foco após primeira data; foco OOB evita item oculto.
  Axe modal audita superfície operável, com página toda antes e Chromium AX
  comprovando fundo inerte. Falta cobertura transversal/último candidato.

## 3. Testes efetivamente executados

Resultados de checkpoints diferentes não devem ser somados como uma suíte verde.

- Unitários: tempos, 68; RS01, domínio 17 e adaptador 28; RS02, 81 puros,
  reexecução root em 0,27 s. Data/recuperação/outbox também na suíte focada/integral.
- Integração: tempo/cache, 101 verdes; assinantes/serviços/budgets, 53 verdes.
  HTTP RS01: 25 passaram/1 fixture corrigida e caso reexecutado verde.
  HTTP final candidato: **95 passaram/1 falhou em 712,97 s**. Falha usa objetivo
  inexistente; corrigida para motivo, ainda sem reexecução.
- Integral: **1897 passaram/1 falhou em 2935,54 s**. Cache de assinantes corrigido e
  53 posteriores verdes; verificar.sh não foi reexecutado integralmente.
- Navegador H: **30 passaram em 384,93 s**; rota final: 2 em 29,70 s;
  carga editor: 5 verdes; cópia Clipboard: 2; barra: 1 em 32,25 s;
  resumo fallback/capturas: 1 em 32,38 s, nos checkpoints posteriores.
- Filtros/cadastro: rodada com 8 verdes/2 falhas de auditoria inicial em 121 s;
  depois os 2 cadastros em 360/1440 passaram em 47,63 s. Seis filtros passaram,
  incluindo ordem/período/URL/teclado/cache. Não são 10 verdes numa execução final.
- Baixar/assinados candidato: **6 passaram/5 falharam/3 erros em 347,72 s**.
  Correção de sincronismo dos callbacks escrita, não reexecutada.
  Baseline original d566: **1 passou/2 falharam em 109,07 s**, reproduzindo seletores
  antigos de Termo e OS antes dos candidatos. Download do resumo passou no baseline,
  que admitia fallback vivo; novo teste precisa preparar emissão pronta pelo worker.
- Acessibilidade: axe sério/crítico passou nos cenários H, barra, cópia e cadastros
  assentados; não equivale a aprovação geral. Capturas/foco/teclado documentados.
- Performance d566: 3 falhas de orçamento/62,47 s, sem falha de coleta.
  Folha: 52→36 pedidos e CSS 161,8→139,5 KB; HTML 139,9 KB,
  JS 155,3/gzip 54,7 KB, SQL 26/DB 106,8 ms ainda excedem tetos.
  Lista/resumo: CSS 149,5 KB e 28/29 pedidos. Candidato novo não medido.
- Estáticos: Ruff completo verde; mypy 303 fontes verde antes dos últimos ajustes;
  TypeScript verde nos checkpoints; 16 fronteiras/bandit/migrações verdes no último
  verificar. Não validar automaticamente fonte posterior com resultado anterior.

## 4. Falhas e classificação

**Bloqueantes de aprovação:** ausência de verificador integral verde; navegador
reprovado do candidato; últimos guards de identidade/pacote/foco sem HTTP/E2E
posterior; sete novos E2E do Resumo e novos casos de leitura não executados.

**Regressões/defeitos abertos agora:** CSS import introduziu404/CSP na análise
axe, corrigido por dois links e casos posteriores verdes; guarda inicial de
filtro fechado corrigida; conexão RS02 deixava minuta indevida no menu e podia
focar item oculto, corrigidas mas validação real final pendente. Callbacks de
novos testes Baixar causaram dropout; correção ainda precisa executar.

**Preexistentes comprovados:** dois E2E antigos usam seletores removidos na UI
aprovada (Termo/OS), reproduzidos emd566. CSS comum acima do teto já existia e
não mudou entre8d1d77e e d566 (só CSS de itinerário mudou nesse intervalo).
Rota de leitura já admitia via vazia/vínculo cruzado; agora guardada no candidato.

**Dívida técnica / não bloqueantes funcionais comprovados:** peso/requisições
acima dos budgets não demonstram por si perda de dado ou falha de fluxo. O impacto
líquido do candidato ainda não foi medido. RS01 adiciona HTML/JS; não atribuir todo
excesso ao legado ou à mudança sem ensaio equivalente. CSS formulários acrescenta
1 pedido, mantendo regras minificadas idênticas. TTFB/FCP/LCP/CLS medidos ficaram
nos tetos nesse checkpoint; não são INP de usuários reais. Ano de data estreito,
rolagem/miniaturas e DOCX/PDF comparativo completo seguem pendências sem nova frente.
D17 (nova emissão sem retificar) continua não confirmada: comportamento preservado.

**Incidente de mídia já comunicado:** primeiro seed DEMO apontou por engano para
MEDIA_ROOT padrão e pode ter removido arquivos de DEV. Sem inventário anterior,
não há prova de ausência de perda. Isolamento corrigido, sem novo seed; backups
remanescentes preservados. Esta pendência não foi escondida no fechamento.

## 5. Commits locais

Na branch original viagens/reconstrucao:
057b154 data Brasília;608b903 rollback/falha outbox;45d20fd recuperação motorista;
44cf5fe isolamento dotenv teste;44b3186 H/motorista/consultas;
b0829d6 domínio eProtocolo;a100953 evidências H;
36d4acd fórmula legado;35a058e adaptador eProtocolo;df93e90 runtime/cache tempos;
d8cbb97 cache assinantes;39355b1 barra teclado;c3ae40a editor adiado;
d5663f2 cópia Folha/Resumo.

Worktree viagens-tempo-legado: **e5e48cc** domínio/adaptador RS02 com81 testes e
especificação. Nenhuma incorporação desse commit/candidatos ao checkout original.
Este relatório e o coletor ficam no commit final de checkpoint, identificado na entrega.
Sem push, sem alteração da main. Estado anterior d566 identifica código do baseline.

## 6. Arquivos principais

Commitados: gestao/viagens/{services.py,rotas.py},
dominio/{tempos_rota.py,emissao.py}, management/commands/recuperar_motoristas.py,
gestao/plataforma/outbox.py, models + migração 0050, templates de ofícios,
JS app/copiar/editores/editor-documento e CSS itinerario, testes/ADR/paridade.
No worktree: gestao/viagens/{documentos_versoes.py,dominio/documentos_versoes.py}.

Candidatos: viagens/{views.py,queries.py,policies.py,assinados.py,pacotes.py},
_resumo* e _menu_oficio.html, app/dialogo/cadastro-rapido/baixar/seletor-data,
formulario.css/seletores.css, estilos_formulario.html e44 consumidores;
HTTP/E2E novos. Manifesto de status preservado junto deste relatório. Não são
alterações commitadas/aprovadas apenas por estarem descritas aqui.

## 7. Evidências e preview

- Original docs/visual-agents/evidencias/lote-h: 30 PNG antes/depois/comparações,
  cinco larguras e quatro JSON; rota-legado: 10 PNG; eprotocolo-editor: 10 PNG.
- Worktree evidencias/cadastro-adiado: 2 PNG + 6 JSON de axe/Chromium AX. Capturas
 390/768/1024 e comparação equivalente desse candidato ainda pendentes.
- Logs completos preservados em var, original ou worktree: lote-h-verificar-final,
 lote-h-browser-checkpoint, rota-legado-integracao, rota-legado-layout-valores,
 assinantes-servicos-orcamentos, viagens-perf-lazy-eprotocolo,
 cadastro-filtros-foco-salvamento, cadastro-axe-estavel, rs02-cadastros-css-http,
 baixar-assinados-carga-browser e baixar-assinados-baseline-d566.
- PDF real sintético de testes copiado a fechamento-bloco/oficio-sintetico-testado.pdf;
 abertura estrutural confirmada. documento.txt registra páginas/origem/SHA256.
 Testes de retry validaram PDF e header/hash; DOCX snapshot testado com adaptador,
 paridade visual completa DOCX→PDF e PDF/A ainda não comprovadas.
- Preview original **http://127.0.0.1:8010** cód.d566; candidato não aprovado
 **http://127.0.0.1:8011**, mesmo DEMO sintético/mídia isolada.8000 preservado.
 Servidores próprios6071/91556 mantidos; nenhum teste mutável ativo ao fechar.

## 8. Próxima etapa recomendada

**Finalizar o mesmo bloco**, sem nova página visual: focused dos últimos ajustes,
fixture DOCX corrigida, 11 Baixar/7 Resumo, atualização dos seletores antigos com
prova de baseline e worker pronto, regressões compartilhadas, métricas equivalentes,
verificar.sh verde e commits somente dos candidatos validados. Depois auditoria
transversal de Ofícios; Termos de Autorização é a próxima página recomendada
somente após esse gate. Não há promessa de execução depois desta resposta.
