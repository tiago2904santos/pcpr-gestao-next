# Prestação — recomposição com componentes existentes, 15/10/2026

## Observar e entender

Pedido: substituir toda a apresentação, sem criar componentes ou um visual paralelo.
Contrato prévio em `docs/product/prestacao-refinamento-integrado.md`; ADR 0040.
Fontes funcionais: migration/prestacao e contratos PR01–PR04 em
product/propagacao-identidade. Não há cadastro manual de prestação.

Baseline real, HTTP 200, POST bloqueado: pasta de evidências
`docs/visual-agents/evidencias/prestacao-refino-20261015/antes/`.
14 combinações de tela/largura. Encontrada uma ocorrência axe `target-size` no
calendário da lista em 1440; nenhuma nas outras 13 combinações.

## Projetar e implementar

Sem classes CSS, controladores JS, modelos ou rotas novos. Cartão, registro,
avatar, metadados, grade, abas e divulgação são os mesmos existentes.
Lista mantém edição imediata por pessoa em duas colunas desktop/uma móvel.
O título da equipe abre o resumo real do Ofício, com o diálogo compartilhado;
sem JS, segue para sua folha. Diário começa nos quilômetros, com troca de
recursos e ajustes de horários preservados. RT organiza os quatro primeiros
textos em pares e o complemento por último. Documentos separa comprovantes e RT
em blocos por pessoa e recolhe apenas a configuração excepcional do carimbo.
As três folhas têm navegação direta, identidade da equipe e retorno filtrado.

Foram retiradas 235 linhas de apresentação específica de `listas.css` depois de
migrar todos os consumidores, incluindo o exemplo §14 do UI Lab. Busca de
consumidores em gestao/templates/static não encontra as duas famílias antigas.
Não houve exclusão de registros, anexos, arquivos oficiais ou regras.

## Testar

Banco exclusivo descartável no PostgreSQL local, nunca o banco DEMO:
`pcpr_prestacao_refino`, candidatos no container QA em `/verificacao` e, para
fechamento, `/prestacao-final`. Primeira rodada funcional: **66 aprovados** em
204,76 s. Cobre solicitação, prazos, finalização, equipe, permissão, Diário,
realizado, RT, anexos, carimbo e pacote. Três avisos de depreciação do pypdf
já existentes; nenhum template oficial de documento alterado.

Suite de navegador: **26 aprovados**, 1236,12 s, saída 0. Fluxos de solicitação,
Enter sem finalizar, envio de pessoa/equipe, filtros/exportação, consulta, calendário,
resumo e foco, navegação entre folhas, autosave, diário realizado, textos prontos,
valores individuais, anexação/correção/remoção/restauração e carimbo sem alterar
a via original. Log em `logs/browser.log`, capturas isoladas em `browser-isolado/`.
Um aviso de encerramento: pytest não conseguiu descartar um banco de teste porque
outra sessão ainda o acessava. Não é falha de cenário nem erro da aplicação.
O banco era exclusivamente descartável. Após a saída dos processos, a consulta
em `pg_stat_activity` confirmou zero sessões; foi descartado somente o banco
residual `test_pcpr_prestacao_browser_gw1`, sem FORCE nem interrupção de conexões.

`scripts/verificar.sh` integral, sem filtro de seleção: **2.598 aprovados**,
3.436,24 s (57min16s), saída 0 e “tudo verde”. Ruff, 16 contratos de fronteiras,
mypy, bandit, migrações e tipos JS também verdes. Log em `logs/verificar.log`.
Cinco avisos: três de depreciação do pypdf e dois de paginação sem ordenação no
recorte vazio de Termos/Viagens, já observados na validação anterior do repositório.
Não foram escondidos, corrigidos fora de escopo nem transformados em falha de Prestação.

Rechecagem dos acabamentos em `/prestacao-acabamento`: `scripts/verificar.sh`
com seleção explícita de três testes de view (Lista/Anexos/Carimbo): **3 aprovados**,
348,91 s, saída 0; ruff, fronteiras, mypy, bandit, migrações e tipos JS completos.
Isso é uma rodada incremental, não uma segunda execução da suíte inteira.
Os três cenários E2E incrementais também passaram, 565,79 s, saída 0.
Logs: `logs/acabamento-verificar.log` e `logs/acabamento-browser.log`.

