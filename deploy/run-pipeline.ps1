$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectPath

$lockPath = Join-Path $ProjectPath "data/pipeline.lock"
$lockStream = $null
try {
    $lockStream = [System.IO.File]::Open(
        $lockPath,
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
} catch [System.IO.IOException] {
    exit 0
}

try {
    & python.exe -X utf8 scripts/run_weekly_pipeline.py
    exit $LASTEXITCODE
} finally {
    if ($lockStream) { $lockStream.Dispose() }
}
