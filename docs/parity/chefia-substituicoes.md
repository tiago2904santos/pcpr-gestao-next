# Substituição da chefia — calendário compacto, 14/10/2026

Contrato: `FormularioSubstituicao`, `services.salvar_substituicao` e Configuração.
Início obrigatório, fim opcional: ausência de fim mantém vigência até encerramento.
O usuário aprovou a variante compacta do calendário e removeu a antecedência nela.
Preservados servidor, tipo de documento, motivo, nomes/IDs, erros, permissão e
POST manual. Fim aberto é apresentado corretamente e pode ser restaurado pelo
seletor, mantendo o início. Não altera dados existentes nem regras de assinatura.
Evidência/limites: `../visual-agents/periodo-propagacao-20261014.md`.

## Dados da unidade — reorganização de 17/10/2026

Decisão explícita da missão: Configuração da unidade passa a Dados da unidade,
com entrada única imediatamente depois de Alterar senha no menu da conta. A rota
antiga e os links contextuais continuam válidos. Unidade atual (nome/sigla) aparece
antes dos campos; a mudança de unidade só oferece contextos autorizados.

Os titulares por tipo e as substituições continuam ligados aos mesmos servidores,
cargos e configurações. As escolhas passam a busca remota contextual limitada
(15 resultados); o vínculo atual continua identificado fora da primeira página
e quando inativo. Sem JavaScript, mantém-se o vínculo atual; nova busca depende
de JavaScript, como nas demais multiescolhas remotas do sistema.

Comparação funcional baseada no contrato já documentado neste arquivo, CD05,
`docs/migration/cadastros.md` e testes existentes, sem nova sessão no legado.
As mudanças de navegação, metadados e conforto são melhorias intencionais; regra
de titular/substituto/chefia e os instantâneos dos documentos permanecem.

Evidências desta rodada em `../auditorias/cadastros-compartilhados/unidade.md`.
