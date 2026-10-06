# Inventário — módulo Viagens (LEGADO × NOVO)

Levantado em 06/10/2026 pelo Agente 1 (Legacy/Parity Analyst). Documento-base do loop por
página (`mission.md`): cada linha é uma unidade de trabalho com status de missão próprio.

## Como foi levantado

- **Rotas**: extraídas dos dois resolvers do Django em execução (`get_resolver()`), com o
  módulo e a docstring de cada view — LEGADO: 201 rotas sob `viagens/`, `campo/`,
  `documentos/`, `agenda/`, `relatorios/`, `dashboard/`; NOVO: 209 rotas sob `viagens/`,
  `cadastros/`, `agenda/`, `relatorios/`, `notificacoes/`, `busca/` (inclui as 24 rotas de
  editor de termo/OS/plano geradas por laço).
- **Modais e ações sem rota própria**: `<dialog>`, `data-confirmar`, menus ⋮ (`_acoes_linha`)
  e `include` de cada template de página do LEGADO (`templates/pages/viagens_*`,
  `templates/components/v32`) e do NOVO (`gestao/viagens/templates`, `gestao/cadastros/templates`,
  `templates/componentes`).
- **Smoke test** (GET autenticado, 1440px): todas as listas e cadastros dos dois sistemas
  responderam 200; os menus abaixo foram lidos da página renderizada.
- **Uso** (contagem de registros no backup do LEGADO, só leitura, sem dados pessoais):
  Roteiro 44 · Viagem 25 · Ofício 12 · PrestaçãoContas 12 (7 por servidor) · Justificativa 10 ·
  Plano 5 · RT 4 · Diário 4 · Termo 4 · OS 2 · DocumentoArtefato 58 (4 vias assinadas).
- Fichas anteriores (03–06/10) em `docs/migration/*.md` e `docs/parity/oficio.md` foram
  usadas como pista, mas a situação abaixo foi conferida no código atual.

### Legenda

| Coluna | Valores |
|---|---|
| **Tipo** | lista · detalhe · form · modal · ação (POST) · download · API (JSON/HTMX/fragmento) · autosave · componente · redirect |
| **Situação** | **existe** (mesma função, ainda que redesenhada) · **parcial** (parte da função falta ou é simulada) · **falta** (sem equivalente no NOVO) · **só no novo** · **compat** (rota de compatibilidade/redirect do LEGADO; não migrar) · **removida** (excluída por decisão registrada) |
| **Missão** | pendente → em análise → em implementação → em QA → aprovado (atualizar aqui e em `completed-pages.md`) |

Rotas abreviadas: LEGADO sem o host `:8001`; NOVO sem o host `:8000`. `<pk>` = id.

---

## 1. Navegação

### 1.1 LEGADO — `registrar_modulo("viagens")` (`viagens_cadastros/apps.py`)

Barra lateral do módulo, nesta ordem. Entrada `/viagens/` **redireciona para Roteiros**.

| # | Item | Rota | Observação |
|---|---|---|---|
| 1 | Viagens | `/viagens/viagem/` | hub da viagem (painel de 5 etapas) |
| 2 | Prestações | `/viagens/prestacoes/` | |
| 3 | Ofícios | `/viagens/oficios/` | acende também em catálogos, numeração, artefatos |
| 4 | Justificativas | `/viagens/oficios/justificativas/` | mesmo namespace de Ofícios |
| 5 | Termos | `/viagens/termos/` | |
| 6 | Roteiros | `/viagens/roteiros/` | entrada do módulo |
| 7 | Planos de trabalho | `/viagens/planos/` | |
| 8 | Ordens de serviço | `/viagens/ordens/` | |
| 9 | Cadastros ▸ (gaveta) | `/viagens/cadastros/servidores/` | Servidores · Viaturas · Unidades · Cargos · Combustíveis · Diárias · Tipos de viagem · Programas · Horários · Atividades do plano · Presets (11) |
| 10 | Modelos ▸ (gaveta) | `/viagens/cadastros/motivos-oficio/` | Motivos de ofício · Modelos de justificativa · Modelos de texto do RT |
| 11 | Configurações (só gestor) | `/viagens/oficios/institucional/` | dados institucionais + assinaturas |
| 12 | Textos dos documentos (só gestor) | `/documentos/modelos/de/viagens/` | textos-base de 7 tipos de documento |

Abas das listas (ofícios, roteiros, termos…): **Todos · Que vão acontecer · Em andamento e
realizados · Contas prestadas · Cancelados** (recortes por data da viagem). Trilha lateral
(`cad_rail`) dentro de Cadastros/Modelos.

### 1.2 NOVO — `gestao/viagens/navegacao.py`

Barra superior do módulo (App Shell). Entrada `/viagens/` = **Painel**.

| Grupo | Ordem | Item | Rota |
|---|---|---|---|
| Operação (barra) | 1 | Painel | `/viagens/` |
| | 2 | Viagens | `/viagens/viagens/` |
| | 3 | Ofícios | `/viagens/oficios/` |
| | 4 | Roteiros | `/viagens/roteiros/` |
| Documentos (menu) | 5 | Justificativas | `/viagens/justificativas/` |
| | 6 | Termos de autorização | `/viagens/termos/` |
| | 7 | Ordens de serviço | `/viagens/ordens/` |
| | 8 | Planos de trabalho | `/viagens/planos/` |
| | 9 | Prestação de contas | `/viagens/prestacoes/` |
| Cadastros (menu) | 10–20 | Todos os cadastros · Servidores · Viaturas · Unidades · Cargos · Combustíveis · Tabela de diárias · Tipos de viagem · Configuração da unidade · Textos prontos · Usuários e perfis | `/cadastros/...` |

Abas da lista de ofícios: **Todos · Rascunhos · Emitidos · Próximas viagens · Contas
prestadas · Cancelados · Arquivados** (situação do documento + data).

### 1.3 Diferenças de navegação a decidir

| # | Diferença | Efeito |
|---|---|---|
| N1 | Prestação de contas era o 2º item visível; no NOVO está dentro do menu "Documentos" | item de uso diário escondido em menu |
| N2 | Programas, Horários, Atividades do plano e Conjuntos (Presets) não estão no menu Cadastros do NOVO (só via "Todos os cadastros") | um clique a mais; LEGADO os listava na gaveta |
| N3 | "Modelos" (3 catálogos de texto) virou "Textos prontos" (um catálogo com tipos) | ok, conferir filtros por tipo |
| N4 | "Textos dos documentos" (gestor) não existe no NOVO | ver DO-19..DO-23 |
| N5 | "Numeração" removida a pedido; "Usuários e perfis" entrou no menu de Viagens | registrado em `decisions.md`/`visual-viagens-progress.md` |
| N6 | Abas das listas mudaram de "por data da viagem" para "por situação do documento + data" | conferir paridade de recortes ("Em andamento e realizados" não tem aba própria) |

---

## 2. Páginas por submódulo

### 2.1 Painel / entrada (PA)

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| PA-01 | `/viagens/` → redirect Roteiros | `/viagens/` (`viagens:painel`) | lista/painel | só no novo | LEGADO não tem painel do módulo | pendente |
| PA-02 | `/dashboard/` (indicadores globais) | `/` início + `/viagens/` | painel | parcial | referência de indicadores de viagens; fora do módulo no LEGADO | pendente |
| PA-03 | — | `/busca/` (fontes de Viagens em `busca.py`) | API | só no novo | paleta de comandos | pendente |

