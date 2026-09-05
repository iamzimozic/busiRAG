from busirag.schemas import PDFPage, Word


def group_words_into_rows(
    words: list[Word],
    y_tolerance: float = 3.0,
) -> list[list[Word]]:
    rows: list[list[Word]] = []

    for word in sorted(words, key=lambda w: (w.y0, w.x0)):
        matched_row = None

        for row in rows:
            row_y = row[0].y0

            if abs(word.y0 - row_y) <= y_tolerance:
                matched_row = row
                break

        if matched_row is None:
            rows.append([word])
        else:
            matched_row.append(word)

    for row in rows:
        row.sort(key=lambda w: w.x0)

    return rows