from pathlib import Path


DATA_DIR = Path("data/raw")


def inspect_file(path: Path) -> dict:
    return {
        "company": path.parent.parent.name,
        "year": path.parent.name,
        "filename": path.name,
        "format": path.suffix.lower().lstrip("."),
        "size_mb": path.stat().st_size / (1024 * 1024),
    }


def main():
    for path in sorted(DATA_DIR.rglob("*")):
        if path.is_file():
            metadata = inspect_file(path)
            print(metadata)


if __name__ == "__main__":
    main()