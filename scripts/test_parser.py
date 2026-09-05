from pathlib import Path

from busirag.extraction.pdf import extract_pdf


path = Path("data/raw/apple/2023/apple-2023.pdf")

document = extract_pdf(path)

print("Pages:", len(document.pages))

page = document.pages[30]

print("Page number:", page.page_number)
print("Dimensions:", page.width, "x", page.height)
print("Words:", len(page.words))

for word in page.words[:20]:
    print(word)