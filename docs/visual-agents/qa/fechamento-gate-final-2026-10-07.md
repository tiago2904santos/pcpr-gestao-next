# Fechamento do mesmo bloco — gate final

07/10/2026. Continuação delimitada por Tiago: fechar → validar → commitar → relatar.
Nenhuma nova página visual, recurso ou trabalho de Termos de Autorização.
Este documento substitui o status de entrega do checkpoint das 19:09, preservado
em `fechamento-bloco-2026-10-07.md`. Histórico completo desta execução em
`../../quality/fechamento-gate-2026-10-07.md`.

## Decisão

**Lote H: APROVADO COM RESSALVAS.** O gate local integral terminou verde:
**2187 testes passaram, zero falhas, sete avisos, 2421,27 s (40min21s)** e saída 0.
Os cenários obrigatórios de navegador/HTTP foram reexecutados, com falhas e
reexecuções discriminadas abaixo. Nenhum bloqueante funcional comprovado restante
nas suítes executadas. Performance permanece vermelha; intermitência CSP e limites
de paridade/dados continuam explícitos. Não é declaração de CI global verde nem de
conclusão de todos os critérios visuais/editoriais da reconstrução.

Fontes incorporadas na pasta original, branch **viagens/reconstrucao**, em
`feb35e2` + `bea84e3`. **43 hashes congelados conferem e as árvores completas de
897 arquivos de fonte são idênticas** ao código validado no worktree. Main e
origin/main locais permanecem em `8d1d77e`; sem push/merge em main.

**Tempo/adicional do legado:** implementado, validado e commitado; D16 confirmada
por Tiago. **Resumo/Documentos/Folha:** correções existentes fechadas, validadas e
incorporadas; paridade integral e demais itens do plano preservam seus estados.

## Correções por área

- Motorista/autosave: escolha preservada na gravação, recuperação auditada,
  conflitos entre abas e idempotência; correções H já commitadas e reexercitadas
  nas jornadas de criação/emissão. Nenhuma nova recuperação em dados DEV.
- Geração documental/retry: falha registrada após rollback, mensagem e repetição
  idempotentes. Resumo usa a corrente máxima; histórico substituído não oferece
  retry nem mantém polling. Worker/HTMX e PDF real nos testes.
- Data do ofício: hoje em Brasília ao emitir, exceção manual preservada, revisão
  informa efeitos sobre Convalidação/justificativa. D13 confirmada por Tiago.
- Outro meio de transporte: interpretação e persistência coerentes no formulário,
  domínio/documento, com campos condicionais e fallback sem JavaScript.
- Tempo/adicional: fórmula e arredondamento do legado, cache versionado; exemplo
  300 km/API180 min produz viagem240 min e adicional45 min. Preserva ajuste manual
  e valores históricos; não reprocessa documentos/trechos antigos.
- Resumo/documentos: identidade máxima por tipo separada da prontidão, corrente
  e histórico distintos, assinatura com dono/tipo/ID/caminho exatos, DOCX por
  snapshot, pacote incompleto recusado com orientação visível. Rascunho conserva
  minuta; emitido/cancelado indisponível não recebe minuta indevida.
- Performance/carregamento: editor/índice por visibilidade já incorporados;
  filtros fechados adiam JS; cadastro canônico e Baixar por primeiro uso, import
  deduplicado, requisição cancelada e resposta obsoleta descartada. CSS separado
  rejeitado e restaurado ao original; nenhum teto aumentado.
- Acessibilidade/teclado: barra dinâmica com um tab stop, Tab/ShiftTab em modais,
  Escape em cadastros sobrepostos com retorno ao gatilho, foco operável após OOB,
  foco na grade após primeira data do período. Axe e Chromium AX nos cenários
  delimitados; não equivalem a aprovação geral da aplicação.

## Candidatos incorporados

- Domínio/adaptador RS02 (`feb35e2`, origem `e5e48cc`): maior identidade por tipo, prontidão separada,
  snapshot, histórico e via exata. Tempo/adicional do legado já incorporado em
  `df93e90`, com fórmula, cache versionado e preservação da edição manual.