### 2.2 Viagens — hub (VG) · LEGADO `viagens_viagem` · NOVO `views_viagem.py`

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| VG-01 | `/viagens/viagem/` lista | `/viagens/viagens/` | lista | existe | abas + busca HTMX no NOVO | pendente |
| VG-02 | `/viagens/viagem/criar/` (POST) | `/viagens/viagens/nova/` | ação/form | existe | LEGADO cria e abre etapa 1 | pendente |
| VG-03 | `/viagens/viagem/<pk>/` painel de 5 etapas | `/viagens/viagens/<pk>/` folha única | detalhe | existe | etapas viraram blocos de uma página | pendente |
| VG-04 | `/<pk>/etapa-1/` Dados da viagem (GET/POST) | folha + `salvar/` + `autosave/` | form/autosave | existe | autosave só no NOVO | pendente |
| VG-05 | `/<pk>/etapa-2/` Roteiros | bloco "Roteiros" + `novo/roteiro/` | lista embutida | existe | | pendente |
| VG-06 | `/<pk>/etapa-3/` Ofícios / Justificativas | bloco "Ofícios e justificativas" + `novo/oficio/` | lista embutida | existe | | pendente |
| VG-07 | `/<pk>/etapa-4/` PT / OS + documentos de solicitação | blocos "Planos" e "Ordens" + `novo/<tipo>/` | lista embutida | parcial | sem os anexos de solicitação (VG-18..20) | pendente |
| VG-08 | `/<pk>/etapa-5/` Termos | bloco "Termos de autorização" + `novo/termo/` | lista embutida | existe | | pendente |
| VG-09 | Quadro de prontidão (`_prontidao`) + "Concluída" no stepper | `_conferencia.html` | componente | existe | | pendente |
| VG-10 | `/<pk>/coerencia/` "Aplicar em todos" (confirm) | `/<pk>/coerencia/` + diálogo | ação/modal | existe | | pendente |
| VG-11 | `/<pk>/acao/cancelar/` (cancela os vinculados) | `/<pk>/cancelar/` | ação/modal | existe | conferir cascata nos documentos | pendente |
| VG-12 | `/<pk>/acao/reativar/` | `/<pk>/reativar/` | ação | existe | | pendente |
| VG-13 | `/<pk>/acao/excluir/` | `/<pk>/excluir/` | ação/modal | existe | | pendente |
| VG-14 | `/<pk>/repetir/` (outra data/cidade) | `/<pk>/repetir/` + `dialogo-repetir` | modal/ação | existe | | pendente |
| VG-15 | `/<pk>/gerar-documentos/` (página) | `/<pk>/gerar-documentos/` (`lote.html`) | form | existe | visual "a fazer" | pendente |
| VG-16 | `/<pk>/baixar/` (modal Baixar documentos) | `/<pk>/baixar/` + `dialogo_baixar` | modal/download | existe | | pendente |
| VG-17 | `/<pk>/baixar-tudo/` ZIP | `/<pk>/baixar-tudo/` (PDFs numerados + LEIA-ME) | download | existe | | pendente |
| VG-18 | `/<pk>/solicitacao/anexar/` | — | ação (upload) | falta | documento de solicitação da viagem | pendente |
| VG-19 | `/<pk>/solicitacao/<anexo>/` | — | download | falta | | pendente |
| VG-20 | `/<pk>/solicitacao/<anexo>/excluir/` | — | ação | falta | | pendente |
| VG-21 | Vincular PT/OS/… já existentes (form etapa 1) | `_vinculo.html` (oficios, roteiros, planos, ordens, termos) | form | parcial | "vincular com busca" pendente (`docs/migration/viagem.md`) | pendente |
| VG-22 | Avisos de conflito no painel (`conflitos_da_viagem`) | — | componente | falta | NOVO avisa só dentro de cada documento | pendente |
| VG-23 | Diálogo de via assinada no painel | `assinados/<tipo>/<pk>/` | modal | existe | | pendente |
| VG-24 | Viagem a partir de solicitação de evento (`solicitacoes.integracao_viagens`) | `de_eventos.py` (botão na solicitação deferida) | integração | existe | NOVO não copia roteiro/anexos (decisão a confirmar) | pendente |
| VG-25 | Menu ⋮ da linha (editar, painel, repetir, reativar, cancelar, excluir) | `viagem/_acoes.html` | componente | existe | | pendente |

### 2.3 Ofícios (OF) · LEGADO `viagens_oficios` · NOVO `views.py`

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| OF-01 | `/viagens/oficios/` lista | `/viagens/oficios/` | lista | existe | abas diferentes (N6); **página atual da missão** | pendente |
| OF-02 | `/exportar/` (Excel do recorte) | `/oficios/exportar/` | download | existe | | pendente |
| OF-03 | `/novo/` (form sem registro) | `/oficios/novo/` (cria e abre) | form | existe | | pendente |
| OF-04 | `/criar/` (POST, rascunho numerado) | `/oficios/novo/` | ação | existe | | pendente |
| OF-05 | `/<pk>/editar/` (4 etapas numa página) | `/oficios/<pk>/editar/` (seções) | form | existe | visual "a fazer" | pendente |
| OF-06 | `/<pk>/autosalvar/` | `/oficios/<pk>/autosave/` | autosave | existe | | pendente |
| OF-07 | `/<pk>/acao/reabrir/` (motivo) | `/oficios/<pk>/reabrir/` | ação/modal | parcial | rota existe, sem botão (decisão pendente em `status.md`) | pendente |
| OF-08 | `/<pk>/acao/cancelar/` (motivo) | `/oficios/<pk>/cancelar/` + `dialogo_motivo` | ação/modal | existe | | pendente |
| OF-09 | `/<pk>/acao/reativar/` | `/oficios/<pk>/reativar/` (gestor, justificativa) | ação/modal | existe | | pendente |
| OF-10 | `/<pk>/acao/arquivar/` | `/oficios/<pk>/arquivar/` | ação | existe | | pendente |
| OF-11 | `/<pk>/acao/retificar/` (liga/desliga marca) | `/oficios/<pk>/retificar/` (editar emitido) | ação | parcial | semântica mudou por decisão (↔) | pendente |
| OF-12 | `/<pk>/acao/complementar/` (liga/desliga) | campo `marcador` na folha | ação | parcial | sem ação no menu ⋮ | pendente |
| OF-13 | `/<pk>/acao/excluir/` (libera número) | `/oficios/<pk>/excluir/` | ação/modal | existe | | pendente |
| OF-14 | Menu ⋮ da linha (editar, reativar, retificar, complementar, cancelar, excluir) | `oficios/_acoes.html`, `_acoes_ciclo.html` | componente | existe | | pendente |
| OF-15 | Finalizar no próprio form | `/oficios/<pk>/emitir/confirmar/` + `_prontidao` | ação/modal | existe | | pendente |
| OF-16 | `/<pk>/oficios-do-motorista/` (JSON do cartão do motorista) | — | API | falta | motorista externo (D3) existe, sem sugestão de ofício/protocolo dele | pendente |
| OF-17 | `/<pk>/baixar/` (modal Baixar documentos) | `/oficios/<pk>/baixar/` + `dialogo_baixar` | modal/download | existe | | pendente |
| OF-18 | `/<pk>/gerar/<tipo>/<formato>/` (ofício/justificativa, DOCX/PDF) | `minuta.pdf`, `documento/<tipo>.docx`, `/viagens/documentos/<id>/` | download | existe | PDF/A versionado na emissão | pendente |
| OF-19 | `/<pk>/visualizar/<tipo>/` (PDF no cartão) | `/oficios/<pk>/documento/<tipo>/folha/` | detalhe (iframe) | existe | HTML em vez de PDF | pendente |
| OF-20 | `/<pk>/documento/folha/` (modo editor) | `/oficios/<pk>/documento/<tipo>/folha/` | detalhe (iframe) | existe | | pendente |
| OF-21 | `/<pk>/documento/` (endereço antigo) | — | redirect | compat | | pendente |
| OF-22 | `/<pk>/visualizar/termo/<servidor>/` | `/termos/<pk>/folha/<chave>/` | detalhe | parcial | termos saíram do ofício para entidade própria (criar do ofício: TE-18) | pendente |
| OF-23 | `/<pk>/termos/todos/pdf/` | `/termos/<pk>/todos.pdf` | download | parcial | idem | pendente |
| OF-24 | `/<pk>/termos/<formato>/` (lote ZIP) | `/termos/<pk>/todos.<formato>` | download | parcial | idem | pendente |
| OF-25 | `/<pk>/termos/<servidor>/<formato>/` | `/termos/<pk>/documento/<chave>.<formato>` | download | parcial | idem | pendente |
| OF-26 | `/documentos/<uuid>/assinatura/` (anexar/remover via assinada) | `/viagens/assinados/oficio/<pk>/` + `.../via/<id>/remover/` | modal/ação | existe | | pendente |
| OF-27 | `/documentos/<uuid>/preview/` | `/viagens/assinados/via/<id>/` | download | existe | | pendente |
| OF-28 | Cartão "Dados para o eProtocolo" (`copiaveis`) | — | componente | falta | campos com "Copiar" para cadastrar o processo | pendente |
| OF-29 | Avisos de conflito (`avisos_conflito`: ofícios, termos, OS, solicitações, palestras) | conflitos no serviço do ofício | componente | parcial | conferir fontes cobertas | pendente |
| OF-30 | ⋮ "Importar processo do eProtocolo" na linha | — | modal | falta | ver PR-70..79 | pendente |
| OF-31 | Editor de roteiro embutido (`viagens_roteiros/_editor`) | `_itinerario`, `_destinos`, `_trecho_campos`, `_bate_volta` | componente | existe | | pendente |
| OF-32 | Equipe no form (`lista_escolha`) | `/oficios/<pk>/equipe/adicionar/`, `/remover/`, `/motorista/` + `/api/servidores/` | API (HTMX) | existe | rotas próprias só no NOVO | pendente |
| OF-33 | Diárias no form | `/oficios/<pk>/diarias/` | API (HTMX) | existe | | pendente |
| OF-34 | — | `/oficios/<pk>/resumo/` (`dialogo-resumo`) | modal (HTMX) | só no novo | janela de resumo da lista | pendente |
| OF-35 | — | `/oficios/<pk>/desarquivar/` | ação | só no novo | | pendente |
| OF-36 | — | `/oficios/<pk>/duplicar/` | ação | só no novo | | pendente |
| OF-37 | — | `/oficios/<pk>/documentos/` | API (HTMX) | só no novo | cartão de documentos | pendente |
| OF-38 | — | `/api/rota/` | API | só no novo | pernas da rota (km/tempo) | pendente |
| OF-39 | `/catalogos/<tipo>/` (+`novo/`, `<pk>/`) → catálogos de cadastro | `/cadastros/textos-prontos/` | redirect | compat | | pendente |
| OF-40 | `/numeracao/` (piso anual, gestor) | — | form | removida | excluída a pedido (regra mantida no serviço) | pendente |

