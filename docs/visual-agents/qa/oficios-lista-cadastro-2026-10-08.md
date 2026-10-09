# Lista e Cadastro de Ofícios — reconstrução de 08/10/2026

## Estado e escopo

Base: `1f69551`; branch: `codex/oficios-lista-cadastro`.
Somente o Resumo/Detalhe foi aprovado visualmente pelo usuário. Lista e Cadastro
anteriores foram reprovados. As novas candidatas foram reconstruídas e aguardam
revisão estética. Nenhuma expansão para Termos, OS, Planos ou integrações.

## Observação, projeto e implementação

O legado local em `Solicitações de eventos` foi consultado somente em leitura:
`templates/pages/viagens_oficios/lista.html`, `viagens_oficios/abas.py` e
`templates/pages/viagens_oficios/form.html`. A matriz de paridade mantém filtros,
abas, campos, estados, ordem, exportação e ações existentes. Não foi copiado código.
ADR: `docs/adr/0030-lista-e-preparacao-no-padrao-do-resumo.md`.

**Lista:** cabeçalho grafite, índice temporal lateral no desktop, filtros em uma
faixa própria e registros com identidade, missão/agenda, recursos e diárias. No
mobile, número/status abrem o registro; agenda e valores dividem a faixa; equipe e
transporte encerram a leitura. Busca, filtros completos, contadores OOB, paginação,
exportação e menu canônico preservam seus contratos.

**Cadastro:** cabeçalho oficial com ações, índice por âncoras, identificação com
larguras semânticas, seções editoriais contínuas, equipe/transporte agrupados,
conferência financeira e cópia no padrão do Resumo. Os IDs e invólucros HTMX,
formulários externos, autosave, Enter, salvamento, revisão e emissão permanecem.
O fechamento segue o fluxo normal para não interceptar controles na rolagem.

Componentes/variantes: `registro_hero`, `colecao-operacional`,
`registros--operacionais`, `indice_preparacao`, `documento--preparacao`,
`campos--registro`, `pessoas--compactas`, `conferencia_valores` horizontal/serena,
`barra-acoes--registro/--fluxo` e `historico_documental`. Documentação na origem
em `docs/design-system/components.md`; exemplos sintéticos no UI Lab.
Nenhuma alteração em modelos, queries, domínio, serviços, cálculos, permissões,
snapshots, hashes, integração ou conteúdo de documento oficial.

Arquivos principais:

- `gestao/viagens/templates/viagens/oficios/{lista,editar,_registro,_equipe,_diarias}.html`.
- `templates/componentes/{registro_hero,indice_preparacao,conferencia_valores,historico_documental}.html`.
- `templates/arquetipos/lista.html`, `templates/base_documento.html`.
- `static/css/{components,layout}.css` e `static/js/componentes/{editores,dialogo}.js`.
- `gestao/ui_lab/templates/ui_lab/` e `docs/design-system/components.md`.
- Contratos de apresentação em `gestao/viagens/tests/test_views.py` e testes de
  navegador em `tests/e2e/{test_oficios_visual,test_resumo_visual,test_lote_h_visual,test_filtros_carga}.py`.

Inventário completo da implementação: `git show --stat 615acd9` e os dois commits
de correção abaixo. Fontes auxiliares de execução e PDFs candidatos de recuperação
ficam ignorados em `var/`; não fazem parte dos commits nem das evidências públicas.

## Comparação, crítica e correção

- Iteração 1 da Lista: grid herdado conflitava com agrupamentos e havia colisão de
  período/protocolo. Corrigidos; E2E verifica geometria dos grupos reais.
- Iteração 1 do Cadastro: havia rótulo cortado, avisos fora da coluna e ações mal
  distribuídas no mobile. Corrigidos; recursos foram separados da identificação
  para evitar uma coluna lateral vazia ao longo do formulário.
- A revisão de dados extensos encontrou controles interceptados pelo rodapé,
  apesar da bateria menor passar. O fechamento final ocupa o fluxo normal.
  O teste visual verifica também a ausência dessa colisão.
- Um token sem definição foi detectado e corrigido para `--cor-marca-fundo`;
  os 68 contratos de tokens foram reexecutados e passaram.
- Autocrítica: a composição muda em miniatura e a Folha deixa de ser uma sucessão
  de cartões isolados. A extensão do formulário e o editor oficial continuam
  exigindo rolagem no celular; nenhum campo foi escondido para encurtar a tela.
  A candidata precisa da avaliação estética do usuário, sem aprovação presumida.

## Evidências reais

Galeria: `../evidencias/oficios-lista-cadastro/index.html`.
Capturas originais do mesmo dataset sintético, sem retoque/imagem gerada, em
360/390/768/1024/1440 px: Lista com dados, filtrada e filtros abertos; Cadastro
preenchido, com pendências, próximo da revisão, equipe, roteiro e emissão.
`antes/` corresponde à base; `depois/` à composição consolidada. Iterações
intermediárias foram preservadas como evidência da crítica. O diálogo histórico é registrado em `historico/historico-360.png` e `historico/historico-1440.png`.

