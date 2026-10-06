# Decisões do dono do produto

Registro oficial das decisões que mudam regra de negócio, permissão, documento, numeração ou
comportamento institucional. Cada decisão aponta requisitos, arquivos e testes. Pendências
classificadas como **bloqueante** (exige decisão), **não bloqueante** (técnica) ou
**dependência externa** (credencial, autorização, ambiente).

## Ofícios — decisões confirmadas em 03/10/2026

| # | Decisão | Comportamento comprovado na referência | Implementação no novo | Testes | Situação |
|---|---|---|---|---|---|
| D1 | **Arquivar ofícios** — implementar; não é exclusão | `acao == 'arquivar'` muda o status para ARQUIVADO (`viagens_oficios/views.py:829`). Sem botão na tela, sem desarquivar, sem aba, sem regra de quem pode | marca `arquivado_em/por` (migração 0011), `services.arquivar/desarquivar`, `policies.pode_arquivar/desarquivar`, aba **Arquivados**, menu da linha e da janela | `test_servicos.py::TestArquivar`, `test_views.py::TestCicloDeVidaNaTela::test_arquivar_leva_para_a_aba_arquivados` | ✅ implementado e testado |
| D2 | **Reativar cancelado** — só gestor, com justificativa | `reativar()` desliga o cancelamento e **apaga** o motivo (`core/models.py:32`); volta ao status que tinha | `situacao_anterior` (guardada ao cancelar; migração preenche os antigos pelo histórico), `services.reativar`, permissão `viagens.reativar_oficio` (só gestor), janela "pedir motivo" | `test_servicos.py::TestReativarCancelado` (sem permissão, sem justificativa, emitido→emitido com mesmo número e documentos, rascunho→rascunho, histórico de→para), `test_views.py::TestCicloDeVidaNaTela` | ✅ implementado e testado |
| D3 | **Motorista externo** — migrar | modo SERVIDOR/MANUAL; manual exige nome; motorista fora da equipe (manual ou servidor) exige ofício de origem `N/AAAA` e protocolo de 9 dígitos (`services.py:170-195`); diárias contam só a equipe (`forms.py:161`); documento mostra o nome (`documents.py:245`) | campos `motorista_externo*` e `motorista_oficio/protocolo_origem` (migração 0012); bloco "Motorista de fora da equipe" no Transporte da folha (servidor de outro ofício via combobox remoto **ou** pessoa não cadastrada); escolher externo tira a marca da equipe e vice-versa; pendências de paridade; nome no documento; cartão do transporte na janela | `test_servicos.py::TestMotoristaExterno` (nome/ofício/protocolo, exclusão mútua com a equipe, **diárias inalteradas**, documento com o nome, servidor que já está na equipe), `test_views.py::TestMotoristaExternoNaFolha` (folha, CPF/protocolo com pontuação, autosave) | ✅ implementado e testado |
| D4 | **Editor visual principal; validar cobertura do DOCX** | geração DOCX + PDF por tipo | análise em [docx-cobertura.md](docx-cobertura.md); "Baixar DOCX" restabelecido (via emitida ou minuta), a partir do mesmo HTML do PDF | `test_views.py::TestBaixarDocx` | ✅ paridade restabelecida; uso real do Word: evidência pendente do usuário |
| D5 | **Manter filtro por data de criação** | `criacao_de`/`criacao_ate` com calendário próprio; ordenação "Criação: mais recente/antiga" | `criacao_de/criacao_ate` → `data_oficio` (é o que a referência filtra), período na gaveta "Mais filtros", ordenação "Data do ofício" | `test_views.py::TestFiltroPorDataDoOficio` (limites inclusivos, pontas invertidas, data inválida, combinação com situação/busca/ordem, paginação, contagem de filtros) | ✅ implementado e testado |
| D6 | **Lista própria de justificativas** | lista com situações (Todas/Pendentes/Preenchidas), busca, regra de prazo, texto, modelo, editar (janela), excluir (limpa o texto), documentos (`docs/paridade/justificativas-lista.md` da referência) | `/viagens/justificativas/` (item no menu Operação): abas Todas/Pendentes/Preenchidas, busca (número, protocolo, destino, servidor, texto), regra de prazo **anotada no banco** (`queries.com_regra_de_prazo`), janela de escrever/editar com texto pronto (grava no ofício, mesma versão otimista), apagar texto, PDF da justificativa emitida | `test_views.py::TestListaDeJustificativas` (regra do banco = regra do domínio em todo o cenário, abas, gravar/apagar, conflito de versão, emitido/consulta sem edição, busca, consultas fixas) | ✅ implementado e testado |
| D7 | **Marcador "Autorização"** | — | já é o rótulo do marcador "nenhum" na folha (`forms.py`, choices do `marcador`); é só rótulo: o assunto Autorização × Convalidação continua calculado (`dominio/assunto.py`) | `test_views.py` (folha) | ✅ confirmado |
| D8 | **Teto de 40 requisições nas folhas de edição, condicionado a validação** | — | ver §D8 | `tests/e2e/test_desempenho.py` (teto 32 nas folhas), medição com rede emulada em `docs/quality/performance-budgets.md` | ✅ validada: necessidade medida 30 → teto 32 (mais estrito que 40); 25 exige build (ADR 0021 B) |

