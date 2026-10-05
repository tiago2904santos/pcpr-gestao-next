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

- "Preencher com um e-mail" (leitura de e-mail e sugestões) e o importador da planilha:
  dependem de decidir de onde vêm os e-mails e as planilhas; ficam para depois.
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
