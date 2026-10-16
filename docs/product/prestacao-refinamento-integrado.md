# Prestação de contas — recomposição integrada, 15/10/2026

## Pedido e fontes

Refazer lista, resumo e preenchimento reaproveitando os componentes existentes,
sem criar outro sistema visual. Contratos funcionais: `prestacao.md` em migration,
`propagacao-identidade.md` §§ Prestação/PR02/PR03/PR04 e serviços atuais.
Não existe cadastro manual de prestação: a emissão do Ofício origina a equipe.
O cadastro solicitado corresponde aos campos da solicitação, Diário, Relatório e anexos.

## Observação e entendimento

Capturas anteriores em `docs/visual-agents/evidencias/prestacao-refino-20261015/antes/`
nas larguras 360/1440. A lista abre dezenas de inputs em linhas pouco diferenciadas;
identificação e ações competem no cabeçalho. As três folhas não oferecem navegação
direta entre si; o RT apresenta cinco textos igualmente largos; a posição do carimbo
ocupa o início de Documentos antes dos anexos. Há uma ocorrência axe anterior na
lista desktop, registrada no manifesto, a investigar na comparação final.

## Projeto

- LIST existente, filtros e paginação preservados. Equipes em `cartao`; identificação
  em `registro`, resumo do próprio Ofício no diálogo canônico já existente.
- Solicitação por pessoa em cartões existentes: avatar/nome, estados, campos em
  grade responsiva e pendências em `divulgacao`. Sem esconder campos ou ações.
- Diário, Relatório e Documentos conectados por `abas`, com indicação da página
  atual e volta à equipe. Sem nova rota nem componente CSS/JS.
- Diário prioriza o preenchimento dos trechos; troca de motorista/viatura e ajustes
  excepcionais ficam depois, ainda abertos e acessíveis.
- RT agrupa os quatro primeiros textos em pares e encerra com informações
  complementares; ferramentas de texto continuam junto dos campos. Custeio e valores em
  blocos de formulário existentes.
- Documentos separa documentos da equipe, anexos individuais e versões; carimbo
  em divulgação existente, sem competir com upload e consulta dos arquivos.
- Rodapés mantêm o padrão comum: Finalizar aguarda o salvamento e volta à lista,
  sem finalizar a prestação. Consulta conserva navegação e downloads, sem edição.

## Invariantes e validação

Não alterar regras, cálculos, documentos oficiais, bancos ou mídia. Preservar
todos os nomes, IDs de autosave, regiões `data-vivo`, CSRF, trava, limites,
voltar, ações de equipe, busca multiaba, exportação e atualização HTMX.
GET da lista não cria RT/Diário. Captura das folhas usa equipe 211 já existente;
POST bloqueado. Edição, anexação e finalização somente em banco de testes isolado.
Testes funcionais + navegador + axe e capturas 360/1440, com evidência em docs.

## Remoção da apresentação antiga

## Diário de bordo — revisão integral em 16/10/2026

Pedido: reconstruir a apresentação, preservando o editor de documento aprovado.
Evidência inicial: `../visual-agents/evidencias/diario-20261016/antes-{360,1440}.png`.
A tabela de sete colunas dificulta a leitura no celular; recursos ocupam linhas
inteiras; horários têm cabeçalho duplicado e um fragmento de HTML exposto.

A folha DOCUMENT passa a compor cartões existentes: identificação compartilhada
da equipe; resumo de motorista/viatura em duas colunas; trechos com rota, agenda,
campos rotulados e distância rodada; horários excepcionais em divulgação.
Reutilizar `diario-linha`, `campo`, `grade`, `pessoa`, `divulgacao` e `secao`.
Não criar componentes nem mudar o editor, o PDF, os cálculos ou os endpoints.
Manter IDs, nomes, autosave, foco, consulta, trava e continuidade por servidor.
As sugestões de distância só preenchem campos vazios e permanecem estimativas.
Validar edição em banco sintético isolado, acessibilidade e capturas 360/1440.

## Histórico da recomposição anterior

### Revisão solicitada: base literal no cadastro do Ofício (16/10/2026)

A composição em cartões acima foi rejeitada pelo usuário. Substituí-la pela
composição de `oficios/editar.html`: hero, documento contínuo de preparação,
seções numeradas com cabeçalho e conteúdo, campos de recursos e barra fixa.
Motorista/transporte ficam diretamente editáveis; roteiro agrupa hodômetro e
ajuste de horários; documento mantém integralmente o editor aprovado. Remover
o índice de etapas e os cartões de resumo duplicados. Não criar campos do Ofício
que não pertencem ao diário. Manter todos os contratos e estados anteriores.
Referência visual: cadastro existente 266, consultado sem salvar alterações.


Busca de consumidores encontrou as classes `prestacao-equipe`/`prestacao-servidor`
somente na lista, em Anexos e no catálogo UI Lab. Os três foram recompostos com
cartão/registro/metadados/grade; retirado o bloco específico de 235 linhas
de `listas.css`. Não houve exclusão de dados, arquivos anexados ou regras.
