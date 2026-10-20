# ADR 0050 — Desligar IA, automações e eProtocolo por configuração

- **Status:** aceito
- **Data:** 2026-10-19

## Contexto

O usuário pediu para encerrar o projeto e deixá-lo pronto para uso, sem as integrações de IA,
sem as automações (WhatsApp pela API, n8n, comunicações automáticas) e sem o eProtocolo. As
Pendências da Agenda e os envios manuais pelo WhatsApp do operador (ADR 0049) continuam, e
reaproveitam os modelos da automação (`Comunicacao`, `LinkAcesso`).

## Decisão

Três chaves de configuração, lidas do ambiente: `IA_HABILITADA`, `AUTOMACAO_HABILITADA` e
`EPROTOCOLO_HABILITADO`. Ligadas por padrão em DEV/TEST/PREVIEW; desligadas por padrão em
STAGING/PRODUCTION (`production_base`), salvo pedido explícito no ambiente.

Um mecanismo central na plataforma (`gestao/plataforma/recursos.py`), sem conhecer os contextos:

- cada contexto registra os namespaces de URL do recurso (`registrar_rotas`); o
  `RecursosDesligadosMiddleware` responde 404 a essas rotas, para quem entrou ou não;
- views avulsas usam `@recursos.exige(...)` (ex.: "Consultar andamento" do protocolo);
- módulos e itens de menu têm `recurso=`; desligado, somem do menu e da central de módulos;
- rotinas diárias têm `recurso=`; desligado, não rodam;
- o processador de contexto expõe `recursos.ia`, `recursos.automacao`, `recursos.eprotocolo`
  para os templates esconderem botões e blocos.

Com cada chave desligada:

- **IA:** Assistência e Central de ajuda fora do menu e 404; cartões e links de sugestão
  (`painel_ia`, `link_ia`) não aparecem; `servicos.pedir` recusa; `processar_ia` fica parado.
- **Automações:** módulo Automação, API `/api/automacao/` e webhook do WhatsApp em 404;
  `comunicacoes.agendar` não agenda nada que não seja pendência manual; nenhum evento ao n8n;
  lembretes automáticos não rodam; `processar_automacao` fica parado; a seção "Exceções da
  automação" sai das Pendências. Os links pessoais (`/p/`) seguem só para o escopo de KM, que
  o envio manual leva no texto da mensagem.
- **eProtocolo:** "Dados para o eProtocolo" (ofício), "Textos para copiar" (coffee) e
  "Consultar andamento" (solicitação de evento) não aparecem; consultar/abrir pelo serviço
  recusam. O número do protocolo continua digitado à mão.

A retenção (purga de conteúdo vencido) segue na rotina diária mesmo com os recursos desligados.

## Consequências

Nada é apagado e nenhuma migração muda: religar uma chave devolve o recurso como estava. Os
workers `automacao` e `ia` do compose ficam no ar sem fazer nada (sem reinícios em laço); podem
ser parados. Os testes rodam com tudo ligado (padrão) e conferem o comportamento desligado com
`override_settings`.
