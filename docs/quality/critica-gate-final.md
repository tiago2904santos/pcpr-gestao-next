# Crítica do candidato antes do gate final

07/10/2026. Leitura independente no worktree `viagens-tempo-legado`, HEAD
observado `e5e48cc`. Escopo: mesmas correções RS-02, separação de CSS e carga/foco
de Baixar/cadastros. Nenhuma edição de produto/testes, banco ou navegador nesta
rodada; somente este documento. Não há aprovação de entrega antecipada.

## Quatro achados RS-02: correções presentes, execução real ainda necessária

- **Minuta indevida:** `_menu_oficio.html:31` agora usa `elif m.minuta`. O ramo
  de ausência de PDF já não habilita minuta de emitido/cancelado. Os quatro
  casos de HTML real em `test_leitura_documental.py` cobrem estados indisponíveis
  e preservação do rascunho; sua leitura não comprova que passaram.
- **Via inválida no download:** `views.py:1034` filtra dono e tipo, depois exige
  caminho não vazio e `assinados.pode_abrir`. Via vazia/branca ou de outro dono/
  tipo deixa de substituir o original. A versão histórica continua endereçada
  pelo ID pedido, sem exigir que seja corrente. Original sem caminho/arquivo
  inexistente recebe 404. Os testes novos com arquivos sintéticos verificam
  bytes e hash, além da seleção; precisam do resultado HTTP real.
- **Foco em menu oculto:** `dialogo.js` guarda o ID do gatilho e confere hidden,
  geometria e visibility antes de focar o item novo. Quando o painel está
  fechado, devolve ao gatilho. O E2E acrescentado usa worker/GET HTMX reais e
  cobre item com ID e sem ID, reabertura do menu e Escape. Concluir pelo código
  que a condição foi corrigida não substitui esses dois casos de navegador.
- **Justificativa esperada ausente:** `pacotes.py` conserva Item indisponível
  quando o snapshot da maior emissão indica texto presente. Seus geradores PDF/
  DOCX levantam `PacoteInvalido`; não voltam à minuta nem promovem versão antiga.
  Os dois testes novos de pacote verificam item e erro. Checkbox desabilitado
  não é contrato atual: os itens são marcados ao abrir; pedir o indisponível
  aborta o lote e orienta pela view existente, comportamento já autorizado.

Não demonstrei bloqueante adicional de produto nessa releitura. Os achados
originais estão em `critica-rs02.md`, com as reproduções anteriores preservadas.
Isso não declara resolvidas falhas futuras da execução real.

## CSS: equivalência demonstrada, custo de recurso separado

Executei comparação somente de fontes com `minificar_css` canônico:
`git show d5663f2:static/css/formulario.css` versus concatenação ordenada de
`seletores.css` + `formulario.css`. **Iguais: 25.714 bytes**;
SHA-256 `cd9b0dc76025d16ce710d593bf68b4c8254618e637c82a4641bb855e7e6a3214`.
Busca em templates confirmou **44 consumidores** do include canônico, nenhum
link direto remanescente para formulário fora do componente, e nenhum `@import`
nos dois arquivos. O componente usa `static`, seletores antes de formulário.

Formulários ganham **um pedido CSS real**, custo atual deste candidato. Lista
troca o pacote completo pelo de seletores e desativa apenas seu próprio preload;
outras listas conservam o padrão. Equivalência de regras não prova igualdade
visual em todos os consumidores, gzip ou atendimento de budgets. Excesso do
candidato só pode ser classificado com medição atual e baseline equivalente;
os valores anteriores não são evidência de aprovação nem autorização para
aumentar teto. Esse custo precisa aparecer no checkpoint do principal.

## Carga e foco: condições relidas e evidência ainda pendente

Baixar tem um único dispatcher de abertura no app, sem import por presença da
casca e sem redispatch de clique. A trava cobre import, não impede reabrir após
fechar; GET usa geração e AbortController. Resposta antiga/fechada não desenha
itens, não redireciona nem muda foco; POST/download permanece no módulo. Falha
de import orienta recarregar em português e não é tratada como sucesso.

Os três testes de corrida agora aguardam sinal DOM posterior a fulfill/dispose;
erros do handler são relançados no mesmo teste. Somente cancelamento identificado
como `net::ERR_ABORTED` com página aberta admite recusa de fulfill. Não encontrei
`ignoreErrors` ou limpeza de console nesses testes. A primeira rodada teve
6 passados, mas 2 falhas novas e 3 erros de setup contaminados por callbacks;
os checks em memória do helper não provam correção desse agendamento real.

Cadastro conserva a casca do diálogo ao receber o formulário canônico, valida
todo o pacote antes da troca, deduplica GET por URL e liga o form uma vez.
Após resposta, só muda foco se o diálogo que continha o foco continua aberto.
Falha libera cache para retry e orienta fechar/reabrir. A guarda explícita de
details fechado no app preserva summary e o padrão fora do opt-in; não vi nova
dependência de geometria sozinha para gaveta fechada.

## Condição de fechamento

A reexecução focused de Baixar, os contratos Baixar/Assinados, os sete casos de
Resumo, guards HTTP, incorporação e `verificar` integral pertencem à sequência
do principal e ainda não foram recebidos como verdes nesta crítica. Falha ou
erro dessas rodadas permanece bloqueante de validação até ser explicado/
corrigido ou comprovadamente reproduzido no baseline, sem mascarar console ou
alterar budgets. Capturas e medição atual precisam ser vinculadas ao checkpoint
final; este documento não aprova estética, acessibilidade geral, desempenho ou
paridade por inspeção de código.

## Encaminhamento pelo principal — evidência posterior

A equivalência CSS acima não bastou: comparação 360/1440 revelou divulgação
eProtocolo sem seu estilo no consumidor Resumo. Separação CSS rejeitada e 44
links/formulario.css restaurados; não entra no commit. Só opt-in JS permanece.
As quatro correções RS02 e as corridas Baixar foram executadas em HTTP/E2E reais;
resultados/logs/capturas em `fechamento-gate-2026-10-07.md` e no pacote final.
Esta atualização é do principal, não uma nova aprovação independente do revisor.
Integral final ainda em execução; crítica original fica preservada como história.
