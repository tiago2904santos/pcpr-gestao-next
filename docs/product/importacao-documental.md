# Importação documental e downloads em fila

Pedido de 16/10/2026: entrada global discreta à direita, vários arquivos, conversão
local para PDF, identificação e distribuição automática; revisão visual dos casos
duvidosos. Downloads individuais com concorrência, sem ZIP.

## Observação da referência

Leitura somente leitura de `viagens_prestacoes/importacao/{entrada,analise}.py`,
`importacao_views.py` e `core/leitura/classificacao.py` no sistema de referência.
O processo é dividido em documentos. Protocolo, número/ano e identificação da
pessoa determinam a prestação/termo. Há prévia, correção, deduplicação e histórico.
Tipos: ofício, justificativa, termo, OS, despacho, diário, RT e comprovante.
Não copiar código nem usar registros reais em testes.

## Contrato

- A fitinha abre uma janela com seleção múltipla/arrastar arquivos e acompanhamento.
  A página de importações conserva o andamento após fechar/recarregar a janela.
- Cada original é privado e imutável, com hash e usuário. O resultado conserva
  páginas de origem, motivos da identificação, destino e anexo criado.
- Processamento persistente fora da requisição, com concorrência limitada,
  retomada após interrupção e aplicação idempotente por documento.
- PDF com texto usa extração direta; imagens e páginas digitalizadas usam OCR
  português. Uma digitalização com rodapé/carimbo textual também precisa de OCR;
  esse rodapé não prova que o corpo da página já foi extraído. Documentos de
  escritório/imagens/texto/e-mail são convertidos localmente.
  Extensões desconhecidas, arquivos protegidos, corrompidos ou acima dos limites
  mostram uma orientação por arquivo; nunca fingir que um formato arbitrário foi lido.
- Limites iniciais: 25 MiB por arquivo, 50 arquivos por envio, 100 páginas por arquivo.
  Conversão/OCR têm timeout. Não buscar recursos remotos de documentos.
  O cliente envia um arquivo por requisição. Essa rota permite corpo de até 26 MiB
  (arquivo + formulário); as outras rotas mantêm o teto geral de 16 MiB. O proxy
  admite até 32 MB, deixando a aplicação aplicar os limites específicos.
  As partes continuam sujeitas aos limites dos destinos: 15 MiB para vias assinadas
  e 10 MiB para anexos da prestação. Excesso pede redução do PDF, sem perder o original.
- Número sem ano só vincula quando identifica um único registro; referências
  conflitantes nunca escolhem o primeiro. Nomes/CPF identificam a pessoa dentro
  do destino. Correspondência de nome aproximado é sugestão, nunca prova única.
- Páginas de continuação/assinatura acompanham o documento anterior; um novo
  título começa nova parte. Documento sem fronteira confiável requer revisão.
- Ofício anexado usa a via compartilhada já consumida na Prestação; não duplicar
  o arquivo em dois cadastros. Despacho/diário vão à equipe; RT/comprovante à pessoa;
  termo/justificativa/OS aos seus documentos. Revalidar permissões e travas na aplicação.
- Uma via diferente já vigente requer decisão explícita antes de substituí-la.
  Mesmo conteúdo no mesmo destino é repetido. Não inferir assinatura criptográfica
  da conversão ou da classificação. Original de PDF assinado permanece preservado.
- Revisão permite abrir/ampliar o PDF, escolher tipo, registro e pessoa e aplicar.
  Falha em um arquivo não impede os outros; sucesso é mostrado somente após gravar.
- Downloads separados geram uma fila com até três arquivos sendo preparados ao
  mesmo tempo. Falhas aparecem individualmente e podem ser repetidas. O navegador
  pode pedir autorização para múltiplos downloads; manter links individuais.
  PDF único continua disponível. Nenhuma ação de download entrega ZIP.

## Validação exigida

Domínio: tipos, fronteiras, números/anos repetidos, conflito protocolo/número,
homônimos, CPF, documentos mistos e páginas sem texto. Integração: conversão real,
OCR real, replay, travas, acesso privado, revisão e downloads. Navegador: lote,
progresso, revisão, zoom, fila e falhas, axe e capturas 360/1440.
Registrar acerto e duração no corpus sintético; não generalizar precisão ou prazo
para arquivos reais não avaliados.
