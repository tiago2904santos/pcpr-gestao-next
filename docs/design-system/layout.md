# Layout e App Shell

```
┌──────────────────────────────────────────────────────────────────────┐
│ ☰ [brasão] PCPR │ Gestão de Eventos e Viagens   [DEV] [🔍 Buscar… Ctrl K]  🔔 (T) Tiago ▾ │  ← grafite, 64px
╞══════════════════════════════ filete dourado 3px ════════════════════╡
│ ┌Módulo─────────┐ │  Início / Viagens / Ofícios                        │
│ │ Viagens     ⇵ │ │  VIAGENS                                           │
│ └───────────────┘ │  Ofícios                           [Exportar][+ Novo]│
│ OPERAÇÃO          │  ──────────────────────────────────────────────────  │
│ ▌Ofícios          │  [Todos 56][Rascunhos 8][Emitidos 38]…              │
│  Roteiros         │  ┌ cartão: filtros + lista/tabela + paginação ────┐ │
│ CADASTROS         │  │                                                │ │
│  Servidores       │  └────────────────────────────────────────────────┘ │
│  Viaturas         │                                                     │
│ [« Recolher]      │  🔒 Ambiente restrito e monitorado · PCPR            │
└───────────────────┴─────────────────────────────────────────────────────┘
```

## Regiões (landmarks)
| Região | Elemento | Notas |
|---|---|---|
| Pular para o conteúdo | `a.pular-conteudo` | Primeiro foco da página |
| Cabeçalho | `header.cabecalho` | Sticky; marca, ambiente, busca global, notificações, perfil |
| Navegação | `nav#navegacao-lateral` | 248px; recolhível a 64px (≥1024); gaveta (<1024) |
| Conteúdo | `main#conteudo` | Largura máx. 1280px; 896px em formulários (`--estreito`) |
| Rodapé | `footer.rodape` | "Ambiente restrito e monitorado" |

## Por que navegação lateral (e não as abas horizontais da referência)?
O módulo Viagens tem 13 destinos; na referência eles transbordam a 1440px (rolagem lateral
da página inteira). A lateral **agrupa** (Operação, Documentos, Cadastros, Configuração),
escala para novos módulos e libera a largura do conteúdo. O DNA é preservado: cabeçalho
grafite, filete dourado e indicador dourado no item ativo. As **abas horizontais com filete
dourado** continuam existindo onde funcionam bem: filtros de lista e abas de conteúdo.
Decisão registrada em `docs/adr/0006-app-shell-navegacao-lateral.md`.

## Grades
- `.campos`: 12 colunas para formulários (`col-3`, `col-4`, `col-6`…; tudo vira 12 no celular).
- `.grade--2/3/4/auto`: cartões e indicadores.
- `.layout-detalhe`: conteúdo + coluna de contexto (320px), sticky.
- `.layout-formulario`: índice de seções (208px, sticky) + seções.

## Larguras de leitura
Descrições de página limitadas a ~42rem (`--largura-leitura`) para linhas de 70–80 caracteres.