### 2.4 Justificativas (JU)

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| JU-01 | `/viagens/oficios/justificativas/` | `/viagens/justificativas/` | lista | existe | | pendente |
| JU-02 | `/justificativas/nova/` (modal, escolhe ofício) | escrever pela linha pendente (`dialogo-justificativa`) | modal | existe | modelo 1:1 no ofício | pendente |
| JU-03 | `/justificativas/<pk>/editar/` (modal) | `/justificativas/<pk>/salvar/` | modal/ação | existe | | pendente |
| JU-04 | `/justificativas/<pk>/excluir/` | `salvar` com `apagar=1` ("Apagar justificativa") | ação/modal | existe | | pendente |
| JU-05 | `/justificativas/<pk>/baixar/` (modal) | `/justificativas/<pk>/baixar/` | modal/download | existe | | pendente |
| JU-06 | Documento da justificativa (gerar PDF/DOCX) | `/oficios/<pk>/documento/justificativa.docx`, folha + editor | download | existe | | pendente |
| JU-07 | Data e assinante próprios da justificativa | — | form | parcial | snapshot só no `Documento.dados` (`docs/parity/oficio.md`) | pendente |

### 2.5 Termos de autorização (TE) · LEGADO `viagens_termos` · NOVO `views_termos.py` — **2ª página da missão**

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| TE-01 | `/viagens/termos/` | `/viagens/termos/` | lista | existe | referência visual aprovada | pendente |
| TE-02 | `/termos/api/oficios/` | `/viagens/api/oficios/` | API | existe | | pendente |
| TE-03 | `/termos/novo/` | `/termos/novo/` | form | existe | | pendente |
| TE-04 | `/termos/<pk>/editar/` | `/termos/<pk>/` | form | existe | | pendente |
| TE-05 | `/termos/<pk>/preview/` | `/termos/<pk>/folha/<chave>/` | detalhe | existe | | pendente |
| TE-06 | `/termos/<pk>/preview/<servidor>/` | `/termos/<pk>/folha/<id>/` | detalhe | existe | | pendente |
| TE-07 | `/termos/<pk>/baixar/` (modal) | `/termos/<pk>/baixar/` | modal/download | existe | | pendente |
| TE-08 | `/termos/<pk>/todos/pdf/` | `/termos/<pk>/todos.pdf` | download | existe | | pendente |
| TE-09 | `/termos/<pk>/gerar/<formato>/` (ZIP) | `/termos/<pk>/todos.<formato>` | download | existe | | pendente |
| TE-10 | `/termos/<pk>/gerar/viatura/<formato>/` | `/termos/<pk>/documento/viatura.<formato>` | download | existe | | pendente |
| TE-11 | `/termos/<pk>/gerar/<servidor>/<formato>/` (0 = genérico) | `/termos/<pk>/documento/<id>.<formato>` ou `generico.<formato>` | download | existe | | pendente |
| TE-12 | `/termos/<pk>/acao/cancelar/` | `/termos/<pk>/cancelar/` | ação | existe | | pendente |
| TE-13 | `/termos/<pk>/acao/reativar/` | `/termos/<pk>/reativar/` | ação | existe | | pendente |
| TE-14 | `/termos/<pk>/acao/excluir/` | `/termos/<pk>/excluir/` | ação/modal | existe | | pendente |
| TE-15 | Editor (`documentos/editor/termo_autorizacao/<pk>/`) | `/termos/<pk>/editor/<chave>/{estado,salvar,restaurar,modelo,original,paginas,presenca,textos}/` | API | existe | | pendente |
| TE-16 | Diálogo de via assinada | `/viagens/assinados/termo/<pk>/` | modal | existe | | pendente |
| TE-17 | Menu ⋮ (editor, editar, prévia, excluir) | `termos/_acoes.html` | componente | existe | | pendente |
| TE-18 | — | `/termos/do-oficio/<id>/` + `/api/oficios/<id>/para-termo/` | ação/API | só no novo | criar a partir do ofício | pendente |
| TE-19 | — | `/termos/<pk>/autosave/` | autosave | só no novo | | pendente |
| TE-20 | — | `/termos/<pk>/finalizar/` | ação | só no novo | | pendente |
| TE-21 | — | `/termos/<pk>/duplicar/` | ação | só no novo | | pendente |
| TE-22 | — | `/termos/<pk>/editor/<chave>/aplicar-em-todos/` | ação | só no novo | | pendente |
| TE-23 | ⋮ "Importar processo do eProtocolo" | — | modal | falta | ver PR-70..79 | pendente |
| TE-24 | Cartão "Dados para o eProtocolo" (`copiaveis`) | — | componente | falta | | pendente |

