# Viagens — refinamento profundo, 15/10/2026

Pedido explícito de recomposição de Lista, Folha e lote. Documentos antecipados
após Dados, em cinco grupos; vínculos recolhidos e filtráveis entre os candidatos
atuais, sem consulta remota ou mudança do limite de 40 livres/tipo. Conferência
mostra as nove etapas reais e mantém divergências distintas de prontidão.
Descrição/objetivo antes ausente na consulta passa a ser lida quando preenchida.
Lote explicita período, roteiro e rascunhos, mantendo equipe/viatura compartilhadas.
CSS exclusivo `viagens.css`; filtro reaproveita `conjuntos.js`, com Enter impedindo
envio acidental do formulário (também válido em Planos).

Diferenças intencionais de composição em relação ao assistente legado; regras,
calendário, título pelos tipos, vínculos diretos/indiretos, autosave/versão,
conhecidos, datas, permissões, cancelamento em cascata, assinados e documentos
oficiais preservados. Busca por protocolo/filtros combináveis/paginação 25 e
histórico específico de vínculos continuam lacunas preexistentes: não se alega
que o refinamento as implemente. Evidências/resultado técnico no QA de 15/10;
homologação visual do usuário permanece separada.

Validação técnica: 24 cenários de navegador aprovados e 3 retestes finais do filtro;
411 testes de apresentação/tokens/templates aprovados; 14 capturas principais
360/1440 com HTTP 200 e overflow/JS/axe/POST zero. Suíte geral: 2.595 aprovados,
expectativa literal de um estado vazio atualizada e retestada; `verificar.sh`
incremental verde. Cadeia exata de execuções no QA, sem alegar segunda suíte integral.

## Calendário de período, 14/10/2026

Contrato: `docs/product/propagacao-identidade.md`, `gestao/viagens/viagem.py` e
`views_viagem.py`. O usuário aprovou o calendário compacto de Termos e sua propagação.
Na edição, o tipo permanece antes do calendário, que usa largura total. Conservados
âncora `periodo`, ID `viagem-periodo`, nomes/IDs de início/fim, versão e autosave.
Duração em dias de viagem e antecedência até início são indicadores de apresentação.
Não altera datas dos documentos, coerência, permissões ou geração em lote.
Consulta/cancelada com metadados e itinerários com horários não foram redesenhados.
Evidência/limites: `../visual-agents/periodo-propagacao-20261014.md`.
