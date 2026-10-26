$ErrorActionPreference = "Stop"

# Project root = directory containing this script
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

Write-Host "`n===== 1. Setting up Backend =====" -ForegroundColor Cyan

Set-Location $backend

# Create virtual environment if missing
if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create Python virtual environment."
    }
}

$python = Join-Path $backend "venv\Scripts\python.exe"

# Install backend dependencies
& $python -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "Backend dependency installation failed."
}

# Create .env without overwriting an existing file
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created backend .env"
} else {
    Write-Host "Backend .env already exists; preserving it."
}

# Apply database migrations
& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    throw "Database migrations failed."
}

Write-Host "`n===== 2. Setting up Frontend =====" -ForegroundColor Cyan

Set-Location $frontend

# Install frontend dependencies
npm install
if ($LASTEXITCODE -ne 0) {
    throw "Frontend dependency installation failed."
}

# Create .env.local without overwriting an existing file
if (-not (Test-Path ".env.local")) {
    Copy-Item ".env.example" ".env.local"
    Write-Host "Created frontend .env.local"
} else {
    Write-Host "Frontend .env.local already exists; preserving it."
}

Write-Host "`n===== 3. Starting Backend =====" -ForegroundColor Cyan

# Launch backend in a separate PowerShell window
$backendCommand = @"
Set-Location '$backend'
& '.\venv\Scripts\python.exe' -m uvicorn bordereaux.main:app --reload
"@

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", $backendCommand
)

# Give the backend a moment to initialize
Start-Sleep -Seconds 3

Write-Host "`n===== 4. Starting Frontend =====" -ForegroundColor Cyan

# Launch frontend in a separate PowerShell window
$frontendCommand = "Set-Location '$frontend'; npm run dev"

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", $frontendCommand
)

Write-Host "`n===== Application Startup Initiated =====" -ForegroundColor Green
Write-Host "Backend API: http://localhost:8000/api/v1"
Write-Host "Health check: http://localhost:8000/health"
Write-Host "API docs: http://localhost:8000/docs"
Write-Host "Frontend: Check the URL printed in the frontend terminal."
Write-Host "`nClose the backend or frontend terminal window to stop that server."
Write-Host "No tests were run."