### 2.6 Roteiros (RO) · LEGADO `viagens_roteiros` · NOVO `views_roteiros.py` — referência visual aprovada

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| RO-01 | `/viagens/roteiros/` | `/viagens/roteiros/` | lista | existe | | pendente |
| RO-02 | `/roteiros/novo/` | `/roteiros/novo/` | form | existe | | pendente |
| RO-03 | `/roteiros/<pk>/editar/` | `/roteiros/<pk>/editar/` | form | existe | | pendente |
| RO-04 | `/roteiros/<pk>/` → editar | — | redirect | compat | | pendente |
| RO-05 | `/roteiros/previa-diarias/` | `/roteiros/previa-diarias/` | API | existe | | pendente |
| RO-06 | `/roteiros/calcular-rota/` (mapa) | `/viagens/api/rota/` | API | existe | | pendente |
| RO-07 | `/roteiros/estimar-trecho/` | `/viagens/api/rota/` | API | existe | | pendente |
| RO-08 | `/roteiros/autosave/` (cria na 1ª) | `/roteiros/autosave/` | autosave | existe | | pendente |
| RO-09 | `/roteiros/<pk>/autosave/` | `/roteiros/autosave/` | autosave | existe | | pendente |
| RO-10 | `/roteiros/<pk>/calcular/` | prévia + autosave | ação | existe | | pendente |
| RO-11 | `/roteiros/<pk>/dados/` (JSON para reaproveitar na montagem) | "Usar um roteiro cadastrado" no ofício (cópia) | API | parcial | conferir reaproveitar dentro do editor de roteiro | pendente |
| RO-12 | `/roteiros/<pk>/cancelar/` | `/roteiros/<pk>/cancelar/` | ação | existe | | pendente |
| RO-13 | `/roteiros/<pk>/reativar/` | `/roteiros/<pk>/reativar/` | ação | existe | | pendente |
| RO-14 | `/roteiros/<pk>/excluir/` | `/roteiros/<pk>/excluir/` | ação/modal | existe | | pendente |
| RO-15 | Calendário "Datas da ida e da volta" | `pc-data` / `_duracao` | modal | existe | | pendente |
| RO-16 | — | `/roteiros/previa-trechos/` | API | só no novo | bate-voltas | pendente |
| RO-17 | — | `/roteiros/<pk>/oficios/` | modal (HTMX) | só no novo | "usado em N ofícios" | pendente |
| RO-18 | — | `/roteiros/<pk>/criar-oficio/` | ação | só no novo | | pendente |

### 2.7 Planos de trabalho (PT) · LEGADO `viagens_planos` · NOVO `views_planos.py`

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| PT-01 | `/viagens/planos/` | `/viagens/planos/` | lista | existe | | pendente |
| PT-02 | `/planos/criar/` | `/planos/novo/` | ação/form | existe | | pendente |
| PT-03 | `/planos/<pk>/editar/` | `/planos/<pk>/` | form | existe | | pendente |
| PT-04 | `/planos/<pk>/autosalvar/` | `/planos/<pk>/autosave/` | autosave | existe | | pendente |
| PT-05 | `/planos/<pk>/calcular/` (prévia ao vivo das diárias) | diárias recalculadas no autosave | API | parcial | sem prévia dedicada | pendente |
| PT-06 | `/planos/<pk>/eventos/adicionar/` | `/planos/<pk>/eventos/salvar/` + `dialogo-evento` | modal/ação | existe | | pendente |
| PT-07 | `/planos/<pk>/eventos/<ev>/editar/` | `/planos/<pk>/eventos/salvar/` | modal/ação | existe | | pendente |
| PT-08 | `/planos/<pk>/eventos/<ev>/remover/` | `/planos/<pk>/eventos/<ev>/remover/` | ação | existe | | pendente |
| PT-09 | `/planos/<pk>/visualizar/` (PDF no cartão) | `/planos/<pk>/folha/` | detalhe | existe | | pendente |
| PT-10 | `/planos/<pk>/resultados/` | `/planos/<pk>/resultados/` | form | existe | visual "a fazer" | pendente |
| PT-11 | `/planos/<pk>/gerar/<formato>/` | `/planos/<pk>/documento.<formato>` + `/finalizar/` | download | existe | | pendente |
| PT-12 | `/planos/<pk>/acao/cancelar/` | `/planos/<pk>/cancelar/` | ação | existe | | pendente |
| PT-13 | `/planos/<pk>/acao/reativar/` | `/planos/<pk>/reativar/` | ação | existe | | pendente |
| PT-14 | `/planos/<pk>/acao/excluir/` | `/planos/<pk>/excluir/` | ação/modal | existe | | pendente |
| PT-15 | Editor (`documentos/editor/plano_trabalho/<pk>/`) | `/planos/<pk>/editor/{...}` (8 rotas) | API | existe | | pendente |
| PT-16 | Calendário do deslocamento | `pc-data` | modal | existe | | pendente |
| PT-17 | Preset de atividades | `dialogo-conjunto` | modal | existe | | pendente |
| PT-18 | Diálogo de via assinada | `/viagens/assinados/plano/<pk>/` | modal | existe | | pendente |
| PT-19 | Aba "Finalizados" | — | lista | parcial | depende da prestação (`planos.md`) | pendente |
| PT-20 | — | `/planos/do-oficio/<id>/` | ação | só no novo | | pendente |
| PT-21 | — | `/planos/<pk>/duplicar/` | ação | só no novo | | pendente |
| PT-22 | — | `/planos/<pk>/baixar/` | download | só no novo | | pendente |

### 2.8 Ordens de serviço (OS) · LEGADO `viagens_ordens` · NOVO `views_ordens.py`

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| OS-01 | `/viagens/ordens/` | `/viagens/ordens/` | lista | existe | | pendente |
| OS-02 | `/ordens/api/oficios/` | `/viagens/api/oficios/` | API | existe | | pendente |
| OS-03 | `/ordens/nova/` | `/ordens/nova/` | form | existe | | pendente |
| OS-04 | `/ordens/<pk>/editar/` | `/ordens/<pk>/` | form | existe | visual "a fazer" | pendente |
| OS-05 | `/ordens/<pk>/autosalvar/` | `/ordens/<pk>/autosave/` | autosave | existe | | pendente |
| OS-06 | `/ordens/<pk>/gerar/<formato>/` (+ "Emitir versão N+1") | `/ordens/<pk>/documento.<formato>` + `/finalizar/` | download/ação | parcial | conferir emissão de nova versão | pendente |
| OS-07 | ⋮ Visualizar (PDF) | `/ordens/<pk>/folha/` | detalhe | existe | | pendente |
| OS-08 | `/ordens/documentos/<uuid>/assinatura/` | `/viagens/assinados/ordem/<pk>/` | modal/ação | existe | | pendente |
| OS-09 | `/ordens/<pk>/acao/cancelar/` | `/ordens/<pk>/cancelar/` | ação | existe | | pendente |
| OS-10 | `/ordens/<pk>/acao/reativar/` | `/ordens/<pk>/reativar/` | ação | existe | | pendente |
| OS-11 | `/ordens/<pk>/acao/excluir/` | `/ordens/<pk>/excluir/` | ação/modal | existe | | pendente |
| OS-12 | Editor (`documentos/editor/ordem_servico/<pk>/`) | `/ordens/<pk>/editor/{...}` (8 rotas) | API | existe | | pendente |
| OS-13 | — | `/ordens/do-oficio/<id>/` | ação | só no novo | | pendente |
| OS-14 | — | `/ordens/<pk>/duplicar/` | ação | só no novo | | pendente |
| OS-15 | — | `/ordens/<pk>/baixar/` | download | só no novo | | pendente |

