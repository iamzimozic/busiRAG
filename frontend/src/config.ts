// Build-time settings (Vite inlines VITE_* variables).

export const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL ?? "";
export const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD ?? "";

export const HAS_DEMO_LOGIN = Boolean(DEMO_EMAIL && DEMO_PASSWORD);

// Read-only public demo: hide registration and document management
// (the API rejects them too when DEMO_MODE=true).
export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

// Keep in sync with MAX_QUERY_LENGTH on the API (default 500).
export const MAX_QUERY_LENGTH =
  Number(import.meta.env.VITE_MAX_QUERY_LENGTH) || 500;
