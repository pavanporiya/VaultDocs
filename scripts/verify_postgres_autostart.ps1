# VaultDocs - verify the auto-start VBS launcher actually works end-to-end
# 1) Stop Postgres  2) Launch via the same VBS the Startup shortcut uses  3) Wait  4) Check port 5433

$ErrorActionPreference = "Continue"

$pgCtl = "C:\Users\pavan\AppData\Local\Programs\pgsql\bin\pg_ctl.exe"
$data  = "C:\Users\pavan\AppData\Local\Programs\pgsql\data"
$vbs   = Join-Path $PSScriptRoot "start_postgres_hidden.vbs"

Write-Output "== STEP 1: stopping postgres =="
& $pgCtl -D $data -m fast stop
Start-Sleep -Seconds 2

$port = Test-NetConnection -ComputerName localhost -Port 5433 -InformationLevel Quiet -WarningAction SilentlyContinue
Write-Output ("PORT_5433_AFTER_STOP: " + $port)

Write-Output "== STEP 2: launching via VBS (simulates logon) =="
Start-Process -FilePath "wscript.exe" -ArgumentList ('"' + $vbs + '"') -WindowStyle Hidden
Start-Sleep -Seconds 8

$port2 = Test-NetConnection -ComputerName localhost -Port 5433 -InformationLevel Quiet -WarningAction SilentlyContinue
Write-Output ("PORT_5433_AFTER_VBS: " + $port2)

if ($port2) { Write-Output "RESULT: PASS - auto-start launcher works" }
else { Write-Output "RESULT: FAIL - postgres did not come up via VBS" }
