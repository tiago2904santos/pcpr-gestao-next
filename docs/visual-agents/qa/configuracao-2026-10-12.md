# CD05 — Configuração da unidade

Base cdb09d7. Contrato em product/propagacao-identidade.md e migration/cadastros.md.
Antes18 capturas integrais/seções/diálogo3607681440. DEMO somente GET/HEAD.
Campos, unidades, assinantes, período e documentos preservados. Formulários de
substituição e alternância continuam fora do formulário principal.

Cabeçalho canônico, filtro de unidade no fluxo e folha de preparação com três
seções substituem cartões soltos. Campo Bairro/Cidade ampliado; destinatário e
prazo seguem grade de conteúdo/período; datas da substituição com grade--2.
Barra de salvar no fluxo elimina sobreposição e distância artificial das
substituições. Sem regras ou consultas novas; carregamento da Guia ajustado para consumidores reais. Acrescentado documento.css para
as seções canônicas; registrar custo real por recurso antes do fechamento.

Capturas finais18 concluídas, sem overflow/erro JS. Primeira automação de Escape
esperava fechar diálogo enquanto a busca estava aberta; corrigida para dois níveis
de Escape, sem alterar o produto. Enter e retorno de foco confirmados.
18759 ativa: configuração integrada; revisão independente solicitada.

Remoção candidata: .escolha-unidade e .escolha-unidade .campo em formulario.css.
Único consumidor template configuração migrou para filtros/campo; ID escolha-unidade
permanece label/select, não é classe. Sem uso JS, includes dinâmicos ou documentos.
Remover somente após testes iniciais e repetir testes sem essas regras.

## Fechamento do candidato

83 testes pós-limpeza aprovados em125,80s; tipos aprovados. E2E cobre salvar, erro,
substituição/encerrar/reativar, consulta, configuração ausente e usuário sem unidade
em360/768/1440, com axe e teclado. Falhas anteriores foram da automação (dropdown
aberto e consulta por username inexistente); logs preservados.

Removidas as duas regras escolha-unidade. Revisão independente confirmou único
consumidor migrado, sem referências dinâmicas/documentais. Guia mantém folhas
numeradas e documento--cartoes; Configuração deixa de carregar JS sem utilidade.
Smoke real GET/HEAD confirmou Ofício259, Roteiro e Coffee com Guia. Tentativas
iniciais usavam rota de criação e ofício arquivado, que redirecionam à lista;
repetido com o registro259 efetivamente editável.

Documento.css canônico acrescentado (21.376 bytes transferidos na captura),
sem ganho de latência alegado. Capturas finais sem overflow/console; revisão
independente favorável. Aprovação visual do usuário e gate global pendentes.
