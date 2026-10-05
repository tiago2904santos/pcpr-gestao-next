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
- **E4** gerar viagem no deferimento.
- Fora por ora: "preencher com e-mail" e importadores; consultar protocolo (integração
  simulada).
