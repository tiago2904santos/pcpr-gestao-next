# Backlog de melhorias transversais

Formato: `[ESCOPO][TIPO][PRIORIDADE]` — escopo GLOBAL/MÓDULO; tipo COMPONENTE, INTEGRAÇÃO,
PERFORMANCE, UX, SEGURANÇA. Marque `✅ feito (data, commit)` ao concluir.

## Abertas

- `[GLOBAL][COMPONENTE][ALTA]` **Catálogo de textos prontos reutilizável** (seletor acima do
  campo + "guardar como modelo" + tela de manutenção com ordem/ativo/padrão). Motivo e
  justificativa do ofício primeiro; depois RT, despacho, resposta padrão da ASCOM.
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

- ✅ Botão × de limpar unificado (`limpar.js`) para todos os campos (out/2026).
- ✅ Escala 90% sem estreitar o shell (out/2026).
- ✅ Autosave do ofício com atualização ao vivo do editor de documento (03/10/2026).
