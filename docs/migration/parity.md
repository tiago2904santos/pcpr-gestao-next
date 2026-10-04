# Paridade por módulo

Visão de cima (atualizada em 05/10/2026). O detalhe de cada módulo fica na ficha (`<modulo>.md`) e, para regras finas,
em `docs/parity/<funcionalidade>.md`. Atualize esta tabela ao fechar cada etapa.

Classificação dos itens: `IGUAL` · `MELHORADO` · `DIFERENÇA INTENCIONAL` · `LEGADO` ·
`PENDENTE` · `DESCONHECIDO`.

| Módulo | Situação | Funções da referência cobertas* | Evidência | Ficha |
|---|---|---:|---|---|
| Plataforma / identidade | Parcial — notificações e gestão de usuários (lista, criar, editar, perfis, lotação, ativar/inativar, troca de senha obrigatória) feitas; faltam esqueci a senha (SMTP), rotinas diárias, setor/módulo | 16 / 19 | `gestao/identidade/tests`, `gestao/painel/tests` | — |
| Viagens · Cadastros | **Implementado** (falta só a consulta de CEP, serviço externo) | 21 / 22 | `gestao/cadastros/tests/test_crud.py`, `tests/e2e/test_cadastros.py` | [cadastros.md](cadastros.md) |
| Viagens · Ofícios | **Em fechamento** (falta comparação com a referência em execução) | 30 / 31 (+1 bloqueado: comparação) | `gestao/viagens/tests/test_views.py`, `test_dominio_*`, `tests/e2e/` | [oficios.md](oficios.md) · [regras](../parity/oficio.md) |
| Viagens · Roteiros | **Em paridade** (falta "Finalizados", que depende da prestação de contas) | 12 / 14 | `gestao/viagens/tests/test_roteiros*.py` | [roteiros.md](roteiros.md) |
| Viagens · Termos | **Implementado** (falta "Finalizados", da prestação; anexar assinado na lista ainda só pela folha) | 11 / 12 | `gestao/viagens/tests/test_termos.py`, `test_folha_termo_os.py`, `test_assinados.py`, `tests/e2e/test_termos.py` | [termos.md](termos.md) |
| Viagens · Ordens de serviço | **Implementado** (falta "Finalizadas", da prestação) | 7 / 8 | `gestao/viagens/tests/test_ordens.py`, `test_dominio_ordem_servico.py`, `test_folha_termo_os.py`, `test_assinados.py`, `tests/e2e/test_ordens.py`, `tests/e2e/test_assinados.py` | [ordens.md](ordens.md) |
| Viagens · Planos de trabalho | **Implementado** (falta "Finalizados", dos módulos 8 e 9; decisões do agente pendentes em [decisoes.md](decisoes.md)) | 11 / 12 | `gestao/viagens/tests/test_planos.py`, `test_dominio_plano_trabalho.py`, `gestao/cadastros/tests/test_catalogos_plano.py`, `tests/e2e/test_planos.py` | [planos.md](planos.md) |
| Viagens · Viagem (agrupador) | **Em andamento** — 8a feito (lista, criar, folha, vínculos, novo documento vinculado); faltam prontidão, coerência, gerar em lote, baixar tudo, repetir, cascata | 6 / 13 | `gestao/viagens/tests/test_viagem.py`, `tests/e2e/test_viagem.py` | [viagem.md](viagem.md) |
| Viagens · Prestação de contas | Ausente | 0 / 68 | — | — |
| Documentos (núcleo) | Parcial — via assinada, conferência do PDF e janela "Baixar documentos" feitas; faltam prévia da conferência, "Baixar tudo" da viagem (módulo 8), editor de termo/OS/plano | 14 / 23 | ADR 0018, `test_editor_documento*`, `gestao/viagens/tests/test_assinados.py`, `tests/e2e/test_assinados.py` | [decisoes.md](decisoes.md#via-assinada-módulo-7a--o-que-segue-a-referência-e-o-que-é-decisão-do-agente) |
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
