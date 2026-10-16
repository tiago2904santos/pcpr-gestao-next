# Operação da importação documental

O Dockerfile inclui LibreOffice Writer/Calc/Impress, Poppler e Tesseract português.
Os manifests PREVIEW/DEV e implantação iniciam `processar_importacoes` no serviço
`importador`. Recrie a imagem ao atualizar; só reiniciar a imagem antiga não instala
os conversores. Aplicar migrações 0059/0060 antes de iniciar o worker.
Atualizar também o modelo do proxy: teto externo de 32 MB; a aplicação libera
26 MiB somente no POST de importação e mantém 16 MiB nas demais rotas. O cliente
envia um arquivo por requisição, mesmo em lote. As partes resultantes respeitam
os limites existentes: 15 MiB por via assinada e 10 MiB por anexo da prestação.

### Atenção ao executor da VPS

O executor `deploy/automatico/atualizar.sh` inclui o importador na mesma imagem da
release (duas conversões simultâneas), na parada de backup/migração e na verificação
final. Conecta o banco existente à rede interna sem recriá-lo. É necessário instalar
administrativamente essa versão do executor e ajustar o proxy para 32 MB; o push
sozinho não atualiza o executor instalado. O fluxo separado de produção em
`deploy/vps/implantar.sh` ainda requer integração equivalente antes de usar importação
nessa arquitetura. Esta ativação é somente do PREVIEW hospedado existente.

O worker usa a rede interna do banco, sem saída à internet. Os subprocessos recebem
ambiente mínimo, sem credenciais do banco. Perfil do LibreOffice exclusivo por
conversão, macros bloqueadas; documentos OOXML com vínculos externos pedem PDF.
Leitura isolada: 240 s por arquivo, 2 GiB de espaço virtual e 180 s de CPU em Linux.
O worker de produção usa dois arquivos simultâneos; PREVIEW usa três. Ajuste com
`--concorrencia` (máximo quatro), respeitando a memória disponível.

PDF textual: extração direta. Página com pouco texto ou digitalização grande com
apenas rodapé/carimbo textual: rasterização até 2400 pixels
e Tesseract `por+eng`. Arquivos de até 25 MiB/100 páginas. Documentos de escritório
modernos e antigos, imagens, texto/CSV, EML/MHTML e HTML são aceitos pelos conversores;
HTML é reduzido a texto antes de gerar PDF. Um formato não suportado gera erro por
arquivo e orientação, preservando o original para download privado.

Os registros ficam em `ArquivoImportado`/`ParteImportada`, com trilha de auditoria.
Não há exclusão automática dos originais. Um worker interrompido deixa lease de
oito minutos; o próximo retoma, até três tentativas. Aplicações já concluídas não
são repetidas. Execute `python manage.py processar_importacoes --uma-vez` para
drenar a fila em operação manual. O serviço de web permanece livre durante OCR.

Acesso: só quem pode editar documentos importa; cada usuário acompanha seus
próprios originais. Destinos respeitam as policies de cada registro na aplicação.
Sem worker disponível, arquivos permanecem na fila; verificar logs do serviço.
