# Expoe o servidor local em uma URL publica HTTPS (Microsoft DevTunnels) para abrir no celular.
# Nao precisa de Node.js, npm nem Docker: o executavel do devtunnel vem do winget ou do
# download direto. Detalhes e alternativas: docs/ops/tunnel.md
#
#   .\scripts\tunnel.ps1                 # sobe DEV + worker e abre o tunnel (URL publica)
#   .\scripts\tunnel.ps1 -Privado        # a URL passa a exigir login (Microsoft ou GitHub)
#   .\scripts\tunnel.ps1 -SemServidor    # o servidor ja esta rodando (ex.: PREVIEW) em outra janela
#   .\scripts\tunnel.ps1 -SemWorker      # sem o worker da outbox (nao gera PDF)
#   .\scripts\tunnel.ps1 -Porta 8001
#   .\scripts\tunnel.ps1 -Remover        # apaga o tunnel persistente da conta

param(
    [switch]$Privado,
    [switch]$SemServidor,
    [switch]$SemWorker,
    [switch]$Remover,
    [int]$Porta = 8000,
    [string]$Tunel = 'pcpr-gestao'
)

$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz

function Passo($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Aviso($msg) { Write-Host "!!  $msg" -ForegroundColor Yellow }

# --- 1. executavel do devtunnel -------------------------------------------------------------
function Resolver-Devtunnel {
    $cmd = Get-Command devtunnel -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $local = Join-Path $Raiz 'var\ferramentas\devtunnel.exe'
    if (Test-Path $local) { return $local }

    Passo 'devtunnel nao encontrado — instalando (nao usa Node.js).'
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install Microsoft.devtunnel --silent `
            --accept-source-agreements --accept-package-agreements
        $env:Path = ([Environment]::GetEnvironmentVariable('Path', 'Machine'), `
                [Environment]::GetEnvironmentVariable('Path', 'User')) -join ';'
        $cmd = Get-Command devtunnel -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
        Aviso 'winget nao resolveu; baixando o executavel direto.'
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $local) | Out-Null
    Invoke-WebRequest -Uri 'https://aka.ms/TunnelsCliDownload/win-x64' -OutFile $local
    return $local
}

$dt = Resolver-Devtunnel
Passo "devtunnel: $dt"

# --- 2. login (uma vez por maquina; a credencial fica no perfil do Windows) ------------------
$quem = (& $dt user show 2>&1) -join ' '
if ($quem -notmatch 'Logged in') {
    Passo 'Login no DevTunnels (Microsoft ou GitHub) — siga o codigo exibido.'
    & $dt user login -d
    if ($LASTEXITCODE -ne 0) { throw 'Login no DevTunnels falhou.' }
}

if ($Remover) {
    & $dt delete $Tunel -f
    Write-Host "Tunel '$Tunel' removido."
    exit 0
}

# --- 3. tunel persistente (a URL continua a mesma entre execucoes) --------------------------
& $dt show $Tunel *> $null
if ($LASTEXITCODE -ne 0) {
    Passo "Criando o tunel '$Tunel'."
    & $dt create $Tunel --description 'PCPR Gestao - servidor de desenvolvimento'
    if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel criar o tunel '$Tunel'." }
}
& $dt port create $Tunel -p $Porta --protocol http *> $null   # ja existir nao e erro

if ($Privado) {
    & $dt access delete $Tunel --anonymous *> $null
    Passo 'Acesso: exige login (Microsoft ou GitHub) para abrir a URL.'
}
else {
    & $dt access create $Tunel --anonymous *> $null
    Aviso 'Acesso anonimo: quem tiver a URL alcanca o seu servidor local.'
    Aviso 'Use so com dados ficticios (DEV/PREVIEW). Nunca com base real.'
}

$info = (& $dt show $Tunel 2>&1) -join "`n"
$url = [regex]::Match($info, "https://[a-z0-9-]+-$Porta\.[a-z0-9.-]*devtunnels\.ms").Value
if (-not $url) {
    Aviso "Nao achei a URL da porta $Porta. O devtunnel respondeu:"
    Write-Host $info -ForegroundColor DarkGray
    Aviso 'A URL tambem aparece na saida do host, logo abaixo.'
}

# --- 4. Django atras do tunel: hosts, origens de CSRF e esquema HTTPS -----------------------
# O tunel entrega HTTPS para fora e HTTP para o runserver; sem isso o login falha
# (ALLOWED_HOSTS) ou o POST e recusado (CSRF). Lido por config/settings/dev.py e preview.py.
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1,.devtunnels.ms'
$env:DJANGO_CSRF_TRUSTED_ORIGINS = 'https://*.devtunnels.ms'
$env:DJANGO_ATRAS_DE_PROXY = 'true'

$processos = @()
function Subir($titulo, $comando) {
    $script:processos += Start-Process powershell -PassThru -ArgumentList @(
        '-NoProfile', '-NoExit', '-Command',
        "`$host.UI.RawUI.WindowTitle = '$titulo'; Set-Location '$Raiz'; $comando"
    )
}

if (-not $SemServidor) {
    Passo "Servidor DEV em http://127.0.0.1:$Porta (janela 'PCPR servidor')."
    Subir 'PCPR servidor' "uv run python manage.py runserver 127.0.0.1:$Porta"
}
if (-not $SemServidor -and -not $SemWorker) {
    Passo "Worker da outbox (PDF, notificacoes) na janela 'PCPR worker'."
    Subir 'PCPR worker' 'uv run python manage.py processar_outbox'
}

# --- 5. tunel em primeiro plano (Ctrl+C encerra tudo) ---------------------------------------
if ($url) {
    Write-Host ''
    Write-Host "  Abra no computador e no celular:  $url" -ForegroundColor Green
    Write-Host '  DEV: usuario operador / senha senha-local-123' -ForegroundColor DarkGray
    Write-Host ''
}
Passo 'Tunel no ar. Ctrl+C encerra o tunel, o servidor e o worker.'

try {
    & $dt host $Tunel
}
finally {
    foreach ($p in $processos) {
        if ($p -and -not $p.HasExited) {
            cmd /c "taskkill /PID $($p.Id) /T /F" *> $null
        }
    }
    Write-Host 'Tunel encerrado.'
}
