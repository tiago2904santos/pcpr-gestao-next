# Navegação

## Níveis
1. **Central de módulos** (`/`): cartões por módulo com indicadores e "Entrar no módulo".
2. **Menu superior do módulo** (`templates/parciais/navegacao.html`): seletor de módulo
   ("▌Viagens ▾" — central de módulos e troca de módulo), links diretos e menus suspensos
   (`<pc-menu>`) para grupos com `em_menu=True`. Item ativo com filete dourado inferior e
   `aria-current="page"`; o botão do menu que contém a página atual também ganha o filete e
   o texto "(seção atual)" para leitores de tela. Máximo de 7 entradas de primeiro nível.
3. **Migalhas** acima do título em páginas de 2º nível ou mais.
4. **Abas de filtro** dentro da página (links com contador).

## Busca global / paleta de comandos
Botão no cabeçalho, `Ctrl+K` ou `/`. Combina destinos do menu (respeitando permissões,
porque são lidos do próprio menu renderizado) com resultados do servidor: número do
ofício ("131/2026"), protocolo, servidor, destino.

## Registro de módulos
Cada contexto registra seu módulo em `AppConfig.ready()` via
`gestao.plataforma.navegacao.registrar_modulo` (ordem, ícone, grupos, permissão exigida
por item). A plataforma não importa contextos de negócio (contrato do import-linter).

## Responsivo
- ≥1024px: barra horizontal fixa no topo, junto com o cabeçalho.
- <1024px: o mesmo menu vira gaveta (☰ no cabeçalho), com véu, Esc, foco no item atual e
  conteúdo `inert` enquanto aberta; os menus suspensos abrem embutidos.
- <768px: cabeçalho mostra só brasão, sigla, busca (ícone), notificações e avatar.
