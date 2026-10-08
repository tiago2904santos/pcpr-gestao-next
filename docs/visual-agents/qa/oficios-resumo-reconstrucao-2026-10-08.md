# Resumo do Ofício — fechamento da reconstrução visual

Branch `codex/oficios-resumo-reconstrucao`, base `c027493`. Piloto único: Resumo,
incluindo a revisão antes de emitir. A entrega visual anterior foi reprovada pelo usuário.
Código útil preservado; nenhuma segunda página de negócio redesenhada neste bloco.

**Estado deste registro: consolidação em execução.** Aprovação visual pendente do usuário.
Não interpretar execução parcial como gate verde.

## Direção e transformação

Três conceitos renderizados antes da implementação final: documento vivo, mesa operacional,
registro editorial. Escolhida mesa operacional. Primeira iteração: documentos laterais e
conferência escura. Crítica e segunda iteração: documentos primeiro em todas as larguras,
arquivo/assinatura unidos, percurso por saída e chegada, equipe em faixas e conferência clara.

Mudanças perceptíveis em identidade/número, hierarquia, documentos, percurso, equipe,
diárias, metadados, relação principal/contexto e composição de celular/tablet/desktop.
Conceitos e riscos em [direção visual](../visual/oficios-resumo-reconstrucao.md);
capturas reais em [galeria antes/depois](oficios-resumo-reconstrucao-evidencias.md).

## Componentes e contratos

- `registro_hero.html`: identidade institucional e contexto, sem inferir estados.
- `bloco_registro.html`: seção compartilhada com heading e referência acessível.
- `documento_assinatura.html`: assinatura dentro da peça, com os menus e policies existentes.
- `conferencia_valores.html`: variante clara `serena=True`, mantendo todos os valores.
- Padrões compartilhados `.mesa-registro`, `.estacao-documental`, `.peca-documental`,
  `.percurso-registro`, missão e dock, na origem do Design System.
- UI Lab atualizado com vazio, conteúdo longo, falha/geração e as três direções.
- Parciais de negócio separadas por apresentação: avisos, período, situação, percurso,
  equipe, conferência e registro. Sem mudança de domínio, serviço, query ou API.

Mantidos diálogo nativo, URLs, IDs HTMX/OOB, polling, retry, histórico, foco/restauração,
menus canônicos, permissões, motorista interno/externo, outro transporte, prazos,
justificativa, data manual e revisão D13. Nenhum JavaScript, biblioteca, migração,
integração ou documento oficial alterado. UI Lab CSS não carrega no Resumo.

## Testes concluídos e evidência

Contagens por execução, sem somar repetições como testes distintos:

- 122 focados: domínio/HTTP de Lote H, documentos, eProtocolo e tokens; passaram.
- Navegador inicial: 23 passaram e 1 falhou na asserção de console CSP do fallback.
  A mesma falha foi reproduzida na base `c027493`; comportamento de cópia e axe passaram.
- 6 casos: quatro estados longo/vazio do UI Lab e dois de via atual sem original; passaram.
- 2 casos de upload/revogação pela peça: passaram em 360/1440, incluindo leitura dos bytes,
  registro revogado e preservação do arquivo histórico. Apenas dados descartáveis do LAB.
- Jornada criar/preencher/revisar/emitir: 1 passou, com documento gerado e console limpo.
- Foco do dock, cinco larguras: **5 passaram na repetição final**, com asserção explícita
  de halo, campo acima do rodapé, foco real e restauração por Escape.
- UI Lab completo com axe em 360/1440: 2 passaram.
- Contrato HTTP final de Resumo/revisão: **9 passaram**, incluindo orçamentos SQL,
  visibilidade por unidade e marcador HTML essencial.
- Tokens após correção de foco: **68 passaram**. Ruff final passou.
- Inspeção direta do piloto final: cinco relatórios axe vazios, console limpo, menu por
  Enter, fechamento por Escape, restauração de foco e campo de cópia acima do dock.