- `views.py`, `queries.py`, `policies.py`: seleção única nos consumidores,
  menu sem minuta indevida, leitura pelo ID solicitado com guard de dono/tipo/
  caminho, DOCX congelado e formulário de cadastro por primeiro uso.
- `assinados.py`, `pacotes.py`, `views_pacotes.py`: não promover versão anterior
  pronta quando a máxima falha/gera; assinatura corrente exata; justificativa
  esperada ausente explícita; recusa do pacote mostrada no diálogo em 422 JSON.
- Templates de Ofícios: parciais de corrente/histórico/rodapé, retry só da corrente,
  cadastro canônico adiado e opt-in dos filtros. Arquétipo lista só recebe bloco
  para dispensar preload local; os demais consumidores preservam o padrão.
- JS app/dialogo/baixar/cadastro-rapido/seletor-data: primeiro comando sem replay,
  deduplicação, cancelamento, resposta obsoleta descartada, foco operável após OOB,
  formulário canônico único e foco após primeira ponta do calendário de período.

## O que ficou fora

**CSS separado rejeitado por regressão visual comprovada.** A lista carregava
somente seletores.css, deixando a divulgação eProtocolo do Resumo sem estilo.
Concatenação equivalente não comprovava esse consumidor. `formulario.css` e
44 links foram restaurados; seletores.css e estilos_formulario.html não entram.
Nenhum template dos outros módulos ou de Termos permanece alterado.
O CSS final tem o mesmo SHA256 do original:
`d5b6f955117bc5b3f40ca386c0b413c5bb982a1421d627d18dbab6b5a103eb1e`.

Não entram: ação visual nova de remover via da OS, nova página, alteração de
budgets, reprocessamento automático de documentos/tempos históricos ou mudança
da regra de emissão posterior ainda dependente de D17.

## Testes desta execução, na ordem solicitada

Resultados de árvores/rodadas diferentes não são somados como uma suíte verde.

1. Focused últimos ajustes: 156 passaram/1 fixture falhou em 360,74 s.
   Fixture cancelado foi corrigida para usar hash pronto e `services.cancelar`
   com motivo; caso final passou em 10,00 s. Constraints não foram afrouxadas.
2. Baixar/assinados: primeira rodada teve falhas de seletores/sincronismo;
   três corridas passaram em 30,31 s. Rodada conjunta posterior passou todos
   os 11 novos Baixar e os dois downloads reais; OS passou após rolar o cartão
   visível, pois seu editor tem display:contents preexistente.
3. Sete E2E de Resumo: 7 passaram em 75,05 s. Polling real, worker, v2 corrente,
   históricos, cópia, abort, reabertura e foco com/sem ID.
4. Guards/consumidores HTTP: 64 passaram em 103,39 s. PDF/DOCX incompleto em
   fetch/POST normal: 2 passaram em 13,61 s. E2E de via cruzada/pacote e upload OS:
   2 passaram em 23,12 s, bytes/hash e ausência de download/versão nova conferidos.
5. Cadastro/filtros/teclado: 10 passaram em 101,77 s, 360/1440, axe, Tab/ShiftTab,
   Escape/retorno em Cargo/Unidade/Combustível, 503, GET tardio, cache e HTMX.
6. Consolidação anterior à retirada CSS: 54 passaram/1 falhou em 505,55 s.
   Única falha: teste pedia minuta do primeiro registro, que era cancelado.
   Passa a selecionar o rascunho conhecido, mantendo conteúdo/Escape/lista.
   Todos os 14 Baixar/assinados e os 8 Resumo passaram nessa execução conjunta.
7. Após retirar CSS: 37 HTTP passaram em 189,52 s, consumidores CSS, Resumo e
   guards de arquivo/via/pacote. Ruff completo verde.
