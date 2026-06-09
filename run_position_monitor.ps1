# run_position_monitor.ps1
# PowerShell wrapper for the 5-minute position monitor — called by Task Scheduler.
# Logs output to position_monitor.log

$ErrorActionPreference = "Stop"
$workDir = "C:\Users\USER\hello"
$log     = Join-Path $workDir "position_monitor.log"

$etZone = [TimeZoneInfo]::FindSystemTimeZoneById("Eastern Standard Time")
$nowET  = [TimeZoneInfo]::ConvertTimeFromUtc([DateTime]::UtcNow, $etZone)

function Log($msg) {
    $ts = $nowET.ToString("yyyy-MM-dd HH:mm:ss ET")
    Add-Content -Path $log -Value "[$ts] $msg"
}

Set-Location $workDir

try {
    $output = & python "$workDir\run_position_monitor.py" 2>&1
    $output | ForEach-Object { Add-Content -Path $log -Value $_ }
} catch {
    Log "Position monitor ERROR: $_"
    exit 1
}
