# Eventos Sociais — especificação levantada da referência (05/10/2026)

Levantamento de comportamento (não de código) dos apps `cadastros` (catálogos de Eventos
Sociais), `solicitacoes` e `dashboard` da referência, para a reimplementação no padrão
das folhas. Caminhos relativos ao clone da referência.

## Acesso

- O módulo "Eventos Sociais" não tem código de módulo: todo usuário autenticado entra
  (`core/apps.py:11-36`). Perfis (`solicitacoes/permissions.py`): SOLICITANTE (todos),
  GESTOR_DG (único que despacha; também gere usuários), ADMINISTRADOR (cadastros e
  usuários; **não** despacha).
- Visibilidade: superusuário, o responsável (`criado_por`), GESTOR_DG ou ADMINISTRADOR veem
  a solicitação; os demais só as próprias (`permissions.py:72-86`).

## Catálogos (`cadastros/models.py`)

Base comum: `nome` (150, único), `ativo`, carimbos; ordem por nome. Catálogos: Tipo de
evento (com "modelo da solicitação": solicitante padrão, cargo/unidade padrão, órgão padrão,
serviços sugeridos e equipes com quantidade), Serviço, Equipe, Órgão responsável, Unidade
móvel, Texto pronto do despacho (`nome` = rótulo, `texto`). Só ADMINISTRADOR mantém; textos
do despacho também GESTOR_DG. Excluir o que está em uso é recusado ("Este registro não
pode ser excluído porque está vinculado a solicitações ou a outros cadastros. Use a ação
Inativar para retirá-lo dos novos formulários."). Seed: tipos (PCPR na Comunidade, Justiça
no Bairro, Paraná em Ação, Demafe, Inauguração/Solenidade, Evento, Palestra, Reunião,
Visita, Capacitação, Feira), serviços (Emissão de CIN, Coleta de digitais, Atendimento
social, Orientação jurídica, Fotografia para documento), órgãos (Instituto de Identificação
do Paraná, Delegacia-Geral, Delegacia-Geral Adjunta), equipes (Alfa, Bravo, Charlie).

## Solicitação de evento (`solicitacoes/models.py`, `services.py`)

Status: RASCUNHO "Rascunho", AGUARDANDO_DESPACHO "Aguardando despacho", DEVOLVIDA
"Devolvida para correção", DEFERIDA_EM_ANDAMENTO "Deferida — em andamento", ATENDIDA
"Atendida", NAO_ATENDIDA "Não atendida", CANCELADA "Cancelada". Decisão da DG: Pendente,
Atender, Não atender, Evento cancelado (e "Enviar para correção"). Tipo de operação:
Diária (padrão), Extrajornada.

Campos: data da solicitação, início/fim do evento (fim ≥ início), município (região
derivada), tipo, solicitante (nome, cargo/unidade, contato), órgão, unidade móvel (sim/não
e qual), local, endereço, bairro, CEP, protocolo (00.000.000-0), descrição, serviços
(com observação), equipes com quantidade (total recalculado), tipo de operação, quantidade
de CIN, motorista (servidor), decisão/observação/quem e quando da DG, responsável.
Anexos (pdf, imagens, office, eml, msg, txt; 10 MB; conteúdo conferido com a extensão).