8. Navegador após retirada CSS: 35 passaram/1 falhou em 417,10 s. H capturas,
   editor 9, cadastros/filtros 10, Resumo 8 (inclui estilo real 360/1440), registro
   rascunho e legado 360/1440 passaram. Fallback de cópia teve 6 avisos CSP;
   seleção/foco/axe passaram. Baseline do mesmo caso passou em 21,65 s; dois
   candidatos isolados passaram em 13,37/13,19 s. Conjunto final dos 5 de cópia
   passou em 51,68 s, console limpo e csp-resumo.json vazio. Sem mudança de produto
   ou policy para suprimir erro; origem da intermitência não confirmada.
9. Performance fresca equivalente: baseline 3 falhas/36,81 s e candidato
   3 falhas/37,24 s, coleta íntegra. Limites e coletor idênticos.
10. Primeira integral completa: 2184 passaram/3 falharam em 2414,51 s. Dois
    testes DEMO recusaram corretamente STAGING/PRODUCTION, mas a captura Windows
    interpretou UTF-8 como CP1252. Baseline08 reproduziu os dois em 6,04 s;
    PYTHONUTF8=1 resolve a codificação sem alterar guard/assertion. O terceiro
    teste exigia tag sem o novo atributo opt-in; agora verifica tag correta,
    ausência de open e opt-in presente. Três focados passaram em 13,02 s.
11. Repetição com --reuse-db foi interrompida: bancos TEST esvaziados pela suíte
    anterior perderam carga inicial de migrações, gerando falhas de catálogos.
    Log parcial preservado e não contado como integral completa. Reexecução
    integral final com --create-db, mesmos bancos TEST LAB, checks e
    fontes; nenhum ajuste em modelos/migrações/catálogo para compensar o ambiente.
    **2187 passaram/zero falhas em 2421,27 s, saída 0 e tudo verde.** Ruff,
    16 contratos, mypy303, Bandit, migrações e tsc passaram. Sete depreciações de
    WeasyPrint/HarfBuzz-Subset e pypdf iguais às do primeiro integral.
12. Evidência de filtros assentada: dois cenários completos passaram em 38,54 s,
    360/1440; capturas renovadas aguardam animação finita, revisadas sem recorte
    horizontal e com foco visível. Nenhuma alteração funcional/CSS.
13. Preview candidato atualizado, sem seed/reset: HTTP200 para lista, Resumo262
    e Folha262. Confirma opt-in final e ausência de seletores.css. Launcher inicial
    recusou importar config por falta de PYTHONPATH; corrigido só ambiente. Após
    incorporação, preview original8010 reiniciado e os mesmos três GETs retornaram
    HTTP200, com mídia DEMO isolada; logs e igualdade das fontes preservados.

## Falhas restantes e limites

- **Bloqueantes funcionais comprovados restantes: nenhum nas suítes executadas.**
  Integral e incorporação concluídos; focused não foi usado para substituir integral.
- Regressões demonstradas no candidato: minuta indevida, foco em item oculto,
  omissão de justificativa ausente, mensagem perdida no redirect fetch e CSS
  ausente na divulgação. Correções/retirada e evidências registradas; fechamento
  concluídos no escopo deste bloco, com integral final verde.
- Preexistente: falta ação visual Remover via na barra da OS. Upload/precedência
  são E2E; revogação foi HTTP real, identificada no nome do teste.
- Performance preexistente/dívida técnica, com comparação atual e sem excesso
  novo: lista/Resumo CSS 149,5 KB (teto 140) nos dois lados. Pedidos 28→23 e29→24,
  JS124,1→104,4 e126,5→106,8 KB. Folha HTML140→128,7 (120), JS155,3→151,2 (130),
  gzip54,7→52,8 (45), pedidos36→34 (32); SQL26→21 e DBmediano95,1→68,2 passaram
  os tetos25/80. CSS139,5/gzip28,6 iguais. Todos os tempos/CLS ficaram dentro do
  teto; não inferir ganho de latência com uma rodada. Testes perf permanecem
  vermelhos, não chamados verdes; classificar resíduos como não bloqueantes
  funcionais deste bloco não muda orçamento/CI nem elimina a dívida.
  O baseline equivalente é `08d46c7`: "preexistente" aqui delimita o que já
  excedia antes destes candidatos RS02/carga/guards, não atribui automaticamente
  o excesso inteiro ao legado ou ao início da reconstrução. RS01/H anteriores
  têm contribuição acumulada não isolada por esse ensaio. CSS comum também foi
  comparado na fonte anterior; não houve corte/afrouxamento de budget.
