# ADR 0006 — App Shell com cabeçalho institucional e navegação lateral agrupada

- **Status:** aceito · **Data:** 2026-10-01

## Contexto
Na referência, o módulo Viagens tem 13 abas horizontais. Em 1440px a barra transborda
(página com 1588px de largura; "Textos dos documentos" cortado) e o botão flutuante
"+ Novo ofício" cobre ações das linhas. As referências visuais aprovadas usam cabeçalho
grafite com filete dourado e navegação com indicador dourado.

## Decisão
- Cabeçalho grafite (64px) + filete dourado (3px): brasão, PCPR, produto, selo de ambiente
  (fora de produção), busca global (Ctrl+K), notificações, perfil.
- **Navegação lateral** (248px) com grupos; recolhível a ícones; gaveta abaixo de 1024px.
- Indicador ativo: fundo dourado claro + barra dourada + `aria-current`.
- Abas horizontais com filete dourado permanecem para **filtros e conteúdo** dentro da página.
- Ação primária no cabeçalho da página; nada flutua sobre o conteúdo.

## Alternativas
| Alternativa | Por que não |
|---|---|
| Manter abas horizontais | Não escala (já transborda); oculta itens em "Mais" piora a descoberta |
| Mega-menu | Esconde a localização atual |

## Consequências
Visual muda de "abas no topo" para "lateral", mas a identidade (grafite/dourado/brasão,
indicador dourado) é preservada. Validar com usuários operacionais (`docs/reviews/`).
