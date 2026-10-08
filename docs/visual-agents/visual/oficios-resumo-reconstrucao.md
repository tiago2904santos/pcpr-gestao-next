# Reconstrução do Resumo — após reprovação visual

## Critério e limite

A entrega `a2c5e42` foi **reprovada visualmente pelo usuário**. A aprovação funcional anterior permanece histórica; não constitui aprovação estética. Referência desta rodada: `c027493`, com capturas novas do mesmo ofício sintético 06/2024. Escopo: somente o Resumo, incluindo revisão da emissão. Não propagar antes de aprovação visual do piloto.

Preservar os contratos de `oficios-lote-h.md`, `oficios-documentos-versoes.md` e `oficios-eprotocolo.md`: identidade, datas, cálculo, prontidão, permissões, versões, vias assinadas, retry, cópia e foco. Nenhuma regra nova. Componentes na origem do Design System, sem biblioteca ou JavaScript novo.

## Diagnóstico da base capturada

- A primeira leitura é uma ficha administrativa: metadados e explicações ocupam o início,
  enquanto documentos e assinatura ficam depois da missão, roteiro e equipe.
- Número e destino têm pouca presença na composição; falta uma identidade de registro.
- Trechos apresentam trajetos e horários em linhas, sem parear claramente saída e chegada.
- A conferência escura tem força visual, mas o restante do conteúdo não tem hierarquia equivalente.
- Arquivo e assinatura são blocos separados; repetir títulos alonga a leitura no celular.
- Mobile conserva a sequência da ficha; tablet comprime a mesma composição do desktop.

O Resumo reúne identidade, roteiro, equipe, dinheiro e arquivos: melhor piloto para testar
uma composição completa sem inventar regra, filtro ou operação nova.

## Exploração antes da implementação final

Três composições no UI Lab, com dados sintéticos iguais. Não são apenas mudanças de cor.

### A — Documento operacional vivo

- Ideia: um documento editorial que pode ser consultado e operado.
- Hierarquia: número e destino no topo; motivo como abertura; roteiro e equipe no miolo; conferência administrativa e documentos ao final.
- Documentos: índice de anexos com tipologia, versão e data, próximo ao fechamento do registro.
- Ações: rodapé discreto, leitura prevalece.
- Mobile: folha de leitura com régua de seções e roteiro vertical.
- Vantagem: ótima leitura institucional; composição serena.
- Risco: documentos e decisões continuam distantes do primeiro contato. Pode perpetuar a limitação principal da entrega reprovada.

### B — Mesa operacional do ofício

- Ideia: abrir o ofício para entender a missão, conferir seus arquivos e decidir a próxima ação.
- Hierarquia: faixa de identidade forte; documentos imediatamente acessíveis; percurso e equipe como conteúdo principal; valores e registro em contexto lateral no desktop.
- Documentos: estação com peças reconhecíveis, estado real, versão e data. Geração não se confunde com situação do ofício.
- Ações: dock persistente; pendências antes da decisão; ações secundárias no menu já existente.
- Mobile: identidade compacta, documentos em seguida, missão e percurso, equipe, conferência; uma única rolagem. Ações sempre disponíveis sem esconder conteúdo.
- Vantagem: transformação clara e ganho operacional; usa o espaço para separar leitura da missão e suporte documental.
- Risco: excesso de caixas e peso do cabeçalho. Evitar duplicação de status, bordas por todo lado e áreas vazias.

### C — Registro institucional editorial

- Ideia: uma ficha oficial de alto cuidado tipográfico, inspirada em registros e arquivos institucionais.
- Hierarquia: número monumental em coluna própria, destino e motivo ao lado; metadados em régua; sequência numerada de roteiro, equipe e anexos.
- Documentos: lista editorial com margens e separadores, sem cartões.
- Ações: faixa inferior; contexto integrado ao texto.
- Mobile: número e estado formam uma capa curta, seções numeradas guiam a leitura.
- Vantagem: personalidade, sobriedade e poucas camadas.
- Risco: número ocupa área demais; aparência de documento estático pode reduzir a clareza operacional.