- Intermitência de validação: avisos CSP na rodada ampla de fallback, não
  reproduzidos nas três execuções posteriores, sem origem demonstrada. Não é
  classificada preexistente, nem corrigida por mudança de policy/assert. Registro
  permanece para acompanhamento delimitado; fluxo/seleção/foco/axe passaram e
  execução final do conjunto foi verde com listener de leitura e console estrito.
- Dívida de paridade: PDF/A e conversão visual DOCX→PDF completa não comprovadas
  por este bloco. Testes reais de bytes, snapshot, composição e PDF não substituem
  essa comparação editorial. Corte do ano no campo estreito permanece registrado.
- Incidente de mídia anterior: preservado no relatório anterior; sem inventário
  anterior suficiente para afirmar ausência de perda. As suítes usam bancos TEST
  LAB e MEDIA_ROOT TEST isolado. Verificação HTTP do preview usa DEMO LAB/mídia
  própria isolada; sem semear ou resetar DEMO/DEV.

## Evidências e commits

Capturas reprovadas CSS, capturas finais H/Resumo/Baixar/cadastro/filtros, seis
JSON axe/Chromium AX e csp-resumo.json preservados em `../evidencias/gate-final/`.
Os logs estão em `gate-final/logs/`; incluem falhas,
correções e baseline. JSON de performance em `gate-final/performance/` preserva
corpos/tamanhos/status/consultas/amostras dos seis ensaios e SHA256 dos arquivos
de origem; transcodificados de CP1252 para UTF-8 sem mudar valores.
Log integral final completo: `gate-final/logs/fechar-verificar-integral-final.log`.
Ambiente/comandos em `gate-final/execucao.md`; navegação em `gate-final/LEIA-ME.md`.
`fontes-integradas.json` comprova43/zero divergências e igualdade das897fontes.
Commits históricos H/D13/D16/RS01 constam do pacote das 19:09. Nenhum push/merge.

Commits finais de código na branch de entrega:

- **feb35e2** — domínio/adaptador documental puro (origem e5e48cc).
- **bea84e3** — consumidores, guards, templates funcionais, JS, testes e regras
  documentadas (origem cddc299). O coletor já estava em08d46c7; sua equivalência
  foi preservada, sem duplicar alteração na incorporação.
- Checkpoint documental final (relatório/paridade/capturas/logs/igualdade das
  fontes) terá seu hash indicado na mensagem de entrega; não se tenta gravar
  dentro do próprio commit o hash que só existe depois de criá-lo.

Arquivos principais deste candidato: `gestao/viagens/{views.py,queries.py,
policies.py,assinados.py,pacotes.py,views_pacotes.py,documentos_versoes.py}`,
`dominio/documentos_versoes.py`, parciais `_resumo_documento(s)` e `_resumo_rodape`,
templates de Ofícios e cadastro adiado, `static/js/app.js` e componentes
`dialogo`, `baixar`, `cadastro-rapido`, `seletor-data`; testes HTTP/E2E e
ADR0026–0028. `manifesto-fontes.json` registra 43 fontes com normalização CRLF→LF
e o CSS original como guard, para conferir a incorporação no checkout original.

PDF sintético já testado preservado em
`../evidencias/fechamento-bloco/oficio-sintetico-testado.pdf`; origem/páginas/hash
em `documento.txt`. Bytes, geração e DOCX snapshot reexecutados, sem alegar nova
comparação visual editorial DOCX→PDF ou validação externa PDF/A.

## Próxima etapa

Entregar e avaliar este pacote antes de qualquer avanço. Termos de Autorização
permanece suspenso; nenhuma nova página foi iniciada. As dívidas registradas
ficam fora deste bloco e não geram uma melhoria automática.
