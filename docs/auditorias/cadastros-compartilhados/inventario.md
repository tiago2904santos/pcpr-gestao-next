# Inventário dos cadastros compartilhados

Observação inicial: 17/10/2026. Fonte: código local, sem consulta ou alteração de produção. Git estava limpo ao iniciar. Este arquivo é o denominador da missão; descoberta não equivale a validação visual. Os documentos `entities.md`, `modules.md` e `product-map.md` ainda chamam vários módulos implementados de planejados; para este levantamento prevalecem rotas, modelos, formulários, serviços e policies efetivos.

## Critérios de contagem

- **35 entidades cadastrais**, relacionadas abaixo por identidade de modelo, incluindo os cadastros sem tela própria e os vínculos embutidos.
- **32 superfícies principais de manutenção**: 14 Cadastros/Identidade, 6 Eventos, 5 Coffee Break, 3 Palestras, 2 Imprensa e 2 Publicações. A mesma tela serve criação e edição quando o cadastro usa modal ou formulário incorporado. Os 35 modelos não se confundem com 35 páginas: Município tem carga/API, Lotação está em Usuários e Substituição está em Dados da unidade.
- **2 catálogos fixos adicionais**, ModeloOS e FuncaoOS, mantidos pelo código/migração, sem cadastro administrativo.
- **13 famílias de fluxos consumidores** com formulários próprios, discriminadas ao final. Incluem documentos/processos; não são novas cópias dos cadastros.
- Os atalhos, seletores e endpoints são listados separadamente. A contagem de telas principais não comprova cobertura de todos esses pontos. O fechamento exige evidência de cada família e de cada variação relevante de formulário, permissão e tamanho.

Situação inicial comum: todos os itens foram **inventariados por leitura de código**. A implementação e validação final devem ser registradas nos arquivos dos lotes; não considerar um item concluído apenas porque um componente global mudou.

## Fontes e regras transversais

`config/urls.py` reúne sete contextos de negócio mais Identidade e Painel. Persistência local Django/PostgreSQL; não existe fonte dedicada integrada. `cadastros/services.py`, `textos.py`, `eventos/catalogos.py` e serviços dos respectivos módulos concentram escritas; os formulários ainda consultam ORM diretamente.

Escopo vigente documentado em `docs/product/permissions.md`: Servidor, Viatura, Unidade, Cargo e Combustível são catálogos institucionais globais; documentos de Viagens são limitados pela lotação, salvo `ver_todas_unidades`. Centralizar o cadastro não altera essa política. A configuração institucional e substituições são por unidade. Coffee e ASCOM são centralizados em seus módulos. Eventos restringe solicitações por autor/DG/admin; seus catálogos são de apoio global ao domínio. Usuário, pessoa/servidor, lotação e assinante continuam identidades e responsabilidades distintas.

Histórico: `viagens.Documento.dados`, versões documentais e arquivos assinados preservam instantâneos; PlanoTrabalho/EventoPlano guardam estruturas de atividades com conteúdo próprio. Uma FK protegida mantém o vínculo, mas sozinha não congela o rótulo mostrado em telas antigas. Onde o código consulta diretamente o nome atual, a imutabilidade do PDF não prova imutabilidade de todo o histórico visual. Validar renomeação e inativação em cada consumidor.

## Cadastros e Identidade — 17 entidades / 14 superfícies

<a id="c01"></a>

### C01 — Unidades (`cadastros.Unidade`)

- Fonte/campos: `cadastros/models.py`; sigla, nome e ativo; nome sem caixa único. Escopo institucional global.
- Uso: lotação de contas e servidores, viaturas, emissora dos documentos/roteiros/viagens, efetivo dos planos; contexto da configuração institucional. Consulta/manutenção pelas permissões `cadastros.*_unidade` (operador/gestor; consulta somente leitura).
- Superfície: `/cadastros/unidades/`, lista + modal `catalogo.html`; rápidos nos formulários de servidor, viatura e usuário e diálogos reutilizados em Viagens. Unidade selecionada pode permanecer inativa na edição.
- Duplicações: `publicacoes.UnidadeResponsavel` é rótulo editorial, não lotação institucional; órgão de Eventos também não é unidade. Não unir por nome. Nome do cabeçalho é complemento documental, não duplicata descartável.
- Histórico/ação: relações PROTECT nos objetos relevantes; manter ID e inativar quando em uso. Preparar origem externa e complemento local; rever largura de nomes/siglas e legibilidade dos seletores.

<a id="c02"></a>

### C02 — Cargos (`cadastros.Cargo`)

- Fonte: modelo local com nome, ativo, padrão. Global; `cadastros.*_cargo`.
- Uso: Servidor; efetivo e coordenadores do Plano; nomes/cargos históricos em documentos e configurações.
- Superfícies: `/cadastros/cargos/`, lista/modal; rápido no Servidor; rápidos de cargo dos coordenadores administrativo/operacional do Plano. Coordenadores guardam texto contextual (`data-valor="nome"`), não FK.
- Duplicações/histórico: cargo da pessoa difere de função na assinatura/fiscal e cargo textual consolidado. Manter esses complementos. Padrão afeta novos servidores, sem reescrever documentos.
- Ação: conservar identidade, preparar vínculo externo; revisar alinhamento, nomes longos e seleção/retorno de foco.

