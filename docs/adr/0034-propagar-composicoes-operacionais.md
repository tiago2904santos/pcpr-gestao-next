# ADR 0034 — Propagar composições operacionais por consumidor

- Status: aceito
- Data: 2026-10-10
- Fonte: missão explícita de propagação visual do usuário.

## Contexto

Ofícios consolidou componentes e variantes operacionais; outras páginas ainda
utilizam seus invólucros anteriores. Uma substituição global poderia mudar estados,
formulários, documentos e consumidores que ainda não foram revisados.

## Decisão

Migrar um conjunto relacionado por vez, reutilizando variantes existentes do
arquétipo de lista, hero, identidade, registros operacionais, itinerário, conferência
e ações. Roteiros é o primeiro consumidor. IDs, formulários, endpoints, validação e
seletores de comportamento permanecem. O rodapé da lista entra no fragmento de
resultados, para acompanhar contagem/paginação após busca HTMX. Variantes antigas
ficam apenas enquanto possuem consumidores comprovados; remoções são separadas e
documentadas após testes. Evidências usam o mesmo DEMO sem semeadura/reset.

## Consequências

Nenhuma biblioteca ou arquitetura nova. Possível compatibilidade transitória,
registrada por consumidor. Conclusão técnica não representa aprovação estética
automática do usuário. Revisão de Ofícios garante que o consumidor de referência
não regrediu após mudanças compartilhadas.
