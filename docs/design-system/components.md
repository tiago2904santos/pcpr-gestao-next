# Catálogo de componentes

Todos vivem em `static/css/components.css` e são exercitados em **/ui-lab/** (estados:
padrão, hover, foco, ativo, desabilitado, carregando, erro, sucesso, vazio, conteúdo longo,
celular). Comportamentos em `static/js/componentes/*.js` (Web Components, sem framework).

| Componente | Classe / elemento | Variantes e estados | Acessibilidade |
|---|---|---|---|
| Botão | `.botao` | `--primario` (grafite), `--marca` (dourado, 1 por tela), padrão (contorno), `--sutil`, `--perigo`, `--perigo-contorno`; `--sm/--lg/--bloco/--icone`; `disabled`; `aria-busy="true"` (carregando) | Botão-ícone exige `aria-label`; carregando preserva largura |
| Campo | `.campo` + `.entrada/.selecao/.area-texto` | erro (`.campo--erro` + `aria-invalid`), sucesso, desabilitado, somente leitura, composto (`.entrada-composta` com ícone ou texto fixo "/ 2026") | Rótulo sempre visível; ajuda/erro via `aria-describedby` |
| Escolha | `.escolha` (checkbox/rádio), `.interruptor` (`role="switch"`) | marcado, desabilitado, com descrição | Área de clique inclui o texto |
| Combobox | `<pc-combobox>` | local (aprimora `<select>`), remoto (`data-fonte`), com ação HTMX (`data-acao-url`) | WAI-ARIA combobox 1.2, `aria-activedescendant`, anúncio de resultados |
| Data/hora | `input[type=date/time]` nativo | — | Teclado do celular adequado; zero JS (ADR 0007) |
| Cartão/Seção | `.cartao` | `__cabecalho` com `__numero` ou `__titulo--institucional` (ícone dourado + caixa alta), `__rodape`, `--destaque`, `--interativo` | Título é heading real |
| Indicador (KPI) | `.indicador` | `--atencao`; pode ser link | Valor + rótulo legíveis por leitor de tela |
| Selo de status | `.selo` | `--neutro/info/sucesso/aviso/perigo/marca/forte`, `--sem-ponto` | Texto obrigatório (status nunca só por cor) |
| Alerta | `.alerta` | info, sucesso, aviso, perigo; com lista | `role="alert"` só para erro bloqueante |
| Toast | `<pc-toasts>` | sucesso/aviso/info somem em 6s (pausam no hover); erro persiste | `role="status"`, não rouba foco |
| Abas | `.abas` + `.aba` | links de filtro (`aria-current`) ou `<pc-abas>` (ARIA tabs) | Setas/Home/End em `<pc-abas>` |
| Sanfona | `details.sanfona` | aberta/fechada | Nativo |
| Etapas | `.etapas` | concluída, atual, pendente; vertical/horizontal | `aria-current="step"` |
| Tabela | `.tabela` | `--compacta`, `--responsiva` (vira cartões <768px), `--linhas-clicaveis`, ordenação (`aria-sort`), rodapé de totais | `caption`, `scope`, números alinhados à direita |
| Lista de registros | `.registros > .registro` | metadados com ícones, vazio em itálico, ações ⋮ | Link principal cobre a linha sem aninhar interativos |
| Filtros | `.filtros`, `.filtros-ativos`, `.ficha` | busca, selects, fichas removíveis | `role="search"` |
| Paginação | `componentes/paginacao.html` | elipses, anterior/próxima desabilitadas | `aria-current="page"`, rótulos |
| Migalhas | `componentes/migalhas.html` | — | `nav[aria-label]`, último item `aria-current` |
| Diálogo | `dialog.dialogo` | confirmação, `--perigo`, gaveta (`.gaveta`) | `<dialog>` nativo: foco preso, Esc, retorno do foco |
| Confirmação | `data-confirmar` / `hx-confirm` | destrutiva (`data-confirmar-perigo`) | Substitui `window.confirm` |
| Menu suspenso | `<pc-menu>` | item de perigo, separador | Padrão menu button; setas, Esc |
| Paleta de comandos | `<pc-comandos>` | navegação + busca no servidor | Ctrl+K ou "/"; combobox + listbox |
| Estado vazio | `componentes/vazio.html` | primeiro uso (ação), sem resultado (limpar filtros) | Heading + orientação |
| Carregando | `.esqueleto`, `.girando`, `.indicador-htmx` | — | `aria-busy`, `role="status"` |
| Pessoa | `.pessoa`, `.avatar` | motorista (selo forte), com termo | Botão remover com nome no rótulo |
| Valor | `.valor-destaque`, `.por-extenso` | `--marca` | — |
| Prévia de documento | `.previa-documento` | iframe do PDF | Título no iframe |
