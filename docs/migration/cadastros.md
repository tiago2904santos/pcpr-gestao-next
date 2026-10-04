# Módulo 2 — Cadastros de Viagens (ficha)

Atualizado em 03/10/2026. Situação: **EM ANDAMENTO** — CRUD em tela implementado e testado;
faltam assinantes por tipo de documento (com substituições por período) e o endereço da
configuração em campos separados. Não é marcado concluído sem a comparação com a referência
em execução (dependência externa, como em Ofícios).

Referência lida: `viagens_cadastros/{models,forms,views,permissions,normalizacao}.py` e as
fichas `docs/paridade/cadastros-*.md` do repositório de referência (comparado por leitura).

Legenda: ✅ implementado e testado · 🟡 parcial · ↔ diferença intencional · ⛔ bloqueado ·
❔ não investigado.

## Matriz de paridade

| Função da referência | Situação | Como ficou aqui | Prova (teste) |
|---|---|---|---|
| Entrada "Cadastros" com os cartões | ✅ | `/cadastros/`: cadastros principais + configuração e textos; cada perfil vê o que abre | `TestPerfis::test_indice_mostra_so_o_que_o_perfil_abre` |
| Servidores: lista, busca sem acento (nome/cargo/unidade/CPF/RG) | ✅ | idem + telefone | `TestServidor::test_busca_sem_acento_por_cargo_e_unidade` |
| Servidores: filtro por cargo com contagem que respeita a busca | ✅ ↔ | todos os cargos presentes no recorte (lá: os 3 mais frequentes) | `test_aba_incompletos_e_filtro_por_cargo_com_contagem` |
| Servidores: dados na ordem cargo · CPF · RG · telefone · unidade | ✅ | idem, com máscara na exibição | captura `cadastros-servidores` |
| Servidor: só o nome obrigatório; "rascunho" sinalizado | ✅ ↔ | "Falta cargo e CPF" (selo) e aba **Incompletos**; regra de completo = cargo + CPF de 11 dígitos (lá o RG vazio contava como "não possui") | `test_so_o_nome_e_obrigatorio_e_o_cadastro_fica_incompleto` |
| CPF com dígito verificador, único | ✅ ↔ | o dígito só é conferido quando o CPF muda (DEMO tem CPF fictício que não confere) | `test_cpf_invalido_*`, `test_cpf_antigo_que_nao_confere_continua_editavel` |
| RG livre (letras e números) ou "não possui", único | ✅ ↔ | vazio = não informado; "não possui" é marca própria (lá vazio virava "não possui") | `test_varios_servidores_sem_rg` |
| Telefone com DDD (10/11 dígitos), único | ✅ | máscara ao digitar | `test_unicidade_vira_mensagem_no_campo` |
| Nome do servidor único | ✅ | sem diferenciar caixa | idem |
| Cargo padrão já escolhido no servidor novo | ✅ | | `test_cargo_padrao_vem_escolhido_no_novo` |
| Unidade de lotação por busca (sigla e nome) | ✅ | `pc-combobox` sobre o select | e2e `test_servidor_nasce_incompleto_e_e_completado` |
| "Gerenciar cargos/unidades" a partir do formulário, com retorno | ❔→↔ | cadastro em janela na própria lista; o atalho de dentro do formulário não foi trazido (backlog) | — |
| Viaturas: lista, busca (placa/modelo/unidade/motorista), filtro por combustível | ✅ | | `TestViatura::test_filtro_*` |
| Viatura: só a placa obrigatória; tipo inicial Descaracterizada; combustível padrão | ✅ | | `test_so_a_placa_e_obrigatoria`, `test_motoristas_e_padroes_da_viatura_nova` |
| Placa antiga/Mercosul, única, normalizada | ✅ | máscara tira separadores | `test_placa_invalida`, `test_placa_repetida` |
| Motoristas por busca (sem repetir, remover) | ✅ | componente novo `pc-multiescolha` (UI Lab) | e2e `test_viatura_com_motoristas_por_busca` |
| Unidades, cargos, combustíveis: lista, busca, novo/editar | ✅ ↔ | janela (lá: painel na lista) | `TestCatalogos` |
| "Usar como padrão" (cargo, combustível), um por cadastro | ✅ | o banco garante um só; editar o nome preserva (P05) | `test_um_padrao_por_cadastro`, `test_editar_o_nome_preserva_o_padrao` |
| Excluir com confirmação; bloqueado com vínculos | ✅ | a mensagem diz onde é usado e sugere desativar | `TestExcluir`, e2e `test_excluir_sem_vinculo_e_recusa_com_vinculo` |
| — (não existe na referência) | ↔ MELHORADO | **Desativar/Reativar** e abas Ativos/Inativos: tira das escolhas sem apagar | `test_desativado_sai_da_busca_de_escolha` |
| Tabela de diárias: histórico (mais recente primeiro), nova/editar, prévia 15%/30% | ✅ | | `TestDiarias`, e2e `test_gestor_cadastra_vigencia_com_previa` |
| Diária: mínimo R$ 0,04 (P08) | ✅ | | `test_valor_minimo_quatro_centavos` |
| Diária: data de vigência escolhida | ↔ | aqui o gestor escolhe a data (o formulário da referência fixava "hoje"; a tela observada tinha calendário) | — |
| Excluir vigência | ✅ ↔ | não deixa uma faixa sem vigência | `test_nao_exclui_a_unica_vigencia_da_faixa` |
| Configuração institucional (por setor lá, por unidade aqui) | 🟡 | nome, sede, rodapé, chefia, destinatário, prazo; gestor escolhe a unidade | `TestConfiguracao` |
| Configuração: endereço em campos (CEP, logradouro…) e consulta CEP (P10) | ⛔ pendente | P10 da referência: "alinhar, sem remover campos nossos" — próximo passo | — |
| Assinantes por tipo de documento (Ofício, Justificativa) | ⛔ pendente | hoje um signatário (chefia) por unidade; P01 dispensa PT e OS | — |
| Substituição de assinante por período | ⛔ pendente | depende dos assinantes por tipo | — |
| Estados (cadastro interno) | ↔ | municípios e UFs são a lista oficial do IBGE, carregada; sem tela | — |

