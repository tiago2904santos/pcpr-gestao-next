# Envios manuais agrupados — diferença intencional

Requisito novo do usuário (18/10/2026), independente do uso institucional da referência.

- Referência local anterior: `views_prestacao._whatsapp` produzia apenas aviso de saque;
  `_cartao.html` abria `wa.me` com `target="_blank"` em cada clique.
- Agora: sino + lista de pendências, por servidor/prestação; mensagem explica saque, ofício,
  RT e KM quando disponíveis. Baixar PDF único ou ZIP e anexar manualmente, conforme a
  escolha do usuário. Abrir conversa usa a mesma aba; copiar permite usar uma já aberta.
- O sistema não afirma envio, entrega ou leitura por abrir/copiar/baixar; a conclusão é
  uma declaração humana com autor e horário. O ofício e o RT não ganham links públicos.
- Reaproveitados: arquétipos LIST/DETAIL, registros, placas, abas, botões, copiar, pacote
  de PDFs, notificações, fila auditada e link de KM. Nenhum novo CSS ou componente JS.
- Referência remota não foi acessada: não contém este requisito e não é necessária para
  redefinir o fluxo de teste pedido pelo usuário.

Evidências: [validação](../automacao/validacao-envios-manuais.md), incluindo capturas 360/1440,
testes de navegador e axe.
