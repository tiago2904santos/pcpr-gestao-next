# Componentes — reutilizar antes de criar

Catálogo vivo para a migração. A especificação visual está em `docs/design-system/` e a
vitrine em `/ui-lab/`. Antes de criar algo: procure aqui, depois no UI Lab, depois `grep`
pelo nome. "Usos" = número de templates que referenciam (03/10/2026).

## Web Components e módulos JS (`static/js/componentes/`)

| Componente | Faz | Usos | Serve para os próximos módulos |
|---|---|---:|---|
| `pc-combobox` | busca com sugestões, primeira já marcada, × de limpar | 8 | servidor, município, viatura, unidade, ofício (Termos/OS/PT) |
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
| `mascara.js` | CPF, RG, protocolo, placa | 2 | cadastros |
| `progresso.js`, `protecao.js`, `guia.js` | barra de progresso, aviso de saída sem salvar, guia | — | global |
| `menu.js` (exporta `icone`, `abrirEspaco`, `limiteInferior`) | utilitários de toda página: ícone do sprite e espaço acima da barra flutuante | — | global (sem requisição extra) |

## Partes de template (`templates/componentes/`, `templates/arquetipos/`)

`campo.html`, `campo_senha.html`, `migalhas.html`, `pagina_cabecalho.html`, `paginacao.html`,
`resumo_erros.html`, `vazio.html`. Arquétipos: assistente, busca, calendário, configurações,
detalhe, documento, formulário, lista, painel, relatório.

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
| **Linha do tempo (histórico)** | seção histórico do ofício | Todo processo | Módulo 4 |
| **Selo temporal** ("faltam N dias", "em andamento") | ofício/roteiro | Termos, OS, PT, prestação | já reutilizável — conferir nome único |
