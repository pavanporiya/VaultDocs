/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL for the VaultDocs API. Empty in dev (Vite proxy handles /v1). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
