# ADR 0042 — Prestação de contas no padrão do sistema modelo

- **Status:** aceito (substitui a ADR 0041 na lista e nas folhas)
- **Data:** 2026-10-16

## Contexto

O usuário rejeitou a lista em linhas operacionais da ADR 0041 ("praticamente inútil"): o
trabalho da prestação é, para cada servidor, gravar o nº da solicitação e o prazo de saque
**na própria lista**, ver o que já foi feito e agir. A referência é o sistema modelo de
gestão de eventos sociais (lista, página de termos e diário de bordo), com o pedido de
"melhorar sem regredir". Pediu ainda uma página que **transcreva** o que está escrito nos
anexos (RT assinado, diário assinado, comprovante de saque/transferência) com botões
"Copiar", como os dados para o eProtocolo do ofício, e que **confira** o valor do
comprovante com a diária do ofício e com a diária escrita no RT.

## Decisão

- **Lista** (`/viagens/prestacoes/`): um bloco por ofício — placa (abre o resumo), destinos,
  situação da equipe, protocolo, período, unidade, diária por servidor com a conta das
  diárias, "prestar até" — e, embaixo, **uma linha por servidor** com crachá (o motorista
  do ofício leva o volante), **nº da solicitação** e **prazo de saque** (liberação → limite
  num campo só, `pc-data data-periodo`) gravando sozinhos (autosave), o que já foi feito
  (✓ diário, ✓ relatório, ✓ comprovante com o valor, ✓ despacho; "gerado" quando falta o
  assinado), a situação e os prazos, cargo · CPF · telefone, as ações (Finalizar, Registrar
  envio, Aprovar, Devolver, Reabrir, Desarquivar) e o ⋮ (pacote final, RT em PDF, anexar,
  ler os anexos, avisar por WhatsApp, arquivar). As pendências ficam num `details` no rodapé
  da linha, com a justificativa para finalizar mesmo assim. Abas de situação e atalhos de
  pendência (novos: sem despacho, sem comprovante, comprovante ≠ diária), busca, 25 ofícios
  por página e exportação continuam.
- **Folhas** — 1 Diário de bordo, 2 Relatório técnico, 3 Documentos e fechamento, 4 Leitura e
  conferência — com o mesmo topo (`prestacao/_topo.html`): o **servidor** é um seletor da
  equipe (`?servidor=`; trocar de servidor mantém a etapa), a situação, a linha do ofício e
  a ação principal; a **trilha** das quatro etapas (✓ quando concluída). Cada folha é um
  cartão numerado e, embaixo, o **documento embutido** (iframe `folha_diario` /
  `folha_relatorio`, só leitura, que se refaz a cada gravação — `previa-documento.js`).
  "Salvar e continuar" espera o autosave e leva à próxima etapa do mesmo servidor.
  - Diário: motorista e viatura como cartões de recurso, a tabela dos trechos (origem,
    destino, saída, km, chegada, km, abastecimento, distância), "Preencher pelas distâncias"
    (`diario-distancias.js`), a conferência do hodômetro e, em `details`, trocar motorista /
    viatura e a viagem realizada.
  - RT: a diária do servidor da folha na linha do custeio (como no modelo), translado,
    combustível e passagem; os cinco textos com texto pronto e "Sugerir texto"; a diária
    recebida de cada servidor; a prévia troca de servidor por um `select`.
  - Documentos e fechamento: só o servidor da folha — solicitação, os cinco documentos
    (ofício assinado com a posição do nº da solicitação, despacho, RT assinado, diário
    assinado, comprovantes), o que falta para o pacote, finalizar (com justificativa), o
    envio, os dados para o eProtocolo e as versões anteriores.
  - Leitura e conferência (`leitura_anexos.py`, nova): o texto do PDF (pypdf; `pdftotext`
    de segunda) transcrito em campos com "Copiar" e "Copiar tudo"; no comprovante, nº de
    autorização (o código hexadecimal), data, valor e operação, conferidos com a diária do
    ofício e com a diária escrita no RT assinado (ou a recebida/liberada), e "Usar no
    comprovante" grava valor, data e operação no anexo. PDF digitalizado ou imagem: a tela
    diz que não há texto, sem inventar.
- A **visão da equipe** (`prestacoes/equipe/<pk>/`) continua, como apoio (etapas, servidores,
  folhas e conferência), ligada pelo título do bloco e pelo ⋮.

Nenhum modelo, migração ou serviço de escrita novo: as gravações passam pelos serviços de
sempre (`prestacao.salvar_solicitacao`, `diario`, `relatorio`, `anexos`). CSS novo em
`static/css/prestacao.css`, só com tokens; o componente da linha nasceu no UI Lab (§14).

## Consequências

Os testes E2E preenchem a solicitação na lista e navegam pela trilha das folhas; a leitura
dos anexos tem testes com PDFs gerados (WeasyPrint). A gestão de viagens (lista de viagens)
não muda. O sistema modelo foi referência de organização e de comportamento, não de código.