## Efeitos no ofício

- Cadastro incompleto **não bloqueia** a emissão (como na referência); a folha avisa
  ("O cadastro de X está incompleto (falta cargo)…") e o documento sai sem o dado, nunca
  "None" — `TestCadastroIncompletoNoOficio`.
- Servidor usado em ofício não se exclui ("usado em N participações em ofícios").

## Perfis (paridade com `viagens_cadastros/permissions.py`)

| | Operador | Gestor | Consulta |
|---|:-:|:-:|:-:|
| Ver servidores, viaturas, unidades, cargos, combustíveis | ✓ | ✓ | ✓ |
| Criar, alterar, desativar, excluir esses cadastros | ✓ | ✓ | — |
| Ver tabela de diárias e configuração da unidade | ✓ | ✓ | — |
| Alterar tabela de diárias e configuração | — | ✓ | — |

Antes desta rodada o operador só consultava; a referência dá a ele a manutenção dos
cadastros. Registrado em [decisoes.md](decisoes.md) como **adotado da referência — a confirmar**.

## Revisões (03/10/2026)

- **Segurança** (sem crítico/alto): configuração decidida por unidade na política (gestor sem
  `ver_todas_unidades` só configura a própria); o formulário do ofício mantém viatura,
  combustível e motorista já gravados mesmo desativados; parâmetros numéricos só ASCII (sem
  erro 500 com "²"); CPF/telefone/RG só com dígitos e letras ASCII; motoristas só ativos;
  a migração normaliza RG e telefone antes das unicidades e para, dizendo quais, se houver
  duplicados; excluir servidor diz de quantas viaturas ele saiu como motorista habitual.
- **UX**: "Novo…" também no topo da lista; "Sem RG" no lugar de "RG NÃO POSSUI RG"; "Excluir"
  só onde não há uso (a linha mostra "Em N ofícios"/"N servidores"); entrada no menu
  ("Todos os cadastros") com contagens e pendências ("3 incompletos"); "Cadastrar e incluir
  outro"; aviso do que falta ao abrir um incompleto; duplicado diz se o existente está
  inativo; viatura identificada pela placa; selo "Vigente" e aviso ao editar vigência;
  configuração em leitura explica que só o gestor altera. Itens restantes em
  [improvements.md](improvements.md).

## Desempenho

Consultas por tela fixas (não crescem com as linhas) — `TestConsultasPorTela` (servidores,
viaturas, unidades, cargos, diárias, entrada: ≤ 20 consultas).

## Pendências do módulo

| Item | Tipo |
|---|---|
| Assinantes por tipo + substituições por período | não bloqueante para os cadastros; bloqueante para fechar o módulo |
| Endereço da configuração em campos + CEP (P10) | não bloqueante |
| Comparação lado a lado com a referência em execução | dependência externa |
| Confirmar: operador mantém cadastros; nome e telefone únicos (regras da referência) | decisão do usuário (não bloqueia: comportamento da referência adotado) |
