# Publicações (ASCOM) — módulo P1

Paridade com o app `publicacoes` da referência (o "Relatório de Publicações" da ASCOM),
reimplementado no padrão das folhas, sem copiar código. As regras vêm de `models.py`,
`services.py`, `forms.py`, `views.py` e `presenters.py` da referência.

## O que existe

| Tela | Rota | Paridade |
|---|---|---|
| Painel | `/publicacoes/` | Pautas no mês, publicadas (com % e quantas na AEN), em aberto, tempo médio até publicar (só as publicadas do mês com os horários); para sair; recentes; jornalistas e unidades do mês; 6 meses |
| Lista | `/publicacoes/pautas/` | Filas Pendentes, Em andamento, Publicadas e Canceladas, com contagens que respeitam a busca. Busca em título, fonte, unidade, andamento e link. Filtros: status, jornalista, unidade e período. Linha: título, status, "Publicada em…", entrada, unidade, jornalista, fonte, andamento da pauta aberta |
| Exportar CSV | `/publicacoes/pautas/exportar/` | ";" e BOM, as 19 colunas da referência (com "Tempo até publicar") |
| Nova / folha | `/publicacoes/pautas/nova/`, `/publicacoes/pautas/<id>/` | Cartões 1 Pauta, 2 Edição e publicação, 3 Divulgação (Bitly, SESP, AEN: Sim/Não/em branco; links), 4 Andamento + histórico. Unidade obrigatória (da lista ou "outra unidade", que entra no cadastro). Publicação nunca antes da pauta (também restrição no banco); publicada exige data. Depois de criada, a folha se grava sozinha |
| Andamento | POST `/publicacoes/pautas/<id>/andamento/` | O status muda só aqui, para um diferente do atual. Marcar Publicada sem data usa a data e a hora do registro (nunca antes da pauta) |
| Cadastros | `/publicacoes/cadastros/equipe/`, `/publicacoes/cadastros/unidades/` | Arquétipo `cadastro_nomes` (o mesmo da imprensa): incluir, renomear, excluir o que nenhuma pauta usa. Só quem administra |
| Agenda | fonte "Pautas" | Cada pauta no dia dela, com o horário de início; a cancelada entra como encerrada |

## Fora deste módulo (da referência)

- "Preencher com um e-mail" (inclusive a identificação da unidade no release) e o
  importador da planilha.

## Decisões (do agente — a confirmar)

- acesso por um papel novo, `ASCOM_PUBLICACOES`, no lugar do módulo da referência;
- a "unidade responsável" é um cadastro próprio da ASCOM (como na referência), não o
  cadastro de unidades de Viagens.

## Testes

- `gestao/publicacoes/tests/test_dominio.py`, `gestao/publicacoes/tests/test_publicacoes.py`;
- `tests/e2e/test_publicacoes.py` (registrar, gravar sozinho, publicar; 360 e 1440 px) e
  axe em `tests/e2e/test_acessibilidade.py`.
