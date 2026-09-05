import re
from pathlib import Path

from busirag.schemas import (
    DocumentMetadata,
    DOCXDocument,
    DOCXParagraph,
    DOCXTable,
    PDFDocument,
    ParsedDocument,
    Provenance,
    TableElement,
    TextElement,
)

from busirag.extraction.table_regions import (
    find_data_core,
    find_recurring_numeric_columns,
    find_region_boundaries,
    get_region_rows,
    inspect_table_rows,
    reconstruct_table_rows,
)


# ---------------------------------------------------------------------
# PDF block / table helpers
# ---------------------------------------------------------------------


def block_inside_expanded_bbox(
    block,
    bbox,
    tolerance: float = 12.0,
) -> bool:
    """
    Determine whether a PDF text block lies inside an expanded
    table bounding box.

    A small tolerance is used because PDF extraction coordinates
    may differ slightly between text blocks and detected table
    boundaries.
    """
    x0, y0, x1, y1 = bbox

    return (
        block.x0 >= x0 - tolerance
        and block.y0 >= y0 - tolerance
        and block.x1 <= x1 + tolerance
        and block.y1 <= y1 + tolerance
    )


def get_preceding_blocks(
    blocks,
    table_bbox,
    max_distance: float = 50.0,
):
    """
    Return blocks immediately preceding a table that are within
    max_distance points of the table's top edge.

    Blocks are returned in document order.
    """
    _, table_y0, _, _ = table_bbox

    preceding = []

    for block in blocks:
        if block.y1 > table_y0:
            continue

        distance = table_y0 - block.y1

        if distance <= max_distance:
            preceding.append(block)

    preceding.sort(key=lambda block: block.y0)

    return preceding


def is_table_title(text: str) -> bool:
    """
    Identify strongly recognizable consolidated financial
    statement titles.

    This intentionally uses a conservative rule. It is better
    to miss a title than to incorrectly associate an unrelated
    block with a financial table.
    """
    normalized = " ".join(text.split()).strip()
    upper = normalized.upper()

    if not upper.startswith("CONSOLIDATED "):
        return False

    if "FOR THE YEARS ENDED" in upper:
        return False

    return True


def find_preceding_table_title(
    blocks,
    table_bbox,
    max_distance: float = 100.0,
):
    """
    Find the nearest preceding block that looks like a
    consolidated financial statement title.
    """
    _, table_y0, _, _ = table_bbox

    candidates = []

    for block in blocks:
        if block.y1 > table_y0:
            continue

        distance = table_y0 - block.y1

        if distance > max_distance:
            continue

        if is_table_title(block.text):
            candidates.append(
                (
                    distance,
                    block,
                )
            )

    if not candidates:
        return None

    _, block = min(
        candidates,
        key=lambda item: item[0],
    )

    return block.text.strip()


def extract_years_from_blocks(blocks) -> list[int]:
    """
    Extract four-digit years from nearby text blocks.

    Years are returned in document order with duplicates removed.
    """
    years = []
    seen = set()

    for block in blocks:
        for match in re.findall(
            r"\b(?:19|20)\d{2}\b",
            block.text,
        ):
            year = int(match)

            if year not in seen:
                years.append(year)
                seen.add(year)

    return years


def get_table_context(
    blocks,
    table_bbox,
) -> tuple[str | None, list[str], list[str]]:
    """
    Extract contextual metadata associated with a table.

    Captures:
    - the nearest recognizable consolidated statement title
    - nearby preceding narrative context
    - year headers found in nearby preceding blocks
    """
    preceding_blocks = get_preceding_blocks(
        blocks,
        table_bbox,
        max_distance=50.0,
    )

    title = find_preceding_table_title(
        blocks,
        table_bbox,
    )

    years = extract_years_from_blocks(
        preceding_blocks,
    )

    column_headers = [
        str(year)
        for year in years
    ]

    context = []

    for block in preceding_blocks:
        text = " ".join(block.text.split()).strip()

        if not text:
            continue

        if is_table_title(text):
            continue

        context.append(text)

    return title, context, column_headers


# ---------------------------------------------------------------------
# DOCX normalization
# ---------------------------------------------------------------------


