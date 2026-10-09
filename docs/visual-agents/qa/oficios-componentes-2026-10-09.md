# Refinamento de componentes — Lista e Cadastro de Ofícios

Base `ffcc343`, branch `codex/oficios-componentes`. Direção preservada: Resumo
aprovado como referência; candidatas Lista/Cadastro aguardam revisão visual.
Escopo restrito a componentes dessas duas páginas e à sua origem compartilhada.
Regras protegidas: `docs/product/oficios-lote-h.md`, versões documentais e
eProtocolo. Nenhuma alteração de cálculo, permissão, documento oficial ou integração.

## Auditoria curta antes de implementar

- **Placa/registro — Lista:** identidade presa ao topo, pouca relação com altura
  do registro. Centralizar no desktop; altura coerente e número tabular. Todas as situações.
- **Chips — Lista/cabeçalho/pendências:** mensagens longas disputam largura;
  algumas pendências viram cápsulas multilinha. Selos compactos indivisíveis;
  avisos longos viram mensagem com leitura contínua, sem truncar instrução.
- **Ações — Lista/equipe:** três pontos soltos; controles de equipe aparecem só
  em hover. Área de clique alinhada, hover/foco próprios, visibilidade em toque.
- **Busca/abas — Lista:** rever altura, contagens, selecionado, foco e truncamento.
  Preservar rádios, links, parâmetros, atualização OOB e resposta sem JS.
- **Gaveta — Lista:** sete campos em grade uniforme deixam lacunas. Grade semântica
  para ordem/datas/ano/situação/valor e rodapé claro; folha mobile preservada.
- **Índice de preparação — Cadastro:** links azuis e estados fracos. Grafite,
  marcador de conclusão, item atual sem sombra dourada e foco separado do estado.
- **Campos — compartilhados:** rever borda, seletor, erro, readonly/disabled e
  foco sem halo exagerado. Alterar apenas deficiências verificadas; testar UI Lab.
- **Identificação/protocolo — Cadastro:** manter largura semântica, conferir
  labels e linha de checkbox. Evitar cortar campo ou orientação.
- **Transporte/viatura — Cadastro:** flex de largura fixa deixa campo e vão.
  Grade de dois controles; campos condicionais organizados pelo tipo escolhido.
- **Motorista externo — Cadastro/Lista:** divulgação sem identidade. Bloco de
  pessoa externa com motivo institucional e campos agrupados; distinção visível
  na lista. Sem mudar modo, fechamento ou cálculo de diárias.
- **Equipe — Cadastro:** cards e controles precisam funcionar em toque e teclado;
  conferir nomes longos, motorista e metadados sem esmagamento.
- **Roteiro — Cadastro:** rever campos de data/hora, seleção, trechos e diárias;
  preservar contratos do itinerário e carregamento do editor.
- **Documentos/eProtocolo — Cadastro:** revisar ações, cópia, estados de geração,
  erro/retry, medidas das áreas de leitura e mensagens.
- **Autosave/pendências/rodapés/vazios — ambas:** feedback com hierarquia e contraste;
  nenhuma ação encobrindo conteúdo; mensagens claras e ações alcançáveis.

## Evidências e validação

Capturas reais em [galeria](../evidencias/oficios-componentes/index.html): 35 pares
antes/depois, nas larguras 360, 390, 768, 1024 e 1440. Sete estados por largura:
Lista, filtros abertos, identificação, equipe/transporte, roteiro, documentos e
motorista externo preenchido. PNGs originais sem edição. A pasta `iteracao-1`
preserva uma versão intermediária. As posições de ancoragem mudaram deliberadamente:
o cabeçalho não é mais descontado duas vezes.

### Alterações incorporadas à candidata

- **Placa e ações:** identidade centralizada com o menu; coluna reserva a largura
  real do botão. No mobile, placa/menu compartilham a primeira faixa e os estados
  ocupam uma faixa própria depois do destino. Fonte móvel não é mais sobrescrita
  pelo registro genérico. Verificações geométricas: diferença entre centros ≤2px.
- **Selos:** unidades indivisíveis, sem encolhimento flex. Texto de protocolo e
  prazo cabe inteiro; mensagens longas de pendência passaram para `pendencia.html`,
  que permite leitura contínua. Não truncar instruções de resolução.
- **Filtros:** grade semântica preenche duas linhas no desktop; tablet usa duas
  colunas e mobile preserva a gaveta. Busca, abas, valores, rádios, intervalo,
  parâmetros, paginação, exportação e atualização OOB mantêm seus contratos.
