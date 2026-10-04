# Componentes — reutilizar antes de criar

Catálogo vivo para a migração. A especificação visual está em `docs/design-system/` e a
vitrine em `/ui-lab/`. Antes de criar algo: procure aqui, depois no UI Lab, depois `grep`
pelo nome. "Usos" = número de templates que referenciam (03/10/2026).

## Web Components e módulos JS (`static/js/componentes/`)

| Componente | Faz | Usos | Serve para os próximos módulos |
|---|---|---:|---|
| `pc-combobox` | busca com sugestões, primeira já marcada, × de limpar; remoto com **valor em campo oculto** (`input[type=hidden][data-valor-id]`) | 9 | servidor, município, viatura, unidade, ofício (Termos/OS/PT) |
| `pc-select` | seleção simples estilizada | 9 | status, tipo, catálogos |
| `pc-data` (`seletor-data.js`) | data e **período** (`data-periodo`) | 2 | **o PeriodoPicker** de PT, Termos, OS, filtros |
| `pc-hora` | hora | 2 | trechos, eventos de PT |
| `pc-itinerario` | sede, destinos, bate-volta, trechos, mapa | 5 | Roteiros, PT (destinos), OS (destinos), diário de bordo |
| `pc-transporte` | viatura cadastrada × descrição manual | 6 | Termos por viatura, OS |
| `pc-menu` (+ `.menu--pousar`) | menu de ações; variante de hover | 10 | ações por linha em toda lista |
| `pc-abas` | abas com contagem animada | 7 | toda lista com situações |
| `pc-comandos` | paleta de comandos/busca global | 7 | navegação |
| `pc-editor-documento` | editor do documento no visualizador | 2 | **todo documento** (Termo, OS, PT, RT) — promover ao núcleo de Documentos |
| `pc-toasts` | mensagens | 5 | global |
| `pc-shell` | casca | 3 | global |
| `registro.js` | linha → janela de resumo (htmx), esqueleto, abrir ao carregar | 10 | **toda lista** com janela de resumo |
| `autosave.js` | gravação automática + `pcpr:dados-salvos` | 2 | toda folha de edição |
| `limpar.js` | botão × em campos | 6 | automático em `input[type=search]` e `[data-limpavel]` |
| `dialogo.js` | janelas; janela aberta pelo servidor; **pedir motivo** (`data-pedir-motivo` + `componentes/dialogo_motivo.html`) | 11 | confirmação, resumo, qualquer ação que exige texto (cancelar, reativar, reabrir; roteiros e próximos módulos) |
| `acao.js` | ações com confirmação | 32 | global |
| `mascara.js` | CPF, telefone, placa, protocolo, data, hora | 4 | cadastros, termos |
| `pc-multiescolha` (`multiescolha.js`, widget `EscolhaMultiplaRemota`) | **vários** registros por busca remota: escolhidos em linhas com campo oculto do mesmo nome, sem repetir, remover, anúncio para leitor de tela; só os escolhidos são desenhados | 1 (motoristas da viatura) + UI Lab | servidores de um termo em lote, equipe da OS/PT, participantes |
| `diaria.js` | prévia dos percentuais (15%/30%) ao digitar o valor de 24 h | 1 | prestação de contas (valores derivados) |
| `progresso.js`, `protecao.js`, `guia.js` | barra de progresso, aviso de saída sem salvar, guia | — | global |
| `menu.js` (exporta `icone`, `abrirEspaco`, `limiteInferior`) | utilitários de toda página: ícone do sprite e espaço acima da barra flutuante | — | global (sem requisição extra) |

## Partes de template (`templates/componentes/`, `templates/arquetipos/`)

`campo.html`, `campo_senha.html`, `migalhas.html`, `pagina_cabecalho.html`, `paginacao.html`,
`resumo_erros.html`, `vazio.html`. CSS de apoio novo (módulo 2): `dialog.dialogo--largo`
(cadastro com mais campos), `.grupo-campos` (fieldset com título), `.barra-acoes--rodape`
(ação "Novo…" no fim da lista, sem flutuar), `.vazio-inline`. O **CRUD em janela** dos
cadastros (`cadastros/catalogo.html` + `views_crud.Catalogo`) é o molde para os catálogos dos
próximos módulos (tipos de evento, serviços, órgãos…). Arquétipos: assistente, busca, calendário, configurações,
detalhe, documento, formulário, lista, painel, relatório.

## Visualizador de documento em modo leitura