<a id="c03"></a>

### C03 — Combustíveis (`cadastros.Combustivel`)

- Fonte: nome, ativo, padrão local; global; `cadastros.*_combustivel`.
- Uso: Viatura e transporte informado manualmente no Ofício. `/cadastros/combustiveis/`, lista/modal, rápido no diálogo Viatura.
- Histórico: FK/documentos e uso atual são distintos; exclusão protegida em uso, inativação para próximos usos.
- Ação: manter catálogo único, opções atuais na edição e padrão; revisar modal/rápido.

<a id="c04"></a>

### C04 — Servidores (`cadastros.Servidor`)

- Fonte: nome, CPF, RG, cargo, unidade, telefone, ativo; CPF normalizado e único quando informado. Escopo global vigente. Conta `Usuario` não é este cadastro.
- Acesso: `cadastros.*_servidor`; leitura em buscas de Viagens também depende de policies de Viagens; Eventos consome nomes de motoristas em solicitações próprias sem abrir manutenção administrativa.
- Superfícies: `/cadastros/servidores/`, lista paginada 25, abas/filtros e diálogo; `/cadastros/servidores/<pk>/dialogo/`; `/cadastros/api/servidores/` (15 resultados); `/viagens/api/servidores/`; rápido no Ofício/equipe, Termo, OS e lote da Viagem. Seletores em assinatura/substituição, planos/coordenadores, motoristas de Eventos, Palestrante e motoristas habituais da Viatura.
- Duplicações: Palestrante já tem FK opcional ao servidor, além de contato/lotação contextual; integrantes ASCOM podem ser parceiros externos. Não fundir automaticamente por nome.
- Histórico/ação: preservar PROTECT em documentos e instantâneos; manter ativo selecionado fora da página e inativo já vinculado. Custo concreto: selects inteiros em assinatura, Eventos/Palestrante; paginação da lista já existe. Preparar acesso canônico reutilizável e origem externa.

<a id="c05"></a>

### C05 — Viaturas (`cadastros.Viatura`)

- Fonte: placa normalizada única, modelo, combustível, tipo, porte, unidade, motoristas M2M, ativo; global; `cadastros.*_viatura`.
- Superfícies: `/cadastros/viaturas/`, lista 25 + modal; `/cadastros/viaturas/<pk>/dialogo/`; rápidos em Ofício, Termo, OS e lote; seleção de transporte nos fluxos de Viagens, diário de bordo/prestação.
- Duplicações: `eventos.UnidadeMovel` é denominação de equipe/recurso designado, não necessariamente veículo com placa; `imprensa.Veiculo` é empresa jornalística. Não fundir.
- Histórico/ação: manter IDs, motoristas e dados consolidados do documento; preparar vínculo externo. Lista já faz `select_related` e `prefetch_related`, seletores de todos os ativos ainda crescem com a frota.

<a id="c06"></a>

### C06 — Municípios (`cadastros.Municipio`)

- Fonte oficial local CSV/IBGE e coordenadas; código IBGE único, nome/UF/latitude/longitude. Sem CRUD na UI.
- Acesso/uso: `/cadastros/api/municipios/` (12 resultados, prefixo sem acentos, Paraná primeiro, filtro UF), `CampoMunicipio` reutilizado por sede, roteiros, documentos, Eventos, Coffee, Palestras e endereços.
- Histórico: FKs PROTECT e textos de localidades nos instantâneos. Não recriar a cidade por variação de acento; identidade é IBGE.
- Ação: preservar fonte oficial e contratos dos autocompletes; validar selecionado fora dos resultados. Tratar UF/região como atributos/filtros, não inventar modelos de região/estado ausentes.

<a id="c07"></a>

### C07 — Tabela de diárias (`cadastros.TabelaDiaria`)

- Fonte: faixa, vigência, valor 24h e norma; 15%/30% derivados; único faixa/vigência; global. Consulta operador/gestor, manutenção gestor.
- Superfícies: `/cadastros/diarias/`, lista de vigências + modal; cálculo do Ofício/Roteiro/Prestação.
- Histórico/ação: instantâneo do cálculo preserva valores passados. Lista inteira é proporcional ao pequeno catálogo de vigências; não alegar gargalo sem medida. Revisar modal, valores/percentuais e erro; impedir alteração dos cálculos consolidados.

<a id="c08"></a>

### C08 — Lotação (`cadastros.Lotacao`)

- Fonte: relação 1:1 Usuario → Unidade; não é lotação da pessoa Servidor. Escopo por vínculo.
- Superfície/manutenção: embutida em `/cadastros/usuarios/`; `views_usuarios.salvar_usuario` altera conta e lotação em transação. Policies de Identidade administram a conta; usa unidade ativa ou atual.
- Uso/histórico: define visibilidade/criação dos documentos; alterações não devem mover documentos antigos de unidade. Sem página própria.
- Ação: preservar distinção conta/pessoa/vínculo e autorização; validar usuário sem lotação, unidade inativa e troca de unidade.