Depois da inclusão de `documento.css` e da correção do ícone, uma última
rechecagem da Lista no mesmo diretório, com bancos novos e nomes distintos:
`scripts/verificar.sh` completo nas ferramentas, com `PYTEST_ADDOPTS` selecionando
explicitamente `test_lista_cartao_e_acoes --create-db`: **1 aprovado**, 170,67 s,
saída 0 e “tudo verde”. Seleção E2E de envio/filtros/foco e resumo/navegação:
**2 aprovados**, 249,89 s, saída 0, sem aviso. Logs `logs/fechamento-verificar.log`
e `logs/fechamento-browser.log`. Esta é uma validação incremental, não outra
suíte inteira. Nenhum candidato em teste foi alterado durante sua execução.
A suíte geral foi concluída no snapshot anterior aos acabamentos de apresentação;
as rechecagens incrementais e capturas verificam a composição final. Não houve
mudança de domínio, serviços, políticas ou documentos entre esses candidatos.

## Comparar, criticar e corrigir

Primeira montagem revelou erro de fechamento de um contêiner na lista e,
depois, ações com largura incompatível com o registro móvel. Corrigidos sem
CSS adicional: cabeçalho identifica o registro e faixa própria agrupa ações.
Fieldsets de recursos/custeio receberam o cartão como contêiner, evitando
conflito entre o padding do campo e o cartão. O teste do carimbo agora abre a
divulgação antes de preencher, sem enfraquecer a conferência do hash da via.

`entrega-manifesto.json`: 14 verificações, HTTP 200, overflow 0, axe 0,
erros JS 0 e POST 0. Revisados visualmente os quatro topos principais em
360/1440; Diário prioriza a tarefa, RT fica em pares, anexos não são empurrados
pelo carimbo. Capturas adicionais de resumo, envio, seções e catálogo em
`conferida/`, com manifesto próprio.

## Proteção da base de demonstração

Captura adicional usa somente navegação e abertura de divulgações/diálogos;
qualquer POST é bloqueado. Antes dela, hashes das linhas completas ordenadas
por ID para a equipe 211:

- Prestação: `df5612ec7ffee230e25f9601459ecb18`.
- Servidores: `f76f0b030686ac507994722256fe16db`.
- Diário: `eb095dce2a759fa92a2442b847109314`.
- Trechos: `7d8d027201ef6769af7fa02f46d4c16e`.
- RT: `3ca7e5ed1edc40c9aa577ed2c28d8df2`.

Depois da captura adicional, os cinco hashes foram conferidos e são idênticos.
Conferência repetida depois das capturas de fechamento: os cinco continuam idênticos.
O resumo e o envio também passaram no axe em 360/1440, sem POST ou overflow.

O UI Lab completo tem 25 px de overflow em 360. A medição foi separada:
`catalogo-manifesto.json` registra explicitamente o overflow da página e o da
seção §14 tocada (0 px, axe 0 nas duas larguras). Não se declarou o catálogo
inteiro validado. Sua captura de componente usa rolagem instantânea/movimento
reduzido para evitar o cabeçalho fixo no meio da captura longa.

Acabamento após a comparação: classe existente `resumo__titulo` nos blocos de
anexos e `linha` no título do envio; ação de equipe e menu no grupo `registro__acoes`.
Nenhum campo, endpoint ou comportamento de submissão muda. Nova captura e axe
em `validada/` e `validada-lista/`, posteriores ao candidato da suíte integral.

A inspeção das pendências abertas encontrou a dependência do checklist:
a lista passou a carregar `documento.css`, folha existente que define o componente,
e a usar o ícone `alert-triangle` já disponível no sprite. Não foi criado estilo
novo. Captura anterior em `pendencias/` e estado corrigido em `fechamento/`.

## Validação final

`fechamento-manifesto.json`: 20 registros verificados (14 telas/estados principais,
quatro diálogos e duas capturas da seção do catálogo), todos com HTTP 200,
overflow do escopo 0, axe 0, JS 0 e POST 0. Mantida a ressalva do catálogo completo.
As pendências abertas foram revisadas novamente em 360/1440 após carregar a
dependência existente do checklist; ícones e textos agora ficam na mesma linha.

Validação concluída: suíte geral, cenários do navegador, rechecagens incrementais,
capturas revisadas, manifesto de acessibilidade/geometria e hashes da demonstração.
Paridade atualizada em `docs/parity/prestacao.md`. Não houve reset, seed ou
alteração de anexos na base de demonstração. Nenhum arquivo CSS/JS, componente
visual, rota ou modelo novo foi adicionado; a mudança é de composição e limpeza.
