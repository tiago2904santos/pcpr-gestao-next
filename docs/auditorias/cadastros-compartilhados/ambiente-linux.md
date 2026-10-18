# Verificador integral em LAB Linux isolado — 17/10/2026

Objetivo: executar o `scripts/verificar.sh` atual por inteiro, sem alterar código,
testes, filtros ou skips, com LibreOffice, Poppler e Tesseract reais. A rodada Windows
ficou preservada em `verificar-windows.log`; três testes nativos não encontravam
executáveis nesse ambiente.

## Isolamento e insumos

- Base local: `pcpr-gestao:importacao-20261016`, ID
  `sha256:cb4b9471ee9277ba416745ad43d5688021cfe016cde75db7e2185d05c4cd203e`.
- PostgreSQL 16 local em cache, ID
  `sha256:1a6ab3f5345eb6dbe04a1349529caabdb0ab09293a09590fad07b2246bfa4b54`.
- Imagem derivada `cadastros-lab-20261017:verificador`; rede Docker **interna**
  `cadastros-lab-20261017`; PG próprio `cadastros-lab-20261017-pg`, sem portas
  publicadas. Usuário/banco exclusivos `cadastros_lab`, autenticação trust apenas
  nessa rede descartável, sem credenciais ou dados de operação.
- PGDATA em tmpfs de 2 GiB, com `fsync=off`, `synchronous_commit=off` e
  `full_page_writes=off`; adequado somente ao LAB descartável.
- Contexto de build em `%TEMP%/cadastros-lab-20261017-build`, contendo somente
  Dockerfile, locks e manifestos de dependências. Nenhum container/serviço existente
  foi modificado, reiniciado ou conectado a essa rede.
- SHA-256 de `uv.lock`:
  `B5E897CBDB4F847B597B52F10CB5F32E6086F5F8559C5529BA63EB08EAB8B85B`.
- SHA-256 de `package-lock.json`:
  `81B0FC8B62877C3C122ABC11A55592A132BB03E048E2DB306F7141309EEFD804`.

Inspeção anterior ao build confirmou Python 3.13.16, uv 0.8.17, LibreOffice,
`pdftoppm` e Tesseract com idiomas `por`, `eng` e `osd`. A imagem não continha as
dependências de desenvolvimento nem Node/npm. A derivada instala esses componentes
sem alterar a `.venv` ou o `node_modules` do Windows.

## Comandos de preparação

```dockerfile
FROM pcpr-gestao:importacao-20261016
USER root
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=0 UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm git fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp/cadastros-deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY package.json package-lock.json /opt/cadastros-js/
RUN npm ci --prefix /opt/cadastros-js --ignore-scripts --no-audit --no-fund
WORKDIR /app
ENTRYPOINT ["/bin/bash"]
```

```powershell
docker build --progress=plain --tag cadastros-lab-20261017:verificador "$env:TEMP/cadastros-lab-20261017-build"
docker network create --internal cadastros-lab-20261017
docker run -d --name cadastros-lab-20261017-pg --network cadastros-lab-20261017 --tmpfs /var/lib/postgresql/data:rw,nosuid,size=2147483648 -e POSTGRES_USER=cadastros_lab -e POSTGRES_DB=cadastros_lab -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16 -c fsync=off -c synchronous_commit=off -c full_page_writes=off
docker exec cadastros-lab-20261017-pg pg_isready -U cadastros_lab -d cadastros_lab
```

A inspeção de portas retornou `PortBindings={}` e `5432/tcp=null` (nenhuma porta
publicada). Node 20.19.2/npm 9.2.0 instalados pelo Debian geraram somente aviso de
engine para pdfjs-dist (seu código Node não é executado por este verificador);
TypeScript é instalado pelo lock, e a verificação de tipos continua integral.

## Isolamento da cópia de validação

A primeira tentativa, com o workspace diretamente em `/app`, encerrou no Ruff com
25 erros em `docs/automacao/prototipo/`, trabalho alheio à missão acrescentado durante
sua execução. Não houve alteração nesses arquivos, no verificador ou nos filtros.
Seu log foi preservado como `verificar-linux-antes-isolamento.log`, com saída 1.

