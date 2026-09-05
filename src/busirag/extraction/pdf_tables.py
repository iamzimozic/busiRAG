from busirag.schemas import PDFPage, Word


TableBBox = tuple[float, float, float, float]


def word_inside_bbox(
    word: Word,
    bbox: TableBBox,
) -> bool:
    x0, y0, x1, y1 = bbox

    return (
        word.x0 >= x0
        and word.x1 <= x1
        and word.y0 >= y0
        and word.y1 <= y1
    )


def get_words_in_table(
    page: PDFPage,
    bbox: TableBBox,
) -> list[Word]:
    return [
        word
        for word in page.words
        if word_inside_bbox(word, bbox)
    ]