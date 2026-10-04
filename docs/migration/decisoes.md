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
