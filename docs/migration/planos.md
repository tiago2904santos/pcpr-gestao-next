# Módulo 6 — Planos de trabalho (ficha)

Atualizado em 04/10/2026. Situação: **EM ANDAMENTO** — 6a (catálogos e configuração)
e 6b (domínio) implementados; 6c–6e pendentes. Comparado por leitura com `viagens_planos/` da referência
(modelos, formulários, serviços, telas, documento, testes); inventário funcional completo
em `scratchpad` da sessão (não versionado) e resumido aqui.

## Etapas

| Etapa | Conteúdo | Situação |
|---|---|---|
| 6a | Catálogos (programas, horários, atividades com meta e recurso, conjuntos com padrão), carga inicial, configuração (assina, coordenador padrão, sufixo), substituto para o plano | ✅ |
| 6b | Domínio puro: textos automáticos (contextualização, coordenação com gênero, considerações), pluralização do efetivo, metas/recursos, pendências, diárias do plano (motor do ofício) | ✅ |
| 6c | Plano de um evento: numeração anual com lacuna e sufixo, folha (cartões), autosave, documento (PDF/DOCX), lista com abas, cancelar/reativar/excluir, histórico | PENDENTE |
| 6d | Vários eventos (multievento) e diárias combinadas | PENDENTE |
| 6e | Resultados por atividade e relatório final | PENDENTE |

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
