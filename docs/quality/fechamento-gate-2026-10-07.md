# Fechamento do mesmo bloco — retomada do gate

Autorização de Tiago em 07/10/2026 após o checkpoint 08d46c7: consolidar somente
os candidatos existentes, corrigir bloqueantes/regressões demonstradas, validar
antes de commitar. Sem nova página ou recurso; Termos permanece fora da etapa visual.

## Ordem e isolamento

1. Focused dos últimos ajustes: domínio/projeção, documentos correntes, leitura,
   resumo HTTP, cadastros adiados e CSS. Log `var/fechar-focused-ultimos.log`.
2. Baixar/assinados, incluindo contratos antigos com baseline documentado.
3. Sete E2E do Resumo.
4. Confirmar HTTP/E2E de identidade/pacote/foco/via inválida e consumidores compartilhados.
5. Decidir incorporação dos candidatos; testar na branch de entrega.
6. Verificar integral, capturas e crítica; commitar somente código validado.

Banco exclusivo PostgreSQL em 127.0.0.1:55432, usuário pcpr_lab. Focused usam
pcpr_lab_rs02 (testes test_*); navegador usa pcpr_lab_ui_isolado sequencialmente.
Mídia de testes em var/test-media do worktree, independente da mídia DEMO e DEV.
Nenhum seed/reset do preview. Checkout original viagens/reconstrucao em 08d46c7;
domínio RS02 em e5e48cc no worktree. Demais candidatos inicialmente sem commit.

## Evidência desta retomada

Primeira rodada: **156 passaram/1 falhou em 360,74 s**. Falha no cenário
cancelado do teste novo de leitura: criou Documento pronto sem sha256, violando
documento_pronto_tem_hash antes de chamar a aplicação. Plano mínimo: completar
hash sintético na fixture quando pronto e repetir esse caso, sem mudar produto
ou relaxar constraint/assert. Demais casos de leitura/identidade/pacote, HTTP
Resumo/cadastros, CSS, domínio/adaptador passaram. A fixture DOCX corrigida também
passou. Resultados anteriores permanecem históricos; não contam como uma suíte
verde do último código.

Reexecução da fixture: 1 falhou/22,16 s, agora por cancelar sem motivo obrigatório.
Fixture passa a usar services.cancelar com gestor e motivo sintético, respeitando
o fluxo e a constraint, sem alteração de produto. Logs anteriores preservados.

Último caso corrigido: **1 passou em 10,00 s**, log
`var/fechar-focused-fixture-final.log`. Portanto todos os cenários da primeira
rodada tiveram resultado verde, distribuídos entre a rodada e a reexecução;
a execução integral posterior confirmará o conjunto de uma vez.

Crítica independente somente de leitura: `critica-gate-final.md`. Confirma os
quatro guards corrigidos, sem demonstrar novo bloqueante de produto. Minificação
CSS contra d5663f2: mesmos 25.714 bytes/SHA256, 44 consumidores e nenhum @import.
O pedido CSS extra permanece custo da mudança a medir, sem aumentar teto.

Segunda etapa em execução: 11 casos novos Baixar + 2 contratos Baixar + 1
Assinados, sequencialmente. Os dois seletores antigos comprovadamente inválidos
no baseline serão corrigidos só após o resultado real, mantendo o contrato de
download/anexação e sem modificar a página visual. Emissão pendente deverá ser
preparada pelo worker real para o teste de download de snapshot.

Baixar/assinados: execução completou 14 casos (linha .....F...FFFFF); o coletor
temporário falhou ao imprimir U+22EE em stdout CP1252 e truncou detalhes/final.
Log parcial preservado, não reivindicado como resultado integral verde. Runner
passa a usar stdout UTF-8. Três falhas novas são problemas de teste demonstrados:
dois procuram Voltar inexistente (template real usa Fechar), repetição tenta um
clique encoberto no UI Lab. Plano mínimo: usar Fechar real e repetir/reabrir por
Enter, exigindo foco antes, mantendo assertions de dedupe/abort/resposta antiga;
sem force, alteração de UI, supressão de erros ou aumento de timeout.

Corridas corrigidas: **3 passaram em 30,31 s**, fechar/abortar/foco e segunda
resposta divergente verificados no navegador. Sete Resumo: **7 passaram em
75,05 s**, polling real, cópia/snapshot, históricos, reabertura, abort e foco
operável com/sem ID. Logs fechar-baixar-corridas e fechar-resumo-sete.

