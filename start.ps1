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

# Libera o modelo da memória após 1 min ocioso (reduz uso de RAM e do
# arquivo de paginação do Windows no SSD). Vale para o Ollama iniciado abaixo.
$env:OLLAMA_KEEP_ALIVE = "60s"

Write-Host "[check] Verificando se o Ollama está acessível em http://localhost:11434 ..."
$ollamaUp = $false
try {
    $null = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 3
    $ollamaUp = $true
    Write-Host "[ok] Ollama já está rodando." -ForegroundColor Green
} catch {
    Write-Host "[run] Ollama não respondeu — iniciando 'ollama serve' (OLLAMA_KEEP_ALIVE=60s) ..."
    try {
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
        for ($i = 0; $i -lt 10 -and -not $ollamaUp; $i++) {
            Start-Sleep -Seconds 1
            try {
                $null = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2
                $ollamaUp = $true
            } catch {}
        }
        if ($ollamaUp) {
            Write-Host "[ok] Ollama iniciado." -ForegroundColor Green
        } else {
            Write-Warning "Não consegui confirmar o Ollama. Verifique se ele está instalado e no PATH."
        }
    } catch {
        Write-Warning "Falha ao iniciar o Ollama automaticamente. Abra outro terminal e rode 'ollama serve'."
    }
}

Write-Host "[run] Iniciando servidor em http://127.0.0.1:8000 (auto-reload ativo) ..."
Set-Location $backend
& $python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload --reload-dir $backend
