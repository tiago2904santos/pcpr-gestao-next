# Explorações de componentes (Overdrive 2)

Registro das abordagens testadas no UI Lab (seção 11, `/ui-lab/#conceitos`) antes de cada
escolha. A regra: três conceitos por componente central; só entra no produto o que passa
por **melhora a experiência? melhora a compreensão? continua eficiente o dia inteiro?**

| Componente | A | B | C | Escolha e motivo |
|---|---|---|---|---|
| Botão de ação | pílula + toast | **linguagem de ação** (processando → concluído / recusado no próprio botão) | barra de progresso interna | **B** — feedback onde o olho está; C inventa progresso que não existe |
| Status | pílula só por cor | **forma do marcador** (anel / ✓ / ×) | só trilho de processo | **B** — lê-se de relance e reaproveita a gramática no trilho e no progresso; C fica só no detalhe |
| Campo de texto | caixa branca com borda | linha de papel | **campo aceso** (tingido → branco + grafite + halo dourado) | **C** — identidade sem perder o alvo em grades densas; B some em formulários longos |
| Registro de lista | linha com ícone | **placa + grupos por mês + expansão em linha** | tabela densa | **B** — leitura pelo número, contexto sem sair da lista; C perde equipe/transporte no celular |
| Filtros | barra de campos (atual) | fichas removíveis | busca única com fichas | **A mantida** — dois controles bastam para o volume atual; fichas entram quando houver mais de três filtros |
| Progresso do formulário | índice lateral fixo | **faixa de progresso** com `<progress>` | só barra | **B** — diz o quê e quanto falta numa linha; A comprime o formulário (painel lateral) |
| Linha do tempo | vertical em painel lateral | **colunas + disclosure** abaixo do documento | linha única compacta | **B** — a folha ocupa a largura toda; C é compacta demais para auditoria |
| Foco | anel azul do navegador | **anel grafite + halo, dourado sobre escuro, campos acendem** | contorno pontilhado | **B** — assinatura própria, ≥ 3:1 em todos os fundos |
| Motion | fade/slide/scale | **continuidade espacial** (View Transitions: placa, aba, emissão, lista) | morphing por JS | **B** — zero JS, degrada para troca instantânea, desliga com reduced-motion |

Ideias mantidas "fora da caixa": o botão **Emitir** que se transforma no selo **Emitido**
ao chegar no detalhe; a **placa** que viaja da linha da lista até o cabeçalho; o
salvamento que **carimba na barra** em vez de abrir um toast.

## Segunda rodada (revisão UX e auditoria de acessibilidade)
Aplicado: título do registro sempre abre o detalhe (editar é ação explícita); selos de
contagem/justificativa só em rascunho; placa em linha no celular (1,5 → ~2,5 ofícios por
tela); histórico em grade por linha (ordem de leitura) e não em `columns`; um só estado no
cabeçalho do detalhe (o trilho); "Revisar e emitir" dourado só quando a emissão está
disponível e o número de pendências vira link; "Salvo" aparece no próprio botão depois do
recarregamento e a barra anuncia ao vivo; bordas de caixa/rádio/campo com ≥ 3:1; summary do
histórico visível quando aberto; expansão com estado de erro e novo clique após falha.

Rejeitado (com motivo): converter o salvar do ofício em HTMX parcial — o formulário tem
formset de destinos, comboboxes e validação de roteiro; a troca parcial multiplicaria
estados; a confirmação na barra + "Salvo" no botão entrega o mesmo feedback sem o risco.
Agrupar só quando ordenado por saída — o grupo por mês também dá ritmo à ordem por
número; o cabeçalho ficou mais discreto (grafite) para não disputar com o dourado.

## Cadastro do ofício (terceira rodada)
| Peça | Antes | Agora | Por quê |
|---|---|---|---|
| Novo ofício | cartão + "passo a passo" de 4 etapas que não era um assistente | abertura da mesma folha: placa tracejada à espera do número, unidade/sede, data e motivo; prévia das seções no rodapé | continuidade com a edição; nada promete etapas que não existem |
| Documento, custeio, transporte | rádios soltos | cartões de escolha com ícone e descrição | são decisões com efeito no documento; o cartão diz o que cada uma significa |
| Instituição que custeia | sempre visível | só com "Outra instituição" (`:has()`, sem JS) | campo irrelevante some |
| Porte de arma | caixa de seleção | interruptor (`role=switch`) | é um sim/não |
| Roteiro | fieldsets em caixas, legenda cortando a borda | itinerário sede → destinos → sede, trilho tracejado, trecho com "Saída de <ponto anterior>" | o roteiro é um trajeto; o rótulo diz de onde se sai |
| Justificativa | sempre aberta | em destaque quando obrigatória; recolhida (divulgação) quando dispensada | espaço para o que importa |
| Fim do formulário | lista de pendências | conferência: seções ✓/○, pendências-link, próxima ação | o formulário conclui |
| Progresso | some ao rolar | faixa fixa sob o topo com "você está aqui" | orientação sem painel lateral |
| Cabeçalho | unidade · sede · criado em | frase do ofício: servidores · destinos · período · transporte · valor | o que o documento diz até agora |