### 2.9 Prestação de contas (PR) · LEGADO `viagens_prestacoes` · NOVO `views_prestacao/diario/relatorio/anexos.py`

LEGADO: um assistente de 3 etapas **por servidor** (diário → RT → documentos), com texto
compartilhado pela equipe. NOVO: folhas **por equipe** (`/prestacoes/equipe/<pk>/...`) e
ações por servidor (`/prestacoes/<pk>/...`).

#### Lista, cartão e ações

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| PR-01 | `/viagens/prestacoes/` | `/viagens/prestacoes/` | lista | existe | | pendente |
| PR-02 | `/prestacoes/exportar.xlsx` | `/prestacoes/exportar/` | download | existe | | pendente |
| PR-03 | `/servidor-prestacao/<ps>/finalizar/` (conclui/reabre) | `/prestacoes/<ps>/finalizar/` · `reabrir/` | ação/modal | existe | | pendente |
| PR-04 | `/servidor-prestacao/<ps>/arquivar/` | `/prestacoes/<ps>/arquivar/` · `desarquivar/` | ação/modal | existe | | pendente |
| PR-05 | `/servidor-prestacao/<ps>/envio/<acao>/` (enviar, aprovar, devolver) | `/prestacoes/<ps>/enviar/` · `aprovar/` · `devolver/` + `_envio` | modal/ação | existe | | pendente |
| PR-06 | `/prestacao/<pc>/equipe/<acao>/` | `/prestacoes/equipe/<pk>/<acao>/` | ação/modal | existe | | pendente |
| PR-07 | `/servidor-prestacao/<ps>/solicitacao/autosave/` (nº, liberação, saque) | `/prestacoes/<ps>/autosave/` + `/salvar/` | autosave | existe | | pendente |
| PR-08 | `/prestacao/<pc>/protocolo/atualizar/` (andamento no eProtocolo) | — | ação | falta | dependência externa (eProtocolo) | pendente |
| PR-09 | Link WhatsApp do servidor no cartão | — | componente | falta | | pendente |
| PR-10 | `/servidor-prestacao/<ps>/downloads/` (JSON do modal Baixar) | — | API | parcial | NOVO baixa pelo pacote (PR-42/43) | pendente |
| PR-11 | `/servidor-prestacao/<ps>/baixar/` (POST, itens marcados) | — | download | parcial | idem | pendente |
| PR-12 | `/servidor-prestacao/<ps>/downloads/compilado/` | `/prestacoes/servidor/<ps>/pacote/` | download | existe | | pendente |
| PR-13 | `/servidor-prestacao/<ps>/downloads/assinado/<item>/<formato>/` | `/prestacoes/anexos/<id>/`, `/assinados/via/<id>/` | download | existe | | pendente |
| PR-14 | Rotas de compatibilidade por `pc_pk` (`oficio/<pk>/abrir`, `prestacao/<pc>/arquivar`, `finalizar`, `documentos`, `rt`, `diario`, `diario/editar-roteiro`, `diario/motorista`, `consolidado`) | — | redirect | compat | 9 rotas | pendente |

#### Diário de bordo

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| PR-20 | `/servidor-prestacao/<ps>/diario/` (etapa 1) | `/prestacoes/equipe/<pk>/diario/` | form | existe | visual "a fazer" | pendente |
| PR-21 | `/servidor-prestacao/<ps>/diario/autosave/` · `/diario/<pk>/autosave/` | `/prestacoes/equipe/<pk>/diario/autosave/` | autosave | existe | 2 rotas → 1 | pendente |
| PR-22 | `/servidor-prestacao/<ps>/diario/motorista/` (`pc-dialogo-motorista`) | `/prestacoes/equipe/<pk>/diario/motorista/` | modal/ação | existe | | pendente |
| PR-23 | `/servidor-prestacao/<ps>/diario/editar-roteiro/` (cópia ajustada no editor de roteiros) | `/prestacoes/equipe/<pk>/diario/realizada/<acao>/` | form/ação | existe | redesenhado (`TrechoRealizado`) | pendente |
| PR-24 | `/servidor-prestacao/<ps>/diario/distancia/<linha>/` (corrige distância) | — | ação | falta | correção na tabela permanente | pendente |
| PR-25 | `/servidor-prestacao/<ps>/diario/celular/<acao>/` (gera/troca/revoga link) | — | ação | falta | ver CA-01..04 | pendente |
| PR-26 | `/diario/<pk>/download/` (+`<formato>/`) | `/prestacoes/equipe/<pk>/diario/<formato>/` | download | existe | | pendente |
| PR-27 | Editor/visualizador do texto do diário (`_visualizador`) | — | componente | parcial | NOVO só gera o documento | pendente |
| PR-28 | — | `/prestacoes/equipe/<pk>/diario/salvar/` | ação | só no novo | sem JavaScript | pendente |

#### Relatório técnico

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| PR-30 | `/servidor-prestacao/<ps>/rt/` (etapa 2) | `/prestacoes/equipe/<pk>/relatorio/` | form | existe | visual "a fazer" | pendente |
| PR-31 | `/servidor-prestacao/<ps>/rt/autosave/` · `/rt/<pk>/autosave/` | `/prestacoes/equipe/<pk>/relatorio/autosave/` | autosave | existe | 2 rotas → 1 | pendente |
| PR-32 | `/servidor-prestacao/<ps>/rt/sugerir/<campo>/` | `/prestacoes/equipe/<pk>/relatorio/sugerir/<campo>/` | API | existe | | pendente |
| PR-33 | `/rt/servidor/<ps>/download/` (+`<formato>/`) | `/prestacoes/equipe/<pk>/relatorio/<ps>/<formato>/` | download | existe | | pendente |
| PR-34 | `/modelos-texto/criar-do-campo/` ("Salvar como modelo") | `/cadastros/textos-prontos/salvar/` (JSON) | modal/API | parcial | nome repetido numerado pendente | pendente |
| PR-35 | Editor/visualizador do texto do RT (`_visualizador`) | — | componente | parcial | | pendente |
| PR-36 | — | `/prestacoes/equipe/<pk>/relatorio/salvar/` | ação | só no novo | | pendente |

