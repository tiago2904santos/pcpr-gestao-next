# Diário de bordo — reconstrução a partir do cadastro de Ofício

## Observar → entender

O usuário rejeitou a composição anterior e indicou expressamente o cadastro de
Ofício como base. A versão rejeitada está em `diario-20261016/resultado-local.png`.
Inspecionados `oficios/editar.html`, seus recursos/itinerário e o cadastro existente
266 no PREVIEW, sem salvar mudanças. O Ofício 258 está emitido e redireciona à
lista; por isso não serve para observar o formulário de cadastro.

Evidências desta revisão: `../visual-agents/evidencias/diario-base-oficio-20261016/`.
`referencia-oficio.png` registra a referência efetivamente aberta.

## Projetar → implementar

Receita `.claude/skills/nova-tela/SKILL.md`, arquétipo FORM com composição própria
para preservar os formulários independentes, decisão revisada no ADR 0043.
Mesmos hero, documento contínuo, seções numeradas, cabeçalhos, conteúdo e rodapé
de preparação usados pelo Ofício. Não adicionar campos de cadastro que não
pertencem ao diário nem modificar dados de negócio.

1. Motorista e transporte: escolhas abertas, campos condicionais junto da escolha,
   sem cartões de resumo duplicados ou painel escondido.
2. Roteiro e quilometragem: ferramentas, campos de hodômetro, conferência e ajuste
   de horários dentro da mesma seção.
3. Documento: editor preservado integralmente. Comparação com a versão anterior
   normalizando apenas CRLF confirmou o mesmo bloco desde `{% if d %}` até seu
   `{% endif %}`. Não alterados editor, folha oficial, PDF, serviços ou endpoints.

Removido o índice horizontal de etapas. Cabeçalho passa a mostrar Ver documento
e o menu de ações; a navegação continua pelo rodapé, conservando `?servidor=`.
Downloads, visão da equipe e retorno à lista continuam no menu existente.

## Comparar → criticar → corrigir

Comparação visual com o Ofício: mesma largura, hero e superfície contínua, divisão
de recursos, numeração e ritmo entre seções. A primeira versão deixava as opções
de transporte quebradas em duas linhas no desktop; corrigidas com escolhas
compactas existentes e rótulos curtos. Nenhum CSS ou componente novo foi criado.

`resultado-local.png` mostra o topo; `resultado-local-completo.png`, a página 211
com o documento carregado. `depois-360.png` e `depois-1440.png` foram revisadas:
formulário sem rolagem horizontal, recursos alinhados, quilometragem com rótulos
e horários no contexto do roteiro. A barra sticky aparece sobre o conteúdo na
captura inteira (posição do viewport), mas acompanha a rolagem normalmente.

O papel do editor ainda comprime a tabela oficial no celular, como já ocorria
antes desta revisão; não foi alterado, por pedido explícito de preservação.

## Testar → validar

- Backend/domínio/documentos/tokens: **150 passed em 910,99 s**, em
  `test_diario.py`, `test_dominio_diario.py`, `test_prestacao.py`,
  `test_prestacao_texto.py`, `test_editor.py` e `test_design_tokens.py`.
- Navegador: **11 passed em 481,91 s**, nos arquivos `test_diario.py`,
  `test_diario_identidade.py` e `test_diario_refino.py`. Edição de km, foco e
  continuidade 360/768/1440, viatura, horários, sugestões sem sobrescrever,
  consulta e trava, editor carregado, axe e capturas 360/1440.
- Revisão estática do bloco do editor: idêntico ao início desta revisão,
  normalizando somente finais de linha. O novo contêiner fica fora desse bloco.
  Também comparado com HEAD: 1.995 caracteres idênticos. Comparação dos nomes
  de campos de motorista/viatura com HEAD: nenhuma diferença.

Edição e testes de navegador apenas em banco sintético isolado no container QA.
PREVIEW usado para leitura; não houve publicação, migração ou mudança de dados.
Ruff, fronteiras (16 contratos), mypy (320 fontes), Bandit, migrações sem novas
alterações e TypeScript passaram. `git diff --check` passou.

A primeira execução global usou os bancos de QA reaproveitados: falhas por
ausência de catálogos iniciais de Plano e por dados esperados no encaminhamento
de Palestras. Foi interrompida após essas falhas para investigar (6 falhas,
43 aprovados, 3 erros). Nova execução iniciada em bancos novos e isolados,
`pcpr_diario_verificacao2_20261016`, com parada na primeira falha. Não se alteraram
fixtures ou outros módulos para encobrir o resultado. Logs preservados ao final.

### Decisão de entrega

O usuário escolheu explicitamente **entregar com os testes focados**, sem aguardar
a suíte global. A segunda execução encerrou com **581 aprovados e 3 avisos**,
sem falhas, em 927,72 s até a interrupção. Foi interrompido apenas o processo
pytest desta tarefa, não os serviços da aplicação.
`scripts/verificar.sh` permanece **pendente**, não é declarado verde. Nenhuma
publicação ou commit foi realizado.

Logs: `backend.log`, `e2e.log`, `verificar-banco-reusado.log` e
`verificar-banco-novo-parcial.log` na pasta de evidências desta revisão.
