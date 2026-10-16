# Importação documental — comparação com a referência

Fonte: leitura local de `viagens_prestacoes/importacao` e `core/leitura` em
16/10/2026. Não foi realizado envio de documentos no sistema de referência.

- Preservado: identificação por protocolo/ofício/pessoa, separação de partes,
  original guardado, revisão, prevenção de repetição e uso das regras de anexação.
- Melhoria solicitada: vários arquivos simultâneos, conversão local de documentos,
  fitinha global, fila persistente com worker concorrente e andamento por arquivo.
- Melhoria solicitada: downloads separados são uma fila de arquivos individuais;
  PDF único continua disponível. ZIP deixa de ser entregue pelas ações da aplicação.
- Decisão de segurança do vínculo: referências conflitantes e via já existente
  diferente pedem revisão. Nome aproximado não autoriza anexação automaticamente.
- A precisão e duração são medidas em corpus sintético; não se afirma infalibilidade
  para documentos externos. Formatos não convertíveis e documentos ilegíveis conservam
  original e orientação explícita para reenviar.

Evidência concluída em `docs/qa/importacao-documental-20261016.md`: verificação
integral com 2.638 acertos, verificação complementar final com 62 acertos, testes
de navegador e UI Lab, capturas revisadas em 360/1440 e nove PDFs textuais anexados
corretamente em 3,509 s no corpus sintético. Nenhum dado da referência foi alterado.
