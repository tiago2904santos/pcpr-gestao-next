# Reorganização dos cadastros — relatório de execução

Data: 17/10/2026. Situação: concluída e validada em LAB isolado.

## Cobertura e organização

Foram inventariadas **35 entidades cadastrais iniciais**, **32 superfícies principais
de manutenção**, **2 catálogos fixos de sistema** e **13 famílias de consumidores**.
São denominadores diferentes, detalhados em [inventario.md](inventario.md) e
[inventario.json](inventario.json). A unificação reduz dois catálogos operacionais a
uma identidade comum; a origem antiga permanece como mapa, sem manutenção paralela.

As 35 entidades foram revisadas: 34 receberam mudanças diretas ou na manutenção
incorporada; Municípios conserva a fonte oficial e sua identidade IBGE. As 32
superfícies principais foram revisadas em 360/1440. Criação, edição, erros, cancelamento,
teclado, ativos/inativos, leitura e uso compartilhado são verificados nos testes dos
lotes e consumidores. As 35 entidades têm situação final, ações e evidências no
inventário; as 32 superfícies e os 18 modais comparados foram validados em 360/1440.
Uma captura de lista não substitui a verificação funcional do formulário.

## Catálogo e dados preservados

`AtividadePlano` é canônico; `eventos.Servico` é proxy contextual, com as permissões
anteriores. A carga versionada passou de 11 atividades + 5 serviços para 15 itens e
5 mapas de origem. Apenas a equivalência CIN comprovada pela carga foi mesclada;
homônimos e inativos foram preservados com identidade própria. FKs, sugestões,
observações e nomes históricos foram migrados em LAB. Documentos emitidos e seus
arquivos não são regravados. [Mapa e contratos](catalogo.md).

Servidor, conta, cargo, lotação e assinatura permanecem conceitos distintos. Equipes
editoriais/veículos de imprensa, unidades móveis e viaturas não foram fundidos por
semelhança de rótulo. A configuração financeira do Coffee é um contexto próprio,
sem unidade/servidor comprovados; seus textos não substituem a configuração institucional.

## Dados da unidade

A entrada fica imediatamente abaixo de Alterar senha, com unidade em administração
explícita. A rota antiga funciona. Titulares por tipo, coordenador e substituições
mantêm vínculos e permissões; a busca contextual devolve no máximo 15 pessoas e mantém
o titular atual, inclusive inativo. O modo de consulta desabilita também a busca
gerada pelo componente. Selecionar um assinante não cria conta nem concede aprovação
ou assinatura digital. [Validação específica](unidade.md).

## Conforto e desempenho

Cabeçalhos e tokens seguem Viagens; modais têm largura proporcional, nomes/cargos em
linha própria, corpo rolável e ações acessíveis. Seletores/calendários usam a camada
flutuante existente. Cadastro rápido preserva o formulário e devolve o foco; erros
de rede/validação não anunciam sucesso indevido. Edição incorporada conserva ícone e
ações junto à identificação do registro.

Os sete cadastros ASCOM receberam busca, paginação e preservação dos filtros. A
edição de palestrante deixa de construir um formulário completo para cada linha;
contagens de uso são feitas no banco por página, sem percorrer todo o histórico.
Palestrantes passou de 42 para 11 consultas e de 387.782 para 62.699 bytes de HTML
no cenário sintético com 31 palestrantes/120 servidores (83,8% menos HTML).
Medições comparáveis e limites estão em
[ascom-validacao.md](ascom-validacao.md). Não se atribui ganho de latência a medições
com caches diferentes. Seletores de assinantes, palestrante e motorista de Eventos
usam busca autorizada limitada a 15 e preservam o vínculo atual. A seleção de
assinantes passou de 402 para 2 opções no HTML
inicial do cenário de volume. [Revisão independente](revisao-final.md).

## Preparação da fonte dedicada

