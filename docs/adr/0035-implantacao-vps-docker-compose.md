# ADR 0035 — Implantar em VPS com Docker Compose por instância, a partir de commit aprovado

- **Status:** proposto · **Data:** 2026-10-13

## Contexto
O sistema precisa de homologação (dados sintéticos) e, depois de autorizada, produção numa
VPS (Hostinger) que pode já hospedar outros serviços. O produto já define a imagem
(`Dockerfile` da raiz), o PREVIEW (ADR 0011), a auditoria pelo banco (ADR 0004) e a outbox
transacional no PostgreSQL (ADR 0005). Faltava decidir como rodar tudo isso fora do CI sem
mexer no produto e sem pôr em risco o que já existe no servidor. A validação está em
`docs/ops/implantacao-vps-evidencias.md` (VPS simulada).

## Decisão
Toda a implantação fica em `deploy/`, separada do código do produto:

1. **Uma instância = um projeto Docker Compose** (`pcpr-<instância>`): PostgreSQL 16.15
   fixado por digest, web (gunicorn) e worker da outbox (`processar_outbox`, LISTEN/NOTIFY)
   — sem fila externa: a outbox continua no próprio banco (ADR 0005).
2. **Rede e portas:** o banco fica numa rede `internal`, sem porta publicada; a web publica só
   em `127.0.0.1`. Um proxy (Caddy compartilhado com HTTPS automático, ou o Nginx que já
   existir no host) é a única entrada pública e nunca serve `/media` (documentos só pelas
   views, com autorização por objeto).
3. **Papéis no banco** (docs/ops/banco.md): `pcpr_owner` só nas migrações; `pcpr_app` na
   aplicação e no worker (auditoria só INSERT/SELECT); `pcpr_leitura` somente leitura; o
   superusuário do cluster só para administração e backup.
4. **Armazenamento:** dados e documentos em bind mounts por instância (`/srv/pcpr/<inst>`),
   segredos em `/etc/pcpr/<inst>/*.env` (0600, fora do Git); contêineres com raiz somente
   leitura, uid dedicado 10001, `cap_drop: ALL` e `no-new-privileges`.
5. **Versão:** implanta-se um SHA de 40 caracteres, nunca uma branch. A imagem do produto
   vem de `git archive <sha>` com o `Dockerfile` da raiz sem alterações, e uma camada fina
   (`deploy/docker/`) acrescenta só a entrada, o health check e os rótulos de versão.
6. **Dados reais** (qualquer instância cujo `app.env` não seja `config.settings.preview` com
   `APP_ENV=preview`, independentemente do nome) exigem o commit em `aprovados.txt`,
   proíbem `--sem-backup` e `--semear`, e usam a mesma imagem do produto já testada na
   homologação do host (o `Dockerfile` parte de uma tag móvel; reconstruir é decisão
   explícita).
7. **Migrações:** backup validado antes; com migração pendente, web e worker param durante a
   migração (janela curta) — o código antigo nunca roda contra um schema novo ou parcial.
8. **Backup:** `pg_dump` validado + cópia externa criptografada (restic), com restauração-teste
   isolada e periódica (cadeia de auditoria e SHA-256 dos PDFs conferidos).

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Kubernetes / orquestrador gerenciado | Uma VPS só; custo operacional e de aprendizado sem ganho para o volume esperado |
| Serviço gerenciado de banco ou fila | Contratação adicional; a outbox no PostgreSQL já atende (ADR 0005) |
| Implantar a branch `main` | Não é imutável nem garantidamente estável; impede saber o que está no ar |
| Alterar o `Dockerfile` do produto para a VPS | Mistura infraestrutura com produto; a camada fina basta |
| Banco publicado na porta 5432 | Superfície de ataque sem necessidade; as tarefas usam o próprio compose |

## Consequências
- Positivas: instâncias isoladas entre si e dos serviços existentes; o que está no ar é
  rastreável até o commit; reversão por imagem anterior sem rebuild; recuperação ensaiada.
- Negativas: migrações causam uma janela curta de indisponibilidade; a atualização de
  segurança da imagem base exige um novo ciclo de homologação; uma VPS é ponto único de
  falha (mitigado pela cópia externa e pelo procedimento de perda total).
- Obrigatório: rodar `deploy/vps/diagnostico.sh` antes de qualquer mudança na VPS; produção
  só com autorização registrada (`deploy/PRODUCAO.md`); `DEMO_MODE` nunca fora do PREVIEW
  (ADR 0011); logs (aplicação, Gunicorn e proxy) nunca registram o token do feed ICS.