<a id="c09"></a>

### C09 — Textos prontos (`cadastros.ModeloTexto`)

- Fonte: tipo, nome, texto, ordem, ativo, padrão/sistema; catálogo global. Tipos: motivo, justificativa, trecho do ofício e cinco campos RT.
- Superfícies: `/cadastros/textos-prontos/` (três abas visíveis de Ofício); modal novo/editar; `dialogo_guardar_texto.html`; seletores no Ofício/Justificativa e relatórios técnicos da Prestação. RT tem pontos próprios de consumo que não aparecem nas três abas da tela central.
- Acesso: `pode_gerir_textos`; padrão/sistema só gestor; sistema nunca excluído; padrão único/ativo por tipo.
- Histórico/ação: inserir copia texto no documento; editar modelo não deve reescrever texto consolidado. Revisar texto longo/modal e cobertura dos tipos RT; lista atual sem paginação, medir proporcionalmente.

<a id="c10"></a>

### C10 — Dados da unidade (`cadastros.ConfiguracaoInstitucional`)

- Fonte: 1:1 Unidade; cabeçalho, sede, endereço/contatos, rodapé substitutivo, chefia, destinatário, prazo, Delegado-Geral, assinantes de Ofício/Justificativa/PT, coordenador e sufixo do Plano.
- Escopo/acesso: por unidade; `pode_ver_configuracao`, `pode_alterar_configuracao`; própria lotação ou `ver_todas_unidades`. `unidades_configuraveis` restringe seletor e `_configuracao_pedida` rejeita ID fora do conjunto.
- Superfície inicial `/cadastros/configuracao/`; página + seletor de unidade + assinantes + substituições. Menu inicial em Viagens/Cadastros; solicitação do usuário determina nova entrada imediatamente abaixo de Alterar senha, com compatibilidade da rota antiga.
- Duplicações/histórico: mestre Unidade continua separado dos complementos; rodapé textual tem precedência explícita ao endereço montado. Coffee tem configuração de natureza contratual/GAF própria, não configurável por unidade hoje.
- Ação: reorganizar navegação, título, grupos e contexto; buscar servidores remotamente, preservar inativos atuais e snapshots. Seleção de assinante não concede conta/permissão/assinatura digital.

<a id="c11"></a>

### C11 — Substituições de assinantes (`cadastros.SubstituicaoAssinante`)

- Fonte: Configuração, Servidor, tipo documental (todos/ofício/justificativa/PT), início/fim, motivo e ativo. Por vínculo da unidade, sem login novo.
- Superfície: lista e modal em C10; salvar e encerrar/reativar por endpoints sob `/cadastros/configuracao/substituicoes/`; seleção de servidor completa atualmente.
- Acesso: serviço valida configuração da unidade e o ID da substituição; não basta esconder botão. Datas devem ser ordenadas; conflitos são regra do serviço.
- Histórico/ação: `quem_assina` resolve pela data do documento; emissão guarda dados. Validar IDs de outra unidade, períodos sobrepostos e encerramento sem alterar PDFs antigos; ampliar conforto do modal.

<a id="c12"></a>

### C12 — Tipos de viagem (`cadastros.TipoViagem`)

- Fonte: nome, motivo, tipo OS, ativo; global; `cadastros.*_tipoviagem`.
- Superfícies: `/cadastros/tipos-de-viagem/`, lista/modal; Viagem com múltiplos tipos; criação contextual de OS usa código tipo OS fixo.
- Histórico/ação: preservar códigos e textos copiados; tipo não se confunde com TipoEvento. Refinar motivo longo e seleção múltipla.

<a id="c13"></a>

### C13 — Programas solicitantes (`cadastros.ProgramaSolicitante`)

- Fonte: nome/ativo; global; `cadastros.*_programasolicitante`.
- Superfícies: `/cadastros/programas/`, lista/modal; Plano e eventos de plano (seletor de programas).
- Histórico/ação: contexto de quem pede a ação não equivale automaticamente a OrgaoResponsavel. Preservar IDs, nomes/textos consolidados, registros inativos selecionados e largura de nome longo.

<a id="c14"></a>

### C14 — Horários de atendimento (`cadastros.HorarioAtendimento`)

- Fonte: nome textual da faixa e ativo; global; `cadastros.*_horarioatendimento`.
- Superfícies: `/cadastros/horarios/`, lista/modal; rápido `dialogo_horario.html` no modal do evento do Plano.
- Histórico: Plano guarda texto da faixa, não ID; rápido retorna `nome`, não PK. Ação: preservar esta semântica, dados do formulário de origem e foco; revisar campos/validação do período.

<a id="c15"></a>

### C15 — Atividades do plano (`cadastros.AtividadePlano`)