A execução final monta o workspace **somente leitura** em `/workspace` e uma cópia
isolada em `/tmp/cadastros-src`. O inventário é obtido por:

```bash
git -c safe.directory=/workspace ls-files --cached --others --exclude-standard -z
```

Cada arquivo versionado atual e cada untracked da missão é copiado pelo conteúdo
atual, com SHA-256 registrado em `snapshot-linux.json`. Somente arquivos **não
versionados** dos seguintes prefixos são omitidos da cópia:

- `docs/automacao/`: trabalho alheio à missão.
- `docs/ops/mudanca-hospedagem/`: trabalho alheio à missão.
- `%SystemDrive%/`: artefatos locais de runtime do Windows (caches), sem atribuição
  de autoria.

Esses conteúdos permanecem no workspace original. Arquivos ignorados pelo Git,
incluindo `.env`, `.venv`, `node_modules` e `var`, não integram a cópia. Não há
checkout/reset nem remoção de alterações locais. O manifesto contém caminhos,
hashes, tamanhos, origem tracked/untracked e hash agregado da cópia.

## Execução

São definidos explicitamente `DJANGO_SETTINGS_MODULE=config.settings.test`,
`APP_ENV=test`, `POSTGRES_HOST=cadastros-lab-20261017-pg`, `POSTGRES_PORT=5432`,
`POSTGRES_USER=cadastros_lab`, `POSTGRES_DB=cadastros_lab`, senha vazia somente do LAB
trust e chave sintética local. O venv é `/opt/venv`; a execução final usa
`/tmp/cadastros-src-exec`, com `node_modules` apontando para as dependências
instaladas em `/opt/cadastros-js/node_modules`. Caches de pytest, mypy, ruff, uv, npm e Hypothesis
ficam em `/tmp`, sem bytecode no workspace. `UV_FROZEN=1` e `UV_OFFLINE=1` mantêm o
lock e impedem downloads durante os testes; dependências já foram instaladas no build.

`PYTEST_XDIST_AUTO_NUM_WORKERS=2` limita o `-n auto` já presente no script. Não há
`--lf`, exclusão de testes nativos ou filtro adicional. A chamada efetiva é:

```bash
bash scripts/verificar.sh
```

O runner apenas registra versões/hashes, encaminha stdout/stderr integralmente para
`verificar-linux.log`, preserva o status da chamada e acrescenta `VERIFICAR_EXIT`.
O resultado final e o encerramento do LAB estão registrados abaixo.

Imagem derivada final:
`sha256:1e4ef36010a2801089a57f2f955c3f3c68ad237682ce12a1f4cce3f9457d1e84`.
O snapshot contém **8.461 arquivos**, dos quais **8.033 versionados**, somando
**1.069.730.684 bytes**. Foram omitidos 34 arquivos untracked dos três prefixos
declarados; nenhum arquivo versionado foi excluído por esses prefixos.

- Hash agregado de caminhos/conteúdos:
  `e321303e40a27e9d57eaa3ed1edd92883acef67bf63db580a03f5cac7bebf5ac`.
- SHA-256 do manifesto JSON completo:
  `92331e4bf8dc207e80493c93c9ab65f12899a3868b22c42c783742b6d6c42b6e`.
- SHA-256 de `scripts/verificar.sh`, executado intacto:
  `7303c6f5157e2bb8790ba4305daee9714a5de5b8dac6b25baa3c8a6bd2580d02`.

Comando de criação do container reutilizado na execução final (PowerShell; `$repoDir` aponta ao workspace e
`$buildDir` à pasta temporária descrita acima):

