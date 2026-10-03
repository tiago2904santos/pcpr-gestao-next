# Ficha de descoberta — Viagens · Ofícios

Situação: **EM ANDAMENTO** (módulo 1 do [roadmap](roadmap.md)). Matriz detalhada de regras:
[`docs/parity/oficio.md`](../parity/oficio.md) (revisão de 01/10/2026). Fontes da referência:
`viagens_oficios/` (models, views, services, protocolo_services), fichas
`docs/paridade/oficios-{lista,form,menus,detalhe,catalogos}.md` e
`justificativas-lista.md`, `docs/EPROTOCOLO_PROTOCOLO_AUTOMATICO.md`,
`docs/FASE_4_OFICIOS_JUSTIFICATIVAS_TERMOS.md`.

## Entidades

| Referência | Novo | Observação |
|---|---|---|
| `Oficio` (37 campos) | `Oficio` (32) + `Viajante` + `Trecho` + `BateVolta` | Trechos embutidos + roteiro opcional; motorista é viajante marcado |
| `protocolo_origem` / `protocolo_situacao` / `protocolo_criado_em` | — | Entra com a integração eProtocolo (I1) |
| motorista manual (6 campos), `motorista_oficio_referencia`, `motorista_protocolo_ref` | — | **PENDENTE** (decisão D-OF-3) |
| transporte manual (placa, modelo, combustível, tipo) | `transporte_placa/descricao/combustivel`, `tipo_transporte` | IGUAL em essência |
| `servidores_termo_autorizacao` | — | Depende do módulo Termos |
| `retificado_documento` / `complementar_documento` | `marcador` (Nenhum/Retificado/Complementar) | MELHORADO (um campo, regra no domínio) |
| `assinante` | `ConfiguracaoInstitucional.chefia_*` | DIFERENÇA INTENCIONAL — assinante por unidade, sem substituições ainda |
| `ConfiguracaoNumeracaoOficio` + `OficioNumeroLacuna` | `NumeracaoAnual` + `LacunaNumeracao` | IGUAL (algoritmo, D5); **tela do piso ausente** |
| `ModeloMotivoOficio` (nome, texto, ordem, ativo, padrão único) | `ModeloTexto(tipo=motivo)` (nome, texto, ordem, ativo, padrão único por tipo no banco, padrao_sistema) | **IGUAL** (03/10/2026) — `test_textos_prontos.py::TestServico` |
| `ModeloJustificativa` | `ModeloTexto(tipo=justificativa)` | **IGUAL** |
| `Justificativa` (1:1, status, snapshots da regra) | campos no `Oficio` + documento `justificativa` | DIFERENÇA INTENCIONAL (sem entidade própria); lista de justificativas: **PENDENTE** |
| status `RASCUNHO/GERADO/FINALIZADO/ARQUIVADO` + `cancelado` ortogonal | `rascunho/emitido/cancelado` | DIFERENÇA INTENCIONAL; arquivar/reativar **PENDENTE** |

## Telas

