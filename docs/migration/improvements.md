# Backlog de melhorias transversais

Formato: `[ESCOPO][TIPO][PRIORIDADE]` — escopo GLOBAL/MÓDULO; tipo COMPONENTE, INTEGRAÇÃO,
PERFORMANCE, UX, SEGURANÇA. Marque `✅ feito (data, commit)` ao concluir.

## Abertas

- `[MÓDULO][UX][MÉDIA]` Motorista de fora "servidor de outro ofício": sugerir os ofícios dele no
  mesmo período e preencher ofício/protocolo de origem (a referência tinha
  `oficios-do-motorista`).
- `[GLOBAL][UX][MÉDIA]` "Desfazer" na mensagem depois de arquivar (e então tirar a confirmação).
- `[GLOBAL][UX][MÉDIA]` Rodapé da janela de resumo a 360 px: agrupar Minuta/Word num grupo
  "Documento" dentro de "Mais ações".
- `[MÓDULO][UX][BAIXA]` Numeração: pedir confirmação quando o piso pula muito acima do maior
  número usado.
- `[GLOBAL][PERFORMANCE][MÉDIA]` **Requisições nas folhas de edição** (37 ofício, 26 roteiro): decisão
  do ADR 0021 (proposto). Peso e tempo já no orçamento.
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
- `[GLOBAL][PERFORMANCE][MÉDIA]` Medir listas com DEMO populoso (300+ ofícios) e registrar
  consultas/tempo por página em `docs/quality/performance-report.md` a cada módulo.
- `[GLOBAL][UX][BAIXA]` Mapa do itinerário traçar só a primeira rota (pedido antigo do
  usuário).
- `[GLOBAL][UX][BAIXA]` Categoria da viatura (ônibus, caminhão, unidade móvel) como campo do
  cadastro, para o filtro de veículo não depender de palavras no modelo.

## Feitas

- ✅ Decisões D1–D8 de Ofícios (03/10/2026) — ver decisoes.md.
- ✅ Componentes: janela "pedir motivo" (dialogo_motivo + dialogo.js), combobox remoto com campo
  oculto, alvo de toque mínimo em .divulgacao/botão-link/.escolha, placa de largura fixa nas
  listas (03/10/2026).
- ✅ Orçamentos de peso: CSS/JS minificados no collectstatic (`estaticos.py`, `rjsmin`), editor de
  documento sob demanda, `icone` dentro de `menu.js` — folha do ofício de 165,9→108,3 KB de CSS e
  195,1→113,1 KB de JS (03/10/2026).
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
