# ADR 0045 — Preserve a configuração local da unidade ao reorganizar seu acesso

- **Status:** aceito
- **Data:** 2026-10-17

## Contexto
A missão move Configuração da unidade para o menu da conta como Dados da unidade.
O sistema já possui Unidade, ConfiguracaoInstitucional (1:1), Servidor e
SubstituicaoAssinante. Documentos usam instantâneos, e a configuração é protegida
pela permissão de alteração e escopo de lotação/ver todas unidades.

## Decisão
Manter as entidades e identidades existentes e a rota compatível, movendo a entrada
para o menu da conta. Uma tag do contexto Cadastros fornece a decisão da política
ao cabeçalho sem inverter a dependência da plataforma. Resolver explicitamente e
validar o identificador da unidade antes de apresentar ou alterar seus dados.

## Alternativas consideradas
- Fundir Unidade e configuração: perderia a separação entre identidade mestre e
  complementos locais, necessária à futura fonte dedicada.
- Criar outro cadastro de assinantes: duplicaria Servidor e vínculos existentes.
- Importar Cadastros no context processor da plataforma: violaria fronteira arquitetural.

## Consequências
Sem migração de dados; vínculos e histórico permanecem. O menu passa a refletir
uma única política. Identificadores inválidos, divergentes ou fora do escopo
retornam 404; escrita sem permissão retorna 403 antes da validação dos campos.
A fonte futura poderá administrar a identidade mestre sem sobrescrever esses
complementos locais sem contrato específico. Configuração Coffee permanece
separada por representar responsabilidade e documentos do domínio contratual.

## Complemento — seleção remota

As escolhas de assinantes passam ao widget compartilhado SelecaoRemota: HTML inicial
com somente o valor atual e endpoint contextual limitado a 15 resultados. O servidor
continua validando a seleção pelo queryset de servidores ativos ou titular atual.
O endpoint exige a política da configuração e valida a unidade; não concede
permissões de Servidor ou conta ao perfil. O contrato permite trocar a fonte futura
sem replicar consultas por formulário. Sem JavaScript preserva-se o vínculo atual,
mas a busca de outro depende de JavaScript, como no componente multiescolha existente.
