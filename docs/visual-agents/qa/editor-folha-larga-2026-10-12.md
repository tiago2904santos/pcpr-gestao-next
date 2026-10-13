# Folha documental larga — candidato em validação

Base: cef0e77, branch codex/oficios-transporte-cartoes. Continuação da correção
de Termos; não fecha TE01/TE02/TE03 nem a meta integral (9/100).

## Evidência e duas passagens

Antes: termos-documento-3-360.png mostra lotação cortada pelo overflow hidden.
Primeira passagem: permitir rolagem X e calcular altura pelo corpo; texto passou
a ser alcançável, mas escapava da superfície branca. Segunda passagem: largura
mínima intrínseca em folha.css, preservando papel sob o conteúdo e tamanho da fonte.
Nenhum template oficial, regra de geração ou CSS de PDF foi alterado.

Capturas reais, mesmo DEMO Termo7, GET/HEAD apenas: termos-editor-rolagem-inicio
e termos-editor-rolagem-direita, larguras360/390/768/1440, no diretório de evidências
migracao-identidade-20261012. JSON termos-editor-rolagem.json registra alcance
horizontal106/76px nas duas menores e nenhum excesso nas maiores. Altura estável
após20 recálculos:1187/1187/1138/1169px. A captura deslocada demonstra o final da
linha; naturalmente o início fica fora do viewport enquanto a folha está deslocada.

## Verificações

Tipos: npm run typecheck verde. Suíte editor-folha-larga (sessão70490) em execução;
não declarar testes concluídos antes de observar resultado terminal. Inclui teclado
em Termos, estabilidade, manutenção de HTML e regressão do editor de Ofícios.
Revisão independente favorável ao candidato, sem defeito concreto encontrado;
pediu evidência adicional de encolhimento após edição e rodapé inferior.

Compatibilidade ainda a concluir: Ordens, Planos, Justificativa e aviso sem documento.
CSS de tela é compartilhado: não presumir compatibilidade pela ausência de mudança
nos templates. Não houve nova dependência, requisição ou mudança de consultas.
Não afirmar ganho de latência. Documentar resultado dos testes e medições finais.

Primeira rodada encerrada:12 testes passaram em357,34s (sessão70490), dois avisos:
HarfBuzz e uma conexão ainda aberta durante teardown do banco isolado. Houve consulta
lenta na preparação de fixture, sem bloqueadores em pg_stat_activity; completou sem
reiniciar a suíte. Causa da lentidão não determinada. Log integral preservado.
Essa rodada coletou o teste antes da extensão de encolhimento/rodapé; esses dois
casos exigem a nova execução editor-folha-larga-final, junto com Ordens, Planos,
testes HTTP/documentais e tokens. Não associar12pass à cobertura nova.

Peso de fontes normalizado para LF: folha.css5924→6115bytes (+191);
editor-documento.js50554→51327bytes (+773), incluindo comentários. Sem novo asset,
dependência ou requisição. Sem medição conclusiva de latência.
Galeria atualizada e validada:661capturas,149telas e512componentes; as8novas
imagens estão identificadas como candidato em validação. PNGs/links/ZIPs íntegros.

Retomada: suíte ampliada ativa na sessão72287; log editor-folha-larga-final.log.
Não há commit do candidato enquanto essa validação não terminar. Próxima ação:
acompanhar a sessão existente, investigar qualquer falha sem apagar o log,
revisar compatibilidade visual e registrar resultado antes de fechar Termos.

## Compatibilidade visual atual

15 capturas reais em360/768/1440: Ofício259, OS5, Plano4 e Ofício242 com
Justificativa. GET/HEAD, sem semeadura nem alteração dos registros. Medições em
editor-folha-compat.json: alturas estáveis, documento carregado, página externa
sem overflow. Ofícios com tabelas largas usam rolagem interna; OS/Plano/Justificativa
destes cenários não precisam de rolagem horizontal. Revisão das capturas mobile,
tablet e desktop não encontrou regressão concreta; não é aprovação do usuário.

