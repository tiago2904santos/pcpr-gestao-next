# Trabalho contínuo — estado persistente da migração

> Lido no início de cada sessão e atualizado a cada checkpoint. Se o código real divergir
> deste arquivo, o código vence e este arquivo é corrigido.

Atualizado em 05/10/2026 · ramo `migracao/loop-continuo` · último checkpoint `b4d92d4`.

## Escopo global

Migração integral do sistema de referência (21 apps, ~330 rotas) para o pcpr-gestao-next,
com paridade comprovada por testes, padrão visual das folhas de Ofício/Roteiro, desempenho
medido e integrações preparadas (eProtocolo, Central de Viagens, IA com aprovação, n8n).
Inventário global: [inventario-global.md](inventario-global.md) · matriz: [parity.md](parity.md)
· status por módulo: [status.md](status.md).

## Ciclo

INVENTARIAR → INVESTIGAR → IMPLEMENTAR → TESTAR → COMPARAR → REVISAR → CORRIGIR → MEDIR →
DOCUMENTAR → CHECKPOINT → PRÓXIMA TAREFA. Um relatório não encerra o ciclo.

## Por que a sessão de 04/10 terminou

Evidência: a última ação foi uma resposta final do agente (relatório) sem chamada de
ferramenta, logo após o commit `b4d92d4` — o turno terminou por decisão do agente
(conclusão prematura). Não há registro de limite de uso, erro de ferramenta ou processo
encerrado; o contexto foi compactado uma vez antes e o trabalho continuou depois dela.
Adaptação: este arquivo como fila persistente; relatório não é ponto de parada.

## Módulo atual

**Módulo 7 — núcleo de Documentos.** 7a (via assinada) implementado; próximo: 7b conferência
do PDF assinado (ADR da biblioteca de leitura), depois 7c modal "Baixar documentos".

## Próxima tarefa concreta

Ver a fila abaixo (primeiro item não concluído).

## Fila (ordem por dependência e valor)

| # | Tarefa | Situação |
|---|---|---|
| A | Regressão de navegador completa (não rodava desde `80e3de0`) | feita: 342 ok, 3 falhas só sob `-n 4` (2 orçamento, 1 roteiro); isoladas passam |
| B | Inventário global de lacunas | feito → [inventario-global.md](inventario-global.md) |
| C | parity.md (Planos, Termos, OS) | feito |
| D | Orçamento de desempenho sob carga: mediana de 3 amostras (TTFB/db) | implementado; a regressão A usou o código antigo — validar na próxima completa |
| 1+2 | Via assinada (ofício, justificativa, termo, OS): anexar, trocar, remover, histórico, "dados mudaram"; revisões de segurança e UX aplicadas. O artefato guardado do termo/OS virou a própria via (o gerado continua sob demanda) | feito (7a) |
| 3 | Conferência do assinado + ADR 0022 (`pypdf`) | feito (7b); prévia antes de anexar pendente |
| 4 | Modal "Baixar documentos" reaproveitável (marcados, PDF/DOCX, ZIP/PDF único) | próximo (7c) |
| 5 | Notificações no sistema (sino) a partir da outbox | pendente |
| 6 | Gestão de usuários em tela | pendente |
| 7–9 | Viagem: base/etapas; gerar em lote e baixar tudo; coerência, repetir, anexos | pendente |
| 10–13 | Prestação de contas: base; diário; RT; documentos e assinados | pendente |
| 14 | Abas "Finalizados" (só depois da prestação real) | bloqueado por 10–13 |
| 15 | Agenda com fontes de Viagens | pendente |
| P | Trilhas paralelas: catálogos de Eventos Sociais; ASCOM; busca global; histórico de roteiros | pendente |

## Concluído (com evidência)

| Item | Checkpoint | Testes depois |
|---|---|---|
| Termo/OS no padrão das folhas | `d62e1b1` | rápida 918; navegador completa 306+3 |
| 6a catálogos do plano | `b883809` | rápida 942; axe completo |
| 6b domínio do plano | `afd630a` | domínio 16; estático |
| 6c plano de um evento | `80e3de0` | rápida 1005; navegador completa 342+3 (orçamento sob carga) |
| 6d vários eventos | `a632ab6` | rápida 1013; navegador só direcionado |
| 6e resultados | `b4d92d4` | rápida 1021; navegador só direcionado |

## Iniciado e incompleto

Nenhum (árvore limpa em `b4d92d4`).

## Falhas conhecidas

- Orçamento de desempenho (TTFB/db_ms) estoura com `-n 4`; passa isolado. Investigar (fila #4).

## Bloqueios externos

Referência em execução (credenciais por ambiente), eProtocolo (credenciamento), Central de
Viagens (canal), hospedagem/n8n (plano e custos).

## Decisões pendentes do usuário (não bloqueiam)

Ver [decisoes.md](decisoes.md): comportamentos adotados de Cadastros e de Planos; botão de
reabrir ofício; uso real do DOCX.

## Próximo comando recomendado

`git status` → ler este arquivo → `uv run pytest -m "not e2e and not visual and not a11y and not perf" -n auto`
→ seguir a fila.
