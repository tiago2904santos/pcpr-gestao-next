# Matriz de oportunidades de automação — PCPR

Fase 2 · 17/10/2026. Consolidação das sete leituras do código, revisada à mão. Base:
[arquitetura](arquitetura.md), [contratos](contratos/), fluxos em [`fluxos/`](fluxos/), fichas em
[`fichas/`](fichas/), [viabilidade do WhatsApp](whatsapp-viabilidade.md),
[inventário de processos](inventario-processos.md) e [desempenho e custos](desempenho-e-custos.md). O
[plano de implantação](plano-implantacao.md) e as fichas usam os identificadores `AUT-NN` definidos aqui.

> Em uma frase: as 337 oportunidades apontadas pelas leituras viram **171 itens** depois de juntar o que
> era a mesma coisa vista por áreas diferentes, mais **3 itens** (AUT-172 a AUT-174) para as frentes do
> WhatsApp que o usuário definiu como prioridade em 17/10/2026 — **174** no total. **95** dependem só do que
> já existe ou de desenvolvimento no próprio sistema (maturidade 1–2), **40** esperam provedor, credencial
> ou custo (3), **11** esperam a instituição (4) e **28** têm maturidade 5: 27 ficam de fora por política
> ou por não serem recomendáveis, e a integração oficial do WhatsApp (AUT-174) é construída desligada, com
> ativação bloqueada. A plataforma oficial do WhatsApp continua **bloqueada** pela política da Meta para
> autoridades policiais (AUT-10); o envio assistido com registro (AUT-172, 2) e a consulta formal à Meta
> (AUT-173, 4) começam já.

## 1. Método e números

Leituras usadas, todas de 17/10/2026. As referências foram lidas somente para entender o processo real.

| Leitura (17/10/2026) | Processos | Oportunidades |
|---|---|---|
| novo · planos-rotas | 22 | 45 |
| novo · prestação | 21 | 33 |
| novo · viagens-núcleo | 22 | 43 |
| novo · plataforma | 23 | 58 |
| novo · outros módulos | 30 | 74 |
| ref. GV | 23 | 45 |
| ref. EV | 23 | 39 |
| **Total** | **164** | **337** |

- **O que foi lido.** Cinco leituras são do sistema novo (`gestao/`), feitas na árvore de trabalho de
  17/10/2026, que tinha alterações ainda não commitadas, então números de linha podem mudar. Duas são das
  referências implantadas em produção: o GV no commit `ded9b648` e o EV no commit `92f57bda`, mais arquivos
  fora do Git. Nenhum código das referências é base do sistema novo. Cada leitura listou processos com
  evidência `caminho:linha`, estados, pontos de integração, lacunas e oportunidades já classificadas. O
  detalhe por processo está no [inventário](inventario-processos.md).
- **Como se juntou.** Duas oportunidades viram um item quando pedem a mesma mudança, com o mesmo gatilho e
  o mesmo efeito, ainda que venham de leituras diferentes. Exemplo: o envio do link de km na véspera aparece
  em sete processos de seis leituras e virou AUT-41. Quando a mesma ideia tem uma parte do sistema e uma
  parte de canal, ficam dois itens, porque a maturidade é diferente. Exemplo: AUT-36 (texto e registro do
  aviso de liberação) e AUT-37 (envio automático). A parte WhatsApp de qualquer proposta foi para AUT-10.
- **Itens derivados.** 10 itens não correspondem a uma oportunidade escrita nas leituras. Sete vêm das
  dependências que elas registraram ou dos fluxos 10-1, 11-2, 11-3 e 13: portal com link, porta de IA,
  central de ajuda sem IA, modelo local, autorização por fluxo, salvaguardas do eProtocolo e resumo de
  movimentações por IA. Três vêm das frentes do WhatsApp do [plano](plano-implantacao.md) (AUT-172 a
  AUT-174, acrescentadas em 17/10/2026 no fim da numeração). A coluna Origens os marca como "derivado".
- **Reclassificação.** A classificação da matriz é a do item consolidado. Ela segue o critério da seção 3 e
  pode divergir da leitura de origem. O apêndice A mostra a classificação original de cada uma das 337, e a
  seção 3.1 lista os casos em que a leitura sugeria n8n e a matriz não.
- **Valor e esforço são estimativas qualitativas.** Os volumes reais não foram medidos neste trabalho:
  viagens e servidores por mês, perguntas ao suporte, e-mails recebidos. Ver
  [desempenho e custos](desempenho-e-custos.md). Nenhum preço, limite ou regra institucional é afirmado
  sem fonte. Onde falta fonte, está escrito "a confirmar" ou "estimativa".
- **Evidências reconferidas para esta matriz** em 17/10/2026:
  - `gestao/viagens/views_prestacao.py:176-191`: o aviso de saque é só um link `wa.me`.
  - `gestao/plataforma/notificacoes.py:79-80`: um único e-mail com todos os destinatários.
  - `gestao/plataforma/outbox.py:44-45`: um assinante por tópico.
  - `gestao/viagens/de_eventos.py:10-14`: a viagem é gerada por botão.
  - `docs/migration/decisoes.md:205`: "amanhã sai a viagem" ficou de fora.
  - `deploy/systemd/pcpr-rotinas@.timer:5`: rotina às 05:40.
  - `gestao/cadastros/models.py:103-119`: telefone único e nenhum e-mail no `Servidor`.

  As demais evidências vêm das leituras e dos fluxos, que as conferiram no mesmo dia.

## 2. Como ler

| Coluna | Significado |
|---|---|
| **ID** | `AUT-NN`, estável. Item novo entra com número novo no fim; item descartado fica marcado e nunca é renumerado |
| **Módulo / processo** | Onde a oportunidade mora |
| **Classificação** | Uma da lista fixa (abaixo) |
| **Mat.** | Maturidade de 1 a 5 (abaixo) |
| **Valor** | **alto**: tira trabalho manual recorrente (por viagem, por servidor ou diário) ou evita erro com efeito financeiro, oficial ou de segurança · **médio**: economia ocasional ou risco moderado · **baixo**: conveniência ou caso raro |
| **Esf.** | **P**: dias, sem modelo novo · **M**: uma a duas semanas, com modelo ou tela nova · **G**: várias semanas, várias telas e modelos ou integração. É estimativa; para os fluxos já desenhados vale o esforço do fluxo |
| **Hoje** | **existe**: o código executa no sistema novo · **parcial**: existe em parte ou com lacuna conhecida (verificado parcialmente) · **planejado**: só em ADR ou desenho · **inexistente** · **só na referência**: GV ou EV fazem, o sistema novo não |
| **Dependências** | O que precisa existir antes; `AUT-NN` aponta outro item |
| **Onde** | Fluxo que detalha o item ([10-1](fluxos/10-1-assistente-dos-servidores.md) a [13](fluxos/13-integracoes-institucionais.md)) e ficha do grupo ([comunicação e viagens](fichas/comunicacao-e-viagens.md), [prestação e documentos](fichas/prestacao-e-documentos.md), [plataforma e módulos](fichas/plataforma-e-modulos.md)) |
| **Origens** | Ids de processo das leituras e, entre parênteses, quantas oportunidades foram juntadas no item |

**Como a lista fixa de classificações foi aplicada**

| Classificação | Quando a matriz usa |
|---|---|
| automação indicada com n8n | O valor está na borda: canal externo, agenda e agregação para quem está fora do sistema, consulta a serviço de fora ou monitoramento. A regra fica no PCPR |
| assistência por IA indicada | Interpretar texto livre ou redigir um rascunho que uma pessoa aceita. A IA nunca decide nem grava |
| automação determinística suficiente | Uma regra fixa dentro do sistema resolve (rotina, cálculo, sugestão explicável), sem n8n e sem IA |
| melhor execução pelo próprio sistema | Funcionalidade ou efeito interno do PCPR (tela, estado, documento, assinante interno da outbox) que não deve ir para o n8n nem para a IA |
| dependente de desenvolvimento | Peça de fundação que ainda não existe e da qual outras automações dependem: API, token, link, contato, eventos |
| dependente de integração externa | O bloqueio é um sistema, provedor ou credencial de fora: eProtocolo, Central de Viagens, SMTP, provedor de rotas, fonte de RH |
| inadequada ou inviável atualmente | Fica na matriz com a justificativa, sempre com maturidade 5 |

**Maturidade.** 1 viável com recursos existentes · 2 depende de desenvolvimento no sistema · 3 depende de
provedor, credencial ou custo · 4 depende de integração institucional · 5 bloqueada ou não recomendada
atualmente.

A maturidade é o nível exigido para entregar a oportunidade **como está descrita**. Quando uma parte já
funciona num nível menor, a coluna Dependências diz qual. Exemplo: AUT-22 é 2 pelo portal e 3 por e-mail.
**A matriz é a referência de maturidade.** Quando um fluxo declara outro nível, a seção 10 registra o
motivo e o fluxo deve ser ajustado, salvo quando a diferença vem de um escopo diferente (por exemplo, a
versão no sino de um aviso que a matriz mede por e-mail); a seção 10 diz qual é o caso.

## 3. Critério: explorar o n8n ao máximo, onde ele agrega

O pedido é usar o n8n ao máximo. A matriz entende isso como **usar o n8n em tudo o que é borda e tem
benefício demonstrável**, e não como mover para ele regras que já estão no código e precisam continuar
testadas. A divisão já está fixada na [arquitetura](arquitetura.md), seção 1: o PCPR é dono do estado, das
regras e de cada comunicação, e o n8n orquestra as bordas.

**Onde o n8n entra.** São 25 itens classificados como "automação indicada com n8n": a instalação
(AUT-99) e os 24 abaixo.

1. **Canais.** Enviar e receber e-mail institucional, repassar status de entrega e devoluções, ler caixas
   postais, entregar link por e-mail: AUT-06, AUT-08, AUT-22, AUT-23, AUT-37, AUT-41, AUT-47, AUT-141, AUT-144, AUT-156.
2. **Agenda e agregação para quem não está no sistema ou não o abre todo dia.** Resumos diários e semanais,
   véspera, lembretes a servidor, palestrante e fornecedor, pauta e relatório mensal: AUT-07, AUT-09, AUT-31,
   AUT-38, AUT-39, AUT-136, AUT-145, AUT-150, AUT-153, AUT-157, AUT-162, AUT-164.
3. **Integrações periféricas.** Agendar consultas a serviços de fora: AUT-148. O n8n sempre chama
   ferramentas do PCPR, que falam com o serviço pelas portas da ADR 0019. Quando houver credencial, ele pode
   agendar as consultas do eProtocolo (AUT-120).
4. **Monitoramento.** Rotear, agrupar e escalar alertas, inclusive das referências em produção: AUT-111.
   Tem maturidade 1 e pode vir logo depois da instalação (AUT-99).

**Onde o n8n não entra, e por quê**

- **Duplicaria regra do sistema.** Prazos, diárias, quem recebe o quê, estados, numeração e documentos
  ficam em Python, com testes. Exemplos: AUT-36, AUT-25.
- **O sino e uma rotina interna já resolvem para quem usa o sistema.** É o caso dos avisos de marcos, de
  conflitos e de configuração (AUT-24, AUT-29, AUT-161). Com AUT-06, qualquer aviso do sino pode ser espelhado
  por e-mail sem um workflow específico.
- **Tornaria o sistema dependente dele.** É o caso das rotinas internas (AUT-109) e da preparação da viagem
  no deferimento (AUT-16, que é assinante da outbox). Com o n8n desligado, tudo tem de continuar à mão pelo
  sistema.
- **Exigiria acesso que contorna as policies.** Endpoints de tela, banco ou feed ICS pessoal (AUT-126).

**Teste aplicado a cada item**

1. Com o n8n desligado, o processo continua à mão pelo sistema?
2. O workflow só transporta, agenda, consulta ou agrega, sem decidir?
3. O ganho existe sem reescrever no n8n uma regra que já está em Python?

Três "sim" levam a "automação indicada com n8n". Qualquer "não" leva a outra classificação. Nos
10 casos abaixo, a leitura de origem sugeria n8n e o teste apontou outro caminho.

#### 3.1 Onde a leitura sugeria n8n e a matriz não (10 itens)

| ID | Oportunidade | Classificação na matriz | Por quê |
|---|---|---|---|
| AUT-24 | Avisos aos operadores nos marcos da viagem: viagem gerada, plano gerado, PDF ou pacote pronto ou com falha definitiva | melhor execução pelo próprio sistema | Quem avisar e quando é regra do sistema e o sino já entrega a usuários internos; com AUT-06 nenhum workflow específico é necessário no n8n. |
| AUT-29 | Alerta proativo de conflitos de pessoa ou viatura nos próximos 7 dias e de conflito novo em ofício já emitido | automação determinística suficiente | A detecção já existe; falta rodar e avisar pelo sino, e o n8n só entraria para espelhar o aviso por e-mail. |
| AUT-46 | DB e RT prontos para assinatura: conclusão explícita, versão congelada (instantâneo e SHA-256), assinante pela regra do documento, devolução ligada à versão e aviso ao operador | melhor execução pelo próprio sistema | Sem versão congelada não há como afirmar que o assinado corresponde ao preparado; é regra documental do sistema e funciona sem n8n. |
| AUT-83 | Lembrete de lançamento de resultados após o fim do evento | automação determinística suficiente | A regra (evento terminou e não há resultados) é do sistema e o sino alcança o operador; o n8n só entraria para quem está fora do sistema. |
| AUT-109 | Rotinas diárias com horário por rotina, independentes do primeiro acesso e com reexecução só do que falhou | automação determinística suficiente | Timers do próprio sistema resolvem; pôr o n8n como agendador de rotinas internas, como as leituras do EV sugeriam, faria o sistema depender dele. |
| AUT-120 | Consulta periódica do andamento dos protocolos e aviso de mudança ou de chegada ao setor | dependente de integração externa | Mostra no sistema quando o processo andou ou voltou, sem consulta manual no portal; a chamada passa pela porta do PCPR, não pelo n8n. |
| AUT-123 | Trazer do eProtocolo o ofício assinado, o despacho e o processo para a importação documental | dependente de integração externa | Elimina baixar e reenviar o que já está no eProtocolo, reaproveitando a leitura e o direcionamento existentes. |
| AUT-143 | Formulário público de pedido de palestra com acompanhamento por link (e confirmação por e-mail quando houver SMTP) | melhor execução pelo próprio sistema | A ASCOM recebe dados estruturados e o solicitante acompanha sem ligar; a confirmação por e-mail é transporte. |
| AUT-154 | Comunicação formal com o fornecedor (OS, OB e notificação de ocorrência) com prévia editável, aprovação e registro | melhor execução pelo próprio sistema | Compor, aprovar e registrar é do sistema; o n8n pode transportar com retentativa, mas comunicação contratual exige aprovação. |
| AUT-161 | Alertas de configuração da unidade: assinante de planos ausente, substituição de assinante começando ou terminando, sede ausente | automação determinística suficiente | Documentos saem com o assinante certo; é consulta interna com aviso no sino, sem n8n. |

Itens consolidados cuja classificação final difere de todas as classificações das oportunidades de origem: **12** (AUT-01, AUT-09, AUT-10, AUT-24, AUT-75, AUT-83, AUT-84, AUT-95, AUT-117, AUT-132, AUT-145, AUT-153). O apêndice A mostra a classificação original de cada uma das 337.

## 4. Limites que valem para toda a matriz