`viagens/oficios/_editor.html` (`pc-editor-documento`) sem `estado_url` e com
`pode_editar_texto=False` é o **DocumentPreview** do sistema: folha HTML num iframe que só
carrega ao chegar à tela, modos Texto/PDF, refeito no evento `pcpr:dados-salvos` (autosave).
Rota da folha: `resposta_de_folha` + `@moldura_da_folha` (views_editor); o PDF emoldurado
usa `@moldura_do_pdf` (com `?previa=1`, erro vira aviso na folha). A folha passa pela mesma
policy de gerar o documento (`pode_ver_documento_*`); sem ela, o visualizador nem é
desenhado.

## Gravação automática com tela viva

`form[data-autosave]` (`autosave.js`) + `[data-status-salvamento]` com `[data-anuncio]`
(o texto do autosave) e regiões `[data-vivo][id]` (refeitas depois de cada gravação). A
resposta `{"salvo", "em", "campos", "recarregar", "mensagem"}`; `mensagem` acende
`.barra-acoes__status--erro` (visível no celular). Usos: ofício, roteiro, termo, OS. Usos: ofício e justificativa (editáveis), termo e OS (leitura). A
moldura reserva a altura da folha antes de carregar (sem CLS).

### Via assinada (módulo 7a)

Janela única por página `componentes/dialogo_assinado.html` + `assinado.js` (como a de
"pedir motivo"): um link `data-anexar-assinado="<url>" data-assinado-titulo="…"
[data-assinado-troca]` abre; extensão e tamanho conferidos antes de enviar; sem JS o link
leva à página `viagens/assinados/anexar.html`. Peças: `viagens/assinados/_registro.html`
(a via como `.registro`), `_itens_menu.html` (itens para um `pc-menu`), `_selo.html`
("Assinado" / "Assinado, mas os dados mudaram") e `_form_remover.html` (fora da folha, que
é um `<form>` só; o item usa `form="remover-via-<pk>"`). Contexto pronto em
`views_assinados.cartao`. Usos: resumo do ofício, folha do termo (lista de documentos),
folha da OS. Vitrine no UI Lab, seção 8.

### Baixar documentos (módulo 7c)

Janela única `componentes/dialogo_baixar.html` + `baixar.js`: um botão
`data-baixar-documentos="<url>" data-baixar-titulo="…"` abre; a lista vem de um GET na url
(JSON `{"itens": [{valor, nome, detalhe, estado, assinado}]}`) e o POST devolve o arquivo
(um documento, um PDF só ou ZIP). Serviço genérico em `viagens/pacotes.py` (`Item`, `montar`);
views em `views_pacotes.py`. Usos: resumo do ofício, justificativas, lista e folha do termo;
a viagem (módulo 8) e a prestação reaproveitam. Vitrine no UI Lab, seção 8.

## A promover / extrair (com o primeiro módulo que precisar)

| Candidato | Hoje | Por que promover | Quando |
|---|---|---|---|
| **Janela de resumo genérica** | específica de ofício (`oficios/_resumo.html` + CSS `resumo__*`) | Termos, OS, PT, roteiros terão o mesmo padrão linha → janela | Módulo 4 (Termos) |
| **Cartões de pessoa/viatura em grade equilibrada** (`larguras_de_cartoes`) | ofício | Equipe em Termos, OS, PT (efetivo) | Módulo 4 |
| **Busca por leituras** (`dominio/busca.py` + `_refino.html`) | ofícios | Toda lista com identificadores numéricos (termos, OS, PT, protocolos) | Módulo 4 |
| **Gaveta "Mais filtros"** | ofícios | Toda lista | Módulo 2 (cadastros) |
| **Catálogo de textos prontos** (seletor + "guardar como modelo") | editor de documento tem "guardar texto pronto" | Motivo, justificativa, RT, despacho, resposta padrão (ASCOM) | Módulo 1 (agora) |
| **CRUD de cadastro em janela** (lista + janela de novo/editar + definir padrão + ativo) | não existe | Todos os catálogos (cargos, combustíveis, motivos, modelos…) | Módulo 2 (o catálogo de motivos é o primeiro) |
| **Numeração anual com lacunas** | domínio do ofício | OS e PT usam o mesmo livro com lacunas na referência | Módulo 5 |
| **Linha do tempo (histórico)** | ✅ promovida (04/10): `plataforma.auditoria.passos_do_registro` lê a trilha do banco (agrupa por requisição, junta tabelas filhas, ignora eventos de id reaproveitado) e `viagens/linha_do_tempo.py` escreve as frases; marcação `oficios/_evento.html` | Termos e OS já usam; PT, prestação, eventos seguem o mesmo par | — |
| **Selo temporal** ("faltam N dias", "em andamento") | ofício/roteiro | Termos, OS, PT, prestação | já reutilizável — conferir nome único |
