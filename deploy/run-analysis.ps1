$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectPath
$lockPath = Join-Path $ProjectPath "data/pipeline.lock"
$lockStream = $null
$deadline = (Get-Date).AddMinutes(30)
while (-not $lockStream) {
    try {
        $lockStream = [System.IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    } catch [System.IO.IOException] {
        if ((Get-Date) -ge $deadline) { throw "수집 작업 대기 시간 초과" }
        Start-Sleep -Seconds 10
    }
}
try {
    & python.exe -X utf8 scripts/run_job.py analysis scripts/process_articles.py
    exit $LASTEXITCODE
} finally {
    $lockStream.Dispose()
}
