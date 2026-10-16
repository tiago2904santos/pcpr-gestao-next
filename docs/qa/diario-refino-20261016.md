# Diário de bordo — refino de 16/10/2026

## Observar → entender

Página local: `/viagens/prestacoes/equipe/211/diario/`. Inspeção somente de leitura:
nenhum campo, anexo ou conteúdo do editor do usuário foi alterado.
Antes em `../visual-agents/evidencias/diario-20261016/antes-1440.png` e
`antes-360.png`. O navegador do usuário tem zoom próprio; as capturas exatas
de breakpoint são produzidas separadamente no Chromium dos testes.

Problemas: tabela de sete colunas, recursos em duas linhas largas, explicações
repetidas e fragmento HTML órfão no parcial de horários com ID duplicado.

## Projetar → implementar

Contrato: `../product/prestacao-refinamento-integrado.md`; decisão: ADR 0043.
Receita utilizada: `.claude/skills/nova-tela/SKILL.md`. DOCUMENT com composição
de seções em cartões existentes, linhas de hodômetro, campos, grade e divulgações.
Nenhum componente novo, CSS novo, migração, endpoint ou cálculo modificado.
Cabeçalho identifica o diário compartilhado, sem confundir o status individual
com o documento da equipe. Seletor de servidor mantém a continuidade do fluxo.

O bloco desde `{% if d %}` até o fechamento da seção do editor foi comparado
com HEAD, normalizando apenas CRLF: **idêntico integralmente**.

## Comparar → criticar → corrigir

Leitura visual desktop: recursos lado a lado, rota e agenda junto dos campos,
distância por trecho e totais separados, sem tabela com rolagem horizontal.
Leitura mobile: nomes longos de motorista/viatura estavam truncados pelo estilo
`pessoa__nome`; corrigidos usando tipografia existente sem truncamento.
Datas preservam o ano. Horários têm uma única divulgação e nenhum HTML órfão.

## Testar → validar

- Backend/domínio/editor/tokens: **150 passed** (972,73 s). Arquivos:
  `test_diario.py`, `test_dominio_diario.py`, `test_prestacao.py`,
  `test_prestacao_texto.py`, `test_editor.py`, `test_design_tokens.py`.
- E2E existentes: **5 passed** — motorista/viatura, viagem realizada e autosave
  com foco/continuidade em 360, 768 e 1440 px.
- E2E novos, rodada final: **6 passed** (112,04 s). Capturas + axe em 360/1440,
  sugestões com distância e sem distância, zero inicial, preservação do que foi
  digitado, estado do documento após autosave, consulta e equipe finalizada.
- Ruff global e fronteiras: aprovados. Bandit, migrações e TypeScript executados
  separadamente: aprovados (migrações sem alterações; aviso de banco-base de teste
  inexistente, pois pytest usa os bancos `test_…`). Ruff final do teste novo: aprovado.
- `scripts/verificar.sh` **não ficou verde**: interrompido no mypy por sete erros
  `union-attr` em `gestao/viagens/views_prestacao.py:482`, trecho de pacote de leitura
  alterado em paralelo e fora deste escopo. Não alterado para encobrir a falha.
  A suíte global completa não foi executada; os 150 testes são o recorte acima.

Logs preservados em `../visual-agents/evidencias/diario-20261016/`:
`backend.log`, `verificar.log`, `e2e-inicial.log`, `e2e-final.log`.

As primeiras rodadas dos testes novos revelaram problemas no próprio teste:
distância ausente tratada como zero calculável; expectativa de um título que não
existe no modelo oficial; captura antes da carga do editor. Corrigidos os cenários
e a espera pelo conteúdo real, sem alterar o documento. A auditoria usa o helper
estável já empregado em outras folhas, que mede com a barra fixa em repouso e
restaura o estilo; a posição sticky e a ausência de overflow continuam verificadas
pelos testes funcionais. Nenhuma regra do axe foi desativada.

Banco sintético isolado para backend e outro para navegador. Snapshot local
em `/diario-refino-20261016` no container de QA; sem escrita no PREVIEW/servidor.
A primeira tentativa iniciou antes do término da cópia e não coletou testes
(pacote `gestao`/script ainda ausentes). Repetir somente após finalizar a cópia.

## Comparação visual final e limites

Capturas `depois-360.png` e `depois-1440.png` revisadas, com o editor carregado.
`resultado-local.png` e `resultado-local-completo.png` registram a página 211.
Layout do formulário sem rolagem lateral, rótulos presentes, nomes de recursos
sem corte, horários separados e documento preservado. O status “Pronto para
imprimir” agora também recebe a atualização ao vivo do autosave.

O editor oficial já comprimia a tabela do papel no celular antes desta tarefa
(ver `antes-360.png`). Esse comportamento permanece: o pedido foi preservar o
editor, não redesenhar sua folha. Não declarar o documento mobile corrigido.

O PREVIEW reiniciou durante alterações simultâneas em arquivos Python de outras
tarefas, causando `ERR_EMPTY_RESPONSE` temporário. A revisão final voltou a abrir
a página; não se reiniciaram serviços nem se editaram esses arquivos aqui.

Não houve commit, push ou publicação; mudanças anteriores e concorrentes no
repositório foram preservadas e não fazem parte desta entrega.
