# Relatório de desempenho — piloto

Medido em 01/10/2026 por `tests/e2e/test_desempenho.py` (Chromium 140 headless, servidor de teste local, PostgreSQL 16, cenário fictício, usuário operador). Valores sem compressão HTTP.

| Página | TTFB | FCP | LCP | CLS | INP | HTML | CSS | JS | Requisições | SQL | Banco |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| / | 20 ms | 100 ms | 100 ms | 0 | 16 ms | 12.2 KB | 70.2 KB | 83.2 KB | 16 | 9 | 5.4 ms |
| /viagens | 47 ms | 148 ms | 148 ms | 0 | 24 ms | 24.5 KB | 70.2 KB | 83.2 KB | 16 | 15 | 13.6 ms |
| /viagens/oficios | 37 ms | 136 ms | 136 ms | 0 | 24 ms | 23.1 KB | 70.2 KB | 83.2 KB | 16 | 11 | 9.7 ms |
| /viagens/oficios/21 | 43 ms | 144 ms | 144 ms | 0 | 16 ms | 23.3 KB | 70.2 KB | 83.2 KB | 16 | 14 | 11.2 ms |
| /viagens/oficios/27/editar | 75 ms | 192 ms | 192 ms | 0 | 24 ms | 37.1 KB | 70.2 KB | 83.2 KB | 16 | 20 | 16.1 ms |
| /viagens/oficios/novo | 20 ms | 120 ms | 120 ms | 0 | 16 ms | 14.2 KB | 70.2 KB | 83.2 KB | 16 | 7 | 4.9 ms |

Orçamentos: TTFB ≤ 300 ms · FCP ≤ 1,2 s · LCP ≤ 1,8 s · CLS ≤ 0,05 · INP ≤ 200 ms ·
HTML ≤ 120 KB · CSS ≤ 90 KB · JS ≤ 110 KB · ≤ 25 requisições · ≤ 25 consultas · ≤ 80 ms de banco.
**Todas as páginas dentro do orçamento.**

## Leitura
- **JS 83 KB** = htmx 52 KB + 8 Web Components (~25 KB) + app.js. Nenhuma biblioteca visual.
- **CSS 70 KB** sem compressão (~13 KB com Brotli em produção). Quatro arquivos cacheáveis.
- **Fonte**: uma Inter variável (48 KB, *preload*, `swap`) — CLS 0.
- **Ícones**: sprite único (18 KB) referenciado por `<use>`.
- **SQL**: trechos e equipe do ofício são carregados **uma vez por requisição**
  (`queries.trechos_de`/`viajantes_de`) e reaproveitados por diárias, prazo, assunto,
  prontidão, conflitos e documento. Antes a tabela de trechos era lida até 7× por página.
  | Página | Antes | Depois |
  |---|---|---|
  | Editar (GET) | 25 | 18 |
  | Revisar e emitir | 26 | 16 |
  | Detalhe (rascunho) | 26 | 17 |
  | Salvar edição (POST) | 37 | 25 |
  Número fixo com equipe de 5 e roteiro de 4 trechos (`TestOrcamentoDeConsultas`, ≤ 20 nas
  páginas e ≤ 25 no POST). Cerca de 9 consultas são do quadro comum (sessão, usuário,
  permissões, lotação, contexto de auditoria).
- **Lista**: número de consultas fixo independentemente do tamanho da página (teste
  `test_lista_tem_orcamento_de_consultas`, ≤ 15).

## Comparação com a referência
A referência carrega `design-system.css` + `ds-v32.css` + `ds-v32-bridge.css` + CSS por
módulo e dezenas de arquivos JS por página (inventário em `docs/product/legacy-lessons.md`);
a lista de Ofícios da referência tem 475 KB de HTML (medido no dump da página) contra
23 KB aqui (20 por página, paginada).
