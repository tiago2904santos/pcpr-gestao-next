# Papéis e permissões

## Modelo no sistema novo

Três camadas (ADR 0009):
1. **Papel** = `Group` do Django gerado de `gestao/identidade/papeis.py` (fonte única,
   versionada; `sincronizar_papeis` é idempotente).
2. **Permissão** do Django (`viagens.emitir_oficio`, `viagens.ver_todas_unidades`…).
3. **Regra por objeto** em `policies.py` do contexto (ex.: `gestao/viagens/policies.py`).
   Views, listas e menus usam só essas funções (inclusive `pode_listar`, `edita_oficios`,
   `pode_buscar_servidores`); nunca checam papel ou permissão "na mão". O menu superior
   filtra itens pela permissão declarada no registro do módulo (`Item.requer`).

Autenticação: tudo exige login (exceções: entrar, saúde); login **ou** e-mail institucional;
bloqueio progressivo (5 falhas em 15 min); sessão de 10 h.

## Matriz — Viagens e cadastros (novo)

| Permissão | OPERADOR_VIAGENS | GESTOR_VIAGENS | CONSULTA | ADMINISTRADOR |
|---|:-:|:-:|:-:|:-:|
| Ver ofícios (`view_oficio`) | ✓ (só da unidade) | ✓ | ✓ | — |
| Ver todas as unidades (`ver_todas_unidades`) | — | ✓ | ✓ | — |
| Criar rascunho (`add_oficio`) | ✓ | ✓ | — | — |
| Editar rascunho (`change_oficio`) | ✓ | ✓ | — | — |
| Emitir (`emitir_oficio`) | ✓ | ✓ | — | — |
| Excluir rascunho sem documento (`delete_oficio`) | ✓ | ✓ | — | — |
| Reabrir emitido (`reabrir_oficio`) | — | ✓ | — | — |
| Cancelar (`cancelar_oficio`) | — | ✓ | — | — |
| Gerir numeração (`gerir_numeracao`) | — | ✓ (sem tela ainda) | — | — |
| Ver roteiros (`view_roteiro`) | ✓ (só da unidade) | ✓ | ✓ | — |
| Criar/alterar/cancelar roteiros (`add_roteiro`, `change_roteiro`) | ✓ | ✓ | — | — |
| Excluir roteiro não usado (`delete_roteiro`) | ✓ | ✓ | — | — |
| Ver servidores, viaturas, unidades, cargos, combustíveis | ✓ | ✓ | ✓ | — |
| Criar/alterar/desativar/excluir (sem vínculos) servidores, viaturas, unidades, cargos, combustíveis | ✓ (referência; a confirmar) | ✓ | — | — |
| Ver tabela de diárias e configuração da unidade | ✓ | ✓ | — | — |
| Alterar configuração da unidade (`change_configuracaoinstitucional`) | — | ✓ | — | — |
| Editar o texto dos documentos do rascunho (`change_oficio`, ADR 0018) | ✓ | ✓ | — | — |
| Guardar/remover textos prontos (`add_modelotexto`, `change_modelotexto`) | ✓ | ✓ | — | — |
| Excluir texto pronto de vez (`delete_modelotexto`; nunca os do sistema) | — | ✓ | — | — |
| Criar/alterar/excluir vigência da tabela de diárias | — | ✓ | — | — |
| Ver modelos de texto | ✓ | ✓ | — | — |
| Usuários (ver/criar/alterar) | — | — | — | ✓ |
| Ver trilha de auditoria (`view_eventoauditoria`) | — | — | — | ✓ |

Observações:
- Cadastros (servidores, viaturas, unidades, cargos, combustíveis) são **globais, sem escopo
  por unidade**, como na referência: o operador mantém os de qualquer unidade (registrado em
  `docs/migration/decisoes.md` como adotado da referência, a confirmar). A configuração da
  unidade só se altera na própria unidade, ou em qualquer uma com `ver_todas_unidades`
  (`cadastros/policies.pode_alterar_configuracao`).
- A descrição do papel ADMINISTRADOR cita "configurações institucionais", mas não há
  permissão de configuração listada em `papeis.py` — **a confirmar**.
- Ordens de serviço (`viagens.*_ordemservico`): operador e gestor criam, editam, geram,
  cancelam/reativam e excluem enquanto o documento nunca foi gerado (escopo da unidade);
  consulta vê.
- Termos de autorização (`viagens.*_termoautorizacao`): operador e gestor criam, editam,
  geram documentos, cancelam/reativam e excluem (escopo da unidade, como os ofícios);
  consulta vê. Excluir de vez pelo operador é paridade com a referência — a confirmar.