Plano da etapa 4: repetir pacotes/assinados/carimbo/conferência/leitura HTTP;
provar leitura pelo link corrente no navegador com via de outro dono e provar
recusa de pacote com justificativa esperada ausente. Atualizar contratos antigos
Baixar para comando atual e emissão pronta via worker. OS exige precisão: a UI
atual/d566 tem Anexar/Trocar no editor e não tem botão de remover. Teste deverá
verificar upload/recusa pelo editor e revogação por HTTP real, identificado assim
no nome; ausência da ação visual de remover permanece dívida preexistente, não
será ocultada por simulação/clique forçado nem corrigida abrindo nova frente OS.

Etapa 4 HTTP: **64 passaram em 103,39 s**, incluindo os 14 de leitura, pacotes,
assinados, carimbo e conferência. Browser conjunto: **13 passaram/2 falharam em
181,25 s**. Onze novos Baixar e dois downloads reais passaram. OS tenta rolar o
editor inicialmente sem altura: repetir pelo cartão Documento visível e exigir
barra visível, sem forçar clique. Guard de via cruzada passou bytes/hash, mas o
pacote incompleto revelou falha real de mensagem: fetch segue o redirect e
consome Django messages, então a navegação seguinte não exibe motivo. Plano
mínimo documentado no produto: 422 JSON no POST fetch e role=alert já existente;
preservar POST normal e testar ambos formatos, pacote sem download/versão nova.

Correção mínima do erro de pacote: views_pacotes/baixar.js, HTTP normal e fetch
PDF/DOCX **2 passaram em 13,61 s**; Ruff/TypeScript verdes. Browser via cruzada/
pacote e OS corrigida: **2 passaram em 23,12 s**. Recusa 422 visível no role=alert,
sem download/versão nova, escolhas preservadas; console só admite o 422 deliberado.
OS não era caixa rolável: CSS preexistente display:contents; teste agora rola o
cartão Documento e exige controle visível, sem alterar produto/CSS.

Antes de decidir incorporação, repetir os candidatos cadastro/filtros. Completar
somente a cobertura de teclado já pendente: Tab/ShiftTab nos modais e Escape/
retorno da origem nos cadastros sobrepostos Cargo/Unidade/Combustível; sem criar
recurso/cadastro novo além dos já previstos no teste.

Cadastro/filtros/teclado: **10 passaram em 101,77 s** (360/1440, axe, Tab/ShiftTab,
Escape em Cargo/Unidade/Combustível e retorno do foco; erro 503 e GET tardio).

Decisão de consolidação: selecionados os candidatos de domínio/projeção,
views/queries/policies/assinados/pacotes, parciais de Resumo, guards, CSS equivalente
e carregamento adiado de cadastro/filtros/Baixar. Nenhuma página/recurso novo.
A integração será feita após validar a árvore candidata nesta worktree; a pasta
principal permanece no checkpoint anterior durante os testes, evitando preview
com Python antigo e templates novos. Não entram orçamento relaxado, remoção
visual da via OS nem alterações visuais de Termos. Próxima validação: regressão
H/Folha/calendário e repetição conjunta dos contratos Baixar/Resumo atualizados.

Revisão visual encontrou regressão demonstrada do candidato CSS: divulgação
Dados para eProtocolo aparece com marcador nativo e ícone/texto empilhados nas
capturas corrente-pronta 360/1440. Antes, resumo-1440 do checkpoint RS01 usa
summary inline-flex. Regra .divulgacao > summary permanece apenas em formulario.css;
a lista candidata carrega só seletores.css. A equivalência da concatenação não
cobre consumidor que carrega apenas uma parte. Capturas reprovadas preservadas
em evidencias/gate-final/css-reprovado-resumo-*.png. Decisão: NÃO incorporar
separação CSS nem 44 substituições de links; restaurar pacotes/consumidores
anteriores após terminar a rodada ativa. Conservar opt-in JS dos filtros e sua
remoção local de preload; testar frio sem importar módulos, mas com CSS aprovado.
Guard de estilo da divulgação será incluído nos dois E2E de transição existentes.

Rodada consolidada anterior à retirada CSS: **54 passaram/1 falhou em 505,55 s**.
Baixar 14 e Resumo 8 passaram juntos, assim como H, calendário, emissão, motorista.
O único erro era o teste de abertura de registro exigir minuta do primeiro item:
HTML real era Ofício 04/2026 cancelado. Contrato RS02 proíbe esse fallback; o teste
agora abre o rascunho conhecido do cenário e conserva todos os checks de abertura,
conteúdo, Escape e permanência da lista, sem afrouxar regra ou criar minuta.

