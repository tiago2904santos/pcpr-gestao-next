# QA — carregamento de Baixar na primeira ação

Data: 07/10/2026. Worktree isolado `viagens-tempo-legado`.
Decisão registrada antes do código: [ADR 0028](../adr/0028-carregar-download-na-primeira-acao.md).

## OBSERVAR / ENTENDER

Baseline fresco da folha em `artifacts/desempenho-viagens_oficios_12_editar.json`:
JS **155,3 KB / gzip 54,7 KB**, acima de **130 / 45 KB**. Antes deste recorte,
`app.js` importava `baixar.js` pela presença de `#dialogo-baixar`, mesmo fechado.
O módulo anterior minificado tinha **6.589 bytes**. Menu/navbar e visita à tela
não precisam preparar download; o GET de itens pertence à abertura explícita.

Fontes primárias locais: `static/js/app.js`, `componentes/baixar.js`,
`templates/componentes/dialogo_baixar.html`, `gestao/viagens/views_pacotes.py`,
`pacotes.py`, testes de pacotes e `tests/e2e/test_baixar.py`/`test_menu_oficio.py`.
Regras e formatos estão no contrato existente e em `docs/product/documents.md`.

## PROJETAR / IMPLEMENTAR / CORRIGIR

Somente o registro de carga por presença de `#dialogo-baixar` foi removido do app.
Um dispatcher delegado de clique entrega o primeiro comando à função exportada
`abrirDialogo(botao)`, após importar. Enter/Espaço de botão nativo continuam
produzindo o mesmo clique. **Não há re-dispatch**, segundo handler de abertura,
download automático ao abrir, ou alteração de endpoints/POST.

O módulo mantém seus handlers únicos de Marcar todos, change e submit. Conserva
reset, escolhas lembradas, título, URL, GET, desenho, regras de formato/versão/
PDF único, erro em português, geração e nome do arquivo entregue.

Durante import, o app deduplica a ação e marca aria-busy na origem. Escape cancela
antes da abertura e botão removido não abre janela tardia. Falha de import gera
toast de perigo: “Não foi possível abrir os documentos. Recarregue a página e
tente de novo.” O foco volta à origem disponível quando não houve outra
interação; erro técnico continua no console e não é filtrado nos casos normais.
A orientação de recarregar evita prometer que um módulo cuja carga falhou será
reavaliado pelo cache do navegador sem nova navegação.

Crítica durante implementação: segurar a trava até o GET terminar impediria
fechar/reabrir para tentar novamente se a leitura ficasse pendente. O coordenador
autorizou a correção antes de executar os novos testes. O token do app agora é
liberado assim que o módulo abre o modal; cada leitura tem AbortController e
geração de abertura próprios. Fechar cancela o GET; reabrir inicia outro.
Resposta antiga/abortada ou janela removida não repinta, não redireciona, não
mostra erro de cancelamento e não muda foco. O POST continua integralmente igual.

Cronologia de fonte comunicada ao coordenador: primeira edição do app às
**18:39:10**, antes da rodada de cadastro iniciada às 18:40. Correção de GET e
novo congelamento do produto às **18:45:53**. Essa rodada em curso exercia
somente cadastro de servidor/viatura, sem usar Baixar; não conta como validação
do recurso adiado.

## TESTAR / COMPARAR — apenas evidências estáticas nesta entrega

- TypeScript `tsc --noEmit -p jsconfig.json`: **exit 0**, repetido após corrigir GET.
- Ruff de `tests/e2e/test_baixar_carga.py`: **All checks passed**.
- Compilação Python do teste e `git diff --check`: **exit 0**.
- Busca de fontes: um único import dinâmico de baixar no dispatcher; nenhum
  registro inicial `#dialogo-baixar`; função exportada presente; um handler de
  cada tipo click/change/submit no módulo; abertura removida do handler click.
- Minificador real do repositório: app antes deste recorte **7.371 bytes**,
  atual **8.918**, delta **1.547**; baixar anterior **6.589**, atual **7.271**.
  O “antes” do app foi reconstruído retirando somente o dispatcher inserido e
  recolocando o único registro inicial, preservando guardas/editores/seletores.

