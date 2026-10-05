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

## 9d-2 — pacote final (05/10/2026)

- `gestao/viagens/pacote_prestacao.py`: por servidor, na ordem oficial da referência —
  ofício (via assinada; sem ela, o PDF emitido) → despacho(s) → RT (assinado; senão o
  gerado) → diário (assinado; senão o gerado) → comprovante(s) pela data; imagens viram
  página (Pillow). Sem nº, despacho ou comprovante não há pacote (`pendencias_consolidado`).
  Nome "Prestação solicitação <nº> Ofício <n-ano> <primeiro nome> <destino> <data>.pdf" sem
  acentos; ZIP da equipe com PENDENCIAS.txt de quem não está pronto.
- Fora por agora: revisão página a página (ordem/giro/ocultas) e carimbo do número (9d-3).

## 9d-1 — anexos (05/10/2026)

- `gestao/viagens/{anexos,views_anexos}.py`, folha `viagens/anexos/folha.html` (1 ofício
  assinado, 2 despacho, 3 diário assinado, 4 por servidor: comprovantes e RT assinado,
  5 versões anteriores). Da referência: PDF/PNG/JPG até 10 MB (conferido pelo conteúdo),
  despacho e comprovante somam, assinados substituem, remover/substituir marca e guarda 30
  dias, valor/data/operação do comprovante, trava (servidor × equipe), pendências na ordem e
  com os textos de `pendencias_para_finalizar` (nº, despacho, comprovante, diário ou
  assinado, RT ou assinado, soma ≠ diária).
- **Correção da 9a**: a pendência "Informe o prazo limite de saque" saiu — a referência não
  a cobra (era invenção minha).
- **Decisão do agente**: o ofício assinado da prestação é a via assinada do próprio ofício
  (módulo 7), não um segundo arquivo. A conferir com o usuário.
- Fora: purga física após 30 dias (comando de limpeza), importação do processo (OCR).

## 9c — estado (05/10/2026)

- **Feito**: `gestao/viagens/{relatorio,views_relatorio}.py`, `dominio/relatorio.py`, folha
  `viagens/relatorio/folha.html` (1 relato com textos prontos e sugestões, 2 valores usados,
  3 diária de cada servidor, 4 documentos), documento `documentos/relatorio_tecnico.html`
  (PDF e DOCX por servidor), tipos `rt_*` no catálogo de textos prontos (um padrão por campo,
  marcadores `{destino}` `{periodo}` `{motivo}` `{servidores}` `{atividades}` `{metas}`),
  pendência e trava, link na lista, DEMO.
- **Pendente (9c-2)**: copiar de outro RT, "Sugerir texto" (regra local), "salvar como
  modelo" com nome repetido numerado (hoje o catálogo recusa o nome repetido).

## 9c — relatório técnico (ficha levantada em 05/10/2026)

Fonte: `viagens_prestacoes/rt_services.py`, `services.py` (`build_relatorio_tecnico_context`,
`relatorio_tecnico_default_values`, `aplicar_diaria_recebida`), `forms.py` (custeio),
`core/utils/dinheiro.py`, `documentos/services/document_context.py`.

- **Um RT por prestação** (texto da equipe), **documento por servidor** (nome, CPF, diária
  dele). Campos: descrição do evento (`motivo`), diária, translado, combustível, passagem,
  objetivo da participação (`atividade`), conclusão, medidas a serem adotadas pelo órgão,
  informações complementares.
- **Custeio**: translado "Não houve"/Outro; combustível "Cartão Prime"/Outro; passagem "Não
  houve"/Outro (padrões: Não houve, Cartão Prime, Não houve); "Outro" abre texto livre.
- **Diária recebida por servidor** (o override): um campo "R$ 87,00 (saque)" → valor +
  observação; > 0; **nunca acima do liberado** (mensagem da referência); vazio = usa o
  liberado. Erro de um servidor não derruba o resto.
- **Sugestões iniciais** (só valor inicial dos vazios, nada gravado): descrição = motivo do
  ofício (sem ele, contextualização do plano); objetivo = descrição da viagem (sem ela, metas
  + atividades do plano); conclusão = considerações finais do plano (aqui:
  `resultados.sugestao_para_rt`). Informações complementares = as trocas do diário (motorista,
  viatura) — só preenche se vazio.
- **Copiar de outro RT**: do mesmo evento (viagem) primeiro, depois do mesmo destino; até 10.
- **Modelos de texto por campo** (com um padrão por campo e marcadores `{destino}`,
  `{periodo}`, `{motivo}`, `{servidores}`, `{atividades}`, `{metas}`); "salvar como modelo"
  (nome repetido ganha número). **Sugerir texto** (regra local, sem IA) para conclusão e
  medidas.
- **Data do documento**: hoje, mas não antes do retorno e no máximo retorno + 3 dias úteis.
- **Pendência**: "Escreva a descrição, o objetivo e a conclusão do relatório técnico, ou
  anexe o RT assinado." Trava com a equipe toda finalizada (texto compartilhado).
- Documento: PDF e DOCX; nome `RT_<NOME>_OFICIO_<n-ano>` sem acentos.

## Fora ou simulado

eProtocolo (consulta de andamento: simulada), importação do processo em PDF/OCR, posição
automática do carimbo (ajuste manual), PWA do diário no celular, WhatsApp (só link wa.me),
assinatura eletrônica do diário e do RT (nem a referência tem). Avisos (sino) da prestação
entram com a rotina diária.