- Fonte: código único, nome, meta, recurso, ativo; global; `cadastros.*_atividadeplano`.
- Superfícies: `/cadastros/atividades/`, lista/modal; seleção Plano/EventoPlano; Conjuntos de atividades; resultados por atividade.
- Duplicação **confirmada por decisão de produto**: `eventos.Servico`. Igualdade de nome isolada não autoriza fusão de registros individuais. Código UNIDADE_MOVEL possui comportamento documental.
- Histórico/ação: manter código, meta e recurso nos instantâneos; identidade canônica compartilhada com mapeamento legado e preservação dos casos ambíguos. Quantidade/observação/resultado são do uso no processo.

<a id="c16"></a>

### C16 — Conjuntos de atividades (`cadastros.PresetAtividades`)

- Fonte: nome, descrição, ativo, padrão e atividades M2M; global; `cadastros.*_presetatividades`.
- Superfícies: `/cadastros/conjuntos/`, lista/modal; aplicado no Plano novo; único padrão ativo.
- Histórico/ação: conjunto é atalho, não nova identidade das atividades. Preservar M2M na unificação, padrão e instantâneos; revisar seleção com muitas atividades e textos longos.

<a id="c17"></a>

### C17 — Usuários (`identidade.Usuario`)

- Fonte: nome, login/e-mail únicos, senha, is_active/deve_trocar_senha; papéis Django Group sincronizados do código.
- Superfícies: `/cadastros/usuarios/`, lista paginada 25 + modal; unidade via C08; rápido Unidade. Permissões `identidade/policies.py`, incluindo proteção da própria conta e privilégios.
- Duplicação/histórico: conta não deve fundir com servidor/assinante. Auditoria preserva responsável pelas operações.
- Ação: refinar modal amplo, instruções de papéis/senha, erro com valores preservados, sem alterar a cadeia de privilégios.

## Eventos Sociais — 6 entidades / 6 superfícies

Todas em `eventos/models.py` e escritas em `eventos/catalogos.py`; nome único sem caixa, ativo. Listas `/eventos/cadastros/<slug>/` paginadas 25, criação incorporada e edição por registro, exclusão protegida e inativação. Manutenção pelo ADMINISTRADOR nas cinco primeiras; textos também pela DG. Solicitantes consomem opções dos formulários sem ganhar permissão administrativa.

<a id="c18"></a>

### C18 — Tipos de evento (`eventos.TipoEvento`, `tipos-evento`)

- Uso: Solicitação; página adicional `/eventos/cadastros/tipos-evento/<pk>/modelo/` mantém solicitante/cargo/órgão padrão, serviços sugeridos M2M e equipes com quantidade (`TipoEventoEquipe`).
- Duplicações: não é TipoViagem. Nome do solicitante/cargo padrão é preenchimento contextual, não pessoa/usuário.
- Histórico/ação: preservar modelo e serviços canônicos; ampliar conforto da edição/modelo; filtros e valores digitados com erro precisam continuar consistentes.

<a id="c19"></a>

### C19 — Serviços (`eventos.Servico`, `servicos`)

- Uso: `SolicitacaoServico` (serviço + observação por solicitação), modelo do TipoEvento e geração de viagem a partir do evento.
- Duplicação: C15 obrigatoriamente. `SolicitacaoServico` PROTECT mantém vínculo, mas nome consultado em tela vem do cadastro atual.
- Ação: migrar FKs/M2M ao catálogo comum, preservar identidade/observação, manutenção compatível de permissões Eventos; congelar rótulo no uso consolidado onde necessário e validar edição/inativação.

<a id="c20"></a>

### C20 — Equipes (`eventos.Equipe`, `equipes`)

- Uso: modelo TipoEventoEquipe e SolicitacaoEquipe; quantidade solicitada/ajustada é do uso e não do catálogo.
- Duplicação: equipe é grupo/recurso coletivo, não Servidor ou integrante ASCOM.
- Ação: manter identidade e particularidades, revisar nome longo e quantidades/erros sem invalidar histórico.

<a id="c21"></a>

### C21 — Órgãos responsáveis (`eventos.OrgaoResponsavel`, `orgaos`)

- Uso: modelo TipoEvento e Solicitação. Escopo domínio, global dentro dele.
- Duplicação: possível interseção textual com Unidade/Programa, sem equivalência comprovada. Não fundir.
- Ação: manter fonte, PROTECT quando aplicável, revisar nomes longos, inativos atuais e filtros.

<a id="c22"></a>

### C22 — Unidades móveis (`eventos.UnidadeMovel`, `unidades-moveis`)

- Uso: recurso designado na Solicitação (`unidade_movel_designada`), separado do booleano de atendimento por unidade móvel.
- Duplicação: possível associação futura com Viatura exige placa/identificador e regras; nome sozinho insuficiente.
- Ação: manter entidade de domínio, preservar vínculo/ativo e revisar seletor longo.

<a id="c23"></a>

### C23 — Textos prontos do despacho (`eventos.TextoDespacho`, `textos-despacho`)

