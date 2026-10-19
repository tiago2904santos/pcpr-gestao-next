# ADR 0049 — Preparar envios manuais agrupados por servidor e viagem

- **Status:** aceito
- **Data:** 2026-10-18

## Contexto

O usuário quer usar o próprio número Business, sem contratar API nem IA. O envio separado
abre uma aba por clique e fragmenta aviso, links e documentos. Há fila auditada de
Comunicacao, notificações, projeção de documentos correntes e links pessoais com escopo.

## Decisão

Reutilizar Comunicacao para uma pendência manual, com contexto `manual: true`, chave
idempotente por prestação e resumo criptográfico do conteúdo. Reutilizar o tipo de aviso
de prestação e os mecanismos de auditoria, sem criar uma fila concorrente. A preparação
em POST relê as fontes e emite o link de KM quando elegível; confirmar exige a mesma versão
preparada. O usuário escolheu baixar os PDFs e anexar manualmente.
O conteúdo com prazo fica em ConteudoComunicacao, nunca guardar tokens no contexto auditado.
Downloads autenticados conferem destinatário, prestação e versão; o pacote reutiliza
pacotes.montar para PDF único ou ZIP, sem criar URLs públicas dos documentos. O instantâneo
do RT fica em ConteudoComunicacao com retenção. KM usa seu escopo existente e revalida motorista. O worker e a API não reservam pendências manuais.

Usar navegação na mesma aba para garantir ausência de novas abas. Disponibilizar copiar
para quem prefere a conversa já aberta. Não prometer controlar abas de terceiros nem
anexar arquivos por `wa.me`. O navegador e o WhatsApp exigem confirmação humana.

## Alternativas consideradas

- API oficial: automatiza anexos/envio, mas contraria o fluxo manual e a restrição de custo.
- Automação do WhatsApp Web: acrescenta dependência de sessão e serviço não oficial.
- Apenas trocar `_blank` por nome fixo: COOP/noopener podem separar os contextos e abrir
  outras abas; não garante resolver o problema relatado.
- Links autenticados internos: destinatário precisaria de conta no sistema.

## Consequências

Não há chamada à Meta no envio manual. Hospedagem e manutenção continuam a cargo do
ambiente existente. Abrir o WhatsApp não prova que a pessoa enviou. O link de KM encaminhado
pode ser usado por terceiros durante sua validade; dados alterados invalidam a conferência.
RT não vira documento assinado; seu conteúdo é fixado na preparação para compor os PDFs.
