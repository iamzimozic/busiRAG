/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_DEMO_EMAIL?: string;
  readonly VITE_DEMO_PASSWORD?: string;
  readonly VITE_DEMO_MODE?: string;
  readonly VITE_MAX_QUERY_LENGTH?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
