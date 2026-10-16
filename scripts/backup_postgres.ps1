# =============================================================================
# VaultDocs - Automated PostgreSQL Backup Script
# =============================================================================
# Features:
# - Custom format backup (pg_dump -Fc)
# - Timestamped filenames: vaultdocs_YYYYMMDD_HHMMSS.dump
# - Verifies non-zero file size and valid custom-format TOC
# - Retention: retains last 7 daily backups
# - Safe guard: NEVER deletes the latest successful backup
# - Detailed logging to D:\VaultDocs\backups\backup.log
# =============================================================================

param (
    [string]$BackupDir = "D:\VaultDocs\backups",
    [string]$ContainerName = "vaultdocs-db",
    [string]$DbUser = "VaultDocs_user",
    [string]$DbName = "VaultDocs",
    [int]$RetentionCount = 7
)

$ErrorActionPreference = "Stop"

function Write-LogMessage {
    param (
        [string]$Level,
        [string]$Message
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logLine = "[$timestamp] [$Level] $Message"
    Write-Output $logLine
    $logFile = Join-Path $BackupDir "backup.log"
    Add-Content -Path $logFile -Value $logLine -ErrorAction SilentlyContinue
}

try {
    # 1. Ensure backup directory exists
    if (-not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
    }

    Write-LogMessage "INFO" "Starting PostgreSQL backup for database '$DbName'..."

    # 2. Check Docker availability
    & docker info >$null 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker daemon / Docker Desktop is not running or unreachable."
    }

    # 3. Check container status
    $containerStatus = (& docker inspect -f '{{.State.Running}}' $ContainerName 2>$null)
    if ($containerStatus -ne "true") {
        Write-LogMessage "WARN" "Container '$ContainerName' is not running. Attempting to start it..."
        & docker start $ContainerName | Out-Null
        Start-Sleep -Seconds 4
        $containerStatus = (& docker inspect -f '{{.State.Running}}' $ContainerName 2>$null)
        if ($containerStatus -ne "true") {
            throw "Container '$ContainerName' could not be started."
        }
    }

    # 4. Check PostgreSQL connectivity
    & docker exec $ContainerName pg_isready -U $DbUser -d $DbName -q
    if ($LASTEXITCODE -ne 0) {
        throw "PostgreSQL database '$DbName' is not ready to accept connections."
    }

    # 5. Generate timestamp and paths
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $dumpFileName = "vaultdocs_$timestamp.dump"
    $dumpFilePath = Join-Path $BackupDir $dumpFileName
    $containerDumpPath = "/tmp/$dumpFileName"

    # 6. Execute pg_dump -Fc inside container
    Write-LogMessage "INFO" "Executing pg_dump -Fc inside container '$ContainerName'..."
    & docker exec $ContainerName pg_dump -U $DbUser -Fc $DbName -f $containerDumpPath
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed with exit code $LASTEXITCODE"
    }

    # 7. Copy dump to host backup directory
    & docker cp "${ContainerName}:$containerDumpPath" "$dumpFilePath"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy dump file from container to host."
    }

    # Clean up container temporary file
    & docker exec $ContainerName rm -f "$containerDumpPath"

    # 8. Verify backup file exists and has non-zero size
    if (-not (Test-Path $dumpFilePath)) {
        throw "Backup verification failed: '$dumpFilePath' does not exist."
    }

    $fileInfo = Get-Item $dumpFilePath
    $fileBytes = $fileInfo.Length
    if ($fileBytes -le 0) {
        throw "Backup verification failed: '$dumpFilePath' is empty (0 bytes)."
    }

    # Verify custom format TOC readability
    $tocOutput = (& docker run --rm -v "${dumpFilePath}:/backup.dump:ro" postgres:16-alpine pg_restore -l /backup.dump 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Backup verification failed: pg_restore could not read TOC of '$dumpFilePath'. Details: $tocOutput"
    }

    Write-LogMessage "SUCCESS" "Backup created and verified: $dumpFileName (Size: $fileBytes bytes)"

    # 9. Retention policy (retain last $RetentionCount backups, never delete latest)
    $allBackups = Get-ChildItem -Path $BackupDir -Filter "vaultdocs_*.dump" | Sort-Object LastWriteTime -Descending

    if ($allBackups.Count -gt $RetentionCount) {
        Write-LogMessage "INFO" "Applying retention policy: found $($allBackups.Count) backups, retaining newest $RetentionCount..."
        # Skip the newest $RetentionCount backups (index 0 through $RetentionCount - 1)
        $oldBackups = $allBackups | Select-Object -Skip $RetentionCount
        foreach ($old in $oldBackups) {
            # Hard guard: never delete the latest successful backup
            if ($old.FullName -eq $dumpFilePath) {
                continue
            }
            try {
                Remove-Item -Path $old.FullName -Force
                Write-LogMessage "INFO" "Rotated old backup: $($old.Name)"
            } catch {
                Write-LogMessage "WARN" "Failed to remove old backup '$($old.Name)': $($_.Exception.Message)"
            }
        }
    }

    Write-LogMessage "SUCCESS" "Backup job completed successfully."
    exit 0
}
catch {
    Write-LogMessage "ERROR" "Backup job failed: $($_.Exception.Message)"
    exit 1
}