- **Índice de preparação:** trilho cinza, grafite, estado atual escuro, conclusão
  por check, foco separado. Posição de leitura usa o `IntersectionObserver` do
  módulo existente, carregado sob demanda; links nativos continuam sem JS.
- **Transporte:** meio curto e viatura proporcional na mesma linha; outro meio
  recebe linha inteira. Motorista externo tem identificação, explicação e campos
  agrupados; nomes, IDs, obrigatoriedade e lógica de abertura/fechamento preservados.
  Lista distingue motorista externo de motorista da equipe em texto visível.
- **Equipe:** ações na lateral, visíveis em toque e mouse, nomes com quebra e
  menos espaço vazio. Marcação de motorista, remoção e atualização instantânea
  mantêm os handlers existentes.
- **Roteiro:** UF mostra duas letras. Ancoragens usam somente o desconto global
  do cabeçalho. Cálculo, adicional, trechos, domínio e serviço de rotas não mudaram.
- **Escolhas e divulgações:** checkbox/radio recebem alvo físico de 24px. Apenas
  o ícone de expansão gira; pessoa e cópia permanecem na orientação correta.
- **Origem compartilhada:** `components.css`, `formulario.css`, `listas.css` e
  `itinerario.css`; novos `pendencia.html` e `pessoa_externa.html`; variante
  `botao--menu-registro`; exemplos de estados no UI Lab. Sem CSS descartável ou
  biblioteca nova.

### Revisados e preservados

Busca e abas já têm estado selecionado, contagens e foco; a rolagem horizontal
móvel é intencional. Inputs/selects/textarea já usam tokens, labels flutuantes,
erro, readonly e disabled do DS; corrigidos os defeitos comprovados de proporção,
UF e alvo, sem trocar os controles por versões paralelas. Número/data/protocolo
mantêm larguras semânticas da reconstrução anterior.

Documentos/editor/eProtocolo, ações de salvar/minuta, autosave e fechamento mantêm
o padrão aprovado e os comportamentos atuais. O rodapé do Cadastro permanece no
fluxo; a barra da Lista conserva paginação/exportação. Estados vazios e de erro
usam os componentes existentes. A validação inclui cópia, atualização HTMX,
autosave, conflito, erro/retry e editor; não se presume cobertura de todos os
fluxos do módulo.

### Autocrítica e correções entre iterações

A primeira versão ainda tinha fonte pequena na placa, ações de equipe recuadas,
UF cortada e motorista externo com apresentação fraca. Corrigidos na origem.
Na extração do motorista, o fallback inicial podia exibir “Da equipe” no bloco
externo e o CSS antigo girava o ícone da pessoa: regressões introduzidas nesta
rodada, detectadas e corrigidas antes do fechamento.

As primeiras matrizes axe detectaram alvo insuficiente e o desconto duplicado do
cabeçalho. Os JSONs `componentes-qa-iteracao-{1,2,3}.json` registram essas falhas,
não são execuções aprovadas. Checkbox/radio foram corrigidos com o token físico;
as ancoragens deixaram de somar margem ao padding global.

Na matriz seguinte, duas ocorrências eram do botão “Limpar viatura” da seção
anterior, parcialmente cortado na borda superior ao alinhar o contêiner do roteiro.
Resultado bruto preservado em `componentes-qa-borda-viewport.json`. A matriz final
alinha o título do roteiro (como o teste de navegador existente); roda axe sobre
o documento inteiro, com as tags WCAG 2 A/AA, 2.1 AA e 2.2 AA. Não há supressão ad-hoc de regra,
seleção de nós ou filtragem de violações. Resultado final: **40/40 estados sem
violação axe, erro de console ou overflow** em `componentes-qa.json`.

Ainda há limites visuais: nomes longos são abreviados na Lista, com título completo;
no Cadastro quebram linha. O índice móvel continua rolável para manter rótulos
legíveis. Esses comportamentos são deliberados; revisão estética permanece com
o usuário. Não declarar Lista/Cadastro aprovados só pelo resultado técnico.

Alguns prints de equipe/roteiro mostram o fundo cinza do mapa com o percurso,
sem todos os blocos cartográficos externos. A captura aguarda `networkidle` na
navegação, fontes carregadas e 250ms depois de rolar; não exige conclusão de cada
bloco após a rolagem. Mapa, provedor e seu carregamento não foram alterados nesta
rodada. Isso limita a evidência visual do mapa; não comprova sozinho falha funcional
nem permite afirmar cobertura de disponibilidade do provedor externo. Sem retocar
o print ou expandir o escopo para uma integração cartográfica.

