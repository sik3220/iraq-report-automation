$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectPath

$listener = Get-NetTCPConnection -LocalPort 3100 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    exit 0
}

if (-not (Test-Path -LiteralPath ".next/BUILD_ID")) {
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& npm.cmd run start -- --port 3100
exit $LASTEXITCODE
