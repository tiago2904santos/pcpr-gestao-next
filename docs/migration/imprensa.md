# Atendimento à imprensa (ASCOM) — módulo I1

Paridade com o app `atendimento_imprensa` da referência (o "Relatório de atendimento" da
ASCOM), reimplementado no padrão das folhas: nada foi copiado. O comportamento vem das
regras lidas em `models.py`, `services.py`, `forms.py`, `views.py` e `presenters.py` da
referência.

## O que existe

| Tela | Rota | Paridade |
|---|---|---|
| Painel | `/imprensa/` | Pedidos no mês, atendidos (com %), em aberto, deadline vencido (cada um leva à lista filtrada); em aberto pelo deadline; recentes; quem atendeu e veículos que mais pediram no mês; pedidos dos últimos 6 meses |
| Lista | `/imprensa/atendimentos/` | Filas Em aberto, Aguardando fonte, Atendidos e Não responder, com contagens que respeitam a busca. Busca em jornalista, pedido, contato, fontes, resposta e veículo. Filtros: situação, veículo, responsável (pelo atendimento ou pela resposta), período e "só com deadline vencido". Linha: jornalista · veículo, situação, deadline, entrada, responsável, contato e o pedido em uma linha |
| Exportar CSV | `/imprensa/atendimentos/exportar/` | Separador ";", BOM e as 16 colunas da referência, do que está filtrado |
| Novo / folha | `/imprensa/atendimentos/novo/`, `/imprensa/atendimentos/<id>/` | Cartões 1 Pedido, 2 Fontes consultadas, 3 Resposta, 4 Andamento + histórico. Horários "17h03", "16h" ou "17:03". "Outro veículo" usa o veículo de mesmo nome (sem diferença de caixa) ou cria um novo. Deadline nunca antes do pedido (também restrição no banco). Depois de criada, a folha se grava sozinha |
| Andamento | POST `/imprensa/atendimentos/<id>/andamento/` | A situação muda só aqui, para uma situação diferente da atual. Para marcar Atendido é preciso anotação, resposta ou andamento anterior (mensagem da referência). Cada mudança vira um `Andamento` com a anotação |
| Cadastros | `/imprensa/cadastros/equipe/`, `/imprensa/cadastros/veiculos/` | Só o nome; incluir, renomear e excluir. Excluir só o que nenhum atendimento usa, com a contagem na linha. Só quem administra |
| Agenda | fonte "Deadlines da imprensa" | O deadline de cada atendimento vira prazo; o atendimento encerrado entra como encerrado (escondido por padrão) |

O histórico junta o registro e as edições (lidos da trilha de auditoria do banco; edições
seguidas da mesma pessoa em até 20 min viram uma linha) com cada andamento.

## Fora deste módulo (da referência)

- O importador da planilha: depende de decidir de onde vêm as planilhas; fica para depois.
- Palestras e Publicações (os outros submódulos da ASCOM): trilhas próprias.

## Decisões (do agente — a confirmar)

Registradas em [decisoes.md](decisoes.md#atendimento-à-imprensa):

- acesso por um papel novo, `ASCOM_IMPRENSA`, no lugar do "módulo" da referência;
- o papel vê e edita todos os atendimentos, sem escopo por unidade (como na referência);
- os cadastros de apoio ficam com o papel ADMINISTRADOR (na referência, "administrador");
- não há exclusão de atendimento (a referência também não tem).

## Testes

- `gestao/imprensa/tests/test_dominio.py`: regras puras.
- `gestao/imprensa/tests/test_imprensa.py`: acesso, criar, autosave, veículo novo,
  andamento e histórico, lista (filas, busca, filtros), CSV, painel, cadastros, agenda e
  a restrição do banco.
- `tests/e2e/test_imprensa.py`: registrar, gravar sozinho, andamento, filas; sem papel não
  vê; 360 e 1440 px sem rolagem horizontal. Axe em `tests/e2e/test_acessibilidade.py`.

## I2 — preencher com um e-mail (06/10/2026)

- "Preencher com um e-mail" no painel e na lista (`/imprensa/atendimentos/novo/email/`):
  cola-se o e-mail (com De/Enviado em/Assunto) ou a mensagem; a leitura própria
  (`dominio_email.py`, Python puro) sugere data e hora do envio, quem pede (a apresentação
  "Sou X, repórter da Y" ganha do nome do remetente; o nome já usado no histórico mantém a
  grafia), o veículo (o cadastrado citado no texto, ou o do domínio do remetente — que, sem
  cadastro, vai para "Outro veículo" como sugestão), o contato (telefone e e-mail), o pedido
  (assunto + corpo, sem cabeçalhos nem a despedida) e o deadline ("até as 17h de hoje",
  "amanhã", "sexta", "dia 14/10" — a hora vai no texto do pedido, que não tem campo). As
  sugestões vão pela sessão para o atendimento novo (nada do e-mail na URL); o que foi lido
  aparece no aviso; prazo vencido avisa. Nada grava até registrar.
- Fora: a memória por remetente e a leitura de conversas do WhatsApp fala a fala da
  referência (decisão do agente).
