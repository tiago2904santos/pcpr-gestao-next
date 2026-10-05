# Módulo 5 — Ordens de serviço (ficha)

Atualizado em 04/10/2026 (folha refeita). Situação: **IMPLEMENTADO, AGUARDANDO COMPARAÇÃO**. Comparado por
leitura com `viagens_ordens/{models,forms,views,services,docxtpl_context,abas}.py` e os
modelos de documento (`documentos/tests/golden/ordem_servico*.txt`) da referência.

## Matriz de paridade

| Função da referência | Situação | Aqui | Prova |
|---|---|---|---|
| Numeração anual própria (menor lacuna liberada por exclusão, senão maior + 1) | ✅ | "OS 001/2026"; trava por ano | `test_ordens.py::TestNumeracao` |
| Número digitado à mão ("N° da OS") | ↔ | só automático (o próximo número aparece antes de salvar) | — |
| Ligar ofícios e copiar deles destinos, período, equipe e motivo | ✅ ↔ | a cópia preenche só o que está vazio, na criação e ao ligar um ofício novo (não a cada gravação — com o autosave, apagar um campo não o traz de volta); a OS nova mostra antes o que virá | `TestCopiaDoOficio`, `test_apagar_o_motivo_nao_traz_de_volta_o_do_oficio` |
| Tipos de necessidade (padrão, operação com dia posterior, caminhão, micro-ônibus, cerimonial) | ✅ | textos da referência em `dominio/ordem_servico.py`; a ajuda diz o efeito de cada tipo | `test_dominio_ordem_servico.py` |
| Funções da equipe nos tipos que as usam | ✅ ↔ | escolhidas na OS salva, uma por servidor; a OS avisa "falta função da equipe" | `TestFuncoesEDocumento`, e2e `test_os_a_partir_do_oficio_com_funcoes` |
| Papéis fixos antigos (motorista, técnico, apoios…) | ↔ | não trazidos (só existiam para OS antigas); as funções cobrem | — |
| Texto: "Eu, <assina>, <cargo> … conferidas pelo Delegado-Geral …, DETERMINO" | ✅ | Delegado-Geral é campo da configuração da unidade | `test_documento_com_texto_do_tipo_assinatura_e_data_fixada` |
| Equipe agrupada por cargo, plural do cargo | ✅ MELHORADO | "escrivães" (a regra da referência daria "escrivões") | `TestEquipeNoTexto` |
| Motivo no meio da frase | ✅ MELHORADO | sem ponto final e com inicial minúscula | `TestRevisaoDeUX` |
| Vários destinos | ✅ MELHORADO | "para os municípios de A e B" | idem |
| Quem assina: assinante desta OS, senão substituto do período, senão chefia | ✅ ↔ | o assinante precisa ser da unidade da OS; a tela diz quem assina se ficar em branco | `test_assinante_da_os_vence_a_configuracao`, `test_assinante_de_outra_unidade_recusado` |
| Data do documento fixada na primeira geração | ✅ | em branco volta ao automático | `test_data_do_documento_em_branco_volta_ao_automatico` |
| Documento PDF e DOCX | ✅ | PDF/A, sem cache | `TestTelas::test_nova_pela_tela_e_documento` |
| Cancelar / reativar / excluir (libera o número) | ✅ ↔ | excluir só enquanto o documento nunca foi gerado (depois, cancelar) — a referência liberava sempre | `TestCicloDeVida`, `test_depois_de_gerado_nao_exclui_so_cancela` |
| Lista: abas, busca (número, destino, servidor, motivo, ofício) | ✅ | "OS 7/2026" procura só a OS | `test_lista_abas_busca_e_filtro_por_oficio` |
| Aba "Finalizadas" (contas prestadas) | ✅ | prestações dos ofícios da OS todas finalizadas; sai de "vão acontecer"/"em andamento" | `gestao/viagens/tests/test_prestacao.py::test_contas_prestadas_nos_outros_modulos`, `test_abas_de_quando_excluem_as_contas_prestadas` |
| Gravação automática | ✅ | a OS salva grava sozinha a cada pausa (autosave), quando o formulário inteiro é válido; o que impede aparece na barra | `test_folha_termo_os.py::TestAutosaveDaOS`, e2e `test_os_a_partir_do_oficio_com_funcoes` |
| Prévia do documento | ✅ MELHORADO | o documento como vai sair, na própria folha (visualizador do ofício em modo leitura, Texto/PDF), refeito a cada gravação; a prévia **não** fixa a data nem conta como geração (`?previa=1` no PDF) | `TestFolhaDaOS` |
| Histórico | ✅ MELHORADO | criação, alterações (destinos, equipe, ofícios vêm das tabelas filhas), primeira geração, cancelamento e reativação, lidos da trilha do banco | `TestHistoricoDaOS` |
| Conflito de agenda (aviso) | ❔ | não trazido nesta rodada (backlog) | — |
| Anexar assinado | ⛔ | núcleo de Documentos (módulo 7) | — |
| Nova OS a partir do ofício | ✅ | "Mais ações" da janela do ofício, com confirmação | `test_criar_do_oficio_em_um_clique` |

