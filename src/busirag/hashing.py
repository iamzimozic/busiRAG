import hashlib
from pathlib import Path


def hash_file(path: Path) -> str:
    """Return SHA-256 hash of a file."""

    sha256 = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def hash_text(text: str) -> str:
    """Return SHA-256 hash of text."""

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()