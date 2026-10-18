# Auditoria de Dados da unidade

## Observar e entender

Git inicialmente limpo. Ambiente informado por `.env`: DEV, PostgreSQL127.0.0.1;
nenhuma conexão remota ou deploy faz parte desta execução.

Inventário: (1) Unidade, cadastro mestre global, nome/sigla/ativo, consumido por
lotação, Servidor, Viatura e documentos; (2) ConfiguracaoInstitucional, complemento
local 1:1, consumido em Ofícios/Justificativas/OS/Planos; (3) assinantes titulares,
FKs para Servidor por Ofício/Justificativa/Plano e coordenador padrão; (4)
SubstituicaoAssinante, por configuração/tipo/período/situação. Superfícies:
`/cadastros/configuracao/`, quatro seletores de servidores, diálogo Nova substituição,
lista Encerrar/Reativar e seletor de unidade autorizado.

Consulta exige view_configuracaoinstitucional (operador/gestor). Alteração exige
change_configuracaoinstitucional e própria unidade, ou ver_todas_unidades.
Usuário/conta e assinante são conceitos separados. Servidor não é duplicado.
Unidade/Configuração são complementares. CoffeeBreak possui configuração de
ofício contratual própria, não duplicação automaticamente equivalente.

Problemas: entrada de configuração está em Cadastros de Viagens, título não
comunica uso compartilhado; unidade administrada pouco destacada; seletores
não exibem erros de seleção; identificador explícito era ignorado na consulta
sem unidades editáveis, e URL prevalecia sobre unidade oculta divergente.

## Projetar
Contrato em `docs/product/dados-da-unidade.md`, ADR0045. Preservar modelos,
identidades, permissões e snapshots. Entrada única no menu da conta; rota legada
compatível; cabeçalho com unidade explícita; validação de contexto antes dos
formulários. Testes adicionais de GET/POST direto e conflito de identificadores.

## Implementar / testar / comparar / criticar / corrigir / validar
Implementação e evidências registradas abaixo.

## Implementação realizada

- Cabeçalho usa tag `cadastros_ui.pode_ver_dados_unidade`, que delega à policy;
  entrada após Alterar senha. Item redundante removido do menu de Viagens e
  cartão do índice. Alertas contextuais de unidade sem configuração permanecem
  links úteis para resolver a pendência, sem criar outra entrada de navegação.
- Página e breadcrumb Dados da unidade, nome/sigla mestre explícitos, seções
  Identificação/Endereço/Assinantes/Destinatário, ações claras. A configuração
  continua separada do mestre Unidade, e nenhuma conta é criada/alterada.
- Unidade explícita inválida, não autorizada ou divergente em GET/POST retorna 404;
  operador não recebe validação editável em POST inválido:403 antes do formulário.
  Uma lotação inativa permanece indicada no seletor autorizado, evitando exibir
  uma escolha visual diferente do destino do salvamento.
- Seletores de assinantes usam widget remoto compartilhado, com endpoint próprio
  `/cadastros/configuracao/assinantes/` protegido pela mesma policy e contexto.
  Busca por nome/cargo/unidade/CPF,15 resultados, cargo/unidade/CPF final 4 de
  identificação. Validação da FK mantém ativos ou titular inativo já escolhido.
- Diálogo de substituição usa largura proporcional (até 52 rem) e variante compartilhada com corpo
  rolável/ações disponíveis; conserva calendário compacto, foco, Escape,
  cancelamento, dados preenchidos e Encerrar/Reativar.
- Sem migração de esquema: preservadas PKs, FKs, tipo de documento, vigência,
  chefia de fallback e instantâneos consolidados. Nenhuma mudança em produção.

## Testar, comparar, criticar e corrigir

A primeira tentativa de pytest com o usuário PostgreSQL local não tinha permissão
de criar banco. Foi abandonada sem escrita no banco DEV. A validação efetiva usa
cluster LAB descartável em 127.0.0.1:55432, usuário cadastros_lab, com bancos
`test_pcpr_unidade_lab` e `test_pcpr_unidade_e 2 e_lab`; nenhum dado operacional.

Na primeira rodada backend,24 passaram e a contagem de links do teste de menu
incluía também um alerta contextual legítimo. Corrigido o teste para contar o
rótulo da entrada e conferir a ordem dos links. Rodada seguinte:31 passaram,
incluindo consulta/gravação/perfis e snapshot de documento emitido.

Na primeira rodada E2E,3 passaram e 3 falharam porque o teste antigo esperava
textboxes Início/Fim, já substituídos anteriormente pelo calendário compacto.
O teste foi atualizado para abrir o calendário real e clicar nos dias, conferindo
os hidden values e a preservação ao cancelar/reabrir. Não se restaurou UI antiga.

Acrescentadas verificações de autorização do endpoint e seleção com 401 servidores:
reprodução do select anterior gera 402 opções (incluindo vazio), o remoto gera 2
(vazio+atual), redução de 99,5% das opções. O teste compara o mesmo queryset e
verifica HTML abaixo de 10% do tamanho anterior; escolhido inativo fora da primeira
página preservado. O endpoint nunca retorna mais de 15 registros. Este é ganho
no payload/renderização; não se declara medição de latência de fonte externa.

