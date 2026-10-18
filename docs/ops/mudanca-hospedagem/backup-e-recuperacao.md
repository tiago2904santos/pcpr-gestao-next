# Backup restaurável dos sistemas da VPS — 17/10/2026

Fase 1 da missão de mudança de hospedagem. O pacote cifrado e o inventário com achados de segurança
**não estão neste repositório** (que é público): ficam numa pasta restrita da VPS e seguem para o HD
externo; o local exato, o acesso e a situação da cópia externa estão no inventário privado, dentro do
pacote. A senha de decifragem **não é gravada na VPS** nem no pacote: foi entregue ao usuário à parte.
Aqui fica o método, para repetir e auditar.

## O que foi copiado

| Componente | Conteúdo | Por quê |
|---|---|---|
| Gerenciador de Viagens (sistema real) | banco `viagens_prod`, mídia, árvore do código implantado (commit = GitHub `main`), staticfiles, logs, venv e lista de pacotes, `.env` | recuperar dados e o funcionamento; o `.env` traz `FIELD_ENCRYPTION_KEYS`, sem a qual campos cifrados ficam ilegíveis |
| Eventos Sociais (sistema real) | banco `eventos_sociais`, mídia, árvore implantada (sem Git no servidor), venv, `.env`, os dumps diários que o servidor já guardava | idem; o código implantado difere do GitHub, então a árvore é a fonte |
| Servidor compartilhado | papéis do PostgreSQL, **cópia física do cluster** (pg_basebackup com manifesto), Redis (`dump.rdb`), nginx, systemd, cron, configs de PostgreSQL/Redis/ClamAV, certificados, inventário (pacotes, portas, serviços, docker) | os dois sistemas dividem PostgreSQL, Redis, nginx e certbot; o EV lê o banco e a mídia do GV |
| PREVIEW do PCPR | banco e mídia fictícios, configuração do PREVIEW | barato de guardar; regenerável |
| Histórico opcional | backup antigo de consolidação (jul/2026) que estava em `/root` | não é necessário para recuperar o estado atual |

Excluído (sem dados de negócio, continua na VPS): cópias antigas de código do EV (~5,6 GB), `.git` do GV
(idêntico ao GitHub), caches e imagens Docker do PREVIEW.

## Consistência (ponto de corte sem parar serviços)

Quem grava: usuários (web dos dois sistemas), Celery do GV (geração documental; agendador a cada 10 min),
webhook do EV, worker/importador do PREVIEW. O EV só **lê** o GV.

1. Duas sessões `REPEATABLE READ` exportam snapshots (`pg_export_snapshot`) de `viagens_prod` e
   `eventos_sociais` no mesmo instante (04:42:03 UTC).
2. Com os snapshots abertos, as duas pastas de mídia são congeladas por **hardlinks** (`cp -al`, 0,14 s;
   o Django não reescreve arquivos no lugar, então o congelamento é estável).
3. `pg_dump -Fc --snapshot=…` e as **contagens exatas por tabela** usam esses snapshots: o dump e a
   contagem descrevem o mesmo instante, e todo arquivo referenciado já existia no congelamento.
4. Depois: papéis (`pg_dumpall --globals-only`), cópia física do cluster (pg_basebackup, `-X stream`,
   limitado a 32 MB/s), Redis (`BGSAVE`), configuração.
5. Cada componente tem `SHA256SUMS` interno; é empacotado (`tar | pigz`) e cifrado com OpenPGP simétrico
   AES-256 (S2K SHA-512 iterado, `--rfc4880` para máxima compatibilidade). A senha chega pela entrada
   padrão e não é gravada na VPS. `SHA256SUMS.txt` cobre os arquivos finais.

Tudo com `nice 15`/`ionice idle`; os dois sistemas ficaram no ar (verificado depois: serviços ativos,
302 nos dois domínios, mídia intacta). Duração: 2 min 54 s.

Ferramentas oficiais: `pg_dump`/`pg_basebackup` 16.15 (mesma versão do servidor), Redis 7.0.15, GnuPG 2.4.4.

## Restauração testada (evidência real, não só listagem)

A partir dos **arquivos finais cifrados**, na própria VPS, isolada:

- PostgreSQL 16.15 em contêiner `--network none`, acessível só por socket unix numa pasta root 0700.
- As aplicações rodam com o **código e o venv extraídos do pacote** dentro de `unshare -n` (namespace sem
  rede — nem loopback): Drive em mock, e-mail no console, sem broker, sem workers/agendador; Redis vazio e
  isolado só para o cache. Uma conexão externa de teste é recusada antes de subir cada app.
- Nada de `migrate`: só `migrate --check`.