PREVIEW isolada em `127.0.0.1:8012`: busca, exportação do recorte, menu com Enter/Esc,
foco, colisão, axe e overflow passaram nas cinco larguras da Lista. Conferência
final de 25 estados (cinco larguras × cadastro/equipe/roteiro/documentos/calendário):
zero violações axe, overflow e erros de console. JSONs:
`lista-qa-preview.json`, `composicao-qa-preview.json`, `depois-medidas.json`.

## Validação automatizada

- Criação/preenchimento/emissão completos em banco limpo: **1 aprovado**.
- Bateria anterior de Cadastro: **53 aprovados, 2 falhas e 1 erro de fixture**.
  As falhas e o erro estão classificados abaixo; não atribuir sucesso à execução inteira.
- Reteste de cópia: **5 aprovados**, inclusive fallback HTMX, autosave e foco.
- Guardas HTTP documentais + retry/histórico: **25 aprovados** (22 HTTP + 3 navegador).
- Tokens após a última correção: **68 aprovados**.
- Visual/UI Lab anterior: **14 aprovados**. Cinco visuais após o rodapé definitivo
  passaram; bateria consolidada final: **35 aprovados** (menu, filtros, cinco larguras, UI Lab, motorista/autosave e histórico).
- Contrato de apresentação do Resumo: dez casos do focused passaram e o único
  caso corrigido foi reexecutado isoladamente e passou.
- Tipos JS e ruff focado passaram após a mudança do diálogo secundário.
- Comentários de templates: **245 aprovados**. UI Lab real em 360/1440 px:
  sem comentário vazando, zero axe/console e retorno de foco após Esc.
- Sequência da Folha e justificativa: **3 aprovados** após atualizar os contratos
  de apresentação, preservando prazo, visibilidade e ordem de leitura.
- PREVIEW: **294 PDFs prontos**, nenhum gerando/falhou. Download real do Ofício
  sintético 159/2026: HTTP 200, assinatura `%PDF-` e hash iguais ao registro;
  polling encerrado, zero axe/console. Evidências: `preview-documento-qa.json`,
  `preview-documento-pronto.png` e `preview-oficio-159-v1.pdf`.
- Gate integral final `scripts/verificar.sh`: **2.241 aprovados, zero falhas,
  9 avisos, 48min06s**. Ruff, 16 contratos de arquitetura, mypy, Bandit, migrações
  e tipos JS passaram. Rodado integralmente após `e450e37`; conclusão em
  09/10/2026, com **`✔ tudo verde`** em `lista-cadastro-verificar-fechamento.log`.

Execuções redundantes/interrompidas não são computadas como aprovadas.
Logs concluídos, inclusive o gate final, em
`../evidencias/oficios-lista-cadastro/logs/`.
Logs são cópias literais das saídas, inclusive CRLF e espaços dos tracebacks;
não foram reformatados para ocultar falhas ou avisos. A conferência de whitespace
da documentação exclui esses arquivos brutos.

## Falhas classificadas e resolvidas

**Regressões desta implementação:** grid/agenda, rótulos, avisos e interceptação pelo
rodapé foram reproduzidos e corrigidos. Token inexistente corrigido. Nenhuma regra
axe ou checagem de console foi desativada.

O gate integral anterior terminou com **2 falhas, 2.239 aprovados e 7 avisos**
em 54min43s (`lista-cadastro-verificar-entrega.log`). Os dois contratos ainda
exigiam documentos nas posições 3/4, anteriores à seção equipe/transporte.
As verificações de prazo/visibilidade passaram. Corrigido em `e450e37`: os testes
exigem sequência contínua e justificativa antes de documentos; três cenários
reexecutados passaram. Isso foi uma atualização de contrato esquecida nesta
implementação, não uma falha preexistente nem mudança de regra de negócio.

**Preexistentes comprovadas na base `1f69551`:** alvo pequeno nas migalhas e corrida
do índice do editor em 768 px reproduzidos em `lista-baseline-browser.log` (2 falhas).
Corrigidos na origem por afetarem diretamente as páginas; escolha explícita do
índice descarta notificações de interseção com geometria antiga.

Comentário Django multilinha inválido em `_dossie.html` do UI Lab confirmado na
base por `dossie-baseline-template.txt`. Corrigido em `0cc1b97`; 245 contratos e
duas larguras reais passaram. O gate interrompido após essa falha conhecida não
é computado como aprovado.

Fallback de cópia HTMX reproduziu seis violações CSP `style-src-attr` do vendor
na base (`resumo-baseline-retry-copia.log`). Configuração limita `attributesToSettle`
a class/width/height, preservando CSP; reteste de cinco casos passou sem erros.

