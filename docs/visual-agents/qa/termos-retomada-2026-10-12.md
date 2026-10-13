# TE01/TE02/TE03 — revalidação atual

Base34d1d57. Estado: EM VALIDAÇÃO, sem homologação visual do usuário.

A revisão independente encontrou um atalho quebrado após a migração: o menu
"Anexar ou abrir termo assinado" apontava para `#lista-documentos`, inexistente.
A folha usa `#previa`. Corrigido o href da Lista e ampliado o E2E de assinatura:
agora parte do menu real em360/768/1440, exige a seção no viewport, abre o diálogo,
anexa um PDF sintético, confere o download e o selo de assinatura na Lista.

Sem CSS/JS/dependência nova, alteração de SQL ou de documento oficial.
O editor e seus documentos permanecem separados da aparência da interface.

Evidências atuais: `termos-retomada-{lista,novo,folha}-{360,768,1440}.png`
e `termos-retomada-capturas.json` em evidencias/migracao-identidade-20261012.
São nove capturas reais, incluindo editor carregado, sem pageerror/overflow.
Referência antes/depois da composição preservada na galeria da migração.

Ruff e diffcheck verdes. Suíte `termos-retomada-final`, sessão4845, em execução:
identidade3larguras, paginação/consulta, assinatura3larguras, jornadas de Termos,
testes HTTP e contratos de anexação de Termo. Não marcar concluído até o resultado.

Limites preservados: orçamento SQL da Folha já excedido antes da migração,
avisos ambientais WeasyPrint/GLib e investigação histórica de teardown.
Os logs atuais são mantidos; não atribuir ganho de latência a um href corrigido.

## Resultado do atalho e pendência da Folha

Suíte4845 encerrada:52aprovados em275,74s,1warningHarfBuzz. Ruff verde.
Recaptura52625 encerrou9páginas+12documentos carregados após abrir o índice,
aguardar texto/fontes e percorrer as4folhas. Galeria653 validada.
Revisor confirmou correção do atalho. Entretanto, documento3/genérico em360
cortam texto institucional: .par nowrap no documento com overflow hidden no
iframe. Preexistente desde34f0d7d; não é regressão do href, mas permanece dentro
do escopo visual desta missão. TE02/TE03 NÃO concluídas enquanto não houver
leitura integral. Corrigir na apresentação do visualizador, preservando HTML/PDF
oficial e paginação. Não usar overflow global=false como prova do iframe.

## Continuação — candidato 9951a73

O corte foi tratado na apresentação compartilhada, com rolagem horizontal e
altura pelo conteúdo. Documentos oficiais preservados. QA detalhado e hashes:
`editor-folha-larga-2026-10-12.md` e `editor-folha-candidato.json`.
Revalidação final: seis testes aprovados; compatibilidade visual em quinze
capturas de Ofícios, Justificativa, OS e Planos. Sem declaração de gate global.
Revisão de fechamento TE01/02/03 em andamento: associar as evidências anteriores
ao código atual e registrar as exceções legítimas antes de atualizar a cobertura.

## Limpeza do controlador substituído

Removido de `termo.js` o listener antigo de `data-trocar-previa`, que substituía
`#lista-documentos` e `#previa` após buscar outra página HTML. Prova de substituição:
as views de novo/edição renderizam o mesmo `termos/editar.html`; seus ramos de
permissão/cancelamento não constroem esse link. O ramo documental usa os botões
`data-ir-pagina` e os itens `data-pagina`, inclusive o genérico. `editores.js`
registra esses botões, ativa e rola até a folha sem substituir seu DOM. Assim,
edições permanecem no editor existente. Os testes de folha larga navegam pelo
índice real em quatro larguras; a jornada de Termos valida autosave e PDF.
A busca em templates, Python e scripts não encontrou construção dinâmica do
atributo antigo. O listener de preenchimento por Ofício permanece intacto.
Revalidação pós-remoção pendente; não fechar o candidato antes dela.

Atualização da nota histórica de compatibilidade: OS, Planos e Viagens também
usam hoje destinos operacionais. Bases de mapas, registros e seletores continuam
necessárias; não são código obsoleto apenas por existirem antes da migração.

