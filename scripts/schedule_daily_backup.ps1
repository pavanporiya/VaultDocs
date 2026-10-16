# =============================================================================
# VaultDocs - Register Daily PostgreSQL Backup in Windows Task Scheduler
# =============================================================================
# Schedules daily execution of D:\VaultDocs\scripts\backup_postgres.ps1
# Runs with current user privileges without requiring a visible window.
# =============================================================================

param (
    [string]$TaskName = "VaultDocs-Daily-PostgreSQL-Backup",
    [string]$DailyTime = "03:00"
)

$ErrorActionPreference = "Stop"

$scriptPath = "D:\VaultDocs\scripts\backup_postgres.ps1"
if (-not (Test-Path $scriptPath)) {
    throw "Backup script not found: $scriptPath"
}

Write-Output "Configuring scheduled task '$TaskName' to run daily at $DailyTime..."

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`""

$trigger = New-ScheduledTaskTrigger -Daily -At $DailyTime

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

# Unregister if previously existed
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Automated daily custom-format backup of VaultDocs PostgreSQL database" | Out-Null

Write-Output "SUCCESS: Scheduled task '$TaskName' registered successfully."
Write-Output "Task will run daily at $DailyTime."
