# Plano aprovado pelo orquestrador — Lista de ofícios

> Consolida `parity/oficios-lista.md` (Agente 1) e `visual/oficios-lista.md` (Agente 2).
> Cada item tem um ID (LP-nn) usado nos commits, em `qa/oficios-lista.md` e em `current-page.md`.
> Decisões de produto tomadas aqui também estão em `decisions.md`.

## Decisões do orquestrador

| # | Tema | Decisão | Por quê |
|---|---|---|---|
| D1 | Abas | **Vocabulário temporal canônico do módulo**: Todos · Que vão acontecer · Em andamento e realizados · Contas prestadas · Cancelados (mesmo de Roteiros/Termos e do legado). A situação do documento (Rascunhos · Emitidos · Arquivados) vira um **filtro de um clique** sempre visível na barra de filtros ("Documento"), com contagem. Arquivados continuam fora de "Todos" até serem pedidos. | Identidade aprovada + paridade com o legado; as 7 abas misturavam duas dimensões e transbordavam a 768 px. Nenhum recorte some: Rascunhos/Emitidos/Arquivados seguem a um clique. |
| D2 | Regras das abas | "Que vão acontecer" = não cancelado, sem contas prestadas e (1ª saída > fim de hoje **ou** sem data). "Em andamento e realizados" = não cancelado, sem contas prestadas, 1ª saída ≤ fim de hoje. "Contas prestadas" = regra atual. **Contadores acompanham busca e filtros** (ignorando só a própria aba). | Regras exatas do legado (`abas.py:73-85`) — fonte de verdade. |
| D3 | Selo de tempo | Um tag compartilhado (`selo_tempo`) com regra em domínio puro, usado em Ofícios, Roteiros e Termos (e depois Ordens/Planos/Viagens): "faltam N dias" (aviso se ≤ prazo de 10 dias) · "amanhã" · "começa hoje" · "em andamento · até dd/mm" · "volta hoje" · passado → **sem selo**. | Três vocabulários para o mesmo fato; "há 1 dia" em viagem em curso era errado; "há 671 dias" é ruído. |
| D4 | Orçamento de selos | No título: situação do documento + **no máximo um** alerta (prioridade: Justificativa pendente > prazo ≤ 10 dias > tempo). Tipo do ofício só quando foge do comum: **Convalidação**, **Retificado**, **Complementar** (Autorização é o padrão e aparece no resumo e no XLSX). | Paridade com o legado (L41) sem o ruído de até 4 pílulas. |
| D5 | Título e metadados | Título = **destinos** (até 3 + "+N", lista completa no `title` e no resumo). Período é o 1º item dos metadados (ícone calendário) — regra para Ofícios e Termos; Roteiros mantém "Sede → destinos" com período no meta. ≥ 1024 px: metadados em **colunas fixas** (uma linha, reticências + `title`), linha com altura constante. Motorista marcado por ícone com texto acessível. Motorista de fora da equipe aparece. | Leitura vertical da lista; altura irregular 72/93/117 px. |
| D6 | Filtros | Barra: Busca · Documento (segmentado) · botão **Filtros (n)**. A gaveta (fechada ao carregar) reúne Ordenar por (rótulos honestos), Período de saída, Data do ofício, **Ano do número**, Protocolo, Veículo, Diárias; rodapé com Limpar/Fechar; Esc e clique fora fecham. **Fichas de filtros ativos** removíveis (inclui ordem não padrão e escopo da busca) + "Limpar tudo". "Limpar filtros" não apaga a busca nem a aba. | Legado tinha fichas e "Filtros e ordem"; gaveta abrindo sozinha cobria a lista. |
| D7 | Clique e menu | Título continua abrindo a **janela de resumo** (superação: decidir sem sair da lista). Menu ⋮ canônico com itens descritos: Ver resumo · Abrir/Editar · Ver minuta ou PDF · Baixar documentos… · Anexar assinado… — Novo termo / OS / plano a partir do ofício · Duplicar — Retificar · Marcar como complementar — Cancelar · Arquivar/Desarquivar · Reativar — Excluir. ⋮ com opacidade 1. | Paridade (L52-L56, L61) e WCAG 1.4.11. |
| D8 | Ações da página | Barra fixa: contagem do recorte ("157 de 255 ofícios") · Exportar planilha · menu "Mais" (Numeração — gestor; Importar processo do eProtocolo — quando existir) · Novo ofício. Cabeçalho sem botões (padrão canônico). | Cabeçalho limpo como Roteiros/Termos, sem perder Numeração/Importar. |
| D9 | Numeração | Nova página do gestor (`/viagens/oficios/numeracao/`): piso do ano, próximo número, lacunas liberadas e último ocupado. | Lacuna L6 (serviço já existe). |
| D10 | Importação do eProtocolo | Fora deste lote: sub-projeto próprio da área de Ofícios (inventário OF), com pontos de entrada na lista (menu Mais, ⋮ da linha, arrastar-soltar) quando estiver pronto. | 9 rotas + diálogo compartilhado com Termos e Prestação; merece página própria no loop. |
| D11 | Tipografia | Rótulo da placa em token (`--texto-2xs`); metadados no celular em `--texto-sm`. Raiz de 90% **não** muda nesta etapa. | 8,1 px é ilegível; mudar a raiz afeta o sistema inteiro. |