## Detalhamento

### D1 — Arquivar
- Lacunas da referência (documentadas, não inventadas como regra institucional): não diz quem
  desarquiva, se arquivado pode ser editado, nem como a lista trata arquivados.
- Escolhas técnicas, reversíveis e conservadoras (podem mudar por decisão): arquivar é uma
  marca **ortogonal** à situação (como o cancelamento na referência), com quem e quando;
  **desarquivar** existe (nada se perde); arquivado sai das abas de trabalho e aparece em
  "Arquivados"; permissão de editar ofício (operador e gestor, como a referência exige só
  operador); arquivado não é editado nem emitido até ser desarquivado.

### Regressão corrigida junto
Cancelar e reabrir tinham perdido o botão quando a página de detalhe foi apagada: as ações do
ciclo de vida voltaram no menu da linha e no "Mais ações" da janela de resumo
(`oficios/_acoes_ciclo.html`), decididas por `policies.acoes_do_oficio`.

### D2 — Reativar cancelado
- Diferença intencional: a referência apaga o motivo do cancelamento; aqui o cancelamento
  anterior continua no histórico e a reativação grava responsável, justificativa, situação
  anterior e posterior (Histórico + trilha do banco).
- O ofício volta à situação que tinha antes de cancelar (rascunho ou emitido). O número
  permanece o mesmo (cancelado já ocupava o número); documentos emitidos continuam os mesmos —
  reativar **não** emite de novo.

### D3 — Motorista externo
- Paridade: nome obrigatório; RG, CPF, cargo, unidade e observação opcionais; ofício de origem
  (`N/AAAA`, até 6 dígitos) e protocolo de 9 dígitos obrigatórios para emitir.
- Diárias: o motorista externo **não** entra na conta (a referência conta só a equipe).
- Documento: o nome do motorista externo sai no campo motorista.