- Capturas 360/390/768/1024/1440: zero overflow horizontal e zero rolagem interna do roteiro.
- Consolidado final sobre markup corrigido e halo preservado: **5 casos de teclado**,
  **4 casos longo/vazio** e **18 casos documentais/Baixar/cópia passaram**. O caso CSP
  já diagnosticado foi excluído desta repetição, não declarado aprovado. A suíte Baixar
  contém uma checagem compartilhada de Termos, preservada no log; não houve redesenho
  ou implementação de Termos. Os casos de Folha/cópia são proteções de componente.
- As três direções também passaram em axe, console e overflow nas seis combinações
  de conceito × 360/1440, com relatórios individuais no diretório `direcoes/`.

Avisos não bloqueantes: depreciação HarfBuzz/WeasyPrint e conexão remanescente ao
desmontar alguns bancos TEST locais. Os testes concluíram com código zero. Nada foi
apagado/resetado no PREVIEW; a fonte dos dados continua sendo o LAB isolado.

**Gate integral verde:** script original `scripts/verificar.sh`, sem excluir casos adicionais;
Ruff, 16 contratos de arquitetura, mypy (303 arquivos), Bandit, migrações e tipos JS passaram.
**2.229 testes passaram, zero falhas, 7 avisos, 51min58s de pytest.** Execução em bancos
LAB isolados, quatro workers. Log `reconstrucao-verificar-final.log`, encerrado com
`✔ tudo verde`. O ajuste final de halo também passou nos 68 tokens e nos 5 E2E finais.

As medições pareadas de performance serão registradas após conclusão.
Logs completos, payloads CSP e hashes ficam em `evidencias/oficios-resumo-reconstrucao/`.

## Falhas encontradas e classificação

**Regressão desta reconstrução, corrigida:** marcador literal `class="resumo"` havia sido
alterado ao acrescentar classe de layout. Primeira integral detectou o contrato quebrado;
execução interrompida e preservada. Contêiner de layout separado restaurou o marcador,
sem relaxar o teste. Os 9 focados passaram depois da correção; integral reiniciada.

**Foco da cópia, corrigido:** regra existente de `[readonly]` retirava o halo. Borda de
foco permanecia, mas o indicador completo exigido para teclado foi restaurado na origem.
Verificação final mede sombra, posição acima do dock e foco real nas cinco larguras.

**Preexistente, não bloqueante desta composição:** fallback de cópia gera violações
`style-src-attr` no HTMX. Atual e snapshot `c027493` mostram os mesmos 12 eventos, mesma
fonte vendor, com cópia e axe funcionais. Segurança/CSP e JavaScript estão idênticos à base,
com hashes registrados. Não enfraquecer CSP para fazer teste passar.
Reprodução sobre o código final: novamente **1 teste falhou somente no console**, depois
de seleção, feedback, responsividade e axe passarem. Os mesmos 12 eventos foram confirmados
em `reconstrucao_csp_fechamento.log` e no payload atual arquivado. A ressalva permanece.

**Performance:** classificação pendente da comparação isolada final. Não declarar todos
os orçamentos verdes nem atribuir excesso antigo ao redesenho sem evidência pareada.

Custo estático final comprovado pelo mesmo minificador da aplicação: componente compartilhado
**+6.751 bytes minificados / +910 bytes gzip**. Protótipos do UI Lab: +6.145 / +938 bytes,
em folha carregada apenas no laboratório. Sem nova biblioteca, script ou folha no Resumo.
Os 28 arquivos de fonte alterados têm hashes normalizados em `fontes-validadas.json`.

## Autocrítica e limites

Os controles de anexação mantêm a apresentação operacional existente. Percurso longo e
avisos de assinatura continuam exigindo leitura; não esconder conteúdo para reduzir a tela.
O cabeçalho de registro curto pode deixar espaço livre. A segunda iteração corrigiu os
problemas maiores da primeira: repetição documental, compressão no tablet e percurso em
tabela. O resultado é uma candidata visual, não uma aprovação dada pelo agente.

Próxima proposta: estação de Documentos, **somente após aprovação visual do piloto**.
Lista/Folha e demais módulos não recebem propagação neste bloco. Sem push/merge/deploy.

## Commits e decisão

Pendentes da consolidação. Não commitar candidato com regressão funcional conhecida.
