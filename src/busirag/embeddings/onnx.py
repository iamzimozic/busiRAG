import numpy as np


class OnnxEmbeddingProvider:
    """
    Embedding provider that runs the model with ONNX Runtime instead of
    PyTorch.

    Produces the same vectors as LocalEmbeddingProvider for BGE models
    (CLS pooling + L2 normalization; cosine similarity 1.0 on the
    indexed corpus), so it can serve queries against an index built
    with sentence-transformers. The API uses it on small hosts, where
    PyTorch does not fit in memory.

    Requires the model repository to ship `onnx/model.onnx` and
    `tokenizer.json` (BAAI/bge-small-en-v1.5 does).
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        max_length: int = 512,
        batch_size: int = 32,
        threads: int = 0,
        tokenizer=None,
        session=None,
    ):
        self.batch_size = batch_size

        if tokenizer is None or session is None:
            from huggingface_hub import hf_hub_download

        if tokenizer is None:
            from tokenizers import Tokenizer

            tokenizer = Tokenizer.from_file(
                hf_hub_download(model_name, "tokenizer.json")
            )

        tokenizer.enable_truncation(max_length=max_length)
        tokenizer.enable_padding()
        self.tokenizer = tokenizer

        if session is None:
            import onnxruntime as ort

            options = ort.SessionOptions()
            # Lower steady-state memory on small hosts.
            options.enable_cpu_mem_arena = False

            if threads > 0:
                options.intra_op_num_threads = threads

            session = ort.InferenceSession(
                hf_hub_download(model_name, "onnx/model.onnx"),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )

        self.session = session
        self.input_names = {item.name for item in session.get_inputs()}

    @property
    def dimension(self) -> int:
        return len(self.embed_query("dimension probe"))

    def _embed(self, texts: list[str]) -> np.ndarray:
        encodings = self.tokenizer.encode_batch(texts)

        feed = {
            "input_ids": np.array(
                [encoding.ids for encoding in encodings],
                dtype=np.int64,
            ),
            "attention_mask": np.array(
                [encoding.attention_mask for encoding in encodings],
                dtype=np.int64,
            ),
        }

        if "token_type_ids" in self.input_names:
            feed["token_type_ids"] = np.array(
                [encoding.type_ids for encoding in encodings],
                dtype=np.int64,
            )

        hidden_states = self.session.run(None, feed)[0]

        # BGE uses the [CLS] token embedding, then L2 normalization.
        cls = hidden_states[:, 0]
        norms = np.linalg.norm(cls, axis=1, keepdims=True)

        return cls / np.clip(norms, 1e-12, None)

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        embeddings = []

        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            embeddings.extend(self._embed(batch).tolist())

        return embeddings

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        return self._embed([text])[0].tolist()
