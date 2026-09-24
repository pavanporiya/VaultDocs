# VaultDocs - one-time setup: PostgreSQL auto-start at Windows logon (no admin needed)
# Creates a shortcut in the user's Startup folder pointing to the hidden VBS launcher.

$ErrorActionPreference = "Stop"

$startupDir = [Environment]::GetFolderPath("Startup")
$linkPath = Join-Path $startupDir "VaultDocs-Postgres.lnk"
$vbsPath = Join-Path $PSScriptRoot "start_postgres_hidden.vbs"

if (-not (Test-Path $vbsPath)) {
    throw "VBS launcher not found: $vbsPath"
}

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($linkPath)
$sc.TargetPath = "C:\Windows\System32\wscript.exe"
$sc.Arguments = '"' + $vbsPath + '"'
$sc.WindowStyle = 7   # minimized/hidden
$sc.Description = "Start VaultDocs PostgreSQL at logon"
$sc.Save()

Write-Output "STARTUP_SHORTCUT_CREATED: $linkPath"
Write-Output "POINTS_TO: $vbsPath"
