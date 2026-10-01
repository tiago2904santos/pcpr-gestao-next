# Linguagem visual

## O que observamos no sistema de referência (e mantemos)
| Elemento | Referência | Decisão |
|---|---|---|
| Cabeçalho grafite com brasão, sigla **PCPR**, divisor e nome do produto | Todas as telas | **Mantido**, com altura 64px e filete dourado de 3px |
| Filete dourado sob o cabeçalho | Todas as telas e referências visuais | **Mantido** — é a assinatura |
| Micro-rótulos em caixa alta e espaçados ("VIAGENS", cabeçalhos de tabela) | Listas, tabelas, KPIs | **Mantido** em 11px/600, `letter-spacing: .06em` |
| Sublinhado dourado no item de navegação ativo | Navegação horizontal | **Mantido** no menu superior e nas abas de filtro |
| Chips de filtro com contagem ("Todos 56") | Listas de Ofícios/Viagens | **Mantido** como abas de filtro com contador |
| Linha-cartão com ícone, título forte e metadados com ícones | Lista de Ofícios | **Mantido e refinado** (`.registro`) |
| Seções numeradas no formulário do ofício (1 Dados… 7 Documentos) | Cadastro de ofício | **Mantido**, com índice lateral fixo |
| Cartões de valor (Valor total, Tipo de destino, Quantidade) | Seção Diárias | **Mantido** como `.indicador` |
| Login em cartão central sobre cinza, botão dourado "Entrar →" | Referência visual 3 | **Mantido** |

## O que corrigimos
| Problema observado | Evidência | Correção |
|---|---|---|
| Navegação do módulo Viagens com 13 itens transborda a 1440px ("Textos dos documentos" cortado; página com rolagem horizontal) | captura `p-viagens-oficios.png` (largura 1588px numa janela de 1440px) | Menu superior com seletor de módulo, links diretos e menus suspensos para grupos (máx. 7 entradas) |
| Botão flutuante "+ Novo ofício" sobrepõe os botões ⋮ das linhas | captura da lista de Ofícios | Ação primária no cabeçalho da página; nada flutua sobre conteúdo |
| Dourado como texto sobre branco (contraste ~2,6:1) | KPIs e links dourados | Texto dourado só em `--dourado-700` (5,8:1) |
| Nomes em CAIXA ALTA em listas longas cansam a leitura | Linhas da lista de Ofícios | Caixa alta só em micro-rótulos e no documento oficial; nomes em caixa original |
| 5 gerações de CSS de componentes convivendo | `docs/design-import/*` | Um único `components.css` sobre tokens |
| Itálico cinza para "Sem viatura", "Sem roteiro" com baixo contraste | Lista de Ofícios | `registro__meta-item--vazio` com contraste ≥ 4,5:1 |

## Personalidade
**Institucional, sóbria, precisa.** Nada de gradientes, ilustrações genéricas ou
glassmorphism. Profundidade só com bordas de 1px e sombras discretas. Cantos de 8–12px
(modernos sem parecer app de consumo).

## Referências visuais externas (fotos 1–4)
Princípios extraídos: cabeçalho institucional escuro com filete dourado; navegação com
ícone + rótulo e indicador dourado; seções com ícone dourado e título em caixa alta;
formulários em grade de duas colunas com rótulos acima; botão principal dourado no login;
selo "Ambiente restrito e monitorado". Não copiamos layouts; reaplicamos os princípios.
