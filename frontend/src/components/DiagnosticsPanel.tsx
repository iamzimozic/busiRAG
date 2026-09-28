import type { Diagnostics } from "../api/rag";
import { formatMs, formatRetrievalMode, formatScore } from "./format";

type DiagnosticsPanelProps = {
  diagnostics: Diagnostics;
};

function DiagnosticsPanel({ diagnostics }: DiagnosticsPanelProps) {
  const { timings } = diagnostics;
  const otherMs = Math.max(
    timings.total_ms - timings.retrieval_ms - timings.generation_ms,
    0,
  );

  const segments = [
    { label: "Retrieval", ms: timings.retrieval_ms, className: "retrieval" },
    { label: "Generation", ms: timings.generation_ms, className: "generation" },
    { label: "Other", ms: otherMs, className: "other" },
  ];

  const hasRerankScores = diagnostics.retrieved.some(
    (chunk) => chunk.rerank_score !== null,
  );

  return (
    <details className="diagnostics">
      <summary>
        <span>Diagnostics</span>
        <span className="diagnostics-summary">
          <span
            className={`badge ${diagnostics.cache_hit ? "badge-hit" : ""}`}
          >
            {diagnostics.cache_hit ? "Cache hit" : "Cache miss"}
          </span>
          <span>{formatMs(timings.total_ms)}</span>
        </span>
      </summary>

      <div className="diagnostics-body">
        <dl className="diagnostics-facts">
          <div>
            <dt>Retrieval</dt>
            <dd>{formatRetrievalMode(diagnostics.retrieval_mode)}</dd>
          </div>
          <div>
            <dt>Model</dt>
            <dd>{diagnostics.generation_model ?? "—"}</dd>
          </div>
          <div>
            <dt>Request ID</dt>
            <dd className="mono">{diagnostics.request_id.slice(0, 8)}</dd>
          </div>
        </dl>

        <div className="latency">
          <div className="latency-title">Latency breakdown</div>

          {diagnostics.cache_hit ? (
            <p className="latency-note">
              Served from cache in {formatMs(timings.total_ms)}; retrieval
              and generation were skipped.
            </p>
          ) : (
            <>
              <div
                className="latency-bar"
                role="img"
                aria-label={segments
                  .map((segment) => `${segment.label} ${formatMs(segment.ms)}`)
                  .join(", ")}
              >
                {segments.map((segment) =>
                  segment.ms > 0 ? (
                    <span
                      key={segment.label}
                      className={`latency-segment ${segment.className}`}
                      style={{
                        width: `${(segment.ms / timings.total_ms) * 100}%`,
                      }}
                    />
                  ) : null,
                )}
              </div>

              <ul className="latency-legend">
                {segments.map((segment) => (
                  <li key={segment.label}>
                    <span
                      className={`legend-dot ${segment.className}`}
                      aria-hidden="true"
                    />
                    {segment.label} <strong>{formatMs(segment.ms)}</strong>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        {diagnostics.retrieved.length > 0 && (
          <div className="retrieved">
            <div className="latency-title">
              Retrieved chunks ({diagnostics.retrieved.length})
            </div>

            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Document</th>
                    <th scope="col" className="num">
                      Retrieval
                    </th>
                    {hasRerankScores && (
                      <th scope="col" className="num">
                        Rerank
                      </th>
                    )}
                    <th scope="col">Cited</th>
                  </tr>
                </thead>
                <tbody>
                  {diagnostics.retrieved.map((chunk) => (
                    <tr
                      key={chunk.chunk_id}
                      className={chunk.cited ? "cited" : ""}
                    >
                      <td>{chunk.citation_id}</td>
                      <td>
                        <span className="retrieved-doc">{chunk.filename}</span>
                        <span className="retrieved-meta">
                          {chunk.page_number !== null
                            ? `p. ${chunk.page_number} · `
                            : ""}
                          {chunk.element_type}
                        </span>
                      </td>
                      <td className="num mono">
                        {formatScore(chunk.retrieval_score)}
                      </td>
                      {hasRerankScores && (
                        <td className="num mono">
                          {formatScore(chunk.rerank_score)}
                        </td>
                      )}
                      <td>{chunk.cited ? "Yes" : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </details>
  );
}

export default DiagnosticsPanel;
