# run_scanner_b.ps1
# PowerShell wrapper for Scanner B — called by Task Scheduler every hour.
# Logs output to scanner_b.log

$ErrorActionPreference = "Stop"
$workDir = "C:\Users\USER\hello"
$log     = Join-Path $workDir "scanner_b.log"

$etZone = [TimeZoneInfo]::FindSystemTimeZoneById("Eastern Standard Time")
$nowET  = [TimeZoneInfo]::ConvertTimeFromUtc([DateTime]::UtcNow, $etZone)

function Log($msg) {
    $ts = $nowET.ToString("yyyy-MM-dd HH:mm:ss ET")
    Add-Content -Path $log -Value "[$ts] $msg"
}

Log "Scanner B starting"
Set-Location $workDir

try {
    $output = & python "$workDir\run_scanner_b.py" 2>&1
    $output | ForEach-Object { Add-Content -Path $log -Value $_ }
    Log "Scanner B completed OK"
} catch {
    Log "Scanner B ERROR: $_"
    exit 1
}
