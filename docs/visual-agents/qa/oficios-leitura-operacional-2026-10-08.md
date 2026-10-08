# Ofícios — fechamento do piloto operacional

Base: `0213d75`. Branch: `codex/oficios-leitura-operacional`. Escopo desta rodada:
Lista e Resumo, componentes reutilizáveis e vitrine. Folha/Documentos foram observados
e testados para detectar impactos compartilhados; não são uma nova frente de redesign.

## Implementação

Lista organiza identificação, viagem, equipe/transporte, diárias e menu em colunas.
Período e protocolo compartilham uma faixa; selos ficam abaixo do destino. Valores
e composição das diárias aparecem sem recorte no desktop. Celular mostra protocolo,
dedica faixas inteiras à equipe/transporte e conserva o valor à direita.

Resumo reutiliza metadados rotulados, com filetes, números tabulares e rótulos claros.
O cabeçalho documental, roteiro, conferência financeira, ações e documentos existentes
continuam disponíveis. Não mudou regra de negócio, cálculo, permissão ou documento oficial.

Componentes: `identidade_documental.html` (variante compacta), `metadado.html` (novo),
`cabecalho_registros.html` (novo), variante `registro--documental` e faixa
`registro__agenda`. CSS na origem dos componentes/listas. Nenhum novo JS ou pedido de rede.
UI Lab mostra a variante documental e os metadados com dados completos/ausentes.

## Autocrítica e correções

- Primeira versão gastava altura excessiva: respiro reduzido e agenda agrupada.
- Regra antiga recortava a composição financeira: altura automática e teste específico.
- Metadados ganharam filetes com respiro menor para preservar a leitura no celular.
- Gate detectou perda do contrato `placa__numero` usado pelos testes de filtros. Contrato
  restaurado dentro da identidade compartilhada; nenhum teste essencial foi enfraquecido.
- Destinos/equipe muito longos ainda usam resumo/reticências conforme a regra existente;
  os nomes completos continuam no título, nome acessível e Resumo.

## Evidências

Renderização real, dados sintéticos PREVIEW/LAB. Capturas antes da alteração em 8010
e depois em 8012; mesmo dataset. Contextos novos, fontes carregadas, documentos prontos.
360/390/768/1024/1440 px. Comparação com a base desta rodada, sem reutilizar o antes de fdc662f.

Galeria: [antes/depois nas cinco larguras](oficios-leitura-operacional-evidencias.md).
Pasta: [evidências desta rodada](../evidencias/oficios-leitura-operacional/).
Resumo: zero overflow horizontal e nenhuma rolagem interna do roteiro nas cinco larguras.
Console das capturas antes/depois sem erros. Logs completos e relatórios axe são arquivados
com hashes; normalização remove somente espaços finais e padroniza quebras de linha.

Navegação manual no navegador integrado, origem limpa `localhost:8012`: busca por
Salto, filtro Rascunhos e recorte de exportação coerentes; Resumo do Ofício 160/2026
aberto pela lista, com pendência institucional preservada. Enter abriu Mais ações;
Escape devolveu foco ao botão; segundo Escape fechou o Resumo e devolveu foco ao
registro de origem. Console dessa navegação sem erros. Nenhum formulário foi salvo
e nenhuma ação destrutiva/documental foi disparada nessa conferência manual.
Na aba Cancelados, selo, identificação tachada (`line-through`) e recorte de
exportação foram conferidos; voltou-se à Lista completa ao concluir.

Fontes: [manifesto de 10 arquivos](../evidencias/oficios-leitura-operacional/fontes-validadas.json).
Tokens e peso do CSS: [custo das fontes](../evidencias/oficios-leitura-operacional/custo-fontes.json).
Relatórios: [axe por página/largura](../evidencias/oficios-leitura-operacional/axe/),
[logs e hashes](../evidencias/oficios-leitura-operacional/logs/).
Integridade: [153 evidências com SHA-256](../evidencias/oficios-leitura-operacional/manifesto-evidencias.json),
10 fontes de produto sem divergência e 22 relatórios axe finais vazios. Esse conjunto
não apaga as falhas preservadas dos testes anteriores ou do estado de carregamento.
Hash das fontes normaliza texto para LF. Atributos locais mantêm JSON/logs em LF
no checkout, preservando os hashes das evidências entre ambientes.

