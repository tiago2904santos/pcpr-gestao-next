# Estado da propagação — 10/10/2026

## Estado vigente — meta integral de12/10/2026

A meta foi reaberta pelo usuário. A matriz canônica por página está em
`matriz-migracao.json`:100 páginas identificadas, mais5 superfícies documentais
associadas que não aumentam a contagem. As linhas agregadas e conclusões abaixo
são histórico de10/10; não comprovam fechamento na meta atual. Páginas antes
migradas retornam a EM VALIDAÇÃO, com preservação das evidências anteriores.
Somente uma revisão atual do fluxo e de seus estados permite fechar cada entrada.

Primeira reabertura concreta:RO02/RO03, Diárias operacional. A variante horizontal
antiga sobrescrevia a grade operacional em Roteiros, Ofícios e Planos;15 capturas
anteriores confirmam uma coluna em360 e quatro em768. Os dois includes migraram
para a única variante operacional; cinco regras antigas foram retiradas.15 novas
capturas mostram duas colunas úteis no celular/tablet e três no desktop. Testes
dos consumidores em execução; não concluído. Evidências em
`evidencias/migracao-identidade-20261012/`. Prestação permanece em validação,
com trabalho anterior preservado. `_equipe.html` do usuário continua intocado.

Prévia própria reiniciada em8017, banco DEMO existente55432 e mídia isolada.
A primeira navegação executou rotinas diárias normais do sistema (notificações);
não houve seed/reset. Nenhuma alteração institucional/manual foi realizada.

Branch inicial: `codex/oficios-transporte-cartoes`; HEAD `722198f`.
Trabalho local e index anteriores preservados em
`var/migracao-visual-20261010-baseline/`. Nenhum push/merge/deploy autorizado.
Referência vigente: cinco capturas do usuário, Ofícios atuais; contrato em
`docs/product/propagacao-identidade.md`. Não é aprovação automática das próximas telas.

## Matriz inicial (aprofundada ao entrar em cada página)

