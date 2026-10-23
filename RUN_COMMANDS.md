# VaultDocs — Local Execution & Operations Runbook

> **Last Updated:** October 2026  
> Comprehensive guide for provisioning, running, testing, and maintaining VaultDocs locally.

---

## Prerequisites

Ensure the following tools are installed on your workstation before starting:

| Tool | Minimum Version | Installation / Reference |
| :--- | :--- | :--- |
| **Python** | 3.11+ (3.13 recommended) | [python.org/downloads](https://www.python.org/downloads/) |
| **uv** | Latest | Astral Python Package Manager (*See Step 1*) |
| **Node.js** | 18+ LTS | [nodejs.org](https://nodejs.org) |
| **Docker Desktop** | Latest | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) |

### Environment Verification

Run the following commands in your terminal to verify your local toolchain:

```powershell
python --version
node --version
npm --version
docker --version
```

---

## Step-by-Step Setup Guide

### Step 0: Clone or Locate the Repository

For a clean setup:
```bash
git clone https://github.com/pavanporiya/VaultDocs.git
cd VaultDocs
```

If the repository is already present on your machine:
```bash
cd path/to/VaultDocs
```

---

### Step 1: Install `uv` Package Manager

If `uv` is not yet installed:

#### Windows (PowerShell)
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### macOS / Linux
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Verify Installation
```bash
uv --version
```

> [!NOTE]
> You may need to restart your terminal session after installation for `uv` to become available in your system `PATH`.

---

### Step 2: Provision the Database (PostgreSQL)

#### Option A: Docker Container with Persistent Volume (Recommended)

```bash
docker run -d --name vaultdocs-db -v vaultdocs-db-data:/var/lib/postgresql/data -e POSTGRES_DB=VaultDocs -e POSTGRES_USER=VaultDocs_user -e POSTGRES_PASSWORD=change-me-in-production -p 5433:5432 --restart unless-stopped postgres:16-alpine
```

> [!TIP]
> The `-v vaultdocs-db-data:/var/lib/postgresql/data` flag attaches a named Docker volume. Your database records remain persistent and safe across container stops, restarts, or rebuilds.

- **To stop the database container** (data remains preserved):
  ```bash
  docker stop vaultdocs-db
  ```
- **To restart the database container**:
  ```bash
  docker start vaultdocs-db
  ```

#### Option B: Docker Compose (Database Only)

```bash
docker compose up -d db
```

#### Option C: Native / Local PostgreSQL Instance
- Ensure the PostgreSQL service is running locally.
- Ensure the `VaultDocs` database exists.
- Adjust connection credentials in `.env` accordingly (*see Step 3*).

---

### Step 3: Configure Environment Variables (`.env`)

Create a `.env` file in the project root directory with the following contents:

```env
# --- Database Configuration ---
DATABASE_HOST=localhost
DATABASE_PORT=5433
DATABASE_NAME=VaultDocs
DATABASE_USER=VaultDocs_user
DATABASE_PASSWORD=change-me-in-production

# --- Application Configuration ---
APP_ENV=development
DEBUG=true
SECRET_KEY=change-this-to-any-random-secret-string
```

> [!IMPORTANT]
> - Never commit `.env` files into source control.
> - The credentials above directly match the Step 2 (Option A) Docker container configuration.

---

### Step 4: Install Backend Dependencies

From the project root:

```bash
uv sync
```

This synchronizes all required Python dependencies into an isolated virtual environment (`.venv`).

---

### Step 5: Execute Database Migrations

From the project root:

```bash
uv run alembic upgrade head
```

> [!NOTE]
> This command is idempotent. It safely applies pending schema migrations and ignores already-applied revisions.

---

### Step 6: Start the Backend API

From the project root:

```bash
uv run uvicorn vaultdocs.main:app --port 8000
```

Verify service availability in another terminal:

```bash
curl http://localhost:8000/v1/health
```

**Expected JSON Response:**
```json
{"status":"healthy","database":"connected"}
```

- **Interactive API Documentation (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Step 7: Start the Frontend Application

Open a new terminal window:

```bash
cd frontend
npm install
npm run dev
```

The Vite development server will report the active local address (typically `http://localhost:3000/`).

> [!NOTE]
> - If port 3000 is occupied, Vite will automatically select `3001` or `3002`. Always open the exact URL displayed in your terminal.
> - Vite automatically proxies `/v1` API requests to the backend server at `http://localhost:8000`.

---

## Daily Development Quick-Start

For routine development sessions, open three terminals:

| Terminal | Service | Command |
| :--- | :--- | :--- |
| **Terminal 1** | Database (if stopped) | `docker start vaultdocs-db` |
| **Terminal 2** | Backend API | `uv run uvicorn vaultdocs.main:app --port 8000` |
| **Terminal 3** | Frontend Dev Server | `cd frontend && npm run dev` |

- **Browser Access:** [http://localhost:3000](http://localhost:3000)

---

## Troubleshooting & Diagnostics

### 1. `relation "users" does not exist` or HTTP 500 during registration
- **Cause:** Database migrations have not been applied.
- **Fix:** Run migrations from the repository root:
  ```bash
  uv run alembic upgrade head
  ```

### 2. Port 8000 Conflict (`WinError 10048` / `address already in use`)
- **Cause:** A previously running backend process is holding port 8000.
- **Fix:** Terminate the occupying process:
  - **Windows (PowerShell/CMD):**
    ```powershell
    netstat -ano | findstr :8000
    taskkill /PID <PID_NUMBER> /F
    ```
  - **macOS / Linux:**
    ```bash
    kill $(lsof -t -i:8000)
    ```

### 3. Database Connection Refused or `database: disconnected`
- **Cause:** PostgreSQL container is stopped or connection details are mismatched.
- **Fix:**
  - Verify container status:
    ```bash
    docker ps
    ```
  - If container is stopped, launch it:
    ```bash
    docker start vaultdocs-db
    ```
  - Ensure `.env` database parameters (`localhost:5433`, user, password) match the container.

### 4. Frontend API / Network Errors (CORS or Gateway Failure)
- **Cause:** Backend server is not running on port 8000.
- **Fix:**
  - Check health: `curl http://localhost:8000/v1/health`
  - Restart the backend if it is unresponsive.

### 5. "Invalid email" error on Registration or Login
- **Cause:** Backend enforces RFC compliance and disallows non-routable domains (e.g., `.test` or `.local`).
- **Fix:** Use standard email formats (e.g., `user@example.com`).

### 6. `npm install` Dependency Conflicts
- **Cause:** Node version mismatch or corrupted node modules.
- **Fix:**
  - Check Node version (18+ required): `node --version`
  - Reset dependencies:
    ```bash
    cd frontend
    # Windows:
    rmdir /s /q node_modules
    del package-lock.json
    # macOS/Linux:
    rm -rf node_modules package-lock.json
    # Reinstall:
    npm install
    ```

### 7. `uv: command not found`
- **Cause:** Environment PATH variable not yet refreshed in the active terminal session.
- **Fix:** Restart your terminal session or run the installer script again.

### 8. Document Upload Errors
- **Cause:** File size exceeds maximum allowed upload limit.
- **Fix:** VaultDocs enforces a 10 MB per-file upload limit. Test with smaller documents.

---

## Optional: Full Docker Compose Mode

To run both backend and database services within Docker:

```bash
docker compose up -d --build
uv run alembic upgrade head
cd frontend && npm run dev
```

- **View backend logs:**
  ```bash
  docker compose logs -f app
  ```
- **Stop containers safely (volumes preserved):**
  ```bash
  docker compose down
  ```

> [!CAUTION]
> **DO NOT** execute `docker compose down -v`. The `-v` flag deletes named volumes and will permanently erase database records.

---

## Code Quality, Testing & Automation

### Backend Test Suite & Linters (Repository Root)

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy backend/src
uv run alembic check
```

> [!TIP]
> **Data Safety Guarantee:** `uv run pytest` connects exclusively to the isolated database `VaultDocs_test`. Built-in guards immediately abort the test run if any connection to the production or development database is detected.

### Database Backups & Restores

- **Manual Snapshot:** (Creates timestamped `.dump` under `backups/`)
  ```powershell
  powershell -File scripts/backup_postgres.ps1
  ```
- **Safe Restore:** (Restores snapshot into a dedicated target database)
  ```powershell
  powershell -File scripts/restore_postgres.ps1 -DumpFile "backups\<filename>.dump" -TargetDatabase "VaultDocs_restore_test"
  ```

### Frontend Validation

```bash
cd frontend
npm run lint
npm run build
```

### End-to-End Verification (With Backend and Frontend active)

```bash
node scripts/e2e-api-verify.mjs
node scripts/e2e-browser-qa.mjs http://localhost:3000
```

---

## Architecture & Operational Summary

| Component | Technology | Address / Port | Notes |
| :--- | :--- | :--- | :--- |
| **Backend API** | FastAPI (Python 3.11+) | `http://localhost:8000` | OpenAPI docs at `/docs` |
| **Frontend** | React 19 + Vite | `http://localhost:3000` | Proxies `/v1` to backend |
| **Database** | PostgreSQL 16 | `localhost:5433` | Database: `VaultDocs` |
| **Migrations** | Alembic | CLI | `uv run alembic upgrade head` |
| **Authentication**| JWT Bearer | Client Storage | Stored in `localStorage` |
