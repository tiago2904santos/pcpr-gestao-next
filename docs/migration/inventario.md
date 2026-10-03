# Inventário cruzado — referência × sistema novo

Levantado em 03/10/2026 lendo o código da referência (clone raso de
`Sistema-de-Gest-o-de-Eventos-Sociais`, commit `53dbf3f` de 29/09/2026) com um script de AST
(rotas `path()`, classes de modelo, telas) e o código de `gestao/`. A referência em execução
**não** foi navegada nesta rodada (sem `REF_USER`/`REF_PASS` no ambiente) — itens que só se
confirmam olhando a tela estão marcados `DESCONHECIDO` em [parity.md](parity.md).

## Tamanho

| | Referência | Novo |
|---|---:|---:|
| Apps de domínio | 23 | 6 (`cadastros`, `identidade`, `painel`, `plataforma`, `ui_lab`, `viagens`) |
| Rotas (`path`) | ~420 | 56 |
| Modelos | ~120 | 36 |

A referência guarda também fichas de paridade por tela em `docs/paridade/*.md`
(ofícios-form/lista/catálogos/detalhe/menus, roteiros, termos, prestações, cadastros…) e
validações gravadas em JSON. São a melhor fonte de "o que a tela faz" antes de abrir a tela.

## Mapa por módulo

Legenda de situação no novo: **Concluído** · **Avançado** (núcleo pronto, lacunas listadas) ·
**Parcial** · **Ausente**.

### Plataforma e identidade
| | Referência | Novo |
|---|---|---|
| Páginas | central de módulos (`/`), notificações (+ marcar lidas, abrir), conflitos de agenda, triagem de e-mail (ler/encaminhar), buscar endereço; conta: entrar, sair, alterar senha, **recuperar senha** (4 telas), **usuários** (lista, novo, editar, ativar/desativar) | `/` início, `/notificacoes/`, busca global, entrar, sair, alterar senha, 403/404/500, saúde |
| Entidades | Setor, Modulo, User, AssinaturaAgenda, PautaSemanal, Notificacao, MemoriaLeitura, Feriado, RegistroAuditoria, LogAuditoria | Usuario, TentativaAcesso, EventoAuditoria (trigger + hash), MensagemOutbox |
| Integrações | e-mail (SMTP), triagem/leitura de mensagens, ViaCEP/Nominatim | — |
| Situação | — | **Parcial** |

### Viagens — Cadastros (`viagens_cadastros` + `cadastros`)
| | Referência | Novo |
|---|---|---|
| Páginas | índice; CRUD genérico por *slug* (servidores, viaturas, unidades, cargos, combustíveis) com **definir padrão**; tabela de diárias (CRUD); consulta CEP; municípios (busca); configuração do sistema + assinaturas e substituições | consulta de servidores, viaturas e tabela de diárias; API de municípios |
| Entidades | Unidade, Cargo, Combustivel, Servidor, Viatura, TabelaDiaria, ConfiguracaoSistema (32 campos), AssinaturaConfiguracao, AssinaturaSubstituicao, Estado, Municipio | Unidade, Cargo, Combustivel, Servidor, Viatura, Municipio, TabelaDiaria, Lotacao, ModeloTexto, ConfiguracaoInstitucional |
| Situação | — | **Parcial** (sem cadastro/edição em tela) |

### Viagens — Ofícios (`viagens_oficios`)
| | Referência | Novo |
|---|---|---|
| Páginas | lista (+ exportar), novo/criar, editar (autosalvar), ações `reabrir/cancelar/reativar/arquivar/retificar/complementar/excluir`, **numeração** (piso), **justificativas** (lista/nova/editar/excluir/baixar), **institucional**, **catálogos** por tipo (motivos, modelos de justificativa…), ofícios do motorista, gerar por tipo×formato (DOCX/PDF), documento/folha, visualizar, termos (por servidor, lote, todos em PDF), assinatura e prévia de artefato | lista com abas, busca inteligente e filtros avançados; janela de resumo; novo; editor em seções com autosave; equipe; diárias; revisão/emissão; retificar, reabrir, cancelar, excluir; minuta; documentos (PDF/A versionado); editor de documento (campos, textos, páginas, presença, restaurar) |
| Entidades | Oficio (37 campos, inclui protocolo_origem/situação, motorista manual, transporte manual, retificado/complementar_documento, servidores_termo_autorizacao), ConfiguracaoNumeracaoOficio, OficioNumeroLacuna, ModeloMotivoOficio, ModeloJustificativa, Justificativa | Oficio, Viajante, Trecho, Documento, EdicaoDocumento, Historico, NumeracaoAnual, LacunaNumeracao |
| Documentos | ofício, justificativa, termos (DOCX/PDF) | ofício e justificativa (PDF/A-2a, SHA-256) |
| Integrações | eProtocolo (abrir protocolo ao gravar; origem MANUAL/EPROTOCOLO/TREINAMENTO/SIMULADO) | nenhuma (protocolo digitado) |
| Situação | — | **Avançado** — ficha: [oficios.md](oficios.md) |

### Viagens — Roteiros (`viagens_roteiros`)
| | Referência | Novo |
|---|---|---|
| Páginas | lista, novo, editar, **detalhe**, dados (JSON), prévia de diárias, **calcular rota**, **estimar trecho**, autosave, calcular, cancelar, reativar, excluir | lista com abas, novo, editar, prévias (diárias, trechos), autosave, rota, cancelar, reativar, excluir, criar ofício, "usado em N ofícios" |
| Entidades | Roteiro, RoteiroDestino, RoteiroTrecho, RoteiroDiariaComponente, DistanciaMunicipios | Roteiro, TrechoRoteiro, BateVolta*, DistanciaMunicipios |
| Integrações | OpenRouteService (rota, km, tempo) com cache | rota via API própria + cache `DistanciaMunicipios` |
| Situação | — | **Avançado** |