```powershell
$auditDir = Join-Path $repoDir 'docs/auditorias/cadastros-compartilhados'
$dockerArgs = @(
  'run', '--name', 'cadastros-lab-20261017-verificador',
  '--network', 'cadastros-lab-20261017', '--cpus', '4',
  '--mount', "type=bind,source=$repoDir,target=/workspace,readonly",
  '--mount', "type=bind,source=$auditDir,target=/logs",
  '--mount', "type=bind,source=$buildDir\executar-snapshot.sh,target=/lab-executar.sh,readonly",
  '--mount', "type=bind,source=$buildDir\snapshot.py,target=/lab-snapshot.py,readonly",
  '--tmpfs', '/tmp/cadastros-src/node_modules:rw,nosuid,size=536870912',
  '--tmpfs', '/tmp/cadastros-src/var:rw,nosuid,size=1073741824',
  '--tmpfs', '/tmp/cadastros-src/.import_linter_cache:rw,nosuid,size=134217728',
  '-e', 'DJANGO_SETTINGS_MODULE=config.settings.test', '-e', 'APP_ENV=test',
  '-e', 'DJANGO_SECRET_KEY=lab-descartavel-20261017-chave-exclusiva-nao-operacional-93j6gl2z',
  '-e', 'DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver',
  '-e', 'POSTGRES_HOST=cadastros-lab-20261017-pg', '-e', 'POSTGRES_PORT=5432',
  '-e', 'POSTGRES_USER=cadastros_lab', '-e', 'POSTGRES_PASSWORD=',
  '-e', 'POSTGRES_DB=cadastros_lab', '-e', 'UV_PROJECT_ENVIRONMENT=/opt/venv',
  '-e', 'UV_COMPILE_BYTECODE=0', '-e', 'UV_OFFLINE=1', '-e', 'UV_FROZEN=1',
  '-e', 'UV_CACHE_DIR=/tmp/uv', '-e', 'PYTHONDONTWRITEBYTECODE=1',
  '-e', 'PYTHONUNBUFFERED=1', '-e', 'PYTEST_XDIST_AUTO_NUM_WORKERS=2',
  '-e', 'PYTEST_ADDOPTS=-o cache_dir=/tmp/pytest-cache --basetemp=/tmp/pytest',
  '-e', 'MYPY_CACHE_DIR=/tmp/mypy', '-e', 'RUFF_CACHE_DIR=/tmp/ruff',
  '-e', 'HYPOTHESIS_STORAGE_DIRECTORY=/tmp/hypothesis',
  '-e', 'NPM_CONFIG_CACHE=/tmp/npm', '-e', 'XDG_CACHE_HOME=/tmp/cache',
  'cadastros-lab-20261017:verificador', '/lab-executar.sh'
)
& docker @dockerArgs
```

## Correção restrita ao ambiente de execução

A segunda tentativa passou Ruff, os 16 contratos, mypy, Bandit e a checagem de
migrações, mas o `npx tsc` encerrou com saída 126: `Permission denied`. O mount
Docker `tmpfs` de `node_modules` tinha `noexec`; a mesma versão TypeScript 6.0.2
executou normalmente em `/opt/cadastros-js/node_modules`. Essa tentativa permanece
em `verificar-linux-node-noexec.log`.

O snapshot existente foi reaproveitado por uma cópia **local Linux**, sem nova
leitura do workspace Windows. Somente a pasta de dependências geradas passou a
ser um symlink para `/opt`; o script e o código mantêm os mesmos bytes. O container
parado foi reiniciado com o runner atualizado, cujo início é:

```bash
set -euo pipefail
if [ ! -f /tmp/cadastros-src-exec/scripts/verificar.sh ]; then
  cp -a /tmp/cadastros-src /tmp/cadastros-src-exec
  rmdir /tmp/cadastros-src-exec/node_modules
  ln -s /opt/cadastros-js/node_modules /tmp/cadastros-src-exec/node_modules
fi
cd /tmp/cadastros-src-exec
bash scripts/verificar.sh
```

```powershell
Copy-Item docs/auditorias/cadastros-compartilhados/verificar-linux.log docs/auditorias/cadastros-compartilhados/verificar-linux-node-noexec.log
docker start -a cadastros-lab-20261017-verificador
```

