# Módulos

Legenda de situação: **Implementado no piloto** · **Parcial** · **Planejado** · **A confirmar**.
Telas citadas da referência são descritas por função (não por implementação).

## Plataforma e identidade

| | Referência | Novo |
|---|---|---|
| Propósito | Central de módulos (cartões com 3 métricas), notificações (sino), conflitos de agenda, triagem de e-mail, busca de endereço | Central de módulos, notificações (tela), busca global de ofícios, páginas de erro 403/404/500, saúde |
| Telas | `/` central, notificações, conflitos, login/logout, recuperação e troca de senha (forçada se `deve_trocar_senha`), gestão de usuários (perfil + setores) | `/` início, `/notificacoes/`, `/conta/entrar/`, `/conta/sair/`, `/conta/senha/` |
| Entidades | Setor, Módulo, Usuário, Notificação, MemoriaLeitura, Feriado | Usuario, TentativaAcesso, EventoAuditoria, MensagemOutbox |
| Situação | — | **Parcial** — gestão de usuários em tela, recuperação de senha por e-mail, triagem de e-mail: planejado |

## Viagens — Ofícios (núcleo do piloto)

- **Propósito**: montar e emitir o ofício de viagem com cálculo de diárias e justificativa.
- **Telas (novo)**: painel de Viagens; lista com abas de situação e busca; novo ofício (data +
  motivo); editor em seções (Dados, Equipe, Transporte, Roteiro, Diárias, Justificativa,
  Documentos, Registro/Histórico) com painel de pendências; revisão da emissão; detalhe;
  minuta PDF; download de documentos; reabrir, cancelar, excluir.
- **Telas (referência)**: lista com filtros de período/ano/ordenação, formulário longo com
  autosave, numeração anual, justificativas, configuração institucional, catálogos de
  motivos/modelos, ações (reabrir, cancelar, reativar, arquivar, retificar, complementar,
  excluir), geração DOCX/PDF, termos.
- **Entidades**: Oficio, Viajante, Trecho, Documento, Historico, NumeracaoAnual.
- **Situação**: **Implementado no piloto**. Faltam (ver [legacy-lessons.md](legacy-lessons.md)):
  arquivar, reativar cancelado, tela de piso da numeração, motorista externo, termos,
  assinatura, eProtocolo, filtros de período/ano.

## Viagens — Roteiros e diárias

- **Propósito**: definir trechos e calcular diárias de forma auditável.
- **Referência**: roteiro como entidade própria (reutilizável), editor com mapa, trechos
  ida/volta, "como foi calculado", histórico, cálculo de rota (OpenRouteService), cache de
  distâncias, autosave.
- **Novo**: trechos embutidos no ofício (até 10 destinos + retorno); cálculo no domínio puro
  `gestao/viagens/dominio/diarias.py`, gravado como instantâneo no ofício.
- **Situação**: **Parcial** — roteiro reutilizável, mapa, km e tempo sugerido: planejado.

## Viagens — Cadastros

| Cadastro | Referência | Novo |
|---|---|---|
| Servidor | nome, cargo, CPF, RG/sem RG, telefone, unidade; status derivado | modelo + tela de consulta |
| Viatura | placa única, modelo, combustível, tipo, unidade, motoristas | modelo + tela de consulta |
| Unidade, Cargo, Combustível | catálogos com padrão | modelos (sem tela própria) |
| Tabela de diárias | faixa, vigência, 24h/15%/30% gravados | faixa, vigência, 24h, norma; 15/30% derivados; tela de consulta |
| Município | IBGE, estado, região, capital, lat/long | IBGE (código, nome, UF) carregado de CSV oficial |
| Configuração | `ConfiguracaoSistema` por setor + assinaturas e substituições | `ConfiguracaoInstitucional` por unidade (cabeçalho, sede, chefia, destinatário, prazo) |
| Modelos de texto | motivos e justificativas com marcadores | `ModeloTexto` (motivo, justificativa), sem marcadores |

**Situação**: **Parcial** — cadastro/edição em tela: planejado (hoje via carga/seed).

## Viagens — demais submódulos (Planejado)