- Uso: modal/ação Despachar da Solicitação. Fonte nome/texto/ativo; DG e ADMIN mantêm.
- Duplicação: finalidade e permissão diferentes de ModeloTexto/RespostaPadrao. Compartilhar componente, não unir dados indiscriminadamente.
- Histórico/ação: despacho registrado como movimento/texto próprio; modelo editado não deve reescrever despacho anterior. Refinar área de texto e validação.

## Coffee Break — 5 entidades / 5 superfícies

Fonte `coffee/models.py`, formulários `coffee/forms.py`, serviços `coffee/services.py`, telas `coffee/views.py`. Acesso requer `coffee.acessar_coffee`; manter cada tabela requer `coffee.change_<modelo>` (administrador do módulo). Global dentro de Coffee. Listas de contratos e afins paginam 25 e já usam joins/prefetch pertinentes.

<a id="c24"></a>

### C24 — Fornecedores (`coffee.Fornecedor`)

- `/coffee/cadastros/fornecedores/`: lista/modal; razão social, nome curto, CNPJ, contato/telefone/e-mail/portal certidão; CNPJ normalizado único quando informado.
- Uso: contratos, pedidos/documentos, certidões e entregas; não equivale a órgão/unidade.
- Histórico/ação: contrato protege fornecedor e PDFs/vias preservam emissão. Manter complementos locais; revisar formulário longo de contato e CNPJ.

<a id="c25"></a>

### C25 — Contratos (`coffee.Contrato`)

- `/coffee/cadastros/contratos/`: lista/modal, anexo PDF; fornecedor, número/GMS, objeto, vigência, valor/quantidades, antecedência, fiscal/cargo e observações.
- Uso: aditivos, lotes, financeiro/documentos; fiscal é texto contratual, não substituir automaticamente pelo cargo atual de um servidor.
- Histórico/ação: vigência efetiva considera aditivos, PROTECT em lotes; documentos arquivados não mudam. Modal extenso precisa largura/seções e actions acessíveis.

<a id="c26"></a>

### C26 — Termos aditivos (`coffee.TermoAditivo`)

- `/coffee/cadastros/aditivos/`: lista/modal + PDF; contrato, número, datas, arquivo.
- Uso: vigência de contrato e verificação do pedido. Preservar todos os aditivos; não sobrescrever o contrato como se fosse novo.
- Ação: revisar seleção de contrato/fornecedor, calendário, arquivo, conflito de versão e validação.

<a id="c27"></a>

### C27 — Lotes (`coffee.Lote`)

- `/coffee/cadastros/lotes/`: lista/modal; contrato, número/exercício, quantidade, ativo, empenho, municípios M2M, orientações/especificações/observações.
- `/coffee/lotes/`, virada de exercício, lote do município e pedidos consomem o mesmo registro; saldo é derivado do consumo.
- Histórico/ação: lote não é cópia do fornecedor; preservar municípios/saldo/exercício e não órfãos; revisar seleção de municípios e modal extenso.

<a id="c28"></a>

### C28 — Ofício e protocolo (`coffee.ConfiguracaoOficio`)

- `/coffee/cadastros/oficio/`: formulário próprio, registro singleton; vocativo/assinante/cargo, protocolo, destinatário, e-mails e modelos de assunto/mensagem.
- Escopo domínio global, não por unidade; não existe FK unidade. Não vincular silenciosamente à unidade corrente de Viagens.
- Duplicação: assinante textual tem interseção conceitual, mas autoria/finalidade GAF e contrato não comprovam equivalência com chefia da unidade. Manter e documentar limites.
- Histórico/ação: novas vias usam configuração atual, antigas ficam arquivadas; revisar grupos e texto longo; preparação externa deve tratar estes dados como complemento local.

## Palestras — 3 entidades / 3 superfícies

Fonte `palestras/models.py`, formulários `palestras/forms.py`, serviços/views próprios; permissão `pode_gerir_cadastros` exige acesso ao módulo e change dos três modelos. Escopo ASCOM centralizado. Criação/edição incorporadas em `palestras/cadastro.html`.

<a id="c29"></a>

### C29 — Palestrantes (`palestras.Palestrante`)

- `/palestras/cadastros/palestrantes/`; nome, servidor opcional, município, divisão, lotação textual, contato/e-mail, tema de abordagem. Único nome+lotação, não apenas nome.
- Uso: Palestra M2M, andamento, autocomplete `/palestras/api/palestrantes/` e conflito de agenda via servidor vinculado.
- Histórico: exclusão recusada em uso; FK servidor SET_NULL não deve apagar identidade contextual. Inativo servidor já vinculado atualmente fica fora do queryset do formulário: **risco concreto de edição recusada/perda de vínculo**, corrigir.
- Desempenho: lista inteira e formulário completo de edição por registro, cada um com select de todos os servidores. Ação: busca/paginação, apenas formulário solicitado, join município/servidor; preservar progressive enhancement, erros e identificação do atual.

<a id="c30"></a>

### C30 — Temas (`palestras.Tema`)

