from pathlib import Path

import pymupdf


path = Path("data/raw/apple/2023/apple-2023.pdf")

document = pymupdf.open(path)

table_pages = []

for page_number, page in enumerate(document, start=1):
    tables = page.find_tables()

    if tables.tables:
        table_pages.append(page_number)

document.close()

print("TABLE PAGES:")
print(table_pages)
print("COUNT:", len(table_pages))