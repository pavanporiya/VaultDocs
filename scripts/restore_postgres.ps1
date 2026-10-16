# =============================================================================
# VaultDocs - Safe PostgreSQL Restore Script
# =============================================================================
# Restores a custom format PostgreSQL dump (.dump) into a specified target database.
# Defaults to a temporary verification database 'VaultDocs_restore_test' to prevent
# accidental overwriting of development data.
# =============================================================================

param (
    [Parameter(Mandatory = $true)]
    [string]$DumpFile,

    [string]$TargetDatabase = "VaultDocs_restore_test",
    [string]$ContainerName = "vaultdocs-db",
    [string]$DbUser = "VaultDocs_user"
)

$ErrorActionPreference = "Stop"

function Write-LogMessage {
    param ([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Output "[$ts] $Message"
}

try {
    # 1. Resolve and verify dump file on host
    if (-not (Test-Path $DumpFile)) {
        throw "Dump file not found: '$DumpFile'"
    }

    $dumpItem = Get-Item $DumpFile
    $dumpPath = $dumpItem.FullName
    if ($dumpItem.Length -le 0) {
        throw "Dump file is empty (0 bytes): '$dumpPath'"
    }

    Write-LogMessage "Starting restore test for '$($dumpItem.Name)' into database '$TargetDatabase'..."

    # 2. Check container
    $containerStatus = (& docker inspect -f '{{.State.Running}}' $ContainerName 2>$null)
    if ($containerStatus -ne "true") {
        throw "Container '$ContainerName' is not running."
    }

    # 3. Create target database if it doesn't already exist
    Write-LogMessage "Ensuring target database '$TargetDatabase' exists..."
    $dbExists = (& docker exec $ContainerName psql -U $DbUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$TargetDatabase'")
    if (-not $dbExists -or "$dbExists".Trim() -ne "1") {
        & docker exec $ContainerName createdb -U $DbUser -O $DbUser $TargetDatabase | Out-Null
        Write-LogMessage "Created database '$TargetDatabase'."
    } else {
        Write-LogMessage "Target database '$TargetDatabase' already exists."
    }

    # 4. Copy dump to container
    $containerDump = "/tmp/restore_in_progress.dump"
    Write-LogMessage "Copying dump file to container..."
    & docker cp "$dumpPath" "${ContainerName}:$containerDump"

    # 5. Execute pg_restore
    Write-LogMessage "Restoring dump into '$TargetDatabase'..."
    # Note: pg_restore might emit exit code 1 if non-critical warnings (like objects to drop not existing)
    $restoreOutput = & docker exec $ContainerName pg_restore -U $DbUser -d "$TargetDatabase" --clean --if-exists --no-owner --no-privileges "$containerDump" 2>&1
    if ($LASTEXITCODE -gt 1) {
        throw "pg_restore failed with exit code $LASTEXITCODE. Details: $restoreOutput"
    }
    if ($restoreOutput) {
        Write-LogMessage "pg_restore diagnostic output: $restoreOutput"
    }

    # Clean up container temp file
    & docker exec $ContainerName rm -f "$containerDump"

    # 6. Verify restored data
    Write-LogMessage "Verifying restored tables and data in '$TargetDatabase'..."
    $tables = & docker exec $ContainerName psql -U $DbUser -d "$TargetDatabase" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
    $userCount = & docker exec $ContainerName psql -U $DbUser -d "$TargetDatabase" -tAc "SELECT count(*) FROM users" 2>$null
    $docCount = & docker exec $ContainerName psql -U $DbUser -d "$TargetDatabase" -tAc "SELECT count(*) FROM documents" 2>$null

    Write-LogMessage "RESTORE_VERIFICATION_RESULTS:"
    Write-LogMessage "  - Public tables count : $("$tables".Trim())"
    Write-LogMessage "  - Users count         : $("$userCount".Trim())"
    Write-LogMessage "  - Documents count     : $("$docCount".Trim())"

    if ([int]("$tables".Trim()) -lt 5) {
        throw "Restore verification failed: expected at least 5 tables, found $("$tables".Trim())"
    }

    Write-LogMessage "SUCCESS: Database '$TargetDatabase' successfully restored and verified from '$($dumpItem.Name)'."
    exit 0
}
catch {
    Write-LogMessage "ERROR: Restore failed: $($_.Exception.Message)"
    exit 1
}
