# Ficha de descoberta — Viagens · Ofícios

Situação: **EM FECHAMENTO** — tudo o que não depende de terceiros está implementado e testado;
**não concluído** enquanto faltar a comparação com a referência em execução (dependência
externa). Decisões do dono do produto: [decisoes.md](decisoes.md). Regras finas:
[`docs/parity/oficio.md`](../parity/oficio.md). Fontes da referência (lidas, não copiadas):
`viagens_oficios/` (urls, views, services, models, forms, documents, protocolo_services),
`core/models.py`, fichas `docs/paridade/oficios-*.md` e `justificativas-lista.md`.

**Legenda.** ✅ implementado e testado · 🟡 implementado, evidência parcial · ↔ divergente
(intencional, justificado) · ⛔ bloqueado (dependência externa) · ❔ não investigado.
Toda comparação abaixo foi feita **por leitura do código** da referência; a comparação lado a
lado com a referência em execução está ⛔ (acesso autorizado pendente).

## Matriz por função da referência (rotas de `viagens_oficios/urls.py`)

| Função da referência | Novo | Estado | Evidência |
|---|---|---|---|
| Lista: busca, situações com contagem, paginação 20 | abas (Todos, Rascunhos, Emitidos, Próximas, Cancelados, **Arquivados**) + busca por leituras + paginação 20 | ✅ | `test_views.py::TestListaEPainel`, e2e `test_fluxo_oficio`, `test_preview_demo` (base de 268) |
| Ordenação (número, criação, viagem) | número, data de saída, **data do ofício** (D5) | ✅ | `TestFiltroPorDataDoOficio` |
| Filtro período da viagem | período de saída na gaveta | ✅ | `TestListaEPainel` (filtros), e2e `test_gaveta_de_filtros_filtra_por_protocolo` |
| Filtro período da criação (= data do ofício) | período "Data do ofício" na gaveta (D5) | ✅ | `TestFiltroPorDataDoOficio` (limites, inversão, data inválida, combinações, paginação) |
| Cartão da lista (equipe, placa, trechos, valor, justificativa) | linha compacta + janela de resumo | ↔ pedido do usuário (ADR 0017) | `TestEmissaoEAcoes::test_resumo*`, e2e janela |
| `exportar/` (XLSX, 14 colunas, recorte) | `oficios/exportar/` | ✅ | `TestExportarPlanilha` (consultas fixas: 11 para 268) |
| `novo/` `criar/` (POST cria numerado) | idem; motivo padrão do catálogo | ✅ | `TestNovoEEdicao`, `TestNaFolhaDoOficio::test_oficio_novo_nasce_com_o_motivo_padrao` |
| `editar/` + `autosalvar/` (wizard 6 etapas) | folha única com autosave | ✅ (↔ uma folha em vez de wizard) | `test_views.py::TestNovoEEdicao`, autosave ×3, e2e fluxo |
| Motorista SERVIDOR fora da equipe / MANUAL | "Motorista de fora da equipe" (D3) | ✅ | `TestMotoristaExterno`, `TestMotoristaExternoNaFolha` |
| Servidores com termo de autorização | — | ⛔ depende do módulo Termos | — |
| Conferência (etapa 5) | janela de revisão sobre a folha (`?revisar=1`) | ✅ | `test_revisar_e_emitir_pronto_vai_para_revisao`, e2e emissão |
| `acao/reabrir` (motivo) | `reabrir` (gestor, motivo) | 🟡 serviço testado; **sem botão** desde a saída da página de detalhe — o caminho da tela é "Editar (retificar)" | `test_servicos.py` (reabrir) |
| `acao/cancelar` (motivo) | menu da linha/janela → pedir motivo | ✅ | `TestCicloDeVidaNaTela::test_cancelar_pela_tela_exige_motivo` |
| `acao/reativar` | só gestor, com justificativa (D2) | ✅ (↔ guarda o cancelamento no histórico; a referência apagava o motivo) | `TestReativarCancelado`, `TestCicloDeVidaNaTela` |
| `acao/arquivar` | arquivar/desarquivar (D1) | ✅ (↔ marca reversível; a referência não tinha volta nem tela) | `TestArquivar`, `test_arquivar_leva_para_a_aba_arquivados` |
| `acao/retificar` (liga/desliga marca) | editar emitido → vira retificado; marcador na folha | ↔ decisão anterior do usuário | `test_views.py` (retificar) |
| `acao/complementar` | marcador "Complementar" na folha | ✅ (por campo, não por ação) | `test_dominio_prazos.py` (assunto), folha |
| `acao/excluir` (libera número) | "Excluir rascunho" na janela | ✅ | `test_servicos.py` (excluir/lacuna) |
| `numeracao/` (piso) | tela do gestor com próximo número | ✅ | `TestNumeracaoAnual`, a11y gestor |
| `justificativas/` (lista, nova, editar, excluir, baixar) | `/viagens/justificativas/` (D6) | ✅ | `TestListaDeJustificativas` |
| `catalogos/<tipo>/` (motivos, modelos de justificativa) | `/cadastros/textos-prontos/` | ✅ | `test_textos_prontos.py` (14) |
| `institucional/` (configuração) | — (seed) | ❔→ vai para o módulo 2 (Cadastros) | — |
| `gerar/<tipo>/<formato>/` (DOCX/PDF) | PDF/A-2a na emissão + **DOCX** (D4) | ✅ | `TestEmissaoEAcoes`, `TestBaixarDocx` |
| `visualizar/<tipo>/`, `documento/folha/` | visualizador/editor de documento (ADR 0018) | ✅ | `test_editor*.py`, e2e `test_editor.py` |
| `documento/` (editor completo) | editor no visualizador | ✅ | idem |
| `oficios-do-motorista/` | aviso de conflito de agenda | ✅ (↔ mesmo propósito) | `TestEquipeEViaturaSugerida`, conflitos |
| `termos/…` (por servidor, lote, todos) | — | ⛔ módulo Termos | — |
| `documentos/<uuid>/assinatura/`, `preview/` | — | ⛔ núcleo de Documentos (assinatura) | — |
| Protocolo automático (eProtocolo) | camada simulada + `protocolo_origem` | ⛔ credenciamento (modo simulado não comprova integração) | `test_eprotocolo.py` (13) |

