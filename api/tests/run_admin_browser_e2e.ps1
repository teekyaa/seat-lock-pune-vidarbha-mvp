$ErrorActionPreference = 'Stop'
$apiDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workspace = (Resolve-Path (Join-Path $apiDir '..')).Path
$webDir = Join-Path $workspace 'web'
$python = Join-Path $apiDir '.venv\Scripts\python.exe'
$dbPath = Join-Path $apiDir '.admin-browser-test.sqlite3'
$playwright = Join-Path $webDir 'node_modules\.bin\playwright.cmd'
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $playwright)) { throw 'Install the API and web dependencies first.' }
if (Test-Path -LiteralPath $dbPath) { throw 'The disposable admin browser database already exists; refusing to overwrite it.' }
foreach ($port in 8011, 3102) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) { throw "Test port $port is already in use." }
}

$env:ADMIN_E2E_ENABLED = '1'
$env:DJANGO_DEBUG = '1'
$env:DJANGO_SECRET_KEY = 'synthetic-isolated-browser-test'
$env:DATABASE_URL = 'sqlite:///' + ($dbPath -replace '\\', '/')
$env:TEXTBEE_API_KEY = ''
$env:TEXTBEE_DEVICE_ID = ''
$env:SMS_BACKEND = 'apps.notifications.channels.UnconfiguredSMSBackend'
$env:REDIS_URL = ''
$env:ADMIN_E2E_PASSWORD = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
$env:ADMIN_E2E_SECRET = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
$env:ADMIN_TOTP_ENCRYPTION_KEY = (& $python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
$apiProcess = $null
$webProcess = $null
$testExit = 1
$createdDb = $false
$logSuffix = [guid]::NewGuid().ToString('N')
try {
    Set-Location $apiDir
    [Environment]::CurrentDirectory = $apiDir
    $createdDb = $true
    & $python manage.py migrate --noinput --verbosity 0
    if ($LASTEXITCODE -ne 0) { throw 'Disposable test migration failed.' }
    & $python tests\seed_admin_browser.py
    if ($LASTEXITCODE -ne 0) { throw 'Disposable test seed failed.' }
    $apiProcess = Start-Process -FilePath $python -ArgumentList 'manage.py','runserver','127.0.0.1:8011','--noreload' `
        -WorkingDirectory $apiDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $env:TEMP "seatlock-admin-api-$logSuffix.out") `
        -RedirectStandardError (Join-Path $env:TEMP "seatlock-admin-api-$logSuffix.err")
    $env:ADMIN_TOTP_ENCRYPTION_KEY = ''
    $env:DATABASE_URL = ''
    $env:API_URL = 'http://127.0.0.1:8011'
    $env:NEXT_DIST_DIR = '.next-admin-e2e'
    $webProcess = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev','--','-p','3102' `
        -WorkingDirectory $webDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $env:TEMP "seatlock-admin-web-$logSuffix.out") `
        -RedirectStandardError (Join-Path $env:TEMP "seatlock-admin-web-$logSuffix.err")
    $env:PLAYWRIGHT_BASE_URL = 'http://127.0.0.1:3102'
    if (-not $env:PLAYWRIGHT_BROWSER_CHANNEL) { $env:PLAYWRIGHT_BROWSER_CHANNEL = 'msedge' }
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri 'http://127.0.0.1:3102/control/login' -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $ready) { throw 'The isolated browser test server did not become ready.' }
    Set-Location $webDir
    [Environment]::CurrentDirectory = $webDir
    & $playwright test tests/admin-e2e.spec.ts
    $testExit = $LASTEXITCODE
} finally {
    if ($webProcess) { Stop-Process -Id $webProcess.Id -ErrorAction SilentlyContinue }
    if ($apiProcess) { Stop-Process -Id $apiProcess.Id -ErrorAction SilentlyContinue }
    foreach ($port in 8011, 3102) {
        $listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
        if ($listener) {
            $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener[0].OwningProcess)"
            if ($process.CommandLine -like "*$workspace*" -or $process.CommandLine -like '*manage.py runserver 127.0.0.1:8011*') {
                Stop-Process -Id $process.ProcessId -ErrorAction SilentlyContinue
            }
        }
    }
    if ($createdDb -and (Test-Path -LiteralPath $dbPath)) {
        $resolved = (Resolve-Path -LiteralPath $dbPath).Path
        if ($resolved -ne (Join-Path $apiDir '.admin-browser-test.sqlite3')) { throw 'Unexpected test database path; refusing cleanup.' }
        Remove-Item -LiteralPath $resolved -Force
    }
}
exit $testExit