#### Documentos, anexos e carimbo

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| PR-40 | `/servidor-prestacao/<ps>/documentos/` (etapa 3) | `/prestacoes/equipe/<pk>/documentos/` | form | existe | visual "a fazer" | pendente |
| PR-41 | `/prestacao/<pc>/despacho/autosave/` (upload do despacho) | `/prestacoes/equipe/<pk>/documentos/anexar/` | autosave/upload | existe | | pendente |
| PR-42 | `/prestacao/<pc>/despacho-assinado/anexar/` | `/prestacoes/equipe/<pk>/documentos/anexar/` | ação (upload) | existe | | pendente |
| PR-43 | `/prestacao/<pc>/oficio-assinado/anexar/` (lê os nºs de solicitação) | via assinada do ofício (`/assinados/oficio/<pk>/`) | ação (upload) | parcial | sem leitura automática dos números | pendente |
| PR-44 | `/servidor-prestacao/<ps>/assinado/<tipo>/anexar/` (RT/diário assinados) | `/prestacoes/equipe/<pk>/documentos/anexar/` | ação (upload) | existe | | pendente |
| PR-45 | `/servidor-prestacao/<ps>/comprovante/autosave/` | `anexar/` + `/prestacoes/anexos/<id>/comprovante/` | autosave/ação | existe | valor/data/operação | pendente |
| PR-46 | `/prestacao/<pc>/anexo/<id>/excluir/` | `/prestacoes/anexos/<id>/remover/` | ação/modal | existe | | pendente |
| PR-47 | `/prestacao/<pc>/anexo/<id>/conteudo/` | `/prestacoes/anexos/<id>/` | download | existe | | pendente |
| PR-48 | `/prestacao/<pc>/anexo/<id>/restaurar/` | `/prestacoes/anexos/<id>/restaurar/` | ação | existe | | pendente |
| PR-49 | Histórico de alterações (`historico_alteracoes`) | — | componente | parcial | trilha existe no banco, sem linha do tempo na tela | pendente |
| PR-50 | Cartão "Dados para o eProtocolo" (`copiaveis`) | — | componente | falta | | pendente |
| PR-51 | `/prestacao/<pc>/oficio-assinado/carimbo/` (arrastar o nº sobre a página) | `/prestacoes/servidor/<ps>/carimbo/` (posição em %) | form | parcial | sem arrastar e sem posição automática | pendente |
| PR-52 | `/prestacao/<pc>/oficio-assinado/cru/` (PDF sem números) | `/prestacoes/equipe/<pk>/carimbo/previa/` | download | parcial | | pendente |

#### Pacotes

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| PR-55 | `/servidor-prestacao/<ps>/consolidado/download/` | `/prestacoes/servidor/<ps>/pacote/` | download | existe | | pendente |
| PR-56 | `/prestacao/<pc>/pacotes.zip` (+ PENDENCIAS.txt) | `/prestacoes/equipe/<pk>/pacotes/` | download | existe | | pendente |
| PR-57 | `/servidor-prestacao/<ps>/pacote/revisar/` (ordem, giro, páginas ocultas) | — | form | falta | | pendente |
| PR-58 | `/servidor-prestacao/<ps>/pacote/revisar/pdf/` | — | download | falta | | pendente |

#### Importação do processo (eProtocolo / PDF)

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| PR-70 | `/prestacoes/importar/` (da lista) | — | ação (upload) | falta | lê o PDF do processo; aplica sozinho quando seguro | pendente |
| PR-71 | `/prestacao/<pc>/importar/` | — | ação (upload) | falta | | pendente |
| PR-72 | `/importar/oficio/<pk>/` (⋮ de Ofícios) | — | ação (upload) | falta | | pendente |
| PR-73 | `/importar/termo/<pk>/` (⋮ de Termos) | — | ação (upload) | falta | | pendente |
| PR-74 | `/importacao/<pk>/` (conferência) | — | detalhe/form | falta | | pendente |
| PR-75 | `/importacao/<pk>/aplicar/` | — | ação | falta | | pendente |
| PR-76 | `/importacao/<pk>/descartar/` | — | ação/modal | falta | | pendente |
| PR-77 | `/importacao/<pk>/desfazer/` | — | ação/modal | falta | | pendente |
| PR-78 | `/importacao/<pk>/arquivo/` (PDF para miniaturas) | — | download | falta | | pendente |
| PR-79 | Diálogo "Importar processo" (`_importar_dialogo`) | — | modal | falta | | pendente |

#### Modelos de texto do RT

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| PR-80 | `/prestacoes/modelos-texto/` → `cadastros/modelos-texto-rt/` | `/cadastros/textos-prontos/` (tipos `rt_*`) | redirect | compat | | pendente |
| PR-81 | `/modelos-texto/<pk>/editar/` · `/excluir/` | `/cadastros/textos-prontos/salvar/` · `/<pk>/excluir/` | redirect | compat | 2 rotas | pendente |

### 2.10 Diário no celular — link público (CA) · LEGADO `campo_diario`

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| CA-01 | `/campo/diario/<token>/` (página do motorista, sem login) | — | form | falta | PWA, funciona sem internet | pendente |
| CA-02 | `/campo/diario/<token>/enviar/` | — | API | falta | sincroniza o que foi digitado | pendente |
| CA-03 | `/campo/diario/<token>/manifest.webmanifest` | — | API | falta | app instalável | pendente |
| CA-04 | `/campo/diario/sw.js` | — | API | falta | service worker | pendente |

### 2.11 Cadastros de viagens (CD) · LEGADO `viagens_cadastros` (+ `viagens_oficios` institucional/numeração) · NOVO `gestao/cadastros`

LEGADO: CRUD genérico por *slug* (`/viagens/cadastros/<slug>/`, `novo/`, `<pk>/editar/` em
modal, `<pk>/excluir/` com diálogo, `<pk>/padrao/`). NOVO: lista + `dialogo-cadastro` +
`<slug>/salvar/`, `<slug>/<pk>/{ativo,padrao,excluir}/`.

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| CD-01 | `/viagens/cadastros/` → Servidores | `/cadastros/` (índice com cartões) | lista | existe | | pendente |
| CD-02 | `servidores/` | `/cadastros/servidores/` | lista | existe | | pendente |
| CD-03 | `servidores/novo/` · `<pk>/editar/` (modal) | `/cadastros/servidores/salvar/` + diálogo | modal/ação | existe | | pendente |
| CD-04 | `servidores/<pk>/excluir/` (diálogo/página de confirmação) | `/cadastros/servidores/<pk>/excluir/` | ação/modal | existe | | pendente |
| CD-05 | `viaturas/` | `/cadastros/viaturas/` | lista | existe | | pendente |
| CD-06 | `viaturas/novo/` · `<pk>/editar/` | `/cadastros/viaturas/salvar/` + diálogo | modal/ação | existe | | pendente |
| CD-07 | `viaturas/<pk>/excluir/` | `/cadastros/viaturas/<pk>/excluir/` | ação/modal | existe | | pendente |
| CD-08 | `unidades/` (+novo/editar/excluir) | `/cadastros/unidades/` + `salvar_catalogo`/`excluir` | lista/modal | existe | | pendente |
| CD-09 | `cargos/` (+padrão) | `/cadastros/cargos/` | lista/modal | existe | | pendente |
| CD-10 | `combustiveis/` (+padrão) | `/cadastros/combustiveis/` | lista/modal | existe | | pendente |
| CD-11 | `diarias/` (histórico de vigências) | `/cadastros/diarias/` | lista | existe | | pendente |
| CD-12 | `diarias/nova/` · `<pk>/editar/` (modal) | `/cadastros/diarias/salvar/` + `dialogo-vigencia` | modal/ação | existe | | pendente |
| CD-13 | `diarias/<pk>/excluir/` | `/cadastros/diarias/<pk>/excluir/` | ação/modal | existe | | pendente |
| CD-14 | `tipos-viagem/` | `/cadastros/tipos-de-viagem/` | lista/modal | existe | | pendente |
| CD-15 | `programas/` | `/cadastros/programas/` | lista/modal | existe | fora do menu (N2) | pendente |
| CD-16 | `horarios/` | `/cadastros/horarios/` + `dialogo-horario` | lista/modal | existe | fora do menu (N2) | pendente |
| CD-17 | `atividades-pt/` | `/cadastros/atividades/` | lista/modal | existe | fora do menu (N2) | pendente |
| CD-18 | `presets-pt/` (+padrão) | `/cadastros/conjuntos/` | lista/modal | existe | fora do menu (N2) | pendente |
| CD-19 | `motivos-oficio/` (+padrão) | `/cadastros/textos-prontos/` (tipo motivo) | lista/modal | existe | | pendente |
| CD-20 | `modelos-justificativa/` (+padrão) | `/cadastros/textos-prontos/` (tipo justificativa) | lista/modal | existe | | pendente |
| CD-21 | `modelos-texto-rt/` (+padrão) | `/cadastros/textos-prontos/` (tipos `rt_*`) | lista/modal | existe | | pendente |
| CD-22 | `<slug>/<pk>/padrao/` | `/cadastros/<slug>/<pk>/padrao/` · `/textos-prontos/<pk>/padrao/` | ação | existe | | pendente |
| CD-23 | `/viagens/oficios/institucional/` (Configurações dos documentos, gestor) | `/cadastros/configuracao/` | form | existe | por unidade no NOVO | pendente |
| CD-24 | `substituicoes-assinatura/` (CRUD) | `/cadastros/configuracao/substituicoes/salvar/` + `dialogo-substituicao` | modal/ação | existe | | pendente |
| CD-25 | `/viagens/oficios/catalogos/assinaturas/` → configurações | — | redirect | compat | | pendente |
| CD-26 | `api/cep/<cep>/` (ViaCEP) | — | API | falta | preenchimento de endereço | pendente |
| CD-27 | `/buscar-endereco/` (core, Nominatim) | — | API | falta | campos Endereço/Bairro/CEP | pendente |
| CD-28 | `/cadastros/municipios/buscar/` (core) | `/cadastros/api/municipios/` | API | existe | | pendente |
| CD-29 | — | `/cadastros/<slug>/<pk>/ativo/` · `/textos-prontos/<pk>/ativo/` · `/substituicoes/<pk>/ativo/` | ação | só no novo | Ativo/Inativo | pendente |
| CD-30 | — | `/cadastros/api/servidores/` | API | só no novo | | pendente |
| CD-31 | (contas, fora de Viagens) | `/cadastros/usuarios/` + `salvar/` + `<pk>/ativo/` | lista/modal | só no novo | entrou no menu de Viagens | pendente |
| CD-32 | Cadastro rápido em modal a partir dos formulários | `componentes/cadastro_rapido`, `dialogo_servidor`, `dialogo_viatura` | modal | existe | | pendente |

