# Ofícios — bloco visual premium, 08/10/2026

Branch `codex/viagens-piloto-resumo`, base `fdc662f`.
**APROVADO COM RESSALVAS — avaliação do agente**. Escopo exclusivo: Lista, Resumo,
Cadastro/Edição/Folha e painel Documentos do Ofício.

## Mudanças consolidadas

- Lista: cabeçalho documental, abas com ação selecionada clara, filtro em
  superfície suave, número editorial, destinos legíveis e composição móvel
  em linhas próprias. Filtros, ordenação, menus, permissões e paginação mantidos.
- Resumo: dossiê amplo, hierarquia número/destino/situação, motivo em destaque,
  tipo/prazo separados, roteiro contínuo, conferência financeira unificada,
  equipe em linhas e documentos com versão e data. Revisão, cópia, polling,
  versões, assinatura, geração e foco preservados.
- Folha: identidade compartilhada, título orientado à tarefa, formulário
  contínuo com seções numeradas, equipe compacta e faixa de valores compartilhada.
  Campos, validação, autosave, motorista, transporte e datas não mudam de regra.
- Documentos: estação com superfícies e índice coerentes; ferramentas de
  formatação recolhidas inicialmente no celular e disponíveis por teclado.
  A folha oficial no iframe e os arquivos gerados permanecem intactos.

Não foram alterados domínio, serviços, views de negócio, queries, assinados,
pacotes, banco, migrations, integração, permissões ou configurações de segurança.
A única view alterada é a vitrine sintética do UI Lab.

## Observar → entender → projetar → implementar

Diagnóstico e direção: `../visual/piloto-resumo-zero-base.md`.
Componentes: `../../design-system/components.md`.
Piloto escolhido: Resumo, por reunir percurso, equipe, valores, metadados e
documentos e ser também a conferência da emissão. Segunda tela: Folha.
Propagação restrita às quatro áreas de Ofícios; UI Lab demonstra variantes.

## Comparar → criticar → corrigir

Antes/depois e lado a lado em 360, 390, 768, 1024 e 1440 px. Cada captura tem
altura 900 px; comparações acrescentam rótulos, sem alterar a aplicação.
Índice visual: `oficios-premium-evidencias.md`.

Problemas encontrados e corrigidos: rolagem interna do roteiro, fragmentação
dos valores em três cartões, cartões excessivos na equipe, destino comprimido
no celular, competição entre número/status/título, cascata CSS anulando o
layout móvel e barra de formatação excessivamente alta no celular.

Autocrítica final: há uma evolução clara de composição e hierarquia; Resumo
e Folha compartilham identidade, pessoas, valores e ações. A Lista ganhou
legibilidade móvel. A folha oficial continua A4 e é exibida em escala no
celular, com texto menor; não foi transformada em formulário responsivo,
o que mudaria sua natureza.
O visual aprovado tecnicamente continua sujeito à avaliação estética humana.

## Evidências e método

PREVIEW fictício `pcpr_lab_demo`, PostgreSQL 127.0.0.1:55432. Portas próprias
8010 (candidato) e 8011 (referência com produto idêntico à base). Mídia isolada
em `%LOCALAPPDATA%/pcpr-codex-lab/preview-media`. Sem reset/seed neste bloco,
sem banco remoto e sem escrita em dados históricos.

Resumo: Ofício sintético 06/2024 emitido, inclusive documentos inferiores.
Folha/Documentos: rascunho sintético 16/2024, dados já presentes. E2E usa
fixtures descartáveis em bancos `pcpr_lab_visual*`, separados do PREVIEW.

O servidor local de QA com DEBUG falso inicialmente não servia o prefixo
de assets documentais no Windows. Foi ajustado apenas seu launcher ignorado
para usar o handler estático do Django; as fontes e o brasão foram verificados
antes das capturas finais. Referência e candidato usam o mesmo método.
Não houve mudança de CSP, autenticação ou exposição externa na aplicação.
Capturas do ambiente incompleto: `../evidencias/oficios-premium/ambiente-antes/`.

Medição do Resumo: overflow horizontal zero em todas as larguras; rolagem
interna do roteiro em 360 px caiu de 102 px para zero. Dados e ações mantidos
nas medições `../evidencias/piloto-resumo/{antes,depois}-medidas.json`.
Console das capturas finais de Lista/Folha/Documentos: zero erros.

## Testes executados e classificação

