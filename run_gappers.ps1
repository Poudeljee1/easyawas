# run_gappers.ps1
# Guard wrapper for premarket_gappers_scan.sh.
# Enforces: weekday only, before 4pm ET, not already run today.
# Called by both the 8:30am scheduled task and the logon catch-up task.

$ErrorActionPreference = "Stop"

$etZone  = [TimeZoneInfo]::FindSystemTimeZoneById("Eastern Standard Time")
$nowET   = [TimeZoneInfo]::ConvertTimeFromUtc([DateTime]::UtcNow, $etZone)
$workDir = "C:\Users\USER\hello"
$log     = Join-Path $workDir "gappers_scheduler.log"

function Log($msg) {
    $ts = $nowET.ToString("yyyy-MM-dd HH:mm:ss ET")
    Add-Content -Path $log -Value "[$ts] $msg"
}

# Weekend guard
if ($nowET.DayOfWeek -in @([DayOfWeek]::Saturday, [DayOfWeek]::Sunday)) {
    Log "Skipped: weekend ($($nowET.DayOfWeek))"
    exit 0
}

# Stale-data guard: premarket closes ~9:30am; no point scanning after 4pm ET
if ($nowET.Hour -ge 16) {
    Log "Skipped: after 4pm ET ($($nowET.ToString('HH:mm')))"
    exit 0
}

# Duplicate-run guard: today's output file already exists
$today      = $nowET.ToString("yyyy-MM-dd")
$outputFile = Join-Path $workDir "premarket_gappers_$today.json"

if (Test-Path $outputFile) {
    Log "Skipped: already ran today (found $outputFile)"
    exit 0
}

# All checks passed — run the scan
Log "Starting scan (ET=$($nowET.ToString('HH:mm')), day=$($nowET.DayOfWeek))"
Set-Location $workDir

try {
    & "C:\Program Files\Git\bin\bash.exe" "premarket_gappers_scan.sh" 2>&1 | Tee-Object -Append -FilePath $log
    Log "Scan completed OK"
} catch {
    Log "Scan ERROR: $_"
    exit 1
}
