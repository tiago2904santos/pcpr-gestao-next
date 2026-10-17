# Matriz de paridade funcional — Eventos Sociais

Legado: `Sistema-de-Gest-o-de-Eventos-Sociais` @ `53dbf3f`, app `solicitacoes` (e o que ela usa:
`cadastros`, `core`, integração com viagens, agenda, lembretes). Novo: `gestao/eventos` (+
`gestao/viagens/de_eventos.py`). O legado foi **lido**, não executado; o novo é verificado por
testes automatizados e no navegador (PREVIEW). Abreviações: L = legado, N = novo,
`vs` = `gestao/eventos/views_solicitacoes.py`.

Situações: **Equivalente** · **Parcial** · **Ausente** · **Defeito** (existe no novo, mas com
comportamento errado) · **Substituída** (por solução equivalente, com decisão documentada) ·
**Descontinuada** (decisão documentada) · **Não verificado**. A coluna "Situação final" é
atualizada a cada lote de correções, com a evidência.

| ID | Funcionalidade | Evidência no legado | Equivalente no novo | Situação inicial | Diferença encontrada | Situação final / evidência |
|---|---|---|---|---|---|---|
| EV-F01 | Catálogos (tipo, serviço, equipe, órgão, unidade móvel, texto do despacho) | L cadastros/models.py:5-150 | gestao/eventos/models.py:54-121 | Equivalente | unicidade sem caixa (mais estrita) | Equivalente |
| EV-F02 | Lista do catálogo: busca, ativos/inativos, 25 por página, contagens | L cadastros/views.py:207-256 | gestao/eventos/views.py `catalogo` | Equivalente | — | ver EV-F02b |
| EV-F02b | Paginação do catálogo aparece | — | eventos/catalogo.html:83-85 | **Defeito** | bloco `depois_lista` inexistente em `base.html`: a paginação nunca aparece | |
| EV-F03 | Excluir item em uso | L cadastros/views.py:351-370 | gestao/eventos/catalogos.py:29,112-121 | Equivalente | mesma mensagem | Equivalente |
| EV-F04 | Ativar / inativar | L cadastros/views.py:331-348 | catalogos.py:103; forms.py `_ativos` | Equivalente | — | Equivalente |
| EV-F05 | Quem mantém os catálogos | L cadastros/views.py:121-127 | policies.py:27-33 | Equivalente | por permissão | Equivalente |
| EV-F06 | Auditoria dos catálogos | L LogAuditoria | trigger do banco | Equivalente | padrão da plataforma | Equivalente |
| EV-F07 | Municípios (estado/região) | L cadastros "municipios" | cadastro compartilhado | Substituída | sem região (decisões) | Substituída |
| EV-F08 | Modelo do tipo de evento | L cadastros/views.py:376-450 | views.py `modelo_do_tipo` | Equivalente | — | Equivalente |
| EV-F09 | Campos da solicitação | L solicitacoes/models.py:43-189 | models_solicitacao.py:14-78 | Parcial | sem `regiao` (decisão); total de servidores 0 em vez de nulo | Parcial (documentado) |
| EV-F10 | Fim ≥ início | L models.py:195-204 | models_solicitacao.py:89-93 | Equivalente | — | Equivalente |
| EV-F11 | Protocolo 00.000.000-0 | L forms.py:337-341 | dominio.py:314-320 | Equivalente | — | Equivalente |
| EV-F12 | CEP com 8 dígitos, normalizado | L forms.py:343 | forms.py:76 (só máscara) | **Defeito** | CEP parcial ou lixo é aceito sem normalizar | |
| EV-F13 | Máscara do contato | L form.html `mascara="telefone"` | forms.py:70 | Parcial | aceita telefone ou e-mail, sem máscara | |
| EV-F14 | Motorista: só cargo MOTORISTA ou motorista de viatura | L forms.py:72-89 | forms.py:103-105 | **Defeito** | lista todos os servidores ativos | |
| EV-F15 | Sem unidade móvel limpa motorista e unidade | L forms.py:288-296 | solicitacoes.py:89-91 | Equivalente | — | Equivalente |
| EV-F16 | Operação padrão "Diária" | L forms.py:259 | solicitacoes.py:92 | Equivalente | — | Equivalente |
| EV-F17 | Estado PR e município do estado | L forms.py:251-265 | CampoMunicipio "Cidade/UF" | Substituída | campo combinado | Substituída |
| EV-F19 | Serviços e equipes com quantidade; total recalculado | L forms.py:109-155 | forms.py:122-153 | Equivalente | teto 9999 | Equivalente |
| EV-F20 | Trava de versão (edição concorrente) | L forms.py:317-335 | forms.py:25,110-116 | Equivalente | — | Equivalente |
| EV-F21 | Criar rascunho | L views.py:371-426 | vs `nova` | Equivalente | — | Equivalente |
| EV-F22 | "Salvar e enviar" na criação | L views.py:378,389-402 | vs `nova` | Parcial | o rascunho sempre é salvo; erros agregados, não por campo | |
| EV-F23 | Anexos já na criação | L views.py:276-285 | folha.html (anexos só depois de salvar) | **Ausente** | — | |
| EV-F24 | Rascunho no navegador na "Nova" + "Limpar" | L app.js:2051-2130 | `data-proteger` | Parcial | aviso de saída; autosave só depois de salvar | |
| EV-F25 | Autosave de rascunho/devolvida | — | vs `autosave` | Extra do novo | — | Equivalente+ |
| EV-F26 | Editar rascunho/devolvida (autor) | L permissions.py:96-103 | policies.py:66-68 | Equivalente | — | Equivalente |
| EV-F27 | Histórico campo a campo (inclui serviços e equipes) | L services.py:100-167 | queries.py `historico` | Parcial | serviços/equipes só pelo nome, sem antes→depois | |
| EV-F28 | Histórico do reenvio e de "editar e enviar" | L services.py:625-637 | queries.py (passos com `status` são pulados) | **Defeito** | a diferença dos campos some quando dados e situação mudam juntos | |
| EV-F29 | Requisitos do envio à DG | L services.py:63-73,182-234 | dominio.py:224-274 | Equivalente | mesmas mensagens | Equivalente |
| EV-F30 | Aviso à DG no envio | L services.py:224-233 | solicitacoes.py:172 | Parcial | texto e âncora #despacho diferentes | |
| EV-F31 | Reabrir depois do envio | L services.py:596-647 | solicitacoes.py:177-212 | Parcial | aviso à DG não lista os campos alterados | |
| EV-F32 | Tabela de transições | L services.py:33-51 | dominio.py:186-191 | Equivalente | — | Equivalente |
| EV-F33 | Despacho só pela DG | L permissions.py:62-64 | policies.py:41-42 | Equivalente | — | Equivalente |
| EV-F34 | Validação do despacho | L forms.py:524-555 | dominio.py:277-289 | Equivalente | — | Equivalente |
| EV-F35 | Devolução | L services.py:237-267 | solicitacoes.py:259-267 | Parcial | motivo gravado em `observacoes_dg` (não é limpo no reenvio); quantidades da DG aplicadas mesmo devolvendo | |
| EV-F36 | Efeitos da decisão | L services.py:340-365 | solicitacoes.py:244-274 | Parcial | sem gerar viagem automática (ver EV-F59) | |
| EV-F37 | DG ajusta servidores | L services.py:270-322 | solicitacoes.py:216-241 | **Defeito** | quantidade inválida ou vazia é ignorada sem erro; versão não muda | |
| EV-F38 | "N de M na fila" | L views.py:534-545 | vs `_posicao_na_fila` | Equivalente | — | Equivalente |
| EV-F39 | "Registrar e abrir a próxima" | L views.py:1435-1487 | solicitacoes.py `proxima_da_fila` | Equivalente | — | Equivalente |
| EV-F40 | Escolha do despacho mantida após erro | L views.py:1096-1116 | sessão | Equivalente | — | Equivalente |
| EV-F41 | Textos prontos do despacho se somam | L solicitacoes-form.js:179-190 | texto-pronto.js | Parcial | um texto substitui o anterior | |
| EV-F42 | Resumo do despacho para quem não é DG | L form.html | folha.html:203-205 | Equivalente | — | Equivalente |
| EV-F43 | Marcar como atendida | L services.py:420-451 | solicitacoes.py:323-337 | Equivalente | aviso à DG sem texto | Equivalente |
| EV-F44 | Cancelar o evento preserva a decisão da DG | L services.py:454-491 | solicitacoes.py:340-354 | **Defeito** | grava `decisao_dg="cancelado"`: apaga um "Atender" e conta como decisão da DG no painel | |
| EV-F45 | Transferir responsável | L services.py:494-543 | solicitacoes.py:357-376 | Equivalente | — | Equivalente |
| EV-F46 | Depois de transferir, voltar à lista se não vê mais | L views.py:1225-1227 | vs `transferir` | **Defeito** | usuário comum recebe 404 | |
| EV-F47 | Duplicar | L services.py:546-587 | solicitacoes.py:379-396 | Equivalente | — | Equivalente |
| EV-F48 | Excluir rascunho (com arquivos) | L models.py:386-399 | solicitacoes.py:399-408 | Equivalente | — | Equivalente |
| EV-F49 | Conteúdo dos anexos conferido | L forms.py:371-505 | solicitacoes.py:412-433 | Parcial | só os primeiros bytes; .eml/.txt sem conferência | |
| EV-F50 | Quem mexe nos anexos | L permissions.py:148-157 | policies.py:93-94 | **Defeito** | permite em aguardando/deferida: documento muda durante/depois do despacho sem reenvio | |
| EV-F51 | Histórico de anexos | L views.py:1319-1364 | solicitacoes.py:447,461 | Equivalente | — | Equivalente |
| EV-F52 | Baixar anexo | L views.py:1340-1348 | vs `abrir_anexo` | Equivalente | — | Equivalente |
| EV-F53 | Anexar por janela | L views.py:1289-1337 | formulário na seção | Substituída | padrão de interface | Substituída |
| EV-F54 | Visibilidade | L permissions.py:72-86 | policies.py:37-55 | Equivalente | — | Equivalente |
| EV-F55 | Acesso por URL direta | L views.py:257-269 | vs `_visivel` (404) | Equivalente | — | Equivalente |
| EV-F56 | Etapas com quem e quando | L services.py:650-763 | dominio.py:365-379 | Parcial | sem quem/quando; devolvida aparece na etapa 2 | |
| EV-F57 | Faixa da devolução (motivo, data, quem) | L form.html:91-101 | folha.html:29 | Parcial | só o motivo | |
| EV-F58 | Conflitos de agenda | L core/conflitos.py | conflitos.py | Parcial | recursos conferidos também contra aguardando/devolvida; sem conferência ao vivo | |
| EV-F59 | Geração da viagem | L services.py:368-417 (automática ao atender) | de_eventos.py (manual) | Substituída | decisão "agente — confirmar"; ninguém é avisado de que a deferida precisa de viagem | |
| EV-F60 | Sincronizar a viagem quando reabre | L integracao_viagens.py:665-767 | — | Ausente | documentado como fora (E4) | |
| EV-F61 | Uma viagem por ambiente/setor | L integracao_viagens.py:146-250 | uma por unidade | Substituída | documentado | Substituída |
| EV-F62 | Roteiro, trechos, diárias e anexos na viagem | L integracao_viagens.py:424-530 | — | Substituída | "ficam com a unidade" | Substituída |
| EV-F63 | Multieventos (juntar vizinhas) | L integracao_viagens.py:382-422 | queries.py `vizinhos` (só mostra) | Parcial | — | |
| EV-F64 | Vizinhas na seção Viagem | L views.py:555-560 | queries.py `vizinhos` | Equivalente | regra lida, limites não comparados por execução | Equivalente |
| EV-F65 | Operador de Viagens gera a viagem de solicitação que não vê | L permissions.py:140-145 | vs `_visivel` → 404 | **Defeito** | operador sem "ver todas" não chega à solicitação | |
| EV-F66 | Encerrar a viagem quando o evento não acontece | L integracao_viagens.py:634-662 | de_eventos.py:157-184 | Equivalente | — | Equivalente |
| EV-F67 | Cartão da viagem (o que falta, contador) | L integracao_viagens.py:104-143 | folha.html:214-222 | Parcial | — | |
| EV-F68 | Rotina diária de viagens pendentes | L gerar_viagens_pendentes | — | Ausente | decorre da geração manual | |
| EV-F69 | Pedir coffee break da solicitação | L form.html:88 | pedir_coffee.py | Equivalente | — | Equivalente |
| EV-F70 | Consultar protocolo no eProtocolo | L views.py:1231-1248 | vs `consultar_protocolo` | Equivalente | simulado sem credencial | Equivalente |
| EV-F71 | Sugestão pelo tipo | L sugestoes.py:1-120 | sugestoes.py | Equivalente | base: só as visíveis ao usuário | Equivalente |
| EV-F72 | Solicitantes anteriores | L sugestoes.py:145-193 | sugestoes.py | Equivalente | sem acento; recência pelo pk | Equivalente |
| EV-F73 | Preencher com e-mail: entradas | L preencher_por_email.py | preenchimento.py | Parcial | só texto e .eml (sem .msg/.pdf/.txt/.zip) | |
| EV-F74 | Preencher com e-mail: o que se lê | L preenchimento.py:44-265 | leitura_email.py | Parcial | sem órgão sugerido; menos sinônimos; só municípios do PR | |
| EV-F75 | Preencher com e-mail: só campos vazios | L preencher-por-email.js | vs `preencher` (recarrega) | Parcial | perde o que foi digitado antes | |
| EV-F76 | Preencher com e-mail: guardar o original como anexo | L views.py:287-312 | — | **Ausente** | — | |
| EV-F77 | Preencher com e-mail: repetido e aprendizado | L views.py:315-335 | preenchimento.py (mesmo remetente) | Parcial | sem aprendizado por remetente | |
| EV-F78 | Filas com contagem | L views.py:582-679 | queries.py:18-57 | Equivalente | — | Equivalente |
| EV-F79 | Filas escondidas (próximos, deferidas no ano) e `?status=` como fichas | L views.py:616-630 | vs `_fichas` | Parcial | recorte invisível na tela | |
| EV-F80 | Busca | L views.py:751-771 | queries.py:102-114 | Equivalente | — | Equivalente |
| EV-F81 | Filtros | L forms.py:558-583 | queries.py:88-125 | Equivalente | — | Equivalente |
| EV-F82 | Ordenação (`?ordem=`) | L views.py:685-697 | — | Parcial | ignorada | |
| EV-F83 | Paginação | L views.py:886-891 | vs `lista` | Equivalente | — | Equivalente |
| EV-F84 | Fatos e selo de tempo na linha | L presenters.py:20-160 | queries.py `linha` | Equivalente | — | Equivalente |
| EV-F85 | Ação da linha "Marcar como atendida" | L presenters.py:162-191 | _registro.html | Parcial | não aparece | |
| EV-F86 | Exportação (XLSX padrão, datas reais, ordem da fila) | L views.py:939-1075 | vs `exportar` | Parcial | CSV padrão; datas como texto; ordem fixa | |
| EV-F87 | Lembretes | L lembretes.py | lembretes.py | Equivalente | sino; e-mail desligado (decisão) | Equivalente |
| EV-F88 | Notificação por e-mail | L core/notificacoes.py | plataforma/notificacoes.py | Substituída | decisões.md | Substituída |
| EV-F89 | Agenda (inclui rascunhos e o motorista) | L agenda/fontes.py:282-320 | agenda.py | Parcial | sem rascunhos; "meu" só para o autor | |
| EV-F90 | "Criar aqui" pela agenda | L views.py:418-421 | vs `nova` | Equivalente | — | Equivalente |
| EV-F91 | Painel (indicadores e série) | L dashboard/views.py | painel.py | Equivalente | afetado por EV-F44 | |
| EV-F92 | Resumo diário "N eventos em 30 dias" | L core/rotinas.py:125-170 | — | Não verificado | — | |
| EV-F93 | Visões SQL para Power BI | L migrations 0007, 0010 | — | Ausente | sem decisão documentada | |
| EV-F94 | Exportar/importar entre ambientes; importar planilha | L commands | — | Ausente | "importadores fora por ora" | |
| EV-F95 | Falha de banco no despacho | L views.py:1456-1465 | transação | Não verificado | — | |
| EV-F96 | Anexos em armazenamento privado | L core/private_media.py | `upload_to` + views autenticadas | Não verificado | — | |