CSS retirado seletivamente (44 links restaurados; nenhum template de outros
contextos permanece alterado). Mantidos somente templates funcionais de Ofícios
mais bloco de preload local do arquétipo lista. Formulario.css voltou exatamente
à fonte d566; seletores.css e estilos_formulario.html excluídos. Guard visual nos
360/1440 E2E existentes exige summary de eProtocolo inline-flex. Frio de filtros
agora exige CSS aprovado e ausência dos módulos JS, não separação CSS rejeitada.

Após retirar CSS: **37 HTTP passaram em 189,52 s**, incluindo teste canônico dos
38 consumidores, Resumo e guards PDF/DOCX. CSS da candidata igual ao original
por SHA256 d5b6f955117bc5b3f40ca386c0b413c5bb982a1421d627d18dbab6b5a103eb1e.
Ruff completo verde. Segue navegador dos consumidores tocados e guard de estilo.

Revisão das capturas atuais H: falha-documentos-360/1440 mostram rótulo da falha,
retry e rodapé operáveis; divulgação eProtocolo com ícone/texto alinhados após
restaurar CSS. Folha 360 revisada também no recorte dos Documentos: pendências e
histórico cabem; miniaturas frias ainda não carregam conteúdo até visibilidade,
conforme contrato de carga que está sendo repetido. Não é prova de PDF editorial.

Navegador após CSS restaurado: **35 passaram/1 falhou em 417,10 s**. H capturas,
editor 9, Folha cópia/autosave, cadastro/filtros 10, Resumo 8, abertura rascunho e
rota legado 360/1440 passaram. Falha de fallback do Resumo ocorreu somente no
console: 6 recusas CSP de style inline; seleção/foco/axe/capturas passaram.
Baseline 08d46c7, mesmo teste sem mudanças: **1 passou em 21,65 s**. Não classificar
como preexistente só por ser aviso. Repetição candidata com diagnóstico CSP
(sourceFile/linha/diretiva), sem afrouxar policy, console ou orçamento.

Fallback CSP: baseline 1 verde/21,65 s; candidato 2 isolados verdes/13,37 e13,19 s.
Depois **5 cópia passaram juntos em 51,68 s**, listener só de leitura gravou
csp-resumo.json=[]; assert console vazio/policy/axe continuam estritos. Nenhuma
mudança de produto feita para eliminar/suprimir avisos. A falha anterior permanece
intermitente de validação, origem não confirmada; NÃO classificada preexistente.
Funções, seleção/foco e axe passaram inclusive na execução que teve avisos.
Sem extrapolar essa evidência para aprovação geral de acessibilidade ou CSP.

Performance equivalente, sequencial, mesmos 3 cenários/coletor/budgets, sem outra
suíte ativa: baseline08 **3 falhas/36,81 s**; candidato final **3 falhas/37,24 s**,
sem erros de coleta. Lista: req28→23, JS124,1→104,4 KB, CSS149,5→149,5 (teto140),
SQL12→12. Resumo: req29→24, JS126,5→106,8, CSS149,5 idêntico, SQL18→18.
Folha: HTML140,0→128,7 (120), JS155,3→151,2 (130), gzip54,7→52,8 (45),
req36→34 (32), SQL26→21 (25), DBmediano95,1→68,2 (80). CSS139,5/gzip28,6
idênticos. Todos os tempos de renderização/interação/CLS ficaram dentro dos tetos;
uma rodada não prova ganho de latência. Nenhum excesso novo nas métricas finais;
peso/requisições residuais reproduzidos antes e melhoraram ou ficaram iguais:
preexistentes/dívida técnica, não bloqueantes funcionais neste bloco autorizado.
A suíte de performance continua vermelha e não é chamada verde. Não elevar teto.

Árvore de produto congelada para scripts/verificar.sh integral. Bash real, sem
editar script/checks; dependências locais existentes via UV_PROJECT_ENVIRONMENT,
UV_NO_SYNC/UV_FROZEN, node_modules junction existente no workspace original.
Banco somente LAB127.0.0.1:55432/pcpr_lab_verificar; TEST MEDIA_ROOT isolado.
4 workers limitam o -n auto à capacidade local; sem outra suíte DB/navegador ativa.

