# Envios manuais pelo WhatsApp

Decisão do usuário em 18/10/2026: o sistema de testes prepara pendências; a pessoa envia
usando o próprio WhatsApp Business, sem API de envio nem IA. O recebimento existente não
é alterado por este trabalho.

- Uma pendência por servidor e prestação reúne aviso de saque, ofício emitido, RT próprio
  e link de KM (somente para quem responde pelo diário). Itens indisponíveis são informados.
- Mudança do conteúdo substitui a pendência anterior ainda não enviada. O sino leva à
  conferência; a lista mostra pendentes e histórico. Pode atualizar as pendências pelo botão.
- Entrada (19/10/2026): a aba **Agenda › Pendências** (`/agenda/pendencias/`, seção "Envios
  aos servidores"), ao lado do Calendário — não há mais item "Envios manuais" no menu de
  Viagens. A conferência continua em `/viagens/envios/<id>/` e volta para as Pendências; a
  lista `/viagens/envios/` fica como histórico ("Enviados"). A rotina diária também atualiza.
- A mensagem explica cada anexo. O usuário baixa PDF único ou PDFs separados (ZIP) e
  anexa manualmente no WhatsApp, conforme sua escolha expressa. Somente KM é link pessoal.
- O ofício usa a versão corrente; RT só aparece se já existe e está preenchido. Documentos
  alterados invalidam a conferência anterior: preparar novamente antes de baixar/enviar.
- Abrir/copiar/preparar nunca confirma envio. Somente a declaração explícita registra
  quem confirmou e quando. Não se afirma entrega nem leitura.
- Não há anexação ou envio automático. O pacote contém apenas o ofício da viagem e o RT
  do destinatário. Nenhum link público de documentos é criado neste fluxo.
- Abrir conversa usa a mesma aba por padrão, evitando abas acumuladas. Acessar uma aba
  arbitrária já aberta não é permitido pelo navegador. Copiar permite usar essa aba à mão.
- Arquétipos: LIST para pendências; DETAIL para conferência. Reutilizar cartões, registros,
  campos, copiar e botões existentes; sem novo componente visual.
- O transporte padrão passa a `manual`. Reservas de saída por worker e n8n são recusadas
  nesse modo; pendências manuais nunca podem ser reservadas mesmo se mudar o transporte.
  O PREVIEW mantém a demonstração simulada. Links reais exigem URL_PUBLICA acessível.

Evidências e limitações: `docs/automacao/validacao-envios-manuais.md`.
