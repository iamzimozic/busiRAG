from dataclasses import dataclass
from typing import Literal
from pathlib import Path

@dataclass
class Provenance:
    source_path: str
    page_number: int | None = None
    element_index: int | None = None

@dataclass
class DocumentMetadata:
    company: str
    year: int
    source_path: str
    filename: str

@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

@dataclass
class PDFBlock:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

@dataclass
class PDFPage:
    page_number: int
    width: float
    height: float
    words: list[Word]
    blocks: list[PDFBlock]
    table_bboxes: list[tuple[float, float, float, float]]


@dataclass
class PDFDocument:
    pages: list[PDFPage]


@dataclass
class DOCXParagraph:
    text: str


@dataclass
class DOCXTable:
    rows: list[list[str]]


@dataclass
class DOCXDocument:
    elements: list[DOCXParagraph | DOCXTable]


@dataclass
class TextElement:
    text: str
    provenance: Provenance


@dataclass
class TableElement:
    rows: list[list[str]]
    provenance: Provenance
    title: str | None = None
    context: list[str] | None = None
    row_label: str | None = None
    column_headers: list[str] | None = None


@dataclass
class ParsedDocument:
    metadata: DocumentMetadata
    elements: list[TextElement | TableElement]

@dataclass
class SourceDocument:
    path: Path
    company: str
    year: int
    format: str

@dataclass
class TableRow:
    cells: list[str]

@dataclass
class Chunk:
    text: str
    company: str
    year: int
    source_path: str
    filename: str
    page_number: int | None
    element_type: str
    section: str | None
    chunk_index: int
    token_count: int