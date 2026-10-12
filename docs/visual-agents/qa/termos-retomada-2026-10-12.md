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
