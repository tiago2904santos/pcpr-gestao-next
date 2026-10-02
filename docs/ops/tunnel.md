# Tunnel — abrir o sistema local no celular (URL pública HTTPS)

Para olhar uma tela no telefone, mostrar para alguém ou testar o layout em 360px num aparelho
real, sem publicar nada. O tunnel só encaminha a porta local: o código, o banco e os dados
continuam na sua máquina.

> Dados fictícios apenas (DEV ou PREVIEW). Nunca aponte um tunnel para base real — ver
> "Segurança" no fim.

## Opção 1 — `scripts/tunnel.ps1` (Windows, recomendado)

```powershell
.\scripts\tunnel.ps1
```

O script faz tudo:

1. Instala o `devtunnel` se faltar (`winget install Microsoft.devtunnel`; se o winget não
   resolver, baixa o executável para `var\ferramentas\devtunnel.exe`). **Não precisa de
   Node.js, npm nem Docker.**
2. Pede login no DevTunnels (Microsoft ou GitHub) na primeira vez — a credencial fica no
   perfil do Windows.
3. Cria o tunnel persistente `pcpr-gestao` com a porta 8000. Por ser persistente, a URL é
   **sempre a mesma** (`https://pcpr-gestao-8000.<cluster>.devtunnels.ms`).
4. Exporta `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` e `DJANGO_ATRAS_DE_PROXY`
   (sem isso o Django recusa o host e o login falha no CSRF).
5. Abre duas janelas — `runserver` e o worker da outbox — e hospeda o tunnel em primeiro
   plano. **Ctrl+C encerra os três.**

| Opção | Para que serve |
|---|---|
| *(padrão)* | URL pública: quem tem o link entra (só o login do sistema protege) |
| `-Privado` | A URL exige login Microsoft/GitHub do dono do tunnel antes de chegar ao Django |
| `-SemServidor` | O servidor já está rodando em outra janela (ex.: PREVIEW) — só abre o tunnel |
| `-SemWorker` | Sem o worker da outbox (não gera PDF) |
| `-Porta 8001` | Outra porta local |
| `-Remover` | Apaga o tunnel `pcpr-gestao` da conta |

Com o DEV no ar, entre com `operador` / `senha-local-123`.

### Expondo o PREVIEW (entrada sem senha) em vez do DEV

```powershell
scripts/preview.sh subir          # ou: scripts/preview.sh local
.\scripts\tunnel.ps1 -SemServidor
```

O `compose.preview.yml` precisa receber as mesmas variáveis
(`PREVIEW_HOSTS=.devtunnels.ms`, `PREVIEW_ORIGENS=https://*.devtunnels.ms`,
`PREVIEW_HTTPS=true`) — ver `docs/ops/preview.md`. Lembre que o PREVIEW entra **sem senha**:
nessa combinação use `-Privado`.

## Opção 2 — mesma rede Wi-Fi (sem conta, sem tunnel)

Mais simples quando o celular está na mesma rede que o PC:

```powershell
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1,192.168.0.42'   # IP da máquina (ipconfig)
uv run python manage.py runserver 0.0.0.0:8000
```

No celular, abra `http://192.168.0.42:8000`. O Firewall do Windows costuma pedir autorização
para a porta na primeira vez. É HTTP puro, então não serve para testar nada que dependa de
HTTPS.

> `ALLOWED_HOSTS` não aceita faixa CIDR: precisa do IP exato (que muda se o DHCP trocar) —
> por isso o tunnel costuma dar menos trabalho.

## Opção 3 — GitHub Codespaces

Não usa a sua máquina: o PREVIEW sobe no Codespace e a porta 8000 ganha uma URL
`https://<codespace>-8000.app.github.dev`, privada por padrão. Passo a passo em
`docs/ops/preview.md` (Opção A).

## Opção 4 — Cloudflare quick tunnel (sem conta)

Alternativa quando o DevTunnels não é opção:

```powershell
winget install Cloudflare.cloudflared
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1,.trycloudflare.com'
$env:DJANGO_CSRF_TRUSTED_ORIGINS = 'https://*.trycloudflare.com'
$env:DJANGO_ATRAS_DE_PROXY = 'true'
uv run python manage.py runserver 127.0.0.1:8000     # em outra janela
cloudflared tunnel --url http://localhost:8000
```

A URL é sorteada a cada execução e é sempre **pública e anônima**.

## Por que as três variáveis

| Variável | Sem ela |
|---|---|
| `DJANGO_ALLOWED_HOSTS` | `400 Bad Request: Invalid HTTP_HOST header` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | A tela abre, mas todo POST morre em `CSRF verification failed` |
| `DJANGO_ATRAS_DE_PROXY` | O Django acha que a conexão é HTTP e gera links/redirects `http://` |

Lidas por `config/settings/dev.py`; no PREVIEW os equivalentes são `PREVIEW_HOSTS`,
`PREVIEW_ORIGENS` e `PREVIEW_HTTPS`.

## Segurança

- Tunnel **só** para DEV ou PREVIEW (`APP_ENV` em `dev`/`lab`/`preview`), nunca para uma
  instância com dados reais — expor a porta é equivalente a publicar o sistema.
- Com acesso anônimo, a única barreira é o login do sistema; o PREVIEW não tem nem isso
  (ADR 0011), então combine PREVIEW com `-Privado`.
- Desligue quando terminar: `Ctrl+C` para de hospedar e `-Remover` apaga o tunnel da conta.
- O `devtunnel.exe` baixado fica em `var/ferramentas/` (ignorado pelo Git). Nenhuma
  credencial é gravada no repositório.
