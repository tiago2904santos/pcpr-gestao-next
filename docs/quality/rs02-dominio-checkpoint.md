# RS-02 — checkpoint do domínio e adaptador

07/10/2026. Domínio puro e adaptador sem consultas: maior identidade por tipo,
readiness separado, via pelo ID/tipo exato, rascunho/cancelado históricos,
justificativa pelo snapshot e aviso de ambiguidade. Especificação documentada
antes do código em oficios-documentos-versoes.md; ADR0025.

Principal reexecutou os dois arquivos de teste puros: 81 passaram em0,27s,
var/documentos-versoes-puros-root.log. Plugin Django desabilitado e conftest
ignorado; aviso de opção django config desconhecida esperado nesse recorte.
Ruff dos quatro arquivos passou. Mypy integral303fontes passou antes dos últimos
ajustes de leitura. QA independente reexecutou81puros e compilou SQL bloqueando
conexão; achados/limites em critica-rs02.md.

Commit deste checkpoint contém apenas domínio/adaptador/testes puros e documentos.
Conexão a queries/policies/pacotes/assinados/views/templates/JS é candidata no
worktree, não aprovada por esses81testes. Rodada HTTP conjunta95passaram/1falha
por fixture usando atributo objetivo inexistente; corrigida para motivo, sem
reexecução ainda. Últimos ajustes de menu, via vazia/vínculo cruzado, pacote
incompleto e foco OOB ainda precisam dos testes reais próprios e verificador.
Não há aprovação de entrega do bloco inteiro neste checkpoint.
