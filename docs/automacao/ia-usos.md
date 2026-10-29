# Usos de IA — o que entra, o que nunca entra, provedor e alternativa

Decisão estrutural: [ADR 0048](../adr/0048-ia-porta-orcamento-e-sugestoes.md). Código: porta em
`gestao/integracoes/ia/`, contexto em `gestao/assistencia/`, usos em `gestao/<app>/ia_usos.py`.
Situação em 18/10/2026. Sistema de testes com dados fictícios.

**Legenda da situação** — *implementado*: código e tela existem; *testado no simulador*: os testes
automatizados exercitam o caminho de IA com os adaptadores simulado e gravado (nenhum teste chama
um provedor); *não validado com o provedor real*: nenhuma chamada real foi feita (nenhuma chave foi
usada). Todo uso começa no modo **regra** (sem IA); o modo IA é escolhido por uso, em Assistência ›
Usos, e mesmo nele a porta é **simulada** sem `IA_MODO=anthropic` + `IA_API_KEY` (e nunca no PREVIEW).

Valem para todos: só o worker `processar_ia` chama a porta; orçamento reservado antes (teto global e
por uso), anotado no pedido e devolvido se o worker morrer entre reservar e liquidar
(`orcamento.liberar_reservas_presas`, no laço do worker a cada 5 min e na rotina diária, depois
do prazo da chamada + 10 min); limites de entrada, saída, tempo, tentativas e chamadas por dia; saída em esquema fechado
e validador de fatos; queda na regra quando algo falha; sugestão sempre revisada (aceitar, editar,
descartar), com fontes e lacunas; obsolescência pela versão da fonte; texto humano só é substituído
com confirmação; conteúdo com retenção de 30 dias, fora da trilha.

| Uso (chave) | Entra (campos do sistema) | Nunca entra | Provedor | Alternativa sem IA | Grava? | Testes | Situação |
|---|---|---|---|---|---|---|---|
| **AUT-50** RT (`viagens.rt_rascunho`) | título e descrição da viagem, motivo do ofício (mascarados), destinos, período, atividades e resultados lançados no plano, relato escrito no pedido (mascarado) | nomes, CPF, RG, telefone, e-mail, placa/viatura, valores e diárias, protocolo, coordenação, assinatura | simulado/gravado; Anthropic se configurado | descrição, objetivo e conclusão montados dos fatos (`deterministico`); conclusão só com resultados lançados | sim — `relatorio.salvar`, com trava e versão | regra, aceitar, editar, texto humano, obsolescência, IA válida/inválida (5 casos), injeção, orçamento, limite diário, fora de transação, simulado sem custo | implementado · testado no simulador · não validado com o provedor real |
| **AUT-81** ofício (`viagens.oficio_textos`) | título, tipos e descrição da viagem, destinos, período, data do ofício, primeira saída, dias de antecedência, prazo (regra do sistema), situação do prazo, orientação do pedido | os mesmos do RT | idem | motivo e justificativa com as datas do próprio ofício; motivo da urgência só se escrito no pedido (senão, lacuna) | sim — `services.salvar_dados` | justificativa com datas, lacuna sem orientação, motivo humano exige confirmação, pendência some | implementado · testado no simulador · não validado |
| **AUT-80** plano (`viagens.plano_textos`) | título e descrição da viagem, destinos, programas, período, atividades escolhidas, orientação do pedido | os mesmos + efetivo | idem | contextualização e considerações só com os fatos (sem "ribeirinhos", "vulneráveis"…) | sim — só os dois campos (`update_fields`), automático desligado | aplica sem reescrever o plano | implementado · testado no simulador · não validado |
| **AUT-89** pendências (`viagens.explicar_pendencias`) | itens do quadro de conferência da viagem por etapa, com nomes trocados por "[servidor da equipe]" | os mesmos | idem | o quadro reescrito por etapa ("Em X, falta…") | não (só leitura) | só lê; nenhum item aplicável | implementado · testado no simulador · não validado |
| **AUT-76** programação (`viagens.leitura_programacao`) | texto colado no pedido (mascarado), sede, ano | os mesmos; o esquema não tem distância, tempo nem diária | idem | leitor por regra: municípios do cadastro IBGE por linha, datas e horários do texto | não (proposta para conferir) | cidades/datas/horas do texto, município conferido; IA que inventa cidade, data ou distância cai na regra | implementado · testado no simulador · não validado |
| **AUT-57** importação (`viagens.importacao_tipo`) | texto extraído da parte (mascarado), destinos possíveis da pessoa (chave, tipo, número/ano) | os mesmos + o arquivo | **simulado/gravado apenas** — o adaptador real recusa documento (ADR 0041) | classificador local (`tipo_do_texto` + `identificar`) | não (aplica-se na revisão da importação) | tipo pela regra; parte de outra pessoa é recusada | implementado · testado no simulador · **provedor real bloqueado por política** |
| **AUT-58** comprovante/NFS-e (`viagens.leitura_comprovante`) | texto extraído do comprovante (mascarado) | os mesmos + o arquivo e dados bancários | **simulado/gravado apenas** (ADR 0041) | `leitura_anexos.ler_comprovante` | não | leitura por regra; adaptador real recusado sem chamada de rede nem reserva de orçamento | implementado · testado no simulador · **provedor real bloqueado por política** |
| **AUT-86** catálogo (`cadastros.atividade_complemento`) | nome e código da atividade | nomes de pessoas, valores, fornecedores | idem | meta/recursos genéricos sem número (lacuna "quantidade") | sim — `cadastros.services.salvar_atividade`, só campos vazios sem confirmação | sugere só o vazio e aplica | implementado · testado no simulador · não validado |
| **AUT-88** assistente (`assistente.responder` + `assistencia.reformular_resposta`) | resposta determinística e pergunta (mascarada) | nomes, CPF, telefone, e-mail; saúde, vítimas e ocorrências são recusadas antes | idem (só a reformulação) | `responder()` determinístico: Central de ajuda + "minha situação" | não | gabarito (13 perguntas), situação do servidor, reformulação que muda número cai na regra | implementado (determinístico e reformulação) · testado no simulador · não validado |
| **AUT-93** triagem (`assistencia.triagem_modulo`) | demanda em texto (mascarada) | os mesmos | idem | pontuação por sinais por módulo; empate → sem sugestão | não | sugere o módulo; só a pessoa que pediu vê | implementado · testado no simulador · não validado |
| **AUT-97** Central de ajuda | 8 artigos aprovados (`gestao/assistencia/conhecimento/*.md`) | — | nenhum (sem IA) | é a própria alternativa | não | busca, natureza, artigo, 404 | implementado (conteúdo inicial **pendente de revisão do responsável**) |
| **AUT-91** gabarito | 19 casos do validador, 5 de leitura, 13 do assistente (fictícios) | — | — | — | — | `manage.py avaliar_ia` e `test_dominio.py` | implementado (38/38 na regra) |
| AUT-92 extração de pedidos | — | — | — | — | — | — | **não feito** (depende do leitor de entrada AUT-132, inexistente) |
| **AUT-94** nota do mês (`painel.nota_executiva`) | mês e, por módulo, o número do mês no relatório consolidado, com a permissão de quem pede | nomes, listas de eventos e cidades, contatos | simulado/gravado; Anthropic se configurado | "Em MM/AAAA, o relatório consolidado registra: …" só com os números | não | regra; número inventado cai na regra; nota é só de quem pediu | implementado · testado no simulador · não validado (sem botão na tela de relatórios: acesso por `/assistencia/pedir/painel.nota_executiva/<usuário>:<ano>-<mês>/`) |
| AUT-171 resumo do eProtocolo | — | — | — | — | — | — | **não feito** (depende da consulta real, AUT-120) |

