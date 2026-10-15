# Refinamento profundo de Viagens — 15/10/2026

Pedido explícito: refazer a composição do módulo, aproximando-o de Ofícios, Termos,
OS e Planos. Fontes funcionais: `propagacao-identidade.md`, `migration/viagem.md`,
`views_viagem.py`, `viagem.py`, `viagem_conferencia.py` e testes atuais.

## Observar e entender

Lista, viagem com documentos, básica, cancelada e lote capturados em 360/1440 em
`../visual-agents/evidencias/viagens-refino-20261015/antes/`. A viagem 1 abre dezenas
de caixas de vínculo antes de mostrar documentos; conferência mistura prontidão e
divergências; documentos não se distinguem de blocos de formulário. Tipo é repetido
no título, metadados e nota. No lote, a orientação ocupa uma seção sem informação
operacional suficiente. Nenhuma gravação DEMO ou consulta à produção.

## Projetar

- Manter LIST, hero e filtros reais. Refinar registros para distinguir período,
  destino, unidade, vínculos e ações, sem inventar número oficial ou indicadores.
- Folha contínua, sem índice extra abaixo do header: Dados → Documentos →
  Reaproveitar existentes (recolhido) → Conferência → Histórico.
- Documentos como cinco grupos reconhecíveis, contagem, estado vazio compacto,
  origem direta/pelo ofício e ação de criação com bloqueios existentes.
- Vínculos recolhidos inicialmente, seleção íntegra; usar busca local já existente
  em `conjuntos.js`, sem aplicar/desmarcar conjuntos, somente filtro e contagem.
  Identificar o limite real de 40 livres/tipo, sem prometer busca no banco inteiro.
- Conferência agrupada nas nove etapas reais. Distinguir etapas resolvidas de
  divergências entre documentos; manter todos os links e a proteção dos assinados.
  Quando todas estão resolvidas, recolher a grade em “Ver etapas concluídas” para
  não empurrar divergências para baixo. Etapas com pendências permanecem abertas.
- Dados: tipos/período e destinos/mapa com os controles compartilhados; motivo e
  descrição agrupados, inclusive na leitura. Lote destaca contexto, equipe,
  motorista/viatura e rascunhos a gerar, sem nova regra.

## Contratos e validação

Não alterar modelo, domínio, números, cálculos, geração ou permissões. Preservar
IDs/âncoras, nomes, querystrings, HTMX/OOB, `data-vivo`, versão/autosave,
`conhecidos`, formulários externos, confirmação de cascatas e cancelados em leitura.
`documentos` continua região viva sem campos editáveis. O filtro de vínculo não
tem nome: pesquisar não muda FormData, não salva nem limpa seleções; Enter só filtra.
Sem JS, caixas reais
e disclosures nativos permanecem funcionais. Estilo exclusivo para Viagens, sem
sobrescrever mudanças simultâneas em CSS/formulários compartilhados.

Obrigatório: testes HTTP/fluxos, navegador/axe, capturas revisadas 360/1440,
`scripts/verificar.sh`, paridade e QA com limites reais registrados.