## Testes

- Tokens: 68 passaram; repetição final: 68 passaram.
- Primeira suíte de navegador/interação: 30 passaram / 1 falhou em 379,39 s.
  Falha: CSP no caso assíncrono de cópia, já reproduzida na referência funcional anterior.
- Revalidação intermediária Lista/Folha/Documentos/UI Lab: 7 passaram em 310,51 s.
- Consolidado de 16 casos: 15 passaram / 1 falhou em 634,46 s. Lista/Folha/Documentos
  nas cinco larguras e Resumo nas cinco larguras passaram; os quatro dossiês do UI Lab
  (longo/ausente, 360/1440) passaram. O UI Lab completo falhou apenas em 360 no estado
  de carregamento do itinerário, fora dos componentes alterados.
- Repetições do teste original do UI Lab completo, sem exclusões axe: 360 passou em
  154,63 s; 1440 passou em 66,29 s. Relatórios separados por largura preservados.
- Identidade compacta após restauração do contrato HTML: 5 passaram em 381,94 s;
  Lista/Folha/Documentos, console estrito, axe sem exclusões, teclado e foco.
- HTTP dos filtros/ordenação: 31 passaram / 140 não selecionados em 691,43 s.
- `scripts/verificar.sh`: primeira execução interrompida ao detectar a regressão de
  marcação; execução final integral **verde**, saída 0: 2.197 passaram, zero falhas,
  7 avisos em 2.925,58 s (48min45s). Ruff, 16 contratos de importação, mypy (303 arquivos),
  Bandit, migrações e tipos JS passaram. Os avisos de WeasyPrint/pypdf são depreciações
  de bibliotecas, preservadas no log; não se relaxou nenhum check.
- Performance: três rotas medidas antes e depois; três reprovações por orçamento em
  ambas as versões. A coleta concorrente teve TTFB alto; repetição isolada voltou ao teto.
  Coleta isolada do código final: 3 falharam / 3 não selecionados em 71,72 s.
  Os orçamentos de recursos anteriores continuam reprovados. A Folha também mediu
  DB 84 ms para teto de 80 ms; repetição focada sem alteração de código: 24,8 ms,
  com as mesmas 21 consultas. Esse caso continua reprovado nos orçamentos de recursos
  anteriores, mas o desvio de banco não se repetiu: 1 falhou / 5 não selecionados,
  em 34,70 s. As duas medições são preservadas.

Os conjuntos se sobrepõem. Não somar essas quantidades como cobertura de casos distintos.

## Performance real do código final

Relatórios antes/depois em `performance-comparacao.json`, com as amostras e recursos
HTTP preservados. Não são tamanhos de fonte ou estimativas. A coleta de fechamento
ocorreu após o término da integral e das demais suítes de navegador.

- Lista: TTFB 70 → 104 ms; FCP 224 → 272 ms; LCP 648 → 692 ms; INP 88 → 96 ms;
  CLS 0. HTML 50,0 → 51,2 KB; CSS 161,3 → 164,9 KB (gzip 30,7 → 31,1 KB).
  JS 104,4 KB, 23 requisições e 12 consultas, sem aumento.
- Resumo: TTFB 91 → 96 ms; FCP 272 → 392 ms; LCP 272 → 804 ms; INP 176 ms;
  CLS 0. HTML 69,2 → 70,5 KB; CSS 161,3 → 164,9 KB (gzip 30,7 → 31,1 KB).
  JS 106,8 KB, 24 requisições e 18 consultas, sem aumento.