- `/palestras/cadastros/temas/`; nome único sem caixa; seleção nas Palestras. Sem campo ativo no modelo atual.
- Histórico/ação: PROTECT do tema utilizado, não inventar inativação sem regra; adicionar busca/paginação e mensagens acessíveis, validar edição/exclusão.

<a id="c31"></a>

### C31 — Respostas padrão (`palestras.RespostaPadrao`)

- `/palestras/cadastros/respostas/`; tipo/mensagem, marcadores; seletor no responder da Palestra.
- Histórico: `RespostaEnviada` guarda texto enviado; editar modelo afeta usos futuros. Não fundir com textos de despacho/viagem.
- Ação: busca/paginação e formulário confortável de mensagem/erros; validar marcadores e preservação de valores.

## Imprensa — 2 entidades / 2 superfícies

Fonte `imprensa/models.py`, serviços e forms do módulo. Manutenção exige `change_veiculo` e `change_integrante`; consulta/uso no Atendimento exige acesso ao módulo. Escopo ASCOM, sem unidade. Arquétipo `templates/arquetipos/cadastro_nomes.html`; criação e edição incorporadas.

<a id="c32"></a>

### C32 — Equipe de atendimento (`imprensa.Integrante`)

- `/imprensa/cadastros/equipe/`; nome curto único sem caixa, sem ativo; responsável dos atendimentos.
- Duplicação: integrante pode ser parceiro; nome não prova correspondência a Usuario/Servidor ou integrante de Publicações.
- Histórico/ação: FK PROTECT em uso; renomeação muda rótulo atual, sem recriar histórico; busca/paginação e cancelamento/erro claros.

<a id="c33"></a>

### C33 — Veículos de imprensa (`imprensa.Veiculo`)

- `/imprensa/cadastros/veiculos/`; nome único sem caixa; Atendimento seleciona ou cria pelo campo **Outro veículo**, em serviço autorizado por `add_veiculo`.
- Duplicação: veículo jornalístico não é Viatura. O rápido textual deve manter dados da folha e reutilizar único nome normalizado.
- Histórico/ação: PROTECT em uso; buscar/paginar lista, validar cadastro rápido, edição e erro.

## Publicações — 2 entidades / 2 superfícies

Fonte `publicacoes/models.py`, services/forms próprios; manutenção exige change_integrante + change_unidaderesponsavel; consulta/uso requer view_publicacao. Escopo ASCOM. Mesmo arquétipo incorporado de Imprensa.

<a id="c34"></a>

### C34 — Equipe de comunicação (`publicacoes.Integrante`)

- `/publicacoes/cadastros/equipe/`; nome curto único sem caixa, sem ativo; jornalista/redação/edição/revisão nas pautas.
- Duplicação: equipe inclui parceiros SESP/AEN; não fundir automaticamente com pessoa/conta/equipe Imprensa.
- Histórico/ação: PROTECT por pauta; implementar busca/paginação e layout/erro no arquétipo.

<a id="c35"></a>

### C35 — Unidades responsáveis (`publicacoes.UnidadeResponsavel`)

- `/publicacoes/cadastros/unidades/`; nome editorial único; pauta permite **Outra unidade** com permissão `add_unidaderesponsavel`.
- Duplicação potencial com C01, mas o próprio modelo documenta vocabulário da ASCOM independente da lotação. Exige mapeamento comprovado/identificador antes de unificar; manter separados nesta missão.
- Histórico/ação: PROTECT em pauta, preservar rótulo de domínio; busca/paginação, validar rápido textual sem perder origem.

## Catálogos fixos adicionais

- **S01 — ModeloOS** e **S02 — FuncaoOS**: `viagens/modelos_do_sistema.py`, `viagens/models.py` e migrações; tipos e funções fixos sincronizados do código. Seletores na Ordem de Serviço e TipoViagem; não há nova tela CRUD a implementar. Preservar códigos e funções da OS emitida. Não confundir com Cargo nem Atividade/Serviço.
- UF, tipo de transporte, tipo de viatura, faixa de diária, situações, canais, tipos documentais e papéis são enumerações/constantes, não tabelas de cadastro descobertas. Papéis vêm de `identidade/papeis.py`, sem CRUD de grupo na UI. DistanciaMunicipios é cache de rota, não catálogo de localidades independente. Numeracao/Lacuna são controle transacional, sem cadastro de entidade duplicada.
- **AUX01 — AssinaturaAgenda**, em `plataforma/models.py`: credencial pessoal do feed ICS, não assinante documental nem cadastro institucional. `/agenda/#assinar` oferece gerar/trocar/revogar link por POST `/agenda/assinatura/`, sem campos cadastrais de entidade; `painel/views_agenda.py` e `plataforma/assinatura.py` validam autorização. Guarda hash do token e selo de senha; não unificar com SubstituicaoAssinante. A Agenda consome os registros e permissões de cada domínio. Conta explicitamente como configuração técnica auxiliar, fora das 35 entidades institucionais e das 32 telas de manutenção. RotinaDoDia é marca técnica de execução diária, sem CRUD na interface.

