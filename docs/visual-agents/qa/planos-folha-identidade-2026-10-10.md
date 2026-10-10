# Planos — Folha, eventos e documentos, 10/10/2026

Base 17663d8, branch codex/oficios-transporte-cartoes. Somente esta unidade em
implementação; Resultados é a seguinte. Contrato funcional em product, migrações
0046/0047/0048 existentes. DEMO e mídia preservados, sem seed/reset/gravações de negócio.

## Observar e projetar

25 estados anteriores: incompleto, multievento, gerado, novo e diálogo adicional,
nas cinco larguras. Antes: cartões isolados, campos uniformes, destinos antigos,
quantidade móvel estreita e conferência sem âncora apesar do redirect #conferencia.
Teste E2E antigo já falhava antes por procurar Programa como combobox; o controle
vigente é escolha múltipla. Evidência original mantida, intenção funcional preservada.

Preparação em superfície contínua, hero com número/sufixo, agenda proporcional,
destinos/mapa canônicos, coordenação condicional, efetivo existente e Diárias por
EVENTO. Registros compactos para adicionais e menu; conferência recebe pendências
calculadas, editor/histórico/barra reutilizados. Nenhuma regra/documento oficial alterado.

## Comparar, criticar e corrigir

Primeira versão ainda deixava quantidade móvel sem largura útil e ligação à Viagem
sem contraste inverso. Coluna quantitativa corrigida na origem (consumidores reais:
Plano/dialogo/UI Lab); 999 cabe nos controles sem reduzir fonte. Metadados usam a
classe canônica também em Termos e OS, com compatibilidade E2E. Sufixo separado
na placa, identificação completa acessível. UI Lab ganhou agenda/conferência e teve
ID duplicado detectado e corrigido na navegação real.

Ferramentas usam a opção real ferramentas_recolhiveis: celular inicia recolhido,
desktop aberto; Enter alterna. Novo diálogo permanece dentro da janela de altura
500 e ação final acessível por foco; Escape fecha. Editor pertence a grid contents,
portanto sua captura usa a janela real, não bounding box inexistente do wrapper.

Revisão independente encontrou destinos truncados sem title e aria-label retirando
nomes do link de evento. Corrigidos título integral e nome acessível, sem alterar
endpoint/permissões. Validação específica de edição existente com erro acrescentada.

## Verificar

143 HTTP/domínio/tokens/contratos de identificação passaram no candidato atual.
20 E2E integrados passaram: preenchimento e autosave, quantitativos, calendário,
evento manual/diárias gerais, PDF real/finalização e remoção, Lista de Planos,
Ofícios e três larguras de Termos/OS. Reteste específico posterior à revisão registrado
em planos-folha-visual.log; a primeira prova de data inválida não atingia o servidor,
pois o calendário preserva a seleção válida. Cenário corrigido para Outro vazio. Ruff sem erros. Capturas finais em cinco larguras:
25 estados HTTP200, axe0, console0 e sem overflow; mais inspeções UI Lab/diálogo/editor.
Não afirmar conformidade completa: axe automatizado mais teclado especificado.

Falhas anteriores conservadas: seletores antigos de teste de coordenação e limiar
arbitrário de largura desktop 40 (controle tinha39,44). Verificação atual exige área
de alvo >=24 e texto 999 cabendo por medição de fonte, sem enfraquecer funcionalidade.
Avisos preexistentes: HarfBuzz e uma conexão do servidor E2E ainda aberta ao teardown
no banco isolado. Nenhuma alteração em dados/mídia reais para contornar aviso.

## Desempenho e limites

SQL antes/depois: 44 incompleto,52 multievento,49 gerado,26 novo,61 diálogo,
zero mutações. Orçamento middleware25 excedido antes e depois (dívida anterior),
sem aumento. CSS LF components +1710 bytes/+358gzip; formulario -2/-3gzip.
JavaScript idêntico, nenhuma dependência nova.

Comparação controlada HTTP1440 em cópia dos templates/CSS17663d8 e candidato:
static41/42/39, editorAPI2 e folha2 inalterados. Mapa3→6 tiles: painel operacional
mostra área maior. Diferença é renderização geográfica, sem chamada extra à regra
ou editor antecipado. Counts separados inicial/depois de rolar editor, JSON URLs
preservado; não alegar ganho de latência. HTML maior pela identificação/status/ações.

Nenhuma exclusão ampla: estrutura antiga substituída nestes templates, bases CSS
com consumidores reais em Viagens/Resultados conservadas. Programas/coordenação/
atividades mantêm classes funcionais. Lacuna antiga de número manual segue registrada.
Gate integral anterior2295 em9963f71; novo gate necessário no fechamento global.
Página concluída tecnicamente após reteste final; avaliação visual do usuário pendente.


## Falha preexistente em validação de evento

O novo E2E mostrou erro real: após POST422 de Outro programa vazio, Cancelar/Fechar
usavam href ?#eventos e navegavam por GET à rota exclusiva de salvamento, retornando405.
Esse href existe no snapshot17663d8 anterior. Corrigidos destinos explícitos para
editar_plano; links do registro também são absolutos para o mesmo contexto.
Permissões/endpoints de escrita intactos. Reteste completo preserva evento salvo.


O reteste expôs uma corrida no teste de finalizar: a ação aguarda autosave e envia
POST assíncrono; a assertiva de banco corria antes da resposta, iniciando teardown
com requisição ainda ativa (SessionInterrupted). Log preservado. Teste aguarda a
resposta POST real de finalização, sem sleep ou relaxar a assertiva gerado/PDF.


Cenário de validação HTTP422 registra a mensagem de recurso do navegador. Teste
agora exige essa única mensagem exata e resposta422 correspondente; nenhum erro JS
ou outro recurso é aceito. Não excluir genericamente mensagens de console.
Ao concluir a remoção, navega à Lista e aguarda networkidle para encerrar requisições
do editor antes do flush TEST. Falha anterior e deadlock de teardown preservados.

Reteste final: cinco E2E verdes (117,82s) e143 focados (98,73s), sem alterar budgets.
Typecheck npm e Ruff verdes. Revisão independente posterior confirma correções.

UI Lab: dois testes existentes verdes (52,42s). Varredura real adicional360/1440
sem CSSOM/ocultar controles: zero violações axe. Método antigo limita-se a graves e
altera posição da barra; essa limitação não foi usada para aceitar o candidato.
