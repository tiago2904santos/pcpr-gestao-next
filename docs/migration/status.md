# Status da migração

Atualizado em 03/10/2026 (ramo `migracao/loop-continuo`).

## Agora

**Módulo 2 — Cadastros: EM ANDAMENTO.** CRUD em tela de servidores, viaturas, unidades,
cargos, combustíveis, tabela de diárias e configuração da unidade, implementado e testado
(ficha e matriz: [cadastros.md](cadastros.md)). Faltam assinantes por tipo de documento com
substituições e o endereço da configuração em campos. Comportamentos adotados da referência
a confirmar: [decisoes.md](decisoes.md#cadastros-módulo-2--comportamentos-adotados-da-referência-a-confirmar).

**Módulo 1 — Ofícios: EM FECHAMENTO** (falta a comparação com a referência em execução e a
decisão sobre o botão de reabrir). Ficha: [oficios.md](oficios.md).

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

Fechar o módulo 2: assinantes por tipo de documento (Ofício, Justificativa) com substituição
por período, que passam a alimentar os documentos; depois o endereço da configuração em
campos. Em seguida, **módulo 3 — Roteiros (fechamento)**.

Checkpoints: `fae9abf` (descoberta), `957f3aa`, `cb32c8c`, `f78250a`, `a447f80`, `0118be7`,
`6209156` (D1/D2/D5), `9cc2df6` (D6), `43dad01` (D3), `2bcf751` (D8), `e59ae99` (D4),
`3e2e094` (revisões), módulo 2 CRUD (este commit).
