# Planos de Trabalho — refinamento de 15/10/2026

## Observar e entender

Capturas de Lista/Novo/Folha de Planos e comparação com Ofícios, Roteiros, Termos
e OS, nas larguras 360/1440: `../evidencias/planos-refino-20261015/antes/`.
O endereço inicial `/viagens/oficios/1/` retornou 404 e não vale como referência:
captura corrigida usando o link real da lista, `/viagens/oficios/267/editar/`,
Ofício 167/2026, HTTP 200 em 360/1440. Provas em `referencias/` e `referencias.log`.
Contratos em `product/planos-refinamento.md`, `product/propagacao-identidade.md`,
ficha de migração e código atual. Arquétipos FORM/LIST e componentes canônicos
foram inspecionados antes da alteração. Nenhum acesso à produção ou reset DEMO.

## Projetar e implementar

ADR 0038. Seções Identificação, Efetivo e diárias, Atividades, Outros eventos e
Documento; índice compacto por âncoras. Coordenações paralelas no desktop e
empilhadas no celular, cargo como ajuda legível. Atividades em linhas com nome
integral, meta visível e `aria-labelledby`/`aria-describedby` distintos; modal de
conjuntos conserva opções compactas. Outros eventos saem do bloco Documento.
Coordenação administrativa acrescentada à lista usando `select_related` existente.
Barra móvel passa a reunir ações em uma linha e estado de salvamento em outra.

CSS exclusivo `planos.css`, carregado após os estilos-base; nenhuma regra de
domínio, consulta remota, migração ou folha oficial introduzida. IDs, campos,
regiões vivas, formulários externos, efetivo por evento, autosave e versão mantidos.
Anotação de tipos pontual em `_transporte` de Termos necessária para liberar mypy;
sem mudança de comportamento. Alterações simultâneas nos compartilhados preservadas.

## Testar

- 452 testes aprovados em 551,05 s: Planos, tokens e comentários de template.
  Log `unitarios.log`; aviso preexistente HarfBuzz no Windows.
- Reteste de tokens/templates no Linux: 404 aprovados em 15,60 s, com Ruff verde.
- `validado-manifesto.json`: 14 combinações (7 telas × 2 larguras), HTTP 200,
  nenhum overflow ou erro JS. Axe sem violações nos componentes de Lista, Novo,
  Folha e diálogo de evento. Resultados e cancelado inspecionados visualmente.
- Navegador: 17 aprovados, em três execuções complementares (9 + 7 + 1). Incluem
  criação a partir do Ofício, autosave, calendário, conjuntos, origem/tratamento,
  busca/ordenação/menu/permissões, multievento/422/PDF/remoção e resultados
  zero/milhar/limpeza/validação sem gravação parcial/consulta de cancelados.
  Logs `navegador.log` e `navegador-complementar.log`.
- Cadastro rápido: módulo compartilhado estava ausente na preparação de Planos,
  embora os diálogos já existissem. Carregamento restaurado como em Ofícios/Termos/OS.
  Fluxo real de criar conjunto via JSON, fechar o diálogo, conservar URL/seleção do
  plano e acrescentar a opção passou; `cadastro-rapido.log`, 1 teste em 89,44 s.
- `componentes-final.log`: coordenação manual e diálogo compacto de conjunto
  exercitados em 360/1440, sem overflow e com todos os POSTs interceptados;
  nenhuma gravação DEMO. Capturas complementares em `final/<largura>/`.
- Teste antigo do evento preenchia `#evento-periodo`, agora oculto pelo calendário
  compartilhado. Atualizado para escolher a data pelo teclado e pelas células reais;
  a repetição do fluxo completo passou. Comparação literal de HTML de conjunto
  padrão também exigia `checked` imediatamente após `id`; essa ordem foi preservada
  com os novos atributos de acessibilidade. Nenhuma assertiva foi removida.
- `final-manifesto.json`: capturas finais repetidas após compactar a barra móvel,
  novamente sem overflow/erros JS/violações de axe nos componentes exercitados.
- Gate integral em andamento; registrar resultado terminal antes de considerar
  a validação técnica concluída. Ruff, fronteiras, mypy, Bandit, migrações e tipos
  JavaScript já passaram no candidato isolado.

Ambiente de teste próprio: PostgreSQL 16 descartável `pcpr-testdb-planos-20261015`,
porta local 55438; nenhuma permissão ampliada no PostgreSQL da aplicação. Fsync,
synchronous_commit e full_page_writes desativados só nesse contêiner descartável
para acelerar fixtures. Não utilizar a duração desses testes como medida do produto.
Verificação Linux em cópia local do candidato, sem alterar a aplicação em execução.

## Comparar, criticar e corrigir

Capturas inteiras iniciais não carregavam os iframes adiantadamente; não foram usadas
como evidência de documento ausente. Script final rola até a minuta antes de capturar,
inclui recortes legíveis por seção e topo/rodapé do modal. Corrigidos alinhamento dos
coordenadores, nome/cargo sobrepostos e especificidade de `[hidden]` na busca de
atividades. Nomes acessíveis preservados quando a meta passou a ficar visível.
Metas detalhadas limitadas à preparação/evento para preservar o diálogo de conjuntos.

Na revisão final, a ajuda com cargo inicialmente renderizada no servidor ficava
desatualizada ao trocar o coordenador. A meta foi movida para dentro do combobox,
abaixo da entrada, mantendo sua sincronização nativa e a descrição acessível.
Ao limpar, a orientação de busca volta a aparecer, sem nome/cargo sobrepostos.

Primeira execução integral encerrada para inspecionar três falhas: 870 aprovados,
3 falhos em 2.137,76 s. As três eram o mesmo teste de Ofícios, parametrizado por
perfil, procurando o protocolo no cabeçalho antigo. O template já usa sub-header;
a correção desse teste já estava no repositório (trabalho concorrente) e foi copiada
para o candidato, sem alterar a implementação de Ofícios. Nova execução integral
em `verificar-consolidado.log`, com oito workers e banco exclusivo desta rodada.

O servidor compartilhado na porta 8000 apresentou `ERR_EMPTY_RESPONSE` intermitente.
Preview local adicional na porta 8015 usa o mesmo banco/mídia DEMO, sem semeadura,
para capturar o candidato de forma estável. Não atribuir esse erro à tela de Planos.

O middleware ainda registra 35–43 consultas em preparações com evento, dívida já
registrada no QA de 12/10. Nenhum budget foi aumentado. A coordenação da Lista
consome os relacionamentos que `planos.com_dados` já carrega.

## Validar

Capturas finais em `../evidencias/planos-refino-20261015/final/` e manifesto correspondente.
Paridade atualizada em `docs/parity/planos.md`. Aprovação visual do usuário pendente;
resultados terminais dos testes complementares ainda precisam ser consolidados.