A bateria funcional encontrou **quatro falhas de overflow**, apesar dos 40 estados
PREVIEW verdes: o cenário sintético contém também a etapa Justificativa. O texto
`.sr-only` dessa etapa escapava do índice rolável, que não tinha vínculo de
posicionamento; largura de 413px na página de 360px. É regressão desta rodada,
não problema preexistente. A hipótese inicial de selo de diárias foi descartada
pelas medidas. `position: relative` no próprio índice contém o texto acessível sem
removê-lo, sem recortar a página e sem impedir a rolagem interna.

Diagnóstico real em `diagnostico/`; a prova DOM controlada adicional (não screenshot
de produto) reproduz etapa extra e registra 414→360/390px ao alterar somente esse
vínculo. Uma segunda tentativa diagnóstica teve erro de preparação porque reutilizei
o banco antes do teardown anterior terminar: erro da execução, não falha da aplicação.
Reruns usam bancos distintos. O gate parcial foi interrompido deliberadamente e
não conta como aprovação; gate integral reiniciado após a correção.

### Custo proporcional

Comparação com templates de `ffcc343`, mesmo banco fictício, três amostras por
página. Consultas aquecidas: Lista **16 →16**, Cadastro **24 →24**. Primeira leitura
da Lista teve três consultas de aquecimento. HTML: **130.920 →131.531 bytes** na
Lista (+0,47%); **154.876 →155.465** no Cadastro (+0,38%). Medianas locais:
Lista 1.036,16 →1.036,06ms; Cadastro 842,70 →869,17ms. Três amostras num LAB com
testes concorrentes não sustentam alegação de ganho nem regressão de latência.

Assets alterados, gzip estimado da fonte final com LF: CSS +1.036 bytes e JS +144 bytes,
total **+1.180 bytes**. Não é medição de transferência HTTP. O Cadastro passa a
importar o módulo pequeno de progresso existente; nenhuma biblioteca nova.
CSS/HTML totais volumosos são dívida anterior, delimitada nesta comparação;
não houve expansão para otimização ampla. Dados completos em `componentes-custo.json`.

### Fechamento validado

Bateria inicial: **32 aprovados e quatro falhas** em 36 cenários (19min49s).
Após a correção do índice, **10 retestes aprovados** (10min42s), cobrindo os quatro
reprovados e os demais casos de `test_oficios_visual.py` e `test_eprotocolo_copia.py`.
Os 32 iniciais incluem filtros frios/abertos, itinerário, Resumo/histórico/vazios,
UI Lab/foco global, motorista/autosave/conflito e falha/retry/PDF idempotente.
Logs brutos em `logs/componentes-browser-focado.log` e
`logs/componentes-browser-reteste.log`; não apresentar a primeira bateria como verde.
Capturas adicionais do Cadastro com etapa Justificativa e seus relatórios axe em
`componentes/cadastro-com-justificativa-{360,390}.png` e JSONs correspondentes.

Matriz PREVIEW repetida após a correção: **40/40 estados verdes**, console/overflow
zerados, cinco larguras e as mesmas tags WCAG habilitadas. Os E2E também incluem
WCAG 2.1 A, conforme `tests/e2e/conftest.py`. 35 capturas finais
regeneradas sobre a fonte corrigida. Teclado: Enter/Escape no menu com devolução
de foco, índice com `aria-current`, disclosure nativo e foco do UI Lab.

Os retestes emitiram dois avisos: depreciação HarfBuzz (também no gate anterior) e
cleanup do banco LAB de testes ainda acessado por uma sessão. Este último é uma
pendência da infraestrutura de testes, não bloqueou os cenários (exit 0); não
presumir que seja preexistente sem comparação específica. Nenhuma conexão remota
ou mídia DEV participou. Não declarar limpeza do banco concluída só pelo exit 0.