| Tela / função | Referência | Novo | Paridade |
|---|---|---|---|
| Lista: busca, situação (4 combináveis + contagem), ordenação (6), período da viagem, período da criação, paginação 20 | sim | abas de situação, **busca inteligente por leitura** (número/protocolo/placa/destino/servidor), filtros avançados (período, protocolo, veículo, faixa de diárias), ordenação | MELHORADO; período de **criação** e **ordenação por criação**: DESCONHECIDO se ainda necessários (ver D-OF-5) |
| Cartão da lista com equipe, placa, trechos, valor, justificativa | cartão rico | linha compacta + **janela de resumo** com tudo isso (ADR 0017) | DIFERENÇA INTENCIONAL (pedido do usuário) |
| Exportar (CSV) | `exportar/` | — | **PENDENTE** |
| Novo (POST cria rascunho numerado) | sim | sim | IGUAL |
| Editor: identidade, motivo (com modelo; ofício novo nasce com o padrão), custeio, equipe, termo por viajante, transporte, motorista externo, porte de arma, roteiro, prazo/justificativa, diárias | wizard de 6 páginas com autosave | uma folha em seções com autosave, roteiro cadastrado aplicável, prévia de diárias | MELHORADO; motorista externo e termo por viajante PENDENTES |
| Conferência/resumo antes de emitir | etapa 5 | janela de resumo em modo revisão sobre a folha (`?revisar=1`), com destinatário, quem assina, justificativa e Emitir | **MELHORADO** — `test_views.py::test_revisar_e_emitir_pronto_vai_para_revisao`, e2e `test_operador_cria_preenche_e_emite_um_oficio` |
| Ações: reabrir, cancelar, reativar, arquivar, retificar, complementar, excluir | sim | reabrir, cancelar, retificar (vira retificado ao editar emitido), excluir | reativar/arquivar/complementar PENDENTES |
| Documentos: ofício, justificativa (visualizar, PDF, DOCX) | DOCX + PDF | PDF/A-2a versionado, minuta, visualizador em nova aba, editor de documento | MELHORADO; DOCX: DIFERENÇA INTENCIONAL (ADR 0008) — confirmar com o usuário |
| Catálogos de motivo e de justificativa (CRUD, padrão, ordem, ativo) | sim | `/cadastros/textos-prontos/` (abas por tipo, busca, janela novo/editar, usar como padrão, desativar/reativar, excluir só gestor e nunca o do sistema) + seletor "Texto pronto" na folha que preenche o campo (confirma antes de substituir) + "Guardar como texto pronto" | **IGUAL + MELHORADO** — `test_textos_prontos.py` |
| Numeração (piso anual) | tela do gestor | — | **PENDENTE** |
| Configuração institucional | tela | — (seed) | **PENDENTE** (pode ir com Cadastros) |
| Justificativas (lista própria) | sim | — | PENDENTE — avaliar se a aba/filtro "justificativa pendente" na lista de ofícios resolve (D-OF-6) |
| Ofícios do motorista | API para conflito | aviso de conflito de servidor/viatura | IGUAL em propósito |
| Termos por ofício | sim | — | vai com o módulo Termos |

## Fluxos

- Principal: Novo → preencher (autosave) → pronto para emitir → revisar (janela) → emitir →
  PDF/A pela outbox → baixar/visualizar.
- Alternativos: editar emitido → vira **retificado** (rascunho + marcador, histórico REABERTO);
  reabrir com motivo; cancelar com motivo; excluir rascunho (libera número como lacuna).
- Exceções: conflito de versão no autosave/salvar (`ConflitoDeEdicao`); regra violada;
  ano da data ≠ ano do número (bloqueia, D3).
- Permissões: `policies.py` (`pode_editar`, `pode_emitir`, `pode_retificar`, `pode_cancelar`…),
  escopo por unidade (lotação).

## Documentos

Ofício e justificativa: dados congelados no `Documento` (JSON), PDF/A-2a, SHA-256, versões
imutáveis; edições do texto em `EdicaoDocumento` (ADR 0018). Termos: módulo próprio.

## Integrações

- **eProtocolo**: referência abre protocolo ao gravar quando o campo está vazio (simulado sem
  credencial, treinamento marcado como não oficial, trava de somente leitura). Novo: nenhuma.
  Plano em [`docs/integrations/eprotocolo.md`](../integrations/eprotocolo.md).
- Central de Viagens: nenhuma em ambos (ver `docs/integrations/central-de-viagens.md`).

## Decisões pendentes (dono do produto)

- **D-OF-1** Arquivar: precisa existir? (referência tem estado ARQUIVADO). Sugestão: aba
  "Arquivados" via flag, sem novo estado.
- **D-OF-2** Reativar cancelado: liberar para gestor? (referência permite).
- **D-OF-3** Motorista externo (fora do cadastro) com ofício/protocolo de origem: migrar?
- **D-OF-4** DOCX editável: o editor de documento (ADR 0018) substitui a necessidade?
- **D-OF-5** Filtro por período de **criação** e ordenação por criação: ainda usados?
- **D-OF-6** Lista própria de justificativas ou filtro na lista de ofícios?
- **D-OF-7** Rótulo "Autorização" para marcador Nenhum conflita com o assunto
  Autorização/Convalidação — manter ou "Documento original"?

## Critério de conclusão deste módulo

Itens PENDENTES sem decisão pendente implementados; decisões registradas; testes rápidos +
navegador verdes; capturas 360/1440 e axe das telas tocadas; orçamento de consultas das
listas com o DEMO populoso; paridade comparada com a referência **em execução** (exige
`REF_USER`/`REF_PASS` ou sessão aberta pelo usuário no navegador do app).
