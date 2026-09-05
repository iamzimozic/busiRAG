from pathlib import Path

from busirag.ingestion import discover_documents


documents = discover_documents(Path("data/raw"))

print(f"Found {len(documents)} documents:\n")

for document in documents:
    print(
        f"{document.company:<12}"
        f"{document.year:<8}"
        f"{document.format:<8}"
        f"{document.path}"
    )