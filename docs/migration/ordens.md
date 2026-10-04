# Módulo 5 — Ordens de serviço (ficha)

Atualizado em 04/10/2026. Situação: **IMPLEMENTADO, AGUARDANDO COMPARAÇÃO**. Comparado por
leitura com `viagens_ordens/{models,forms,views,services,docxtpl_context,abas}.py` e os
modelos de documento (`documentos/tests/golden/ordem_servico*.txt`) da referência.

## Matriz de paridade

| Função da referência | Situação | Aqui | Prova |
|---|---|---|---|
| Numeração anual própria (menor lacuna liberada por exclusão, senão maior + 1) | ✅ | "OS 001/2026"; trava por ano | `test_ordens.py::TestNumeracao` |
| Número digitado à mão ("N° da OS") | ↔ | só automático (o próximo número aparece antes de salvar) | — |
| Ligar ofícios e copiar deles destinos, período, equipe e motivo | ✅ ↔ | a cópia preenche só o que está vazio, ao salvar; a tela mostra antes o que virá ("Ao salvar, vem dos ofícios: …") | `TestCopiaDoOficio` |
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
| Aba "Finalizadas" (contas prestadas) | ⛔ | depende da prestação de contas (módulo 9) | — |
| Gravação automática | ↔ | botão Salvar (o documento sai do que está salvo; a tela avisa) | — |
| Conflito de agenda (aviso) | ❔ | não trazido nesta rodada (backlog) | — |
| Anexar assinado | ⛔ | núcleo de Documentos (módulo 7) | — |
| Nova OS a partir do ofício | ✅ | "Mais ações" da janela do ofício, com confirmação | `test_criar_do_oficio_em_um_clique` |

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
referência em execução.