Transições: RASCUNHO→AGUARDANDO; AGUARDANDO→DEFERIDA|NÃO ATENDIDA|CANCELADA|DEVOLVIDA;
DEVOLVIDA→AGUARDANDO|CANCELADA; DEFERIDA→ATENDIDA|CANCELADA; reabrir AGUARDANDO/DEFERIDA→
AGUARDANDO (edição depois do envio limpa a decisão: "Alterada depois do despacho: aguarda
novo despacho da DG."). Mensagens e quem pode cada ação estão em `services.py`/`views.py`
(enviar exige campos, ≥1 serviço, ≥1 equipe com quantidade, tipo de operação e a unidade
móvel quando marcada; despacho só GESTOR_DG, observação obrigatória para não atender ou
cancelar; atendida só depois do fim do evento; cancelar com motivo; transferir responsável;
duplicar como rascunho sem datas/protocolo/decisão/anexos; excluir só rascunho).
Trava de versão: "Esta solicitação foi alterada por outra pessoa depois que você abriu a
tela. Recarregue a página antes de salvar."

Lista: trilho de situações (Aguardando despacho — só DG —, Devolvidas, Deferidas,
Confirmar atendimento, Canceladas, Meus rascunhos, Minhas), busca (nº, solicitante, local,
município, protocolo, tipo, órgão), período do evento, município, tipo; selo de tempo
("Evento em N dias", vermelho ≤3, âmbar ≤7) e "Pedido em cima da hora" (< 10 dias).
Folha única: etapas (Enviar para a DG → Aguardando despacho → Deferida → Atendimento),
cartões Dados, Serviços e estrutura, Anexos, Despacho da DG (decisão, textos prontos,
ajuste de servidores, "Registrar e abrir a próxima"), Viagem, Encerramento, Responsável,
histórico com as diferenças. Sugestões: modelo do tipo / serviços e equipes mais comuns;
solicitantes anteriores. Conflitos: unidade móvel, motorista, pedido repetido.

Avisos (sino e e-mail): enviar → DG; devolver/despacho → responsável; concluir/cancelar/
reenvio → DG; transferir → novo e antigo responsável. Lembretes diários: confirmar
atendimento (dia seguinte ao fim), despacho próximo (≤7 dias, à DG), devolução parada
(> 3 dias). Exportação XLSX/CSV com 29 colunas. Integrações: consultar protocolo
(eProtocolo, simulado sem credencial), "preencher com e-mail", **gerar viagem** no
deferimento (uma por "ambiente"/setor, com roteiro de evento, anexos copiados; cancelada
quando não atendida/cancelada sem documentos emitidos).

## Painel (`dashboard/views.py:71-276`)

Solicitações no mês (vs. mês anterior), Aguardando despacho, Deferidas no ano (atendidas e
% das decididas), Eventos nos próximos 30 dias (com unidade móvel); série mensal 6/12/24;
últimas 6; próximos 7; bloco do despacho (tempo médio do envio à decisão, decisões do ano).

## Plano de entrega aqui

- **E1** catálogos (app `gestao/eventos`, arquétipo de cadastros) e modelo do tipo.
- **E2** solicitação: folha, envio, despacho, devolução, reenvio, concluir, cancelar,
  transferir, duplicar, excluir, anexos, histórico, lista, exportação, avisos, agenda e
  conflitos.
- **E3** painel de Eventos Sociais e lembretes diários.

## E2 — o que foi feito (05/10/2026)

- Modelos `Solicitacao`, `SolicitacaoServico`, `SolicitacaoEquipe`, `AnexoSolicitacao`,
  `Movimento` (`gestao/eventos/models_solicitacao.py`), auditados pelo trigger do banco.
- Serviços (`solicitacoes.py`): criar, salvar (rascunho/devolvida), enviar (o que falta,
  com as mensagens da referência; avisa a DG), reabrir e reenviar (só se mudou algo; a
  decisão é desfeita), ajustar servidores, despachar (atender, não atender, cancelado,
  devolver; observação obrigatória quando a referência exige; "Registrar e abrir a
  próxima"), concluir (só depois do fim do evento), cancelar com motivo, transferir,
  duplicar (rascunho sem datas/protocolo/decisão/anexos), excluir (só rascunho), anexos
  (extensões da referência, 10 MB, conteúdo conferido com a extensão).
- Políticas (`policies.py`): qualquer usuário pede; vê as próprias; GESTOR_DG e
  ADMINISTRADOR veem todas; só GESTOR_DG despacha.
- Lista com as filas da referência (Aguardando despacho só para a DG), busca (inclui `#nº`
  e protocolo), período, município e tipo; selo de tempo e "pedido em cima da hora";
  exportação CSV.
- Folha única no padrão das folhas: etapas, Dados, Serviços e estrutura, Anexos, Despacho
  da DG (textos prontos, ajuste de servidores), Encerramento, Responsável e histórico
  (trilha do banco + movimentos). Autosave com trava de versão. "Nova solicitação" com o
  modelo do tipo (`?tipo=`) e com as datas vindas da agenda (`?inicio=&fim=`).
- Agenda (fonte "solicitacao") e conflitos (fonte "solicitacoes": motorista e unidade
  móvel em outro evento no período, pedido repetido no mesmo município); os conflitos
  aparecem também na folha do ofício.
- DEMO: ~30 solicitações em todos os status, textos prontos, unidades móveis e o modelo
  de "PCPR na Comunidade" (`gestao/eventos/demonstracao.py`); o usuário demo é GESTOR_DG.
- Revisões: segurança (fórmula em todas as colunas do CSV, números só ASCII com teto,
  serviço/equipe inativos fora do POST, anexos apagados só depois do commit, visibilidade
  conferida também no despacho) e UX (fila do despacho pelo evento mais próximo, ação
  principal "abrir a próxima", decisão que volta depois de um erro, selos coerentes, ação
  da linha que diz o que faz). Pendentes da revisão de UX: dados em leitura (sem campos
  desabilitados) fora da edição, cores por decisão, unidade móvel só quando marcada.
- Fora do E2: XLSX e a coluna "Região" da exportação (não há região no cadastro de
  municípios aqui), sugestões de solicitantes anteriores, consultar protocolo, "preencher
  com e-mail", gerar viagem (E4), painel e lembretes (E3).
- **E4** gerar viagem no deferimento.

## E3 — o que foi feito (05/10/2026)

- Painel (`/eventos/`, entrada do módulo): os quatro indicadores da referência sobre as
  solicitações que a pessoa vê (no mês vs. mês anterior; aguardando despacho; deferidas no
  ano com atendidas e % das decididas; eventos nos próximos 30 dias com unidade móvel),
  cada um levando à fila com o mesmo recorte; próximos eventos (7) e últimas solicitações
  (6) com a mesma linha da lista; solicitações por mês (6/12/24, série densa no UI Lab
  §18); despacho da DG (dias em média do primeiro envio à primeira decisão, pendentes e as
  decisões do ano). Números numa consulta agregada só.
- Lembretes diários pela rotina da plataforma (`gestao/eventos/lembretes.py`), uma vez só
  por solicitação, tipo e data de referência (`Lembrete`, migração 0006): confirmar o
  atendimento (responsável, depois do fim do evento deferido), despacho com evento em até
  7 dias (DG), devolução parada há mais de 3 dias (responsável); janela de 30 dias.
- Fora (E3): e-mail dos lembretes (o sino é o canal; SMTP institucional é dependência externa)
  e o "simular" do comando da referência (a rotina tem o comando `rodar_rotinas_diarias`).
- Fora por ora: "preencher com e-mail" e importadores; consultar protocolo (integração
  simulada).

## E4 — o que foi feito (05/10/2026)

- "Gerar viagem" na folha da solicitação deferida (seção 5, "Viagem"): a DG ou quem cria
  viagens escolhe a unidade responsável (sugerida pela equipe designada com o nome/sigla da
  unidade, senão a lotação de quem gera; operador de viagens só a própria). A viagem nasce
  em rascunho com título (município/UF — data), período, destino, motivo com "(Solicitação
  #N)", descrição e o tipo de viagem com o nome do tipo de evento; a equipe de viagens da
  unidade é avisada no sino; o movimento "Viagem gerada" entra no histórico. Uma por
  solicitação (enquanto não cancelada).
- Não atendida ou cancelada: a viagem sem documento é cancelada junto ("Solicitação #N
  cancelada: motivo"); com documento, a equipe de viagens da unidade é avisada e decide.
  Uma falha aqui não desfaz o despacho (vira log).
- Arquitetura: o código está em Viagens (`gestao/viagens/de_eventos.py`); Eventos não
  importa Viagens — a folha e os serviços chamam os ganchos (`gestao/eventos/ganchos.py`)
  registrados no `ready` de Viagens; o vínculo é `eventos.ViagemGerada` (auditado).
- Fora do E4 (diferente da referência): geração automática no deferimento, "ambiente" por
  setor (aqui a viagem é de uma unidade), roteiro com sede/trechos/diárias, cópia dos
  anexos, multieventos (juntar eventos vizinhos), meta de servidores por equipe,
  sincronizar a viagem num novo deferimento e o aviso "viagem desatualizada" na folha da
  viagem. Ver decisoes.md.

