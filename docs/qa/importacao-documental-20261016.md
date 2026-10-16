# Importação documental e downloads — validação de 16/10/2026

## Observar e entender

Pedido: entrada global discreta, lotes heterogêneos convertidos em PDF, distribuição
automática por documento/pessoa e revisão ampliada somente quando necessária;
downloads separados concorrentes sem ZIP. A referência foi inspecionada somente
para leitura (`viagens_prestacoes/importacao`, `core/leitura` e testes de termos).
Regras registradas antes da implementação em `docs/product/importacao-documental.md`.

## Projetar e implementar

ADR 0041: fila persistente, conversores locais isolados, classificação pura por
evidências e serviços de anexação existentes. O ofício tem uma única via, já usada
na prestação. O original não é descartado. O documento de páginas separadas é um
derivado: não representa preservação da assinatura criptográfica do PDF inteiro.

Tela construída sobre DETAIL, diálogo, cartões, campos e botões existentes.
PDF.js local na revisão, carregado sob demanda; sem serviços externos de IA.
Worker dedicado em rede interna sem acesso à internet; conversores sem credenciais
do banco no ambiente. Migrations 0059/0060 aplicadas no PREVIEW local, sem reset.

## Testar e comparar

Somente cenários sintéticos, PostgreSQL descartável e snapshots Linux do código.

- 77 testes de regressão inicial passaram: importação, pacotes, termos, prestação
  e protocolo de Coffee. Log `importacao-regressao.log` no ambiente de QA.
- 26 testes finais de integração passaram em 133,40 s, incluindo documentos produzidos pelos modelos
  reais do sistema, DOCX/LibreOffice, imagem/Tesseract, conflitos, privacidade,
  substituição explícita, retomada de lease e PDF digitalizado com rodapé textual.
  Log preservado em `integracao-final.log`, junto das capturas.
- Seis testes de navegador passaram em 265,24 s: envio/revisão em 360/1440,
  PDF efetivamente renderizado e zoom; fila de quatro PDFs reais com falha
  transitória simulada, repetição e três requisições simultâneas; PDF único e
  download pelo resumo continuam funcionando. Axe sem violações nas telas
  avaliadas; sem erros de console.
- Repetição final dos dois cenários de importação/revisão: dois testes passaram
  em 247,63 s, após as correções de estado ocupado e recursos do leitor PDF.
- UI Lab: 16 testes visuais/de acessibilidade passaram em 425,96 s, incluindo
  360/1440, interação por teclado e componentes compartilhados.
- Limites HTTP: sete testes passaram em 40,07 s, incluindo upload multipart real
  de 25 MiB gravado na fila, excesso de 26 MiB recusado e preservação da recusa
  de 17 MiB nas rotas antigas. Log `limites-upload.log` junto das capturas.
- Medição real do worker: nove PDFs textuais independentes, três workers,
  **3,509 s**, nove destinos corretos e nenhuma revisão. Durações individuais
  entre 901 e 1.228 ms. Não inclui upload nem geração prévia do corpus. A máquina
  também executava a regressão. Arquivo `medicao.json` junto das capturas.

Evidências visuais: `docs/visual-agents/evidencias/importacao-20261016/`.
Revisados envio, resultados, histórico, revisão ajustada/ampliada e downloads em
360/1440. Rolagem do documento fica dentro do leitor; não há overflow da página.

## Criticar e corrigir

- Axe detectou alvo de toque insuficiente no link do original: passou a botão.
- `writing-mode` com posicionamento lógico esticava a fita: fixação física à direita.
- Envio assíncrono não deve deixar o botão no estado ocupado do submit genérico:
  o controlador agora controla e encerra esse estado; o listener global respeita
  o cancelamento do envio pelos módulos carregados sob demanda.
- Prévia nativa de PDF apareceu vazia: substituída pelo leitor local em canvas.
- Build moderno do PDF.js exigia API ainda ausente no Chromium de teste: adotado
  build de compatibilidade com polyfills do próprio pacote.
- Termo sem referência de ofício exigia reconhecer o período completo por extenso,
  além de CPF/nome. Testado com PDF gerado pelo modelo de termo, não só texto artificial.
- PDF com carimbo textual e corpo digitalizado também precisa de OCR: recursos de
  imagem grandes são detectados e o texto reconhecido complementa o texto digital.
  Cenário testado com imagem real embutida no PDF, rodapé e Tesseract.
- A proteção geral de corpo HTTP era 16 MiB, inferior aos 25 MiB anunciados na
  entrada. Exceção configurada por caminho exato permite 26 MiB com o formulário;
  os demais caminhos continuam com 16 MiB. Modelos de proxy ajustados para 32 MB.
  Nenhum proxy de produção foi alterado. Os limites dos anexos finais (10/15 MiB)
  permanecem nos serviços existentes e são explicados na documentação operacional.
- Arquivo esgotado não pode bloquear os seguintes; reenvio de erro permite nova
  tentativa sem duplicar original ou partes já aplicadas.
- Título desconhecido de nota fiscal/declaração cria parte para revisão, não é
  incorporado silenciosamente ao ofício anterior. Ano de dois dígitos não é ignorado.
- A regressão encontrou um teste antigo dependente do dia da execução: `hoje+400`
  caiu em 20/11/2027, que a própria agenda exibe como feriado. O teste de estado
  vazio agora isola a fonte da viagem sintética; nenhuma regra da agenda foi alterada.
  A primeira passagem foi interrompida após 777 acertos/essa falha para consolidar
  o snapshot final e repetir a verificação com mais workers isolados.