- **WhatsApp: plataforma oficial bloqueada, prioridade do usuário.** A política oficial do WhatsApp
  Business lista autoridades policiais entre os usuários proibidos do WhatsApp Business Platform, sem
  exceção nem processo de aprovação. A regra está na
  seção de uso governamental e político, atualizada em 23/09/2026 e consultada em 17/10/2026
  (<https://whatsappbusiness.com/policy/>). Provedores de soluções como a 360dialog também recusam polícia
  (<https://docs.360dialog.com/docs/resources/government-agencies>, consultada em 17/10/2026). Não há
  integração WhatsApp ativa em produção: o EV tem só a rota do webhook comentada e uma unidade de serviço
  que chama um comando inexistente, e os sistemas usam links `wa.me` abertos à mão pelo operador. Tudo o
  que depende da plataforma oficial ou de integração não oficial tem maturidade 5 (AUT-10, AUT-11). Em
  17/10/2026 o usuário definiu o WhatsApp como **prioridade**: o [plano](plano-implantacao.md) abre as
  frentes WA-1 (envio assistido com registro, AUT-172, maturidade 2), WA-2 (consulta formal à Meta,
  AUT-173, 4) e WA-3 (integração oficial pronta e desligada, AUT-174, 5 para ativar). O canal adotado em
  cada caso está na seção 6, e a análise completa em [whatsapp-viabilidade.md](whatsapp-viabilidade.md).
- **O eProtocolo é o sistema oficial.** O Decreto estadual 7.304/2021 define o eProtocolo como sistema
  oficial de gestão de documentos do Executivo e veda sistemas paralelos de controle e tramitação
  ([texto do decreto](https://www.administracao.pr.gov.br/sites/default/arquivos_restritos/files/documento/2021-04/decreto_7304_-_2021_-_eprotocolo_-_com_anexos_0.pdf),
  consultado em 17/10/2026). **Ponto a confirmar com a instituição:** as automações de distribuição e
  recebimento (AUT-22, AUT-47, AUT-52, AUT-08) devem complementar a tramitação oficial, não substituí-la. Elas
  entregam cópia, avisam e recebem de volta para conferência. Juntada e tramitação ficam no eProtocolo
  (AUT-122).
- **Servidores viajantes não são usuários do sistema novo.** `Servidor` não tem e-mail, o telefone é único
  e o vínculo usuário↔servidor está pendente, então o sino não os alcança. Todo aviso ao servidor depende de
  AUT-02. Entregar documento ou receber devolução depende também de AUT-03.
- **Assinatura.** O GV em produção tem assinatura eletrônica simples de RT e DB por link público (token
  cifrado com hash, CPF e expiração) e entrega documento por link temporário de 15 minutos. A assinatura
  digital de ofícios é feita no eProtocolo, decisão registrada no GV. A matriz não propõe que o sistema novo
  assine por ninguém (AUT-59): ele prepara, versiona, entrega e confere o que volta.
- **Outbox atual.** Cada tópico tem um só assinante. O worker segura a transação enquanto o assinante roda,
  por isso HTTP externo vai para um worker de entregas com lease (AUT-101). A retentativa efetiva dura cerca
  de 21 minutos (AUT-102) e não há tela de falhas (AUT-103).
- **O que continua humano**, como no [plano](plano-implantacao.md): escolher quem participa, emitir,
  retificar, cancelar, assinar, aprovar ou devolver prestação, registrar a liberação das diárias, decidir
  despacho e aprovar ações irreversíveis. As linhas de maturidade 5 incluem as tentativas de automatizar
  esses atos.
- **IA.** Mensagens, anexos e textos recuperados são dados, nunca instruções. A ADR 0041 exclui enviar
  documentos da importação a IA externa, e um modelo local não cabe com folga na VPS atual (AUT-98). Toda
  assistência por IA passa pela porta e pelo validador de AUT-96. Ela só é ligada depois de medida com o
  gabarito de AUT-91.

## 5. A matriz

Seis tabelas, uma por tema. Dentro de cada tema a ordem vai da fundação para as aplicações, e as linhas de
maturidade 5 ficam no fim. Itens acrescentados depois da primeira numeração entram no fim do seu tema com
número novo, para não mudar ids já usados. As fichas usam o mesmo `AUT-NN`.

**Índice pelas categorias pedidas na missão.** Os temas das tabelas são da própria matriz; este índice
mostra onde está cada categoria pedida no levantamento. Um item pode aparecer em mais de uma categoria.
Nenhuma categoria ficou sem item.

| Categoria da missão | Itens |
|---|---|
| Comunicação com servidores e canais (contato, avisos, envio, WhatsApp) | AUT-01 a AUT-13, AUT-22, AUT-23, AUT-36, AUT-37, AUT-41, AUT-47, AUT-144, AUT-172 a AUT-174 |
| Documentos (geração, versão, envio, assinatura, conferência) | AUT-21, AUT-22, AUT-46, AUT-47, AUT-53, AUT-56, AUT-59, AUT-87 |
| Recebimento e leitura de documentos | AUT-08, AUT-52, AUT-54, AUT-55, AUT-57, AUT-58, AUT-61, AUT-112, AUT-123, AUT-151 |
| Prestação de contas e diárias | AUT-34, AUT-36 a AUT-39, AUT-46 a AUT-51, AUT-55, AUT-56, AUT-59, AUT-60, AUT-63, AUT-169 |
| Diário de bordo e quilometragem | AUT-40 a AUT-45, AUT-62 |
| Viaturas, motoristas e conflitos | AUT-17, AUT-19, AUT-20, AUT-29, AUT-32, AUT-42, AUT-45, AUT-135 |
| Rotas e roteiros | AUT-64 a AUT-77 |
| Planos de trabalho | AUT-78 a AUT-87 |
| Proposta consolidada e autonomia ("selecionar o evento, informar quem vai, conferir") | AUT-14, AUT-15, AUT-16, AUT-118 |
| Dados da unidade e assinantes | AUT-28, AUT-161 |
| Fontes dedicadas de cadastros | AUT-159, AUT-160, AUT-168 |
| Relatórios e consultas | AUT-31, AUT-39, AUT-89, AUT-94, AUT-105, AUT-124, AUT-162, AUT-163, AUT-164 |
| Prazos e lembretes | AUT-25, AUT-26, AUT-27, AUT-38, AUT-51, AUT-83, AUT-140, AUT-145, AUT-147, AUT-153, AUT-158 |
| Monitoramento, recuperação e backups | AUT-99, AUT-102, AUT-103, AUT-109, AUT-110, AUT-111, AUT-116, AUT-127 |
| Entrada de demandas | AUT-08, AUT-92, AUT-93, AUT-132, AUT-133, AUT-138, AUT-143 |
| Eventos Sociais (solicitações, despacho, catálogos) | AUT-134 a AUT-142, AUT-165 |
| Palestras, ASCOM, Imprensa e Publicações | AUT-95, AUT-143 a AUT-149 |
| Coffee Break | AUT-150 a AUT-158, AUT-166, AUT-167 |
| IA (assistente, rascunhos, leitura) | AUT-13, AUT-33, AUT-34, AUT-50, AUT-57, AUT-58, AUT-61, AUT-63, AUT-76, AUT-77, AUT-80, AUT-81, AUT-86 a AUT-98, AUT-171 |
| Fundação de integração (API, eventos, exceções, ferramentas, links) | AUT-01 a AUT-03, AUT-100 a AUT-108 |
| Integrações institucionais e futuras (eProtocolo, Central de Viagens, SSO, Drive, migração) | AUT-115, AUT-117, AUT-119 a AUT-123, AUT-125, AUT-128 a AUT-131, AUT-170, AUT-171 |

### 5.1 Comunicação e canais — AUT-01 a AUT-13 e AUT-172 a AUT-174 (16 itens)

| ID | Módulo / processo | Oportunidade | Classificação | Mat. | Valor | Esf. | Hoje | Dependências | Onde | Justificativa | Origens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **AUT-01** | Plataforma · comunicação | Registro de cada comunicação no PCPR (`Comunicacao`): estado, versão, destinatário, texto enviado, histórico de entrega e ações manuais (enviar agora, copiar, marcar "enviado por outro meio") | dependente de desenvolvimento | **2** | alto | M | inexistente (o aviso de saque é um link `wa.me` sem registro) | Modelo comum aos fluxos 10-2 a 10-6; nenhuma externa | [arquitetura](arquitetura.md) · [10-2](fluxos/10-2-envio-de-documentos.md) · [10-3](fluxos/10-3-prestacao-e-mensagem-de-saque.md) · [ficha](fichas/comunicacao-e-viagens.md) | Sem registro o PCPR não sabe o que foi avisado nem a quem; com ele todo envio automático tem estado, versão e alternativa manual, e o n8n vira só transporte. | `GV-NOTIFICACOES` (1) |
| **AUT-02** | Cadastros · servidor | Contato verificado, consentimento e identidade do servidor viajante (`ContatoVerificado` e vínculo usuário↔servidor) | dependente de desenvolvimento | **2** | alto | M | parcial (`Servidor` tem só telefone, único, e nenhum e-mail; vínculo usuário↔servidor pendente) | Decisão institucional sobre uso de e-mail e telefone (LGPD) | [arquitetura](arquitetura.md) · [10-1](fluxos/10-1-assistente-dos-servidores.md) · [10-4](fluxos/10-4-link-de-km-na-vespera.md) · [ficha](fichas/comunicacao-e-viagens.md) | Servidores viajantes não são usuários do sistema: sem contato verificado e vinculado a um servidor identificado nenhum aviso automático pode sair, e um número informado numa conversa não autoriza nada. | `ID-AUTENTICACAO-AUTORIZACAO`, `CAD-SERVIDORES-VIATURAS-CATALOGOS`, `EV-VINCULO-USUARIO-SERVIDOR` (3) |
| **AUT-03** | Plataforma · acesso sem login | Link de acesso com escopo, validade, revogação e registro de uso (`LinkAcesso`) e portal mínimo do servidor (documentos, situação e devolução) | dependente de desenvolvimento | **2** | alto | G | parcial (o padrão de token com hash existe no feed ICS, `gestao/plataforma/assinatura.py`) | AUT-02; ADR nova para rota sem login (como o feed ICS); máscara do token nos logs | [arquitetura](arquitetura.md) · [10-2](fluxos/10-2-envio-de-documentos.md) · [10-5](fluxos/10-5-db-e-rt-para-assinatura.md) · [10-6](fluxos/10-6-recebimento-de-documentos.md) · [ficha](fichas/comunicacao-e-viagens.md) | É o canal que não depende de provedor: entrega o documento certo à pessoa certa e recebe a devolução sem anexar arquivo em e-mail, e serve aos fluxos 10-2 a 10-6. | derivado das dependências de VIA-TERMOS, VIA-OFICIO-EMISSAO e PREST-DOCS-ENVIO-ASSINATURA e da [arquitetura](arquitetura.md) |
| **AUT-04** | Plataforma · e-mail | SMTP institucional: conta, remetente autorizado e credencial para o PCPR e o n8n | dependente de integração externa | **3** | alto | P | parcial (o envio existe; sem `EMAIL_HOST` cai no console, `config/settings/base.py:266-279`) | TI institucional; a pesquisa achou Google Workspace do Estado via Celepar (AEN, 01/12/2025, consultada em 17/10/2026) sem confirmar se a PCPR está incluída | [10-2](fluxos/10-2-envio-de-documentos.md) · [10-3](fluxos/10-3-prestacao-e-mensagem-de-saque.md) · [12 custos](desempenho-e-custos.md) · [ficha](fichas/comunicacao-e-viagens.md) | É o único canal externo viável hoje; sem ele os fluxos funcionam só por portal e sino, e os e-mails do coffee, a pauta e o "esqueci a senha" seguem bloqueados. | `PLAT-NOTIF-EMAIL` (1) |
| **AUT-05** | Plataforma · e-mail | E-mail de notificação individual por destinatário (hoje vai uma lista no "Para") | automação determinística suficiente | **2** | médio | P | parcial (`gestao/plataforma/notificacoes.py:79-80` envia um e-mail com todos os destinatários) | Nenhuma | [arquitetura](arquitetura.md) · [ficha](fichas/comunicacao-e-viagens.md) | Correção pequena no próprio sistema que evita expor endereços entre destinatários e permite reenvio e status por pessoa. | `NOTIFICACOES-ROTINAS` (1) |
| **AUT-06** | Plataforma · comunicação | Entrega externa das comunicações e avisos pelo n8n (e-mail institucional): reserva, envio, resultado, devoluções e retentativa | automação indicada com n8n | **3** | alto | M | inexistente | AUT-01, AUT-02, AUT-04, AUT-101, AUT-104 | [arquitetura](arquitetura.md) · [10-2](fluxos/10-2-envio-de-documentos.md) · [10-3](fluxos/10-3-prestacao-e-mensagem-de-saque.md) · [ficha](fichas/comunicacao-e-viagens.md) | Borda típica do n8n (canal, retentativa, status de entrega, leitura de devoluções) sem decisão de negócio: quem, quando e o quê ficam no PCPR, e com o n8n parado tudo fica "agendado" para envio manual. | `PLAT-NOTIF-SINO`, `NOTIFICACOES-ROTINAS`, `EVT-LEMBRETES`, `EV-COFFEE-FORNECEDOR-PAGAMENTO` (4) |
| **AUT-07** | Plataforma · notificações | Resumo diário por pessoa: pendências e compromissos do dia numa única mensagem | automação indicada com n8n | **3** | médio | P | inexistente (sino e central de notificações existem) | AUT-105, AUT-06 | [ficha](fichas/comunicacao-e-viagens.md) | O canal é o uso natural do n8n (agregação e horário ficam no PCPR pelo contrato rascunho 3, §10 item 14); uma mensagem por pessoa substitui vários resumos por módulo e várias consultas ao sistema. | `PLAT-NOTIF-SINO` (1) |
| **AUT-08** | Entrada por e-mail (transversal) | Leitura das caixas postais institucionais pelo n8n (IMAP/OAuth) com deduplicação por Message-ID, entregando ao PCPR documentos devolvidos e pedidos recebidos | automação indicada com n8n | **4** | alto | M | inexistente (o operador baixa e arrasta os anexos) | Caixa dedicada e credencial concedidas pela TI institucional; AUT-52; AUT-132; AUT-112; política de remetentes | [10-6](fluxos/10-6-recebimento-de-documentos.md) · [10-1](fluxos/10-1-assistente-dos-servidores.md) · [ficha](fichas/comunicacao-e-viagens.md) · [ficha](fichas/plataforma-e-modulos.md) | Trazer o e-mail para dentro é borda pura; ler, classificar e direcionar continua na importação documental e na caixa de entrada do PCPR, e o canal deve complementar a tramitação oficial do eProtocolo, não substituí-la (ponto a confirmar). | `DOC-IMPORTACAO-ENTRADA`, `VIA-VIAS-ASSINADAS`, `VIA-IMPORTACAO-FILA`, `EV-DB-RT-ASSINATURA`, `CB-CERTIDOES`, `PLAT-LEITURA-EMAIL`, `PAL-PEDIDO-REGISTRO`, `IMP-ATENDIMENTO`, `PUB-PAUTA`, `CB-PEDIDO-OS`, `EV-LEITURA-PEDIDO`, `GV-EVENTO`, `VIA-SOLICITACAO-ANEXO` (13) |
| **AUT-09** | Agenda · servidor | Agenda do dia seguinte enviada a cada servidor escalado (véspera) | automação indicada com n8n | **3** | médio | P | inexistente | AUT-02, AUT-06, AUT-105; tratamento de cancelamento tardio | [10-4](fluxos/10-4-link-de-km-na-vespera.md) · [ficha](fichas/comunicacao-e-viagens.md) | O servidor viajante não usa o sistema; receber na véspera o compromisso do dia é borda de canal e agenda, com a mesma regra de véspera do fluxo 10-4. | `AGENDA-ESCALA-PAUTA-ICS` (1) |
| **AUT-10** | Canais · WhatsApp | Canal WhatsApp Business Platform (Cloud API) para avisos, links, documentos e recebimento de devolvidos | inadequada ou inviável atualmente | **5** | alto | — | inexistente (o EV tem só a rota do webhook comentada e um serviço que chama comando inexistente; os sistemas usam links `wa.me` abertos à mão) | Política oficial: autoridades policiais estão entre os usuários proibidos do WhatsApp Business Platform, sem exceção nem processo de aprovação (<https://whatsappbusiness.com/policy/>, atualizada em 23/09/2026, consultada em 17/10/2026); BSPs como a 360dialog também recusam polícia | [whatsapp](whatsapp-viabilidade.md) · [10-3](fluxos/10-3-prestacao-e-mensagem-de-saque.md) · [ficha](fichas/comunicacao-e-viagens.md) | Bloqueado pela política da plataforma, não por falta de desenvolvimento. É prioridade do usuário: a preparação fica pronta e desligada (AUT-174) e a consulta formal à Meta (AUT-173) é o caminho para rever o bloqueio; até lá, portal, e-mail institucional, sino e o envio assistido com registro (AUT-172). | `EV-WHATSAPP-CANAL`, `ENTRADA-DEMANDAS-CANAIS` (2) |
| **AUT-11** | Canais · WhatsApp | Integração não oficial de WhatsApp (automação do WhatsApp Web, bibliotecas não oficiais, número pessoal) | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [whatsapp](whatsapp-viabilidade.md) · [ficha](fichas/comunicacao-e-viagens.md) | Contraria os termos do serviço, depende de número pessoal, esconde a identidade institucional e não dá trilha confiável; vetada em todos os fluxos. | `EV-WHATSAPP-CANAL` (1) |
| **AUT-12** | Referência EV · WhatsApp | Remover os resíduos do canal WhatsApp no EV em produção (unidade de serviço sem comando correspondente e configuração de webhook sem uso) | automação determinística suficiente | **1** | baixo | P | inexistente (os resíduos continuam lá; nenhuma integração ativa) | Acesso administrativo ao servidor do EV e ao painel da Meta (fora desta missão) | [whatsapp](whatsapp-viabilidade.md) | Tarefa única de manutenção na referência que evita tomar os resíduos por uma integração existente ou reativá-los por engano. | `EV-WHATSAPP-CANAL` (1) |
| **AUT-13** | Comunicações padronizadas | IA escolhendo destinatários ou redigindo avisos, respostas padrão ao solicitante e observações de despacho | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [ficha](fichas/comunicacao-e-viagens.md) | Destinatário e texto já são regra e modelo aprovado (textos prontos, marcadores, `TextoDespacho`); IA só introduziria variação em comunicação institucional. | `PLAT-NOTIF-SINO`, `EVT-DESPACHO-DG`, `PAL-ANDAMENTO-RESPOSTA` (3) |
| **AUT-172** | Canais · WhatsApp | WhatsApp assistido com registro (frente WA-1 do plano): o sistema monta a mensagem mínima pela função de domínio e o link `wa.me`; o operador envia do aparelho institucional; o sistema registra "enviado por WhatsApp manual" (`Comunicacao` com `origem = outro_meio`), quem e quando. Vale para o aviso de liberação, o link de km, documentos disponíveis e lembretes | melhor execução pelo próprio sistema | **2** | alto | P | parcial (`wa.me` sem texto mínimo nem registro em `gestao/viagens/views_prestacao.py:176-191`; registro declarativo em Palestras) | AUT-01, AUT-02, AUT-36; decisão D4a do plano (aparelho e número institucionais, nunca pessoais); perguntas P3/P4 da viabilidade | [plano](plano-implantacao.md) · [whatsapp](whatsapp-viabilidade.md) · [10-3](fluxos/10-3-prestacao-e-mensagem-de-saque.md) · [ficha](fichas/comunicacao-e-viagens.md) | Prioridade do usuário (17/10/2026): dá trilha ao canal que já é usado à mão, sem envio automático nem plataforma oficial. | derivado do plano (frente WA-1) |
| **AUT-173** | Canais · WhatsApp | Consulta formal de elegibilidade à Meta ou a provedor autorizado (frente WA-2): enviar as perguntas P1–P10 já redigidas, por canal oficial e com responsável designado pela PCPR, e arquivar a resposta | dependente de integração externa | **4** | alto | P | inexistente (perguntas redigidas; nenhum contato feito) | Decisão D4a do plano (quem envia e por qual canal) | [plano](plano-implantacao.md) · [whatsapp](whatsapp-viabilidade.md) · [ficha](fichas/comunicacao-e-viagens.md) | Única forma de rever o bloqueio: resposta escrita da Meta registrada em ADR. | derivado do plano (frente WA-2) |
| **AUT-174** | Canais · WhatsApp | Integração oficial do WhatsApp pronta e desligada (frente WA-3): porta `gestao/integracoes/whatsapp` (simulado e Cloud API), opt-in no `ContatoVerificado`, modelos *utility* para aprovação, webhook com `X-Hub-Signature-256`, mídia por id, status para `/entrega`, workflows n8n exportados desligados e testados contra simulador | dependente de integração externa | **5** | alto | G | inexistente | Construção: fundação da etapa 1 (2). Ativação: portão da WA-3 — autorização escrita da Meta (AUT-173), conta verificada, decisão formal e LGPD, modelos aprovados; achado T13 do protótipo resolvido | [plano](plano-implantacao.md) · [whatsapp](whatsapp-viabilidade.md) · [10-6](fluxos/10-6-recebimento-de-documentos.md) · [ficha](fichas/comunicacao-e-viagens.md) | Maturidade 5 para ativar (política vigente); construir e testar desligada está no plano, para ligar por configuração se a autorização vier. Único item de maturidade 5 fora de "inadequada", porque o bloqueio é externo e a construção é recomendada. | derivado do plano (frente WA-3); preparação de AUT-10 |

### 5.2 Viagens — AUT-14 a AUT-35 (22 itens)

| ID | Módulo / processo | Oportunidade | Classificação | Mat. | Valor | Esf. | Hoje | Dependências | Onde | Justificativa | Origens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **AUT-14** | Viagens · evento → viagem → documentos | Proposta consolidada: selecionar o evento, informar quem vai e conferir numa tela só roteiro, ofícios, diárias, termos, OS, plano, conflitos e pendências, sem gravar nem numerar até aprovar | melhor execução pelo próprio sistema | **2** | alto | G | parcial (o lote "quem vai" gera direto, sem prévia; o EV tem "Gerar documentos") | AUT-15, AUT-135, AUT-64; a mesma função monta a prévia e grava; numeração só no aprovar | [11-3](fluxos/11-3-autonomia-progressiva.md) · [plano](plano-implantacao.md) · [ficha](fichas/comunicacao-e-viagens.md) | É o objetivo operacional central e é regra pura do sistema (montagem, diárias, numeração); n8n não acrescenta, e a IA no máximo preenche lacunas de texto (AUT-81). | `VIA-EVENTO-SEMENTE-LOTE`, `VIA-LOTE-QUEM-VAI`, `EVT-GERAR-VIAGEM`, `GV-OFICIO-WIZARD`, `EV-PROPOSTA-DOCUMENTOS`, `GV-OS` (6) |
| **AUT-15** | Viagens · viagem e plano a partir da solicitação | Semente completa da viagem e do plano a partir da solicitação deferida (serviços → atividades, órgão/programa, efetivo, unidade móvel, motorista sugerido) | automação determinística suficiente | **2** | alto | M | parcial (só datas, destinos e unidade móvel chegam ao plano) | Decisão de produto: serviços substituem ou somam ao conjunto padrão; catálogo único de atividades (ADR 0044) | [11-3](fluxos/11-3-autonomia-progressiva.md) · [11-2](fluxos/11-2-textos-de-plano-de-trabalho.md) · [ficha](fichas/comunicacao-e-viagens.md) | Cópia determinística de dados já cadastrados elimina a remarcação do que o solicitante pediu e deixa ao operador só a conferência, com a origem de cada dado visível. | `VIA-VIAGEM-DE-SOLICITACAO`, `PT-CRIACAO-NUMERACAO`, `PT-ATIVIDADES-CONJUNTOS`, `VIA-PLANO` (4) |
| **AUT-16** | Viagens · deferimento | Preparar automaticamente, no deferimento, a viagem ou a proposta em rascunho, como assinante interno da outbox | melhor execução pelo próprio sistema | **2** | médio | P | parcial (hoje é botão na folha deferida, `gestao/viagens/de_eventos.py:10-14`; o EV gera automaticamente) | Decisão do dono do produto; AUT-100 | [11-3](fluxos/11-3-autonomia-progressiva.md) · [ficha](fichas/comunicacao-e-viagens.md) | Se adotada, é efeito interno do sistema com retentativa da outbox, não do n8n; a leitura de planos-rotas a julgou inadequada pelo risco de consumir números, risco que some se nada numerado for criado. | `VIA-VIAGEM-DE-SOLICITACAO`, `EVT-GERAR-VIAGEM`, `EV-DEFERIMENTO-GERA-VIAGEM`, `VIA-EVENTO-SEMENTE-LOTE` (4) |
| **AUT-17** | Viagens · quem vai | Sugestões explicáveis de equipe, motorista e viatura no "quem vai" | automação determinística suficiente | **2** | médio | M | inexistente | AUT-15 (opcional); histórico de ofícios emitidos | [11-3](fluxos/11-3-autonomia-progressiva.md) · [ficha](fichas/comunicacao-e-viagens.md) | Acelera a escolha com critério visível e ignorável, mantendo a decisão com a pessoa. | `VIA-LOTE-QUEM-VAI` (1) |
| **AUT-18** | Viagens · termos do lote | Termos gerados no lote com o nome da ação correta em vez do padrão "PCPR na Comunidade" | automação determinística suficiente | **2** | médio | P | existe com defeito | Confirmação do dono do produto | [11-3](fluxos/11-3-autonomia-progressiva.md) · [ficha](fichas/comunicacao-e-viagens.md) | Correção determinística de um texto que hoje sai errado em documento assinado. | `VIA-LOTE-QUEM-VAI` (1) |
| **AUT-19** | Viagens · ofício | Preencher automaticamente o ofício e o protocolo de origem do motorista externo (quando há um único candidato) | automação determinística suficiente | **2** | médio | P | inexistente (digitação manual de N/AAAA e do protocolo) | Nenhuma | [ficha](fichas/comunicacao-e-viagens.md) | Elimina uma pendência bloqueante frequente com busca exata no próprio banco, preenchendo só no caso inequívoco. | `VIA-OFICIO-RASCUNHO` (1) |
| **AUT-20** | Viagens · OS | Pré-atribuir as funções da Ordem de Serviço (condução ao motorista etc.) | automação determinística suficiente | **2** | médio | P | inexistente | Confirmar que todo modelo usa o código `conducao` para motorista | [ficha](fichas/comunicacao-e-viagens.md) | Menos cliques e menos OS incompletas com regra fixa; a OS só determina quem, onde, cronograma e função. | `VIA-OS` (1) |
| **AUT-21** | Viagens · documentos | Gerar e congelar na emissão as versões de termo, OS e plano (instantâneo dos dados, SHA-256, geração assíncrona) | melhor execução pelo próprio sistema | **2** | alto | M | parcial (o ofício tem versão; termo e OS têm impressão SHA-256 dos dados, `gestao/viagens/assinados.py:92-96`, mas são gerados na hora) | Decisão de produto (hoje gerar na hora é proposital) | [10-2](fluxos/10-2-envio-de-documentos.md) · [ficha](fichas/comunicacao-e-viagens.md) | Pré-requisito para afirmar que o que volta assinado é o que foi enviado e para substituir versões com aviso; é regra documental do sistema. | `VIA-TERMOS`, `PT-PENDENCIAS-FINALIZAR-GERAR`, `GV-DOC-GERACAO` (3) |
| **AUT-22** | Viagens · envio de documentos | Envio dos documentos emitidos (ofício, justificativa, termos, OS, plano) a cada servidor e destinatário: só o que é dele, na versão corrente, pelo portal e, com SMTP, por e-mail, com registro por pessoa | automação indicada com n8n | **2** | alto | G | parcial (há "Baixar documentos" e o envio é feito por fora, sem registro) | AUT-01, AUT-02, AUT-03, AUT-21; e-mail por AUT-06 (3); destinatário institucional pelo eProtocolo AUT-122 (4) | [10-2](fluxos/10-2-envio-de-documentos.md) · [ficha](fichas/comunicacao-e-viagens.md) | Elimina o envio pessoa a pessoa e cria o histórico que as retificações exigem; o PCPR decide o que cada um recebe, o n8n só transporta o e-mail, e o envio complementa a tramitação oficial (ponto a confirmar). | `VIA-PACOTES-ENVIO`, `VIA-TERMOS`, `PLAT-OUTBOX-ASSINANTES`, `VIA-OFICIO-EMISSAO`, `GV-TERMOS` (5) |
| **AUT-23** | Viagens · correção e cancelamento | Aviso de retificação, cancelamento ou reagendamento a quem já recebeu documentos da viagem | automação indicada com n8n | **3** | alto | M | inexistente (aviso feito de memória) | AUT-22 (registro de envios); AUT-06 | [10-2](fluxos/10-2-envio-de-documentos.md) · [ficha](fichas/comunicacao-e-viagens.md) | Só o registro de envios permite avisar exatamente quem recebeu a versão que deixou de valer, evitando deslocamento à toa e uso de documento vencido. | `VIA-VIAGEM-CICLO`, `VIA-OFICIO-CORRECAO` (2) |
| **AUT-24** | Viagens · avisos internos | Avisos aos operadores nos marcos da viagem: viagem gerada, plano gerado, PDF ou pacote pronto ou com falha definitiva | melhor execução pelo próprio sistema | **2** | médio | P | parcial (o sino existe; a falha definitiva do PDF só aparece na tela) | AUT-100; espelho externo opcional por AUT-06 | [11-3](fluxos/11-3-autonomia-progressiva.md) · [ficha](fichas/comunicacao-e-viagens.md) | Quem avisar e quando é regra do sistema e o sino já entrega a usuários internos; com AUT-06 nenhum workflow específico é necessário no n8n. | `VIA-VIAGEM-DE-SOLICITACAO`, `PT-PENDENCIAS-FINALIZAR-GERAR`, `GV-DOC-GERACAO`, `PLAT-OUTBOX-ASSINANTES` (4) |
| **AUT-25** | Viagens · prazo do ofício | Data-limite para emitir sem justificativa e aviso de "pronto para emitir" | automação determinística suficiente | **2** | alto | P | parcial (a antecedência é avaliada na emissão, sem aviso antecipado) | Nenhuma (regra em `gestao/viagens/dominio/prazos.py`) | [ficha](fichas/comunicacao-e-viagens.md) | A regra de antecedência já existe no domínio; antecipar o aviso reduz justificativas e convalidações evitáveis sem depender de canal externo. | `VIA-OFICIO-PRAZO-JUSTIFICATIVA`, `VIA-OFICIO-EMISSAO` (2) |
| **AUT-26** | Viagens · diárias | Alerta antecipado de tabela de diárias sem vigência | automação determinística suficiente | **2** | médio | P | inexistente | Nenhuma | [ficha](fichas/comunicacao-e-viagens.md) | Rotina interna simples evita descobrir na véspera que nenhum ofício pode ser emitido. | `VIA-OFICIO-DIARIAS` (1) |
| **AUT-27** | Viagens · numeração | Lembrete de rascunhos vazios que prendem números | automação determinística suficiente | **2** | baixo | P | inexistente | Nenhuma | [ficha](fichas/comunicacao-e-viagens.md) | Rotina interna reduz números presos e lacunas na sequência anual sem tocar no rascunho. | `VIA-OFICIO-CORRECAO` (1) |
| **AUT-28** | Cadastros · viagem próxima | Aviso de cadastro incompleto (CPF, cargo) de servidor escalado em viagem próxima | automação determinística suficiente | **2** | médio | P | inexistente | Nenhuma | [ficha](fichas/comunicacao-e-viagens.md) | Documento não sai sem CPF ou cargo; o aviso antes da véspera é consulta determinística. | `CAD-SERVIDORES-VIATURAS-CATALOGOS` (1) |
| **AUT-29** | Viagens · conflitos | Alerta proativo de conflitos de pessoa ou viatura nos próximos 7 dias e de conflito novo em ofício já emitido | automação determinística suficiente | **2** | alto | P | parcial (conflitos aparecem na tela, sem alerta) | Nenhuma externa (`gestao/plataforma/conflitos.py`, `gestao/viagens/conflitos.py`) | [ficha](fichas/comunicacao-e-viagens.md) | A detecção já existe; falta rodar e avisar pelo sino, e o n8n só entraria para espelhar o aviso por e-mail. | `VIA-CONFLITOS-DISPONIBILIDADE`, `PAINEL-AGENDA`, `AGENDA-ESCALA-PAUTA-ICS` (3) |
| **AUT-30** | Viagens · véspera | Aviso interno "sai amanhã" no sino para a equipe de viagens, com horário próprio | melhor execução pelo próprio sistema | **2** | médio | P | inexistente (fora por decisão registrada, `docs/migration/decisoes.md:205`) | AUT-109 (horário por rotina) | [10-4](fluxos/10-4-link-de-km-na-vespera.md) · [ficha](fichas/comunicacao-e-viagens.md) | Funciona sem n8n e é a base do gatilho da véspera; precisa de horário próprio, porque a rotina atual roda às 05:40 ou no primeiro acesso. | `VIA-VESPERA-SAIDA` (1) |
| **AUT-31** | Viagens · prontidão | Resumo diário por unidade das viagens próximas (D-7 a D0): ofícios em rascunho, justificativa pendente, planos não gerados ou vazios, termos sem via assinada, eventos deferidos sem proposta | automação indicada com n8n | **3** | alto | P | parcial (o quadro de prontidão por viagem existe) | AUT-104, AUT-109 (o PCPR monta o resumo com a política de cada destinatário; o token de transporte do n8n não chama ferramentas), AUT-06 | [11-3](fluxos/11-3-autonomia-progressiva.md) · [ficha](fichas/comunicacao-e-viagens.md) | O conteúdo já é calculado pelo quadro de prontidão; o PCPR agrega por unidade na rotina e o n8n entrega (§10, item 14), poupando a abertura viagem por viagem. | `VIA-CONFERENCIA`, `GV-OFICIO-WIZARD`, `GV-JUSTIFICATIVA`, `PT-CICLO-VIDA-LISTA`, `GV-TERMOS` (5) |
| **AUT-32** | Viagens · disponibilidade | Fonte de indisponibilidade de servidores (férias, afastamentos) nos conflitos | dependente de integração externa | **4** | médio | M | inexistente | Fonte oficial de RH desconhecida; expor só "indisponível" (LGPD) | [ficha](fichas/comunicacao-e-viagens.md) | Evita escalar quem estará ausente, mas depende de uma fonte institucional que não se sabe se existe nem se tem API. | `VIA-CONFLITOS-DISPONIBILIDADE` (1) |
| **AUT-33** | Viagens · quem vai | IA escolhendo quem participa, a equipe ou a viatura | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [11-3](fluxos/11-3-autonomia-progressiva.md) · [ficha](fichas/comunicacao-e-viagens.md) | Decisão de gestão com responsabilização e risco de viés; as sugestões explicáveis de AUT-17 bastam. | `VIA-LOTE-QUEM-VAI`, `EV-PROPOSTA-DOCUMENTOS` (2) |
| **AUT-34** | Viagens · diárias | IA calculando ou ajustando diárias (ofício ou plano) | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [ficha](fichas/comunicacao-e-viagens.md) | O cálculo normativo determinístico já existe (`gestao/viagens/dominio/diarias.py`); IA só traria risco de erro financeiro em documento oficial. | `PT-DIARIAS`, `VIA-OFICIO-DIARIAS` (2) |
| **AUT-35** | Viagens · atos oficiais | Emitir, finalizar, retificar, reabrir, cancelar ou excluir documentos e viagens automaticamente | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [11-3](fluxos/11-3-autonomia-progressiva.md) · [ficha](fichas/comunicacao-e-viagens.md) | São atos oficiais e irreversíveis que a ADR 0020 manda passar por aprovação humana; a automação só prepara e avisa. | `VIA-OFICIO-EMISSAO`, `VIA-OFICIO-CORRECAO`, `VIA-VIAGEM-CICLO`, `PT-PENDENCIAS-FINALIZAR-GERAR`, `PT-CICLO-VIDA-LISTA` (5) |

### 5.3 Prestação de contas e documentos — AUT-36 a AUT-63 (28 itens)

| ID | Módulo / processo | Oportunidade | Classificação | Mat. | Valor | Esf. | Hoje | Dependências | Onde | Justificativa | Origens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **AUT-36** | Prestação · aviso de liberação | Aviso de liberação de diárias ("mensagem de saque"): texto e situação como função de domínio testada, com registro de quem foi avisado | automação determinística suficiente | **2** | alto | M | parcial (link `wa.me` montado na view, `gestao/viagens/views_prestacao.py:176-191`, sem registro) | Texto institucional aprovado; AUT-01 | [10-3](fluxos/10-3-prestacao-e-mensagem-de-saque.md) · [ficha](fichas/prestacao-e-documentos.md) | Dá paridade com a produção e uma base única para o link manual, o envio automático e o assistente, sem IA e sem canal externo. | `PREST-MENSAGEM-SAQUE`, `GV-PREST-AVISO-DIARIAS` (2) |
| **AUT-37** | Prestação · aviso de liberação | Envio automático do aviso de liberação pelo canal institucional no dia em que a liberação é registrada | automação indicada com n8n | **3** | alto | M | inexistente | AUT-36, AUT-02, AUT-04, AUT-06; o registro humano da liberação é o único gatilho | [10-3](fluxos/10-3-prestacao-e-mensagem-de-saque.md) · [ficha](fichas/prestacao-e-documentos.md) | O PCPR decide quando o aviso é devido e guarda o estado; o n8n transporta por e-mail; pelo WhatsApp, só o envio assistido com registro (AUT-172), com a plataforma oficial bloqueada (AUT-10). | `PREST-MENSAGEM-SAQUE`, `PLAT-ROTINAS-DIARIAS`, `GV-PREST-AVISO-DIARIAS`, `EV-MENSAGEM-LIBERACAO`, `PREST-SOLICITACAO-LIBERACAO` (5) |
| **AUT-38** | Prestação · prazos | Lembretes ao servidor: saque vencendo, prestação vencida e o que entregar após o retorno, até o comprovante entrar | automação indicada com n8n | **3** | alto | P | parcial (avisos só para operadores no sino, `gestao/viagens/avisos.py:47-87`) | AUT-37; prazos já calculados (`gestao/viagens/dominio/prestacao.py:85-130`) | [10-3](fluxos/10-3-prestacao-e-mensagem-de-saque.md) · [ficha](fichas/prestacao-e-documentos.md) | Hoje o operador lê o sino e cobra por fora; levar o lembrete ao interessado reduz prestações vencidas, e ele para quando o comprovante é anexado. | `PREST-AVISOS-PRAZOS`, `EV-AVISOS-PRESTACAO`, `GV-PREST-ABERTURA` (3) |
| **AUT-39** | Prestação · pendências | Resumo de pendências da prestação por equipe (diário) e de prestações paradas (semanal) | automação indicada com n8n | **3** | médio | P | parcial (abas de cobrança e pendências na lista) | AUT-105, AUT-06 | [ficha](fichas/prestacao-e-documentos.md) | Agregação agendada e entrega são borda; as pendências já são calculadas pelo sistema. | `PREST-PENDENCIAS-FINALIZACAO`, `GV-PREST-CONSOLIDADO` (2) |
| **AUT-40** | Prestação · Diário de Bordo | Link de quilometragem por trecho para o motorista (página que funciona sem sinal no celular, token em hash) | dependente de desenvolvimento | **2** | alto | G | só na referência (o EV tem o fluxo m096; o sistema novo não) | ADR nova de link público; AUT-03; AUT-02 | [10-4](fluxos/10-4-link-de-km-na-vespera.md) · [ficha](fichas/prestacao-e-documentos.md) | Os km passam a ser anotados no momento, por trecho, com a distância prevista à vista, e o Diário de Bordo fica pronto na chegada. | `PREST-DIARIO-LINK-CAMPO`, `GV-PREST-DIARIO`, `EV-DIARIO-LINK-KM` (3) |
| **AUT-41** | Prestação · véspera | Envio do link de km na véspera (America/Sao_Paulo) e lembretes pelo canal institucional | automação indicada com n8n | **3** | alto | P | inexistente | AUT-40, AUT-06, AUT-30; horário da véspera e quem recebe quando há vários veículos (decisões) | [10-4](fluxos/10-4-link-de-km-na-vespera.md) · [ficha](fichas/prestacao-e-documentos.md) | Ninguém precisa lembrar de mandar o link; reagendar revoga e reenvia, e sem n8n o operador entrega o mesmo link pela tela. | `PREST-DIARIO-LINK-CAMPO`, `VIA-VESPERA-SAIDA`, `GV-PREST-DIARIO`, `EV-DIARIO-LINK-KM`, `PLAT-ROTINAS-DIARIAS`, `ROT-PLANEJADO-REALIZADO-KM`, `PREST-AVISOS-PRAZOS` (7) |
| **AUT-42** | Prestação · Diário de Bordo | Km inicial do diário pré-preenchido pelo último km da viatura | automação determinística suficiente | **2** | médio | P | inexistente | Nenhuma | [ficha](fichas/prestacao-e-documentos.md) | Menos digitação e menos avisos de "hodômetro voltou" com uma consulta ao último diário da viatura. | `PREST-DIARIO-PREENCHIMENTO` (1) |
| **AUT-43** | Prestação · viagem realizada | Sugerir os horários realizados a partir dos lançamentos do link de km | automação determinística suficiente | **2** | médio | P | inexistente | AUT-40 | [10-4](fluxos/10-4-link-de-km-na-vespera.md) · [ficha](fichas/prestacao-e-documentos.md) | Corrige horários e diárias realizadas sem redigitar, como sugestão que o operador aceita. | `PREST-VIAGEM-REALIZADA` (1) |
| **AUT-44** | Prestação · Diário de Bordo | Validação de continuidade do km (saltos e retrocessos) e de prontidão do DB antes de assinar | automação determinística suficiente | **2** | médio | P | parcial (o aviso de hodômetro que volta existe; limiar de salto não) | Limiar institucional | [10-4](fluxos/10-4-link-de-km-na-vespera.md) · [ficha](fichas/prestacao-e-documentos.md) | Regra numérica simples que pega erro de digitação antes de o DB ir para assinatura. | `GV-PREST-DIARIO` (1) |
| **AUT-45** | Prestação · Diário de Bordo | DB com motorista de outro ofício: signatário correto e direcionamento correto do assinado | automação determinística suficiente | **2** | médio | P | parcial | Confirmação da regra de quem assina o DB | [10-5](fluxos/10-5-db-e-rt-para-assinatura.md) · [ficha](fichas/prestacao-e-documentos.md) | Evita anexar o DB assinado no ofício errado e mandar a assinatura a quem não dirigiu. | `DOC-IMPORTACAO-IDENTIFICACAO`, `GV-PREST-DIARIO` (2) |
| **AUT-46** | Prestação · DB e RT | DB e RT prontos para assinatura: conclusão explícita, versão congelada (instantâneo e SHA-256), assinante pela regra do documento, devolução ligada à versão e aviso ao operador | melhor execução pelo próprio sistema | **2** | alto | M | inexistente (gerados na hora por GET, sem versão) | AUT-44, AUT-53 | [10-5](fluxos/10-5-db-e-rt-para-assinatura.md) · [ficha](fichas/prestacao-e-documentos.md) | Sem versão congelada não há como afirmar que o assinado corresponde ao preparado; é regra documental do sistema e funciona sem n8n. | `PREST-DOCS-GERACAO`, `GV-PREST-ASSINATURA` (2) |
| **AUT-47** | Prestação · DB e RT | Disponibilizar DB e RT ao signatário pelo portal e avisar por e-mail, com lembrete antes do prazo | automação indicada com n8n | **3** | alto | M | inexistente (download e envio por fora) | AUT-46, AUT-03, AUT-06 | [10-5](fluxos/10-5-db-e-rt-para-assinatura.md) · [ficha](fichas/prestacao-e-documentos.md) | Acaba a cobrança manual de assinaturas; o n8n só avisa e lembra, e o documento fica no portal, não anexado. | `PREST-DOCS-ENVIO-ASSINATURA`, `EV-DB-RT-ASSINATURA`, `GV-PREST-ASSINATURA` (3) |
| **AUT-48** | Prestação · RT | Relato do servidor (o que fez, público, intercorrências) coletado por link | dependente de desenvolvimento | **2** | médio | M | inexistente | AUT-03, AUT-02; decisão de quem responde | [10-5](fluxos/10-5-db-e-rt-para-assinatura.md) · [ficha](fichas/prestacao-e-documentos.md) | Quem participou escreve o que fez e o operador só revisa; é também a matéria-prima honesta para o rascunho de RT. | `PREST-RT-PREENCHIMENTO` (1) |
| **AUT-49** | Prestação · RT | RT sem afirmações não verificadas por padrão (ex.: "sem intercorrências") | automação determinística suficiente | **2** | médio | P | parcial (o RT nasce com textos prontos e conta como preenchido sem ninguém escrever) | Nenhuma | [10-5](fluxos/10-5-db-e-rt-para-assinatura.md) · [ficha](fichas/prestacao-e-documentos.md) | Evita declaração falsa em documento assinado com uma mudança de regra, antes de qualquer IA. | `EV-RT-SUGESTAO` (1) |
| **AUT-50** | Prestação · RT | Rascunho do RT por IA ancorado nos dados do sistema, no plano e no relato do servidor | assistência por IA indicada | **3** | médio | M | inexistente | AUT-48, AUT-96, AUT-91; provedor e orçamento; ADR nova (a ADR 0041 veda enviar documentos a IA externa na importação); 4 se exigir aval institucional/LGPD | [10-5](fluxos/10-5-db-e-rt-para-assinatura.md) · [ficha](fichas/prestacao-e-documentos.md) | Redação é onde a IA ajuda, desde que use só dados fornecidos, rotule a sugestão e exija aceite, porque o RT é assinado. | `PT-RESULTADOS-RELATORIO`, `PREST-RT-PREENCHIMENTO`, `GV-PREST-RT`, `EV-RT-SUGESTAO` (4) |
| **AUT-51** | Prestação · prazos | Feriados no cálculo de dias úteis (prazo da prestação e data do RT) | automação determinística suficiente | **2** | baixo | P | inexistente (feriados não são considerados) | Cadastro de feriados estaduais e municipais; confirmação da regra | [ficha](fichas/prestacao-e-documentos.md) | Prazo calculado errado em semana de feriado gera cobrança indevida; é regra de calendário, não automação externa. | `GV-PREST-RT` (1) |
| **AUT-52** | Documentos · recebimento | Recebimento de documentos devolvidos pelo servidor: portal por link e ingestão autenticada na importação documental, com rastro de remetente e resposta padronizada | dependente de desenvolvimento | **2** | alto | M | parcial (a importação com fila, OCR, identificação e revisão existe; não há entrada pelo servidor) | AUT-01, AUT-02, AUT-03, AUT-104, AUT-112 | [10-6](fluxos/10-6-recebimento-de-documentos.md) · [ficha](fichas/prestacao-e-documentos.md) | Reaproveita a leitura e o direcionamento que já existem e acrescenta só a porta de entrada e o rastro de quem mandou e em resposta a quê. | `DOC-IMPORTACAO-ENTRADA`, `GV-DOC-ASSINADO-MANUAL` (2) |
| **AUT-53** | Documentos · conferência | Conferência de via assinada (ADR 0022) estendida a DB, RT e plano e feita no original antes de separar páginas | automação determinística suficiente | **2** | alto | M | parcial (vale para ofício, justificativa, termo e OS) | Definição de quem assina o DB | [10-5](fluxos/10-5-db-e-rt-para-assinatura.md) · [10-6](fluxos/10-6-recebimento-de-documentos.md) · [ficha](fichas/prestacao-e-documentos.md) | O aviso de "assinados recebidos" passa a dizer se o documento certo foi assinado por quem devia, sem abrir o PDF. | `DOC-VIA-ASSINADA-CONFERENCIA`, `PT-ASSINATURA-CIRCULACAO` (3) |
| **AUT-54** | Documentos · importação | Persistir o texto/OCR de cada parte importada | automação determinística suficiente | **2** | médio | P | inexistente | Política de retenção (o texto contém CPF) | [10-6](fluxos/10-6-recebimento-de-documentos.md) · [ficha](fichas/prestacao-e-documentos.md) | A leitura e a conferência passam a funcionar em digitalizados que já passaram por OCR. | `DOC-IMPORTACAO-ENTRADA` (1) |
| **AUT-55** | Documentos · comprovantes | Comprovante: extrair valor, data e operação na entrada e casar pela janela de saque e pelo valor | automação determinística suficiente | **2** | médio | P | parcial (a conferência valor × diária existe, com clique extra) | AUT-54; liberação e prazo preenchidos | [10-6](fluxos/10-6-recebimento-de-documentos.md) · [ficha](fichas/prestacao-e-documentos.md) | Comprovantes que não citam o ofício passam a ser distribuídos sem revisão quando o caso é inequívoco. | `DOC-IMPORTACAO-IDENTIFICACAO`, `PREST-ANEXOS` (2) |
| **AUT-56** | Prestação · carimbo | Posição automática do carimbo do nº da solicitação pela linha do servidor no PDF | automação determinística suficiente | **2** | médio | P | parcial (ajuste manual por servidor) | Ofício com camada de texto | [ficha](fichas/prestacao-e-documentos.md) | Regra geométrica sobre o texto do PDF elimina o ajuste manual. | `PREST-CARIMBO` (1) |
| **AUT-57** | Documentos · importação | IA só como sugestão de tipo e destino na revisão da importação | assistência por IA indicada | **3** | baixo | M | inexistente | AUT-96; ADR nova; corpus de avaliação | [10-6](fluxos/10-6-recebimento-de-documentos.md) · [ficha](fichas/prestacao-e-documentos.md) | Ajuda só nos documentos sem título reconhecível e sempre na revisão humana; o classificador determinístico continua sendo a fonte. | `DOC-IMPORTACAO-IDENTIFICACAO` (1) |
| **AUT-58** | Documentos · comprovantes e NFS-e | Extração por IA de campos de comprovantes e NFS-e de layout desconhecido (só sugestão) | assistência por IA indicada | **3** | baixo | M | inexistente | AUT-54, AUT-96; minimização (só a página relevante) | [ficha](fichas/prestacao-e-documentos.md) · [ficha](fichas/plataforma-e-modulos.md) | As regras cobrem a maioria; a IA entra como sugestão para layouts que elas não leem, sem aceitar valor sem leitura humana. | `PREST-LEITURA-CONFERENCIA`, `CB-LEITURA-PDFS` (2) |
| **AUT-59** | Prestação · assinatura | Assinatura eletrônica simples por link público feita pelo próprio sistema (como o GV faz com RT e DB) | inadequada ou inviável atualmente | **5** | médio | — | só na referência (o GV assina RT e DB por link público com token, CPF e expiração) | Decisão jurídica e institucional | [10-5](fluxos/10-5-db-e-rt-para-assinatura.md) · [ficha](fichas/prestacao-e-documentos.md) | Validade jurídica e verificação de identidade dependem de decisão institucional; a assinatura digital de ofícios já é feita no eProtocolo, e o caminho recomendado é assinar fora e devolver pelo portal. | `PREST-DOCS-ENVIO-ASSINATURA` (1) |
| **AUT-60** | Prestação · finalização | Finalização automática da prestação | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [ficha](fichas/prestacao-e-documentos.md) | Finalizar trava documentos e é decisão de quem confere; a automação só mostra o que falta. | `PREST-PENDENCIAS-FINALIZACAO` (1) |
| **AUT-61** | Documentos · importação | IA decidindo o destino dos documentos importados | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [10-6](fluxos/10-6-recebimento-de-documentos.md) · [ficha](fichas/prestacao-e-documentos.md) | Anexar no lugar errado tem efeito na prestação; a IA fica restrita à sugestão na revisão (AUT-57). | `EV-IMPORTACAO-PROCESSO` (1) |
| **AUT-62** | Prestação · Diário de Bordo | Leitura automática do km por foto do hodômetro | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [10-4](fluxos/10-4-link-de-km-na-vespera.md) · [ficha](fichas/prestacao-e-documentos.md) | Erro de leitura viraria dado oficial do DB com ganho pequeno sobre a digitação por trecho; o fluxo 10-4 também não recomenda agora. | `EV-DIARIO-LINK-KM` (1) |
| **AUT-63** | Prestação · carimbo | IA no carimbo do nº da solicitação | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [ficha](fichas/prestacao-e-documentos.md) | O carimbo é posição e texto determinísticos; IA não acrescenta. | `GV-PREST-DOCUMENTOS-CARIMBO` (1) |

### 5.4 Planos, rotas e IA — AUT-64 a AUT-98, AUT-171 (36 itens)

| ID | Módulo / processo | Oportunidade | Classificação | Mat. | Valor | Esf. | Hoje | Dependências | Onde | Justificativa | Origens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **AUT-64** | Rotas · proposta de roteiro | Proposta determinística de roteiro a partir da viagem ou do evento (sede → município → sede, horários calculados, alternativas com diferença em km e diárias) | automação determinística suficiente | **2** | alto | M | inexistente (o roteiro nasce vazio) | Parâmetros da unidade (antecedência, pernoite na véspera: regra não está no código); horário do evento na solicitação | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [ficha](fichas/comunicacao-e-viagens.md) | Distância, tempo, chegada e diárias já saem do código; propor o roteiro pronto para conferir poupa a montagem trecho a trecho, sem IA. | `ROT-PROPOSTA-ROTEIRO-DO-EVENTO`, `VIA-ROTEIRO` (2) |
| **AUT-65** | Rotas · trechos | Fonte do km e do tempo registrada no trecho e "Usar roteiro" preservando km e tempos | melhor execução pelo próprio sistema | **2** | médio | P | parcial (km e tempos não guardam a fonte) | Migração aditiva | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [ficha](fichas/comunicacao-e-viagens.md) | Distingue rota real de estimativa em documentos, diário e auditoria e evita perder km já conferidos. | `ROT-ITINERARIO-TRECHOS`, `ROT-ROTEIRO-CADASTRADO` (2) |
| **AUT-66** | Rotas · provedor | Provedor de rotas de produção atrás de porta (`gestao/integracoes/rotas`): OSRM próprio ou OpenRouteService com chave | dependente de integração externa | **3** | alto | M | parcial (OSRM, ORS e estimativa com cache existem; em produção a estimativa é linha reta × 1,3) | Decisão de provedor; memória do pré-processamento OSRM a medir; plano gratuito do ORS com 2.000 rotas/dia e 40/min no host novo `api.heigit.org/openrouteservice` (<https://giscience.github.io/openrouteservice/frequently-asked-questions.html>, consultada em 17/10/2026); o host antigo foi depreciado em 28/04/2026 e opera com cota reduzida ([12 custos](desempenho-e-custos.md) §14.6) | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [12 custos](desempenho-e-custos.md) · [ficha](fichas/comunicacao-e-viagens.md) | Km confiáveis afetam diárias e a conferência do hodômetro; é decisão de provedor, não de automação. | `ROT-CALCULO-ROTA-CACHE`, `INT-ROTAS` (2) |
| **AUT-67** | Rotas · ordem | Ordem sugerida dos destinos por menor percurso | automação determinística suficiente | **2** | médio | P | inexistente | AUT-66 para valer (com a estimativa a ordem é aproximada) | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [ficha](fichas/comunicacao-e-viagens.md) | Cálculo determinístico apresentado como sugestão; a agenda dos municípios pode justificar outra ordem. | `ROT-ITINERARIO-TRECHOS`, `VIA-ROTEIRO`, `INT-ROTAS` (3) |
| **AUT-68** | Rotas · roteiros cadastrados | Sugerir roteiro cadastrado compatível com os destinos da viagem | automação determinística suficiente | **2** | médio | P | inexistente | Nenhuma | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [ficha](fichas/comunicacao-e-viagens.md) | Reaproveita percursos já conferidos com uma busca simples. | `ROT-ROTEIRO-CADASTRADO` (1) |
| **AUT-69** | Rotas · itinerário | Aviso de chegada incompatível com o início do atendimento | automação determinística suficiente | **2** | médio | P | inexistente | Margem institucional mínima (não definida); horário do catálogo é texto livre | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [ficha](fichas/comunicacao-e-viagens.md) | Evita equipe chegando depois do horário com uma comparação simples. | `ROT-ITINERARIO-TRECHOS` (1) |
| **AUT-70** | Rotas · bate-volta | Sugestão bate-volta × pernoite pelo tempo de estrada | automação determinística suficiente | **2** | médio | P | inexistente | Regra institucional de jornada (não existe no código) | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [ficha](fichas/comunicacao-e-viagens.md) | Ajuda a decisão com dado de rota, mas só como sugestão enquanto não houver norma. | `ROT-BATE-VOLTA` (1) |
| **AUT-71** | Rotas · bate-volta | Aplicar o tempo de veículo lento no bate-volta | melhor execução pelo próprio sistema | **2** | baixo | P | parcial | Definir de onde vem o "lento" no roteiro (o roteiro não tem viatura) | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [ficha](fichas/comunicacao-e-viagens.md) | Tempos corretos para unidade móvel pesada com a regra que já existe no ofício. | `ROT-BATE-VOLTA` (1) |
| **AUT-72** | Rotas · recálculo | Recalcular rotas desatualizadas (repetição em outra cidade, mudança de roteiro ou de tabela) e avisar divergência de diárias, só em rascunhos | automação determinística suficiente | **2** | médio | P | parcial (a repetição desloca datas sem recalcular a rota) | Cota do provedor | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [ficha](fichas/comunicacao-e-viagens.md) | Evita documento com tempo ou diária defasados sem tocar no que já foi emitido. | `VIA-REPETIR-VIAGEM`, `GV-ROTEIRO-DIARIAS` (2) |
| **AUT-73** | Rotas · cache | Aquecimento do cache de distâncias a partir da sede de cada unidade | automação determinística suficiente | **2** | baixo | P | inexistente | AUT-66; política de taxa | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [ficha](fichas/comunicacao-e-viagens.md) | Respostas instantâneas e menos chamadas externas no horário de uso. | `ROT-CALCULO-ROTA-CACHE` (1) |
| **AUT-74** | Rotas · API | Limitar e tornar assíncrona a API de rota | melhor execução pelo próprio sistema | **2** | médio | M | inexistente | Nenhuma externa | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [ficha](fichas/comunicacao-e-viagens.md) | Protege os poucos workers web quando automações pedirem muitas rotas. | `ROT-CALCULO-ROTA-CACHE` (1) |
| **AUT-75** | Rotas · texto | Descrição do roteiro em texto por modelo fixo a partir dos trechos calculados | automação determinística suficiente | **2** | baixo | P | inexistente | Nenhuma | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [ficha](fichas/comunicacao-e-viagens.md) | Um modelo de frase sobre dados já calculados resolve; a leitura do EV sugeria IA, mas ela não acrescenta e pode errar (o 11-1 também não a recomenda na 1ª entrega). | `EV-ROTA-DISTANCIA` (1) |
| **AUT-76** | Rotas · leitura da programação | Leitura da programação por IA: pedido, e-mail ou anexo em texto livre → proposta estruturada de destinos, datas e horários para conferência | assistência por IA indicada | **3** | médio | M | inexistente (a extração de texto de anexos existe) | AUT-64, AUT-96, AUT-91, AUT-105; provedor, credencial, custo e decisão LGPD | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [ficha](fichas/comunicacao-e-viagens.md) | Interpretar texto livre é o uso certo da IA; o sistema valida município e datas e a pessoa aplica, e a IA nunca estima distância nem define diária. | `ROT-ITINERARIO-TRECHOS`, `VIA-ROTEIRO`, `ROT-PROPOSTA-ROTEIRO-DO-EVENTO`, `GV-ROTEIRO-DIARIAS`, `VIA-VIAGEM-DADOS` (5) |
| **AUT-77** | Rotas | IA calculando rotas, distâncias ou tempos | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [11-1](fluxos/11-1-rotas-e-roteiros.md) · [ficha](fichas/comunicacao-e-viagens.md) | Distância inventada contamina diárias, chegada e conferência do hodômetro; o cálculo já é determinístico. | `ROT-CALCULO-ROTA-CACHE`, `INT-ROTAS`, `EV-ROTA-DISTANCIA` (3) |
| **AUT-78** | Planos · coerência | Divergências entre plano e ofícios (datas, efetivo, diárias) com "atualizar do ofício" | melhor execução pelo próprio sistema | **2** | médio | M | parcial (o plano herda dados dos ofícios na criação) | Regra do que é divergência relevante (multievento, equipes de apoio) | [ficha](fichas/comunicacao-e-viagens.md) | Detecta plano subestimado ou desatualizado antes da assinatura com comparação no próprio sistema. | `PT-HERANCA-OFICIOS`, `PT-DIARIAS` (2) |
| **AUT-79** | Planos · textos | Texto-base de contextualização por programa cadastrado pelo gestor | automação determinística suficiente | **2** | médio | P | inexistente | Aprovação dos textos pela ASCOM (4 se exigir aval formal, segundo o 11-2) | [11-2](fluxos/11-2-textos-de-plano-de-trabalho.md) · [ficha](fichas/comunicacao-e-viagens.md) | Alternativa sem IA que já resolve a maioria dos planos com texto aprovado. | `PT-TEXTOS-AUTOMATICOS` (1) |
| **AUT-80** | Planos · textos | Rascunho por IA da contextualização e das considerações do Plano de Trabalho a partir da solicitação e dos dados reais, com validador de fatos | assistência por IA indicada | **3** | médio | M | inexistente | AUT-79 antes; AUT-96, AUT-91; provedor; validação do tom pela ASCOM; 4 se exigir aval institucional | [11-2](fluxos/11-2-textos-de-plano-de-trabalho.md) · [ficha](fichas/comunicacao-e-viagens.md) | Redação contextual é onde a IA ajuda, restrita às atividades já escolhidas e sempre com aceite humano antes de entrar no documento. | `PT-TEXTOS-AUTOMATICOS`, `VIA-PLANO`, `EVT-GERAR-VIAGEM`, `GV-PLANO-TRABALHO`, `EV-PROPOSTA-DOCUMENTOS` (5) |
| **AUT-81** | Viagens · ofício e justificativa | Rascunho por IA do motivo do ofício e da justificativa por antecedência insuficiente | assistência por IA indicada | **3** | médio | M | inexistente | AUT-96, AUT-91; base legal da justificativa a confirmar; provedor | [11-3](fluxos/11-3-autonomia-progressiva.md) · [ficha](fichas/comunicacao-e-viagens.md) | Reduz a redação nas viagens urgentes, que são as que exigem justificativa, com campos citados e revisão obrigatória. | `VIA-EVENTO-SEMENTE-LOTE`, `VIA-OFICIO-PRAZO-JUSTIFICATIVA`, `GV-OFICIO-WIZARD`, `GV-JUSTIFICATIVA` (4) |
| **AUT-82** | Planos · editor | Aviso de texto editado desatualizado após mudança de dados | melhor execução pelo próprio sistema | **2** | médio | P | parcial (há impressão de dados; reexibição não confirmada) | Nenhuma | [11-2](fluxos/11-2-textos-de-plano-de-trabalho.md) · [ficha](fichas/comunicacao-e-viagens.md) | Evita PDF com valores antigos depois de um recálculo. | `PT-EDITOR-TEXTO` (1) |
| **AUT-83** | Planos · resultados | Lembrete de lançamento de resultados após o fim do evento | automação determinística suficiente | **2** | médio | P | inexistente | Prazo institucional não definido; coordenador digitado à mão não tem conta | [ficha](fichas/comunicacao-e-viagens.md) | A regra (evento terminou e não há resultados) é do sistema e o sino alcança o operador; o n8n só entraria para quem está fora do sistema. | `PT-RESULTADOS-RELATORIO` (1) |
| **AUT-84** | Planos · multievento | Criar evento adicional do plano a partir de outra solicitação ou ofício da mesma viagem | melhor execução pelo próprio sistema | **2** | baixo | M | inexistente | Confirmar se uma viagem agrega várias solicitações | [ficha](fichas/comunicacao-e-viagens.md) | Monta planos itinerantes sem redigitação; é regra de produto. | `PT-MULTIEVENTO` (1) |
| **AUT-85** | Cadastros · catálogo de atividades | Detecção de possíveis duplicatas no catálogo de serviços e atividades (só sugestão) | automação determinística suficiente | **2** | baixo | M | inexistente | Tela de revisão | [ficha](fichas/comunicacao-e-viagens.md) | Reduz variantes sem fundir por nome, o que a ADR 0044 proíbe. | `CAD-CATALOGO-ATIVIDADES` (1) |
| **AUT-86** | Cadastros · catálogo de atividades | Rascunho por IA de meta e recurso para serviços sem complemento | assistência por IA indicada | **3** | baixo | P | inexistente | AUT-96; tela de revisão | [ficha](fichas/comunicacao-e-viagens.md) | Acelera completar o catálogo, sempre aprovado pelo gestor; ganho pequeno e pontual. | `CAD-CATALOGO-ATIVIDADES` (1) |
| **AUT-87** | Documentos oficiais | IA redigindo ou editando texto determinativo de documento oficial (OS; coordenação, atividades, metas e recursos do plano; regiões do documento) | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [11-2](fluxos/11-2-textos-de-plano-de-trabalho.md) · [ficha](fichas/comunicacao-e-viagens.md) | Esses textos já são determinísticos a partir do cadastro; IA introduziria variação em texto normativo e risco de valor divergente dos dados. | `PT-TEXTOS-AUTOMATICOS`, `GV-PLANO-TRABALHO`, `VIA-OS`, `PT-EDITOR-TEXTO` (4) |
| **AUT-88** | Assistente · servidores | Assistente de dúvidas dos servidores (só leitura): situação da própria viagem, diárias, prazos, documentos e procedimentos | assistência por IA indicada | **3** | médio | G | inexistente (o EV teve um assistente com LLM, removido do produto) | AUT-97, AUT-02, AUT-03, AUT-105, AUT-96, AUT-91; base de conhecimento aprovada; provedor e LGPD | [10-1](fluxos/10-1-assistente-dos-servidores.md) · [ficha](fichas/plataforma-e-modulos.md) | Responder dúvidas repetitivas com dado real e procedimento citado tira carga da equipe, desde que a identidade do servidor limite o que ele vê e a IA diga o que não sabe. | `API-FERRAMENTAS`, `GV-ASSISTENTE-DUVIDAS`, `EV-IA-ASSISTENTE` (3) |
| **AUT-89** | Assistente · operadores | Explicar em linguagem simples o que falta numa viagem (operadores) | assistência por IA indicada | **3** | baixo | M | inexistente | AUT-105, AUT-96 | [10-1](fluxos/10-1-assistente-dos-servidores.md) · [11-3](fluxos/11-3-autonomia-progressiva.md) · [ficha](fichas/plataforma-e-modulos.md) | O quadro de prontidão já lista as pendências de forma determinística; a IA só reformularia, por isso o valor é baixo. | `VIA-CONFERENCIA` (1) |
| **AUT-90** | Assistente | Reinstalar o assistente do EV ou copiar o seu código | inadequada ou inviável atualmente | **5** | baixo | — | só na referência (removido do produto) | — | [10-1](fluxos/10-1-assistente-dos-servidores.md) · [ficha](fichas/plataforma-e-modulos.md) | O EV é referência, nunca código-base (regra do repositório), e o app foi removido do produto. | `EV-IA-ASSISTENTE` (1) |
| **AUT-91** | IA · avaliação | Conjunto de avaliação com gabarito (casos fictícios novos) para leituras por regra e por IA | automação determinística suficiente | **2** | médio | P | só na referência (o EV tem bateria-gabarito) | Casos fictícios escritos para o sistema novo (sem copiar a referência) | [10-1](fluxos/10-1-assistente-dos-servidores.md) · [11-2](fluxos/11-2-textos-de-plano-de-trabalho.md) · [ficha](fichas/plataforma-e-modulos.md) | Mede cada mudança campo a campo antes de ligar qualquer IA; sem ele não há como afirmar "nenhum fato fora dos dados". | `EV-LEITURA-PEDIDO` (1) |
| **AUT-92** | Entrada de pedidos | Extração por IA de pedidos em texto livre só quando o leitor por regras não acha o campo | assistência por IA indicada | **3** | médio | M | inexistente (o leitor por regras existe) | AUT-132, AUT-96, AUT-91; anonimização | [ficha](fichas/plataforma-e-modulos.md) | Mantém as regras como fonte e cobre só frases soltas (horário relativo, local descrito), com conferência humana. | `PLAT-LEITURA-EMAIL`, `EV-LEITURA-PEDIDO` (2) |
| **AUT-93** | Entrada de pedidos | Triagem por IA do módulo de destino só quando nenhum sinal determinístico pontuou | assistência por IA indicada | **3** | baixo | M | inexistente | AUT-133, AUT-96, AUT-91 | [ficha](fichas/plataforma-e-modulos.md) | Reduz itens "sem módulo" sem efeito automático: é só sugestão. | `ENTRADA-DEMANDAS-CANAIS`, `EV-TRIAGEM-MODULO` (2) |
| **AUT-94** | Painel · relatório | Nota executiva do mês por IA sobre o relatório consolidado | assistência por IA indicada | **3** | baixo | P | inexistente | AUT-164, AUT-96 | [ficha](fichas/plataforma-e-modulos.md) | Economiza a redação do texto de apresentação; o número citado tem de bater com o relatório. | `PAINEL-RELATORIO-CONSOLIDADO`, `RELATORIOS-PAINEIS-EXPORTACOES` (2) |
| **AUT-95** | Imprensa | Rascunho de resposta à imprensa por IA | inadequada ou inviável atualmente | **5** | médio | — | inexistente | Política institucional de uso de IA com informação policial | [ficha](fichas/plataforma-e-modulos.md) | Resposta à imprensa é manifestação institucional com informação policial sensível; sem política aprovada de dados e de provedor, não é recomendada agora (a leitura a classificou como IA de risco alto). | `IMP-ATENDIMENTO` (1) |
| **AUT-96** | IA · fundação | Porta única de IA em `gestao/integracoes/` com adaptadores simulado e gravado, validador de saída e worker | dependente de desenvolvimento | **2** | alto | M | inexistente | ADR 0019 (aceita); nome único da porta (10-1 usa `llm`, 11-2 usa `ia`) | [10-1](fluxos/10-1-assistente-dos-servidores.md) · [11-2](fluxos/11-2-textos-de-plano-de-trabalho.md) · [ficha](fichas/plataforma-e-modulos.md) | Toda assistência por IA passa por um ponto testável sem provedor, com saída validada pelo sistema antes de chegar à pessoa. | derivado dos fluxos [10-1](fluxos/10-1-assistente-dos-servidores.md) e [11-2](fluxos/11-2-textos-de-plano-de-trabalho.md) |
| **AUT-97** | Assistente · servidores | Central de ajuda com base aprovada e página "Minha situação" do servidor (prazos, pendências e documentos, sem IA) | melhor execução pelo próprio sistema | **2** | alto | M | inexistente | AUT-02, AUT-03; conteúdo escrito e aprovado | [10-1](fluxos/10-1-assistente-dos-servidores.md) · [ficha](fichas/plataforma-e-modulos.md) | Entrega a maior parte do valor do assistente sem IA nem custo, com respostas que saem dos dados e de texto aprovado. | derivado do fluxo [10-1](fluxos/10-1-assistente-dos-servidores.md) |
| **AUT-98** | IA · infraestrutura | Modelo de IA local na VPS atual | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | 2 vCPU e 7,8 GiB compartilhados (capacidade-vps.md) | [10-1](fluxos/10-1-assistente-dos-servidores.md) · [11-2](fluxos/11-2-textos-de-plano-de-trabalho.md) · [12 custos](desempenho-e-custos.md) · [ficha](fichas/plataforma-e-modulos.md) | Um modelo de 7–8 B ocupa 4–6 GB e gera poucos tokens por segundo em CPU, e modelos pequenos têm qualidade fraca em português (fontes no 11-2 e em desempenho-e-custos). | derivado dos fluxos 10-1 e 11-2 e de [capacidade-vps](../ops/mudanca-hospedagem/capacidade-vps.md) |
| **AUT-171** | eProtocolo · IA | Resumo por IA das movimentações do protocolo e sugestão de assunto e palavras-chave na abertura | assistência por IA indicada | **3** | baixo | M | inexistente | AUT-120, AUT-96; provedor e orçamento | [13](fluxos/13-integracoes-institucionais.md) · [ficha](fichas/plataforma-e-modulos.md) | Ajuda a ler processos longos e a preencher a abertura, sempre como sugestão; só faz sentido depois que a consulta funcionar. | derivado do fluxo [13](fluxos/13-integracoes-institucionais.md) |

### 5.5 Plataforma, operação e integrações institucionais — AUT-99 a AUT-131, AUT-170 (34 itens)

| ID | Módulo / processo | Oportunidade | Classificação | Mat. | Valor | Esf. | Hoje | Dependências | Onde | Justificativa | Origens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **AUT-99** | Operação · n8n | n8n isolado na VPS atual (contêiner, PostgreSQL próprio, poda de execuções, chave de criptografia guardada fora da VPS), separado por ambiente, com backup e workflows versionados | automação indicada com n8n | **1** | alto | M | planejado (não instalado) | Decisões D1 e D2 do plano; pré-requisitos da etapa 0 | [hospedagem-n8n](../ops/mudanca-hospedagem/hospedagem-n8n.md) · [plano](plano-implantacao.md) · [12 custos](desempenho-e-custos.md) · [ficha](fichas/plataforma-e-modulos.md) | A VPS medida comporta o n8n em modo normal sem serviço pago novo (capacidade-vps.md), e nenhum fluxo é ligado antes da fundação. | `OPS-DEPLOY`, `PLAT-AMBIENTES-SALVAGUARDAS`, `OPS-BACKUP-RESTAURACAO` (3) |
| **AUT-100** | Plataforma · outbox | Catálogo de eventos de domínio para integração (viagem, documento, prestação, solicitação, importação) num tópico próprio da outbox | dependente de desenvolvimento | **2** | alto | M | parcial (três tópicos; um assinante por tópico, `gestao/plataforma/outbox.py:44-45`) | Contrato de evento ([`evento-integracao.schema.json`](contratos/evento-integracao.schema.json)) | [arquitetura](arquitetura.md) · [contratos](contratos/) · [ficha](fichas/plataforma-e-modulos.md) | Dá ao n8n e às rotinas gatilhos que só existem depois do commit, sem varrer o banco. | `PLAT-OUTBOX-PUBLICACAO`, `PREST-NASCIMENTO`, `PREST-CONCLUSAO`, `EVT-ENVIO-DG`, `VIA-IMPORTACAO-FILA` (5) |
| **AUT-101** | Plataforma · outbox | Worker de entregas com lease: leva os eventos ao n8n fora de transação, com HMAC e retentativa de horas | dependente de desenvolvimento | **2** | alto | M | inexistente | AUT-100 | [arquitetura](arquitetura.md) · [ficha](fichas/plataforma-e-modulos.md) | O worker atual segura a transação durante o assinante; HTTP externo ali poderia travar escritas e a auditoria, por isso a entrega precisa de worker próprio. | `PLAT-OUTBOX-PUBLICACAO`, `PLAT-OUTBOX-WORKER` (2) |
| **AUT-102** | Plataforma · outbox | Política de retentativa por tópico e comando de reprocessamento da outbox | automação determinística suficiente | **2** | alto | P | parcial (retentativa efetiva de ~21 min até "falhou"; a ADR 0005 diz 5 s → 1 h) | Nenhuma | [arquitetura](arquitetura.md) · [ficha](fichas/plataforma-e-modulos.md) | Uma queda de horas do SMTP ou do n8n não pode virar falha definitiva nem exigir SQL manual. | `PLAT-OUTBOX-WORKER` (1) |
| **AUT-103** | Plataforma · exceções | Tela de saúde da outbox e fila de exceções da automação (dono, prazo, resolver, repetir, fazer à mão) | melhor execução pelo próprio sistema | **2** | alto | M | inexistente (só `doctor` e SQL) | AUT-102 | [arquitetura](arquitetura.md) · [ficha](fichas/plataforma-e-modulos.md) | Cumpre o "falhou, visível ao administrador" da ADR 0005 e dá um lugar único onde as exceções de todos os fluxos aparecem. | `PLAT-OUTBOX-WORKER` (1) |
| **AUT-104** | Plataforma · API de automação | API de automação v1 (`/api/automacao/v1`) com token de serviço, escopos, delegação emitida pelo PCPR na ação humana (nunca usuário representado declarado pelo chamador), `Idempotency-Key` e chave de desligamento (`/estado`) | dependente de desenvolvimento | **2** | alto | M | planejado (contrato em `contratos/api-automacao.v1.yaml`) | ADR 0020 aceita | [arquitetura](arquitetura.md) · [contratos](contratos/) · [ficha](fichas/plataforma-e-modulos.md) | Pré-requisito de qualquer fluxo seguro: autentica a máquina, avalia as mesmas policies do usuário da delegação e desliga tudo com uma chave. | `ID-AUTENTICACAO-AUTORIZACAO` (1) |
| **AUT-105** | Plataforma · ferramentas | Ferramentas de leitura (fase A da ADR 0020): pendências, busca, conflitos, situação de prestação, com política e auditoria | dependente de desenvolvimento | **2** | alto | G | planejado (ADR 0020 proposta) | AUT-104; extrair a lógica das views JSON para consultas reutilizáveis | [arquitetura](arquitetura.md) · [ficha](fichas/plataforma-e-modulos.md) | Base de todos os resumos, do assistente e da validação da proposta, sem SQL direto e sem endpoints de tela. | `API-FERRAMENTAS`, `PREST-LISTA-ABAS-EXPORT`, `PLAT-BUSCA-CONFLITOS`, `API-JSON-INTERNA` (4) |
| **AUT-106** | Plataforma · aprovação | Portão de aprovação humana e ferramentas de preparação (fases B/C): rascunhos preparados pela máquina e aprovados na tela | dependente de desenvolvimento | **2** | alto | M | planejado (`PedidoAprovacao`) | AUT-105 | [arquitetura](arquitetura.md) · [11-3](fluxos/11-3-autonomia-progressiva.md) · [ficha](fichas/plataforma-e-modulos.md) | "A máquina prepara, a pessoa aprova" mantém os atos irreversíveis humanos sem perder a automação. | `API-FERRAMENTAS`, `PT-CRIACAO-NUMERACAO` (2) |
| **AUT-107** | Plataforma · ferramentas | Fachada MCP sobre o registro de ferramentas | dependente de desenvolvimento | **2** | baixo | P | planejado | AUT-105, AUT-106 | [ficha](fichas/plataforma-e-modulos.md) | Transporte opcional para o n8n e clientes de IA usarem as mesmas ferramentas; não traz regra nova. | `API-FERRAMENTAS` (1) |
| **AUT-108** | Plataforma · salvaguardas | Salvaguardas do registro de ferramentas: contexto de auditoria obrigatório, trava por ambiente, minimização de dados e proibição de reservar número para propostas | melhor execução pelo próprio sistema | **2** | alto | M | parcial (salvaguardas por ambiente e auditoria por trigger existem; o registro de ferramentas não) | AUT-104 | [arquitetura](arquitetura.md) · [ficha](fichas/plataforma-e-modulos.md) | Garante por código que n8n e IA ajam em nome de alguém identificado, só leiam em produção até liberação explícita e não furem a numeração oficial. | `PLAT-AUDITORIA`, `PLAT-AMBIENTES-SALVAGUARDAS`, `GV-CIFRAGEM-SEGREDOS`, `VIA-NUMERACAO` (4) |
| **AUT-109** | Plataforma · rotinas | Rotinas diárias com horário por rotina, independentes do primeiro acesso e com reexecução só do que falhou | automação determinística suficiente | **2** | médio | P | parcial (timer às 05:40 e primeiro acesso do dia; rotina que falha não roda de novo no dia; o PREVIEW não tem timer) | Nenhuma | [ficha](fichas/plataforma-e-modulos.md) | Timers do próprio sistema resolvem; pôr o n8n como agendador de rotinas internas, como as leituras do EV sugeriam, faria o sistema depender dele. | `PLAT-ROTINAS-DIARIAS`, `NOTIFICACOES-ROTINAS`, `EV-SOLICITACAO-DESPACHO`, `EV-ROTINAS-DIARIAS` (4) |
| **AUT-110** | Operação · saúde | Saúde estendida: outbox, importador, rotinas e documentos em falha nas checagens e no `/saude/` | automação determinística suficiente | **2** | alto | M | parcial (`deploy/vps/monitorar.sh` não cobre importador nem rotinas) | Nenhuma | [ficha](fichas/plataforma-e-modulos.md) | Detectar fila parada em minutos é a lição da fila "drive" do GV, parada desde 26/08/2026 sem ninguém saber. | `OPS-MONITOR-SAUDE`, `VIA-IMPORTACAO-FILA`, `VIA-DOCUMENTO-PDF` (3) |
| **AUT-111** | Operação · alertas | Roteamento e escalonamento de alertas operacionais pelo n8n (saúde, filas, auditoria, backup e restauração), inclusive das referências em produção | automação indicada com n8n | **1** | alto | P | parcial (o monitor já envia alerta a um webhook configurável, que pode apontar para o n8n) | AUT-99; AUT-110 para cobrir mais | [ficha](fichas/plataforma-e-modulos.md) | Rotear, agrupar e escalar alertas é borda de monitoramento em que o n8n agrega usando o que já existe. | `PLAT-AUDITORIA`, `OPS-MONITOR-SAUDE`, `OPS-BACKUP-RESTAURACAO`, `GV-DRIVE-ESPELHO`, `GV-OBS-BACKUP-AUDITORIA` (5) |
| **AUT-112** | Plataforma · arquivos | Pipeline único de entrada de arquivos com antivírus (tela, importação, portal e n8n) | melhor execução pelo próprio sistema | **3** | alto | M | só na referência (o GV usa ClamAV; o sistema novo não tem antivírus de upload) | Contêiner `clamd` (≈1 GiB de RAM, estimativa a medir) | [10-6](fluxos/10-6-recebimento-de-documentos.md) · [ficha](fichas/plataforma-e-modulos.md) | Arquivos que chegam por e-mail ou por portal sem login precisam da mesma proteção antes de entrar na importação. | `GV-DOC-ASSINADO-MANUAL`, `GV-UPLOAD-AV` (2) |
| **AUT-113** | Identidade · e-mail | Convite e recuperação de senha por e-mail | dependente de integração externa | **3** | médio | P | inexistente | AUT-04 | [ficha](fichas/plataforma-e-modulos.md) | Tira o administrador do ciclo de senhas assim que houver SMTP. | `CAD-USUARIOS-PAPEIS` (1) |
| **AUT-114** | Identidade · acessos | Revisão periódica de acessos (contas ociosas e papéis sensíveis) | automação determinística suficiente | **2** | médio | P | inexistente | Nenhuma | [ficha](fichas/plataforma-e-modulos.md) | Consulta determinística com aviso ao administrador; o n8n só entraria para entregar fora. | `CAD-USUARIOS-PAPEIS` (1) |
| **AUT-115** | Identidade · SSO | SSO pela Central de Segurança do PR | dependente de integração externa | **4** | médio | G | inexistente | Credenciamento institucional | [ficha](fichas/plataforma-e-modulos.md) | Elimina senhas locais e liga a identidade estadual, mas depende de credenciamento institucional. | `ID-AUTENTICACAO-AUTORIZACAO` (1) |
| **AUT-116** | Referência GV · operação | Fila "drive" parada no GV em produção: purgar e reconciliar pelo banco ou reprocessar (decisão D3 do plano) | melhor execução pelo próprio sistema | **1** | médio | M | parcial (cerca de 7.100 tarefas paradas desde 26/08/2026) | Decisão D3; acesso de manutenção | [plano](plano-implantacao.md) · [ficha](fichas/plataforma-e-modulos.md) | É correção operacional na referência em produção, não automação; purgar e reconciliar evita uma avalanche de reprocessamento disputando CPU com os usuários. | `GV-DRIVE-ESPELHO` (1) |
| **AUT-117** | Integrações · Google Drive | Espelho Google Drive no sistema novo como assinante da outbox com estado por item | dependente de integração externa | **4** | baixo | G | só na referência (parcial no GV) | Decisão institucional sobre a conta Drive e o compartilhamento | [ficha](fichas/plataforma-e-modulos.md) | Só vale se a instituição mantiver o Drive como destino; o estado durável no banco evita repetir a fila parada do GV. | `GV-DRIVE-ESPELHO` (1) |
| **AUT-118** | Autonomia | Autorização por fluxo (sombra → assistido → automático), painel "o que a automação fez" e desfazer | dependente de desenvolvimento | **2** | alto | M | inexistente | AUT-106; decisões do 11-3 | [11-3](fluxos/11-3-autonomia-progressiva.md) · [ficha](fichas/plataforma-e-modulos.md) | Permite subir a autonomia de cada fluxo com métricas e voltar atrás, em vez de ligar tudo de uma vez. | derivado do fluxo [11-3](fluxos/11-3-autonomia-progressiva.md) |
| **AUT-119** | eProtocolo · abertura | Abrir protocolo no eProtocolo pela API (ofício, pagamento do coffee) atrás do portão de aprovação | dependente de integração externa | **4** | alto | G | parcial (no sistema novo o adaptador HTTP recusa abrir e o simulado devolve número marcado SIMULADO; o GV tem cliente da API; nenhum teste em treinamento tem evidência) | Credenciais e escopos (Celepar), ambiente de treinamento, trava de mutação aberta explicitamente (ADR 0019), AUT-106 | [13](fluxos/13-integracoes-institucionais.md) · [ficha](fichas/plataforma-e-modulos.md) | Elimina a digitação dupla do protocolo, mas é ato institucional: só com credencial, portão humano e chave idempotente. | `VIA-OFICIO-PROTOCOLO`, `INT-EPROTOCOLO`, `GV-EPROTOCOLO`, `EV-EPROTOCOLO`, `CB-PROTOCOLO-PAGAMENTO` (5) |
| **AUT-120** | eProtocolo · consulta | Consulta periódica do andamento dos protocolos e aviso de mudança ou de chegada ao setor | dependente de integração externa | **3** | alto | M | parcial (porta de consulta existe; sem credencial real) | Credencial de consulta em treinamento (`consumerId`, escopo, IP de saída autorizado); vínculo documento↔protocolo; AUT-170; n8n como agendador opcional | [13](fluxos/13-integracoes-institucionais.md) · [ficha](fichas/plataforma-e-modulos.md) | Mostra no sistema quando o processo andou ou voltou, sem consulta manual no portal; a chamada passa pela porta do PCPR, não pelo n8n. | `VIA-OFICIO-PROTOCOLO`, `INT-EPROTOCOLO`, `GV-EPROTOCOLO`, `EV-EPROTOCOLO`, `PAL-PEDIDO-REGISTRO` (5) |
| **AUT-121** | eProtocolo · andamento | Interpretar o andamento do protocolo como sugestão de marco (prestação aprovada ou devolvida; atesto e OB do coffee) | dependente de integração externa | **4** | médio | M | inexistente | AUT-120; significado das movimentações (não público) | [13](fluxos/13-integracoes-institucionais.md) · [ficha](fichas/plataforma-e-modulos.md) | Útil só depois que a consulta funcionar e a semântica das movimentações for conhecida, e sempre como sugestão. | `PREST-ENVIO-FINANCEIRO`, `CB-FINANCEIRO-MARCOS` (2) |
| **AUT-122** | eProtocolo · juntada | Juntar documentos e o pacote da prestação ao processo e solicitar assinatura no eProtocolo, com aprovação | dependente de integração externa | **4** | alto | G | inexistente | Escopo de inclusão de documentos; fluxo institucional; AUT-106 | [13](fluxos/13-integracoes-institucionais.md) · [ficha](fichas/plataforma-e-modulos.md) | Elimina download e upload do pacote e mantém a tramitação no sistema oficial, como o Decreto estadual 7.304/2021 exige. | `PREST-PACOTE`, `GV-PREST-CONSOLIDADO`, `EV-ENVIO-FINANCEIRO`, `PT-ASSINATURA-CIRCULACAO` (4) |
| **AUT-123** | eProtocolo · importação | Trazer do eProtocolo o ofício assinado, o despacho e o processo para a importação documental | dependente de integração externa | **4** | médio | M | inexistente (o operador baixa e importa) | Credencial de leitura; vínculo protocolo↔documento; AUT-112 | [13](fluxos/13-integracoes-institucionais.md) · [ficha](fichas/plataforma-e-modulos.md) | Elimina baixar e reenviar o que já está no eProtocolo, reaproveitando a leitura e o direcionamento existentes. | `GV-PREST-DOCUMENTOS-CARIMBO`, `EV-IMPORTACAO-PROCESSO` (2) |
| **AUT-124** | Central de Viagens | Painel "dados para a Central de Viagens" com botão copiar | automação determinística suficiente | **2** | médio | P | inexistente | Lista de campos exigidos pela Central | [13](fluxos/13-integracoes-institucionais.md) · [ficha](fichas/plataforma-e-modulos.md) | Reduz a redigitação já, sem depender de uma API que não se sabe se existe. | `INT-CENTRAL-VIAGENS` (1) |
| **AUT-125** | Central de Viagens | Integração oficial com a Central de Viagens / sistema de diárias: registrar a solicitação e importar nº, liberação e prazo de saque | dependente de integração externa | **4** | alto | G | inexistente | API no gateway estadual (não encontrada publicamente; passa a 5 se a instituição confirmar que não há API); credenciamento; saber qual sistema emite o nº | [13](fluxos/13-integracoes-institucionais.md) · [ficha](fichas/plataforma-e-modulos.md) | Eliminaria a digitação e o erro de transcrição dos dados que disparam o aviso de liberação, mas depende inteiramente da instituição. | `INT-CENTRAL-VIAGENS`, `PREST-SOLICITACAO-LIBERACAO` (2) |
| **AUT-126** | Plataforma · acesso do n8n | n8n consumindo endpoints de tela (cookie/sessão), o feed ICS pessoal ou o banco diretamente | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [arquitetura](arquitetura.md) · [ficha](fichas/plataforma-e-modulos.md) | Contorna policies e auditoria e quebra a cada mudança de tela; a ADR 0020 manda usar só ferramentas com token. | `API-JSON-INTERNA`, `PAINEL-ICS` (2) |
| **AUT-127** | Operação | IA ou n8n decidindo retentativas, avaliando a integridade da auditoria, diagnosticando incidentes ou operando deploy e infraestrutura | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [ficha](fichas/plataforma-e-modulos.md) | São regras determinísticas (retentativa, hash da cadeia) ou operações privilegiadas; automação ali amplia o risco sem ganho. | `PLAT-OUTBOX-WORKER`, `PLAT-AUDITORIA`, `OPS-MONITOR-SAUDE`, `OPS-DEPLOY` (4) |
| **AUT-128** | eProtocolo e Central | Robô de navegador no portal do eProtocolo ou da Central de Viagens | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [13](fluxos/13-integracoes-institucionais.md) · [ficha](fichas/plataforma-e-modulos.md) | Frágil, contorna a autenticação e o controle institucional e pode violar termos de uso; só integração oficial. | `INT-EPROTOCOLO`, `INT-CENTRAL-VIAGENS` (2) |
| **AUT-129** | eProtocolo | IA decidindo abertura ou tramitação de protocolo | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [13](fluxos/13-integracoes-institucionais.md) · [ficha](fichas/plataforma-e-modulos.md) | Ato institucional com responsabilidade funcional; a automação prepara e uma pessoa decide. | `GV-EPROTOCOLO` (1) |
| **AUT-130** | Integrações · Google Drive | Levar para o n8n a organização de pastas e nomes do espelho Drive | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [ficha](fichas/plataforma-e-modulos.md) | É regra documental; no n8n ficaria duplicada e sem estado durável. | `GV-DRIVE-ESPELHO` (1) |
| **AUT-131** | Migração | Carga contínua GV → sistema novo por n8n ou IA | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [ficha](fichas/plataforma-e-modulos.md) | A migração é carga controlada com o legado só em leitura; sincronização contínua criaria duas fontes de verdade. | `EV-MIGRACAO-GV` (1) |
| **AUT-170** | eProtocolo · salvaguardas | Salvaguardas do eProtocolo por ambiente: adaptador desligado em produção sem credencial, trava de mutação para todas as operações e pendência "protocolo não oficial" quando o número vier do simulado ou do treinamento | melhor execução pelo próprio sistema | **2** | alto | P | parcial (trava de mutação existe; sem credencial o serviço cai no adaptador simulado, que devolve número fictício marcado SIMULADO) | Nenhuma | [13](fluxos/13-integracoes-institucionais.md) · [ficha](fichas/plataforma-e-modulos.md) | Impede que um número fictício ou de treinamento seja tratado como protocolo oficial antes de qualquer integração real; é regra do próprio sistema e não espera credencial. | derivado do fluxo [13](fluxos/13-integracoes-institucionais.md) |

### 5.6 Outros módulos (Eventos, Palestras, Imprensa, Publicações, Coffee, Cadastros, Painel) — AUT-132 a AUT-169 (38 itens)

| ID | Módulo / processo | Oportunidade | Classificação | Mat. | Valor | Esf. | Hoje | Dependências | Onde | Justificativa | Origens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **AUT-132** | Entrada de demandas (transversal) | Caixa de entrada única de demandas: cada e-mail ou pedido vira item com o original preservado e conversão assistida em rascunho no módulo certo (solicitação, palestra, imprensa, pauta, coffee, anexo da viagem) | melhor execução pelo próprio sistema | **2** | alto | G | parcial (leitura de e-mail colado existe em imprensa, publicações e coffee) | AUT-104; decisão de canais; retenção (LGPD); duplicidade pela digital do texto | [ficha](fichas/plataforma-e-modulos.md) | Nada se perde e ninguém redigita, e a conversão em registro continua sendo do sistema e da pessoa, nunca do n8n. | `ENTRADA-DEMANDAS-CANAIS`, `EVT-SOLICITACAO-CADASTRO` (2) |
| **AUT-133** | Entrada de demandas | Triagem determinística do módulo provável na caixa de entrada, com sinais visíveis e confirmação humana | automação determinística suficiente | **2** | médio | M | só na referência (o EV tem triagem com memória por remetente) | AUT-132 | [ficha](fichas/plataforma-e-modulos.md) | Regras e memória por remetente resolvem a maioria dos casos de forma explicável. | `EV-TRIAGEM-MODULO` (1) |
| **AUT-134** | Eventos ↔ Viagens ↔ Coffee ↔ Palestras | Sincronização entre módulos: alteração ou cancelamento da solicitação refletidos na viagem, no coffee e na palestra, e decisão da DG refletida na palestra | melhor execução pelo próprio sistema | **2** | alto | M | parcial (ganchos de origem existem; sem situação nem cancelamento propagados) | AUT-100 (eventos da solicitação); registro de origens (o coffee não pode importar eventos) | [ficha](fichas/plataforma-e-modulos.md) | Evita viagem e coffee montados sobre dados antigos e entrega de coffee de evento cancelado; é regra interna, sem n8n. | `EVT-ENVIO-DG`, `EVT-ENCERRAMENTO`, `PAL-ENCAMINHAR-DG`, `CB-PEDIDO-OS` (5) |
| **AUT-135** | Eventos · catálogos | Vincular unidade móvel à viatura e a "equipe" do evento aos servidores | dependente de desenvolvimento | **2** | alto | M | inexistente | Decisão sobre o significado de "equipe" (Alfa/Bravo/Charlie) | [11-3](fluxos/11-3-autonomia-progressiva.md) · [ficha](fichas/plataforma-e-modulos.md) | Habilita sugerir viatura e participantes na proposta consolidada e cruzar conflitos reais com ofícios. | `EVT-CATALOGOS-MODELO` (1) |
| **AUT-136** | Eventos · DG | Aviso à DG de nova solicitação (agrupado) e resumo diário da fila de despacho por e-mail | automação indicada com n8n | **3** | médio | P | parcial (lembretes no sino) | AUT-100, AUT-105, AUT-06 | [ficha](fichas/plataforma-e-modulos.md) | Leva o pedido a quem decide sem abrir o sistema e reduz o tempo até o despacho; quem recebe vem da permissão. | `EVT-ENVIO-DG`, `EVT-DESPACHO-DG` (2) |
| **AUT-137** | Eventos · despacho | Resumo de despacho determinístico na folha da DG (conflitos, antecedência, ocupação de unidades móveis) | automação determinística suficiente | **2** | médio | P | inexistente | Nenhuma | [ficha](fichas/plataforma-e-modulos.md) | Decisão mais bem informada sem abrir outras telas, com dados que o sistema já tem. | `EVT-DESPACHO-DG` (1) |
| **AUT-138** | Eventos · solicitação | Contato do solicitante estruturado (e-mail, telefone) na solicitação | melhor execução pelo próprio sistema | **2** | médio | P | inexistente (texto livre) | Migração; ajuste da exportação | [ficha](fichas/plataforma-e-modulos.md) | Pré-requisito para qualquer comunicação automática com o solicitante e para exportação limpa. | `EVT-SOLICITACAO-CADASTRO` (1) |
| **AUT-139** | Eventos · solicitação | Sugestão de serviços e equipes pelo histórico do solicitante ou do tipo de evento | automação determinística suficiente | **2** | baixo | P | inexistente | Nenhuma | [ficha](fichas/plataforma-e-modulos.md) | Acelera o preenchimento sem IA, complementando o modelo do tipo. | `EVT-SOLICITACAO-CADASTRO` (1) |
| **AUT-140** | Eventos · lembretes | Ajustes nos lembretes de solicitações: destinatários da DG pela permissão e lembrete de rascunho esquecido | automação determinística suficiente | **2** | baixo | P | parcial | Nenhuma | [ficha](fichas/plataforma-e-modulos.md) | Coerência de destinatários e pedidos que não ficam esquecidos, com regras simples. | `EVT-LEMBRETES` (2) |
| **AUT-141** | Eventos · pós-evento | Confirmação pós-evento pelo responsável por link enviado por e-mail | automação indicada com n8n | **3** | baixo | M | parcial (lembrete interno existe) | AUT-03, AUT-06 | [ficha](fichas/plataforma-e-modulos.md) | Colhe números reais no dia, mas o lembrete interno já existe; ganho pequeno. | `EVT-ENCERRAMENTO` (1) |
| **AUT-142** | Eventos · situação | Sugerir mudança de situação do evento ou da solicitação pelas datas | automação determinística suficiente | **2** | baixo | P | inexistente | Confirmação institucional da regra | [ficha](fichas/plataforma-e-modulos.md) | Mantém o painel coerente, só como sugestão para não inventar regra. | `GV-EVENTO` (1) |
| **AUT-143** | Palestras · pedido | Formulário público de pedido de palestra com acompanhamento por link (e confirmação por e-mail quando houver SMTP) | melhor execução pelo próprio sistema | **2** | médio | M | só na referência (o EV tem pedido público com token) | Decisão institucional sobre rota sem login; antispam; dados de menores (escolas); AUT-04 para o e-mail | [ficha](fichas/plataforma-e-modulos.md) | A ASCOM recebe dados estruturados e o solicitante acompanha sem ligar; a confirmação por e-mail é transporte. | `PAL-PEDIDO-REGISTRO`, `EV-PEDIDO-PUBLICO` (2) |
| **AUT-144** | Palestras · resposta | Resposta padrão ao solicitante de palestra enviada pelo sistema por e-mail, com status de entrega | automação indicada com n8n | **3** | médio | P | parcial (`mailto` abre o cliente de e-mail; registro declarativo) | AUT-01, AUT-06, AUT-138 | [ficha](fichas/plataforma-e-modulos.md) | O envio e a prova de envio ficam no mesmo clique; o texto continua sendo o modelo aprovado. | `PAL-ANDAMENTO-RESPOSTA`, `EV-RESPOSTA-PADRAO` (2) |
| **AUT-145** | Palestras · lembretes | Lembretes da palestra (palestrante em D-2; ASCOM para cobrar retorno e registrar público) | automação indicada com n8n | **3** | médio | P | inexistente | Antecedência a definir; e-mail do palestrante; AUT-06 | [ficha](fichas/plataforma-e-modulos.md) | O palestrante é externo, então o canal é a parte essencial; a regra de quando lembrar fica no sistema. | `PAL-ANDAMENTO-RESPOSTA` (1) |
| **AUT-146** | ASCOM · cadastros | Vincular integrantes da ASCOM a usuários | dependente de desenvolvimento | **2** | médio | P | inexistente | Decisão do usuário; integrantes externos sem conta | [ficha](fichas/plataforma-e-modulos.md) | Sem vínculo não há como notificar o responsável certo por prazo ou pauta parada. | `ASCOM-CADASTROS-APOIO` (1) |
| **AUT-147** | Imprensa | Alerta de prazo (deadline) do atendimento à imprensa | automação determinística suficiente | **2** | médio | P | inexistente | AUT-146 | [ficha](fichas/plataforma-e-modulos.md) | O prazo da redação é dado do registro; o sino alcança o responsável. | `IMP-ATENDIMENTO` (1) |
| **AUT-148** | Publicações | Detecção da matéria publicada por feed público, preenchendo link e data | automação indicada com n8n | **3** | baixo | P | inexistente | Feed público estável a confirmar | [ficha](fichas/plataforma-e-modulos.md) | Consultar feed externo de forma agendada é borda típica do n8n, mas o ganho é pequeno e há risco de falso positivo. | `PUB-PAUTA` (1) |
| **AUT-149** | ASCOM · cadastros | Sugestão de correspondência entre unidade responsável (ASCOM) e unidade policial | automação determinística suficiente | **2** | baixo | P | inexistente | Nenhuma | [ficha](fichas/plataforma-e-modulos.md) | Relatórios cruzados por unidade com conferência humana dos pares. | `ASCOM-CADASTROS-APOIO` (1) |
| **AUT-150** | Coffee · financeiro | Resumo diário "O que fazer hoje" da equipe do coffee | automação indicada com n8n | **3** | médio | P | parcial (painel existe) | AUT-105, AUT-06 | [ficha](fichas/plataforma-e-modulos.md) | Pendências financeiras já calculadas no painel chegam à equipe sem abrir o sistema. | `CB-FINANCEIRO-MARCOS` (1) |
| **AUT-151** | Coffee · documentos | Coffee na importação documental e na conferência de vias (NF, OB, certidões, processo de pagamento, vias assinadas) | melhor execução pelo próprio sistema | **2** | médio | M | parcial (leitura de NF, OB e contrato existe no coffee) | Refatorar a fila para não acoplar coffee a viagens (import-linter); conferência reutilizável | [ficha](fichas/plataforma-e-modulos.md) | Reaproveita a fila com OCR e a conferência de assinatura em vez de manter uma segunda leitura. | `CB-DOCUMENTOS-VIAS`, `CB-LEITURA-PDFS` (3) |
| **AUT-152** | Coffee · pagamento | Separar "baixar pacote" de "registrar atesto" no protocolo de pagamento | automação determinística suficiente | **2** | médio | P | existe (acoplado) | Decisão do usuário (comportamento herdado da referência) | [ficha](fichas/plataforma-e-modulos.md) | Leituras e automações deixam de alterar marcos financeiros por acidente. | `CB-PROTOCOLO-PAGAMENTO` (1) |
| **AUT-153** | Coffee · certidões | Aviso de vencimento de certidão e pedido de renovação ao fornecedor | automação indicada com n8n | **3** | médio | P | parcial (vencimento visível no painel) | AUT-04, AUT-06; texto padrão aprovado | [ficha](fichas/plataforma-e-modulos.md) | O vencimento é regra do sistema; o pedido ao fornecedor externo é canal, e evita protocolo de pagamento travado. | `CB-CERTIDOES` (1) |
| **AUT-154** | Coffee · fornecedor | Comunicação formal com o fornecedor (OS, OB e notificação de ocorrência) com prévia editável, aprovação e registro | melhor execução pelo próprio sistema | **3** | médio | M | inexistente | AUT-04; envio com anexos (o tópico atual de e-mail não leva anexos); AUT-06 como transporte | [ficha](fichas/plataforma-e-modulos.md) | Compor, aprovar e registrar é do sistema; o n8n pode transportar com retentativa, mas comunicação contratual exige aprovação. | `CB-COMUNICACAO-FORNECEDOR`, `CB-ENTREGAS` (2) |
| **AUT-155** | Coffee · fornecedor | Link seguro do fornecedor para enviar NF e certidões | melhor execução pelo próprio sistema | **2** | médio | M | só na referência (o EV tem link seguro) | Decisão institucional (rota sem login); AUT-03; AUT-112 | [ficha](fichas/plataforma-e-modulos.md) | Fornecedor entrega direto com conferência, sem e-mail intermediário. | `CB-COMUNICACAO-FORNECEDOR` (1) |
| **AUT-156** | Coffee · entregas | Confirmação de recebimento da entrega pelo responsável no local, por link | automação indicada com n8n | **3** | baixo | M | inexistente | Contato estruturado na OS; AUT-03; AUT-06; WhatsApp e SMS indisponíveis (AUT-10) | [ficha](fichas/plataforma-e-modulos.md) | Avaliação colhida no dia, mas o registro manual atual já funciona; ganho pequeno. | `CB-ENTREGAS` (1) |
| **AUT-157** | Coffee · contrato | Alerta semanal de saldo e vigência do contrato com o relatório anexo | automação indicada com n8n | **3** | médio | P | parcial (alertas no painel) | AUT-105, AUT-06 | [ficha](fichas/plataforma-e-modulos.md) | Fiscal e gestor providenciam aditivo a tempo; agenda e anexo são borda do n8n. | `CB-PAINEL-CONTRATO-VIRADA` (1) |
| **AUT-158** | Coffee · exercício | Lembrete de virada de exercício (lotes do ano novo) | automação determinística suficiente | **2** | baixo | P | inexistente | Nenhuma | [ficha](fichas/plataforma-e-modulos.md) | Evento anual previsível; o aviso no sino basta. | `CB-PAINEL-CONTRATO-VIRADA` (1) |
| **AUT-159** | Cadastros · fonte dedicada | Sincronização agendada da fonte dedicada de cadastros (servidores, cargos, unidades) preservando complementos locais | dependente de integração externa | **4** | médio | M | parcial (espelho com reconciliação em três estados) | Fonte oficial e contrato a identificar; LGPD (CPF/RG); AUT-104 | [ficha](fichas/plataforma-e-modulos.md) | Elimina digitação de cadastros, mas a fonte oficial ainda não foi identificada; o n8n pode só agendar a chamada à ferramenta. | `CAD-FONTE-EXTERNA`, `CAD-FONTE-DEDICADA` (2) |
| **AUT-160** | Cadastros · fonte dedicada | Reconhecimento assistido dos vínculos iniciais com a fonte de cadastros | automação determinística suficiente | **2** | médio | P | inexistente | AUT-159 (extração da origem) | [ficha](fichas/plataforma-e-modulos.md) | Liga os registros existentes à origem com conferência de homônimos, sem IA. | `CAD-FONTE-DEDICADA` (1) |
| **AUT-161** | Cadastros · unidade | Alertas de configuração da unidade: assinante de planos ausente, substituição de assinante começando ou terminando, sede ausente | automação determinística suficiente | **2** | médio | P | inexistente | Nenhuma | [ficha](fichas/plataforma-e-modulos.md) | Documentos saem com o assinante certo; é consulta interna com aviso no sino, sem n8n. | `PT-ASSINATURA-CIRCULACAO`, `CAD-DADOS-UNIDADE-ASSINANTES`, `CAD-UNIDADE-ASSINANTES-DIARIAS-TEXTOS` (3) |
| **AUT-162** | Painel · agenda | Pauta semanal e escala do dia seguinte enviadas automaticamente | automação indicada com n8n | **3** | médio | P | parcial (pauta em PDF baixada e enviada à mão) | AUT-04, AUT-105; lista de destinatários definida pela ASCOM | [ficha](fichas/plataforma-e-modulos.md) | A geração continua determinística no sistema (a leitura do EV recomenda mantê-la assim); o n8n só agenda e entrega. | `PLAT-NOTIF-EMAIL`, `PAINEL-AGENDA`, `AGENDA-ESCALA-PAUTA-ICS`, `EV-AGENDA-ICS-PAUTA` (4) |
| **AUT-163** | Painel · agenda | Feed iCalendar de equipe ou de unidade | melhor execução pelo próprio sistema | **2** | baixo | P | parcial (feed pessoal existe) | Decisão de quem pode ver o quê fora do sistema | [ficha](fichas/plataforma-e-modulos.md) | A chefia acompanha o calendário no próprio cliente de agenda; é extensão do feed pessoal que já existe. | `PAINEL-ICS` (1) |
| **AUT-164** | Painel · relatório | Envio mensal automático do relatório consolidado e da planilha | automação indicada com n8n | **3** | médio | P | parcial (relatório e XLSX gerados sob demanda) | AUT-109, AUT-06; relatório gerado pelo PCPR com o escopo de cada destinatário (sem delegação: não há ação humana no disparo) | [ficha](fichas/plataforma-e-modulos.md) | Agenda mensal e entrega são borda; o relatório já é gerado pelo sistema. | `PAINEL-RELATORIO-CONSOLIDADO`, `RELATORIOS-PAINEIS-EXPORTACOES` (2) |
| **AUT-165** | Eventos · despacho | Despacho da DG por automação, IA ou resposta de e-mail ou mensagem | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [ficha](fichas/plataforma-e-modulos.md) | Decisão institucional exige autenticação forte, observação e trilha; resposta de mensagem não oferece isso. | `EVT-DESPACHO-DG`, `EV-SOLICITACAO-DESPACHO` (2) |
| **AUT-166** | Coffee · certidões | Emitir certidões automaticamente nos portais dos órgãos | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [ficha](fichas/plataforma-e-modulos.md) | Violaria termos de uso e pode ser bloqueado; o fornecedor envia a certidão (AUT-153). | `CB-CERTIDOES` (1) |
| **AUT-167** | Coffee · financeiro | Registrar marcos financeiros do coffee por IA | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [ficha](fichas/plataforma-e-modulos.md) | Erro financeiro e de auditoria sem ganho; os marcos vêm de documentos e de ação humana. | `CB-FINANCEIRO-MARCOS` (1) |
| **AUT-168** | Cadastros · identidade | Casar identidades de pessoas por IA | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [ficha](fichas/plataforma-e-modulos.md) | Fusão errada de pessoas é grave e difícil de desfazer; o reconhecimento assistido determinístico (AUT-160) basta. | `CAD-FONTE-DEDICADA` (1) |
| **AUT-169** | Cadastros · diárias | Atualizar a tabela de diárias automaticamente a partir da norma | inadequada ou inviável atualmente | **5** | baixo | — | inexistente | — | [ficha](fichas/plataforma-e-modulos.md) | Evento raro, com valor financeiro e legal; a tabela é cadastrada e conferida por uma pessoa. | `CAD-UNIDADE-ASSINANTES-DIARIAS-TEXTOS` (1) |

## 6. WhatsApp: o que dependia dele e o canal adotado

As propostas abaixo citavam o WhatsApp como canal ou como uma das opções. A parte WhatsApp de cada uma é
AUT-10 (maturidade 5). O objetivo continua viável pelo canal da quarta coluna, com a maturidade da última.
A tabela equivalente, com a fonte de cada maturidade, está em
[whatsapp-viabilidade.md](whatsapp-viabilidade.md), seção 2.1.

**Estado atual (17/10/2026).** A plataforma oficial continua **bloqueada** pela política (AUT-10,
maturidade 5), mas o WhatsApp é **prioridade do usuário**, em três frentes do [plano](plano-implantacao.md)
que começam já: **WA-1**, envio assistido com registro (AUT-172, maturidade 2) — o link `wa.me` aberto pelo
operador no aparelho institucional passa a ter texto mínimo e registro "enviado por WhatsApp manual", e
vale para todas as comunicações da tabela que chegam a um servidor; **WA-2**, consulta formal à Meta
(AUT-173, 4); **WA-3**, integração oficial pronta e desligada (AUT-174, 5 para ativar). Por isso a coluna
"Canal adotado" vale até o portão de ativação da WA-3; os fluxos são independentes de canal, e ligar o
WhatsApp depois não muda estados nem regras.

| ID | Oportunidade | Processos cuja proposta citava WhatsApp | Canal adotado na matriz | Mat. sem WhatsApp |
|---|---|---|---|---|
| AUT-01 | Registro de cada comunicação no PCPR (`Comunicacao`): estado, versão, destinatário, texto enviado, histórico de entrega e ações manuais (enviar agora, copiar, marcar "enviado por outro meio") | `GV-NOTIFICACOES` | o registro vale para qualquer canal; o `wa.me` manual entra como "enviado por outro meio" | 2 |
| AUT-02 | Contato verificado, consentimento e identidade do servidor viajante (`ContatoVerificado` e vínculo usuário↔servidor) | `ID-AUTENTICACAO-AUTORIZACAO`, `CAD-SERVIDORES-VIATURAS-CATALOGOS` | contato verificado por e-mail; telefone só como dado cadastral | 2 |
| AUT-06 | Entrega externa das comunicações e avisos pelo n8n (e-mail institucional): reserva, envio, resultado, devoluções e retentativa | `PLAT-NOTIF-SINO`, `NOTIFICACOES-ROTINAS`, `EVT-LEMBRETES` | e-mail institucional (SMTP) com status e devoluções; sino como fonte | 3 |
| AUT-08 | Leitura das caixas postais institucionais pelo n8n (IMAP/OAuth) com deduplicação por Message-ID, entregando ao PCPR documentos devolvidos e pedidos recebidos | `VIA-VIAS-ASSINADAS`, `VIA-IMPORTACAO-FILA`, `PAL-PEDIDO-REGISTRO`, `GV-EVENTO` | caixa postal institucional lida pelo n8n; portal do servidor para devolução | 4 |
| AUT-22 | Envio dos documentos emitidos (ofício, justificativa, termos, OS, plano) a cada servidor e destinatário: só o que é dele, na versão corrente, pelo portal e, com SMTP, por e-mail, com registro por pessoa | `VIA-TERMOS`, `GV-TERMOS` | portal + sino; e-mail com SMTP | 2 |
| AUT-23 | Aviso de retificação, cancelamento ou reagendamento a quem já recebeu documentos da viagem | `VIA-VIAGEM-CICLO` | portal + sino; e-mail com SMTP | 3 |
| AUT-24 | Avisos aos operadores nos marcos da viagem: viagem gerada, plano gerado, PDF ou pacote pronto ou com falha definitiva | `VIA-VIAGEM-DE-SOLICITACAO` | sino; espelho por e-mail (AUT-06) | 2 |
| AUT-25 | Data-limite para emitir sem justificativa e aviso de "pronto para emitir" | `VIA-OFICIO-PRAZO-JUSTIFICATIVA` | sino; e-mail opcional por AUT-06 | 2 |
| AUT-31 | Resumo diário por unidade das viagens próximas (D-7 a D0): ofícios em rascunho, justificativa pendente, planos não gerados ou vazios, termos sem via assinada, eventos deferidos sem proposta | `VIA-CONFERENCIA`, `GV-OFICIO-WIZARD` | e-mail institucional | 3 |
| AUT-36 | Aviso de liberação de diárias ("mensagem de saque"): texto e situação como função de domínio testada, com registro de quem foi avisado | `PREST-MENSAGEM-SAQUE` | o mesmo texto serve ao `wa.me` manual, ao e-mail e ao portal | 2 |
| AUT-37 | Envio automático do aviso de liberação pelo canal institucional no dia em que a liberação é registrada | `PREST-MENSAGEM-SAQUE`, `PLAT-ROTINAS-DIARIAS`, `GV-PREST-AVISO-DIARIAS`, `EV-MENSAGEM-LIBERACAO`, `PREST-SOLICITACAO-LIBERACAO` | e-mail institucional + situação no portal; `wa.me` manual registrado como "enviado por outro meio" | 3 |
| AUT-38 | Lembretes ao servidor: saque vencendo, prestação vencida e o que entregar após o retorno, até o comprovante entrar | `PREST-AVISOS-PRAZOS`, `EV-AVISOS-PRESTACAO` | e-mail institucional; para quando o comprovante entra | 3 |
| AUT-41 | Envio do link de km na véspera (America/Sao_Paulo) e lembretes pelo canal institucional | `PREST-DIARIO-LINK-CAMPO`, `VIA-VESPERA-SAIDA`, `GV-PREST-DIARIO`, `EV-DIARIO-LINK-KM`, `PLAT-ROTINAS-DIARIAS` | e-mail institucional ao motorista com contato verificado; entrega manual do link pela tela | 3 |
| AUT-47 | Disponibilizar DB e RT ao signatário pelo portal e avisar por e-mail, com lembrete antes do prazo | `PREST-DOCS-ENVIO-ASSINATURA`, `GV-PREST-ASSINATURA` | portal (`LinkAcesso`) + aviso por e-mail | 3 |
| AUT-52 | Recebimento de documentos devolvidos pelo servidor: portal por link e ingestão autenticada na importação documental, com rastro de remetente e resposta padronizada | `DOC-IMPORTACAO-ENTRADA` | portal do servidor e caixa postal institucional (AUT-08) | 2 |
| AUT-88 | Assistente de dúvidas dos servidores (só leitura): situação da própria viagem, diárias, prazos, documentos e procedimentos | `API-FERRAMENTAS`, `GV-ASSISTENTE-DUVIDAS`, `EV-IA-ASSISTENTE` | assistente dentro do portal do servidor (10-1); e-mail como canal só no nível 4 | 3 |
| AUT-111 | Roteamento e escalonamento de alertas operacionais pelo n8n (saúde, filas, auditoria, backup e restauração), inclusive das referências em produção | `PLAT-AUDITORIA` | webhook já existente do monitor (ntfy/e-mail) via n8n | 1 |
| AUT-112 | Pipeline único de entrada de arquivos com antivírus (tela, importação, portal e n8n) | `GV-UPLOAD-AV` | o antivírus vale para portal e e-mail | 3 |
| AUT-136 | Aviso à DG de nova solicitação (agrupado) e resumo diário da fila de despacho por e-mail | `EVT-ENVIO-DG` | e-mail institucional | 3 |
| AUT-144 | Resposta padrão ao solicitante de palestra enviada pelo sistema por e-mail, com status de entrega | `PAL-ANDAMENTO-RESPOSTA` | e-mail institucional após confirmação | 3 |
| AUT-156 | Confirmação de recebimento da entrega pelo responsável no local, por link | `CB-ENTREGAS` | link enviado por e-mail ao responsável | 3 |

## 7. Resumo por classificação

| Classificação | Itens | % | IDs |
|---|---|---|---|
| automação indicada com n8n | 25 | 14% | AUT-06, AUT-07, AUT-08, AUT-09, AUT-22, AUT-23, AUT-31, AUT-37, AUT-38, AUT-39, AUT-41, AUT-47, AUT-99, AUT-111, AUT-136, AUT-141, AUT-144, AUT-145, AUT-148, AUT-150, AUT-153, AUT-156, AUT-157, AUT-162, AUT-164 |
| assistência por IA indicada | 13 | 7% | AUT-50, AUT-57, AUT-58, AUT-76, AUT-80, AUT-81, AUT-86, AUT-88, AUT-89, AUT-92, AUT-93, AUT-94, AUT-171 |
| automação determinística suficiente | 51 | 29% | AUT-05, AUT-12, AUT-15, AUT-17, AUT-18, AUT-19, AUT-20, AUT-25, AUT-26, AUT-27, AUT-28, AUT-29, AUT-36, AUT-42, AUT-43, AUT-44, AUT-45, AUT-49, AUT-51, AUT-53, AUT-54, AUT-55, AUT-56, AUT-64, AUT-67, AUT-68, AUT-69, AUT-70, AUT-72, AUT-73, AUT-75, AUT-79, AUT-83, AUT-85, AUT-91, AUT-102, AUT-109, AUT-110, AUT-114, AUT-124, AUT-133, AUT-137, AUT-139, AUT-140, AUT-142, AUT-147, AUT-149, AUT-152, AUT-158, AUT-160, AUT-161 |
| melhor execução pelo próprio sistema | 27 | 16% | AUT-14, AUT-16, AUT-21, AUT-24, AUT-30, AUT-46, AUT-65, AUT-71, AUT-74, AUT-78, AUT-82, AUT-84, AUT-97, AUT-103, AUT-108, AUT-112, AUT-116, AUT-132, AUT-134, AUT-138, AUT-143, AUT-151, AUT-154, AUT-155, AUT-163, AUT-170, AUT-172 |
| dependente de desenvolvimento | 16 | 9% | AUT-01, AUT-02, AUT-03, AUT-40, AUT-48, AUT-52, AUT-96, AUT-100, AUT-101, AUT-104, AUT-105, AUT-106, AUT-107, AUT-118, AUT-135, AUT-146 |
| dependente de integração externa | 15 | 9% | AUT-04, AUT-32, AUT-66, AUT-113, AUT-115, AUT-117, AUT-119, AUT-120, AUT-121, AUT-122, AUT-123, AUT-125, AUT-159, AUT-173, AUT-174 |
| inadequada ou inviável atualmente | 27 | 16% | AUT-10, AUT-11, AUT-13, AUT-33, AUT-34, AUT-35, AUT-59, AUT-60, AUT-61, AUT-62, AUT-63, AUT-77, AUT-87, AUT-90, AUT-95, AUT-98, AUT-126, AUT-127, AUT-128, AUT-129, AUT-130, AUT-131, AUT-165, AUT-166, AUT-167, AUT-168, AUT-169 |
| **Total** | **174** | 100% | |

**Leitura dos números**

- **78 itens não precisam de n8n nem de IA** (determinística + próprio sistema). São melhorias de
  regra e de tela. A maior parte está na trilha paralela da seção 9.2 e pode entrar a qualquer momento.
- **O n8n aparece em 25 itens**, quase todos de canal e agenda. Quase todos dependem da fundação: API
  v1, worker de entregas e registro de comunicações. Para sair do servidor, dependem também do SMTP
  institucional (AUT-04). As exceções são a instalação (AUT-99), o roteamento de alertas (AUT-111) e a
  detecção de matéria publicada (AUT-148).
- **A IA aparece em 13 itens**, todos de redação ou interpretação com aceite humano. Nenhum deles é
  pré-requisito de outro fluxo.

## 8. Resumo por maturidade

| Maturidade | Itens | IDs |
|---|---|---|
| **1** — viável com recursos existentes | 4 | AUT-12, AUT-99, AUT-111, AUT-116 |
| **2** — depende de desenvolvimento no sistema | 91 | AUT-01, AUT-02, AUT-03, AUT-05, AUT-14, AUT-15, AUT-16, AUT-17, AUT-18, AUT-19, AUT-20, AUT-21, AUT-22, AUT-24, AUT-25, AUT-26, AUT-27, AUT-28, AUT-29, AUT-30, AUT-36, AUT-40, AUT-42, AUT-43, AUT-44, AUT-45, AUT-46, AUT-48, AUT-49, AUT-51, AUT-52, AUT-53, AUT-54, AUT-55, AUT-56, AUT-64, AUT-65, AUT-67, AUT-68, AUT-69, AUT-70, AUT-71, AUT-72, AUT-73, AUT-74, AUT-75, AUT-78, AUT-79, AUT-82, AUT-83, AUT-84, AUT-85, AUT-91, AUT-96, AUT-97, AUT-100, AUT-101, AUT-102, AUT-103, AUT-104, AUT-105, AUT-106, AUT-107, AUT-108, AUT-109, AUT-110, AUT-114, AUT-118, AUT-124, AUT-132, AUT-133, AUT-134, AUT-135, AUT-137, AUT-138, AUT-139, AUT-140, AUT-142, AUT-143, AUT-146, AUT-147, AUT-149, AUT-151, AUT-152, AUT-155, AUT-158, AUT-160, AUT-161, AUT-163, AUT-170, AUT-172 |
| **3** — depende de provedor, credencial ou custo | 40 | AUT-04, AUT-06, AUT-07, AUT-09, AUT-23, AUT-31, AUT-37, AUT-38, AUT-39, AUT-41, AUT-47, AUT-50, AUT-57, AUT-58, AUT-66, AUT-76, AUT-80, AUT-81, AUT-86, AUT-88, AUT-89, AUT-92, AUT-93, AUT-94, AUT-112, AUT-113, AUT-120, AUT-136, AUT-141, AUT-144, AUT-145, AUT-148, AUT-150, AUT-153, AUT-154, AUT-156, AUT-157, AUT-162, AUT-164, AUT-171 |
| **4** — depende de integração institucional | 11 | AUT-08, AUT-32, AUT-115, AUT-117, AUT-119, AUT-121, AUT-122, AUT-123, AUT-125, AUT-159, AUT-173 |
| **5** — bloqueada ou não recomendada atualmente | 28 | AUT-10, AUT-11, AUT-13, AUT-33, AUT-34, AUT-35, AUT-59, AUT-60, AUT-61, AUT-62, AUT-63, AUT-77, AUT-87, AUT-90, AUT-95, AUT-98, AUT-126, AUT-127, AUT-128, AUT-129, AUT-130, AUT-131, AUT-165, AUT-166, AUT-167, AUT-168, AUT-169, AUT-174 (5 só para ativar; a construção desligada está no plano) |

### 8.1 Classificação × maturidade

| Classificação | 1 | 2 | 3 | 4 | 5 | Total |
|---|---|---|---|---|---|---|
| automação indicada com n8n | 2 | 1 | 21 | 1 | · | 25 |
| assistência por IA indicada | · | · | 13 | · | · | 13 |
| automação determinística suficiente | 1 | 50 | · | · | · | 51 |
| melhor execução pelo próprio sistema | 1 | 24 | 2 | · | · | 27 |
| dependente de desenvolvimento | · | 16 | · | · | · | 16 |
| dependente de integração externa | · | · | 4 | 10 | 1 | 15 |
| inadequada ou inviável atualmente | · | · | · | · | 27 | 27 |
| **Total** | **4** | **91** | **40** | **11** | **28** | **174** |

### 8.2 Por tema e por situação atual

| Tema | Itens | Mat. 1–2 | Mat. 3 | Mat. 4 | Mat. 5 | Valor alto |
|---|---|---|---|---|---|---|
| Comunicação e canais | 16 | 6 | 4 | 2 | 4 | 10 |
| Viagens | 22 | 16 | 2 | 1 | 3 | 8 |
| Prestação de contas e documentos | 28 | 15 | 8 | 0 | 5 | 9 |
| Planos, rotas e IA | 36 | 20 | 11 | 0 | 5 | 4 |
| Plataforma, operação e integrações institucionais | 34 | 18 | 3 | 7 | 6 | 18 |
| Outros módulos (Eventos, Palestras, Imprensa, Publicações, Coffee, Cadastros, Painel) | 38 | 20 | 12 | 1 | 5 | 3 |

Situação hoje (coluna "Hoje"): **inexistente** 104; **parcial** 54; **só na referência** 9; **planejado** 5; **existe** 2.

## 9. Lista ordenada por valor e dependência (alimenta o plano de implantação)

**Critério de ordenação.** Primeiro a dependência: nada entra antes do que precisa. Depois o valor (alto →
baixo), a maturidade (menor primeiro) e o esforço (menor primeiro).

As etapas são as do [plano de implantação](plano-implantacao.md), com dois ajustes que vêm dos fluxos:

1. A saúde estendida (AUT-110) fica na fundação. O roteamento de alertas (AUT-111, maturidade 1) abre a etapa 2,
   e pode ser antecipado para logo depois da instalação do n8n.
2. A proposta consolidada (AUT-14) e a semente (AUT-15) não dependem da fundação
   ([11-3](fluxos/11-3-autonomia-progressiva.md), seção 13). Por isso estão na trilha paralela. Na etapa 5
   ficou só o que precisa da fundação (AUT-118, AUT-16).

**Pedidos institucionais demorados saem já na etapa 0**, mesmo que o item fique numa etapa posterior:

- SMTP e caixa postal (AUT-04, AUT-08);
- credenciais do eProtocolo e da Central de Viagens (AUT-119, AUT-120, AUT-122, AUT-125);
- decisão sobre o uso do contato dos servidores (AUT-02).

### 9.1 Etapas do plano

| Ordem | Etapa | ID | Oportunidade | Classificação | Mat. | Valor | Esf. | Depende de |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 | AUT-99 | n8n isolado na VPS atual (contêiner, PostgreSQL próprio, poda de execuções, chave de criptografia guardada fora da VPS), separado por ambiente, com backup e workflows versionados | automação indicada com n8n | 1 | alto | M | — |
| 2 | 0 | AUT-116 | Fila "drive" parada no GV em produção: purgar e reconciliar pelo banco ou reprocessar (decisão D3 do plano) | melhor execução pelo próprio sistema | 1 | médio | M | — |
| 3 | 0 | AUT-12 | Remover os resíduos do canal WhatsApp no EV em produção (unidade de serviço sem comando correspondente e configuração de webhook sem uso) | automação determinística suficiente | 1 | baixo | P | — |
| 4 | 1 | AUT-102 | Política de retentativa por tópico e comando de reprocessamento da outbox | automação determinística suficiente | 2 | alto | P | — |
| 5 | 1 | AUT-01 | Registro de cada comunicação no PCPR (`Comunicacao`): estado, versão, destinatário, texto enviado, histórico de entrega e ações manuais (enviar agora, copiar, marcar "enviado por outro meio") | dependente de desenvolvimento | 2 | alto | M | — |
| 6 | 1 | AUT-02 | Contato verificado, consentimento e identidade do servidor viajante (`ContatoVerificado` e vínculo usuário↔servidor) | dependente de desenvolvimento | 2 | alto | M | — |
| 7 | 1 | AUT-100 | Catálogo de eventos de domínio para integração (viagem, documento, prestação, solicitação, importação) num tópico próprio da outbox | dependente de desenvolvimento | 2 | alto | M | — |
| 8 | 1 | AUT-101 | Worker de entregas com lease: leva os eventos ao n8n fora de transação, com HMAC e retentativa de horas | dependente de desenvolvimento | 2 | alto | M | AUT-100 |
| 9 | 1 | AUT-103 | Tela de saúde da outbox e fila de exceções da automação (dono, prazo, resolver, repetir, fazer à mão) | melhor execução pelo próprio sistema | 2 | alto | M | AUT-102 |
| 10 | 1 | AUT-104 | API de automação v1 (`/api/automacao/v1`) com token de serviço, escopos, delegação emitida pelo PCPR na ação humana (nunca usuário representado declarado pelo chamador), `Idempotency-Key` e chave de desligamento (`/estado`) | dependente de desenvolvimento | 2 | alto | M | — |
| 11 | 1 | AUT-108 | Salvaguardas do registro de ferramentas: contexto de auditoria obrigatório, trava por ambiente, minimização de dados e proibição de reservar número para propostas | melhor execução pelo próprio sistema | 2 | alto | M | AUT-104 |
| 12 | 1 | AUT-110 | Saúde estendida: outbox, importador, rotinas e documentos em falha nas checagens e no `/saude/` | automação determinística suficiente | 2 | alto | M | — |
| 13 | 1 | AUT-03 | Link de acesso com escopo, validade, revogação e registro de uso (`LinkAcesso`) e portal mínimo do servidor (documentos, situação e devolução) | dependente de desenvolvimento | 2 | alto | G | AUT-02 |
| 14 | 1 | AUT-105 | Ferramentas de leitura (fase A da ADR 0020): pendências, busca, conflitos, situação de prestação, com política e auditoria | dependente de desenvolvimento | 2 | alto | G | AUT-104 |
| 15 | 1 | AUT-106 | Portão de aprovação humana e ferramentas de preparação (fases B/C): rascunhos preparados pela máquina e aprovados na tela | dependente de desenvolvimento | 2 | alto | M | AUT-105 |
| 16 | 1 | AUT-05 | E-mail de notificação individual por destinatário (hoje vai uma lista no "Para") | automação determinística suficiente | 2 | médio | P | — |
| 17 | 1 | AUT-109 | Rotinas diárias com horário por rotina, independentes do primeiro acesso e com reexecução só do que falhou | automação determinística suficiente | 2 | médio | P | — |
| 18 | 2 | AUT-111 | Roteamento e escalonamento de alertas operacionais pelo n8n (saúde, filas, auditoria, backup e restauração), inclusive das referências em produção | automação indicada com n8n | 1 | alto | P | AUT-99, AUT-110 |
| 19 | 2 | AUT-21 | Gerar e congelar na emissão as versões de termo, OS e plano (instantâneo dos dados, SHA-256, geração assíncrona) | melhor execução pelo próprio sistema | 2 | alto | M | — |
| 20 | 2 | AUT-36 | Aviso de liberação de diárias ("mensagem de saque"): texto e situação como função de domínio testada, com registro de quem foi avisado | automação determinística suficiente | 2 | alto | M | AUT-01 |
| 21 | 2 | AUT-04 | SMTP institucional: conta, remetente autorizado e credencial para o PCPR e o n8n | dependente de integração externa | 3 | alto | P | — |
| 22 | 2 | AUT-06 | Entrega externa das comunicações e avisos pelo n8n (e-mail institucional): reserva, envio, resultado, devoluções e retentativa | automação indicada com n8n | 3 | alto | M | AUT-01, AUT-02, AUT-04, AUT-101, AUT-104 |
| 23 | 2 | AUT-22 | Envio dos documentos emitidos (ofício, justificativa, termos, OS, plano) a cada servidor e destinatário: só o que é dele, na versão corrente, pelo portal e, com SMTP, por e-mail, com registro por pessoa | automação indicada com n8n | 2 | alto | G | AUT-01, AUT-02, AUT-03, AUT-21, AUT-06 |
| 24 | 2 | AUT-31 | Resumo diário por unidade das viagens próximas (D-7 a D0): ofícios em rascunho, justificativa pendente, planos não gerados ou vazios, termos sem via assinada, eventos deferidos sem proposta | automação indicada com n8n | 3 | alto | P | AUT-104, AUT-105, AUT-06 |
| 25 | 2 | AUT-23 | Aviso de retificação, cancelamento ou reagendamento a quem já recebeu documentos da viagem | automação indicada com n8n | 3 | alto | M | AUT-22, AUT-06 |
| 26 | 2 | AUT-37 | Envio automático do aviso de liberação pelo canal institucional no dia em que a liberação é registrada | automação indicada com n8n | 3 | alto | M | AUT-36, AUT-02, AUT-04, AUT-06 |
| 27 | 2 | AUT-38 | Lembretes ao servidor: saque vencendo, prestação vencida e o que entregar após o retorno, até o comprovante entrar | automação indicada com n8n | 3 | alto | P | AUT-37 |
| 28 | 2 | AUT-24 | Avisos aos operadores nos marcos da viagem: viagem gerada, plano gerado, PDF ou pacote pronto ou com falha definitiva | melhor execução pelo próprio sistema | 2 | médio | P | AUT-100, AUT-06 |
| 29 | 2 | AUT-30 | Aviso interno "sai amanhã" no sino para a equipe de viagens, com horário próprio | melhor execução pelo próprio sistema | 2 | médio | P | AUT-109 |
| 30 | 2 | AUT-07 | Resumo diário por pessoa: pendências e compromissos do dia numa única mensagem | automação indicada com n8n | 3 | médio | P | AUT-105, AUT-06 |
| 31 | 2 | AUT-39 | Resumo de pendências da prestação por equipe (diário) e de prestações paradas (semanal) | automação indicada com n8n | 3 | médio | P | AUT-105, AUT-06 |
| 32 | 2 | AUT-113 | Convite e recuperação de senha por e-mail | dependente de integração externa | 3 | médio | P | AUT-04 |
| 33 | 2 | AUT-136 | Aviso à DG de nova solicitação (agrupado) e resumo diário da fila de despacho por e-mail | automação indicada com n8n | 3 | médio | P | AUT-100, AUT-105, AUT-06 |
| 34 | 2 | AUT-144 | Resposta padrão ao solicitante de palestra enviada pelo sistema por e-mail, com status de entrega | automação indicada com n8n | 3 | médio | P | AUT-01, AUT-06, AUT-138 |
| 35 | 2 | AUT-145 | Lembretes da palestra (palestrante em D-2; ASCOM para cobrar retorno e registrar público) | automação indicada com n8n | 3 | médio | P | AUT-06 |
| 36 | 2 | AUT-150 | Resumo diário "O que fazer hoje" da equipe do coffee | automação indicada com n8n | 3 | médio | P | AUT-105, AUT-06 |
| 37 | 2 | AUT-153 | Aviso de vencimento de certidão e pedido de renovação ao fornecedor | automação indicada com n8n | 3 | médio | P | AUT-04, AUT-06 |
| 38 | 2 | AUT-157 | Alerta semanal de saldo e vigência do contrato com o relatório anexo | automação indicada com n8n | 3 | médio | P | AUT-105, AUT-06 |
| 39 | 2 | AUT-162 | Pauta semanal e escala do dia seguinte enviadas automaticamente | automação indicada com n8n | 3 | médio | P | AUT-04, AUT-105 |
| 40 | 2 | AUT-164 | Envio mensal automático do relatório consolidado e da planilha | automação indicada com n8n | 3 | médio | P | AUT-105, AUT-06 |
| 41 | 2 | AUT-154 | Comunicação formal com o fornecedor (OS, OB e notificação de ocorrência) com prévia editável, aprovação e registro | melhor execução pelo próprio sistema | 3 | médio | M | AUT-04, AUT-06 |
| 42 | 3 | AUT-53 | Conferência de via assinada (ADR 0022) estendida a DB, RT e plano e feita no original antes de separar páginas | automação determinística suficiente | 2 | alto | M | — |
| 43 | 3 | AUT-97 | Central de ajuda com base aprovada e página "Minha situação" do servidor (prazos, pendências e documentos, sem IA) | melhor execução pelo próprio sistema | 2 | alto | M | AUT-02, AUT-03 |
| 44 | 3 | AUT-40 | Link de quilometragem por trecho para o motorista (página que funciona sem sinal no celular, token em hash) | dependente de desenvolvimento | 2 | alto | G | AUT-03, AUT-02 |
| 45 | 3 | AUT-132 | Caixa de entrada única de demandas: cada e-mail ou pedido vira item com o original preservado e conversão assistida em rascunho no módulo certo (solicitação, palestra, imprensa, pauta, coffee, anexo da viagem) | melhor execução pelo próprio sistema | 2 | alto | G | AUT-104 |
| 46 | 3 | AUT-41 | Envio do link de km na véspera (America/Sao_Paulo) e lembretes pelo canal institucional | automação indicada com n8n | 3 | alto | P | AUT-40, AUT-06, AUT-30 |
| 47 | 3 | AUT-112 | Pipeline único de entrada de arquivos com antivírus (tela, importação, portal e n8n) | melhor execução pelo próprio sistema | 3 | alto | M | — |
| 48 | 3 | AUT-52 | Recebimento de documentos devolvidos pelo servidor: portal por link e ingestão autenticada na importação documental, com rastro de remetente e resposta padronizada | dependente de desenvolvimento | 2 | alto | M | AUT-01, AUT-02, AUT-03, AUT-104, AUT-112 |
| 49 | 3 | AUT-08 | Leitura das caixas postais institucionais pelo n8n (IMAP/OAuth) com deduplicação por Message-ID, entregando ao PCPR documentos devolvidos e pedidos recebidos | automação indicada com n8n | 4 | alto | M | AUT-52, AUT-132, AUT-112 |
| 50 | 3 | AUT-43 | Sugerir os horários realizados a partir dos lançamentos do link de km | automação determinística suficiente | 2 | médio | P | AUT-40 |
| 51 | 3 | AUT-44 | Validação de continuidade do km (saltos e retrocessos) e de prontidão do DB antes de assinar | automação determinística suficiente | 2 | médio | P | — |
| 52 | 3 | AUT-46 | DB e RT prontos para assinatura: conclusão explícita, versão congelada (instantâneo e SHA-256), assinante pela regra do documento, devolução ligada à versão e aviso ao operador | melhor execução pelo próprio sistema | 2 | alto | M | AUT-44, AUT-53 |
| 53 | 3 | AUT-47 | Disponibilizar DB e RT ao signatário pelo portal e avisar por e-mail, com lembrete antes do prazo | automação indicada com n8n | 3 | alto | M | AUT-46, AUT-03, AUT-06 |
| 54 | 3 | AUT-55 | Comprovante: extrair valor, data e operação na entrada e casar pela janela de saque e pelo valor | automação determinística suficiente | 2 | médio | P | AUT-54 |
| 55 | 3 | AUT-48 | Relato do servidor (o que fez, público, intercorrências) coletado por link | dependente de desenvolvimento | 2 | médio | M | AUT-03, AUT-02 |
| 56 | 3 | AUT-133 | Triagem determinística do módulo provável na caixa de entrada, com sinais visíveis e confirmação humana | automação determinística suficiente | 2 | médio | M | AUT-132 |
| 57 | 3 | AUT-143 | Formulário público de pedido de palestra com acompanhamento por link (e confirmação por e-mail quando houver SMTP) | melhor execução pelo próprio sistema | 2 | médio | M | AUT-04 |
| 58 | 3 | AUT-151 | Coffee na importação documental e na conferência de vias (NF, OB, certidões, processo de pagamento, vias assinadas) | melhor execução pelo próprio sistema | 2 | médio | M | — |
| 59 | 3 | AUT-155 | Link seguro do fornecedor para enviar NF e certidões | melhor execução pelo próprio sistema | 2 | médio | M | AUT-03, AUT-112 |
| 60 | 3 | AUT-09 | Agenda do dia seguinte enviada a cada servidor escalado (véspera) | automação indicada com n8n | 3 | médio | P | AUT-02, AUT-06, AUT-105 |
| 61 | 3 | AUT-148 | Detecção da matéria publicada por feed público, preenchendo link e data | automação indicada com n8n | 3 | baixo | P | — |
| 62 | 3 | AUT-141 | Confirmação pós-evento pelo responsável por link enviado por e-mail | automação indicada com n8n | 3 | baixo | M | AUT-03, AUT-06 |
| 63 | 3 | AUT-156 | Confirmação de recebimento da entrega pelo responsável no local, por link | automação indicada com n8n | 3 | baixo | M | AUT-03, AUT-06 |
| 64 | 4 | AUT-96 | Porta única de IA em `gestao/integracoes/` com adaptadores simulado e gravado, validador de saída e worker | dependente de desenvolvimento | 2 | alto | M | — |
| 65 | 4 | AUT-91 | Conjunto de avaliação com gabarito (casos fictícios novos) para leituras por regra e por IA | automação determinística suficiente | 2 | médio | P | — |
| 66 | 4 | AUT-50 | Rascunho do RT por IA ancorado nos dados do sistema, no plano e no relato do servidor | assistência por IA indicada | 3 | médio | M | AUT-48, AUT-96, AUT-91 |
| 67 | 4 | AUT-76 | Leitura da programação por IA: pedido, e-mail ou anexo em texto livre → proposta estruturada de destinos, datas e horários para conferência | assistência por IA indicada | 3 | médio | M | AUT-64, AUT-96, AUT-91, AUT-105 |
| 68 | 4 | AUT-80 | Rascunho por IA da contextualização e das considerações do Plano de Trabalho a partir da solicitação e dos dados reais, com validador de fatos | assistência por IA indicada | 3 | médio | M | AUT-79, AUT-96, AUT-91 |
| 69 | 4 | AUT-81 | Rascunho por IA do motivo do ofício e da justificativa por antecedência insuficiente | assistência por IA indicada | 3 | médio | M | AUT-96, AUT-91 |
| 70 | 4 | AUT-92 | Extração por IA de pedidos em texto livre só quando o leitor por regras não acha o campo | assistência por IA indicada | 3 | médio | M | AUT-132, AUT-96, AUT-91 |
| 71 | 4 | AUT-88 | Assistente de dúvidas dos servidores (só leitura): situação da própria viagem, diárias, prazos, documentos e procedimentos | assistência por IA indicada | 3 | médio | G | AUT-97, AUT-02, AUT-03, AUT-105, AUT-96, AUT-91 |
| 72 | 4 | AUT-107 | Fachada MCP sobre o registro de ferramentas | dependente de desenvolvimento | 2 | baixo | P | AUT-105, AUT-106 |
| 73 | 4 | AUT-86 | Rascunho por IA de meta e recurso para serviços sem complemento | assistência por IA indicada | 3 | baixo | P | AUT-96 |
| 74 | 4 | AUT-94 | Nota executiva do mês por IA sobre o relatório consolidado | assistência por IA indicada | 3 | baixo | P | AUT-164, AUT-96 |
| 75 | 4 | AUT-57 | IA só como sugestão de tipo e destino na revisão da importação | assistência por IA indicada | 3 | baixo | M | AUT-96 |
| 76 | 4 | AUT-58 | Extração por IA de campos de comprovantes e NFS-e de layout desconhecido (só sugestão) | assistência por IA indicada | 3 | baixo | M | AUT-54, AUT-96 |
| 77 | 4 | AUT-89 | Explicar em linguagem simples o que falta numa viagem (operadores) | assistência por IA indicada | 3 | baixo | M | AUT-105, AUT-96 |
| 78 | 4 | AUT-93 | Triagem por IA do módulo de destino só quando nenhum sinal determinístico pontuou | assistência por IA indicada | 3 | baixo | M | AUT-133, AUT-96, AUT-91 |
| 79 | 5 | AUT-118 | Autorização por fluxo (sombra → assistido → automático), painel "o que a automação fez" e desfazer | dependente de desenvolvimento | 2 | alto | M | AUT-106 |
| 80 | 5 | AUT-16 | Preparar automaticamente, no deferimento, a viagem ou a proposta em rascunho, como assinante interno da outbox | melhor execução pelo próprio sistema | 2 | médio | P | AUT-100 |
| 81 | 6 | AUT-120 | Consulta periódica do andamento dos protocolos e aviso de mudança ou de chegada ao setor | dependente de integração externa | 3 | alto | M | AUT-170 |
| 82 | 6 | AUT-119 | Abrir protocolo no eProtocolo pela API (ofício, pagamento do coffee) atrás do portão de aprovação | dependente de integração externa | 4 | alto | G | AUT-106 |
| 83 | 6 | AUT-122 | Juntar documentos e o pacote da prestação ao processo e solicitar assinatura no eProtocolo, com aprovação | dependente de integração externa | 4 | alto | G | AUT-106 |
| 84 | 6 | AUT-125 | Integração oficial com a Central de Viagens / sistema de diárias: registrar a solicitação e importar nº, liberação e prazo de saque | dependente de integração externa | 4 | alto | G | — |
| 85 | 6 | AUT-32 | Fonte de indisponibilidade de servidores (férias, afastamentos) nos conflitos | dependente de integração externa | 4 | médio | M | — |
| 86 | 6 | AUT-121 | Interpretar o andamento do protocolo como sugestão de marco (prestação aprovada ou devolvida; atesto e OB do coffee) | dependente de integração externa | 4 | médio | M | AUT-120 |
| 87 | 6 | AUT-123 | Trazer do eProtocolo o ofício assinado, o despacho e o processo para a importação documental | dependente de integração externa | 4 | médio | M | AUT-112 |
| 88 | 6 | AUT-159 | Sincronização agendada da fonte dedicada de cadastros (servidores, cargos, unidades) preservando complementos locais | dependente de integração externa | 4 | médio | M | AUT-104 |
| 89 | 6 | AUT-160 | Reconhecimento assistido dos vínculos iniciais com a fonte de cadastros | automação determinística suficiente | 2 | médio | P | AUT-159 |
| 90 | 6 | AUT-115 | SSO pela Central de Segurança do PR | dependente de integração externa | 4 | médio | G | — |
| 91 | 6 | AUT-171 | Resumo por IA das movimentações do protocolo e sugestão de assunto e palavras-chave na abertura | assistência por IA indicada | 3 | baixo | M | AUT-120, AUT-96 |
| 92 | 6 | AUT-117 | Espelho Google Drive no sistema novo como assinante da outbox com estado por item | dependente de integração externa | 4 | baixo | G | — |

- **Etapa 0 — Pré-requisitos (VPS, n8n sem fluxos, correções nas referências):** AUT-99, AUT-116, AUT-12.
- **Etapa 1 — Fundação no PCPR:** AUT-102, AUT-01, AUT-02, AUT-100, AUT-101, AUT-103, AUT-104, AUT-108, AUT-110, AUT-03, AUT-105, AUT-106, AUT-05, AUT-109.
- **Etapa 2 — Primeiras automações (comunicação e avisos):** AUT-111, AUT-21, AUT-36, AUT-04, AUT-06, AUT-22, AUT-31, AUT-23, AUT-37, AUT-38, AUT-24, AUT-30, AUT-07, AUT-39, AUT-113, AUT-136, AUT-144, AUT-145, AUT-150, AUT-153, AUT-157, AUT-162, AUT-164, AUT-154.
- **Etapa 3 — Campo, prestação e entrada de documentos:** AUT-53, AUT-97, AUT-40, AUT-132, AUT-41, AUT-112, AUT-52, AUT-08, AUT-43, AUT-44, AUT-46, AUT-47, AUT-55, AUT-48, AUT-133, AUT-143, AUT-151, AUT-155, AUT-09, AUT-148, AUT-141, AUT-156.
- **Etapa 4 — IA assistiva:** AUT-96, AUT-91, AUT-50, AUT-76, AUT-80, AUT-81, AUT-92, AUT-88, AUT-107, AUT-86, AUT-94, AUT-57, AUT-58, AUT-89, AUT-93.
- **Etapa 5 — Autonomia progressiva (depende da fundação):** AUT-118, AUT-16.
- **Etapa 6 — Integrações institucionais:** AUT-120, AUT-119, AUT-122, AUT-125, AUT-32, AUT-121, AUT-123, AUT-159, AUT-160, AUT-115, AUT-171, AUT-117.

**Frentes do WhatsApp (prioridade do usuário, 17/10/2026).** Correm à parte da ordem acima, sem esperar as
outras etapas ([plano](plano-implantacao.md), seção "Prioridade definida pelo usuário"):

| Frente | Etapa | ID | Oportunidade | Classificação | Mat. | Valor | Esf. | Depende de |
|---|---|---|---|---|---|---|---|---|
| WA-2 | 0 | AUT-173 | Consulta formal de elegibilidade à Meta ou a provedor autorizado | dependente de integração externa | 4 | alto | P | decisão D4a do plano |
| WA-1 | 1 | AUT-172 | WhatsApp assistido com registro (mensagem mínima, `wa.me` no aparelho institucional, registro) | melhor execução pelo próprio sistema | 2 | alto | P | AUT-01, AUT-02, AUT-36; D4a |
| WA-3 | 1–2 | AUT-174 | Integração oficial pronta e desligada (porta, opt-in, modelos, webhook, workflows desligados) | dependente de integração externa | 5 para ativar | alto | G | fundação da etapa 1; portão de ativação |

### 9.2 Trilha paralela: melhorias no próprio sistema, sem n8n nem fundação

Itens de maturidade 2 que não usam n8n, IA nem a fundação. Podem entrar entre as etapas, conforme a
capacidade de desenvolvimento.

A última coluna diz qual etapa precisa do item pronto, por dependência direta ou indireta. "—" significa
que nada depende dele. O provedor de rotas (AUT-66, maturidade 3) entra aqui porque é uma decisão
independente do restante.

| Ordem | ID | Oportunidade | Classificação | Mat. | Valor | Esf. | Necessário antes da etapa |
|---|---|---|---|---|---|---|---|
| P1 | AUT-138 | Contato do solicitante estruturado (e-mail, telefone) na solicitação | melhor execução pelo próprio sistema | 2 | médio | P | 2 |
| P2 | AUT-54 | Persistir o texto/OCR de cada parte importada | automação determinística suficiente | 2 | médio | P | 3 |
| P3 | AUT-64 | Proposta determinística de roteiro a partir da viagem ou do evento (sede → município → sede, horários calculados, alternativas com diferença em km e diárias) | automação determinística suficiente | 2 | alto | M | 4 |
| P4 | AUT-79 | Texto-base de contextualização por programa cadastrado pelo gestor | automação determinística suficiente | 2 | médio | P | 4 |
| P5 | AUT-170 | Salvaguardas do eProtocolo por ambiente: adaptador desligado em produção sem credencial, trava de mutação para todas as operações e pendência "protocolo não oficial" quando o número vier do simulado ou do treinamento | melhor execução pelo próprio sistema | 2 | alto | P | 6 |
| P6 | AUT-25 | Data-limite para emitir sem justificativa e aviso de "pronto para emitir" | automação determinística suficiente | 2 | alto | P | — |
| P7 | AUT-29 | Alerta proativo de conflitos de pessoa ou viatura nos próximos 7 dias e de conflito novo em ofício já emitido | automação determinística suficiente | 2 | alto | P | — |
| P8 | AUT-15 | Semente completa da viagem e do plano a partir da solicitação deferida (serviços → atividades, órgão/programa, efetivo, unidade móvel, motorista sugerido) | automação determinística suficiente | 2 | alto | M | — |
| P9 | AUT-134 | Sincronização entre módulos: alteração ou cancelamento da solicitação refletidos na viagem, no coffee e na palestra, e decisão da DG refletida na palestra | melhor execução pelo próprio sistema | 2 | alto | M | — |
| P10 | AUT-135 | Vincular unidade móvel à viatura e a "equipe" do evento aos servidores | dependente de desenvolvimento | 2 | alto | M | — |
| P11 | AUT-14 | Proposta consolidada: selecionar o evento, informar quem vai e conferir numa tela só roteiro, ofícios, diárias, termos, OS, plano, conflitos e pendências, sem gravar nem numerar até aprovar | melhor execução pelo próprio sistema | 2 | alto | G | — |
| P12 | AUT-66 | Provedor de rotas de produção atrás de porta (`gestao/integracoes/rotas`): OSRM próprio ou OpenRouteService com chave | dependente de integração externa | 3 | alto | M | — |
| P13 | AUT-18 | Termos gerados no lote com o nome da ação correta em vez do padrão "PCPR na Comunidade" | automação determinística suficiente | 2 | médio | P | — |
| P14 | AUT-19 | Preencher automaticamente o ofício e o protocolo de origem do motorista externo (quando há um único candidato) | automação determinística suficiente | 2 | médio | P | — |
| P15 | AUT-20 | Pré-atribuir as funções da Ordem de Serviço (condução ao motorista etc.) | automação determinística suficiente | 2 | médio | P | — |
| P16 | AUT-26 | Alerta antecipado de tabela de diárias sem vigência | automação determinística suficiente | 2 | médio | P | — |
| P17 | AUT-28 | Aviso de cadastro incompleto (CPF, cargo) de servidor escalado em viagem próxima | automação determinística suficiente | 2 | médio | P | — |
| P18 | AUT-42 | Km inicial do diário pré-preenchido pelo último km da viatura | automação determinística suficiente | 2 | médio | P | — |
| P19 | AUT-45 | DB com motorista de outro ofício: signatário correto e direcionamento correto do assinado | automação determinística suficiente | 2 | médio | P | — |
| P20 | AUT-49 | RT sem afirmações não verificadas por padrão (ex.: "sem intercorrências") | automação determinística suficiente | 2 | médio | P | — |
| P21 | AUT-56 | Posição automática do carimbo do nº da solicitação pela linha do servidor no PDF | automação determinística suficiente | 2 | médio | P | — |
| P22 | AUT-65 | Fonte do km e do tempo registrada no trecho e "Usar roteiro" preservando km e tempos | melhor execução pelo próprio sistema | 2 | médio | P | — |
| P23 | AUT-67 | Ordem sugerida dos destinos por menor percurso | automação determinística suficiente | 2 | médio | P | — |
| P24 | AUT-68 | Sugerir roteiro cadastrado compatível com os destinos da viagem | automação determinística suficiente | 2 | médio | P | — |
| P25 | AUT-69 | Aviso de chegada incompatível com o início do atendimento | automação determinística suficiente | 2 | médio | P | — |
| P26 | AUT-70 | Sugestão bate-volta × pernoite pelo tempo de estrada | automação determinística suficiente | 2 | médio | P | — |
| P27 | AUT-72 | Recalcular rotas desatualizadas (repetição em outra cidade, mudança de roteiro ou de tabela) e avisar divergência de diárias, só em rascunhos | automação determinística suficiente | 2 | médio | P | — |
| P28 | AUT-82 | Aviso de texto editado desatualizado após mudança de dados | melhor execução pelo próprio sistema | 2 | médio | P | — |
| P29 | AUT-83 | Lembrete de lançamento de resultados após o fim do evento | automação determinística suficiente | 2 | médio | P | — |
| P30 | AUT-114 | Revisão periódica de acessos (contas ociosas e papéis sensíveis) | automação determinística suficiente | 2 | médio | P | — |
| P31 | AUT-124 | Painel "dados para a Central de Viagens" com botão copiar | automação determinística suficiente | 2 | médio | P | — |
| P32 | AUT-137 | Resumo de despacho determinístico na folha da DG (conflitos, antecedência, ocupação de unidades móveis) | automação determinística suficiente | 2 | médio | P | — |
| P33 | AUT-146 | Vincular integrantes da ASCOM a usuários | dependente de desenvolvimento | 2 | médio | P | — |
| P34 | AUT-147 | Alerta de prazo (deadline) do atendimento à imprensa | automação determinística suficiente | 2 | médio | P | — |
| P35 | AUT-152 | Separar "baixar pacote" de "registrar atesto" no protocolo de pagamento | automação determinística suficiente | 2 | médio | P | — |
| P36 | AUT-161 | Alertas de configuração da unidade: assinante de planos ausente, substituição de assinante começando ou terminando, sede ausente | automação determinística suficiente | 2 | médio | P | — |
| P37 | AUT-17 | Sugestões explicáveis de equipe, motorista e viatura no "quem vai" | automação determinística suficiente | 2 | médio | M | — |
| P38 | AUT-74 | Limitar e tornar assíncrona a API de rota | melhor execução pelo próprio sistema | 2 | médio | M | — |
| P39 | AUT-78 | Divergências entre plano e ofícios (datas, efetivo, diárias) com "atualizar do ofício" | melhor execução pelo próprio sistema | 2 | médio | M | — |
| P40 | AUT-27 | Lembrete de rascunhos vazios que prendem números | automação determinística suficiente | 2 | baixo | P | — |
| P41 | AUT-51 | Feriados no cálculo de dias úteis (prazo da prestação e data do RT) | automação determinística suficiente | 2 | baixo | P | — |
| P42 | AUT-71 | Aplicar o tempo de veículo lento no bate-volta | melhor execução pelo próprio sistema | 2 | baixo | P | — |
| P43 | AUT-73 | Aquecimento do cache de distâncias a partir da sede de cada unidade | automação determinística suficiente | 2 | baixo | P | — |
| P44 | AUT-75 | Descrição do roteiro em texto por modelo fixo a partir dos trechos calculados | automação determinística suficiente | 2 | baixo | P | — |
| P45 | AUT-139 | Sugestão de serviços e equipes pelo histórico do solicitante ou do tipo de evento | automação determinística suficiente | 2 | baixo | P | — |
| P46 | AUT-140 | Ajustes nos lembretes de solicitações: destinatários da DG pela permissão e lembrete de rascunho esquecido | automação determinística suficiente | 2 | baixo | P | — |
| P47 | AUT-142 | Sugerir mudança de situação do evento ou da solicitação pelas datas | automação determinística suficiente | 2 | baixo | P | — |
| P48 | AUT-149 | Sugestão de correspondência entre unidade responsável (ASCOM) e unidade policial | automação determinística suficiente | 2 | baixo | P | — |
| P49 | AUT-158 | Lembrete de virada de exercício (lotes do ano novo) | automação determinística suficiente | 2 | baixo | P | — |
| P50 | AUT-163 | Feed iCalendar de equipe ou de unidade | melhor execução pelo próprio sistema | 2 | baixo | P | — |
| P51 | AUT-84 | Criar evento adicional do plano a partir de outra solicitação ou ofício da mesma viagem | melhor execução pelo próprio sistema | 2 | baixo | M | — |
| P52 | AUT-85 | Detecção de possíveis duplicatas no catálogo de serviços e atividades (só sugestão) | automação determinística suficiente | 2 | baixo | M | — |

### 9.3 Fora do plano (maturidade 5)

AUT-174 também tem maturidade 5, mas **está no plano**: a integração oficial do WhatsApp é construída e
testada desligada (frente WA-3), e só a ativação depende do portão. A lista abaixo é do que não se constrói.

- **AUT-10** — Canal WhatsApp Business Platform (Cloud API) para avisos, links, documentos e recebimento de devolvidos
- **AUT-11** — Integração não oficial de WhatsApp (automação do WhatsApp Web, bibliotecas não oficiais, número pessoal)
- **AUT-13** — IA escolhendo destinatários ou redigindo avisos, respostas padrão ao solicitante e observações de despacho
- **AUT-33** — IA escolhendo quem participa, a equipe ou a viatura
- **AUT-34** — IA calculando ou ajustando diárias (ofício ou plano)
- **AUT-35** — Emitir, finalizar, retificar, reabrir, cancelar ou excluir documentos e viagens automaticamente
- **AUT-59** — Assinatura eletrônica simples por link público feita pelo próprio sistema (como o GV faz com RT e DB)
- **AUT-60** — Finalização automática da prestação
- **AUT-61** — IA decidindo o destino dos documentos importados
- **AUT-62** — Leitura automática do km por foto do hodômetro
- **AUT-63** — IA no carimbo do nº da solicitação
- **AUT-77** — IA calculando rotas, distâncias ou tempos
- **AUT-87** — IA redigindo ou editando texto determinativo de documento oficial (OS; coordenação, atividades, metas e recursos do plano; regiões do documento)
- **AUT-90** — Reinstalar o assistente do EV ou copiar o seu código
- **AUT-95** — Rascunho de resposta à imprensa por IA
- **AUT-98** — Modelo de IA local na VPS atual
- **AUT-126** — n8n consumindo endpoints de tela (cookie/sessão), o feed ICS pessoal ou o banco diretamente
- **AUT-127** — IA ou n8n decidindo retentativas, avaliando a integridade da auditoria, diagnosticando incidentes ou operando deploy e infraestrutura
- **AUT-128** — Robô de navegador no portal do eProtocolo ou da Central de Viagens
- **AUT-129** — IA decidindo abertura ou tramitação de protocolo
- **AUT-130** — Levar para o n8n a organização de pastas e nomes do espelho Drive
- **AUT-131** — Carga contínua GV → sistema novo por n8n ou IA
- **AUT-165** — Despacho da DG por automação, IA ou resposta de e-mail ou mensagem
- **AUT-166** — Emitir certidões automaticamente nos portais dos órgãos
- **AUT-167** — Registrar marcos financeiros do coffee por IA
- **AUT-168** — Casar identidades de pessoas por IA
- **AUT-169** — Atualizar a tabela de diárias automaticamente a partir da norma

## 10. Divergências encontradas e pontos a confirmar

**Entre leituras, fluxos e a matriz**

1. **E-mail institucional de entrada — alinhado.** Os fluxos dão 4 à leitura de caixa postal:
   [10-6](fluxos/10-6-recebimento-de-documentos.md) (credencial IMAP e `Authentication-Results` concedidos
   pela TI), [10-3](fluxos/10-3-prestacao-e-mensagem-de-saque.md) item C1 (comprovante por resposta de
   e-mail, corrigido de 3 para 4) e [10-1](fluxos/10-1-assistente-dos-servidores.md) (canal e-mail). A matriz
   usa 4 para a leitura de caixa postal (AUT-08) e 3 para o envio SMTP (AUT-04). Falta confirmar com a TI se
   envio e leitura saem do mesmo pedido. Se saírem, os dois ficam no mesmo nível.
2. **WhatsApp nos fluxos.** Corrigido em 17/10/2026: todos os fluxos usam 5/BLOQUEADO para a plataforma
   oficial, sem condição de autorização interna, como a matriz e
   [whatsapp-viabilidade.md](whatsapp-viabilidade.md), seção 2 (os 10-3, 10-4 e 10-5 tinham sido escritos
   antes da conclusão da pesquisa). Na mesma data, com a prioridade definida pelo usuário, os fluxos que
   avisam servidores (10-2 a 10-6) passaram a registrar as frentes WA-1 (2, AUT-172), WA-2 (4, AUT-173) e
   WA-3 (5 para ativar, AUT-174); os fluxos internos (10-1, 11-1 a 13) dizem que as frentes não os cobrem.
3. **Leitura do km por foto — resolvida.** O 10-4 dava 4 ("não recomendado agora"); agora dá 5,
   inadequada ou inviável atualmente, como a matriz (AUT-62), porque a recomendação é não fazer.
4. **Preparar a viagem no deferimento.** As leituras divergiram:
   - planos-rotas: inadequada, pelo risco de consumir números;
   - viagens-núcleo: dependente de desenvolvimento;
   - outros-módulos e EV: execução do próprio sistema (o EV já faz).

   A matriz segue o [11-3](fluxos/11-3-autonomia-progressiva.md): assinante interno da outbox que não cria
   nada numerado (AUT-16). A decisão é do dono do produto.
5. **Porta de IA com dois nomes — resolvida.** O 10-1 propunha `gestao/integracoes/llm` e o 11-2,
   `gestao/integracoes/ia`. Nome adotado em todos os fluxos e fichas: `gestao/integracoes/ia`, uma porta só
   (AUT-96).
6. **Resumo de eventos deferidos sem proposta.** O 11-3 dá 2, porque a alternativa no sino funciona sem
   credencial. A matriz dá 3 ao resumo por e-mail (AUT-31), que depende de SMTP. A versão no sino é 2.
7. **Agendador das rotinas.** As leituras do EV sugeriam o n8n como agendador externo. A matriz usa timers
   do próprio sistema (AUT-109) para não criar dependência do n8n, que continua útil para vigiar se as
   rotinas rodaram (AUT-111).
8. **Pauta semanal.** A leitura do EV recomenda mantê-la sem n8n; as do sistema novo indicam envio pelo
   n8n. A matriz mantém a geração no sistema e põe só o envio no n8n (AUT-162). Uma alternativa equivalente é
   o PCPR enviar direto, quando o tópico de e-mail aceitar anexo.
9. **Resposta à imprensa por IA.** A leitura classificou como assistência por IA de risco alto. A matriz
   reclassifica como inadequada atualmente (AUT-95) até existir política institucional de uso de IA com
   informação policial.
10. **Descrição do roteiro.** A leitura do EV sugeria IA. A matriz usa um modelo fixo (AUT-75), coerente com
    o 11-1.
11. **Ordem do plano.** Resolvido no plano (17/10/2026): a etapa 5 ficou com AUT-118 e AUT-16, e AUT-14 e
    AUT-15 foram para a trilha paralela, como pede o 11-3 (as entregas E0–E4 não dependem da fundação).
    Reconferir quando o plano for reescrito.
12. **Consulta de protocolos.** O [13](fluxos/13-integracoes-institucionais.md) dá 3 à consulta e ao
    acompanhamento assim que houver credencial de treinamento, e 4 às mutações. A matriz segue o fluxo
    (AUT-120 = 3; AUT-119, AUT-122, AUT-123 = 4), mas mantém 4 para interpretar o andamento como marco (AUT-121),
    porque o significado das movimentações não é público. O 13 também corrige o levantamento: no sistema
    novo, "abrir sempre recusa" vale só para o adaptador HTTP; sem credencial o serviço cai no simulado, que
    devolve número fictício (AUT-170 fecha isso).
13. **Envio de documentos.** O 10-2 declara maturidade 2 para o fluxo (portal) e 3 só para o e-mail sair. A
    matriz mantém 2 em AUT-22, mas os avisos que só existem por e-mail (AUT-23, AUT-47) ficam em 3.
14. **Resumos agendados × contrato rascunho 3.** Várias fichas desenhavam o n8n chamando uma ferramenta de
    preparação "como cada destinatário" (AUT-07, AUT-31, AUT-39, AUT-136, AUT-150, AUT-157, AUT-162,
    AUT-164). O contrato não permite: o token de transporte não tem `ferramentas:*` e a delegação só nasce
    de uma ação humana (≤ 15 min, uso único). As fichas passaram a montar o resumo no PCPR (rotina AUT-109,
    com a política de cada destinatário) e o n8n só transporta a `Comunicacao`. A classificação continua
    "automação indicada com n8n" (canal e entrega); se o usuário quiser o n8n como agendador, o contrato
    precisa de uma rota de preparação para o token de transporte. Os tipos `resumo_*` e `agenda_vespera` (AUT-09) também não
    estão no `TipoComunicacao` do rascunho 3.
15. **Propostas dos fluxos ainda fora do contrato rascunho 3.** (a) 10-6 E1 e 10-1 §6.2: identificar a
    mensagem pelo UID do IMAP (não pelo `Message-ID`) e mandar os `Authentication-Results` em bruto para o
    PCPR interpretar; o contrato ainda tem `Message-ID` e `autenticacao`/`autenticacao_remetente`
    interpretados antes. (b) AUT-104: chave de `resultado` sem o token da reserva (`sha256(token)[:16]`). (c)
    11-2 alternativa D6: o evento `texto.rascunho_solicitado` não tem campo para o id da delegação. (d)
    `arquivo_malicioso` em `Recebimento.motivo_codigo` (AUT-112). Ficam como proposta até o próximo rascunho.

**A confirmar com o usuário ou com a instituição**

- Se o envio e o recebimento por portal e e-mail são aceitos como complemento da tramitação oficial do
  eProtocolo (Decreto 7.304/2021).
- Se a PCPR tem contas institucionais no Google Workspace do Estado e quem concede SMTP e caixa postal. A
  notícia oficial de 01/12/2025 cita 26 órgãos sem nomeá-los
  (<https://www.parana.pr.gov.br/aen/Noticia/Governo-do-Estado-amplia-uso-do-Google-Workspace-e-ativa-60-mil-contas-corporativas>,
  consultada em 17/10/2026).
- Volumes reais, para trocar as estimativas de valor por números: viagens, servidores e prestações por
  mês, e-mails recebidos, dúvidas ao suporte.
- Regras institucionais que vários itens usam sem fonte: horário da véspera, limiar de salto de km, margem
  de chegada, regra de jornada para bate-volta, prazo de lançamento de resultados, quem assina o DB quando
  há revezamento.
- Se a preparação automática no deferimento (AUT-16) é desejada.

## Apêndice A. Rastreabilidade das 337 oportunidades

Cada linha é uma oportunidade como a leitura a escreveu, na ordem das leituras e dos processos. `O001` a
`O337` são números deste apêndice, não ids de sistema.

"Item" é o `AUT-NN` em que a oportunidade foi consolidada. Quando a proposta citava WhatsApp, a parte
WhatsApp foi para AUT-10.

| # | Leitura | Processo | Oportunidade (como a leitura escreveu) | Classificação original | Item |
|---|---|---|---|---|---|
| O001 | novo · planos-rotas | `PT-CRIACAO-NUMERACAO` | Semear o plano com os serviços da solicitação de evento | automação determinística suficiente | AUT-15 |
| O002 | novo · planos-rotas | `PT-CRIACAO-NUMERACAO` | Ferramenta 'planos.preparar_rascunho' para automação | dependente de desenvolvimento | AUT-106 |
| O003 | novo · planos-rotas | `PT-HERANCA-OFICIOS` | Aviso de divergência plano x ofícios e botão 'atualizar do ofício' | melhor execução pelo próprio sistema | AUT-78 |
| O004 | novo · planos-rotas | `PT-TEXTOS-AUTOMATICOS` | Sugestão de redação por IA da contextualização e das considerações com dados reais | assistência por IA indicada | AUT-80 |
| O005 | novo · planos-rotas | `PT-TEXTOS-AUTOMATICOS` | Textos prontos de contextualização por programa | automação determinística suficiente | AUT-79 |
| O006 | novo · planos-rotas | `PT-TEXTOS-AUTOMATICOS` | Coordenação, atividades, metas e recursos por IA | inadequada ou inviável atualmente | AUT-87 |
| O007 | novo · planos-rotas | `PT-ATIVIDADES-CONJUNTOS` | Sugerir conjunto pelo tipo de evento/serviços pedidos | automação determinística suficiente | AUT-15 |
| O008 | novo · planos-rotas | `PT-DIARIAS` | Conciliação diárias do plano x soma das diárias dos ofícios | melhor execução pelo próprio sistema | AUT-78 |
| O009 | novo · planos-rotas | `PT-DIARIAS` | Diárias calculadas por IA | inadequada ou inviável atualmente | AUT-34 |
| O010 | novo · planos-rotas | `PT-MULTIEVENTO` | Criar evento adicional a partir de outra solicitação/ofício da mesma viagem | dependente de desenvolvimento | AUT-84 |
| O011 | novo · planos-rotas | `PT-PENDENCIAS-FINALIZAR-GERAR` | Congelar o documento gerado (Documento versionado com sha256) | melhor execução pelo próprio sistema | AUT-21 |
| O012 | novo · planos-rotas | `PT-PENDENCIAS-FINALIZAR-GERAR` | Publicar 'viagens.plano.gerado' na outbox para notificação | automação indicada com n8n | AUT-24 |
| O013 | novo · planos-rotas | `PT-PENDENCIAS-FINALIZAR-GERAR` | Finalizar/gerar automaticamente | inadequada ou inviável atualmente | AUT-35 |
| O014 | novo · planos-rotas | `PT-EDITOR-TEXTO` | IA editando regiões do documento | inadequada ou inviável atualmente | AUT-87 |
| O015 | novo · planos-rotas | `PT-EDITOR-TEXTO` | Aviso de texto editado desatualizado após mudança de dados | melhor execução pelo próprio sistema | AUT-82 |
| O016 | novo · planos-rotas | `PT-CICLO-VIDA-LISTA` | Resumo diário de planos urgentes e vazios (America/Sao_Paulo) | automação indicada com n8n | AUT-31 |
| O017 | novo · planos-rotas | `PT-CICLO-VIDA-LISTA` | Excluir vazios automaticamente | inadequada ou inviável atualmente | AUT-35 |
| O018 | novo · planos-rotas | `PT-RESULTADOS-RELATORIO` | Lembrete de lançamento de resultados após o fim do evento | automação indicada com n8n | AUT-83 |
| O019 | novo · planos-rotas | `PT-RESULTADOS-RELATORIO` | Redação narrativa do RT a partir dos números lançados | assistência por IA indicada | AUT-50 |
| O020 | novo · planos-rotas | `PT-ASSINATURA-CIRCULACAO` | Via assinada do plano e reconhecimento na leitura documental | melhor execução pelo próprio sistema | AUT-53 |
| O021 | novo · planos-rotas | `PT-ASSINATURA-CIRCULACAO` | Envio para assinatura via e-Protocolo | dependente de integração externa | AUT-122 |
| O022 | novo · planos-rotas | `PT-ASSINATURA-CIRCULACAO` | Aviso quando a unidade não tem assinante de planos | automação determinística suficiente | AUT-161 |
| O023 | novo · planos-rotas | `CAD-CATALOGO-ATIVIDADES` | Rascunho de meta/recurso para serviços sem complemento | assistência por IA indicada | AUT-86 |
| O024 | novo · planos-rotas | `CAD-CATALOGO-ATIVIDADES` | Detecção de possíveis duplicatas de serviço | automação determinística suficiente | AUT-85 |
| O025 | novo · planos-rotas | `CAD-FONTE-EXTERNA` | Sincronização agendada da fonte externa | dependente de integração externa | AUT-159 |
| O026 | novo · planos-rotas | `CAD-DADOS-UNIDADE-ASSINANTES` | Alertas de configuração (substituição vencendo, assinante de plano ausente, sede ausente) | automação indicada com n8n | AUT-161 |
| O027 | novo · planos-rotas | `ROT-CALCULO-ROTA-CACHE` | Provedor de rotas próprio/autorizado e porta em gestao/integracoes/rotas | dependente de integração externa | AUT-66 |
| O028 | novo · planos-rotas | `ROT-CALCULO-ROTA-CACHE` | Aquecimento do cache para a sede de cada unidade | automação determinística suficiente | AUT-73 |
| O029 | novo · planos-rotas | `ROT-CALCULO-ROTA-CACHE` | Limitar e assincronizar a API de rota | melhor execução pelo próprio sistema | AUT-74 |
| O030 | novo · planos-rotas | `ROT-CALCULO-ROTA-CACHE` | IA estimando distâncias/tempos | inadequada ou inviável atualmente | AUT-77 |
| O031 | novo · planos-rotas | `ROT-ITINERARIO-TRECHOS` | Ordem ótima de destinos por cálculo determinístico | automação determinística suficiente | AUT-67 |
| O032 | novo · planos-rotas | `ROT-ITINERARIO-TRECHOS` | IA converte pedido em texto livre em proposta estruturada de roteiro | assistência por IA indicada | AUT-76 |
| O033 | novo · planos-rotas | `ROT-ITINERARIO-TRECHOS` | Aviso de chegada incompatível com o início do atendimento | automação determinística suficiente | AUT-69 |
| O034 | novo · planos-rotas | `ROT-ITINERARIO-TRECHOS` | Registrar a fonte do km/tempo no trecho | melhor execução pelo próprio sistema | AUT-65 |
| O035 | novo · planos-rotas | `ROT-ROTEIRO-CADASTRADO` | Sugerir roteiro cadastrado compatível com os destinos da viagem | automação determinística suficiente | AUT-68 |
| O036 | novo · planos-rotas | `ROT-ROTEIRO-CADASTRADO` | Preservar km e tempos ao aplicar roteiro no ofício | melhor execução pelo próprio sistema | AUT-65 |
| O037 | novo · planos-rotas | `ROT-BATE-VOLTA` | Sugestão bate-volta x pernoite por tempo de estrada | automação determinística suficiente | AUT-70 |
| O038 | novo · planos-rotas | `ROT-BATE-VOLTA` | Aplicar veículo lento no bate-volta | melhor execução pelo próprio sistema | AUT-71 |
| O039 | novo · planos-rotas | `ROT-PLANEJADO-REALIZADO-KM` | Link de quilometragem da véspera alimentando o diário com a distância prevista | automação indicada com n8n | AUT-41 |
| O040 | novo · planos-rotas | `VIA-EVENTO-SEMENTE-LOTE` | Proposta consolidada em modo prévia (sem gravar) | dependente de desenvolvimento | AUT-14 |
| O041 | novo · planos-rotas | `VIA-EVENTO-SEMENTE-LOTE` | IA para lacunas de texto da proposta (motivo, justificativa) | assistência por IA indicada | AUT-81 |
| O042 | novo · planos-rotas | `VIA-EVENTO-SEMENTE-LOTE` | Disparar a geração da viagem automaticamente no deferimento | inadequada ou inviável atualmente | AUT-16 |
| O043 | novo · planos-rotas | `VIA-REPETIR-VIAGEM` | Recalcular rota ao trocar a cidade na repetição | melhor execução pelo próprio sistema | AUT-72 |
| O044 | novo · planos-rotas | `ROT-PROPOSTA-ROTEIRO-DO-EVENTO` | Roteiro padrão sede -> município do evento -> sede | automação determinística suficiente | AUT-64 |
| O045 | novo · planos-rotas | `ROT-PROPOSTA-ROTEIRO-DO-EVENTO` | IA para extrair programação/horários de anexos da solicitação | assistência por IA indicada | AUT-76 |
| O046 | novo · prestação | `PREST-NASCIMENTO` | Publicar evento de prestação criada e pré-criar diário | melhor execução pelo próprio sistema | AUT-100 |
| O047 | novo · prestação | `PREST-SOLICITACAO-LIBERACAO` | Evento `diarias_liberadas` para disparar a mensagem de saque | melhor execução pelo próprio sistema | AUT-37 (parte WhatsApp → AUT-10) |
| O048 | novo · prestação | `PREST-SOLICITACAO-LIBERACAO` | Importar nº da solicitação/liberação/prazo da fonte oficial | dependente de integração externa | AUT-125 |
| O049 | novo · prestação | `PREST-MENSAGEM-SAQUE` | Texto e regras do aviso como função de domínio testada | automação determinística suficiente | AUT-36 (parte WhatsApp → AUT-10) |
| O050 | novo · prestação | `PREST-MENSAGEM-SAQUE` | Envio automático da mensagem de saque via n8n + WhatsApp Business API | automação indicada com n8n | AUT-37 (parte WhatsApp → AUT-10) |
| O051 | novo · prestação | `PREST-AVISOS-PRAZOS` | Lembretes ao servidor (saque vencendo, prestação vencida) por n8n | automação indicada com n8n | AUT-38 (parte WhatsApp → AUT-10) |
| O052 | novo · prestação | `PREST-AVISOS-PRAZOS` | Aviso de véspera com link de km | melhor execução pelo próprio sistema | AUT-41 |
| O053 | novo · prestação | `PREST-DIARIO-PREENCHIMENTO` | Pré-preenchimento do km inicial pelo último km da viatura | automação determinística suficiente | AUT-42 |
| O054 | novo · prestação | `PREST-DIARIO-LINK-CAMPO` | Implementar o diário de campo por link (porte do desenho m096 com token em hash) | dependente de desenvolvimento | AUT-40 |
| O055 | novo · prestação | `PREST-DIARIO-LINK-CAMPO` | Envio do link na véspera (America/Sao_Paulo) pelo n8n | automação indicada com n8n | AUT-41 (parte WhatsApp → AUT-10) |
| O056 | novo · prestação | `PREST-VIAGEM-REALIZADA` | Sugerir horários realizados a partir dos lançamentos do diário de campo | automação determinística suficiente | AUT-43 |
| O057 | novo · prestação | `PREST-RT-PREENCHIMENTO` | Rascunho de RT por IA ancorado nos dados do sistema | assistência por IA indicada | AUT-50 |
| O058 | novo · prestação | `PREST-RT-PREENCHIMENTO` | Coletar o relato do servidor por formulário com link | dependente de desenvolvimento | AUT-48 |
| O059 | novo · prestação | `PREST-DOCS-GERACAO` | Congelar a versão enviada para assinatura (hash dos dados) | melhor execução pelo próprio sistema | AUT-46 |
| O060 | novo · prestação | `PREST-DOCS-ENVIO-ASSINATURA` | Pacote para assinatura enviado pelo n8n (sem assinar pelo sistema) | automação indicada com n8n | AUT-47 (parte WhatsApp → AUT-10) |
| O061 | novo · prestação | `PREST-DOCS-ENVIO-ASSINATURA` | Assinatura desenhada por link (como GV) | inadequada ou inviável atualmente | AUT-59 |
| O062 | novo · prestação | `DOC-IMPORTACAO-ENTRADA` | Endpoint de ingestão para automação (API de ferramentas) | dependente de desenvolvimento | AUT-52 (parte WhatsApp → AUT-10) |
| O063 | novo · prestação | `DOC-IMPORTACAO-ENTRADA` | Caixa de e-mail institucional → importador (n8n) | automação indicada com n8n | AUT-08 |
| O064 | novo · prestação | `DOC-IMPORTACAO-ENTRADA` | Persistir texto/OCR da parte | automação determinística suficiente | AUT-54 |
| O065 | novo · prestação | `DOC-IMPORTACAO-IDENTIFICACAO` | Casar comprovante pela janela de saque e pelo valor (regra determinística) | automação determinística suficiente | AUT-55 |
| O066 | novo · prestação | `DOC-IMPORTACAO-IDENTIFICACAO` | IA apenas como sugestão de tipo/destino na revisão | assistência por IA indicada | AUT-57 |
| O067 | novo · prestação | `DOC-IMPORTACAO-IDENTIFICACAO` | Corrigir direcionamento do DB com motorista de outro ofício | automação determinística suficiente | AUT-45 |
| O068 | novo · prestação | `DOC-VIA-ASSINADA-CONFERENCIA` | Estender a conferência para DB e RT assinados | automação determinística suficiente | AUT-53 |
| O069 | novo · prestação | `DOC-VIA-ASSINADA-CONFERENCIA` | Conferir a assinatura no original antes de separar | automação determinística suficiente | AUT-53 |
| O070 | novo · prestação | `PREST-ANEXOS` | Preencher valor, data e operação do comprovante na entrada | automação determinística suficiente | AUT-55 |
| O071 | novo · prestação | `PREST-LEITURA-CONFERENCIA` | Extração de comprovantes heterogêneos com IA local como fallback | assistência por IA indicada | AUT-58 |
| O072 | novo · prestação | `PREST-CARIMBO` | Posição automática pela linha do servidor no texto do PDF | automação determinística suficiente | AUT-56 |
| O073 | novo · prestação | `PREST-PENDENCIAS-FINALIZACAO` | Resumo diário de pendências por equipe (n8n) | automação indicada com n8n | AUT-39 |
| O074 | novo · prestação | `PREST-PENDENCIAS-FINALIZACAO` | Finalização automática | inadequada ou inviável atualmente | AUT-60 |
| O075 | novo · prestação | `PREST-PACOTE` | Anexar o pacote ao processo no eProtocolo | dependente de integração externa | AUT-122 |
| O076 | novo · prestação | `PREST-ENVIO-FINANCEIRO` | Acompanhar o andamento do protocolo de envio e sugerir aprovação/devolução | dependente de integração externa | AUT-121 |
| O077 | novo · prestação | `PREST-CONCLUSAO` | Eventos de ciclo da prestação | melhor execução pelo próprio sistema | AUT-100 |
| O078 | novo · prestação | `PREST-LISTA-ABAS-EXPORT` | Ferramentas de leitura para o assistente de dúvidas | melhor execução pelo próprio sistema | AUT-105 |
| O079 | novo · viagens-núcleo | `VIA-VIAGEM-DE-SOLICITACAO` | Semente completa da viagem a partir da solicitação | automação determinística suficiente | AUT-15 |
| O080 | novo · viagens-núcleo | `VIA-VIAGEM-DE-SOLICITACAO` | Evento de outbox 'viagens.viagem.gerada' com aviso externo pelo n8n | automação indicada com n8n | AUT-24 (parte WhatsApp → AUT-10) |
| O081 | novo · viagens-núcleo | `VIA-VIAGEM-DE-SOLICITACAO` | Geração automática da viagem no deferimento | dependente de desenvolvimento | AUT-16 |
| O082 | novo · viagens-núcleo | `VIA-VIAGEM-DADOS` | Proposta de dados da viagem extraída do e-mail/ofício anexado | assistência por IA indicada | AUT-76 |
| O083 | novo · viagens-núcleo | `VIA-SOLICITACAO-ANEXO` | Caixa postal institucional → anexo da viagem pelo n8n | automação indicada com n8n | AUT-08 |
| O084 | novo · viagens-núcleo | `VIA-ROTEIRO` | Roteiro sugerido a partir da viagem (horários calculados) | automação determinística suficiente | AUT-64 |
| O085 | novo · viagens-núcleo | `VIA-ROTEIRO` | Ordenação de múltiplos destinos por menor percurso | automação determinística suficiente | AUT-67 |
| O086 | novo · viagens-núcleo | `VIA-ROTEIRO` | Roteiro descrito em texto livre convertido em trechos | assistência por IA indicada | AUT-76 |
| O087 | novo · viagens-núcleo | `VIA-LOTE-QUEM-VAI` | Proposta consolidada (prévia sem gravar) antes de gerar | dependente de desenvolvimento | AUT-14 |
| O088 | novo · viagens-núcleo | `VIA-LOTE-QUEM-VAI` | Sugestões explicáveis de equipe, motorista e viatura | automação determinística suficiente | AUT-17 |
| O089 | novo · viagens-núcleo | `VIA-LOTE-QUEM-VAI` | Corrigir o evento dos termos gerados no lote | automação determinística suficiente | AUT-18 |
| O090 | novo · viagens-núcleo | `VIA-LOTE-QUEM-VAI` | IA escolher quem participa | inadequada ou inviável atualmente | AUT-33 |
| O091 | novo · viagens-núcleo | `VIA-OFICIO-RASCUNHO` | Preencher o ofício e o protocolo de origem do motorista externo | automação determinística suficiente | AUT-19 |
| O092 | novo · viagens-núcleo | `VIA-OFICIO-DIARIAS` | Alerta antecipado de tabela de diárias sem vigência | automação determinística suficiente | AUT-26 |
| O093 | novo · viagens-núcleo | `VIA-OFICIO-DIARIAS` | IA calcular ou ajustar diárias | inadequada ou inviável atualmente | AUT-34 |
| O094 | novo · viagens-núcleo | `VIA-OFICIO-PRAZO-JUSTIFICATIVA` | Data-limite para emitir sem justificativa, com lembretes | automação determinística suficiente | AUT-25 (parte WhatsApp → AUT-10) |
| O095 | novo · viagens-núcleo | `VIA-OFICIO-PRAZO-JUSTIFICATIVA` | Rascunho de justificativa por IA | assistência por IA indicada | AUT-81 |
| O096 | novo · viagens-núcleo | `VIA-OFICIO-PROTOCOLO` | Abrir protocolo pela API do eProtocolo com aprovação humana | dependente de integração externa | AUT-119 |
| O097 | novo · viagens-núcleo | `VIA-OFICIO-PROTOCOLO` | Consulta periódica da situação dos protocolos | automação indicada com n8n | AUT-120 |
| O098 | novo · viagens-núcleo | `VIA-OFICIO-EMISSAO` | Emissão automática | inadequada ou inviável atualmente | AUT-35 |
| O099 | novo · viagens-núcleo | `VIA-OFICIO-EMISSAO` | Relay de eventos para o n8n após o PDF ficar pronto | automação indicada com n8n | AUT-22 |
| O100 | novo · viagens-núcleo | `VIA-OFICIO-EMISSAO` | Aviso 'pronto para emitir' | automação determinística suficiente | AUT-25 |
| O101 | novo · viagens-núcleo | `VIA-DOCUMENTO-PDF` | Monitor da outbox e dos documentos em falha | automação determinística suficiente | AUT-110 |
| O102 | novo · viagens-núcleo | `VIA-OFICIO-CORRECAO` | Automatizar retificar, reabrir, cancelar ou excluir | inadequada ou inviável atualmente | AUT-35 |
| O103 | novo · viagens-núcleo | `VIA-OFICIO-CORRECAO` | Eventos de correção para avisar quem recebeu o documento | automação indicada com n8n | AUT-23 |
| O104 | novo · viagens-núcleo | `VIA-OFICIO-CORRECAO` | Lembrete de rascunhos vazios que prendem números | automação determinística suficiente | AUT-27 |
| O105 | novo · viagens-núcleo | `VIA-NUMERACAO` | Proibir que automações reservem número para propostas | melhor execução pelo próprio sistema | AUT-108 |
| O106 | novo · viagens-núcleo | `VIA-TERMOS` | Enviar a cada servidor o termo dele para assinatura | automação indicada com n8n | AUT-22 (parte WhatsApp → AUT-10) |
| O107 | novo · viagens-núcleo | `VIA-TERMOS` | Instantâneo do termo e da OS no envio para assinatura | dependente de desenvolvimento | AUT-21 |
| O108 | novo · viagens-núcleo | `VIA-OS` | Pré-atribuir funções da OS | automação determinística suficiente | AUT-20 |
| O109 | novo · viagens-núcleo | `VIA-OS` | IA redigir o texto da OS | inadequada ou inviável atualmente | AUT-87 |
| O110 | novo · viagens-núcleo | `VIA-PLANO` | Contextualização e considerações do plano com IA | assistência por IA indicada | AUT-80 |
| O111 | novo · viagens-núcleo | `VIA-PLANO` | Atividades e coordenadores sugeridos | automação determinística suficiente | AUT-15 |
| O112 | novo · viagens-núcleo | `VIA-CONFERENCIA` | Resumo diário de pendências das viagens próximas | automação indicada com n8n | AUT-31 (parte WhatsApp → AUT-10) |
| O113 | novo · viagens-núcleo | `VIA-CONFERENCIA` | Assistente que explica o que falta | assistência por IA indicada | AUT-89 |
| O114 | novo · viagens-núcleo | `VIA-VIAS-ASSINADAS` | Recebimento automático de devolvidos pelo n8n reaproveitando a importação | automação indicada com n8n | AUT-08 (parte WhatsApp → AUT-10) |
| O115 | novo · viagens-núcleo | `VIA-CONFLITOS-DISPONIBILIDADE` | Fonte de indisponibilidade (férias/afastamentos) | dependente de integração externa | AUT-32 |
| O116 | novo · viagens-núcleo | `VIA-CONFLITOS-DISPONIBILIDADE` | Alerta de conflito novo em ofício já emitido | automação indicada com n8n | AUT-29 |
| O117 | novo · viagens-núcleo | `VIA-VIAGEM-CICLO` | Cancelamento automático | inadequada ou inviável atualmente | AUT-35 |
| O118 | novo · viagens-núcleo | `VIA-VIAGEM-CICLO` | Aviso de cancelamento aos envolvidos | automação indicada com n8n | AUT-23 (parte WhatsApp → AUT-10) |
| O119 | novo · viagens-núcleo | `VIA-VESPERA-SAIDA` | Ferramenta 'saídas de amanhã' e envio do link pelo n8n | automação indicada com n8n | AUT-41 (parte WhatsApp → AUT-10) |
| O120 | novo · viagens-núcleo | `VIA-VESPERA-SAIDA` | Aviso interno 'sai amanhã' no sino | melhor execução pelo próprio sistema | AUT-30 |
| O121 | novo · viagens-núcleo | `VIA-PACOTES-ENVIO` | Envio de ofícios e documentos com aprovação e recibo | automação indicada com n8n | AUT-22 |
| O122 | novo · plataforma | `PLAT-OUTBOX-PUBLICACAO` | Catálogo de eventos de domínio finos para automação | dependente de desenvolvimento | AUT-100 |
| O123 | novo · plataforma | `PLAT-OUTBOX-PUBLICACAO` | Fan-out para consumidores externos sem mexer no assinante interno | dependente de desenvolvimento | AUT-101 |
| O124 | novo · plataforma | `PLAT-OUTBOX-WORKER` | Política de retentativa por tópico e comando de reprocessamento | automação determinística suficiente | AUT-102 |
| O125 | novo · plataforma | `PLAT-OUTBOX-WORKER` | Entrega HTTP curta e fora de escrita auditada | melhor execução pelo próprio sistema | AUT-101 |
| O126 | novo · plataforma | `PLAT-OUTBOX-WORKER` | Tela de saúde da outbox para o administrador | melhor execução pelo próprio sistema | AUT-103 |
| O127 | novo · plataforma | `PLAT-OUTBOX-WORKER` | IA decidindo retentativas ou tratando erros | inadequada ou inviável atualmente | AUT-127 |
| O128 | novo · plataforma | `PLAT-OUTBOX-ASSINANTES` | Ofício emitido dispara preparação do envio (com portão humano) | automação indicada com n8n | AUT-22 |
| O129 | novo · plataforma | `PLAT-OUTBOX-ASSINANTES` | Avisar o emissor quando o PDF falhar definitivamente | automação determinística suficiente | AUT-24 |
| O130 | novo · plataforma | `PLAT-NOTIF-SINO` | Espelhar avisos em canal externo (e-mail/WhatsApp) via n8n | automação indicada com n8n | AUT-06 (parte WhatsApp → AUT-10) |
| O131 | novo · plataforma | `PLAT-NOTIF-SINO` | Resumo diário por pessoa | automação indicada com n8n | AUT-07 |
| O132 | novo · plataforma | `PLAT-NOTIF-SINO` | IA escolhendo destinatários ou redigindo avisos | inadequada ou inviável atualmente | AUT-13 |
| O133 | novo · plataforma | `PLAT-NOTIF-EMAIL` | Ativar SMTP institucional com envio individual | dependente de integração externa | AUT-04 |
| O134 | novo · plataforma | `PLAT-NOTIF-EMAIL` | Pauta semanal enviada automaticamente | automação indicada com n8n | AUT-162 |
| O135 | novo · plataforma | `PLAT-ROTINAS-DIARIAS` | Rotina da véspera: link de quilometragem por trecho | dependente de desenvolvimento | AUT-41 (parte WhatsApp → AUT-10) |
| O136 | novo · plataforma | `PLAT-ROTINAS-DIARIAS` | Agendador independente do primeiro acesso | automação determinística suficiente | AUT-109 |
| O137 | novo · plataforma | `PLAT-ROTINAS-DIARIAS` | Mensagem de saque enviada ao servidor com confirmação do operador | automação indicada com n8n | AUT-37 (parte WhatsApp → AUT-10) |
| O138 | novo · plataforma | `PLAT-AUDITORIA` | Contexto de auditoria obrigatório nas chamadas de automação | melhor execução pelo próprio sistema | AUT-108 |
| O139 | novo · plataforma | `PLAT-AUDITORIA` | Alertas da cadeia e da operação roteados pelo n8n | automação indicada com n8n | AUT-111 (parte WhatsApp → AUT-10) |
| O140 | novo · plataforma | `PLAT-AUDITORIA` | IA para avaliar integridade da auditoria | inadequada ou inviável atualmente | AUT-127 |
| O141 | novo · plataforma | `ID-AUTENTICACAO-AUTORIZACAO` | Token de serviço com escopos e usuário representado | dependente de desenvolvimento | AUT-104 |
| O142 | novo · plataforma | `ID-AUTENTICACAO-AUTORIZACAO` | Identidade externa do servidor (telefone verificado) | dependente de desenvolvimento | AUT-02 (parte WhatsApp → AUT-10) |
| O143 | novo · plataforma | `ID-AUTENTICACAO-AUTORIZACAO` | SSO pela Central de Segurança do PR | dependente de integração externa | AUT-115 |
| O144 | novo · plataforma | `PLAT-AMBIENTES-SALVAGUARDAS` | Trava de risco por ambiente no registro de ferramentas | melhor execução pelo próprio sistema | AUT-108 |
| O145 | novo · plataforma | `PLAT-AMBIENTES-SALVAGUARDAS` | n8n e credenciais separados por ambiente | automação indicada com n8n | AUT-99 |
| O146 | novo · plataforma | `INT-EPROTOCOLO` | Acompanhamento automático de andamento dos protocolos | dependente de integração externa | AUT-120 |
| O147 | novo · plataforma | `INT-EPROTOCOLO` | Abrir protocolo via outbox atrás do portão de aprovação | dependente de desenvolvimento | AUT-119 |
| O148 | novo · plataforma | `INT-EPROTOCOLO` | Automação de navegador no portal do eProtocolo | inadequada ou inviável atualmente | AUT-128 |
| O149 | novo · plataforma | `INT-CENTRAL-VIAGENS` | Painel 'dados para a Central de Viagens' com copiar | automação determinística suficiente | AUT-124 |
| O150 | novo · plataforma | `INT-CENTRAL-VIAGENS` | Integração oficial com a Central | dependente de integração externa | AUT-125 |
| O151 | novo · plataforma | `INT-CENTRAL-VIAGENS` | Robô de navegador na Central | inadequada ou inviável atualmente | AUT-128 |
| O152 | novo · plataforma | `INT-ROTAS` | Provedor de rotas de produção (OSRM próprio ou ORS com chave) | dependente de integração externa | AUT-66 |
| O153 | novo · plataforma | `INT-ROTAS` | Ordem sugerida dos destinos de um roteiro | automação determinística suficiente | AUT-67 |
| O154 | novo · plataforma | `INT-ROTAS` | IA calculando rotas ou distâncias | inadequada ou inviável atualmente | AUT-77 |
| O155 | novo · plataforma | `API-FERRAMENTAS` | Fase A: ferramentas de leitura com política e auditoria | dependente de desenvolvimento | AUT-105 |
| O156 | novo · plataforma | `API-FERRAMENTAS` | Portão de aprovação humana (fases B/C) | dependente de desenvolvimento | AUT-106 |
| O157 | novo · plataforma | `API-FERRAMENTAS` | Fachada MCP para n8n e assistente | dependente de desenvolvimento | AUT-107 |
| O158 | novo · plataforma | `API-FERRAMENTAS` | Assistente de dúvidas dos servidores | assistência por IA indicada | AUT-88 (parte WhatsApp → AUT-10) |
| O159 | novo · plataforma | `API-JSON-INTERNA` | Usar os endpoints de tela a partir do n8n (cookie/sessão) | inadequada ou inviável atualmente | AUT-126 |
| O160 | novo · plataforma | `API-JSON-INTERNA` | Extrair a lógica das views JSON para queries reutilizáveis | melhor execução pelo próprio sistema | AUT-105 |
| O161 | novo · plataforma | `PAINEL-AGENDA` | Pauta semanal e escala do dia seguinte enviadas automaticamente | automação indicada com n8n | AUT-162 |
| O162 | novo · plataforma | `PAINEL-AGENDA` | Aviso diário de conflitos de pessoa ou viatura nos próximos 7 dias | automação determinística suficiente | AUT-29 |
| O163 | novo · plataforma | `PAINEL-ICS` | Usar o feed ICS pessoal como fonte do n8n | inadequada ou inviável atualmente | AUT-126 |
| O164 | novo · plataforma | `PAINEL-ICS` | Feed de equipe/unidade | melhor execução pelo próprio sistema | AUT-163 |
| O165 | novo · plataforma | `PAINEL-RELATORIO-CONSOLIDADO` | Envio mensal automático da planilha consolidada | automação indicada com n8n | AUT-164 |
| O166 | novo · plataforma | `PAINEL-RELATORIO-CONSOLIDADO` | Comentário analítico do mês (rascunho) | assistência por IA indicada | AUT-94 |
| O167 | novo · plataforma | `PLAT-BUSCA-CONFLITOS` | Ferramentas busca.global e conflitos.verificar para n8n e assistente | dependente de desenvolvimento | AUT-105 |
| O168 | novo · plataforma | `PLAT-LEITURA-EMAIL` | Captura automática da caixa institucional para rascunho | automação indicada com n8n | AUT-08 |
| O169 | novo · plataforma | `PLAT-LEITURA-EMAIL` | Fallback de extração por IA quando o parser falha | assistência por IA indicada | AUT-92 |
| O170 | novo · plataforma | `VIA-IMPORTACAO-FILA` | Documentos devolvidos por e-mail/WhatsApp entram direto na fila existente | automação indicada com n8n | AUT-08 (parte WhatsApp → AUT-10) |
| O171 | novo · plataforma | `VIA-IMPORTACAO-FILA` | Monitorar, pausar e reiniciar o importador nos scripts da VPS | automação determinística suficiente | AUT-110 |
| O172 | novo · plataforma | `VIA-IMPORTACAO-FILA` | Eventos de conclusão e revisão da importação | melhor execução pelo próprio sistema | AUT-100 |
| O173 | novo · plataforma | `OPS-DEPLOY` | Implantar o n8n isolado na VPS | melhor execução pelo próprio sistema | AUT-99 |
| O174 | novo · plataforma | `OPS-DEPLOY` | Deploy ou operação de infraestrutura pelo n8n ou pela IA | inadequada ou inviável atualmente | AUT-127 |
| O175 | novo · plataforma | `OPS-BACKUP-RESTAURACAO` | Incluir o n8n no backup e versionar os workflows | automação determinística suficiente | AUT-99 |
| O176 | novo · plataforma | `OPS-BACKUP-RESTAURACAO` | Relatório de backup e restauração pelo canal de alertas | automação indicada com n8n | AUT-111 |
| O177 | novo · plataforma | `OPS-MONITOR-SAUDE` | Saúde estendida das filas e rotinas | automação determinística suficiente | AUT-110 |
| O178 | novo · plataforma | `OPS-MONITOR-SAUDE` | Roteamento e escalonamento de alertas no n8n | automação indicada com n8n | AUT-111 |
| O179 | novo · plataforma | `OPS-MONITOR-SAUDE` | IA diagnosticando incidentes automaticamente | inadequada ou inviável atualmente | AUT-127 |
| O180 | novo · outros módulos | `EVT-SOLICITACAO-CADASTRO` | Rascunho de solicitação a partir de e-mail/protocolo recebido | dependente de desenvolvimento | AUT-132 |
| O181 | novo · outros módulos | `EVT-SOLICITACAO-CADASTRO` | Contato do solicitante estruturado | melhor execução pelo próprio sistema | AUT-138 |
| O182 | novo · outros módulos | `EVT-SOLICITACAO-CADASTRO` | Sugestão de serviços e equipes pelo histórico | automação determinística suficiente | AUT-139 |
| O183 | novo · outros módulos | `EVT-ENVIO-DG` | Eventos de domínio da solicitação na outbox | melhor execução pelo próprio sistema | AUT-100 |
| O184 | novo · outros módulos | `EVT-ENVIO-DG` | Aviso externo à DG de nova solicitação | automação indicada com n8n | AUT-136 (parte WhatsApp → AUT-10) |
| O185 | novo · outros módulos | `EVT-ENVIO-DG` | Aviso a Viagens e Coffee quando solicitação deferida é alterada | automação determinística suficiente | AUT-134 |
| O186 | novo · outros módulos | `EVT-DESPACHO-DG` | Resumo de despacho determinístico | automação determinística suficiente | AUT-137 |
| O187 | novo · outros módulos | `EVT-DESPACHO-DG` | Digest diário da fila de despacho | automação indicada com n8n | AUT-136 |
| O188 | novo · outros módulos | `EVT-DESPACHO-DG` | Decidir o despacho por WhatsApp/resposta de e-mail | inadequada ou inviável atualmente | AUT-165 |
| O189 | novo · outros módulos | `EVT-DESPACHO-DG` | IA para redigir a observação do despacho | inadequada ou inviável atualmente | AUT-13 |
| O190 | novo · outros módulos | `EVT-ENCERRAMENTO` | Propagar cancelamento à OS de coffee de origem | melhor execução pelo próprio sistema | AUT-134 |
| O191 | novo · outros módulos | `EVT-ENCERRAMENTO` | Confirmação pós-evento por canal externo | automação indicada com n8n | AUT-141 |
| O192 | novo · outros módulos | `EVT-GERAR-VIAGEM` | Proposta consolidada do evento (selecionar evento, informar quem vai, conferir) | melhor execução pelo próprio sistema | AUT-14 |
| O193 | novo · outros módulos | `EVT-GERAR-VIAGEM` | Geração automática da viagem no deferimento | melhor execução pelo próprio sistema | AUT-16 |
| O194 | novo · outros módulos | `EVT-GERAR-VIAGEM` | IA para textos do Plano de Trabalho a partir da solicitação | assistência por IA indicada | AUT-80 |
| O195 | novo · outros módulos | `EVT-LEMBRETES` | Lembretes também pela outbox para entrega externa | automação indicada com n8n | AUT-06 (parte WhatsApp → AUT-10) |
| O196 | novo · outros módulos | `EVT-LEMBRETES` | Destinatários da DG pela permissão | automação determinística suficiente | AUT-140 |
| O197 | novo · outros módulos | `EVT-LEMBRETES` | Lembrete de rascunho esquecido | automação determinística suficiente | AUT-140 |
| O198 | novo · outros módulos | `EVT-CATALOGOS-MODELO` | Vincular unidade móvel à viatura e equipe aos servidores | dependente de desenvolvimento | AUT-135 |
| O199 | novo · outros módulos | `PAL-PEDIDO-REGISTRO` | Formulário público de pedido com acompanhamento | melhor execução pelo próprio sistema | AUT-143 |
| O200 | novo · outros módulos | `PAL-PEDIDO-REGISTRO` | Entrada de pedidos por e-mail/WhatsApp | automação indicada com n8n | AUT-08 (parte WhatsApp → AUT-10) |
| O201 | novo · outros módulos | `PAL-PEDIDO-REGISTRO` | Consulta do protocolo no eProtocolo | dependente de integração externa | AUT-120 |
| O202 | novo · outros módulos | `PAL-ANDAMENTO-RESPOSTA` | Envio real da resposta com status de entrega | automação indicada com n8n | AUT-144 (parte WhatsApp → AUT-10) |
| O203 | novo · outros módulos | `PAL-ANDAMENTO-RESPOSTA` | Lembretes da palestra (palestrante e equipe) | automação determinística suficiente | AUT-145 |
| O204 | novo · outros módulos | `PAL-ANDAMENTO-RESPOSTA` | IA para redigir respostas | inadequada ou inviável atualmente | AUT-13 |
| O205 | novo · outros módulos | `PAL-ENCAMINHAR-DG` | Reflexo automático da decisão da DG na palestra | automação determinística suficiente | AUT-134 |
| O206 | novo · outros módulos | `PAL-ENCAMINHAR-DG` | Cancelamento coordenado | automação determinística suficiente | AUT-134 |
| O207 | novo · outros módulos | `IMP-ATENDIMENTO` | Entrada automática dos pedidos de jornalistas | automação indicada com n8n | AUT-08 |
| O208 | novo · outros módulos | `IMP-ATENDIMENTO` | Alerta de deadline | automação determinística suficiente | AUT-147 |
| O209 | novo · outros módulos | `IMP-ATENDIMENTO` | Rascunho de resposta à imprensa por IA | assistência por IA indicada | AUT-95 |
| O210 | novo · outros módulos | `PUB-PAUTA` | Entrada de releases por e-mail | automação indicada com n8n | AUT-08 |
| O211 | novo · outros módulos | `PUB-PAUTA` | Detecção da matéria publicada | automação indicada com n8n | AUT-148 |
| O212 | novo · outros módulos | `ASCOM-CADASTROS-APOIO` | Vincular integrantes da ASCOM a usuários | dependente de desenvolvimento | AUT-146 |
| O213 | novo · outros módulos | `ASCOM-CADASTROS-APOIO` | Sugestão de correspondência UnidadeResponsavel ↔ Unidade | automação determinística suficiente | AUT-149 |
| O214 | novo · outros módulos | `CB-PEDIDO-OS` | Monitor de remarcação e cancelamento da origem | automação determinística suficiente | AUT-134 |
| O215 | novo · outros módulos | `CB-PEDIDO-OS` | Pedido de coffee recebido por e-mail entra pela caixa de entrada | automação indicada com n8n | AUT-08 |
| O216 | novo · outros módulos | `CB-FINANCEIRO-MARCOS` | Digest diário 'O que fazer hoje' da equipe | automação indicada com n8n | AUT-150 |
| O217 | novo · outros módulos | `CB-FINANCEIRO-MARCOS` | Sugestão de marcos pelo andamento do processo no eProtocolo | dependente de integração externa | AUT-121 |
| O218 | novo · outros módulos | `CB-FINANCEIRO-MARCOS` | Registrar marcos financeiros por IA | inadequada ou inviável atualmente | AUT-167 |
| O219 | novo · outros módulos | `CB-DOCUMENTOS-VIAS` | Conferência da assinatura nas vias do coffee | melhor execução pelo próprio sistema | AUT-151 |
| O220 | novo · outros módulos | `CB-DOCUMENTOS-VIAS` | Retorno do documento assinado pela importação documental | melhor execução pelo próprio sistema | AUT-151 |
| O221 | novo · outros módulos | `CB-PROTOCOLO-PAGAMENTO` | Abrir o protocolo de pagamento no eProtocolo | dependente de integração externa | AUT-119 |
| O222 | novo · outros módulos | `CB-PROTOCOLO-PAGAMENTO` | Separar 'baixar pacote' de 'registrar atesto' | automação determinística suficiente | AUT-152 |
| O223 | novo · outros módulos | `CB-LEITURA-PDFS` | Destinos do Coffee na importação documental | melhor execução pelo próprio sistema | AUT-151 |
| O224 | novo · outros módulos | `CB-LEITURA-PDFS` | Extração por IA para layouts desconhecidos de NFS-e | assistência por IA indicada | AUT-58 |
| O225 | novo · outros módulos | `CB-CERTIDOES` | Aviso de vencimento e pedido de renovação | automação determinística suficiente | AUT-153 |
| O226 | novo · outros módulos | `CB-CERTIDOES` | Emitir certidões automaticamente nos portais | inadequada ou inviável atualmente | AUT-166 |
| O227 | novo · outros módulos | `CB-CERTIDOES` | Certidão enviada pelo fornecedor por e-mail | automação indicada com n8n | AUT-08 |
| O228 | novo · outros módulos | `CB-ENTREGAS` | Confirmação de recebimento pelo responsável no local | automação indicada com n8n | AUT-156 (parte WhatsApp → AUT-10) |
| O229 | novo · outros módulos | `CB-ENTREGAS` | Notificação formal de ocorrência ao fornecedor | automação indicada com n8n | AUT-154 |
| O230 | novo · outros módulos | `CB-PAINEL-CONTRATO-VIRADA` | Alerta semanal de saldo e vigência com o relatório anexo | automação indicada com n8n | AUT-157 |
| O231 | novo · outros módulos | `CB-PAINEL-CONTRATO-VIRADA` | Lembrete de virada de exercício | automação determinística suficiente | AUT-158 |
| O232 | novo · outros módulos | `CB-COMUNICACAO-FORNECEDOR` | Enviar OS e OB ao fornecedor com prévia editável | melhor execução pelo próprio sistema | AUT-154 |
| O233 | novo · outros módulos | `CB-COMUNICACAO-FORNECEDOR` | Link seguro do fornecedor | melhor execução pelo próprio sistema | AUT-155 |
| O234 | novo · outros módulos | `CAD-SERVIDORES-VIATURAS-CATALOGOS` | Contato e consentimento do servidor para automações | dependente de desenvolvimento | AUT-02 (parte WhatsApp → AUT-10) |
| O235 | novo · outros módulos | `CAD-SERVIDORES-VIATURAS-CATALOGOS` | Aviso de cadastro incompleto em viagem próxima | automação determinística suficiente | AUT-28 |
| O236 | novo · outros módulos | `CAD-FONTE-DEDICADA` | Sincronização da fonte via n8n + ferramenta | dependente de integração externa | AUT-159 |
| O237 | novo · outros módulos | `CAD-FONTE-DEDICADA` | Reconhecimento assistido dos vínculos iniciais | automação determinística suficiente | AUT-160 |
| O238 | novo · outros módulos | `CAD-FONTE-DEDICADA` | Casamento de identidades por IA | inadequada ou inviável atualmente | AUT-168 |
| O239 | novo · outros módulos | `CAD-USUARIOS-PAPEIS` | Convite e recuperação de senha por e-mail | dependente de integração externa | AUT-113 |
| O240 | novo · outros módulos | `CAD-USUARIOS-PAPEIS` | Revisão periódica de acessos | automação determinística suficiente | AUT-114 |
| O241 | novo · outros módulos | `CAD-UNIDADE-ASSINANTES-DIARIAS-TEXTOS` | Aviso de substituição de assinante começando/terminando | automação determinística suficiente | AUT-161 |
| O242 | novo · outros módulos | `CAD-UNIDADE-ASSINANTES-DIARIAS-TEXTOS` | Atualizar a tabela de diárias automaticamente a partir da norma | inadequada ou inviável atualmente | AUT-169 |
| O243 | novo · outros módulos | `AGENDA-ESCALA-PAUTA-ICS` | Pauta semanal automática | automação indicada com n8n | AUT-162 |
| O244 | novo · outros módulos | `AGENDA-ESCALA-PAUTA-ICS` | Agenda do dia/véspera por pessoa | dependente de desenvolvimento | AUT-09 |
| O245 | novo · outros módulos | `AGENDA-ESCALA-PAUTA-ICS` | Conflitos como alerta proativo | automação determinística suficiente | AUT-29 |
| O246 | novo · outros módulos | `NOTIFICACOES-ROTINAS` | Canal externo de entrega via outbox → n8n | automação indicada com n8n | AUT-06 (parte WhatsApp → AUT-10) |
| O247 | novo · outros módulos | `NOTIFICACOES-ROTINAS` | E-mail individual por destinatário | automação determinística suficiente | AUT-05 |
| O248 | novo · outros módulos | `NOTIFICACOES-ROTINAS` | Reexecutar só as rotinas que falharam | automação determinística suficiente | AUT-109 |
| O249 | novo · outros módulos | `RELATORIOS-PAINEIS-EXPORTACOES` | Relatório mensal automático | automação indicada com n8n | AUT-164 |
| O250 | novo · outros módulos | `RELATORIOS-PAINEIS-EXPORTACOES` | Nota executiva do mês por IA | assistência por IA indicada | AUT-94 |
| O251 | novo · outros módulos | `ENTRADA-DEMANDAS-CANAIS` | Caixa de entrada única com conversão assistida | dependente de desenvolvimento | AUT-132 |
| O252 | novo · outros módulos | `ENTRADA-DEMANDAS-CANAIS` | Triagem por IA quando as regras não decidem | assistência por IA indicada | AUT-93 |
| O253 | novo · outros módulos | `ENTRADA-DEMANDAS-CANAIS` | WhatsApp Business como canal de entrada | dependente de integração externa | AUT-10 |
| O254 | ref. GV | `GV-OFICIO-WIZARD` | Proposta consolidada de ofício a partir do evento + participantes | melhor execução pelo próprio sistema | AUT-14 |
| O255 | ref. GV | `GV-OFICIO-WIZARD` | Alerta diário de ofícios em rascunho com saída próxima | automação indicada com n8n | AUT-31 (parte WhatsApp → AUT-10) |
| O256 | ref. GV | `GV-OFICIO-WIZARD` | Sugestão de 'motivo' a partir do convite/ofício solicitante | assistência por IA indicada | AUT-81 |
| O257 | ref. GV | `GV-ROTEIRO-DIARIAS` | Montagem do roteiro a partir do texto do convite (extração assistida) | assistência por IA indicada | AUT-76 |
| O258 | ref. GV | `GV-ROTEIRO-DIARIAS` | Recalcular em lote rotas 'desatualizadas' e avisar a divergência de diárias | automação determinística suficiente | AUT-72 |
| O259 | ref. GV | `GV-JUSTIFICATIVA` | Rascunho de justificativa sugerido por IA a partir do contexto do evento | assistência por IA indicada | AUT-81 |
| O260 | ref. GV | `GV-JUSTIFICATIVA` | Aviso automático quando a justificativa obrigatória estiver pendente | automação indicada com n8n | AUT-31 |
| O261 | ref. GV | `GV-TERMOS` | Envio do termo ao servidor e recebimento do assinado pela importação documental | dependente de desenvolvimento | AUT-22 (parte WhatsApp → AUT-10) |
| O262 | ref. GV | `GV-TERMOS` | Painel de termos sem versão assinada por ofício próximo da saída | automação determinística suficiente | AUT-31 |
| O263 | ref. GV | `GV-OS` | OS gerada deterministicamente junto com a proposta consolidada | melhor execução pelo próprio sistema | AUT-14 |
| O264 | ref. GV | `GV-PLANO-TRABALHO` | IA para enriquecer a contextualização e as considerações a partir da solicitação | assistência por IA indicada | AUT-80 |
| O265 | ref. GV | `GV-PLANO-TRABALHO` | Metas e atividades seguem determinísticas (catálogo/presets) | inadequada ou inviável atualmente | AUT-87 |
| O266 | ref. GV | `GV-EVENTO` | Entrada de convites e solicitações por canal monitorado -> importação documental | dependente de integração externa | AUT-08 (parte WhatsApp → AUT-10) |
| O267 | ref. GV | `GV-EVENTO` | Sugestão de mudança de status do evento por datas | automação determinística suficiente | AUT-142 |
| O268 | ref. GV | `GV-DOC-GERACAO` | Gerar o pacote documental na emissão via outbox | melhor execução pelo próprio sistema | AUT-21 |
| O269 | ref. GV | `GV-DOC-GERACAO` | n8n avisa quando o pacote fica pronto ou falha | automação indicada com n8n | AUT-24 |
| O270 | ref. GV | `GV-DOC-ASSINADO-MANUAL` | Recebimento de documentos devolvidos reaproveitando a importação documental | dependente de desenvolvimento | AUT-52 |
| O271 | ref. GV | `GV-DOC-ASSINADO-MANUAL` | Aplicar antivírus também no upload de versão assinada | melhor execução pelo próprio sistema | AUT-112 |
| O272 | ref. GV | `GV-DRIVE-ESPELHO` | Restabelecer o consumidor e higienizar a fila 'drive' no GV (correção operacional) | melhor execução pelo próprio sistema | AUT-116 |
| O273 | ref. GV | `GV-DRIVE-ESPELHO` | Monitor de filas, workers e espelho com alerta | automação indicada com n8n | AUT-111 |
| O274 | ref. GV | `GV-DRIVE-ESPELHO` | No sistema novo: espelho Drive como assinante da outbox com estado durável por item | dependente de desenvolvimento | AUT-117 |
| O275 | ref. GV | `GV-DRIVE-ESPELHO` | Levar a organização de pastas/nomes para o n8n | inadequada ou inviável atualmente | AUT-130 |
| O276 | ref. GV | `GV-PREST-ABERTURA` | Checklist de prestação aberto no retorno da viagem | automação indicada com n8n | AUT-38 |
| O277 | ref. GV | `GV-PREST-DIARIO` | Página pública de quilometragem por trecho (token) | dependente de desenvolvimento | AUT-40 |
| O278 | ref. GV | `GV-PREST-DIARIO` | Envio do link de KM na véspera (America/Sao_Paulo) | automação indicada com n8n | AUT-41 (parte WhatsApp → AUT-10) |
| O279 | ref. GV | `GV-PREST-DIARIO` | Validação determinística de continuidade de KM e prontidão do DB | automação determinística suficiente | AUT-44 |
| O280 | ref. GV | `GV-PREST-DIARIO` | Corrigir o signatário do DB para o motorista efetivo do diário | melhor execução pelo próprio sistema | AUT-45 |
| O281 | ref. GV | `GV-PREST-RT` | Rascunho dos textos do RT a partir do Plano de Trabalho e do relato | assistência por IA indicada | AUT-50 |
| O282 | ref. GV | `GV-PREST-RT` | Feriados no cálculo de dias úteis da data do RT | automação determinística suficiente | AUT-51 |
| O283 | ref. GV | `GV-PREST-ASSINATURA` | Envio automático do link de assinatura e lembrete antes de expirar | automação indicada com n8n | AUT-47 (parte WhatsApp → AUT-10) |
| O284 | ref. GV | `GV-PREST-ASSINATURA` | Aviso ao operador quando a assinatura é concluída | automação indicada com n8n | AUT-46 |
| O285 | ref. GV | `GV-PREST-DOCUMENTOS-CARIMBO` | Ofício assinado e despacho recebidos via importação/eProtocolo com carimbo automático | dependente de integração externa | AUT-123 |
| O286 | ref. GV | `GV-PREST-DOCUMENTOS-CARIMBO` | Carimbo continua determinístico (sem IA) | inadequada ou inviável atualmente | AUT-63 |
| O287 | ref. GV | `GV-PREST-AVISO-DIARIAS` | Mover a montagem da mensagem para um serviço backend com registro de envio | melhor execução pelo próprio sistema | AUT-36 |
| O288 | ref. GV | `GV-PREST-AVISO-DIARIAS` | Disparo automático no dia da liberação e lembrete antes do prazo de saque | automação indicada com n8n | AUT-37 (parte WhatsApp → AUT-10) |
| O289 | ref. GV | `GV-PREST-CONSOLIDADO` | Digest semanal de prestações paradas por pendência | automação indicada com n8n | AUT-39 |
| O290 | ref. GV | `GV-PREST-CONSOLIDADO` | Envio do pacote final ao destino institucional | dependente de integração externa | AUT-122 |
| O291 | ref. GV | `GV-EPROTOCOLO` | Consulta periódica de situação/pendências dos protocolos ativos | dependente de integração externa | AUT-120 |
| O292 | ref. GV | `GV-EPROTOCOLO` | Abertura e tramitação de protocolo só com aprovação humana | melhor execução pelo próprio sistema | AUT-119 |
| O293 | ref. GV | `GV-EPROTOCOLO` | IA decidindo tramitação/abertura | inadequada ou inviável atualmente | AUT-129 |
| O294 | ref. GV | `GV-UPLOAD-AV` | Pipeline único de entrada de arquivos para tela, importação e n8n | melhor execução pelo próprio sistema | AUT-112 (parte WhatsApp → AUT-10) |
| O295 | ref. GV | `GV-CIFRAGEM-SEGREDOS` | Minimização de dados em automações e IA | melhor execução pelo próprio sistema | AUT-108 |
| O296 | ref. GV | `GV-OBS-BACKUP-AUDITORIA` | Vigia operacional no n8n (health, métricas, filas, backup) | automação indicada com n8n | AUT-111 |
| O297 | ref. GV | `GV-NOTIFICACOES` | Central de notificações por outbox + n8n como entregador | dependente de integração externa | AUT-01 (parte WhatsApp → AUT-10) |
| O298 | ref. GV | `GV-ASSISTENTE-DUVIDAS` | Assistente que responde 'qual a situação da minha viagem/diária' e dúvidas de procedimento | assistência por IA indicada | AUT-88 (parte WhatsApp → AUT-10) |
| O299 | ref. EV | `EV-IA-ASSISTENTE` | Assistente de dúvidas dos servidores só com ferramentas de leitura | assistência por IA indicada | AUT-88 (parte WhatsApp → AUT-10) |
| O300 | ref. EV | `EV-IA-ASSISTENTE` | Reinstalar o app 'assistente' do EV ou copiar o seu código | inadequada ou inviável atualmente | AUT-90 |
| O301 | ref. EV | `EV-WHATSAPP-CANAL` | Canal WhatsApp oficial (Cloud API) via n8n, só com autorização formal | dependente de integração externa | AUT-10 |
| O302 | ref. EV | `EV-WHATSAPP-CANAL` | Usar biblioteca não oficial de WhatsApp (automação do WhatsApp Web) | inadequada ou inviável atualmente | AUT-11 |
| O303 | ref. EV | `EV-WHATSAPP-CANAL` | Limpar os resíduos do canal no servidor do EV (não instalar o .service) | automação determinística suficiente | AUT-12 |
| O304 | ref. EV | `EV-LEITURA-PEDIDO` | Caixa postal institucional → fila de 'pedidos recebidos' para conferência | automação indicada com n8n | AUT-08 |
| O305 | ref. EV | `EV-LEITURA-PEDIDO` | Extração por IA apenas como fallback de campos de confiança baixa | assistência por IA indicada | AUT-92 |
| O306 | ref. EV | `EV-LEITURA-PEDIDO` | Portar a bateria-gabarito como harness de avaliação do NEXT | automação determinística suficiente | AUT-91 |
| O307 | ref. EV | `EV-TRIAGEM-MODULO` | Triagem automática da fila de entrada com confirmação humana | automação determinística suficiente | AUT-133 |
| O308 | ref. EV | `EV-TRIAGEM-MODULO` | Classificação por IA só quando nenhum sinal pontuou | assistência por IA indicada | AUT-93 |
| O309 | ref. EV | `EV-PEDIDO-PUBLICO` | Confirmação e acompanhamento por e-mail ao solicitante | automação indicada com n8n | AUT-143 |
| O310 | ref. EV | `EV-RESPOSTA-PADRAO` | Envio pelo sistema por e-mail institucional após confirmação | automação indicada com n8n | AUT-144 |
| O311 | ref. EV | `EV-SOLICITACAO-DESPACHO` | Disparo garantido das rotinas por agendador externo | automação indicada com n8n | AUT-109 |
| O312 | ref. EV | `EV-SOLICITACAO-DESPACHO` | Despacho da DG por automação | inadequada ou inviável atualmente | AUT-165 |
| O313 | ref. EV | `EV-DEFERIMENTO-GERA-VIAGEM` | Geração da viagem como assinante da outbox | melhor execução pelo próprio sistema | AUT-16 |
| O314 | ref. EV | `EV-PROPOSTA-DOCUMENTOS` | Proposta consolidada determinística no NEXT (equipe informada → pacote em rascunho) | melhor execução pelo próprio sistema | AUT-14 |
| O315 | ref. EV | `EV-PROPOSTA-DOCUMENTOS` | Redação por IA dos textos do Plano de Trabalho (objetivo, justificativa, descrição) | assistência por IA indicada | AUT-80 |
| O316 | ref. EV | `EV-PROPOSTA-DOCUMENTOS` | IA escolher a equipe ou a viatura | inadequada ou inviável atualmente | AUT-33 |
| O317 | ref. EV | `EV-ROTA-DISTANCIA` | IA para calcular rotas, km ou tempo | inadequada ou inviável atualmente | AUT-77 |
| O318 | ref. EV | `EV-ROTA-DISTANCIA` | IA para descrever o roteiro em linguagem natural (texto do plano/ofício) | assistência por IA indicada | AUT-75 |
| O319 | ref. EV | `EV-DIARIO-LINK-KM` | Portar o link de campo (km por trecho) para o NEXT, com token em hash | dependente de desenvolvimento | AUT-40 |
| O320 | ref. EV | `EV-DIARIO-LINK-KM` | Envio automático do link na véspera (America/Sao_Paulo) | automação indicada com n8n | AUT-41 (parte WhatsApp → AUT-10) |
| O321 | ref. EV | `EV-DIARIO-LINK-KM` | Leitura automática do km por foto do hodômetro | inadequada ou inviável atualmente | AUT-62 |
| O322 | ref. EV | `EV-AVISOS-PRESTACAO` | Lembretes diretos ao servidor (saque e prestação) por canal institucional | automação indicada com n8n | AUT-38 (parte WhatsApp → AUT-10) |
| O323 | ref. EV | `EV-MENSAGEM-LIBERACAO` | Envio da mensagem de liberação pelo canal institucional com confirmação em lote | automação indicada com n8n | AUT-37 (parte WhatsApp → AUT-10) |
| O324 | ref. EV | `EV-RT-SUGESTAO` | Rascunho do RT por IA a partir de dados estruturados e anotações do servidor | assistência por IA indicada | AUT-50 |
| O325 | ref. EV | `EV-RT-SUGESTAO` | Corrigir a regra determinística para não afirmar 'sem intercorrências' por padrão | automação determinística suficiente | AUT-49 |
| O326 | ref. EV | `EV-DB-RT-ASSINATURA` | Envio do DB/RT para assinatura com acompanhamento | automação indicada com n8n | AUT-47 |
| O327 | ref. EV | `EV-DB-RT-ASSINATURA` | Recebimento do assinado por caixa postal reutilizando a importação | automação indicada com n8n | AUT-08 |
| O328 | ref. EV | `EV-IMPORTACAO-PROCESSO` | Entrada automática de processos e comprovantes na fila de importação | automação indicada com n8n | AUT-123 |
| O329 | ref. EV | `EV-IMPORTACAO-PROCESSO` | IA para decidir o destino dos documentos | inadequada ou inviável atualmente | AUT-61 |
| O330 | ref. EV | `EV-COFFEE-FORNECEDOR-PAGAMENTO` | Transporte de e-mails com status e retentativa | automação indicada com n8n | AUT-06 |
| O331 | ref. EV | `EV-EPROTOCOLO` | Consulta de andamento agendada e aviso de chegada ao setor | dependente de integração externa | AUT-120 |
| O332 | ref. EV | `EV-EPROTOCOLO` | Abertura de protocolo oficial somente com aprovação humana | dependente de integração externa | AUT-119 |
| O333 | ref. EV | `EV-ENVIO-FINANCEIRO` | Protocolar o pacote da prestação no eProtocolo com aprovação | dependente de integração externa | AUT-122 |
| O334 | ref. EV | `EV-ROTINAS-DIARIAS` | Agendamento externo garantido das rotinas | automação indicada com n8n | AUT-109 |
| O335 | ref. EV | `EV-AGENDA-ICS-PAUTA` | Manter determinístico (sem IA/n8n) | melhor execução pelo próprio sistema | AUT-162 |
| O336 | ref. EV | `EV-VINCULO-USUARIO-SERVIDOR` | Identidade do servidor para canais e assistente | melhor execução pelo próprio sistema | AUT-02 |
| O337 | ref. EV | `EV-MIGRACAO-GV` | Automatizar carga contínua GV→sistema novo por n8n/IA | inadequada ou inviável atualmente | AUT-131 |
