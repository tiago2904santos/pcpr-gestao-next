# Módulo 6 — Planos de trabalho (ficha)

Atualizado em 04/10/2026. Situação: **IMPLEMENTADO, AGUARDANDO COMPARAÇÃO** — 6a (catálogos e configuração)
6a–6e implementados (catálogos, domínio, plano de um evento, vários eventos, resultados); falta só a aba "Finalizados", que depende da prestação de contas (módulo 9). Comparado por leitura com `viagens_planos/` da referência
(modelos, formulários, serviços, telas, documento, testes); inventário funcional completo
em `scratchpad` da sessão (não versionado) e resumido aqui.

## Etapas

| Etapa | Conteúdo | Situação |
|---|---|---|
| 6a | Catálogos (programas, horários, atividades com meta e recurso, conjuntos com padrão), carga inicial, configuração (assina, coordenador padrão, sufixo), substituto para o plano | ✅ |
| 6b | Domínio puro: textos automáticos (contextualização, coordenação com gênero, considerações), pluralização do efetivo, metas/recursos, pendências, diárias do plano (motor do ofício) | ✅ |
| 6c | Plano de um evento: numeração anual com lacuna e sufixo, folha (cartões), autosave, documento (PDF/DOCX), lista com abas, cancelar/reativar/excluir, histórico | ✅ |
| 6d | Vários eventos (multievento) e diárias combinadas | ✅ |
| 6e | Resultados por atividade e relatório final | ✅ |

## Matriz de paridade (6a)

| Função da referência | Situação | Aqui | Prova |
|---|---|---|---|
| Programas solicitantes (nome único, maiúsculas) | ✅ | lista genérica de cadastros | `test_catalogos_plano.py::TestRegras::test_programa_em_maiusculas_e_sem_repetir` |
| Horários (início e fim → "HH:MM até HH:MM", únicos) | ✅ ↔ | fim antes do início é recusado ("O fim precisa ser depois do início.") | `test_horario_de_inicio_e_fim` |
| Atividades com código nascido do nome (`_2`, `_3`…), meta obrigatória, recurso opcional | ✅ | o código não muda ao renomear | `test_codigo_da_atividade_nasce_do_nome_e_nao_muda`, `test_atividade_exige_meta` |
| Conjuntos ("presets"): nome único em maiúsculas, ao menos uma atividade, um só padrão | ✅ | caixas de escolha (componente novo, no UI Lab) | `test_conjunto_exige_atividade_e_um_so_padrao` |
| Carga inicial (3 programas, 3 horários, 11 atividades com meta e recurso) | ✅ | migração idempotente | `TestCargaInicial` |
| Catálogos sem "ativo" (apagar o que não serve) | ↔ MELHORADO | Desativar tira das escolhas sem apagar; excluir só o que nunca foi usado (como cargos) | `test_atividade_usada_num_conjunto_nao_se_exclui_na_lista` |
| Configuração: "Assina os planos de trabalho", coordenador administrativo padrão, sufixo da numeração | ✅ ↔ | por unidade; sufixo vazio vale a sigla da unidade | `TestConfiguracaoDoPlano` |
| Sem assinante, o plano sai sem nome (não cai na chefia) | ✅ | `quem_assina(…, "plano_trabalho", …)` | `test_plano_sem_assinante_sai_sem_nome_nao_cai_na_chefia` |
| Substituto por período para o plano | ✅ | tipo "Plano de trabalho" na substituição | `test_substituto_do_plano_no_periodo` |

## Matriz de paridade (6b — domínio, `dominio/plano_trabalho.py`)

| Regra da referência | Situação | Prova |
|---|---|---|
| Contextualização em três parágrafos (municípios sem repetir, programa legível, "________" na falta) | ✅ | `test_dominio_plano_trabalho.py::TestTextos` |
| Considerações finais com os municípios | ✅ | `test_considera_varios_municipios_sem_repetir` |
| Designação dos coordenadores com gênero; no de vários eventos, só o administrativo | ✅ | `test_coordenacao_com_genero_e_capitalizacao` |
| Período por extenso ("30 de junho a 02 de julho de 2026"…) | ✅ | `test_periodos_por_extenso` |
| Atividades, metas e recursos ("• …", sem repetir, ordem alfabética, unidade móvel) | ✅ | `test_metas_e_recursos_sem_repetir_e_unidade_movel` |
| Efetivo "6 Policiais Civis (ASCOM)" por unidade e cargo | ✅ MELHORADO | plural só do núcleo do cargo ("Agentes de Polícia Judiciária", "Escrivães de Polícia"); a referência pluralizava palavra por palavra | `test_efetivo_no_plural_com_sigla` |
| Diárias: um trecho sede → destino principal → sede; faltas juntas; sem tabela vigente recusa | ✅ | Maringá e Sarandi ao centavo (`TestDiarias`) |
| Texto do valor ("Valor total: R$7.234,68 (…). Valor correspondente a …") | ✅ ↔ | extenso no padrão do sistema (sem vírgula entre milhar e centena) | `test_texto_do_valor_como_na_referencia` |
| Pendências na ordem (coordenador, destino, data, efetivo, diárias) | ✅ | `test_plano_vazio_lista_as_cinco_na_ordem` |

