# Cadastro inferior — nova rodada de 09/10/2026

Estado: implementação e validação técnica concluídas; revisão visual do usuário pendente. Pedido atual prevalece sobre o fechamento anterior. Header,
Identificação e Equipe/transporte ficam preservados, inclusive ajustes do usuário.
Base de fonte: HEAD 722198f mais alterações locais do usuário, preservadas em
`var/cadastro-inferior-r2-baseline`. Gate anterior não valida esta rodada.
Prévia sintética local :8017, banco LAB existente :55432; sem reset/seed.

## Auditoria e intenção

- A / seletor de roteiro: campo ocupa toda a seção; integrar contexto e busca num
  recurso compacto, mantendo seleção, aplicação e aviso de prévia não gravada.
- A / destinos e UF: títulos repetidos, controles fragmentados; sequência legível,
  campos unidos, marcadores alinhados e ação de ordem com alvo suficiente.
- A / mapa e totais: altura depende da coluna inteira, métricas se quebram e nota
  compete com o percurso; painel de rota com mapa proporcional e legenda operacional
  própria (distância/tempo), sem mudar provedor ou cálculo.
- B / trechos: sequência repetitiva, chegada parecida com campo; composição de
  partida → duração → resultado; manter calendário, passos e alerta de sobreposição.
- B / diárias: números competem; total forte e demais dados mais discretos, sempre
  valor por servidor e estado do cálculo, com composição horizontal no desktop.
- C / justificativa: dar contexto curto e status evidente antes da edição; preservar
  textos prontos, texto dispensado e gestão de textos.
- D / documentos: separar decisão, dados copiáveis e trabalho documental; reutilizar
  o componente do Resumo, preservando campos e cópia completa.
- E / editor: ferramentas sem hierarquia e grandes páginas empilhadas; agrupar
  ferramentas e documentos sem perder ações, conteúdo oficial ou atalhos.
- F / histórico e rodapé: linhas com pouca hierarquia; log compacto e autoria clara,
  conclusão junto ao estado de gravação, mantendo todos os eventos e ações.

## Evidências

Antes em `../evidencias/oficios-cadastro-inferior-r2/antes/`, cinco larguras,
três estados existentes. Capturas, críticas, testes e pendências serão registrados
por bloco. Não inferir aprovação visual sem avaliação do usuário.


## Segunda crítica e correções

- A: rótulo flutuante cortava o seletor no mobile; variante usa rótulo estático.
  Mapa não acompanha a altura arbitrária da lista de destinos. Métricas abaixo dele.
- B: primeiro layout repetia demasiada hierarquia; desktop passou a identificar a
  rota à esquerda e concentrar controles à direita. Km não fica acima das cidades.
  Diárias perdeu o excesso de altura e de tipografia; valor individual permanece.
- C: estado duplicado no contexto saiu; texto antes da seleção de modelo. Texto
  dispensado incluído continua editável, com status explícito e divulgação aberta.
- D: rejeitada a coluna lateral de prontidão por deixar vazio sob a conferência.
  Conferência horizontal e cópia separada. Copiar tudo foi para a indicação da fonte.
  Expansão automática dos dados causava alvos parcialmente encobertos ao usar o
  editor; a divulgação agora abre por solicitação, com foco preservado pelo vivo.
- E: rótulos dos grupos voltaram a aparecer. Identidade do documento não fica
  confundida com o estado salvo. Sem sombra ou alteração no papel oficial.
- F: rejeitada a primeira grade mobile por sobrepor data e descrição. Data/hora
  agora ficam acima do evento; autoria embaixo. Sem cartões por evento ou barra fixa.

## Falhas intermediárias e base preservada

Ruff encontrou E501 em docstring e dois F821 em teste visual, ambos com hashes iguais
à base inicial (`lint-preexistente.json`). Corrigidos sem alterar regra ou remover
asserções funcionais: protocolo continua no cabeçalho e cópia ausente do Resumo.

