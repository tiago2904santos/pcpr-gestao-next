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

**Eventos Sociais** concluído em E1–E4 (catálogos, solicitação com despacho, painel e
lembretes, gerar viagem; [eventos-sociais.md](eventos-sociais.md)). Prestação de contas (9)
segue com 9a–9d feitos; falta a revisão página a página do pacote (13d). Próximo: a fila
abaixo (Agenda A2c, Palestras PL2, Coffee Break, relatórios).

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
| 11b | 9b-2: viagem realizada (trechos realizados na prestação, horários corrigidos, diárias recalculadas sem mudar o ofício; diário segue os realizados; RT com a diária nova e o texto das mudanças) | feito (decisão do agente: sem roteiro à parte) |
| 12 | Prestação 9c: relatório técnico (texto da equipe, custeio, diária recebida ≤ liberada, sugestões, textos prontos por campo com marcadores, PDF/DOCX por servidor, pendência, trava) | feito (sem copiar de outro RT e sem "Sugerir texto") |
| 12b | 9c-2: copiar de outro RT (mesmo evento, depois mesmo destino; só da unidade) e "Sugerir texto" da conclusão e das medidas (regra local) | feito (componente `sugerir.js`, UI Lab §16) |
| 13 | Prestação 9d-1: anexos (despacho, comprovantes com valor/data/operação, RT e diário assinados; ofício assinado = via do módulo 7), versões 30 dias, pendências da referência (soma dos comprovantes = diária), selo de saque com comprovante | feito |
| 13b | 9d-2: pacote final por servidor (ordem oficial, assinados no lugar dos gerados, imagem vira página) e ZIP da equipe com PENDENCIAS.txt | feito |
| 13c | 9d-3: carimbo do nº da solicitação no ofício assinado (posição manual por servidor, prévia, aplicado no pacote sem alterar a via; pendência da referência) | feito (sem posição automática) |
| 13d | Revisão página a página do pacote (ordem/giro/ocultar) | pendente |
| 14b | Rotina diária (plataforma.rotinas: registro por contexto, uma rodada por dia pela marca no banco, middleware no primeiro acesso + comando para cron) e avisos da prestação (saque vencido/vencendo sem comprovante, prestação vencida, documentos gerados/assinados, equipe chegou) | feito (sem "amanhã sai", que fala do PWA) |
| 14 | Finalizados completo (pendências de despacho/comprovante/diário/RT entram com 9b–9d) | feito (pendências na ordem e com os textos da referência em `viagens/prestacao.py:pendencias`, desde 9d-1/9d-3) |
| 15 | Agenda com fontes de Viagens (A1: mês/lista, viagens, prazos de saque, feriados; ver [agenda.md](agenda.md)) | feito (A1) |
| 15b | Agenda A2a: semana/dia, conflitos entre módulos (ofício × palestra), busca global ([busca.md](busca.md)) | feito (A2a) |
| 15c | Agenda A2b: "só os meus", pauta em PDF, escala pessoa × dia | feito (A2b) |
| 15d | Agenda A2c: dossiê, assinatura ICS (link público por token — revisão de segurança), conflitos de termos/OS | pendente |
| 17 | Eventos Sociais E1 (catálogos e modelo do tipo) e E2 (solicitação: folha, envio, despacho da DG, devolução, reenvio, concluir, cancelar, transferir, duplicar, excluir, anexos, lista, CSV, avisos, agenda, conflitos) — ver [eventos-sociais.md](eventos-sociais.md) | feito (E1, E2) |
| 17b | Eventos Sociais E3 (painel com os indicadores da referência, série 6/12/24, despacho da DG; lembretes diários pela rotina) | feito (E3) |
| 17c | Eventos Sociais E4 (gerar viagem da deferida pela folha, com a unidade; cancelar/avisar quando não atendida ou cancelada) | feito (E4 — sem automático, roteiro, anexos, multieventos e sincronização; ver decisoes.md) |
| 16 | ASCOM · Atendimento à imprensa (I1; ver [imprensa.md](imprensa.md)) | feito (sem e-mail/importador) |
| 16b | ASCOM · Publicações (P1; ver [publicacoes.md](publicacoes.md)) | feito (sem e-mail/importador) |
| 16c | ASCOM · Palestras e eventos (PL1; ver [palestras.md](palestras.md)) | feito (PL1) |
| 16d | Palestras PL2: pedido público com acompanhamento (revisão de segurança), choque palestrante × viagem | pendente |
| P | Trilhas paralelas: histórico de roteiros | pendente (telas de roteiros em mudança pela sessão paralela de correção visual) |
| 18 | Coffee Break — especificação levantada ([coffee-break.md](coffee-break.md)); CB1 acesso e cadastros contratuais | feito (CB1) |
| 18b | Coffee Break CB2 (solicitação/etapa 1 e lista: lote pelo município, saldo com trava, vigência, retroativo, antecedência, duplicar, cancelar/reativar/excluir, CSV, lotes com saldo) | feito (CB2 — numeração própria até a decisão) |
| 18c | Coffee Break CB3a (etapas 2 e 3, ordem dos marcos, faturada, ofício, protocolo, andamento do próximo marco, reabrir/encerrar correção) | feito (CB3a) |
| 18d | Coffee Break CB3b (pagamento conjunto: candidatas, espelhamento com histórico, protocolo/atesto com a nota de todas, principal que sai) | feito (CB3b) |
| 18e | Coffee Break CB4 (OS, ofício, certifico e certificado em PDF/prévia; pendências; vias; versão assinada) | feito (CB4) |
| 18f | Coffee Break CB5a (certidões: quadro, anexo com conferência de tipo/CNPJ/validade pelo texto do PDF) | feito (CB5a) |
| 18g | Coffee Break CB5b/c (PDFs da nota e da OB com leitura e avisos; anexo do protocolo e textos do eProtocolo), CB6–CB8 | pendente |
| 19 | Relatórios (agenda/painel: os da referência ainda sem equivalente) — levantar e fatiar | pendente |

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

- Prestação: revisão página a página do pacote (13d) e posição automática do carimbo.
- Eventos Sociais: o que ficou fora de E1–E4 está em [eventos-sociais.md](eventos-sociais.md)
  (geração automática da viagem, roteiro/anexos/multieventos, XLSX, consultar protocolo).

## Falhas conhecidas

- Nenhuma conhecida (05/10): em `6e92030` (E3), suíte rápida 1436 passaram, 0 falhas;
  navegador direcionado (eventos, imprensa, publicações, UI Lab, axe) 21 passaram. A
  regressão de navegador completa não foi rodada depois de `85d58d4` (375 passaram).

- Intermitente (06/10): `tests/e2e/test_coffee.py::test_cadastrar_fornecedor_contrato_e_lote`
  falhou uma vez sob carga (o clique no combobox "Fornecedor" achou o `<select>` nativo
  ainda sem a lista própria); passou sozinho duas vezes em seguida. Em observação.

## Bloqueios externos

Referência em execução (credenciais por ambiente), eProtocolo (credenciamento), Central de
Viagens (canal), hospedagem/n8n (plano e custos).

## Decisões pendentes do usuário (não bloqueiam)

Ver [decisoes.md](decisoes.md): comportamentos adotados de Cadastros e de Planos; botão de
reabrir ofício; uso real do DOCX.

## Próximo comando recomendado

`git status` → ler este arquivo → `uv run pytest -m "not e2e and not visual and not a11y and not perf" -n auto`
→ seguir a fila.
