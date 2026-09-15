export interface Source {
  citation_id: string;
  company: string;
  year: number;
  page_number: number | null;
  chunk_id: number;
}

export interface QueryResponse {
  answer: string;
  sources: Source[];
}

const API_BASE_URL = "http://127.0.0.1:8000";

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
      error?.message || `Request failed with status ${response.status}`,
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