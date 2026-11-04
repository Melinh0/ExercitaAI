import hashlib
from sentence_transformers import SentenceTransformer

from core.config import EMBEDDING_MODEL_NAME

QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "


class EmbeddingModel:
    def __init__(self):
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        self._requires_prefix = "e5" in EMBEDDING_MODEL_NAME.lower()
        self._cache = {}

    def encode(self, texts, is_query=False):
        if not texts:
            return []

        if self._requires_prefix:
            prefix = QUERY_PREFIX if is_query else PASSAGE_PREFIX
            texts = [prefix + t for t in texts]

        keys = [hashlib.md5(t.encode()).hexdigest() for t in texts]
        to_encode = []
        to_encode_idx = []
        results = [None] * len(texts)

        for i, (k, t) in enumerate(zip(keys, texts)):
            if k in self._cache:
                results[i] = self._cache[k]
            else:
                to_encode.append(t)
                to_encode_idx.append(i)

        if to_encode:
            new_embeddings = self.model.encode(
                to_encode, show_progress_bar=False
            ).tolist()
            for i, emb in zip(to_encode_idx, new_embeddings):
                self._cache[keys[i]] = emb
                results[i] = emb

        return results

    def encode_queries(self, texts):
        return self.encode(texts, is_query=True)

    def encode_passages(self, texts):
        return self.encode(texts, is_query=False)


embedder = EmbeddingModel()