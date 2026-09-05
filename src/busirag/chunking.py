import re

from pathlib import Path

from busirag.schemas import (
    Chunk,
    ParsedDocument,
    TableElement,
    TextElement,
)


TARGET_CHARS = 1800
MAX_CHARS = 2400
TABLE_ROWS_PER_CHUNK = 4


def normalize_text(text: str) -> str:
    """Normalize whitespace while preserving paragraph boundaries."""

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    return "\n".join(lines)


def approximate_token_count(text: str) -> int:
    """
    Rough token estimate.

    This is intentionally simple for the first chunking iteration.
    We will replace this with the actual model tokenizer later.
    """
    return max(1, len(text) // 4)


def serialize_table(table: TableElement) -> str:
    """Convert a structured table into retrieval-friendly text."""

    parts = []

    if table.title:
        parts.append(table.title.strip())

    if table.context:
        parts.extend(
            context.strip()
            for context in table.context
            if context.strip()
        )

    headers = table.column_headers or []

    for row in table.rows:
        if not row:
            continue

        row = [cell.strip() for cell in row]

        if not any(row):
            continue

        label = row[0]
        values = row[1:]

        if label:
            if headers and len(headers) == len(values):
                formatted_values = [
                    f"{header}: {value}"
                    for header, value in zip(headers, values)
                    if value
                ]

                if formatted_values:
                    parts.append(
                        f"{label}: " + "; ".join(formatted_values)
                    )
                else:
                    parts.append(label)

            else:
                values_text = "; ".join(
                    value for value in values if value
                )

                if values_text:
                    parts.append(f"{label}: {values_text}")
                else:
                    parts.append(label)

        else:
            parts.append(
                " | ".join(value for value in row if value)
            )

    return "\n".join(parts)

def serialize_table_rows(
    table: TableElement,
    rows: list[list[str]],
) -> str:
    """Serialize a group of table rows with repeated table context."""

    parts = []

    if table.title:
        parts.append(table.title.strip())

    if table.context:
        parts.extend(
            context.strip()
            for context in table.context
            if context.strip()
        )

    headers = table.column_headers or []

    for row in rows:
        if not row:
            continue

        row = [cell.strip() for cell in row]

        if not any(row):
            continue

        label = row[0]
        values = row[1:]

        if label:
            if headers and len(headers) == len(values):
                formatted_values = [
                    f"{header}: {value}"
                    for header, value in zip(headers, values)
                    if value
                ]

                if formatted_values:
                    parts.append(
                        f"{label}: " + "; ".join(formatted_values)
                    )
                else:
                    parts.append(label)

            else:
                values_text = "; ".join(
                    value for value in values if value
                )

                if values_text:
                    parts.append(f"{label}: {values_text}")
                else:
                    parts.append(label)

        else:
            parts.append(
                " | ".join(value for value in row if value)
            )

    return "\n".join(parts)

def make_chunk(
    text: str,
    company: str,
    year: int,
    source_path: str,
    page_number: int | None,
    element_type: str,
    section: str | None,
    chunk_index: int,
) -> Chunk:

    text = normalize_text(text)

    return Chunk(
        text=text,
        company=company,
        year=year,
        source_path=source_path,
        filename=Path(source_path).name,
        page_number=page_number,
        element_type=element_type,
        section=section,
        chunk_index=chunk_index,
        token_count=approximate_token_count(text),
    )

def split_large_text(
    text: str,
    max_chars: int = MAX_CHARS,
) -> list[str]:
    """
    Split text conservatively.

    Priority:
    1. paragraph boundaries
    2. sentence boundaries
    3. word boundaries as a final fallback
    """

    paragraphs = [
        paragraph.strip()
        for paragraph in text.split("\n")
        if paragraph.strip()
    ]

    chunks: list[str] = []
    current = ""

    sentence_pattern = re.compile(r"(?<=[.!?])\s+")

    def flush():
        nonlocal current

        if current:
            chunks.append(current.strip())
            current = ""

    for paragraph in paragraphs:

        if len(paragraph) <= max_chars:
            candidate = (
                paragraph
                if not current
                else f"{current} {paragraph}"
            )

            if len(candidate) <= max_chars:
                current = candidate
            else:
                flush()
                current = paragraph

            continue

        # Paragraph itself is too large.
        flush()

        sentences = sentence_pattern.split(paragraph)

        for sentence in sentences:
            sentence = sentence.strip()

            if not sentence:
                continue

            candidate = (
                sentence
                if not current
                else f"{current} {sentence}"
            )

            if len(candidate) <= max_chars:
                current = candidate
                continue

            flush()

            # A single sentence is still too large.
            if len(sentence) > max_chars:
                words = sentence.split()
                word_buffer = ""

                for word in words:
                    candidate = (
                        word
                        if not word_buffer
                        else f"{word_buffer} {word}"
                    )

                    if len(candidate) <= max_chars:
                        word_buffer = candidate
                    else:
                        if word_buffer:
                            chunks.append(word_buffer)

                        word_buffer = word

                current = word_buffer

            else:
                current = sentence

    flush()

    return chunks

def chunk_table_element(
    element: TableElement,
    company: str,
    year: int,
    source_path: str,
    start_index: int,
) -> list[Chunk]:

    valid_rows = [
        row
        for row in element.rows
        if row and any(cell.strip() for cell in row)
    ]

    chunks = []

    for start in range(
        0,
        len(valid_rows),
        TABLE_ROWS_PER_CHUNK,
    ):
        row_group = valid_rows[
            start : start + TABLE_ROWS_PER_CHUNK
        ]

        text = serialize_table_rows(
            table=element,
            rows=row_group,
        )

        if not text:
            continue

        chunks.append(
            make_chunk(
                text=text,
                company=company,
                year=year,
                source_path=source_path,
                page_number=element.provenance.page_number,
                element_type="table",
                section=element.title,
                chunk_index=start_index + len(chunks),
            )
        )

    return chunks

def chunk_text_elements(
    elements: list[TextElement],
    company: str,
    year: int,
    source_path: str,
    start_index: int,
) -> tuple[list[Chunk], int]:

    chunks = []
    current_parts = []
    current_length = 0

    for element in elements:

        text = normalize_text(element.text)

        if not text:
            continue

        text_length = len(text)

        should_flush = (
            current_parts
            and current_length + text_length > TARGET_CHARS
        )

        if should_flush:
            combined = "\n\n".join(current_parts)

            for part in split_large_text(combined):
                chunks.append(
                    make_chunk(
                        text=part,
                        company=company,
                        year=year,
                        source_path=source_path,
                        page_number=element.provenance.page_number,
                        element_type="text",
                        section=None,
                        chunk_index=start_index + len(chunks),
                    )
                )

            current_parts = []
            current_length = 0

        current_parts.append(text)
        current_length += text_length

    if current_parts:
        combined = "\n\n".join(current_parts)

        for part in split_large_text(combined):
            chunks.append(
                make_chunk(
                    text=part,
                    company=company,
                    year=year,
                    source_path=source_path,
                    page_number=elements[-1].provenance.page_number,
                    element_type="text",
                    section=None,
                    chunk_index=start_index + len(chunks),
                )
            )

    return chunks, start_index + len(chunks)


def chunk_document(
    document: ParsedDocument,
    company: str,
    year: int,
    source_path: str,
) -> list[Chunk]:

    chunks = []
    text_buffer = []

    def flush_text_buffer():
        nonlocal text_buffer

        if not text_buffer:
            return

        new_chunks, _ = chunk_text_elements(
            elements=text_buffer,
            company=company,
            year=year,
            source_path=source_path,
            start_index=len(chunks),
        )

        chunks.extend(new_chunks)
        text_buffer = []

    for element in document.elements:

        if isinstance(element, TextElement):
            text_buffer.append(element)
            continue

        if isinstance(element, TableElement):

            flush_text_buffer()

            table_chunks = chunk_table_element(
                element=element,
                company=company,
                year=year,
                source_path=source_path,
                start_index=len(chunks),
            )

            chunks.extend(table_chunks)

    flush_text_buffer()

    return chunks