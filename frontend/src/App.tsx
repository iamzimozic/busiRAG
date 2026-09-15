import Auth from "./Auth";
import { useEffect, useState } from "react";
import "./App.css";
import {
  deleteDocument,
  queryRAG,
  uploadDocument,
  type Source,
} from "./api/rag";

type UserMessage = {
  role: "user";
  content: string;
};

type AssistantMessage = {
  role: "assistant";
  content: string;
  sources: Source[];
};

type Message = UserMessage | AssistantMessage;

type Document = {
  id: number;
  company: string;
  year: number;
  filename: string;
};

type Page = "knowledge-base" | "documents" | "settings";

const API_BASE_URL = "http://127.0.0.1:8000";

function App() {
  const [page, setPage] = useState<Page>("knowledge-base");

  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [documents, setDocuments] = useState<Document[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentsError, setDocumentsError] = useState<string | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [company, setCompany] = useState("");
  const [year, setYear] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [authenticated, setAuthenticated] = useState(
    () => Boolean(localStorage.getItem("access_token")),
  );

  useEffect(() => {
    function handleAuthExpired() {
      setAuthenticated(false);
    }

    window.addEventListener("auth-expired", handleAuthExpired);

    return () => {
      window.removeEventListener("auth-expired", handleAuthExpired);
    };
  }, []);

  if (!authenticated) {
    return <Auth onAuthenticated={() => setAuthenticated(true)} />;
  }

  useEffect(() => {
    if (page !== "documents") {
      return;
    }

    async function loadDocuments() {
      setDocumentsLoading(true);
      setDocumentsError(null);

      try {
        const token = localStorage.getItem("access_token");

        const response = await fetch(`${API_BASE_URL}/documents`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error(
            `Failed to load documents (${response.status})`,
          );
        }

        const data: Document[] = await response.json();
        setDocuments(data);
      } catch (err) {
        setDocumentsError(
          err instanceof Error
            ? err.message
            : "Something went wrong while loading documents.",
        );
      } finally {
        setDocumentsLoading(false);
      }
    }

    loadDocuments();
  }, [page]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    const trimmedQuery = query.trim();

    if (!trimmedQuery || loading) {
      return;
    }

    const userMessage: UserMessage = {
      role: "user",
      content: trimmedQuery,
    };

    setMessages((current) => [...current, userMessage]);
    setQuery("");
    setLoading(true);
    setError(null);

    try {
      const result = await queryRAG(trimmedQuery);

      const assistantMessage: AssistantMessage = {
        role: "assistant",
        content: result.answer,
        sources: result.sources,
      };

      setMessages((current) => [...current, assistantMessage]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while querying BusiRAG.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(event: React.FormEvent) {
  event.preventDefault();

  if (!selectedFile || !company.trim() || !year) {
    setUploadMessage("Please select a file, company, and year.");
    return;
  }

  setUploading(true);
  setUploadMessage(null);

  try {
    await uploadDocument(
      selectedFile,
      company.trim(),
      Number(year),
    );

    setUploadMessage("Document uploaded successfully.");

    setSelectedFile(null);
    setCompany("");
    setYear("");

    const token = localStorage.getItem("access_token");

    const response = await fetch(`${API_BASE_URL}/documents`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.ok) {
      const data: Document[] = await response.json();
      setDocuments(data);
    }
  } catch (err) {
    setUploadMessage(
      err instanceof Error
        ? err.message
        : "Something went wrong while uploading the document.",
    );
  } finally {
    setUploading(false);
  }
}

async function handleDelete(documentId: number) {
  const confirmed = window.confirm(
    "Are you sure you want to delete this document?",
  );

  if (!confirmed) {
    return;
  }

  try {
    await deleteDocument(documentId);

    setDocuments((current) =>
      current.filter((document) => document.id !== documentId),
    );
  } catch (err) {
    setDocumentsError(
      err instanceof Error
        ? err.message
        : "Something went wrong while deleting the document.",
    );
  }
}

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">BusiRAG</div>

        <nav className="navigation">
          <button
            className={`nav-item ${
              page === "knowledge-base" ? "active" : ""
            }`}
            onClick={() => setPage("knowledge-base")}
          >
            Knowledge Base
          </button>

          <button
            className={`nav-item ${
              page === "documents" ? "active" : ""
            }`}
            onClick={() => setPage("documents")}
          >
            Documents
          </button>

          <button
            className={`nav-item ${
              page === "settings" ? "active" : ""
            }`}
            onClick={() => setPage("settings")}
          >
            Settings
          </button>
        </nav>

        <div className="sidebar-footer">
          <span className="status-dot" />
          System online
        </div>
      </aside>

      <main className="main">
        <header className="header">
          <div>
            <p className="eyebrow">
              {page === "documents"
                ? "Knowledge Base"
                : page === "settings"
                  ? "Workspace"
                  : "Knowledge Base"}
            </p>

            <h1>
              {page === "documents"
                ? "Documents"
                : page === "settings"
                  ? "Settings"
                  : "Financial & Business Intelligence"}
            </h1>
          </div>

          <div className="profile">
            <div className="avatar">U</div>
            <span>User</span>
            <button
              type="button"
              onClick={() => {
                localStorage.removeItem("access_token");
                setAuthenticated(false);
              }}
            >
              Logout
            </button>
          </div>
        </header>

        <section className="content">
          {page === "knowledge-base" && (
            <>
              <div className="welcome">
                <p className="eyebrow">BusiRAG</p>
                <h2>Ask your knowledge base anything.</h2>
                <p>
                  Search your business documents and get answers grounded in
                  your data.
                </p>
              </div>

              <div className="chat-card">
                <div className="conversation">
                  {messages.length === 0 && !loading && !error && (
                    <div className="empty-state">
                      <div className="empty-icon">?</div>
                      <h3>Start a conversation</h3>
                      <p>
                        Ask a question about the documents in your knowledge
                        base.
                      </p>
                    </div>
                  )}

                  {messages.length > 0 && (
                    <div className="messages">
                      {messages.map((message, index) => (
                        <div
                          className={`message ${message.role}`}
                          key={`${message.role}-${index}`}
                        >
                          <div className="message-label">
                            {message.role === "user" ? "You" : "BusiRAG"}
                          </div>

                          <div className="message-content">
                            {message.content}
                          </div>

                          {message.role === "assistant" &&
                            message.sources.length > 0 && (
                              <div className="sources">
                                <div className="sources-title">Sources</div>

                                <div className="source-list">
                                  {message.sources.map((source) => (
                                    <div
                                      className="source"
                                      key={`${source.citation_id}-${source.chunk_id}`}
                                    >
                                      <div className="source-citation">
                                        {source.citation_id}
                                      </div>

                                      <div className="source-details">
                                        <strong>{source.company}</strong>
                                        <span>
                                          {source.year}
                                          {source.page_number !== null
                                            ? ` · Page ${source.page_number}`
                                            : ""}
                                        </span>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                        </div>
                      ))}
                    </div>
                  )}

                  {loading && (
                    <div className="loading-state">
                      <div className="loading-spinner" />
                      <p>Searching your knowledge base...</p>
                    </div>
                  )}

                  {error && (
                    <div className="error-state">
                      <h3>Something went wrong</h3>
                      <p>{error}</p>
                    </div>
                  )}
                </div>

                <form className="input-area" onSubmit={handleSubmit}>
                  <input
                    type="text"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Ask a question..."
                    aria-label="Ask a question"
                    disabled={loading}
                  />

                  <button
                    className="send-button"
                    type="submit"
                    disabled={loading || !query.trim()}
                  >
                    {loading ? "Searching..." : "Send"}
                  </button>
                </form>
              </div>
            </>
          )}

          {page === "documents" && (
            <div className="documents-page">
              <div className="upload-card">
                <div className="upload-header">
                  <div>
                    <p className="eyebrow">Knowledge Base</p>
                    <h3>Upload a document</h3>
                    <p>Add a PDF or DOCX to your knowledge base.</p>
                  </div>
                </div>

                <form className="upload-form" onSubmit={handleUpload}>
                  <label className="file-input">
                    <span>Document</span>
                    <input
                      type="file"
                      accept=".pdf,.docx"
                      onChange={(event) =>
                        setSelectedFile(event.target.files?.[0] ?? null)
                      }
                    />
                    {selectedFile && (
                      <small>{selectedFile.name}</small>
                    )}
                  </label>

                  <label>
                    <span>Company</span>
                    <input
                      type="text"
                      value={company}
                      onChange={(event) => setCompany(event.target.value)}
                      placeholder="e.g. apple"
                    />
                  </label>

                  <label>
                    <span>Year</span>
                    <input
                      type="number"
                      value={year}
                      onChange={(event) => setYear(event.target.value)}
                      placeholder="e.g. 2026"
                      min="1900"
                      max="2100"
                    />
                  </label>

                  <button
                    className="send-button upload-button"
                    type="submit"
                    disabled={uploading}
                  >
                    {uploading ? "Uploading..." : "Upload document"}
                  </button>
                </form>

                {uploadMessage && (
                  <div className="upload-message">
                    {uploadMessage}
                  </div>
                )}
              </div>
              <div className="welcome">
                <p className="eyebrow">Knowledge Base</p>
                <h2>Your documents.</h2>
                <p>
                  Documents currently indexed and available to BusiRAG.
                </p>
              </div>

              {documentsLoading && (
                <div className="loading-state">
                  <div className="loading-spinner" />
                  <p>Loading documents...</p>
                </div>
              )}

              {documentsError && (
                <div className="error-state">
                  <h3>Could not load documents</h3>
                  <p>{documentsError}</p>
                </div>
              )}

              {!documentsLoading &&
                !documentsError &&
                documents.length === 0 && (
                  <div className="empty-state">
                    <div className="empty-icon">+</div>
                    <h3>No documents yet</h3>
                    <p>
                      Upload a document to start building your knowledge base.
                    </p>
                  </div>
                )}

              {!documentsLoading &&
                !documentsError &&
                documents.length > 0 && (
                  <div className="documents-card">
                    <div className="documents-header">
                    <span>Document</span>
                    <span>Company</span>
                    <span>Year</span>
                    <span></span>
                  </div>

                    {documents.map((document) => (
                      <div className="document-row" key={document.id}>
                        <div className="document-name">
                          <div className="document-icon">PDF</div>
                          <div>
                            <strong>{document.filename}</strong>
                            <span>ID #{document.id}</span>
                          </div>
                        </div>

                        <div className="document-company">
                          {document.company}
                        </div>

                        <div className="document-year">
                          {document.year}
                        </div>
                        <button
                          className="delete-button"
                          type="button"
                          onClick={() => handleDelete(document.id)}
                        >
                          Delete
                        </button>
                      </div>
                    ))}
                  </div>
                )}
            </div>
          )}

          {page === "settings" && (
            <div className="welcome">
              <p className="eyebrow">Workspace</p>
              <h2>Settings.</h2>
              <p>Workspace settings will be available here later.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;