`cadastros/fontes.py` é a porta do espelho local para servidor, viatura, unidade,
cargo e atividade/serviço. `VinculoFonteCadastro` associa identidade externa à PK
interna e declara campos da origem. Atualizações validam payload, formatos,
permissões e responsabilidades, usando transação e comparação base/local/recebido.
Conflitos são explícitos; complementos documentais, relações e configurações locais
não são sobrescritos. [Contrato detalhado e testes](catalogo.md#fonte-dedicada-preparada).

Permanecem dependentes da futura base: transporte/autenticação, formato e ordem das
revisões, mapeamento inicial real, responsabilidades definitivas e eventual escrita
na origem. Nenhuma conexão remota ou infraestrutura de sincronização foi implantada.

## Ambiente, evidências e resultados

Git inicial limpo. A base DEV existente tinha 15 migrações anteriores pendentes e
foi preservada. Toda escrita de dados de validação ocorreu em PostgreSQL LAB
separado: inicialmente em `127.0.0.1:55432`, depois em `55433` fora da pasta
sincronizada e, no aceite integral, em PostgreSQL 16 numa rede Docker interna,
sem portas publicadas. Foram usados bancos descartáveis e dados sintéticos. As migrações
foram preparadas no código e aplicadas nos testes; não houve deploy nem migração da
base operacional. O cluster LAB foi configurado para testes descartáveis, não para
medição de durabilidade ou desempenho de produção.

O aceite usa uma cópia isolada de todos os arquivos versionados atuais e dos novos
arquivos da missão. Foram preservados e omitidos da cópia apenas arquivos não
versionados de outras tarefas (`docs/automacao`, `docs/ops/mudanca-hospedagem`) e
caches locais em `%SystemDrive%`. O script não foi alterado nem recebeu filtros
adicionais. [Ambiente e comandos](ambiente-linux.md),
[manifesto dos 8.461 arquivos](snapshot-linux.json),
[conferência da cópia Linux](verificacao-copia-linux.json) e
[conferência do código no workspace](verificacao-snapshot.json) registram a
rastreabilidade. Os 1.374 arquivos de código/recursos conferidos permanecem iguais;
os relatórios de resultados foram atualizados após a execução.

Os clusters Windows das portas 55432/55433 estão parados. Os três containers e a
rede Docker criados pela missão foram removidos; a imagem de validação foi
preservada para reprodução. A limpeza opcional da pasta do primeiro LAB Windows
foi bloqueada por política da revisão automática; a pasta ficou preservada,
conforme [registro do ambiente](reproduzir.md).

- [Ciclo e decisões](ciclo.md), ADR 0044 e ADR 0045.
- [Verificador integrado final](verificar.log): **2.816 aprovados**, cinco avisos,
  saída zero e `✔ tudo verde`. Ruff, 16 contratos de arquitetura, mypy em 325
  arquivos, Bandit, migrações e tipos JS passaram. A suíte inclui conversão DOCX e
  OCR reais; não houve filtros adicionais ou skips.
- [Rodada Windows preservada](verificar-windows.log): 2.813 aprovados e três falhas
  por `libreoffice`/`tesseract` indisponíveis. Os três casos passaram no aceite
  Linux completo. Tentativas de preparação do Docker também estão preservadas
  e explicadas no registro do ambiente; não foram contabilizadas como aprovação.
- [Fluxos iniciais de cadastro](ui-fluxos.log): 13 aprovados.
- [Capturas finais de todas as superfícies](capturas-finais.log): 2 aprovados,
  32 listas e 18 modais por largura, sem excesso horizontal ou erro JS; os modais
  passaram no axe. As capturas finais usam os componentes e seletores atuais.
- [Consumidores, rodada ampla](consumidores-e2e.log): 69 aprovados; falhas de interação
  do teste e lentidão/teardown foram resolvidas nas reexecuções consolidadas e dirigidas.
- [Interface consolidada](ui-consolidado.log): 34 aprovados e quatro falhas iniciais;
  os quatro casos passaram em [reexecução](ui-encerramento.log). A rodada cobre 38
  cenários, com os ajustes posteriores de cabeçalho, efetivo e certidões novamente
  verificados nos logs finais específicos abaixo.
- [Identificadores adulterados](identificadores.log): 10 aprovados.
- [Correções e reexecução de consumidores](ui-encerramento.log): 4 aprovados,
  incluindo identidade comum nas duas larguras, calendário do Termo e axe do Plano
  móvel após separar Cargo do botão de remover.
- [Catálogo e cabeçalho finais](catalogo-ui-final.log): 2 aprovados em 360/1440,
  com verificação de que fechar não cobre o texto do cabeçalho.
- [Certidões finais](certidoes-validacao-final.log): 6 aprovados, sendo 4 de backend
  e 2 de navegador; erro no modal, validade preservada, calendário dentro da área
  visível, teclado e cancelamento. A geometria foi medida após estabilizar
  controles, fontes e dois quadros de layout.
- [ASCOM final](ascom-validacao.md): 43 testes dirigidos e sete fluxos em cada
  largura; 42 capturas, sem violações de axe ou erros JS nos cenários finais.
- [Motorista e contagens](catalogo.md#fechamento-p03):
  cinco testes dirigidos aprovados, busca contextual e contagens sem N+1.
- [Índice visual](evidencias.md) e [reprodução em LAB](reproduzir.md).
- [Paridade atualizada](../../parity/cadastros-compartilhados.md).

Os logs preservam tentativas e correções. As rodadas têm cenários sobrepostos e não
são somadas como um total de testes distintos. O denominador da cobertura permanece
35 entidades/32 superfícies/13 famílias, com ações e evidências por item no inventário.
Não resta pendência executável do inventário desta missão. A conexão real com a
fonte dedicada depende dos contratos descritos acima. Na estação Windows, DOCX/OCR
real ainda exige disponibilizar os conversores no PATH; o aceite desses fluxos foi
feito no LAB Linux. Os cinco avisos finais são de depreciação do pypdf e ordenação
de paginação em fluxos de Viagens não alterados aqui, também observados na rodada
Windows. A base operacional não foi migrada e não houve deploy.