Economia inicial estimada deste recorte, isoladamente: **5.042 bytes (~4,9 KB)**
e um pedido, antes dos efeitos de gzip. O módulo maior passa à primeira ação,
quando seu custo continua existindo. Isso é aritmética sobre fontes minificadas,
**não medição do candidato em navegador**; não comprova atendimento dos tetos
nem combina ganhos de alterações simultâneas de outros agentes.

Nenhum teste de banco/navegador ou commit foi executado por este agente.

## CRITICAR / VALIDAR — testes entregues e pendências

Novo `tests/e2e/test_baixar_carga.py`: **11 casos codificados**. A entrega inicial
era estática; a primeira rodada real e suas falhas estão registradas abaixo.

- Lista/resumo/folha fria e menu do usuário não solicitam baixar.js.
- UI Lab em 360/1440: primeiro Enter, ausência de POST/download ao abrir,
  controles e preferências, Space na reabertura, cache, arquivo real recebido
  do endpoint de exemplo e somente um envio. Capturas após fim da animação:
  `artifacts/baixar-carga/baixar-360.png` e `baixar-1440.png`.
- Página inteira auditada antes da abertura; superfície modal operável depois,
  mesmas tags WCAG e nenhuma regra/violação excluída. Relatórios axe em
  `artifacts/baixar-carga-axe-360.json` / `baixar-carga-axe-1440.json`.
- Import em curso: clique repetido, Escape e remoção da origem. Handler Route
  conclui a própria rota com try/finally; não guarda rota fora do callback nem
  espera um evento que só seria produzido depois de sua saída.
- 503 deliberado na carga do módulo: mensagem, foco, ausência de GET/POST do
  pacote, erro técnico esperado e recuperação por reload. Nenhum outro erro é
  tolerado; a lista do console não é apagada para o teste passar.
- Fechar durante GET preserva foco posterior; fechar/reabrir enquanto GET está
  pendente mantém os três itens da leitura nova e descarta resposta antiga
  divergente. Não há espera arbitrária longa ou rota retida fora do handler.

O endpoint UI Lab entrega texto de exemplo, não PDF de negócio. Executar também
os contratos existentes de download real:

- `tests/e2e/test_baixar.py` (termo, resumo do ofício e PDF entregue).
- `tests/e2e/test_menu_oficio.py::test_baixar_documentos_pelo_menu_e_foco_volta_ao_botao`.
- `tests/e2e/test_acessibilidade.py::test_janela_baixar_documentos_sem_violacoes`.
- `gestao/viagens/tests/test_pacotes.py` para formatos, versões, ZIP/PDF único,
  seleção e permissão, se houver qualquer falha nos contratos de navegador.

Consumidores diretos do diálogo encontrados: Ofícios (lista/resumo/folha),
painel de Viagens, Termos (lista/folha), OS, plano, viagem, justificativas e UI Lab.
Testar primeira ação em menu flutuante e botão direto, resumo modal sobreposto,
reposição HTMX após módulo em cache e retorno de foco. A delegação por documento
suporta HTML novo sem registrar handlers por instância, mas isso continua
dependendo de teste real das telas consumidoras.

Depois: coleta sequencial das três rotas com o mesmo coletor/tetos, revisão de
capturas 360/1440, `scripts/verificar.sh` completo e paridade aplicável. Não há
aprovação de desempenho, acessibilidade geral ou estética inferida nesta entrega.

## Revisão curta do contexto modal — evidência recebida do coordenador

Leitura real de `artifacts/cadastro-adiado-ax-360.json`: backend 219, o controle
de fundo, está **ignored=true**, com razão **activeModalDialog** apontando para
`#dialogo-servidor` (backend 147). Captura final `cadastro-adiado/servidor-360.png`,
após `animations.finished`, mostra formulário inteiro e foco visível em Nome
completo; o fundo está sob véu/blur. Os relatórios atuais de axe inicial/modal
360 são ambos `[]`. O JSON antigo foi sobrescrito; o achado antigo target-size
do marcador no fundo é verificável no log da rodada anterior, não no JSON atual.

