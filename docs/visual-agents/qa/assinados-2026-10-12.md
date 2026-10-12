# AS01 — Anexar/trocar via assinada

Base167b81b. Em implementação/validação; root único editor.
Capturas antes/depois360/768/1440 no Ofício159/2026, pk258, DEMO somente leitura.
Sem console/overflow nesses cenários. Template único atende Ofício, Justificativa,
Termo e OS, mantendo a permissão original de anexação no GET.

Hero canônico compacto, seção contínua, orientação junto ao arquivo com
aria-describedby, consultas ao PDF/via como ações secundárias e barra no fluxo.
Nenhum CSS/JS novo. Preservados arquivo-assinado, multipart, CSRF, voltar,
limite15MB, conteúdo PDF, retorno422 e versões. Sem escrita no DEMO.
Removidos do consumidor pagina-cabecalho e documento--cartoes; bases globais
mantidas porque ainda têm consumidores não migrados.

HTTP30 aprovados em74,57s, log assinados-identidade-http.log.
Teste novo sem JS cobre erro422, anexação, troca/histórico e retorno nas três
larguras; ruff verde. Navegador/axe em execução sessão31709, processos8180/8836
confirmados vivos. Não reiniciar por ausência de saída durante preparação.
Ainda faltam capturas de troca/erro, revisão independente, medição e fechamento.

Revisão independente detectou dois pontos: botão desktop esticado pela coluna
flexível da barra de preparação; teste presume retorno à lista sem query, mas
o GET usa destino_padrao com resumo. Após execução inicial, corrigir teste para
validar hidden voltar e URL correspondente; corrigir barra com contrato compacto
legítimo, sem inventar autosave. Não alterar regra de navegação. Revalidar depois.
Classes inexistentes texto-suave/botao--secundario já substituídas pelo DS real.

Segunda passagem: barra-acoes--confirmacao corrige o botão esticado, variante
reutilizável demonstrada no UI Lab. Capturas de inclusão renovadas nas três
larguras; typecheck e68 tokens aprovados. Readonly7SQL antes/depois, HTML+240bytes,
nenhum JS novo; tempos concorrentes não sustentam ganho de latência.

Rodada inicial terminou5falhas/273,42s: três cliques semJS excederam estabilidade
(não chegaram à expectativa de retorno); duas procuravam #via-assinada antigo
na OS. Teste corrigido para controle atual #editor-ordem [data-anexar-assinado],
mantendo abertura/axe do diálogo e fallback. Clique trial em preview corrigido
passou comJS e semJS; causa anterior de estabilidade ainda não comprovada.
Nova rodada final sessão1245, log assinados-identidade-final.log: candidato
com barra corrigida, retorno real e capturas de erro/troca. Não concluída.

Resultado1245:72 passaram,3falharam,185,23s. Axe do fluxo de via/diálogo e UI Lab
verdes. Duas falhas de envio eram fixture incompleta: Ofício emitido ainda sem
PDF PRONTO; serviço recusa corretamente. Preparação agora processa outbox e
afirma documento_emitido antes do navegador. Terceira falha360 foi estabilidade
do clique; janela própria agora trazida à frente e carregamento networkidle,
sem forceclick nem retirada de asserções. Focado sessão8500 em execução,
log assinados-fallback-cenario.log; aguardar resultado e examinar imagens.

Fechamento técnico:3 casos semJS passaram em138,22s; teclado/foco/axe no erro
passou em51,84s (assinados-fallback-teclado.log). Inclusão, erro e troca nas três
larguras revisados por root e revisor independente; galeria616PNG validada.
Nenhuma falha funcional atual conhecida; timeout anterior de estabilidade do
teste mantido como investigação de automação, causa não comprovada. Não foi
mascarado por forceclick nem remoção de asserções. Aprovação estética pendente.
Bases compartilhadas antigas mantidas nos consumidores restantes; AS01 não
depende mais de pagina-cabecalho/documento--cartoes. Variante da barra é aditiva.
AS01 concluída tecnicamente com essa ressalva explícita. Próxima página VG01.
