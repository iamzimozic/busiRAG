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

export async function queryRAG(query: string): Promise<QueryResponse> {
  const response = await fetch(`${API_BASE_URL}/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
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

  const response = await fetch(`${API_BASE_URL}/documents`, {
    method: "POST",
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
  const response = await fetch(
    `${API_BASE_URL}/documents/${documentId}`,
    {
      method: "DELETE",
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