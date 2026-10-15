# Viagens — refinamento profundo de 15/10/2026

## Observar → entender

Pedido de refino profundo de Viagens. Branch `main`, alterações simultâneas em
Planos, OS, calendário, modelos e CSS compartilhados preservadas. Inspeção de
produto, migração, views/serviços/forms, receitas locais e arquétipos existentes.
Capturas reais anteriores em 360/1440: Lista, vinculada 1, básica 5, cancelada 3,
lote 1. Navegação GET no PREVIEW; banco e mídia DEMO não foram resetados.

A viagem com documentos mostrava 41 Ofícios disponíveis e outros vínculos abertos
antes da estação documental. A prontidão podia dizer “Tudo pronto” ao lado de
divergências de datas. O objetivo persistido não aparecia no modo consulta.

## Projetar → implementar

Contrato `product/viagens-refinamento-profundo.md`, ADR 0039. Usada receita local
`nova-tela` para organização por arquétipo, estados, navegador/axe e capturas.
Não há alteração do domínio, serviço ou API: apresentação dos mesmos dados.

- Lista com cabeçalho de resultados visível e relações documentais legíveis.
- Folha: Dados → Documentos → Vínculos recolhidos → Conferência → Histórico,
  mesma ordem visual e DOM. Sem índice extra no cabeçalho.
- Documentos antecipados com cinco grupos, quantidade, estado/origem, criação
  externa e estados vazios. Região viva mantém ID e não contém campos editáveis.
- Vínculos continuam dentro de `form-viagem`, inclusive recolhidos. Filtro local
  reutiliza o controlador de conjuntos (sem conjuntos/aplicar/desmarcar).
  FormData/seleção não mudam ao filtrar; Enter não envia o formulário.
- Conferência usa nove etapas reais; resolvidas recolhidas, pendentes abertas.
  Divergências em bloco distinto; ação existente protege vias assinadas.
  Quando todas estão concluídas, a grade inteira começa recolhida para priorizar
  divergências. Dois testes de apresentação cobrem ambas as condições sem banco.
- Motivo/descrição lado a lado no desktop; objetivo também no modo consulta.
- Lote com contexto de período/roteiro, equipes/transporte agrupados e opções
  de documentos. Geração mantém rascunhos e não substitui Plano/OS existentes.
- CSS delimitado ao módulo; barra móvel mantém feedback de salvamento visível.

## Testar

- 409 testes de tokens e comentários de templates aprovados em 9,38 s;
  Ruff inicial e tipos JavaScript sem erro. `estatica-inicial.log`.
- Repetição após os ajustes finais: 409 aprovados em 5,87 s, Ruff e tipos JS
  aprovados; `estatica-final.log`.
- Conferência compacta: **411 aprovados em 20,51 s** (dois casos de apresentação
  mais tokens/templates), Ruff aprovado; `conferencia-compacta.log`.
- `final-manifesto.json`: 14 combinações, HTTP 200, overflow 0, nenhum erro JS
  ou violação axe no conteúdo. Capturas 360/1440 revisadas: topo, documentos,
  conferência, vínculos abertos, consulta/cancelada e lote. A rodada final foi
  repetida após permitir que nomes longos quebrem no seletor de tipos.
- Complemento de lote em 360/1440 (`complemento/`, `complemento-manifesto.json`):
  equipe/transporte e opções inferiores capturados em tamanho legível e revisados.
  Ambos HTTP 200, overflow/JS/axe/POST 0; nenhum documento DEMO gerado.
- Gate integral em candidato Linux isolado, PostgreSQL descartável próprio,
  oito workers, bancos `test_pcpr_viagens_gate_gw*`, criados do zero para conservar
  as cargas de migração. Nenhum banco da aplicação é alvo da suíte.
  Resultado: **2.595 aprovados e 1 falho em 3.802,78 s**, `verificar.log`.
  A única falha foi `test_criar_pela_tela_e_folha`, pela expectativa literal do
  texto vazio antigo. Nenhum teste de domínio, serviço ou permissão falhou.
  O teste foi atualizado e fortalecido; não houve skip/xfail ou remoção de caso.
  O cache de falhas continha apenas esse ID. Reexecução de `scripts/verificar.sh`
  com `PYTEST_ADDOPTS="--lf --reuse-db"`, dois workers: repetição incremental
  explícita do único caso falho e de todas as etapas estáticas; não é uma segunda
  execução integral dos 2.596 casos. Resultado terminal em `verificar-reteste.log`.
  **Exit 0, 1 aprovado em 48,76 s, “tudo verde”**. Ruff, 16 contratos de imports,
  mypy (309 fontes), Bandit, migrações e tipos JavaScript também aprovados.
