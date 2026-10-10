# Lista e Resumo de Ofícios — refinamento de consulta

Rodada de 09–10/10/2026. Fonte inicial: HEAD `722198f` com os ajustes locais
existentes do usuário. Cadastro preservado. Sem push, merge ou deploy.

**Estado: validação técnica concluída, gate integral verde e navegador verde.
Nenhuma regressão funcional conhecida nos fluxos tocados. A candidata continua
sujeita à revisão estética do usuário.**

## Problemas observados e correções

- **Motivo/Roteiro:** a grade compartilhava linhas entre Motivo e lateral. O painel
  usava altura vinculada à janela, distribuição fracionária e rolagem própria.
  Motivo agora integra a coluna principal com Roteiro e Equipe. Lateral tem altura
  de conteúdo, sem determinar o posicionamento da leitura.
- **Diárias:** variante compartilhada de consulta: total protagonista; valor por
  servidor secundário; destino e composição como metadados. Não altera valores,
  regra de cálculo, estado de ausência ou erro. Registro Institucional permanece
  separado, mas usa metadados compactos em duas colunas.
- **Roteiro:** datas alinhadas ao começo do trecho, ligação central mais curta,
  ícone derivado do meio de transporte e chegada em outro dia preservada. Não
  altera saída, chegada, duração, adicional ou ordenação.
- **Documentos:** vazio compacto explica a minuta disponível e oferece sua ação.
  Painel corrente, histórico, assinatura, geração, falha e retry continuam com as
  projeções e controles autorizados existentes.
- **Status:** situação documental conserva seu badge; condição documental recebe
  apresentação secundária; tempo até a saída é metadado discreto. O título do
  indicador temporal explicita que se refere à saída da viagem.
- **eProtocolo:** dados copiáveis restabelecidos por pedido desta rodada. Reutiliza
  componente, módulo de cópia e projeção autorizada existentes. Estado do PDF não
  é duplicado dentro do disclosure de cópia, evitando informação desatualizada
  durante polling. Fallback de seleção manual mantém acesso por teclado.
- **Scroll:** somente corpo do modal rola; cabeçalho e rodapé ficam fora do
  contêiner rolável. A scrollbar não atravessa o cabeçalho grafite. Região de
  leitura mantém nome acessível e foco; conteúdo não fica inacessível sob o rodapé.
- **Lista:** hero mais baixo; filtros temporais horizontais, separados da dimensão
  documental; disposição móvel rolável. Conteúdo e rodapé seguem o tamanho real
  do resultado. Barra de ações acompanha a rolagem somente com múltiplas páginas.
- **Geometria:** placa e ações compartilham alinhamento vertical; placa possui
  largura estável para numeração de quatro algarismos. Coluna financeira tem
  espaço suficiente para valor e composição; chips não quebram; quina do último
  registro respeita a geometria dos demais.

## Componentes e consumidores

Alterações na origem: `conferencia_valores.html` (variante `consulta`),
`dados_eprotocolo.html` (opção de não duplicar estado do PDF), componentes de
registro/mesa/percurso/estado documental em `components.css` e classes semânticas
de selos no tag library. UI Lab e documentação do Design System atualizados.

O Cadastro continua usando a apresentação padrão dos componentes. Templates do
Cadastro, itinerário e editor JavaScript são idênticos à cópia local anterior à
rodada, conforme `manifesto-fontes.json` e `custo-final.json`. Nenhuma mudança em
models, serviços, queries, pacotes, assinados, integração ou cálculo nesta missão.

## Duas passadas críticas

A primeira implementação foi revista no navegador. A segunda passada corrigiu:

1. Regra do hero da Lista que atingia o hero do Resumo aninhado: seletor agora
   restringe o filho direto da coleção, preservando a hierarquia do modal.
2. Borda da última linha herdada de uma tabela: todos os registros conservam raio.
3. Valor alto e composição financeira comprimidos: largura explícita sem recorte.
4. Placa com quatro algarismos alterando largura no mobile: dimensão constante.
5. Fixtures com aéreo/ônibus revelaram um carro fixo no bloco de transporte do
   Resumo. Esse bloco agora usa o mesmo helper semântico do percurso e da Lista.
   Ausência de transporte mantém o estado vazio existente. Cadastro não é alterado.

Equipe compacta e blocos copiáveis já bem resolvidos foram preservados. O espaço
livre abaixo de conteúdo curto não foi preenchido com dados artificiais.

## Evidência visual e medições

[Galeria antes/depois](../evidencias/oficios-resumo-lista-refinamento/index.html):
43 pares e 86 originais, sem edição dos pixels ou imagens geradas. Larguras
360, 390, 768, 1024, 1440 e 1920. Mesmos registros DEMO, lidos sem alteração.
A mudança de dia durante o trabalho explica a redução de um dia nos indicadores.

Na mesma viagem, a variação da altura da janela mostrou a causa estrutural:

- Antes: intervalo Motivo–Roteiro 22,375 / 62 / 162 px em alturas 900/1000/1200;
  painel Diárias 392,578 / 492,578 / 692,578 px.
- Depois: intervalo 22,375 px e Diárias 238,281 px nas três alturas.

Lista: 24 combinações (seis larguras × 0/1/3/20 registros), sem overflow, erros
de console ou violações axe. Diferença máxima entre centros de placa e ações:
0,0078125 px. Placas `1/2026`, `03/2026`, `165/2026`, `1250/2026` mantêm 115,1875 px.
Probe de numeração altera apenas texto no DOM para medir geometria; não compõe os
prints da galeria nem altera registros. Fixtures E2E validam numeração real.

