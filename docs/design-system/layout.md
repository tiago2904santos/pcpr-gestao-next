# Layout e App Shell

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ☰ [brasão] PCPR │ Gestão de Eventos e Viagens [DEV]  [🔍 Buscar… Ctrl K]  🔔 (OT) Operador ▾ │ ← grafite 64px
╞══════════════════════════ filete dourado 3px ═══════════════════════════╡
│     ▌Viagens ▾    ⊞ Painel   📄 Ofícios   Cadastros ▾                      │ ← menu superior 52px
│                               ▔▔▔▔▔▔▔▔ (filete dourado no ativo)           │
├──────────────────────────────────────────────────────────────────────────┤
│     Início / Viagens / Ofícios                                             │
│     VIAGENS                                                                │
│     Ofícios                                        [Exportar] [+ Novo]     │
│     [Todos 56][Rascunhos 8][Emitidos 38]…                                  │
│     ┌ cartão: filtros + lista/tabela + paginação ─────────────────────┐    │
│     └─────────────────────────────────────────────────────────────────┘    │
│     🔒 Ambiente restrito e monitorado · PCPR                               │
└──────────────────────────────────────────────────────────────────────────┘
```

## Regiões (landmarks)
| Região | Elemento | Notas |
|---|---|---|
| Pular para o conteúdo | `a.pular-conteudo` | Primeiro foco da página |
| Topo fixo | `div.topo` | Cabeçalho + menu ficam fixos juntos ao rolar |
| Cabeçalho | `header.cabecalho` | Marca, ambiente, busca global, notificações, perfil |
| Navegação | `nav#navegacao-principal` | Menu superior horizontal (≥768); gaveta lateral temporária pelo ☰ (<768, D9). Barra lateral permanente nunca (ADR 0006) |
| Conteúdo | `main#conteudo` | Largura máx. 1280px; 896px em formulários (`--estreito`) |
| Rodapé | `footer.rodape` | "Ambiente restrito e monitorado" |

## Menu superior (decisão do dono do produto)
O padrão conhecido pelos usuários e presente nas referências visuais é o **menu horizontal**.
Mantemos a barra com **seletor de módulo** ("▌Viagens ▾"), **links diretos** e **filete
dourado** no item ativo. Para não repetir o transbordo da referência (13 abas que estouram a
1440px), grupos secundários viram **menus suspensos** ("Cadastros ▾") e vale a regra de no
máximo 7 entradas de primeiro nível. Menu, conteúdo e rodapé usam a mesma coluna centralizada.
Decisão registrada em `docs/adr/0006-app-shell-menu-superior.md`.

## Grades
- `.campos`: 12 colunas para formulários (`col-3`, `col-4`, `col-6`…; tudo vira 12 no celular).
- `.grade--2/3/4/auto`: cartões e indicadores.
- `.layout-detalhe`: conteúdo + coluna de contexto (320px), sticky.
- `.layout-formulario`: índice de seções (208px, sticky) + seções — só no arquétipo (CSS em `ui-lab.css`); o produto usa a folha única `.documento` com a faixa `.progresso--fixo`.

## Larguras de leitura
Descrições de página limitadas a ~42rem (`--largura-leitura`) para linhas de 70–80 caracteres.