`scripts/verificar.sh` integral final **verde**, exit 0: **2.251 aprovados,
zero falhas, nove avisos**, 54min56s. Ruff, 16 contratos de arquitetura, mypy
(303 arquivos), Bandit, migrações e tipos JS passaram. Execução completa, sem
deseleção, `--lf`, supressão de falha ou mudança na fonte durante a execução.
Log bruto: `logs/componentes-verificar-fechamento.log`, encerrado por
`✔ tudo verde`. Os nove avisos são depreciações HarfBuzz/WeasyPrint e pypdf,
também presentes no gate anterior; não são nove falhas de aplicação. Avisos
de leitura de comentários pelo Bandit permanecem no log, sem checks reprovados.

O gate intermediário terminou com **2.250 aprovados, uma falha e nove avisos**
(52min53s), registrado em `logs/gate-contrato-antigo-falhou.log`. Encontrou
`TestLinhaDaLista.test_motorista_marcado_e_motorista_de_fora_aparece`:
o assert exige a antiga indicação externa apenas em `sr-only`. A missão pede
distinção visível, e a candidata apresenta “(motorista externo)”, mantendo nome,
ordem do motorista e title completo. É contrato de apresentação desatualizado,
não alteração de domínio. Expectativa atualizada para proteger a distinção visível,
o title completo e ausência de duplicação para leitor de tela, com assert limitado
ao registro correto. **Três HTTP da classe passaram** (1min28s) e Ruff passou.
Teste mantido ativo; essa execução intermediária com falha não é gate verde.
Gate integral final em `logs/componentes-verificar-fechamento.log`, com fonte de
18 arquivos registrada em `fonte-validada.json`. A aplicação permaneceu igual à
fonte dos retestes de navegador; a última mudança foi apenas no contrato HTTP.

O gate intermediário usou uma base LAB distinta e avisou inicialmente que esse banco-base
não existia para checar o histórico de migrações. Base criada e o mesmo comando
`makemigrations --check --dry-run` reexecutado: **No changes detected**, exit 0,
sem esse aviso (`componentes-migracoes-final.log`). A integral final também passou
a checagem de migrações sem esse aviso. Não esconder o aviso da primeira
execução nem atribuí-lo à aplicação. Todas as conexões são locais, porta 55432;
sem bancos remotos. LAB descartável não valida durabilidade operacional.

O apontamento anterior de CSP no fallback de cópia permanece delimitado no pacote
`oficios-resumo-reconstrucao-2026-10-08.md` e suas evidências de base. `copiar.js` e
CSP não foram alterados nem relaxados. Console limpo dos 40 estados PREVIEW não
significa aprovação de toda combinação de clipboard/permissão em todos os navegadores.

Incidente dos dois PDFs DEV da rodada anterior permanece pendente de resposta do
usuário, separado desta entrega e não classificado como preexistente. Mídia PREVIEW
isolada; sem semeadura, substituição, alteração de hashes/histórico ou recuperação
nesta rodada. Detalhes em `oficios-lista-cadastro-2026-10-08.md`.

### Decisão e próxima ação

**Candidata tecnicamente validada; revisão visual pendente do usuário.** Não há
regressão funcional conhecida ou teste bloqueante restante nesta rodada. Os
defeitos demonstrados do índice, alvos de toque, ancoragem, UF e indicação externa
foram corrigidos e revalidados. Quatorze grupos de componentes revisados; oito
famílias de refinamentos, mais os padrões compartilhados e exemplos do UI Lab.

Ressalvas não bloqueantes delimitadas: depreciações de bibliotecas, aviso de
cleanup na bateria focada, nomes abreviados com título completo, índice rolável,
capturas sem exigir todos os blocos cartográficos e fallback CSP de cópia já
reproduzido na base anterior. CSS/HTML volumosos permanecem dívida técnica
preexistente. A pendência dos PDFs DEV pertence ao incidente anterior, não foi
resolvida nem ocultada por este gate LAB.

Próxima ação: revisão das capturas de Lista e Cadastro pelo usuário. Sem avanço
para Termos, outro módulo, push, merge ou deploy. Commit local após conferência
das 18 fontes/testes congelados e `git diff --cached --check` sobre fonte,
documentação e evidências, excetuando os arquivos `.log` brutos. Estes preservam
espaços finais emitidos pelo terminal/tracebacks; não foram editados para passar
a conferência de whitespace. Nenhum erro de whitespace em código/documentação.

Commit local da candidata: **`18de18f`**, na branch `codex/oficios-componentes`,
com implementação, testes, UI Lab, documentação, paridade e evidências. Fonte
conferida sem divergência dos 18 hashes depois do gate. Registro final deste
hash em commit de documentação posterior, sem alterar a aplicação. Sem push,
merge ou deploy.