Os auxiliares de escrita (datas, listas, plural, capitalização, moeda) passaram a um módulo
comum, `dominio/escrita.py`, usado também pela OS.

## Matriz de paridade (6c — plano de um evento)

| Função da referência | Situação | Aqui | Prova |
|---|---|---|---|
| Numeração anual "07/2026/ASCOM", menor lacuna da exclusão, sufixo da configuração | ✅ ↔ | número só automático; sufixo vazio vale a sigla da unidade | `test_planos.py::TestNumeracao` |
| Criar a partir da viagem (destino, datas, efetivo dos ofícios, saída/chegada dos roteiros) | ✅ ↔ | a partir dos ofícios (a viagem é o módulo 8); "Novo plano de trabalho" na janela do ofício | `TestCriacaoDoOficio`, e2e `test_plano_a_partir_do_oficio` |
| Coordenador administrativo padrão da configuração; coordenadores do cadastro ou à mão (maiúsculas) | ✅ MELHORADO | o tratamento ("o Coordenador"/"a Coordenadora") é escolhido — sem padrão masculino; vazio é pendência; o padrão da configuração traz o seu | `TestRevisoes::test_tratamento_do_coordenador_padrao_vem_da_configuracao` |
| Textos automáticos (contextualização, coordenação, considerações) e "apagar volta ao automático" | ✅ MELHORADO | ajustáveis na folha (cartão 4); aviso quando o texto escrito à mão ficou para trás do automático; botão "Voltar ao texto automático" | `TestTextosEAtividades` |
| Atividades → metas, atividades, recursos, unidade móvel; conjunto padrão | ✅ MELHORADO | o conjunto padrão é gravado no plano novo (na referência, só marcado na tela) | `test_conjunto_padrao_gravado_ao_criar_do_oficio` |
| Efetivo em linhas (mesmo cargo pode repetir); diárias de um trecho com cópia gravada | ✅ | componente `pc-linhas`; cargo/unidade desativados continuam na linha; no máximo 50 linhas | `TestDiariasEPendencias`, `test_efetivo_em_linhas_com_erro_por_linha` |
| Prévia das diárias ao vivo (rota calcular) | ↔ | a gravação automática refaz o quadro de diárias (mesmo bloco da folha do ofício) | e2e |
| Pendências bloqueiam finalizar/gerar | ✅ MELHORADO | rótulo curto nos selos; diárias só quando a pendência é delas; avisos que não impedem (sem programa, sem atividade) | `test_dominio_plano_trabalho.py` |
| Finalizar (GERADO) e gerar PDF/DOCX como passos separados; a lista gerava sem finalizar | ↔ | uma ação só: "Finalizar e gerar o plano" (grava a tela, confere, fixa a data, libera PDF/DOCX); o GET não gera antes dela | `test_finalizar_grava_o_que_esta_na_tela`, `test_documento_pdf_docx_e_previa` |
| Documento: 8 seções na ordem do PDF da referência, cabeçalho e página em todas, assinatura na última página | ✅ | PDF/A e DOCX do mesmo HTML; prévia com MINUTA | `test_geracao_fixa_data_e_marca_gerado_previa_nao` |
| Quem assina: o do plano, substituto do período, assinante dos planos — sem chefia | ✅ | | `TestConfiguracaoDoPlano` (6a) |
| Lista: abas (sem data em "Que vão acontecer"), busca (número, N/AAAA, destino, programa) | ✅ | estado único com a folha (pendências / pronto para gerar / gerado em / cancelado) | `test_lista_abas_busca_e_permissoes` |
| Aba "Finalizados" (contas prestadas) | ⛔ | módulo 9 | — |
| Cancelar (motivo) / reativar / excluir (número volta) | ✅ MELHORADO | cancelado bloqueado no servidor; excluir só antes de gerar | `test_cancelado_nao_altera_e_reativa`, `test_depois_de_gerado_nao_exclui` |
| Autosave (também depois de gerado) | ✅ MELHORADO | com versão (não grava por cima de outra pessoa); a geração toca a versão e não deixa "em branco" apagar a data fixada | `test_autosave_versao_e_cancelado`, `test_aba_velha_depois_de_gerar_nao_apaga_a_data` |
| Histórico | ✅ MELHORADO | lido da trilha do banco | `test_historico` |
| Resultados por atividade (realizado ≥ 0 com ponto de milhar, observação até 500, linha vazia apaga; previstas de todos os eventos + as que saíram do plano com resultado) | ✅ | página própria na linguagem das folhas, ligada do cartão Documento depois de gerado; cancelado só leitura **e** bloqueado no servidor (a referência só escondia) | `test_planos.py::TestResultados`, `test_dominio_plano_trabalho.py::TestResultados` |
| Relatório final e sugestão para o Relatório Técnico | ✅ | `resultados.relatorio_final`, `resultados.sugestao_para_rt` (usada quando a prestação de contas chegar) | `test_salvar_listar_apagar_e_relatorio` |
| Vários eventos | ✅ ↔ | o evento 1 são os campos do plano; os demais, registros editados numa janela (na referência o plano era o "rascunho do evento atual", com adicionar/editar/remover que limpavam e recarregavam o rascunho); efetivo e deslocamento do plano (a mesma equipe numa viagem — resolve a ambiguidade 1: o texto e as diárias usam o mesmo efetivo); diárias combinadas num trecho só; contextualização e considerações com os destinos de todos os eventos (a referência usava só o rascunho e podia sair com "________"); só o coordenador administrativo designado; documento com atuação, atividades, metas e recursos por evento e o valor com "Valor total do evento dias: …" | `test_planos.py::TestVariosEventos`, `test_dominio_plano_trabalho.py::TestVariosEventos` |
| Valor por evento ("Valor do evento dia: …") | ↔ | não há: com a mesma equipe numa viagem só, o valor é o combinado (a referência copiava as diárias do rascunho no momento em que o evento era gravado — frágil, ambiguidade 3) | — |

