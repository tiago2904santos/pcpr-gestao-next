# Palestras e eventos (ASCOM) — módulo PL1

Paridade com o app `demandas_eventos` da referência (a planilha "Palestras e Eventos
ASCOM"), reimplementado no padrão das folhas, sem copiar código. As regras vêm de
`models.py`, `services.py`, `forms.py`, `views.py` e `presenters.py` da referência.

## O que existe

| Tela | Rota | Paridade |
|---|---|---|
| Painel | `/palestras/` | Em aberto, agendadas, atendidas no ano (pelo ano do evento ou, sem data, da solicitação) com o público, aguardando retorno; próximas; recentes; temas do ano |
| Lista | `/palestras/pedidos/` | Status como abas (contagens com a busca), tipo de evento, tema e período da solicitação; busca em solicitante, descrição, pedido, assunto, palestrante, protocolo, telefone, e-mail, município, tema e local |
| Exportar CSV | `/palestras/pedidos/exportar/` | As colunas da planilha, na ordem dela (MÊS … SERVIDOR), e local, endereço, bairro e CEP no fim |
| Nova / folha | `/palestras/pedidos/nova/`, `/palestras/pedidos/<id>/` | 1 Pedido (data, canal — protocolo com 9 dígitos, só no canal Protocolo —, solicitante com sugestões dos anteriores, telefone e CEP formatados, e-mail em minúsculas), 2 Evento (tipo, período, horário, município Cidade/UF, local e endereço, público), 3 Palestra (temas, palestrantes por busca). Autosave |
| Resposta | POST `/palestras/pedidos/<id>/responder/` | A resposta padrão vem com {solicitante}, {data}, {horario}, {municipio}, {palestrante}, {tema} trocados; ajusta-se e registra (com mudança de status opcional); a última abre no e-mail (mailto) ou no WhatsApp |
| Andamento | POST `/palestras/pedidos/<id>/andamento/` | Etapas (Recebida → Em andamento/Aguardando retorno → Agendada → Atendida); Agendada pede data e palestrante, Atendida pede o público e só aparece depois do dia do evento — o que falta é perguntado e gravado junto |
| Cadastros | `/palestras/cadastros/{palestrantes,temas,respostas}/` | Palestrantes (com vínculo ao cadastro de servidores), temas e respostas padrão; tema e palestrante só saem sem uso |
| Agenda | fonte "Palestras e eventos" | Cada palestra com data, com horário e período; a cancelada entra como encerrada |

## Fora desta fatia (da referência)

- Pedido público (`/pedido/`, sem login, com link de acompanhamento por token e anexo):
  rota aberta a quem não tem conta — fica para uma fatia própria, com revisão de segurança.
- Consultar o protocolo no eProtocolo: a integração ainda é simulada.
- "Preencher com um e-mail" e o importador da planilha.

## PL2a — encaminhar à DG (06/10/2026)

- "Encaminhar à DG" na folha (quem edita palestras; não em cancelada; uma vez só): cria o
  rascunho da solicitação de evento (Eventos Sociais) com datas (fim = início se faltar),
  município, tipo (PCPR na Comunidade/Palestra pelo nome do tipo), solicitante, contato
  (telefone e e-mail), local/endereço e a descrição com tema, palestrante, horário, público
  e "Encaminhada da … #N da ASCOM."; liga as duas (`Palestra.solicitacao_dg`), registra o
  andamento e leva à solicitação para completar órgão, serviços e equipes. Na folha, depois,
  o link "Solicitação à DG #N".
- O que a DG faz (envio, devolução, reenvio, decisão, conclusão, cancelamento) aparece no
  histórico da palestra, lido da solicitação ligada (Palestras pode importar Eventos; o
  contrário, não).
- O choque palestrante × viagem já está nos conflitos de agenda (A2a).
- Continua fora: o pedido público sem login (decisão do usuário), consultar o protocolo no
  eProtocolo (integração simulada), "preencher com e-mail" e o importador da planilha.

## Decisões (do agente — a confirmar)

- papel novo `ASCOM_PALESTRAS` no lugar do módulo `ASCOM_DEMANDAS_EVENTOS`;
- na referência, cada palestra é vista pelos setores de quem a registrou; aqui não há
  setores: o papel vê todas;
- os cadastros de apoio ficam com o próprio papel (como na referência, com quem tem o
  módulo);
- a resposta enviada é guardada à parte (`RespostaEnviada`), com o texto exato.

## Testes

- `gestao/palestras/tests/test_dominio.py`, `gestao/palestras/tests/test_palestras.py`;
- `tests/e2e/test_palestras.py` (registrar, gravar sozinho, agendar pedindo data e
  palestrante, responder; 360 e 1440 px) e axe em `tests/e2e/test_acessibilidade.py`.
