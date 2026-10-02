# Mantem o PREVIEW (Docker) rodando com o codigo mais recente do main.
#   .\scripts\atualizar-preview.ps1            # atualiza agora (git pull + rebuild se houver novidade)
#   .\scripts\atualizar-preview.ps1 -Agendar   # agenda: ao entrar no Windows e a cada 30 min
#   .\scripts\atualizar-preview.ps1 -Agendar -Minutos 10
#   .\scripts\atualizar-preview.ps1 -Remover   # remove o agendamento

param(
    [switch]$Agendar,
    [switch]$Remover,
    [int]$Minutos = 30
)

$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $PSScriptRoot
$Tarefa = 'PCPR-Preview-Atualizar'
$Compose = @('compose', '-f', 'compose.preview.yml')

if ($Remover) {
    Unregister-ScheduledTask -TaskName $Tarefa -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Agendamento '$Tarefa' removido."
    exit 0
}

if ($Agendar) {
    $acao = New-ScheduledTaskAction -Execute 'powershell.exe' -WorkingDirectory $Raiz `
        -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $gatilhos = @(
        (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME),
        (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $Minutos))
    )
    $config = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $Tarefa -Action $acao -Trigger $gatilhos -Settings $config -Force | Out-Null
    Write-Host "Agendado: ao entrar no Windows e a cada $Minutos min. Log: var\atualizar-preview.log"
    exit 0
}

Set-Location $Raiz
New-Item -ItemType Directory -Force -Path var | Out-Null
$Log = Join-Path $Raiz 'var\atualizar-preview.log'

function Log($msg) {
    $linha = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $msg
    Write-Host $linha
    Add-Content -Path $Log -Value $linha
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Log 'Docker nao esta rodando (abra o Docker Desktop). Nada feito.'
    exit 1
}

$mudou = $false
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
$sujo = (git status --porcelain).Trim()

if ($branch -ne 'main') {
    Log "Branch atual e '$branch', nao 'main'. Pulando git pull."
}
elseif ($sujo) {
    Log 'Ha alteracoes locais nao commitadas. Pulando git pull.'
}
else {
    git fetch origin main --quiet
    $local = (git rev-parse HEAD).Trim()
    $remoto = (git rev-parse origin/main).Trim()
    if ($local -ne $remoto) {
        git pull --ff-only origin main
        if ($LASTEXITCODE -ne 0) { Log 'git pull falhou (nao e fast-forward?).'; exit 1 }
        Log "Atualizado para $((git rev-parse --short HEAD).Trim())."
        $mudou = $true
    }
}

if ($mudou) {
    Log 'Reconstruindo e subindo o preview...'
    docker @Compose up --build -d
}
else {
    docker @Compose up -d
}
if ($LASTEXITCODE -ne 0) { Log 'docker compose falhou.'; exit 1 }
Log 'Preview no ar em http://localhost:8000'
