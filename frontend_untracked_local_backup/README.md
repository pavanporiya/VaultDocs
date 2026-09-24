# VaultDocs Frontend

React + TypeScript SPA for the VaultDocs API (backend lives in `/backend`, frozen at MVP).

## Stack

- React 18 + TypeScript (strict)
- Vite 7
- Tailwind CSS 4 (via `@tailwindcss/vite`)
- shadcn/ui foundation (`components.json`, `cn` helper) — no components generated yet
- TanStack Query v5
- React Router v7

## Development

```bash
npm install
npm run dev      # http://localhost:5173
```

The dev server proxies `/v1/*` to the FastAPI backend at `http://localhost:8000`
(see `vite.config.ts`), so no CORS middleware is needed on the backend.

Start the backend first:

```bash
# repo root
uv run uvicorn vaultdocs.main:app --reload
```

## Scripts

| Script         | Purpose                             |
| -------------- | ----------------------------------- |
| `dev`          | Vite dev server (port 5173, strict) |
| `build`        | `tsc -b` + production bundle        |
| `preview`      | Preview the production build        |
| `lint`         | ESLint (type-checked)               |
| `format`       | Prettier write                      |
| `format:check` | Prettier check                      |
| `typecheck`    | TypeScript project build check      |

## Environment

Copy `.env.example` to `.env.local` if you need to override the API base URL.
Leave `VITE_API_BASE_URL` empty in development — the Vite proxy handles `/v1`.

Never store secrets in `VITE_*` variables; they are bundled into client code.

## shadcn/ui

Foundation is configured (`components.json`, aliases, `src/lib/utils.ts`).
Add components when needed:

```bash
npx shadcn@latest add button dialog ...
```
