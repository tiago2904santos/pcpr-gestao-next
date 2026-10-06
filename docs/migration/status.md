# Status da migração

Atualizado em 06/10/2026 (ramo `migracao/loop-continuo`). Detalhe por módulo em
[parity.md](parity.md); fila e falhas conhecidas em [continuous-work.md](continuous-work.md).

## Agora

Todos os módulos da referência têm equivalente navegável. Nesta rodada (05–06/10):
Eventos Sociais E1–E5, Palestras PL1 e PL2a (encaminhar à DG), Imprensa I1–I2, Publicações
P1–P2, Coffee Break CB1–CB7 (com CB5d), Agenda A1–A2c (dossiê, assinatura ICS, conflitos de
termos/OS) e o relatório consolidado R1. O que resta depende de decisão do usuário, de
dependência externa ou de arquivos que a sessão paralela de correção visual ainda não
commitou (ver "Bloqueios").

## Módulos

| # | Módulo | Status | Pendências | O que destrava |
|---|---|---|---|---|
| 1 | Ofícios (+ justificativas) | IMPLEMENTADO | comparação com a referência em execução; botão de reabrir | acesso / decisão |
| 2 | Cadastros | IMPLEMENTADO | comportamentos adotados a confirmar | decisão (não bloqueia) |
| 3 | Roteiros | IMPLEMENTADO | histórico de roteiros (trilha P) | commits da sessão paralela |
| 4–6 | Termos, Ordens, Planos | IMPLEMENTADO (área da sessão paralela) | editor e folhas em mudança lá | — |
| 7 | Documentos (via assinada, conferência, baixar) | IMPLEMENTADO | prévia da conferência antes de anexar | `assinado.js` da sessão paralela |
| 8 | Viagem | IMPLEMENTADO (8a–8d) | geração automática/anexos a partir do evento (decisão E4) | decisão |
| 9 | Prestação de contas | IMPLEMENTADO (9a–9d) | revisão página a página do pacote (13d); carimbo automático; OCR; eProtocolo | migração 0045 da sessão paralela; externos |
| 10 | Plataforma (usuários, notificações, rotinas, agenda, busca, relatórios) | IMPLEMENTADO | esqueci a senha (SMTP); setor/módulo | SMTP; decisão |
| 11 | Eventos Sociais | IMPLEMENTADO (E1–E5) | consultar protocolo; preencher com e-mail | eProtocolo; — |
| 12 | ASCOM: imprensa, publicações, palestras | IMPLEMENTADO (I2, P2, PL2a) | importadores de planilha; pedido público de palestra | decisão do usuário |
| 13 | Coffee Break | IMPLEMENTADO (CB1–CB7, CB5d) | e-mails e link do fornecedor (CB8); importações (CB9) | SMTP + decisão institucional; decisão |
| 14 | ETL (dados da referência) | BLOQUEADO EXTERNAMENTE | acesso aos dados | — |
| — | Rodapé padrão das folhas (pedido do usuário via sessão paralela) | PENDENTE | coffee, eventos, palestras | commit do componente pela sessão paralela |

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
| SMTP institucional | credencial externa | esqueci a senha, e-mails do Coffee Break (CB8), pauta semanal por e-mail |
| Arquivos não commitados da sessão de correção visual | coordenação | rodapé padrão das folhas (20), migração 0045 (13d), `assinado.js` (prévia), arquétipo do painel (18l) |
| Decisões do usuário | decisão | pedido público de palestra (16e), rota pública do fornecedor (CB8), importações (CB9, planilhas da imprensa/publicações), setor/módulo |
| Reabertura formal com motivo sem botão (hoje o caminho é "Editar (retificar)") | **decisão** | dizer se a reabertura formal ainda precisa de botão |
| Cadastros: operador mantém cadastros; nome/RG/telefone únicos (adotados da referência) | decisão (não bloqueia) | confirmar ou pedir mudança |
| Uso real do DOCX fora do sistema | **evidência** do usuário | dizer como o Word é usado (editar e devolver? anexar?) |

## Próximo passo

**Módulo 6 — Planos de trabalho** (multievento, efetivo, atividades, diárias combinadas).

Checkpoints: `fae9abf` (descoberta), `957f3aa`, `cb32c8c`, `f78250a`, `a447f80`, `0118be7`,
`6209156` (D1/D2/D5), `9cc2df6` (D6), `43dad01` (D3), `2bcf751` (D8), `e59ae99` (D4),
`3e2e094` (revisões), módulo 2 CRUD `5310817`, assinantes `b6a6375`, termos `50f79d0`, ordens `e4994fa`, folhas de termo e OS `d62e1b1`, catálogos do plano `b883809`, domínio do plano `afd630a`, plano de um evento `80e3de0`, vários eventos `a632ab6`, resultados (este commit).
