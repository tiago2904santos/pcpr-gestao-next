# Módulo 9 — Prestação de contas

Ficha levantada em 05/10/2026 da referência (`viagens_prestacoes/`, fichas
`docs/paridade/prestacoes-*.md`). Fonte de comportamento, não de código.

## Modelo (referência)

- **PrestacaoContas**: uma por ofício (nasce sozinha quando o ofício tem equipe; ofício
  cancelado fica de fora). Status: pendente, em preenchimento, enviada, aprovada, devolvida.
  Guarda roteiro ajustado (o realizado) e dados do eProtocolo.
- **PrestacaoServidor**: uma por servidor do ofício — nº da solicitação, liberação das
  diárias, prazo limite de saque, diária própria (override), arquivada, finalizada (com
  justificativa quando há pendência), envio ao financeiro (enviada em, protocolo, decidida
  em, motivo da devolução), remoção reversível ao sair da equipe (com dados) .
- Prazo para prestar = prazo de saque + **3 dias úteis** (sábado, domingo, feriados nacionais
  fixos e móveis; feriados cadastrados — cadastro de feriados ainda não existe aqui).
- **Diário de bordo** (um por prestação, da equipe): km inicial/final e abastecimento por
  trecho do roteiro efetivo; troca de motorista/viatura só no diário; conferência do
  hodômetro (aviso); documento PDF/XLSX.
- **Relatório técnico** (texto da equipe, documento por servidor): motivo, diária recebida
  (nunca acima da liberada), translado/combustível/passagem, atividade, conclusão, medidas,
  informações complementares; modelos de texto por campo com marcadores; sugestões do plano
  (`resultados.sugestao_para_rt`, já existe aqui).
- **Anexos**: ofício assinado (carimbo do nº da solicitação), despacho (soma), RT assinado,
  DB assinado, comprovantes (soma; valor/data/operação). Remoção marcada, guarda 30 dias.
- **Pacote final** (PDF na ordem oficial), revisão página a página, ZIP da equipe.

## Lista

Um bloco por ofício com um cartão por servidor; 25 ofícios por página. Abas: Não liberadas,
Liberadas, Devolvidas, Arquivados, **Finalizados** (ninguém da prestação com finalizada=False),
Saque vencendo, Prestação vencida; pendências: sem nº de solicitação, sem despacho, sem
comprovante, comprovante ≠ diária, finalizadas no mês. Lote (nº, liberação, prazo) e XLSX.

## Abas "Finalizados"/"Contas prestadas" dos outros módulos

Todas: existe prestação de servidor ligada e nenhuma com finalizada=False (arquivar não
conta), registro não cancelado. Ligação: roteiro → ofícios do roteiro; ofício → própria;
termo → o ofício dele (avulso nunca); OS → ofícios dela; plano e viagem → ofícios da viagem.

## Sub-módulos

- **9a base**: modelos, nascimento pela equipe do ofício, prazos (dias úteis), lista com abas
  e lote, arquivar/finalizar (servidor e equipe), pendências, envio/aprovação/devolução,
  trava de finalizada, histórico; abas Finalizados nos outros módulos.
- **9b diário de bordo** (sem o PWA do celular).
- **9c relatório técnico** (com modelos de texto e sugestões do plano).
- **9d documentos**: anexos com versões, carimbo (ajuste manual), pacote final, baixar.

## Estado

- **9a feito** (05/10/2026): `gestao/viagens/{prestacao,views_prestacao}.py`,
  `dominio/prestacao.py`, tela `viagens/prestacao/lista.html` (bloco por ofício, cartão por
  servidor, lote no cartão, atalhos "pedem atenção"), DEMO em
  `demonstracao.prestacoes_para_avaliar`. Decisões em [decisoes.md](decisoes.md#prestação-de-contas-9a).
- Revisões de segurança e UX (05/10) aplicadas: cartão-formulário com autosave, ação grava o
  digitado, reabrir/reenviar não desfazem aprovação, linha removida e ofício reaberto não se
  alteram, permissão da equipe antes do laço, classes renomeadas (colisão de CSS), âncoras.
- Pendências de 9a que dependem de 9b–9d: despacho, comprovante (e o selo de saque que o
  considera), diário e RT nas pendências de finalizar; rotina diária de avisos.
- Histórico em tela da prestação (finalizada com justificativa, reaberta, enviada,
  devolvida): a trilha do banco já guarda; a linha do tempo na tela fica para a página do
  servidor (9d). Até lá, a justificativa da última finalização aparece no cartão.

## 9b — diário de bordo (05/10/2026)

- `gestao/viagens/{diario,views_diario}.py`, `dominio/diario.py`, folha
  `viagens/diario/folha.html` (placa, frase-resumo, 1 motorista e viatura, 2 trechos com
  autosave, 3 conferência), documento `documentos/diario_bordo.html` (A4 paisagem) e
  planilha; UI Lab §15. Da referência: uma linha por trecho (guarda o digitado quando o
  trecho é refeito), abastecimento padrão "Sim", km final ≥ inicial (única regra que
  impede), avisos do hodômetro (voltou para trás; fora de 20%/mín. 10 km; menor que o último
  km da viatura), troca de motorista (3 modos) e viatura (3 modos) só no diário, trava com a
  equipe toda finalizada, pendência "Preencha o km de todos os trechos do diário de bordo, ou
  anexe o diário assinado." Exigido mesmo sem viatura no ofício (como a referência).
- Fora por agora: roteiro ajustado (o realizado) editável — as linhas seguem os trechos do
  ofício; PWA do celular; diário assinado (9d); correção da distância na tabela permanente.

## Fora ou simulado

eProtocolo (consulta de andamento: simulada), importação do processo em PDF/OCR, posição
automática do carimbo (ajuste manual), PWA do diário no celular, WhatsApp (só link wa.me),
assinatura eletrônica do diário e do RT (nem a referência tem). Avisos (sino) da prestação
entram com a rotina diária.
