$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectPath

& python.exe -X utf8 scripts/process_articles.py
exit $LASTEXITCODE
