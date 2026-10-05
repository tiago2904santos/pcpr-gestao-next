# Status da migração

Atualizado em 04/10/2026 (ramo `migracao/loop-continuo`).

## Agora

**Módulo 6 — Planos de trabalho: implementado** (catálogos, plano de um e de vários eventos, documento, resultados; ficha [planos.md](planos.md)). Próximo: módulo 7 (núcleo de Documentos).

**Termos e Ordens de serviço: folhas refeitas** na linguagem da folha do ofício (placa e
frase, cartões numerados com selos de falta, conferência, documento como vai sair,
histórico da trilha do banco, gravação automática). Fichas: [termos.md](termos.md),
[ordens.md](ordens.md).

## Módulos

Inventário da referência (rotas por app): accounts 11, agenda 7, atendimento_imprensa 12,
cadastros 8, coffee_break 60, config 25, core 8, dashboard 1, demandas_eventos 16,
documentos 23, publicacoes 12, relatorios 2, solicitacoes 19, viagens_cadastros 11,
viagens_oficios 29, viagens_ordens 8, viagens_planos 12, viagens_prestacoes 10,
viagens_roteiros 14, viagens_termos 12, viagens_viagem 13.

| # | Módulo | Status | Paridade | Testes | Performance | Visual | Pendências | Próximo passo |
|---|---|---|---|---|---|---|---|---|
| 1 | Ofícios (+ justificativas) | EM FECHAMENTO | matriz completa por leitura ([oficios.md](oficios.md)) | unit, e2e, axe | teto 32 req., TTFB/LCP no orçamento | 6 larguras | comparação com a referência em execução; botão de reabrir | aguarda decisão/acesso |
| 2 | Cadastros | IMPLEMENTADO | completa por leitura ([cadastros.md](cadastros.md)) | ~84 unit, e2e, axe | listas sem N+1 | 6 larguras | comportamentos adotados a confirmar | — |
| 3 | Roteiros | EM PARIDADE | "Finalizados" feito com a prestação 9a ([roteiros.md](roteiros.md)) | unit, e2e, axe | medido | 6 larguras | "Finalizados" (módulo 9) | com o módulo 9 |
| 4 | Termos de autorização | IMPLEMENTADO (folha refeita) | completa, menos anexar assinado e "Finalizados" | 33 + folha termo/OS (28), e2e, axe 360/1440 | lista com consultas fixas | 6 larguras | anexar assinado (7), "Finalizados" (9) | com 7 e 9 |
| 5 | Ordens de serviço | IMPLEMENTADO (folha refeita) | completa, menos anexar assinado, "Finalizadas", conflito de agenda | 24 + 23 domínio + folha termo/OS (28), e2e, axe 360/1440 | lista com consultas fixas | 6 larguras | idem + conflito de agenda | com 7 e 9 |
| 6 | Planos de trabalho | IMPLEMENTADO (6a–6e) | matriz em [planos.md](planos.md) | 17 catálogos + 23 domínio + 40 plano, e2e, axe 360/1440 | lista com consultas fixas | 6 larguras | "Finalizados" (9), integração com viagem (8) | com 8 e 9 |
| 7 | Documentos (núcleo: anexar assinado, conferência) | PENDENTE | — | — | — | — | `documentos` (23 rotas) | **próximo** |
| 8 | Viagem (assistente) | PENDENTE | — | — | — | — | `viagens_viagem` (13) | depois do 7 |
| 9 | Prestação de contas (+ abas "Finalizados") | PENDENTE | — | — | — | — | `viagens_prestacoes` (10) | depois do 8 |
| 10 | Plataforma (usuários/setores, notificações, agenda, relatórios, painel) | PARCIAL | entrada, notificações (vazio) e painel existem | — | — | — | `accounts`, `config`, `agenda`, `relatorios`, `dashboard` | depois do 9 |
| 11 | Eventos sociais (solicitações, demandas, cadastros de eventos) | PENDENTE | — | — | — | — | `solicitacoes` (19), `demandas_eventos` (16), `cadastros` (8) | — |
| 12 | ASCOM (atendimento à imprensa, publicações) | PENDENTE | — | — | — | — | 12 + 12 rotas | — |
| 13 | Coffee Break | PENDENTE | — | — | — | — | 60 rotas | — |
| 14 | ETL (dados da referência) | BLOQUEADO EXTERNAMENTE | — | — | — | — | acesso aos dados | — |

## Decisões de Ofícios

| Decisão (Ofícios) | Situação |
|---|---|
| D1 Arquivar | ✅ implementado e testado |
| D2 Reativar (gestor, justificativa) | ✅ implementado e testado |
| D3 Motorista de fora da equipe | ✅ implementado e testado |
| D4 Editor principal + DOCX | ✅ "Baixar DOCX" restabelecido; uso real do Word: evidência pendente |
| D5 Filtro pela data do ofício | ✅ implementado e testado |
| D6 Lista de justificativas | ✅ implementado e testado |
| D7 Marcador "Autorização" | ✅ confirmado (só rótulo) |
| D8 Teto de requisições | ✅ validado: necessidade 30 → teto 32 (mais estrito que 40) |

## Bloqueios

| Item | Tipo | O que destrava |
|---|---|---|
| Comparação lado a lado com a referência em execução | dependência externa | forma autorizada de acesso (credenciais só por variável de ambiente, ou o usuário abre a sessão no navegador do app) |
| eProtocolo real | dependência externa | credenciamento (PDS Mantis), usuário de sistema com CPF, `consumerId`, IP fixo, escopos |
| Central de Viagens | dependência externa | canal institucional (DETO/SEAP, Celepar) |
| Hospedagem / n8n / IA | dependência externa | plano, recursos, backups e custos da VPS |
| Termos por servidor, assinatura de documentos | sequência do roteiro | módulos Termos e Documentos |
| Reabertura formal com motivo sem botão (hoje o caminho é "Editar (retificar)") | **decisão** | dizer se a reabertura formal ainda precisa de botão |
| Cadastros: operador mantém cadastros; nome/RG/telefone únicos (adotados da referência) | decisão (não bloqueia) | confirmar ou pedir mudança |
| Uso real do DOCX fora do sistema | **evidência** do usuário | dizer como o Word é usado (editar e devolver? anexar?) |

## Próximo passo

**Módulo 6 — Planos de trabalho** (multievento, efetivo, atividades, diárias combinadas).

Checkpoints: `fae9abf` (descoberta), `957f3aa`, `cb32c8c`, `f78250a`, `a447f80`, `0118be7`,
`6209156` (D1/D2/D5), `9cc2df6` (D6), `43dad01` (D3), `2bcf751` (D8), `e59ae99` (D4),
`3e2e094` (revisões), módulo 2 CRUD `5310817`, assinantes `b6a6375`, termos `50f79d0`, ordens `e4994fa`, folhas de termo e OS `d62e1b1`, catálogos do plano `b883809`, domínio do plano `afd630a`, plano de um evento `80e3de0`, vários eventos `a632ab6`, resultados (este commit).
