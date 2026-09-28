export interface Source {
  citation_id: string;
  company: string;
  filename: string;
  year: number;
  page_number: number | null;
  chunk_id: number;
  section: string | null;
  element_type: string | null;
  text: string | null;
  retrieval_score: number | null;
  rerank_score: number | null;
}

export interface RetrievedChunk {
  citation_id: string;
  chunk_id: number;
  company: string;
  filename: string;
  year: number;
  page_number: number | null;
  element_type: string;
  retrieval_score: number | null;
  rerank_score: number | null;
  cited: boolean;
}

export interface Diagnostics {
  request_id: string;
  cache_hit: boolean;
  retrieval_mode: string;
  generation_model: string | null;
  timings: {
    retrieval_ms: number;
    generation_ms: number;
    total_ms: number;
  };
  retrieved: RetrievedChunk[];
}

export interface QueryResponse {
  answer: string;
  sources: Source[];
  diagnostics: Diagnostics | null;
}

export interface Document {
  id: number;
  company: string;
  year: number;
  filename: string;
}

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

// FastAPI returns {detail: string}, {detail: [{msg}]} for validation
// errors, and BusiRAG's own handlers return {message}.
function errorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === "object") {
    const body = error as {
      detail?: string | { msg?: string }[];
      message?: string;
    };

    if (typeof body.detail === "string") {
      return body.detail;
    }

    if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      return body.detail[0].msg;
    }

    if (body.message) {
      return body.message;
    }
  }

  return fallback;
}

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("access_token");

  if (!token) {
    throw new Error("Not authenticated");
  }

  return {
    Authorization: `Bearer ${token}`,
  };
}

async function authenticatedFetch(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      ...getAuthHeaders(),
    },
  });

  if (response.status === 401) {
    localStorage.removeItem("access_token");
    window.dispatchEvent(new Event("auth-expired"));
  }

  return response;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export async function registerUser(
  email: string,
  password: string,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);

    throw new Error(
      error?.detail ||
        error?.message ||
        `Registration failed with status ${response.status}`,
    );
  }
}

export async function loginUser(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);

    throw new Error(
      error?.detail ||
        error?.message ||
        `Login failed with status ${response.status}`,
    );
  }

  return response.json();
}

export async function queryRAG(query: string): Promise<QueryResponse> {
  const response = await authenticatedFetch(`${API_BASE_URL}/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);

    throw new Error(
      errorMessage(error, `Request failed with status ${response.status}`),
    );
  }

  return response.json();
}

export async function listDocuments(): Promise<Document[]> {
  const response = await authenticatedFetch(`${API_BASE_URL}/documents`);

  if (!response.ok) {
    const error = await response.json().catch(() => null);

    throw new Error(
      error?.detail ||
        error?.message ||
        `Failed to load documents (${response.status})`,
    );
  }

  return response.json();
}

export interface Workspace {
  id: number;
  name: string;
  created_at: string;
}

export async function getWorkspace(): Promise<Workspace> {
  const response = await authenticatedFetch(`${API_BASE_URL}/workspace`);

  if (!response.ok) {
    const error = await response.json().catch(() => null);

    throw new Error(
      error?.detail ||
        error?.message ||
        `Failed to load workspace (${response.status})`,
    );
  }

  return response.json();
}

export interface CurrentUser {
  id: number;
  email: string;
  tenant_id: number;
  created_at: string;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  const response = await authenticatedFetch(`${API_BASE_URL}/auth/me`);

  if (!response.ok) {
    const error = await response.json().catch(() => null);

    throw new Error(
      error?.detail ||
        error?.message ||
        `Failed to load user (${response.status})`,
    );
  }

  return response.json();
}

export async function uploadDocument(
  file: File,
  company: string,
  year: number,
): Promise<void> {
  const formData = new FormData();

  formData.append("file", file);
  formData.append("company", company);
  formData.append("year", String(year));

  const response = await authenticatedFetch(`${API_BASE_URL}/documents`, {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);

    throw new Error(
      error?.detail ||
        error?.message ||
        `Upload failed with status ${response.status}`,
    );
  }
}

export async function deleteDocument(documentId: number): Promise<void> {
  const response = await authenticatedFetch(
    `${API_BASE_URL}/documents/${documentId}`,
    {
      method: "DELETE",
      headers: {
        ...getAuthHeaders(),
      },
    },
  );

  if (!response.ok) {
    const error = await response.json().catch(() => null);

    throw new Error(
      error?.detail ||
        error?.message ||
        `Delete failed with status ${response.status}`,
    );
  }
}