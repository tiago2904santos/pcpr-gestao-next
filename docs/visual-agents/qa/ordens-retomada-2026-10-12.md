# OS01/OS02/OS03 — retomada da revisão

Base a76e620. Contrato e migração anteriores em ordens-identidade-2026-10-10.md
e product/propagacao-identidade.md. Lista, nova e folha usam componentes canônicos;
não impor redesenho sem defeito concreto. Documentos oficiais preservados.

Lacuna de cobertura corrigida: teste de cancelamento usava `aba=cancelados`,
que normaliza para Todas. Valor efetivo em views_ordens é `canceladas`. O teste
agora exige a aba Canceladas ativa e exatamente o registro cancelado, mantendo
download PDF real, motivo, reativação, leitura sem edição e axe.

Capturas atuais somenteGET/HEAD de Lista/Nova/OS5 em360/768/1440: sessão37107.
Regressão isolada16768: identidade, jornada de criação/funções/autosave, HTTP,
documentos e assinatura. Log ordens-retomada-final.log. Sem conclusão antecipada.

37107 terminou:9capturas completas,HTTP200,consolezero,semoverflow. Revisadas
NovaOS1440 e Lista360: hierarquia canônica, campos agrupados e ação de criação
visível, sem barra cobrindo registros. Outras capturas ainda aguardam leitura;
isso não é declaração de revisão integral. Resultado16768 pendente.

## Resultado da retomada

A sessão 16768 terminou: **64 passed, 1 warning, 220,97 s**. Inclui criação,
autosave, funções, filtros, cancelamento/reativação, download PDF, permissões,
documento oficial e assinatura. Ruff do teste modificado aprovado. Aviso
HarfBuzz é de dependência; orçamento SQL continua excedido na folha, já medido
antes/depois na revisão anterior, sem mudança de consulta nesta retomada.

Revisão das nove capturas: a folha 360 inicial tinha sido fotografada antes do
carregamento da minuta. Corrigido o script para aguardar conteúdo DETERMINO e
fontes do iframe. Recaptura 57735 terminou com nove HTTP 200, console sem erros
e sem overflow externo. Agora documento, histórico e ações finais estão visíveis.
Lista, nova e folha foram examinadas nas três larguras, incluindo as seções
inferiores. Preservada a composição canônica; não identificado defeito visual
que justifique outro redesenho. Documento móvel mantém sua leitura dentro do
editor; conteúdo e paginação oficial não alterados.

Galeria atualizada com as capturas corrigidas. Revisão independente do candidato
solicitada; aguardar parecer antes de mudar a matriz para concluída.

Parecer final recebido: revisor examinou as nove capturas atualizadas e o código;
fechamento técnico sustentado sem bloqueante novo. Matriz OS01/02/03 atualizada,
15/100 páginas concluídas tecnicamente. Homologação visual do usuário pendente.
Fontes testadas em ordens-retomada-candidato.json. Nenhuma remoção adicional
autorizada por prova nesta unidade; preservados consumidores funcionais reais.
