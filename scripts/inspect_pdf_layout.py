from pathlib import Path

from busirag.extraction.pdf import extract_pdf
from busirag.extraction.layout import group_words_into_rows
from busirag.extraction.tables import detect_table_regions
from busirag.extraction.tables import cluster_x_positions
from busirag.extraction.tables import get_numeric_x_positions
from busirag.extraction.tables import cluster_numeric_columns
from busirag.extraction.tables import reconstruct_table_region


path = Path("data/raw/nvidia/2025/nvidia-2025.pdf")

document = extract_pdf(path)
page = document.pages[70]

rows = group_words_into_rows(page.words)

x_positions = cluster_x_positions(rows)

print()
print("X POSITION CLUSTERS")
print("=" * 100)

for x in x_positions:
    print(f"x ≈ {x:.1f}")

regions = detect_table_regions(rows)

from busirag.extraction.tables import numeric_word_count

print()
print("REGION DIAGNOSTICS")
print("=" * 100)

for region_number, region in enumerate(regions, start=1):
    print(
        f"REGION {region_number}: "
        f"rows={len(region)}, "
        f"numeric_words={numeric_word_count(region)}"
    )

print()
print("NUMERIC COLUMNS BY REGION")
print("=" * 100)

for region_number, region in enumerate(regions, start=1):
    columns = cluster_numeric_columns(region)

    print(
        f"REGION {region_number}: "
        + ", ".join(f"{x:.1f}" for x in columns)
    )

print("=" * 100)
print(f"FILE: {path}")
print(f"PAGE: {page.page_number}")
print(f"ROWS: {len(rows)}")
print(f"TABLE-LIKE REGIONS: {len(regions)}")
print("=" * 100)

for region_number, region in enumerate(regions, start=1):
    print()
    print(f"--- REGION {region_number} ({len(region)} rows) ---")

    for row in region:
        print(
            " | ".join(
                word.text
                for word in row
            )
        )

print()
print("RECONSTRUCTED TABLES")
print("=" * 100)

for region_number, region in enumerate(regions, start=1):
    table = reconstruct_table_region(region)

    print()
    print(f"--- TABLE {region_number} ---")

    for row in table:
        print(row)