def normalize_docx(
    document: DOCXDocument,
    source_path: Path,
    company: str,
    year: int,
) -> ParsedDocument:
    """
    Convert a raw DOCXDocument into the normalized ParsedDocument
    representation.
    """
    elements = []

    for index, element in enumerate(document.elements):
        provenance = Provenance(
            source_path=str(source_path),
            page_number=None,
            element_index=index,
        )

        if isinstance(element, DOCXParagraph):
            elements.append(
                TextElement(
                    text=element.text,
                    provenance=provenance,
                )
            )

        elif isinstance(element, DOCXTable):
            elements.append(
                TableElement(
                    rows=element.rows,
                    provenance=provenance,
                )
            )

    return ParsedDocument(
        metadata=DocumentMetadata(
            company=company,
            year=year,
            source_path=str(source_path),
            filename=source_path.name,
        ),
        elements=elements,
    )


# ---------------------------------------------------------------------
# PDF normalization
# ---------------------------------------------------------------------


def normalize_pdf(
    document: PDFDocument,
    source_path: Path,
    company: str,
    year: int,
) -> ParsedDocument:
    """
    Convert a raw PDFDocument into the normalized ParsedDocument
    representation.

    PDF text blocks and detected tables are normalized into a
    common element stream while preserving their visual order.

    Tables additionally receive contextual metadata such as:
    - statement title
    - detected year / column headers
    """
    elements = []

    for page in document.pages:
        table_bboxes = page.table_bboxes

        # Keep text blocks and tables together temporarily so
        # we can restore their visual order on the page.
        page_elements = []

        # ---------------------------------------------------------
        # Text blocks
        # ---------------------------------------------------------

        for block_index, block in enumerate(page.blocks):
            inside_table = any(
                block_inside_expanded_bbox(
                    block,
                    bbox,
                )
                for bbox in table_bboxes
            )

            if inside_table:
                continue

            text_element = TextElement(
                text=block.text,
                provenance=Provenance(
                    source_path=str(source_path),
                    page_number=page.page_number,
                    element_index=block_index,
                ),
            )

            page_elements.append(
                (
                    block.y0,
                    0,
                    text_element,
                )
            )

        # ---------------------------------------------------------
        # Tables
        # ---------------------------------------------------------

        for table_index, bbox in enumerate(table_bboxes):
            rows = inspect_table_rows(
                page,
                bbox,
            )

            columns = find_recurring_numeric_columns(
                rows,
                minimum_occurrences=3,
            )

            if not columns:
                continue

            core = find_data_core(
                rows,
                columns,
            )

            if core is None:
                continue

            region = find_region_boundaries(
                rows,
                list(
                    range(
                        core[0],
                        core[1] + 1,
                    )
                ),
            )

            if region is None:
                continue

            region_rows = get_region_rows(
                rows,
                region,
            )

            reconstructed_rows = reconstruct_table_rows(
                region_rows,
                columns,
            )

            # -----------------------------------------------------
            # Table context
            # -----------------------------------------------------

            title, context, column_headers = get_table_context(
                page.blocks,
                bbox,
            )

            table_element = TableElement(
                rows=reconstructed_rows,
                provenance=Provenance(
                    source_path=str(source_path),
                    page_number=page.page_number,
                    element_index=table_index,
                ),
                title=title,
                context=context or None,
                column_headers=column_headers or None,
            )

            page_elements.append(
                (
                    bbox[1],
                    1,
                    table_element,
                )
            )

        # ---------------------------------------------------------
        # Restore visual order
        # ---------------------------------------------------------

        page_elements.sort(
            key=lambda item: (
                item[0],
                item[1],
            )
        )

        elements.extend(
            element
            for _, _, element in page_elements
        )

    return ParsedDocument(
        metadata=DocumentMetadata(
            company=company,
            year=year,
            source_path=str(source_path),
            filename=source_path.name,
        ),
        elements=elements,
    )

def find_preceding_context(
    blocks,
    table_bbox,
    max_distance=25.0,
):
    _, table_y0, _, _ = table_bbox

    candidates = []

    for block in blocks:
        if block.y1 > table_y0:
            continue

        distance = table_y0 - block.y1

        if distance > max_distance:
            continue

        candidates.append((distance, block))

    candidates.sort(key=lambda item: item[0])

    if not candidates:
        return None

    return candidates[0][1].text.strip()