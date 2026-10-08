# Crítica independente de RS-02, Resumo e polling

Data: 07/10/2026. Checkout `viagens-tempo-legado`, HEAD observado `d5663f2`, alterações locais da integração informadas como congeladas pelo coordenador por volta de 18:49:44. Revisão somente de leitura do produto; este documento é a única edição desta tarefa. Instruções lidas: `.claude/agents/revisor-cetico.md` e `docs/product/oficios-documentos-versoes.md`.

## Achados concretos

### P1 — menu externo ao Resumo continua oferecendo minuta de emitido indisponível

`gestao/viagens/templates/viagens/oficios/_menu_oficio.html:29-33` usa `else` quando `m.pdf` não existe. Não verifica `m.minuta`, que a política agora retorna falso para emitido gerando/falhou e cancelado. Assim, v1 pronta + v2 gerando/falhou continua oferecendo “Ver minuta” na lista, com URL da prévia dos dados vivos. O Resumo não sofre esse ramo porque passa `no_resumo=True`.

Evidência independente: `render_to_string` do template real, com conexão explicitamente bloqueada e DTO `pdf=None, minuta=False`, produziu `Ver minuta no HTML=True`. O teste `test_corrente_nao_promove_v1_no_menu_anexacao_docx_ou_pacote` verifica o DTO, mas não este HTML.

Plano mínimo: trocar o ramo por `elif m.minuta`; testar HTML real do menu/lista nos estados gerando, falhou, cancelado e rascunho. Não transformar ausência de PDF em prévia de dados vivos.

### P1 — download seleciona novamente via vazia rejeitada pela projeção

`gestao/viagens/views.py:1034-1037` escolhe a primeira via não revogada por relação e chama `resposta_da_via` sem conferir caminho. Com original corrente pronto/caminho preenchido e via exata não revogada/arquivo vazio, a projeção corretamente oferece o original. O link por ID do Resumo/menu, porém, seleciona essa mesma via vazia no download. `FieldFile.open` lança `ValueError`, resultando em erro de servidor.

Evidência independente: despacho da função real com objetos em memória, ORM substituído, conexão bloqueada e `ViaAssinada` Django real com `arquivo=""`: `ValueError: The 'arquivo' attribute has no file associated with it.` Nenhuma leitura de storage foi realizada. O teste integrado de caminho vazio/branco verifica seleção, mas não o GET correspondente.

Plano mínimo: filtrar a via automática por dono/tipo exatos e caminho não vazio antes de substituí-la pelo original. Testar GET com via vazia/branca e original real no LAB. Preservar a leitura histórica pelo ID solicitado; exigir versão corrente aqui impediria a leitura autorizada de históricos.

O mesmo ramo possui uma falha **pré-existente e condicionada a vínculo inconsistente**, relevante para autorização: uma via cujo dono é Ofício B e cujo `documento_id` aponta para Documento de A pode ser devolvida ao leitor autorizado somente para A. As constraints atuais de `ViaAssinada` não exigem igualdade entre dono/tipo da via e do documento. Reproduzi o despacho com objetos em memória: autorização permitiu apenas A, mas `resposta_da_via` recebeu a via de B. Isso não comprova criação desse vínculo pelo fluxo normal, que seleciona o documento corretamente. Completar a defesa com validação de dono/tipo e autorização da via; fixture LAB de FK cruzada deve negar a substituição e nunca expor B.

### P2 — polling tenta devolver foco a item oculto de Mais ações

`static/js/componentes/dialogo.js:269-270` restaura qualquer elemento equivalente por ID, sem verificar sua operabilidade. `_resumo_rodape.html` renderiza o painel do menu com `hidden`; `menu.js` inicializa o novo gatilho fechado. Se a pessoa estiver num item com ID do menu aberto quando o worker concluir, a troca remove esse menu e tenta focar o item equivalente dentro do painel novo oculto. O ramo alternativo de foco no rodapé não roda porque o elemento existe.

Reprodução mínima para navegador: v2 gerando; abrir Mais ações; focar com teclado um item com ID; concluir worker; aguardar polling; verificar foco em controle visível/operável. A cadeia de código demonstra o problema, mas não executei essa reprodução no navegador nesta tarefa. O E2E atual preserva foco no campo de cópia, não dentro de menu aberto.

Plano mínimo: restaurar ao gatilho Mais ações se o item estiver em painel/grupo oculto, ou preservar explicitamente a abertura e o grupo do menu. Verificar ainda itens sem ID e remoção do item após mudança de estado.

### P2 — pacote omite estado de justificativa esperada mas inexistente

`gestao/viagens/pacotes.py:63-65` inclui justificativa somente se houver identidade corrente. Com snapshot do ofício contendo texto de justificativa, mas sem Documento desse tipo, o domínio emite aviso explícito; o pacote o descarta e devolve apenas ofício. No diálogo não há indicação da parte esperada ausente, e a pessoa pode baixar o conjunto apresentado como completo.

Evidência independente: execução da função real de construção com documento materializado, conexão bloqueada e consulta de vias substituída por mapa vazio: itens `['oficio']`; projeção com aviso `A justificativa desta emissão está indisponível. Confira o documento emitido.` É estado incompleto explicitamente previsto na regra; não proponho inferir igualdade de versões ou promover uma justificativa antiga.

Plano mínimo: preservar a indicação de indisponibilidade no pacote, por item não disponível ou aviso explícito no diálogo, mantendo ausência quando o snapshot disser texto vazio. Testar presente/ausente/indeterminado e o comportamento do POST correspondente.

## Evidência positiva e limites

- Executei diretamente os testes puros de `test_documentos_versoes.py` e `test_documentos_projecao.py`: **81 passed in 3.54s**. Esses testes não pedem fixture de banco; nenhum banco/navegador foi iniciado pela revisão.
- Compilei SQL de `com_dados_de_lista` com `connection.ensure_connection` substituída por erro. As subconsultas das anotações de via correlacionam ao `viagens_oficio.id` externo e ao documento exato; não encontrei confusão com PK de via nessa compilação. Compilar não mede quantidade, latência ou plano de execução.
- Li domínio, adaptador, queries, políticas, seleção/anexação de assinados, pacotes, `_contexto_resumo`, `_vias_do_oficio`, DOCX, parciais novos, hook de diálogo e preservação de cópia. DOCX gerando/falhou não cai em dados vivos. A cópia mantém a maior emissão mesmo pendente, conforme RS-01. Não encontrei alteração de permissão na entrada autorizada dessas views.
- Inspecionei os consumidores `pacote_prestacao`, `carimbo` e `viagem_conferencia` de `vigente`: passam a rejeitar assinatura antiga quando a maior versão está pendente/falha, coerente com a regra. Não executei regressão funcional da prestação; exige testes de pacote/carimbo/conferência com v1 assinada + v2 gerando/falhou e v2 pronta/exata.
- HTTP, browser, foco real, abort de polling, capturas 360/1440, bytes de arquivos, budgets SQL/desempenho e paridade visual não foram validados por este revisor. As reproduções sem ORM não substituem os testes reais necessários acima. Não há aprovação estética ou declaração de entrega pronta neste documento.
