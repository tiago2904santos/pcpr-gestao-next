# Catálogo e fonte dedicada — inventário e evidências

Data: 17/10/2026. Ambiente: PostgreSQL LAB isolado em 127.0.0.1:55432,
banco de testes `test_pcpr_catalogo_lab`; nenhum acesso remoto/deploy.

## Observar e entender

- **Atividades do plano**: `cadastros.AtividadePlano`, fonte local, escopo global
  documentado em `permissions.md`. Consulta/CRUD por permissões `cadastros.*_atividadeplano`
  dos papéis Viagens. Lista/manutenção `/cadastros/atividades/`, escolha na folha do
  plano, modal de evento adicional e conjuntos. Código único estável, nome, meta,
  recurso, ativo. Consumidores: `PlanoTrabalho.atividades`, `EventoPlano.atividades`,
  `ResultadoAtividade.atividade`, `PresetAtividades.atividades`. Resultados guardam
  quantidades/unidade de medida no uso; planos guardam textos já compostos.
- **Serviços de Eventos Sociais**: antiga `eventos.Servico`, fonte local global,
  manutenção por `eventos.change_servico` (administrador), seleção por qualquer
  solicitante autenticado sem ampliar acesso a solicitações. Lista/manutenção
  `/eventos/cadastros/servicos/`; seletores na solicitação e no modelo do tipo de
  evento; carga DEMO. Consumidores: `SolicitacaoServico.servico` (observação por uso)
  e `TipoEvento.servicos_sugeridos`. Nome, ativo e timestamps. Duplicação conceitual
  com AtividadePlano confirmada pela decisão explícita do usuário.
- **Conjuntos de atividades**: `PresetAtividades`, global, equipe Viagens, lista,
  formulário e cadastro rápido no plano; composição M2M e padrão local preservados.
- **Servidores**: `Servidor`, global, permissões `cadastros.*_servidor`; cadastro e
  cadastro rápido Viagens, equipe/coordenadores/assinantes/motoristas e eventos.
  Pessoa distinta de conta de usuário; cargo/unidade são relações locais preservadas.
  CPF/RG/telefone com unicidade e normalização existentes. Históricos protegem por FK
  e documentos mantêm snapshots. Porta local aplicada às escolhas de motorista externo,
  motoristas habituais e aos complementos comuns dos formulários.
- **Viaturas**: `Viatura`, global, permissões `cadastros.*_viatura`; cadastro, cadastro
  rápido, transporte do ofício. Placa e tipo/porte permanecem validados; motoristas,
  combustível e unidade continuam locais. Porta local aplicada ao transporte do ofício.
- **Unidades**: `Unidade`, global, permissões `cadastros.*_unidade`; cadastro, cadastro
  rápido e linhas do efetivo. A entidade mestre não absorve configuração institucional,
  assinantes, lotação nem permissão de conta. Porta local aplicada a escolhas comuns e
  efetivo; administração dos dados da unidade é tratada no lote próprio desta missão.
- **Cargos**: `Cargo`, global, permissões `cadastros.*_cargo`; cadastro, cadastro rápido,
  servidor e efetivo. Padrão é complemento local. Porta local aplicada às escolhas de
  cargo do servidor e do efetivo.
- **Combustíveis, municípios, programas e horários**: entidades distintas; não há
  equivalência comprovada com os serviços. Fonte local e regras próprias preservadas.
  Conexão futura destas entidades depende de contrato específico; não são importadas
  pelo contrato inicial de cinco tipos.

Problemas funcionais observados: dois catálogos independentes; manutenção por nome
nos testes/DEMO confundia identidade; exclusão pela tela de Eventos não conhecia usos
M2M de planos/conjuntos; acesso de leitura espalhado pelos formulários; ausência de
vínculo externo, propriedade por campo e reconciliação. O refinamento visual e suas
capturas pertencem ao lote de superfícies compartilhadas, não estão comprovados por
estes testes de backend.

