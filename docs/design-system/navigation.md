# Navegação

## Níveis
1. **Central de módulos** (`/`): cartões por módulo com indicadores e "Entrar no módulo".
2. **Navegação lateral do módulo**: grupos com micro-rótulo; item ativo com fundo
   `--cor-marca-fundo`, barra dourada à esquerda e `aria-current="page"`. O bloco
   "Módulo: Viagens" no topo volta à central.
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
- ≥1024px: lateral fixa, recolhível (preferência local do navegador).
- <1024px: lateral vira gaveta (☰ no cabeçalho), com véu, Esc, foco no item atual e
  conteúdo `inert` enquanto aberta.
- <768px: cabeçalho mostra só brasão, sigla, busca (ícone), notificações e avatar.
