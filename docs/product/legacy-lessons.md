# Lições da referência e decisões pendentes

## 1. Problemas observados na referência e resposta do sistema novo

| Problema (referência) | Como o novo trata |
|---|---|
| Qualquer usuário que via um evento podia cancelá-lo (falha de autorização, P0) | Autorização centralizada em `policies.py`; cancelar exige permissão própria; views não checam papel à mão |
| Dossiês visíveis a todos; permissões espalhadas | Escopo por unidade de lotação; outra unidade → 404 |
| Invariantes só na camada de serviço | **Constraints no banco**: número único por ano, protocolo 9 dígitos, motivo de cancelamento, um motorista, trecho chega depois de sair, versão de documento única |
| Edições concorrentes sobrescreviam dados | Concorrência otimista por `versao` com mensagem clara |
| Trilha de auditoria por *signals* (contornável) | Trigger no PostgreSQL com cadeia de hash; tabela imutável |
| Geração síncrona de documentos segurando a requisição; cadeia Word → LibreOffice frágil | PDF/A-2a por WeasyPrint, assíncrono via outbox, idempotente |
| Documentos regeráveis sem versão clara | Versões imutáveis com instantâneo dos dados e SHA-256 |
| CSS (~3.300 linhas) e JS (~1.700) monolíticos; cores fora de tokens | Design System com tokens obrigatórios (teste reprova hex soltos), UI Lab, CSP estrita sem inline |
| Foco de teclado invisível; cinza sem contraste; erros não associados; mensagens não anunciadas | Testes de acessibilidade (axe) obrigatórios por tela |
| Linha da lista não abria o registro; ação principal no meio da página; barra com 12 itens | Arquétipos de tela; menu superior com no máximo 7 entradas por módulo |
| Sem páginas 404/500 próprias | Páginas de erro 403/404/500 da plataforma |
| Viagens sem painel | Painel de Viagens (rascunhos, próximas viagens) e indicadores na central |
| 44 roteiros rascunho vazios sem filtro; rascunho vazio reaproveitado após 30 min | Rascunho pode ser excluído (libera número); roteiro embutido no ofício |
| Horários UTC × local (agenda mostrava dia errado) | Domínio recebe instantes no fuso local da sede; serviço converte (`localtime`) |
| 15%/30% gravados na tabela podiam divergir do arredondamento | Derivados do valor de 24 h na hora do cálculo |
| Cálculo de diárias com divisão/remultiplicação por efetivo (erro de centavo) | Contagem viva da equipe; congelada no instantâneo da emissão |
| Exclusão de qualquer ofício (bloqueada só por FK) | Só rascunho sem documento |
| "Suíte verde ≠ tela conferida" (defeitos só vistos no navegador) | Testes E2E, visuais e capturas 360–1440 px obrigatórios |
| Migração de dados no mesmo arquivo da de esquema | Regra mantida como lição (a confirmar no processo do novo) |

Elogiados na referência — **manter**: leitura de e-mail que preenche e destaca campos;
painel da viagem dizendo "o que falta, por área"; fila "O que fazer hoje"; editor de roteiro
com "como foi calculado"; tela de alterar senha.

## 2. Lacunas do novo em relação à referência (Ofício)

| # | Lacuna | Severidade | Situação no código atual |
|---|---|---|---|
| R1 | Assunto Convalidação / Retificado / Complementar | Alta | **Resolvida** após a matriz de paridade: `dominio/assunto.py` + campo `marcador`; template usa rótulo e termo derivados |
| R2 | Motorista externo à equipe (com ofício/protocolo do motorista); motorista hoje entra nas diárias | Alta | Aberta |
| R3 | Bate-volta perdia voltas intermediárias ao reeditar | Alta | **Resolvida**: `forms.iniciais_do_roteiro` trata só o último trecho como retorno; coberta por `TestRoteiroComVoltaIntermediaria` (`viagens/tests/test_views.py`) |
| R4 | Termos de autorização | Alta | Aberta |
| R5 | Assinatura (upload, versão assinada, revogação) | Alta | Aberta |
| R6 | Editor de documento / DOCX | Média-alta | Aberta |
| R7 | eProtocolo (painel de cópia, abertura automática, origem) | Média | Aberta |
| R8 | Modelos de motivo (cadastro existe, sem uso em tela) | Média | Aberta |
| R9 | Marcadores `{destino}`, `{periodo}`… em modelos de justificativa (hoje copiados literalmente) | Média | Aberta |
| R10 | Assinante por ofício e substituto no período | Média | Aberta |
| R11 | Arquivar; reativar cancelado | Média | Aberta |
| R12 | Tela do piso da numeração (permissão existe, sem tela) | Baixa-média | Aberta |
| R13 | Rota, distâncias, mapa, tempo sugerido | Média | Decisão de fase |
| R14 | Roteiro reutilizável e vínculo com Viagem | — | Decisão pendente |
| R15 | Conflitos com termos, OS, solicitações, palestras, extrajornada | Média | Aberta (só ofícios) |
| R16 | Filtros de período/ano/ordenação; autosave | Baixa | Aberta |
| R17 | Justificativa com data, assinante e status próprios | Baixa-média | Aberta |

Outros riscos registrados: `get_or_create` do primeiro número do ano pode colidir sob corrida
(IntegrityError não tratado); excluir rascunho apaga o `Historico` (fica só o trigger);
transporte "outro meio" com placa não exige motorista (confirmar regra).

## 3. Decisões pendentes com o dono do produto

| # | Pergunta | Referência | Novo hoje | Impacto |
|---|---|---|---|---|
| **a** | **Protocolo é obrigatório para emitir?** | Bloqueante para finalizar ("Informe o protocolo.") | Aviso não bloqueante | Ofício emitido sem protocolo; afeta a integração eProtocolo |
| **b** | **Formato da numeração: `03d` ou `02d`?** | `05/2026` | `005/2026` | Texto impresso, busca e migração; confirmar padrão oficial |
| **c** | **Data do ofício fora do ano do número: erro ou aviso?** | Aviso ao finalizar | Erro ao salvar | Rascunho de dezembro emitido em janeiro exige excluir e recriar (perde o número) |
| **d** | **Unificar GERADO + FINALIZADO em "Emitido"?** | 4 estados + cancelado ortogonal | rascunho/emitido/cancelado | Simplifica; exige mapeamento na migração e definição de onde entram assinatura e arquivamento |

Também em aberto (da matriz de paridade):
- Numeração: reaproveitar **qualquer** buraco (novo) ou só lacunas de exclusão (referência)?
  Afeta dados migrados com saltos e o livro compartilhado com o Coffee Break.
- Justificativa: gerar documento sempre que há texto (novo) ou só quando exigida (referência)?
- DOCX: oferecer documento editável fora do sistema?
- Efetivo ≠ equipe listada (snapshot de quantidade de servidores da referência)?
- Tabelas históricas de diária com 15%/30% gravados que não batem com o arredondamento.
- Base legal e vigência da tabela de diárias (R$ 290,55 / 371,26 / 468,12).
