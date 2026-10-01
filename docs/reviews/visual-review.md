# Revisão visual — Fase 12

Fontes comparadas:
1. **Sistema de referência** (navegação somente leitura em 01/10/2026; capturas em
   `artifacts/referencia/`, **não versionadas** porque contêm nomes e CPFs reais);
2. **Referências visuais** aprovadas (fotos 1–4: SRDO, Repressão Qualificada, login PCPR,
   criação de ofício de diárias);
3. **Nova implementação** (capturas com dados fictícios em `artifacts/responsivo/<largura>/`,
   geradas a cada execução de `tests/e2e/test_responsivo.py`; seleção em `docs/reviews/img/`).

Larguras: **360, 390, 768, 1024, 1280, 1440**, em 10 páginas (60 combinações),
verificadas automaticamente quanto a rolagem horizontal, sobreposição de elementos
interativos, texto cortado em botões/selos/abas e erros de console.

## O que se manteve (DNA)
| Elemento | Referência | Novo |
|---|---|---|
| Cabeçalho grafite + brasão + PCPR + nome do produto | ✅ | ✅ 64 px, filete dourado de 3 px |
| Micro-rótulos em caixa alta | ✅ ("VIAGENS", cabeçalhos de tabela) | ✅ token `--rastreio-rotulo` |
| Indicador dourado no item ativo | sublinhado na barra horizontal | barra vertical dourada na lateral + filete nas abas |
| Abas de filtro com contagem | "Todos 56", "Que vão acontecer 8"… | "Todos 4", "Rascunhos 2"… |
| Linha-cartão com título forte e metadados com ícones | lista de Ofícios | `.registro` (mesmo padrão, contraste corrigido) |
| Seções numeradas do ofício (1 a 7) | ✅ | ✅ com índice lateral e estado de cada seção |
| Cartões de diárias (Valor total / Tipo de destino / Quantidade) + "Como foi calculado" | ✅ | ✅ mesmos números (R$ 2.411,56 · 4 x 100% + 1 x 15%) |
| Login em cartão central, botão dourado "Entrar →", "Ambiente restrito e monitorado" | foto 3 | ✅ |
| Documento oficial (timbre, tabelas, roteiro de ida/retorno, custeio, assinatura, destinatário) | ✅ DOCX→PDF | ✅ PDF/A-2a de uma página |

## O que melhorou (com evidência)
| Problema na referência | Evidência | Novo |
|---|---|---|
| Página da lista de Ofícios com **1588 px** de largura numa janela de 1440 (13 abas transbordam) | `p-viagens-oficios.png` | Lateral agrupada; 0 px de rolagem lateral nas 6 larguras |
| A 390 px a lista tem **622 px** de largura; título do produto corta e sobrepõe ícones do cabeçalho; navegação truncada ("Ofi…") | `artifacts/referencia/390/viagens-oficios.png` | Cabeçalho compacto (brasão, sigla, busca, sino, avatar); gaveta de navegação |
| Botão flutuante "+ Novo ofício" cobre os botões ⋮ das linhas (1440 e 390) | idem | Ação primária no cabeçalho da página |
| Nomes em CAIXA ALTA nas linhas da lista | lista de Ofícios | Caixa original nos nomes; caixa alta só em micro-rótulos e no documento |
| "Sem viatura", "Sem roteiro" em itálico cinza claro | lista | `registro__meta-item--vazio` com contraste ≥ 4,5:1 |
| Ícones + nome do usuário cortados no cabeçalho a 390 px | idem | Perfil vira avatar; menu acessível por teclado |

## Problemas encontrados no novo e corrigidos nesta fase
| Achado | Largura | Correção |
|---|---|---|
| Paginação estourava o cartão | 360–1280 (UI Lab) | `flex-wrap` + só anterior/atual/próxima < 480 px |
| Texto "2 × 100% + 1 × 15%" vazava do indicador | 1024 | Indicador quebra linha (`overflow-wrap`, `text-wrap: balance`) |
| Data/hora `datetime-local` truncada | 1440 (coluna estreita) | Grade 4/4/4 no roteiro |
| Barra de ações fixa podia cobrir o campo focado | 360/390 | `scroll-padding-bottom` (WCAG 2.4.11) |
| Matriz de botões do UI Lab sobreposta | 1024 | Colunas `max-content` com rolagem interna |

## Observações não resolvidas (registradas)
- O formato de data/hora dos campos nativos depende do idioma do navegador; no Chromium
  *headless* das capturas aparece em inglês (mm/dd/aaaa). Em navegadores em pt-BR aparece
  dd/mm/aaaa — validar no Chrome/Edge institucional.
- Abas de filtro rolam na horizontal no celular (comportamento intencional), mas falta uma
  indicação visual de que há mais abas → backlog do Design System.