## Projetar e implementar

Regra escrita primeiro em `docs/product/cadastros-compartilhados.md`; ADR 0044 aceita.
`AtividadePlano` é canônico por já ter identidade/código e mais consumidores. `Servico`
passa a ser proxy contextual, com as mesmas permissões e sem tabela operacional própria.
Ambos módulos leem a mesma fonte `atividades_e_servicos`, mantendo inativos já escolhidos.

Migrações 0018 (cadastros) e 0008 (eventos) mantêm IDs de atividades, resultados e
documentos. FKs e sugestões de Eventos migram por colunas/relações temporárias antes
da remoção das antigas. `ServicoLegado` preserva ID/nome/situação/datas anteriores,
FK `canonico`, critério e JSON das relações originais com observações. Não é cadastro
operacional e não possui permissões de manutenção geradas.

Merge automático único: serviço seed **Emissão de CIN** ativo → atividade `codigo=CIN`
ativa, com nome/meta/recurso integrais iguais à carga versionada. O nome canônico
permanece **Confecção da Carteira de Identidade Nacional (CIN)**. Sem estes atributos,
o serviço ganha identidade canônica própria `EVENTO_<id>` e mantém situação/datas.
Homônimos são preservados com `criterio=preservado_homonimo`; a igualdade de nome não
autoriza fusão. Mapeamento é consultável no banco e não depende do relatório estático.

Dados da carga: 11 atividades + 5 serviços → 15 itens canônicos, 5 mapas legados e
nenhuma cópia operacional por módulo. Mudanças locais adicionais podem alterar estes
totais; o teste de migração calcula os totais a partir da situação anterior.

`vinculos` agora verifica M2M do catálogo, PROTECT e identidades externas antes de excluir. A
exclusão de item com usos ou legado é recusada com orientação para inativar. Observações
e quantidades continuam nos usos. Atualizar cadastro não regrava arquivos/snapshots
emitidos; a migração não modifica tabelas de documento nem seus JSONs.
`SolicitacaoServico.nome_registrado` guarda o nome de cada uso: a migração usa o nome
original do serviço, e novos usos capturam o nome atual. Renomear o catálogo não
altera a leitura nem a exportação dos usos anteriores. Observações também permanecem.
O ContentType/permissões de `eventos.servico` mantêm IDs e vínculos de grupos/usuários:
a migração desfaz explicitamente a renomeação automática do ContentType para o legado.

## Fonte dedicada preparada

`gestao/cadastros/fontes.py` é a porta local, com `FonteLocalCadastros.consultar` para
servidor, viatura, unidade, cargo e atividade. Retorna QuerySets do espelho local e
carrega relações de servidor/viatura juntas. Consumidores continuam recebendo IDs
internos. Inclusão de inativos exige IDs previamente autorizados pelo consumidor.
As políticas de documento/solicitação permanecem nos módulos existentes.

`VinculoFonteCadastro` associa `(fonte, entidade, identificador_externo)` a um ID
local. Unicidade impede duas identidades na origem ou duas origens administrando o
mesmo item. Vínculo passa por existência do registro, autorização de alteração e
`full_clean`; exclusão local com vínculo é recusada.

`vincular_fonte` declara os campos de propriedade externa e registra a base conhecida.
`atualizar_da_fonte` exige revisão/payload completo, trava vínculo e registro, compara
base/local/recebido, valida as constraints locais e grava atomicamente. A mesma revisão
com payload divergente é recusada; repetição idêntica é idempotente. Origem sem mudança
não elimina uma mudança local; mudanças divergentes no mesmo campo abortam a transação.
O CRUD local informa o conflito quando tenta mudar campo de propriedade externa.

