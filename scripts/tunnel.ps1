# Dev Tunnels - servidor com acesso publico
# Uso: .\scripts\tunnel.ps1

param(
    [ValidateSet('Start', 'Status', 'Logout')]
    [string]$Command = 'Start',
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

function Write-Info { Write-Host "[INFO] $($args[0])" -ForegroundColor Blue }
function Write-Success { Write-Host "[OK] $($args[0])" -ForegroundColor Green }
function Write-Warning { Write-Host "[AVISO] $($args[0])" -ForegroundColor Yellow }

$TUNNEL_ID = "pcpr-preview"

# Verifica devtunnel
function Ensure-DevTunnel {
    Write-Info "Verificando devtunnel..."
    $devtunnel = Get-Command devtunnel -ErrorAction SilentlyContinue

    if (-not $devtunnel) {
        Write-Warning "Instalando devtunnel via npm..."
        if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
            Write-Host "[ERRO] npm nao encontrado! Instale Node.js em https://nodejs.org" -ForegroundColor Red
            exit 1
        }
        npm install -g "@microsoft/devtunnels-cli"
    }

    Write-Success "devtunnel OK"
}

# Verifica login
function Ensure-LoggedIn {
    Write-Info "Verificando login Microsoft..."

    $result = devtunnel user show 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Fazendo login na conta Microsoft..."
        devtunnel user login
    }

    Write-Success "Logado"
}

# Status do tunnel
function Show-Status {
    Write-Info "Verificando tunnel..."

    try {
        $tunnels = devtunnel list 2>&1
        if ($tunnels -match $TUNNEL_ID) {
            Write-Success "Tunnel ativo"
            Write-Host ""
            $tunnels | Select-String $TUNNEL_ID | ForEach-Object { Write-Host "   $_" -ForegroundColor Cyan }
            Write-Host ""
        }
        else {
            Write-Warning "Tunnel nao encontrado. Inicie com: .\scripts\tunnel.ps1"
        }
    }
    catch {
        Write-Warning "Nao foi possivel verificar. Inicie o tunnel primeiro."
    }
}

# Setup tunnel
function Setup-Tunnel {
    Write-Info "Configurando tunnel..."

    $tunnels = devtunnel list 2>&1
    if (-not ($tunnels -match $TUNNEL_ID)) {
        Write-Info "Criando tunnel..."
        devtunnel create $TUNNEL_ID --allow-anonymous
    }

    Write-Info "Conectando ao tunnel na porta $Port..."
    Write-Host ""

    devtunnel connect $TUNNEL_ID -p $Port --allow-anonymous
}

# Inicia servidor
function Start-LocalServer {
    Write-Info "Iniciando servidor local..."

    # Verifica PostgreSQL
    $psql = Get-Command psql -ErrorAction SilentlyContinue
    if (-not $psql) {
        Write-Host "[ERRO] PostgreSQL nao encontrado!" -ForegroundColor Red
        Write-Host "   Instale de: https://www.postgresql.org/download/windows/" -ForegroundColor Yellow
        exit 1
    }

    # Ambiente
    $env:DJANGO_SETTINGS_MODULE = "config.settings.preview"
    $env:DEMO_MODE = "true"
    $env:POSTGRES_DB = "pcpr_preview"

    if (-not $env:DJANGO_SECRET_KEY) {
        $env:DJANGO_SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(50))"
    }

    # Cria banco
    Write-Info "Verificando banco de dados..."
    try {
        $dbExists = psql -lqt 2>&1 | Select-String "pcpr_preview"
        if (-not $dbExists) {
            Write-Info "Criando banco pcpr_preview..."
            createdb pcpr_preview
        }
    }
    catch {
        Write-Host "[ERRO] Erro ao verificar banco: $_" -ForegroundColor Red
        exit 1
    }

    # Django setup
    Write-Info "Configurando Django..."
    uv run python manage.py check --deploy --fail-level ERROR
    uv run python manage.py migrate --noinput
    uv run python manage.py semear_demo --se-vazio
    uv run python manage.py collectstatic --noinput -v0

    Write-Success "Servidor pronto"
}

# Main
try {
    switch ($Command) {
        'Status' {
            Ensure-DevTunnel
            Show-Status
        }

        'Logout' {
            Ensure-DevTunnel
            Write-Warning "Desconectando..."
            devtunnel user logout
            Write-Success "Desconectado"
        }

        'Start' {
            Write-Host ""
            Write-Host "=== Dev Tunnels - PCPR Gestao ===" -ForegroundColor Blue
            Write-Host ""

            Ensure-DevTunnel
            Write-Host ""

            Ensure-LoggedIn
            Write-Host ""

            Start-LocalServer
            Write-Host ""

            Write-Info "Iniciando processador de eventos..."
            $workerProcess = Start-Process -NoNewWindow -PassThru `
                -FilePath "uv" `
                -ArgumentList "run", "python", "manage.py", "processar_outbox"
            Write-Success "Worker iniciado"
            Write-Host ""

            Write-Info "Iniciando gunicorn..."
            $gunicornProcess = Start-Process -NoNewWindow -PassThru `
                -FilePath "uv" `
                -ArgumentList "run", "gunicorn", "config.wsgi", `
                    "--bind", "127.0.0.1:$Port", "--workers", "3"
            Write-Success "Gunicorn iniciado"
            Write-Host ""

            Start-Sleep -Seconds 2

            Write-Info "Criando tunnel publico..."
            Write-Host ""

            Setup-Tunnel

            # Cleanup
            $null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
                Write-Host ""
                Write-Warning "Encerrando..."
                Stop-Process -Id $workerProcess.Id -ErrorAction SilentlyContinue
                Stop-Process -Id $gunicornProcess.Id -ErrorAction SilentlyContinue
            }

            while ($true) { Start-Sleep -Seconds 1 }
        }
    }
}
catch {
    Write-Host "[ERRO] $_" -ForegroundColor Red
    exit 1
}