### D5 — Data de criação
- Na referência, "criação" é `data_criacao`, que é a **data do ofício** (rótulos "Ofício a partir
  de / até"; desempate por `criado_em`). Aqui: `data_oficio`, rótulo "Data do ofício".
- Filtro `criacao_de`/`criacao_ate` (período) na gaveta "Mais filtros", combinável com busca,
  situação, demais filtros, ordem e paginação; ordenação por criação.

### D6 — Justificativas
- A justificativa continua sendo do ofício (sem cópia de dados): a lista é uma leitura dos
  ofícios com justificativa exigida ou escrita.

### D8 — Requisições
- O teto 40 só vale depois da validação descrita em `docs/quality/performance-budgets.md`.

## Cadastros (módulo 2) — comportamentos adotados da referência, a confirmar

Não são regras inventadas: são o que a referência faz (`viagens_cadastros`). Ficaram
implementados e testados; o usuário pode pedir para mudar sem retrabalho grande.

| Comportamento | Na referência | Aqui | Teste |
|---|---|---|---|
| Operador mantém servidores, viaturas, unidades, cargos e combustíveis | `pode_editar_cadastros` = gestor **ou** operador | permissões `add/change/delete` desses modelos no papel OPERADOR_VIAGENS (antes: só consulta) | `test_crud.py::TestPerfis` |
| Servidor só com o nome; viatura só com a placa | campos opcionais + status RASCUNHO | `cargo`, `unidade`, `combustivel`, `modelo`, `tipo` opcionais; "Falta …" sinalizado; ofício **avisa** sem bloquear | `TestServidor`, `TestViatura`, `TestCadastroIncompletoNoOficio` |
| Nome do servidor único; RG e telefone únicos quando informados | constraints `viagens_servidor_*_unico` | constraints `servidor_nome_unico` (sem caixa), `servidor_rg_unico`, `servidor_telefone_unico` | `test_unicidade_vira_mensagem_no_campo` |
| Diária mínima R$ 0,04 | `TabelaDiariaForm.clean_valor_24h` (P08) | idem | `test_valor_minimo_quatro_centavos` |

## Plano de trabalho — decisões do AGENTE, pendentes de confirmação do usuário

Nenhuma destas foi decidida pelo usuário. Reavaliadas em 05/10/2026 contra (1) a referência,
(2) as decisões já confirmadas (D1–D8 de Ofícios), (3) as ADRs, (4) a integridade documental
e dos dados e (5) os testes. Ficam como estão até o usuário decidir; nenhuma bloqueia.

| Decisão | Referência | Aqui | Confronto | Recomendação | Prova |
|---|---|---|---|---|---|
| Vínculo do plano | liga-se à viagem | liga-se aos ofícios até a viagem (módulo 8) existir | a viagem não existe ainda; os ofícios são o que a viagem agrupava → reversível quando o 8 entrar | manter até o módulo 8; então migrar o vínculo para a viagem | `TestCriacaoDoOficio` |
| Número digitado à mão | editável; salto não vira lacuna | só automático | integridade: evita buraco não rastreado e colisão; coerente com a OS (também do agente) | manter; confirmar se há caso real de número imposto de fora | `TestNumeracao` |
| Finalizar e gerar | dois passos; a lista gerava sem finalizar; a prévia já marcava GERADO | uma ação (POST) que confere, fixa a data e libera PDF/DOCX | integridade: impede gerar por GET/link externo e pular a conferência (achado de segurança) | manter (melhoria de segurança) | `test_finalizar_grava_o_que_esta_na_tela`, `test_documento_pdf_docx_e_previa` |
| Tratamento do coordenador | gênero com padrão masculino | sem padrão; vazio é pendência | integridade do texto oficial (coordenadora saía como "designado") | manter (correção de texto oficial) | `test_tratamento_do_coordenador_e_pendencia` |
| Excluir depois de gerado | permitido (número vira lacuna) | só antes da 1ª geração | integridade documental: o número já saiu num documento; igual à trava da OS | manter; confirmar | `test_depois_de_gerado_nao_exclui` |
| Vários eventos | plano = rascunho do evento atual; efetivo e diárias por evento | evento 1 = campos do plano; demais numa janela; efetivo e deslocamento do plano; valor combinado | resolve 3 ambiguidades da referência (efetivo somado × máximo; diárias por evento frágeis; textos com "________") | manter; **confirmar** se há eventos com equipes diferentes no mesmo plano (aí o efetivo por evento voltaria) | `TestVariosEventos` |
| Só o destino principal nas diárias | sim | mantido | igual à referência | — | `test_copia_das_diarias_ao_centavo` |
| Ordem das seções | DOCX numa ordem, PDF noutra | a do PDF para os dois | um documento, uma ordem | manter | `test_geracao_fixa_data_e_marca_gerado_previa_nao` |
| Aba "Finalizados" | depende das prestações da viagem | **não implementada** | depende dos módulos 8 e 9 | implementar com a prestação de contas, não antes | — |

## Via assinada (módulo 7a) — o que segue a referência e o que é decisão do AGENTE

Fonte: `documentos/services/persistence.py` (`anexar_arquivo_assinado`,
`remover_arquivo_assinado`, `_validar_upload_assinado`), `viagens_oficios/views.py` e
`viagens_ordens/views.py` (`assinatura_artefato`), `viagens_oficios/services.py`
(`reabrir_oficio`), fichas `docs/paridade/termos-*.md` e `oficios-*.md` da referência.

| Ponto | Referência | Aqui | Origem |
|---|---|---|---|
| Documentos que recebem via | ofício, justificativa, termo (por servidor, genérico, viatura) e OS | os mesmos | referência |
| Validação | `.pdf`, até 15 MB, começa com `%PDF-` (mensagens iguais) | igual, também no navegador | referência |
| Anexar outra | versão nova; a anterior "permanece no histórico" | igual, e a anterior é **revogada** ("Substituída por uma via nova.") | agente (achado de segurança: remover a nova traria a antiga de volta; na referência remover limpa a via em vigor, então o efeito final é o mesmo) |
| Remover | revoga, o arquivo fica; "O PDF gerado volta a valer." | igual; remover de novo avisa "já tinha sido removida" | referência + agente |
| Via prevalece no PDF | em todo download | igual; `?versao=original` dá o gerado; DOCX segue gerado | referência |
| Reabrir o ofício | revoga a via (tem de assinar de novo) | reabrir **e retificar** revogam, com o motivo | referência (retificação é a reabertura do sistema novo) |
| OS sem PDF gerado | "Anexar assinado" inativo até haver PDF | só depois da primeira geração | referência |
| Termo sem PDF gerado | idem | o termo é gerado na hora, sempre disponível; anexar vale com o termo ativo | **agente** (não há marca de geração no termo) — confirmar |
| Plano de trabalho | sem rota de anexar assinado | sem via | referência (não inventar) |
| "Assinado, mas os dados mudaram" | comparação do instantâneo | impressão SHA-256 dos dados do documento na hora do anexo (termo e OS) | referência (técnica do agente) |
| Quem abre a via | quem baixa o artefato | ofício: quem vê o ofício; termo/OS: a régua do documento gerado (ativo, quem prepara) | agente (achado de segurança) |
| Termo com via | — | não se exclui (cancelar) | agente (a via é prova; FK protegida) |
| Conferência do PDF (assinatura digital, quem assinou, número, protocolo, nomes) | lida ao anexar e mostrada como aviso, nunca bloqueia | igual (7b, `pypdf`, ADR 0022): campos `/Sig` e carimbos eProtocolo/ICP/gov.br nas 4 primeiras páginas; fica na via e no registro | referência |
| Validação jurídica da assinatura (cadeia ICP-Brasil, revogação) | não faz | não faz: o resultado é aviso, não prova | decisão institucional pendente (exigiria repositório de ACs) |
| Prévia da conferência antes de anexar (modal) | existe (`conferir-assinado`) | ainda não: o resultado aparece depois de anexar | pendente (melhoria; não bloqueia) |
| Limite do corpo | — | 413 acima de 16 MB antes do CSRF; Nginx `client_max_body_size 16m` | agente (achado de segurança) |

## Baixar documentos (módulo 7c)

Fonte: `templates/components/v32/dialogo_baixar.html`, `static/js/baixar-documentos.js`,
`viagens_oficios/views.py` (`baixar`), `viagens_termos/views.py` (`baixar`),
`viagens_oficios/justificativas_views.py` da referência.

| Ponto | Referência | Aqui | Origem |
|---|---|---|---|
| Onde aparece | listas de ofícios, justificativas e termos; painel da viagem | resumo do ofício, lista de justificativas, lista e folha do termo; viagem com o módulo 8 | referência |
| OS e plano | sem janela (só botões de PDF); entram pela viagem | iguais | referência |
| Opções | todos marcados; PDF/DOCX; assinada/original (com PDF e algum assinado); separados/um PDF só (≥2 em PDF); escolhas lembradas | iguais | referência |
| Ordem | a da tela | igual | referência |
| Falha de um documento | aborta o lote com a mensagem | igual | referência |
| Ofício sem PDF | gera e **emite** (reserva número, muda o status) | rascunho sai como **minuta** (marca d'água); emitir continua sendo a ação da folha, com a conferência | **agente** (não emitir por efeito colateral de um download) — confirmar |
| Nome do arquivo único | `<tipo>_sem_referencia_<data>` (defeito) | o nome do documento (`oficio-12-2026.pdf`, `termo-5-generico.pdf`) | agente (correção) |
| Nomes repetidos no ZIP | só a viagem tratava | sempre " (2)", " (3)" | agente |
| Lista dos documentos | embutida no botão (JSON na página) | pedida ao abrir (GET), para as listas não gerarem nada à toa | agente (desempenho) |
| Via que não abre ao juntar | — | mensagem "baixe em arquivos separados" | agente |

## Notificações (sino) — mecanismo

Fonte: `core/models.py` (`Notificacao`), `core/notificacoes.py`, `core/views.py`
(`lista_notificacoes`, `abrir_notificacao`, `marcar_notificacoes_lidas`),
`core/context_processors.py` da referência.

| Ponto | Referência | Aqui | Origem |
|---|---|---|---|
| Modelo | uma linha por destinatário; título 150, mensagem 255, link, lida | igual (`plataforma.Notificacao`), fora da auditoria | referência |
| `notificar` | tira repetidos, inativos e o autor; corta com "…" | igual | referência |
| Central | todas/não lidas/lidas, 25 por página, Abrir (marca lida), Marcar todas | igual, no padrão de lista; link externo é ignorado | referência + agente (segurança) |
| Sino | ponto quando há não lidas | igual (contagem preguiçosa, só quando o cabeçalho lê) | referência |
| E-mail | um por aviso, depois do commit, "[Eventos Sociais]" | pela outbox, **desligado por padrão** (`NOTIFICACOES_POR_EMAIL`), backend console sem `EMAIL_HOST`; assunto "[PCPR]" | agente (nada sai sem SMTP configurado pelo usuário) |
| Eventos de Viagens | prestação (diárias, saque, prestação vencida, documentos, devolução, véspera/chegada), solicitações, eProtocolo, resumo do dia | **ainda nenhum**: a referência não avisa emissão de ofício/termo/OS/plano; os eventos entram com os módulos 9 (prestação), solicitações e rotinas | referência (não inventar avisos) |
| Rotinas diárias | middleware no primeiro acesso do dia | pendente (com a prestação) | — |

## Gestão de usuários

Fonte: `accounts/views.py`, `accounts/forms.py`, `accounts/middleware.py` e
`solicitacoes/permissions.py` da referência.

| Ponto | Referência | Aqui | Origem |
|---|---|---|---|
| Quem gerencia | ADMINISTRADOR, GESTOR_DG e superusuário | ADMINISTRADOR e superusuário (`docs/product/permissions.md`) | regra do projeto |
| Hierarquia | nenhuma (gestor promovia a administrador, editava superusuário) | quem não é superusuário não edita nem inativa superusuário; ninguém tira o próprio perfil de administrador | **agente** (segurança) — confirmar |
| Inativar a si mesmo | bloqueado ("Você não pode inativar o seu próprio usuário.") | igual | referência |
| Campos | nome, sobrenome, usuário, e-mail, perfil (um), setores, servidor | nome completo, usuário, e-mail institucional, perfis (vários, como os papéis do sistema), lotação | referência + modelo novo (papéis + lotação; setor/módulo e vínculo com servidor pendentes) |
| E-mail | obrigatório | obrigatório, único e do domínio institucional (`DOMINIO_EMAIL_INSTITUCIONAL`) quando muda | agente (o domínio já estava configurado e sem uso) |
| Senha | quem cadastra digita; troca obrigatória no próximo acesso | igual (mínimo 10, validadores do Django); "Defina sua senha" sem Cancelar | referência |
| Exclusão | não há | não há (inativar) | referência |
| Esqueci a senha | 4 telas por e-mail | pendente (SMTP institucional) | credencial externa |
| DEMO | — | o usuário demo também é administrador no PREVIEW (dados fictícios) | agente (avaliar a tela) |

## Viagem (módulo 8) — decisões do AGENTE, pendentes de confirmação

| Ponto | Referência | Aqui | Por quê |
|---|---|---|---|
| Excluir viagem com documentos | apaga os documentos só dela (CASCADE) | solta os documentos (ficam sem viagem) | número emitido ou via assinada nunca somem por efeito colateral |
| Cancelar viagem com ofício | operador cancelava tudo | cada documento pelo serviço dele: sem permissão de cancelar ofício (operador), nada é cancelado e a tela explica | a regra de cancelar ofício (gestor) não pode ser contornada pela viagem |
| Reativar em cascata | só os que caíram junto | igual (marca "Viagem cancelada"); roteiros, que não guardam motivo, voltam todos | — |
| Etapas | 5 telas, etapa 1 grava ao avançar | uma folha com cartões; a etapa 1 grava sozinha | padrão das folhas |
| Baixar plano/OS | gerava na hora se faltava | só depois de gerados na folha deles | o download não gera documento oficial |
| Meta da DG, sugestões pelo histórico, anexos de solicitação | existiam | ficam para o módulo Solicitações | dependem dele |

## Prestação de contas 9a

Fonte: `viagens_prestacoes/{signals,services,prazos,models,forms}.py` e `core/feriados.py`
da referência ([prestacao.md](prestacao.md)).

| Ponto | Referência | Aqui | Origem |
|---|---|---|---|
| Quando nasce | a cada gravação do ofício com equipe (sinal), menos cancelado | na **emissão** (e a cada nova emissão/retificação); rascunho não tem prestação | **agente** — rascunho ainda muda de equipe e não deve aparecer para prestar contas; confirmar |
| Quem sai da equipe | sem dados: apagado; com dados: marcado e volta inteiro | igual | referência |
| Prazo para prestar | prazo de saque + 3 dias úteis (fim de semana, feriados nacionais fixos e móveis, feriados cadastrados) | igual, sem feriados cadastrados (o cadastro não existe aqui ainda) | referência; cadastro de feriados pendente |
| Diária liberada | por servidor do roteiro efetivo (teto); "recebida" (override) só quando diferente | por servidor do cálculo do ofício; recebida (override) entra com o RT (9c) | referência |
| Abas | não liberadas, liberadas, devolvidas, arquivados, finalizados (ninguém em aberto), saque vencendo, prestação vencida + pendências | iguais; "pendências" que dependem de anexos (despacho, comprovante) entram com 9d | referência |
| Finalizar com pendência | só com justificativa (registrada) | igual; equipe toda pula quem tem pendência e diz quem | referência |
| Finalizada trava a edição | "Prestação finalizada — reabra para editar." | igual (lote ignora as finalizadas e avisa) | referência |
| Envio ao financeiro | registra data e protocolo; devolução reabre com motivo | igual; **só registra** — nada é enviado a sistema externo | referência + regra do projeto |
| Avisos (sino) | equipe de viagens | equipe de viagens **da unidade do ofício**, menos quem fez a ação | **agente** (quem é de outra unidade nem vê a prestação); confirmar |
| Reabrir enviada/aprovada | permitido (a situação ficava "aprovada" com dados reabertos) | recusado: "para corrigir, devolva com o motivo" | **agente** (revisão de segurança: aprovação não pode ser desfeita por baixo) |
| Reenviar | reenviava todas as finalizadas, inclusive aprovadas | aprovada não volta a "enviada"; pela equipe, só as finalizadas ainda não enviadas | **agente** (mesmo motivo) |
| Quem aprova/devolve | qualquer usuário do módulo (sem separação) | igual (quem altera prestação) | referência — **confirmar** se a aprovação deve ser só da gestão |
| Lista com campos | salvamento automático por campo | autosave por cartão (status no cartão); Enter grava; ação do cartão grava o digitado antes | referência + revisão de UX |
| Ofício reaberto (rascunho) | prestação continuava visível | some da lista até a nova emissão (dados guardados); quem saiu da equipe não se altera pelo pk antigo | agente (coerente com "nasce na emissão") |
| Rotina diária (saque vencendo, prestação vencida, documentos, chegada) | middleware no primeiro acesso do dia; uma vez por dia pelo cache compartilhado | middleware + comando `rodar_rotinas_diarias`; uma vez por dia pela marca única no banco (`RotinaDoDia`), já que não há cache compartilhado configurado; desligado nos testes (`ROTINAS_DIARIAS_NO_ACESSO`) | referência + agente (mecanismo) |
| "Amanhã sai a viagem" | aviso para mandar o link do diário no celular | não sai (o PWA de campo não existe aqui) | agente |
| Abas Finalizados/Contas prestadas | exclusivas com "vão acontecer"/"em andamento"; roteiro pelos ofícios dele, termo pelo ofício (avulso nunca), OS pelos ofícios, plano e viagem pelos ofícios da viagem | iguais; rótulo "Finalizadas" na OS (as abas dela são no feminino) | referência |
| Ofícios: "Contas prestadas" | aba entre as de quando | as abas daqui são da situação do documento (D1): o emitido de contas prestadas continua também em "Emitidos" | agente (mantém D1) |

## Atendimento à imprensa

Fonte: `atendimento_imprensa/{models,services,forms,views,permissions,presenters}.py` da
referência ([imprensa.md](imprensa.md)).

| Ponto | Referência | Aqui | Origem |
|---|---|---|---|
| Quem acessa | quem tem o módulo `ASCOM_ATENDIMENTO_IMPRENSA` | papel novo `ASCOM_IMPRENSA` (o acesso por módulo não existe aqui) | **agente** — confirmar o nome e a quem dar o papel |
| Escopo | todos os atendimentos, sem unidade | igual | referência |
| Cadastros de apoio (equipe, veículos) | só o administrador | papel ADMINISTRADOR | referência (mapeada ao papel daqui) |
| Veículo novo pelo atendimento | "outro veículo" cria o cadastro | igual, sem diferença de maiúsculas | referência |
| Situação | só pelo registro de andamento; Atendido exige anotação, resposta ou andamento anterior | igual; cada mudança vira um `Andamento` | referência |
| Atendido sem resposta | a edição recusa apagar a resposta de um atendido sem andamento | igual | referência |
| Histórico de edições | tabela própria ("Campos atualizados: …") | lido da trilha de auditoria do banco, edições seguidas juntas (20 min) | agente (regra do projeto: auditoria é do banco) |
| Deadline antes do pedido | recusado no formulário | recusado no formulário e por restrição no banco | referência + agente |
| Excluir atendimento | não existe | não existe | referência |
| Preencher com e-mail; importar planilha | existe | fica para depois (depende de definir a origem dos e-mails/planilhas) | pendente |

## Publicações

Fonte: `publicacoes/{models,services,forms,views,permissions,presenters}.py` da referência
([publicacoes.md](publicacoes.md)).

| Ponto | Referência | Aqui | Origem |
|---|---|---|---|
| Quem acessa | módulo `ASCOM_PUBLICACOES` | papel novo `ASCOM_PUBLICACOES` | **agente** — confirmar |
| Escopo | todas as pautas | igual | referência |
| Cadastros de apoio (equipe, unidades) | só o administrador | papel ADMINISTRADOR | referência |
| Unidade responsável | obrigatória (da lista ou "outra unidade", que cria o cadastro) | igual | referência |
| Publicar pelo andamento sem data | data e hora do registro (nunca antes da pauta) | igual | referência |
| Unidade da pauta | cadastro próprio da ASCOM | igual (não é o cadastro de unidades de Viagens) | referência |
| Histórico de edições | tabela própria | trilha de auditoria do banco; a publicação automática aparece só no andamento | agente (regra do projeto) |

## Palestras e eventos

Fonte: `demandas_eventos/{models,services,forms,views,permissions,presenters}.py` da
referência ([palestras.md](palestras.md)).

| Ponto | Referência | Aqui | Origem |
|---|---|---|---|
| Quem acessa | módulo `ASCOM_DEMANDAS_EVENTOS`; cada palestra visível aos setores de quem a registrou | papel `ASCOM_PALESTRAS`, vê todas (não há setores) | **agente** — confirmar |
| Cadastros de apoio | quem tem o módulo | o próprio papel | referência |
| Status | só pelo andamento; Agendada pede data e palestrante; Atendida pede público e só depois do dia | igual | referência |
| Resposta padrão | marcadores {solicitante} {data} {horario} {municipio} {palestrante} {tema}; registro no histórico | igual; a resposta enviada fica guardada à parte, com o texto | referência + agente |
| Protocolo | só no canal Protocolo, 9 dígitos | igual | referência |
| Pedido público, encaminhar à DG, consultar protocolo | existem | fora da PL1 (segurança; Solicitações; integração simulada) | pendente |

## Eventos Sociais — solicitações (E2)

Fonte: `solicitacoes/{models,services,permissions,views}.py` da referência
([eventos-sociais.md](eventos-sociais.md)).

| Ponto | Referência | Aqui | Origem |
|---|---|---|---|
| Quem pede / vê / despacha | todos pedem; responsável, GESTOR_DG e ADMINISTRADOR veem; só GESTOR_DG despacha | igual | referência |
| Histórico | lista de alterações com diferenças | trilha de auditoria do banco + movimentos (quem, quando, observação) | agente (padrão do sistema) |
| Reenvio depois do envio | edição limpa a decisão e volta a aguardar | igual, mas só quando algo mudou de fato (salvar sem mudanças não reenvia) | **agente** — confirmar |
| Exportação | XLSX/CSV, 29 colunas | CSV, 28 colunas (sem "Região": não há região no cadastro de municípios) | **agente** — confirmar |
| Conflitos | unidade móvel, motorista, pedido repetido; consultam todas as solicitações | os mesmos, pelo registro comum de conflitos (aparecem também na folha do ofício); o aviso cita nº, município e período mesmo de solicitação que a pessoa não abre (o link dá 404) — paridade; esconder o nº seria endurecimento opcional | referência + **agente** — confirmar |
| Selo de tempo | "Realizado" também na cancelada e na não atendida | sem selo de tempo nessas duas (o evento não aconteceu) | **agente** — confirmar |
| Ordem da fila "Aguardando despacho" | pela data do pedido | pelo evento mais próximo, a mesma ordem do "Registrar e abrir a próxima"; com mais de um na fila, este é o botão principal | **agente** — confirmar |
| Gerar viagem | automática no deferimento, uma por "ambiente" (setor casado pelo nome da equipe), com roteiro (sede, trechos, diárias), anexos copiados e multieventos | botão "Gerar viagem" na folha deferida (DG ou quem cria viagens), uma viagem para a unidade escolhida (sugerida pela equipe com o nome da unidade); sem roteiro, anexos nem multieventos — ficam com a unidade | **agente** — confirmar |
| Viagem quando o evento não acontece | cancela a viagem sem documento; com documento avisa Viagens | igual | referência |
| Painel, lembretes | existem | E3 (sino; sem e-mail) | referência |
| Consultar protocolo | eProtocolo | segue simulado | pendente (dependência externa) |

## Coffee Break — CB1 (cadastros)

Fonte: `coffee_break/{models,forms,views,permissions}.py` da referência ([coffee-break.md](coffee-break.md)).

| Ponto | Referência | Aqui | Origem |
|---|---|---|---|
| Perfis | módulo ASCOM_COFFEE_BREAK por setor; admin = módulo + grupo ADMINISTRADOR | papel `ASCOM_COFFEE_BREAK` (vê tudo); admin = o papel + `ADMINISTRADOR` | **agente** — confirmar |
| Municípios do lote | N:N escolhido em tela + texto original da planilha | lista de nomes digitada, validada contra os municípios do Paraná; o texto fica guardado | **agente** — confirmar |
| Configuração do ofício | nasce com nomes reais de pessoas | nasce com valores neutros (vocativo, textos dos e-mails); assinante e destinatário em branco | **agente** (dados pessoais) |
| Numeração da OS e do ofício | livro único com Viagens | OS com sequência anual própria do módulo (CB2), atrás de `queries.proximo_numero`; ofício na CB3 | **pendente — decisão do usuário** |
| Pagamento conjunto sem nota em todas | "Protocolo N registrado no ofício. Ele vira o protocolo de pagamento quando… tiverem a nota fiscal." | recusa o protocolo/atesto até todas as OS terem a nota, dizendo qual falta (o PCPR do ofício pode ser digitado à parte) | **agente** — confirmar |
| Selo de tempo e abas da lista | trilha na ordem dos marcos | trilha na ordem do fluxo (aguardando nota → … → concluídas, canceladas) com rótulos curtos | agente (UX) |

## Pendências abertas

| Pendência | Tipo |
|---|---|
| Acesso autorizado à referência em execução para comparação visual/funcional | dependência externa |
| eProtocolo real (credenciamento, usuário de sistema, `consumerId`, IP fixo, escopos) | dependência externa |
| Central de Viagens (existência de API, requisitos) | dependência externa |
| Hospedagem/IA/n8n (plano, recursos, backups, custos) | dependência externa |
| Reabertura formal (emitido → rascunho com motivo, gestor) sem botão desde a saída da página de detalhe; hoje a tela oferece "Editar (retificar)" | **bloqueante** (decisão: manter só a retificação ou repor o botão de reabrir) |
| Uso real do DOCX fora do sistema (D4) | evidência do usuário |
| Confirmar os comportamentos de Cadastros adotados da referência (tabela acima) | decisão do usuário (não bloqueia) |
| Confirmar os comportamentos do Plano de trabalho adotados (tabela acima) | decisão do usuário (não bloqueia) |
| Via assinada do termo sem exigir geração prévia (tabela "Via assinada") | decisão do usuário (não bloqueia) |
| Termo de vários servidores assinado num único PDF escaneado: hoje é uma via por documento; anexo único para todos? | decisão do usuário (não bloqueia) |
| Validação jurídica de assinatura ICP-Brasil (cadeia/revogação) | decisão institucional |
| Baixar documentos de ofício em rascunho como minuta (sem emitir) | decisão do usuário (não bloqueia) |
| SMTP institucional para notificações por e-mail (servidor, remetente, credenciais) | credencial externa |
| Setor/Módulo (acesso por módulo) e vínculo Usuário↔Servidor da referência | decisão do usuário (não bloqueia) |
| Hierarquia na gestão de usuários (só superusuário mexe em superusuário) | decisão do usuário (não bloqueia) |
| Viagem: excluir solta os documentos; cancelar respeita a permissão de cada documento | decisão do usuário (não bloqueia) |
| Coffee Break: numeração da OS e do ofício conjunta com Viagens (como na referência) ou própria | decisão do usuário (bloqueia só a numeração da CB2/CB3; o resto segue) |
| Coffee Break: rota pública do fornecedor (sem login) e carga histórica (planilha × ETL) | decisão institucional / do usuário (CB8/CB9) |
| Prestação: nascer na emissão (não no rascunho); avisos só para a unidade do ofício | decisão do usuário (não bloqueia) |
| Prestação: aprovar/devolver só pela gestão (a referência não separa) | decisão do usuário (não bloqueia) |
| Prestação: o ofício assinado é a via do próprio ofício (módulo 7), não um anexo separado | decisão do usuário (não bloqueia) |
| Cadastro de feriados (estaduais/municipais/ponto facultativo) para os prazos em dias úteis | decisão do usuário (não bloqueia) |
| Imprensa: papel `ASCOM_IMPRENSA` no lugar do módulo da referência; a quem dar | decisão do usuário (não bloqueia) |
| Imprensa: "preencher com e-mail" e importador da planilha (origem dos e-mails/planilhas) | decisão do usuário (não bloqueia) |
| Publicações: papel `ASCOM_PUBLICACOES`; "preencher com e-mail" e importador | decisão do usuário (não bloqueia) |
| Palestras: papel `ASCOM_PALESTRAS` (sem setores); pedido público sem login (PL2) | decisão do usuário (não bloqueia) |
