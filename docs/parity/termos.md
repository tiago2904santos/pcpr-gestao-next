# Termos — paridade preservada na migração visual, 10/10/2026

Referência funcional: `docs/migration/termos.md` e relatórios de Termos do sistema
de Gestão de Eventos Sociais, somente leitura. Referência visual: Ofícios atuais.

Mantidos busca, situações temporais/canceladas/finalizadas, filtro por Ofício,
paginação, ações condicionais e criação avulsa/vinculada. Vínculo múltiplo continua
limitado à mesma viagem/roteiro. Evento, período, destinos ordenados, equipe,
viatura, herança, versão, autosave e conflitos mantêm contratos e endpoints.

Documentos por servidor, genérico e veículo; PDF único, ZIP/DOCX, texto editável,
miniaturas, Texto/PDF, aplicação entre páginas, vias assinadas e histórico
continuam nos componentes existentes. Nenhuma alteração do documento oficial.
Termo incompleto não recebe bloqueio de emissão de Ofício.

Permissões, restrição de dados pessoais na folha, cancelamento/reativação,
duplicação, exclusão protegida e salvamento antes de finalizar foram preservados.
Interface nova não apresenta integração externa que não exista no contrato.

Cobertura, lacunas e evidências: `../visual-agents/qa/termos-identidade-2026-10-10.md`.
Não declara aprovação visual do usuário nem cobertura integral do legado ausente.

## Período — refinamento de 14/10/2026

As folhas do calendário são o gatilho nativo da edição, com dobra de canto e layout
ampliado. Mantidos `pc-data`, campos ocultos de início/fim, calendário de intervalo,
origem das datas, teclado e retorno de foco. Folhas e descrição atualizam em regiões
vivas separadas, sem substituir o gatilho. Não altera cálculo do evento nem documento.
Evidência: `../visual-agents/termo-periodo-folhas-20261014.md`.

Indicador visual adicional de antecedência ao início, solicitado pelo usuário:
conta dias de calendário a partir de hoje no fuso da aplicação. Não altera prazo
institucional nem obrigatoriedade de justificativa; duração permanece entre folhas.

O calendário agora consome o template compartilhado da Plataforma. Mantidos os
IDs vivos `periodo-evento` e `periodo-evento-folhas`, a origem efetiva do período e
o gatilho estável. Evidência da extração: `../visual-agents/periodo-propagacao-20261014.md`.
