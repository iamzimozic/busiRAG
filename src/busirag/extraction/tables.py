import re

from busirag.schemas import Word
from dataclasses import dataclass

@dataclass
class TableStructure:
    columns: list[float]
    roles: list[str]
    rows: list[list[Word]]

NUMBER_PATTERN = re.compile(
    r"^\(?\$?-?\d[\d,]*(?:\.\d+)?\)?$"
)

FORMATTING_TOKENS = {
    "$",
    "%",
}


def is_numeric_word(word: Word) -> bool:
    return bool(NUMBER_PATTERN.match(word.text))


def numeric_x_positions_by_row(
    rows: list[list[Word]],
) -> list[list[float]]:
    """
    Return the right-edge x positions of numeric words for each row.

    Financial tables commonly right-align numeric values, so x1 is
    more useful than x0 for identifying numeric columns.
    """
    return [
        [
            word.x1
            for word in row
            if is_numeric_word(word)
        ]
        for row in rows
    ]

def cluster_numeric_columns(
    rows: list[list[Word]],
    x_tolerance: float = 5.0,
    minimum_occurrences: int = 2,
) -> list[float]:
    """
    Identify recurring numeric columns across rows.

    A column is considered meaningful only when its x position
    occurs repeatedly across the region.
    """
    positions_by_row = numeric_x_positions_by_row(rows)

    all_positions = [
        x
        for row_positions in positions_by_row
        for x in row_positions
    ]

    if not all_positions:
        return []

    positions = sorted(all_positions)

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
        sum(cluster) / len(cluster)
        for cluster in clusters
        if len(cluster) >= minimum_occurrences
    ]


def row_numeric_columns(
    row: list[Word],
    columns: list[float],
    x_tolerance: float = 5.0,
) -> list[int]:
    """
    Return the column indices matched by numeric words in a row.
    """
    matches = []

    for word in row:
        if not is_numeric_word(word):
            continue

        distances = [
            abs(word.x1 - column)
            for column in columns
        ]

        if not distances:
            continue

        closest_distance = min(distances)

        if closest_distance <= x_tolerance:
            matches.append(distances.index(closest_distance))

    return matches


def find_data_rows(
    rows: list[list[Word]],
    columns: list[float],
    x_tolerance: float = 5.0,
    minimum_matched_columns: int = 2,
) -> list[int]:
    """
    Find rows that contain values aligned with multiple
    recurring numeric columns.
    """
    data_rows = []

    for index, row in enumerate(rows):
        matches = row_numeric_columns(
            row,
            columns,
            x_tolerance=x_tolerance,
        )

        if len(set(matches)) >= minimum_matched_columns:
            data_rows.append(index)

    return data_rows


def find_table_core(
    rows: list[list[Word]],
    columns: list[float],
    x_tolerance: float = 5.0,
    minimum_matched_columns: int = 2,
) -> tuple[int, int] | None:
    """
    Find the contiguous data core of a table.
    """
    data_rows = find_data_rows(
        rows,
        columns,
        x_tolerance=x_tolerance,
        minimum_matched_columns=minimum_matched_columns,
    )

    if not data_rows:
        return None

    return min(data_rows), max(data_rows)


def rows_share_numeric_columns(
    row_a: list[Word],
    row_b: list[Word],
    x_tolerance: float = 5.0,
    minimum_shared_columns: int = 2,
) -> bool:
    """
    Determine whether two rows share multiple numeric x positions.
    """
    positions_a = [
        word.x1
        for word in row_a
        if is_numeric_word(word)
    ]

    positions_b = [
        word.x1
        for word in row_b
        if is_numeric_word(word)
    ]

    if not positions_a or not positions_b:
        return False

    matches = 0

    for x_a in positions_a:
        if any(
            abs(x_a - x_b) <= x_tolerance
            for x_b in positions_b
        ):
            matches += 1

    return matches >= minimum_shared_columns


def detect_table_regions(
    rows: list[list[Word]],
    x_tolerance: float = 5.0,
    minimum_shared_columns: int = 2,
    minimum_rows: int = 2,
) -> list[list[list[Word]]]:
    """
    Group visually adjacent rows that share recurring numeric columns.
    """
    regions = []
    current_region = []

    for row in rows:
        if not current_region:
            current_region = [row]
            continue

        if rows_share_numeric_columns(
            current_region[-1],
            row,
            x_tolerance=x_tolerance,
            minimum_shared_columns=minimum_shared_columns,
        ):
            current_region.append(row)
            continue

        if len(current_region) >= minimum_rows:
            columns = cluster_numeric_columns(
                current_region,
                x_tolerance=x_tolerance,
            )

            if len(columns) >= minimum_shared_columns:
                regions.append(current_region)

        current_region = [row]

    if len(current_region) >= minimum_rows:
        columns = cluster_numeric_columns(
            current_region,
            x_tolerance=x_tolerance,
        )

        if len(columns) >= minimum_shared_columns:
            regions.append(current_region)

    return regions


def assign_words_to_columns(
    row,
    columns,
    roles,
    x_tolerance=5.0,
):
    cells = [""] * len(columns)
    row_label_words = []
    label_words = []

    for word in row:
        if word.text in FORMATTING_TOKENS:
            continue

        if not is_numeric_word(word):
            label_words.append(word.text)
            continue

        distances = [abs(word.x1 - column) for column in columns]
        closest_distance = min(distances)

        if closest_distance > x_tolerance:
            label_words.append(word.text)
            continue

        column_index = distances.index(closest_distance)
        role = roles[column_index]

        if role == "row_label":
            row_label_words.append(word.text)
        else:
            if cells[column_index]:
                cells[column_index] += " " + word.text
            else:
                cells[column_index] = word.text

    row_label = " ".join(row_label_words).strip()
    label = " ".join(label_words).strip()

    return label, row_label, cells