### Viagens — Termos de autorização (`viagens_termos`)
Páginas: lista, novo, editar, prévia (geral e por servidor), baixar, todos em PDF, lote,
**por viatura**, por servidor, ações; API de busca de ofícios. Entidade: TermoAutorizacao
(oficio, viagem, destino, destinos extras, período, servidores, viatura). **Novo: Ausente.**

### Viagens — Ordens de serviço (`viagens_ordens`)
Páginas: lista, nova, editar (autosalvar), ações, gerar, assinatura; API de ofícios.
Entidades: OrdemServico (tipo de necessidade, funções: motorista, técnico, montagem, escolta,
cerimonial, preparação), OrdemServicoDestino, lacunas de numeração. **Novo: Ausente.**

### Viagens — Planos de trabalho (`viagens_planos`)
Páginas: lista, criar, editar (autosalvar), ações, calcular (diárias), eventos
(adicionar/editar/remover), visualizar, resultados, gerar. Entidades: PlanoTrabalho
(48 campos: programa, coordenadores adm/op, multievento, diárias combinadas, atividades,
metas), EventoPlano, PlanoDestino, EfetivoPlano/EfetivoEvento (unidade × cargo × quantidade),
AtividadePlanoTrabalho, PresetAtividades, ResultadoAtividade, ProgramaSolicitante,
HorarioAtendimento. **Novo: Ausente.**

### Viagens — Viagem / assistente (`viagens_viagem`)
Páginas: lista, criar, painel, etapas 1–5, coerência, repetir, gerar documentos, baixar tudo
(ZIP), anexos da solicitação. Entidades: Viagem, TipoViagem, EquipePrevista,
ViagemDocumentoSolicitacao. Agrega solicitação → roteiros → ofícios → PT/OS → termos.
**Novo: Ausente.**

### Viagens — Prestação de contas (`viagens_prestacoes`, 68 rotas)
Por ofício e por servidor: **Diário de bordo (etapa 1)** → RT → documentos/comprovantes →
consolidado/pacote; despacho e ofício assinados, carimbo; importação de processo do
eProtocolo (aplicar/descartar/desfazer); modelos de texto do RT; **diário no celular por
token** (PWA: `sw.js`, manifest) sem login; exportar XLSX. Entidades: PrestacaoContas,
PrestacaoServidor, PrestacaoDocumentoAnexo, ImportacaoProcesso, CarimboSolicitacao,
RelatorioTecnico, DiarioBordo(+Trecho), ModeloTextoRelatorioTecnico, LinkDiarioCampo,
LancamentoDiarioCampo. **Novo: Ausente.**

### Documentos (núcleo, `documentos`)
Abrir/baixar, **conferir assinado**, editor (página, folha, embutido, campos, blocos, quebras,
páginas, parágrafos, textos, presença, completo + salvar/modelo/restaurar), **modelos de
documento** por módulo/tipo. Entidades: DocumentoArtefato, DocumentoAssinaturaVersao,
DocumentoBloco, DocumentoVersaoEditada, ModeloTextoDocumento. **Novo: Parcial** (editor de
documento do ofício — ADR 0018; sem conferência de assinado nem modelos por tipo).

### Eventos Sociais (`solicitacoes` + `cadastros`)
Lista, nova, **ler e-mail**, exportar, sugestão de tipo, solicitantes, editar, enviar, excluir,
anexos, despachar (DG), concluir, cancelar evento, transferir, duplicar, **gerar viagem**,
consultar protocolo. Cadastros: tipo de evento (+ modelo), serviço, equipe, órgão, região,
unidade móvel, texto de despacho, municípios. **Novo: Ausente.**

### ASCOM
- Palestras e eventos (`demandas_eventos`, 19 rotas + pedido público por token): Tema,
  Palestrante, RespostaPadrao, DemandaEvento, HistoricoDemanda.
- Publicações (12 rotas): Responsavel, Unidade, Publicacao, HistoricoPublicacao.
- Imprensa (12 rotas): Responsavel, Veiculo, Atendimento, HistoricoAtendimento.
**Novo: Ausente.**

### Coffee Break (61 rotas + portal do fornecedor por token)
Fornecedor, Contrato, Aditivo, Configuração, Lote, Solicitação, Histórico, Ocorrência de
entrega, Certidão, Link e Envio ao fornecedor. **Novo: Ausente.**

### Agenda, relatórios, painel
Agenda: painel, eventos, detalhe por fonte, escala, pauta PDF, feed ICS por token,
assinatura. Relatórios: painel + exportar. Dashboard. **Novo: Ausente** (só aviso de conflito
entre ofícios).

### Migração de dados (`migracao_legado`, `migracao_relatorios`)
Lote/Etapa/Registro/Vínculo — ETL idempotente do sistema antigo. **Novo: Ausente** (planejar
antes da virada).

## Dependências entre módulos

```
Plataforma/Identidade ─┬─> Cadastros ─┬─> Roteiros ──┐
                       │              ├─> Ofícios <──┘──┬─> Termos
                       │              │                 ├─> Ordens de serviço
                       │              ├─> Planos de trabalho
                       │              └─> (Documentos núcleo: transversal)
                       │
                       └─> Viagem (assistente) <── Ofícios + Termos + OS + PT + Roteiros
                                 └─> Prestação de contas (por ofício/servidor) ─> Diário de campo
Eventos Sociais ──(gerar viagem)──> Viagem
eProtocolo: Ofícios (abrir/consultar), Prestação (importar processo), Eventos (consultar)
```
