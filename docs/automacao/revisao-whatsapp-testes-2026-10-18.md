# Revisão do plano — WhatsApp principal no sistema de testes

## Observação e entendimento

Em 18/10/2026 o usuário esclareceu que o site não é oficial da polícia, não vai operar com
policiais e é apenas um sistema de testes. Solicitou WhatsApp Business como canal principal.
O plano anterior aplicava a esse projeto a restrição de uma implantação institucional policial.

## Projeto e implementação documental

- Regra em `docs/product/automacao-whatsapp-testes.md`, antes de qualquer implementação futura.
- ADR 0046 com a decisão de canal e isolamento do LAB em relação ao PREVIEW/DEMO.
- Plano e viabilidade revisados; resumo e contrato alinhados ao cenário independente.
- Documentos de 17/10 identificados como histórico quando falam de uso policial bloqueado.
- Exemplo de `/estado` para o piloto desligado, sem credenciais ou ativação real.

## Comparação e crítica

Antes: e-mail/portal sustentavam a operação e WhatsApp oficial aguardava uma autorização
institucional excepcional. Depois: WhatsApp Cloud API é principal no piloto; portal é apoio,
e-mail opcional; onboarding normal e ensaio em LAB são as dependências externas.

O envio manual passa a contingência. A consulta policial WA-2 deixa de ser pré-requisito do
piloto. Os testes anteriores continuam sendo contra simuladores; não se declara integração
real concluída. PREVIEW público continua sem mensagens externas. Contatos dos testadores
podem ser reais e, por isso, verificação, opt-in e retenção continuam necessários.

## Validação

- **Validação documental aprovada:** YAML OpenAPI carregado; 97 referências internas resolvidas;
  38 JSONs de contrato/exemplos lidos; exemplo do piloto com chave geral e fluxos desligados,
  WhatsApp desligado na entrada/saída e ambiente `teste`; oito workflows exportados continuam
  inativos; 57 links locais dos documentos centrais resolvidos; notas de escopo conferidas.
- **Comparação:** `git diff --check` dos dois documentos de produto versionados sem erros de
  whitespace; alterações nos demais arquivos da aplicação já existentes no workspace preservadas.
- **`scripts/verificar.sh`:** ruff aprovado; 16 contratos de fronteiras mantidos; mypy sem
  erros em 325 arquivos; bandit sem falha (avisos sobre comentários `nosec`); migrações e tipos
  JavaScript passaram. A suíte pytest encontrou erros de preparação de banco e a execução
  ampla foi interrompida após confirmar a causa em um teste isolado.
- **Reprodução da limitação:** `.venv/Scripts/python.exe -m pytest
  gestao/cadastros/tests/test_crud.py -x -n 0 -q` encerrou com um erro de setup:
  `psycopg.errors.InsufficientPrivilege` ao tentar criar `test_pcpr_gestao` (permissão negada
  ao criar banco). Nenhuma permissão ou configuração de banco foi alterada. Portanto,
  **a verificação geral não está verde** neste ambiente; a validação documental passou.
- Não há telas, regras executáveis ou workflows modificados nesta revisão; testes de navegador
  e capturas 360/1440 não se aplicam à alteração documental. Suítes do protótipo não foram
  reexecutadas: os resultados anteriores permanecem identificados como evidência histórica.
