$ErrorActionPreference = 'Stop'
$envFile = Join-Path $PSScriptRoot '.env.local'
if (Test-Path -LiteralPath $envFile) {
    throw 'dev/.env.local already exists; keep it to preserve the development database credentials.'
}

function New-LocalSecret {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}

$lines = @(
    '# Local development only. Never upload or use production credentials here.'
    "DEV_POSTGRES_PASSWORD=$(New-LocalSecret)"
    "DEV_REDIS_PASSWORD=$(New-LocalSecret)"
    "DEV_ADMIN_PASSWORD=$(New-LocalSecret)"
    "DEV_JWT_SECRET=$(New-LocalSecret)"
    "DEV_TOTP_ENCRYPTION_KEY=$(New-LocalSecret)"
)
[IO.File]::WriteAllLines($envFile, $lines, (New-Object Text.UTF8Encoding($false)))
Write-Host 'Created dev/.env.local with independent development credentials. Values were not printed.'