## Lotes de implementação (Agente 2 implementa; Agente 3 testa)

### Lote 1 — componentes compartilhados (afeta Ofícios, Roteiros, Termos e demais listas)
- LP-01 Corrigir seletor `.registro--inativo .registro__link` (`listas.css` ~l. 596).
- LP-02 `z-index` do cabeçalho de mês acima do ⋮ das linhas (token, não número solto).
- LP-03 ⋮ com opacidade 1 sempre (hover só dá fundo).
- LP-04 Criar `selo--neutro` (ou trocar os 16 usos por classe existente) — nenhum selo montado à mão.
- LP-05 Rótulo da placa em token (`--texto-2xs`); `placa--cancelada` tacha só o número.
- LP-06 Tag/domínio `selo_tempo` (D3) com testes por fronteira; aplicar em Ofícios, Roteiros e Termos.
- LP-07 Orçamento de selos + tipo do ofício (D4) com regra no domínio (`dominio/assunto.py`), anotado em lote.
- LP-08 Título = destinos (≤ 3 + "+N"), período no meta (D5) em Ofícios e Termos.
- LP-09 Metadados em colunas ≥ 1024 px (variante do componente `.registro__meta`), altura constante; 768–1023 em duas faixas; celular em pilha legível.
- LP-10 Celular: placa dentro da linha do título e ⋮ no canto; meta máx. 2 linhas; meta ≥ 3 ofícios por tela a 390×844.
- LP-11 Foco das abas e de `summary` com o anel do DS; abas com indício de rolagem + aba ativa visível.
- LP-12 UI Lab atualizado com tudo o que mudou (estados: normal, hover, foco, cancelado, inativo, celular).

### Lote 2 — comportamento da lista de ofícios
- LP-20 Abas temporais (D1/D2) + filtro Documento + contadores do recorte.
- LP-21 Gaveta de filtros (D6) + Ano + ordem com rótulos honestos + fichas de filtros ativos + Limpar correto (F8).
- LP-22 Busca: placa na busca ampla (F1), destino sem a sede (F2), `unaccent` no motivo (F4), refino mesmo com uma leitura quando a ampla vem vazia, placeholder com os campos.
- LP-23 Vazio certo para qualquer filtro (F5); erro de rede na busca HTMX com "Tentar de novo".
- LP-24 `voltar` vivo nos diálogos depois de busca HTMX (F3).
- LP-25 `select_related` do motorista externo (F9) e consultas constantes (≤ 20) com 20 e 200 ofícios.
- LP-26 Contagens não repetidas: h2 só leitor de tela sem busca; barra "N de M ofícios"; cabeçalho de mês com contagem.
- LP-27 XLSX: Situação "Arquivado" quando for o caso (L4); Tipo com Retificado/Complementar.

### Lote 3 — ações
- LP-30 Menu ⋮ canônico com itens descritos (D7) — componente `menu__item--descrito` no UI Lab.
- LP-31 Barra fixa com menu "Mais" (D8).
- LP-32 Página de Numeração (D9) com testes de permissão (só gestor) e de serviço.
- LP-33 Docs do design system atualizadas (`components.md`, `page-archetypes.md`).

## Critérios de aceite (QA)
Ver `parity/oficios-lista.md` §6 + : nenhuma rolagem horizontal 360–1440; axe sem violações nos
estados (lista, gaveta aberta, menu aberto, resumo aberto, vazios, celular); ≥ 3 ofícios por
tela a 390×844; linhas de altura constante a ≥ 1024; Roteiros e Termos sem regressão após os
componentes compartilhados; `scripts/verificar.sh` verde; benchmark legado × novo das tarefas:
achar um ofício por número, por destino, por servidor, por placa; ver rascunhos; ver o que vai
acontecer; cancelar; baixar documentos; exportar.
