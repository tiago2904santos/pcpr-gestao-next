# Trabalho contínuo — estado persistente da migração

> Lido no início de cada sessão e atualizado a cada checkpoint. Se o código real divergir
> deste arquivo, o código vence e este arquivo é corrigido.

Atualizado em 05/10/2026 · ramo `migracao/loop-continuo` · último checkpoint: ver `git log`.

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

**Módulo 9 — Prestação de contas** ([prestacao.md](prestacao.md)). 9a (base) implementado:
nascimento na emissão, equipe que muda, prazos em dias úteis, lista com abas/lote/ações,
finalizar com justificativa, envio/aprovação/devolução, avisos no sino, planilha, DEMO;
9a-2 (abas Finalizados/Contas prestadas nos outros módulos) feito; 9b (diário de bordo)
feito; 9c (relatório técnico) feito. Próximo: 9d anexos e pacote.

## Próxima tarefa concreta

Ver a fila abaixo (primeiro item não concluído).

## Fila (ordem por dependência e valor)

| # | Tarefa | Situação |
|---|---|---|
| A | Regressão de navegador completa | feita em `a320553`: **357 passaram, 0 falhas** (`-n 4`) |
| B | Inventário global de lacunas | feito → [inventario-global.md](inventario-global.md) |
| C | parity.md (Planos, Termos, OS) | feito |
| D | Orçamento de desempenho sob carga: mediana de 3 amostras (TTFB/db) | validado: passou sob `-n 4` na regressão completa |
| 1+2 | Via assinada (ofício, justificativa, termo, OS): anexar, trocar, remover, histórico, "dados mudaram"; revisões de segurança e UX aplicadas. O artefato guardado do termo/OS virou a própria via (o gerado continua sob demanda) | feito (7a) |
| 3 | Conferência do assinado + ADR 0022 (`pypdf`) | feito (7b); prévia antes de anexar pendente |
| 4 | Janela "Baixar documentos" (ofício, justificativa, termo; viagem no 8) | feito (7c) |
| 5 | Notificações: mecanismo (modelo, notificar, sino, central, e-mail pela outbox desligado) | feito; eventos entram com prestação/solicitações |
| 6 | Gestão de usuários em tela + troca de senha obrigatória | feito |
| 7–9 | Viagem: 8a base/etapas → 8b prontidão e coerência → 8c lote e baixar tudo → 8d repetir e cascata ([viagem.md](viagem.md)) | feito (8a–8d) |
| 10 | Prestação 9a: base (modelos, nascimento, prazos, lista, lote, finalizar, envio) | feito (9a) |
| 10b | 9a-2: abas "Finalizados"/"Contas prestadas" em roteiros, ofícios, termos, OS, planos, viagens | feito (exclusivas com as abas de quando; ofícios: além de Emitidos) |
| 11 | Prestação 9b: diário de bordo (linhas pelos trechos, km com validação, conferência do hodômetro, motorista/viatura só no diário, PDF/XLSX, pendência na finalização, trava pela equipe) | feito (sem roteiro ajustado e sem PWA) |
| 11b | 9b-2: roteiro ajustado (o realizado) editável no diário | pendente |
| 12 | Prestação 9c: relatório técnico (texto da equipe, custeio, diária recebida ≤ liberada, sugestões, textos prontos por campo com marcadores, PDF/DOCX por servidor, pendência, trava) | feito (sem copiar de outro RT e sem "Sugerir texto") |
| 12b | 9c-2: copiar de outro RT (mesmo evento/destino) e "Sugerir texto" (regra local) | pendente |
| 13 | Prestação 9d: anexos (ofício/despacho/RT/DB assinados, comprovantes), carimbo, pacote final | próximo |
| 14 | Finalizados completo (pendências de despacho/comprovante/diário/RT entram com 9b–9d) | depende de 11–13 |
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

- Prestação 9a: pendências para finalizar só conhecem nº de solicitação e prazo de saque
  (despacho, comprovante, diário e RT chegam com 9b–9d); selo de saque ignora comprovante
  até 9d. Rotina diária de avisos (saque vencendo etc.) ainda não existe.

## Falhas conhecidas

- Nenhuma conhecida: suíte rápida completa verde depois do 9b (1221 passaram, 05/10).
  Regressão de navegador completa em `cc007ca`: 367 passaram, 1 falha — orçamento de
  desempenho de `/viagens/oficios/?resumo=` sob 4 workers (db 96,8 ms/80; INP 208/200);
  isolado passa (6/6). Reconferir na próxima regressão (suspeita: carga; a contagem nova de
  "Contas prestadas" na lista de ofícios também entra na conta).

## Bloqueios externos

Referência em execução (credenciais por ambiente), eProtocolo (credenciamento), Central de
Viagens (canal), hospedagem/n8n (plano e custos).

## Decisões pendentes do usuário (não bloqueiam)

Ver [decisoes.md](decisoes.md): comportamentos adotados de Cadastros e de Planos; botão de
reabrir ofício; uso real do DOCX.

## Próximo comando recomendado

`git status` → ler este arquivo → `uv run pytest -m "not e2e and not visual and not a11y and not perf" -n auto`
→ seguir a fila.
