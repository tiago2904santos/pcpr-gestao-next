# Status da migração

Atualizado em 03/10/2026 (ramo `migracao/loop-continuo`).

## Agora

**Módulo 5 — Ordens de serviço: IMPLEMENTADO** (ficha [ordens.md](ordens.md)): numeração
anual, OS avulsa ou a partir do ofício (copiando destinos, período, equipe e motivo), os
cinco tipos de necessidade com os textos da referência, funções da equipe, PDF/DOCX,
cancelar/reativar/excluir. O menu de Viagens ganhou o grupo "Documentos" (Justificativas,
Termos, Ordens de serviço).

**Módulo 4 — Termos de autorização: IMPLEMENTADO** (ficha [termos.md](termos.md)): termo
avulso ou a partir do ofício (herdando destinos, período, equipe e viatura), documento por
servidor, genérico e da viatura, PDF único e ZIP de DOCX, cancelar/reativar/excluir.

**Módulo 3 — Roteiros: EM PARIDADE** (ficha [roteiros.md](roteiros.md)); falta "Finalizados",
que depende da prestação de contas.

**Módulo 2 — Cadastros: IMPLEMENTADO** (ficha [cadastros.md](cadastros.md)): CRUD em tela,
assinantes por tipo com substituições e endereço em campos. Comportamentos adotados da
referência a confirmar: [decisoes.md](decisoes.md).

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

**Módulo 6 — Planos de trabalho** (multievento, efetivo, atividades, diárias combinadas).

Checkpoints: `fae9abf` (descoberta), `957f3aa`, `cb32c8c`, `f78250a`, `a447f80`, `0118be7`,
`6209156` (D1/D2/D5), `9cc2df6` (D6), `43dad01` (D3), `2bcf751` (D8), `e59ae99` (D4),
`3e2e094` (revisões), módulo 2 CRUD `5310817`, assinantes `b6a6375`, termos `50f79d0`, ordens (este commit).
