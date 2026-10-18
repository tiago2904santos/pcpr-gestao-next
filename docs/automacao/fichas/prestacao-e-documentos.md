# Fichas — prestação de contas e documentos (AUT-36 a AUT-63)

> **Escopo revisado em 18/10/2026:** [regra vigente do piloto](../../product/automacao-whatsapp-testes.md). Este site é um sistema
> de testes independente, não oficial da polícia e sem operação com policiais. WhatsApp Business
> Cloud API é o canal principal planejado; portal é apoio e e-mail opcional. As classificações e
> restrições policiais de 17/10 abaixo são histórico do cenário institucional, sem bloquear
> automaticamente o piloto. Não houve implementação ou ativação real nesta revisão.

Fase 2 da missão de automação · 17/10/2026. Fichas implementáveis das 28 oportunidades do grupo
"prestação e documentos" da [matriz](../matriz-oportunidades.md) (seção 5.3). Base obrigatória:
[arquitetura](../arquitetura.md), [envelope de evento](../contratos/evento-integracao.schema.json),
[API de automação](../contratos/api-automacao.v1.yaml) e [plano de implantação](../plano-implantacao.md).
Fluxos já desenhados, que as fichas **resumem e apontam** em vez de repetir:
[10-3 prestação e aviso de saque](../fluxos/10-3-prestacao-e-mensagem-de-saque.md),
[10-4 link de km na véspera](../fluxos/10-4-link-de-km-na-vespera.md),
[10-5 DB e RT para assinatura](../fluxos/10-5-db-e-rt-para-assinatura.md) e
[10-6 recebimento de documentos](../fluxos/10-6-recebimento-de-documentos.md).

> Em uma frase: a prestação já existe no sistema novo e é toda manual nas bordas. O que dá para fazer
> **agora**, sem n8n nem provedor, são regras do próprio sistema (texto do aviso, km, conferência de
> assinatura, comprovante, carimbo, feriados, RT sem afirmação falsa). O que depende do n8n é transporte
> por **e-mail institucional** (aviso, lembretes, link de km, DB/RT para assinar), e isso espera SMTP e
> contato verificado dos servidores. A plataforma oficial do WhatsApp está **bloqueada** pela política da
> Meta (maturidade 5), mas o WhatsApp é prioridade do usuário: o aviso de liberação, o link de km e os
> lembretes também saem pelo WhatsApp assistido com registro (WA-1, AUT-172, maturidade 2), e a integração
> oficial fica pronta e desligada (WA-3, AUT-174) enquanto a consulta à Meta (WA-2, AUT-173) não muda o
> quadro. IA entra só
> como rascunho ou sugestão, e ainda depende de decisão sobre provedor. Assinar, finalizar e decidir
> continuam humanos.

Repositório público: nenhuma credencial, endereço interno ou detalhe de segurança da infraestrutura aparece
aqui. Credenciais (SMTP, caixa postal, provedor de IA) ficam só em variáveis de ambiente.

---

## 1. Como ler

**Situação de cada capacidade** (sempre declarada no cabeçalho da ficha):

| Marca | Significado |
|---|---|
| **EXISTENTE** | O código do sistema novo executa hoje. Evidência `caminho:linha` conferida em 17/10/2026 na árvore de trabalho, que tinha alterações não commitadas: os números de linha podem mudar |
| **VERIFICADA PARCIALMENTE** | Existe em parte ou com lacuna conhecida, **ou** o mecanismo só foi exercitado no protótipo local (PCPR e canal simulados) |
| **PLANEJADA** | Só desenho: fluxo, contrato, ADR proposta ou esta ficha |

Evidências `gestao/…`, `static/…`, `deploy/…` e `config/…` são relativas à raiz do repositório. `ref/gv/…` e
`ref/ev-implantado/…` são cópias **somente leitura** das referências em produção, usadas só para entender o
processo; nada delas é copiado.

**Campos de toda ficha, nesta ordem:** identificador · módulo e processo · evidência · problema que resolve ·
pessoas beneficiadas · gatilho · pré-condições · etapas · responsabilidade (sistema / n8n / IA) · dados e
permissões · APIs existentes e necessárias · participação humana · resultado esperado · falhas e
recuperação · deduplicação · cancelamento · métricas · custos · dependências · prioridade e esforço ·
cenários de aceite · desligamento e continuação manual · maturidade.

Quando o fluxo já detalha um campo, a ficha diz o essencial em poucas linhas e aponta a seção
(ex.: "10-3 §9"). Os padrões repetidos em várias fichas estão na seção 3 (**B1 a B9**) e são citados pelo código.

**Classificação** (lista fixa da matriz): automação indicada com n8n · assistência por IA indicada · automação
determinística suficiente · melhor execução pelo próprio sistema · dependente de desenvolvimento ·
dependente de integração externa · inadequada ou inviável atualmente.

**Maturidade:** 1 viável com recursos existentes · 2 depende de desenvolvimento no sistema · 3 depende de
provedor, credencial ou custo · 4 depende de integração institucional · 5 bloqueada ou não recomendada
atualmente. Vale o nível da matriz; onde esta ficha encontrou motivo para divergir, a divergência está
registrada na seção 8 e não muda o número da matriz.

**Prioridade e esforço:** valor (alto/médio/baixo) e esforço (P/M/G) da matriz; "etapa" é a do
[plano](../plano-implantacao.md) e "ordem" é a posição na lista da matriz (seção 9). "Trilha paralela" (P*n*)
são melhorias do sistema que não dependem de n8n, IA nem da fundação.

---

## 2. Visão do grupo