## O que ninguém pode pedir à IA (e como o sistema garante)

| Proibido | Garantia |
|---|---|
| Escolher equipe, motorista ou viatura | Nenhum esquema tem esses campos; "motorista"/"viatura" no texto sem estar nos fatos reprova |
| Inventar km, pagamento, atividade ou valor | Número fora dos fatos, "R$", "diária", "km" reprovam; atividade do catálogo fora do plano reprova |
| Calcular diárias por linguagem natural | Não há campo nem ferramenta; diárias continuam com o motor do ofício |
| Emitir, cancelar, assinar, aprovar prestação, decidir despacho | Não existe ferramenta de escrita; `aplicar` só grava os campos de texto do uso, pelo serviço do contexto |
| Seguir instrução escondida em anexo/mensagem | Dados em blocos `<dados>` neutralizados; saída fechada; validador |

## Para ligar um provedor real (não feito)

1. `IA_MODO=anthropic`, `IA_API_KEY` (e, se quiser, `IA_MODELO`) no servidor — nunca no PREVIEW.
2. `python manage.py avaliar_ia` verde e o uso em modo IA em Assistência › Usos.
3. Teto mensal definido (global e, se quiser, por uso). A fatura do provedor é a fonte do custo real.
4. Documentos (AUT-57/58) continuam bloqueados até uma ADR nova.

## Obsolescência e entradas nas telas (revisão de 18/10/2026)

| Uso | Fonte da versão (`versao_atual`) | Entrada na tela dona |
|---|---|---|
| AUT-50 RT | viagem, ofício, plano e os três textos do RT | cartão na folha do RT |
| AUT-81 ofício | datas, destinos, prazo e os textos do ofício | cartão na folha do ofício |
| AUT-80 plano | destinos, programas, período, atividades e os dois textos | cartão na folha do plano |
| AUT-89 pendências | quadro de conferência da viagem | cartão na folha da viagem |
| AUT-76 programação | sede e ano do ofício (o texto colado é do pedido e não muda) | link no cartão do ofício |
| AUT-57 importação | texto da parte, destinos possíveis e a revisão da parte (tipo, destino, estado) | cartão na revisão da importação (`importacao/revisao.html`) |
| AUT-58 comprovante | texto do comprovante | link em cada comprovante da leitura e conferência (`prestacao/leitura.html`) |
| AUT-86 catálogo | nome, código, meta e recursos da atividade | link nas atividades sem recursos (`cadastros/catalogo.html`) |
| AUT-88 reformulação | a resposta determinística refeita com a pergunta guardada (muda quando a Central muda) | botão na Central de ajuda (só no modo IA) |
| AUT-93 triagem | **sem** `versao_atual`: não há registro de origem; o recurso é o hash do próprio texto | nenhuma tela de entrada de demandas existe ainda (AUT-132) |
| AUT-94 nota do mês | o relatório consolidado refeito com a permissão de quem pediu | cartão em `painel/relatorios.html` (ano corrente) |

AUT-93 agora exige, na saída da IA, `sinais`: até 3 palavras copiadas do texto; o validador
recusa módulo fora da lista, módulo sem sinal citado, sinal que não está no texto e sinal que não
é daquele módulo, e "sem módulo" sem a lacuna `sem_sinal`.
