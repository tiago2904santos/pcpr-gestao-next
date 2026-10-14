# ADR 0036 — Compartilhe o calendário de período entre cadastros

- **Status:** aceito
- **Data:** 2026-10-14

## Contexto

O usuário aprovou o calendário compacto de Termos e pediu sua propagação aos
cadastros com início/fim. Copiar a marcação e os cálculos criaria divergências
visuais, e outros contextos não devem importar telas ou regras de Viagens.
Referência: `docs/product/calendario-periodo-teclado.md` e capturas de Termos.

## Decisão

Extrair a apresentação pura de datas para `gestao.plataforma.periodos` e um
inclusion tag do Design System para `componentes/periodo_calendario.html`.
Reutilizar `pc-data` e seus campos ocultos/contratos de teclado. Cada consumidor
informa rótulo, natureza do período, fonte e IDs; Termos conserva sua origem
efetiva e IDs vivos. O gatilho permanece fora das regiões atualizadas.
Datas mudadas no calendário atualizam imediatamente a apresentação, inclusive
em formulários novos e no diálogo de evento, sem depender de gravação.

## Alternativas consideradas

- Copiar HTML/cálculos por contexto: aumenta manutenção e divergência.
- Importar apresentações de Viagens em outros contextos: viola as fronteiras.
- Substituir datas/horários de itinerários automaticamente: são outro contrato;
  não fazem parte dos casos diretos desta propagação.

## Consequências

Cadastros compartilham uma peça com dias de duração e antecedência distintos.
Nomes dos campos, permissões, valores inválidos, erros e envio são preservados.
O UI Lab demonstra os estados vazio, um dia, período futuro, passado e consulta.
Filtros/intervalos administrativos e horários permanecem pendentes da escolha do usuário.
