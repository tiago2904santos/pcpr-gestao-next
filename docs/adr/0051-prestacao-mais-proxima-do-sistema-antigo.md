# ADR 0051 — Prestação de contas mais próxima do sistema antigo

- **Status:** aceito (revê a ordem das folhas da ADR 0042)
- **Data:** 2026-10-19

## Contexto

Ao encerrar o projeto, o usuário pediu que as páginas de prestação de contas "fiquem mais
parecidas com as do sistema antigo". O Gerenciador de Viagens foi aberto localmente, isolado e
só para leitura (cópia do banco, sem rede), e suas telas foram capturadas como referência
visual — nenhum código, template, CSS ou JS foi copiado. No antigo, cada servidor percorre um
assistente de quatro etapas — **1 Diário de Bordo → 2 Relatório Técnico → 3 Documentos →
4 PDF Final** — com rodapé "Voltar ao …" / "Ir para …"; a etapa Documentos começa pelo
servidor com o número da solicitação, depois os documentos do ofício (ofício e despacho
assinados) e os assinados do servidor (RT, diário, comprovante); o PDF Final mostra a equipe,
o pacote do servidor e "Falta para fechar o PDF final". A lista se chama "Prestações de
Contas", busca "por servidor, ofício, protocolo ou solicitação", filtra por Não liberadas,
Liberadas, Arquivados e Finalizados, mostra "Mostrando 1–20 de N", a viatura do ofício e um
lápis "Abrir prestação" (etapa 1 do servidor).

## Decisão

Seguir o usuário onde a ADR 0042 se afastou do antigo, mantendo o Design System (tokens,
componentes, CSP, a11y) e todas as regras e serviços:

- Barra de etapas com as quatro do antigo: "Leitura e conferência" passa a se chamar
  **Documentos** (mesma rota e mesma leitura dos anexos) e entra **PDF final**
  (`/viagens/prestacoes/equipe/<pk>/pdf-final/?servidor=`), só leitura: equipe com o servidor
  da folha em destaque, o que entra no pacote na ordem, o que falta (com "Ir para
  Documentos") e abrir em nova aba / baixar o pacote (a rota de sempre; `?abrir=1` mostra o
  PDF no navegador).
- Documentos na ordem do antigo: 1 Equipe (o cartão do servidor da folha, com nº da
  solicitação e prazo de saque gravando sozinhos), 2 Documentos do ofício, 3 Relatório técnico,
  4 Diário de bordo, 5 Comprovante de saque/transferência, 6 Versões anteriores. RT e
  comprovante passam a ser os do servidor da folha (troca no cabeçalho), como no antigo.
- Rodapés: "Voltar à lista" / "Ir para Relatório técnico"; "Voltar ao Diário de bordo" / "Ir
  para Documentos"; "Voltar ao Relatório técnico" / "Ir para PDF final"; "Voltar aos
  Documentos" / "Voltar à lista". Os botões que avançam continuam esperando o autosave.
- Lista: título "Prestações de contas", a busca do antigo, as abas Não liberadas, Liberadas,
  Arquivados e Finalizados primeiro, "Mostrando x–y de N equipes", a viatura do ofício e o
  lápis "Abrir prestação" em cada servidor; os menus ganham "3 · Documentos" e "4 · PDF final".
- RT: "Custeios", como no antigo.

Mantido de propósito (com motivo): a lista agrupa os servidores por ofício (o antigo repete o
ofício em um cartão por servidor; o agrupamento evita repetir viatura, trechos e valores e
sustenta as ações da equipe); Finalizar continua pedindo justificativa quando há pendência (no
antigo não valida nada); cabeçalho escuro com a placa do ofício no lugar da faixa
"Identificação" (mostra os mesmos quatro fatos) e migalhas (o antigo não tem); as abas de
pendência e os prazos (pedidos anteriores do usuário); a visão da equipe e a leitura dos
comprovantes (não existem no antigo); paginação no rodapé fixo, 25 ofícios por página.

## Consequências

Uma rota nova só de leitura e nenhuma migração. Testes e E2E acompanham os novos rótulos.
