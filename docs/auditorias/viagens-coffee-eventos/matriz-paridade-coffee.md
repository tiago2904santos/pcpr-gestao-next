# Matriz de paridade funcional — Coffee Break

Legado: `Sistema-de-Gest-o-de-Eventos-Sociais` @ `53dbf3f`, app `coffee_break/` (e o que usa:
`core`, páginas públicas, e-mails, link do fornecedor, importações). Novo: `gestao/coffee`.
O legado foi **lido**, não executado. Abreviações: L = `coffee_break/` do legado,
N = `gestao/coffee/`, D = `docs/migration/`.

Situações como na matriz de Eventos. "Situação final" é atualizada a cada lote.

| ID | Funcionalidade | Evidência no legado | Equivalente no novo | Situação inicial | Diferença | Situação final / evidência |
|---|---|---|---|---|---|---|
| CB-F01 | Acesso ao módulo | L/permissions.py:1-38 | N/policies.py:8-10 | Substituída | permissão `acessar_coffee` (D/decisoes.md:281) | Substituída |
| CB-F02 | Administração do módulo | L/permissions.py:28-38 | N/policies.py:18-21 | Equivalente | — | Equivalente |
| CB-F03 | Menu do módulo | L/apps.py:40-86 | N/navegacao.py | Equivalente | sem "Textos" (CB-F16) | Equivalente |
| CB-F04 | Tela única de cadastros (abas, busca, 25/pág., janela, versão) | L/views.py:1850-1982 | N/views.py:188-229 | Equivalente | — | Equivalente |
| CB-F05 | Fornecedor | L/models.py:31-90 | N/forms.py:97-120 | Equivalente | — | Equivalente |
| CB-F06 | Resumo de entregas do fornecedor | L/presenters.py:233-249 | N/views.py:127-134 | Equivalente | — | Equivalente |
| CB-F07 | Contrato | L/models.py:93-161 | N/models.py:62-112 | Equivalente | — | Equivalente |
| CB-F08 | Selo vigente/vencido | L/presenters.py:310-359 | N/views.py:135-149 | Equivalente | — | Equivalente |
| CB-F09 | Atalho para o relatório na lista de contratos | spec §2.2 | — | Ausente | — | |
| CB-F10 | Termo aditivo | L/models.py:164-190 | N/forms.py:150-170 | Equivalente | — | Equivalente |
| CB-F11 | Contrato/aditivo lidos do PDF | L/contratos_pdf.py | N/contratos_pdf.py | Equivalente | heurísticas não comparadas com PDFs reais | Equivalente |
| CB-F12 | Lote | L/forms.py:566-603 | N/forms.py:173-219 | Equivalente | — | Equivalente |
| CB-F13 | Municípios do lote | L/forms.py | lista digitada validada | Substituída | D/decisoes.md:282 | Substituída |
| CB-F14 | Configuração do ofício/protocolo/e-mails | L/models.py:193-286 | N/views.py:305-318 | **Defeito** | corrida de versão (`CadastroEmUso`) não tratada → erro 500 || **Corrigida** — a corrida volta como erro do formulário (422), não 500 (`test_configuracao_salva_por_outra_pessoa_nao_da_erro_500`) |
| CB-F15 | Recusar excluir cadastro em uso | L/views.py:1965-1982 | N/services.py:50-60 | Equivalente | — | Equivalente |
| CB-F16 | Textos-base dos documentos editáveis | L/editor.py:100-190 | — | Substituída | D/decisoes.md:286 | Substituída |
| CB-F17 | Edição na folha A4 | L/editor.py:383-404 | — | Substituída | D/decisoes.md:286 | Substituída |
| CB-F18 | Lote pelo município | L/services.py:561-625 | N/dominio_pedido.py:72-82 | Equivalente | — | Equivalente |
| CB-F19 | Cidade mais próxima | idem | N/dominio_pedido.py:83-95 | Equivalente | — | Equivalente |
| CB-F20 | Lote mostrado ao escolher o município | L/views.py:784-811 | N/_lote.html | Equivalente | — | Equivalente |
| CB-F21 | Lote só muda com o município; preço congelado | L/forms.py:213-231 | N/pedidos.py:105-113 | Equivalente | — | Equivalente |
| CB-F22 | Saldo conferido com trava | L/services.py:55-106 | N/pedidos.py:131-134 | Equivalente | — | Equivalente |
| CB-F23 | Quantidade faturada | L/views.py:1351-1365 | N/financeiro.py:112-130 | Equivalente | — | Equivalente |
| CB-F24 | Selo de consumo, valor da OS | L/presenters.py:270-279 | N/dominio_pedido.py:102-122 | Equivalente | — | Equivalente |
| CB-F25 | Numeração da OS compartilhada com Viagens | L/services.py:668-760 | N/queries.py:118-123 | Parcial | **decisão pendente do usuário** (D/decisoes.md:320) | Pendente (decisão) |
| CB-F26 | Ano do número da OS ao editar | L/forms.py:123-159 | N/pedidos.py:130 | **Defeito** | usa o ano da data da solicitação: "5/2025" vira "5/2026" || **Corrigida** — na edição vale o ano do número que a OS já tem (`test_editar_mantem_o_ano_do_numero`) |
| CB-F27 | Número repetido / reserva | L/services.py:747-782 | N/pedidos.py:57-69 | Equivalente | — | Equivalente |
| CB-F28 | Numeração do ofício | L/services.py:683-720 | N/financeiro.py:54-101 | Parcial | sequência própria (como CB-F25) | Pendente (decisão) |
| CB-F29 | Vigência bloqueia o pedido | L/forms.py:233-256 | N/pedidos.py:98-120 | Equivalente | — | Equivalente |
| CB-F30 | Retroativo + justificativa | L/forms.py:343-362 | N/dominio_pedido.py:174-180 | Equivalente | — | Equivalente |
| CB-F31 | Aviso de antecedência | L/services.py:524-539 | N/dominio_pedido.py:183-193 | Equivalente | — | Equivalente |
| CB-F32 | Trava de versão da OS | L/forms.py:190-198 | N/forms_pedido.py:118-119 | Equivalente | — | Equivalente |
| CB-F33 | Descrição em uma linha; CEP | L/forms.py:119-121 | N/pedidos.py:124 | Equivalente | — | Equivalente |
| CB-F34 | Uma data por OS | L/forms.py:160-176 | — | Substituída | dúvida 4 (coffee-break.md:956) | Substituída |
| CB-F35 | Locais já usados | L/views.py:1180-1213 | N/views_pedidos.py:239-245 | Substituída | D/decisoes.md:297 | Substituída |
| CB-F36 | Busca de endereços já usados | core/buscar_endereco.py | — | Ausente | — | |
| CB-F37 | Duplicar OS | L/views.py:1157-1175 | N/pedidos.py:235-241 | Equivalente | — | Equivalente |
| CB-F38 | "Criar aqui" pela agenda | agenda/criar.py:36-40 | N/views_pedidos.py (`?inicio=`) | Descontinuada | coffee-break.md:894 | Descontinuada |
| CB-F39 | Mensagens de criar/editar/erro | L/views.py:1269-1454 | N/views_pedidos.py:339-385 | Equivalente | — | Equivalente |
| CB-F40 | Campos travados após a NF | L/forms.py:102-114 | N/forms_pedido.py:17-19 | Equivalente | — | Equivalente |
| CB-F41 | Cancelada/concluída só leitura | L/models.py:763-766 | N/models_pedido.py:137-140 | Equivalente | — | Equivalente |
| CB-F42 | Cancelar | L/services.py:118-154 | N/pedidos.py:179-197 | Equivalente | no conjunto, o histórico vai só para a principal | Equivalente |
| CB-F43 | Reativar | L/services.py:215-247 | N/pedidos.py:200-216 | Equivalente | — | Equivalente |
| CB-F44 | Excluir | L/views.py:1649-1666 | N/pedidos.py:219-232 | Substituída | também recusa com entrega (D/decisoes.md:291) | Substituída |
| CB-F45 | Reabrir/encerrar correção | L/services.py:187-212 | N/financeiro.py:179-208 | Equivalente | — | Equivalente |
| CB-F46 | Andamento do próximo marco | L/services.py:980-1063 | N/financeiro.py:134-176 | Equivalente | só na folha (ver CB-F87) | Equivalente |
| CB-F47 | Histórico | L/models.py:789-825 | N/models_pedido.py | Equivalente | — | Equivalente |
| CB-F48 | Três etapas | L/views.py:816-852 | folha única + etapas | Substituída | padrão de folha (CB3a) | Substituída |
| CB-F49 | Ordem e mensagens dos marcos | L/models.py:625-671 | N/dominio_pedido.py:239-257 | Equivalente | — | Equivalente |
| CB-F50 | Nota não fica em branco após protocolo | L/forms.py:383-389 | N/financeiro.py:87-88 | Equivalente | — | Equivalente |
| CB-F51 | Máscara do protocolo | L/protocolo_pagamento.py | N/dominio_pedido.py:260-267 | Equivalente | — | Equivalente |
| CB-F52 | Nº do eProtocolo vira protocolo de pagamento | L/services.py:869-891 | N/financeiro.py:102-107 | Parcial | só pagamento → PCPR; não PCPR → pagamento quando há nota || **Corrigida** — com a nota, o PCPR no formato do eProtocolo vira o de pagamento (em branco, ou o do ofício mudou e o de pagamento não); número interno não conta; conjunto só com todas as notas (`test_protocolo_do_oficio_vira_o_de_pagamento`) |
| CB-F53 | Atesto ao baixar os arquivos | L/services.py:893-907 | N/protocolo.py:156-162 | Equivalente | — | Equivalente |
| CB-F54 | Situação financeira derivada | L/services.py:33-52 | N/dominio_pedido.py:126-162 | Equivalente | — | Equivalente |
| CB-F55 | Pagamento conjunto | L/services.py:910-962 | N/conjunto.py:45-92 | Equivalente | — | Equivalente |
| CB-F56 | Espelhamento no conjunto | L/services.py:830-866 | N/conjunto.py:106-128 | Equivalente | — | Equivalente |
| CB-F57 | Protocolo/atesto só com nota em todas | L/services.py:819,878 | N/conjunto.py:95-103 | Substituída | D/decisoes.md:285 | Substituída |
| CB-F58 | Principal sai → próxima assume | L/services.py:157-185 | N/conjunto.py:131-148 | Equivalente | — | Equivalente |
| CB-F59 | PDF da NF | L/views.py:2547-2599 | N/pdfs.py:61-94 | Equivalente | — | Equivalente |
| CB-F60 | Conferência da NF (avisos) | L/services.py:377-430 | N/pdfs.py:97-109 | Equivalente | — | Equivalente |
| CB-F61 | PDF da OB | L/services.py:1070-1148 | N/pdfs.py:112-160 | Equivalente | — | Equivalente |
| CB-F62 | Aviso OB ≠ soma das notas | L/services.py:1128-1148 | N/pdfs.py:163-171 | Equivalente | — | Equivalente |
| CB-F63 | Documentos (OS, ofício, certifico) | L/documentos.py:145-220 | N/documentos.py:98-152 | Equivalente | timbre em texto (D/decisoes.md:286) | Equivalente |
| CB-F64 | Vias do ofício pertencem à OS principal do pagamento | L/vias.py:12-43 | N/vias.py (por OS) | **Defeito** | ofício assinado na principal é ignorado nas outras OS; vias duplicadas || **Corrigida** — `vias.dono`: o ofício guarda as vias na principal; folha e download pela outra OS (`test_vias_do_oficio_ficam_na_principal`) |
| CB-F65 | Certificado da solicitação | L/views.py:1584-1617 | N/documentos.py | Equivalente | — | Equivalente |
| CB-F66 | Nome do arquivo, falta do motor de PDF, prévia | L/documentos.py:650-653 | N/documentos.py:160-178 | Equivalente | — | Equivalente |
| CB-F67 | Vias emitidas e download | L/vias.py:96-143 | N/vias.py; folha | Equivalente | — | Equivalente |
| CB-F68 | Via assinada no lugar da gerada | L/views.py:2101-2160 | N/vias.py:61-99 | Equivalente | — | Equivalente |
| CB-F69 | Lista de anexos do protocolo | L/documentos.py:345-578 | N/protocolo.py:56-108 | Equivalente | — | Equivalente |
| CB-F70 | Nomes numerados dos arquivos | L/documentos.py:383-493 | N/protocolo.py:123-127 | Parcial | — | |
| CB-F71 | ZIP ou PDF único | L/views.py:1671-1724 | fila de downloads | Substituída | sem decisão escrita (coffee-break.md ainda diz ZIP) | |
| CB-F72 | Parte sem documentos | L/views.py:1693-1700 | N/protocolo.py:151-155 | **Defeito** | interrompe o download todo || **Corrigida** — a parte vazia fica de fora com aviso; o resto sai (`test_parte_vazia_fica_de_fora_e_o_resto_sai`) |
| CB-F73 | Textos do eProtocolo e passo a passo | L/documentos.py:599-647 | N/protocolo.py:176-204 | Equivalente | — | Equivalente |
| CB-F74 | Quadro de certidões | L/certidoes.py | N/certidoes.py | Equivalente | — | Equivalente |
| CB-F75 | "Emitir" copia o CNPJ e abre o portal | LT/certidoes.html:46-73 | NT/certidoes.html | Parcial | só o link | |
| CB-F76 | Anexar certidão com conferência | L/views.py:2748-2787 | N/certidoes.py:77-108 | Equivalente | — | Equivalente |
| CB-F77 | Entrega/ocorrência | L/services.py:1155-1221 | N/entregas.py | Equivalente | — | Equivalente |
| CB-F78 | Entrega pela janela da lista | LT/_acoes_linha.html:14 | seção da folha | Substituída | D/decisoes.md:292 | Substituída |
| CB-F79 | Lista de lotes (busca, exercício, ordenação, paginação) | L/views.py:369-443 | N/views_pedidos.py:598-627 | Parcial | só a situação || **Corrigida** — busca (lote, contrato, fornecedor, empenho, município), exercício, ordem e paginação; contagem nas abas (`test_lotes_com_busca_exercicio_ordem_e_contagem`) |
| CB-F80 | "Abrir exercício N+1" | L/views.py:446-451 | NT/lotes.html | Equivalente | — | Equivalente |
| CB-F81 | Detalhe do lote (comprometido, pago, saldo do empenho, contato do fornecedor, fiscal, todas as OS) | L/views.py:453-493 | NT/lote.html | Parcial | faltam valores e contatos || **Corrigida** — comprometido, pago, saldo do empenho, contato do fornecedor e fiscal; as 10 OS mais recentes + "Ver todas" (lista filtrada pelo lote) |
| CB-F82 | Virada de exercício | L/virada.py | N/virada.py | Equivalente | — | Equivalente |
| CB-F83 | Relatório do contrato | L/relatorio_contrato.py | N/relatorio.py | Equivalente | — | Equivalente |
| CB-F84 | Lista: filtros, trilha, pendentes | L/views.py:610-725 | N/views_pedidos.py:135-167 | Equivalente | — | Equivalente |
| CB-F85 | Ordenação da lista | L/views.py:610-617 | — | Ausente | — || **Corrigida** — "Ordenar por" na gaveta e `?ordem=` no CSV (`test_lista_e_csv_na_ordem_escolhida`); sem ordem por número (texto "5/2026"): a data da solicitação acompanha a sequência |
| CB-F86 | Linha: selos, parada, fatos | L/presenters.py | NT/_registro.html | Equivalente | — | Equivalente |
| CB-F87 | ⋮ da linha (entrega, andamento, baixar arquivos, certificado, cancelar, excluir) | LT/_acoes_linha.html:11-23 | NT/_registro.html | Parcial | — | |
| CB-F88 | CSV da lista | L/views.py:731-781 | N/views_pedidos.py:205-225 | Equivalente | — | Equivalente |
| CB-F89 | Soltar o PDF do processo na lista | LT/_importar_processo.html | — | Ausente | depende de CB-F110 | |
| CB-F90 | Indicadores do painel | L/views.py:253-362 | NT/painel.html | Substituída | D/decisoes.md:288 | Substituída |
| CB-F91 | Alertas de saldo, vigência e certidões | L/services.py:250-521 | N/painel.py:119-156 | Equivalente | — | Equivalente |
| CB-F92 | "O que fazer hoje" | L/services.py:1224-1370 | N/painel.py:168-190 | Equivalente | — | Equivalente |
| CB-F93 | Botões "Enviar a OS"/"Enviar a OB" no painel | L/services.py:1239-1246 | N/dominio_painel.py:105-122 | Parcial | decisão baseada em "e-mail só no CB8", que já existe | |
| CB-F94 | Dias parada com evento futuro | L/services.py:1283-1299 | N/dominio_painel.py:96-99 | **Defeito** | usa a data do evento futuro → sempre 0 || **Corrigida** — o fim do evento só conta se já passou (`test_parada_nao_zera_com_evento_futuro`) |
| CB-F95 | Indicadores da página inicial | core/views.py:55-91 | N/painel.py:193-201 | Equivalente | — | Equivalente |
| CB-F96 | Tela de e-mail OS/OB | L/views.py:2180-2317 | N/envio_email.py | Equivalente | + checagem de SMTP e limites | Equivalente |
| CB-F97 | Campos do e-mail (`{local}` com endereço; `{numero}` "#pk") | L/emails.py:46-66 | N/envio_email.py:95-110 | **Defeito** | `{local}` sem endereço || **Corrigida** — `{local}` = local — endereço, bairro, CEP; `{numero}` sem número = #pk (`test_local_do_email_leva_o_endereco`) |
| CB-F98 | Envio da OS grava a data; da OB conclui o conjunto | L/views.py:2243-2322 | N/envio_email.py | Equivalente | — | Equivalente |
| CB-F99 | Link: validade configurável | L/link_fornecedor.py:48-96 | N/link_fornecedor.py:35 | Parcial | fixo em 30 dias | |
| CB-F100 | Revogar o link | L/views.py:2377-2387 | N/link_fornecedor.py | Equivalente | — | Equivalente |
| CB-F101 | Página pública e limites | L/views_publicas.py | N/views_publicas.py | Equivalente | — | Equivalente |
| CB-F102 | Fornecedor envia nota/certidão | L/link_fornecedor.py:188-266 | N/link_fornecedor.py:148-215 | Equivalente | nota do fornecedor sem a conferência de NF repetida | |
| CB-F103 | Conferência aceitar/recusar | L/link_fornecedor.py:269-320 | N/link_fornecedor.py:218-249 | Equivalente | — | Equivalente |
| CB-F104 | Pedido vindo de eventos/palestras | L/origem.py | N/ganchos.py | Equivalente | — | Equivalente |
| CB-F105 | Agenda e prazos | agenda/fontes.py | N/agenda.py | Equivalente | — | Equivalente |
| CB-F106 | Relatórios consolidados | relatorios/consolidacao.py | gestao/painel/consolidado.py | Equivalente | — | Equivalente |
| CB-F107 | Busca global | — | N/busca.py | Equivalente | — | Equivalente |
| CB-F108 | Preencher com e-mail | L/leitura_pedido.py | N/preenchimento.py | Substituída | sem memória por remetente (D/decisoes.md:297) | Substituída |
| CB-F109 | Trilha de auditoria | auditoria/signals.py | trigger | Não verificado | — | |
| CB-F110 | Importar o PDF do processo de pagamento | L/importacao_processo.py | — | Ausente | CB9, **decisão pendente** (D/status.md:29) | Pendente (decisão) |
| CB-F111 | Importar planilha | L/management/commands/importar_coffee_break.py | — | Ausente | **decisão pendente** (D/decisoes.md:321) | Pendente (decisão) |
