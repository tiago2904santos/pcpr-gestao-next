# Cadastro de Ofício — Roteiro até ações finais

Pedido do usuário: reconstruir apenas a metade inferior, preservando a direção
do Header, Identificação e Equipe/transporte. Base Git `671c3a9`; as mudanças
anteriores de transporte e os cartões clicáveis/volante do usuário são preservados.
Contrato em `docs/product/oficios-cadastro-inferior.md`, composição no ADR 0031.

## Estado do trabalho

**Fechamento técnico: aprovado com ressalvas.** Blocos A–F recuperados,
implementados e revistos; transporte em cartões e ajustes do usuário preservados.
Aprovação estética permanece com o usuário. O gate integral desta fonte passou;
o gate anterior é usado somente para comparar avisos preexistentes.
PREVIEW local 8016, banco `pcpr_lab_demo` e mídia LAB separados do DEV; nenhuma
semeadura, recuperação de PDF, alteração de histórico ou dado institucional.

## Iterações e evidências

- A: seletor de roteiro contextual, destinos numerados e mapa integrado. Segunda
  passada retirou espaço duplo dos rótulos, marcador repetido e desequilíbrio do
  mapa. 73 testes focados passaram; dez estados finais sem axe/console/overflow.
- B: trechos em sequência com durações agrupadas e chegada como resultado;
  Diárias compactas. Segunda passada retirou a fórmula repetida por trecho.
  Cinco testes de gravação/chegada passaram; dez estados finais sem falhas visuais
  automatizadas. Primeiro cenário falhou por retorno anterior à saída: dados do
  teste corrigidos, regra mantida.
- C: contexto do prazo separado da escrita, seletor compacto, rótulos legíveis
  e área de texto proporcional. Cinco larguras sem falhas axe/console/overflow;
  quatro testes passaram, incluindo texto preservado mesmo dispensado.
- D: conferência antes da cópia. Primeira coluna criou um vão; segunda versão
  usa faixa horizontal no desktop e contexto antes dos dados no celular. Dez
  estados sem falhas axe/console/overflow; cinco E2E de cópia/atualização/foco
  passaram. Mantido o componente copiável do Resumo.
- E: editor com cabeçalho grafite, modos/ações separados e grupos de ferramentas
  identificados. Segunda passada retirou moldura extra e corrigiu a distribuição
  dos botões. Teste encontrou contraste ruim no hover de Texto selecionado:
  corrigido. Cobertura mobile também revelou expectativa limitada a botões,
  ignorando o summary de Formatar texto: teste ampliado para esse controle e
  sua abertura por teclado. Troca da minuta revelou clone de `pc-select` com
  `data-pronto` mas sem referências/eventos: inicialização corrigida e teste de
  reconexão/cópia incluído. Bateria consolidada: **80 passaram em 323,85s**,
  incluindo 68 tokens, seis casos de editor/PDF, cinco de carga e um de clone.
- F: histórico com data completa e autoria; barra final estática com status
  visível. Segunda passada colocou autoria em coluna no desktop, reduzindo
  altura sem perder a leitura em duas linhas no celular. Dez estados finais
  nas cinco larguras sem violações axe, erros de console ou overflow.

Capturas reais em `../evidencias/oficios-cadastro-inferior/`: `antes/` contém
95 imagens dos estados preenchido, obrigatório/pronto e pendente, nas cinco
larguras. `iteracao-a1/a2`, `b1/b2`, `c1/c2`, `d1/d2`, `e1/e2/e3` preservam a
  crítica e correção. F em `iteracao-f1-revisada/f2`; primeira captura F1 teve
  ancoragem afetada pelo carregamento tardio do editor e não foi usada na crítica.
  JSON `qa-bloco-*.json` contém axe, console e overflow.
Não são imagens geradas nem montagens usadas como screenshot da aplicação.

## Falha de clique demonstrada

Diagnóstico separado confirmou deslocamento de cerca de 53,5 px entre pointerdown
e focusin do cartão da equipe no mobile. O aviso de salvamento acima do cadastro
recebe `barra-acoes__status--sujo`, cujo estilo mobile global é absoluto; isso
retira a altura e margem do fluxo, movendo o alvo antes do pointerup. O estilo e
o aviso superior existem na base; a falha foi reproduzida no fluxo atual. Não
atribuir a ela aprovação com base apenas no teste por teclado. Corrigida no bloco
F mantendo o aviso no fluxo da barra final. **Oito E2E passaram em 364,55s**:
clique em 360/768/1440, teclado em 390/1024, fallback sem JS e escolha automática
com movimento normal/reduzido. Cartão/volante do usuário preservados.

## Preservação da data escolhida

Campo oculto `data_oficio_manual=""` residual podia limpar a flag manual ao
editar outro dado. Dois casos HTTP da Folha/autosave falharam antes (115,39s);
campo removido, sem mudar a regra de `forms.clean`. **15 testes do Lote H passaram
em 387,76s**, incluindo os dois novos casos e emissão/data/incompleta/retry/permissões.
Um aviso de teardown de banco com duas conexões do teste concorrente permanece;
não é falha de asserção nem prova de limpeza concluída.