Resultados concretos da cobertura estão registrados na seção final abaixo.

## Validação final da área

Oito cenários funcionais únicos de navegador executados em 360/768/1440:
gravação/erro/consulta/substituição em três larguras; ausência de configuração e
lotação em três; troca de unidade e persistência do titular em duas. A rodada
`unidade-e2e.log` terminou com 7 passes e um timeout em 360, iniciado antes da
correção compartilhada da busca remota. A rodada estável `unidade-e2e-final.log`
passou nos 3 cenários reexecutados: fluxo completo 360 e troca de contexto/titular
360/1440. A união dessas rodadas cobre os 8 cenários sem pendência funcional.
A troca de titular verifica que digitar limpa o ID anterior sem apagar o texto,
seleciona outro servidor e preserva o novo valor após salvar e recarregar; ASCOM
permanece inalterada ao editar DPC.

Backend: a rodada remota executou 37 casos, com 36 passes e uma fixture de volume
incorreta (não indicava o titular como valor inicial do formulário). Após correção,
19 casos de contexto/endpoint passaram e o caso de volume corrigido passou isolado:
`unidade-volume-unitario.log`, 1 pass, 402 opções no select anterior contra 2 no
remoto, com HTML abaixo de 10% do anterior. Os testes de perfil, assinantes por tipo,
endereço, escopo e snapshot emitido passaram na rodada de 36. A repetição redundante
foi encerrada para liberar recursos; o verificador completo coordenado pela missão
é a confirmação integrada final, registrada no relatório principal.

Axe executado nos estados de erro, edição, diálogo, consulta, sem configuração,
sem unidade e troca de contexto. Teclado: Enter para abrir, Escape para cancelar,
retorno de foco, preservação do período e nova abertura. Nenhuma rolagem horizontal
em 360/768/1440. Titulares inativos atuais e lotação inativa identificados no backend.

Capturas anteriores preservadas em `unidade/antes/`: arquivos de 14/10/2026 já
existentes em `artifacts/configuracao`, não nova sessão no legado. Capturas desta
execução em `unidade/depois/`: menu, página com titular longo, erro, consulta,
substituição, ausência de configuração e lotação. O diálogo foi revisto em 360/1440:
campos amplos, período legível e ações disponíveis. Há capturas por seção para
conferir contatos e assinantes com a barra sticky no comportamento real; nenhuma
regra de apresentação foi alterada apenas para a captura.

Limites: conexão externa real depende do contrato da fonte dedicada. A seleção
remota requer JavaScript para buscar outro registro; sem ele o vínculo existente
continua enviado e pode ser preservado. Não houve deploy nem alteração do banco DEV
operacional. A comparação funcional usa o contrato documentado, sem alegar nova
homologação do sistema de referência em execução.

### Exceção investigada: configuração de Coffee Break

`gestao/coffee/models.py::ConfiguracaoOficio` é um singleton sem relação com
Unidade, destinado ao ofício ao GAF, protocolo e e-mails ao fornecedor. Seus
campos são vocativo, assinante/cargo textuais, destinatário, destino do despacho,
assunto/palavras-chave do protocolo e modelos de e-mail/cópias. Não possui um
cadastro duplicado do nome/endereço mestre da unidade. O documento financeiro e
seu destinatário diferem dos ofícios de viagem ao DG; não há correspondência de
unidade ou identidade de servidor suficiente para migrar esses textos por nome.
A configuração permanece no domínio Coffee com permissões existentes. Uma futura
seleção de servidor nesse domínio deverá preservar os textos antigos e a decisão
de escopo, sem inferir que o signatário financeiro seja o titular de Viagens.

### Fechamento visual e consulta

A regeneração estável passou: `unidade-evidencias.log`, 1 pass, duas larguras
(360/1440), reduced_motion, menu após animações e capturas de viewport por seção.
Os menus finais estão opacos e legíveis; identificação, contatos e assinantes
foram revistos mantendo a barra sticky real. São 18 imagens finais e 4 baselines.

A revisão compartilhada encontrou que a busca remota precisava propagar o estado
disabled do select para o input aprimorado. A correção foi feita no componente
comum, e o teste dirigido do operador passou: `unidade-consulta-e2e.log`, 1 pass,
quatro buscas desabilitadas em 360/1440, ações de gravação/substituição ausentes e
axe sem violações. O mesmo assert foi incorporado à consulta do fluxo completo.
A cobertura da área fica em 8 cenários funcionais principais, um teste dirigido
de consulta e uma fixture visual que registra duas larguras. Todos os cenários
possuem execução bem-sucedida após as correções correspondentes.

Nenhum pytest ou navegador desta área permanece aberto. A confirmação integrada
final de `scripts/verificar.sh` pertence ao relatório coordenado da missão.