| ID | Assunto | Classificação | Mat. | Valor | Esf. | Etapa · ordem | Situação hoje | Detalhe |
|---|---|---|---:|---|---|---|---|---|
| [AUT-36](#aut-36) | Aviso de liberação: texto e situação como regra testada, com registro | automação determinística suficiente | 2 | alto | M | 2 · 20 | VERIFICADA PARCIALMENTE (só link `wa.me` sem regra nem registro) | 10-3 |
| [AUT-37](#aut-37) | Envio automático do aviso por e-mail institucional | automação indicada com n8n | 3 | alto | M | 2 · 26 | PLANEJADA | 10-3 |
| [AUT-38](#aut-38) | Lembretes ao servidor até o comprovante entrar | automação indicada com n8n | 3 | alto | P | 2 · 27 | VERIFICADA PARCIALMENTE (só sino interno) | 10-3 |
| [AUT-39](#aut-39) | Resumo diário de pendências e semanal de prestações paradas | automação indicada com n8n | 3 | médio | P | 2 · 31 | VERIFICADA PARCIALMENTE (abas e planilha) | esta ficha |
| [AUT-40](#aut-40) | Link de km por trecho (página offline, token em hash) | dependente de desenvolvimento | 2 | alto | G | 3 · 44 | PLANEJADA (só na referência EV) | 10-4 |
| [AUT-41](#aut-41) | Envio do link de km na véspera e lembretes | automação indicada com n8n | 3 | alto | P | 3 · 46 | PLANEJADA | 10-4 |
| [AUT-42](#aut-42) | Km inicial sugerido pelo último km da viatura | automação determinística suficiente | 2 | médio | P | P18 | VERIFICADA PARCIALMENTE (consulta existe, só informativa) | esta ficha |
| [AUT-43](#aut-43) | Horários realizados sugeridos pelos lançamentos do link | automação determinística suficiente | 2 | médio | P | 3 · 50 | PLANEJADA | esta ficha |
| [AUT-44](#aut-44) | Continuidade do km e prontidão do DB | automação determinística suficiente | 2 | médio | P | 3 · 51 | VERIFICADA PARCIALMENTE (avisos existem; salto e km máximo não) | esta ficha + 10-4/10-5 |
| [AUT-45](#aut-45) | DB com motorista de outro ofício: signatário e direcionamento | automação determinística suficiente | 2 | médio | P | P19 | VERIFICADA PARCIALMENTE (signatário certo; direcionamento não) | esta ficha |
| [AUT-46](#aut-46) | DB e RT prontos para assinatura, versão congelada | melhor execução pelo próprio sistema | 2 | alto | M | 3 · 52 | PLANEJADA (gerados na hora, sem versão) | 10-5 |
| [AUT-47](#aut-47) | DB e RT ao signatário pelo portal, aviso e lembrete por e-mail | automação indicada com n8n | 3 | alto | M | 3 · 53 | PLANEJADA | 10-5 |
| [AUT-48](#aut-48) | Relato do servidor por link | dependente de desenvolvimento | 2 | médio | M | 3 · 55 | PLANEJADA | 10-5 |
| [AUT-49](#aut-49) | RT sem afirmações não verificadas por padrão | automação determinística suficiente | 2 | médio | P | P20 | EXISTENTE com defeito (frase fixa "Não houve intercorrências…") | esta ficha |
| [AUT-50](#aut-50) | Rascunho do RT por IA ancorado em dados | assistência por IA indicada | 3 | médio | M | 4 · 66 | PLANEJADA | 10-5 |
| [AUT-51](#aut-51) | Feriados estaduais e municipais nos dias úteis | automação determinística suficiente | 2 | baixo | P | P41 | VERIFICADA PARCIALMENTE (nacionais existem) | esta ficha |
| [AUT-52](#aut-52) | Recebimento de devolvidos pelo portal e pela importação | dependente de desenvolvimento | 2 | alto | M | 3 · 48 | VERIFICADA PARCIALMENTE (importação existe; entrada do servidor não) | 10-6 |
| [AUT-53](#aut-53) | Conferência de assinatura em DB, RT e plano, no original | automação determinística suficiente | 2 | alto | M | 3 · 42 | VERIFICADA PARCIALMENTE (só ofício, justificativa, termo, OS) | esta ficha + 10-5/10-6 |
| [AUT-54](#aut-54) | Guardar o texto/OCR de cada parte importada | automação determinística suficiente | 2 | médio | P | P2 | PLANEJADA (o OCR roda e o texto é descartado) | esta ficha |
| [AUT-55](#aut-55) | Comprovante: valor, data e operação na entrada; casar pela janela de saque | automação determinística suficiente | 2 | médio | P | 3 · 54 | VERIFICADA PARCIALMENTE (leitura manual com clique) | esta ficha |
| [AUT-56](#aut-56) | Carimbo do nº da solicitação posicionado pela linha do servidor | automação determinística suficiente | 2 | médio | P | P21 | VERIFICADA PARCIALMENTE (posição manual) | esta ficha |
| [AUT-57](#aut-57) | IA só como sugestão de tipo/destino na revisão da importação | assistência por IA indicada | 3 | baixo | M | 4 · 75 | PLANEJADA | esta ficha |
| [AUT-58](#aut-58) | IA extraindo campos de comprovante/NFS-e de layout desconhecido | assistência por IA indicada | 3 | baixo | M | 4 · 76 | PLANEJADA | esta ficha |
| [AUT-59](#aut-59) | Assinatura eletrônica simples feita pelo próprio sistema | inadequada ou inviável atualmente | 5 | médio | — | — | só na referência GV | 10-5 |
| [AUT-60](#aut-60) | Finalização automática da prestação | inadequada ou inviável atualmente | 5 | baixo | — | — | — | esta ficha |
| [AUT-61](#aut-61) | IA decidindo o destino de documentos importados | inadequada ou inviável atualmente | 5 | baixo | — | — | — | 10-6 |
| [AUT-62](#aut-62) | Km lido por foto do hodômetro | inadequada ou inviável atualmente | 5 | baixo | — | — | — | 10-4 |
| [AUT-63](#aut-63) | IA no carimbo do nº da solicitação | inadequada ou inviável atualmente | 5 | baixo | — | — | — | esta ficha |

**Totais do grupo.** Classificação: 11 automação determinística suficiente, 5 automação indicada com n8n,
3 assistência por IA indicada, 3 dependente de desenvolvimento, 1 melhor execução pelo próprio sistema,
5 inadequada ou inviável atualmente. Maturidade: 15 em 2, 8 em 3, 5 em 5. Situação hoje:
1 EXISTENTE com defeito, 11 VERIFICADAS PARCIALMENTE, 11 PLANEJADAS, 5 sem implantação recomendada.

"Pacote e envio ao financeiro" não tem item próprio neste grupo: ver a seção 5.

---

## 3. Base comum (citada nas fichas como B1 a B9)

**B1 — Fundação [PLANEJADA].** `Comunicacao` (AUT-01), `ContatoVerificado` e vínculo com o servidor
(AUT-02), `LinkAcesso` e portal mínimo do servidor (AUT-03), catálogo de eventos (AUT-100), worker de
entregas com lease (AUT-101), API `/api/automacao/v1` com token de serviço, escopos, `Idempotency-Key` e
`/estado` (AUT-104), ferramentas de leitura (AUT-105), fila de exceções `ExcecaoAutomacao` e tela de saúde
da outbox (AUT-103). Nada disso existe em código; os contratos estão escritos. O mecanismo comum (reserva,
idempotência, 409/423, reconciliação, reinício do n8n, exceção sem laço) passou nos 12 cenários do
[protótipo local](../prototipo/) na execução final de 17/10/2026, 03:53–03:59, horário de Brasília
(`n8nio/n8n:2.43.7`, SQLite, PCPR e canal simulados; resultados e métricas em
[`prototipo/README.md`](../prototipo/README.md) e `prototipo/resultados/resultados.json`): **VERIFICADA
PARCIALMENTE como mecanismo**, não no sistema nem na VPS.

**B2 — Transporte de uma comunicação pelo n8n** (padrão dos fluxos 10-3 a 10-5). O PCPR cria a
`Comunicacao` com `enviar_em` na mesma transação da mudança de negócio e publica `comunicacao.agendada`. O
worker de entregas leva o evento ao webhook do n8n (HMAC). O n8n chama `POST /comunicacoes/{id}/reservar`,
e o PCPR revalida tudo **no momento do envio** (versão, cancelamento, destinatário, contato verificado,
chave ligada): 409 ou 423 encerram sem envio. Com a reserva, o n8n envia o e-mail com o texto montado pelo
PCPR e devolve `POST /comunicacoes/{id}/resultado`; devoluções (bounce) chegam por
`POST /comunicacoes/{id}/entrega`. A consulta `GET /comunicacoes/devidas` a cada 15 min recupera o que um
evento perdido deixou. No n8n são 3 tentativas curtas; depois, exceção `canal_indisponivel`. Resultado
desconhecido (canal caiu no meio) vira exceção para uma pessoa conferir, **sem reenvio às cegas**
([arquitetura](../arquitetura.md) §3).

**B3 — Deduplicação em camadas.** (1) chave de idempotência da outbox; (2) `id` estável do evento, que o
n8n descarta se já viu; (3) reserva com `Idempotency-Key` **única por tentativa**
(`reserva:<comunicacao>:v<versao>:exec<id>`, com o id da execução do n8n); a exclusividade vem da transição
`agendada → enviando`, em que só uma vence (com a chave estável, uma segunda execução receberia a resposta
repetida, com o mesmo token de reserva, e enviaria de novo — achado do protótipo); os demais POSTs usam
chave estável e a repetição volta com `Idempotency-Replayed: true`; (4) unicidade de negócio da
comunicação (tipo, alvo, versão ou marco); (5) "enviar agora" na tela usa a mesma reserva, então pessoa e
n8n não enviam os dois.

**B4 — Desligamento.** Chave geral e chave por fluxo no PCPR (`GET /estado`). Desligada: as escritas da API
respondem 423, o PCPR **continua planejando**, as comunicações ficam agendadas ou aguardando envio manual,
e o n8n pode ser parado sem perda. Ao religar, só sai o que ainda for devido.

**B5 — Continuação manual.** Toda comunicação tem na tela "enviar agora pelo PCPR", "copiar mensagem",
"marcar como enviado por outro meio" (com o meio e quem marcou) e "cancelar". O sino interno continua como
hoje. Nenhuma tarefa depende do n8n para ser feita.

**B6 — Canal.** O canal automático é o **e-mail institucional**. Hoje o sistema só manda e-mail a usuários
internos, desligado por padrão e no console sem `EMAIL_HOST` (`gestao/plataforma/notificacoes.py:54-60`,
`config/settings/base.py:266-279`), e num único envio com todos os destinatários no "Para"
(`notificacoes.py:79-80`, AUT-05). SMTP institucional e remetente autorizado: AUT-04 (maturidade 3, não
confirmado). **WhatsApp: bloqueado** (AUT-10, maturidade 5). A política oficial lista autoridades policiais
entre os usuários proibidos do WhatsApp Business Platform, sem exceção nem processo de aprovação
(<https://whatsappbusiness.com/policy/>, seção de uso governamental, atualizada em 23/09/2026, consultada em
17/10/2026), e provedores como a 360dialog também recusam polícia
(<https://docs.360dialog.com/docs/resources/government-agencies>, consultada em 17/10/2026). Não há
integração WhatsApp ativa em produção; os sistemas usam links `wa.me` abertos à mão pelo operador. O
usuário definiu o WhatsApp como **prioridade** (17/10/2026), nas frentes do [plano](../plano-implantacao.md):
WA-1, envio assistido com registro (AUT-172, maturidade 2: texto mínimo da função de domínio, `wa.me` no
aparelho institucional e registro "enviado por WhatsApp manual"); WA-2, consulta formal à Meta (AUT-173, 4);
WA-3, integração oficial pronta e desligada (AUT-174, 5 para ativar). Falta a decisão D4a do plano
(aparelho e número institucionais), que responde o resto da D16 do 10-3.

**B7 — Dados pessoais.** Servidores viajantes **não são usuários** do sistema novo: `Servidor` tem só
telefone (único) e nenhum e-mail, e o vínculo usuário↔servidor não existe em modelo
(`gestao/cadastros/models.py:86-128`, `gestao/identidade/models.py:25-31`). Todo aviso ao servidor depende
de AUT-02, e toda entrega ou devolução de documento depende de AUT-03. Eventos não levam dados pessoais nem
documentos: o n8n obtém endereço e texto só na reserva. Textos nunca trazem CPF, dados bancários ou telefone.
Os workflows do n8n que carregam mensagem ou arquivo não guardam execução nenhuma, nem de erro: o destino e
o link (que é credencial) ficariam retidos numa falha de SMTP; o diagnóstico sai só com metadados pelo
workflow de erro (regra RC-9 de [comunicação e viagens](comunicacao-e-viagens.md)).

**B8 — Custos comuns.** O n8n cabe na VPS atual sem custo adicional de hospedagem, em modo normal
[medido e estimativa, [desempenho e custos](../desempenho-e-custos.md) §1 e §9]. E-mail institucional: sem
custo direto **se** a conta institucional existir, o que não está confirmado. O limite do Google Workspace é
de 2.000 mensagens por dia por usuário
(<https://knowledge.workspace.google.com/admin/gmail/gmail-sending-limits-in-google-workspace?hl=en>,
consultada em 17/10/2026), mas não se sabe se a PCPR está entre os órgãos do Workspace do Estado
(<https://www.parana.pr.gov.br/aen/Noticia/Governo-do-Estado-amplia-uso-do-Google-Workspace-e-ativa-60-mil-contas-corporativas>,
01/12/2025, consultada em 17/10/2026). O custo real é o desenvolvimento da fundação (etapa 1, G) e o tempo
de quem trata exceções (hipótese H9: 5 % das comunicações, 10 min cada). Volumes por viagem são hipóteses
(H1–H8 do [desempenho e custos](../desempenho-e-custos.md) §3: 50/200/500 viagens por mês, 4 servidores por
viagem, 80 % com viatura).

**B9 — Tramitação oficial.** O Decreto estadual 7.304/2021 define o eProtocolo como sistema oficial de gestão
de documentos e veda sistemas paralelos de controle e tramitação
([texto](https://www.administracao.pr.gov.br/sites/default/arquivos_restritos/files/documento/2021-04/decreto_7304_-_2021_-_eprotocolo_-_com_anexos_0.pdf),
consultado em 17/10/2026). **Ponto a confirmar com a instituição:** as fichas que distribuem ou recebem
documentos (AUT-47, AUT-52, AUT-53 e a seção 5) **complementam** a tramitação oficial — entregam cópia,
avisam, recebem de volta para conferência — e não a substituem. A assinatura digital de ofícios é feita no
eProtocolo (decisão registrada no GV); juntada e tramitação ficam no eProtocolo (AUT-122).

**O que continua humano em todo o grupo:** registrar a liberação das diárias (dado de fonte externa),
assinar, finalizar, enviar ao financeiro, aprovar ou devolver prestação, aceitar sugestão de IA, aceitar
devolução de versão vencida.

---

## 4. Fichas

### 4.1 Aviso de liberação ("mensagem de saque"), lembretes e resumos

<a id="aut-36"></a>
#### AUT-36 — Aviso de liberação de diárias: texto e situação como regra testada, com registro

> **Automação determinística suficiente · maturidade 2 · valor alto · esforço M · etapa 2, ordem 20.**
> Situação: VERIFICADA PARCIALMENTE — EXISTENTE só o link `wa.me` montado na view, sem regra, sem registro e
> sem teste. Detalhe: [10-3](../fluxos/10-3-prestacao-e-mensagem-de-saque.md) §2.2, §3.1–3.3, §7, §13 (partes A1 e A2).

- **Identificador:** AUT-36 (origens O049, O287).
- **Módulo e processo:** Viagens › Prestação de contas › aviso de liberação das diárias ao servidor
  (`PREST-MENSAGEM-SAQUE`, `GV-PREST-AVISO-DIARIAS`).
- **Evidência:** `gestao/viagens/views_prestacao.py:176-191` (`_whatsapp` monta `https://wa.me/55<telefone>?text=…`;
  só tira o que não é dígito, não exige nº nem prazo, não impede liberação futura);
  `gestao/viagens/templates/viagens/prestacao/_cartao.html:97`; registro humano da liberação em
  `gestao/viagens/prestacao.py:268-284` (`salvar_solicitacao`; `liberou_agora` em `:276`); sino interno em
  `:436-442`. Nenhum teste cobre o texto (10-3 §2.2). Referência GV: validação só no navegador
  (`ref/gv/static/js/pages/prestacoes-diaria-wa.js:25-30`, `:43-68`).
- **Problema que resolve:** o texto muda conforme quem envia, o link aparece antes da hora (liberação
  futura, prazo vazio) e ninguém sabe quem foi avisado. Sem uma regra única não há como automatizar (AUT-37)
  nem responder pelo assistente.
- **Pessoas beneficiadas:** operador de viagens (não monta texto e vê a situação no cartão); servidor (dados
  certos); gestão e auditoria (registro de quem foi avisado, quando e por qual meio).
- **Gatilho:** `prestacao.salvar_solicitacao` (único gatilho, sempre humano) e todo serviço que muda uma
  condição da regra: finalizar, arquivar, sincronizar a equipe, reabrir, retificar ou cancelar o ofício
  (10-3 §3.1–3.2).
- **Pré-condições:** texto institucional aprovado (decisão D1 do 10-3) e decisão sobre trazer ou não o valor
  (D2: o valor de `diaria_liberada` é **calculado**, não o liberado de fato, `prestacao.py:109-124`). Para o
  registro: `Comunicacao` (AUT-01).
- **Etapas:** (1) função pura `situacao_do_aviso` em `gestao/viagens/dominio/aviso_liberacao.py`
  [novo], com os estados `devido`, `agendar`, `aguardando_dados` e `bloqueado` e as 7 condições do 10-3 §3.2;
  (2) `mensagem_liberacao` e `impressao` (SHA-256 só dos campos informados por pessoa) com renderizadores
  para e-mail e para copiar (10-3 §3.3); (3) `_whatsapp` e "Copiar" passam a usar a função, com a regra do
  GV (liberação ≤ hoje, 11 dígitos) no caminho manual; (4) com AUT-01, `planejar_aviso` na mesma transação
  cria ou atualiza a `Comunicacao(tipo=mensagem_saque)` e o cartão mostra a situação; (5) ações manuais
  (B5), "cancelar" e "enviar retificação".
- **Responsabilidade:** *sistema* — regra, texto, estado, registro e ações; *n8n* — nada nesta ficha (o
  transporte é AUT-37); *IA* — nenhuma: o texto é modelo aprovado. O assistente só lê a situação por
  ferramenta de leitura (10-3, critério 17).
- **Dados e permissões:** lê nº da solicitação, liberação e prazo (`PrestacaoServidor`), nº do ofício,
  destinos e período, primeiro nome e unidade. Nunca CPF, dados bancários ou telefone no texto. Policies:
  `prestacoes_visiveis` (`gestao/viagens/policies.py:585-594`) e `pode_comunicar_servidor` [novo] (10-3 §7.3).
- **APIs existentes e necessárias:** existente — o serviço `salvar_solicitacao`. Necessária — nenhuma API
  externa; opcionalmente a ferramenta de leitura `prestacao.aviso_liberacao` (AUT-105) para o assistente.
- **Participação humana:** registrar nº, liberação e prazo; aprovar o texto (gestor); enviar à mão enquanto
  AUT-37 não existir; decidir retificação depois de envio.
- **Resultado esperado:** o cartão mostra "Aviso: falta o nº / agendado para dd/mm / enviado por <meio> em
  dd/mm por <pessoa>"; o texto é o mesmo em qualquer meio; a regra tem teste de domínio.
- **Falhas e recuperação:** o autosave grava campo a campo (`views_prestacao.py:335-343`), então liberação
  sem prazo fica `aguardando_dados` e não cria comunicação; liberação futura fica `agendar`; prazo de saque
  vencido fica `bloqueado` e vira pendência do operador (D7); correção depois do envio mostra "enviado com
  dados anteriores" e pede retificação humana (10-3 §9).
- **Deduplicação:** uma `mensagem_saque` vigente por `PrestacaoServidor` (unicidade parcial); mesma
  `impressao` de um envio anterior → nada a fazer (10-3 §10).
- **Cancelamento:** na transação de finalizar, arquivar, remover da equipe ou cancelar o ofício →
  `cancelada` com motivo; ofício reaberto → `suspensa` até nova emissão.
- **Métricas:** % de liberações registradas com aviso registrado (qualquer meio); mediana entre liberação e
  aviso registrado; avisos "enviados com dados anteriores" ÷ enviados (qualidade da digitação).
- **Custos:** só desenvolvimento (A1 P, A2 M). Operação sem custo.
- **Dependências:** AUT-01 para o registro; decisões D1 e D2 do 10-3. A parte A1 (função e testes) não
  depende da fundação e pode entrar já.
- **Prioridade e esforço:** alta; M.
- **Cenários de aceite:** 10-3 §12, critérios 3, 4, 5, 16 e 18. Além deles:
  1. **Dado** liberação amanhã, **quando** o operador abre o menu do servidor, **então** o link `wa.me` não
     é oferecido e "Copiar" informa "aviso disponível a partir de dd/mm".
  2. **Dado** telefone com 10 dígitos, **quando** o aviso fica devido, **então** nenhum link `wa.me` é
     gerado e "Copiar" continua disponível.
  3. **Dado** o mesmo nº, liberação e prazo salvos duas vezes, **quando** `planejar_aviso` roda, **então**
     continua existindo uma única comunicação vigente.
- **Desligamento e continuação manual:** é regra interna e não tem chave; o que se desliga é o envio
  automático (chave `saque-aviso`, AUT-37). A continuação manual é o próprio cartão (B5).
- **Maturidade:** **2**.

<a id="aut-37"></a>
#### AUT-37 — Envio automático do aviso de liberação pelo canal institucional

> **Automação indicada com n8n · maturidade 3 · valor alto · esforço M · etapa 2, ordem 26.**
> Situação: PLANEJADA (mecanismo de transporte VERIFICADO PARCIALMENTE no protótipo simulado, B1).
> Detalhe: [10-3](../fluxos/10-3-prestacao-e-mensagem-de-saque.md) §4.2, §4.4, §6, §8–§10 e §13 (B1, B2).

- **Identificador:** AUT-37 (origens O050, O137, O288, O323, O047).
- **Módulo e processo:** Prestação › aviso de liberação (`PREST-MENSAGEM-SAQUE`, `PREST-SOLICITACAO-LIBERACAO`,
  `PLAT-ROTINAS-DIARIAS`, `GV-PREST-AVISO-DIARIAS`, `EV-MENSAGEM-LIBERACAO`).
- **Evidência:** não existe envio: o único caminho é o `wa.me` manual (`gestao/viagens/views_prestacao.py:176-191`);
  a outbox só tem os tópicos `viagens.documento.gerar`, `viagens.oficio.emitido` e `plataforma.email.enviar`
  (`gestao/plataforma/outbox.py`); e-mail só para usuários internos (B6); `Servidor` sem e-mail (B7).
- **Problema que resolve:** o operador precisa lembrar de avisar cada servidor, um por vez, pelo próprio
  aparelho; o prazo de saque é curto e o atraso prejudica o servidor.
- **Pessoas beneficiadas:** servidor (aviso no dia, pelo canal institucional); operador (não envia);
  gestão (registro de envio e entrega).
- **Gatilho:** `Comunicacao` `mensagem_saque` criada por AUT-36 com `enviar_em` alcançado. Propostas do 10-3
  §8: carência de 15 min depois do registro; liberação futura às 08:00; janela 08:00–20:00 todos os dias
  (decisões D3 e D4).
- **Pré-condições:** situação `devido` (AUT-36); contato verificado com e-mail (AUT-02); SMTP institucional
  (AUT-04); entrega pelo n8n (AUT-06); chave `saque-aviso` ligada.
- **Etapas:** B2 com o texto de `mensagem_liberacao`; o cartão passa de "agendado" a "enviado" ou
  "falhou"; devolução (bounce) reabre a verificação do contato (10-3 §4.4).
- **Responsabilidade:** *sistema* — se é devido, quando, para quem, texto, revalidação na reserva, estado e
  exceções; *n8n* — transporte por e-mail, 3 tentativas curtas, resultado, devoluções e alerta; *IA* — nenhuma.
- **Dados e permissões:** evento sem dado pessoal; endereço e texto só na reserva, com token de serviço de
  escopo mínimo (B7). O texto nunca traz CPF.
- **APIs existentes e necessárias:** nenhuma existe. Necessárias: `/estado`, `/comunicacoes/devidas`,
  `/comunicacoes/{id}/reservar`, `/resultado`, `/entrega`, `/excecoes`
  ([contrato](../contratos/api-automacao.v1.yaml)); eventos `comunicacao.agendada` e
  `comunicacao.cancelada`; `outbox.publicar(disponivel_em)` e demais extensões do 10-3 §6.3.
- **Participação humana:** o registro da liberação é o único gatilho; a pessoa resolve exceções e pode
  "enviar agora" ou "marcar por outro meio" a qualquer momento.
- **Resultado esperado:** cada servidor com contato verificado recebe um aviso, uma vez, no dia da
  liberação; o cartão mostra quando e para qual endereço.
- **Falhas e recuperação:** tabela do 10-3 §9 — evento duplicado, PCPR ou SMTP fora, webhook do n8n fora
  (a outbox desiste em cerca de 21 min; a consulta `devidas` recupera), reinício do n8n (resultado
  desconhecido vira exceção), devolução do e-mail, servidor sem contato (`sem_canal` com exceção
  `destinatario_sem_contato`).
- **Deduplicação:** B3; 10-3 §10.
- **Cancelamento:** só o PCPR cancela, na transação da mudança de negócio; o n8n fica sabendo por
  `comunicacao.cancelada` ou pelo 409 na reserva. Aviso já enviado e ofício cancelado: exceção para uma
  pessoa decidir o que comunicar (D10).
- **Métricas:** 10-3 §11 — latência p95 ≤ 20 min após `enviar_em`; falha < 2 %; duplicidade 0; % em
  `sem_canal` (cobertura de contato); mediana entre liberação e comprovante anexado, antes e depois.
- **Custos:** cerca de 4 e-mails por viagem (H2) → ~200, ~800 e ~2.000 por mês nos cenários de 50, 200 e
  500 viagens [estimativa], bem abaixo do limite diário citado em B8. Custo monetário adicional R$ 0
  [estimativa, [desempenho e custos](../desempenho-e-custos.md) §15.2]. Desenvolvimento M sobre a fundação
  (o workflow em si é P).
- **Dependências:** AUT-36, AUT-02, AUT-04, AUT-06 (e, por elas, AUT-01, AUT-100, AUT-101, AUT-104).
- **Prioridade e esforço:** alta; M.
- **Cenários de aceite:** 10-3 §12, critérios 1, 2, 6 a 11 e 15. Os essenciais:
  1. **Dado** servidor com contato verificado e liberação = hoje, **quando** o operador salva, **então** há
     uma comunicação agendada para agora + carência e um único `comunicacao.agendada` na outbox.
  2. **Dado** o mesmo evento entregue duas vezes, **quando** o n8n processa, **então** sai uma mensagem só.
  3. **Dado** a chave `saque-aviso` desligada, **quando** o n8n tenta reservar, **então** recebe 423 e o
     operador consegue "enviar agora pelo PCPR" ou "marcar por outro meio".
- **Desligamento e continuação manual:** chave `saque-aviso` (B4); continuação manual B5. O renderizador
  para WhatsApp serve só ao envio assistido da WA-1 (AUT-172), aberto pelo operador; envio automático por
  WhatsApp só depois do portão de ativação da WA-3 (AUT-174).
- **Maturidade:** **3** (SMTP institucional e e-mail verificado dos servidores). WhatsApp assistido com
  registro: 2 (AUT-172); plataforma oficial: 5 (AUT-10).

<a id="aut-38"></a>
#### AUT-38 — Lembretes ao servidor: saque vencendo, prestação vencida e o que entregar depois do retorno

> **Automação indicada com n8n · maturidade 3 · valor alto · esforço P · etapa 2, ordem 27.**
> Situação: VERIFICADA PARCIALMENTE — EXISTENTE o cálculo dos prazos e os avisos **só para operadores** no
> sino. Detalhe: [10-3](../fluxos/10-3-prestacao-e-mensagem-de-saque.md) §3.4, §3.5 (E2), §4.3, §4.5, §8.

- **Identificador:** AUT-38 (origens O051, O322, O276).
- **Módulo e processo:** Prestação › prazos (`PREST-AVISOS-PRAZOS`, `EV-AVISOS-PRESTACAO`, `GV-PREST-ABERTURA`).
- **Evidência:** rotina `avisar_prazos` em `gestao/viagens/avisos.py:47-87` (saque vencendo ou vencido sem
  comprovante, prestação vencida, documentos gerados e recebidos) e `avisar_chegadas` em `:90-114`, só para
  o sino da equipe; prazos em `gestao/viagens/dominio/prestacao.py:17-18` e `:85-130` (`DIAS_AVISO_SAQUE = 3`,
  prazo para prestar = saque + 3 dias úteis, selo do saque); rotina diária em
  `gestao/plataforma/rotinas.py:30-61` e `deploy/systemd/pcpr-rotinas@.timer:5` (05:40 no fuso do host).
  Divergência conhecida: a aba "Saque vencendo" (`prestacao.filtrar`, `gestao/viagens/prestacao.py:190-230`)
  lista também quem já tem comprovante (10-3 §2.4, item 1).
- **Problema que resolve:** o operador lê o sino e cobra cada servidor por fora; quem precisa sacar ou
  prestar contas não recebe nada direto.
- **Pessoas beneficiadas:** servidor (lembrete enquanto falta o comprovante); operador (menos cobrança).
- **Gatilho:** a rotina diária existente **planeja** os marcos do dia; o envio sai no horário proposto
  (09:00 BRT, decisão D5) por B2. Marcos do 10-3 §3.4: `saque_d3`, `saque_hoje`, `saque_vencido` (uma vez);
  `prestacao_vencida` fica só interna, salvo decisão D6. **Marco pós-retorno [proposta desta ficha]:** no
  dia útil seguinte à chegada, uma lista do que **o próprio servidor** ainda deve entregar, tirada de
  `prestacao.pendencias(ps)` (`prestacao.py:127-156`) e limitada às pendências que dependem dele
  (comprovante; RT ou DB assinado quando AUT-47 estiver ativo). Sem prazo inventado: só "a viagem terminou
  em dd/mm; falta X" (decisão D-PR1, seção 7).
- **Pré-condições:** infraestrutura de AUT-37; comprovante ativo consultável (`AnexoPrestacao` tipo
  `comprovante`, `removido_em` nulo); chave `saque-lembretes` ligada.
- **Etapas:** (1) função pura `marco_do_saque(prazo, hoje, …)` com as regras do selo existente; (2) a rotina
  cria `Comunicacao(tipo=lembrete_pendencia, marco=saque_d<N>|saque_hoje|saque_vencido)` (nomes do contrato
  rascunho 3) com chave de negócio (marco, prazo); (3) B2; (4) E2 do 10-3 §3.5:
  comprovante anexado, finalização, arquivamento ou remoção cancelam os lembretes **na mesma transação**;
  (5) com recebimento do servidor aguardando conferência (AUT-52), os lembretes ficam adiados; (6) alinhar a
  aba "Saque vencendo" ao selo e à rotina.
- **Responsabilidade:** *sistema* — quais marcos valem, texto, cancelamento e adiamento; *n8n* — transporte
  (B2); *IA* — nenhuma.
- **Dados e permissões:** como AUT-37; o texto cita ofício, prazo e o que falta, sem valores nem CPF.
- **APIs existentes e necessárias:** existentes — `avisos.avisar_prazos` e as funções de prazo do domínio.
  Necessárias — as mesmas de AUT-37.
- **Participação humana:** aprovar marcos e textos; resolver exceções; anexar o comprovante recebido
  (ou aceitar a importação).
- **Resultado esperado:** o servidor recebe no máximo um lembrete por marco; nada chega depois que o
  comprovante entra.
- **Falhas e recuperação:** marco planejado só no próprio dia e nunca enviado atrasado (reserva depois de
  23:59 → 409 e `obsoleta`); o fuso do host não afeta o envio, porque `enviar_em` é instante absoluto; demais
  casos como AUT-37.
- **Deduplicação:** chave de negócio única por (prestação do servidor, marco, prazo); B3. No mesmo dia de
  um aviso de liberação, nenhum lembrete (o aviso já traz o prazo).
- **Cancelamento:** E2 do 10-3 (comprovante, finalizar, arquivar, remover); prazo corrigido replaneja.
- **Métricas:** mediana de dias entre liberação e comprovante; contagem de saques vencidos sem comprovante
  e da aba "Prestação vencida", antes e depois; lembretes enviados depois de comprovante anexado (meta 0).
- **Custos:** ~1 lembrete por servidor (H5) → mesmo volume de AUT-37 [hipótese]; R$ 0 adicional
  [estimativa]; desenvolvimento P sobre AUT-37.
- **Dependências:** AUT-37 (e a fundação por ela); AUT-52 para o adiamento.
- **Prioridade e esforço:** alta; P.
- **Cenários de aceite:** 10-3 §12, critérios 12, 13, 14 e 18. Além deles:
  1. **Dado** viagem que terminou ontem e servidor sem comprovante, **quando** a rotina roda, **então** um
     único lembrete pós-retorno é agendado para o dia, listando só as pendências desse servidor e sem citar
     prazo que o sistema não tenha.
  2. **Dado** servidor que já tem comprovante, **quando** a aba "Saque vencendo" é aberta, **então** ele
     não aparece.
- **Desligamento e continuação manual:** chave `saque-lembretes`, independente de `saque-aviso` (B4); o sino
  interno continua avisando a equipe como hoje; B5.
- **Maturidade:** **3**.

<a id="aut-39"></a>
#### AUT-39 — Resumo diário de pendências por equipe e semanal de prestações paradas

> **Automação indicada com n8n · maturidade 3 · valor médio · esforço P · etapa 2, ordem 31.**
> Situação: VERIFICADA PARCIALMENTE — EXISTENTE o cálculo das pendências, as abas de cobrança e a planilha;
> não há resumo agregado nem entrega fora da tela. Sem fluxo próprio: esta ficha é o detalhe.

- **Identificador:** AUT-39 (origens O073, O289).
- **Módulo e processo:** Prestação › pendências e finalização (`PREST-PENDENCIAS-FINALIZACAO`,
  `GV-PREST-CONSOLIDADO`); leitura das abas (`PREST-LISTA-ABAS-EXPORT`).
- **Evidência:** `gestao/viagens/prestacao.py:127-156` (`pendencias(ps)`), `:190-230` (`filtrar`, abas de
  cobrança); `gestao/viagens/prestacao_equipe.py:148-160` (`conferencia` da equipe);
  `gestao/viagens/exportacao.py:133-162` (planilha); o sino diário avisa caso a caso
  (`gestao/viagens/avisos.py:47-87`), sem agregação. Não há leitura por API.
- **Problema que resolve:** para saber o que falta, o operador abre a lista e cada aba; a chefia não tem
  visão do acúmulo sem entrar no sistema.
- **Pessoas beneficiadas:** operadores de viagens de cada unidade (resumo diário); chefia ou gestor de
  viagens (resumo semanal).
- **Gatilho:** rotina do PCPR com horário próprio (AUT-109), America/Sao_Paulo. Proposta: diário às 08:00
  em dias úteis e semanal às segundas às 08:00 (decisão D-PR2). O desenho anterior (agenda do n8n chamando
  uma ferramenta) não cabe no contrato rascunho 3: o token de transporte não tem `ferramentas:*` e não há
  ação humana que emita delegação ([AUT-105](plataforma-e-modulos.md)).
- **Pré-condições:** ferramentas da fase A da ADR 0020 (AUT-105), que hoje é **proposta**
  (`docs/adr/0020-automacao-ferramentas-e-aprovacao.md:3`); entrega por e-mail (AUT-06) com um e-mail por
  destinatário (AUT-05). Os destinatários são **usuários internos**, que já têm e-mail institucional
  (`gestao/identidade/models.py:34`): este item não depende do contato dos servidores (AUT-02).
- **Etapas:** (1) a rotina chama o serviço interno `prestacao.preparar_resumo` [novo]; (2) o PCPR calcula, por unidade, com as **mesmas funções da tela** (`pendencias`,
  `filtrar`, `conferencia`), cria uma `Comunicacao(tipo=resumo_pendencias)` (tipo **proposto**, fora do
  `TipoComunicacao` do rascunho 3) por destinatário com a chave
  (destinatário, tipo, data) e devolve os ids; sem pendência, não cria; (3) B2 para cada comunicação;
  (4) no semanal, "prestação parada" = não finalizada, com pendência e sem atividade há N dias, medida pelo
  maior entre `PrestacaoServidor.atualizado_em` (`gestao/viagens/models.py:1469`), anexos novos e alterações
  do diário e do RT. N a decidir (proposta: 7 dias corridos). Atenção: `prestacao.enviar` usa `.update()`
  (`prestacao.py:386`) e não mexe em `atualizado_em`; a consulta precisa considerar `enviada_em`.
- **Responsabilidade:** *sistema* — horário, quem recebe (policies por unidade), o que é pendência, o
  texto, o registro; *n8n* — transportar e alertar se falhar; *IA* — nenhuma: é agregação determinística.
- **Dados e permissões:** nome do servidor, nº do ofício, tipo de pendência e link para a tela; sem CPF e
  sem valores. Recebe quem tem `pode_editar_equipe_prestacao` na unidade (`gestao/viagens/policies.py:624-626`);
  o semanal vai a quem a unidade indicar (decisão D-PR2). O resumo de cada destinatário é calculado com a
  política dele.
- **APIs existentes e necessárias:** existentes — só tela e XLSX. Necessárias — serviço interno de
  preparação, `/comunicacoes/*`, `/estado` (contrato v1).
- **Participação humana:** ler e agir na tela; o gestor define horários, destinatários e N.
- **Resultado esperado:** um e-mail por pessoa por dia útil com as prestações que dependem dela (nada quando
  não há pendência) e um semanal com as paradas, ambos com os mesmos números das abas.
- **Falhas e recuperação:** n8n fora no horário → o resumo do dia só vale até as 12:00 (proposta); depois a
  comunicação fica `obsoleta` e não sai atrasada; PCPR fora → 3 tentativas e alerta (AUT-111); SMTP fora →
  exceção `canal_indisponivel`; números diferentes da tela → teste de contrato compara com `filtrar`.
- **Deduplicação:** chave `resumo:<usuario>:<tipo>:<data>`; repetir a ferramenta no mesmo dia devolve as
  mesmas comunicações (B3).
- **Cancelamento:** sem pendência, nada é criado; usuário inativo ou sem lotação não recebe; o resumo não
  enviado até as 12:00 vira `obsoleta`.
- **Métricas:** prestações vencidas e paradas por unidade, antes e depois; tempo médio entre o surgimento de
  uma pendência e sua resolução; taxa de falha de envio; pedidos de descadastro.
- **Custos:** 1 e-mail por operador por dia útil (22 por mês, convenção H10) mais 4 semanais por
  destinatário de chefia [estimativa]; R$ 0 adicional; desenvolvimento P sobre AUT-105.
- **Dependências:** AUT-105, AUT-06 (e AUT-04, AUT-05).
- **Prioridade e esforço:** média; P.
- **Cenários de aceite:**
  1. **Dado** 3 prestações com pendência na unidade A e nenhuma na unidade B, **quando** o resumo diário
     roda, **então** só os operadores de A recebem, com as mesmas contagens das abas.
  2. **Dado** o resumo do dia já preparado, **quando** o n8n chama a ferramenta de novo, **então** nenhuma
     comunicação nova é criada.
  3. **Dado** nenhuma pendência na unidade, **quando** o resumo roda, **então** nada é enviado.
  4. **Dado** o n8n parado das 07:00 às 13:00, **quando** volta, **então** o resumo do dia não é enviado e
     fica `obsoleta`.
  5. **Dado** qualquer resumo, **quando** o conteúdo é inspecionado, **então** não há CPF nem valores.
- **Desligamento e continuação manual:** chave `resumo-prestacao` (B4) e preferência por pessoa; sem o
  resumo, as abas, a planilha e o sino continuam como hoje.
- **Maturidade:** **3** (SMTP institucional, AUT-04).

### 4.2 Link de quilometragem e Diário de Bordo

<a id="aut-40"></a>
#### AUT-40 — Link de quilometragem por trecho para o motorista

> **Dependente de desenvolvimento · maturidade 2 · valor alto · esforço G · etapa 3, ordem 44.**
> Situação: PLANEJADA — no sistema novo o recurso não existe (ficou de fora por decisão,
> `docs/migration/decisoes.md:205`); só a referência EV tem (fluxo m096).
> Detalhe: [10-4](../fluxos/10-4-link-de-km-na-vespera.md) §2–§7, §9–§13.

- **Identificador:** AUT-40 (origens O054, O277, O319).
- **Módulo e processo:** Prestação › Diário de Bordo (`PREST-DIARIO-LINK-CAMPO`, `GV-PREST-DIARIO`,
  `EV-DIARIO-LINK-KM`).
- **Evidência:** diário por prestação com uma linha por trecho (`gestao/viagens/models.py:1500-1575`);
  `diario.salvar_linhas` exige usuário com `pode_editar_equipe_prestacao` e não aceita link
  (`gestao/viagens/diario.py:281-320`, `gestao/viagens/policies.py:624-626`); padrão de token só em hash já
  usado no feed da agenda (`gestao/plataforma/assinatura.py:20-59`, `gestao/painel/views_agenda.py:167-186`);
  previsto em `docs/product/workflows.md:158-159`. Referência EV: token guardado em claro
  (`ref/ev-implantado/viagens_prestacoes/models.py:515-543`) e GET que grava (10-4 §2.2).
- **Problema que resolve:** o motorista passa os km depois, de memória ou no papel; o operador digita trecho
  a trecho; erros de hodômetro e diário pendente travam a finalização (`gestao/viagens/prestacao.py:127-156`).
- **Pessoas beneficiadas:** motorista (lança no momento, sem login, sem sinal); operador (recebe o diário
  pronto e só confere); gestão (vê quem lançou e o que falta).
- **Gatilho:** emissão ou reemissão do ofício com viatura → `diario_km.planejar(prestacao)` [novo] na
  transação de `prestacao.sincronizar` (10-4 §3.3); o operador também pode gerar o link à mão.
- **Pré-condições:** ADR nova "link público de km" (exceção ao login, como o feed ICS); elegibilidade do
  10-4 §3.1 (ofício emitido, viatura, responsável identificado, equipe não finalizada); responsável pela
  regra de `diario.motorista` (10-4 §3.2). Contato verificado (AUT-02) só é necessário para o envio
  automático (AUT-41): entregue pelo operador, o link funciona sem ele.
- **Etapas:** 10-4 §7 — `LinkDiarioKm` (só o hash do token) e `LancamentoKm` (único por diário e
  `cliente_id`), `DiarioBordo.versao`, `KM_MAXIMO`; rotas `/km/<token>/` com GET sem efeito e POST JSON
  com limites de tamanho, taxa por IP **e cota por link** (sem ela, um link vazado aceitaria POSTs
  ilimitados de 50 lançamentos; regra comum do AUT-03) e `Origin`; página offline (service worker e IndexedDB, CSP com nonce, sem
  bundler); conflito com a correção do operador; cartão "Link do motorista" (primeiro no UI Lab); dados em
  `gestao/viagens/demonstracao.py` para o PREVIEW.
- **Responsabilidade:** *sistema* — tudo; *n8n* — nada nesta ficha (envio é AUT-41); *IA* — proibida por
  desenho e por teste: não preenche, não sugere nem corrige km (10-4 §5.3).
- **Dados e permissões:** a página mostra trechos, placa e primeiro nome, sem CPF e sem a equipe; token
  mascarado nos logs da aplicação e do proxy; autoria pelo `requisicao_id` do trigger de auditoria
  (10-4 §7.4); policies novas em `gestao/viagens/policies.py` (10-4 §7.5).
- **APIs existentes e necessárias:** existentes — `diario.salvar_linhas` (a refatorar para aceitar a
  credencial do link) e o padrão de `plataforma/assinatura.py`. Necessárias — rotas públicas do 10-4 §6.4 e
  os eventos `quilometragem.trecho_salvo` e `quilometragem.concluida` (já no
  [envelope](../contratos/evento-integracao.schema.json)).
- **Participação humana:** o motorista lança; o operador confere avisos, resolve recusas e conflitos,
  revoga link vazado e continua podendo preencher tudo à mão.
- **Resultado esperado:** o diário chega completo na chegada da equipe, com os avisos de hodômetro já
  calculados; nenhuma estimativa vira leitura.
- **Falhas e recuperação:** 10-4 §9 — pré-visualização de mensageiro não grava; sem sinal, a fila fica no
  celular; percurso alterado → recusa; conflito com o operador → escolha humana; equipe finalizada → 409;
  link vazado → revogar e gerar outro.
- **Deduplicação:** um link não revogado por diário; lançamento único por (diário, `cliente_id`)
  (10-4 §10).
- **Cancelamento:** ofício cancelado → link revogado e página 410; reaberto → link suspenso; motorista
  trocado → link antigo revogado e novo criado.
- **Métricas:** 10-4 §11 — adoção (% de diários com lançamento pelo link), diário pronto até a chegada +
  24 h, recusas e conflitos por lançamento, 404/429 por IP.
- **Custos:** desenvolvimento G (a página offline com fila idempotente é a parte mais cara de acertar e
  testar); operação sem custo externo.
- **Dependências:** ADR nova; AUT-03 (padrão `LinkAcesso`); AUT-02 só para o envio automático.
- **Prioridade e esforço:** alta; G.
- **Cenários de aceite:** 10-4 §12, critérios 3 a 6, 8, 13 a 16 e 18. Os essenciais: GET de robô de
  pré-visualização não insere nem altera nenhuma linha; quatro trechos lançados offline chegam numa fila
  só quando a conexão volta; km de 12.345.678 é recusado com mensagem, sem erro 500.
- **Desligamento e continuação manual:** chave `LINK_KM_PUBLICO` (rotas respondem 503 sem revelar nada);
  revogação em massa por comando, sem apagar; o operador volta a digitar como hoje (10-4 §10).
- **Maturidade:** **2**.

<a id="aut-41"></a>
#### AUT-41 — Envio do link de km na véspera e lembretes pelo canal institucional

> **Automação indicada com n8n · maturidade 3 · valor alto · esforço P · etapa 3, ordem 46.**
> Situação: PLANEJADA. A regra da véspera foi escrita como função pura **no protótipo**
> (`prototipo/regra_vespera.py` e `test_regra_vespera.py`, cenário T11 aprovado em 17/10/2026): VERIFICADA
> PARCIALMENTE, fora do sistema. Detalhe: [10-4](../fluxos/10-4-link-de-km-na-vespera.md) §3.3, §4.3–4.4, §8–§10.

- **Identificador:** AUT-41 (origens O055, O119, O278, O320, O135, O039, O052).
- **Módulo e processo:** Prestação › véspera da saída (`PREST-DIARIO-LINK-CAMPO`, `VIA-VESPERA-SAIDA`,
  `PLAT-ROTINAS-DIARIAS`, `ROT-PLANEJADO-REALIZADO-KM`, `PREST-AVISOS-PRAZOS`, `GV-PREST-DIARIO`,
  `EV-DIARIO-LINK-KM`).
- **Evidência:** não existe aviso de véspera (`gestao/viagens/avisos.py:12`, por decisão
  `docs/migration/decisoes.md:205`); a rotina diária roda às 05:40 do host ou no primeiro acesso e não serve
  para um envio às 09:00 (`gestao/plataforma/rotinas.py:25-61`). Referência EV: aviso ao operador "amanhã
  sai a viagem" e texto `wa.me` montado à mão (`ref/ev-implantado/viagens_prestacoes/avisos.py:124-152`,
  `campo_services.py:160-189`).
- **Problema que resolve:** alguém precisa lembrar de mandar o link a cada motorista na véspera e de cobrar
  os km que faltam depois da chegada.
- **Pessoas beneficiadas:** motorista (recebe o link antes de sair); operador (só acompanha).
- **Gatilho:** `Comunicacao(tipo=link_km)` criada por `planejar` com `enviar_em` = D−1 às 09:00
  America/Sao_Paulo (proposta, decisão 3 do 10-4); envio imediato quando o ofício é emitido em cima da hora;
  lembretes no dia seguinte à chegada final e na véspera do vencimento do link, nunca durante o deslocamento
  (10-4 §8).
- **Pré-condições:** AUT-40; contato verificado do motorista (AUT-02); SMTP (AUT-04); entrega (AUT-06);
  aviso interno de véspera no sino (AUT-30); chave `km-vespera` (e `km-lembretes`) ligada.
- **Etapas:** B2 com o texto aprovado (rascunho em 10-4 §14, item 12); reagendamento gera nova versão e
  mantém o token enquanto o responsável não muda; `quilometragem.concluida` cancela os lembretes.
- **Responsabilidade:** *sistema* — elegibilidade, responsável, horário, versão, texto, estado; *n8n* —
  transporte e pull de `devidas` a cada 15 min; *IA* — nenhuma.
- **Dados e permissões:** o e-mail leva o link pessoal (que é credencial): retenção curta das execuções no
  n8n e escopo mínimo do link (B7). O motorista "não cadastrado" nunca recebe envio automático.
- **APIs existentes e necessárias:** nenhuma existe; as de B2 mais as extensões do 10-4 §6.3.
- **Participação humana:** conferir motorista e viatura antes da véspera; entregar à mão quando não houver
  contato; marcar "enviado por outro meio".
- **Resultado esperado:** ≥ 95 % das comunicações elegíveis com contato verificado enviadas antes da saída
  (meta do 10-4 §11).
- **Falhas e recuperação:** 10-4 §9 — n8n fora às 08:00 e de volta às 10:30 → o pull envia uma vez;
  resultado desconhecido → exceção; sem contato → `aguardando_manual` e sino ao operador.
- **Deduplicação:** comunicação única por (tipo, link, versão da agenda); B3.
- **Cancelamento:** ofício cancelado, motorista trocado ou saída alterada cancelam a comunicação antiga
  (409 na reserva).
- **Métricas:** latência p95 ≤ 15 min; envio antes da saída; % em `aguardando_manual` por falta de contato.
- **Custos:** ~1,2 comunicações por viagem (0,8 link + 0,4 lembrete, hipóteses H3 e H5) → ~60, ~240 e ~600
  e-mails por mês nos cenários de 50, 200 e 500 viagens [estimativa]; R$ 0 adicional; workflow P se a
  fundação já existir, +M se este for o primeiro fluxo a construí-la (10-4 §13).
- **Dependências:** AUT-40, AUT-06, AUT-30 (e AUT-02, AUT-04).
- **Prioridade e esforço:** alta; P.
- **Cenários de aceite:** 10-4 §12, critérios 1, 2, 7, 9 a 12 e 17.
- **Desligamento e continuação manual:** chaves `km-vespera` e `km-lembretes` (B4): a comunicação vai a
  `aguardando_manual` e o aviso interno de véspera diz "envie manualmente"; o cartão oferece "mostrar
  link", "copiar mensagem" e "marcar enviado por outro meio".
- **Maturidade:** **3** (2 quando SMTP e contatos existirem, como diz o 10-4 §13). WhatsApp assistido com registro (link pelo `wa.me` do aparelho
  institucional): 2 (AUT-172); plataforma oficial: 5 (AUT-10), pronta e desligada pela WA-3 (AUT-174).

<a id="aut-42"></a>
#### AUT-42 — Km inicial sugerido pelo último km da viatura

> **Automação determinística suficiente · maturidade 2 · valor médio · esforço P · trilha paralela P18.**
> Situação: VERIFICADA PARCIALMENTE — EXISTENTE a consulta do último km da viatura, usada só num aviso;
> INEXISTENTE a sugestão. Sem fluxo próprio: esta ficha é o detalhe.

- **Identificador:** AUT-42 (origem O053).
- **Módulo e processo:** Prestação › Diário de Bordo › preenchimento (`PREST-DIARIO-PREENCHIMENTO`).
- **Evidência:** `diario.ultimo_km_da_viatura` em `gestao/viagens/diario.py:169-198` ("só informação: nada é
  preenchido com ele"); aviso "km de saída menor que o último km registrado desta viatura" em
  `gestao/viagens/dominio/diario.py:58-65`; o padrão de sugestão que só escreve em campo vazio, acionada por
  uma pessoa, já existe para as distâncias (`static/js/componentes/diario-distancias.js:1-36`).
- **Problema que resolve:** o operador digita o km de saída da primeira linha; um erro aqui gera o aviso de
  "hodômetro voltou" e cascata nos trechos seguintes.
- **Pessoas beneficiadas:** operador; motorista no link (AUT-40), que vê o mesmo valor como referência.
- **Gatilho:** abrir a folha do diário com a primeira linha sem km inicial (leitura, sem gravar).
- **Pré-condições:** viatura do cadastro (`viatura_id` resolvido, `diario.py:160-166`) e um diário anterior
  da mesma viatura com km final e chegada antes desta saída. Viatura de outro órgão ou fretada: sem sugestão.
- **Etapas:** (1) a view passa o `UltimoKm` (km, data, nº do ofício) ao template; (2) a primeira linha mostra
  "usar 45.210 (último km desta viatura, Ofício 12/2026, dd/mm)"; (3) aceitar grava por `diario.salvar_linhas`
  com `origem_km = ultimo_da_viatura` [novo, mesmo campo que o 10-5 cria para R-DB-5]; (4) nada é
  preenchido sem clique; (5) no link de km, o valor aparece só como referência ao lado do campo.
- **Responsabilidade:** *sistema* — tudo; *n8n* — nenhuma; *IA* — nenhuma.
- **Dados e permissões:** os mesmos do diário (`pode_editar_equipe_prestacao`). A sugestão mostra km, data e
  nº de ofício de outro diário, a mesma exposição do aviso que já existe.
- **APIs existentes e necessárias:** existentes — `ultimo_km_da_viatura`, `salvar_linhas`. Necessária — o
  campo `origem_km`.
- **Participação humana:** aceitar ou ignorar a sugestão e conferir com o painel. Proposta: o km sugerido
  conta como "a confirmar" na conclusão para assinatura, como o km pela distância (R-DB-5 do 10-5; decisão
  D-PR3).
- **Resultado esperado:** menos digitação na primeira linha e menos avisos de hodômetro.
- **Falhas e recuperação:** a viatura rodou sem registro entre as viagens → a sugestão difere do painel; a
  pessoa corrige e o aviso de continuidade aparece como hoje; diário anterior com km errado → a sugestão
  mostra a origem (ofício e data) para conferência.
- **Deduplicação:** não se aplica; o GET não grava e aceitar duas vezes grava o mesmo valor.
- **Cancelamento:** não se aplica; apagar o campo volta ao estado anterior.
- **Métricas:** % de primeiras linhas preenchidas pela sugestão; avisos "menor que o último km" por diário,
  antes e depois; correções posteriores do km aceito.
- **Custos:** desenvolvimento P; sem custo de operação.
- **Dependências:** nenhuma; combina com `origem_km` de AUT-46 se vierem juntos.
- **Prioridade e esforço:** média; P.
- **Cenários de aceite:**
  1. **Dado** uma viatura com último km 45.210 e a primeira linha vazia, **quando** a folha abre, **então** a
     sugestão aparece com a origem e nenhuma linha de nenhuma tabela é inserida ou alterada.
  2. **Dado** a sugestão aceita, **quando** a linha é salva, **então** o km inicial é 45.210 com
     `origem_km = ultimo_da_viatura`.
  3. **Dado** a primeira linha já preenchida ou uma viatura sem cadastro, **quando** a folha abre, **então**
     não há sugestão.
- **Desligamento e continuação manual:** parâmetro de configuração [novo] que esconde a sugestão; a pessoa
  digita como hoje.
- **Maturidade:** **2**.

<a id="aut-43"></a>
#### AUT-43 — Horários realizados sugeridos pelos lançamentos do link de km

> **Automação determinística suficiente · maturidade 2 · valor médio · esforço P · etapa 3, ordem 50.**
> Situação: PLANEJADA (depende de AUT-40; o 10-4 §1 deixou fora do escopo como "sugestão futura, sempre
> confirmada por uma pessoa"). Esta ficha é o detalhe.

- **Identificador:** AUT-43 (origem O056).
- **Módulo e processo:** Prestação › viagem realizada (`PREST-VIAGEM-REALIZADA`).
- **Evidência:** ajuste dos horários reais e recálculo das diárias em `gestao/viagens/realizado.py:61-131`
  (gravação em `:81-107`); tela em `gestao/viagens/views_diario.py:180-208`; a diária liberada passa a ser a
  realizada (`gestao/viagens/prestacao.py:109-124`). Hoje os horários reais são digitados.
- **Problema que resolve:** o operador redigita data e hora de cada trecho para corrigir a diária, quando o
  motorista já marcou no celular a saída e a chegada de cada trecho.
- **Pessoas beneficiadas:** operador; servidores (diária realizada correta com menos atraso).
- **Gatilho:** abrir o ajuste da viagem realizada quando há lançamentos do link; opcionalmente, um aviso no
  sino depois de `quilometragem.concluida` ("horários sugeridos disponíveis").
- **Pré-condições:** AUT-40 em uso, com `LancamentoKm.digitado_em` (relógio do celular) e `recebido_em`
  (relógio do servidor) gravados (10-4 §7.2).
- **Etapas:** (1) para cada linha, saída sugerida = `digitado_em` do lançamento do km inicial; chegada
  sugerida = `digitado_em` do km final; (2) **confiança**: alta quando o lançamento foi online
  (|`recebido_em` − `digitado_em`| ≤ 5 min, proposta) e baixa quando veio da fila offline, porque o relógio
  do celular pode estar errado; (3) a tela mostra lado a lado o horário atual e o sugerido, com a confiança e
  a diferença em diárias que a mudança causaria (prévia, sem gravar); (4) "aplicar" chama `realizado.salvar`
  com o usuário que clicou.
- **Responsabilidade:** *sistema* — calcular a sugestão e a prévia; *n8n* — nenhuma; *IA* — nenhuma.
- **Dados e permissões:** os do ajuste existente (`pode_editar_equipe_prestacao`); nenhum dado novo sai do
  sistema.
- **APIs existentes e necessárias:** existente — `realizado.salvar` e `realizado.desfazer`. Necessária —
  consulta de lançamentos por linha (AUT-40).
- **Participação humana:** obrigatória: horário realizado muda diária, que tem efeito financeiro. O 10-4 já
  define `digitado_em` como "só informativo, nunca ordena nem decide"; a sugestão respeita isso.
- **Resultado esperado:** ajuste da viagem realizada em poucos cliques quando o motorista usou o link online.
- **Falhas e recuperação:** relógio do celular errado → confiança baixa e diferença visível; lançamento
  corrigido depois → vale o último gravado da linha; trecho sem lançamento → sem sugestão.
- **Deduplicação:** não se aplica (leitura); aplicar duas vezes grava o mesmo horário.
- **Cancelamento:** não se aplica; `realizado.desfazer` já existe.
- **Métricas:** % de ajustes feitos pela sugestão; diferença média entre o horário sugerido e o aplicado;
  tempo entre a chegada e o ajuste.
- **Custos:** desenvolvimento P; sem operação.
- **Dependências:** AUT-40.
- **Prioridade e esforço:** média; P.
- **Cenários de aceite:**
  1. **Dado** lançamentos online com km inicial às 06:32 e km final às 09:10, **quando** o ajuste abre,
     **então** a saída 06:32 e a chegada 09:10 aparecem como sugestão de confiança alta e nada é gravado.
  2. **Dado** um lançamento offline sincronizado 3 h depois, **quando** o ajuste abre, **então** a sugestão
     aparece com confiança baixa.
  3. **Dado** a sugestão aplicada, **quando** `realizado.salvar` grava, **então** a diária realizada é
     recalculada como hoje e a autoria é de quem clicou.
- **Desligamento e continuação manual:** parâmetro que esconde as sugestões; a digitação continua.
- **Maturidade:** **2**.

<a id="aut-44"></a>
#### AUT-44 — Continuidade do km (saltos e retrocessos) e prontidão do DB antes de assinar

> **Automação determinística suficiente · maturidade 2 · valor médio · esforço P · etapa 3, ordem 51.**
> Situação: VERIFICADA PARCIALMENTE — EXISTENTES os avisos de retrocesso entre trechos, desvio da distância
> prevista e km abaixo do último da viatura; INEXISTENTES o aviso de salto entre trechos e o limite máximo
> de km. Prontidão do DB: 10-5 §3.3; limite de km: 10-4 §7.2.

- **Identificador:** AUT-44 (origem O279).
- **Módulo e processo:** Prestação › Diário de Bordo (`GV-PREST-DIARIO`).
- **Evidência:** `gestao/viagens/dominio/diario.py:1-9` e `:58-87` (avisos que não bloqueiam: retrocesso,
  desvio de 20 % com mínimo de 10 km — números de paridade com a referência, não regra institucional
  confirmada —, km abaixo do último da viatura); `numero_do_km` aceita qualquer quantidade de dígitos
  (`:29-32`); o único bloqueio é km final < inicial na mesma linha (constraint em
  `gestao/viagens/models.py:1567-1571`). Na referência GV não há validação de continuidade entre trechos.
- **Problema que resolve:** salto de km entre a chegada de um trecho e a saída do seguinte (km não
  registrado) e valores absurdos passam sem aviso até o DB ir para assinatura.
- **Pessoas beneficiadas:** operador; motorista (aviso imediato no link); conferência da prestação.
- **Gatilho:** cada gravação de linha (autosave do operador e POST do link) e a conclusão para assinatura.
- **Pré-condições:** limiar de salto definido pela instituição (decisão D-PR4). Sem ele, o aviso de salto
  fica desligado; o limite máximo não depende de decisão.
- **Etapas:** (1) `KM_MAXIMO = 9_999_999` (o mesmo do EV) recusado com mensagem no autosave e no link,
  em vez de erro de banco; (2) aviso de salto: `km_inicial(n+1) − km_final(n) > limiar`, só aviso, porque
  rodar no destino entre trechos é legítimo; (3) km iguais na mesma linha continuam válidos (trecho sem
  deslocamento); (4) todos os avisos entram na lista de ciência R-DB-9 da conclusão do DB (10-5 §3.3) e o
  km máximo e km final < inicial entram em R-DB-4 (bloqueio).
- **Responsabilidade:** *sistema* — tudo, em Python puro com testes; *n8n* — nenhuma; *IA* — nenhuma.
- **Dados e permissões:** os do diário.
- **APIs existentes e necessárias:** existente — `dominio.diario.conferir`. Necessária — o parâmetro de
  limiar (configuração por unidade ou global, decisão D-PR4).
- **Participação humana:** ler o aviso e corrigir ou dar ciência na conclusão.
- **Resultado esperado:** erro de digitação é apontado antes do DB ir para assinatura; nenhum km absurdo
  causa erro 500.
- **Falhas e recuperação:** limiar mal calibrado → muitos avisos falsos; medir na conferência e ajustar o
  parâmetro; o aviso nunca bloqueia.
- **Deduplicação:** não se aplica (cálculo puro).
- **Cancelamento:** não se aplica.
- **Métricas:** avisos de salto por diário; % de avisos que levaram a correção (indica limiar útil);
  ocorrências de km fora do limite.
- **Custos:** desenvolvimento P.
- **Dependências:** limiar institucional (só para o salto). Alimenta AUT-46.
- **Prioridade e esforço:** média; P.
- **Cenários de aceite:**
  1. **Dado** trecho 1 com chegada 45.300 e trecho 2 com saída 45.900 e limiar de 300 km, **quando** a
     conferência roda, **então** aparece o aviso de salto de 600 km e nada é bloqueado.
  2. **Dado** km 12.345.678 digitado, **quando** a linha é salva, **então** a gravação é recusada com
     "km fora do limite" e sem erro 500.
  3. **Dado** km inicial igual ao final, **quando** salva, **então** é aceito sem aviso.
  4. **Dado** o limiar não configurado, **quando** a conferência roda, **então** não há aviso de salto e os
     demais avisos continuam.
- **Desligamento e continuação manual:** limiar vazio desliga o aviso de salto; o km máximo é validação de
  entrada e não se desliga.
- **Maturidade:** **2**.

### 4.3 Diário de Bordo e Relatório Técnico para assinatura

<a id="aut-45"></a>
#### AUT-45 — DB com motorista de outro ofício: signatário correto e direcionamento correto do assinado

> **Automação determinística suficiente · maturidade 2 · valor médio · esforço P · trilha paralela P19.**
> Situação: VERIFICADA PARCIALMENTE — EXISTENTE: o DB do sistema novo já imprime o motorista efetivo do
> diário; INEXISTENTE: o direcionamento correto do DB assinado na importação quando o motorista é de outro
> ofício. Relacionado: [10-5](../fluxos/10-5-db-e-rt-para-assinatura.md) §3.3 (R-DB-11) e §3.8.

- **Identificador:** AUT-45 (origens O067, O280).
- **Módulo e processo:** Prestação › Diário de Bordo e importação documental (`DOC-IMPORTACAO-IDENTIFICACAO`,
  `GV-PREST-DIARIO`).
- **Evidência:** o signatário vem de `diario.motorista` (`gestao/viagens/diario.py:219-224`), que respeita a
  troca feita no diário e o motorista "de outro ofício" — diferente do GV, que usa o motorista do ofício e
  ignora o diário (`ref/gv/prestacoes_contas/assinatura_services.py:44-46`). Mas, com motorista de outro
  ofício, o DB imprime o nº e o protocolo **do ofício do motorista** (`gestao/viagens/diario.py:397-401`), e
  o destino `db_assinado` da importação é por ofício (`gestao/viagens/importacao.py:43`): o assinado pode
  casar com o ofício do motorista, e não com o da equipe, ou cair na revisão sem o candidato certo.
- **Problema que resolve:** DB assinado anexado no ofício errado e, no futuro envio para assinatura
  (AUT-47), pedido a quem não dirigiu.
- **Pessoas beneficiadas:** operador (menos revisão e menos anexo errado); motorista (recebe só o que é dele).
- **Gatilho:** importação de uma parte identificada como DB assinado; conclusão do DB para assinatura (AUT-46).
- **Pré-condições:** confirmar a regra de quem assina o DB (decisão D-01 do 10-5: só o motorista? e com
  revezamento?).
- **Etapas:** (1) **regra de identificação** [recomendada agora, sem mudar o modelo do documento]: quando o
  nº ou protocolo lido num DB assinado coincide com `motorista_oficio`/`motorista_protocolo` de algum
  diário em modo "outro ofício", esse diário entra como candidato e a parte vai à revisão com ele
  pré-selecionado; nunca aplica sozinha ao ofício do motorista; (2) **código da versão** [quando AUT-46 e a
  decisão D-07 do 10-5 existirem]: o código impresso aponta a versão e, por ela, o diário certo; (3) toda
  comunicação de assinatura do DB usa `diario.motorista`, nunca o motorista do ofício (10-5 §3.8).
- **Responsabilidade:** *sistema* — tudo; *n8n* — nenhuma; *IA* — nenhuma.
- **Dados e permissões:** os da importação (`policies.edita_oficios`) e do diário.
- **APIs existentes e necessárias:** existentes — `dominio/importacao.identificar_conjunto`,
  `importacao.destinos_do_usuario`, `diario.motorista`. Nenhuma API externa.
- **Participação humana:** confirmar o destino na revisão.
- **Resultado esperado:** nenhum DB de equipe com motorista de fora anexado no ofício do motorista.
- **Falhas e recuperação:** dois diários citam o mesmo ofício do motorista → revisão com os dois
  candidatos; anexado por engano antes da regra → `anexos.remover` (versões guardadas).
- **Deduplicação:** a da importação (hash por usuário; parte terminal não reaplica, `importacao.py:253-254`).
- **Cancelamento:** não se aplica.
- **Métricas:** DB assinados removidos ou movidos depois de aplicados (meta 0); % de DB com motorista de
  outro ofício que vão à revisão com o candidato certo.
- **Custos:** desenvolvimento P.
- **Dependências:** decisão D-01 do 10-5; o passo (2) depende de AUT-46.
- **Prioridade e esforço:** média; P.
- **Cenários de aceite:**
  1. **Dado** o diário do Ofício 20/2026 com motorista do Ofício 15/2026, **quando** o DB assinado é
     importado, **então** a parte não é anexada ao Ofício 15/2026 e vai à revisão com o Ofício 20/2026
     sugerido.
  2. **Dado** um diário com o motorista trocado para outro servidor da equipe, **quando** o DB é gerado,
     **então** nome e CPF impressos são os do novo motorista (regressão do que já existe).
  3. **Dado** o envio para assinatura (AUT-47), **quando** o DB é concluído, **então** o destinatário é o
     resolvido por `diario.motorista`.
- **Desligamento e continuação manual:** a regra só manda para revisão, então não precisa de chave; a
  revisão manual continua como hoje.
- **Maturidade:** **2**.

<a id="aut-46"></a>
#### AUT-46 — DB e RT prontos para assinatura: conclusão explícita e versão congelada

> **Melhor execução pelo próprio sistema · maturidade 2 · valor alto · esforço M · etapa 3, ordem 52.**
> Situação: PLANEJADA — hoje DB e RT são gerados na hora, por GET, sem instantâneo, hash nem estado.
> Detalhe: [10-5](../fluxos/10-5-db-e-rt-para-assinatura.md) §3.1–3.9, §4.1, §7, §13 (Fase A).

- **Identificador:** AUT-46 (origens O059, O284).
- **Módulo e processo:** Prestação › DB e RT (`PREST-DOCS-GERACAO`, `GV-PREST-ASSINATURA`).
- **Evidência:** geração sob demanda em `gestao/viagens/views_diario.py:211-230`,
  `gestao/viagens/prestacao_texto.py:53-127`, `gestao/viagens/diario.py:390-442` e
  `gestao/viagens/relatorio.py:332-382`; a data do RT é "hoje" (`relatorio.py:338`;
  `gestao/viagens/dominio/relatorio.py:94-101`), então o mesmo RT gerado em outro dia sai diferente; a
  "impressão dos dados" (SHA-256) existe para termo e OS (`gestao/viagens/assinados.py:92-96`, `:111-125`);
  a pendência aceita "preenchido **ou** assinado" (`gestao/viagens/prestacao.py:144-147`); o pacote gera de
  novo quando falta o assinado (`gestao/viagens/pacote_prestacao.py:83-92`).
- **Problema que resolve:** não há como afirmar que o documento assinado corresponde ao preparado, nem
  impedir que uma versão vencida passe como válida.
- **Pessoas beneficiadas:** operador (checklist e situação por documento); conferência e gestão (assinado
  ligado à versão).
- **Gatilho:** **humano e explícito**: `para_assinatura.concluir(usuario, prestacao_id, chave, confirmacoes)`
  [novo], por documento (DB da equipe ou RT de cada servidor). Nenhum autosave conclui (10-5 §3.2).
- **Pré-condições:** requisitos R-DB e R-RT do 10-5 §3.3–3.4 (inclui AUT-44); viagem terminada; equipe não
  finalizada.
- **Etapas:** 10-5 §3.7, passos P1 a P5 e P9 — requisitos na tela, revalidação na transação,
  `VersaoParaAssinatura` com instantâneo e data fixada, PDF gerado pela outbox a partir do instantâneo, SHA-256
  do PDF armazenado, assinante resolvido pelos dados; devolução ligada à versão; travas de edição e
  "Corrigir" (§3.9). Aviso **interno** ao operador quando o assinado volta e é ligado à versão (sino, padrão
  AUT-24), sem n8n.
- **Responsabilidade:** *sistema* — tudo; *n8n* — nada nesta ficha (disponibilizar e avisar é AUT-47);
  *IA* — nenhuma.
- **Dados e permissões:** `pode_concluir_para_assinatura` e `pode_aceitar_versao_vencida` [novas] (10-5 §7.4);
  instantâneo guarda nome e CPF do assinante (documento interno, não sai do sistema).
- **APIs existentes e necessárias:** existentes — `prestacao_texto.dados_do_documento`, `pdf_do_documento`,
  `assinados.impressao` (princípio). Necessárias — tópico interno `viagens.prestacao.versao.gerar` e evento
  `prestacao.documentos_gerados` (já no envelope).
- **Participação humana:** concluir, dar ciência dos avisos, corrigir, aceitar o devolvido.
- **Resultado esperado:** cada devolução ligada a uma versão congelada; dados que mudaram depois ficam
  visíveis e pedem decisão.
- **Falhas e recuperação:** 10-5 §9 — falha do PDF (exceção e "gerar novamente" com o mesmo instantâneo),
  dados alterados depois (`divergente`), devolução de versão vencida (revisão, nunca anexo automático).
- **Deduplicação:** uma versão vigente por (prestação, chave), garantida no banco; conclusão idempotente pela
  impressão (10-5 §10).
- **Cancelamento:** ofício cancelado, servidor removido ou "Corrigir" → versão `cancelada` ou `substituida`.
- **Métricas:** versões por documento; % substituídas por correção; devoluções de versão vencida (10-5 §11).
- **Custos:** desenvolvimento M; sem custo de operação.
- **Dependências:** AUT-44, AUT-53.
- **Prioridade e esforço:** alta; M.
- **Cenários de aceite:** 10-5 §12, critérios 1 a 7, 10 a 13 e 18.
- **Desligamento e continuação manual:** a conclusão e o congelamento são internos e não se desligam; o
  modo de hoje (baixar e mandar por fora) continua possível, agora com o PDF congelado da versão (10-5 §10).
- **Maturidade:** **2**.

<a id="aut-47"></a>
#### AUT-47 — DB e RT ao signatário pelo portal, com aviso e lembrete por e-mail

> **Automação indicada com n8n · maturidade 3 · valor alto · esforço M · etapa 3, ordem 53.**
> Situação: PLANEJADA (hoje: download e envio por fora). Detalhe: [10-5](../fluxos/10-5-db-e-rt-para-assinatura.md)
> §3.7 (P6–P8), §4.2, §6, §8–§10, §13 (Fase B).

- **Identificador:** AUT-47 (origens O060, O326, O283).
- **Módulo e processo:** Prestação › DB e RT (`PREST-DOCS-ENVIO-ASSINATURA`, `EV-DB-RT-ASSINATURA`,
  `GV-PREST-ASSINATURA`).
- **Evidência:** não há estado "enviado para assinatura", destinatário nem prazo; só o texto do aviso
  interno "Documentos gerados — envie ao servidor para assinar" (`gestao/viagens/avisos.py:76-86`). A volta
  é inferida pelo anexo `rt_assinado`/`db_assinado`. Referência GV: link de assinatura enviado à mão por
  `wa.me` (`ref/gv/prestacoes_contas/signature_views.py:35-44`).
- **Problema que resolve:** baixar, enviar, cobrar e receber cada documento por fora; cerca de 8 min por
  documento na hipótese do 10-5 §11 (não medido).
- **Pessoas beneficiadas:** motorista (DB) e cada servidor (RT); operador.
- **Gatilho:** versão `pronta` (AUT-46) → `LinkAcesso` de escopo `assinatura` (só as versões vigentes daquele
  assinante) e uma `Comunicacao(tipo=documentos_para_assinatura)` por assinante, na janela proposta (dias
  úteis, 08:00–18:00); lembretes no dia do prazo e 2 dias úteis depois, no máximo 2 (proposta D-05).
- **Pré-condições:** AUT-46, AUT-03 (portal), AUT-02, AUT-06; decisão D-03 do 10-5 sobre **qual assinatura
  vale** (física digitalizada, gov.br, assinatura do eProtocolo); chave `db-rt-assinatura` ligada.
- **Etapas:** B2; o documento fica **no portal** (link autenticado), não anexado ao e-mail; a devolução volta
  pelo portal ou por resposta de e-mail para a importação com destino pré-definido pela versão (AUT-52);
  lembretes como novas comunicações; exceção `prazo_devolucao_vencido` ao final.
- **Responsabilidade:** *sistema* — quem assina, link, prazo, estado, revalidação; *n8n* — avisar e lembrar
  por e-mail; *IA* — nenhuma. **O sistema não assina por ninguém** (AUT-59).
- **Dados e permissões:** o link só dá acesso aos documentos daquele assinante; o e-mail não leva o PDF;
  identificação no portal a decidir (D-06: só link, link + CPF, ou link + código). Proposta comum do AUT-03
  para o escopo `assinatura` (nível alto: RT e DB têm CPF e o servidor devolve arquivo): link + código de
  uso único enviado ao contato verificado no primeiro uso em cada aparelho, **pedido por POST** — o GET
  nunca envia código, para o robô do antivírus de e-mail não gastar a cota nem disparar códigos. Sem isso,
  um e-mail encaminhado ou numa caixa compartilhada permitiria a um terceiro baixar o RT e devolver um
  "assinado" falso.
- **APIs existentes e necessárias:** nenhuma existe; B2, rotas do portal (AUT-03) e as extensões do 10-5 §6.3.
- **Participação humana:** assinar (fora do sistema), devolver, conferir e aceitar.
- **Resultado esperado:** ≥ 70 % das versões devolvidas sem cobrança humana (meta inicial do 10-5 §11).
- **Falhas e recuperação:** 10-5 §9 — link expirado (pedir novo, no máximo 1 por 24 h, só ao contato
  verificado), assinante sem cadastro (`assinante_indefinido`, caminho manual), dados mudaram depois do envio
  (versão `divergente`, download suspenso, reserva 409).
- **Deduplicação:** uma comunicação por assinante e rodada; um lembrete por (versão, ordem); B3.
- **Cancelamento:** "Corrigir", cancelamento do ofício, remoção do servidor ou finalização → comunicações
  canceladas e link revogado; quem já recebeu é avisado de que a versão não vale mais.
- **Métricas:** 10-5 §11 — latência de disponibilização p90 < 10 min, tempo até a devolução, devolução sem
  cobrança, duplicidade 0.
- **Custos:** ~9,6 comunicações por viagem (4,8 assinantes + 4,8 lembretes, hipótese) → ~480, ~1.920 e
  ~4.800 e-mails por mês nos cenários de 50, 200 e 500 viagens [estimativa]; R$ 0 adicional; desenvolvimento M
  (portal público com controles é a maior parte).
- **Dependências:** AUT-46, AUT-03, AUT-06 (e AUT-02, AUT-04); B9 (complementa o eProtocolo, não o substitui).
- **Prioridade e esforço:** alta; M.
- **Cenários de aceite:** 10-5 §12, critérios 8, 9, 14 a 16.
- **Desligamento e continuação manual:** chave `db-rt-assinatura` (B4); na aba "Assinaturas": baixar o PDF
  congelado, copiar link e mensagem, marcar entregue por outro meio, anexar assinado (10-5 §10).
- **Maturidade:** **3**. Assinatura com validade reconhecida feita pelo sistema: 4 (integração
  institucional). WhatsApp assistido com registro: 2 (AUT-172); plataforma oficial: 5 (AUT-10).

### 4.4 Relatório Técnico e prazos

<a id="aut-48"></a>
#### AUT-48 — Relato do servidor coletado por link

> **Dependente de desenvolvimento · maturidade 2 · valor médio · esforço M · etapa 3, ordem 55.**
> Situação: PLANEJADA. Detalhe: [10-5](../fluxos/10-5-db-e-rt-para-assinatura.md) §3.6 (a), §8 e R-RT-11.

- **Identificador:** AUT-48 (origem O058).
- **Módulo e processo:** Prestação › RT (`PREST-RT-PREENCHIMENTO`).
- **Evidência:** o RT tem 5 textos, custeio e diária recebida (`gestao/viagens/models.py:1578-1602`,
  `gestao/viagens/relatorio.py:269-321`); a sugestão local usa motivo, descrição e resultados do plano
  (`gestao/viagens/dominio/relatorio.py:117-220`); não existe coleta do relato de quem participou.
- **Problema que resolve:** o operador escreve sobre o que outros fizeram; as afirmações do RT não têm fonte.
- **Pessoas beneficiadas:** servidor (escreve o que fez); operador (só revisa); conferência (RT com origem).
- **Gatilho:** chegada da viagem → `LinkAcesso` de escopo `relato` por `PrestacaoServidor`, entregue pelo
  operador ou, com AUT-06, por e-mail.
- **Pré-condições:** AUT-03, AUT-02; decisão D-09 do 10-5 (pedir a cada servidor ou a um representante;
  perguntas e prazo aprovados).
- **Etapas:** questionário objetivo do 10-5 §3.6 (a): atividades previstas realizadas, resumo de até 600
  caracteres, intercorrências, medidas, custeio, valor recebido (opcional) e declaração de veracidade (não é
  assinatura); respostas viram **sugestões rotuladas** "Relato de <nome>, <data>", aplicadas campo a campo
  pelo operador; o link trava quando o RT daquele servidor é concluído.
- **Responsabilidade:** *sistema* — link, formulário, guarda, sugestões; *n8n* — só levar o link por e-mail,
  se ligado; *IA* — nenhuma na coleta (o relato pode alimentar AUT-50).
- **Dados e permissões:** texto livre pode conter dado pessoal: retenção igual à da prestação (decisão);
  o relato não dá acesso a dados de colegas.
- **APIs existentes e necessárias:** existente — `relatorio.salvar` (aplicação pelo operador). Necessárias —
  rotas do portal (AUT-03), entidade `RelatoServidor` [novo].
- **Participação humana:** o servidor responde; o operador aplica ou descarta cada sugestão.
- **Resultado esperado:** RT com objetivo, conclusão e intercorrências vindos de quem participou.
- **Falhas e recuperação:** link expirado (pedir novo); relato não respondido → ciência R-RT-11 na conclusão,
  sem bloqueio; resposta em conflito com o plano → o operador decide.
- **Deduplicação:** um relato por `PrestacaoServidor` e versão do questionário; reenvio substitui o rascunho
  até a trava.
- **Cancelamento:** remoção da equipe, conclusão do RT ou finalização travam o link.
- **Métricas:** % de servidores que respondem; % de sugestões aplicadas; tempo de redação do RT, antes e
  depois (10-5 §11).
- **Custos:** desenvolvimento M; ~1 e-mail por servidor se enviado pelo n8n [estimativa].
- **Dependências:** AUT-03, AUT-02.
- **Prioridade e esforço:** média; M.
- **Cenários de aceite:**
  1. **Dado** um relato respondido, **quando** o operador abre o RT, **então** as respostas aparecem como
     sugestões rotuladas e nenhum campo foi alterado.
  2. **Dado** o RT do servidor concluído, **quando** ele abre o link, **então** a página mostra "relato
     encerrado" e não aceita envio.
  3. **Dado** o servidor A, **quando** abre o próprio link, **então** não vê nada dos colegas.
- **Desligamento e continuação manual:** chave `relato-servidor` (10-5 §10); o operador escreve o RT como hoje.
- **Maturidade:** **2** (entrega automática do link por e-mail: 3).

<a id="aut-49"></a>
#### AUT-49 — RT sem afirmações não verificadas por padrão

> **Automação determinística suficiente · maturidade 2 · valor médio · esforço P · trilha paralela P20.**
> Situação: EXISTENTE com defeito — a sugestão local de conclusão termina **sempre** com "Não houve
> intercorrências que comprometessem os resultados." Relacionado: [10-5](../fluxos/10-5-db-e-rt-para-assinatura.md)
> R-RT-4, R-RT-5 e R-RT-8.

- **Identificador:** AUT-49 (origem O325).
- **Módulo e processo:** Prestação › RT › "Sugerir texto" (`EV-RT-SUGESTAO`; no sistema novo,
  `PREST-RT-PREENCHIMENTO`).
- **Evidência:** `gestao/viagens/dominio/relatorio.py:166-189` (`sugerir_conclusao`: "foi realizada conforme
  o planejado" e, na linha 188, a frase fixa sobre intercorrências, sem nenhum dado que a sustente);
  `:209-212` (medidas terminam em "Não há outras medidas a adotar além da prestação de contas das diárias.");
  o RT nasce com os textos padrão e o custeio padrão (`gestao/viagens/relatorio.py:236-256`,
  `dominio/relatorio.py:17-21`) e conta como preenchido sem ninguém escrever (`dominio/relatorio.py:112-114`).
  A referência EV tem a mesma frase fixa (`ref/ev-implantado/viagens_prestacoes/rt_services.py:466`).
- **Problema que resolve:** declaração não verificada em documento que o servidor assina.
- **Pessoas beneficiadas:** servidor que assina; conferência e gestão.
- **Gatilho:** "Sugerir texto" na tela do RT; criação do RT com textos padrão.
- **Pré-condições:** nenhuma técnica; os textos padrão do cadastro (`ModeloTexto`) são da instituição e não
  são alterados por esta ficha.
- **Etapas:** (1) a frase de intercorrências só entra quando há fonte: relato do servidor (AUT-48) ou uma
  marcação explícita "não houve intercorrências" feita por pessoa; sem fonte, a sugestão sai sem a frase;
  (2) "conforme o planejado" só quando os resultados do plano cobrem as atividades previstas; senão,
  "foi realizada"; (3) a frase final das medidas sai só quando a pessoa marcar que não há outras medidas;
  (4) custeio e textos padrão não valem como confirmados (R-RT-5 e R-RT-8 do 10-5, quando AUT-46 existir);
  (5) testes de domínio cobrindo cada caso.
- **Responsabilidade:** *sistema* — tudo; *n8n* — nenhuma; *IA* — nenhuma (é anterior a qualquer IA).
- **Dados e permissões:** os do RT.
- **APIs existentes e necessárias:** existentes — `relatorio.sugerir` e `dominio.relatorio.sugerir`.
- **Participação humana:** marcar explicitamente o que afirma; revisar o texto.
- **Resultado esperado:** nenhuma sugestão afirma fato que o sistema não tem.
- **Falhas e recuperação:** sem fonte, a conclusão fica mais curta e a pessoa completa.
- **Deduplicação:** não se aplica (sugestão calculada na hora, sem gravação).
- **Cancelamento:** não se aplica; a pessoa descarta a sugestão.
- **Métricas:** RTs concluídos com a frase de intercorrências sem fonte registrada (meta 0, depois de AUT-46).
- **Custos:** desenvolvimento P.
- **Dependências:** nenhuma; fica mais útil com AUT-48.
- **Prioridade e esforço:** média; P. Pode entrar já.
- **Cenários de aceite:**
  1. **Dado** um RT sem relato e sem marcação, **quando** "Sugerir texto" roda para a conclusão, **então**
     a frase "Não houve intercorrências…" não aparece.
  2. **Dado** a marcação "não houve intercorrências" feita por pessoa, **quando** a sugestão roda, **então**
     a frase aparece.
  3. **Dado** atividades previstas sem resultado lançado, **quando** a sugestão roda, **então** o texto não
     diz "conforme o planejado".
- **Desligamento e continuação manual:** não se desliga (corrige regra); a pessoa continua escrevendo o que
  quiser no campo.
- **Maturidade:** **2**.

<a id="aut-50"></a>
#### AUT-50 — Rascunho do RT por IA, ancorado nos dados do sistema, no plano e no relato

> **Assistência por IA indicada · maturidade 3 · valor médio · esforço M · etapa 4, ordem 66.**
> Situação: PLANEJADA. Detalhe: [10-5](../fluxos/10-5-db-e-rt-para-assinatura.md) §3.6 (e), §9 (IA), §11 (IA),
> critério 17.

- **Identificador:** AUT-50 (origens O019, O057, O281, O324).
- **Módulo e processo:** Prestação › RT (`PREST-RT-PREENCHIMENTO`, `PT-RESULTADOS-RELATORIO`, `GV-PREST-RT`,
  `EV-RT-SUGESTAO`).
- **Evidência:** só existe a sugestão por regra local (`gestao/viagens/relatorio.py:69-127`,
  `gestao/viagens/dominio/relatorio.py:117-220`, `gestao/viagens/resultados.py:99-115`); não há porta de IA no
  código (AUT-96).
- **Problema que resolve:** conclusão e medidas genéricas; redação manual demorada.
- **Pessoas beneficiadas:** operador; servidor (RT mais fiel ao que fez).
- **Gatilho:** clique "Rascunho (IA)" na tela do RT → tópico interno `viagens.rt.rascunho_ia` [novo].
- **Pré-condições:** porta única de IA com validador (AUT-96); gabarito de avaliação (AUT-91); relato
  (AUT-48) recomendado; **ADR nova** autorizando o envio desses dados estruturados a um provedor (a
  [ADR 0041](../../adr/0041-importacao-documental-e-fila-de-download.md) veda enviar **documentos** da
  importação a IA externa, linhas 19-20; aqui seriam dados estruturados, mas a decisão é institucional,
  D-10 do 10-5); provedor e orçamento (D8 do plano, "provedor de IA, modelo, orçamento mensal e política de
  dados"). Modelo local na VPS é inviável (AUT-98,
  [desempenho e custos](../desempenho-e-custos.md) §11.4).
- **Etapas:** contexto pela ferramenta de leitura `prestacao.contexto_rt` (sem CPF, valores bancários ou
  telefone); saída JSON `{campo, texto, fatos_usados[]}` só para atividade, conclusão, medidas e informações
  complementares; validação determinística no PCPR (todo número, data, município e nome próprio precisa estar
  no contexto; sem marcador; tamanho máximo); sugestão rotulada "Sugestão (IA) — revise" em `SugestaoTextoRT`
  [novo]; aplicar copia pelo `relatorio.salvar` de quem clicou; a declaração de revisão (R-RT-5) continua
  exigida.
- **Responsabilidade:** *sistema* — contexto, chamada ao modelo pela porta, validação, guarda, aplicação;
  *n8n* — **nenhuma** (a chamada sai do PCPR para concentrar mascaramento, custo e política,
  [desempenho e custos](../desempenho-e-custos.md) §11.3); *IA* — redigir rascunho a partir só do contexto
  dado. Nunca diária, custeio, km, assinante ou data.
- **Dados e permissões:** quem edita o RT; entrada do usuário e textos recuperados são dados, nunca
  instruções.
- **APIs existentes e necessárias:** nenhuma existe; porta única `gestao/integracoes/ia` (AUT-96; nome
  decidido, vale também para o 10-1), ferramenta `prestacao.contexto_rt`.
- **Participação humana:** obrigatória: aceitar, editar ou descartar; o RT é assinado.
- **Resultado esperado:** zero fato fora do contexto aplicado; tempo de redação menor (medir).
- **Falhas e recuperação:** IA indisponível ou resposta inválida → nenhuma sugestão (ou `recusada_validacao`
  registrada) e a regra local continua (10-5 §9); teto mensal atingido → fluxo desliga com motivo "orçamento".
- **Deduplicação:** uma sugestão por (RT, campo, impressão do contexto); repetir o pedido com o mesmo contexto
  devolve a mesma.
- **Cancelamento:** RT concluído para assinatura descarta sugestões pendentes.
- **Métricas:** % aplicadas, aplicadas com edição, recusadas pela validação; fatos fora do contexto
  aplicados (meta 0); custo por tarefa medido.
- **Custos:** por rascunho, ~5.000 tokens de entrada e ~1.500 de saída → ~US$ 0,0013 (Claude Haiku 5.5) a
  ~US$ 0,025 (Claude Sonnet 5.5) [estimativa sobre preços oficiais em
  <https://platform.claude.com/docs/en/about-claude/pricing>, consultados em 17/10/2026;
  [desempenho e custos](../desempenho-e-custos.md) §11.2]. Com 1 rascunho por viagem e 30 % de retrabalho
  (H8), 200 viagens por mês dão ~US$ 0,34 (Haiku) a ~US$ 6,50 (Sonnet) [estimativa]. Mais o gabarito de
  avaliação e o desenvolvimento M.
- **Dependências:** AUT-48, AUT-96, AUT-91; ADR nova; provedor e orçamento.
- **Prioridade e esforço:** média; M.
- **Cenários de aceite:** 10-5 §12, critério 17. Além dele:
  1. **Dado** a IA desligada, **quando** a pessoa pede rascunho, **então** recebe a sugestão da regra local.
  2. **Dado** um contexto sem informação de intercorrência, **quando** a IA propõe "não houve
     intercorrências", **então** a validação recusa a frase (coerente com AUT-49).
  3. **Dado** uma sugestão aplicada, **quando** se inspeciona a tabela do RT, **então** a autoria da gravação é
     da pessoa que clicou.
- **Desligamento e continuação manual:** chave `rascunho-rt-ia` e teto mensal de gasto; a pessoa escreve ou usa
  a regra local.
- **Maturidade:** **3** (provedor e custo); **4** se exigir aval institucional ou de LGPD.

<a id="aut-51"></a>
#### AUT-51 — Feriados estaduais e municipais no cálculo de dias úteis

> **Automação determinística suficiente · maturidade 2 · valor baixo · esforço P · trilha paralela P41.**
> Situação: VERIFICADA PARCIALMENTE — EXISTENTES os feriados nacionais fixos e móveis e o parâmetro
> `extras` nas funções de dia útil; INEXISTENTES o cadastro de feriados e a ligação dos chamadores.
> Sem fluxo próprio: esta ficha é o detalhe.

- **Identificador:** AUT-51 (origem O282).
- **Módulo e processo:** Prestação › prazos e data do RT (`GV-PREST-RT`).
- **Evidência:** `gestao/viagens/dominio/prestacao.py:1-7` (a docstring já prevê "feriado extra informado"
  e chama o cadastro da unidade de decisão pendente), `:38-51` (nacionais), `:63-86` (`dia_util`,
  `somar_dias_uteis` e `prazo_para_prestar` aceitam `extras`); `gestao/viagens/dominio/relatorio.py:94-101`
  (`data_do_documento` também aceita). **Nenhum chamador passa feriados extras:** `gestao/viagens/avisos.py:71`,
  `gestao/viagens/prestacao.py:212`, `gestao/viagens/exportacao.py:154` e `gestao/viagens/relatorio.py:338`.
  Não há modelo de feriado no cadastro.
- **Problema que resolve:** em semana de feriado estadual ou municipal, o prazo para prestar e a data máxima
  do RT saem um dia antes, o que gera cobrança e selo de "vencida" indevidos.
- **Pessoas beneficiadas:** servidor (não é cobrado antes da hora); operador (selos e abas corretos).
- **Gatilho:** cada cálculo de prazo (rotina diária, abas, planilha, data do RT).
- **Pré-condições:** decidir **quais** feriados contam: da sede da unidade? do município do servidor?
  ponto facultativo conta? (decisão D-PR5). O sistema não inventa calendário: o cadastro é mantido pelo gestor.
- **Etapas:** (1) cadastro `Feriado` [novo] em `gestao/cadastros` (data, abrangência estadual ou municipal,
  município, descrição, fonte), mantido pelo gestor com o padrão de cadastros existente; (2) consulta
  `feriados_extras(unidade, inicio, fim)`; (3) os quatro chamadores passam `extras`; (4) mudar o cadastro
  replaneja os lembretes de AUT-38 na rotina seguinte; versões já congeladas (AUT-46) não mudam.
- **Responsabilidade:** *sistema* — tudo; *n8n* — nenhuma; *IA* — nenhuma.
- **Dados e permissões:** cadastro só para gestor (policy de cadastros); leitura livre para o cálculo.
- **APIs existentes e necessárias:** existentes — as funções de domínio com `extras`. Necessárias — o modelo
  e a consulta.
- **Participação humana:** o gestor cadastra os feriados do ano.
- **Resultado esperado:** prazos e data do RT certos em semana de feriado local.
- **Falhas e recuperação:** feriado não cadastrado → comportamento de hoje; cadastro errado → corrigir e o
  cálculo seguinte já sai certo.
- **Deduplicação:** feriado único por (data, abrangência, município).
- **Cancelamento:** excluir o feriado volta ao cálculo anterior.
- **Métricas:** prestações marcadas como vencidas que deixam de estar depois do cadastro; feriados
  cadastrados por ano.
- **Custos:** desenvolvimento P.
- **Dependências:** decisão D-PR5. A regra "+3 dias úteis" é paridade com a referência e não tem fonte
  institucional confirmada (10-3 §8).
- **Prioridade e esforço:** baixa; P.
- **Cenários de aceite:**
  1. **Dado** prazo de saque numa quarta e feriado municipal cadastrado na quinta, **quando** o prazo para
     prestar é calculado, **então** a quinta não conta como dia útil.
  2. **Dado** nenhum feriado cadastrado, **quando** o cálculo roda, **então** o resultado é igual ao de hoje.
  3. **Dado** um RT já congelado, **quando** um feriado é cadastrado depois, **então** a data do documento
     congelado não muda.
- **Desligamento e continuação manual:** sem feriados cadastrados, vale o cálculo atual.
- **Maturidade:** **2**.

### 4.5 Recebimento pela importação documental

<a id="aut-52"></a>
#### AUT-52 — Recebimento de documentos devolvidos pelo servidor: portal e entrada autenticada na importação

> **Dependente de desenvolvimento · maturidade 2 · valor alto · esforço M · etapa 3, ordem 48.**
> Situação: VERIFICADA PARCIALMENTE — EXISTENTE a importação documental (fila com lease, OCR, separação,
> identificação, revisão); INEXISTENTE qualquer entrada pelo servidor. A deduplicação de recebimento passou no
> protótipo simulado (cenário T9, B1), mas por um canal fictício no formato de webhook: a leitura da caixa
> postal por IMAP e a deduplicação por `Message-ID` não foram exercitadas. Detalhe: [10-6](../fluxos/10-6-recebimento-de-documentos.md) inteiro.

- **Identificador:** AUT-52 (origens O062, O270).
- **Módulo e processo:** Documentos › recebimento (`DOC-IMPORTACAO-ENTRADA`, `GV-DOC-ASSINADO-MANUAL`).
- **Evidência:** entrada só pela "fitinha", com sessão e CSRF (`gestao/viagens/views_importacao.py:32-56`), e
  só para quem tem `change_oficio` (`gestao/viagens/importacao.py:31-35`); fila com lease
  (`importacao.py:160-182`); OCR local (`gestao/viagens/documentos/importador.py:200-270`); revisão privada de
  quem enviou (`views_importacao.py:92-96`, `importacao.py:248-252`); `ArquivoImportado.usuario` obrigatório
  (`gestao/viagens/models.py:1859`) sem vínculo usuário↔servidor. Correções ao contrato `/recebimentos` no
  10-6, anexo A.
- **Problema que resolve:** o operador baixa anexos de e-mail ou mensagem, arrasta na fitinha e responde à
  mão; não há registro de quem mandou, quando, nem em resposta a quê.
- **Pessoas beneficiadas:** servidor (devolve pelo link e recebe resposta clara); operador (os documentos
  entram sozinhos na mesma fila); gestão (tempo de entrada, vínculo errado).
- **Gatilho:** upload no portal pelo link pessoal (o próprio PCPR chama o serviço, **sem n8n**); e-mail na
  caixa dedicada lido pelo n8n e entregue por `POST /recebimentos` (AUT-08, maturidade 4); recebimento
  pela plataforma oficial do WhatsApp bloqueado (AUT-10), pronto e desligado pela WA-3 (AUT-174).
- **Pré-condições:** AUT-01, AUT-02, AUT-03, AUT-104; antivírus na entrada externa (AUT-112, maturidade 3;
  o GV exige em produção, 10-6 §2.2); regra do envio pelo próprio servidor (10-6 §7.3), que só vale como
  "enviado pelo servidor" — e só permite aplicação automática — quando o contato foi confirmado pelo próprio
  titular e o link de devolução passou pelo código de uso único do nível alto (AUT-02, etapa 6; AUT-03);
  contato só "conferido pelo operador" manda o documento à revisão.
- **Etapas:** 10-6 §7 — `MensagemRecebida` e `Recebimento` [novos], usuário técnico, universo de destinos
  restrito ao remetente, revisão pela unidade e não pelo dono do original, erros de infraestrutura separados
  dos de conteúdo, eventos `importacao.parte_aplicada` e `prestacao.documento_recebido`, resposta padronizada
  por `Comunicacao`.
- **Responsabilidade:** 10-6 §5 — *sistema* valida remetente, lê, identifica e aplica pelas regras existentes;
  *n8n* só lê a caixa, chama a API e transporta a resposta, sem ler ou classificar PDF; *IA* nenhuma na v1
  (AUT-57 é sugestão futura, AUT-61 é vetada).
- **Dados e permissões:** 10-6 §7.4–7.5; o servidor vê só os próprios envios; quarentena para remetente não
  verificado; guarda da quarentena e do texto da mensagem a decidir (D5 do 10-6, LGPD).
- **APIs existentes e necessárias:** existentes — `importacao.receber`, `aplicar`, `processar_importacoes`.
  Necessárias — `POST /recebimentos`, `GET /recebimentos/{id}` com as extensões do 10-6 §6.3; rota do portal.
- **Participação humana:** revisar partes ambíguas, confirmar substituições, liberar ou descartar quarentena.
- **Resultado esperado:** documento devolvido anexado à prestação certa ou em revisão com motivo, e o
  remetente informado do que aconteceu. Recebimento **não** é finalização nem assinatura válida.
- **Falhas e recuperação:** 10-6 §9 — duplicado, acima do limite, formato não suportado, PDF com senha, falha
  do conversor (não pede reenvio), documento de outra viagem, versão anterior, PDF sem assinatura.
- **Deduplicação:** cinco camadas do 10-6 §10.1 (mensagem e anexo, arquivo, conteúdo no destino, efeito,
  resposta).
- **Cancelamento:** 10-6 §10.2 ("enviei por engano" antes de associar; destinos cancelados saem do universo).
- **Métricas:** 10-6 §11 — vínculo errado (prioritária, meta 0 no corpus sintético), anexação automática,
  latência de entrada p95 ≤ 2 min (push) e ≤ 15 min (pull), respostas duplicadas 0.
- **Custos:** ~8,8 arquivos por viagem (hipótese H6) → ~440, ~1.760 e ~4.400 por mês nos cenários de 50, 200
  e 500 viagens [estimativa]; antivírus com cerca de 1 GiB de RAM na VPS [estimativa, a medir]; R$ 0 de
  serviço externo; desenvolvimento M sobre a fundação (G se for o primeiro fluxo a construí-la).
- **Dependências:** AUT-01, AUT-02, AUT-03, AUT-104, AUT-112; AUT-08 para o e-mail; B9 (complementa a
  tramitação oficial). Relacionado: AUT-123 (trazer do eProtocolo o ofício assinado e o despacho, maturidade 4).
- **Prioridade e esforço:** alta; M.
- **Cenários de aceite:** 10-6 §12, critérios 1 a 20; os essenciais são 1 (portal, caminho feliz), 2 (entrega
  duplicada), 4 (remetente não verificado), 6 (documento de outra viagem), 18 (pendência resolvida sem
  concluir) e 19 (desligamento).
- **Desligamento e continuação manual:** chaves `recebimento-canais`, `recebimento-portal` e
  `recebimento-aplicacao-automatica` (modo seguro: tudo vai à revisão) (10-6 §10.3); a fitinha continua
  como hoje.
- **Maturidade:** **2** pelo portal; e-mail 4 (AUT-08); WhatsApp oficial 5 para ativar (AUT-10, AUT-174).

<a id="aut-54"></a>
#### AUT-54 — Guardar o texto/OCR de cada parte importada

> **Automação determinística suficiente · maturidade 2 · valor médio · esforço P · trilha paralela P2
> (necessária antes da etapa 3).** Situação: PLANEJADA — o OCR roda e o texto é descartado. Sem fluxo
> próprio: esta ficha é o detalhe.

- **Identificador:** AUT-54 (origem O064).
- **Módulo e processo:** Documentos › importação (`DOC-IMPORTACAO-ENTRADA`).
- **Evidência:** o worker extrai texto e faz OCR (`gestao/viagens/documentos/importador.py:200-270`) e usa o
  texto para identificar (`gestao/viagens/importacao.py:209`), mas `ParteImportada` não tem campo de texto
  (`gestao/viagens/models.py:1883-1908`); a tela de leitura usa só a camada de texto do PDF do anexo
  (`gestao/viagens/leitura_anexos.py:248-296`), então digitalizados e fotos aparecem vazios. A parte já
  aponta o anexo que gerou (`ParteImportada.anexo`, `models.py:1897`).
- **Problema que resolve:** a leitura e a conferência não funcionam em documentos que já passaram por OCR;
  AUT-55, AUT-57 e AUT-58 precisam do texto.
- **Pessoas beneficiadas:** operador na etapa de leitura e conferência.
- **Gatilho:** o worker termina de identificar uma parte.
- **Pré-condições:** política de guarda: o texto contém CPF e nomes (decisão D-PR6; hoje o original
  aceito não tem exclusão automática, 10-6 D5).
- **Etapas:** (1) `ParteImportada.texto` [novo] gravado na mesma transação em que a parte é criada;
  (2) `leitura_anexos.ler` usa o texto da parte quando o PDF do anexo não tem camada de texto; (3) o texto
  nunca vai a log, evento ou API externa.
- **Responsabilidade:** *sistema* — tudo; *n8n* — nenhuma; *IA* — nenhuma.
- **Dados e permissões:** mesmas policies do anexo e da revisão; nada novo é exposto.
- **APIs existentes e necessárias:** existentes — `processar_importacoes`, `leitura_anexos.ler`. Nenhuma API.
- **Participação humana:** nenhuma nova.
- **Resultado esperado:** comprovante em foto importado mostra valor e data na leitura.
- **Falhas e recuperação:** OCR ruim → texto ruim, a leitura mostra o que achou e a pessoa confere como hoje;
  partes antigas sem texto → comportamento atual.
- **Deduplicação:** um texto por parte (a parte já é única por arquivo e início).
- **Cancelamento:** apagar a parte apaga o texto (mesma guarda).
- **Métricas:** % de anexos importados com leitura útil na tela de conferência, antes e depois.
- **Custos:** desenvolvimento P; espaço em disco pequeno — o importador aceita até 100 páginas por arquivo
  e, com algo como 2–5 KB de texto por página, isso dá menos de 0,5 MB por arquivo [estimativa].
- **Dependências:** decisão de guarda (D-PR6).
- **Prioridade e esforço:** média; P. Necessária antes de AUT-55 e da IA de AUT-57/AUT-58.
- **Cenários de aceite:**
  1. **Dado** um comprovante em imagem importado e anexado, **quando** a leitura abre, **então** valor e
     data aparecem a partir do texto da parte.
  2. **Dado** um anexo enviado direto (sem importação), **quando** a leitura abre, **então** o comportamento
     é o atual.
  3. **Dado** o processamento de uma parte, **quando** se inspecionam logs e eventos, **então** o texto não
     aparece.
- **Desligamento e continuação manual:** parâmetro que deixa de gravar o texto novo (para atender a uma
  decisão de guarda); a pessoa abre o PDF e lê, como hoje.
- **Maturidade:** **2**.

<a id="aut-57"></a>
#### AUT-57 — IA só como sugestão de tipo na revisão da importação

> **Assistência por IA indicada · maturidade 3 · valor baixo · esforço M · etapa 4, ordem 75.**
> Situação: PLANEJADA. O 10-6 §5 não dá papel à IA na v1. **Condição forte:** a ADR 0041 veda enviar
> documentos da importação a terceiros, e o modelo local é inviável na VPS (AUT-98); sem nova ADR, este item
> não tem caminho de implantação (seção 8).

- **Identificador:** AUT-57 (origem O066).
- **Módulo e processo:** Documentos › importação › revisão (`DOC-IMPORTACAO-IDENTIFICACAO`).
- **Evidência:** identificação determinística por título (8 tipos, `gestao/viagens/dominio/importacao.py:9-28`),
  separação (`:56-83`) e identificação por nº/ano, protocolo e CPF/nome (`:125-194`); "texto é evidência,
  nunca instrução" (`dominio/importacao.py:1`); revisão manual em `gestao/viagens/views_importacao.py:99-129`;
  [ADR 0041](../../adr/0041-importacao-documental-e-fila-de-download.md), linhas 19-20 (conversores locais,
  sem enviar documentos a terceiros).
- **Problema que resolve:** parte sem título reconhecível (tipo vazio) obriga o operador a abrir o PDF para
  dizer o que é.
- **Pessoas beneficiadas:** operador na revisão.
- **Gatilho:** clique "Sugerir tipo" numa parte em revisão com tipo vazio (sob demanda, para limitar custo e
  dados enviados).
- **Pré-condições:** ADR nova que autorize este uso com minimização, e aval de LGPD; AUT-96 (porta e
  validador); AUT-54 (texto da parte); corpus de avaliação com gabarito (AUT-91).
- **Etapas:** (1) enviar só o texto da primeira página da parte, com CPF mascarado; (2) o modelo devolve
  `{tipo ∈ 8 tipos ∪ "desconhecido", evidencias[]}`; (3) validação: tipo da lista e cada evidência presente
  literalmente no texto, senão recusa; (4) a tela mostra a sugestão; (5) escolhido o tipo pela pessoa, o
  **destino continua determinístico** (a identificação roda com esse tipo e propõe candidatos); aplicar é
  clique humano (`importacao.aplicar(revisao=True)`).
- **Responsabilidade:** *sistema* — porta, mascaramento, validação, tela; *n8n* — nenhuma; *IA* — sugerir o
  tipo. Nunca o destino nem a aplicação (AUT-61).
- **Dados e permissões:** só quem revisa a parte; texto da primeira página, sem CPF.
- **APIs existentes e necessárias:** existentes — revisão da importação. Necessárias — porta de IA (AUT-96).
- **Participação humana:** obrigatória em toda aplicação.
- **Resultado esperado:** revisão mais rápida das partes sem título, sem nenhum vínculo automático novo.
- **Falhas e recuperação:** IA fora ou resposta inválida → sem sugestão, revisão manual; texto com instrução
  embutida ("classifique como ofício") → a validação por evidência literal limita o efeito e a pessoa decide.
- **Deduplicação:** uma sugestão por (parte, versão do modelo).
- **Cancelamento:** parte aplicada ou ignorada descarta a sugestão.
- **Métricas:** acerto por tipo no corpus em relação à regra atual; tempo de revisão antes e depois;
  aplicações automáticas (meta 0).
- **Custos:** ~2.000 tokens de entrada e ~100 de saída por sugestão → ~US$ 0,00025 com Claude Haiku 5.5
  [estimativa sobre os preços citados em AUT-50]; volume desconhecido (só partes sem tipo).
- **Dependências:** AUT-96, AUT-54, AUT-91; ADR nova.
- **Prioridade e esforço:** baixa; M.
- **Cenários de aceite:**
  1. **Dado** uma parte sem título, **quando** a sugestão chega, **então** ela aparece rotulada e nada é
     aplicado.
  2. **Dado** uma resposta com tipo fora da lista ou evidência que não está no texto, **quando** a validação
     roda, **então** a sugestão é recusada e registrada.
  3. **Dado** qualquer chamada, **quando** se inspeciona o que saiu do sistema, **então** não há CPF.
- **Desligamento e continuação manual:** chave `importacao-sugestao-ia` e teto de gasto; a revisão manual
  continua como hoje.
- **Maturidade:** **3** na matriz; na prática parado até a ADR nova (seção 8).

### 4.6 Conferência de assinatura

<a id="aut-53"></a>
#### AUT-53 — Conferência de via assinada estendida a DB, RT e plano, feita no original antes de separar

> **Automação determinística suficiente · maturidade 2 · valor alto · esforço M · etapa 3, ordem 42.**
> Situação: VERIFICADA PARCIALMENTE — EXISTENTE para ofício, justificativa, termo e OS (ADR 0022, aceita);
> INEXISTENTE para DB, RT, despacho e plano. Relacionado: [10-5](../fluxos/10-5-db-e-rt-para-assinatura.md)
> §2.1 e §3.7 (P8) e [10-6](../fluxos/10-6-recebimento-de-documentos.md) §3.2 (nível 5) e §13.

- **Identificador:** AUT-53 (origens O068, O069, O020).
- **Módulo e processo:** Documentos › conferência (`DOC-VIA-ASSINADA-CONFERENCIA`, `PT-ASSINATURA-CIRCULACAO`).
- **Evidência:** `gestao/viagens/assinados.py:128-149` e `:236-268` gravam `ViaAssinada.conferencia`
  (`gestao/viagens/models.py:637`); a leitura acha campo `/Sig`, CN do certificado **sem validar a cadeia** e
  carimbos de eProtocolo, ICP e gov.br (`gestao/viagens/documentos/leitura.py:75-124`,
  `gestao/viagens/dominio/conferencia.py:23-185`); `AnexoPrestacao` não tem campo de conferência
  (`models.py:1605-1660`); ao separar partes, o PDF perde os campos `/Sig` (`importador.py:245-255`); o aviso
  "Documentos assinados recebidos" só conta anexos (`gestao/viagens/avisos.py:76-86`); a importação não
  reconhece "PLANO DE TRABALHO" e `ViaAssinada` não tem tipo plano (`dominio/importacao.py:9-28`,
  `models.py:607-640`).
- **Problema que resolve:** para saber se o RT ou o DB que voltou está assinado, e por quem, a pessoa abre o
  PDF; processos com vários documentos assinados perdem a evidência ao serem separados.
- **Pessoas beneficiadas:** operador e conferência da prestação.
- **Gatilho:** anexar RT, DB ou despacho assinado (upload ou importação); processar um original com assinaturas
  antes da separação; anexar plano assinado.
- **Pré-condições:** decisão de quem assina o DB (D-01 do 10-5). Para o plano: instantâneo do plano emitido
  (AUT-21) para comparar "dados mudaram".
- **Etapas:** (1) `AnexoPrestacao.conferencia` [novo, JSON] preenchido em `anexos.anexar` com
  `leitura.conferir(Esperado(...))`: RT espera o servidor da linha; DB espera `diario.motorista`; despacho, o
  ofício e o protocolo; (2) no importador, ler os campos `/Sig` do PDF **inteiro** antes de separar e
  atribuir cada assinatura à página do widget, devolvendo por parte a lista de assinantes; (3) plano:
  `ViaAssinada.Tipo.PLANO`, título "PLANO DE TRABALHO" na identificação e "assinado, mas os dados mudaram"
  pela impressão (AUT-21); (4) o aviso diário passa a dizer "assinado por X" ou "sem assinatura detectada";
  (5) nunca bloqueia e nunca afirma validade jurídica: "presença conferida" não é "assinatura válida"
  (10-6 §3.2, D13).
- **Responsabilidade:** *sistema* — tudo (pypdf, regra pura); *n8n* — nenhuma; *IA* — nenhuma.
- **Dados e permissões:** nomes e CN lidos são dados pessoais; aparecem só para quem já vê a prestação.
- **APIs existentes e necessárias:** existentes — `leitura.conferir`, `assinados.*`. Nenhuma API externa.
- **Participação humana:** ler o resultado e decidir; a conferência é apoio, não decisão.
- **Resultado esperado:** o aviso de "assinados recebidos" diz se o documento certo foi assinado por quem
  devia, sem abrir o PDF.
- **Falhas e recuperação:** digitalizado sem camada de texto → "não verificada" (com AUT-54 os carimbos de
  texto passam a ser lidos); assinatura em página diferente da esperada → aviso.
- **Deduplicação:** uma conferência por anexo (recalculada se o anexo for substituído).
- **Cancelamento:** anexo removido leva a conferência junto.
- **Métricas:** % de RT/DB com conferência "presença conferida"; avisos "sem assinatura" que se confirmaram;
  aberturas de PDF evitadas (amostra).
- **Custos:** desenvolvimento M.
- **Dependências:** D-01 do 10-5; AUT-21 para o plano. Pré-requisito de AUT-46.
- **Prioridade e esforço:** alta; M.
- **Cenários de aceite:**
  1. **Dado** PDFs sintéticos com campo `/Sig`, com carimbo do eProtocolo, sem assinatura e com nome
     diferente do esperado, **quando** são anexados como RT assinado, **então** os avisos correspondem a cada
     caso e nenhum anexo é recusado.
  2. **Dado** um PDF com dois documentos assinados digitalmente em páginas diferentes, **quando** é importado
     e separado, **então** cada parte informa o próprio assinante.
  3. **Dado** um plano assinado importado, **quando** a identificação roda, **então** o candidato é o plano
     certo e a aplicação passa por revisão.
- **Desligamento e continuação manual:** não precisa de chave (só informa); a pessoa continua abrindo o PDF.
- **Maturidade:** **2**.

### 4.7 Comprovantes

<a id="aut-55"></a>
#### AUT-55 — Comprovante: valor, data e operação na entrada e casamento pela janela de saque

> **Automação determinística suficiente · maturidade 2 · valor médio · esforço P · etapa 3, ordem 54.**
> Situação: VERIFICADA PARCIALMENTE — EXISTENTES a leitura do comprovante e o botão "Usar no comprovante";
> o comprovante importado entra sem valor, e sem nº do ofício nunca casa sozinho. Relacionado:
> [10-6](../fluxos/10-6-recebimento-de-documentos.md) §2.1 e §13 (melhoria que não bloqueia o fluxo).

- **Identificador:** AUT-55 (origens O065, O070).
- **Módulo e processo:** Documentos › comprovantes (`DOC-IMPORTACAO-IDENTIFICACAO`, `PREST-ANEXOS`).
- **Evidência:** `importacao.aplicar` anexa o comprovante sem valor, data nem operação
  (`gestao/viagens/importacao.py:306-313`); os destinos de comprovante não têm data
  (`importacao.py:50-67`) e a identificação exige data quando falta referência
  (`gestao/viagens/dominio/importacao.py:173-181`); `leitura_anexos.ler_comprovante` já extrai autorização,
  data, valor e operação (`gestao/viagens/leitura_anexos.py:179-245`); a divergência "soma ≠ diária" fica
  calada quando algum comprovante não tem valor (`gestao/viagens/anexos.py:99-109`). Defeito encontrado
  pela leitura: "Usar no comprovante" envia o rótulo lido em minúscula e com acento; "Depósito" e
  "Transferência" não casam com `deposito`/`transferencia` de `AnexoPrestacao.Operacao` e o serviço os
  descarta (Pix, TED, DOC e Saque passam) (`anexos.py:212`, `gestao/viagens/models.py:1618-1624`,
  `leitura_anexos.py:46-47`, `gestao/viagens/templates/viagens/prestacao/leitura.html:110`). Referência
  EV: casa por CPF/nome, valor ≤ diária e data na janela de saque
  (`ref/ev-implantado/viagens_prestacoes/importacao/analise.py:333-341`).
- **Problema que resolve:** comprovante de banco não cita o ofício e cai sempre na revisão; a conferência
  valor × diária depende de clique.
- **Pessoas beneficiadas:** operador; servidor (lembretes param assim que o comprovante entra, AUT-38).
- **Gatilho:** aplicação de uma parte do tipo comprovante; identificação de um comprovante sem referência.
- **Pré-condições:** AUT-54 (texto da parte); nº, liberação e prazo preenchidos (AUT-36).
- **Etapas:** (1) na aplicação, `ler_comprovante` sobre o texto da parte e envio de valor, data e operação
  normalizada para os valores de `AnexoPrestacao.Operacao`, marcados "lidos automaticamente" para conferência;
  (2) corrigir a normalização do botão "Usar no comprovante"; (3) destinos de comprovante ganham a janela
  (liberação até prazo de saque + folga) e a diária liberada; (4) sem referência, só aplica sozinho se CPF ou
  nome único + data na janela + valor ≤ diária liberada, entre prestações **não finalizadas** e com **um único**
  candidato; senão, revisão com os candidatos.
- **Responsabilidade:** *sistema* — tudo; *n8n* — nenhuma; *IA* — nenhuma (AUT-58 é o complemento por IA,
  só como sugestão).
- **Dados e permissões:** os da importação; valor e data são do próprio comprovante.
- **APIs existentes e necessárias:** existentes — `ler_comprovante`, `anexos.anexar`, `editar_comprovante`.
  Nenhuma API externa.
- **Participação humana:** conferir os valores lidos; decidir os casos com mais de um candidato.
- **Resultado esperado:** comprovante inequívoco anexado sem revisão, já com valor; a divergência volta a
  aparecer.
- **Falhas e recuperação:** a diária liberada é **calculada** (`prestacao.py:109-124`), não o valor pago:
  o critério "valor ≤ diária" só exclui o impossível e não prova nada; homônimos, duas viagens na mesma janela
  e saque parcial em vários comprovantes vão à revisão; segundo comprovante da mesma pessoa vai à revisão
  (D7 do 10-6).
- **Deduplicação:** a da importação (hash; parte terminal não reaplica).
- **Cancelamento:** remover o anexo replaneja os lembretes (AUT-38).
- **Métricas:** vínculo errado (meta 0 no corpus sintético; erro de vínculo é a falha prioritária, 10-6 §11);
  % de comprovantes aplicados sem revisão; comprovantes com valor preenchido.
- **Custos:** desenvolvimento P.
- **Dependências:** AUT-54; dados de AUT-36.
- **Prioridade e esforço:** média; P.
- **Cenários de aceite:**
  1. **Dado** comprovante Pix com CPF do servidor, data dentro da janela e valor menor que a diária, e uma
     única prestação aberta dele, **quando** é importado, **então** é anexado com valor, data e operação
     "pix".
  2. **Dado** duas prestações abertas do mesmo servidor com janelas sobrepostas, **quando** o comprovante
     chega, **então** vai à revisão com os dois candidatos.
  3. **Dado** valor acima da diária liberada, **quando** chega, **então** vai à revisão.
  4. **Dado** "Usar no comprovante" com operação "Transferência", **quando** grava, **então** o valor salvo é o
     da lista de operações e não é descartado.
- **Desligamento e continuação manual:** parâmetro que desliga só a aplicação automática de comprovante sem
  referência (tudo vai à revisão); a leitura com clique continua.
- **Maturidade:** **2**.

<a id="aut-58"></a>
#### AUT-58 — IA extraindo campos de comprovante e NFS-e de layout desconhecido (só sugestão)

> **Assistência por IA indicada · maturidade 3 · valor baixo · esforço M · etapa 4, ordem 76.**
> Situação: PLANEJADA. Mesma condição forte de AUT-57 (ADR 0041 e AUT-98). A parte de NFS-e é do módulo
> Coffee e está também na [ficha de plataforma e módulos](plataforma-e-modulos.md).

- **Identificador:** AUT-58 (origens O071, O224).
- **Módulo e processo:** Documentos › comprovantes; Coffee › leitura de nota fiscal (`PREST-LEITURA-CONFERENCIA`,
  `CB-LEITURA-PDFS`).
- **Evidência:** a leitura do comprovante é por expressões genéricas (`gestao/viagens/leitura_anexos.py:179-245`);
  a leitura de NFS-e, OB e contrato do Coffee é só por pypdf, sem OCR (`gestao/coffee/dominio_leitura.py:76-157`,
  `gestao/coffee/pdfs.py:62-171`); as heurísticas foram testadas só com textos sintéticos.
- **Problema que resolve:** layouts que as regras não leem (aplicativos de banco, notas municipais
  diferentes) ficam sem sugestão e a pessoa digita.
- **Pessoas beneficiadas:** operador de viagens; equipe do Coffee.
- **Gatilho:** só quando a leitura determinística não acha valor (comprovante) ou número/valor/CNPJ (nota), e
  sob demanda na tela.
- **Pré-condições:** AUT-54 (texto); AUT-96 (porta e validador); ADR nova e aval de LGPD; minimização: só a
  página relevante, sem CPF.
- **Etapas:** (1) texto da página → modelo → JSON `{valor, data, operacao, autorizacao}` (comprovante) ou
  `{numero, valor, cnpj}` (nota); (2) validação: formato por expressão regular, valor presente literalmente no
  texto, e para comprovante valor ≤ diária liberada; (3) a tela mostra como sugestão; a pessoa clica "usar";
  (4) os avisos determinísticos de sempre continuam valendo.
- **Responsabilidade:** *sistema* — porta, validação, tela; *n8n* — nenhuma; *IA* — extrair campos como
  sugestão. Nunca grava.
- **Dados e permissões:** os da tela de leitura de cada módulo.
- **APIs existentes e necessárias:** existentes — leituras determinísticas. Necessária — porta de IA (AUT-96).
- **Participação humana:** obrigatória para gravar qualquer valor.
- **Resultado esperado:** sugestão útil nos layouts não cobertos, sem valor aceito sem leitura humana.
- **Falhas e recuperação:** valor sugerido que não está no texto → recusado pela validação; IA fora → tela
  como hoje.
- **Deduplicação:** uma sugestão por (anexo, versão do modelo).
- **Cancelamento:** anexo removido descarta a sugestão.
- **Métricas:** acerto por campo contra gabarito (corpus de comprovantes e notas anonimizados); gravações
  sem confirmação (meta 0).
- **Custos:** ~1.500 tokens de entrada e ~150 de saída por sugestão → cerca de US$ 0,0002 com Claude Haiku 5.5
  [estimativa sobre os preços citados em AUT-50]; volume desconhecido.
- **Dependências:** AUT-54, AUT-96; ADR nova.
- **Prioridade e esforço:** baixa; M.
- **Cenários de aceite:**
  1. **Dado** um comprovante cujo valor a regra não acha, **quando** a pessoa pede sugestão, **então** o valor
     aparece como sugestão e nada é gravado.
  2. **Dado** uma resposta com valor que não está no texto, **quando** a validação roda, **então** a sugestão é
     recusada.
- **Desligamento e continuação manual:** chave por módulo e teto de gasto; digitação como hoje.
- **Maturidade:** **3** na matriz; na prática parado até a ADR nova (seção 8).

### 4.8 Carimbo do nº da solicitação

<a id="aut-56"></a>
#### AUT-56 — Posição automática do carimbo pela linha do servidor no PDF

> **Automação determinística suficiente · maturidade 2 · valor médio · esforço P · trilha paralela P21.**
> Situação: VERIFICADA PARCIALMENTE — EXISTENTE o carimbo com posição manual por servidor; a posição
> automática ficou de fora na migração. Sem fluxo próprio: esta ficha é o detalhe.

- **Identificador:** AUT-56 (origem O072).
- **Módulo e processo:** Prestação › carimbo do nº da solicitação no ofício assinado (`PREST-CARIMBO`).
- **Evidência:** `gestao/viagens/carimbo.py:1-8` (a posição automática "lia o texto do PDF e fica de fora"),
  `:40-61` (`posicionar`: página e posição em frações, por servidor), `:83-104` (o carimbo é desenhado na hora
  sobre a via assinada, que não muda no disco), `:106` (pendência quando falta); `docs/migration/prestacao.md:79-89`.
  Referência GV: posição pelo texto do PDF (`ref/gv/prestacoes_contas/carimbo_services.py:102-150`).
- **Problema que resolve:** o operador informa página e posição em % para cada servidor.
- **Pessoas beneficiadas:** operador.
- **Gatilho:** anexar a via assinada do ofício ou abrir "Ajustar posição do número".
- **Pré-condições:** via assinada com camada de texto (assinatura digital no eProtocolo preserva o texto do
  PDF gerado pelo sistema; via digitalizada não tem).
- **Etapas:** (1) extrair o texto com coordenadas (pypdf, `visitor_text`) da via assinada; (2) achar, por
  servidor, a linha da tabela pelo CPF (com ou sem máscara) ou pelo nome; (3) achar a coluna do nº da
  solicitação pelo cabeçalho do modelo do ofício; (4) propor página e posição para todos; (5) a prévia mostra
  os carimbos e a pessoa confirma tudo com um clique ou ajusta um a um; (6) sem texto ou sem achar a linha, cai
  no ajuste manual de hoje.
- **Responsabilidade:** *sistema* — tudo; *n8n* — nenhuma; *IA* — nenhuma (AUT-63).
- **Dados e permissões:** `pode_editar_equipe_prestacao` (como `posicionar`).
- **APIs existentes e necessárias:** existentes — `carimbo.posicionar`, `carimbado`. Nenhuma API.
- **Participação humana:** confirmar na prévia.
- **Resultado esperado:** um clique para carimbar a equipe toda quando a via tem texto.
- **Falhas e recuperação:** página extra inserida pelo eProtocolo (folha de assinaturas) → a busca percorre
  todas as páginas; nome repetido → usa o CPF; não achou → manual.
- **Deduplicação:** um carimbo por (via, servidor), já garantido (`update_or_create`, `carimbo.py:55-60`).
- **Cancelamento:** via revogada leva os carimbos (comportamento atual).
- **Métricas:** % de servidores carimbados sem ajuste; meta proposta: posição a menos de 2 % da manual em 95 %
  dos ofícios gerados pelo sistema (a medir).
- **Custos:** desenvolvimento P.
- **Dependências:** nenhuma.
- **Prioridade e esforço:** média; P.
- **Cenários de aceite:**
  1. **Dado** uma via assinada no eProtocolo com a tabela da equipe, **quando** a posição automática roda,
     **então** cada servidor recebe página e posição na sua linha, e nada é gravado antes da confirmação.
  2. **Dado** uma via digitalizada sem texto, **quando** roda, **então** a tela oferece o ajuste manual.
- **Desligamento e continuação manual:** parâmetro que esconde a proposta; o ajuste manual continua.
- **Maturidade:** **2**.

### 4.9 Não recomendadas atualmente (maturidade 5)

Fichas curtas: nada será implantado, então os campos de execução (gatilho, etapas, APIs, falhas,
deduplicação, métricas, custos, aceite) não se aplicam. Cada uma traz identificador, processo, evidência,
justificativa, o que faria a avaliação mudar, a continuação manual e a maturidade.

<a id="aut-59"></a>
#### AUT-59 — Assinatura eletrônica simples por link feita pelo próprio sistema

> **Inadequada ou inviável atualmente · maturidade 5 · valor médio.** Situação: só na referência GV.
> Detalhe: [10-5](../fluxos/10-5-db-e-rt-para-assinatura.md) §2.2, §13 e decisão D-03.

- **Identificador e processo:** AUT-59 (origem O061) · Prestação › assinatura (`PREST-DOCS-ENVIO-ASSINATURA`).
- **Evidência:** o GV em produção assina RT e DB por link público, com token cifrado e hash, confirmação do
  nome e do CPF completo, 5 tentativas e bloqueio de 15 min, e carimba no PDF uma assinatura desenhada ou em
  fonte manuscrita (`ref/gv/prestacoes_contas/assinatura_services.py:1-9`, `:93-147`, `:187-195`); o EV
  **removeu** o recurso (`ref/ev-implantado/viagens_prestacoes/migrations/0006_remove_assinatura_eletronica.py`);
  o sistema novo não assina nada.
- **Justificativa:** a validade jurídica dessa assinatura e a verificação de identidade dependem de decisão
  institucional (D-03 do 10-5); a assinatura digital de ofícios já é feita no eProtocolo (decisão registrada
  no GV); assinar é ação irreversível que a ADR 0020 deixa para pessoa. O caminho recomendado é **assinar
  fora** (eProtocolo, gov.br ou física) e devolver pelo portal (AUT-47, AUT-52), com conferência (AUT-53).
- **O que faria mudar:** decisão jurídica formal sobre o tipo de assinatura aceito para DB e RT. Uma
  assinatura com validade reconhecida feita pelo sistema seria integração institucional (maturidade 4).
- **Desligamento e continuação manual:** não há o que desligar; assinatura externa e devolução, como hoje.
- **Maturidade:** **5**.

<a id="aut-60"></a>
#### AUT-60 — Finalização automática da prestação

> **Inadequada ou inviável atualmente · maturidade 5 · valor baixo.**

- **Identificador e processo:** AUT-60 (origem O074) · Prestação › finalização (`PREST-PENDENCIAS-FINALIZACAO`).
- **Evidência:** finalizar grava `finalizada_em` e a justificativa quando há pendência
  (`gestao/viagens/prestacao.py:299-364`); com a equipe toda finalizada, diário, RT e anexos travam
  (`gestao/viagens/diario.py:46-48`); a indicação "pronta para finalizar" já existe.
- **Justificativa:** finalizar trava documentos e é decisão de quem confere; a pendência pode ser aceita com
  justificativa, o que só uma pessoa avalia. A automação só mostra o que falta (AUT-39) e publica o evento
  quando a pessoa finaliza (`prestacao.concluida`, 10-3 §3.5, E3).
- **O que faria mudar:** nada previsto; é ato de conferência.
- **Desligamento e continuação manual:** finalização humana, como hoje.
- **Maturidade:** **5**.

<a id="aut-61"></a>
#### AUT-61 — IA decidindo o destino dos documentos importados

> **Inadequada ou inviável atualmente · maturidade 5 · valor baixo.** Detalhe:
> [10-6](../fluxos/10-6-recebimento-de-documentos.md) §1 (fora do escopo) e §5.

- **Identificador e processo:** AUT-61 (origem O329) · Documentos › importação (`EV-IMPORTACAO-PROCESSO`).
- **Evidência:** a identificação por protocolo, nº/ano e CPF/nome é determinística e já existe
  (`gestao/viagens/dominio/importacao.py:125-194`), com aplicação só de destino único e revalidação
  (`gestao/viagens/importacao.py:229-233`, `:243-323`); a referência EV também decide por regras
  (`ref/ev-implantado/viagens_prestacoes/importacao/analise.py:1-40`).
- **Justificativa:** anexar no lugar errado tem efeito na prestação e é a falha prioritária da importação
  (10-6 §11); a regra atual é auditável; a ADR 0041 veda enviar documentos da importação a terceiros. A IA fica
  restrita à sugestão de tipo na revisão (AUT-57).
- **O que faria mudar:** nada previsto; mesmo uma IA com bom acerto continuaria como sugestão.
- **Desligamento e continuação manual:** regras atuais e revisão humana.
- **Maturidade:** **5**.

<a id="aut-62"></a>
#### AUT-62 — Km lido por foto do hodômetro

> **Inadequada ou inviável atualmente · maturidade 5 · valor baixo.** Detalhe:
> [10-4](../fluxos/10-4-link-de-km-na-vespera.md) §5.3.

- **Identificador e processo:** AUT-62 (origem O321) · Prestação › Diário de Bordo (`EV-DIARIO-LINK-KM`).
- **Evidência:** nenhum dos sistemas lê foto do painel; o EV não pede foto do hodômetro
  (`EV-DIARIO-LINK-KM`, lacunas da leitura) e o sistema novo não tem link de km (AUT-40).
- **Justificativa:** erro de leitura viraria dado oficial do DB, com ganho pequeno sobre a digitação por
  trecho no link (AUT-40); exigiria ADR, análise de LGPD (foto) e provedor. O 10-4 e a matriz dão 5
  (inadequada ou inviável atualmente), porque a recomendação é não fazer (divergência antiga, resolvida).
- **O que faria mudar:** só como proposta que o motorista confirma, com a foto guardada como evidência.
- **Desligamento e continuação manual:** digitação por trecho no link ou pelo operador.
- **Maturidade:** **5**.

<a id="aut-63"></a>
#### AUT-63 — IA no carimbo do nº da solicitação

> **Inadequada ou inviável atualmente · maturidade 5 · valor baixo.**

- **Identificador e processo:** AUT-63 (origem O286) · Prestação › carimbo (`GV-PREST-DOCUMENTOS-CARIMBO`).
- **Evidência:** o carimbo é desenho de texto em posição conhecida sobre a via assinada
  (`gestao/viagens/carimbo.py:68-104`); a referência GV acha a posição lendo o texto do PDF, sem IA
  (`ref/gv/prestacoes_contas/carimbo_services.py:102-150`).
- **Justificativa:** posição e texto são determinísticos; a âncora pelo texto do PDF (AUT-56) resolve e é
  auditável. IA não acrescenta.
- **O que faria mudar:** nada previsto.
- **Desligamento e continuação manual:** AUT-56 e o ajuste manual.
- **Maturidade:** **5**.

---

## 5. Pacote e envio ao financeiro (sem item próprio neste grupo)

A matriz não tem um AUT do grupo para o pacote final nem para o envio ao financeiro. O que existe, o que
este grupo muda e onde está o resto:

| Parte | Hoje | O que muda e onde |
|---|---|---|
| Pacote final por servidor (PDF) e ZIP da equipe | EXISTENTE, gerado por GET (`gestao/viagens/pacote_prestacao.py:28-158`, `gestao/viagens/views_anexos.py:115-147`); usa o assinado anexado, senão **gera de novo** e cria RT ou diário se faltarem (`pacote_prestacao.py:84-92`) | Com AUT-46, usa o assinado aceito ou, na falta, o PDF **congelado** da versão vigente, sem regenerar (10-5 §10). Com AUT-53, mostra se cada peça tem assinatura detectada |
| Envio ao financeiro, aprovação e devolução | EXISTENTE **só como registro digitado** (`gestao/viagens/prestacao.py:368-420`; campos em `gestao/viagens/models.py:1461-1465`); sem outbox; `enviar` usa `.update()` (`prestacao.py:386`) | Eventos de ciclo (finalizada, enviada, aprovada, devolvida, concluída): AUT-100 ([plataforma e módulos](plataforma-e-modulos.md)); `prestacao.concluida` já está no envelope e é publicado quando uma pessoa finaliza (10-3 §3.5, E3) |
| Juntar o pacote ao processo e pedir assinatura no eProtocolo | INEXISTENTE | AUT-122, maturidade 4, com aprovação humana (ADR 0020: ação irreversível) — [13](../fluxos/13-integracoes-institucionais.md) |
| Saber se o financeiro aprovou ou devolveu | INEXISTENTE (a consulta de andamento do eProtocolo é simulada, `docs/migration/prestacao.md:183`) | AUT-120 (consulta, maturidade 3) e AUT-121 (interpretar o andamento como **sugestão** de marco, maturidade 4): aprovar e devolver continuam humanos |
| Registro de **qual** pacote foi entregue | INEXISTENTE (lacuna de `PREST-PACOTE`) | A matriz juntou isso a AUT-122. Esta ficha observa que guardar o SHA-256 e a lista de peças do pacote no momento de `prestacao.enviar` é regra interna, determinística e de maturidade 2, que **não** depende do eProtocolo. Decisão D-PR7 |
| Finalizar sozinho | — | Não recomendado (AUT-60) |

Envio ao financeiro é tramitação oficial: pelo Decreto 7.304/2021 (B9), fica no eProtocolo. Nenhuma
automação deste grupo envia, aprova ou devolve prestação.

---

## 6. Ordem sugerida dentro do grupo

Segue a matriz (seção 9) e o [plano](../plano-implantacao.md); só explicita o que pode começar antes.

1. **Já, sem n8n nem fundação (trilha paralela):** AUT-54 (P2, necessária antes da etapa 3) → AUT-49 (P20) →
   AUT-45 (P19) → AUT-42 (P18) → AUT-56 (P21) → AUT-51 (P41, depois da decisão D-PR5). Também podem ser
   antecipadas, por não dependerem da fundação: a parte A1 de AUT-36 (função de domínio e testes, com a
   correção da aba "Saque vencendo"), o limite de km de AUT-44 e AUT-53.
2. **Pedidos institucionais que saem já (etapa 0):** SMTP e remetente (AUT-04), caixa postal (AUT-08),
   uso do contato dos servidores (AUT-02), texto oficial do aviso (D1 do 10-3), tipo de assinatura aceito para
   DB e RT (D-03 do 10-5).
3. **Etapa 2, com a fundação:** AUT-36 (A2) → AUT-37 → AUT-38 → AUT-39.
4. **Etapa 3:** AUT-53 → AUT-40 → AUT-41 → AUT-52 → AUT-43 e AUT-44 → AUT-46 → AUT-47 → AUT-55 → AUT-48.
5. **Etapa 4, depois da ADR de IA, do provedor e do gabarito:** AUT-50 → AUT-57 → AUT-58.
6. **Fora do plano:** AUT-59 a AUT-63.

---

## 7. Decisões a confirmar

**Novas, desta ficha:**

| # | Pergunta | Ficha | Proposta |
|---|---|---|---|
| D-PR1 | O servidor deve receber, depois do retorno, a lista do que ainda falta entregar? Em que dia? | AUT-38 | Dia útil seguinte à chegada, só pendências dele, sem prazo inventado |
| D-PR2 | Horários e destinatários dos resumos; quem recebe o semanal; quantos dias sem atividade fazem uma prestação "parada" | AUT-39 | Diário 08:00 em dias úteis aos operadores da unidade; semanal às segundas à chefia; 7 dias |
| D-PR3 | O km inicial vindo do último km da viatura precisa de confirmação na conclusão do DB, como o km pela distância? | AUT-42 | Sim |
| D-PR4 | Qual limiar de salto de km entre trechos gera aviso? A tolerância de 20 % (mínimo 10 km) do código é paridade com a referência: vale como regra da instituição? | AUT-44 | Limiar por unidade; sem valor, aviso desligado |
| D-PR5 | Quais feriados contam no prazo (sede da unidade? município do servidor? ponto facultativo?) e quem cadastra. A regra "prazo de saque + 3 dias úteis" é oficial? | AUT-51 | Feriados da sede da unidade, cadastrados pelo gestor |
| D-PR6 | Por quanto tempo guardar o texto/OCR das partes, que contém CPF? | AUT-54 | O mesmo prazo do original importado |
| D-PR7 | Registrar o SHA-256 do pacote enviado ao financeiro vira item novo ou fica dentro de AUT-122? | seção 5 | Item novo, de maturidade 2, numerado no fim do tema |
| D-PR8 | A ADR de IA autoriza enviar a um provedor externo dados estruturados do RT (AUT-50) e texto minimizado de documentos importados (AUT-57, AUT-58), revendo a ADR 0041? Qual provedor e qual teto mensal? | AUT-50, 57, 58 | Só dados estruturados do RT na primeira entrega; documentos importados só depois de medir com o gabarito |

**Herdadas dos fluxos, que bloqueiam fichas deste grupo:** texto oficial e valor no aviso (D1 e D2 do 10-3);
hora, janela e marcos (D3 a D6 do 10-3); e-mail dos servidores e forma de verificação (D8 do 10-3, AUT-02);
aparelho e número institucionais do WhatsApp assistido com registro, WA-1 (D16 do 10-3, respondida em
parte pelo usuário; D4a do plano); quem
preenche o km, validade e horário do link (itens 1 a 3 do 10-4); quem assina o DB e o RT e qual assinatura
vale (D-01 a D-03 do 10-5); prazo de devolução e lembretes (D-05 do 10-5); identificação no portal (D-06 do
10-5); tipos que o servidor pode devolver com aplicação automática (D1 do 10-6); caixa institucional e
procedimento da TI (10-6 §14); e se distribuir e receber pelo portal e por e-mail é aceito como complemento
da tramitação oficial do eProtocolo (B9).

---

## 8. Divergências e correções encontradas

1. **AUT-51, coluna "hoje" da matriz.** A matriz diz "inexistente (feriados não são considerados)". O código
   já considera feriados nacionais fixos e móveis (`gestao/viagens/dominio/prestacao.py:38-51`, `:63-64`) e as
   funções aceitam feriados extras (`:63-86`); faltam o cadastro e a ligação dos chamadores. O certo é
   "parcial".
2. **AUT-45.** O defeito "signatário do DB errado" é do GV (`ref/gv/prestacoes_contas/assinatura_services.py:44-46`).
   No sistema novo o DB já imprime o motorista efetivo do diário (`gestao/viagens/diario.py:219-224`); o que
   falta é o direcionamento do assinado na importação quando o motorista é de outro ofício.
3. **AUT-49.** A origem na matriz é só o EV, mas o mesmo defeito existe no sistema novo: a frase fixa sobre
   intercorrências está em `gestao/viagens/dominio/relatorio.py:188`.
4. **AUT-57 e AUT-58.** A maturidade 3 supõe provedor externo autorizado. Com a ADR 0041 como está (documentos
   da importação não vão a terceiros, linhas 19-20) e o modelo local inviável na VPS (AUT-98,
   [desempenho e custos](../desempenho-e-custos.md) §11.4), não há caminho de implantação sem ADR nova. O 10-6
   §5 ainda cita "modelo local" como futuro: esse caminho não cabe na VPS atual. A matriz não foi alterada;
   a condição está nas fichas e em D-PR8.
5. **WhatsApp nos fluxos — resolvida.** O 10-3 (§13, item D1: "5 enquanto em análise, depois 3–4"), o 10-4
   (§13: "sob análise") e o 10-5 (§13: "4/5") foram escritos antes da pesquisa. Corrigido nos três: a
   plataforma oficial vale 5 sem ressalva de autorização interna (AUT-10), e cada fluxo registra as frentes
   priorizadas pelo usuário — WA-1, envio assistido com registro (2, AUT-172); WA-2, consulta formal (4,
   AUT-173); WA-3, integração pronta e desligada (5 para ativar, AUT-174) (matriz §10, item 2).
6. **Retentativa da outbox.** O 10-4 (§2.1: "backoff de 5 s até 1 h") e o 10-5 (§9: "após 8 tentativas (5 s →
   1 h)") repetem a fórmula da ADR 0005. O efetivo é 10 s → 640 s, com `falhou` na 8ª tentativa, cerca de
   21 min (10-3 §2.4, item 4; 10-6, anexo A).
7. **AUT-38.** O título da matriz inclui "o que entregar após o retorno", que o 10-3 não detalha; esta ficha
   propõe o marco pós-retorno, sujeito a D-PR1.
8. **AUT-43.** O 10-4 deixou fora do escopo e define `digitado_em` como "só informativo". A ficha mantém isso:
   o horário do celular só aparece como sugestão com nível de confiança, e a pessoa decide.
9. **AUT-40.** A matriz lista AUT-02 como dependência; ela só é necessária para o envio automático (AUT-41).
   Entregue pelo operador, o link funciona sem contato verificado (10-4 §3.2).
10. **Pacote enviado ao financeiro.** O registro de qual pacote foi entregue foi juntado a AUT-122
    (maturidade 4), mas não depende do eProtocolo (seção 5, D-PR7).
11. **Números de linha que mudaram desde os fluxos:** `prestacao.filtrar` começa em `gestao/viagens/prestacao.py:190`
    (o 10-3 cita `:206-208`, trecho de dentro da função) e `salvar_solicitacao` em `:268` (o 10-3 cita
    `:267`). A árvore de trabalho tem alterações não commitadas; confira a linha antes de editar.

---

## 9. O que não foi possível confirmar

- **Volumes reais** (viagens, servidores, prestações, devoluções por mês): todos os custos e volumes desta
  ficha são estimativas sobre as hipóteses H1–H9 de [desempenho e custos](../desempenho-e-custos.md) §3.
- **Tempo humano economizado**: nenhum tempo foi cronometrado; cada fluxo define como medir antes e depois.
- **SMTP institucional e Workspace**: não se sabe se a PCPR tem contas no Google Workspace do Estado nem quem
  concede SMTP e caixa postal (B8).
- **E-mail dos servidores**: o cadastro não tem; a origem (diretório, cadastro, o próprio servidor) é
  desconhecida.
- **Fuso do host** que roda o timer das 05:40 (D13 do 10-3, D-14 do 10-5); as fichas tornam o envio
  independente dele, mas a rotina continua dependendo.
- **Via assinada no eProtocolo com camada de texto** (AUT-56): não foi conferido em PDFs reais se a tabela
  da equipe continua legível por coordenadas depois da assinatura.
- **Textos padrão do cadastro** (`ModeloTexto`): só as sugestões do código foram conferidas (AUT-49); os
  textos cadastrados pela instituição não foram lidos.
- **Protótipo**: os 12 cenários passaram na execução final de 17/10/2026 (03:53–03:59, horário de
  Brasília) com PCPR e canal simulados e SQLite; resultados e métricas em
  [`prototipo/README.md`](../prototipo/README.md) (evento → envio p50 314 ms e p95 403 ms em série; p50
  5,1 s e p95 6,6 s com 20 simultâneos). O recebimento usou canal fictício; IMAP e SMTP reais não foram
  exercitados. Não representa a VPS nem o sistema.
- **Decreto 7.304/2021**: se as automações de distribuição e recebimento são aceitas como complemento da
  tramitação oficial depende de confirmação institucional (B9).
