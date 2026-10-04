# Paridade por módulo

Visão de cima. O detalhe de cada módulo fica na ficha (`<modulo>.md`) e, para regras finas,
em `docs/parity/<funcionalidade>.md`. Atualize esta tabela ao fechar cada etapa.

Classificação dos itens: `IGUAL` · `MELHORADO` · `DIFERENÇA INTENCIONAL` · `LEGADO` ·
`PENDENTE` · `DESCONHECIDO`.

| Módulo | Situação | Funções da referência cobertas* | Evidência | Ficha |
|---|---|---:|---|---|
| Plataforma / identidade | Parcial | 9 / 19 | `gestao/identidade/tests`, `gestao/painel/tests` | — |
| Viagens · Cadastros | **Implementado** (falta só a consulta de CEP, serviço externo) | 21 / 22 | `gestao/cadastros/tests/test_crud.py`, `tests/e2e/test_cadastros.py` | [cadastros.md](cadastros.md) |
| Viagens · Ofícios | **Em fechamento** (falta comparação com a referência em execução) | 29 / 31 (+2 bloqueados: termos, assinatura) | `gestao/viagens/tests/test_views.py`, `test_dominio_*`, `tests/e2e/` | [oficios.md](oficios.md) · [regras](../parity/oficio.md) |
| Viagens · Roteiros | **Em paridade** (falta "Finalizados", que depende da prestação de contas) | 12 / 14 | `gestao/viagens/tests/test_roteiros*.py` | [roteiros.md](roteiros.md) |
| Viagens · Termos | **Implementado** (faltam "Finalizados" e anexar assinado, de outros módulos) | 10 / 12 | `gestao/viagens/tests/test_termos.py`, `tests/e2e/test_termos.py` | [termos.md](termos.md) |
| Viagens · Ordens de serviço | **Implementado** (faltam "Finalizadas" e anexar assinado, de outros módulos) | 6 / 8 | `gestao/viagens/tests/test_ordens.py`, `test_dominio_ordem_servico.py`, `tests/e2e/test_ordens.py` | [ordens.md](ordens.md) |
| Viagens · Planos de trabalho | Ausente | 0 / 12 | — | — |
| Viagens · Viagem (assistente) | Ausente | 0 / 13 | — | — |
| Viagens · Prestação de contas | Ausente | 0 / 68 | — | — |
| Documentos (núcleo) | Parcial | 9 / 23 | ADR 0018, `test_editor_documento*` | — |
| Eventos Sociais | Ausente | 0 / 27 | — | — |
| ASCOM (3 submódulos) | Ausente | 0 / 43 | — | — |
| Coffee Break | Ausente | 0 / 61 | — | — |
| Agenda / relatórios / painel | Ausente (só conflito) | 1 / 10 | — | — |
| Integração eProtocolo | Simulada (E1/E2) | 0 / 4 operações reais | `gestao/integracoes/tests` | [eprotocolo.md](../integrations/eprotocolo.md) |

\* Contagem aproximada por rota da referência com função equivalente no novo (uma tela nova
pode cobrir várias rotas antigas, ex.: a janela de resumo). Serve para dimensionar, não
como prova — a prova está nos testes citados.

## Como a evidência é aceita

"Parece igual" não conta. Um item só vira `IGUAL`/`MELHORADO` quando:
1. o comportamento foi lido no código da referência **ou** observado na referência em execução;
2. existe teste no novo que exercita o mesmo comportamento (nome do teste na ficha);
3. a diferença, se houver, foi classificada e justificada.

Itens comparados apenas pelo código da referência levam a nota "comparado por leitura";
a comparação visual lado a lado depende da referência em execução (credenciais por ambiente).