O Resumo aprovado retirou o histórico da estação corrente, mas o pacote continha
somente a corrente. Foi recuperado acesso por **Mais ações → Histórico de documentos**,
usando projeção autorizada e links exatos existentes. Diálogo secundário preserva
estação principal e devolve foco. Sem alteração de pacote, dados ou geração.

**Contratos de teste antigos:** classe da lista substituída pelo redesenho;
metadados retirados do Resumo aprovado (falha reproduzida em
`resumo-baseline-http.log`); nome acessível do PDF ganhou data de emissão
(falha reproduzida em `resumo-baseline-retry-copia.log`). Atualizados para a
apresentação vigente; PDF continua exigindo tipo/versão, href exato, identidade,
idempotência e download válido. Não se reduz cobertura funcional.

**Ambiente de teste:** banco reutilizado de execução interrompida continha ASCOM
antes do fixture, causando duplicidade. Criação completa reexecutada em banco
limpo passou. Aviso HarfBuzz/WeasyPrint do runtime não impede PDFs verificados;
nenhum documento oficial alterado para ocultá-lo.
Os nove avisos do gate final são depreciações WeasyPrint/HarfBuzz e pypdf,
também presentes na execução anterior; fontes correspondentes não foram alteradas.
São dívida técnica preexistente, sem falha nos PDFs testados. Avisos de comentários
`nosec` do Bandit ficaram visíveis no log; a ferramenta terminou sem achados.

## Custo e limites da medição

Comparação de templates da base/atuais no mesmo dataset sintético isolado:
Lista mantém 16 consultas aquecidas; Cadastro 24. HTML: 128.009 → 130.983 bytes
(+2,3%) e 154.547 → 154.876 (+0,2%). CSS compartilhado LF: 119.042 → 133.906;
gzip: 25.397 → 27.437 (+2.040 bytes). `app.js` inalterado; editor +219 bytes gzip;
layout compartilhado +14 bytes gzip; controlador do diálogo +216 bytes gzip.
Total das fontes alteradas: CSS +2.054 bytes gzip; JS +435 bytes gzip.
Dados brutos: `lista-custo.json`; compressão das fontes não equivale à compressão
efetivamente configurada no servidor de desenvolvimento.
Nenhuma biblioteca ou carga antecipada adicionada. Medianas sob concorrência
não comprovam mudança pequena de latência. CSS global já extenso é dívida
preexistente; não foi aberta otimização ampla.

LAB próprio, PostgreSQL 55432 e mídia separada. Para o cluster descartável, após
verificar o datadir exato, foram desativados fsync/synchronous_commit/full_page_writes.
Isso não valida durabilidade de armazenamento. DEV PostgreSQL 5432 não foi alterado.
Uma consulta de fixture demorou vários minutos e terminou sem intervenção; isso
é limitação do ambiente de validação, não evidência de regressão da página.
O gate final usa seis workers e bases novas (`--create-db`), sem filtro de testes.
A base principal LAB foi criada antes da execução. No gate anterior houve aviso
inicial de base ausente na verificação de história de migrações; a checagem foi
repetida sem aviso, com `No changes detected` (`migracoes-entrega-final.log`).

## Incidente de preparação do ambiente — pendente

O primeiro comando de semeadura da prévia usava mídia padrão `var/media` e tentava
limpar subpastas documentais. Foi interrompido e o isolamento corrigido: banco
`pcpr_lab_demo`, porta 55432; mídia `%LOCALAPPDATA%/pcpr-codex-lab/preview-media`.

Depois foram encontrados dois registros de PDF pronto do Ofício 03/2026 no DEV
sem arquivos correspondentes. Sem inventário anterior nesta máquina, não é possível
atribuir ausência preexistente. O comando inicial pode ter causado a perda.
Candidatos em `var/recuperacao-pdfs/` diferem dos hashes originais e não foram
usados para substituição. Banco, hashes, snapshots e histórico não foram alterados.
Usuário informado e consultado sobre originais ou recuperação; resposta pendente.
Não classificar esse incidente como dívida preexistente sem evidência.

## Fechamento

Commits locais validados:

- `615acd9` — reconstruir Lista e preparação de Ofícios.
- `0cc1b97` — impedir vazamento de comentário no exemplo do dossiê.
- `e450e37` — preservar a sequência da Folha sem índices fixos.

**Validação técnica encerrada com gate verde.** Não há regressão funcional conhecida
nas candidatas após os retestes. Esse resultado não encerra o incidente de mídia DEV
descrito acima nem equivale à aprovação visual do usuário. Não houve push, merge
ou deploy. O commit documental final registra evidências e classificação.

**Decisão: candidatas tecnicamente validadas, aprovação visual pendente e recuperação
DEV pendente.** Próxima ação é a revisão estética de Lista e Cadastro; não abrir
página posterior nem outro módulo. Autocrítica remanescente: formulário longo no
mobile e densidade do editor oficial; ambos preservam a cobertura funcional.