## Entidades (referência × novo)

| Referência | Novo | Estado |
|---|---|---|
| `Oficio` (37 campos) | `Oficio` + `Viajante` + `Trecho` + `BateVolta` | ✅ |
| status RASCUNHO/GERADO/FINALIZADO/ARQUIVADO + `cancelado` | rascunho/emitido/cancelado + `arquivado_em` + `situacao_anterior` | ↔ GERADO/FINALIZADO → emitido (mapear na migração de dados) |
| motorista manual + ofício/protocolo de origem | `motorista_externo*`, `motorista_oficio/protocolo_origem` | ✅ |
| `protocolo_origem` | `protocolo_origem` (manual ao digitar) | ✅ (abertura automática ⛔) |
| `ConfiguracaoNumeracaoOficio` + lacunas | `NumeracaoAnual` + `LacunaNumeracao` | ✅ |
| `ModeloMotivoOficio`, `ModeloJustificativa` | `ModeloTexto` (ordem, ativo, padrão único) | ✅ |
| `Justificativa` (1:1, status, snapshots) | campos do `Oficio` + regra anotada no banco | ↔ sem entidade própria (lista lê o ofício) |
| `assinante` (+ substituições) | chefia da `ConfiguracaoInstitucional` | ❔ substituições: módulo 2 |

## Fluxos exercitados de ponta a ponta

- Criar → preencher (autosave) → revisar → emitir → PDF/A → baixar/DOCX — e2e
  `test_operador_cria_preenche_e_emite_um_oficio`.
- Emitido → editar (retificado) → emitir de novo — `test_views.py` (retificar).
- Cancelar (motivo) → reativar (gestor, justificativa) → mesma situação e número.
- Arquivar → aba Arquivados → desarquivar.
- Justificativa pendente → escrever pela lista → preenchida → apagar → pendente.
- Erros: conflito de versão (folha, autosave × Salvar, justificativa), regra violada, motivo
  ausente, justificativa ausente, sem permissão (operador reativando, consulta escrevendo).

## Divergências e limitações restantes

1. ⛔ Comparação visual/funcional com a referência **em execução** (acesso autorizado).
2. ⛔ eProtocolo real; ⛔ termos por servidor; ⛔ assinatura de documentos.
3. 🟡 Reabrir formal (com motivo) sem botão: o caminho da tela é "Editar (retificar)".
   Decidir se a reabertura formal ainda precisa de botão (pergunta ao usuário).
4. ↔ Configuração institucional e substituições de assinante: módulo 2.
5. D4: uso real do Word ainda sem evidência do usuário.

## Critério de conclusão

Todos os itens ✅/↔ com evidência; ⛔ documentados com o bloqueio exato; regressão completa
verde; capturas antes × depois; desempenho medido; acessibilidade e segurança verificadas.
