# Inventário de processos — automação com n8n e IA (Fase 2)

Levantamento de **17/10/2026**. Descreve o que existe hoje, processo a processo, no sistema novo e nas
duas referências em produção. Não propõe desenho: a base técnica está em [arquitetura.md](arquitetura.md)
e nos [contratos](contratos/); os desenhos detalhados estão nos [fluxos](fluxos/); a ordem de entrega
está no [plano de implantação](plano-implantacao.md).

## 1. Metodologia

### 1.1 O que foi lido

Sete leituras de código, cada uma com: processos (id, estado, evidências `caminho:linha`, estados e
gatilhos, pontos de integração, trabalho manual, lacunas, oportunidades classificadas), integrações,
achados e dúvidas. As leituras são estáticas: o código foi lido, não executado contra produção.

| Leitura | Sistema | Escopo | Processos |
|---|---|---|---:|
| `viagens-nucleo` | novo | Módulo Viagens: evento → viagem → roteiro → ofício; equipe, viaturas, motoristas e conflitos; emissão, numeração, versões e PDFs; termos, justificativas, OS, plano; hub da Viagem | 22 |
| `planos-rotas` | novo | Planos de trabalho, catálogo compartilhado de atividades/serviços, dados da unidade e assinantes, rotas, roteiros e itinerário | 22 |
| `prestacao` | novo | Prestação de contas, Diário de Bordo, Relatório Técnico, anexos, vias assinadas, importação documental (comparada a GV e EV) | 21 |
| `plataforma` | novo | Outbox, worker, auditoria, notificações, rotinas, identidade, eProtocolo, Central de Viagens, rotas, painel, API/JSON, implantação, backup, monitoramento | 23 |
| `outros-modulos` | novo | Eventos, Coffee Break, Imprensa, Palestras, Publicações, Cadastros, Painel (com `docs/product` e `docs/migration`) | 30 |
| `gv-implantado` | referência em produção | Gerenciador de Viagens completo, incluindo núcleo documental, prestação, eProtocolo, espelho Google Drive, Celery/Redis | 23 |
| `ev-implantado` | referência em produção | Eventos Sociais implantado, comparado ao histórico Git do EV e ao sistema novo | 23 |

**Versões examinadas**

| Sistema | Árvore | Prefixo nas evidências |
|---|---|---|
| Sistema novo (`pcpr-gestao-next`) | Árvore de trabalho local em 17/10/2026: HEAD `2b6c1fe` (16/10/2026) **com alterações não commitadas** (entre elas `gestao/cadastros/fontes.py`, migrações `cadastros/0018` e `eventos/0008`, ADRs 0044 e 0045, mudanças em `gestao/viagens/planos.py`). O PREVIEW publicado vem do `main` e não contém essas alterações | `gestao/`, `config/`, `deploy/`, `docs/`; `NEXT/` quando citado pela leitura do EV |
| GV — Gerenciador de Viagens | Commit `ded9b648`, igual ao `main` do GitHub | `gv/` (`ref/gv/` nas leituras do sistema novo) |
| EV — Eventos Sociais | Árvore implantada = commit `92f57bda` + 8 arquivos fora do Git | `EVI/` (`ref/ev-implantado/` nas leituras do novo); `EVG@<commit>` = histórico Git do EV |

Outros insumos da mesma data: pesquisa em fontes oficiais (WhatsApp/Meta, n8n, Hostinger, IA, mapas,
e-mail; consultada em 17/10/2026); medição de tempos do PREVIEW publicado; medição de capacidade da VPS
([capacidade-vps.md](../ops/mudanca-hospedagem/capacidade-vps.md)) e decisão de hospedagem do n8n
([hospedagem-n8n.md](../ops/mudanca-hospedagem/hospedagem-n8n.md)).

### 1.2 Como ler as tabelas

- **Estado** — `existente`: o código que executa o processo está na árvore lida (para as referências,
  na árvore implantada); `parcial`: parte existe e o resto é manual, simulado ou sem ponto de entrada;
  `inexistente`: nada no código; `planejado`: só em ADR ou documentação.
- **†** verificação parcial: o código existe, mas a configuração efetiva (variáveis de ambiente, timers,
  chave de provedor), o uso real em produção ou a precisão com dados reais não puderam ser confirmados
  pela leitura.
- **‡** depende de alterações não commitadas do sistema novo (fora do PREVIEW).
- **Evidência principal** — a primeira evidência registrada pela leitura (em um caso trocada pela mais
  representativa). As listas completas ficaram no material de trabalho da auditoria, fora do repositório.
- **Fluxo 10-x / 11-1** — o processo é tratado em detalhe no fluxo correspondente:
  [10-2 envio de documentos](fluxos/10-2-envio-de-documentos.md),
  [10-3 prestação e mensagem de saque](fluxos/10-3-prestacao-e-mensagem-de-saque.md),
  [10-4 link de KM na véspera](fluxos/10-4-link-de-km-na-vespera.md),
  [10-5 DB e RT para assinatura](fluxos/10-5-db-e-rt-para-assinatura.md),
  [10-6 recebimento de documentos](fluxos/10-6-recebimento-de-documentos.md),
  [11-1 rotas e roteiros](fluxos/11-1-rotas-e-roteiros.md).
- **Oport.** — quantidade de oportunidades que a leitura registrou para o processo, por classe:
  **N** automação indicada com n8n · **IA** assistência por IA indicada · **D** automação
  determinística suficiente · **S** melhor execução pelo próprio sistema · **Dev** dependente de
  desenvolvimento · **Ext** dependente de integração externa · **X** inadequada ou inviável atualmente.
  É a classificação bruta das leituras; a consolidação, a maturidade (1 a 5) e a prioridade ficam na
  matriz de oportunidades desta fase (`matriz-oportunidades.md`).
- Há sobreposição deliberada entre leituras (o mesmo processo visto pelo hub da Viagem e pelo módulo,
  por exemplo `VIA-PLANO` e `PT-*`). Os 164 registros foram mantidos; a observação indica o par.

### 1.3 Limites

- Nenhum teste foi executado para este inventário e nada foi gravado em nenhum sistema.
- Arquivos de ambiente e configuração interna dos servidores de produção não foram lidos. Por isso o
  ambiente efetivo de integrações das referências (eProtocolo, chave de rotas, SMTP) aparece como
  "não verificável pelo código".
- O repositório é público: detalhes de configuração de segurança dos sistemas em produção foram
  omitidos de propósito, inclusive nas tabelas de processos e de integrações.
- O sistema novo tinha trabalho em andamento no disco; a análise reflete a árvore de 17/10/2026, não só
  o commit `2b6c1fe`.

### 1.4 Fatos confirmados que valem para todo o inventário

