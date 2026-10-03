# Status da migração

Atualizado em 03/10/2026 (ramo `migracao/loop-continuo`).

## Agora

**Módulo 1 — Ofícios: EM FECHAMENTO.** Tudo o que não depende de terceiros está implementado e
testado; o módulo **não** é marcado concluído enquanto faltar a comparação com a referência em
execução. Ficha e matriz: [oficios.md](oficios.md). Decisões: [decisoes.md](decisoes.md).

| Decisão | Situação |
|---|---|
| D1 Arquivar | ✅ implementado e testado |
| D2 Reativar (gestor, justificativa) | ✅ implementado e testado |
| D3 Motorista de fora da equipe | ✅ implementado e testado |
| D4 Editor principal + DOCX | ✅ "Baixar DOCX" restabelecido; uso real do Word: evidência pendente |
| D5 Filtro pela data do ofício | ✅ implementado e testado |
| D6 Lista de justificativas | ✅ implementado e testado |
| D7 Marcador "Autorização" | ✅ confirmado (só rótulo) |
| D8 Teto de requisições | ✅ validado: necessidade 30 → teto 32 (mais estrito que 40) |

Também nesta rodada: revisão na janela de resumo, textos prontos, exportar planilha, numeração,
base de integrações (eProtocolo simulado), minificação de CSS/JS, correções das revisões de
segurança e de UX (duas rodadas cada).

## Bloqueios

| Item | Tipo | O que destrava |
|---|---|---|
| Comparação lado a lado com a referência em execução | dependência externa | forma autorizada de acesso (credenciais só por variável de ambiente, ou o usuário abre a sessão no navegador do app) |
| eProtocolo real | dependência externa | credenciamento (PDS Mantis), usuário de sistema com CPF, `consumerId`, IP fixo, escopos |
| Central de Viagens | dependência externa | canal institucional (DETO/SEAP, Celepar) |
| Hospedagem / n8n / IA | dependência externa | plano, recursos, backups e custos da VPS |
| Termos por servidor, assinatura de documentos | sequência do roteiro | módulos Termos e Documentos |
| Reabertura formal com motivo sem botão (hoje o caminho é "Editar (retificar)") | **decisão** (nova) | dizer se a reabertura formal ainda precisa de botão |
| Uso real do DOCX fora do sistema | **evidência** do usuário | dizer como o Word é usado (editar e devolver? anexar?) |

## Próximo passo

Com a regressão desta rodada verde, seguir para o **módulo 2 — Cadastros (CRUD)**: servidores,
viaturas, unidades, cargos, combustíveis, tabela de diárias, configuração institucional e
assinaturas, reaproveitando o "cadastro em janela" dos textos prontos e a janela "pedir motivo".

Checkpoints: `fae9abf` (descoberta), `957f3aa`, `cb32c8c`, `f78250a`, `a447f80`, `0118be7`,
`6209156` (D1/D2/D5), `9cc2df6` (D6), `43dad01` (D3), `2bcf751` (D8), `e59ae99` (D4),
`3e2e094` (revisões).