Descartado: pré-visualização viva do PDF ao lado (painel lateral; pedido explícito para não usar) e
assistente em etapas com páginas separadas (o operador volta a seções o tempo todo; a folha única
com âncoras e a faixa fixa é mais rápida).


## Campos e seletores (quarta rodada)
Pedido: componentes mais parecidos com os do modelo; calendário, relógio e listas não podiam
continuar com o visual nativo.

| Peça | Antes | Agora | Por quê |
|---|---|---|---|
| Campo | "campo aceso" (tingido em repouso) | caixa branca, rótulo na borda (conceito A do UI Lab) | é a linguagem que os usuários já leem no sistema de referência; a identidade fica no foco |
| Data | `input type=date` nativo | `<pc-data>`: dd/mm/aaaa + calendário próprio | o seletor nativo não segue a identidade e muda de navegador para navegador |
| Hora | `input type=time` / `datetime-local` | `<pc-hora>`: hh:mm + relógio em colunas; data e hora lado a lado nos trechos | como no modelo; digitar continua sendo o caminho mais rápido |
| Lista | `<select>` nativo | `<pc-select>`: lista própria sobre o `<select>` | a lista aberta do navegador não segue a identidade |

Descartado: `appearance: base-select` (lista customizável só com CSS). Hoje só o Chromium
suporta; o Firefox continuaria mostrando a lista nativa. Painel do calendário abrindo para
cima: ficava sob a faixa fixa de progresso.


## Refinamento visual V2 (componente por componente, página por página)
Evidências em `artifacts/visual-refinement-v2/` (galeria `comparacoes/index.html`, gerada por
`scripts/evidencias_visuais.py`).

| Peça | Antes | Agora | Por quê |
|---|---|---|---|
| Rótulos | `*` **e** "(opcional)" em todo campo | só `*` (e "(necessário para emitir)") | marcar os dois lados era ruído; o login chegava a dizer "Senha (opcional)" |
| Controles nativos | "x" azul no campo de busca (paleta, filtros), setas no numérico, amarelo do autofill, rolagem padrão | neutralizados em `base.css` | nada com a cara do navegador no meio da identidade |
| Central de módulos | um cartão estreito perdido na largura | console do módulo: números, ação e atalhos (itens do menu que o usuário vê) | a central passa a levar direto ao trabalho |
| Painel · coluna de contexto | três botões em bloco + cartão de texto | lista de atalhos com seta e lembrete como nota | menos caixa, mais leitura |
| Lista · registro | resumo aparece de uma vez | abre crescendo; linha recém-salva acende ao voltar | movimento que explica o que mudou e onde está |
| Lista · filtros | "Aplicar" ao lado de uma busca que já é ao vivo | some com JavaScript (fica para quem não tem) | um controle a menos sem perder a função |
| Tabelas no celular | rótulo/valor em linhas (uma tela por registro) | cartão: principal no alto, demais colunas 2 a 2 | metade da altura, leitura em grade |
| KPIs no celular | quatro cartões empilhados | dois a dois, compactos | a lista entra na primeira tela |
| Assistente de emissão | três pílulas soltas | etapas ligadas por um fio, percorrido em dourado | lê-se onde se está e o que falta |
| Senha | campo mudo | mostrar/ocultar dentro da caixa (login e troca de senha) | erro de digitação é a causa nº 1 de bloqueio |
| Resumo de erros / regras de senha | marcador desalinhado; lista HTML quebrando o parágrafo | itens alinhados; uma frase de ajuda, regras voltam como erro | legibilidade |
| Paleta no celular | entrada estourando e "Esc" cortado | entrada encolhe; "Esc" some abaixo de 480px | caber é o mínimo |
| CSS compartilhado | 31,2 KB gzip após as adições | 29,9 KB: catálogo sem uso (fichas, ordenação, linhas clicáveis, arquétipo de formulário) foi para `ui-lab.css` | orçamento mantido sem subir o número |
