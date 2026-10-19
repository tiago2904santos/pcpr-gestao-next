# Validação — pendências e envio manual de documentos

Trabalho em `C:\Users\tiago\pcpr-worktrees\piloto-whatsapp-ia`, branch
`feat/piloto-whatsapp-ia`. A pasta principal não contém o piloto do Claude e apresenta
conflitos anteriores; não foi usada para implementar, nem foram descartadas alterações
existentes de Eventos/Coffee/CSS neste worktree.

## Observar e entender

Pedido: avisar no sistema e deixar o operador enviar no próprio WhatsApp Business.
O usuário escolheu explicitamente baixar PDFs e anexar manualmente. Antes havia aviso
isolado de saque, `wa.me`, `_blank` e ausência de agrupamento com RT/ofício/KM.

## Projetar e implementar

[Regra](../product/envios-manuais.md), [ADR 0049](../adr/0049-preparar-envios-manuais-agrupados.md)
e [paridade intencional](../parity/envios-manuais.md). Domínio puro primeiro; depois serviço,
policies existentes, telas dos arquétipos e testes. `Comunicacao` é a fila auditada;
contexto guarda IDs/versão, conteúdo com retenção guarda texto e instantâneo do RT.

As pendências são atualizadas ao liberar diárias, salvar o RT, gerar PDF e anexar via
assinada de ofício; há rotina diária e botão de atualização para os demais casos. Uma
notificação não lida por destinatário/prestação; a confirmação resolve os avisos do grupo.

## Testar, comparar, criticar e corrigir

- PostgreSQL 16 local descartável, contêiner `pcpr-testdb-envios`, porta 55442. Bancos de
  teste separados para serviços, navegador e verificação geral. Sem acesso a banco remoto.
- [17 testes novos de domínio/serviço/tela passaram](testes-envios-manuais.log) na rodada
  específica. Cobrem chave
  idempotente, notificações, pacote individual, motorista, ZIP/PDF único, confirmação
  explícita, revisão alterada, links revogados, bloqueio de reserva automática, notificações
  resolvidas e recusas de acesso de outra unidade ou de pacote de outra pessoa.
- [2 testes de navegador passaram](navegador-envios-manuais.log), um por largura.
  Uma execução adicional do teste de agendamento, após desligar os eventos de saída no modo
  manual, também passou: nenhum evento de envio é publicado para o n8n.
- Primeira verificação de segurança identificou `assert` no serviço; substituído por
  recusa explícita. Teste de clipboard ajustado para CRLF do Windows. Classes das abas e
  registros ajustadas para usar as existentes do DS. Capturas esperam animações terminarem.
- Download no navegador usa o gerador real de RT e a composição real de PDFs. O WhatsApp
  é interceptado por uma página de teste: nenhuma mensagem foi enviada. A navegação verifica
  contato/telefone de destino, uma única aba, retorno à conferência e conclusão humana.
- [Axe 360](evidencias-envios-manuais/axe-360.json) e
  [axe 1440](evidencias-envios-manuais/axe-1440.json): sem violações nas três telas.
- Capturas em [evidencias-envios-manuais/](evidencias-envios-manuais/): lista, conferência
  e histórico em 360 e 1440 pixels, mais a prestação de contas com o atalho alterado.
  Revisadas visualmente: hierarquia, texto, botões, quebras e ausência de rolagem lateral.
  Corrigidas a posição da ação no registro móvel e a captura com cabeçalho no meio da página.
- Verificação geral: [log do script obrigatório](verificar-envios-manuais.log).
  A primeira rodada foi interrompida em 19%, já com falhas: [log parcial](verificar-envios-manuais-parcial.log).
  Rodada final com `PYTEST_ADDOPTS="--reuse-db --maxfail=1 --tb=short"` e 4 workers,
  para detalhar a primeira falha sem repetir a suíte inteira. Resultado: **719 passaram e
  1 falhou** (`gestao/eventos/tests/test_motoristas.py::test_formulario_renderiza_so_atual_e_mantem_inativo_fora_de_15`,
  linha 60: o seletor não contém `solicitacao=<id>`). Arquivos de Eventos já estavam
  alterados antes deste trabalho e não foram modificados aqui. A suíte completa não ficou
  verde; o [relatório anterior](relatorio-piloto-2026-10-18.md) já registra falhas em Eventos.
  Ruff, 20 contratos de importação, mypy (441 arquivos), bandit, migrações e tsc passaram.
- Revisão adicional: corrigida a volta a um conteúdo anterior. Pendência obsoleta ainda
  não enviada volta a ser pendente com revisão nova; conteúdo já confirmado não é cobrado
  novamente. Os dois casos têm teste; a conferência antiga continua recusada.
- [Medição local do servidor](evidencias-envios-manuais/servidor.json), requisições 200:
  lista 8 consultas/198 ms; conferência 24/111 ms; preparar 39/146 ms. As leituras ficam
  no orçamento de 25 consultas. O POST de preparação ainda excede esse número, com
  revalidação, locks e gravações auditadas; fica registrado como limite de desempenho.
  A medição usou dados sintéticos em transação revertida.
- **Validação específica final: 17 testes de domínio/serviço/tela + 2 de navegador,
  todos passaram.** Capturas 360/1440 revisadas; axe sem violações nas telas de envio e
  na prestação de contas. Nenhum resultado declara envio ou entrega real pelo WhatsApp.

## Limites e ativação

- Não houve deploy. Configurar `AUTOMACAO_TRANSPORTE=manual` no ambiente que receber o
  código; é o padrão novo, mas uma variável anterior explícita precisa ser alterada.
  `URL_PUBLICA` deve ser a origem HTTPS acessível do sistema para o link de KM funcionar.
- Não precisa de credencial Meta/IA/n8n para este envio. Hospedagem existente continua
  necessária. Não houve compra, ativação de canal ou envio a contato real.
- Abrir a conversa na mesma aba evita criar abas; não controla uma aba arbitrária do
  WhatsApp já aberta. Copiar a mensagem é o caminho para usar essa aba manualmente.
  Referência técnica: [MDN window.open](https://developer.mozilla.org/en-US/docs/Web/API/Window/open)
  e [WhatsApp click-to-chat](https://faq.whatsapp.com/5913398998672934).
- Anexar os PDFs e clicar Enviar são ações do operador no WhatsApp. Downloads são
  autenticados e por destinatário; não revogam arquivos que já foram baixados.
- Não altera a integração de recebimento nem promete que ela funciona sem seu canal
  configurado. PREVIEW conserva o transporte simulado interno da demonstração anterior.

O contêiner PostgreSQL exclusivo desta validação foi removido ao terminar; os demais
contêineres e as alterações pré-existentes do worktree foram preservados.
