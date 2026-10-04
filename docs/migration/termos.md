# Módulo 4 — Termos de autorização (ficha)

Atualizado em 04/10/2026. Situação: **IMPLEMENTADO, AGUARDANDO COMPARAÇÃO**. Comparado por
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
| Prévia em tela | ✅ MELHORADO | o documento escolhido aparece na própria folha, como vai sair (visualizador do ofício em modo leitura, Texto/PDF), refeito a cada gravação; "Prévia" em cada documento troca qual se vê | `test_folha_termo_os.py::TestFolhaDoTermo`, e2e `test_termo_a_partir_do_oficio` |
| Gravação | ✅ MELHORADO | o termo salvo grava sozinho a cada pausa (autosave); o que impede aparece na barra ("Não salvo: …") | `test_autosave_e_historico`, e2e |
| Histórico | ✅ MELHORADO | criação, alterações (juntas por pessoa em 20 min), cancelamento e reativação, lidos da trilha de auditoria do banco | `test_autosave_e_historico` |

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

## Folha (04/10/2026)

A tela foi refeita na linguagem da folha do ofício (a primeira versão era "título + cartões +
salvar", reprovada pela régua de qualidade): placa "Termo #N" e frase-resumo em chips
(situação, ofício, servidores, destino, período, viatura); cartões numerados — 1 Ofício e
evento, 2 Destinos e período, 3 Servidores e viatura, 4 Documentos — com nota e selo do que
falta; no cartão 4, a conferência (cada falta leva ao cartão), o que o termo emite (PDF/DOCX
e "Prévia" por documento), o visualizador e o histórico. "Todos em um PDF" no cabeçalho; ZIP,
histórico, cancelar e excluir no menu. Capturas em `artifacts/visual-refinement-v2/depois/
termos-editar-*.png`; axe sem violações em 360 e 1440 com o visualizador carregado.

## Revisões da folha (04/10/2026)

- **Segurança**: a folha exige a régua de gerar (`pode_ver_documento_termo`: termo ativo,
  quem altera termos) — Consulta não vê RG/CPF/telefone dos servidores pela folha, e termo
  cancelado não mostra documento; autosave com versão (não grava por cima de quem salvou
  depois); corridas viram mensagem; histórico com política explícita e marcos garantidos.
- **UX**: a tela acompanha cada gravação (frase, selos, conferência, lista de documentos e
  pendências da barra se refazem); trocar o ofício recarrega a tela (a herança sob cada
  campo muda); a conferência traz "Gerar os termos (PDF)" e a barra também; cada linha da
  lista abre o documento em "Como vai sair" pelo nome e tem PDF + menu (DOCX); sem ofício,
  "Obrigatório sem ofício vinculado"; com ofício, o vazio diz "valem os do ofício" (sem a
  ajuda fixa que contradizia o cabeçalho); reativar volta ao próprio termo.

## Perfis

Operador e gestor: criar, editar, gerar documentos, cancelar/reativar e excluir termos da
própria unidade (gestor: de todas). Consulta: vê. Permissões `viagens.*_termoautorizacao`.

## Desempenho

Lista com número fixo de consultas (`TestTelas::test_consultas_da_lista_nao_crescem`); a
janela do ofício não ganhou consulta (o link "Termos deste ofício" não conta).

## Pendências

"Finalizados" (módulo 9), anexar assinado (módulo 7), comparação com a referência em
execução.