| Módulo/página | Estados | Situação | Componentes | Antigos/compatibilidade | Testes/evidência | Commit/pendência |
|---|---|---|---|---|---|---|
| Ofícios: Lista/Resumo/Folha | consulta, filtros, vazio, geração, falha, equipe, trechos | referência técnica consolidada; passada curta validada | hero, coleção consulta, mesa registro, itinerário operacional, conferência, editor | variantes anteriores para consumidores ainda não migrados | QA anterior: integral 2291, navegador 32+10, HTTP 27; nova compatibilidade 5 E2E e revisão financeira nas 3 larguras | a675739; identidade vigente das capturas do usuário |
| Roteiros: lista | busca, abas, vazio, cancelado, paginação, menu, vínculos | concluída tecnicamente; avaliação visual pendente | hero/coleção/registro operacional | regras exclusivas antigas removidas; bases de outras listas preservadas | 89 focados, 9 E2E compatibilidade, 25 pares, teclado/HTMX/axe/UI Lab, SQL equivalente | gate 2295 verde; manifesto candidato-roteiros.json |
| Roteiros: novo/edição | vazio, preenchido, erro, autosave, bate-volta | concluída tecnicamente; avaliação visual pendente | itinerário/rota/trechos/Diárias canônicos, salvamento sem emissão | mapa alternativo sem consumidores removido | 7 E2E de fluxo, compatibilidade após remoção, 68 tokens, cinco larguras | gate 2295 verde; sem documento/resumo próprio |
| Termos: lista/folha/documentos | busca, filtro por Ofício, avulso/vinculado, novo, documentos, cancelado | concluída tecnicamente; avaliação visual pendente | hero, coleção/registro de relações, preparação, destinos/mapa, equipe compacta, viatura/cartão, editor/histórico | quatro regras exclusivas antigas removidas; mapa mantido para OS/Planos/Viagens | 69 HTTP pós-limpeza; 8 E2E compatíveis; 25 cenários reais verdes; 3 Baixar/documentos e 2 paginação/consulta/assinado verdes | manifesto candidato-termos.json; avaliação estética pendente |
| OS: lista/folha/documentos | busca, vazio, avulsa/vinculada, funções, cancelada, consulta, documentos | concluída tecnicamente; avaliação visual pendente | coleção, registros de relações, preparação, destinos, equipe compacta, editor/histórico | bases compartilhadas mantidas para Planos/Viagens | 81 focados, 6 E2E, 25 capturas e interações cinco larguras | manifesto candidato-ordens.json; HTTP antes/depois inconclusivo |
| Planos: lista | busca, ordem, Ofício, grupos, vazio, cancelados, paginação, consulta | concluída tecnicamente; avaliação visual pendente | coleção, identidade com complemento, registro operacional financeiro, observação larga | bases antigas mantidas para demais consumidores | 47 HTTP, 79 focados, 9 E2E compatíveis, cinco larguras; paginação antiga corrigida | candidato-planos-lista.json; achado de rolagem global não bloqueante registrado |
| Planos: folha/multievento/documentos | incompleto, pronto, novo, gerado, evento adicional | concluída tecnicamente; avaliação visual pendente | hero/preparação/agenda/destinos/financeiro/conferência/editor/histórico | bases genéricas mantidas para consumidores reais | 143 focados, 20 E2E integrados +5 finais, 2 UI Lab, 25 capturas e teclado/diálogo | candidato-planos-folha.json; SQL anterior classificado |
| Planos: Resultados | atividades previstas/retiradas, erro, vazio, cancelado/consulta | concluída tecnicamente; avaliação visual pendente | hero/preparação/lançamentos/leitura/barra no fluxo | duas variantes CSS exclusivas removidas |72HTTP/tokens,5E2E+7pós-limpeza,20capturas cinco larguras | gate global final pendente |
| Justificativas | lista/diálogo/exclusão/download/erro/conflito/consulta | concluída tecnicamente; avaliação visual pendente | coleção/registro/diálogo/paginação com rota explícita | bases genéricas preservadas |108HTTP,2contratos,7E2E,2UI Lab,20pares;SQL igual | candidato-justificativas.json; gate global final pendente |
| Viagens: Lista | busca, abas, vazio, canceladas, consulta, 20+ registros | concluída tecnicamente; avaliação visual pendente | coleção/hero/identidade/registro de relações sem ações | bases compartilhadas preservadas | 94 HTTP,5 E2E+3 finais,20 pares,SQL igual | candidato-viagens-lista.json |
| Viagens: Folha/lote | edição/autosave/conflito/consulta/cancelada/vínculos/conferência/lote | concluída tecnicamente; avaliação visual pendente | hero/preparação/destinos/documentos relacionados/conferência/histórico/barra no fluxo | sete regras exclusivas substituídas removidas | 118 HTTP,15 E2E+4 finais,20 pares,SQL igual | candidato-viagens-folha.json; gate global atualizado pendente |
| Prestação: Lista | edição por servidor/abas/atenção/autosave/envio/equipe/exportação | em implementação | coleção/hero/identidade/linhas operacionais | bases também usadas por Anexos/UI Lab | contrato e captura anterior em curso | próxima unidade ativa; Diário/RT/Anexos não iniciados |
| Prestação: Diário/RT/Anexos | fluxos implementados | não iniciada | aprofundar ao entrar | idem | GET editável pode inicializar registros | após Lista |
| Cadastros/configuração/auxiliares | aprofundar por rota | não iniciada | idem | idem | inventário existente | após fluxos principais |

## Checkpoint de referência

Fontes confirmadas: `oficios/lista.html` → `colecao-operacional--consulta`, filtros
temporais horizontais; `_resumo.html` → leitura independente/contexto; Cadastro →
`_itinerario.html` operacional, `painel_rota`, `_trecho_campos`, `conferencia_valores`.
O gate anterior terminou verde, associado ao manifesto local da rodada, sem novo
commit. Reutilizar resultados apenas onde os hashes permanecem iguais.
Prévia local retomada em :8017, banco LAB existente :55432, mídia isolada existente.
Sem seed/reset. Implementação ativa segue a matriz atual; descoberta paralela
somente leitura, sem edição ou suíte mutável.

## Checkpoint e próxima ação

