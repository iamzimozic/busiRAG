import { useState } from "react";
import type { Source } from "../api/rag";
import { formatElementType, formatScore } from "./format";

type SourceListProps = {
  sources: Source[];
};

function SourceList({ sources }: SourceListProps) {
  const [openId, setOpenId] = useState<string | null>(null);

  if (sources.length === 0) {
    return (
      <div className="sources sources-empty">
        No sources cited. The indexed documents may not contain this answer.
      </div>
    );
  }

  return (
    <div className="sources">
      <div className="sources-title">Sources</div>

      <ul className="source-list">
        {sources.map((source) => {
          const key = `${source.citation_id}-${source.chunk_id}`;
          const isOpen = openId === key;
          const panelId = `source-panel-${key}`;
          const elementType = formatElementType(source.element_type);

          return (
            <li className={`source ${isOpen ? "open" : ""}`} key={key}>
              <button
                type="button"
                className="source-toggle"
                aria-expanded={isOpen}
                aria-controls={panelId}
                onClick={() => setOpenId(isOpen ? null : key)}
              >
                <span className="source-citation">{source.citation_id}</span>

                <span className="source-details">
                  <strong>{source.filename}</strong>
                  <span>
                    <span className="source-company">{source.company}</span>
                    {` · ${source.year}`}
                    {source.page_number !== null
                      ? ` · Page ${source.page_number}`
                      : ""}
                  </span>
                </span>

                <span className="source-chevron" aria-hidden="true">
                  {isOpen ? "−" : "+"}
                </span>
              </button>

              {isOpen && (
                <div className="source-panel" id={panelId}>
                  <div className="source-meta">
                    {elementType && <span>{elementType}</span>}
                    {source.section && <span>{source.section}</span>}
                    {source.retrieval_score !== null && (
                      <span>
                        Retrieval {formatScore(source.retrieval_score)}
                      </span>
                    )}
                    {source.rerank_score !== null && (
                      <span>Rerank {formatScore(source.rerank_score)}</span>
                    )}
                  </div>

                  <blockquote className="source-text">
                    {source.text ?? "Source text is not available."}
                  </blockquote>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default SourceList;
