from dataclasses import dataclass

from busirag.schemas import PDFPage, Word
from busirag.extraction.layout import group_words_into_rows
from busirag.extraction.tables import (
    cluster_numeric_columns,
    is_numeric_word,
    FORMATTING_TOKENS,
)


@dataclass
class TableRegion:
    bbox: tuple[float, float, float, float]
    rows: list[list[Word]]

def row_x_span(row: list[Word]) -> tuple[float, float]:
    return (
        min(word.x0 for word in row),
        max(word.x1 for word in row),
    )

def reconstruct_table_rows(
    rows: list[list[Word]],
    columns: list[float],
    x_tolerance: float = 5.0,
) -> list[list[str]]:
    return [
        assign_words_to_columns(
            row,
            columns,
            x_tolerance=x_tolerance,
        )
        for row in rows
    ]

def numeric_x_positions_by_row(
    rows: list[list[Word]],
) -> list[list[float]]:
    return [
        [
            word.x1
            for word in row
            if is_numeric_word(word)
        ]
        for row in rows
    ]

def cluster_positions(
    positions: list[float],
    x_tolerance: float = 5.0,
) -> list[tuple[float, int]]:
    if not positions:
        return []

    positions = sorted(positions)

    clusters: list[list[float]] = []

    for x in positions:
        if not clusters:
            clusters.append([x])
            continue

        current = clusters[-1]
        center = sum(current) / len(current)

        if abs(x - center) <= x_tolerance:
            current.append(x)
        else:
            clusters.append([x])

    return [
        (sum(cluster) / len(cluster), len(cluster))
        for cluster in clusters
    ]

def find_recurring_numeric_columns(
    rows: list[list[Word]],
    x_tolerance: float = 5.0,
    minimum_occurrences: int = 3,
) -> list[float]:
    positions_by_row = numeric_x_positions_by_row(rows)

    all_positions = [
        x
        for row_positions in positions_by_row
        for x in row_positions
    ]

    clusters = cluster_positions(
        all_positions,
        x_tolerance=x_tolerance,
    )

    return [
        center
        for center, count in clusters
        if count >= minimum_occurrences
    ]

def row_column_matches(
    row: list[Word],
    columns: list[float],
    x_tolerance: float = 5.0,
) -> list[int]:
    if not columns:
        return []

    matches = []

    for word in row:
        if not is_numeric_word(word):
            continue

        distances = [
            abs(word.x1 - column)
            for column in columns
        ]

        closest = min(distances)

        if closest <= x_tolerance:
            matches.append(
                distances.index(closest)
            )

    return matches

def find_data_rows(
    rows: list[list[Word]],
    columns: list[float],
    x_tolerance: float = 5.0,
    minimum_matched_columns: int = 2,
) -> list[int]:
    data_rows = []

    for index, row in enumerate(rows):
        matches = row_column_matches(
            row,
            columns,
            x_tolerance=x_tolerance,
        )

        if len(matches) >= minimum_matched_columns:
            data_rows.append(index)

    return data_rows

def find_data_core(
    rows: list[list[Word]],
    columns: list[float],
) -> tuple[int, int] | None:
    data_rows = find_data_rows(
        rows,
        columns,
    )

    if not data_rows:
        return None

    return min(data_rows), max(data_rows)

def filter_words_to_bbox(
    words: list[Word],
    bbox: tuple[float, float, float, float],
) -> list[Word]:
    x0, y0, x1, y1 = bbox

    return [
        word
        for word in words
        if (
            word.x0 >= x0
            and word.x1 <= x1
            and word.y0 >= y0
            and word.y1 <= y1
        )
    ]


def count_numeric_words(row: list[Word]) -> int:
    return sum(
        1
        for word in row
        if is_numeric_word(word)
    )


def inspect_table_rows(
    page: PDFPage,
    bbox: tuple[float, float, float, float],
) -> list[list[Word]]:
    words = filter_words_to_bbox(page.words, bbox)

    rows = group_words_into_rows(words)

    positions = numeric_x_positions_by_row(rows)

    return rows

def row_numeric_count(row: list[Word]) -> int:
    return sum(
        1
        for word in row
        if is_numeric_word(word)
    )


def find_table_core(
    rows: list[list[Word]],
    minimum_numeric_words: int = 2,
) -> tuple[int, int] | None:
    numeric_rows = [
        index
        for index, row in enumerate(rows)
        if row_numeric_count(row) >= minimum_numeric_words
    ]

    if not numeric_rows:
        return None

    start = min(numeric_rows)
    end = max(numeric_rows)

    return start, end

def row_matches_numeric_columns(
    row: list[Word],
    columns: list[float],
    x_tolerance: float = 5.0,
    minimum_matches: int = 2,
) -> bool:
    matches = 0

    for word in row:
        if not is_numeric_word(word):
            continue

        nearest_column = min(
            columns,
            key=lambda column: abs(word.x1 - column),
        )

        if abs(word.x1 - nearest_column) <= x_tolerance:
            matches += 1

    return matches >= minimum_matches

