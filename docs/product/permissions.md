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
| Ver servidores, viaturas, unidades | ✓ | ✓ | ✓ | — |
| Criar/alterar servidores, viaturas, unidades | — | ✓ | — | — |
| Ver tabela de diárias | ✓ | ✓ | — | — |
| Editar o texto dos documentos do rascunho (`change_oficio`, ADR 0018) | ✓ | ✓ | — | — |
| Guardar/remover textos prontos (`add_modelotexto`, `change_modelotexto`) | ✓ | ✓ | — | — |
| Excluir texto pronto de vez (`delete_modelotexto`; nunca os do sistema) | — | ✓ | — | — |
| Criar/alterar tabela de diárias | — | ✓ | — | — |
| Ver modelos de texto | ✓ | ✓ | — | — |
| Usuários (ver/criar/alterar) | — | — | — | ✓ |
| Ver trilha de auditoria (`view_eventoauditoria`) | — | — | — | ✓ |

Observações:
- A descrição do papel ADMINISTRADOR cita "configurações institucionais", mas não há
  permissão de configuração listada em `papeis.py` — **a confirmar**.
- A descrição do OPERADOR cita "termos", que ainda não existem no novo.

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
| SOLICITANTE | Eventos | cria/edita rascunhos, envia, reenvia, confirma atendimento; vê só os próprios | Planejado |
| GESTOR_DG | Eventos | único que despacha; ajusta quantidades; gerencia usuários; gera viagem | Planejado |
| ADMINISTRADOR | Plataforma | usuários e cadastros; visão transversal; **não despacha** | `ADMINISTRADOR` (parcial) |
| ANALISTA | legado | migrado para SOLICITANTE | — |
| Admin do módulo | Coffee Break / Publicações / Imprensa | cadastros contratuais/de apoio; operação aberta a todos do módulo | Planejado |

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
