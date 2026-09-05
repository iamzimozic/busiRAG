from sentence_transformers import CrossEncoder


class LocalReranker:
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
    ):
        self.model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        if not query.strip():
            raise ValueError("query must not be empty")

        if not documents:
            return []

        pairs = [(query, document) for document in documents]

        scores = self.model.predict(pairs)

        ranked = sorted(
            enumerate(scores),
            key=lambda item: float(item[1]),
            reverse=True,
        )

        if top_k is not None:
            ranked = ranked[:top_k]

        return [
            (index, float(score))
            for index, score in ranked
        ]