# Coffee Break — especificação levantada da referência (05/10/2026)

Levantamento de comportamento (não de código) do app `coffee_break` da referência e das
integrações dele com `agenda`, `core` (página inicial, busca de endereço, "preencher com
e-mail"), `relatorios`, `solicitacoes`, `demandas_eventos` e `documentos`. Caminhos
relativos ao clone da referência. Documentos de apoio da própria referência:
`docs/COFFEE_BREAK_ETAPAS.md` e `docs/COFFEE_BREAK_CERTIFICADO.md`. Não há ficha do Coffee
Break em `docs/paridade/` (só Viagens e Cadastros).

**Dados pessoais:** o comando de importação (`coffee_break/management/commands/importar_coffee_break.py:37-92`)
e os valores padrão da configuração do ofício (`coffee_break/models.py:205-217`) trazem
nomes, CNPJs, telefones e e-mails reais (fiscal, assinante, destinatário, fornecedores).
**Não foram transcritos**; a reimplementação deve usar valores neutros ou vazios e ler o
real só da carga de dados autorizada.

**Tamanho:** 11 modelos próprios (+ vias em `DocumentoArtefato` do núcleo documental), 60
rotas autenticadas + 1 rota pública por token, 16 telas cheias + 13 modais e trechos,
5 documentos gerados (OS, ofício, certifico, certificado, relatório do contrato), ~19 mil
linhas Python e ~330 testes.

---

## 1. Acesso e perfis

- Módulo `ASCOM_COFFEE_BREAK` (`coffee_break/permissions.py:16`). Quem tem algum setor
  autorizado no módulo enxerga **tudo** (não há isolamento por setor nem por autor):
  lotes, solicitações, certidões (`permissions.py:1-7`). Superusuário sempre tem acesso
  (`accounts/modulos.py:101-115`). Módulo inativo bloqueia todos (`coffee_break/tests.py:160-162`).
- Semente: cria o módulo e autoriza o setor ASCOM (`coffee_break/migrations/0002_seed_modulo_ascom.py:14-23`).
- **Administrador do módulo** = módulo + perfil ADMINISTRADOR (grupo) ou superusuário
  (`permissions.py:28-38`, `solicitacoes/permissions.py:58-59`). Só ele: Cadastros
  (fornecedores, contratos, lotes, ofício e eProtocolo), importar planilha, anexar
  contrato/aditivo por PDF, virada de exercício, reabrir concluída para correção, editar
  na folha do documento os dados que vêm de cadastro (`coffee_break/editor.py:383-404`),
  e os itens de menu "Cadastros" e "Textos dos documentos" (`coffee_break/apps.py:69-84`).
- Sem módulo: 403 em qualquer URL, inclusive POST de ações; anônimo vai ao login
  (`coffee_break/tests.py:133-157`). O módulo aparece no portal e na navegação só para quem
  tem o código (`tests.py:164-196`).
- Rota pública `/fornecedor/<token>/` fora do namespace protegido; só responde a token
  válido (`coffee_break/urls_publicas.py:1-16`).
- Menu do módulo: Painel, Lotes, Solicitações, Certidões, Cadastros (admin), Textos dos
  documentos (admin) (`apps.py:40-86`).

## 2. Cadastros (catálogos contratuais)

Tela única de cadastros com trilha lateral (um item por tabela, com total), busca, lista
paginada (25) e criar/editar em modal; sem JavaScript, `?novo=1` / `?editar=<pk>` abrem o
modal (`coffee_break/views.py:102-143`, `1849-1962`). Todos com **trava de versão**:
"Este cadastro foi alterado por outra pessoa. Recarregue a página antes de salvar."
(`coffee_break/forms.py:470-494`). Sucesso: "<Singular> salvo com sucesso.". Excluir em uso
é recusado: "Não é possível excluir: <singular> em uso (contratos, lotes ou solicitações)."
(`views.py:1965-1982`; FKs `PROTECT`).

### 2.1 Fornecedor (`coffee_break/models.py:31-90`, `forms.py:497-516`)
| Campo | Regra |
|---|---|
| razão social | 200, obrigatória, única |
| nome curto | 60, opcional — vai no detalhamento do eProtocolo; em branco usa a razão social em maiúsculas sem LTDA/EIRELI/ME/EPP/S.A. (`models.py:75-80`) |
| CNPJ | aceita com ou sem pontuação, guarda 14 dígitos; único quando preenchido; "O CNPJ deve ter 14 dígitos." |
| contato (150), telefone (30), e-mail | opcionais; o e-mail é o destinatário dos e-mails ao fornecedor |
| portal da certidão municipal | URL (300) — a prefeitura da sede |

Na lista: CNPJ, contato, e-mail e o resumo das entregas ("N entregas registradas · nota
média 4,5 · 2 ocorrências") (`coffee_break/presenters.py:233-249`, `services.py:1212-1221`).

### 2.2 Contrato (`models.py:93-161`, `forms.py:519-544`)
Fornecedor (obrigatório), número (30, único), número GMS, termo aditivo em vigor (texto),
fiscal responsável e cargo do fiscal (padrão "Agente de Polícia Judiciária"), cláusula do
pagamento (padrão "Cláusula Décima, item 10.2.6"), PDF do contrato e do termo aditivo (só
PDF), vigência início/fim (+ "estimada"), quantidade contratada, valor unitário (4 casas),
valor total, **antecedência mínima do pedido em dias (padrão 2)**, objeto, observações.
Referência documental usada nos documentos: "<número> – GMS <gms> - TERMO ADITIVO Nº <aditivo>"
(`models.py:153-161`). Na lista: selo Vigente/Vencido e "Vigente até / Vencido em dd/mm/aaaa
(estimada)" (`presenters.py:310-328`, `348-359`). Atalho para o relatório do contrato.

**Termo aditivo** (`models.py:164-190`): número (único por contrato), PDF, vigência
início/fim. Todos ficam (o anexo do protocolo leva todos); o contrato cita o de vigência
mais longa. **Fim da vigência efetivo** = o maior entre o do contrato e o dos aditivos
(`services.py:484-488`).

**Anexar contrato ou aditivo por PDF** (admin; `views.py:2648-2743`, `coffee_break/contratos_pdf.py`):
basta anexar; o sistema identifica se é contrato ou aditivo, lê CNPJ e razão social do
contratado, número, GMS, aditivo, lote, quantidade, valores e vigência (do contrato
inicial só o prazo → vigência estimada; o aditivo traz a data escrita e corrige). Cria o
fornecedor pelo CNPJ se não existir; cria o lote se o contrato não tiver nenhum. Mensagens:
"Escolha o PDF do contrato ou do termo aditivo."; "Este PDF não parece ser um contrato nem
um termo aditivo da SESP (não achei o número do contrato)."; "Não achei o CNPJ do contratado
no documento do contrato N."; "O contrato N está cadastrado para X, mas este documento é de
Y."; sucesso "Contrato N (X) anexado e conferido; vigente até dd/mm/aaaa (estimada pelo
prazo; o termo aditivo confirma); 1.234 unidades; lote K criado — escolha os municípios dele
em Lotes." (aviso em vez de sucesso se vencido).

### 2.3 Lote (`models.py:300-390`, `forms.py:566-603`)
Contrato, número (inteiro), exercício (texto até 9, ex. "2026"), quantidade total (≥ 1),
empenho, valor do empenho, municípios abrangidos (N:N com Município), municípios (texto
original da planilha), orientações, especificações técnicas, observações, **lote vigente**
(ativo; só lotes ativos recebem pedido pelo município). Único por (contrato, número,
exercício). Ordem: exercício desc, número. Rótulo "Lote N (AAAA)".
- Capacidade não pode ficar abaixo do consumido: "O lote já consumiu N unidades; a
  capacidade não pode ficar abaixo disso." (`forms.py:593-603`).

### 2.4 Ofício e eProtocolo (configuração, registro único — `models.py:193-286`, `forms.py:547-563`)
Vocativo do ofício, quem assina e cargo, bloco do destinatário (uma linha por linha),
assunto e palavras-chave do eProtocolo (padrões "LICITACAO" / "REGISTRO DE PRECO"), destino
do despacho ("Ao GAF,"), e-mail da ASCOM em cópia (vários separados por vírgula), assunto e
texto do e-mail da OS e da ordem bancária com campos `{numero} {evento} {data} {horario}
{local} {responsavel} {quantidade} {fornecedor}` (+ `{nota} {ordem_bancaria}
{data_ordem_bancaria}` no da OB). Não se cria nem exclui: "Esta configuração não se exclui;
edite os campos." (`views.py:1970-1972`). Padrões de texto dos e-mails em `models.py:233-265`
(textos genéricos, podem ser reaproveitados; os nomes de pessoas não).

### 2.5 Textos dos documentos
Admin edita os textos-base (blocos) da OS, do ofício e do certifico pela tela de modelos
do núcleo documental (`apps.py:77-84`, `coffee_break/editor.py:100-190`). Blocos: cabeçalho
(secretaria, órgão, unidade), rodapé, cidade, títulos, rótulos, parágrafos do ofício e do
atesto, linha de assinatura; quebras de página nomeadas.

## 3. Solicitação de coffee break (= a Ordem de Serviço)

### 3.1 Campos (`models.py:411-786`)
| Campo | Tipo / regra | Etapa |
|---|---|---|
| lote | FK, **escolhido pelo município** (quem pede não escolhe) | 1 |
| município do evento | só municípios do PR (+ o atual); obrigatório, exceto registro antigo sem município | 1 |
| data da solicitação | data, padrão hoje | 1 |
| número (Nº da OS) | texto 20, "NN/AAAA"; tela mostra só a sequência com "/ AAAA" ao lado; texto livre só para legado | 1 |
| descrição do evento (objeto da OS) | obrigatória; quebras de linha viram espaço (`forms.py:119-121`) | 1 |
| quantidade (pessoas) | inteiro ≥ 1: "A quantidade deve ser de pelo menos 1 unidade." | 1 |
| data do evento | uma data só; salvar a etapa 1 limpa o fim antigo (`forms.py:323-367`) | 1 |
| fim do evento / período em texto | legado da planilha; "Use as datas estruturadas ou o período em texto, não os dois." | — |
| horário | hora | 1 |
| detalhamento do pedido | em branco a OS monta "Solicito coffee para:\nDia 01/10 às 9h30 p/ 40 pessoas." (`models.py:704-723`) | editor |
| local de entrega, endereço, bairro, CEP (00000-000), responsável pelo recebimento ("nome e telefone") | texto | 1 |
| registro retroativo + justificativa (255) | campos de tela, não do modelo | 1 |
| OS enviada ao fornecedor em | data (gravada pelo e-mail) | — |
| nº da nota fiscal, PDF da nota, valor/emissão/CNPJ emitente lidos do PDF | | 2 |
| quantidade faturada | ≥ 1; em branco o lote desconta a pedida | 2 |
| nº do ofício, data do ofício, "PCPR protocolo n.º" | | 2 |
| protocolo de pagamento | máscara 00.000.000-0 (vem do protocolo do ofício) | 2/3 |
| atesto e envio ao GAF, ordem bancária emitida em, OB enviada à empresa em | datas | 3 |
| PDF da OB, nº e valor da OB lidos | | 3 |
| observações | texto | 3 |
| valor unitário | cópia do preço do contrato na criação (ou na troca de lote) | auto |
| cancelada, quando, por quem, motivo (255) | | ação |
| em correção (reaberta) | booleano | ação |
| pagamento junto com | auto-FK para a OS principal do pagamento conjunto | 2 |
| origem | FK opcional para Solicitação de evento ou Palestra/evento da ASCOM | auto |
| criado por / em, atualizado em | | auto |

Restrições do banco (`models.py:581-612`): número único por lote quando preenchido; fim ≥
início; quantidade ≥ 1 salvo cancelada; OB ≥ atesto; envio à empresa ≥ OB.

### 3.2 Situação financeira (derivada, nunca gravada — `services.py:33-52`)
Pela ordem dos marcos: Cancelada → Concluída (envio à empresa) → Aguardando envio à empresa
(OB) → Aguardando ordem bancária (atesto) → Aguardando atesto (protocolo) → Aguardando
protocolo (nota) → **Aguardando nota fiscal**. Rótulos em `models.py:393-408`.
Regras de ordem (`models.py:625-671`, mensagens literais):
- "A data de fim não pode ser anterior à data de início."
- "Informe a nota fiscal antes do protocolo de pagamento."
- "Informe o protocolo de pagamento antes do atesto."
- "Informe o atesto antes da ordem bancária."
- "Informe a emissão da ordem bancária antes do envio à empresa."
- "A ordem bancária não pode ser anterior ao atesto."
- "O envio à empresa não pode ser anterior à emissão da ordem bancária."
- Etapa 2: "O protocolo de pagamento já foi registrado: a nota não pode ficar em branco." (`forms.py:383-389`)

Estados derivados: **financeiro iniciado** = qualquer marco preenchido (`models.py:747-757`)
→ trava município, data, número, descrição, quantidade e período (`forms.py:102-114`; aviso
"Os dados do pedido e do evento foram bloqueados porque a nota fiscal já foi registrada. Os
dados da ordem de serviço continuam editáveis."). **Concluída** = envio à empresa e não
cancelada. **Bloqueada** = cancelada, ou concluída sem estar em correção (`models.py:763-766`):
abre só para consulta; POST: "Solicitações canceladas ou concluídas ficam bloqueadas para
edição." (`views.py:1391-1402`).

### 3.3 Escolha do lote pelo município (`services.py:561-625`, `forms.py:213-231`)
1. Lotes ativos que listam o município; havendo vários, prefere contrato **não vencido** na
   data do evento, depois o do **exercício do ano da data**, depois o de **maior saldo**.
2. Senão, o lote cuja cidade listada está mais perto em linha reta (haversine, precisa de
   latitude/longitude dos municípios), preferindo não vencido, menor distância (km
   arredondado) e exercício do ano; a tela mostra "<cidade>, a N km".
3. Nada: "Nenhum lote ativo atende <município>. Inclua o município na lista de um lote em
   Cadastros › Lotes."
A tela mostra, ao escolher o município, o lote que ele recebe: lote, fornecedor, contrato e
aditivo, "N de M unidades", empenho, "Vigente até / Vencido em" (`views.py:784-811`).
Registro existente só troca de lote se o município mudar.

### 3.4 Saldo do lote (`models.py:289-313`, `services.py:55-106`)
- **Consumido** = Σ quantidade efetiva das solicitações **não canceladas** do lote, onde
  quantidade efetiva = faturada se houver, senão pedida. **Restante** = total − consumido.
  Nunca armazenados.
- Gravar trava a linha do lote (`select_for_update`) e revalida na mesma transação:
  "Quantidade acima do saldo do lote: restam R de T unidades."
- Exemplo: lote de 1.000; OS A pede 300, OS B pede 200 → restante 500. Nota de A fatura 280
  → consumido 480, restante 520 (histórico: "Quantidade faturada: 280 de 300 pedidas; 20
  voltaram ao saldo do lote."; se faturar a mais: "…; N a mais saíram do saldo do lote.";
  remover: "Quantidade faturada removida: o lote volta a descontar as N pedidas.")
  (`views.py:1351-1365`). Cancelar B → restante 720. Reativar B revalida o saldo.
- Percentual consumido = round(consumido × 100 / total); selo "N% consumido" verde < 70,
  âmbar ≥ 70, vermelho ≥ 90 (`presenters.py:270-279`).

### 3.5 Valores em reais (`models.py:731-745`, `services.py:437-472`)
- Valor da OS = quantidade efetiva × valor unitário (o guardado na OS; legado sem ele usa o
  do contrato), arredondado a centavo (meio para cima). Ex.: 40 × R$ 21,0700 = R$ 842,80.
- Por lote: comprometido (OS não canceladas), pago (com data de OB), saldo do empenho =
  valor do empenho − comprometido.
- Gasto no ano: OS não canceladas com evento no ano (ou pedido, sem data de evento) e
  quanto já foi pago. Formato "R$ 1.234,56", "—" sem valor.

### 3.6 Numeração da OS e do ofício (`services.py:632-793`, `forms.py:123-158`, `402-425`, `apps.py:20-25`)
- **Livro único com Viagens**: a OS do Coffee Break usa a mesma sequência anual das Ordens
  de Serviço de Viagens; o ofício ao GAF, a mesma dos Ofícios de Viagens. Os números daqui
  contam como ocupados lá (registro de "números externos").
- Próximo = a menor lacuna liberada por exclusão; senão o maior usado nos dois módulos + 1.
  A nova solicitação já vem com o próximo sugerido (editável).
- Digitar "41" vira "41/AAAA" (ano do número atual, senão o da data da solicitação / do
  ofício). Sequência < 1: "O número da OS deve ser 1 ou mais." / "O número do ofício deve
  ser 1 ou mais.". Repetido: "A OS 41/2026 já existe (<evento>). A próxima livre é 42." ou
  "O número 41/2026 já é de uma ordem de serviço de Viagens (a numeração é conjunta). A
  próxima livre é 42." (ofício: "O ofício N já existe." / "…de um ofício de Viagens…
  O próximo livre é N.").
- Gravação sob a trava do livro: em branco ou igual ao sugerido → **reservar** (pode sair
  outro se alguém acabou de usar); digitado → **conferir** e recusar se ocupado. O número
  usado deixa de ser lacuna em Viagens. Ofício em branco = próximo; data do ofício em
  branco = hoje. OS do mesmo pagamento conjunto dividem o número do ofício.

### 3.7 Outras regras do pedido (etapa 1)
- **Vigência** (`forms.py:233-256`): evento (ou pedido) depois do fim da vigência efetiva
  bloqueia: "Contrato vencido em dd/mm/aaaa: o contrato N do Lote K (AAAA) não cobre um
  evento em dd/mm/aaaa. Providencie o aditivo de prorrogação ou cadastre outro lote para o
  município." Vale só para pedido novo ou quando município/data mudam.
- **Retroativo** (`forms.py:343-362`): evento antes da data da solicitação exige marcar
  "registro retroativo" e justificar ("O evento é anterior à data da solicitação. Confira a
  data ou marque "registro retroativo" e justifique." / "Justifique o registro
  retroativo."); a justificativa vai ao histórico.
- **Antecedência** (aviso, não bloqueia — `services.py:524-539`): evento em menos dias que
  a antecedência mínima do contrato: "O evento é hoje|amanhã|em N dias (dd/mm/aaaa), com
  menos que os M dias de antecedência do contrato N: ligue para o fornecedor para confirmar
  o atendimento."
- **Trava de versão**: "Esta solicitação foi alterada por outra pessoa. Recarregue a página
  antes de salvar." (`forms.py:190-198`).
- **Sugestão de local** (`views.py:1178-1213`): ao escolher o município, até 10 locais já
  usados nele (local + responsável, sem repetir, do mais recente), com OS e data; o clique
  preenche local, responsável e, se gravados, endereço/bairro/CEP.
- **Duplicar** (`views.py:1157-1175`, `1288-1294`): nova solicitação com município,
  descrição, quantidade, horário, local, endereço, bairro, CEP e responsável copiados;
  **nunca** datas, número, nota, ofício, protocolo ou pagamento. Cartão "Copiada de …" e
  histórico "Duplicada da solicitação N.".
- **"Criar aqui" da Agenda**: `?inicio=` preenche a data do evento (`views.py:1280-1287`).
- Criar: "Solicitação N registrada no Lote K (AAAA) (<fornecedor>). A ordem de serviço já
  pode ser gerada." e volta à lista (`views.py:1269-1275`). Editar: "Solicitação de coffee
  break atualizada."; etapa 2 segue para a 3; etapas 1 e 3 voltam à lista (`views.py:1448-1454`).
  Erro: "Corrija os campos destacados para continuar.". Erro do modelo num campo de outra
  etapa sobe para o topo (`forms.py:269-286`).

### 3.8 Ações sobre a solicitação
| Ação | Quem | Regra e mensagens |
|---|---|---|
| Cancelar | módulo | motivo obrigatório; não cancela concluída nem já cancelada. "A solicitação já está cancelada." / "Solicitações com o fluxo financeiro concluído não podem ser canceladas." / "Informe o motivo do cancelamento." Sucesso: "Solicitação cancelada — a quantidade voltou ao saldo do lote." Sai do pagamento conjunto (`services.py:118-154`, `views.py:1622-1646`) |
| Reativar | módulo | revalida saldo: "A solicitação não está cancelada." / "Informe uma quantidade válida antes de reativar a solicitação." Sucesso: "Solicitação reativada e saldo consumido." (`services.py:215-247`) |
| Excluir | módulo | só sem nota nem protocolo (financeiro não iniciado): "A solicitação N já tem nota ou protocolo: cancele em vez de excluir." Sucesso: "Solicitação N excluída — a quantidade voltou ao saldo do lote." (`views.py:1649-1666`) |
| Reabrir para correção | admin | só concluída; motivo obrigatório. "Só solicitações concluídas são reabertas para correção." / "A solicitação já está aberta para correção." / "Informe o motivo da correção." Sucesso: "Solicitação reaberta para correção. O que mudar fica no histórico." Cada campo mudado vira "Correção — <rótulo>: antes → depois." (`services.py:187-212`, `views.py:1334-1348`, `1724-1739`) |
| Encerrar correção | admin | "A solicitação não está aberta para correção." / "Correção encerrada: a solicitação voltou a ficar só para consulta." |
| Registrar andamento | módulo | grava só o **próximo marco** (nº NF → protocolo → atesto → OB → envio), com anotação opcional; data padrão hoje. "Esta solicitação não tem marco a registrar." / "Informe: <rótulo>." / "Data inválida." Sucesso: "Andamento registrado: <situação>." Modal na lista (`services.py:980-1063`, `views.py:1499-1530`) |

### 3.9 Histórico (`models.py:789-825`)
Ações: Solicitação criada / atualizada / cancelada / reativada / E-mail enviado / Envio do
fornecedor. Cada gravação registra "Campos atualizados: <rótulos>" (ou "Solicitação salva
sem alteração de campos."). Criação diz a origem ("Pedida a partir de: …", "Duplicada da
solicitação …", e-mail de origem). Aqui o histórico de campos vem da trilha do banco; os
movimentos de negócio (cancelar, e-mail, fornecedor, correção) ficam como movimentos.

## 4. Fluxo em três etapas (telas da solicitação)

Stepper com três etapas (`views.py:816-852`), cada uma grava só os seus campos:

1. **Solicitação e OS** (`/solicitacoes/<pk>/editar/`): seção "Evento e ordem de serviço"
   (município com lote e saldo, data, nº OS, descrição, pessoas, data/horário, local,
   endereço, responsável, retroativo), cartão da origem (evento/palestra) com aviso de
   remarcação, a **OS no editor de documentos** (folha A4 editável que acompanha o
   formulário já na criação), envio da OS por e-mail ("OS ainda não enviada ao fornecedor"),
   entrega ("Entrega ainda não registrada"), "Situação da solicitação" (cancelar/reativar/
   reabrir), histórico. Concluída quando a OS não tem pendências ou o financeiro começou.
2. **Nota fiscal, ofício e certifico** (`/nota/`): anexar a nota (PDF; número lido do PDF),
   nº da nota, pessoas faturadas ("Pedido: N. Em branco, o lote desconta o pedido; com a
   nota, desconta o faturado e a diferença volta ao saldo."), conferência da nota, data e nº
   do ofício (próximo sugerido), protocolo PCPR, pagamento conjunto (escolher OS do mesmo
   lote), envios do fornecedor pelo link (aceitar/recusar), ofício e certifico no editor.
   Concluída com protocolo, ou nota + PDF + nº do ofício.
3. **Protocolo e pagamento** (`/protocolo/`): passo a passo do eProtocolo, dados para copiar,
   anexo do protocolo (lista ordenada com "Pronto"/o que falta/"Resolver"), baixar
   documentos, registrar o número do protocolo, anexar OB, atesto/OB/envio, observações,
   enviar OB ao fornecedor. Concluída quando concluída a solicitação.

### 4.1 Nota fiscal (`views.py:2547-2599`, `services.py:341-430`, `coffee_break/nota_fiscal.py`)
- Só PDF ("Envie o arquivo em PDF.") e validação central de upload. Lê número (chave de
  acesso NF-e/NFC-e de 44 dígitos, "Nº 000.008.957" do DANFE, rótulos de NFS-e), valor
  total, data de emissão e CNPJ do emitente.
- "Nota fiscal N anexada — o número foi lido do PDF." ou "Nota fiscal anexada, mas não deu
  para ler o número no PDF: informe-o no campo ao lado."; remover: "Nota fiscal removida."
  (limpa o que foi lido). Histórico "Nota fiscal (PDF) anexada|substituída; número N lido do PDF.".
- **Conferência (só avisa)**: CNPJ do emitente ≠ fornecedor do lote ("A nota foi emitida
  pelo CNPJ X, e não pelo do fornecedor do lote (Y, Z)."); valor ≠ quantidade efetiva ×
  unitário ("O valor da nota (R$ A) não bate com N pessoas × R$ U = R$ E. Se a nota cobrou
  outra quantidade, informe as pessoas faturadas."); emitida antes do evento; mesma nota do
  mesmo fornecedor em outra OS não cancelada ("A nota N do X já está na OS M.").

### 4.2 Pagamento conjunto (`services.py:796-962`, `models.py:555-566`, `768-786`)
- Várias OS **do mesmo lote** num só ofício e num só protocolo. Uma é a principal; as
  outras apontam para ela. Candidatas: mesmo lote, não canceladas, não concluídas, sem
  protocolo de pagamento, fora de outro pagamento conjunto. Recusa: "Só entram OS do mesmo
  lote, sem protocolo de pagamento e fora de outro pagamento conjunto."
- Marcar/desmarcar já vincula (JSON, sem salvar a etapa — `views.py:2531-2544`).
- **Espelhados** em todas: nº/data do ofício, protocolo PCPR, protocolo de pagamento,
  atesto, OB (data, PDF, nº, valor) e envio à empresa. Os campos posteriores à nota só vão
  para OS que já têm nota. Cada OS recebe histórico "Copiado da OS N (pagamento conjunto) —
  <campo>: <valor>.". Nota e certifico são de cada OS.
- O protocolo de pagamento só entra quando **todas** as OS do grupo têm nota; o atesto
  idem. Cancelar ou excluir a principal: a próxima (por número) assume; histórico nas que
  ficam ("A OS N foi cancelada|excluída e saiu do pagamento conjunto.").
- Ofício lista um item por OS ("• <evento> - Coffee Break para N (extenso) pessoas.") e as
  notas no plural ("8950, 8952 e 8954").

### 4.3 Protocolo de pagamento (`coffee_break/protocolo_pagamento.py`, `services.py:869-907`)
- O eProtocolo alcançado é de treinamento: o protocolo é **aberto à mão** e o número é
  registrado na etapa 3: formato 00.000.000-0 (máscara automática com 9 dígitos); "Informe o
  número do protocolo aberto no eProtocolo." / "O número do protocolo deve estar no formato
  00.000.000-0.". Vira o "PCPR protocolo n.º" do ofício (espelhado) e, com a nota (de todas
  as OS do grupo), o protocolo de pagamento: "Protocolo N registrado como protocolo de
  pagamento. Ficou no histórico." ou "Protocolo N registrado no ofício. Ele vira o protocolo
  de pagamento quando a nota fiscal for registrada | as OS X, Y tiverem a nota fiscal."
- PCPR em outro formato (número interno "2026.050880.000") não substitui um protocolo de
  pagamento já gravado.
- **Atesto e envio ao GAF** = o dia em que se baixam os arquivos do protocolo (uma vez só;
  exige protocolo; não em cancelada) (`services.py:893-907`, `views.py:1701`, `2091-2093`).
- Passo a passo literal em `protocolo_pagamento.py:52-63`.

### 4.4 Ordem bancária (`views.py:2423-2474`, `services.py:1070-1148`, `coffee_break/ordem_bancaria.py`)
- Exige nota: "Registre a nota fiscal antes da ordem bancária.". PDF; lê número (ex.
  "2026OB012345"), data e valor. Guarda em todas as OS do pagamento; se a OB é o próximo
  marco, registra a data lida (ou hoje; se anterior ao atesto, hoje). Mensagem "Ordem
  bancária anexada — nº N lido do PDF; OB emitida em dd/mm/aaaa (data lida do PDF)." ou
  "…; registre o atesto para a data da OB entrar.". Remover tira de todas as OS; o arquivo
  só sai do disco quando ninguém mais aponta para ele.
- Aviso: valor da OB ≠ soma das notas do pagamento (ou das OS, sem nota lida): "O valor da
  ordem bancária (R$ A) não bate com o valor das notas fiscais (R$ E). Confira o PDF anexado
  (retenções de imposto explicam diferença)."

## 5. Documentos gerados

Todos por WeasyPrint a partir de HTML (aqui: o motor de PDF de Viagens), medidos sobre os
modelos reais (Arial/Times, posições em pontos), brasão e marca PCPR, cabeçalho e rodapé da
ASCOM. Tela mostra prévia em HTML (não depende de leitor de PDF), "Visualizar" e "Baixar".
Falha do motor: "O gerador de PDF (WeasyPrint) não está disponível neste servidor."
Nome do arquivo: "<prefixo> <nº> - Lote <n> - <4 primeiras palavras do fornecedor>.pdf"
(`documentos.py:650-653`).

| Documento | Pendências (bloqueiam) | Conteúdo |
|---|---|---|
| **Ordem de serviço** | "Informe o número da solicitação (é o número da OS)." / "Informe o local de entrega." / "Informe o responsável pelo recebimento." (`documentos.py:145-153`) | Cidade e data por extenso; "ORDEM DE SERVIÇO <nº>"; fornecedor; Contrato (referência documental); Empenho (se houver); OBJETO; DETALHAMENTO DO PEDIDO; LOCAL DE ENTREGA + endereço completo; RESPONSÁVEL PELO RECEBIMENTO; linha de assinatura com o fiscal (maiúsculas) e o cargo |
| **Ofício ao GAF** (um por pagamento) | nota de cada OS do grupo ("Informe o número da nota fiscal [da OS N]."), nº do ofício (`documentos.py:212-220`) | "OFÍCIO <nº>"; linha miúda com "PCPR Protocolo n.º" e cidade/data ("21 de Setembro de 2026"); vocativo; parágrafo de entrega; itens por OS com quantidade por extenso; "Encaminho, em anexo, a(s) Nota(s) Fiscal(is) n° …, devidamente atestada…, nos termos da <cláusula>, do CONTRATO <referência>."; fecho, assinante e cargo; bloco do destinatário |
| **Certifico digital** (um por nota) | "Informe o número da nota fiscal." | "CERTIFICO DIGITAL"; "Nota Fiscal nº N, emitida pela empresa X, inscrita no CNPJ nº Y (CONTRATO <referência>)."; caixa do ATESTO com o texto padrão; "(assinado e datado digitalmente)"; fiscal, cargo, "Fiscal do Contrato n° N" |
| **Certificado da solicitação** (`docs/COFFEE_BREAK_CERTIFICADO.md`, `coffee_break/documents.py`, `templates/documentos/pdf/coffee_break_certificado.html`) | nenhuma; sai também para cancelada/concluída | Espelho do registro, não armazenado: Pedido (nº, data, quantidade, situação, evento, período); Lote, contrato e fornecedor (lote, exercício, contrato, GMS, empenho, fiscal, fornecedor, CNPJ, municípios); Fluxo financeiro (os 5 marcos, "Pendente" quando vazio); observações; faixa de cancelamento com motivo; pé com local/data de emissão, quem registrou e quem emitiu, ressalva "Vale como espelho do registro na data da emissão; a situação corrente é sempre a do sistema." Sem runtime: "Não foi possível gerar o certificado agora. <erro>" |
| **Relatório do contrato** (tela, PDF, CSV — `coffee_break/relatorio_contrato.py`) | — | ver §8 |

**Editor de documentos** (`coffee_break/editor.py:1-23`): tudo na folha se edita — dado da
solicitação muda a solicitação (com as mesmas validações de número; dados-base travados com
financeiro iniciado); dado de cadastro muda o cadastro (só admin; "Muda o cadastro, em todos
os documentos deste …"); texto do modelo vale só para aquele documento daquela solicitação;
quebras de página. O texto do ofício mora na OS principal.

**Vias** (`coffee_break/vias.py:1-143`): todo PDF que sai (visualizar, baixar, e-mail,
arquivos do protocolo) é guardado como via emitida (data, quem); folha igual à última não
gera outra via. **Via assinada**: anexar o PDF assinado da OS, do ofício ou do certifico;
passa a valer no lugar do gerado em todo pedido até ser removida (a via fica guardada).
Mensagens: "Escolha o PDF assinado."; "Documento assinado anexado. Ele passa a valer no
lugar do gerado; a versão anterior fica guardada."; "Versão assinada removida. O PDF gerado
volta a valer." (`views.py:2101-2160`). Bloqueado em cancelada/concluída.

**Anexo do protocolo** (`documentos.py:345-578`) — ordem: ofício; para cada OS do pagamento,
nota fiscal e certifico; certidões FGTS, trabalhista, municipal, estadual, federal; todos os
termos aditivos (do mais antigo ao mais novo; ou o aditivo do contrato); contrato. Cada item
diz pronto ou o que falta ("Certidão não cadastrada.", "Vencida em dd/mm/aaaa.", "Anexe o
PDF do termo aditivo em Cadastros › Contratos.", "Anexe o PDF no cadastro do contrato.") e
leva a "Resolver". Certidão vencida entra no PDF com aviso; o que falta fica de fora. Nomes
numerados "01 - Of.124 coffee break <NOME CURTO>.pdf", "02 - NF8957 …", "CERTIFICO DIGITAL …".
**Quatro arquivos para baixar** (`PARTES`): (1) OS de todas as OS do pagamento; (2) ofício;
(3) notas e certificos intercalados; (4) contrato, aditivos e certidões. Saída: um PDF por
arquivo, ZIP com vários, ou PDF único na ordem. "Marque ao menos um arquivo para baixar.";
"<parte>: nenhum documento disponível ainda." (`views.py:1669-1721`, `2080-2094`).

**Textos do eProtocolo** (`documentos.py:599-647`): detalhamento "ENVIO P/ PAGAMENTO DA NOTA
FISCAL N <nº> - (<NOME CURTO>)" (plural: "…DAS NOTAS FISCAIS N 8952 E 8954 - (…)");
despacho "<destino>\nEncaminhamos o presente protocolado com as devidas informações para o
pagamento da Nota fiscal n° …"; assunto do despacho "CONTRATO N - GMS G - TERMO ADITIVO No
A"; interessado (CNPJ e nome), assunto, palavras-chave, Nº/Ano do ofício — cada um com botão
"Copiar".

## 6. Certidões dos fornecedores (`coffee_break/certidoes.py`, `models.py:882-930`, `views.py:2626-2787`)

- Tipos: Federal, Estadual (Paraná), Municipal, Trabalhista, FGTS. Histórico preservado; a
  vigente de cada tipo é a de maior validade.
- Quadro por fornecedor **com lote ativo**: uma linha por tipo com situação **faltando /
  vencida / vencendo (≤ 15 dias) / vigente**, validade, link do portal emissor (federal,
  estadual, trabalhista e FGTS fixos; municipal do cadastro do fornecedor — "Cadastre o
  endereço do portal municipal no fornecedor") e botão de copiar o CNPJ. Emissão é manual
  (portais com CAPTCHA).
- Anexar (modal, PDF): confere que o texto é de certidão, que é **do tipo pedido** ("Este
  PDF parece ser a certidão X, não a Y." / "Este PDF não parece ser a certidão Y.") e **do
  CNPJ do fornecedor** (14 dígitos ou raiz de 8) ("Esta certidão não é de X: o CNPJ … não
  aparece nela."), e lê a validade ("Válida até", "Validade: … a …" usa o fim, ou emissão +
  "válida por N dias"). PDF só imagem: vale a data informada ("O PDF é uma imagem: não deu
  para conferir o conteúdo; vale a data informada."), sem data: "Não deu para ler este PDF
  (parece uma imagem). Anexe de novo informando até quando ele é válido."; sem validade: "Não
  achei a validade nesta certidão. Anexe de novo informando até quando ela é válida."
  Sucesso: "Certidão X de Y conferida e anexada — válida até|vencida em dd/mm/aaaa." (aviso
  se vencida). Toda mensagem de erro prefixada "Certidão X: ".

## 7. Entregas e ocorrências (`models.py:828-879`, `services.py:1155-1221`, `forms.py:606-622`)

- Registrar a partir do dia do evento (legado sem data também), não em cancelada: "A entrega
  se registra a partir do dia do evento."
- Campos: o que aconteceu (Entregue sem ocorrência [padrão], Atraso na entrega, Falta de
  itens, Problema de qualidade, Não entregue, Outra ocorrência), avaliação 1–5 (opcional),
  quem recebeu, observação (**obrigatória quando há ocorrência**: "Descreva a ocorrência: é a
  base de uma notificação ao fornecedor."), foto ou documento (PDF/PNG/JPG), quem e quando.
- Vários registros por OS. Histórico "Entrega registrada: <tipo>; avaliação N/5; recebido
  por X. <obs>". Sucesso "Entrega registrada: <tipo>.". Modal na lista ou página própria.
- Resumo por fornecedor/contrato: OS com entrega registrada, nota média, ocorrências por tipo.

## 8. Lotes, painel, relatório e virada

### 8.1 Lista de lotes (`views.py:369-443`) e detalhe (`views.py:453-493`)
Busca (fornecedor, contrato, municípios), exercício, situação (Todas/Ativos/Inativos),
trilha por exercício com total, ordenação (lote, fornecedor, contrato, exercício,
capacidade, restante). Linha: "Lote N · FORNECEDOR", selo Ativo/Inativo, selo de consumo,
exercício, contrato, "R de T unidades", municípios. Botão "Abrir exercício N+1" (admin).
Detalhe: capacidade e contrato (capacidade, consumidas, restante, %, fornecedor, CNPJ,
contato, e-mail, contrato, empenho e valores comprometido/pago/saldo do empenho, fiscal),
municípios e orientações, solicitações do lote na linha padrão.

### 8.2 Painel (`views.py:253-362`, `templates/pages/coffee_break/painel.html`)
- Indicadores: **Capacidade contratada** (Σ lotes ativos; "N lotes ativos"), **Unidades
  consumidas** ("N% da capacidade" / "Sem lotes ativos"), **Saldo restante**, **Gasto em
  AAAA** ("R$ X com ordem bancária"), **Pendências financeiras** (não canceladas e não
  concluídas; destaque; leva a `?pendentes=1`).
- **Alerta de saldo** por lote ativo (`services.py:250-334`): ritmo = média mensal dos
  últimos **3 meses completos** (mês do evento, ou do pedido); se há ritmo e fim de
  vigência e o saldo acaba antes: "No ritmo dos últimos 3 meses (12,3 por mês), os R de saldo
  acabam por volta de dd/mm/aaaa, antes do fim do contrato (dd/mm/aaaa): providencie o
  aditivo ou o reforço." Sem como projetar: restante ≤ **15%** → "Restam apenas R de T
  unidades (limite de alerta: 15%)." Projeção: acaba_em = hoje + restante/ritmo × 30,44
  dias; sobra no fim = restante − ritmo × meses até o fim. Ex.: restante 300, ritmo 100/mês,
  fim em 120 dias → acaba em ~91 dias (antes) → alerta; sobra = 300 − 100 × 3,94 ≈ −94.
- **Vigência** (`services.py:481-521`): contratos com lote ativo que vencem em até 90 dias
  (faixas 30/60/90) ou já venceram: "A vigência termina em dd/mm/aaaa (em N dias, faixa de F
  dias). Providencie o aditivo de prorrogação." / "Vigência encerrada em dd/mm/aaaa. Novas
  solicitações com evento depois dessa data não são aceitas neste contrato."
- **Certidões**: por fornecedor com lote ativo, as não vigentes, com botão "Renovar".
- **O que fazer hoje** (`services.py:1224-1370`): grupos na ordem do fluxo, cada um com
  contagem, ajuda e botão que resolve:
  | Grupo | Critério | Botão |
  |---|---|---|
  | Entregas desta semana | sem nota, evento entre hoje e +7 dias | "Abrir a OS" (ou "Enviar a OS" se pronta e não enviada) |
  | Eventos realizados sem nota fiscal | fim do evento < hoje, sem nota | "Anexar a nota" |
  | Notas sem ofício | com nota, sem nº de ofício | "Gerar o ofício" |
  | Ofícios sem protocolo | nota + ofício, sem protocolo | "Informar o protocolo" |
  | Protocolos sem ordem bancária | protocolo, sem OB | "Registrar a OB" / "Anexar a OB" (com atesto) |
  | Ordens bancárias não enviadas à empresa | OB, sem envio | "Enviar a OB" |
  Entregas ordenadas por data/horário (com horário, local, quem recebe, fornecedor); os
  demais pelo maior tempo parado ("Parada hoje" / "Parada há N dias"; "a mais antiga parada
  há N dias"). Dias parada = desde o último histórico (ou criação), ou desde o fim do evento
  se posterior. Vazio: "Nada pendente com a equipe: nenhuma entrega nos próximos dias e
  nenhum pagamento parado."
- Lotes ativos e 5 solicitações recentes na linha padrão; "Importar processo de pagamento".

### 8.3 Relatório do contrato (`coffee_break/relatorio_contrato.py:30-164`, `views.py:568-603`)
Tela, PDF e CSV (`;`, BOM, vírgula decimal): consumo por mês (OS, quantidade, valor, barra
relativa), por município, lotes (exercício, vigente, capacidade, consumido, restante,
empenho, valor do empenho), capacidade e saldo dos vigentes, ritmo (3 meses), quando o saldo
acaba e sobra/falta no fim da vigência, gasto, pago, empenhado, saldo do empenho, prazo médio
nota→OB (emissão da nota, ou data do ofício, até a OB) e o resumo das entregas. Conta OS não
canceladas no mês do evento (ou do pedido).

### 8.4 Virada de exercício (admin — `coffee_break/virada.py`, `views.py:496-565`)
"Abrir exercício N+1" copia os lotes **ativos** do maior exercício: por lote, marcar criar,
quantidade (padrão a atual; obrigatória se marcado: "Informe a quantidade do novo
exercício."), empenho e valor do empenho; opção de encerrar os lotes de origem. Copia
municípios, texto original, orientações e especificações; observação "Aberto na virada do
exercício a partir do Lote N (AAAA).". Impedimentos: "O Lote N (AAAA) deste contrato já
existe." / "Contrato vencido em dd/mm/aaaa: providencie o aditivo de prorrogação antes.";
aviso "O contrato vai até dd/mm/aaaa: o lote de AAAA só cobre eventos até lá.". Mensagens:
"Não há lotes vigentes para copiar."; "Marque ao menos um lote para abrir o exercício.";
"Corrija as linhas destacadas."; sucesso "Exercício N aberto: K lotes criados com os
municípios, orientações e especificações de N−1. [Os lotes de N−1 copiados foram encerrados.]"

## 9. Lista de solicitações e exportação (`views.py:610-781`, `presenters.py`)

- Busca (evento, nº, nota fiscal, protocolo), lote, fornecedor, eventos de/até (data do
  evento), situação financeira (trilha lateral com contagem de cada situação sobre o recorte
  do banco), `pendentes=1`. Ordenação: nº, lote, descrição, data, evento, quantidade; padrão
  data da solicitação desc. 25 por página.
- Linha: "<nº> · <evento>", selo da situação financeira, selo temporal (Previsto /
  Acontecendo / Realizado), "Parada há N dias" (≥ 7 dias, só quando depende da equipe),
  fatos (data do evento, quantidade, lote, nota fiscal, "Solicitada em").
- Menu ⋮ (`templates/pages/coffee_break/_acoes_linha.html`): Abrir (editável) / consultar;
  Duplicar; Enviar OS ao fornecedor ("Enviada em …" / "Por e-mail, com cópia para a ASCOM");
  Registrar entrega (a partir do evento); Andamento; Baixar arquivos; Certificado em PDF;
  Importar processo de pagamento; Cancelar; Excluir ("Só antes da nota e do protocolo").
- Área de soltar o PDF do processo de pagamento ("O sistema descobre a solicitação pelo
  ofício, pelo protocolo e pelas notas.").
- **CSV** "coffee-break-AAAA-MM-DD.csv" do recorte atual (`;`, BOM, decimais com vírgula), 21
  colunas: Nº, Lote, Fornecedor, Data da solicitação, Evento, Período, Local de entrega,
  Endereço, Bairro, CEP, Quantidade, Quantidade faturada, Valor unitário, Valor, Nota fiscal,
  Protocolo, Atesto GAF, Ordem bancária, Envio à empresa, Situação, Criado por.

## 10. Comunicação com o fornecedor

### 10.1 E-mails (`coffee_break/emails.py`, `views.py:2180-2317`)
Tela de e-mail pronta e editável (para = e-mail do fornecedor; cópia = e-mail da ASCOM da
configuração; assunto e texto com os campos substituídos; campo desconhecido fica
`{campo}`; "a combinar" quando falta data/horário/local/responsável). Pendências impedem o
envio ("Ainda não dá para enviar."). Confirmação "Enviar este e-mail ao fornecedor agora?".
Erros: "E-mail inválido: x"; "Informe o e-mail do fornecedor."; "Informe o assunto do
e-mail."; servidor: "O e-mail não foi enviado: o servidor de e-mail recusou ou não respondeu
(…). Tente de novo." Histórico (ação E-mail) com quando, para, cópia, assunto e anexos.
- **Enviar a OS**: anexa a OS em PDF; grava "OS enviada ao fornecedor em"; "OS N enviada ao
  fornecedor por e-mail. O envio ficou no histórico."; aviso se já enviada.
- **Enviar a OB**: exige PDF da OB e data da OB; anexa o comprovante; registra o envio à
  empresa (último marco) em todas as OS do pagamento: "Ordem bancária enviada ao fornecedor.
  O pagamento foi concluído [em todas as OS dele]."

### 10.2 Link seguro do fornecedor (`coffee_break/link_fornecedor.py`, `coffee_break/views_publicas.py`)
- Etapa 2, "Enviar link ao fornecedor": a mesma tela de e-mail com `{link}`; o link **nasce
  só no envio confirmado** (token aleatório só no e-mail; banco guarda SHA-256), revoga o
  anterior da OS, vale 30 dias (configurável) e pode ser revogado ("Link do fornecedor
  revogado: ele deixa de funcionar agora."). Não disponível em cancelada/concluída.
- Página pública (sem login, sem cache): número da OS, evento, data, valor, fornecedor,
  validade do link, situação da nota ("Aguardando envio" / "Recebida, aguardando
  conferência" / "Já anexada pela ASCOM") e das certidões ("Válida até …", "Vencida em … —
  envie a renovada", "Não enviada"). Nenhum dado de servidor. Token inexistente, expirado ou
  revogado → mesma página "Link indisponível" (404); limites por IP de tokens inválidos (20/h)
  e de envios por link e por IP (30/h) → 429.
- Envio da nota: PDF validado e conferido como no §4.1 (avisos guardados); envio da
  certidão: conferida como no §6 e **precisa estar válida** ("Esta certidão venceu em …. Envie
  a certidão renovada."). Novo envio do mesmo tipo substitui o não conferido. Fica
  "Recebido, aguardando conferência", entra no histórico (ação Envio do fornecedor) e avisa
  no sino quem gerou o link e quem criou a OS.
- Conferência pela equipe: **Aceitar** (a nota entra na OS pelo mesmo caminho do anexo; a
  certidão entra no cadastro do fornecedor) ou **Recusar** com motivo ("… recusada. O
  fornecedor pode enviar de novo pelo link."). "Este envio já foi conferido."

## 11. Integrações internas

- **Origem do pedido** (`coffee_break/origem.py`): botão "Pedir coffee break" na
  solicitação de evento (Eventos Sociais) e na palestra/evento da ASCOM, só para quem tem o
  módulo (`templates/pages/coffee_break/_pedir_coffee_break.html`). Abre a nova solicitação
  com município, data, horário, descrição ("<tipo> – <local> – <município>" / "<evento> –
  <temas> – <município>"), local, quem recebe (solicitante + contato), quantidade (público da
  palestra) e endereço. Só vale origem que a pessoa pode ver. A OS mostra de onde veio e
  avisa remarcação: "O evento foi remarcado para dd/mm/aaaa, e a OS está com dd/mm/aaaa.
  Confira a data e avise o fornecedor."
- **Agenda** (`agenda/fontes.py:335-375`, `agenda/prazos.py:211-310`, `agenda/criar.py:36-40`,
  `agenda/detalhes.py:581-611`): fonte "Coffee break" ("<descrição> (N)", Ativa/Cancelada,
  detalhes evento/local/endereço/quantidade); prazos "Fim da vigência — Contrato/Termo
  aditivo …" e "Certidão X vence — <fornecedor>" (só a vigente de cada tipo); "Novo coffee
  break" no "criar aqui".
- **Página inicial** (`core/views.py:55-91`): Saldo dos lotes, Pendências financeiras,
  Lotes em alerta.
- **Relatórios consolidados** (`relatorios/consolidacao.py:353-382`): por mês do evento —
  solicitações, quantidade servida, canceladas, valor (não canceladas).
- **Busca de endereço** já usado (`core/buscar_endereco.py:171`) e **"Preencher com um
  e-mail"** (`views.py:1137-1152`, `coffee_break/preenchimento.py`, `leitura_pedido.py`): lê
  o e-mail do pedido e sugere data, município do PR, evento, quantidade ("2 turmas de 25",
  por extenso), data, horário, local, endereço, quem recebe; avisa falta de lote/saldo
  ("O Lote K (…), que atende X, tem saldo de N unidade(s) e o pedido é de M: a solicitação
  não poderá ser salva com essa quantidade.") e período de vários dias ("…a OS tem uma data
  só: preenchi o primeiro dia. Para os outros dias, registre uma solicitação por dia."). Não
  sugere o nº da OS. Mostra solicitações já criadas do mesmo e-mail.
- **Auditoria**: modelos do app auditados (`auditoria/signals.py:22`, `42`) — aqui, trigger.

## 12. Importações

- **Importar processo de pagamento** (`coffee_break/importacao_processo.py:1-50`,
  `importacao_views.py`): solta o PDF inteiro do processo do eProtocolo (da lista, do painel,
  da etapa 3 ou do ⋮). Lê capa, ofício, notas, certificos, certidões, aditivo, contrato,
  despacho ao GAF; identifica a(s) solicitação(ões) por nº do processo, PCPR do ofício,
  nº/ano do ofício e nº das notas (mesmo fornecedor); aplica sozinho se a identificação for
  segura, senão abre conferência. Aplica: anexa a nota recortada a quem não tem, grava o
  protocolo de pagamento (= nº do processo), atesto (= data do despacho), espelha no
  conjunto, registra certidões mais novas. Nunca sobrescreve o digitado (vira pendência);
  reconhece o mesmo arquivo pelo hash ("Este mesmo arquivo já foi importado em …"). Não guarda
  o texto do processo (LGPD). Limite de tamanho; "Envie o PDF do processo, como o eProtocolo
  gera (Processo_….pdf)."
- **Importar planilha** "CONTROLE COFFE ASCOM.xlsx" (admin; `views.py:1773-1846`, comando
  `importar_coffee_break`): simular → importar, idempotente; .xlsx até 20 MB ("Escolha a
  planilha em .xlsx." / "A planilha passa de 20 MB." / "Envie a planilha e simule de novo
  antes de importar."); trata números de OS que o Excel virou data, períodos livres ("23, 24
  e 25/03"), linhas "CANCELADO"/quantidade zero como canceladas, aba de ordens bancárias.
  Fornecedores, contratos e abas→lotes estão fixos no código (dados reais; não transcritos).

## 13. Seeds / carga inicial

- Referência: só o módulo e o setor ASCOM por migração; o resto pela planilha. Configuração
  do ofício nasce com os padrões (alguns com nomes reais — trocar por neutros/vazios).
- Aqui (DEMO, `gestao/coffee/demonstracao.py` ou equivalente): 2–3 fornecedores fictícios
  com CNPJ válido de teste, contratos (um vigente, um vencendo em < 60 dias, um com aditivo),
  lotes de dois exercícios com municípios do PR (um com saldo < 15%), ~25 solicitações em
  todas as situações financeiras (incluindo canceladas, concluída, em correção, pagamento
  conjunto, retroativa, faturada ≠ pedida), certidões vigentes/vencendo/vencidas/faltando,
  entregas com e sem ocorrência, um link do fornecedor com envio pendente. O usuário demo
  com o papel do módulo e administrador.

---

## Plano de entrega aqui

Ordem de dependência; cada fatia testável sozinha (unidade + navegador + a11y + 360–1440 px
+ dados no DEMO). Premissas: app novo `gestao/coffee` (contexto próprio, `services.py`,
`policies.py`, regras puras em `dominio/`), auditoria por trigger, movimentos de negócio
como histórico.

- **CB1 — Acesso e cadastros.** Papel/módulo do Coffee Break e "administrador do módulo";
  Fornecedor, Contrato, Termo aditivo (manual), Lote (municípios, exercício, empenho),
  Configuração do ofício (registro único, valores neutros); exclusão protegida; trava de
  versão; DEMO dos cadastros.
- **CB2 — Solicitação (etapa 1) e lista.** Escolha do lote pelo município (exato → mais
  próximo por coordenadas; preferências por vigência/exercício/saldo) como regra pura; saldo
  com trava; valor unitário congelado; vigência, retroativo, antecedência; sugestão de
  locais; duplicar; cancelar/reativar/excluir; histórico; lista com situação derivada,
  filtros, trilha, selos, "parada há N dias"; CSV. Numeração da OS **provisoriamente**
  própria do módulo, atrás de uma interface (ver dúvida 1).
- **CB3 — Fluxo financeiro.** Etapas 2 e 3 (campos, ordem dos marcos com as mensagens,
  quantidade faturada e saldo), andamento do próximo marco (modal), stepper, bloqueio de
  concluída/cancelada, reabrir/encerrar correção (admin) com diff no histórico, registrar o
  protocolo manual (00.000.000-0), pagamento conjunto com espelhamento.
- **CB4 — Documentos.** OS, ofício e certifico (motor de PDF de Viagens, prévia HTML,
  pendências), vias emitidas e assinadas, certificado da solicitação, textos do eProtocolo,
  anexo do protocolo (lista ordenada, quatro arquivos, PDF único/ZIP) e atesto ao baixar.
  Edição na folha e textos-base por admin numa subfatia **CB4b** se o editor daqui
  suportar.
- **CB5 — Certidões e leitura de PDFs.** Quadro e alertas de certidões, anexar com
  conferência (tipo, CNPJ, validade lida); leitura da nota (número/valor/emissão/CNPJ) com os
  avisos; leitura da OB e avisos; contrato/aditivo lido do PDF (admin). Testes com PDFs
  sintéticos gerados no próprio teste.
- **CB6 — Entregas, painel, relatório e virada.** Entregas e ocorrências; painel (KPIs,
  alerta de saldo com projeção, vigência 30/60/90, certidões, "O que fazer hoje"); relatório
  do contrato (tela, PDF, CSV); virada de exercício.
- **CB7 — Integrações internas.** "Pedir coffee break" a partir de Eventos Sociais e
  Palestras (ganchos, sem import cruzado), aviso de remarcação; agenda (fonte, prazos,
  criar aqui) e conflitos se couber; página inicial, relatórios consolidados, busca global.
- **CB8 — Fornecedor.** E-mails da OS e da OB (tela editável, histórico, outbox) e link
  seguro com a página pública (token com hash, validade, revogação, limites, conferência
  aceitar/recusar, aviso no sino).
- **CB9 — Importações (opcional).** "Preencher com e-mail"; importar processo de pagamento
  do eProtocolo; importar planilha só se a carga histórica não for pelo ETL da virada.

## CB1 — o que foi feito (05/10/2026)

- App `gestao/coffee` (contexto próprio; contrato do import-linter: só cadastros de base;
  regras puras em `dominio.py`). Papel `ASCOM_COFFEE_BREAK` (acessar o módulo e ver os
  cadastros); o administrador do módulo é esse papel + `ADMINISTRADOR` (que ganha
  add/change/delete dos cadastros do Coffee Break).
- Cadastros numa tela (`/coffee/cadastros/<tabela>/`): aba por tabela com o total, busca
  (CNPJ com ou sem pontuação), lista e novo/editar na janela (`?novo=1`, `?editar=`), trava de
  versão, exclusão protegida com a mensagem da referência:
  - Fornecedor: razão social única (sem caixa), CNPJ 14 dígitos único quando preenchido, nome
    curto derivado para os documentos, contato, e-mail, portal da certidão municipal.
  - Contrato: número único, GMS, aditivo em vigor, vigência (com "estimada"), quantidade,
    valor unitário (4 casas, vírgula), valor total, antecedência mínima (padrão 2), fiscal,
    cargo e cláusula (padrões da referência), PDF conferido pelo conteúdo (baixado só pela
    view autorizada), objeto. Selo Vigente/Vencido pela vigência efetiva (maior fim entre o
    contrato e os aditivos).
  - Termo aditivo: número único por contrato, vigência, PDF.
  - Lote: contrato, número, exercício, quantidade ≥ 1, empenho e valor, vigente/encerrado,
    municípios do Paraná digitados como lista (validados; o texto original fica guardado),
    orientações, especificações; único por contrato/número/exercício.
  - Ofício e protocolo (registro único, valores neutros sem nomes de pessoas): vocativo,
    assinante, destinatário, destino do despacho, assunto e palavras-chave do protocolo,
    e-mails da ASCOM em cópia (validados), assunto e texto dos e-mails da OS e da OB.
- Auditoria por trigger em todas as tabelas; DEMO com dois fornecedores, três contratos
  (vigente, vencendo, com aditivo) e lotes de dois exercícios.
- Fora da CB1: anexar contrato/aditivo lendo o PDF (CB5); a regra "capacidade não abaixo do
  consumido" (precisa das solicitações, CB2); textos-base dos documentos (CB4).

## CB2 — o que foi feito (05/10/2026)

- `Solicitacao` (a OS) e `Movimento` (`gestao/coffee/models_pedido.py`), auditados; regras
  puras em `dominio_pedido.py` (escolha do lote, valor, situação, vigência, retroativo,
  antecedência, número), leituras em `queries.py`, escritas em `pedidos.py`.
- Lote pelo município: os ativos que o listam (não vencido na data → exercício do ano →
  maior saldo); senão a cidade listada mais perto em linha reta (coordenadas do cadastro de
  municípios), com "Cidade, a N km"; nenhum: a mensagem da referência. Registro existente só
  troca de lote quando o município muda; o valor unitário é congelado na criação ou na troca.
- Saldo = Σ quantidade efetiva (faturada, senão pedida) das não canceladas; conferido com a
  linha do lote travada ("Quantidade acima do saldo do lote: restam R de T unidades.");
  cancelar devolve, reativar revalida. Vigência (só pedido novo ou mudança de município/
  data), retroativo com justificativa no histórico, aviso de antecedência (não bloqueia).
- Nº da OS "NN/AAAA" (sequência digitada, em branco = próxima; repetido recusado com a
  próxima livre) — **numeração própria do módulo por ora**; a conjunta com Viagens depende
  de decisão do usuário.
- Folha (padrão das folhas): placa "OS", frase-resumo (situação, selo temporal, data,
  município, pessoas, lote, valor), 1 Evento e pedido com o lote consultado ao digitar o
  município (htmx), 2 Entrega, 3 Situação (cancelar com motivo, reativar, excluir só antes da
  nota/protocolo) e histórico; duplicar (sem datas, número ou pagamento); travas: financeiro
  iniciado bloqueia os dados do pedido; cancelada/concluída só consulta; trava de versão.
- Lista com a trilha da situação financeira (derivada, contagens sobre o recorte), busca,
  lote, fornecedor, eventos de/até; CSV com as 21 colunas da referência. Lotes com "R de T
  unidades" e o selo de consumo (< 70 / ≥ 70 / ≥ 90%).
- DEMO: 18 solicitações em todas as situações. O Coffee Break saiu da lista "Próximos
  módulos" da página inicial.
- Revisão de segurança (CB1+CB2) aplicada: o PDF trocado sai do disco (o nome antigo é lido
  antes da validação), trava de versão conferida de novo sob a trava da linha (cadastros e
  solicitação; com financeiro iniciado, os campos travados vêm da linha travada), número
  em branco tenta de novo quando outro pedido acabou de usar o número, permissão por tabela
  nos cadastros, capacidade do lote não abaixo do consumido, CSV em fluxo, nome do PDF
  baixado saneado, só erros de validação viram mensagem no trecho do lote.
- Fora da CB2: etapas 2 e 3 (nota, ofício, protocolo, OB) e reabrir para correção (CB3);
  "parada há N dias" (CB6); sugestão de locais já usados; "criar aqui" da agenda (CB7).

## CB3a — fluxo financeiro (06/10/2026)

- Etapas 2 e 3 na folha (gravadas juntas, `financeiro.py`): nº da nota fiscal, pessoas
  faturadas (o saldo do lote passa a descontar o faturado, com o texto da referência no
  histórico e o saldo revalidado), nº e data do ofício (com a nota: em branco = próximo /
  hoje; numeração própria do módulo até a decisão sobre o livro conjunto), "PCPR protocolo
  n.º", protocolo de pagamento no formato 00.000.000-0 (também vira o PCPR quando este está
  vazio), atesto, ordem bancária, envio à empresa, observações. A ordem dos marcos com as
  mensagens da referência; "a nota não pode ficar em branco" depois do protocolo.
- Andamento: grava só o próximo marco (nota → protocolo → atesto → OB → envio) com anotação,
  e o stepper das etapas (UI Lab §19) mostra o feito e o atual.
- Concluída (envio à empresa) fica só para consulta; o administrador do módulo reabre para
  correção (com motivo) — cada campo que mudar vira "Correção — rótulo: antes → depois." —
  e encerra a correção.
- Fora da CB3a (CB3b): pagamento conjunto (várias OS num ofício e num protocolo, campos
  espelhados); PDFs da nota e da OB e a leitura deles (CB4/CB5).

## CB3b — pagamento conjunto (06/10/2026)

- Várias OS do mesmo lote num só ofício e num só protocolo (`conjunto.py`): a principal e as
  que apontam para ela (`pagamento_com`). Candidatas: mesmo lote, não canceladas, não
  concluídas, sem protocolo de pagamento e fora de outro grupo (mensagem da referência);
  marcar e desmarcar pela seção "Pagamento conjunto" da folha.
- Espelhados em todas, com "Copiado da OS N (pagamento conjunto) — campo: valor." no
  histórico: nº/data do ofício e PCPR protocolo; protocolo de pagamento, atesto, OB e envio
  só nas que já têm nota. O número do ofício é um só no grupo.
- Protocolo de pagamento e atesto só entram quando todas as OS do grupo têm a nota (texto do
  agente: "…só entra quando todas as OS têm a nota fiscal: falta a nota da OS N."). Com
  protocolo, o grupo não muda.
- Cancelar ou excluir a principal: a próxima pelo número assume; as outras recebem "A OS N
  foi cancelada|excluída e saiu do pagamento conjunto."
- Fora: o ofício com um item por OS e as notas no plural (CB4, documentos).

## CB4 — documentos (06/10/2026)

- `documentos.py`: ordem de serviço (cidade e data por extenso, fornecedor, contrato pela
  referência documental, empenho, objeto, detalhamento "Solicito coffee para: Dia dd/mm às
  hh p/ N pessoas.", local com endereço, responsável, assinatura do fiscal), ofício ao GAF
  (um por pagamento: um item por OS com a quantidade por extenso e as notas no plural,
  cláusula e contrato, assinante e destinatário da configuração), certifico digital (nota,
  empresa, CNPJ, contrato e o ATESTO) e o certificado da solicitação (espelho: pedido, lote/
  contrato/fornecedor, marcos ou "Pendente", faixa de cancelada, ressalva). Pendências que
  bloqueiam com as mensagens da referência; PDF pelo WeasyPrint ("Ver" em tela com o nonce
  da CSP, "PDF" para baixar) e nome "<prefixo> <nº> - Lote <n> - <fornecedor>.pdf".
- Vias (`vias.py`, modelo `Via`, auditado): cada PDF que sai fica guardado; a mesma folha
  (comparada pelo HTML — o PDF leva a data da geração) não gera outra via; o certificado,
  espelho do momento, não se guarda. Versão assinada (PDF conferido) vale no lugar do gerado
  até ser removida (fica guardada); recusada em cancelada/concluída.
- Prévia em tela: a CSP (`style-src 'self'`) recusa estilo embutido, então na tela vale
  `static/css/impresso.css` (só tokens) e o estilo embutido fica só para o PDF. O mesmo
  defeito existia na tela imprimível da pauta da agenda (A2b: aparecia sem estilo, com erro
  de CSP no console) e foi corrigido do mesmo jeito.
- Diferenças: timbre em texto (sem o brasão em imagem) e sem editar o texto na folha nem os
  textos-base por administrador (o editor de documentos daqui é o de Viagens; fica para uma
  CB4b se for preciso). Fora: anexo do protocolo (lista ordenada, quatro arquivos, PDF
  único/ZIP, atesto ao baixar) e textos do eProtocolo para copiar — dependem das certidões e
  dos PDFs da nota (CB5).

## CB5a — certidões (06/10/2026)

- `Certidao` (auditada) com o histórico; a vigente de cada tipo é a de maior validade.
  Regras puras em `dominio_certidoes.py`; leitura do texto do PDF pelo pypdf (`certidoes.py`).
- Tela "Certidões": por fornecedor com lote ativo, uma linha por tipo (federal, estadual,
  municipal, trabalhista, FGTS) com a situação (faltando, vencida, vencendo em até 15 dias,
  vigente), a validade, o portal emissor (fixos; o municipal vem do cadastro do fornecedor,
  ou o aviso "Cadastre o endereço do portal municipal no fornecedor") e Anexar/Renovar.
- Anexar confere o PDF (bytes), o texto de certidão, o tipo pelas marcas do texto, o CNPJ
  (inteiro ou a raiz) e lê a validade ("Válida até …", intervalo "… a …" vale o fim,
  emissão + "válida por N dias"); PDF só de imagem vale a data informada; mensagens da
  referência prefixadas "Certidão X: ". Aviso quando vencida.
- DEMO com certidões em todas as situações. Fora (próximas fatias): leitura dos PDFs da
  nota e da OB, contrato/aditivo lido do PDF, anexo do protocolo (CB5b/CB5c); alertas no
  painel (CB6); envio pelo fornecedor (CB8).

## CB5b — PDFs da nota fiscal e da ordem bancária (06/10/2026)

- Campos `nota_pdf`, `nota_valor`, `nota_emissao`, `nota_cnpj`, `ob_pdf`, `ob_numero`,
  `ob_valor`; leitura pura em `dominio_leitura.py`, escrita em `pdfs.py`.
- Nota: o número vem da chave de acesso (modelo 55/65, posições 26–34), do "Nº 000.008.957"
  do DANFE ou dos rótulos da NFS-e; o CNPJ do emitente da chave (na NFS-e, o do prestador);
  valor total e emissão pelos rótulos. Sugere o número quando o campo está vazio; mensagens
  da referência ("Nota fiscal N anexada — o número foi lido do PDF." / "…não deu para ler o
  número…"). Conferência que só avisa: CNPJ de outro emitente, valor ≠ pessoas × unitário,
  emitida antes do evento, mesma nota do mesmo fornecedor em outra OS.
- Ordem bancária: exige a nota; número ("2026OB012345"), data e valor lidos; vale para todas
  as OS do pagamento (mesmo arquivo; sai do disco quando ninguém mais aponta); sendo o
  próximo marco, a data lida entra (ou hoje; anterior ao atesto, hoje) e é espelhada; sem
  atesto, "registre o atesto para a data da OB entrar"; aviso quando o valor não bate com as
  notas (retenções explicam).
- Fora: contrato/aditivo lido do PDF (CB5d, administrador) e o anexo do protocolo (CB5c).

## CB5c — protocolo de pagamento (06/10/2026)

- Tela "Montar o protocolo" (`/coffee/solicitacoes/<pk>/protocolo/`, a partir da etapa 3):
  1 passo a passo (o protocolo é aberto à mão — o eProtocolo alcançado é de treinamento);
  2 textos para copiar (interessado, assunto, palavras-chave, detalhamento "ENVIO P/
  PAGAMENTO DA NOTA FISCAL N … - (NOME CURTO)" no singular/plural, Nº/Ano do ofício, assunto
  e texto do despacho) com o componente novo "Copiar" (UI Lab §20, `copiar.js`, carregado
  só pela tela); 3 a lista do anexo na ordem da referência (ofício; nota e certifico de cada
  OS do pagamento; certidões FGTS, trabalhista, municipal, estadual, federal; termos
  aditivos do mais antigo ao mais novo; contrato), cada item pronto, com aviso (certidão
  vencida entra) ou dizendo o que falta, com "Resolver"; 4 os quatro arquivos (ordens de
  serviço; ofício; notas e certificos intercalados; contrato, aditivos e certidões) em um PDF
  cada (ZIP) ou tudo num PDF só (pypdf); o que falta fica de fora; mensagens da referência.
- Baixar registra o "atesto e envio ao GAF" (uma vez; exige o protocolo; não em cancelada),
  espelhado no pagamento conjunto e no histórico.
- Fora: contrato/aditivo lido do PDF (CB5d) e a importação do processo do eProtocolo (CB9).

## CB6a — entregas e painel (06/10/2026)

- **Entregas e ocorrências** (`entregas.py`, modelo `Entrega`, auditado): seção
  "Recebimento e ocorrências" na folha da OS (estado na frase-resumo) a partir do dia do evento (sem data também; não em cancelada), com o que aconteceu, a
  avaliação 1–5, quem recebeu, a observação (obrigatória com ocorrência — mensagem da
  referência) e uma foto ou PDF (extensão conferida pelo conteúdo, até 10 MB; baixa só para
  quem tem o módulo). Vários registros por OS; histórico "Entrega registrada: <tipo>;
  avaliação N/5; recebido por X. <obs>"; recusado, o que foi digitado volta. A lista de
  fornecedores mostra o resumo ("N entregas registradas · nota média 4,5 · 2 ocorrências").
  OS com entrega não se exclui (cancela-se).
- **Painel** (`/coffee/painel/`, a entrada do módulo; `painel.py` + `dominio_painel.py`
  puro): saldo restante, consumidas, gasto do ano (com a parte já com OB), pendências
  financeiras (→ `?pendentes=1`); alerta de saldo pela projeção dos 3 meses completos (a
  mesma conta da referência — inclusive o limite de 15% sem como projetar e o saldo zerado
  "acabando" hoje), vigência (30/60/90 e encerrada), certidões não vigentes com "Renovar",
  "O que fazer hoje" nos seis grupos da referência (entregas por data/horário; os demais pelo
  tempo parado; 5 por grupo e "Mostrar mais"; cada botão leva à seção da folha onde a ação
  acontece — ver decisoes.md), solicitações recentes e lotes ativos.
- **Lista**: "Parada há N dias" (≥ 7, só quando a OS depende da equipe; desde o último
  histórico, ou desde o evento se posterior). Linha da OS virou o parcial `_registro.html`.
- DEMO: histórico datado do pedido (há OS paradas) e quatro entregas (duas com ocorrência).
- Fora: "Enviar a OS" (CB8), relatório do contrato e virada (CB6b), "Importar processo de
  pagamento" (CB9).

## Integrações externas e dependências sem credencial

- **SMTP institucional** para os e-mails ao fornecedor (OS, OB, link): sem ele, enviar só
  para o backend de arquivo/console no PREVIEW (envio real fica pendente).
- **eProtocolo (Celepar)**: a referência **não** integra de verdade (ambiente de
  treinamento/mock; protocolo aberto à mão — `coffee_break/protocolo_pagamento.py:1-26`).
  Abrir o protocolo e anexar os arquivos automaticamente exige credenciais e o endpoint de
  documentos, que nem a referência tem.
- **Portais de certidão** (Receita, Sefa-PR, prefeituras, TST, Caixa): CAPTCHA — só links;
  emissão manual.
- **Página pública do fornecedor**: precisa de URL pública acessível fora da rede e de
  decisão de segurança (rota sem login, limites, antivírus de upload se houver).
- **Runtime do WeasyPrint** (GTK/Pango) no servidor para os PDFs.
- **Planilha "CONTROLE COFFE ASCOM.xlsx" e PDFs reais** (notas, OB, contratos, processos):
  necessários para validar as heurísticas de leitura e para a carga histórica; contêm dados
  pessoais e de empresas — só com autorização.
- **Coordenadas dos municípios**: o cadastro daqui já tem latitude/longitude; conferir se
  estão preenchidas para o "lote mais próximo".

## Pontos de dúvida (para decisões.md)

1. **Numeração conjunta com Viagens** (OS e ofício no mesmo livro anual): manter a regra da
   referência (o roadmap já marca como decisão pendente) ou numeração própria do Coffee
   Break? Afeta as lacunas e a trava de `gestao/viagens`.
2. **Perfis**: a referência usa "módulo por setor (ASCOM) + grupo ADMINISTRADOR". Mapear para
   os papéis daqui (ex.: operador do Coffee Break × administrador do módulo).
3. **Excluir solicitação** é exclusão física antes da nota/protocolo; aceitar ou trocar por
   arquivamento?
4. **Evento de um dia só**: a tela descarta o fim do período; manter fim/período em texto só
   para legado?
5. **Editar cadastro pela folha do documento** (admin) e "textos-base" — depende do editor de
   documentos daqui.
6. **Leitura de PDFs** (nota, OB, contrato, certidão, processo): heurísticas presas a
   formatos específicos (DANFE/NFS-e, SIAF, contratos da SESP); entregar como "sugestão com
   confirmação" e não como verdade?
7. **Link público do fornecedor**: confirmar se a instituição aceita rota sem login.
8. **Carga histórica**: pela planilha (como a referência) ou pelo ETL do sistema antigo?
9. **Valores padrão da configuração** com nomes de pessoas: definir os neutros e quem
   preenche em produção.