## Folha (04/10/2026)

Refeita na linguagem da folha do ofício: placa "OS 001/2026" (ou "nova", com o número que
receberá) e frase-resumo (situação no tempo, tipo, equipe, destinos, período, ofícios);
cartões numerados — 1 Ofícios e tipo, 2 Destinos e período, 3 Equipe, 4 Motivo e assinatura,
5 Documento — com nota (o que vem dos ofícios, quem assina em branco) e selos de falta; no
cartão 5, conferência com links para os cartões e "Gerar PDF", visualizador e histórico.
Decisão: a prévia na tela não trava a exclusão (só o PDF/DOCX gerado conta como emissão do
número). axe sem violações em 360 e 1440 com o visualizador carregado.

## Revisões da folha (04/10/2026)

- **Segurança**: a prévia (tela e PDF `?previa=1`) sai com a marca **MINUTA** e "-previa"
  no nome do arquivo — não circula como OS emitida e por isso pode não travar a exclusão;
  a folha exige a mesma régua de gerar (`pode_ver_documento_ordem`: OS ativa, quem altera)
  — Consulta e OS cancelada não veem o documento; autosave com **versão** (`atualizado_em`):
  quem abriu antes não grava por cima de quem salvou depois; corridas (cancelada/excluída no
  meio) viram mensagem; histórico com política explícita (`pode_ver_historico_ordem`), que
  nunca perde criação, cancelamento e primeira geração (marcos buscados à parte) e só conta
  tabelas filhas *desta* OS; índice da trilha criado com `CONCURRENTLY`; X-Frame-Options
  `SAMEORIGIN` coerente com o CSP da moldura; erro no PDF do visualizador vira aviso na folha.
- **UX**: depois de cada gravação a tela acompanha — frase do topo, selos dos cartões,
  conferência e pendências da barra se refazem (regiões `data-vivo`); quando a gravação muda
  campos (funções a escolher, ofício recém-ligado) a página recarrega sozinha; os dados dos
  ofícios entram na criação e ao ligar um ofício novo (apagar o motivo não traz o do ofício
  de volta) ↔; no cabeçalho, "Ver como vai sair" (ver não compromete); "Gerar a OS" na
  conferência e na barra (dourado quando nada falta); selo do documento primeiro na frase
  (pendências / pronta / gerada em) e o tempo como item; função só com o nome; quem assina
  em branco sob o campo; status de erro visível no celular; datas empilhadas abaixo de
  420px; ação da conferência em linha própria no celular; cancelada sem conferência verde.
- **Mantido**: rótulos dos tipos com hífen, como na referência (mudar exigiria migração só de
  texto; fica para quando houver outra mudança no modelo).

## Perfis

Operador e gestor: criar, editar, gerar, cancelar/reativar e excluir (sem documento gerado)
OS da própria unidade (gestor: de todas). Consulta: vê. Permissões `viagens.*_ordemservico`.

## Revisões (04/10/2026)

- **Segurança** (sem crítico/alto): assinante só da unidade da OS; excluir só sem documento
  gerado (o número já saiu num documento oficial); ofício cancelado recusado no serviço;
  limites conferidos depois da cópia; documento sem cache; "Nova OS" só aparece para a
  unidade do ofício; corrida na exclusão vira mensagem.
- **UX**: falta de função sinalizada (selo, alerta, aviso ao salvar com link para a equipe);
  ajuda do tipo diz o efeito no documento; ajuda do motivo mostra a frase do tipo; o que
  vem dos ofícios aparece antes de salvar; quem assina se ficar em branco; criar a partir
  do ofício pede confirmação; data do documento em branco volta ao automático; motivo e
  destinos com a gramática certa no documento; "Mais ações" com rótulo; voltar à própria OS
  depois de cancelar/reativar.
- **Decisão a confirmar**: assinante por OS escolhido pela equipe (na referência também) —
  limitado à unidade; e a trava de exclusão depois de gerado (diferente da referência).

## Pendências

"Finalizadas" (módulo 9), anexar assinado (módulo 7), conflito de agenda, comparação com a
referência em execução. As funções de quem entra na equipe aparecem depois de salvar pelo
botão (o autosave não redesenha a tela).