| Verificação | GV | EV |
|---|---|---|
| SHA-256 e decifragem dos arquivos finais | ✅ | ✅ |
| `pg_restore` sem erros; contagens = snapshot em todas as tabelas | ✅ 85 tabelas | ✅ 137 tabelas |
| FKs recriadas e validadas (= índice do dump) | ✅ 174 | ✅ 253 |
| Sequências à frente do maior id | ✅ 81 | ⚠️ 1 atrás — **idêntica na produção** (tabela de configuração de uma linha) |
| Cópia física: `pg_verifybackup`, recuperação pelo WAL, contagens | ✅ | ✅ |
| Redis: fila restaurada igual à origem | ✅ | — |
| `manage.py check` / `migrate --check` | ✅ / sem pendências | ✅ / sem pendências |
| Arquivos referenciados pelos registros presentes | ✅ 1037/1037 | ✅ 746/746 (inclui mídia do GV lida pelo EV) |
| PDFs abertos com pypdf | ✅ 907 | ✅ 653 |
| Campos cifrados lidos com a chave do pacote | ✅ | — |
| Páginas lidas como superusuário (test client) | ✅ 59, nenhum 500 | ⚠️ 84, um 500 em `/agenda/escala/` — **defeito preexistente** (51 ocorrências no log de produção) |
| gunicorn servindo pelo socket (GET / e tela de entrada) | ✅ 302 → 200 | ✅ 302 → 200 |
| Permissões do EV para ler o GV | — | ✅ SELECT em 85 tabelas |

A decifragem do arquivo final também foi conferida no Windows (gpg do Git Bash, por fluxo, sem gravar em
disco). Depois do teste, todo texto claro (área de preparo e restauração) foi apagado da VPS.

## As cinco situações (não confundir)

| Situação | Como se comprova |
|---|---|
| 1. Backup gerado | arquivos finais + `MANIFESTO.txt` + `SHA256SUMS.txt` |
| 2. Restauração testada | `RELATORIO-VALIDACAO.txt` (resumo acima) |
| 3. Disponível para download | cópia por SCP com a chave SSH do administrador; nenhuma URL pública |
| 4. Cópia fora da VPS confirmada | SHA-256 conferidos no computador de destino |
| 5. Cópia no HD externo conferida | SHA-256 conferidos de novo, lendo do HD |

Em 17/10/2026 as situações 1–3 foram concluídas; o andamento de 4 e 5 é registrado só no inventário
privado. **Regra:** enquanto 4 e 5 não estiverem confirmados com SHA-256, nenhuma operação destrutiva na
VPS (reinstalar, trocar template, formatar, excluir volumes).

## Baixar e conferir no Windows

Usuário, host e pasta reais: ver o inventário privado e o `RESTAURAR.md` do pacote.

```powershell
scp -r <usuario>@<host-da-vps>:<pasta-do-pacote> E:\PCPR-Backups\
cd E:\PCPR-Backups\<nome-do-pacote>
Get-Content SHA256SUMS.txt | ForEach-Object { $h,$f = $_ -split '\s+',2; $f=$f -replace '^\./',''; $r=(Get-FileHash $f -Algorithm SHA256).Hash; '{0}  {1}' -f ($(if ($r -eq $h.ToUpper()) {'OK   '} else {'ERRO '}), $f) }
```

(`E:` = letra do HD externo; exFAT ou NTFS.) Teste de abertura: `gpg --decrypt 03-servidor-compartilhado.tar.gz.gpg | tar -tzf - | head`.

## Atualidade e cópia final do dia da mudança

Este pacote protege os dados até 17/10/2026 04:42 UTC. Para a mudança, `ferramentas/30-atualizacao-final.sh`
(preparado, **não executado**) faz a cópia definitiva com ponto de corte por parada dos gravadores:

1. para o agendador do Celery e espera a fila padrão esvaziar (até 10 min);
2. para as duas aplicações e os workers (SIGTERM: a tarefa em curso termina) e confere que nenhuma
   conexão das aplicações ficou no PostgreSQL;
3. roda o mesmo backup e a mesma restauração-teste;
4. deixa os serviços **parados** (a VPS antiga não aceita mais gravações) até o pacote ser baixado e
   conferido fora dela; `--religar` desfaz se a mudança for adiada.

Janela estimada: 10–15 min com os sistemas indisponíveis (parada ≤ 2 min, backup ≈ 3 min, teste ≈ 3 min),
mais o download de ~1,6 GB, que depende da conexão do usuário (≈ 5 min a 50 Mbit/s). Pendências
operacionais dos sistemas a decidir antes da janela estão no inventário privado.
