# ADR 0041 — Prestação organizada como a gestão de viagens

- **Status:** aceito (revê a parte de rotas da ADR 0040)
- **Data:** 2026-10-16

## Contexto

O usuário pede refazer a prestação de contas "igual, em organização, à gestão de viagens",
só com componentes que já existem e parecida com a gestão de eventos sociais. A lista da
ADR 0040 ainda abria dezenas de campos (um cartão por servidor de cada equipe) e as três
folhas voltavam para ela.

## Decisão

- **Lista** como a das viagens: uma linha operacional (`registro-operacional`) por
  ofício/equipe, com placa do ofício, quantos estão finalizados, o selo mais urgente, o
  prazo mais perto e as pendências (`linha_pendencias`); o ⋮ leva às folhas e ao resumo do
  ofício. Abas, atalhos "pedem atenção", busca HTMX, 25 equipes por página e exportação
  continuam como estavam.
- **Folha da equipe** (`prestacoes/equipe/<pk>/`, `prestacao_equipe`) como a da viagem:
  cabeçalho `registro_hero`, as etapas no topo (`etapas-progresso`, como a solicitação de
  evento), abas das páginas da prestação, seções numeradas — 1 Servidores (os mesmos
  cartões, ids, formulários e autosave), 2 Diário, relatório e documentos (a lista da trilha
  da viagem), 3 Conferência (o mesmo bloco da viagem, por servidor) — e a barra de ações com
  Finalizar equipe ou Registrar envio da equipe.
- **Folhas** (diário, RT, documentos): a primeira aba é "Equipe"; Voltar e Finalizar levam
  à folha da equipe.

Uma rota nova (a folha da equipe), só leitura; nenhum modelo, serviço, regra, endpoint de
escrita ou componente novo. A única regra de CSS acrescentada esconde o aviso de gravação
vazio do cartão.

## Consequências

Os testes que preenchiam os cartões pela lista passam a abri-los pela folha da equipe. A
apresentação vem de `prestacao_equipe.py` (dados prontos de `prestacao` e `anexos`; abrir
não cria diário nem RT).
