#Requires -Version 5.1
<#
  Inicia Streamlit + túnel ngrok para compartir la app desde tu PC.
  Uso:
    1. Copia .env.example → .env y pega NGROK_AUTHTOKEN
    2. .\scripts\run_ngrok.ps1
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$port = 8501

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
}

function Load-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
        $k, $v = $_ -split '=', 2
        $k = $k.Trim()
        $v = $v.Trim().Trim('"').Trim("'")
        if ($k) { Set-Item -Path "Env:$k" -Value $v }
    }
}

Refresh-Path
Load-EnvFile (Join-Path $PWD ".env")

if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
    Write-Host "Instalando ngrok..." -ForegroundColor Yellow
    winget install Ngrok.Ngrok --accept-package-agreements --accept-source-agreements | Out-Null
    Refresh-Path
}

$token = $env:NGROK_AUTHTOKEN
if (-not $token) {
    Write-Host ""
    Write-Host "Falta NGROK_AUTHTOKEN." -ForegroundColor Red
    Write-Host "1. Crea cuenta gratis: https://dashboard.ngrok.com/signup"
    Write-Host "2. Copia token: https://dashboard.ngrok.com/get-started/your-authtoken"
    Write-Host "3. Crea .env con: NGROK_AUTHTOKEN=tu_token"
    Write-Host "4. Vuelve a ejecutar: .\scripts\run_ngrok.ps1"
    exit 1
}

ngrok config add-authtoken $token | Out-Null

$listening = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    Write-Host "Iniciando Streamlit en puerto $port..." -ForegroundColor Cyan
    Start-Process -WindowStyle Minimized -FilePath "streamlit" -ArgumentList @(
        "run", "streamlit_app.py",
        "--server.headless", "true",
        "--server.port", "$port",
        "--browser.gatherUsageStats", "false"
    )
    $deadline = (Get-Date).AddSeconds(45)
    do {
        Start-Sleep -Seconds 1
        $listening = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    } while (-not $listening -and (Get-Date) -lt $deadline)
    if (-not $listening) { throw "Streamlit no arrancó en el puerto $port" }
}

# Cerrar ngrok previo en 4040 si existe
Get-Process -Name "ngrok" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

Write-Host "Iniciando túnel ngrok..." -ForegroundColor Cyan
Start-Process -WindowStyle Minimized -FilePath "ngrok" -ArgumentList @("http", $port, "--log=stdout")

$publicUrl = $null
$deadline = (Get-Date).AddSeconds(30)
while (-not $publicUrl -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 3
        $publicUrl = ($resp.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1).public_url
    } catch { }
}

Write-Host ""
if ($publicUrl) {
    Write-Host "=== APP LISTA ===" -ForegroundColor Green
    Write-Host "Local:   http://localhost:$port"
    Write-Host "Publico: $publicUrl" -ForegroundColor Green
    Write-Host ""
    Write-Host "Comparte el link PUBLICO. Ctrl+C aqui no detiene ngrok (cierra ventana ngrok o: Stop-Process -Name ngrok)"
    Start-Process $publicUrl
} else {
    Write-Host "Ngrok iniciado. Abre http://127.0.0.1:4040 para ver la URL publica." -ForegroundColor Yellow
}