Integral primeiro completo: **2184 passaram/3 falharam em2414,51s (40m14s)**.
Duas identidade/configuração: guard DEMO realmente levanta exceção e returncode1,
mas subprocesso herda PYTHONIOENCODING=utf8 do runner e captura text=True pela
codificação Windows CP1252: é viraÃ© no assertion. Config/testhelper idênticos ao
checkpoint; não alterar proteção/app nem retirar assertion. Reproduzir baseline
com mesmo runner, depois ativar PYTHONUTF8=1 em todos os processos da execução.
Terceira: TestGavetaEFichas usa regex que exige > imediatamente após id; atributo
opt-in data-controladores-adiados novo impede match embora gaveta esteja fechada,
provado pelos seis E2E. Corrigir assertion semântica: tag/class/id corretos,
sem atributo open, marca opt-in presente; preservar todos os checks de fichas.
Trata-se de regressão do contrato de teste atual, não defeito funcional de abrir
filtro. Após três focados verdes, repetir o script integral sem mudança de checks.
Log primeiro completo preservado em evidencias/gate-final/logs, não sobrescrito.

Três focados da integral passaram em 13,02 s. Identidade permanece estrita;
PYTHONUTF8=1 alinha a captura do subprocesso à saída UTF-8. O mesmo teste DEMO
falhou nos dois ambientes no baseline08 com a codificação anterior (6,04 s).
Antes da segunda integral, melhorar somente a evidência de filtros: a captura
360 registrou uma transição ainda em andamento. Aguardar as animações finitas
do calendário antes da captura, repetir os dois cenários completos e revisar
360/1440; nenhum CSS/comportamento da aplicação muda. Na integral final, um
plugin de diagnóstico somente imprime a falha no processo mestre assim que
ela ocorre; não muda seleção, assertions ou resultado.

Filtros/capturas finais: 2 passaram em 38,54 s; PNG 360/1440 revisados com
calendário assentado e foco visível, sem recorte/rolagem horizontal.
Segunda tentativa integral interrompida pelo responsável após diagnóstico:
--reuse-db recuperou os bancos gw0..gw3 esvaziados pelos testes transacionais da
primeira integral. Catálogos de migração (ProgramaSolicitante/HorarioAtendimento/
TipoEvento) ausentes já no início; mesma fonte não falhou nesses casos na primeira
integral completa. Nenhuma mudança nesses modelos/carga/migrações/conftest.
Processos próprios da árvore var/fechar_gate.py foram identificados e encerrados;
log parcial preservado como fechar-verificar-reuso-interrompido.log, sem contar
interrupção/worker encerrado como resultado integral ou defeito do produto.
Repetir Bash real com --create-db nos mesmos bancos TEST LAB próprios. A opção
recria esquema e carga inicial de migração; não afrouxa assertion nem semeia DEMO
ou DEV. PYTHONUTF8=1 permanece; código de produto/testes congelado.

Precisão da classificação de performance: baseline fresco equivalente08d46c7
comprova excesso anterior aos candidatos RS02/carga/guards, não prova sozinho
que todo excesso é anterior à reconstrução. RS01/H anteriores têm contribuição
acumulada não isolada; CSS comum também foi conferido por fonte antiga. Histórico
pré-RS01 já registrava excesso, mas seu coletor tinha erro de ciclo de vida e não
substitui a coleta fresca completa usada para comparação final. Não usar esse
histórico contaminado para inventar uma causa ou aprovar orçamento. Scripts/
verificar.sh tem SHA2567303c6f5157e2bb8790ba4305daee9714a5de5b8dac6b25baa3c8a6bd2580d02
idêntico ao checkout original; checks não editados.

## Resultado integral final — 07/10/2026 21:57

**2187 passaram, 0 falhas, 7 avisos em2421,27s (40m21s); saída0 e tudo verde.**
Ruff, 16 contratos, mypy303fontes, Bandit, migrações e tipos JS também passaram.
Os sete avisos são depreciações WeasyPrint/HarfBuzz-Subset e pypdf, nos mesmos
casos do primeiro integral; não convertidos em erros nem mascarados. Fonte
continua igual ao manifesto congelado43/sem divergências. Não houve alteração
de produto/testes durante o gate, nem retirada de assertion ou aumento de teto.
Performance continua3falhas, classificadas com baseline08 e ressalvas explícitas;
não declarar CI global/parate editorial completos verdes pelo script.
Log completo preservado em gate-final/logs/fechar-verificar-integral-final.log.

Preview candidato próprio8011 reiniciado com source/PYTHONPATH do worktree,
host127.0.0.1:55432/pcpr_lab_demo e mídia LocalAppData isolada, sem seed/reset.
Primeiro launcher esqueceu PYTHONPATH e recusou importar config; corrigido só
ambiente, nenhuma fonte alterada. HTTP de lista confirma200, opt-in final e
ausência de seletores.css. Fonte já validada pronta para commitar/incorporar;
guardas/foco/pacote/via e navegadores anteriores permanecem com logs explícitos.
