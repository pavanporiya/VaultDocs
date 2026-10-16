# =============================================================================
# VaultDocs - PostgreSQL Readiness & Startup Safety Guard
# =============================================================================
# Responsibilities:
# 1. Docker Desktop readiness check before DB commands.
# 2. Verifies expected persistent volume 'vaultdocs-db-data' exists.
#    FAILS LOUDLY if expected volume is missing (prevents silent empty DB creation).
# 3. Ensures container 'vaultdocs-db' is running with correct volume mount.
# 4. Verifies database connectivity and that 'VaultDocs' database exists.
#    FAILS LOUDLY if expected database is missing.
# 5. Ensures isolated 'VaultDocs_test' database exists for safe test execution.
# =============================================================================

param (
    [string]$ContainerName = "vaultdocs-db",
    [string]$VolumeName = "vaultdocs-db-data",
    [string]$DbUser = "VaultDocs_user",
    [string]$DbSecret = $(if ($env:DATABASE_PASSWORD) { $env:DATABASE_PASSWORD } else { "change-me-in-production" }),
    [string]$DbName = "VaultDocs",
    [string]$TestDbName = "VaultDocs_test",
    [int]$HostPort = 5433
)

$ErrorActionPreference = "Stop"

function Write-InfoLog { param ([string]$Message) Write-Output "[INFO] $Message" }
function Write-ErrorLog { param ([string]$Message) Write-Error "[ERROR] $Message" }

Write-InfoLog "Checking Docker Desktop readiness..."

# 1. Docker daemon check
& docker info >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-InfoLog "Docker daemon not responding. Attempting to start Docker Desktop..."
    $dockerDesktopPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerDesktopPath) {
        Start-Process -FilePath $dockerDesktopPath
    }

    $maxWait = 60
    $waited = 0
    while ($waited -lt $maxWait) {
        Start-Sleep -Seconds 3
        $waited += 3
        & docker info >$null 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-InfoLog "Docker Desktop is now ready."
            break
        }
        Write-InfoLog "Waiting for Docker Desktop... ($waited/$maxWait s)"
    }

    & docker info >$null 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "CRITICAL FAILURE: Docker Desktop is not running or unreachable. Please launch Docker Desktop and retry."
    }
} else {
    Write-InfoLog "Docker Desktop is active and responsive."
}

# 2. Verify named volume exists -- FAIL LOUDLY if missing
Write-InfoLog "Verifying persistent volume '$VolumeName'..."
$volList = (& docker volume ls -q --filter "name=^${VolumeName}$")
if (-not $volList -or "$volList".Trim() -ne $VolumeName) {
    throw "CRITICAL SAFETY VIOLATION: Expected Docker volume '$VolumeName' does NOT exist! " +
          "Refusing to start an unattached container that would silently create an empty database. " +
          "If this is a disaster recovery scenario, restore from D:\VaultDocs\backups first."
}
Write-InfoLog "Persistent volume '$VolumeName' verified."

# 3. Check container status
$containerRunning = (& docker inspect -f '{{.State.Running}}' $ContainerName 2>$null)

if ($containerRunning -eq "true") {
    Write-InfoLog "Container '$ContainerName' is currently running."

    # Verify mount
    $mounts = (& docker inspect -f '{{json .Mounts}}' $ContainerName 2>$null)
    if ($mounts -notmatch $VolumeName) {
        throw "CRITICAL SAFETY VIOLATION: Container '$ContainerName' is running but NOT mounted to '$VolumeName'! " +
              "Current mounts: $mounts"
    }
} elseif ($containerRunning -eq "false") {
    Write-InfoLog "Container '$ContainerName' exists but is stopped. Starting container..."
    & docker start $ContainerName | Out-Null
} else {
    Write-InfoLog "Container '$ContainerName' does not exist. Creating container with persistent volume '$VolumeName'..."
    & docker run -d `
        --name $ContainerName `
        -v "${VolumeName}:/var/lib/postgresql/data" `
        -e "POSTGRES_DB=$DbName" `
        -e "POSTGRES_USER=$DbUser" `
        -e "POSTGRES_PASSWORD=$DbSecret" `
        -p "${HostPort}:5432" `
        --restart unless-stopped `
        postgres:16-alpine | Out-Null

    # Connect to custom network if available
    & docker network connect vaultdocs-network $ContainerName 2>$null
}

# 4. Wait for PostgreSQL readiness
Write-InfoLog "Waiting for PostgreSQL to be ready on port $HostPort..."
$pgReady = $false
for ($i = 0; $i -lt 15; $i++) {
    & docker exec $ContainerName pg_isready -U $DbUser -d $DbName -q
    if ($LASTEXITCODE -eq 0) {
        $pgReady = $true
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $pgReady) {
    throw "CRITICAL FAILURE: PostgreSQL did not become ready within timeout."
}

# 5. Verify live database name and existence -- FAIL LOUDLY if missing
$liveDbCheck = (& docker exec $ContainerName psql -U $DbUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'")
if (-not $liveDbCheck -or "$liveDbCheck".Trim() -ne "1") {
    throw "CRITICAL SAFETY VIOLATION: Database '$DbName' does NOT exist inside PostgreSQL! " +
          "Refusing to silently initialize. Restore data from D:\VaultDocs\backups."
}
Write-InfoLog "Database '$DbName' verified and ready."

# 6. Ensure isolated test database exists
$testDbCheck = (& docker exec $ContainerName psql -U $DbUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$TestDbName'")
if (-not $testDbCheck -or "$testDbCheck".Trim() -ne "1") {
    Write-InfoLog "Creating isolated test database '$TestDbName'..."
    & docker exec $ContainerName createdb -U $DbUser -O $DbUser $TestDbName | Out-Null
    Write-InfoLog "Isolated test database '$TestDbName' created."
} else {
    Write-InfoLog "Isolated test database '$TestDbName' verified."
}

Write-InfoLog "POSTGRESQL READINESS CHECK COMPLETED SUCCESSFULLY."
exit 0