Pós-remoção98607 terminou:51aprovados,1falha,1warning,223,04s. A falha é
color-contrast no diálogo de via assinada em1440, antes do upload. O relatório
abreviado não identifica o nó; teste passa a imprimir JSON integral das violações.
Rodada diagnóstica48265 (termos-assinado-contraste) em execução nas três larguras.
Não aceitar passagem posterior como explicação da intermitência. Limpeza ainda
sem commit, matriz em validação. Revisão independente considerou a remoção segura,
condicionada à regressão; índice real pós-remoção funcionou em quatro larguras.

48265 terminou3passed,1warningteardown,92,03s; não reproduziu a falha.
Diagnóstico permanece aberto: capturar nós/cores/transições na abertura real do
diálogo. Nenhuma asserção enfraquecida, nenhuma classificação causal presumida.

## Causa reproduzida da leitura de contraste

Instrumentação somente GET/HEAD no DEMO: oito aberturas do diálogo em1440,
auditadas imediatamente e depois de aguardar as animações finitas terminarem.
Seis aberturas apontaram contraste durante a transição; todas as oito passaram
na superfície estável (opacidade1). Nós: `#dialogo-assinado-ajuda`,
`#dialogo-assinado-documento` e `.anexo__link`. A ajuda "PDF escaneado..."
registrou contraste intermediário4,19:1. Evidência integral:
`termos-contraste-abertura.json`. O keyframe `dialogo-entrar` começa em opacity0
e dura220ms; `to_be_visible` não aguarda seu término.

E2E agora aguarda `Animation.finished` das animações finitas do diálogo antes
da auditoria. Sem espera fixa, CSS modificado, exclusão de nós ou regra axe
desativada. Redução de movimento continua suportada (lista vazia/anim. encerrada).
O diagnóstico explica a intermitência; a nova regressão usa log separado
`termos-poslimpeza-final.log`. Aprovação ainda depende dessa execução.

72449 encerrou49aprovados/3falhas/1warning,217,75s. Relatórios completos agora
apontam elementos ao fundo: rótulos de distância em360/768 e remover destino
parcialmente encoberto em1440. Não são os mesmos nós da transição do diálogo.
Um caso isolado1440(18475)passou, sem comprovar causa. Instrumentação adicionada
ao teste registra open, :modal, opacidade, foco, HTML e screenshot na falha.
Execução8419 repete o conjunto na mesma ordem com essa nova evidência disponível;
log separado termos-poslimpeza-diagnostico.log. Limpeza permanece sem commit.

8419 terminou52passed,1warningHarfBuzz,246,11s. As três assinaturas passaram,
sem registro ESTADO_DIALOGO. Isso não comprova a causa das falhas de fundo.
Revisão estática do axe empacotado: detector de modalidade usa hit-test interno
e oclusão externa, não :modal. Produto usa showModal/foco nativos; não foi
identificado lifecycle que libere o fundo. Próximo diagnóstico deve registrar
active-view-transition, animações globais e elementsFromPoint durante navegação.
Não excluir nós de fundo nem modificar inert para obter resultado verde.

## Jornada e condição de auditoria estável

Nove jornadas DEMO Lista→#previa→Anexar, três por largura360/768/1440,
somenteGET/HEAD: modalidade nativa verdadeira, hit-test interno/externo no diálogo,
sem animações remanescentes, sem active-view-transition e sem violações. Registro:
`termos-modal-jornada.json`. Isso não reproduziu as falhas anteriores e não prova
que view-transition foi sua causa. A hipótese permanece identificada como tal.

Teste passa a exigir a superfície final da página: fontes prontas, animações
finitas concluídas, dois frames de composição e modalidade nativa mantida. Não
modifica animações/CSS nem restringe axe. Ao falhar, inclui animações globais e
estado de view-transition no diagnóstico. Regressão de navegador31326 em execução,
log `termos-assinado-superficie-estavel.log`. A cobertura HTTP52 da8419 permanece
registrada separadamente; não executar novamente apenas por mudar diagnóstico.

## Fechamento técnico

31326 terminou **9 passed, 2 warnings, 177,67s**. Com os52aprovados da8419,
índice em4larguras, nove jornadas instrumentadas e revisão independente,
TE01/TE02/TE03 ficam concluídas tecnicamente com ressalva explícita: a causa exata
das três falhas históricas do axe sobre o fundo não foi comprovada. A condição
final de auditoria estável é agora exigida, não obtida desligando verificações.
Os avisos HarfBuzz e conexão no teardown permanecem registrados. Não há regressão
funcional conhecida no candidato; não se declara homologação visual ou gate global.
31linhas de controlador obsoleto removidas; nenhum dado/documento alterado.
