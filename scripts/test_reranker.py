from busirag.reranking import LocalReranker


def main():
    reranker = LocalReranker()

    query = "How much marketable securities did Apple have in 2023?"

    documents = [
        "Apple's net income was $96,995 million in 2023.",
        "Apple repurchased shares during fiscal year 2023.",
        "Marketable securities: 2023: 31,590; 2022: 24,658",
        "Apple experienced various macroeconomic conditions during 2023.",
    ]

    results = reranker.rerank(query, documents)

    for index, score in results:
        print(f"{score:.4f} | {documents[index]}")


if __name__ == "__main__":
    main()