Auditar a página inteira antes e a superfície operável depois de showModal é
legítimo nesse contexto nativo, sem excluir violações/rules da superfície ativa.
Isso não autoriza ignorar o fundo numa tela normal ou num details comum.
Para claim amplo ainda faltam Tab/Shift+Tab presos no modal, Escape/retorno à
origem, diálogos sobrepostos de Cargo/Unidade/Combustível e estados de erro,
validação e viatura. Axe/AX/screenshot não provam esses fluxos de teclado.

## Rodada real e correção do sincronismo dos testes

Evidência recebida do coordenador: `var/baixar-assinados-carga-browser.log`,
**5 failed, 6 passed, 3 errors in 347.72s**, incluindo os contratos antigos de
Baixar/Assinados. Seis casos novos passaram: três visitas frias, primeiro Enter
em 360/1440 e remoção da origem durante import. O caso repetir import encontrou
modal ainda oculto; fechar durante GET encontrou modal ainda visível. Callbacks
pendentes falharam em `APIResponse.dispose` após teardown e contaminaram os três
setups seguintes. Isso não é evidência de aprovação dos demais casos novos.

Fonte primária local: `playwright/_impl/_helper.py`, `RouteHandler._handle_internal`,
executa cada callback sync em uma greenlet e aguarda sua conclusão separadamente.
`wait_for_load_state("networkidle")` após o clique pode apenas reconhecer o estado
já alcançado pela navegação anterior, antes de fetch/fulfill/dispose da interceptação.

Plano antes da alteração: cada teste de corrida cria um marcador DOM pendente
antes do clique; o handler sinaliza conclusão somente depois de entregar a rota
e liberar a resposta. O corpo principal aguarda esse sinal antes de verificar
modal/foco/dedupe/cancelamento/resposta antiga. Erros do handler são registrados
e relançados no corpo principal, para não aparecerem apenas no teardown de outro
teste. Falha de fulfill após fechamento somente é esperada quando a página
continua aberta e `request.failure` identifica `net::ERR_ABORTED`; outros erros
continuam falhando. Não há espera arbitrária nem `ignoreErrors`.

Escopo autorizado: apenas o teste novo e este relatório. Produto, testes antigos,
bancos e navegador permanecem sob controle do coordenador. Próximas verificações:
três corridas focadas e depois todos os 11 casos novos, sequencialmente. Resultados
posteriores ainda pendentes; capturas anteriores de Enter não validam as corridas.

Correção implementada nos três testes de corrida. O sinal tem timeout de 60 s,
enquanto fetch tem 15 s e cliques internos têm 5 s; é espera condicionada ao DOM,
não pausa fixa. A rota de resposta antiga também termina em finally quando um
assert interno falha. Fetch inesperadamente falho aborta sua requisição e relança
o erro, para não deixar uma interceptação sem conclusão.

Checks desta correção, sem banco/navegador: Ruff verde, compilação/AST Python e
`git diff --check` verdes. Exercício dos helpers com objetos em memória verificou
ordem entrega/dispose/sinal, erro relançado ao corpo principal, recusa de
`ERR_FAILED`/falha sem código e recusa de tolerância quando a página está fechada.
Somente `net::ERR_ABORTED` com página aberta foi aceito. A primeira execução do
exercício auxiliar teve erro em seu stub de anotação Callable; corrigido o stub,
passou. Isso valida a lógica do helper, não o agendamento real do Playwright;
as duas rodadas sequenciais do coordenador continuam necessárias.

## Reexecução pelo principal — gate delimitado de 07/10/2026

As três corridas passaram em 30,31 s. Os 14 Baixar/assinados passaram juntos na
consolidação de navegador (54 verdes/1 falha alheia ao download, registro de
rascunho depois corrigido). Dois HTTP de pacote PDF/DOCX e o E2E de mensagem 422
com via cruzada passaram; a recusa fetch deixa orientação visível e não cria
download/versão. OS anexa pelo diálogo real e confere bytes; revogação é HTTP
real porque a barra anterior não oferece Remover, limitação explícita no nome.
Log/capturas e resultados completos em
`../visual-agents/qa/fechamento-gate-final-2026-10-07.md`; aprovação integral ainda
depende do gate final. Não somar execuções distintas como uma suíte verde.