A sessão dessa execução integral é `56535`, iniciada às `2026-10-17T06:32:48Z`.
O runner captura a saída via `tee`, preservando o status original com
`${PIPESTATUS[0]}`. A conferência independente em `verificacao-snapshot.json`
comparou 1.374 arquivos de código, recursos e dependências com o workspace e
registrou zero divergências. Nenhum código ou teste de produto foi alterado para
acomodar Linux ou as ferramentas nativas.

A conferência da pasta efetivamente executada, em `verificacao-copia-linux.json`,
recalculou SHA-256 de todos os 8.461 arquivos do manifesto às
`2026-10-17T06:38:23.701331+00:00`: **zero divergências**. O symlink de dependências
resolve para `/opt/cadastros-js/node_modules`. Essa verificação foi somente leitura.

## Resultado integral e encerramento

**Verificador verde, código de saída 0.** A chamada original de
`scripts/verificar.sh` concluiu todas as etapas: Ruff, 16 contratos de importação,
mypy (325 arquivos), Bandit, ausência de migrações pendentes de geração, tipos
JavaScript e pytest com dois workers. Resultado do pytest: **2.816 aprovados,
5 warnings, 2.896,67 s (48 min 16 s)**. Não houve skips ou falhas. Os três testes
nativos que falharam por indisponibilidade de executáveis no Windows foram
executados e aprovados nesta suíte com LibreOffice, Poppler, Tesseract `por`/`eng`
e fonte DejaVu reais.

O log registra início em `2026-10-17T06:32:48Z`, fim em
`2026-10-17T07:21:25Z`, `✔ tudo verde` e `VERIFICAR_EXIT=0`.
Os cinco warnings do pytest são três depreciações de pypdf e dois avisos de
paginação de querysets sem ordenação em Viagens; não são falhas desta missão.
Não houve alteração de produto, de teste, do script, de filtros ou de skips para
obter o resultado.

Evidências preservadas no workspace antes da remoção dos containers:

- `verificar-linux.log`: saída integral final; SHA-256
  `eff2753f7dbd33cb35e2bd6b64337a3f9c892e67166684b7eabaff2b92127e89`.
- `snapshot-linux.json`: inventário de origem com SHA-256 de cada arquivo.
- `verificacao-snapshot.json`: comparação independente com o workspace.
- `verificacao-copia-linux.json`: confirmação dos 8.461 arquivos executados,
  sem divergências; SHA-256
  `5a9441a7325854d17f8b9abfcb3b90fd39524215774c5a92e060d86121f0c0f4`.
- `verificar-linux-antes-isolamento.log`: primeira tentativa, encerrada no Ruff
  por arquivos de outra tarefa, preservados no workspace.
- `verificar-linux-node-noexec.log`: segunda tentativa, encerrada pelo mount
  `noexec` da dependência gerada, antes dos testes.

Após confirmar o status 0 do container e a persistência das evidências, o PG foi
encerrado e somente os três containers e a rede próprios foram removidos:

```powershell
docker stop cadastros-lab-20261017-pg
docker rm cadastros-lab-20261017-verificador cadastros-lab-20261017-antes-isolamento cadastros-lab-20261017-pg
docker network rm cadastros-lab-20261017
docker ps -a --filter name=cadastros-lab-20261017 --format '{{.Names}} {{.Status}}'
docker network ls --filter name=cadastros-lab-20261017 --format '{{.Name}}'
docker image inspect cadastros-lab-20261017:verificador --format '{{.Id}}'
```

Às `2026-10-17T07:21:41.7194222Z`, as consultas de containers e rede retornaram
listas vazias. A imagem derivada permaneceu disponível com o mesmo ID
`sha256:1e4ef36010a2801089a57f2f955c3f3c68ad237682ce12a1f4cce3f9457d1e84`
para reprodução. Nenhum prune foi executado e nenhum outro objeto Docker foi
alterado. O PGDATA sintético estava no tmpfs do container removido; não restou
serviço ou porta do LAB em execução.