Conjunto funcional consolidado: **149 passaram / 1 falhou**, 944,63 s.
Inclui tokens, novos casos do Resumo/UI Lab, versões documentais/guards,
cópia, emissão, menus, Baixar, carga adiada do Baixar, editor e carga do editor.
Falha única: `test_resumo_htmx_carrega_copia_e_fallback_seleciona_texto`,
seis mensagens CSP `style-src-attr` originadas no HTMX; funcionalidades do
caso funcionaram, mas seu contrato estrito de console falhou.

**Preexistente comprovado**: o mesmo caso falhou na referência com fontes de
produto anteriores ao redesenho, com as mesmas mensagens CSP, em 39,14 s.
Log de referência será preservado com os logs deste bloco. CSP e asserções
de console não foram relaxadas.

Primeira rodada visual final: **81 passaram / 3 falharam**, 300,52 s.
Os três achados eram premissas da nova automação: toolbar da primeira folha
presumida ativa mesmo ao centralizar o bloco inteiro; índice presumido aberto
no celular; controle anterior cortado sob navegação fixa ao avaliar uma posição
arbitrária. Os testes passaram a operar a folha ativa, verificar a transição
real do índice e avaliar a seção Documentos desde seu título. Nenhuma regra
axe foi excluída. A rodada posterior testa a composição e formatação acessível.

Primeira rodada do piloto também revelou um erro da nova automação:
expressão sem função em `wait_for_function`, recusada por CSP. Corrigido para
função explícita; nenhuma configuração de segurança foi alterada.

Gate integral `scripts/verificar.sh`: **verde**, exit 0. Ruff, fronteiras
(16 contratos), mypy (303 fontes), bandit, migrações e tipos JS passaram.
**2.193 testes passaram, zero falhas, 7 avisos, 2.878,74 s (47min58s)**.
Avisos preexistentes de bibliotecas: HarfBuzz-Subset/WeasyPrint e API
`replace_contents` do pypdf. Log integral preservado em
`../evidencias/oficios-premium/logs/oficios-premium-verificar-integral.log`.

## Limites e pendências

Nenhum bloqueante funcional demonstrado no conjunto concluído. Falha CSP
preexistente continua aberta e exige ressalva no fechamento. A missão não
inclui nova integração, redesign de documento oficial, certificação PDF/A,
auditoria geral de performance ou páginas de outros módulos.

CSS das variantes aumenta o payload existente; não há biblioteca, fonte,
imagem remota, endpoint ou requisição adicional introduzida pelo redesenho.
Orçamentos de performance anteriores já estavam acima dos limites, conforme
o fechamento da base. Não declarar performance global verde sem medição.

## Checkpoint de refinamento final

A revisão manual encontrou rótulos cortados em 768 px: a identificação
mantinha cinco campos na mesma linha. Variante compartilhada
`campos--legiveis` permite quebra acima de 768 px, mantendo a composição
de duas colunas no celular. Foi adicionada à vitrine e aos testes com
asserção explícita de ausência de truncamento. Capturas finais recapturadas.

Rodada editor/responsividade: **20 passaram / 3 falharam**, 534,75 s.
Editor, persistência, campos vivos, histórico, Texto/PDF, carga adiada e
Lista/Folha/Documentos passaram. Três casos do Resumo falharam somente no
console: dois CSP durante polling e um abort de pedido ao fechar. Axe,
layout, ações, foco e fechamento passaram nesses casos.

O cenário visual estava usando uma emissão que ainda aguardava o worker.
Agora a própria outbox gera o PDF real antes da comparação do estado pronto,
como nas capturas. Há asserção de que todos os documentos ficaram prontos;
não foi simulado sucesso nem removida a asserção de console. A suíte RS-02
continua verificando a geração em andamento, o polling e o abort em voo.

**Abort preexistente comprovado**: probe na referência chamou o teste
existente de fechamento em voo e acrescentou a asserção estrita de console.
Reproduziu `htmx:afterRequest` e `htmx:sendAbort`, iguais ao candidato,
em 126,21 s. É ruído de console no cancelamento intencional; fechamento,
foco e interrupção dos pedidos funcionaram. Não é regressão visual.
Probe e logs são preservados como evidência, sem alterar o teste funcional
original ou introduzir tolerância a erros no produto.