### Revisões (04/10/2026)

- **Segurança**: Enter não finaliza (o 1º botão do formulário é Salvar); finalizar grava o que
  está na tela (com versão) antes; geração só por "Finalizar e gerar" (POST) — o GET de
  PDF/DOCX não gera antes, nem por link de fora; corrida excluir × gerar recusada (trava a
  linha); aba velha não apaga a data fixada; linhas de efetivo limitadas e com ids validados;
  cadastros desativados mantidos na linha; outra unidade recebe 403 em todas as rotas;
  contexto da trilha restaurado ao sair de um bloco aninhado.
- **UX**: tratamento do coordenador sem padrão (pendência); conjunto padrão gravado de
  verdade; ação decisiva na barra; assinatura e textos antes de gerar; textos automáticos que
  se refazem e aviso de texto manual desatualizado; selos com rótulo curto; estado único na
  lista e na folha; "Outro programa" só com "Outro"; o plano novo diz o que vem do ofício;
  total do efetivo; efetivo no celular em duas colunas; filtro de atividades só com catálogo
  longo; "Desmarcar todas" com confirmação; metas e recursos recolhíveis; "Usar como padrão"
  já na criação do conjunto.

## Decisões para as próximas etapas (adotadas; a confirmar)

As ambiguidades do inventário e o que este sistema faz (registro em
[decisoes.md](decisoes.md) quando a etapa entrar):

1. **Vínculo**: na referência o plano liga-se só à *viagem* (módulo 8, ainda não migrado) e
   dela recebe ofícios. Aqui, até a viagem existir, o plano liga-se (opcionalmente) a
   **ofícios** — de onde vêm destino, datas, efetivo (por unidade e cargo) e a sugestão de
   saída/chegada — como a semente da viagem fazia. Quando a viagem chegar, o vínculo passa
   por ela.
2. **Número**: só automático (como a OS); a referência deixa digitar. Evita o "salto que não
   vira lacuna" (ambiguidade 10).
3. **Novo plano**: tela de criação, sem o "rascunho vazio reaproveitado depois de 30 min".
4. **GERADO**: só a geração real (PDF/DOCX) e o "finalizar" marcam; a prévia na tela sai com
   MINUTA e não marca (na referência, abrir a prévia já marcava).
5. **Cancelado**: bloqueado no servidor em toda escrita (a referência só escondia botões).
6. **Excluir**: só enquanto o documento nunca foi gerado (como a OS); depois, cancelar.
7. **Diárias**: só o destino principal entra no cálculo, como na referência (a confirmar).
8. **Multievento**: contextualização e considerações usam os destinos de todos os eventos
   (na referência usavam só o rascunho e podiam sair com "________" — defeito).
9. **Efetivo no multievento**: a referência soma no texto e usa o maior nas diárias; a
   decisão fica para a etapa 6d (se não houver como confirmar, a mesma equipe — o maior —
   nos dois, com a soma por evento à vista).
10. **Ordem das seções**: a do PDF da referência (pedido do usuário lá) para PDF e DOCX.
11. **Texto fixo "PCPR na Comunidade"** na contextualização: mantido (texto institucional da
    referência).

## Perfis

Catálogos: operador e gestor mantêm (como os demais cadastros da equipe); consulta vê.
Configuração do plano: gestor.

## Pendências

6b–6e; aba "Finalizados" (depende da prestação de contas, módulo 9); integração com a
viagem (módulo 8) e com a solicitação (módulo 11).
