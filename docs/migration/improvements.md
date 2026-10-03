# Backlog de melhorias transversais

Formato: `[ESCOPO][TIPO][PRIORIDADE]` — escopo GLOBAL/MÓDULO; tipo COMPONENTE, INTEGRAÇÃO,
PERFORMANCE, UX, SEGURANÇA. Marque `✅ feito (data, commit)` ao concluir.

## Abertas

- `[GLOBAL][PERFORMANCE][ALTA]` **Orçamentos de peso estourados** (medidos em 03/10/2026 por
  `tests/e2e/test_desempenho.py`, dívida acumulada de rodadas anteriores; esta rodada somou
  ~5 KB de JS e ~2 KB de CSS):
  folha do ofício CSS 165,9/140 KB (gzip 43,5/30), JS 195,1/130 KB (gzip 65,4/45),
  **43/25 requisições**; folha do roteiro CSS 142,9, JS 142,7, 27 requisições; lista de
  ofícios CSS 148,7 (gzip 36,9); painel CSS gzip 33,0. Caminhos: (1) dividir
  `components.css` por uso real (o teste `test_css_por_pagina` já mapeia classe→pacote);
  (2) carregar `editor-documento.js` só ao abrir o editor; (3) reduzir módulos pequenos
  pré-carregados na folha; (4) avaliar minificação no `collectstatic` (ADR, pois ADR 0002 é
  sem bundler). TTFB/FCP/LCP/CLS/INP e SQL estão dentro do orçamento.
- `[GLOBAL][COMPONENTE][ALTA]` **Janela de resumo genérica** extraída do ofício para Termos,
  OS, PT e roteiros (cabeçalho com placa/chips, grade de cartões equilibrada, rodapé de ações).
- `[GLOBAL][COMPONENTE][ALTA]` **CRUD de cadastro em janela** (lista + janela novo/editar +
  ativo + definir padrão + exclusão bloqueada por vínculo) para todos os catálogos.
- `[GLOBAL][COMPONENTE][MÉDIA]` **Busca por leituras** generalizada (registrar leituras por
  lista: termos, OS, PT, protocolos).
- `[GLOBAL][COMPONENTE][MÉDIA]` **Linha do tempo de processo** a partir do histórico do ofício.
- `[GLOBAL][INTEGRAÇÃO][ALTA]` `gestao/integracoes/eprotocolo` simulado + diagnóstico (E1/E2).
- `[GLOBAL][INTEGRAÇÃO][MÉDIA]` Painel "dados para a Central de Viagens / eProtocolo" com
  botões de copiar (alívio imediato sem API).
- `[GLOBAL][SEGURANÇA][ALTA]` Registro de ferramentas com portão de aprovação antes de
  qualquer automação de escrita (ADR 0020).
- `[MÓDULO][UX][MÉDIA]` Ofícios: exportar CSV respeitando filtros e visibilidade.
- `[MÓDULO][UX][MÉDIA]` Ofícios: tela do piso da numeração anual (gestor).
- `[GLOBAL][PERFORMANCE][MÉDIA]` Medir listas com DEMO populoso (300+ ofícios) e registrar
  consultas/tempo por página em `docs/quality/performance-report.md` a cada módulo.
- `[GLOBAL][UX][BAIXA]` Mapa do itinerário traçar só a primeira rota (pedido antigo do
  usuário).
- `[GLOBAL][UX][BAIXA]` Categoria da viatura (ônibus, caminhão, unidade móvel) como campo do
  cadastro, para o filtro de veículo não depender de palavras no modelo.

## Feitas

- ✅ Catálogo de textos prontos reutilizável (componente + tela + serviço único, inclusive para o
  editor de documento) (03/10/2026).
- ✅ Abertura de janela pelo servidor promovida a `dialogo.js` (global) (03/10/2026).
- ✅ Rodapé fixo na janela de resumo (03/10/2026).
- ✅ Conflito falso entre autosave e "Salvar" (beacon de saída) corrigido (03/10/2026).
- ✅ Menus de ação não abrem mais sob a barra flutuante (todas as listas) (03/10/2026).
- ✅ Alvo mínimo de toque em px (`--alvo-minimo`) contra a escala de 90% (03/10/2026).
- ✅ Dívida de tipos (mypy) em `views_roteiros`/`itinerario`/`forms` zerada (03/10/2026).
- ✅ Botão × de limpar unificado (`limpar.js`) para todos os campos (out/2026).
- ✅ Escala 90% sem estreitar o shell (out/2026).
- ✅ Autosave do ofício com atualização ao vivo do editor de documento (03/10/2026).
