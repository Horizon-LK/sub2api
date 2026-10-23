$ErrorActionPreference = 'Stop'
if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    throw 'Node 24 and pnpm 9 are required. This script does not install software.'
}
$values = @{
    VITE_DEV_PROXY_TARGET = 'http://127.0.0.1:18080'
    VITE_DEV_PORT = '13000'
    VITE_API_BASE_URL = '/api/v1'
    VITE_WS_BASE_URL = '127.0.0.1:18080'
}
$previous = @{}
try {
    foreach ($name in $values.Keys) {
        $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $values[$name], 'Process')
    }
    Push-Location (Join-Path (Split-Path $PSScriptRoot -Parent) 'frontend')
    try {
        & pnpm dev --host 127.0.0.1 --strictPort
        if ($LASTEXITCODE -ne 0) { throw "Vite exited with code $LASTEXITCODE" }
    } finally { Pop-Location }
} finally {
    foreach ($name in $previous.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
}
