$ErrorActionPreference = 'Stop'
if (-not (Get-Command go -ErrorAction SilentlyContinue)) {
    throw 'Go 1.27.3 is required. This script does not install software.'
}
$envFile = Join-Path $PSScriptRoot '.env.local'
if (-not (Test-Path -LiteralPath $envFile)) {
    throw 'Run dev/Initialize.ps1 first.'
}

$secrets = @{}
foreach ($line in [IO.File]::ReadAllLines($envFile)) {
    if ($line -match '^(DEV_[A-Z_]+)=([0-9a-f]{64})$') {
        $secrets[$matches[1]] = $matches[2]
    }
}
foreach ($name in @('DEV_POSTGRES_PASSWORD', 'DEV_REDIS_PASSWORD', 'DEV_ADMIN_PASSWORD', 'DEV_JWT_SECRET', 'DEV_TOTP_ENCRYPTION_KEY')) {
    if (-not $secrets.ContainsKey($name)) { throw "Invalid local development credential: $name" }
}

$dataDir = Join-Path $PSScriptRoot '.runtime/data'
$values = @{
    AUTO_SETUP = 'true'
    DATA_DIR = $dataDir
    CONFIG_FILE = (Join-Path $dataDir 'config.yaml')
    SERVER_HOST = '127.0.0.1'
    SERVER_PORT = '18080'
    SERVER_MODE = 'debug'
    SERVER_FRONTEND_URL = 'http://127.0.0.1:13000'
    RUN_MODE = 'standard'
    DATABASE_HOST = '127.0.0.1'
    DATABASE_PORT = '15432'
    DATABASE_USER = 'sub2api_dev'
    DATABASE_PASSWORD = $secrets.DEV_POSTGRES_PASSWORD
    DATABASE_DBNAME = 'sub2api_dev'
    DATABASE_SSLMODE = 'disable'
    REDIS_HOST = '127.0.0.1'
    REDIS_PORT = '16379'
    REDIS_USERNAME = ''
    REDIS_PASSWORD = $secrets.DEV_REDIS_PASSWORD
    REDIS_DB = '0'
    REDIS_ENABLE_TLS = 'false'
    ADMIN_EMAIL = 'admin@local.test'
    ADMIN_PASSWORD = $secrets.DEV_ADMIN_PASSWORD
    JWT_SECRET = $secrets.DEV_JWT_SECRET
    TOTP_ENCRYPTION_KEY = $secrets.DEV_TOTP_ENCRYPTION_KEY
    LOG_ENV = 'development'
    TZ = 'Asia/Shanghai'
}
$previous = @{}
try {
    foreach ($name in $values.Keys) {
        $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $values[$name], 'Process')
    }
    New-Item -ItemType Directory -Force -Path $dataDir, (Join-Path $PSScriptRoot '.runtime/air') | Out-Null
    Push-Location (Split-Path $PSScriptRoot -Parent)
    try {
        & go run github.com/air-verse/air@v1.67.4 -c dev/air.toml
        if ($LASTEXITCODE -ne 0) { throw "Air exited with code $LASTEXITCODE" }
    } finally { Pop-Location }
} finally {
    foreach ($name in $previous.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
}
