' VaultDocs - PostgreSQL auto-start (hidden window, runs at logon)
' Installed in: C:\Users\pavan\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup
Set shell = CreateObject("WScript.Shell")

PG_BIN = "C:\Users\pavan\AppData\Local\Programs\pgsql\bin\pg_ctl.exe"
PG_DATA = "C:\Users\pavan\AppData\Local\Programs\pgsql\data"
PG_LOG = "C:\Users\pavan\AppData\Local\Programs\pgsql\pg_server.log"

' 0 = hidden window, False = don't wait
shell.Run """" & PG_BIN & """ -D """ & PG_DATA & """ -l """ & PG_LOG & """ start", 0, False