### 2.12 Documentos e editor (DO) · LEGADO `documentos/` · NOVO `views_editor*.py`, `views_assinados.py`, `views_pacotes.py`

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| DO-01 | `/documentos/<uuid>/baixar/` | `/viagens/documentos/<id>/` | download | existe | | pendente |
| DO-02 | `/documentos/<uuid>/abrir/` | `/viagens/assinados/via/<id>/`, `minuta.pdf` | download | existe | | pendente |
| DO-03 | `/documentos/<uuid>/conferir-assinado/` (prévia da conferência antes de anexar) | conferência depois de anexar (`views_assinados.anexar`) | modal/API | parcial | prévia pendente (`assinado.js`) | pendente |
| DO-04 | `/documentos/editor/<tipo>/<pk>/` (endereço antigo) | — | redirect | compat | | pendente |
| DO-05 | `/editor/<tipo>/<pk>/folha/` | `.../documento/<tipo>/folha/`, `termos/<pk>/folha/<chave>/`, `ordens/<pk>/folha/`, `planos/<pk>/folha/` | detalhe (iframe) | existe | | pendente |
| DO-06 | `/editor/<tipo>/<pk>/embutido/` | `oficios/_editor.html` no cartão Documentos | componente | existe | | pendente |
| DO-07 | `/editor/<tipo>/<pk>/campos/<chave>/` (GET painel, PATCH grava) | `/oficios/<pk>/documento/<tipo>/campos/<chave>/` | API | parcial | só no ofício (termo/OS/plano sem campos vinculados) | pendente |
| DO-08 | `/editor/<tipo>/<pk>/blocos/<chave>/` (override de parágrafo) | `.../original/` + `.../salvar/` (regiões) | API | existe | redesenhado (ADR 0018) | pendente |
| DO-09 | `/editor/<tipo>/<pk>/quebras/<chave>/` | quebras no `.../salvar/` | API | existe | | pendente |
| DO-10 | `/editor/<tipo>/<pk>/paginas/` | `.../paginas/` | API | existe | | pendente |
| DO-11 | `/editor/<tipo>/<pk>/paragrafos/<chave>/` (parágrafo extra) | — | API | parcial | conferir se regiões livres cobrem | pendente |
| DO-12 | `/editor/<tipo>/<pk>/textos/<chave>/` | `.../textos/` + `.../textos/<id>/remover/` + `dialogo_guardar_texto` | API/modal | existe | | pendente |
| DO-13 | `/editor/<tipo>/<pk>/presenca/` | `.../presenca/` | API | existe | | pendente |
| DO-14 | `/editor/<tipo>/<pk>/completo/` (editor completo, página) | editor no visualizador (`_editor.html`) | form | existe | sem página separada (decisão) | pendente |
| DO-15 | `/completo/folha/` | `.../folha/?versao=N` | detalhe | existe | | pendente |
| DO-16 | `/completo/salvar/` | `.../salvar/` | API | existe | | pendente |
| DO-17 | `/completo/modelo/` (voltar ao modelo) | `.../modelo/` | ação | existe | | pendente |
| DO-18 | `/completo/restaurar/<versao>/` | `.../restaurar/<n>/` + `historico-*` | ação/modal | existe | | pendente |
| DO-19 | `/documentos/modelos/` (tipos) | — | lista | falta | textos-base dos modelos (gestor) | pendente |
| DO-20 | `/documentos/modelos/de/viagens/` (menu "Textos dos documentos") | — | lista | falta | | pendente |
| DO-21 | `/documentos/modelos/<tipo>/` (7 tipos de Viagens) | — | form | falta | | pendente |
| DO-22 | `/documentos/modelos/<tipo>/folha/` | — | detalhe (iframe) | falta | | pendente |
| DO-23 | `/documentos/modelos/<tipo>/salvar/` | — | API | falta | | pendente |
| DO-24 | Diálogo "Baixar documentos" (`dialogo_baixar`) | `componentes/dialogo_baixar` + `/viagens/{viagens,oficios,justificativas,termos,ordens,planos}/<pk>/baixar/` | modal | existe | | pendente |
| DO-25 | Diálogo de via assinada (`dialogo_assinado`) | `componentes/dialogo_assinado` + `/viagens/assinados/<tipo>/<pk>/[<chave>/]` (`anexar.html`) | modal/ação | existe | visual "a fazer" | pendente |
| DO-26 | Remover via assinada (POST em `assinatura`) | `/viagens/assinados/via/<id>/remover/` | ação | existe | | pendente |
| DO-27 | Confirmações `data-confirmar` | `parciais/dialogo_confirmacao` | modal | existe | | pendente |

### 2.13 Agenda, conflitos, avisos e integrações (AG)