Logs arquivados normalizam somente finais de linha e espaços finais, sem
remover linhas, mensagens, falhas ou resultados. Hashes do bruto/arquivado
e contagem de linhas constam em `logs/metadados-logs.json`, dentro da pasta
de evidências. Saídas brutas permanecem em `var/` do checkout e da referência.

Custo das fontes, comparadas com `fdc662f`: CSS +15.535 bytes; JS +312 bytes.
Gzip dessas fontes, sem representar payload HTTP medido: CSS +2.534 bytes,
JS +121 bytes. Resultado em `../evidencias/oficios-premium/custo-fontes.json`.
Não houve novas requisições obrigatórias; os testes de carga adiada exercitam
que miniaturas e editor continuam esperando a aproximação da seção.

Fontes de produto registradas em `fontes-validadas.json` (SHA-256, 19 arquivos).
O ajuste final de campos ocorreu durante a suíte integral; tokens e navegador
foram repetidos sobre ele antes da entrega. Nenhuma regra de negócio mudou
durante a execução do gate.

## Rodadas finais sobre o candidato consolidado

- **16/16 passaram**, 642,49 s: cinco larguras do conjunto Lista/Folha/Documentos,
  cinco do Resumo pronto (PDF real concluído pelo worker), quatro estados de
  dossiê no UI Lab e duas larguras da auditoria completa do UI Lab.
- **73/73 passaram**, 361,06 s, na revalidação do último ajuste: cinco larguras com
  asserção explícita de rótulos sem cortes, toolbar com um tabstop, alternância
  de documento ativo, disclosure de formatação operável por teclado, menus,
  foco, console, overflow e axe; 68 verificações de tokens/contraste/foco.
- Todos os 20 relatórios axe do conjunto (4 áreas × 5 larguras) contêm
  lista vazia de violações; regras WCAG 2.0/2.1/2.2 A/AA não foram excluídas.
- Manifesto das 19 fontes de produto: **zero divergências** depois da
  revalidação. Não foram introduzidos novos recursos após o congelamento.

Os números descrevem rodadas distintas, com sobreposição; não são somados
como se representassem testes únicos adicionais ao gate.

## Decisão por área e fechamento

- Lista: **aprovada visualmente** pelo agente. Destinos e hierarquia móvel
  legíveis, filtros/ações operáveis e cinco larguras verificadas.
- Resumo: **aprovado visualmente com ressalva** de console no polling da
  geração, demonstrada na referência. Estado pronto, revisão, versões,
  documentos, foco e menus foram validados nos cenários executados.
- Folha: **aprovada visualmente** pelo agente. Identidade, seções, equipe,
  valores e proporções coerentes; rótulos cabem no tablet; controles e regras
  preservados. Há capturas das cinco larguras e axe sem violações.
- Documentos: **aprovados visualmente com ressalva** da leitura reduzida
  da folha A4 em celular. A estação é responsiva; formatação está disponível
  por teclado; persistência, histórico, Texto/PDF, Baixar e carga foram testados.

Nenhuma regressão funcional conhecida nos cenários executados; nenhum
bloqueante novo demonstrado. Não equivale à aprovação estética do usuário.
Não declarar CI global ou performance global verde: testes E2E antigos
relatam CSP/abort preexistentes, e os orçamentos anteriores de performance
continuam uma dívida explícita, acrescida do custo CSS registrado acima.

Commit de implementação validada: **`e219222`**, incluindo catálogo dos
componentes e testes. Segundo commit registra documentação e evidências.
Principais arquivos: `editar.html`, `lista.html`, `_resumo.html`, `_editor.html`,
`_resumo_documento.html`, `_diarias_corpo.html`, `_equipe.html`, `_registro.html`,
dois parciais compartilhados, arquétipo de Lista, três CSS, `editor-documento.js`,
UI Lab e duas suítes novas de navegador. Manifesto lista os 19 arquivos de
produto; a implementação inclui também testes e documentação do DS.

Fora do bloco: Termos e demais páginas de outros módulos, nova integração,
mudança de regra, documento oficial, paridade editorial independente de
PDF/A/DOCX e performance ampla. Helpers de QA e capturas históricas de outros
módulos permanecem em `var/`, fora dos commits. Probe de referência foi
retirado da coleta de testes e preservado em `var/` e na evidência `.txt`.

Próxima etapa: revisão humana deste conjunto de Ofícios pelas comparações
e pelo PREVIEW. Nenhuma nova página iniciada. Sem push, merge ou deploy.