## Treze famílias de formulários consumidores obrigatórias

Cada família exige validação das telas de criação, edição/detalhe e ações incorporadas pertinentes; os arquivos de teste/evidência devem declarar as variações executadas.

1. **F01 — Viagem**, `views_viagem.py`, `viagem/editar.html` e `viagem/lote.html`: tipos, unidade, municípios, servidores, viaturas, geração/repetição/lote e cadastro rápido compartilhado.
2. **F02 — Ofício/Justificativa**, `views.py`, `oficios/editar.html`: equipe e motorista interno/externo, viatura/combustível, sede/rota, motivo/modelo, editor e textos guardados; lazy dialogs reutilizados, edição do cadastro dentro da folha.
3. **F03 — Roteiro**, `views_roteiros.py`, `roteiros/editar.html`: municípios/UF, sede e cálculo; seleção de roteiro pelo Ofício.
4. **F04 — Termo**, `views_termos.py`, `termos/editar.html`: servidores, viaturas, ofícios remotos, destinos; rápido com atualização da origem; versões/assinados.
5. **F05 — Ordem de serviço**, `views_ordens.py`, `ordens/editar.html`: servidores, modelos/funções fixos, viaturas, ofícios, municípios; cadastro rápido e versões.
6. **F06 — Plano e EventoPlano**, `views_planos.py`, `planos/editar.html` e `_dialogo_evento.html`: atividades, conjuntos, programa, horários, efetivo por unidade/cargo, coordenadores/assinante, resultados. Modal EventoPlano e rápidos Horário/Cargo são superfícies próprias.
7. **F07 — Prestação/diário/RT**, `views_prestacao.py`, `views_diario.py`, templates de prestação: equipe/servidor e transporte/rota herdados, textos prontos RT, anexos, importação e documentos; não criar cópia de cadastro ao importar.
8. **F08 — Solicitação de Evento Social**, `views_solicitacoes.py`, `eventos/forms.py`: município/tipo/órgão/serviços/equipes/unidade móvel/motorista, modelo inicial, despacho com texto pronto, geração de viagem. Quantidade/observação pertencem a relações de uso.
9. **F09 — Solicitação/financeiro Coffee**, `views_pedidos.py`, `forms_pedido.py`: município/lote/contrato/fornecedor, etapas financeiras, pagamento conjunto, configuração documental atual e vias anteriores.
10. **F10 — Palestra**, `palestras/views.py`, `forms.py`: tema/município/palestrantes remotos; modal andamento com palestrante e resposta com modelo/marcadores; encaminhar DG.
11. **F11 — Atendimento à imprensa**, `imprensa/views.py`, `forms.py`: responsável/veículo e Outro veículo; andamento, e-mail inicial, autosave e CSV.
12. **F12 — Pauta/Publicação**, `publicacoes/views.py`, `forms.py`: integrantes por função, unidade e Outra unidade; andamento, e-mail inicial, autosave e CSV.
13. **F13 — Certidões/entregas Coffee**, `coffee/views_painel.py`, `views_pedidos.py`: fornecedor, contrato/lote/pedido, arquivos e modal de entrega/ocorrência. São registros de domínio, não nova identidade de fornecedor.

Agenda, painel, notificações, relatórios/CSV e pacotes/documentos são consumidores somente leitura dos registros anteriores; políticas de cada origem continuam válidas. Uploads/editor documental são ações do processo correspondente, não catálogos canônicos adicionais.

## Atalhos escondidos e endpoints a exercitar

- Servidor: cargo/unidade por +; viatura: combustível/unidade por +; usuário: unidade por +.
- Ofício: adicionar servidor, editar cadastro de servidor/viatura, adicionar viatura; carregamento de formulários adiado em `dialogos_cadastro_adiados.html` deve preservar o diálogo e a folha.
- Termo/OS/lote da Viagem: `dialogos_cadastro.html` reutiliza Servidor/Viatura/Cargo/Combustível/Unidade; o alvo pode ser seleção múltipla ou `destino` de nova viatura. Não supor que testar o Ofício comprova todos os alvos.
- Plano: + Cargo de cada coordenador e + Horário dentro do modal EventoPlano; são valores textuais, não IDs.
- Textos: Guardar como texto pronto em editor; seleção e padrões nos diferentes tipos de documento/RT.
- Imprensa: Outro veículo; Publicações: Outra unidade; são inclusões na gravação do próprio formulário, sem segundo diálogo.
- Unidade: assinante por finalidade, coordenador padrão, substituição por data, seleção explícita da unidade autorizada e POST adulterado.
- Eventos: modelo do TipoEvento mantém três catálogos, e Despacho usa textos restritos à DG; solicitação preserva inativos já usados.
- Coffee: PDF contrato/aditivo, municípios do lote, abrir exercício e certidões/entregas usam os mesmos contratos/fornecedores.

## Problemas confirmados e ações proporcionais