## UI Lab

Estados contextuais e prontidão demonstrados com dados sintéticos. O primeiro
axe encontrou alvo do índice lateral parcialmente coberto pelo cabeçalho no
fim da vitrine (1024/1440), fora dos componentes novos; problema semelhante já
registrado no diagnóstico anterior de transporte. Limite de altura/rolagem do
índice corrigido somente em `ui-lab.css`. Reteste integral da página nas cinco
larguras: **zero violações, console ou overflow**, sem excluir regras ou nós.
Logs brutos antes da correção mantidos em `qa-ui-lab-antes-indice.json`.

## Fluxos e digitação durante o carregamento

Bateria final inicial: **23 passaram, uma falha** na busca de servidor da criação
(553,83s). Diagnóstico: jornada normal completa passou; teste com import retido
falhou depois de digitar antes da inicialização (133,01s, um passou/um falhou).
O input é HTML nativo e já podia receber texto, mas o evento ocorrido antes da
conexão não era retomado. A inicialização da base `671c3a9` também não retoma essa
consulta; fragilidade preexistente demonstrada no fluxo atual, corrigida por
bloquear a jornada essencial. `pc-combobox` retoma texto focado sem apagar seleção
com identificação existente. Teste real de atraso, escolha e gravação incluído.
Criação/emissão/PDF, escolha automática normal/reduzida e UI Lab passaram no
reteste (quatro casos verdes). O novo caso precisou aguardar o POST antes de
conferir o banco e localizar o cartão específico entre dois servidores; falhas
dessas expectativas mantidas nos logs. Caso corrigido: **um passou em 62,35s**, com
consulta, cartão e persistência comprovados. A jornada completa também passou
no último reteste distinto (78,22s, um passou/uma expectativa de seletor falhou).
Nenhuma espera fixa foi adicionada para esconder a consulta perdida.

Matriz final: **20 estados, zero violações axe, erros de console ou overflow**,
com preenchido, obrigatório/pronto, pendente e conflito/menu nas cinco larguras.
O conflito visual foi simulado apenas na resposta do navegador, sem POST no
banco; a bateria E2E distinta testa conflito real entre abas e gravação no banco.
Menu abriu com Enter, navegou com seta e devolveu foco com Escape. Primeira
expectativa do helper esperava o primeiro item depois de seta para baixo; corrigida
para o segundo, preservando a navegação existente. Nenhum ajuste de menu necessário.

95 pares reais da metade inferior em `evidencias/oficios-cadastro-inferior/index.html`.
Validação da galeria confirmou arquivos, larguras e dimensões originais em todos
os pares, sem erro JS. Dez pares de transporte recapturados na prévia 8016 após
preservar os ajustes do usuário; 15 estados de transporte/UI Lab sem falhas.

## Autocrítica e limites visuais

- A primeira organização do mapa tinha desequilíbrio e controles com respiro
  duplo; corrigidos. UFs antes truncadas agora aparecem integralmente.
- A primeira prontidão em coluna criava um vão; conferência horizontal resolveu
  o desktop, com decisão antes da cópia no celular.
- O editor tinha camada e ferramentas excessivamente fragmentadas; estação plana,
  ferramentas nomeadas e modo selecionado com contraste corrigiram os pontos.
- O primeiro histórico repetia autoria abaixo do evento no desktop e usava altura
  demais; autoria em coluna e sequência mais compacta na segunda versão.
- A prévia HTML do documento mantém a apresentação oficial preexistente. Uma tabela
  larga pode ficar parcialmente cortada dentro do iframe no celular; PDF e ferramentas
  foram testados, mas isso não é declarado resolvido. Nenhuma alteração de conteúdo
  ou formato oficial feita para esconder o limite.
- O mapa mostra o aviso verdadeiro do fallback de estimativa quando o provedor não
  responde. Não retirar aviso para melhorar a captura nem apresentar cálculo como exato.
- A composição foi revista bloco a bloco. Aprovação estética continua com o usuário.

## Performance e classificação

Comparação de templates da base `671c3a9` com a candidata, mesmo banco/usuário
sintético, três GET por estado e POST da equipe com rollback no LAB:

- Consultas GET preenchido/justificativa/pendente: **24/25/21 antes e depois**.
- POST adicionar servidor: **28 antes e depois**, acima do orçamento 25. E2E com
  outro cenário registrou 29. Problema preexistente / dívida técnica; nenhuma
  nova consulta ou frente de otimização foi introduzida.
- HTML comprimido cresceu aproximadamente 0,38–0,54 KB conforme o estado.
- CSS gzip: **+3.598 bytes**, dos quais 41 só na vitrine do UI Lab.
- JS gzip: **+1.516 bytes**. Sem biblioteca nova ou endpoint adicional.
- Amostras locais de latência variam com suítes concorrentes; não são benchmark
  de produção, SLA ou prova absoluta de ausência de regressão de tempo.
- Carga adiada do editor/miniaturas, fallback e reposição durante import passaram
  na bateria E. Não antecipar editor ou PDF por motivo estético.