Propriedade externa possível: nome/identificação/contato/ativo do servidor; placa,
modelo/tipo/porte/ativo da viatura; nome/sigla/ativo da unidade; nome/ativo do cargo ou
atividade. Configuração institucional/assinantes, relações de cargo/unidade/combustível,
motoristas, padrões, código da atividade, meta e recurso permanecem locais. As
permissões do usuário também são locais. Nenhuma origem tem autoridade implícita.

Pendente da integração real: transporte/autenticação, contrato e tipos dos campos,
ordenação de revisões, fonte responsável por cada campo, identificadores de origem e
reconhecimento assistido dos registros existentes. Vincular exige ID local explícito;
não há matching por nome, polling ou sincronização remota configurados. Os testes
comprovam o contrato local, não a disponibilidade de uma base externa.

## Testar, comparar, criticar, corrigir e validar

- Domínio puro primeiro: quatro cenários de código estável e reconciliação passaram
  antes da implementação do serviço (`test_dominio_catalogo.py`).
- A primeira execução integral do esquema aplicou as duas migrações sem erro no LAB;
  identificou expectativa antiga pelo nome seed de CIN. Testes/DEMO passaram a buscar
  a identidade canônica pelo código ou nome canônico, sem recriar o seed antigo.
- Testes de integração adicionais cobrem o mesmo PK nos dois módulos, edição sem
  cópia, observação histórica, inativação, seleção anterior e proteção de exclusão;
  fontes cobrem cinco entidades, replay, conflitos, ownership e autorização.
- `test_migracao_catalogo.py` cria banco próprio descartável, migra o esquema anterior,
  injeta solicitação atendida, homônimos e serviço inativo, executa a migração real e
  confere contagens, mapas, FKs, observações, sugestões e situação histórica.

Validação concluída até este registro:

- `uv run pytest gestao/cadastros/tests/test_dominio_catalogo.py -q`: **6 passed**,
  incluindo normalização de CPF/RG/telefone/placa e aviso para meta não cadastrada.
- `uv run pytest gestao/cadastros/tests/test_migracao_catalogo.py -q`: **1 passed**
  em **47,23 s**, com snapshots e permissões legadas após o injector real de ContentType.
- Seleção anterior de catálogo/fontes/eventos/plano: **37 passed** antes da ampliação
  dos cenários de snapshot/ownership; nova execução abrangente registrada abaixo.
- `ruff check` dos arquivos do lote: verde.
- `mypy` de fontes, serviços, formulários, modelos, catálogo Eventos, planos e domínio:
  **Success: no issues found in 9 source files**.
- `makemigrations --check --dry-run`: **No changes detected**. A conexão ao nome base
  `pcpr_catalogo_lab` (que não existe) gera aviso de histórico; as aplicações e os testes
  de migração ocorreram nos bancos descartáveis/testes efetivamente criados.

A fonte reutiliza os validadores puros de CPF, telefone, RG e placa, além de
`full_clean`/constraints. A meta vazia é aviso contextual no Plano, conforme regra
prévia que já permite emitir sem atividades/metas, e não recebe texto inventado.

Rodada ampliada em LAB (431,07 s): `uv run pytest gestao/cadastros/tests
gestao/eventos/tests gestao/viagens/tests/test_planos.py
gestao/viagens/tests/test_de_eventos.py
gestao/viagens/tests/test_dominio_plano_trabalho.py -q --reuse-db --create-db
--maxfail=3` → **258 passed, 1 failed**. Catálogo, fontes, migração, Eventos e
Planos passaram. A única falha foi o teste de volume do seletor de assinantes do
lote Dados da unidade (`test_dados_unidade.py:163`): contagem esperada de duas opções
contra uma renderizada pelo combobox. Encaminhada ao coordenador desse lote para
correção; a verificação geral da missão registra o resultado final após integração.

Revisão cética final: o coordenador confirmou correção do teste do seletor por seu
lote e execução direcionada verde. As mutações de ativo em Cadastros e Eventos passam
pelo mesmo guardião de campos externos; exclusão nos cinco tipos verifica vínculos
de fonte. A associação não concede permissão adicional. O mapa preserva observações,
identificadores e situações, e a correção explícita de ContentType mantém também
permissões atribuídas diretamente, além das dos grupos.