Seis testes HTTP ainda exigiam HTML copiável do Resumo, incompatível com a decisão
já aplicada pelo usuário. Mantidas verificações de snapshot, maior versão, ausência
CPF/RG, indisponibilidade, autorização e GET sem escrita; apresentação agora exige
cópia na Folha e ausência no Resumo. Marcador `unit` não registrado no novo teste de
duração impedia coleta; retirada apenas a marca, preservadas todas as asserções.

Axe do Resumo apontou corpo rolável sem foco. Reproduzido também nos templates/CSS
da base preservada, no mesmo teste. Corrigido somente com tabindex, papel de região
e nome acessível; aparência aprovada do Resumo preservada. Nenhum módulo novo aberto.

Gates interrompidos para correções não são resultados verdes nem falhas reais de
trabalhadores (os workers mortos pela interrupção não representam bugs do produto).

## Fonte consolidada e testes

Resultados por execução, sem somar casos repetidos:
Os caminhos `logs/` abaixo são relativos à pasta de evidências
`../evidencias/oficios-cadastro-inferior-r2/`.

- Itinerário e tokens: 101 passaram (`logs/cadastro-r2-a-focused.log`).
- Navegador do itinerário compartilhado e percurso da Folha: 9 passaram.
- Percurso após separação da chegada: 5 passaram, cinco larguras.
- Prazo e Lote H: 65 passaram (`logs/cadastro-r2-c-focused.log`).
- HTTP eProtocolo e duração: 25 passaram após compatibilização com a decisão do
  usuário de manter a cópia somente na Folha.
- Resumo: 6 passaram, incluindo cinco larguras e protocolo no cabeçalho, após
  correção acessível do corpo rolável reproduzida na base.
- Editor/PDF, foco e reposição HTMX: 7 passaram na fonte final, após correção da
  margem de rolagem e da especificidade do seletor compartilhado (`:where`).
- Reexecução final de editor, carga, salvar, emissão, prazo obrigatório,
  calendário e relógio: 13 passed, 1 warning in 647.28s (0:10:47) (`logs/cadastro-r2-fluxos-definitivos.log`).
- `scripts/verificar.sh` integral: 1 failed, 2290 passed, 9 warnings in 3045.12s (0:50:45)
  (`logs/cadastro-r2-verificar-consolidado.log`). A única falha foi o contrato
  preexistente do Resumo, reproduzido na base preservada e corrigido.
  O grupo completo foi reexecutado: 8 passaram.
- Confirmação final de `scripts/verificar.sh`: verde, 1 passed in 58.71s
  (`logs/cadastro-r2-verificar-confirmacao.log`). Repete todos os checks
  estáticos e seleciona o contrato corrigido com `-k`; é confirmação
  incremental, não uma segunda execução integral. Produto e capturas
  permaneceram iguais; só o teste mudou depois da execução integral.

Logs intermediários permanecem na pasta de evidências: expectativas HTTP antigas,
axe preexistente do Resumo e falhas de alvos parcialmente encobertos no editor.
Uma execução intermediária também teve timeout em `networkidle` durante reposição
HTMX sob carga concorrente; o mesmo caso passou na execução final. Nenhum timeout
foi ocultado ou transformado em sucesso.

O primeiro gate consolidado também encontrou uma expectativa antiga em
`TestSelosDasListas.test_resumo_usa_o_mesmo_vocabulario_sem_duplicar_o_prazo`:
exigia o assunto dentro do HTML da cópia já retirada pelo usuário. A mesma falha
foi reproduzida nos templates da base preservada
(`logs/cadastro-r2-contrato-resumo-baseline.log`). O teste passou a verificar o
assunto na projeção autorizada e a ausência da cópia no Resumo; continuou exigindo
vocabulário, mensagem de prazo única, pendência obrigatória e revisão dispensada.
Não houve mudança adicional no produto ou na aparência aprovada.

## Evidência visual e crítica final

