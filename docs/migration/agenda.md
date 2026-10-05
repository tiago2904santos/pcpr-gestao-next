# Agenda (item 15 da fila) — primeira entrega: fontes de Viagens

Ficha levantada em 05/10/2026 da referência (`agenda/{fontes,prazos,feriados,views}.py`).
Fonte de comportamento, não de código.

## Referência

- Uma agenda que junta os compromissos de todos os módulos: viagens, solicitações de evento,
  coffee break, palestras/demandas, prazos (saque das diárias, imprensa, contratos,
  certidões), pautas e feriados (nacionais, do PR e municipais das cidades com compromisso).
- A permissão de cada fonte é a do módulo de origem; fonte fora do acesso nem aparece no
  filtro; pedir uma fonte pelo nome não abre a porta.
- Encerrados (cancelados) escondidos por padrão, com opção de mostrar.
- Prazos: um dia, com destaque "vencido" / "vence em até 7 dias" / "no prazo".
- Calendário FullCalendar (mês, semana, dia, lista), detalhe em dossiê, conflitos (a mesma
  pessoa/viatura em dois compromissos), "meus", escala, pauta semanal em PDF/e-mail,
  assinatura ICS.

## Aqui (05/10/2026)

- `gestao/plataforma/agenda.py`: registro de fontes (a plataforma não conhece os módulos),
  `Compromisso`, grade do mês (domingo a sábado) montada no servidor.
- `gestao/viagens/agenda.py`: fontes **Viagens** (a Viagem, o agrupador — ofício sem viagem
  não aparece, como na referência), **Prazos de saque das diárias** (com a situação pela
  distância de hoje) e **Feriados nacionais** (os mesmos dias que os prazos pulam).
- `gestao/painel/views_agenda.py` + `painel/agenda.html` + `static/css/agenda.css`: mês em
  grade (no celular, lista dos dias com algo) ou lista do mês; filtro por fonte; cancelados
  escondidos com contagem; navegação de mês. Módulo "Agenda" no menu. UI Lab §17.
- **Decisão do agente**: grade própria no servidor em vez de vendorizar o FullCalendar (sem
  bundler, CSP estrita, design system próprio). Semana/dia, dossiê, conflitos, "meus",
  escala, pauta e ICS ficam para as próximas entregas; as fontes de Solicitações, Coffee
  Break, Palestras e Imprensa entram quando esses módulos existirem.

## A2a — semana, dia e conflitos (05/10/2026)

- Fontes novas registradas pelos módulos da ASCOM: **Deadlines da imprensa** (prazo),
  **Pautas** (no dia da pauta, com o horário de início) e **Palestras e eventos** (período e
  horário; cancelada como encerrada).
- Visões **Semana** (sete colunas, domingo a sábado, com o horário de cada compromisso; no
  celular vira lista dos dias com algo) e **Dia** (a lista com os detalhes), além de Mês e
  Lista; navegação anterior/próximo e "Hoje" em cada visão (`?vista=semana&dia=AAAA-MM-DD`).
- **Conflitos de agenda** (`gestao/plataforma/conflitos.py`, paridade com
  `core/conflitos.py`): registro de fontes por contexto, período semiaberto (encostar não
  é sobrepor; só data = dia inteiro), aviso que não bloqueia, cancelados e o próprio
  registro fora. Fontes: `oficios` (equipe, motorista do cadastro, viatura, período dos
  trechos) e `palestras` (palestrante, servidor que é palestrante, pedido repetido no mesmo
  município e data). O aviso do ofício passou a usar o serviço (cruza com as palestras) e a
  folha da palestra mostra os avisos dela.
- Ainda não: "meus", dossiê em janela, escala pessoa × dia, pauta semanal em PDF, assinatura
  ICS, e as fontes de termos/OS/solicitações nos conflitos.
