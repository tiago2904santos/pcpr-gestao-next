# ADR 0006 — App Shell com cabeçalho institucional e menu superior

- **Status:** aceito (revisado em 01/10/2026 por decisão do dono do produto; tablet e celular
  ajustados na auditoria do Ofício) · **Data:** 2026-10-01

## Contexto
A primeira versão do piloto usou navegação lateral para resolver o transbordo da referência
(13 abas horizontais no módulo Viagens; página com 1588 px numa janela de 1440 e 622 px a
390 px). O dono do produto decidiu: **menu superior, não lateral** — é o padrão do sistema
atual e das referências visuais aprovadas (fotos 1 e 2).

## Decisão
**A navegação principal é SUPERIOR/HORIZONTAL, nunca lateral.** Não substituir por barra
lateral, nem criar uma navegação lateral paralela, sem autorização explícita do dono do produto.

| Largura | Navegação principal |
|---|---|
| Desktop (≥ 1024 px) | **Menu superior** horizontal |
| Tablet (768–1023 px) | **Menu superior responsivo** (horizontal, mais compacto) |
| Celular (< 768 px) | **Gaveta lateral temporária** aberta pelo ☰ do cabeçalho (decisão D9 do dono do produto): começa fechada, fecha ao escolher, com Esc ou tocando fora |
| Qualquer largura | **SIDEBAR PERMANENTE = NÃO** |

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
  em menus. `registrar_modulo` recusa módulos acima do limite; o teste responsivo reprova
  rolagem horizontal de 360 a 1440 px.
- De 768 a 1023 px (tablet) o menu continua horizontal, com espaçamentos menores.
- Abaixo de 768 px (celular) o ☰ abre os mesmos itens numa **gaveta lateral temporária**
  (decisão D9, 01/10/2026), sob o cabeçalho, com no máximo `min(20rem, 86vw)`: começa
  fechada, fecha ao escolher, com Esc (devolvendo o foco ao ☰) ou tocando no véu; conteúdo
  `inert` enquanto aberta; menus suspensos embutidos. Não existe em tablet nem desktop.
- **Proteção contra regressão**: `tests/test_navegacao_superior.py` (sem classes de
  navegação lateral no código, gaveta só abaixo de 768 px e sempre temporária, limite de
  entradas, esta regra
  escrita aqui e no Design System) e `tests/e2e/test_navegacao_superior.py` (geometria real
  do menu em 360–1440 px).

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Navegação lateral (versão anterior do piloto) | Rejeitada pelo dono do produto: foge do padrão conhecido pelos usuários |
| Gaveta lateral no tablet | O tablet tem espaço para o menu horizontal |
| Menu que desce do topo no celular | Testado na auditoria; o dono do produto preferiu a gaveta lateral temporária (D9) |
| 13 abas planas como na referência | Transborda já em 1440 px |
| Abas com rolagem horizontal | Esconde itens e os menus suspensos seriam cortados |

## Consequências
Identidade da referência preservada (barra horizontal, filete dourado, seletor de módulo) sem
o transbordo. Novos itens de um módulo exigem decidir se são de primeiro nível ou de menu.
