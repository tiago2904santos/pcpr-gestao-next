# Folha e lote de Viagens — identidade vigente

Base `3708d54`, branch `codex/oficios-transporte-cartoes`. Contrato registrado antes
da implementação em docs/product/propagacao-identidade.md; referência funcional em
docs/migration/viagem.md. DEMO existente preservado, sem semeadura/reset ou edição.

## Implementação e segunda revisão

Hero com identificação por data/ID, tipos, destinos, período e contagens reais.
O contêiner data-vivo atualiza título e contexto após autosave; IDs anteriores,
versão, campos conhecidos e proteção dos vínculos permanecem. Preparação contínua,
campos de conteúdo/período proporcionais, destinos/mapa operacionais, vínculos
compactos, conferência por etapas, documentos relacionados, histórico operacional
e barra no fluxo. Consulta/cancelada conserva leitura e permissões.

Lote usa equipe compacta e cartão de viatura canônicos, mantendo os campos por
índice, adicionar/remover sem gravação e gerar rascunhos pelo serviço existente.
Não gera documentos oficiais nem muda regras, textos ou margens do PDF.

A primeira revisão encontrou o caminho interno de um template vazando no hero
do lote por colisão do parâmetro complemento; o contexto ganhou nome próprio.
Segunda revisão: grupos documentais em duas colunas, último ímpar integral e cada
lista interna com largura completa; um documento não reserva meia coluna vazia.
No cenário preenchido, Adicionar Ofício estava fora do alinhamento dos seletores;
passou para o final da última seção, usando secao__bloco--integrado existente.

## Limpeza com prova de substituição

Cinco regras `.vinculo .caixas*` de formulario.css tinham somente o template
_vinculo.html, substituído por campo--documentos. Duas regras checklist__sub de
documento.css tinham somente _conferencia.html, substituído por conferencia_etapas.
Revisão de consumidores considerou includes, criação dinâmica, data-*, JavaScript,
documentos/impressão e estados condicionais. As bases caixas/checklist/documento
continuam com consumidores e foram preservadas. Links novos mantêm alvo mínimo.
Nenhum teste, fallback, permissão ou dado removido. Revisão independente de código
não encontrou bloqueante no candidato. Arquivo de equipe de Ofícios do usuário
permanece fora desta unidade e do commit.

## Evidências e testes

20 pares antes/depois nas larguras360/390/768/1024/1440: vinculada, básica,
cancelada e lote; HTTP200, axe zero, pageerror zero e overflow false. Iterações
intermediárias preservadas. Cenário preenchido do lote em360/1440 usa banco TEST
isolado, não dados DEMO. UI Lab documenta vínculos, relações e conferência.
Revisão manual em360/768/1440 com altura500: menu Enter/Escape/devolução de foco,
checkbox por Espaço, foco em pendência e barra estática; axe UI Lab zero.
Isso não representa auditoria manual completa de tecnologias assistivas.

118 HTTP/domínio/pacotes/tokens pós-limpeza verdes (162,67s), 15 E2E integrados
verdes (356,14s), Ruff e TypeScript verdes. Primeira rodada:13E2E verdes e dois
erros no seletor do teste (título incluía a numeração da seção); log preservado,
seletor corrigido, cinco focused verdes e repetição integrada verde. Nenhuma regra
de negócio flexibilizada. Finalização do teste aguarda requisições do mapa e sai
para a Lista antes da limpeza do banco, evitando chamadas após remoção da sessão.

UI Lab inicial: dois E2E verdes em94,20s, com diagnóstico faulthandler durante
flush/post_migrate/sincronização de papéis. Não houve falha de teste; consulta
posterior ao PostgreSQL não mostrou bloqueio. Causa do tempo de teardown não foi
comprovada como problema de interface; não declarar ganho de latência.

Reteste final do ajuste de Adicionar Ofício e UI Lab: **quatro E2E verdes em134,06s**
(lote360/1440 + dois UI Lab). Capturas finais novamente verificadas nos vinte estados.
Galeria185pares/370originais carregados e filtro1440 conferido. Sem regressão bloqueante
conhecida; conclusão técnica não representa aprovação estética do usuário.

## Desempenho e pendências

sql-peso-viagens-folha.json compara os mesmos quatro GET com templates anteriores:
180/148/39/21 consultas idênticas antes/depois, zero mutações DEMO. A Folha já
excedia orçamento SQL25 (middleware176/144/35 nos estados comparados); dívida de
consultas do contexto/vínculos, sem aumentar budget. HTML cresceu entre554 e1337
bytes por estado. JS autosave/transporte inalterados; CSS LF components+2681bytes,
formulario-1084 e documento-271; conjunto gzip+110bytes. Não são bytes transferidos
nem medição de latência/requisições HTTP. Documento oficial sem alteração.

Seleção entre40candidatos por tipo continua sem busca; histórico de vínculos é
lacuna anterior registrada em migration/viagem.md. Não foi criada uma frente nova.
Avaliação visual do usuário e gate global atualizado permanecem pendentes.