Referência: `a675739`. Roteiros fechados tecnicamente: 89 focados, 9 E2E ampliados,
7 E2E novamente após remoção, 68 tokens e gate integral 2295/code 0.
SHA final e manifesto em `evidencias/migracao-identidade-20261010/commit-roteiros.json`.
Prévia :8017; galeria :8021; comparação :8023 encerrada; LAB :55432 preservado.

Termos fechados com 69 HTTP pós-limpeza, 8 E2E de compatibilidade, 3 documentais,
3 de geometria após a correção e 2 de paginação/consulta/assinados. Capturas finais
nas cinco larguras, comparação de SQL/recursos e galeria de 40 pares validadas.
SHA e hashes no candidato-termos.json/commit-termos.json.

Ordens de Serviço fechadas tecnicamente: 81 focados e seis E2E, 25 capturas,
funções por servidor, teclado/HTMX/consulta/assinados. SQL e CSS/JS sem aumento;
comparação HTTP controlada inconclusiva por renderização da cópia anterior.
Nenhum código exclusivo antigo removido sem prova. Manifesto candidato-ordens.json.

Lista de Planos concluída tecnicamente; próxima página ativa: Folha/multievento.
Resultados ficam na fila seguinte; contratos distintos de OS: pendências bloqueiam geração/finalização e
efetivo/diárias pertencem a cada evento. DEMO preservado, sem reset/seed.
Não refazer snapshot nem usar git add indiscriminado.


Folha de Planos: 143 focados e 20 E2E integrados verdes. Revisão independente
identificou destinos truncados sem texto integral acessível no novo registro do evento;
corrigidos title e nome do link. Reteste específico: cinco E2E finais verdes, incluindo HTTP422/retorno e geração real.
SQL idêntico nos cinco estados, JS idêntico, CSS gzip +358/-3 bytes por arquivo.
Galeria 105 pares/210 originais conferidos. Ferramentas recolhíveis e diálogo em altura
500 testados por teclado. Resultados continua sem alteração até este fechamento.

Folha fechada: cinco E2E finais, dois UI Lab automatizados e axe real360/1440 zero,
sem alterar estilos. Próxima unidade: Resultados, cujos20 estados anteriores já existem.


Resultados fechado tecnicamente:72HTTP/tokens, cinco E2E e sete pós-limpeza verdes.
20pares nas cinco larguras; rótulos móveis corrigidos com classe própria; tabela
cancelada não exige rolagem horizontal/foco inexistente.66linhas CSS exclusivas
removidas com revisão de consumidores. SQL17/21/17/17 idêntico, JS idêntico,
CSS conjunto+6gzip. Galeria125pares250originais. Próxima unidade:Justificativas,
lista/diálogo/exclusão/download; preservação do contexto após422 é defeito anterior
já identificado em leitura. Não abrir outra implementação em paralelo.


Justificativas fechadas tecnicamente:108HTTP/documentos, dois contratos de paginação,
sete E2E completos171,35s e dois UI Lab91,61s.20pares nas cinco larguras; galeria145pares.
Contexto422/rotas corrigidos com prova anterior. QA diagnosticou espera de cronômetro
pausado e contraste durante transição nativa; somente sincronização dos testes foi
corrigida, sem alterar CSS/CSP/axe. SQL igual14/14/10/19; JS igual; CSS+73gzip.
Próxima unidade:Lista de Viagens. Somente ela em implementação ativa; Folha/Prestação
seguem na fila. Não inventar menu/exportação da Lista que ainda não existem.


Lista de Viagens fechada tecnicamente:94HTTP/domínio/tokens, cinco E2E e três finais
(inclui vinte registros e UI Lab).20pares reais em cinco larguras e teclado/altura500;
SQL20/20/16/19 inalterado, CSSgzip+94bytes e JS igual. Dados DEMO preservados. Nova
variante sem coluna de ações não esconde funções; somente Lista/UI Lab consumidores.
SHA/hashes em candidato-viagens-lista.json e commit-viagens-lista.json. Próxima unidade:
Folha de Viagens e lote, antes de Prestação. Avaliação visual pelo usuário e gate global
atualizado permanecem pendentes.

