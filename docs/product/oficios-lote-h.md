# Ofícios — regras do Lote H

Fontes: missão do usuário em 07/10/2026, matrizes
`docs/visual-agents/parity/oficios-{folha,documentos}.md` e confirmação humana de D13
no chat de 07/10/2026 ("Confirmo essa regra").

- Salvar sem alterar o transporte mantém o motorista da equipe. Motorista de fora
  só substitui a seleção da equipe quando esse modo é escolhido. Fechar o bloco
  desativa o motorista externo. Outro transporte não cita motorista de viatura.
- Recuperação de rascunhos usa simulação por padrão, em LAB/DEV/TEST/PREVIEW
  descartável. Não inventar quem dirigia: restaurar somente com evidência de auditoria
  inequívoca; casos ambíguos precisam de seleção humana. Não tocar emitidos.
- Falha na geração é persistente e visível após rollback. Gerar de novo reutiliza
  documento, snapshot, número, versão e mensagem; não emite novamente. Apenas quem
  pode preparar documentos do ofício pode pedir nova tentativa. Arquivados/cancelados
  não são regenerados pelo fluxo.
- Outro transporte aceita um meio selecionado ou descrição livre existente; detalhe
  é opcional quando há meio. Ambos vazios bloqueiam. Lista, resumo, folha e documento
  usam o mesmo texto (meio seguido de detalhe, quando houver).
- **D13 confirmada pelo usuário:** na emissão usar hoje em Brasília, salvo data
  escolhida manualmente. Revisão antecipa data, assunto e exigência de justificativa.
  Emissão recusada não altera o rascunho. Data de outro ano não muda silenciosamente
  o ano/número: bloquear com orientação para criar ofício no ano atual ou escolher
  uma data válida explicitamente. Documentos já emitidos permanecem imutáveis.

A data inicial informada explicitamente pelo serviço é considerada manual; a data
gerada automaticamente na criação é automática. Migração conserva datas existentes
que diferem da data local de criação; a revisão permite corrigir a interpretação.