- Navegador em `test_pcpr_viagens_browser`: testes reais de Lista/Folha/lote,
  geração, calendário, autosave/conflito e novos casos de busca/ordem/formulários.
  **24 aprovados em 1.049,08 s**, dois workers Linux; `navegador-linux.log`.
- A execução nativa Windows foi encerrada sem resultado terminal: a sincronização
  de papéis em `post_migrate`/flush dominava o tempo, demonstrada por stack somente
  leitura. Repetição integral dos 24 casos no candidato Linux, dois workers,
  navegador Chromium fixado no lock do projeto, mesmos testes e banco PostgreSQL
  próprio (`test_pcpr_viagens_browser_gw*`). Não se modificou Identidade para
  acelerar a suíte nem se retiraram testes. Infra apenas no contêiner QA.
- O teste HTTP de criação ainda exigia a redação vazia anterior. Atualizado para
  exigir a nova orientação de Ofícios, os cinco estados vazios e Documentos antes
  de Vínculos. Repetição isolada: 1 aprovado em 80,45 s (`estado-vazio-final.log`).
  Tentativa diagnóstica no banco da execução Windows interrompida encontrou fixture
  residual (unidade sintética duplicada), não erro da aplicação; reteste usou outro
  banco TEST próprio, sem duplicação. Gate integral conserva o log da primeira rodada.

## Comparar → criticar → corrigir

Inspeção das primeiras capturas identificou seta sem símbolo e ícone de calendário
isolado acima da data no documento. Corrigidos usando seta existente e flex inline.
Quando as nove etapas estão concluídas mas existem divergências, a mensagem agora
orienta conferi-las, sem anunciar prontidão total.
O cabeçalho conta informações divergentes, não documentos distintos: várias
divergências podem pertencer à mesma peça. A grade concluída foi recolhida após
revisão das capturas mobile, mantendo as pendências abertas e a ordem real.

O primeiro script novo de captura rotulava larguras sem aplicá-las ao viewport.
Imagens de `depois/` não valem como evidência responsiva; script corrigido para
aplicar `set_viewport_size`. Somente a rodada `final/` serve à validação 360/1440.

A revisão do contrato de proteção detectou que filtrar, embora não alterasse
FormData nem enviasse POST, podia marcar o formulário como sujo. O controlador
existente passou a conter `input/change` da busca no próprio controle; só caixas
e campos reais chegam à proteção/autosave. Asserções novas cobrem estado visível
inalterado após filtrar, Enter e saída do foco, em Viagens e no consumidor Planos.
Repetição dos três casos: **3 aprovados em 345,76 s**, `filtro-sem-sujo.log`.
Captura GET final também exercita busca, Enter/blur e restauração nas duas larguras:
seleção e status preservados; manifesto registra zero POSTs tentados/bloqueados.

## Validar

Navegador, retestes do filtro, apresentação e capturas finais revisados e aprovados.
Gate concluído cumulativamente: execução integral mais rechecagem incremental
explícita do único teste cuja expectativa de apresentação mudou. Fonte do candidato
isolada de alterações concorrentes; nenhum teste removido ou marcado como skip.
Paridade e catálogo atualizados. Sem mudança de domínio, permissões ou documentos
oficiais; nenhum reset/semeadura/gravação do dataset DEMO.
Não confundir homologação visual do usuário com resultado técnico.

Avisos preservados: depreciação pypdf, ordenação de paginação no recorte de vazios
(Termos/Viagens) e orçamento SQL da Folha (63 consultas, limite 25; faixa 62–69 já
registrada no QA de 12/10). Nenhum budget foi aumentado e não se alega ganho de
latência. São dívidas anteriores, fora desta recomposição de apresentação.