A revisão reforçou a revalidação da whitelist em cada atualização externa (além da
vinculação inicial), tipos explícitos de payload, e persistência do snapshot ao usar
`save(update_fields=...)`. Uma fonte inconsistente não passa a administrar campos
locais nem converte objetos JSON indevidos em nomes. A verificação geral coordenada
registra o resultado integrado; não foram iniciadas novas rodadas amplas deste lote.

Validação direcionada após a revisão: domínio puro (8 cenários) + contrato com
ownership persistido inválido (1 cenário) → **9 passed em 26,38 s**. `ruff check`
dos arquivos deste reforço: verde. O lote entrega cinco entidades na porta local,
um catálogo canônico com 15 itens da carga e cinco mapas legados recuperáveis; não
implanta integração remota nem altera bases em operação.

<a id="fechamento-p03"></a>

## Fechamento P03 — motorista de Eventos e indicação de usos

O seletor de motorista de `FormularioSolicitacao` ainda carregava integralmente os
servidores ativos. Foi substituído por `OpcaoServidor` + `SelecaoRemota`, consultando
`fonte_local` e o endpoint `/eventos/api/motoristas/`. A busca devolve até 15 ativos
com nome/cargo/unidade; o registro atual inativo permanece no HTML e na validação,
mesmo fora dos primeiros resultados. A inclusão de outro inativo é recusada.

O endpoint usa a policy de criar solicitação quando não há contexto salvo; com
solicitação, exige contexto visível e permissão de editar/reabrir. Solicitação alheia
continua 404, estado fechado 403, e a seleção não concede `cadastros.view_servidor`
nem acesso administrativo ao cadastro. O formulário mantém `form=form-solicitacao`;
o coordenador propagou esse atributo ao input gerado pelo combobox compartilhado.

A lista central passou a mostrar contagens independentes de conjuntos, planos e
solicitações, reutilizando `_contagem` com subconsultas. Um cenário com três conjuntos,
dois planos e dois pedidos resultou em **3 / 2 / 2**, sem multiplicação por joins.
Adicionar cinco itens à mesma página não aumentou o número de consultas HTTP. Usos
adicionais/legados continuam protegidos pela verificação de vínculos no serviço.

Validação direcionada, sem nova rodada ampla:

- `pytest gestao/eventos/tests/test_motoristas.py -q --reuse-db -n 0`: **3 passed**;
  autorização/limite/metadados, ausência de CRUD, atual inativo fora de 15, rejeição
  de novo inativo e HTML com duas opções; renderização do campo em uma consulta.
- Teste de contagem + `test_motorista_por_busca_canonica_preserva_formulario_e_persistencia`:
  **2 passed em 38,84 s**. O primeiro ensaio corrigiu apenas o acesso da fixture ao
  contexto `page_obj` (usava `pagina`, sinalizador do cabeçalho).
- E2E selecionou servidor fora da primeira página, conferiu nome/cargo/unidade,
  confirmou o ID salvo por autosave sem perder o local do evento, inativou o servidor
  e confirmou preservação ao reabrir. Select e input mantiveram o mesmo formulário.
- Capturas `evidencias/motorista-eventos-360.png` e `motorista-eventos-1440.png`
  revisadas: campo ocupa uma coluna no celular e duas com unidade móvel no desktop,
  com controles, ações e contexto visíveis.

Ambiente: o mesmo banco LAB isolado do lote, sem paralelismo adicional. A manutenção
`ANALYZE cadastros_municipio` foi aplicada somente ao banco de teste para corrigir
estatísticas desatualizadas; o cenário sintético compartilhado passou a fazê-la
antes dos fluxos de navegador, conforme diagnóstico registrado pelo coordenador.