1. **WhatsApp — plataforma oficial bloqueada; prioridade do usuário.** A política oficial do WhatsApp Business
   (<https://whatsappbusiness.com/policy/>, seção de uso governamental, atualizada em 23/09/2026,
   consultada em 17/10/2026) lista "Law Enforcement Agencies" (autoridades policiais) entre os usuários
   **proibidos** do WhatsApp Business Platform, sem exceção nem processo de aprovação. Provedores
   (BSPs) também recusam polícia (ex.: 360dialog,
   <https://docs.360dialog.com/docs/resources/government-agencies>, consultada em 17/10/2026).
   Não há integração WhatsApp ativa em produção: no EV a rota do webhook está só comentada e um
   `.service` fora do Git chama um comando inexistente; os três sistemas usam links click-to-chat
   (`wa.me`/`api.whatsapp.com`) abertos à mão pelo operador. Toda oportunidade cujo canal seja o
   WhatsApp Business Platform é tratada como **inadequada ou inviável atualmente**. 47 das 337
   oportunidades citam WhatsApp em algum campo; as que dependem dele como canal precisam ser
   reavaliadas com outro canal (a coluna "Oport." mostra a classe original da leitura). Em 17/10/2026 o
   usuário definiu o WhatsApp como **prioridade**: o [plano](plano-implantacao.md) abre as frentes WA-1
   (envio assistido com registro, maturidade 2), WA-2 (consulta formal à Meta, 4) e WA-3 (integração
   oficial pronta e desligada, 5 para ativar) — itens AUT-172 a AUT-174 da
   [matriz](matriz-oportunidades.md). A plataforma oficial continua bloqueada até autorização escrita.
2. **eProtocolo é o sistema oficial.** O Decreto estadual PR 7.304/2021
   (<https://www.administracao.pr.gov.br/sites/default/arquivos_restritos/files/documento/2021-04/decreto_7304_-_2021_-_eprotocolo_-_com_anexos_0.pdf>,
   consultado em 17/10/2026) define o eProtocolo como sistema oficial de gestão de documentos e veda
   sistemas paralelos de controle e tramitação. **A confirmar:** automações de distribuição e
   recebimento devem complementar a tramitação oficial, não substituí-la.
3. **Servidores viajantes não são usuários do sistema novo.** `Servidor` não tem e-mail, tem telefone
   único, e o vínculo usuário↔servidor está pendente. No GV em produção há assinatura eletrônica
   simples de RT e DB por link público (token cifrado + hash, CPF, expiração) e documento por link
   temporário de 15 min; a assinatura digital de ofícios é feita no eProtocolo (decisão registrada no GV).
4. **Outbox do sistema novo.** Um assinante por tópico; o worker segura a transação durante o
   assinante (HTTP externo deve ir para um worker de entregas com lease); retentativa efetiva de
   ~21 min; não há tela de falhas.

## 2. Números

| | Sistema novo | Referências (GV + EV) | Total |
|---|---:|---:|---:|
| Processos registrados | 118 | 46 | 164 |
| — existente | 93 | 37 | 130 |
| — parcial | 18 | 6 | 24 |
| — inexistente | 6 | 3 | 9 |
| — planejado | 1 | 0 | 1 |
| — com verificação parcial (†) | 7 | 9 | 16 |
| — dependentes de alterações não commitadas (‡) | 6 | — | 6 |

| Classe de oportunidade (como registrada nas leituras) | Código | Sistema novo | Referências | Total |
|---|---|---:|---:|---:|
| automação indicada com n8n | N | 54 | 23 | 77 |
| assistência por IA indicada | IA | 22 | 12 | 34 |
| automação determinística suficiente | D | 64 | 9 | 73 |
| melhor execução pelo próprio sistema | S | 37 | 14 | 51 |
| dependente de desenvolvimento | Dev | 25 | 5 | 30 |
| dependente de integração externa | Ext | 19 | 9 | 28 |
| inadequada ou inviável atualmente | X | 32 | 12 | 44 |
| **Total** | | 253 | 84 | 337 |

- **Integrações:** 111 registros nas sete leituras, consolidados em 46 linhas na seção 5.
- **Achados:** 148 registros, consolidados em 21 achados transversais na seção 6.
- **Dúvidas:** 93 registros, consolidadas em 41 dúvidas na seção 7 (algumas já respondidas
  pelos fatos da seção 1.4).
- Leitura rápida: no sistema novo, 93 de 118 processos (79 %) já existem em código, mas **nenhum**
  pode ser acionado hoje por máquina (seção 6, achado 1). Na coluna "Trabalho manual hoje", o que mais
  se repete é **comunicação com pessoas fora do sistema** (avisar, enviar, cobrar, receber) e
  **digitação de dados que vêm de fora** (km, nº da solicitação, datas de liberação, documentos
  devolvidos) — exatamente o terreno das automações de borda descritas na arquitetura.

## 3. Processos do sistema novo

### 3.1 Viagens — núcleo (`viagens-nucleo`) — 22 processos

Evento → viagem → roteiro → ofício; equipe, viaturas e motoristas; emissão, numeração, versões e PDFs; termos, justificativas, OS e plano vistos pelo hub da Viagem.

| ID | Processo | Estado | Evidência principal | Trabalho manual hoje | Observação | Oport. |
|---|---|---|---|---|---|---|
| VIA-VIAGEM-DE-SOLICITACAO | Gerar a Viagem a partir de solicitação de evento deferida | existente | `gestao/viagens/de_eventos.py:121-155` | Clicar em gerar, escolher a unidade e depois redigitar na viagem, no lote e no plano o que a solicitação já sabe: serviços, unidade móvel, motorista, quantidade de servidores e equipes. | Ponte por botão; propaga só título, período, destino, motivo e tipos. Aviso de viagem gerada sai em on_commit, sem evento na outbox. Ver também EVT-GERAR-VIAGEM. | N1 D1 Dev1 |
| VIA-VIAGEM-DADOS | Criar a viagem e preencher os dados (etapa 1) | existente | `gestao/viagens/viagem.py:170-190` | Digitar tipos, motivo, período e destinos lendo o e-mail ou ofício do solicitante. Criar cada documento. | Sem horário do evento na viagem. IA poderia propor os dados a partir do e-mail/ofício anexado, sempre como proposta conferida. | IA1 |
| VIA-SOLICITACAO-ANEXO | Anexar à viagem a solicitação (e-mail/ofício do solicitante) | existente | `gestao/viagens/viagem_solicitacao.py:32-81` | Salvar o e-mail como .eml/.msg ou PDF e enviar pela tela. | Entrada só por upload em sessão; texto do anexo não é lido. | N1 |
| VIA-ROTEIRO | Montar o roteiro (trechos, rota, tempos e diárias estimadas) | existente | `gestao/viagens/services.py:1337-1387` | Escolher a ordem dos destinos e a data/hora de saída de cada trecho, ajustar o tempo adicional e conferir o mapa. | Ordem e horários manuais; a coerência não compara os trechos copiados para os ofícios com o roteiro. Fluxo 11-1. | IA1 D2 |
| VIA-LOTE-QUEM-VAI | Informar quem vai: gerar documentos em lote da viagem | existente | `gestao/viagens/viagem_lote.py:44-73` | Escolher pessoa a pessoa, motorista e viatura de cada ofício sem ver conflitos nem diárias antes. Depois abrir cada documento e completar: protocolo, justificativa, funções da OS, coordenadores do plano. | Não verifica conflitos nem disponibilidade; reserva números na hora; termos do lote saem com o evento padrão 'PCPR na Comunidade' (provável defeito). | D2 Dev1 X1 |
| VIA-OFICIO-RASCUNHO | Cadastrar e editar o ofício (dados, equipe, motorista, transporte, trechos, texto) | existente | `gestao/viagens/services.py:154-174` | Preencher tudo. No motorista externo, digitar o ofício e o protocolo de origem procurando no outro ofício. | Motorista externo exige localizar à mão o ofício de origem; ponto sensível desde o incidente do 'externo fantasma' (Lote H). | D1 |
| VIA-OFICIO-DIARIAS | Calcular as diárias | existente | `gestao/viagens/dominio/diarias.py:1-80` | Nenhum no cálculo. Cadastrar a vigência da tabela quando falta. | Cálculo determinístico no domínio (manter fora da IA); falta de vigência só aparece ao abrir o ofício. | D1 X1 |
| VIA-OFICIO-PRAZO-JUSTIFICATIVA | Avaliar antecedência, assunto e justificativa | existente | `gestao/viagens/dominio/prazos.py:55-67` | Perceber o prazo, escolher um texto pronto e redigir a justificativa. | Regra determinística; a data de emissão muda o conteúdo (pode virar Convalidação). Lembrete 'emitir até' é determinístico e de alto valor. | IA1 D1 |
| VIA-OFICIO-PROTOCOLO | Protocolo do eProtocolo do ofício | parcial | `gestao/viagens/models.py:175-190` | Abrir o protocolo no eProtocolo copiando os campos e digitar o número no ofício. | Protocolo digitado e exigido para emitir; a porta do eProtocolo existe mas nenhum fluxo a chama. Automação complementa o eProtocolo, não o substitui (Decreto 7.304/2021). | N1 Ext1 |
| VIA-OFICIO-EMISSAO | Revisar e emitir o ofício (passagem para FINAL) | existente | `gestao/viagens/services.py:1035-1078` | Revisar e clicar em emitir. Depois baixar o PDF e encaminhar por fora (assinatura, protocolo, destinatário, servidores). | Único documento com estado final imutável (PDF/A + SHA-256). viagens.oficio.emitido só grava log. Fluxo 10-2. | N1 D1 X1 |
| VIA-DOCUMENTO-PDF | Gerar o PDF/A de forma assíncrona e regenerar falhas | existente | `gestao/viagens/assinantes.py:15-43` | Perceber que o PDF não saiu e clicar em gerar novamente. | PDF/A assíncrono pela outbox; o Documento fica FALHOU já na 1ª falha transitória e ninguém é avisado. Fluxo 10-2. | D1 |
| VIA-OFICIO-CORRECAO | Corrigir e encerrar o ofício: retificar, reabrir, cancelar, reativar, arquivar, marcador, excluir | existente | `gestao/viagens/services.py:1082-1290` | Tudo manual; avisar por fora quem já recebeu o documento. | Retificar não exige motivo e revoga vias assinadas: ação irreversível, só com aprovação. Nenhum evento avisa quem já recebeu. Fluxo 10-2. | N1 D1 X1 |
| VIA-NUMERACAO | Numeração anual (ofício, OS, plano) | existente | `gestao/viagens/services.py:90-149` | Nenhum na reserva; limpar rascunhos esquecidos. | Número reservado no rascunho: automação não pode criar rascunhos para propor (gera lacunas). | S1 |
| VIA-TERMOS | Termos de autorização (individual, genérico, por viatura) | existente | `gestao/viagens/termos.py:278-396` | Baixar cada termo, mandar a cada servidor, receber assinado e anexar um a um. | Termo sem estado final; a prova do assinado é a impressão dos dados na via assinada. Fluxo 10-2. | N1 Dev1 |
| VIA-OS | Ordem de Serviço (OS) | existente | `gestao/viagens/ordens.py:99-161` | Escolher a função de cada servidor e a hora do briefing; finalizar; encaminhar para assinatura. | OS 'finalizada' continua editável; o motorista não recebe a função 'Condução' automaticamente. | D1 X1 |
| VIA-PLANO | Plano de Trabalho | existente | `gestao/viagens/planos.py:134-171` | Coordenadores com gênero, programas, ajuste de atividades e textos. | Mesmo processo visto pelo hub da Viagem; detalhe em PT-*. Textos genéricos; ignora os serviços pedidos. | IA1 D1 |
| VIA-CONFERENCIA | Quadro de prontidão, coerência e trilha da viagem (conferir) | existente | `gestao/viagens/viagem_conferencia.py:81-208` | Abrir cada viagem para saber o que falta. | Quadro de prontidão é a base natural de um resumo diário; 'aplicar' grava OS, termo e plano fora dos services. | N1 IA1 |
| VIA-VIAS-ASSINADAS | Receber e conferir as vias assinadas (ofício, justificativa, termo, OS) | existente | `gestao/viagens/assinados.py:76-90` | Receber o PDF por e-mail/WhatsApp, baixar e enviar pela tela ou importação. | Conferência por pypdf (ADR 0022) só gera aviso; nenhum evento quando a assinatura chega. Fluxo 10-6. | N1 |
| VIA-CONFLITOS-DISPONIBILIDADE | Conflitos de agenda e disponibilidade de servidores, motoristas e viaturas | parcial | `gestao/plataforma/conflitos.py:1-80` | Ler avisos ofício a ofício; checar férias por fora. | Conflito é aviso não bloqueante; não existe fonte de férias, afastamentos ou escalas. | N1 Ext1 |
| VIA-VIAGEM-CICLO | Cancelar em cascata, reativar, excluir e repetir a viagem | existente | `gestao/viagens/viagem.py:332-419` | Tudo manual; avisar os envolvidos por fora. | Cancelamento em cascata existe; avisar envolvidos é manual e sem evento. | N1 X1 |
| VIA-VESPERA-SAIDA | Gatilho da véspera da saída (base do link de quilometragem do Diário de Bordo) | inexistente | `gestao/viagens/avisos.py:1-14` | O motorista preenche o km depois, à mão ou no papel; o operador digita no diário. | Deixado de fora de propósito (sem PWA de campo). Rotinas das 05:40 não servem para 'véspera às 17h'. Fluxo 10-4. | N1 S1 |
| VIA-PACOTES-ENVIO | Baixar e enviar os documentos da viagem | parcial | `gestao/viagens/urls.py:179-187` | Baixar o ZIP e anexar num e-mail ou no eProtocolo. | Download só em sessão; sem registro de quem recebeu o quê e quando. Fluxo 10-2. | N1 |

### 3.2 Planos de trabalho, cadastros compartilhados e rotas (`planos-rotas`) — 22 processos

Plano de trabalho, catálogo único de atividades/serviços, dados da unidade e assinantes, cálculo de rotas, roteiros e itinerário.

| ID | Processo | Estado | Evidência principal | Trabalho manual hoje | Observação | Oport. |
|---|---|---|---|---|---|---|
| PT-CRIACAO-NUMERACAO | Criação do plano de trabalho e numeração anual | existente | `gestao/viagens/planos.py:99-117` | Operador decide quando criar o plano, de qual ofício/viagem, e confere número. | Quatro caminhos de criação; número anual reservado no rascunho. O plano da viagem não recebe os serviços da solicitação. | D1 Dev1 |
| PT-HERANCA-OFICIOS | Herança de dados dos ofícios para o plano | existente | `gestao/viagens/planos.py:134-169` | Conferir se o que veio do ofício está certo; atualizar o plano à mão quando o ofício muda depois. | Cópia única: mudanças posteriores no ofício não chegam ao plano nem geram aviso. | S1 |
| PT-TEXTOS-AUTOMATICOS | Montagem dos textos do plano (contextualização, coordenação, considerações, atividades, metas, recursos) | existente | `gestao/viagens/dominio/plano_trabalho.py:145-199` | Reescrever a contextualização/considerações quando o texto fixo ('PCPR na Comunidade', populações ribeirinhas) não se aplica; conferir gênero dos coordenadores. | Texto institucional fixo para todo programa; candidato a rascunho por IA ancorado em dados, sempre conferido. | IA1 D1 X1 |
| PT-ATIVIDADES-CONJUNTOS | Seleção de atividades e conjuntos (presets) no plano | existente | `gestao/viagens/planos.py:301-314` | Marcar/desmarcar atividades conforme o evento. | Sugerir o conjunto pelo tipo de evento ou pelos serviços pedidos é regra determinística. | D1 |
| PT-DIARIAS | Cálculo das diárias do plano (por evento) | existente | `gestao/viagens/dominio/plano_trabalho.py:326-350` | Informar saída/chegada quando não vieram do ofício; conferir valor. | Só o destino principal entra (decisão 'a confirmar'); sem conciliação com as diárias dos ofícios. | S1 X1 |
| PT-MULTIEVENTO | Eventos adicionais do plano | existente | `gestao/viagens/planos.py:579-646` | Digitar cada evento em janela própria. | Eventos adicionais digitados; não nascem de outra solicitação ou ofício. | Dev1 |
| PT-PENDENCIAS-FINALIZAR-GERAR | Pendências, finalizar e gerar documento (PDF/DOCX) | existente | `gestao/viagens/dominio/plano_trabalho.py:249-297` | Conferir a minuta, finalizar, baixar PDF e encaminhar para assinatura fora do sistema. | Plano GERADO continua editável e o PDF é refeito dos dados atuais: sem snapshot não há envio automatizado seguro. | N1 S1 X1 |
| PT-EDITOR-TEXTO | Edição do texto do documento no visualizador (versões) | existente | `gestao/viagens/planos.py:882-946` | Ajustes finos de redação direto no documento. | Texto editado congela regiões sem fusão; dados atualizados depois não chegam ao documento editado. | S1 X1 |
| PT-CICLO-VIDA-LISTA | Lista, atenção, cancelar, reativar, excluir, duplicar | existente | `gestao/viagens/views_planos.py:48-145` | Entrar na lista para descobrir urgências. | Urgências só para quem abre a lista; candidato a resumo diário. | N1 X1 |
| PT-RESULTADOS-RELATORIO | Resultados por atividade, relatório final e sugestão para o RT | existente | `gestao/viagens/resultados.py:53-115` | Coletar números com a equipe e digitar; redigir o RT. | Sem lembrete pós-evento; os números alimentam o RT. | N1 IA1 |
| PT-ASSINATURA-CIRCULACAO | Assinante, envio para assinatura e retorno do plano assinado | parcial | `gestao/cadastros/services.py:307-325` | Baixar PDF, enviar por fora, guardar o assinado fora do sistema. | Sem via assinada do plano e sem tipo 'PLANO DE TRABALHO' na importação; circulação toda fora do sistema. | D1 S1 Ext1 |
| CAD-CATALOGO-ATIVIDADES | Catálogo único de atividades e serviços (Plano e Eventos) | existente ‡ | `gestao/cadastros/models.py:568-595` | Completar meta/recurso de serviços criados em Eventos; evitar homônimos. | Catálogo único Serviço = Atividade (ADR 0044) em alterações não commitadas; serviço sem meta degrada o plano. | IA1 D1 |
| CAD-FONTE-EXTERNA | Espelho local de fonte externa de cadastros (identidade e reconciliação) | parcial ‡ | `gestao/cadastros/fontes.py:19-31` | Cadastro manual local. | Só os testes chamam vincular/atualizar; fonte externa não definida. Ver também CAD-FONTE-DEDICADA. | Ext1 |
| CAD-DADOS-UNIDADE-ASSINANTES | Dados da unidade, assinantes, substituições e padrões do plano | existente ‡ | `gestao/cadastros/models.py:382-459` | Lembrar de cadastrar/encerrar substituições em férias/afastamentos. | Sem aviso de substituição vencendo ou de assinante ausente; sem sede não há diárias nem rotas. | N1 |
| ROT-CALCULO-ROTA-CACHE | Cálculo de distância/tempo entre municípios (provedor, cache, estimativa) | existente † | `gestao/viagens/rotas.py:32-36` | Ajustar tempos quando a sugestão não reflete a realidade. | HTTP direto fora de gestao/integracoes (contraria ADR 0019); API síncrona, sem limitação de taxa. Fluxo 11-1. | D1 S1 Ext1 X1 |
| ROT-ITINERARIO-TRECHOS | Itinerário do ofício/roteiro: trechos com chegada calculada | existente | `gestao/viagens/itinerario.py:54-111` | Escolher ordem dos destinos e horários de saída; conferir chegada e diárias. | A fonte do km (rota real × estimativa) não fica registrada no trecho. Fluxo 11-1. | IA1 D2 S1 |
| ROT-ROTEIRO-CADASTRADO | Roteiros cadastrados (modelo de percurso) e uso em ofícios | existente | `gestao/viagens/views_roteiros.py:134-204` | Procurar um roteiro parecido na lista e aplicá-lo. | 'Usar roteiro' perde km e tempos até o próximo autosave; roteiro é cópia (ADR 0015). Fluxo 11-1. | D1 S1 |
| ROT-BATE-VOLTA | Bate-volta: blocos de dias com ida e volta no mesmo dia | existente | `gestao/viagens/dominio/bate_volta.py:22-75` | Decidir entre bate-volta e pernoite. | Veículo lento não aplicado; critério bate-volta × pernoite depende de norma a confirmar. | D1 S1 |
| ROT-PLANEJADO-REALIZADO-KM | Planejado x realizado: trechos realizados e km previsto no Diário de Bordo | existente | `gestao/viagens/realizado.py:1-8` | Digitar km por trecho a partir do hodômetro. | Km estimado (linha reta × 1,3) ou vazio gera avisos falsos na conferência de 20% do hodômetro. Fluxo 10-4. | N1 |
| VIA-EVENTO-SEMENTE-LOTE | Do evento deferido à viagem e aos documentos em lote (proposta consolidada) | parcial | `gestao/viagens/de_eventos.py:1-16` | Montar o roteiro do zero (sede -> município do evento -> sede, horários), escolher equipes e viaturas, depois conferir cada documento separadamente. | Falta o roteiro como elo da 'proposta consolidada', que precisa ser prévia sem gravar. Fluxo 11-1. | IA1 Dev1 X1 |
| VIA-REPETIR-VIAGEM | Repetir viagem em outra data (roteiros e plano deslocados) | existente | `gestao/viagens/viagem_repetir.py:1-8` | Conferir horários quando a cidade muda. | Com cidade trocada mantém as durações antigas e perde km; o bate-volta não é copiado. | S1 |
| ROT-PROPOSTA-ROTEIRO-DO-EVENTO | Proposta automática de roteiro/itinerário a partir do evento | inexistente | `gestao/viagens/de_eventos.py:6-9` | Digitar sede, destino e horários de ida/volta. | A solicitação não tem horário nem programação estruturados. Desenho no Fluxo 11-1. | IA1 D1 |

### 3.3 Prestação de contas e recebimento de documentos (`prestacao`) — 21 processos

Prestação, Diário de Bordo, Relatório Técnico, anexos, vias assinadas e importação documental.

| ID | Processo | Estado | Evidência principal | Trabalho manual hoje | Observação | Oport. |
|---|---|---|---|---|---|---|
| PREST-NASCIMENTO | Nascimento e sincronização da prestação na emissão do ofício | existente | `gestao/viagens/services.py:1073-1077` | Nenhum para criar; a equipe de viagens precisa abrir cada folha para que o diário e o RT existam. | Prestação criada na emissão do ofício; diário e RT só nascem na primeira visita; sem evento 'prestação criada'. | S1 |
| PREST-SOLICITACAO-LIBERACAO | Registro do nº da solicitação, liberação das diárias e prazo de saque | existente | `gestao/viagens/prestacao.py:267-284` | Digitar três campos por servidor; avisar o servidor fora do sistema. | Dados de fonte externa não modelada; 'liberada' significa data informada, não pagamento confirmado. Fluxo 10-3. | S1 Ext1 |
| PREST-MENSAGEM-SAQUE | Mensagem de saque (aviso de liberação de diárias ao servidor por WhatsApp) | parcial | `gestao/viagens/views_prestacao.py:176-191` | Abrir menu, clicar no link e enviar pelo WhatsApp do próprio operador, um servidor por vez. | Só link wa.me, texto diferente do GV, sem validações nem registro de envio. WhatsApp Business bloqueado: alternativa no Fluxo 10-3. | N1 D1 |
| PREST-AVISOS-PRAZOS | Rotina diária de avisos da prestação (saque, prestação vencida, documentos, chegada) | existente | `gestao/viagens/avisos.py:1-13` | O operador lê o sino e cobra o servidor por fora. | Avisos só a operadores internos; sem feriados; a chegada usa os trechos do ofício, não os realizados. Fluxo 10-3. | N1 S1 |
| PREST-DIARIO-PREENCHIMENTO | Preenchimento do Diário de Bordo (km, abastecimento, motorista e viatura) | existente | `gestao/viagens/diario.py:61-112` | Obter os km do motorista (papel, WhatsApp, memória) e digitar trecho a trecho. | Km chega por fora (papel, mensagem, memória) e é digitado. Fluxo 10-4. | D1 |
| PREST-DIARIO-LINK-CAMPO | Link de quilometragem para o motorista (diário de campo, véspera) | inexistente | `docs/product/workflows.md:158-159` | Inexistente no sistema; os km chegam por fora. | Excluído conscientemente (decisoes.md:205); existe na referência EV; o padrão de token em hash já existe no novo. Fluxo 10-4. | N1 Dev1 |
| PREST-VIAGEM-REALIZADA | Viagem realizada: ajuste de horários e recálculo de diárias | existente | `gestao/viagens/realizado.py:61-122` | Digitar data/hora real de cada trecho. | Horários reais digitados; poderiam vir do lançamento de campo. Fluxo 10-4. | D1 |
| PREST-RT-PREENCHIMENTO | Relatório Técnico: dados exigidos e redação | existente | `gestao/viagens/models.py:1578-1602` | Escrever ou ajustar 5 textos, conferir o custeio e informar a diária recebida (valor do saque). | Conclusão e medidas genéricas por regra; rascunho por IA só ancorado em dados e conferido. Fluxo 10-5. | IA1 Dev1 |
| PREST-DOCS-GERACAO | Geração dos documentos DB (PDF/XLSX) e RT (PDF/DOCX por servidor) | existente | `gestao/viagens/prestacao_texto.py:1-24` | Baixar PDF/DOCX e enviar ao servidor por fora. | Sem snapshot nem hash do que foi enviado para assinatura. Fluxo 10-5. | S1 |
| PREST-DOCS-ENVIO-ASSINATURA | Envio do DB e do RT para assinatura e retorno | inexistente | `gestao/viagens/avisos.py:82-86` | Baixar, enviar por WhatsApp/e-mail, cobrar a devolução, receber e anexar. | Sem estado de envio, destinatário, canal ou prazo; tipo de assinatura válida a confirmar. Fluxo 10-5. | N1 X1 |
| DOC-IMPORTACAO-ENTRADA | Recebimento de documentos: envio, fila persistente, conversão e OCR | existente | `gestao/viagens/views_importacao.py:32-56` | Baixar anexos de e-mail/WhatsApp/eProtocolo e arrastar para a fitinha. | Fila com conversão e OCR locais (ADR 0041); entrada só por sessão; texto/OCR não persistido. Fluxo 10-6. Ver também VIA-IMPORTACAO-FILA. | N1 D1 Dev1 |
| DOC-IMPORTACAO-IDENTIFICACAO | Leitura e direcionamento: separação, identificação de tipo/registro/pessoa e aplicação | existente | `gestao/viagens/dominio/importacao.py:9-28` | Revisar as partes sem destino único e confirmar substituições. | Comprovante avulso nunca casa sozinho; DB de motorista de outro ofício pode ir ao ofício errado. Fluxo 10-6. | IA1 D2 |
| DOC-VIA-ASSINADA-CONFERENCIA | Conferência de assinatura e do documento certo (ADR 0022) | parcial | `gestao/viagens/documentos/leitura.py:75-124` | Abrir cada RT/DB devolvido para ver se está assinado. | Conferência só para ViaAssinada; a separação de partes pode perder a assinatura criptográfica (plausível). Fluxo 10-6. | D2 |
| PREST-ANEXOS | Anexos da prestação (despacho, comprovantes, DB/RT assinados) e versões | existente | `gestao/viagens/anexos.py:1-10` | Conferir e digitar valor, data e operação de cada comprovante. | Comprovante importado entra sem valor, data e operação (divergência fica cega); 'Usar no comprovante' descarta Transferência/Depósito (defeito confirmado). | D1 |
| PREST-LEITURA-CONFERENCIA | Leitura e conferência (etapa 3): transcrição dos anexos e conferência de valores | parcial | `gestao/viagens/leitura_anexos.py:1-9` | Copiar campos para o eProtocolo e conferir valor × diária. | Sem OCR na leitura; o resultado não é persistido nem vira pendência. | IA1 |
| PREST-CARIMBO | Carimbo do nº da solicitação no ofício assinado | parcial | `gestao/viagens/carimbo.py:1-23` | Informar a página e as posições em %. | Posição manual; a referência achava a linha do servidor no texto do PDF (regra determinística). | D1 |
| PREST-PENDENCIAS-FINALIZACAO | Pendências e finalização (servidor e equipe) | existente | `gestao/viagens/prestacao.py:127-156` | Conferir as pendências e finalizar servidor a servidor. | Finalizar continua humano; nenhum evento ao ficar pronta. | N1 X1 |
| PREST-PACOTE | Pacote final da prestação (PDF por servidor, ZIP da equipe) | existente | `gestao/viagens/pacote_prestacao.py:28-158` | Baixar o pacote e juntar no processo/sistema financeiro. | O download cria RT e diário se faltarem (efeito em GET); sem registro do pacote entregue. | Ext1 |
| PREST-ENVIO-FINANCEIRO | Envio ao financeiro, aprovação e devolução | existente | `gestao/viagens/prestacao.py:367-420` | Enviar fora do sistema e voltar para registrar o envio e a decisão. | Envio só registrado; consulta de andamento no eProtocolo simulada; quem aprova está a confirmar. | Ext1 |
| PREST-CONCLUSAO | Conclusão da prestação/viagem (estado final) | parcial | `gestao/viagens/prestacao.py:64-105` | Consultar as abas para saber o que está concluído. | Sem gatilho para encerrar, arquivar ou notificar. Fluxo 10-5. | S1 |
| PREST-LISTA-ABAS-EXPORT | Lista de prestações, abas de cobrança, agenda de prazos e exportação | existente | `gestao/viagens/prestacao.py:159-230` | Filtrar abas e cobrar um a um. | Lista mais pesada do PREVIEW (848 KB, até 1,3 s de servidor): paginar antes de servir a automações. | S1 |

### 3.4 Plataforma, integrações e operação (`plataforma`) — 23 processos

Outbox, worker, auditoria, notificações, rotinas, identidade, eProtocolo, Central de Viagens, rotas, painel, API/JSON, implantação, backup e monitoramento.

| ID | Processo | Estado | Evidência principal | Trabalho manual hoje | Observação | Oport. |
|---|---|---|---|---|---|---|
| PLAT-OUTBOX-PUBLICACAO | Publicação transacional de efeitos e eventos (outbox) | existente | `gestao/plataforma/outbox.py:54-69` | Nenhuma reação externa a eventos: operadores acompanham as telas e o sino. | Três tópicos; um assinante por tópico (o segundo registro levanta ValueError); payload sem versão de schema. | Dev2 |
| PLAT-OUTBOX-WORKER | Entrega, retentativa e falha definitiva (worker processar_outbox) | existente | `gestao/plataforma/outbox.py:34` | Falha definitiva só aparece no doctor/monitor. PDF falho exige clicar 'gerar novamente' (regenerar_documento). | Transação aberta durante o assinante; retentativa efetiva ~21 min; sem tela de falhas nem reprocessamento genérico. | D1 S2 X1 |
| PLAT-OUTBOX-ASSINANTES | Assinantes atuais: geração de PDF/A, emissão de ofício e e-mail | parcial | `gestao/viagens/assinantes.py:15-43` | O operador baixa o PDF emitido e envia/protocola manualmente fora do sistema. | Emissão sem efeito além do log; HTTP externo precisa de worker de entregas com lease, fora da transação. | N1 D1 |
| PLAT-NOTIF-SINO | Notificações internas (sino e central) | existente | `gestao/plataforma/notificacoes.py:33-67` | Operador lê o sino e repassa ao servidor por WhatsApp/telefone. Há link wa.me pronto só para a liberação de diárias (views_prestacao.py:176-191). | Só alcança usuários; servidores viajantes não são usuários. Deduplicação por título + link é frágil. | N2 X1 |
| PLAT-NOTIF-EMAIL | E-mail das notificações pela outbox | parcial | `config/settings/base.py:266-279` | Nenhum e-mail automático sai hoje; a pauta é baixada e enviada à mão. | Um único e-mail com todos os destinatários no 'Para'; sem SMTP institucional; só texto. | N1 Ext1 |
| PLAT-ROTINAS-DIARIAS | Rotinas diárias (avisos de prestação, chegadas e lembretes de solicitações) | existente † | `gestao/plataforma/rotinas.py:25-61` | O operador olha o sino e avisa os servidores do saque e dos documentos por telefone/WhatsApp, com o texto montado à mão ou pelo link wa.me. | 05:40 pelo timer (fuso do host não confirmado) ou no 1º acesso; falha não reexecuta no dia; sem horário por rotina. | N1 D1 Dev1 |
| PLAT-AUDITORIA | Trilha de auditoria por trigger e verificação diária da cadeia | existente | `gestao/plataforma/migrations/0001_auditoria_outbox.py:11-120` | Nenhum para o usuário; os operadores de TI conferem os alertas. | Trigger + verificação diária da cadeia; worker da outbox sem contexto de usuário; a trilha contém dados pessoais: não expor a n8n nem a LLM. | N1 S1 X1 |
| ID-AUTENTICACAO-AUTORIZACAO | Autenticação, papéis e escopo por unidade | existente | `gestao/identidade/backends.py:17-45` | Administrador cria usuários e define papéis; nada automatizado. | Sem token de serviço, conta de serviço ou 'agir em nome de'; sem SSO. | Dev2 Ext1 |
| PLAT-AMBIENTES-SALVAGUARDAS | Salvaguardas por ambiente (LAB/DEV/PREVIEW/STAGING/PRODUCTION/TEST) | existente | `gestao/plataforma/ambiente.py:14-60` | Nenhum (salvaguardas automáticas por ambiente). | A regra 'ferramentas do agente só leitura em PRODUCTION' não tem mecanismo no código. | N1 S1 |
| INT-EPROTOCOLO | Integração eProtocolo/PR (consulta e abertura de protocolo) | parcial | `gestao/integracoes/eprotocolo/adaptadores.py:45-66` | O operador copia os campos do painel 'dados para o eProtocolo', abre o processo no portal estadual e digita o número de 9 dígitos no ofício. | Porta + adaptadores (simulado, HTTP, gravado); abrir() sempre recusa; nenhum contexto chama; fases E3–E6 dependem de credencial institucional. | Dev1 Ext1 X1 |
| INT-CENTRAL-VIAGENS | Central de Viagens (Estado do PR) | inexistente | `docs/integrations/central-de-viagens.md:17-36` | O operador digita a solicitação de viagem e diárias na Central e copia o número de volta, por servidor. | Sem API pública conhecida; recomendação registrada: adaptador nulo + painel de cópia. | D1 Ext1 X1 |
| INT-ROTAS | Provedor de rotas (distância, tempo e traçado) | existente † | `gestao/viagens/rotas.py:1-40` | O operador confere e ajusta km e tempos no roteiro. | Produção sem provedor definido; PREVIEW em servidor público de demonstração (provedor efetivo incerto). Ver ROT-CALCULO-ROTA-CACHE; Fluxo 11-1. | D1 Ext1 X1 |
| API-FERRAMENTAS | Registro de ferramentas, portão de aprovação e fachada MCP (ADR 0020) | planejado | `docs/adr/0020-automacao-ferramentas-e-aprovacao.md:3-38` | Todo o trabalho passa pelas telas. | ADR 0020 'proposto'; gestao/automacao inexistente. Fundação de todo fluxo n8n/IA (contrato em contratos/api-automacao.v1.yaml). | IA1 Dev3 |
| API-JSON-INTERNA | Endpoints JSON internos das telas (autosave, buscas, rota, importação, downloads) | existente | `gestao/painel/views.py:35-40` | Nenhum (uso interno das telas). | Contratos de tela com cookie e CSRF: não devem ser usados pelo n8n. | S1 X1 |
| PAINEL-AGENDA | Agenda consolidada, escala e pauta em PDF | existente | `gestao/plataforma/agenda.py:187-250` | A ASCOM baixa a pauta e distribui; a equipe consulta a escala na tela. | Pauta semanal por e-mail depende de SMTP; sem aviso proativo de conflitos. | N1 D1 |
| PAINEL-ICS | Feed iCalendar pessoal da agenda (link com token) | existente | `gestao/painel/views_agenda.py:167-218` | Cada pessoa gera e assina o link na própria agenda. | Token só em hash; precedente de acesso externo somente leitura, não fonte de dados para o n8n. | S1 X1 |
| PAINEL-RELATORIO-CONSOLIDADO | Relatório consolidado mensal/anual e planilha XLSX | existente | `gestao/painel/consolidado.py:1-60` | A ASCOM baixa a planilha e repassa à chefia. | Envio mensal é transporte simples; comentário analítico por IA só como rascunho. | N1 IA1 |
| PLAT-BUSCA-CONFLITOS | Consultas transversais: busca global e conflitos de recurso | existente | `gestao/plataforma/busca.py:43-62` | O operador verifica conflitos ao montar ofício ou solicitação. | Só por tela; viraria ferramenta de leitura (busca e conflitos) para n8n e assistente. | Dev1 |
| PLAT-LEITURA-EMAIL | Leitura de e-mail colado (cabeçalhos, data, corpo, assinatura, contatos) | existente † | `gestao/plataforma/leitura_email.py:1-96` | O usuário copia o e-mail e cola no formulário. | Heurística local, sem IA, validada com corpus sintético; sem captura de caixa postal. | N1 IA1 |
| VIA-IMPORTACAO-FILA | Fila de importação documental (recebimento de documentos assinados e devolvidos) | existente | `gestao/viagens/importacao.py:137-183` | O operador recebe por e-mail ou WhatsApp os PDFs assinados (DB, RT, comprovantes, despachos), baixa e faz upload na tela. | Fila com lease (modelo para o worker de entregas); o importador fica fora dos scripts de monitor, backup e reinício. Fluxo 10-6. | N1 D1 S1 |
| OPS-DEPLOY | Implantação (homologação/produção por script; PREVIEW automático do main) | existente | `deploy/vps/implantar.sh:1-60` | A ativação de produção é manual e depende de autorização. | n8n fora da topologia; ativação de produção manual. Capacidade em ops/mudanca-hospedagem/capacidade-vps.md. | S1 X1 |
| OPS-BACKUP-RESTAURACAO | Backup diário, cópia externa criptografada e teste de restauração | existente † | `deploy/vps/backup.sh:1-107` | Conferência dos alertas. | RPO de 24 h; n8n não incluído; instalação dos timers no PREVIEW publicado a confirmar. | N1 D1 |
| OPS-MONITOR-SAUDE | Monitoramento leve, saúde e diagnóstico | existente † | `deploy/vps/monitorar.sh:1-91` | Leitura de journal e operacoes.log. | Importador e fila de importação não cobertos; /saude/ não reflete worker nem rotinas. | N1 D1 X1 |

### 3.5 Eventos, Coffee Break, ASCOM, cadastros e painel (`outros-modulos`) — 30 processos

gestao/eventos, gestao/coffee, gestao/imprensa, gestao/palestras, gestao/publicacoes, gestao/cadastros e gestao/painel.

| ID | Processo | Estado | Evidência principal | Trabalho manual hoje | Observação | Oport. |
|---|---|---|---|---|---|---|
| EVT-SOLICITACAO-CADASTRO | Cadastro da solicitação de evento (rascunho, modelo do tipo, anexos, duplicar, excluir) | existente | `gestao/eventos/models_solicitacao.py:16-103` | Digitar tudo a partir do ofício/e-mail/protocolo recebido, anexar o original, escolher serviços e equipes. | Contato do solicitante em texto livre; sem 'preencher com e-mail'; equipes só como quantidade. | D1 S1 Dev1 |
| EVT-ENVIO-DG | Envio à DG e reenvio após alteração | existente | `gestao/eventos/solicitacoes.py:158-212` | Conferir pendências e clicar em enviar; DG precisa abrir o sino para saber. | Nenhum evento na outbox (só sino); reenviar uma deferida não sincroniza a viagem nem avisa Viagens/Coffee. | N1 D1 S1 |
| EVT-DESPACHO-DG | Despacho da Diretoria-Geral | existente | `gestao/eventos/solicitacoes.py:215-284` | Abrir cada solicitação, ler, verificar conflitos e decidir. | Decisão humana na tela (correto); resumo de despacho e digest diário são determinísticos. | N1 D1 X2 |
| EVT-ENCERRAMENTO | Conclusão, cancelamento e transferência da solicitação | existente | `gestao/eventos/solicitacoes.py:310-363` | Lembrar de concluir após o evento; avisar manualmente coffee/palestras de cancelamentos. | Cancelamento não chega à OS de coffee nem à palestra de origem. | N1 S1 |
| EVT-GERAR-VIAGEM | Geração da viagem a partir da solicitação deferida (ponte Eventos → Viagens) | parcial | `gestao/eventos/ganchos.py:1-33` | Após gerar, a unidade monta à mão equipe, viatura, roteiro, diárias, ofícios, OS, PT e termos; copia anexos. | Por botão (na referência é automático no deferimento; decisão E4 pendente); a viagem nasce vazia. | IA1 S2 |
| EVT-LEMBRETES | Lembretes diários das solicitações | existente | `gestao/eventos/lembretes.py:28-118` | Nenhum para gerar; leitura do sino é manual. | DG achada pelo grupo, envio pela permissão (inconsistência); sem canal externo. | N1 D2 |
| EVT-CATALOGOS-MODELO | Catálogos de Eventos Sociais e modelo do tipo de evento | existente ‡ | `gestao/eventos/models.py:18-125` | Manutenção eventual dos catálogos. | Equipe é só um nome; unidade móvel não se liga a viatura; unificação Serviço/Atividade não commitada. | Dev1 |
| PAL-PEDIDO-REGISTRO | Registro de pedido de palestra/evento (ASCOM) | existente | `gestao/palestras/models.py:85-200` | Copiar o pedido do e-mail/WhatsApp para o formulário. | Sem pedido público nem leitura de e-mail (a referência tinha); decisão pendente. | N1 S1 Ext1 |
| PAL-ANDAMENTO-RESPOSTA | Andamento da palestra e resposta padrão ao solicitante | existente | `gestao/palestras/services.py:110-177` | Copiar/colar resposta em e-mail/WhatsApp, lembrar palestrante e cobrar retorno. | 'Resposta registrada' antes do envio real (mailto/wa.me); o módulo não notifica. | N1 D1 X1 |
| PAL-ENCAMINHAR-DG | Encaminhar palestra à DG (vira solicitação de evento) | existente | `gestao/palestras/encaminhamento.py:57-98` | Completar órgão/serviços/equipes e enviar; acompanhar a decisão abrindo a palestra. | A decisão da DG não volta à palestra; cancelamentos não são coordenados. | D2 |
| IMP-ATENDIMENTO | Atendimento à imprensa | existente | `gestao/imprensa/models.py:19-146` | Copiar e-mail, acompanhar prazos de cabeça/agenda, responder fora do sistema. | Deadline sem hora (impede alerta intradiário); responsável sem vínculo a usuário. | N1 IA1 D1 |
| PUB-PAUTA | Controle de publicações (pautas) | existente | `gestao/publicacoes/models.py:56-150` | Colar release, copiar link publicado, marcar divulgação. | Link publicado digitado; detectar a matéria depende de RSS/sitemap (a confirmar). | N2 |
| ASCOM-CADASTROS-APOIO | Cadastros de apoio da ASCOM | existente | `gestao/palestras/models.py:21-83` | Manutenção eventual. | Integrantes são nomes, sem usuário nem contato. | D1 Dev1 |
| CB-PEDIDO-OS | Solicitação de coffee break / Ordem de Serviço | existente | `gestao/coffee/models_pedido.py:18-152` | Ler e-mail do pedido, escolher/confirmar lote, criar OS, avisar fornecedor por fora. | A OS não é enviada ao fornecedor (CB8 inexistente); remarcação/cancelamento da origem só aparece ao abrir. | N1 D1 |
| CB-FINANCEIRO-MARCOS | Fluxo financeiro da OS e pagamento conjunto | existente | `gestao/coffee/dominio_pedido.py:126-165` | Digitar cada marco, conferir ordem, espelhar conjunto. | Marcos digitados; nada consulta o processo de pagamento. | N1 Ext1 X1 |
| CB-DOCUMENTOS-VIAS | Documentos do Coffee Break e vias assinadas | existente | `gestao/coffee/documentos.py:98-182` | Baixar, colher assinatura fora, anexar o assinado. | Via assinada só confere PDF e tamanho (sem ADR 0022); geração síncrona na requisição. | S2 |
| CB-PROTOCOLO-PAGAMENTO | Montagem do protocolo de pagamento | existente | `gestao/coffee/protocolo.py:56-204` | Abrir processo, copiar textos, juntar arquivos. | O download registra o atesto (efeito de negócio): automação não pode tratá-lo como leitura. | D1 Ext1 |
| CB-LEITURA-PDFS | Leitura de nota fiscal, ordem bancária e contrato/aditivo | existente † | `gestao/coffee/dominio_leitura.py:76-157` | Anexar cada PDF na OS certa e conferir avisos. | pypdf sem OCR, fora da importação documental; heurísticas testadas só com textos sintéticos. | IA1 S1 |
| CB-CERTIDOES | Certidões dos fornecedores | existente | `gestao/coffee/certidoes.py:48-107` | Olhar o painel, pedir renovação, baixar e anexar. | Só consulta ao painel/agenda; emitir nos portais (com CAPTCHA) não é automatizável. | N1 D1 X1 |
| CB-ENTREGAS | Recebimento e ocorrências da entrega | existente | `gestao/coffee/entregas.py:31-142` | Ligar para o local, registrar depois, avisar fornecedor por fora. | Registro posterior pela equipe; ocorrência não vira notificação ao fornecedor. | N2 |
| CB-PAINEL-CONTRATO-VIRADA | Painel, alertas de saldo e vigência, relatório do contrato e virada de exercício | existente | `gestao/coffee/painel.py:119-210` | Abrir painel e relatório periodicamente. | Alertas só ao abrir; o Coffee não emite notificações nem tem rotinas. | N1 D1 |
| CB-COMUNICACAO-FORNECEDOR | Comunicação com o fornecedor (e-mail da OS e da OB, link seguro) | inexistente | `gestao/coffee/models.py:181-199` | E-mails escritos à mão fora do sistema; datas de envio digitadas. | Assunto/texto dos e-mails da OS e da OB configuráveis mas sem uso; depende de SMTP. | S2 |
| CAD-SERVIDORES-VIATURAS-CATALOGOS | Cadastros de servidores, viaturas e catálogos gerais | existente | `gestao/cadastros/models.py:86-180` | Cadastrar e completar servidores e viaturas à mão. | Servidor sem e-mail, sem consentimento de contato e sem vínculo com Usuario. | D1 Dev1 |
| CAD-FONTE-DEDICADA | Fonte dedicada de cadastros (identidade externa e propriedade por campo) | parcial ‡ | `gestao/cadastros/fontes.py:1-128` | Nenhuma origem conectada; tudo digitado. | Mesmo mecanismo de CAD-FONTE-EXTERNA; arquivos não commitados, fora do PREVIEW. | D1 Ext1 X1 |
| CAD-USUARIOS-PAPEIS | Usuários, papéis e lotação | existente | `gestao/cadastros/views_usuarios.py:1-159` | Criar contas e informar senha inicial. | Sem 'esqueci a senha' (SMTP); Usuario sem telefone. | D1 Ext1 |
| CAD-UNIDADE-ASSINANTES-DIARIAS-TEXTOS | Dados da unidade, assinantes e substituições, tabela de diárias, textos prontos e municípios | existente ‡ | `gestao/cadastros/models.py:284-321` | Cadastrar substituições e vigências. | Substituições e vigências manuais; reorganização 'Dados da unidade' não commitada. Ver CAD-DADOS-UNIDADE-ASSINANTES. | D1 X1 |
| AGENDA-ESCALA-PAUTA-ICS | Agenda unificada, escala, pauta semanal, assinatura ICS e conflitos | existente | `gestao/painel/views_agenda.py:64-221` | Baixar e enviar a pauta; conferir conflitos abrindo folhas. | Pessoas do compromisso são nomes, não ids; 'estou escalado' depende do vínculo Usuario↔Servidor. Ver PAINEL-AGENDA. | N1 D1 Dev1 |
| NOTIFICACOES-ROTINAS | Notificações (sino), e-mail pela outbox e rotinas diárias | parcial | `gestao/plataforma/notificacoes.py:37-80` | Abrir o sino. | Só Eventos e Viagens notificam; e-mail desligado; sem preferência de canal. Ver PLAT-NOTIF-*. | N1 D2 |
| RELATORIOS-PAINEIS-EXPORTACOES | Painéis de módulo, exportações CSV/XLSX e relatório consolidado | existente | `gestao/painel/consolidado.py:1-404` | Gerar e enviar relatórios à mão. | Nada periódico; exportações já protegidas contra fórmula. | N1 IA1 |
| ENTRADA-DEMANDAS-CANAIS | Entrada de demandas por canais e triagem entre módulos (transversal) | parcial | `gestao/plataforma/leitura_email.py:1-30` | Copiar e colar e-mails/mensagens em cada módulo. | Sem caixa de entrada nem triagem entre módulos; canal oficial em decisão (WhatsApp Business bloqueado). | IA1 Dev1 Ext1 |

## 4. Processos das referências em produção

Os mesmos processos na forma em que rodam hoje. Servem de referência de comportamento e de lição; o código delas não é copiado para o sistema novo.

### 4.1 GV — Gerenciador de Viagens (`gv-implantado`, commit `ded9b648`) — 23 processos

Ofícios, roteiros e diárias, justificativas, termos, OS, planos, eventos, núcleo documental, prestação de contas, Central de Protocolos/eProtocolo, espelho Google Drive, Celery/Redis, unoserver, observabilidade.

| ID | Processo | Estado | Evidência principal | Trabalho manual hoje | Observação | Oport. |
|---|---|---|---|---|---|---|
| GV-OFICIO-WIZARD | Elaboração, numeração e emissão do ofício | existente | `gv/oficios/models.py:25-35` | Preencher 5 etapas, digitar protocolo e referências do motorista, escolher modelo de motivo, finalizar, baixar o PDF, levar ao eProtocolo para assinar e tramitar. | Cinco etapas sem proposta consolidada; protocolo digitado; assinatura digital no eProtocolo (decisão registrada no GV). | N1 IA1 S1 |
| GV-ROTEIRO-DIARIAS | Roteiro, cálculo de rota e diárias | existente † | `gv/roteiros/models.py:14-36` | Montar trechos e datas, disparar a estimativa e conferir as diárias. | ORS se houver chave, senão estimativa local; configuração de produção não verificável pelo código. **Risco externo:** o host do ORS fixo no código (`gv/roteiros/services/routing/openrouteservice.py:206`, `api.openrouteservice.org`) está depreciado, opera com 10 % da cota desde 27/08/2026 e será desligado em 02–06/11/2026; o km da referência pode cair na estimativa. A chave atual funciona em `api.heigit.org/openrouteservice` (<https://ask.openrouteservice.org/t/reducing-the-quota-of-deprecated-api-api-openrouteservice-org/8013>, consulta em 17/10/2026). Fluxo 11-1. | IA1 D1 |
| GV-JUSTIFICATIVA | Justificativa por antecedência insuficiente | existente | `gv/justificativas/services.py:22-28` | Redigir o texto e finalizar. | Prazo padrão de 10 dias corridos (regra determinística a preservar); texto todo manual. | N1 IA1 |
| GV-TERMOS | Termos de autorização (por servidor do ofício e avulsos) | existente | `gv/termos/services.py:57` | Gerar, distribuir, recolher assinados e anexar um por um. | Coleta do assinado manual (imprimir, assinar e escanear, ou baixar do eProtocolo). | D1 Dev1 |
| GV-OS | Ordem de Serviço | existente | `gv/ordens_servico/models.py:24` | Criar a OS, vincular ofícios, gerar e encaminhar para assinatura. | Assinatura e tramitação fora do sistema. | S1 |
| GV-PLANO-TRABALHO | Plano de Trabalho (evento itinerante) | existente | `gv/planos_trabalho/models.py:235-268` | Escolher o programa, o efetivo e os presets e revisar os textos padrão. | Presets e templates; o 'prompt' do repositório é material de desenvolvimento, não IA em execução. | IA1 X1 |
| GV-EVENTO | Cadastro de evento, anexos e solicitações; cancelamento em cascata | existente | `gv/eventos/models.py:14-36` | Cadastrar o evento, anexar o convite e as solicitações e mudar o status pelo formulário. | Status intermediários não avançam sozinhos: não servem de gatilho. | D1 Ext1 |
| GV-DOC-GERACAO | Núcleo documental: geração DOCX/XLSX -> PDF, artefatos e jobs assíncronos | existente | `gv/documentos/models.py:9-128` | Pedir cada download, esperar o job e baixar. | Artefato imutável com hash e snapshot (conceito a preservar); conversão em série no unoserver. | N1 S1 |
| GV-DOC-ASSINADO-MANUAL | Anexação de versão assinada (ofício, justificativa, termo) e revogação | existente | `gv/documentos/models.py:192-246` | Baixar do eProtocolo ou escanear, localizar o registro e anexar. | Versões assinadas append-only com revogação; recebimento manual, sem conferir se é o documento certo. Fluxo 10-6. | S1 Dev1 |
| GV-DRIVE-ESPELHO | Espelho Google Drive (organização de pastas, envio, pendências, reorganização, exclusão) | parcial † | `gv/config/settings/base.py:316-337` | Conectar a conta, escolher a pasta raiz e usar 'Tentar novamente' ou 'Reorganizar tudo' quando há pendências (sem efeito enquanto a fila não for consumida). | Espelho só de escrita (os canônicos ficam no disco do GV); envio interrompido desde 26/08/2026: decisão D3 do plano de implantação. | N1 S1 Dev1 X1 |
| GV-PREST-ABERTURA | Abertura automática da prestação e reconciliação da equipe | existente | `gv/prestacoes_contas/signals.py:6-67` | Abrir a lista de prestações e procurar as que precisam de ação. | Prestação nasce por signal; os status enviada/aprovada/reprovada nunca são atribuídos. | N1 |
| GV-PREST-DIARIO | Diário de Bordo (Etapa 1 da prestação) | existente | `gv/prestacoes_contas/models.py:556-665` | Receber KMs do motorista (papel/mensagem, a confirmar) e digitar trecho a trecho; ajustar o roteiro real; trocar motorista/viatura quando necessário. | Km digitado; o signatário do DB é o motorista do ofício, não o efetivo do diário. Fluxo 10-4. | N1 D1 S1 Dev1 |
| GV-PREST-RT | Relatório Técnico (Etapa 2) | existente | `gv/prestacoes_contas/models.py:530-554` | Escrever os textos, ajustar a diária recebida de cada servidor e gerar o RT por servidor. | A data do RT conta dias úteis sem feriados. | IA1 D1 |
| GV-PREST-ASSINATURA | Assinatura eletrônica de RT e DB por link público | existente | `gv/prestacoes_contas/models.py:724-862` | Gerar o link, abrir o WhatsApp, enviar, cobrar e conferir se foi assinado. | Assinatura eletrônica simples por link público (token cifrado + hash, CPF, expiração); envio e cobrança manuais. Fluxo 10-5. | N2 |
| GV-PREST-DOCUMENTOS-CARIMBO | Etapa 3: nº de solicitação, datas de liberação/saque, anexos e carimbo automático no ofício assinado | existente | `gv/prestacoes_contas/models.py:228-237` | Digitar número e datas, baixar do eProtocolo, anexar, ajustar o carimbo e anexar comprovantes. | Carimbo por âncora de texto (determinístico, preservar); nº da solicitação e datas digitados. | Ext1 X1 |
| GV-PREST-AVISO-DIARIAS | Mensagem de liberação de diárias / prazo de saque ('mensagem de saque') | existente | `gv/static/js/pages/prestacoes-diaria-wa.js:34-97` | Abrir cada cartão, preencher datas e clicar para enviar o WhatsApp um a um, lembrando do prazo de cabeça. | Texto institucional ('PRAZO IMPRORROGÁVEL') e validações no navegador, sem registro de envio. Fluxo 10-3. | N1 S1 |
| GV-PREST-CONSOLIDADO | Etapa 4: PDF final por servidor, finalização e arquivamento | existente | `gv/prestacoes_contas/services.py:635-655` | Conferir pendências, baixar o PDF final, enviar por fora e marcar como finalizado. | Finalizar sem pré-condição é decisão travada por teste; o destino do PDF final fica fora do sistema. | N1 Ext1 |
| GV-EPROTOCOLO | Central de Protocolos e integração eProtocolo (spi-servicos v3) | parcial † | `gv/config/settings/base.py:395-417` | Protocolar, anexar, pedir assinatura e acompanhar no próprio eProtocolo; copiar o número para o ofício. | Cliente do barramento spi-servicos v3 com modo simulado por padrão; ambiente efetivo de produção não verificável pelo código. | S1 Ext1 X1 |
| GV-UPLOAD-AV | Validação de uploads e antivírus (ClamAV) | existente | `gv/core/uploads.py:16-115` | Nenhum (automático), exceto reenviar quando o AV está indisponível. | Validação de uploads com antivírus; conceito a levar: um único pipeline de entrada para tela, importação e n8n. | S1 |
| GV-CIFRAGEM-SEGREDOS | Cifragem de campos e tratamento de segredos/dados pessoais | existente | `gv/core/db_fields.py:11-46` | Rotação de chave manual. | Cifragem de tokens e mascaramento em logs (conceitos a preservar); classificação LGPD aguarda o encarregado. | S1 |
| GV-OBS-BACKUP-AUDITORIA | Observabilidade, auditoria e backup | parcial † | `gv/core/views.py:29-53` | Verificar systemctl e logs manualmente. | Sentry, /metrics e /health existem, sem métricas de fila e de worker. | N1 |
| GV-NOTIFICACOES | Notificações e canais de contato | parcial | `gv/integracoes/google_drive/signals.py:104-117` | Copiar/abrir WhatsApp e enviar mensagem por mensagem. | Único canal com o servidor é o telefone por click-to-chat; sem e-mail configurado. | Ext1 |
| GV-ASSISTENTE-DUVIDAS | Assistente de dúvidas dos servidores | inexistente | `gv/requirements/base.txt:1-30` | O operador responde individualmente por telefone/WhatsApp (presumido; não verificável no código). | Sem base de conhecimento curada nem canal de atendimento. | IA1 |

### 4.2 EV — Eventos Sociais (`ev-implantado`, `92f57bda` + 8 arquivos fora do Git) — 23 processos

Eventos sociais, ASCOM, Coffee Break, viagens e prestação na árvore implantada, comparada ao histórico Git do EV e ao sistema novo.

| ID | Processo | Estado | Evidência principal | Trabalho manual hoje | Observação | Oport. |
|---|---|---|---|---|---|---|
| EV-IA-ASSISTENTE | Assistente conversacional de viagens (LLM) — removido | inexistente | `EVI/config/settings.py:58-88` | Servidores tiram dúvidas com a equipe por telefone/WhatsApp pessoal; não há registro no sistema. | App 'assistente' (Anthropic opcional) existiu no Git em 20–21/09/2026 e foi removido; 'assistente Gemini' sem respaldo no código. | IA1 X1 |
| EV-WHATSAPP-CANAL | Canal WhatsApp Cloud API (webhook Meta) — resíduos sem código | inexistente | `EVI/config/urls.py:46-48` | O operador clica em 'Enviar por WhatsApp' (wa.me) e manda pelo aparelho dele. | Rota do webhook só comentada; .service fora do Git chama comando inexistente. Ativação bloqueada pela política da Meta. | D1 Ext1 X1 |
| EV-LEITURA-PEDIDO | Preencher formulário a partir de e-mail, conversa de WhatsApp exportada ou print | existente † | `EVI/core/preencher_por_email.py:1-24` | Baixar o e-mail ou exportar a conversa, arrastar para a tela, conferir e salvar. | Leitura local e determinística; bateria de 560 casos fictícios reaproveitável como avaliação. | N1 IA1 D1 |
| EV-TRIAGEM-MODULO | Triagem do pedido na página inicial (qual módulo) com memória por remetente | existente | `EVI/core/triagem_email.py:1-18, 35-36` | Decidir o módulo quando a confiança é baixa; repassar e-mails entre setores. | Decide com confiança mínima de 0,55; sem fila compartilhada. | IA1 D1 |
| EV-PEDIDO-PUBLICO | Pedido público de palestra/evento (sem login) com acompanhamento por token | existente | `EVI/demandas_eventos/pedido_publico.py:1-23, 83-123, 190-276` | Triagem do pedido e resposta ao solicitante (ver EV-RESPOSTA-PADRAO). | Página pública com acompanhamento por token; sem confirmação por e-mail. | N1 |
| EV-RESPOSTA-PADRAO | Resposta padrão ao solicitante de palestra (e-mail/WhatsApp manual) | existente | `EVI/demandas_eventos/services.py:186-240` | Abrir o e-mail ou o WhatsApp, colar, enviar e voltar para registrar. | Registro de 'enviado' declarativo. | N1 |
| EV-SOLICITACAO-DESPACHO | Solicitação de evento social: envio, despacho da DG, devolução e lembretes | existente | `EVI/solicitacoes/services.py:1-7, 33-51` | Despacho e confirmação de atendimento (decisões humanas que devem permanecer). | Lembretes dependem do primeiro login do dia. | N1 X1 |
| EV-DEFERIMENTO-GERA-VIAGEM | Deferimento gera a viagem automaticamente (com multieventos e rede de segurança) | existente | `EVI/solicitacoes/services.py:368-418` | Completar quem vai e a viatura. | Geração síncrona em on_commit; falha vira notificação; nova tentativa manual ou diária. | S1 |
| EV-PROPOSTA-DOCUMENTOS | Proposta consolidada da viagem: 'Gerar documentos' com equipe, histórico, plano e prontidão | existente | `EVI/viagens_viagem/views.py:445-497` | Escolher a equipe, revisar e finalizar cada documento no seu módulo. | Proposta 'preenchida pelo histórico', sem IA: referência para a proposta consolidada do novo. | IA1 S1 X1 |
| EV-ROTA-DISTANCIA | Cálculo de rota, tempo e distância do roteiro | existente † | `EVI/viagens_roteiros/services/rota.py:1-40` | Ajustar horários e paradas. | ORS + geocodificação com cache; só coordenadas saem do servidor. **Risco externo:** host antigo do ORS fixo no código (`EVI/viagens_roteiros/services/rota.py:24`), com 10 % da cota desde 27/08/2026 e desligamento em 02–06/11/2026; a chave atual funciona em `api.heigit.org/openrouteservice` (mesma fonte de GV-ROTEIRO-DIARIAS). Fluxo 11-1. | IA1 X1 |
| EV-DIARIO-LINK-KM | Link do diário de bordo no celular do motorista (km por trecho, offline) | existente † | `EVI/viagens_prestacoes/campo_services.py:1-13, 39-45, 84-133` | Gerar o link, abrir o WhatsApp, enviar ao motorista e cobrar o preenchimento. | Link de km com PWA offline e sincronização idempotente; envio manual por wa.me; uso real em produção não verificado. Fluxo 10-4. | N1 Dev1 X1 |
| EV-AVISOS-PRESTACAO | Avisos de prazo e situação da prestação de contas | existente | `EVI/viagens_prestacoes/avisos.py:1-18, 40-44, 51-96, 124-166` | O operador lê o sino e cobra cada servidor por WhatsApp. | O servidor não recebe nada direto; 'amanhã sai a viagem' pode sair para ofício em rascunho (plausível). Fluxo 10-3. | N1 |
| EV-MENSAGEM-LIBERACAO | Aviso de liberação das diárias ao servidor (a 'mensagem de saque') | existente | `EVI/viagens_prestacoes/cartoes.py:60-79` | Clicar, abrir o WhatsApp do operador, enviar, um servidor por vez. | wa.me com dados pessoais na URL; sem prova de envio. Fluxo 10-3. | N1 |
| EV-RT-SUGESTAO | Sugestão de texto do Relatório Técnico (conclusão e medidas) | existente | `EVI/viagens_prestacoes/rt_services.py:448-514` | Ajustar o texto sugerido e colher a assinatura. | A regra afirma 'sem intercorrências' sem dado que sustente: alerta para qualquer geração por IA. Fluxo 10-5. | IA1 D1 |
| EV-DB-RT-ASSINATURA | Geração do Diário de Bordo e do RT, envio para assinatura e retorno do assinado | parcial | `EVI/config/settings.py:294-296` | Baixar PDF, mandar ao servidor (WhatsApp/e-mail), cobrar, receber, anexar. | Sem estado 'enviado para assinatura'; retorno por upload manual. Fluxo 10-5. | N2 |
| EV-IMPORTACAO-PROCESSO | Importação do processo do eProtocolo na prestação (leitura e direcionamento de documentos devolvidos) | existente | `EVI/viagens_prestacoes/importacao_views.py:1-17, 139-215` | Baixar o processo do eProtocolo e enviar; conferir quando não é seguro. | Importação síncrona na requisição (OCR de até 12 páginas); o novo optou por fila. Fluxo 10-6. | N1 X1 |
| EV-COFFEE-FORNECEDOR-PAGAMENTO | Coffee break: e-mails ao fornecedor, link seguro para nota/certidões e importação do processo de pagamento | existente † | `EVI/coffee_break/emails.py:1-9` | Conferir e aceitar nota/certidões; acompanhar o pagamento. | E-mails síncronos, sem fila nem status de entrega; SMTP efetivo não verificado. | N1 |
| EV-EPROTOCOLO | Integração eProtocolo: abertura automática do protocolo do ofício e consulta de andamento | parcial † | `EVI/integracoes/eprotocolo/__init__.py:1-19` | Abrir o protocolo no eProtocolo em outra aba e digitar o número; baixar o processo para importar. | Simulado por padrão: números SIMULADOS devem ser tratados como não oficiais por qualquer automação. | Ext2 |
| EV-ENVIO-FINANCEIRO | Envio da prestação ao financeiro, aprovação e devolução | existente | `EVI/viagens_prestacoes/envio_services.py:1-80` | Montar o pacote, protocolar, anotar o número, acompanhar a devolução. | Envio e decisão do financeiro registrados à mão. | Ext1 |
| EV-ROTINAS-DIARIAS | Rotinas diárias disparadas pelo primeiro acesso (sem agendador) | existente | `EVI/core/rotinas.py:1-26, 59-101, 144-187` | Nenhum; depende de alguém entrar no sistema no dia. | Sem agendador; o novo herdou o padrão e acrescentou um timer. | N1 |
| EV-AGENDA-ICS-PAUTA | Agenda unificada, feed iCalendar pessoal e pauta semanal por e-mail | existente | `EVI/agenda/fontes.py:1-22` | Nenhum (agenda e feed automáticos). | Determinístico, sem papel para n8n ou IA; equivalente já existe no novo (PAINEL-ICS). | S1 |
| EV-VINCULO-USUARIO-SERVIDOR | Vínculo usuário ↔ servidor de viagens | existente | `EVI/accounts/models.py:70-80` | Vincular manualmente. | Vínculo manual e nem todo servidor tem conta; no novo o vínculo está pendente. | S1 |
| EV-MIGRACAO-GV | Carga do GV para o EV (somente leitura no legado) | existente | `EVI/config/settings.py:164-178` | Execução manual. | Carga única GV→EV por conexão somente leitura; não automatizar carga contínua. | X1 |

## 5. Integrações existentes

Uma linha por integração, deduplicada entre as sete leituras. Estado por sistema: `existente`,
`parcial`, `simulado`, `planejado`, `inexistente`; "—" = não se aplica ou não examinado.

| Integração | Sistema novo | GV | EV | Onde (evidência principal) | Observação |
|---|---|---|---|---|---|
| Outbox transacional + worker (PostgreSQL, LISTEN/NOTIFY, SKIP LOCKED) | existente | — | inexistente | `gestao/plataforma/outbox.py:34-118`; `gestao/viagens/services.py:1067-1075` | Só 3 tópicos: `viagens.documento.gerar`, `viagens.oficio.emitido` (assinante só grava log), `plataforma.email.enviar`. Ver fato 4 |
| Celery + Redis (filas `celery` e `drive`, beat) | — | existente | inexistente | `gv/config/celery.py:1-10`; `gv/config/settings/base.py:345-393` | No GV a fila `drive` não é consumida desde 26/08/2026 (decisão D3 do plano). EV não tem broker |
| Webhook de saída de eventos de negócio (para n8n ou terceiros) | inexistente | inexistente | inexistente | contrato proposto em [`contratos/evento-integracao.schema.json`](contratos/evento-integracao.schema.json) | Hoje só eProtocolo e rotas fazem HTTP de saída no novo |
| API de ferramentas / token de serviço / MCP (ADR 0020, `gestao/automacao`) | planejado | inexistente | inexistente | `docs/adr/0020-automacao-ferramentas-e-aprovacao.md:3`; `docs/ai/ferramentas.md` | ADR "proposto"; pacote não existe. Contrato proposto em [`contratos/api-automacao.v1.yaml`](contratos/api-automacao.v1.yaml) |
| Endpoints JSON internos das telas (autosave, buscas, rota, importação) | existente | — | — | `gestao/painel/views.py:35-40`; `gestao/viagens/views_importacao.py:32-56` | Sessão + CSRF; não servem a consumidor externo |
| n8n | planejado | inexistente | inexistente | `docs/integrations/orquestracao.md:5-28`; `docs/integrations/hostinger.md:24-50` | Protótipo local de mecanismos em `docs/automacao/prototipo/` (simuladores; não é integração) |
| Notificações internas (sino) | existente | — | existente | `gestao/plataforma/notificacoes.py:33-67`; `EVI/core/notificacoes.py:50-93` | Só usuários internos; no novo só Eventos e Viagens notificam |
| E-mail SMTP (notificações, pauta, e-mails do coffee) | parcial | inexistente | parcial † | `gestao/plataforma/notificacoes.py:54-80`; `config/settings/base.py:266-279`; `EVI/config/settings.py:217-235` | Novo: desligado por padrão, console sem `EMAIL_HOST`, um envio com todos no "Para". GV: sem `EMAIL_*`. SMTP institucional pendente de credencial (`docs/migration/decisoes.md:313`) |
| `mailto` (resposta de palestras) | existente | — | existente | `gestao/palestras/dominio.py:157-160`; `EVI/demandas_eventos/services.py:186-240` | Abre o cliente de e-mail; o registro de "resposta" não comprova envio |
| WhatsApp click-to-chat (`wa.me` / `api.whatsapp.com`) | parcial | existente | existente | `gestao/viagens/views_prestacao.py:176-191`; `gv/static/js/pages/prestacoes-diaria-wa.js:127-145`; `EVI/viagens_prestacoes/cartoes.py:60-79` | Nada é enviado pelo sistema; envio manual pelo aparelho do operador; dados pessoais vão na URL |
| WhatsApp Business Platform (Cloud API, webhook Meta) | inexistente | inexistente | inexistente | `EVI/config/urls.py:46-48` | **Bloqueado** pela política (fato 1); a integração oficial fica pronta e desligada pela frente WA-3 (AUT-174). No EV, app e canal existiram no Git em 20–21/09/2026 e foram removidos; restam resíduos |
| Transcrição de áudio (faster-whisper) | — | — | inexistente | `EVI/.env.example:78-80` | Fazia parte do canal WhatsApp removido |
| eProtocolo/PR (barramento spi-servicos, OAuth2) | parcial | parcial † | simulado † | `gestao/integracoes/eprotocolo/adaptadores.py:45-187`; `gv/integracoes/eprotocolo/settings.py:14-209`; `EVI/config/settings.py:319-342` | Novo: porta e adaptadores, simulado por padrão, `abrir()` recusa, nenhum fluxo chama. GV e EV: simulado por padrão; endpoints "a confirmar"; ambiente efetivo não verificável pelo código. EV gera números SIMULADOS |
| Central de Viagens (sistema estadual de viagens/diárias) | inexistente | inexistente | inexistente | `docs/integrations/central-de-viagens.md:17-36` | Sem API pública conhecida; nº da solicitação e datas de liberação são digitados. "Central de Viagens 3" é o nome do próprio GV |
| Roteamento OSRM | existente | parcial | — | `gestao/viagens/rotas.py:101-106`; `gv/roteiros/services/routing_provider.py:200-226` | Novo: fora de `gestao/integracoes`, síncrono; dev/PREVIEW no servidor público de demonstração. GV: código sem configuração em settings (inativo) |
| OpenRouteService | existente | parcial † | existente † | `gestao/viagens/rotas.py:109-116`; `gv/config/settings/base.py:214-218`; `EVI/viagens_roteiros/services/rota.py:1-40` | Novo: adaptador não usado como padrão em nenhum ambiente. GV/EV: usado se houver chave no ambiente |
| Estimativa offline de rota + cache de distâncias | existente | existente | — | `gestao/viagens/rotas.py:73-80, 135-157`; `gestao/viagens/models.py:537-555` | Linha reta × 1,3; padrão da base e de toda falha; cache versionado (ADR 0024). A origem do km não fica no trecho |
| Mosaicos OpenStreetMap (Leaflet) | existente | — | — | `config/settings/base.py:228-239` | Origem no `img-src` da CSP |
| Municípios com coordenadas / IBGE | existente | — | existente | `gestao/cadastros/carga.py:9-21`; `EVI/cadastros/management/commands/importar_localidades_ibge.py:14-16` | 5.571 municípios; sem geocodificação de endereço do evento no novo |
| ViaCEP / Nominatim (busca de endereço) | inexistente | existente (ViaCEP) | existente | `gv/cadastros/services_via_cep.py:12-20`; `EVI/viagens_cadastros/geocodificacao.py:13` | No novo, só pela camada de integrações e com aprovação (ADR 0019) |
| Importação documental com fila (conversão, OCR, identificação, direcionamento) | existente | inexistente | existente | `gestao/viagens/importacao.py:38-320`; `gestao/viagens/management/commands/processar_importacoes.py:16-60`; `EVI/viagens_prestacoes/importacao_views.py:139-215` | Novo: só Viagens, só upload em sessão, sem evento ao concluir. EV: síncrona na requisição. GV: recebimento por upload manual |
| OCR e conversão locais (Tesseract, LibreOffice, Poppler) | existente | — | existente † | `Dockerfile:17-24`; `gestao/viagens/importacao.py:192-240`; `EVI/core/leitura/ocr.py:1-28` | Sem internet nem IA externa (ADR 0041) |
| unoserver/LibreOffice (DOCX/XLSX → PDF) | — | existente | — | `gv/documentos/services/pdf_engine.py:322-348` | Uma conversão por vez, compartilhada com o espelho do Drive |
| Geração de PDF (PDF/A pela outbox; WeasyPrint síncrono) | existente | — | existente | `gestao/viagens/assinantes.py:15-43`; `gestao/coffee/documentos.py:160-170`; `EVI/config/settings.py:294-296` | Novo: ofício/justificativa assíncronos; coffee e pauta na requisição |
| Leitura de PDF para conferir assinatura (pypdf, ADR 0022) | parcial | — | — | `gestao/viagens/documentos/leitura.py:75-124`; `gestao/viagens/dominio/conferencia.py:1-120` | Só ViaAssinada (ofício, justificativa, termo, OS); não DB, RT, despacho nem Coffee; não valida a cadeia ICP |
| Leitura de e-mail colado / conversa exportada (heurística) | existente | — | existente † | `gestao/plataforma/leitura_email.py:1-96`; `EVI/core/preencher_por_email.py:1-24` | Novo: imprensa, publicações, coffee; sem triagem entre módulos. EV: também conversa de WhatsApp exportada e print, com triagem |
| Leitura de PDFs do Coffee (NF, OB, certidões, contrato) | existente † | — | — | `gestao/coffee/dominio_leitura.py:76-157` | pypdf sem OCR; validada só com textos sintéticos |
| Feed iCalendar (ICS) pessoal por token | existente | — | existente | `gestao/painel/views_agenda.py:167-218`; `gestao/plataforma/assinatura.py`; `EVI/agenda/ics.py:1-17` | Único acesso externo por token do novo (token só em hash); somente leitura |
| Link público para o servidor lançar km (diário de campo) | inexistente | inexistente | existente † | `EVI/viagens_prestacoes/campo_services.py:1-385` | PWA offline com sincronização idempotente; envio ao motorista manual. Fluxo 10-4 |
| Assinatura eletrônica simples de RT/DB por link público | inexistente | existente | inexistente | `gv/prestacoes_contas/assinatura_services.py:1-132`; `gv/documentos/services/temporary_links.py:19-26` | Ver fato 3. O EV removeu (migração 0006). Fluxo 10-5 |
| Pedido público de palestra e link seguro do fornecedor | inexistente | — | existente | `EVI/demandas_eventos/pedido_publico.py:1-23`; `docs/migration/decisoes.md:329` | No novo, depende de decisão do usuário |
| E-mail ao fornecedor do Coffee (OS e OB) | inexistente | — | existente † | `gestao/coffee/models.py:181-199`; `EVI/coffee_break/emails.py:1-9` | Novo: textos configuráveis sem uso. EV: envio síncrono, sem fila nem status |
| Fonte externa de cadastros (espelho com reconciliação) | parcial ‡ | — | — | `gestao/cadastros/fontes.py:1-128`; `gestao/cadastros/models.py:598-620` | Serviços e testes, sem transporte nem fonte definida |
| Ponte Eventos → Viagens (gerar e encerrar viagem pela solicitação) | existente | — | existente | `gestao/viagens/de_eventos.py:121-189`; `EVI/solicitacoes/services.py:368-418` | Novo: por botão, propaga só título, período, destino, motivo e tipos. EV: automática no deferimento |
| Rotinas diárias (timer + primeiro acesso do dia) | existente † | — | existente | `gestao/plataforma/rotinas.py:25-61`; `deploy/systemd/pcpr-rotinas@.timer:5`; `EVI/core/rotinas.py:173-187` | Novo: 05:40 no fuso do host (não confirmado) ou 1º acesso. EV: só 1º acesso. GV usa o beat do Celery |
| Exportações CSV/XLSX e relatório consolidado | existente | — | — | `gestao/painel/consolidado.py:1-404` | Células protegidas contra fórmula; sob demanda, em sessão |
| Google Drive API (espelho de documentos) | inexistente | parcial † | inexistente | `gv/config/settings/base.py:316-337`; `gv/integracoes/google_drive/services.py` | Espelho só de escrita; envio interrompido desde 26/08/2026 (decisão D3) |
| Antivírus de uploads (ClamAV) | — | existente | existente (código) | `gv/core/uploads.py:16-115`; `EVI/core/uploads.py:73-91` | Configuração de produção não detalhada aqui |
| IA / LLM (Gemini, Anthropic ou outro) | inexistente (planejado em `docs/ai/`) | inexistente | inexistente | `docs/ai/README.md:1-73`; `gv/requirements/base.txt:1-30`; `EVI/config/settings.py:58-88` | Nenhuma IA executa hoje. No EV o app "assistente" (Anthropic opcional) existiu em 20–21/09/2026 e foi removido; "assistente Gemini" sem respaldo no código |
| Observabilidade (Sentry, `/metrics`, `/health`; `/saude/`, `doctor`, monitor) | existente | existente | — | `deploy/vps/monitorar.sh:1-91`; `gv/core/views.py:29-53` | Nenhum dos dois mede filas e workers; no novo o importador não é coberto |
| Alertas operacionais por webhook (ntfy/Slack/Discord) | existente | — | — | `deploy/vps/lib.sh:28-50` | Pode apontar para o n8n |
| Backup externo (restic) e teste de restauração | existente † | existente † | — | `deploy/vps/backup.sh:73-104`; `deploy/vps/restaurar-teste.sh`; `gv/scripts/backup_production.sh:1-50` | Novo: validado em VPS simulada; no PREVIEW, backup por publicação. Agendamento nas referências não verificável pelo código |
| Deploy automático (GitHub Actions → VPS) | existente | existente | existente | `.github/workflows/deploy-vps.yml`; `gv/.github/workflows/deploy.yml`; `EVI/scripts/deploy/vps/atualizar.sh:20-36` | Novo: só PREVIEW, a partir do `main` |
| SSO institucional | inexistente | existente (desligado por padrão) | — | `gv/config/settings/base.py:76-94` | No novo, SSO pela Central de Segurança é dependente de integração externa |
| Banco do GV em leitura (carga para o EV) | — | — | existente | `EVI/config/settings.py:164-178` | Só nos comandos de migração |
| MCP `postgres-leitura` | existente | — | — | `.mcp.json`; `deploy/postgres/01-papeis.sh:18,34-35` | Ferramenta dos agentes de desenvolvimento com o papel `pcpr_leitura`; não é integração do produto |

## 6. Achados transversais relevantes para automação

Consolidados dos 148 achados das leituras. Ficaram fora os que tratam de configuração de segurança dos
servidores de produção.

### 6.1 Fundação de integração

1. **Não há canal de máquina para o sistema novo.** Todas as views exigem sessão, exceto login,
   `/saude/` e o feed ICS; os JSON atuais são de tela, com cookie e CSRF. O ADR 0020 está "proposto" e
   `gestao/automacao/` não existe: faltam token de serviço, delegação emitida pelo PCPR (`Delegacao`), `PedidoAprovacao` e
   `ExecucaoFerramenta` (`docs/adr/0020-automacao-ferramentas-e-aprovacao.md:3`;
   `gestao/viagens/views_importacao.py:32-56`). **Nenhuma** oportunidade classificada como n8n é
   executável antes da etapa 1 do [plano de implantação](plano-implantacao.md). A regra "ferramentas do
   agente somente leitura em PRODUCTION" também não tem mecanismo no código.
2. **Catálogo de eventos mínimo.** A outbox publica três tópicos (`gestao/viagens/services.py:1067-1075`;
   `gestao/plataforma/notificacoes.py:57`) e `viagens.oficio.emitido` só grava log
   (`gestao/viagens/assinantes.py:46-49`). Não há evento para viagem gerada ou cancelada, PDF pronto,
   via assinada recebida, reabertura, retificação, plano, roteiro, prestação, diário, RT, importação ou
   solicitações. Avisos de solicitação e de viagem gerada saem em `transaction.on_commit`, fora da
   transação (`gestao/eventos/solicitacoes.py:63`; `gestao/viagens/de_eventos.py:149`): se o processo
   cair entre o commit e o aviso, o aviso se perde.
3. **O worker atual não serve para HTTP externo.** Ele segura a transação durante o assinante; o papel
   da aplicação tem limite de 5 min para transação ociosa (`deploy/postgres/01-papeis.sh:38-39`) e a
   auditoria serializa as escritas por advisory lock global
   (`gestao/plataforma/migrations/0001_auditoria_outbox.py`): uma chamada lenta travaria o sistema. A retentativa efetiva é de 10 s a 640 s, ~21 min até
   `falhou` (`gestao/plataforma/outbox.py:34, 72-73, 108-111`); `ao_falhar` roda a cada falha, então o
   Documento fica `FALHOU` já na 1ª falha transitória (`outbox.py:98-106`); não há tela de falhas,
   reprocessamento genérico, contexto de auditoria no worker nem retenção da outbox e das notificações.
   O modelo certo já existe no importador: fila com lease, claim curto, execução fora da transação,
   até 3 tentativas (`gestao/viagens/importacao.py:161-183`).
4. **Peças reaproveitáveis.** Token seguro com só o hash SHA-256 gravado, exibido uma vez, revogável e
   mascarado em logs (`gestao/plataforma/assinatura.py`; `gestao/plataforma/logs.py`) — base para link
   de acesso e token de serviço. Domínio puro com mensagens prontas em todos os módulos, histórico de
   negócio por módulo e registro de fontes (agenda, busca, conflitos) permitem integrar sem import
   cruzado. A porta do eProtocolo já tem `abrir(PedidoDeAbertura)` com chave de idempotência.

### 6.2 Tempo e agendamento

5. **Rotinas diárias não servem para horário marcado.** Rodam às 05:40 pelo timer, no fuso do host (não
   confirmado), ou dentro da requisição do primeiro usuário do dia (`deploy/systemd/pcpr-rotinas@.timer:5`;
   `gestao/plataforma/middleware.py:108-127`). Rotina que falha não roda de novo no mesmo dia; o aviso de
   chegada só enxerga 36 h; a deduplicação de avisos usa título + link (`gestao/viagens/avisos.py:32-36`),
   então mudar o texto reenvia. No EV, sem login (fim de semana, feriado) nada roda
   (`EVI/core/rotinas.py:173-187`). Gatilhos como "véspera às 17h" precisam de agendamento com
   `America/Sao_Paulo` explícito, mantendo no sistema a regra do que é devido.

### 6.3 Pessoas, contato e canais

6. **O servidor não é alcançável pelo sistema.** `Servidor` tem telefone único de 11 dígitos e não tem
   e-mail; não há vínculo `Usuario`↔`Servidor` (decisão pendente); `Usuario` não tem telefone;
   integrantes da ASCOM são só nomes; `Solicitacao.contato` é texto livre de 100 caracteres
   (`gestao/cadastros/models.py:86-128`; `gestao/identidade/models.py:25-31`). O sino só alcança os
   grupos internos. No GV também não há e-mail do servidor nem `EMAIL_*`
   (`gv/cadastros/models.py:254-282`). Aviso de saque, link de km, assinatura e assistente dependem de
   modelar contato verificado e consentimento.
7. **Canais disponíveis hoje.** Plataforma oficial do WhatsApp bloqueada (fato 1); o `wa.me` manual vira
   envio assistido com registro na frente WA-1 (AUT-172). Os links `wa.me` em uso levam
   nome, valor da diária, telefone e ofício na URL, que passa pelo redirecionador da Meta
   (`EVI/viagens_prestacoes/cartoes.py:60-79`; `gestao/viagens/views_prestacao.py:176-191`) — ponto de
   atenção LGPD. O e-mail do novo está desligado e, quando ligado, manda **um** e-mail com todos os
   destinatários no "Para" (`gestao/plataforma/notificacoes.py:79-80`). O SMTP institucional depende de
   credencial externa (`docs/migration/decisoes.md:313`). A pesquisa indica que o Governo do PR usa
   Google Workspace via Celepar (fonte de imprensa oficial, confiança média, consultada em 17/10/2026):
   relay SMTP institucional é possível, mas **não confirmado** para a PCPR.
8. **Nenhum sistema sabe se uma mensagem saiu.** Palestras grava "Resposta registrada" antes de qualquer
   envio (`gestao/palestras/views.py:338-353`); o GV monta a mensagem de saque no navegador, com a data
   do cliente e sem registro (`gv/static/js/pages/prestacoes-diaria-wa.js:34-97`); o EV registra
   "enviado" de forma declarativa (`EVI/demandas_eventos/services.py:186-240`).

### 6.4 Documentos, versões e numeração

9. **Só o ofício tem documento final imutável** (EMITIDO + PDF/A-2a com instantâneo e SHA-256;
   `gestao/viagens/services.py:1035-1078`). O termo não tem estado final, a OS "finalizada" continua
   editável e o plano GERADO também (`gestao/viagens/policies.py:455, 522-526`); o plano é refeito dos
   dados atuais a cada download e DB/RT não guardam hash da versão enviada. Envio automatizado para
   assinatura exige snapshot antes. A versão corrente deve sair da projeção da ADR 0025
   (`gestao/viagens/dominio/documentos_versoes.py`), para não mandar PDF de emissão anterior.
10. **Número oficial reservado no rascunho** (`gestao/viagens/services.py:154-171`; idem OS e plano).
    Lote, repetição e duplicação consomem números na hora. Proposta automática tem de ser **prévia sem
    gravar**; criar rascunhos para propor gera lacunas.
11. **Retificar é amplo e muda conteúdo.** Qualquer operador com `change_oficio` retifica um ofício
    emitido sem motivo, o que revoga as vias assinadas (`gestao/viagens/services.py:1101-1118`;
    `policies.py:97-103`) — deve ser ação irreversível com aprovação. Emitir em outro dia troca a data e
    pode virar Convalidação com justificativa (`gestao/viagens/dominio/assunto.py:36-48`).
12. **Leituras com efeito colateral e escritas fora dos services.** O download do pacote da prestação cria
    RT e diário se faltarem (`gestao/viagens/pacote_prestacao.py:84-92`); o download do protocolo de
    pagamento do Coffee grava o atesto (`gestao/coffee/protocolo.py:137-160`); `viagem_conferencia.aplicar`
    grava OS, termo e plano por `QuerySet.update`, sem os services nem checagem de versão
    (`gestao/viagens/viagem_conferencia.py:345-382`). Automação não pode tratar esses caminhos como leitura.

### 6.5 Dados que não fluem entre módulos

13. **A solicitação não alimenta a viagem.** `de_eventos.gerar` propaga só título, período, destino,
    motivo e tipos; ignora serviços (mesmo catálogo do plano, ADR 0044 ainda não commitada), unidade
    móvel, motorista, quantidades/equipes e protocolo (`gestao/viagens/de_eventos.py:121-155`). Não há
    horário nem programação estruturados na solicitação; o roteiro nasce vazio e o lote exige roteiro
    (`gestao/viagens/viagem_lote.py:96-100`). `Viagem.situacao` só vira GERADOS pelo lote: não serve de
    gatilho (use prontidão e datas).
14. **Cancelamentos e decisões não se propagam.** Solicitação ou palestra cancelada deixa a OS de coffee
    ativa (`gestao/coffee/ganchos.py:93-105`); a decisão da DG não volta à palestra
    (`gestao/palestras/encaminhamento.py:63-98`); reeditar uma solicitação deferida não sincroniza a
    viagem (`gestao/eventos/solicitacoes.py:177-212`). Coffee, Palestras, Imprensa e Publicações não
    emitem notificações nem têm rotinas.
15. **Disponibilidade não existe como dado.** O lote só checa duplicidade dentro da viagem
    (`gestao/viagens/viagem_lote.py:44-73`); conflitos entre viagens aparecem depois como aviso; não há
    férias, afastamentos ou escalas.

### 6.6 Recebimento e leitura de documentos

16. **A importação documental é a base certa, com defeitos conhecidos.** Fila com conversão e OCR
    locais e revisão humana (ADR 0041), porém: comprovante importado entra sem valor, data e operação,
    e a divergência "soma ≠ diária" fica cega (`gestao/viagens/importacao.py:306-313`;
    `gestao/viagens/anexos.py:103-104`); "Usar no comprovante" descarta Transferência e Depósito
    (`gestao/viagens/anexos.py:212`, defeito confirmado); comprovante avulso nunca casa sozinho
    (`gestao/viagens/dominio/importacao.py:173-181`); o texto/OCR não é persistido
    (`gestao/viagens/models.py:1883-1900`); a conferência de assinatura só cobre `ViaAssinada`
    (`gestao/viagens/assinados.py:250-253`); separar partes pode perder a assinatura criptográfica
    (plausível, `gestao/viagens/documentos/importador.py:249-255`); "PLANO DE TRABALHO" não é
    reconhecido; limites por destino diferem (importação 25 MB, via assinada 15 MB, anexo 10 MB). No
    Coffee, a leitura de PDFs fica fora da importação e a via assinada só confere PDF e tamanho
    (`gestao/coffee/vias.py:62-85`).

### 6.7 Rotas e quilometragem

17. **Km estimado vira "previsto" sem marcação.** A integração de rotas está em `gestao/viagens/rotas.py`
    (fora de `gestao/integracoes`, contra a ADR 0019) e a view chama a rede de forma síncrona: até 11
    consultas de até 4 s, sem limitação de taxa (`gestao/viagens/views.py:1270, 1286-1293`). Produção não
    tem provedor definido; o PREVIEW usa o servidor público de demonstração do OSRM. A fonte do km não
    fica no trecho, e a estimativa (linha reta × 1,3; 0 km sem coordenadas) é usada na conferência de
    20 % do hodômetro (`gestao/viagens/dominio/diario.py:17-21, 82-86`), gerando avisos falsos. Decisões a
    preservar: tempos calibrados (ADR 0016), cache versionado (ADR 0024), roteiro é cópia (ADR 0015).

### 6.8 IA

18. **Nenhuma IA executa hoje** em nenhum dos três sistemas: não há SDK de LLM no novo nem no GV; no EV
    o app "assistente" existiu no Git em 20–21/09/2026 (`EVG@5f939ba`) e foi removido (`EVG@f62c2cb`);
    a menção a um "assistente Gemini" não tem respaldo no código examinado. Restrições já registradas:
    a ADR 0041 veda enviar documentos a IA externa na importação; a ADR 0020 proíbe o n8n de gravar no
    banco ou guardar regra; a trilha de auditoria registra dados pessoais (CPF, telefone) das
    alterações, então não deve ser exposta a n8n nem a LLM. A regra do EV que sugere RT
    afirma "Não houve intercorrências…" sem dado (`EVI/viagens_prestacoes/rt_services.py:466`): é o
    tipo de declaração falsa que qualquer rascunho por IA precisa evitar. IA local na VPS concorreria
    com o OCR (2 vCPU; ver [capacidade-vps.md](../ops/mudanca-hospedagem/capacidade-vps.md)).
    Reaproveitável: bateria de 560 casos fictícios com gabarito "não invente"
    (`EVI/core/leitura/tests/bateria/__init__.py:1-30`) e o desenho removido do assistente, que já
    seguia IA → ferramenta tipada → política → aprovação (ADR 0020).
19. **Regras que ficam determinísticas.** Justificativa por antecedência (prazo padrão de 10 dias
    corridos no GV, `gv/justificativas/services.py:22-28`), diárias (no novo, `gestao/viagens/dominio/diarias.py`;
    no GV, valor × efetivo em snapshot), diária recebida ≤ liberada, data do RT = retorno + até 3 dias
    úteis, pendências do consolidado, carimbo por âncora de texto. Finalizar a prestação sem pré-condição
    é decisão travada por teste no GV (`gv/docs/REGRAS_DE_NEGOCIO.md:230-235`): automação não finaliza.
    O sistema só sabe que liberação e prazo de saque foram **digitados** — não presumir pagamento.

### 6.9 Operação

20. **Falha silenciosa de fila é o risco operacional recorrente.** Na referência GV, a fila de
    espelhamento do Drive deixou de ser consumida em 26/08/2026 sem alerta; como as tarefas carregam só
    ids e o organizador relê o estado, a reconciliação pelo banco é viável (decisão D3 do plano). No
    novo, o serviço importador fica fora dos scripts de monitoramento, backup e reinício
    (`deploy/vps/monitorar.sh:15`; `deploy/vps/backup.sh:65`; `deploy/vps/pcpr.sh:92`) e `/saude/` não
    reflete worker nem rotinas. A lista de prestações é a página mais pesada do PREVIEW (848 KB, até
    1,3 s de servidor, medição de 17/10/2026) e deve ser paginada antes de servir a automações.
21. **Lições das referências para gatilhos e destinatários.** No GV, status intermediários do Evento e
    `enviada/aprovada/reprovada` da prestação nunca mudam sozinhos: não servem de gatilho. O signatário do
    DB no GV é o motorista do ofício, não o efetivo do diário (`gv/prestacoes_contas/assinatura_services.py:44-46`):
    um link automático iria à pessoa errada. No EV, o eProtocolo simulado gera números SIMULADOS para todo
    ofício salvo sem protocolo (`EVI/config/settings.py:319-332`): automação deve tratá-los como não
    oficiais. Conceitos a preservar sem copiar código: idempotência por objeto + campo, artefato
    imutável com hash e snapshot, versões assinadas append-only com revogação, link público com token,
    expiração e limite de tentativas, carimbo por âncora de texto, lista única de pendências, trava para
    mutação real no eProtocolo, fila separada para trabalho pesado e diagnóstico sem rede.

## 7. Dúvidas em aberto

Consolidadas das 93 dúvidas das leituras. "Origem" indica as leituras que levantaram a dúvida. Dúvidas
sobre configuração interna dos servidores de produção ficaram fora deste documento público.

| # | Dúvida | Origem | Situação |
|---|---|---|---|
| **A. Canais, identidade e consentimento** | | | |
| A1 | Qual canal oficial a PCPR usará para mensagens a servidores e solicitantes? Há SMTP/relay institucional autorizado (domínio, remetente, quem aprova, limites)? Haverá um portal mínimo do servidor? | prestacao, plataforma, outros-modulos, gv, ev | Respondida em parte: plataforma oficial do WhatsApp bloqueada (fato 1), com o WhatsApp como prioridade do usuário nas frentes WA-1 a WA-3 (D4 do plano; aparelho e número institucionais na D4a). E-mail institucional e portal em aberto (D4) |
| A2 | Servidores consentem receber mensagens no contato cadastrado? Onde registrar consentimento e preferência de canal (LGPD)? Como contatar o motorista 'pessoa não cadastrada'? | viagens-nucleo, outros-modulos | Aberta |
| A3 | Quem é o 'usuário representado' das automações: o operador responsável pela viagem, uma conta de serviço por unidade ou o próprio servidor identificado? | plataforma, outros-modulos | Aberta. Regra já fixada no contrato (rascunho 3): ninguém declara quem representa; a máquina age só com delegação emitida pelo PCPR no momento da ação humana, e clientes MCP usam credencial do próprio usuário ([`api-automacao.v1.yaml`](contratos/api-automacao.v1.yaml)) |
| A4 | Quem aprova ações irreversíveis vindas da automação (gestor da unidade, operador emissor, ASCOM)? | plataforma | Aberta |
| A5 | Quem deve receber os avisos automáticos internos: só OPERADOR_VIAGENS, como hoje, ou também gestor, coordenador do plano e motorista? | viagens-nucleo | Aberta |
| A6 | Qual o canal oficial de entrada de demandas (caixa de e-mail por módulo, formulário público, eProtocolo)? Órgãos externos (prefeituras, escolas) pedem eventos diretamente ou continuam pela ASCOM/DG? | outros-modulos | Aberta |
| **B. Prestação de contas e assinatura** | | | |
| B1 | Qual é o texto oficial da 'mensagem de saque': o aviso de liberação de diárias do GV ('… PRAZO IMPRORROGÁVEL') ou outro? | prestacao, ev | Aberta (o fluxo 10-3 parte do texto do GV) |
| B2 | De onde vêm o nº da solicitação, a data de liberação e o prazo de saque, quem os obtém e quando? Há API ou arquivo estruturado? 'Central de Viagens' é o sistema estadual ou o próprio GV ('Central de Viagens 3')? | prestacao, viagens-nucleo, plataforma, gv | Aberta |
| B3 | Prazos institucionais: início e conclusão da prestação, antecedência do lembrete de saque, '3 dias úteis após o saque' (EV) é norma ou implementação? Feriados (de qual calendário) entram no prazo e na data do RT? | prestacao, gv, ev | Aberta |
| B4 | Que assinatura é válida para DB e RT (física digitalizada, gov.br, ICP-Brasil, eProtocolo ou a assinatura eletrônica simples por link do GV)? Quem assina o DB: o motorista efetivo do diário ou o do ofício? | prestacao, gv, ev | Aberta (ver fato 3) |
| B5 | Por qual canal os assinados voltam hoje (eProtocolo, e-mail, WhatsApp, papel)? Existe caixa institucional dedicada que possa ser lida por IMAP? | prestacao, plataforma | Aberta |
| B6 | Quem aprova ou devolve a prestação? Para onde vai o PDF final? O andamento do protocolo no eProtocolo indica aprovação? | prestacao, plataforma, gv | Aberta |
| B7 | O DB de motorista 'de outro ofício' deve citar o ofício da equipe, o do motorista ou ambos? | prestacao | Aberta |
| **C. Link de quilometragem** | | | |
| C1 | Quem preenche o km pelo link (só o motorista ou a equipe)? A que horas sai na véspera? Quais campos por trecho (hodômetro, abastecimento)? Por quantos dias vale? Como o operador recebe os km hoje? | prestacao, plataforma, gv | Aberta (decisão "regras institucionais" do plano, hoje D7; fluxo 10-4) |
| C2 | O link do diário no celular do EV é usado em produção (quantos links e lançamentos existem)? | ev | Aberta |
| **D. Viagem, ofício e plano** | | | |
| D1 | Qual a ordem institucional entre abrir protocolo, emitir, assinar e enviar o ofício? Quem assina ofício e plano, por qual meio, e o plano assinado volta ao sistema? | viagens-nucleo, planos-rotas | Respondida em parte: no GV a assinatura digital de ofícios é feita no eProtocolo (fato 3) |
| D2 | A viagem deve ser gerada automaticamente no deferimento (como na referência) ou continuar por botão (decisão E4)? O Coffee deve ser pedido automaticamente em algum tipo de evento? | viagens-nucleo, outros-modulos | Aberta |
| D3 | O lote ou a proposta devem bloquear em conflito de agenda ou cadastro incompleto, ou só avisar? Existe fonte oficial de férias, afastamentos e escalas? | viagens-nucleo | Aberta |
| D4 | Há norma para horário de saída e pernoite na véspera, antecedência entre chegada e atendimento, e critério bate-volta × pernoite? | planos-rotas, viagens-nucleo | Aberta |
| D5 | Termo, OS e plano devem ganhar versão congelada ao serem enviados para assinatura? Um plano gerado pode continuar sendo alterado, ou precisa de reabrir/retificar com motivo? | viagens-nucleo, planos-rotas | Aberta |
| D6 | Os termos do lote devem usar o título da viagem como evento, ou o padrão 'PCPR na Comunidade' é intencional? | viagens-nucleo | Aberta |
| D7 | A base legal da justificativa (Decreto 6.358/2024) e o prazo padrão de 10 dias valem para todas as unidades? | viagens-nucleo | Aberta |
| D8 | Plano: diárias só pelo destino principal? O texto fixo 'PCPR na Comunidade' vale para todo programa? Serviços da solicitação substituem ou somam ao conjunto padrão? ProgramaSolicitante corresponde ao órgão da solicitação? Plano sem assinante vira pendência? Há prazo e responsável para lançar resultados? Uma viagem pode agregar várias solicitações? | planos-rotas | Aberta |
| D9 | A programação/horários do evento existem estruturados em algum lugar? 'Equipe' (Alfa, Bravo…) é um grupo fixo de servidores? | planos-rotas, outros-modulos | Aberta |
| **E. IA** | | | |
| E1 | Qual provedor de LLM é aceitável e com que política de dados (LGPD; nomes, CPF, telefone, viagens, conteúdo policial)? IA externa ou local? É possível exigir provedor sem retenção? Respostas à imprensa podem ter rascunho por IA? | planos-rotas, prestacao, viagens-nucleo, plataforma, outros-modulos | Aberta (decisão "provedor de IA" do plano, hoje D8) |
| E2 | Existe base normativa ou FAQ aprovada (manual de diárias, portarias) para alimentar um assistente de dúvidas, e quem a mantém? | gv, ev | Aberta |
| E3 | De onde vem a menção a um 'assistente Gemini' no EV? Não há código nos repositórios examinados; o app 'assistente' chegou a rodar em 20–21/09/2026? | outros-modulos, ev | Aberta (exige conferência no servidor, sem acesso nesta auditoria) |
| **F. Integrações institucionais e externas** | | | |
| F1 | eProtocolo: há credenciais de treinamento emitidas? Os endpoints v3 foram validados com a documentação oficial? Qual o ambiente efetivo do GV em produção? | plataforma, gv | Aberta (decisão "credenciais do eProtocolo e da Central" do plano, hoje D9) |
| F2 | Houve contato com DETO/SEAP/Celepar sobre API da Central de Viagens? | plataforma | Aberta |
| F3 | Qual é a 'fonte dedicada' de cadastros (sistema de pessoal do Estado?), por qual meio (API, arquivo, banco) e de quais campos ela seria dona? | outros-modulos | Aberta |
| F4 | Qual provedor de rotas em produção (OSRM próprio, OpenRouteService com a chave do GV, estimativa) e qual está ativo no PREVIEW? Um OSRM próprio cabe na VPS ao lado do n8n? | planos-rotas, gv | Aberta (fluxo 11-1). Respondido em parte: as chaves do ORS valem no host novo `api.heigit.org/openrouteservice`; o host antigo será desligado em 02–06/11/2026 ([desempenho-e-custos §14.6](desempenho-e-custos.md)) |
| F5 | O site da PCPR/AEN oferece RSS ou sitemap estável para detectar matérias publicadas? | outros-modulos | Aberta |
| F6 | Quem consome as pastas do Google Drive do GV (exigência institucional ou conveniência)? Em que modo o espelho roda em produção? Isso decide se o espelho existe no sistema novo | gv | Aberta (decisão D3 do plano) |
| **G. Operação e plataforma** | | | |
| G1 | Qual o fuso do host e quais timers (rotinas, monitor, backup, teste de restauração) estão instalados no PREVIEW publicado? | prestacao, viagens-nucleo, plataforma | Aberta |
| G2 | O n8n roda na mesma VPS ou em outra máquina? Quem administra a interface e com qual controle de acesso? | plataforma | Respondida em parte: recomendação em hospedagem-n8n.md (decisão D2 do plano) |
| G3 | A produção do sistema novo usará o PostgreSQL em contêiner ou o PostgreSQL nativo da VPS? | plataforma | Aberta |
| G4 | Qual retenção para outbox, notificações e auditoria (a trilha é imutável e cresce sem limite)? | plataforma | Aberta |
| **H. Demais módulos e referências** | | | |
| H1 | Quais prazos usar nos lembretes ainda inexistentes (palestra aguardando retorno há N dias, D-x do palestrante, certidão 15/7/1 dias)? | outros-modulos | Aberta |
| H2 | O efeito 'baixar o pacote do protocolo de pagamento registra o atesto' deve continuar? | outros-modulos | Aberta |
| H3 | Os status do Evento no GV (em execução, finalizado) devem mudar por data ou continuar manuais? | gv | Aberta |
| H4 | Os 3 templates fora do Git na árvore implantada do EV ainda são renderizados por alguma view? | ev | Aberta |

## 8. Documentação desatualizada encontrada

Conferida contra a árvore de 17/10/2026. Nenhum destes arquivos foi alterado por este inventário.

| Documento | O que diz | O que o código ou o fato mostra |
|---|---|---|
| `docs/product/workflows.md:26` | Protocolo não informado "não bloqueia (aviso)" | A emissão é bloqueada sem protocolo (`gestao/viagens/services.py:517-519`); a própria `workflows.md:78` e `documents.md:138` dizem que bloqueia |
| `docs/product/workflows.md:77-78` | Cancelamento é terminal, sem reativar, não há arquivar | Existem reativar e arquivar (`gestao/viagens/services.py:1175-1225`) |
| `docs/product/workflows.md:80, 103, 120, 127, 134, 143` | Eventos, Coffee Break, Palestras, Publicações/Imprensa, Viagem e Prestação "(Planejado)" | Implementados (seção 3) |
| `docs/product/workflows.md:98` | Falha na geração da viagem "notifica com Tentar de novo" | Não existe; a geração é por botão (`gestao/viagens/de_eventos.py`) |
| `docs/product/modules.md:35-37` | Ofícios: faltam arquivar, reativar, motorista externo, termos, assinatura, eProtocolo | Implementados (eProtocolo parcial) |
| `docs/product/modules.md:69, 79, 89, 100, 108-116` | Demais submódulos de Viagens, Eventos Sociais, Coffee Break, ASCOM, Agenda e Relatórios "Planejado" | Implementados (o arquivo tem alterações locais não commitadas; conferido na árvore de 17/10) |
| `docs/product/documents.md:9-19, 117` | Termo, OS, PT, RT, Diário, consolidado, documentos do Coffee, pauta, exportações e assinatura "Planejado" | Implementados; upload e conferência de via assinada existem (ADR 0022) |
| `docs/adr/0005-outbox-transacional.md:13-14` e `docs/product/integrations.md:8-9` | Backoff "5 s → 1 h"; falha "visível ao administrador" | Efetivo 10 s → 640 s (~21 min); sem tela (`gestao/plataforma/outbox.py:34, 72-73, 108-111`) |
| `docs/product/integrations.md:32` | Leitura de processo eProtocolo (PDF) "Planejado" | Importação documental com fila implementada em Viagens (ADR 0041) |
| `docs/product/integrations.md:36` | Assinatura de documentos "Não implementado" | Upload de via assinada, conferência e revogação existem (`gestao/viagens/assinados.py`) |
| `docs/product/integrations.md:37` | OpenRouteService "Não implementado" | Adaptador existe (`gestao/viagens/rotas.py:109-116`) |
| `docs/product/integrations.md:39-42` | Leitura de e-mail, OCR, leitura de NF/certidões e ICS "Não implementado" | Existem (`gestao/plataforma/leitura_email.py`; OCR no importador; `gestao/coffee/dominio_leitura.py`; `gestao/painel/views_agenda.py:167-218`) |
| `docs/product/integrations.md:43` | WhatsApp "Não implementado"; "webhook a confirmar" | Há links `wa.me` (parcial); webhook/Platform bloqueado pela política (fato 1) |
| `docs/product/integrations.md:47-52` | "Não há agendador no código atual"; lista de tópicos sem `plataforma.email.enviar` | Há middleware de rotinas, comando `rodar_rotinas_diarias` e timer `pcpr-rotinas` |
| `docs/ops/rotas.md:8` | `ROTAS_TIMEOUT` padrão 6 s | Padrão no código: 4 s (`config/settings/base.py:227`) |
| `docs/migration/planos.md:100-101, 126` | Número do plano "só automático"; número manual "permanece lacuna" | Número editável (`gestao/viagens/planos.py:433-447`; `docs/product/planos-refinamento.md:47-52`) |
| `docs/migration/prestacao.md:185` | Assinatura eletrônica do diário e do RT: "nem a referência tem" | O GV em produção tem (fato 3, `gv/prestacoes_contas/assinatura_services.py:1-9`); o EV removeu |
| `docs/integrations/eprotocolo.md:87-89` | A abertura "publica na outbox (`integracoes.eprotocolo.abrir`)" | Desenho, não estado: o tópico não existe e `AdaptadorHttp.abrir` sempre recusa (`gestao/integracoes/eprotocolo/adaptadores.py:177-187`) |
| `docs/automacao/plano-implantacao.md` (decisão D4, canal com os servidores) | Opção "WhatsApp só com autorização formal" | **Corrigido no plano:** a D4 diz que o WhatsApp é prioridade (frentes WA-1 a WA-3): já, o assistido com registro; a plataforma oficial só com autorização escrita da Meta, porque a política a proíbe (fato 1) |
| `docs/integrations/orquestracao.md:8`; `docs/ai/README.md:34` | n8n com notificações por WhatsApp; WhatsApp entre as integrações previstas | Bloqueado (fato 1) |
| Referência GV: `gv/prestacoes_contas/assinatura_services.py:3-5` | Docstring: "5 primeiros dígitos do CPF" | O código exige o CPF completo (`:187-199`); vale o comportamento do código |
| Referência EV: `EVI/.env.example:47-80` | Documenta variáveis do assistente e do WhatsApp | Nenhum código implantado as lê (app e canal removidos) |
