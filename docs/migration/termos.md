# Módulo 4 — Termos de autorização (ficha)

Atualizado em 03/10/2026. Situação: **IMPLEMENTADO, AGUARDANDO COMPARAÇÃO**. Comparado por
leitura com `viagens_termos/{models,forms,services,views,abas}.py`, os modelos de documento
(`documentos/tests/golden/termo_autorizacao*.txt`) e `docs/paridade/termos-*.md` da
referência.

## Matriz de paridade

| Função da referência | Situação | Aqui | Prova |
|---|---|---|---|
| Termo ligado (opcional) a um ofício não cancelado | ✅ | busca de ofícios (número, protocolo, destino, servidor); escopo da unidade | `test_termos.py::TestRegras`, `TestTelas::test_busca_de_oficios_nao_traz_cancelados` |
| Herança do ofício (destinos, período, servidores, viatura) quando em branco | ✅ | o que vem do ofício aparece na tela ("Do ofício: …") e na lista | `test_termo_do_oficio_herda_o_que_fica_em_branco`, `test_o_proprio_vence_o_do_oficio` |
| Destino principal + destinos adicionais | ✅ ↔ | uma lista de destinos (Cidade/UF), na ordem, sem repetir | `test_avulso_pela_tela_com_destinos_e_servidores` |
| Período (data inicial e final; um dia repete a inicial) | ✅ | | `test_o_proprio_vence_o_do_oficio` |
| Mensagens: "Informe o destino ou selecione um ofício com roteiro", "Informe a data…", "A data final não pode ser anterior à inicial" | ✅ | mesmas regras, mensagens equivalentes | `test_avulso_exige_destino_e_data`, `test_erro_volta_com_mensagem` |
| Servidores (múltipla escolha) e viatura | ✅ | servidores por busca (`pc-multiescolha`), viatura com busca local | idem |
| Documento por servidor (completo com/sem viatura) | ✅ | PDF/A (abre no navegador) e DOCX | `TestDocumentos` |
| Termo genérico (semipreenchido) | ✅ | | idem |
| Termo da viatura (servidor em branco) | ✅ | só quando há viatura efetiva | idem |
| Todos em um PDF / ZIP de DOCX | ✅ | `termo-N-todos.pdf` (um termo por página) | `test_telas_geram_pdf_docx_pdf_unico_e_zip` |
| Texto do documento | ✅ ↔ | mesmo texto; a unidade (sigla e nome) vem do cadastro e o nome do evento é um campo do termo (padrão "PCPR na Comunidade", o da referência) — na referência eram fixos ("ASCOM") | `test_texto_do_documento` |
| Lista: título "destino · período", selo de tempo, ofício · servidores · viatura, busca (destino, ofício, protocolo, servidor, placa/modelo) | ✅ | | `test_lista_abas_busca_e_filtro_por_oficio` |
| Abas Que vão acontecer / Em andamento e realizados / Cancelados | ✅ ↔ | uma por vez | idem |
| Aba "Finalizados" (contas prestadas) | ⛔ | depende da prestação de contas (módulo 9) | — |
| Cancelar (com motivo) / reativar / excluir | ✅ | cancelado não se edita nem gera documento | `test_cancelar_exige_motivo_e_bloqueia_edicao`, `test_cancelado_nao_gera`, e2e `test_cancelar_e_reativar_termo` |
| Criar termo a partir do ofício | ✅ | "Mais ações" da janela do ofício → "Novo termo de autorização" (e "Termos deste ofício") | e2e `test_termo_a_partir_do_oficio` |
| Marcar no ofício quem precisa de termo (`servidores_termo_autorizacao`) | ↔ | sem marcação no ofício: o termo do ofício vale para toda a equipe; para só alguns, escolha os servidores no termo | — |
| Anexar termo assinado | ⛔ | chega com o núcleo de Documentos (módulo 7: conferência de assinado) | — |
| Prévia em tela | ↔ | o PDF abre na aba (é a prévia) | — |

## Revisões (03/10/2026)

- **Segurança**: termo ligado a ofício de outra unidade passa a ser da unidade do ofício (e
  um termo existente não troca de unidade); limites de 50 servidores e 30 destinos; a busca
  de município não trava mais com texto longo (regex linear, tamanho máximo — vale também
  para ofícios e roteiros); números na busca só ASCII; motivo até 1000 caracteres; reativar
  só cancelado; destinos só regravados quando mudam; o PDF só busca recursos da pasta dos
  documentos (brasão e fontes) — vale também para ofício e justificativa.
- **UX**: "Novo termo de autorização" na janela do ofício cria em um clique e abre nos
  documentos; o termo salvo mostra os documentos primeiro; sob cada campo em branco, o valor
  que vem do ofício ("Do ofício: …"); erros de destino e data juntos e no campo; título com
  destino · período e selo (Cancelado/Incompleto); reativar no próprio aviso; cancelar e
  excluir no "Mais ações"; lista com a placa "Termo #N", selo "Avulso", filtro por ofício
  com título, contagens e abas que respeitam o filtro e "Criar termo para este ofício" no
  vazio; busca de ofício pelo começo do número; documento com "participar do evento “…”" e
  "nos municípios de A e B"; configuração mostra quem assina hoje (e por quê) e avisa quando
  o texto do rodapé ignora o endereço.

## Perfis

Operador e gestor: criar, editar, gerar documentos, cancelar/reativar e excluir termos da
própria unidade (gestor: de todas). Consulta: vê. Permissões `viagens.*_termoautorizacao`.

## Desempenho

Lista com número fixo de consultas (`TestTelas::test_consultas_da_lista_nao_crescem`); a
janela do ofício não ganhou consulta (o link "Termos deste ofício" não conta).

## Pendências

"Finalizados" (módulo 9), anexar assinado (módulo 7), comparação com a referência em
execução.