Fonte completa em `custo-final.json`. Regressões demonstradas nesta rodada
(contraste no hover selecionado, clone do seletor) corrigidas e retestadas.
Fragilidades preexistentes que bloquearam o fluxo (clique deslocado, busca durante
import) foram corrigidas. Tabela oficial móvel, aviso SQL e higiene de teardown
permanecem explicitamente delimitados.

## Gate integral e registro final

Commit local de código, testes e evidências: **`5140533` — Refina preparação do
ofício e transporte em cartões**, branch `codex/oficios-transporte-cartoes`.
O checkpoint posterior altera apenas o registro documental, preservando as 47
fontes/testes validadas. Nenhum push, merge ou deploy.

Executado o `scripts/verificar.sh` real, sem alteração do script ou remoção de
checks, em banco e mídia LAB isolados: **2.281 passaram, zero falhas, nove avisos,
3.138,31s (52min18s), exit 0 e `✔ tudo verde`**. Ruff, 16 contratos de arquitetura,
mypy, Bandit, migrações e tipos JS passaram. O script não inclui navegador;
as baterias de navegador/axe descritas acima são a validação complementar.

Os nove avisos são seis ocorrências de HarfBuzz-Subset/WeasyPrint e três de
`PageObject.replace_contents()`/pypdf. As duas mensagens e o mesmo total constam
no log anterior de componentes (2.251 testes); o teste que primeiro emite a
mensagem pode variar com a distribuição dos workers. Classificação: avisos de
biblioteca preexistentes, não bloqueantes. Os avisos de interpretação de comentários
do Bandit também aparecem naquele log, sem falha no check.

Fonte congelada em 09/10/2026 às 16:05:23 UTC: **47 arquivos de código/testes
conferidos novamente depois do gate, sem divergência**. Código e documentação
passaram `git diff --cached --check`, excluindo exclusivamente a pasta dos logs
brutos: ela preserva espaços finais produzidos por pytest/lint-imports. A primeira
conferência geral do índice apontou esses espaços; nenhum log foi reescrito para
esconder a saída original. Não se fez alteração de código durante o gate.

- [Log integral bruto](../evidencias/oficios-cadastro-inferior/logs/cadastro-inferior-verificar-integral.log).
- [Registro do gate e hashes](../evidencias/oficios-cadastro-inferior/gate-integral.json).
- [Baterias focadas, incluindo falhas e retestes](../evidencias/oficios-cadastro-inferior/baterias-focadas.json).
- [Galeria com 95 pares originais](../evidencias/oficios-cadastro-inferior/index.html).
- [Matriz final da Folha](../evidencias/oficios-cadastro-inferior/qa-final.json) e [UI Lab](../evidencias/oficios-cadastro-inferior/qa-ui-lab.json).
- [Medições comparadas](../evidencias/oficios-cadastro-inferior/custo-final.json).

## Componentes e arquivos principais

Componentes novos compartilhados em `templates/componentes/`: `selecao_roteiro`,
`formulario_contextual`, `prontidao_documental`, `modos_documento`,
`estado_salvamento` e `recurso_selecionado`. Variantes de `conferencia_valores`
e `rodape_documento`; apresentação operacional do itinerário, trechos e editor.
Todas as variantes são demonstradas/documentadas no UI Lab e no Design System.

Composição em `gestao/viagens/templates/viagens/oficios/editar.html`; parciais
de justificativa, motorista externo, diárias, editor e histórico. Estilos
compartilhados em `static/css/components.css`, com ajustes necessários nas folhas
existentes. Comportamentos em `combobox.js`, `seletor.js`, `transporte.js` e
`cadastro-rapido.js`; testes HTTP/E2E protegem as correções demonstradas.
`_equipe.html`, `scripts/vendor_assets.py` e `static/icons/sprite.svg` incluem os
ajustes de cartão inteiro clicável/volante do próprio usuário, preservados.

## Limites e pendências

- Aprovação estética pertence ao usuário; capturas e autocrítica não a substituem.
- Nenhuma regressão funcional ou falha bloqueante conhecida na superfície validada.
  Permanecem a tabela oficial larga no iframe móvel, o orçamento SQL preexistente
  de adicionar equipe (28/25) e os avisos de biblioteca: limites não bloqueantes.
- Avisos de teardown nas baterias focadas foram preservados. A espera do POST foi
  incluída nos casos pertinentes; o caso final de carga retida passou sem aviso,
  mas não se afirma que toda conexão dos testes antigos foi limpa. Dívida técnica
  de higiene de testes; o gate integral terminou sem aviso de teardown.
- Incidente anterior dos dois PDFs DEV permanece separado, sem autorização de
  substituição/recuperação. Nenhuma ação nesse incidente foi feita nesta missão.
- Escopo fechado nesta candidata da Folha, na branch `codex/oficios-transporte-cartoes`.
  Registro local; sem push, merge ou deploy. Próxima ação é a revisão estética das
  imagens pelo usuário, sem abrir outro módulo.