Galeria `../evidencias/oficios-cadastro-inferior-r2/index.html`: 125 pares reais,
com três estados e cinco larguras. São 95 pares de seções, 15 páginas inteiras e
15 estados de dados copiáveis expandidos. Originais não editados, JavaScript
habilitado, dados/mídia fictícios LAB. Hashes em `capturas-originais.json`.
Sete comparações renderizadas da galeria complementam os originais.

Relatórios A–F cobrem os componentes modificados com axe, console e overflow,
incluindo estado pendente e editor com duas páginas. Os relatórios de componentes
não são uma afirmação de axe global em qualquer posição de rolagem. Testes do
editor verificam a página nas larguras 360/768/1440; o Resumo nas cinco larguras.
UI Lab validado nas cinco larguras. Capturas finais: nenhum erro de console ou
overflow horizontal nas 95 verificações registradas em `depois-medidas.json`.

Autocrítica aplicada: rejeitadas a conferência lateral com vazio, a divulgação
automática de cópia e a primeira grade de histórico mobile. Foram corrigidos o
rótulo cortado, a hierarquia repetitiva de trechos e a ferramenta anterior
parcialmente sob o topo. A toolbar expandida ainda ocupa área significativa em
celulares por preservar todas as ferramentas; fica recolhida inicialmente. A
experiência de edição do papel oficial continua sendo a existente, sem reescrever
o documento institucional ou trocar de editor nesta missão.

## Custo e preservação

GET da Folha: 24/25/21 consultas nos estados preenchido/justificativa/pendências,
iguais à base. Abertura: 39 requisições em ambas, sem editor antecipado. CSS gzip
34.913 → 35.417 bytes (+504); JS do itinerário 12.376 → 12.452 (+76). HTML aumentou
2.013–2.281 bytes por estado. Nenhuma dependência nova. Medianas locais com suítes
concorrentes variaram; não validam SLA nem permitem garantir latência em produção.

`fonte-validada.json` confirma Header/Identificação e Equipe/transporte preservados
em relação à base local do usuário. Sem mudança de fórmula, adicional, permissões,
snapshots, documento oficial ou dados históricos. Apenas ambientes fictícios locais.
Alterações desta rodada permanecem locais, junto dos ajustes existentes do usuário;
não foi criado commit, push, merge ou deploy nesta rodada.

Avaliação visual: candidato à revisão do usuário, com ressalva da densidade da
toolbar expandida no celular. Sem avanço para outra página ou módulo.

## Pendências classificadas e decisão

- Bloqueantes/regressões funcionais conhecidas: nenhuma após as reexecuções.
- Preexistente, corrigido: contrato de cópia do Resumo, foco da região rolável,
  problemas de lint/coleta e expectativas HTTP incompatíveis com os ajustes locais.
  Reproduções e logs anteriores foram mantidos. A confirmação incremental não é
  apresentada como um segundo gate integral.
- Não bloqueante: toolbar de formatação expandida ainda densa em 360 px; controles
  completos foram preservados e o estado inicial é recolhido.
- Dívida técnica preexistente: depreciações de HarfBuzz-Subset/WeasyPrint e
  `pypdf.PageObject.replace_contents`; os nove avisos do integral se distribuem
  entre essas dependências. Bandit também imprime avisos sobre comentários `nosec`,
  sem achado de segurança que reprove o check. Nenhuma atualização de dependência
  foi aberta nesta missão.
- Medição de latência: inconclusiva sob concorrência local; consultas, requisições
  e peso foram registrados, sem extrapolar para produção.

Decisão técnica: aprovado com ressalvas, conforme a autorização para classificar
falhas preexistentes com evidência. Decisão estética: candidato à revisão visual
do usuário. O conjunto não recebe aprovação definitiva por inferência dos testes.
Próxima ação recomendada: revisar a galeria desta metade inferior; manter o foco
no Cadastro, sem expansão para outro módulo.
