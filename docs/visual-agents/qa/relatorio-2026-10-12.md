# PR03 — Relatório Técnico

Base4edd3c6, branch codex/oficios-transporte-cartoes. Concluída tecnicamente.

## Diagnóstico e implementação

Antes: placa clara sem título visual, cartões altos com sombra, barra fixa
cobrindo relato, estado de salvamento só para leitor de tela, nomes/limites
cortados nos rótulos de diárias. Depois: hero canônico, seções contínuas,
barra no fluxo com status real, registros financeiros individuais e peças
documentais compactas. Textos permanecem editáveis; nenhuma nova regra.

Componentes: registro_hero, estado_salvamento, documento--preparacao,
modos--recurso, texto_pronto (opções de tupla), registro_valor e
peca-documental--acoes. Campos condicionais/ações/documentos preservados.

Revisão independente detectou limite liberado sem associação acessível ao
input. Corrigido por ID/aria-describedby; novo E2E verifica a descrição.
Nova crítica trocou o invólucro antigo de documentos pela peça compartilhada.

## Limpeza

`grade-campos` tinha apenas RT como consumidor. Inspeção de HTML, Python,
JS, includes e revisão independente não encontrou criação dinâmica, impressão,
documentos ou outros usos. Nova apresentação validada no navegador e primeira
suíte antes da remoção. Excluída regra de formulario.css; pós-limpeza em curso.
Bases modos/registro/cartoes/frase-oficio permanecem necessárias fora desta página.

## Evidências e testes

Diretório20261012: antes/depois-relatorio-equipe/parcial/consulta em360/768/1440.
Capturas em registros RT existentes, GET sem criação, POST bloqueado e hash
inalterado de relatórios/prestações. Não acionar sugerir/copiar no DEMO.

Primeira execução:92 testes passaram246,89s em logs/relatorio-identidade.log.
Inclui HTTP/domínio, documento PDF/DOCX, sugestão/cópia, autosave/custeio/diária,
teclado/Finalizar, axe e tokens. Validação posterior cobre referência acessível,
opções de texto pronto/diálogo, remoção de CSS e peça documental final.

Desempenho readonly, três repetições por cenário: SQL27/17/9/9 idêntico;
HTML33412→34897,32645→33820,23418→23852,24545→25083bytes. Sem JS novo.
Tempo concorrente com testes não prova ganho de latência. Orçamento SQL HTTP
preexistente aparece no log e não foi aumentado nem ocultado.

Pós-limpeza inicial: 77 passaram e 1 falhou. O teste procurava o texto literal
do label “Nome”, que contém asterisco visual aria-hidden. Corrigido para procurar
textbox pelo nome acessível “Nome”, mantendo a asserção de foco. Teste isolado
passou em 36,66 s (logs/relatorio-dialogo-foco.log). A falha original permanece
registrada em relatorio-poslimpeza.log; não houve alteração funcional para aprovar.
O teardown dessa execução avisou uma conexão restante no banco isolado de teste;
nenhum banco foi apagado manualmente. Reexecução final em andamento.

Compatibilidade texto pronto: nove contextos reais (Ofícios, OS e Justificativas,
360/768/1440), abertura/Escape/devolução de foco e console limpo.
Captura final: 15 cenários (equipe, parcialmente finalizada e consulta em
360/390/768/1024/1440), axe e console sem ocorrências, sem overflow e hash de
dados preservado. Recapturados após revisão do custeio: são rádios estilizados,
não selects antigos; o HTML servido confirma modos--recurso e campo condicional.
Revisão independente não encontrou outro bloqueante após aria-describedby.

Suíte final: **78 passaram em166,50s**, log relatorio-poslimpeza-final.log.
Ruff e git diff --check verdes. Persistiram os avisos HarfBuzz e conexão restante
no teardown do banco isolado; são ressalvas do ambiente de testes, sem falha de
asserção. Não houve aumento de budget, exclusão de teste ou limpeza de banco.
O gate geral anterior passou2343 testes; antecede este candidato e não é
apresentado como gate integral desta revisão. Homologação visual permanece
com o usuário. Próxima página: PR04 Documentos/Anexos, antes já capturado.