def reconstruct_table_region(
    region,
    x_tolerance=5.0,
):
    columns = cluster_numeric_columns(
        region,
        x_tolerance=x_tolerance,
    )

    roles = classify_numeric_columns(
        region,
        columns,
        x_tolerance=x_tolerance,
    )

    structure = TableStructure(
        columns=columns,
        roles=roles,
        rows=region,
    )

    reconstructed = []

    for row in structure.rows:
        label, row_label, cells = assign_words_to_columns(
            row,
            structure.columns,
            structure.roles,
            x_tolerance=x_tolerance,
        )

        reconstructed.append(
            {
                "label": label,
                "row_label": row_label,
                "cells": cells,
            }
        )

    return reconstructed


def numeric_word_count(
    region: list[list[Word]],
) -> int:
    return sum(
        1
        for row in region
        for word in row
        if is_numeric_word(word)
    )


def is_table_like_region(
    region: list[list[Word]],
    x_tolerance: float = 5.0,
    minimum_numeric_columns: int = 2,
    minimum_rows: int = 2,
) -> bool:
    """
    Decide whether a group of rows contains a structured
    multi-column numeric table.
    """
    columns = cluster_numeric_columns(
        region,
        x_tolerance=x_tolerance,
    )

    if len(columns) < minimum_numeric_columns:
        return False

    data_rows = find_data_rows(
        region,
        columns,
        x_tolerance=x_tolerance,
        minimum_matched_columns=minimum_numeric_columns,
    )

    return len(data_rows) >= minimum_rows

def classify_numeric_columns(
    rows,
    columns,
    x_tolerance=5.0,
):
    """
    Classify detected numeric columns as either:

    - row_label: numeric values that behave like row identifiers
    - value: numeric values that behave like table values

    Returns a list of roles aligned with `columns`.
    """
    roles = []

    for column in columns:
        values = []

        for row in rows:
            for word in row:
                if not is_numeric_word(word):
                    continue

                if abs(word.x1 - column) <= x_tolerance:
                    values.append(word.text)

        if not values:
            roles.append("unknown")
            continue

        integer_values = []

        for value in values:
            normalized = value.replace(",", "").replace("$", "")
            normalized = normalized.strip("()")

            try:
                number = float(normalized)
            except ValueError:
                continue

            integer_values.append(number)

        # A column dominated by calendar years is a row dimension.
        year_like = [
            value
            for value in integer_values
            if 1900 <= value <= 2100
        ]

        if len(year_like) >= max(2, len(integer_values) * 0.7):
            roles.append("row_label")
        else:
            roles.append("value")

    return roles

def horizontal_overlap(
    x0_a: float,
    x1_a: float,
    x0_b: float,
    x1_b: float,
) -> float:
    overlap_start = max(x0_a, x0_b)
    overlap_end = min(x1_a, x1_b)

    return max(0.0, overlap_end - overlap_start)


def horizontal_overlap_ratio(
    block,
    column_x: float,
    column_width: float = 60.0,
) -> float:
    """
    Estimate how strongly a block overlaps a table column.

    `column_x` is the detected numeric x-position.
    The column is represented by a small horizontal window
    around that position.
    """
    column_x0 = column_x - column_width
    column_x1 = column_x + 5.0

    overlap = horizontal_overlap(
        block.x0,
        block.x1,
        column_x0,
        column_x1,
    )

    block_width = block.x1 - block.x0

    if block_width <= 0:
        return 0.0

    return overlap / block_width

def column_x_ranges(
    rows,
    columns,
    x_tolerance=5.0,
):
    ranges = []

    for column in columns:
        matching_words = []

        for row in rows:
            for word in row:
                if not is_numeric_word(word):
                    continue

                if abs(word.x1 - column) <= x_tolerance:
                    matching_words.append(word)

        if not matching_words:
            ranges.append(None)
            continue

        x0 = min(word.x0 for word in matching_words)
        x1 = max(word.x1 for word in matching_words)

        ranges.append((x0, x1))

    return ranges

def block_overlaps_column(
    block,
    column_range,
    minimum_overlap=0.2,
):
    if column_range is None:
        return False

    column_x0, column_x1 = column_range

    overlap_start = max(block.x0, column_x0)
    overlap_end = min(block.x1, column_x1)

    overlap = max(0.0, overlap_end - overlap_start)

    block_width = block.x1 - block.x0

    if block_width <= 0:
        return False

    return overlap / block_width >= minimum_overlap

def numeric_x_ranges(
    rows,
    columns,
    x_tolerance=5.0,
):
    ranges = []

    for column in columns:
        matching_words = []

        for row in rows:
            for word in row:
                if not is_numeric_word(word):
                    continue

                if abs(word.x1 - column) <= x_tolerance:
                    matching_words.append(word)

        if not matching_words:
            ranges.append(None)
            continue

        x0 = min(word.x0 for word in matching_words)
        x1 = max(word.x1 for word in matching_words)

        ranges.append((x0, x1))

    return ranges