Primeira captura de compatibilidade75897 falhou aguardando networkidle em Planos.
Critério foi corrigido para conteúdo real da folha, fontes prontas e dois frames
de renderização, sem ocultar controles ou modificar dados. Execução11542 encerrou
as15capturas. Não há diagnóstico comprovado da requisição que impediu networkidle;
a falha de sincronização não foi convertida em alegação de melhora de desempenho.
O aviso sem configuração está incluído na cobertura HTTP da suíte em execução.

Próximo conjunto após fechar Termos: OS01/02/03. Descoberta independente encontrou
uma lacuna de teste: aba=cancelados é inválida e cai em Todas; o valor real é
canceladas. Corrigir a cobertura dessa aba na próxima rodada, sem misturar edição
de Ordens com a atual. Documentos PDF normais/DOCX podem fixar geração/data;
capturas devem usar HTML ou PDF com previa=1.

Checkpoint21:06: suíte72287 ainda ativa. Houve F no E2E de OS, resumo detalhado
pendente até encerramento. Não classificado como preexistente nem regressão sem
traceback/reprodução. Quatro casos de largura passaram, incluindo novo crescimento,
encolhimento e rodapé em360. Tipos/ruff finais verdes. Galeria676 validada em360/1440:
149telas,527componentes; PNGs,links,ZIPs íntegros. Nenhum commit do candidato.

## Resultado terminal e classificação em curso

72287 terminou:137pass,1falha,1warningHarfBuzz,777,42s. A falha é
test_os_a_partir_do_oficio_com_funcoes: após mudar o tipo e salvar, o localizador
por nome de servidor resolveu para o select nativo, que ficou oculto durante
o clique (timeout30s). Não há falha nos testes novos do editor, Planos, Termos,
HTTP/documentos ou tokens. Ainda não classificar a falha apenas pelo contexto.

Reprodução12586 ativa, editor-os-baseline: mesmo E2E com folha.css e
editor-documento.js servidos de cef0e77 via interceptação de rede no navegador
isolado. Nenhum arquivo do checkout substituído. Registrar assets efetivamente
servidos, HTML dos campos e screenshot ao encerrar. Próxima ação: conferir a
reprodução, corrigir sincronização/contrato acessível se comprovado e revalidar.

Reprodução12586 inválida: callback do instrumento confundiu Request com corpo
do asset. Corrigido somente o instrumento, sem alterar aplicação; log preservado.
26063 encerrou1pass60,72s com assets cef0e77 efetivamente interceptados. Esse
resultado isolado não comprova preexistência; não foi usado para aprovar a falha.
O DOM registrado confirma select nativo hidden e botão combobox visível do
pc-select. No erro original, o clique resolveu o nativo antes de ele ser ocultado.

Teste corrigido para aguardar explicitamente button[role=combobox] com o mesmo
nome acessível do servidor e abrir por Enter. Mantidas asserções de validação,
função persistida, autosave e PDF; ampliado para360/1440. Aplicação de OS inalterada.
Revalidação98230 ativa: dois fluxos OS + quatro casos de folha larga. Ruff verde.

## Fechamento do candidato

Revalidação 98230 encerrada: **6 passed, 2 warnings, 153,71s**. Os dois
fluxos OS (360/1440) e os quatro casos do editor passaram. Avisos: HarfBuzz e
conexão ainda aberta no teardown do banco isolado; não foram apagados nem
classificados como corrigidos. O log ampliado continua registrando 137 aprovados
e a falha de sincronização diagnosticada; não se declara aquela rodada verde.

Revisão independente favorável ao controle canônico por teclado e à cobertura
de crescimento/encolhimento. Manifesto vincula os quatro arquivos testados por
SHA256 normalizado para LF. Galeria validada novamente: 676 PNGs íntegros,
149 capturas de telas e 527 de componentes, filtros e links em 360/1440.
O candidato resolve o corte da folha; não conclui a migração global nem presume
homologação visual. Gate integral permanece para o fechamento global.
