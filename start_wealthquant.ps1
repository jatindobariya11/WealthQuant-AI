# WealthQuant OS Startup Script (start_wealthquant.ps1)
# Automatic startup of PostgreSQL, FastAPI backend, and React frontend.

$ErrorActionPreference = "Stop"

# Ensure we are running from the script directory
$scriptDir = $PSScriptRoot
if (-not $scriptDir) {
    $scriptDir = Get-Location
}

Write-Host "==================================================" -ForegroundColor Green
Write-Host "          WEALTHQUANT OS STARTUP UTILITY          " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host "Base Directory: $scriptDir" -ForegroundColor Gray

# Define Paths
$pgLocalDir = Join-Path $scriptDir "backend\pg_local"
$pgCtl = Join-Path $pgLocalDir "pgsql\bin\pg_ctl.exe"
$pgData = Join-Path $pgLocalDir "data"
$pgLog = Join-Path $pgLocalDir "pg.log"
$pidFile = Join-Path $pgData "postmaster.pid"

$backendDir = Join-Path $scriptDir "backend"
$pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"

$frontendDir = Join-Path $scriptDir "frontend"

# --- STEP 1: Check and Recover PostgreSQL PID File ---
Write-Host "`n[1/4] Checking PostgreSQL PID file..." -ForegroundColor Cyan
if (Test-Path $pidFile) {
    Write-Host "Found existing postmaster.pid at: $pidFile" -ForegroundColor Yellow
    try {
        $pidContent = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($pidContent -and $pidContent.Count -gt 0) {
            $pidVal = $pidContent[0].Trim()
            if ($pidVal -match '^\d+$') {
                Write-Host "PID inside file is: $pidVal. Verifying if process is running..." -ForegroundColor Gray
                $process = Get-Process -Id ([int]$pidVal) -ErrorAction SilentlyContinue
                if ($process -and $process.ProcessName -like "*postgres*") {
                    Write-Host "PostgreSQL is already active (PID $pidVal)." -ForegroundColor Green
                } else {
                    Write-Host "Process with PID $pidVal is dead or not PostgreSQL. Removing stale PID file." -ForegroundColor Red
                    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
                    $backupFile = Join-Path $pgData "postmaster.pid.bak_$timestamp"
                    Copy-Item $pidFile $backupFile -Force
                    Remove-Item $pidFile -Force
                    Write-Host "Stale PID file backed up to postmaster.pid.bak_$timestamp and deleted." -ForegroundColor Yellow
                }
            } else {
                Write-Host "Invalid PID format in file: '$pidVal'. Removing PID file." -ForegroundColor Red
                Remove-Item $pidFile -Force
            }
        } else {
            Write-Host "Empty PID file found. Removing." -ForegroundColor Red
            Remove-Item $pidFile -Force
        }
    } catch {
        Write-Host "Error reading or handling PID file: $_. Attempting to remove it." -ForegroundColor Red
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "No active PID file found. Proceeding with clean start." -ForegroundColor Green
}

# --- STEP 2: Start PostgreSQL ---
Write-Host "`n[2/4] Initializing PostgreSQL Database..." -ForegroundColor Cyan

# Check if port 5432 is already listening (maybe running as a system service or another instance)
$portCheck = Test-NetConnection localhost -Port 5432 -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
if ($portCheck.TcpTestSucceeded) {
    Write-Host "Port 5432 is already listening. PostgreSQL is likely already running." -ForegroundColor Green
} else {
    if (-not (Test-Path $pgCtl)) {
        Write-Error "PostgreSQL pg_ctl not found at: $pgCtl"
        exit 1
    }
    
    Write-Host "Starting PostgreSQL using pg_ctl..." -ForegroundColor Gray
    # Run pg_ctl start
    & $pgCtl -D $pgData -l $pgLog start
    
    # Wait for PostgreSQL to start listening
    $maxAttempts = 15
    $started = $false
    Write-Host "Waiting for database port 5432 to become active..." -ForegroundColor Gray
    for ($i = 1; $i -le $maxAttempts; $i++) {
        Start-Sleep -Seconds 2
        $portCheck = Test-NetConnection localhost -Port 5432 -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
        if ($portCheck.TcpTestSucceeded) {
            Write-Host "PostgreSQL is now online and listening on port 5432." -ForegroundColor Green
            $started = $true
            break
        }
        Write-Host "Attempt $i/$($maxAttempts): Port 5432 is not listening yet..." -ForegroundColor Yellow
    }
    
    if (-not $started) {
        Write-Error "PostgreSQL failed to respond on port 5432 after 30 seconds. Please check logs at: $pgLog"
        exit 1
    }
}

# --- STEP 3: Start FastAPI Backend ---
Write-Host "`n[3/4] Launching FastAPI Backend..." -ForegroundColor Cyan
$backendPortCheck = Test-NetConnection localhost -Port 8000 -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
if ($backendPortCheck.TcpTestSucceeded) {
    Write-Host "Port 8000 is already in use. Skipping backend launch." -ForegroundColor Yellow
} else {
    if (-not (Test-Path $pythonExe)) {
        Write-Error "Python virtual environment executable not found at: $pythonExe"
        exit 1
    }
    
    Write-Host "Starting Uvicorn backend in a new window..." -ForegroundColor Gray
    $backendCmd = "/k cd /d `"$backendDir`" && `"$pythonExe`" -m uvicorn main:app --host 127.0.0.1 --port 8000"
    Start-Process cmd.exe -ArgumentList $backendCmd -WindowStyle Normal
    Write-Host "FastAPI launch command sent." -ForegroundColor Green
}

# --- STEP 4: Start React Frontend ---
Write-Host "`n[4/4] Launching React Frontend..." -ForegroundColor Cyan
$frontendPortCheck = Test-NetConnection localhost -Port 3000 -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
if ($frontendPortCheck.TcpTestSucceeded) {
    Write-Host "Port 3000 is already in use. Skipping frontend launch." -ForegroundColor Yellow
} else {
    Write-Host "Starting React app (npm start) in a new window..." -ForegroundColor Gray
    $frontendCmd = "/k cd /d `"$frontendDir`" && npm start"
    Start-Process cmd.exe -ArgumentList $frontendCmd -WindowStyle Normal
    Write-Host "Frontend launch command sent." -ForegroundColor Green
}

# --- Verification & Summary ---
Write-Host "`n==================================================" -ForegroundColor Green
Write-Host "          VERIFYING PLATFORM INTEGRITY            " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green

Write-Host "Waiting for FastAPI health endpoint to respond..." -ForegroundColor Gray
$healthPassed = $false
for ($i = 1; $i -le 15; $i++) {
    Start-Sleep -Seconds 2
    try {
        $healthResponse = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/pipeline/db-health" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($healthResponse -and $healthResponse.connected -eq $true) {
            Write-Host "Health Check: PASS" -ForegroundColor Green
            Write-Host "Database connected successfully!" -ForegroundColor Green
            Write-Host "Total Database Rows: $($healthResponse.total_rows)" -ForegroundColor Green
            $healthPassed = $true
            break
        }
    } catch {
        # Backend not online yet, retry
    }
    Write-Host "Retrying health check ($i/15)..." -ForegroundColor Yellow
}

if (-not $healthPassed) {
    Write-Host "Warning: Could not confirm database health check. The backend might still be initializing." -ForegroundColor Yellow
}

Write-Host "`n==================================================" -ForegroundColor Green
Write-Host "          WEALTHQUANT OS RUNNING SERVICES         " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host "  React Frontend:     http://localhost:3000" -ForegroundColor Cyan
Write-Host "  FastAPI Backend:    http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "  Database Health:    http://127.0.0.1:8000/api/pipeline/db-health" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Green

# Open frontend in the browser
Write-Host "Opening WealthQuant Frontend in default browser..." -ForegroundColor Gray
Start-Process "http://localhost:3000"