## Validar e limites

A verificação integral `scripts/verificar.sh` terminou verde: **2.638 testes passaram**
em 3.416,15 s (56 min 56 s), com seis workers/bancos de teste isolados. Ruff, fronteiras
(16 contratos), mypy (315 fontes), Bandit, migrações e tipos JS também passaram.
Log completo: `verificacao-integral.log` na pasta de evidências.

Cinco avisos não bloqueantes da suíte: três de API legada do pypdf no carimbo e dois
de paginação sem ordenação no recorte de listas vazias. Não são falhas da importação.

O snapshot integral permaneceu congelado durante a execução. Depois dele, foi
sincronizado com o código final (OCR híbrido, limite HTTP e comentários) para repetir
o mesmo script com os testes de importação, limites HTTP e vias assinadas:
**62 testes passaram em 147,68 s**, novamente com todas as checagens estáticas verdes.
O escopo complementar foi definido via `PYTEST_ADDOPTS` com os quatro arquivos de
teste; não é apresentado como uma segunda execução integral. Log:
`verificacao-complementar.log` na pasta de evidências.

O CI foi provisionado com LibreOffice, Poppler e Tesseract/português nos jobs de
integração e navegador. Não foi disparada uma execução remota do CI. O compose
PREVIEW/DEV passou em `docker compose ... config --quiet`; `/saude/` respondeu 200
e o importador local permaneceu em execução, sem reinicializações inesperadas.

Não se afirma infalibilidade nem a mesma duração para imagens, manuscritos,
digitalizações ruins, arquivos protegidos ou formatos arbitrários. O corpus
sintético não mede a taxa de revisão da documentação real. Limites atuais:
25 MiB/100 páginas por arquivo, 50 arquivos por envio, até 240 s por leitura.
Conversão não reconhecida mantém original e explica como reenviar. EML/MHTML usa
o corpo textual da mensagem, não importa anexos internos automaticamente.
O navegador pode pedir permissão para múltiplos downloads; a fila precisa ficar
na página até terminar. Não foi feito deploy em produção.

## Integração para publicação no main

Após o pedido de publicação, `origin/main` avançou até `9e74fa4` (nove commits,
incluindo o visualizador e o anexo da solicitação da viagem). O merge textual
preservou ambos os trabalhos. A migração 0061 une as folhas independentes
`0059_anexo_da_viagem` e `0060_importacao_auditoria`, sem renomear migrações já
aplicadas e sem operações destrutivas. O script `scripts/verificar.sh` passou com
131 testes do escopo integrado (importação, limites, pacotes, viagem e termos), em
178,70 s, e todas as checagens estáticas verdes (`integracao-main.log`).

O primeiro navegador integrado passou 7/8 testes e revelou que a fita disputava
espaço com a seta do visualizador em 1440 px (`navegador-main-antes.log`). A fita
agora fica oculta durante janelas modais, com teste explícito de retorno ao fechar.
Revalidação: **8/8 passaram em 351,18 s**, incluindo acessibilidade, lote/revisão,
downloads em 360/1440 e o visualizador (`navegador-main-final.log`).
Na aba local antiga, o acesso estava ausente até
recarregar a listagem; após atualizar, o link abriu a janela de seleção múltipla.

Antes do push, chegou também `3e95b69` (refino da prestação). Os três conflitos
foram reconciliados: preservados o novo layout e a correção de feriados da agenda;
mantidos os imports e endpoints de downloads em fila. Os três novos menus de
pacotes da prestação passaram de ZIP para fila. A migração 0062 une a edição da
prestação à cadeia da importação sem alterar as migrações existentes. Migrações
0060 de edição e 0062 aplicadas no PREVIEW local sem erro. Checagem complementar
do segundo estado integrado: **99 testes passaram em 188,79 s**, todas as checagens
do `scripts/verificar.sh` verdes; navegador de importação/fila e anexos: **5 passaram
em 295,68 s**. Logs `integracao-main-prestacao.log` e `navegador-main-prestacao.log`.
Capturas de envio 360/1440 em `main/` revisadas, sem cortes nos controles.

## Ativação autorizada no PREVIEW hospedado

O usuário confirmou explicitamente a ativação no servidor. SSH por chave e host
conhecido (IP) confirmou `APP_ENV=preview`, settings preview e versão `3e95b69`.
O nome DNS não estava em known_hosts; usado o IP já conhecido, sem desativar a
verificação de identidade. Nenhum segredo foi lido ou publicado.

Executor automático atualizado para incluir importador na imagem da release,
parada de backup/migração, rede interna (alias db, banco não recriado), retomada
por versão e checagem final. Duas conversões simultâneas na VPS. `bash -n`, testes
de política e teste simulado do ciclo do importador passaram; ShellCheck 0.11.0
sem avisos. Não alterado o fluxo separado de produção.

Executor instalado administrativamente sob lock. Configuração anterior do executor
e do Nginx preservadas em `/srv/pcpr/automatico/backups/config-importacao-20261016`.
Somente o teto de upload do site PCPR mudou de 16m para 32m. `nginx -t` aprovado,
reload sem reinício, saúde pública 200 com banco ok. Outros sites não alterados.
SHA-256 do executor instalado: `c2e086c50c1f83d7a88ce4c1812c372969cb0558117f1bd59fc64424aa385319`.
Publicação e verificação do lote real sintético no HTTPS ainda pendentes.
