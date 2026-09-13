$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
$PowerShellPath = (Get-Command powershell.exe).Source
$TaskUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$Principal = New-ScheduledTaskPrincipal -UserId $TaskUser -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

function Install-ReportTask($Name, $Script, $Triggers) {
    $arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $ProjectPath $Script) + '"'
    $action = New-ScheduledTaskAction -Execute $PowerShellPath -Argument $arguments
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $Triggers -Principal $Principal -Settings $Settings -Force | Out-Null
}

$collection = 7..16 | ForEach-Object { New-ScheduledTaskTrigger -Daily -At ('{0:D2}:00' -f $_) }
$analysis = @('09:00', '12:00', '15:00', '16:30') | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
Install-ReportTask 'Iraq Report Dashboard' 'deploy/start-dashboard.ps1' @(New-ScheduledTaskTrigger -AtLogOn -User $TaskUser)
Install-ReportTask 'Iraq Report Pipeline' 'deploy/run-pipeline.ps1' $collection
Install-ReportTask 'Iraq Report Analysis' 'deploy/run-analysis.ps1' $analysis
Start-ScheduledTask -TaskName 'Iraq Report Dashboard'
Write-Host '이라크 보고서 예약 작업 3개 설치 완료'