def row_signature(
    row: list[Word],
    columns: list[float],
    x_tolerance: float = 5.0,
) -> tuple[int, ...]:
    return tuple(
        row_column_matches(
            row,
            columns,
            x_tolerance=x_tolerance,
        )
    )

def find_structured_rows(
    rows: list[list[Word]],
    minimum_numeric_columns: int = 2,
) -> list[int]:
    columns = cluster_numeric_columns(rows)

    if len(columns) < minimum_numeric_columns:
        return []

    return [
        index
        for index, row in enumerate(rows)
        if row_matches_numeric_columns(
            row,
            columns,
            minimum_matches=minimum_numeric_columns,
        )
    ]

def find_region_boundaries(
    rows: list[list[Word]],
    data_rows: list[int],
    maximum_gap: float = 18.0,
) -> tuple[int, int] | None:
    if not data_rows:
        return None

    first_data = min(data_rows)
    last_data = max(data_rows)

    start = first_data
    end = last_data

    # Expand upward while rows are visually close.
    while start > 0:
        current_y = min(word.y0 for word in rows[start])
        previous_y = min(word.y0 for word in rows[start - 1])

        if current_y - previous_y > maximum_gap:
            break

        start -= 1

    # Expand downward while rows are visually close.
    while end < len(rows) - 1:
        current_y = min(word.y0 for word in rows[end])
        next_y = min(word.y0 for word in rows[end + 1])

        if next_y - current_y > maximum_gap:
            break

        end += 1

    return start, end

def get_region_rows(
    rows: list[list[Word]],
    region: tuple[int, int],
) -> list[list[Word]]:
    start, end = region
    return rows[start : end + 1]

def assign_words_to_columns(
    row: list[Word],
    columns: list[float],
    x_tolerance: float = 5.0,
) -> list[str]:
    cells = [""] * len(columns)
    label_words = []

    for word in row:
        if word.text in FORMATTING_TOKENS:
            continue

        if not is_numeric_word(word):
            label_words.append(word.text)
            continue

        distances = [
            abs(word.x1 - column)
            for column in columns
        ]

        closest_distance = min(distances)

        if closest_distance <= x_tolerance:
            column_index = distances.index(closest_distance)

            if cells[column_index]:
                cells[column_index] += " " + word.text
            else:
                cells[column_index] = word.text
        else:
            label_words.append(word.text)

    return [" ".join(label_words)] + cells

def row_features(
    row: list[Word],
    columns: list[float],
    x_tolerance: float = 5.0,
) -> dict:
    matches = row_column_matches(
        row,
        columns,
        x_tolerance=x_tolerance,
    )

    return {
        "numeric_columns": tuple(matches),
        "numeric_count": len(matches),
        "word_count": len(row),
        "y0": round(min(word.y0 for word in row), 1),
        "y1": round(max(word.y1 for word in row), 1),
        "text": " ".join(word.text for word in row),
    }

def vertical_gap(
    row_a: list[Word],
    row_b: list[Word],
) -> float:
    return min(
        word.y0 for word in row_b
    ) - max(
        word.y1 for word in row_a
    )

def rows_are_contiguous(
    row_a: list[Word],
    row_b: list[Word],
    maximum_gap: float = 4.0,
) -> bool:
    return vertical_gap(row_a, row_b) <= maximum_gap

def row_text_span(
    row: list[Word],
) -> tuple[float, float]:
    return (
        min(word.x0 for word in row),
        max(word.x1 for word in row),
    )

def merge_text_only_rows(
    rows: list[list[Word]],
) -> list[list[Word]]:
    merged: list[list[Word]] = []

    for row in rows:
        if not row:
            continue

        has_numeric = any(
            is_numeric_word(word)
            for word in row
        )

        if not has_numeric and merged:
            merged[-1] = merged[-1] + row
        else:
            merged.append(row)

    return merged

def group_rows_into_blocks(
    rows: list[list[Word]],
    maximum_gap: float = 3.0,
) -> list[list[list[Word]]]:
    blocks: list[list[list[Word]]] = []

    for row in rows:
        if not blocks:
            blocks.append([row])
            continue

        previous_row = blocks[-1][-1]

        if vertical_gap(previous_row, row) <= maximum_gap:
            blocks[-1].append(row)
        else:
            blocks.append([row])

    return blocks

def reconstruct_table_rows(
    rows: list[list[Word]],
    columns: list[float],
    x_tolerance: float = 5.0,
) -> list[list[str]]:
    return [
        assign_words_to_columns(
            row,
            columns,
            x_tolerance=x_tolerance,
        )
        for row in rows
    ]