Folha/lote de Viagens fechados tecnicamente:118HTTP/domínio/pacotes/tokens,15E2E
integrados e quatro finais verdes.20pares em cinco larguras, teclado/altura500 e
UI Lab revisados; SQL180/148/39/21 idêntico, JS idêntico, CSS conjunto+110gzip.
Sete regras CSS exclusivas removidas após prova. Lote validado com equipe/motorista/
viatura e geração real de rascunhos em banco TEST isolado. Galeria185pares/370imagens.
Manifesto e SHA em candidato-viagens-folha.json/commit-viagens-folha.json. Próxima
unidade: Lista de Prestação de Contas, antes de Diário/RT/Anexos; não abrir todos
em paralelo. GET de Diário/RT editável pode inicializar registros: verificar
isolamento/estado antes de qualquer captura. DEMO e mídia continuam preservados.

### Checkpoint solicitado — prints integrais e componentes em uso

Pedido do usuário: mostrar todas as telas alteradas e abrir os componentes para
captura. Entrega em `evidencias/migracao-identidade-20261010/prints.html`:
515 PNGs originais, sendo75 de25páginas/estados em360/768/1440 e440 de componentes,
famílias do UI Lab e sobreposições abertas nos fluxos reais. ZIPs separados para
telas e componentes. Catálogo registra rota, largura, estado e viewport efetivo;
`prints-validacao.json` registra integridade PNG/ZIP, hashes e revisão da galeria.

Cobertura: Ofícios Lista/Cadastro/Resumo; Roteiros Lista/Novo/Edição; Termos
Lista/Novo/Edição-documentos; OS Lista/Nova/Edição-documentos; Planos Lista/Novo/
Folha/Multievento/Documentos/Resultados; Justificativas Lista/Edição; Viagens
Lista/Folha/Lote; Prestação Lista/Liberadas. Componentes capturados dentro dos
fluxos, famílias completas do UI Lab e menus/filtros/calendários/seletores/
diálogos. Motorista externo manual/servidor e justificativa capturados usando
registros DEMO existentes. Cadastros rápidos de servidor, cargo, unidade, viatura
e combustível capturados depois da hidratação, sem confirmar cadastro.

As tentativas iniciais com timeout permanecem nos manifestos de pendências:
espera de networkidle do editor e referência dinâmica ao diálogo filho.
Recapturas explícitas em editor-manifesto e cadastros-manifesto concluídas sem
erro; componentes faltantes na primeira seleção cobertos por complementos.
Nenhum controle foi forçado visível nem imagem retocada. Capturas de componentes
altos usam viewport mais alto para incluir o conteúdo; não simulam a rolagem de
um celular com altura900. Estados condicionais de todos os papéis/permissões
não foram exaustivamente reproduzidos; capturas não equivalem a aprovação visual.

Galeria validada no navegador em360/1440: filtros, busca, abertura de original,
console sem erro e sem overflow horizontal.515 PNGs íntegros; ZIP de telas75
PNGs e ZIP de componentes440 PNGs, sem nomes duplicados e CRC válido.

Retomada da implementação: branch`codex/oficios-transporte-cartoes`,
HEAD`73972833063dc17e90af74e19281be537da84ee8`. Prestação Lista continua em
validação, sem commit:96HTTP/domínio/tokens,9E2E e3provas focadas verdes;
falta comparação SQL/peso com views anteriores, novas capturas de QA depois da
barra final estática, prova/remoção das classes de atalhos substituídas e reteste.
Não declarar encerramento global nem abrir Diário/RT antes desse fechamento.
Arquivo `_equipe.html` do usuário preservado, não incluído no trabalho desta
rodada. Preview8017 e galeria8021 ativos; nenhuma semeadura/reset de banco ou
mídia foi utilizada para obter estas capturas.

### Checkpoint operacional — 12/10/2026, 18h30

Diárias: remoção validada por6E2E finais,94verificações da regressão ampliada,
Ruff e tsc. Revisor independente confirmou teclado/visibilidade; os falsos
negativos do teste (transição/recorte e SVG filho do botão) foram documentados,
sem desativar axe. Imagens de Roteiros inteiros/menu foram revistas. O gate
integral continua ativo, sessão43292, log
`evidencias/migracao-identidade-20261012/logs/gate-propagacao-125caa7f.log`.
Executa com2workers por memória disponível. Não reiniciar por timeout de observação.
A etapa makemigrations do runner alertou sobre o banco-base UUID inexistente;
a verificação adicional de histórico no LAB existente, com conexão explicitamente
somente leitura, passou: `logs/migracoes-historico-readonly.log`.