## Princípios consultados

[DWP — interfaces internas](https://design-system.dwp.gov.uk/get-started/internal-systems): densidade para uso especializado mantendo rigor de usabilidade. [GOV.UK — task list](https://design-system.service.gov.uk/components/task-list/): estados claros, sem transformar conferência de respostas em checklist artificial. Não copiar aparência nem introduzir etapas de negócio.

## Decisão e evidências

Registrar aqui a escolha após renderizar as três alternativas, as duas iterações, autocrítica e validação. Diretório: `docs/visual-agents/evidencias/oficios-resumo-reconstrucao/`.

Escolha: **B — Mesa operacional**, após revisar as três renderizações reais em 360 e
1440. A traz leitura serena, mas mantém arquivos tarde; C tem identidade forte, porém
consome espaço com o número. B aproxima documentos e decisões da compreensão da missão.

### Iteração 1

Identidade grafite, número ampliado, documentos em coluna lateral, missão/percurso/equipe
na coluna principal, conferência separada. Em 360 os documentos passam para o início.
Capturas: `iteracao-1/`. Autocrítica: via assinada repete o título e torna o painel alto;
tablet aperta as duas colunas; percurso ainda parece uma tabela. Não aceitar essa versão.

### Iteração 2

Estação documental no início em toda largura. PDF e assinatura na mesma peça, com estado
real e todas as ações. Percurso mostra origem/saída e destino/chegada em pares, com virada
de dia quando presente nos dados. Conferência clara, equipe em faixas e transporte próprio.
Tablet tem percurso inteiro e conferência em duas colunas; celular ocupa a tela, com dock
e uma rolagem. Metadados institucionais passam para o contexto, sem apagar explicações.

Correções durante revisão: contagem de trechos usa o pluralizador sem duplicar o número;
menus de assinatura usam a camada de topo existente, para não serem recortados pela peça.
CSS dos três protótipos fica no UI Lab; produção carrega apenas os padrões reutilizáveis.

### Onde o usuário teria razão se ainda chamasse a tela de comum

- Os menus e controles de anexação conservam os componentes operacionais atuais; sua
  apresentação não foi reinventada. Preservar teclado e ações pesa mais que decorar.
- Percurso muito longo continua exigindo rolagem. Não reduzir legibilidade ou esconder
  trechos para caber tudo numa primeira captura.
- Número/destino curto deixa área livre no cabeçalho amplo; revisar com dados longos e
  não preencher com métricas repetidas ou ilustrações sem função.
- Vias assinadas com muitos avisos aumentam a peça; estados precisam permanecer completos.

Mudança estrutural em identidade, hierarquia, documentos/assinatura, percurso, equipe,
diárias, metadados, relação principal/contexto, tablet e celular. A comparação em miniatura
é uma evidência de impacto, não substitui a aprovação estética do usuário.

## Gate e correções de contrato

A primeira integral detectou uma regressão de markup: o teste essencial exige
`class="resumo"` no fragmento. O novo layout tinha acrescentado a classe da composição
nesse mesmo atributo. Contrato restaurado com contêiner de layout externo; nenhuma
asserção foi relaxada. Execução interrompida após diagnóstico e integral completa
reiniciada sobre o código corrigido (`reconstrucao-verificar-final.log`).

O foco da cópia ganhou margem de rolagem para permanecer acima do dock. Verificação
por teclado mede o campo focado e o limite do rodapé nas cinco larguras. CSS antigo da
composição substituída, sem consumidores, removido; padrões compartilhados preservados.

Na verificação final, a regra existente de campos somente leitura retirava o halo de foco.
O componente mantém agora o indicador completo também na cópia. Cinco larguras passaram
com foco real, halo, campo acima do dock, menu/Escape, console limpo e axe vazio.