| Submódulo | Propósito (referência) | Principais telas | Entidades |
|---|---|---|---|
| Viagem (assistente) | Amarra solicitação → roteiros → ofícios → PT/OS → termos; painel "o que falta, por área" | lista, painel, 5 etapas, coerência, geração em lote, ZIP | Viagem, EquipePrevista, ViagemDocumentoSolicitacao |
| Termos de autorização | Termo individual, genérico, por viatura, lote ZIP/PDF | lista, form, prévia | TermoAutorizacao |
| Ordens de serviço | OS com tipo de necessidade e funções | lista, form, geração | OrdemServico |
| Planos de trabalho | PT simples/multievento, metas, efetivo, resultados | lista, form, eventos, resultados | PlanoTrabalho, EventoPlano, EfetivoPlano… |
| Prestação de contas | Por ofício/servidor: diário de bordo, RT, comprovantes, consolidado, importação do processo eProtocolo, diário no celular (token) | lista, stepper diário → RT → documentos → PDF final | PrestacaoContas, PrestacaoServidor, RelatorioTecnico, DiarioBordo… |

## Eventos Sociais (Planejado)

- **Propósito**: pedido de apoio a evento (serviços, equipes, unidade móvel, motorista,
  anexos) com despacho da Diretoria-Geral; deferido gera Viagem(ns).
- **Telas**: lista por filas (chips), formulário longo em seções com resumo/checklist/timeline,
  preencher com e-mail, exportar CSV, ações de workflow em modal, anexos privados.
- **Entidades**: SolicitacaoEvento, …Servico, …Equipe, AnexoSolicitacao,
  HistoricoSolicitacao, LembreteSolicitacao; cadastros de apoio (tipo de evento, serviço,
  equipe, órgão, região, município, unidade móvel, texto de despacho).

## Coffee Break (Planejado)

- **Propósito**: pedidos de coffee break contra lotes/contratos de fornecedores, com ciclo
  financeiro (OS → NF → ofício/certifico → protocolo → atesto → OB → envio).
- **Telas**: painel com fila "O que fazer hoje", cadastros (fornecedores, contratos,
  aditivos, configuração), lotes e virada de exercício, wizard em 3 etapas, documentos,
  certidões, portal público do fornecedor por token.
- **Entidades**: Fornecedor, ContratoCoffeeBreak, AditivoContrato, LoteCoffeeBreak,
  SolicitacaoCoffeeBreak, HistoricoCoffeeBreak, OcorrenciaEntrega, CertidaoFornecedor,
  LinkFornecedor, EnvioFornecedor.

## ASCOM (Planejado)

| Submódulo | Propósito | Telas | Entidades |
|---|---|---|---|
| Palestras e Eventos | Pedidos de palestra/participação; encaminhar à DG | painel, lista, form com stepper, andamento, resposta padrão, pedido público + acompanhamento por token | DemandaEvento, Tema, Palestrante, RespostaPadrao, HistoricoDemanda |
| Publicações | Pautas de publicação e produtividade | painel, lista, form, andamento, CSV | Publicacao, HistoricoPublicacao |
| Atendimento à imprensa | Atendimentos a jornalistas com prazo | painel, lista, form, andamento, CSV | Atendimento, HistoricoAtendimento |

## Agenda, relatórios e documentos (Parcial/Planejado)

- **Agenda** (planejado): calendário unificado (mês/semana/programação/ano), escala
  pessoa × dia, pauta semanal em PDF, feed ICS por token, conflitos entre fontes. No novo
  existe apenas o **aviso de conflito** entre ofícios (servidor ou viatura no mesmo período).
- **Relatórios** (planejado): consolidado em tela + XLSX com os mesmos números; CSV por
  módulo respeitando filtros e visibilidade.
- **Documentos**: novo gera PDF/A-2a versionado e imutável (ofício e justificativa);
  editor na página, DOCX, upload/conferência de assinado: planejado. Ver
  [documents.md](documents.md).

## UI Lab (novo)

Vitrine do Design System (`/ui-lab/`): todo componente nasce lá antes de ir para as telas.
Sem equivalente na referência.