Resumo: seis larguras da viagem de referência; mais 12 estados com duas/seis
etapas, 12 servidores/valor alto e dados incompletos em 360/768/1440. Sem violações
axe nesses estados. Casos sintéticos de motivo longo, um trecho e chegada no dia
seguinte são cobertos pelos novos testes E2E, em banco TEST isolado.

## Testes

- HTTP final: **27 passaram**, em 1.336,18 s. Projeções e scope de eProtocolo,
  snapshot corrente/histórico, disponibilidade, GET sem escrita e vocabulário.
- Tokens do Design System: **68 passaram**, em 6,51 s.
- UI Lab: quatro combinações preenchido/vazio × 360/1440, sem violações axe,
  overflow ou erros de console; fechamento por Escape validado após a animação.
- Scroll por teclado: em 360/1440, Tab alcança o corpo, Page Down aumenta seu
  scrollTop sem deslocar cabeçalho/rodapé, e Escape fecha. Medição em
  `scroll-teclado-qa.json`. O seletor do roteiro usa o nome acessível efetivo
  “Fechar o resumo”; a tentativa com nome abreviado não é evidência de falha da UI.
- Navegador consolidado: **32 passaram**, em 1.373,07 s. Versões, guards de via/pacote, assinatura,
  polling, foco/fechamento, cópia fallback, filtros lazy/HTMX, composição/paginação
  e compatibilidade visual do Cadastro.
- Conteúdo extremo: **seis reexecuções passaram**, em 264,69 s, com os maiores
  nomes de municípios do cadastro IBGE da fixture, cinco municípios diferentes,
  chegada no dia seguinte e meios aéreo/ônibus. Após a correção final do ícone,
  **quatro reexecuções passaram**, em 178,24 s, verificando o mesmo ícone no
  percurso e no bloco de transporte, em 360/1440. Dois casos fora desse recorte
  foram deselected; não são falhas nem exclusões do gate integral.
- Gate integral `scripts/verificar.sh`: **2.291 passaram**, nove avisos, em
  **3.040,91 s (50min40s)**, exit code 0 e “tudo verde”, sem seleção de testes ou
  aumento de budgets. PostgreSQL LAB localhost:55432, seis workers, bases TEST
  novas com `--create-db`. Ruff verde; 17 contratos de arquitetura preservados;
  mypy verde em 303 arquivos; Bandit sem finding; migrações e tsc verdes.
  Log integral: [resumo-lista-verificar-final.log](../evidencias/oficios-resumo-lista-refinamento/logs/resumo-lista-verificar-final.log).
  A correção final de ícone foi coberta também pelos quatro casos focados acima.

## Falhas intermediárias e classificação

- Cinco falhas da primeira rodada E2E foram reproduzidas com os templates/CSS da
  fonte inicial: três assertions buscavam ausência de histórico em todo o DOM,
  apesar do diálogo histórico fechado; duas supunham Word como primeira opção,
  apesar de Histórico preceder essa ação. Contratos foram corrigidos para testar
  painel corrente, invisibilidade do histórico e primeira opção operável. Guardas,
  disponibilidade de Word, foco, links e polling continuam verificados.
- Expectativas antigas de ausência do bloco copiável conflitam com o pedido
  atual, que exige eProtocolo no Resumo. Foram atualizadas preservando os guards
  de unidade, snapshot e dados indisponíveis. Uma execução já coletada foi
  interrompida e substituída pela rodada integral de fontes estáveis.
- Reutilizar um TEST DB de execução interrompida causou unicidade em fixtures.
  Classificação: preparação de ambiente, sem relação com a apresentação. A rodada
  final cria bancos TEST novos. Não houve limpeza ou semeadura do banco DEMO.
- Tentativa inicial de baseline Python incompleto não continha o CSV de municípios;
  foi descartada. A prova válida de baseline usa somente seus templates/CSS, com
  o código de negócio atual, que esta missão não altera.
- Um node E2E foi informado com nome inexistente; não executou testes. A rodada
  consolidada usa o nome correto. Logs de preparação não contam como aprovação.

## Desempenho

`components.css`: 185.077 → 187.501 bytes; gzip 35.636 → 35.661 (**+25 bytes**).
`listas.css`, `app.js`, itinerário e editor JS preservados. Lista: HTML
132.498 → 132.569 bytes, 23 requisições em ambas as fontes. Resumo: HTML
154.981 → 161.482 bytes, 23 → 24 requisições ao reutilizar `copiar.js` solicitado.
Editor não é carregado antecipadamente. Não há biblioteca nova.

Latências observadas sob concorrência do gate não sustentam afirmação de ganho ou
regressão de tempo. Budgets de consultas continuam nos testes existentes, inclusive
20/200 registros. Nenhum budget foi relaxado.

## Pendências e registro

Não há teste obrigatório pendente nem falha bloqueante conhecida nesta rodada.
Revisão estética pelo usuário permanece pendente; não equivale à revisão técnica local.
Nenhum commit novo nesta rodada; o index previamente preparado pelo usuário foi
preservado byte a byte. Manifesto compara fontes com a cópia local inicial,
distinguindo esta missão das alterações anteriores ainda não commitadas.

O navegador registra um aviso de depreciação da dependência WeasyPrint sobre
HarfBuzz-Subset para versões futuras. Classificação: aviso da infraestrutura
existente, não bloqueante; nenhuma dependência foi alterada nesta missão.
O integral registra seis ocorrências desse aviso e três de depreciação do pypdf
em testes existentes de carimbo. Bandit registra avisos de interpretação de
comentários `nosec`, sem finding. São manutenção preexistente, fora do redesenho;
os testes associados passaram e seus arquivos não foram alterados nesta rodada.

Capturas auxiliares aguardam as animações e a visibilidade efetiva dos campos.
As verificações imediatas antes do término da animação não são usadas como
diagnóstico de regressão; os testes operáveis utilizam espera pelo estado final.