## Matriz — Atendimento à imprensa (ASCOM)

| Permissão | ASCOM_IMPRENSA | ADMINISTRADOR | demais |
|---|:-:|:-:|:-:|
| Ver painel, lista, folha e exportar CSV (`imprensa.view_atendimento`) | ✓ (todos, sem unidade) | — | — |
| Registrar atendimento (`add_atendimento`) | ✓ | — | — |
| Editar e registrar andamento (`change_atendimento`) | ✓ | — | — |
| Incluir veículo pelo "outro veículo" do atendimento (`add_veiculo`) | ✓ | ✓ | — |
| Cadastros de apoio: equipe e veículos (`*_integrante`, `*_veiculo`) | ver | ✓ | — |

Regras em `gestao/imprensa/policies.py`; o módulo só aparece no menu para quem tem
`view_atendimento` (`Modulo.requer`). O papel substitui o "módulo" da referência —
decisão do agente, a confirmar ([decisoes.md](../migration/decisoes.md#atendimento-à-imprensa)).

## Matriz — Publicações (ASCOM)

| Permissão | ASCOM_PUBLICACOES | ADMINISTRADOR | demais |
|---|:-:|:-:|:-:|
| Ver painel, lista, folha e exportar CSV (`publicacoes.view_publicacao`) | ✓ (todas) | — | — |
| Registrar pauta (`add_publicacao`) | ✓ | — | — |
| Editar e registrar andamento (`change_publicacao`) | ✓ | — | — |
| Incluir unidade pelo "outra unidade" da pauta (`add_unidaderesponsavel`) | ✓ | ✓ | — |
| Cadastros de apoio: equipe e unidades (`*_integrante`, `*_unidaderesponsavel`) | ver | ✓ | — |

Regras em `gestao/publicacoes/policies.py`; o módulo só aparece para quem tem
`view_publicacao`.

## Matriz — Palestras e eventos (ASCOM)

| Permissão | ASCOM_PALESTRAS | demais |
|---|:-:|:-:|
| Ver painel, lista, folha e exportar CSV (`palestras.view_palestra`) | ✓ (todas) | — |
| Registrar, editar, andamento e resposta (`add_palestra`, `change_palestra`) | ✓ | — |
| Cadastros: palestrantes, temas, respostas padrão (`*_palestrante`, `*_tema`, `*_respostapadrao`) | ✓ | — |

Regras em `gestao/palestras/policies.py`.

## Matriz — Eventos Sociais (solicitações)

| Ação | Qualquer usuário | GESTOR_DG | ADMINISTRADOR |
|---|:-:|:-:|:-:|
| Pedir (criar), editar rascunho/devolvida, enviar, reenviar, confirmar atendimento, cancelar, anexar | as próprias | as próprias | as próprias |
| Ver lista, folha e exportar CSV | as próprias | todas (`ver_todas_solicitacoes`) | todas (`ver_todas_solicitacoes`) |
| Despachar e ajustar servidores (`despachar_solicitacao`) | — | ✓ | — |
| Gerar a viagem da solicitação deferida (unidade à escolha) | — | ✓ | — |
| Textos prontos do despacho (`*_textodespacho`) | — | ✓ | ✓ |
| Demais catálogos (tipos, serviços, equipes, órgãos, unidades móveis) | — | — | ✓ |

Solicitação que a pessoa não vê → 404. Regras em `gestao/eventos/policies.py`. Quem cria
viagens (`viagens.add_viagem`, lotado) também gera a viagem de uma solicitação que vê, só
para a própria unidade (`gestao/viagens/de_eventos.py`).

## Matriz — Coffee Break (ASCOM)

| Ação | ASCOM_COFFEE_BREAK | + ADMINISTRADOR | demais |
|---|:-:|:-:|:-:|
| Entrar no módulo (`coffee.acessar_coffee`) | ✓ (vê tudo) | ✓ | — |
| Cadastros contratuais: fornecedores, contratos, termos aditivos, lotes, ofício e protocolo | ver | ✓ | — |
| Baixar o PDF do contrato/aditivo | ✓ | ✓ | — |

`ADMINISTRADOR` sem o papel do módulo não entra (como na referência: o administrador do
módulo é o módulo + o perfil). Regras em `gestao/coffee/policies.py`.

## Regras por objeto (Ofício)

| Ação | Condição (`policies.py`) |
|---|---|
| Ver | `view_oficio` **e** (`ver_todas_unidades` **ou** ofício da unidade de lotação do usuário) |
| Criar | `add_oficio` **e** usuário lotado em uma unidade (o ofício nasce nessa unidade) |
| Editar | situação *Rascunho* **e** `change_oficio` **e** pode ver |
| Emitir | pode editar **e** `emitir_oficio` |
| Reabrir | situação *Emitido* **e** `reabrir_oficio` **e** pode ver |
| Cancelar | situação ≠ *Cancelado* **e** `cancelar_oficio` **e** pode ver |
| Excluir | *Rascunho* **sem nenhum documento** **e** `delete_oficio` **e** pode ver |

## Escopo por unidade

- O usuário tem uma **lotação** (`cadastros.Lotacao`, 1:1) que define sua unidade.
- Sem `ver_todas_unidades`, listas, painel, busca global e indicadores mostram só ofícios
  da unidade; usuário sem lotação não vê nem cria ofícios.
- **Ofício (ou documento) de outra unidade → HTTP 404**, não 403: o sistema não revela que
  o registro existe (`views._oficio_visivel`, `baixar_documento`; teste
  `test_outra_unidade_e_404`).
- Ação sem permissão sobre ofício visível → 403 com mensagem em português.

## Papéis da referência e mapeamento

A referência tinha **duas camadas**: usuário ∈ setores ∈ módulos (middleware protege o
namespace) e grupo dentro do módulo; superusuário passa por tudo.

| Referência | Escopo | O que faz | Mapeamento no novo |
|---|---|---|---|
| VIAGENS_GESTOR | Viagens | tudo, inclusive tabela de diárias e numeração | `GESTOR_VIAGENS` |
| VIAGENS_OPERADOR | Viagens | mutações em servidores, viaturas, catálogos, roteiros, ofícios, prestações | `OPERADOR_VIAGENS` (sem mutação de cadastros) — a confirmar |
| Módulo VIAGENS sem grupo | Viagens | somente consulta | `CONSULTA` |
| SOLICITANTE | Eventos | cria/edita rascunhos, envia, reenvia, confirma atendimento; vê só os próprios | todo usuário autenticado (sem papel) |
| GESTOR_DG | Eventos | único que despacha; ajusta quantidades; gerencia usuários; gera viagem | `GESTOR_DG` (despacha e vê todas; usuários ficam com ADMINISTRADOR; gerar viagem no E4) |
| ADMINISTRADOR | Plataforma | usuários e cadastros; visão transversal; **não despacha** | `ADMINISTRADOR` (parcial) |
| ANALISTA | legado | migrado para SOLICITANTE | — |
| Admin do módulo | Coffee Break / Publicações / Imprensa | cadastros contratuais/de apoio; operação aberta a todos do módulo | Coffee Break: `ASCOM_COFFEE_BREAK` + `ADMINISTRADOR` (CB1); Imprensa/Publicações: ver as matrizes acima |

Regras por objeto da referência a preservar quando os módulos vierem:
- **Eventos**: ver = criador, DG, admin; editar só em RASCUNHO/DEVOLVIDA pelo autor (travado
  até para superusuário); anexos fecham na finalização; cancelar = autor/DG/admin.
- **Demandas ASCOM**: visibilidade por setores da demanda ∩ setores do usuário; responsáveis
  restritos a setores elegíveis. (Na referência "editar = ver" mesmo em estado final — rever.)
- **Coffee Break**: operação centralizada (todos do módulo veem tudo).
- **Agenda**: cada fonte aplica a permissão do seu módulo.
- **Acessos públicos por token**: pedido de palestra, fornecedor, diário de campo, feed ICS.
- Usuário com `deve_trocar_senha` é forçado à troca.

## Auditoria

| Mecanismo | Referência | Novo |
|---|---|---|
| Trilha técnica | `RegistroAuditoria` por *signals* da aplicação (delta de campos, origem, caminho) | **Trigger do PostgreSQL** em todas as tabelas de negócio → `auditoria_evento` (antes, depois, alterados, usuário, IP, id da requisição), **cadeia de hash SHA-256**; UPDATE/DELETE bloqueados; `manage.py verificar_auditoria` |
| Histórico de negócio | por módulo (`Historico*`) | `viagens.Historico`: criado, alterado (campos), equipe, emitido (total), documento (sha256), reaberto (motivo), cancelado (motivo) |
| Escrita | aplicação | a aplicação **nunca** escreve em `auditoria_evento`; o contexto (usuário/IP/requisição) é passado pelo middleware |

Ponto de atenção: excluir um rascunho apaga seu `Historico`; a trilha fica só no trigger.