- **P01 — Sem busca/paginação em sete cadastros ASCOM.** `_cadastro` de Imprensa/Publicações/Palestras materializa todos os registros; Palestrante cria formulário de edição por registro e cada formulário carrega servidores. Implementar busca e 25 registros/página, edição apenas mediante solicitação e `select_related` de município/servidor. Medir volume, consultas e HTML antes/depois no LAB.
- **P02 — Servidor inativo ligado ao Palestrante não aparece no queryset da edição.** Incluir o atual explicitamente; validação deve permitir manter vínculo e impedir selecionar novo inativo arbitrário.
- **P03 — Seletores completos de pessoas/frota.** Configuração/Evento/Palestrante e outros forms ainda carregam coleções inteiras. Reutilizar busca limitada/registro atual em pontos centrais; qualquer otimização deve preservar autorização do módulo consumidor, nome desambiguado e valores atuais fora da primeira página.
- **P04 — Atividade/Serviço duplicados.** Dois modelos e consumidores diferentes; executar lote de unificação com mapeamento explícito e testes de idempotência, ambiguidades, quantidades, inativos, FKs/M2M e conteúdo histórico.
- **P05 — Sem contrato de origem dedicada.** ORM espalhado por forms; preparar pontos de leitura/escrita e associação externa sem trocar PK nem sobrescrever complemento local.
- **P06 — Contexto/navegação da unidade.** Link precisa nome/posição solicitados, unidade em evidência e mesmas proteções no GET/POST/substituição. Teste de acesso direto imprescindível.
- **P07 — Superfícies visuais diversas.** Catálogos Viagens usam coleção/modal, Eventos e ASCOM formulários incorporados, Coffee modal extenso. Padronizar tokens/hierarquia/espaçamento sem forçar todo cadastro simples a modal. Capturas 360/1440, foco/teclado, erro e nome longo são evidência pendente até execução.
- **P08 — Parsing de PK em catálogos antigos.** Alguns views ASCOM/Eventos usam `isdigit()` antes de `int()`; dígitos Unicode como ² passam pelo primeiro e causam ValueError. Normalizar parsing ASCII limitado e testar requisição malformada ao alterar esses pontos.

## Registro de execução

Este inventário registra a situação **inicial** e as ações propostas. Cada lote deve acrescentar abaixo IDs alterados, regras documentadas, testes/capturas e pendências. Não marcar o inventário inteiro como validado com uma captura genérica.

- **C29–C35 / P01–P02–P03 (Palestrante)–P08: concluídos no lote ASCOM.** Os sete cadastros receberam busca/paginação, contagens no banco, edição confortável e cancelamento; Palestrante passou a usar fonte canônica/seleção remota autorizada pelo módulo, com vínculo atual preservado. 43 testes dirigidos verdes, sete fluxos móveis completos e cobertura desktop dos sete, com revalidação de Palestrante após a seleção remota. Há 42 capturas, axe zero e logs JS finais vazios. Detalhamento e resultados em [ascom-validacao.md](ascom-validacao.md), [ascom-unitarios.xml](ascom-unitarios.xml), [ascom-mobile.xml](ascom-mobile.xml) e [ascom-palestrante-desktop.xml](ascom-palestrante-desktop.xml). A leitura inicial de C29 descreve o problema antes da correção; esta entrada registra a situação final.
- **C10–C11 / P06:** Dados da unidade implementado e validado no lote específico: posição do menu, contexto, persistência, assinantes, substituições, consulta, acessos diretos e IDs adulterados. [Relatório e evidências](unidade.md).
- **C15/C19 / P04–P05:** catálogo canônico e fonte local implementados; teste de migração real, permissões e contratos aprovados no lote. A rodada de navegador integrada verifica criação/uso da mesma identidade nos dois módulos, edição e inativação. [Mapa e contratos](catalogo.md).
- **C01–C09/C12–C18/C20–C28 / P03–P07–P08:** componentes comuns e superfícies específicas refinados, com [índice de 32 listas e 18 modais em duas larguras](evidencias.md). Municípios (C06) conserva a carga oficial/IBGE e é verificado pelos consumidores; Lotação (C08) e Substituição (C11) têm manutenção incorporada, por isso não acrescentam páginas ao denominador de 32.
- **Fechamento integrado:** resultados finais e pendências de cada rodada estão no [relatório](relatorio.md). O JSON vincula ações e evidências para cada uma das 35 entidades; o encerramento geral só ocorre com o verificador e os fluxos finais aprovados.

**Encerramento em 17/10/2026:** 35 entidades revisadas e validadas; 34 receberam
alterações e C06 conservou a fonte oficial. As 32 superfícies principais e os 18
modais comparados têm capturas 360/1440 e revisão visual. As 13 famílias consumidoras
têm cenários de backend/navegador vinculados nos relatórios. O
[verificador integral](verificar.log) terminou verde: 2.816 aprovados, cinco avisos,
saída zero, sem filtro adicional ou skip. A cópia isolada preservou os arquivos de
outras tarefas e manteve todo o código da missão, conforme manifesto e hashes.
Os estados finais por entidade estão em [inventario.json](inventario.json).