| ID | LEGADO | NOVO | Tipo | Situação | Observações | Missão |
|---|---|---|---|---|---|---|
| AG-01 | `/agenda/` (ofícios, termos, OS no calendário) | `/agenda/` (`viagens/agenda.py`) | lista | existe | | pendente |
| AG-02 | `/agenda/eventos/` (feed) | `/agenda/` | API | existe | | pendente |
| AG-03 | `/agenda/detalhe/<fonte>/<pk>/` (dossiê no modal) | dossiê da agenda | modal | existe | | pendente |
| AG-04 | `/agenda/escala/` | `/agenda/escala/` | lista | existe | | pendente |
| AG-05 | `/agenda/pauta.pdf` | `/agenda/pauta/` | download | existe | | pendente |
| AG-06 | `/agenda/ics/<token>.ics` | `/agenda/ics/<token>.ics` | API | existe | | pendente |
| AG-07 | `/agenda/assinatura/` | `/agenda/assinatura/` | ação | existe | | pendente |
| AG-08 | `/conflitos/` (página de conflitos de agenda) | avisos dentro de cada documento | lista | parcial | sem tela consolidada | pendente |
| AG-09 | Avisos de prazo de prestação/viagem (rotina + notificações) | `viagens/avisos.py` + `/notificacoes/` | componente | existe | | pendente |
| AG-10 | `/relatorios/` + `exportar/` (inclui viagens) | `/relatorios/` + `planilha/` | lista/download | existe | | pendente |
| AG-11 | eProtocolo: abrir o protocolo ao gravar o ofício (`protocolo_services`, origem MANUAL/EPROTOCOLO/…) | `integracoes/eprotocolo` (porta + adaptador simulado), campo de origem | integração | parcial | credenciamento externo pendente | pendente |
| AG-12 | eProtocolo: andamento do processo | — | integração | falta | ver PR-08 | pendente |

---

## 3. Contagens e ordem de trabalho

### 3.1 Contagem por submódulo

| Submódulo | Linhas | existe | parcial | falta | só no novo | compat | removida |
|---|---:|---:|---:|---:|---:|---:|---:|
| PA Painel | 3 | 0 | 1 | 0 | 2 | 0 | 0 |
| VG Viagens | 25 | 19 | 2 | 4 | 0 | 0 | 0 |
| OF Ofícios | 40 | 21 | 8 | 3 | 5 | 2 | 1 |
| JU Justificativas | 7 | 6 | 1 | 0 | 0 | 0 | 0 |
| TE Termos | 24 | 17 | 0 | 2 | 5 | 0 | 0 |
| RO Roteiros | 18 | 13 | 1 | 0 | 3 | 1 | 0 |
| PT Planos | 22 | 17 | 2 | 0 | 3 | 0 | 0 |
| OS Ordens | 15 | 11 | 1 | 0 | 3 | 0 | 0 |
| PR Prestação de contas | 59 | 28 | 9 | 17 | 2 | 3 | 0 |
| CA Diário no celular | 4 | 0 | 0 | 4 | 0 | 0 | 0 |
| CD Cadastros | 32 | 26 | 0 | 2 | 3 | 1 | 0 |
| DO Documentos/editor | 27 | 18 | 3 | 5 | 0 | 1 | 0 |
| AG Agenda/integrações | 12 | 9 | 2 | 1 | 0 | 0 | 0 |
| **Total** | **288** | **185** | **30** | **38** | **26** | **8** | **1** |

(Contagem por linha da tabela; linhas que agrupam rotas — PR-14 com 9 redirects, PR-81, as
8 rotas de editor de termo/OS/plano — contam uma vez.)

### 3.2 Maiores lacunas (LEGADO sem equivalente no NOVO)

1. **Importação do processo do eProtocolo** (PR-70..79, OF-30, TE-23): 9 rotas + diálogo
   nas listas de Ofícios, Termos e Prestação. Lê o PDF do processo e preenche a prestação.
   Não depende do credenciamento do eProtocolo (é upload de PDF).
2. **Diário no celular** (CA-01..04, PR-25): página pública por token, PWA offline.
3. **Textos dos documentos** (DO-19..23): gestor edita o texto-base de 7 tipos de documento.
4. **Revisão do pacote** (PR-57/58) e **carimbo por arrastar** (PR-51/52 parciais).
5. **Cartão "Dados para o eProtocolo"** (OF-28, TE-24, PR-50): cópia dos campos do processo,
   barato e de uso diário.
6. **Anexos de solicitação da viagem** (VG-18..20) e **conflitos no painel da viagem** (VG-22).
7. **Andamento do eProtocolo** (PR-08, AG-12) — dependência externa.
8. Menores: sugestão de ofício/protocolo do motorista externo (OF-16), correção de distância
   do diário (PR-24), WhatsApp do servidor (PR-09), CEP/endereço (CD-26/27), editor de texto
   do diário e do RT (PR-27, PR-35).

### 3.3 Ordem de trabalho recomendada (depois de Ofícios e Termos)

| # | Submódulo | Por quê (dependências · uso) |
|---|---|---|
| 3 | **Justificativas** (JU, 7 linhas) | 1:1 com o ofício (10 justificativas para 12 ofícios no LEGADO); reaproveita folha, editor e `dialogo_baixar` recém-aprovados em Ofícios. Pequeno: fecha o ciclo do ofício antes de sair dele. |
| 4 | **Prestação de contas** (PR + CA, 63 linhas) em fatias: 4a lista/cartão/envio (PR-01..14) → 4b diário de bordo + celular (PR-20..28, CA) → 4c relatório técnico (PR-30..36) → 4d documentos/anexos/carimbo (PR-40..52) → 4e pacotes (PR-55..58) → 4f importação do processo (PR-70..79) | Depende só do ofício emitido e da via assinada, que estarão prontos. Item nº 2 do menu do LEGADO, toda viagem gera prestação (12 no backup) e tem impacto financeiro (diárias). Concentra 21 das 38 faltas (com o diário no celular) e 9 dos 30 parciais. As folhas (diário, RT, documentos) ainda estão "a fazer" no visual. |
| 5 | **Viagens** — hub (VG, 25 linhas) | 2º maior volume no LEGADO (25) e item nº 1 do menu. Agrega roteiros, ofícios, termos, PT e OS e gera documentos em lote: entra quando Ofícios, Termos e Prestação já estão estáveis. Lacunas pequenas (anexos de solicitação, conflitos). |
| 6 | **Ordens de serviço** (OS, 15 linhas) | O formulário do LEGADO reutiliza peças do Termo (`_destino_linha`, `multi_pick`, `date_range`, visualizador): é a página que mais aproveita o padrão de Termos. Pouco uso (2) e quase sem lacunas. |
| 7 | **Planos de trabalho** (PT, 22 linhas, + CD-15..18 catálogos do plano) | Depende dos catálogos (programas, horários, atividades, conjuntos) e da tabela de diárias. Os Resultados alimentam as sugestões do RT, então convém revisitar 4c depois. A aba "Finalizados" depende da Prestação (feita em 4). |
| 8 | **Roteiros** (RO, 18 linhas) | Já é referência visual aprovada e é o mais usado (44). Falta só uma auditoria de paridade (RO-11, reaproveitar dados) e de desempenho. |
| 9 | **Cadastros** (CD, 32 linhas) | Padrão CRUD único, já quase todo "existe". Uma passada de consolidação: menu (N2), CEP/endereço (CD-26/27), confirmações de exclusão. Ajustes pontuais entram antes, dentro de cada submódulo que precisar. |
| 10 | **Documentos/editor transversais** (DO) + **Configurações** | Textos dos documentos (DO-19..23), prévia da conferência do assinado (DO-03), campos vinculados em termo/OS/plano (DO-07). Mexe em todos os documentos, por isso fica depois de todos eles estarem aprovados. |
| 11 | **Painel, Agenda e integrações** (PA, AG) | O Painel só existe no NOVO e resume os outros: faz sentido por último. eProtocolo real depende de credenciamento externo. |

---

## 4. Status de missão

Toda linha das tabelas da seção 2 começa como **pendente**. Ao mudar, atualizar a coluna
"Missão" aqui, registrar em `current-page.md` e, quando aprovada pelo QA, mover para
`completed-pages.md` com o ID (ex.: `OF-01`).
