# ADR 0007 — Componentes complexos: nativo primeiro, biblioteca só com evidência

- **Status:** aceito · **Data:** 2026-10-01

| Necessidade | Decisão | Motivo |
|---|---|---|
| Seletor de data/hora | `input type=date/time` nativo | Acessível, teclado numérico no celular, 0 KB |
| Busca de servidores/viaturas | `<pc-combobox>` remoto + HTMX | Padrão WAI-ARIA, servidor decide o que é válido |
| Diálogos | `<dialog>` nativo | Foco preso e Esc nativos |
| Paleta de comandos | `<pc-comandos>` próprio (~5 KB) | Simples; reusa o menu já filtrado por permissão |
| Mapa de rota (seção Roteiro) | **Leaflet** carregado só nessa seção (exceção) | Biblioteca madura, leve, sem chave de API; tiles OSM |
| Calendário/agenda (módulo futuro) | Tabela HTML semântica + HTMX; avaliar FullCalendar só se houver arrastar-soltar | Calendário mensal simples não justifica 100 KB+ |
| Editor de documento completo (futuro) | Avaliar ProseMirror isolado na tela de edição | Única tela que talvez justifique JS pesado |
