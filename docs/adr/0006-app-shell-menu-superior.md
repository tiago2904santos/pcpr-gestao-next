# ADR 0006 — App Shell com cabeçalho institucional e menu superior

- **Status:** aceito (revisado em 01/10/2026 por decisão do dono do produto) · **Data:** 2026-10-01

## Contexto
A primeira versão do piloto usou navegação lateral para resolver o transbordo da referência
(13 abas horizontais no módulo Viagens; página com 1588 px numa janela de 1440 e 622 px a
390 px). O dono do produto decidiu: **menu superior, não lateral** — é o padrão do sistema
atual e das referências visuais aprovadas (fotos 1 e 2).

## Decisão
- Cabeçalho grafite (64 px) com filete dourado: brasão, PCPR, produto, selo de ambiente,
  busca global (Ctrl+K), notificações, perfil.
- **Menu superior** (52 px, fundo branco), alinhado à coluna do conteúdo:
  - **seletor de módulo** à esquerda ("Viagens ▾", com filete dourado vertical, como na
    referência) que leva à central e aos demais módulos;
  - **links diretos** para o trabalho do dia a dia (Painel, Ofícios…);
  - **menus suspensos** para grupos secundários (`Grupo(em_menu=True)`, ex.: "Cadastros ▾");
  - item ativo com **filete dourado** inferior + `aria-current`.
- Cabeçalho + menu ficam fixos no topo juntos (`.topo`).
- **Regra anti-transbordo**: no máximo 7 entradas de primeiro nível por módulo; o resto entra
  em menus. O teste responsivo reprova rolagem horizontal em 1024 px.
- Abaixo de 1024 px o mesmo menu vira **gaveta** aberta pelo ☰ (Esc fecha e devolve o foco;
  conteúdo `inert`); os menus suspensos abrem embutidos.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Navegação lateral (versão anterior do piloto) | Rejeitada pelo dono do produto: foge do padrão conhecido pelos usuários |
| 13 abas planas como na referência | Transborda já em 1440 px |
| Abas com rolagem horizontal | Esconde itens e os menus suspensos seriam cortados |

## Consequências
Identidade da referência preservada (barra horizontal, filete dourado, seletor de módulo) sem
o transbordo. Novos itens de um módulo exigem decidir se são de primeiro nível ou de menu.
