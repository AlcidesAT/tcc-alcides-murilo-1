# Script de inicialização do sistema RAG
# Inicia o servidor FastAPI; o Ollama deve estar rodando separadamente.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv"
$backend = Join-Path $root "backend"

if (-not (Test-Path $venv)) {
    Write-Host "[setup] Criando ambiente virtual em .venv..."
    python -m venv $venv
}

$python = Join-Path $venv "Scripts\python.exe"

Write-Host "[setup] Instalando dependências (apenas se necessário)..."
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $backend "requirements.txt")

Write-Host "[check] Verificando se o Ollama está acessível em http://localhost:11434 ..."
try {
    $null = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 3
    Write-Host "[ok] Ollama respondeu." -ForegroundColor Green
} catch {
    Write-Warning "Ollama não respondeu. Abra outro terminal e execute 'ollama serve' antes de fazer perguntas."
}

Write-Host "[run] Iniciando servidor em http://127.0.0.1:8000 (auto-reload ativo) ..."
Set-Location $backend
& $python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload --reload-dir $backend