Index contém somente o candidato Diárias/contrato/QA/testes (12arquivos), com
hunks de components.css e contrato separados de Prestação. Ainda não há novo
commit. Base7397283, branchcodex/oficios-transporte-cartoes. `_equipe.html`
permanece fora do index. Prévia8017 e galeria8021 ativas; banco/mídia preservados.

Próxima ação exata: consultar sessão43292, registrar resultado; se verde,
fechar checkpoint Diárias e Roteiros com manifesto/commit local. Depois consolidar
o candidato existente de PrestaçãoLista: retirar seis regras antigas
.atalhos-atencao* comprovadamente substituídas (preservar IDs/OOB), testar
Lista/Anexos/UI Lab e atualizar capturas. Comparação somente leitura de Prestação
em `prestacao-comparacao-view.json`:mesmas16–26consultas antes/depois, inclusive
25equipes reais; HTML com crescimento pequeno, latência inconclusiva durante gate.
Diário editável pode criar registro no GET; usar dados isolados antes de capturar.
Matriz integral100páginas segue sem fechamento global ou homologação estética.

### Capturas solicitadas — atualização de 12/10/2026

Pedido imediato: prints integrais das telas alteradas e componentes em uso com estados abertos. Atualizadas as 25 telas/estados em 360/768/1440 (75 PNGs), as 81 capturas do UI Lab, nove recortes de Diárias/Prestação e 12 menus do editor. Preservadas as capturas dos demais componentes sem mudança nesta rodada. Catálogo consolidado: 519 PNGs (75 telas, 111 componentes em uso, 81 UI Lab, 252 estados abertos). Galeria: `evidencias/migracao-identidade-20261010/prints.html`; downloads `prints-telas.zip` e `prints-componentes.zip`. Manifestos discriminam rota, viewport e estado. Referência Git d27329c com alterações locais preservadas. Nenhuma alteração de produto nesta rodada de capturas. Esta entrega cobre os cenários DEMO catalogados; não equivale à cobertura de todas as permissões/estados condicionais nem à conclusão da migração global. Resultado da verificação de PNGs, ZIPs, filtros e links: `prints-validacao.json`.


### Fechamento PR01 e próxima página — 12/10, 18h52

Commit `65452f4f239ab064736629ae4e576b5b1decab4b` fecha Lista de Prestação: dez E2E pós-limpeza verdes (276,24s), 68 tokens, 20 capturas axe0, menus/calendários/foco/Anexos compatíveis, paginação25equipes/volta e equipe única em3larguras. Seis regras antigas removidas. CSS líquido+920bytes, sem JS novo; SQL comparável igual. QA e paridade registrados. PR01 concluída tecnicamente,1de100na matriz; homologação visual pendente. Gate integral ativo, session43292, progresso33%, sem resultado final. Próxima página PR02 Diário: preservar4formulários/autosave/viagem realizada/PDF/XLSX, capturar diário existente sincronizado211(edição),201(realizado travado),199(5trechos travados),190(edição) sem seed/reset. Agente readonly levantou contrato e risco de sincronização porGET; root único editor. Arquivo de equipe do usuário permanece intocado.


## 12/10 — fechamento PR02 Diário e entrega de prints

O turno anterior teve progresso:555 prints publicados na galeria e ZIPs, incluindo Diário e modos abertos sem salvar. Esta continuação fechou PR02:100 testes finais em359,21s;20 cenários reais,24 compatibilidades do hero e seis revisões768. SQL igual, sem JS novo; HTML cresceu3,4–6,6% pelos resultados e metadados. Segunda crítica corrigiu hero tablet, campos manuais e consulta de horários. Revisão independente sem bloqueante; homologação visual pendente. Cobertura2/100. Gate integral43292 segue vivo, último43%, sem reiniciar. Próxima PR03 Relatório Técnico: GET editável seguro apenas com RT existente; conferir hash antes/depois. Estado/candidato detalhados em qa/diario-2026-10-12.md e evidências20261012/diario-candidato.json. Arquivo usuário oficios/_equipe.html preservado.
