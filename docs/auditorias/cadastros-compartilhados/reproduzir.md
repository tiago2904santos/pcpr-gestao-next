# Reproduzir a validação em LAB

O aceite final é o **verificador integral no LAB Docker**, com 2.816 aprovados,
saída zero e conversão/OCR reais. Siga o [ambiente Linux](ambiente-linux.md) para
reproduzir a cópia isolada, as dependências e o comando intacto. O manifesto e as
conferências de hashes estão vinculados no [relatório](relatorio.md).

As instruções Windows abaixo registram os lotes locais de backend/navegador e a
rodada anterior. Elas exigem iniciar novamente o cluster próprio, atualmente
parado; para obter o verificador inteiro verde no Windows também é necessário
disponibilizar LibreOffice/Tesseract no PATH do subprocesso.

Os comandos desta missão usam um cluster descartável próprio, separado do banco
DEV configurado no `.env`. Não remova as variáveis de conexão ao repetir os testes.
Não é necessário migrar a base operacional para executar pytest: ele cria bancos
de teste e aplica as migrações neles.

## Conexão local usada nos lotes Windows

Em PowerShell, na raiz do repositório:

```powershell
$env:PYTHONUTF8 = '1'
$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = '55433'
$env:POSTGRES_USER = 'cadastros_lab'
$env:POSTGRES_PASSWORD = ''
$env:POSTGRES_DB = 'pcpr_verificar_final_local_lab'
$env:PYTEST_XDIST_AUTO_NUM_WORKERS = '2'
& 'C:\Program Files\Git\bin\bash.exe' scripts/verificar.sh
```

O cluster final PostgreSQL 18 fica em
`C:\Users\tiago\AppData\Local\Temp\pcpr-cadastros-lab-20261017-final`,
fora da pasta sincronizada, com log `servidor.log` nessa pasta. O cluster inicial
em `var/cadastros-postgres`/porta 55432 foi parado antes da recriação. Seu acesso
trust é local e sua durabilidade foi
reduzida exclusivamente para testes descartáveis (`fsync`, `synchronous_commit`
e `full_page_writes` desligados). Essa configuração não é referência de produção.
Para confirmar o estado, use `pg_ctl status -D` com o diretório final acima.
Ao iniciar por `Start-Process`, use `-WindowStyle Hidden` e aguarde somente
`$processo.WaitForExit()` do `pg_ctl`; `Start-Process -Wait` aguarda também o servidor
descendente, que deve permanecer em execução. Não altere outro serviço PostgreSQL.

A limpeza opcional do cluster inicial confirmou caminho absoluto, ausência de
reparse point, `PG_VERSION=18` e `pg_ctl status` sem servidor. Mesmo assim, a
exclusão foi bloqueada por política da revisão automática; a pasta inicial ficou
preservada e parada. Nenhuma tentativa de contornar esse bloqueio foi feita.

### Estatísticas após carga sintética

A rodada inicial do verificador foi interrompida em 28%, sem falha de teste
registrada, após diagnosticar estatísticas de tabela vazia para os 5.571 municípios
recarregados pelo cenário. O plano escolhia duas varreduras completas de municípios
antes de relacionar os trechos; uma consulta observada ultrapassou dois minutos.
Após `ANALYZE cadastros_municipio`, o plano passa a procurar origem e destino pelas
respectivas PKs (`Index Cond`). Os planos finais estão em
[ambiente-estatisticas.log](ambiente-estatisticas.log).

`gestao/viagens/tests/cenarios.py` agora atualiza essas estatísticas imediatamente
após garantir a carga sintética, tanto nos testes como em `semear_dev`. O helper de
carga utilizado pelas migrações e a consulta da aplicação não foram alterados.
Os testes foram reiniciados com esse cenário e os arquivos finais. O log anterior
foi preservado em `verificar-antes-estatisticas.log`; ele não é resultado de aceite.
A rodada posterior com dados ainda na pasta sincronizada foi preservada em
`verificar-onedrive.log`. A validação final foi reiniciada por inteiro no cluster
temporário local, com todos os ajustes de código já presentes e dois workers.

A rodada final também encontrou contenção na estação: uma leitura do sistema
mostrou CPU em 100% e cerca de 648 MiB de memória física livre. Duas inspeções
dos workers confirmaram construção/limpeza de cenários e sincronização de papéis
após `flush`, sem evidência de chamada externa presa. Os registros
`diagnostico-worker-*.log` são diagnósticos de andamento, não resultados de testes.
A aplicação e as regras de permissão não foram alteradas para acelerar a suíte.

### Encerramento da rodada Windows

O verificador completo terminou com 2.813 aprovados e três falhas de ambiente:
conversão DOCX e dois cenários de OCR real não encontraram `libreoffice` ou
`tesseract` pelo PATH do subprocesso. O log foi preservado em
[verificar-windows.log](verificar-windows.log). Não houve falha de domínio ou
permissão nessa rodada; ela não equivale a verificador verde.

O servidor LAB Windows da porta 55433 foi encerrado com `pg_ctl -m fast -w stop`,
e seu estado parado confirmado. A repetição integral usa um LAB Docker separado,
com os conversores reais já presentes na imagem local do projeto; o código dos
testes e da aplicação não foi adaptado para ignorar as dependências ausentes.

## Navegador e contratos

Mantendo as variáveis locais acima, use um nome de banco diferente por execução
concorrente. As rodadas finais limitaram concorrência para reduzir contenção de
memória e não confundir demora de infraestrutura com comportamento do produto.

```powershell
$env:POSTGRES_DB = 'pcpr_ui_final_local_lab'
$env:CADASTROS_FASE = 'depois'
uv run pytest tests/e2e/test_cadastros_missao.py -n 2 -q
```

Esse arquivo registra as 32 listas e 18 modais em 360/1440, cadastro auxiliar sem
perda de contexto, inclusão em sequência, identidade comum Plano/Eventos, seis
catálogos de Eventos e termo aditivo/contrato Coffee. Os demais cenários e comandos
ficam nos testes/relatórios de [unidade](unidade.md), [ASCOM](ascom-validacao.md)
e [catálogo/fonte](catalogo.md), e no [relatório geral](relatorio.md).

O teste de migração `gestao/cadastros/tests/test_migracao_catalogo.py` aplica os
estados reais com homônimos, inativos, FKs/M2M, snapshots, permissões de grupo e
permissões diretas. A migração conserva o legado e o mapa para recuperação; após
novos usos a reversão requer reconciliação explícita, conforme ADR 0044.

Os dados são sintéticos. Nenhum comando desta missão publicou a aplicação,
conectou uma fonte dedicada ou executou migrações em produção.
