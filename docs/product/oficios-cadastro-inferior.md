# Cadastro de Ofício — apresentação da metade inferior

Fonte: pedido explícito do usuário em 09/10/2026. Refazer a apresentação de Roteiro
até a barra final; manter Header, Identificação e Equipe/transporte como referência.
Preservar os ajustes do usuário no cartão da equipe e no ícone de volante.

Contrato funcional: ADR 0015/0016, `tempos-de-rota.md`, `oficios-lote-h.md`,
`oficios-documentos-versoes.md` e `oficios-eprotocolo.md`. Esta missão não altera
fórmulas, permissões, versões, histórico, auditoria nem conteúdo oficial.

- A: busca de roteiro existente compacta; selecionar/aplicar mantém o POST atual,
  prévia não gravada e origem do roteiro. Sequência sede/destinos/retorno clara,
  preservando UF, município, ordem, exclusão, adição e bate-volta. Mapa mantém
  pinos, traçado, enquadramento, zoom, totais e fallback do provedor.
- B: trecho identificado por origem/destino e quilometragem; saída e durações
  editáveis, chegada como resultado calculado. Nenhuma mudança de tempo/adicional.
  Diárias compactas, com total, valor individual, composição e estado do cálculo.
- C: justificativa com estado e explicação proporcionais; manter texto pronto,
  gestão de textos, obrigatoriedade e texto incluído mesmo quando dispensado.
- D: separar prontidão/pendências, revisão e dados copiáveis; usar o componente
  aprovado do Resumo, preservando os seis campos e cópia individual/completa.
- E: editor/minuta/PDF com ferramentas agrupadas e navegação de páginas; manter
  todas as ações, seleção Texto/PDF, atualização, baixar, edição e salvamento.
- F: histórico escaneável com autor/horário/evento, sem perder eventos anteriores;
  barra final com hierarquia de Finalizar, Voltar, Ações e feedback de autosave.

Estados: preenchido, vazio/pendente, bate-volta, erro, pronto para emissão,
justificativa obrigatória/dispensada incluída, documento em geração/erro/pronto.
Validar 360/390/768/1024/1440, teclado/foco/axe/console, fluxos existentes e gate.

Implementar em blocos A–F com segunda revisão visual. Sem expansão para outros
módulos. Variantes compartilhadas ativadas nesta Folha e no UI Lab; mudanças
globais somente quando necessárias e cobertas por testes das telas afetadas.