- Folha: TTFB 133 → 150 ms; FCP 336 → 476 ms; LCP 716 → 864 ms; INP 32 ms;
  CLS 0. HTML 129,6 KB; CSS 151,0 → 151,7 KB (gzip 30,2 → 30,3 KB).
  JS 151,2 KB / gzip 52,8 KB, 34 requisições e 21 consultas, sem aumento.
  Tempo de banco 71,8 → 84,0 ms: desvio registrado, não ocultado pela mediana anterior.

Tempos de carregamento/interação ficaram dentro dos orçamentos. O tempo de banco
da Folha excedeu o teto na coleta completa e voltou a 24,8 ms na repetição focada,
sem alteração de código/consultas (TTFB 111 ms, FCP 364 ms, LCP 768 ms, INP 24 ms,
CLS 0). Relatórios adicionais em `performance-folha-repeticao/`, conservando a URL
e o identificador realmente usados pela fixture. O custo atual de CSS/HTML é assumido
como custo desta implementação. Nenhum orçamento foi elevado e nenhuma consulta,
biblioteca, script ou requisição foi acrescentada.

## Classificação das pendências

**Regressões desta rodada, corrigidas:** marcação do número; recorte da composição
financeira na primeira proposta; excesso de espaço da primeira composição.

**Preexistente / não bloqueante:** CSP de estilo inline no polling HTMX. Evidência da
base em `oficios-premium-2026-10-08.md` e nos logs do bloco anterior. Não houve alteração
de CSP, HTMX, polling ou geração nesta rodada. A navegação manual de busca/filtro teve
console limpo; isso não substitui a falha do teste assíncrono.

**Dívida técnica de recursos:** os três orçamentos já falham na base 0213d75. A rodada
acrescenta CSS e HTML, cujo custo é apresentado na comparação; não classificar esse
incremento como preexistente. JS, consultas e requisições não aumentaram na medição
isolada. Não se elevou orçamento para fazer o teste passar.

**Preexistente / intermitente sob carga:** contraste dos totais do itinerário enquanto
`aria-busy=true`, observado no UI Lab completo em 360. CSS esmaece o grupo a 0,45 e
os valores a 0,5; arquivo CSS e componente JS são idênticos à base `0213d75`, comprovados
em `carregamento-itinerario-preexistente.json`. O log do consolidado registra contraste
2,02/1,58. Repetições originais 360/1440 passaram. As páginas de Ofícios e os dossiês
alterados passaram com todas as regras axe. Não se declarou o estado de carregamento
acessível; a pendência fica registrada e delimitada, sem abrir um redesign de itinerário.

**Limites visuais:** documentos oficiais A4 mantêm escala e tipografia institucional;
apresentação móvel do papel continua limitada. Não se mudou documento oficial.

**Desvio de medição não reproduzido:** banco da Folha mediu 84 ms e depois 24,8 ms,
sem alterações e com 21 consultas em ambas. Não se classifica o valor de 84 ms como
regressão demonstrada nem se apaga a coleta. Não se iniciou otimização ampla.

**Bloqueantes / regressões funcionais restantes:** nenhum demonstrado nas suítes
concluídas. O contrato HTML restaurado está coberto pelos 31 HTTP e pela integral.
As ressalvas acima permanecem abertas; CI/performance global não são declarados verdes.

## Decisão

**APROVADO COM RESSALVAS — avaliação do agente**, limitado ao piloto Lista e à
aplicação do padrão no Resumo. Gate integral verde, fluxos tocados e capturas revisados,
componentes demonstrados no UI Lab, sem regressão funcional conhecida nesta rodada.
Não representa aprovação estética do usuário nem conclusão de toda a missão de Viagens.

Implementação local validada: `a2c5e42` — `feat(ui): refinar leitura operacional de Ofícios`.
Pacote de evidências/documentação consolidado no commit seguinte, sem alteração de produto.

Próxima página recomendada depois do fechamento: Folha/Cadastro de Ofício, com foco
na proporcionalidade dos campos e na composição de equipe/transporte, dentro de Ofícios.
Sem push, merge ou deploy; sem abrir Termos ou outro módulo.
