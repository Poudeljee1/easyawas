# setup_trading_tasks.ps1
# Registers two Windows Task Scheduler tasks:
#   1. TJL_ScannerB       — runs run_scanner_b.ps1 every 1 hour, 10AM-3:30PM ET weekdays
#   2. TJL_PositionMonitor — runs run_position_monitor.ps1 every 5 min, 10AM-3:30PM ET weekdays
#
# Run once as Administrator (or current user — uses -RunLevel Limited by default).

$workDir    = "C:\Users\USER\hello"
$psExe      = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

# ── Helper: register a repeating daily task ───────────────────────────────────
function Register-RepeatingTask {
    param(
        [string]$TaskName,
        [string]$ScriptPath,
        [string]$StartTime,       # e.g. "10:00"
        [string]$RepeatInterval,  # ISO 8601 duration, e.g. "PT1H" or "PT5M"
        [string]$RepeatDuration,  # total window, e.g. "PT5H30M"
        [string]$Description
    )

    # Remove old task if it exists
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "  Removed existing task: $TaskName"
    }

    # Action
    $action = New-ScheduledTaskAction `
        -Execute $psExe `
        -Argument "-NonInteractive -WindowStyle Hidden -File `"$ScriptPath`"" `
        -WorkingDirectory $workDir

    # Trigger: daily at StartTime, Mon-Fri only
    # We use a daily trigger with a repetition pattern
    $trigger = New-ScheduledTaskTrigger -Daily -At $StartTime -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday

    # Add repetition via CIM instance
    $repInterval = (New-TimeSpan -Minutes 0)   # placeholder, replaced below
    $triggerXml  = $null   # use XML approach for fine-grained repetition

    # Build the task via XML for full control over repetition
    $xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <CalendarTrigger>
      <Repetition>
        <Interval>$RepeatInterval</Interval>
        <Duration>$RepeatDuration</Duration>
        <StopAtDurationEnd>true</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>2026-01-01T${StartTime}:00</StartBoundary>
      <ScheduleByWeek>
        <WeeksInterval>1</WeeksInterval>
        <DaysOfWeek>
          <Monday />
          <Tuesday />
          <Wednesday />
          <Thursday />
          <Friday />
        </DaysOfWeek>
      </ScheduleByWeek>
    </CalendarTrigger>
  </Triggers>
  <Actions Context="Author">
    <Exec>
      <Command>$psExe</Command>
      <Arguments>-NonInteractive -WindowStyle Hidden -File "$ScriptPath"</Arguments>
      <WorkingDirectory>$workDir</WorkingDirectory>
    </Exec>
  </Actions>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <RegistrationInfo>
    <Description>$Description</Description>
  </RegistrationInfo>
</Task>
"@

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Xml $xml `
        -Force | Out-Null

    Write-Host "  [OK] Registered: $TaskName"
    Write-Host "       Start=$StartTime  Interval=$RepeatInterval  Window=$RepeatDuration"
}

# ── Task 1: Scanner B — every 1 hour, 10:00 AM – 3:30 PM (5h30m window) ─────
Write-Host "`nRegistering Scanner B task..."
Register-RepeatingTask `
    -TaskName       "TJL_ScannerB" `
    -ScriptPath     "$workDir\run_scanner_b.ps1" `
    -StartTime      "10:00" `
    -RepeatInterval "PT1H" `
    -RepeatDuration "PT5H30M" `
    -Description    "TJL Scanner B: hourly gapper scan + auto paper trade, 10AM-3:30PM ET"

# ── Task 2: Position Monitor — every 5 minutes, 10:00 AM – 3:35 PM ───────────
Write-Host "`nRegistering Position Monitor task..."
Register-RepeatingTask `
    -TaskName       "TJL_PositionMonitor" `
    -ScriptPath     "$workDir\run_position_monitor.ps1" `
    -StartTime      "10:00" `
    -RepeatInterval "PT5M" `
    -RepeatDuration "PT5H35M" `
    -Description    "TJL Position Monitor: TP/SL/EOD check every 5 min, 10AM-3:35PM ET"

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host "`n--- Registered Tasks ---"
Get-ScheduledTask | Where-Object { $_.TaskName -like "TJL_*" } | ForEach-Object {
    $info = $_ | Get-ScheduledTaskInfo
    $nxt  = if ($info.NextRunTime) { $info.NextRunTime.ToString("yyyy-MM-dd HH:mm") } else { "N/A" }
    Write-Host ("  {0,-26}  Next run: {1}" -f $_.TaskName, $nxt)
}

Write-Host "`nDone. Both tasks are active."
Write-Host "Logs: $workDir\scanner_b.log  and  $workDir\position_monitor.log"
