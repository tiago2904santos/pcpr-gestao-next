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
