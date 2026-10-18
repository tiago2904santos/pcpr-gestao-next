# Dados da unidade — contrato da reorganização

Data: 17/10/2026. Fonte: missão do usuário; comportamento existente em
`docs/product/propagacao-identidade.md` (CD05), `permissions.md`, `workflows.md`
e `docs/migration/cadastros.md`. A referência funcional já está documentada;
esta rodada não representa nova consulta ao legado em execução.

- Entrada única no menu da conta, imediatamente depois de Alterar senha,
  nomeada Dados da unidade e condicionada à política de consulta existente.
- A rota `/cadastros/configuracao/` permanece compatível. A página apresenta
  unidade, sigla e nome mestre, distinguindo cadastro institucional e valores
  locais usados nos próximos documentos. Os links contextuais continuam válidos.
- Gestor pode alterar unidades autorizadas; operador consulta a própria unidade;
  demais perfis conservam suas permissões. Unidade explicitamente solicitada
  deve ser autorizada inclusive por GET/POST direto. Identificadores divergentes
  entre formulário e URL são rejeitados para evitar salvar em contexto incorreto.
- ConfiguracaoInstitucional permanece complemento local 1:1 de Unidade.
  Nome de cabeçalho, endereço, contatos, chefia, destinatário e padrões de plano
  não serão fundidos com sigla/nome do cadastro mestre nem configurações contratuais
  de Coffee Break, cujo destinatário e responsabilidade são diferentes.
- Assinantes usam Servidor canônico e cargo atual por tipo documental;
  substituições conservam datas, tipo e situação. Não se cria conta nem permissão
  ao escolher assinante. Ativos são oferecidos para novo uso e um titular inativo
  já escolhido permanece identificado na edição. Documentos emitidos preservam
  seus instantâneos e PDFs; alterações só afetam próximas montagens.
- Usar arquétipo de folha de preparação e componentes existentes, campos amplos,
  validações junto dos quatro seletores e diálogo confortável de substituição.

## Busca de assinantes em volume

Os quatro titulares/padrões e o substituto usam escolha remota do Design System,
com no máximo 15 resultados por busca. A renderização contém apenas o valor atual;
um selecionado fora da primeira página e um titular atual inativo continuam legíveis.
O formulário valida a FK contra o mesmo catálogo permitido no backend. A escolha
não exige permissão geral de manutenção de Servidor: endpoint específico exige
consulta à configuração e unidade autorizada. Como no comportamento anterior,
este catálogo de servidores é institucional/global; a unidade na URL é o contexto
administrado e não amplia suas permissões. CPF aparece apenas pelos quatro últimos
dígitos para identificação. Sem JavaScript o vínculo existente continua enviado;
a busca por outro registro requer JavaScript, padrão já usado em multiescolha.
