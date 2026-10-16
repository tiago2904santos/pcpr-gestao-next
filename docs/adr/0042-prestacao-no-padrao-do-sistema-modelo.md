# ADR 0042 — Prestação de contas: organização do sistema modelo, peças das folhas de documento

- **Status:** aceito (substitui a ADR 0041)
- **Data:** 2026-10-16

## Contexto

O usuário pediu a prestação de contas organizada como o sistema modelo de gestão de eventos
sociais — a lista com o nº da solicitação e o prazo de saque gravando **na própria lista**,
as páginas de diário de bordo, relatório técnico e documentos, e uma página nova que
transcreve o que está escrito nos anexos (RT, diário e comprovante) com "Copiar" e confere o
valor do comprovante com a diária do ofício e a do RT. Rejeitou uma primeira versão com
componentes próprios ("horrível"): o acabamento tem de ser o das folhas de ofícios, planos,
OS e termos — **as mesmas peças** —, o visualizador/editor de documento tem de ser o mesmo
dessas folhas e os documentos (diário de bordo e RT) têm de sair **iguais aos do sistema
modelo**.

## Decisão

- **Lista** (`/viagens/prestacoes/`): a mesma linha operacional da lista de ofícios
  (`registro-operacional`: placa que abre o resumo, destinos, situação da equipe, período,
  protocolo, unidade, equipe com avatares, viatura, diária por servidor, ⋮ com as ações da
  equipe) e, colada a ela, uma linha de registro (`registro`) por servidor: avatar (o
  motorista em grafite), nome com a situação e o que já foi feito (selos), a nota (cargo,
  CPF, telefone, prazo), a pílula de pendências das listas e, à direita, **nº da solicitação**
  e **prazo de saque** (liberação a limite, `pc-data data-periodo`) gravando sozinhos, a ação
  da vez e o ⋮ (as quatro folhas, pacote, RT em PDF, WhatsApp, arquivar). Abas, atalhos de
  pendência (sem solicitação, sem despacho, sem comprovante, valor ≠ diária, finalizadas no
  mês), busca HTMX, 25 ofícios por página e exportação como antes.
- **Folhas** — 1 Diário de bordo, 2 Relatório técnico, 3 Documentos e fechamento, 4 Leitura
  e conferência — com as peças e o arranjo da folha do termo/OS: `registro_hero` (placa do
  ofício, título da etapa, a frase com situação, ofício, destinos, período, unidade, equipe; o
  **servidor da folha** num menu da equipe, `?servidor=`; o ⋮), a barra `etapas-progresso`,
  o `documento--preparacao` com cartões `secao` numerados, `secao__bloco`, a conferência
  `prontidao-documental` com `checklist`, `texto_pronto`, `registro_valor`, as listas
  `registros` e a barra do rodapé com Voltar e "Salvar e continuar" (espera o autosave).
  - Diário: 1 Trechos e quilometragem (`tabela` com os km e o abastecimento, "Preencher
    pelas distâncias", a conferência do hodômetro), 2 Motorista e viatura (cartões
    `pessoa recurso-selecionado`; trocar só neste diário; viagem realizada), 3 Documento.
  - RT: 1 Custeio (a diária do servidor da folha, translado, combustível, passagem),
    2 Relato (cinco blocos com texto pronto e "Sugerir texto"; copiar de outro RT),
    3 Diária recebida de cada servidor, 4 Documentos (uma página por servidor).
  - Documentos e fechamento (por servidor): 1 Solicitação, 2 Documentos assinados (os cinco,
    como as linhas de documentos do termo, com Anexado/Pendente, os arquivos e o anexar; a
    posição do nº da solicitação no ofício assinado), 3 Fechamento (conferência, finalizar
    com justificativa, envio, aprovar/devolver; eProtocolo e versões anteriores).
  - Leitura e conferência: os `dados-copiaveis` do eProtocolo — nº de autorização, data,
    valor e operação do comprovante, conferidos com a diária do ofício e a escrita no RT
    assinado ("Usar no comprovante" grava no anexo); os campos do RT e do diário assinados.
- **Documento no mesmo editor** (ADR 0018): o diário e cada RT saem no bloco `editores` com
  `viagens/oficios/_editor.html` — índice de páginas, Texto/PDF, Atualizar, formatação,
  versões, "voltar ao modelo", presença. O texto editado por região fica em
  **EdicaoPrestacao** (prestação, chave `diario` | `rt-<pk>`, numero, regiões…), com as
  regras de `edicao_texto.py` e o adaptador genérico de `views_editor_avulso.py`
  (`prestacao_texto.py`: dados, HTML do modelo, regiões, salvar/restaurar/modelo). O PDF,
  o DOCX e o pacote final saem com o texto editado.
- **Documentos iguais aos do modelo**: `diario_bordo.html` (A4 deitado, Arial 8, cabeçalho
  curto, os dados do ofício e da viatura em duas colunas com os rótulos no texto, os trechos
  em doze colunas iguais com "( X ) Sim (   ) Não", o motorista — nome, CPF, assinatura —
  fechando a tabela, sem rodapé) e `relatorio_tecnico.html` (folha ASCOM: brasão 2,8 cm e
  três linhas em negrito 12 pt, Arial 10, referência ao ofício e local/data, título
  sublinhado, tabela do servidor, "VALORES UTILIZADOS NA VIAGEM", as cinco seções em grade,
  a declaração, a linha de assinatura com o CPF, marca e endereço no pé). Liberation Sans
  (OFL) entra nas fontes dos documentos. Escritos aqui, pela referência — nada copiado.

O que já existia e continua: serviços (`prestacao`, `diario`, `relatorio`, `anexos`),
autosave, ids (`ps-{pk}`, `form-ps-{pk}`, `equipe-{pk}`, `envio-{pk}`), regiões `data-vivo`,
finalização/envio/aprovação/devolução, carimbo, versões anteriores, pacotes, planilha. CSS
próprio reduzido ao encaixe dos servidores no registro do ofício, aos campos na linha, ao
trilho de pendências e ao km na tabela (`static/css/prestacao.css`, só tokens).

## Consequências

Uma migração (EdicaoPrestacao) e rotas do editor para a prestação. Os testes E2E navegam
pela barra de etapas e pelo menu do cabeçalho; a justificativa para finalizar com pendência
mora na folha de documentos. A lista de viagens, os ofícios e os demais documentos não
mudam. O UI Lab §14 mostra a linha do ofício com os servidores dentro.
