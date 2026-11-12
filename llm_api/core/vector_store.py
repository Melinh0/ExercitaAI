import chromadb
from chromadb.config import Settings
from core.config import CHROMA_DIR
from core.embeddings import embedder


EMBED_BATCH_SIZE = 64
UPSERT_BATCH_SIZE = 256


class VectorStore:
    def __init__(self, collection_name="questions"):
        self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def _embed_in_batches(self, documents):
        embeddings = []
        for i in range(0, len(documents), EMBED_BATCH_SIZE):
            batch = documents[i:i + EMBED_BATCH_SIZE]
            embeddings.extend(embedder.encode_passages(batch))
        return embeddings

    def add_documents(self, ids, documents, metadatas):
        embeddings = self._embed_in_batches(documents)
        for i in range(0, len(ids), UPSERT_BATCH_SIZE):
            self.collection.add(
                ids=ids[i:i + UPSERT_BATCH_SIZE],
                embeddings=embeddings[i:i + UPSERT_BATCH_SIZE],
                metadatas=metadatas[i:i + UPSERT_BATCH_SIZE],
                documents=documents[i:i + UPSERT_BATCH_SIZE]
            )

    def upsert_documents(self, ids, documents, metadatas):
        embeddings = self._embed_in_batches(documents)
        for i in range(0, len(ids), UPSERT_BATCH_SIZE):
            self.collection.upsert(
                ids=ids[i:i + UPSERT_BATCH_SIZE],
                embeddings=embeddings[i:i + UPSERT_BATCH_SIZE],
                metadatas=metadatas[i:i + UPSERT_BATCH_SIZE],
                documents=documents[i:i + UPSERT_BATCH_SIZE]
            )

    def query(self, query_text, n_results=5, where=None):
        query_embedding = embedder.encode_queries([query_text])[0]
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )

    def delete_all(self):
        try:
            self.client.delete_collection(self.collection.name)
        except ValueError:
            pass
        self.collection = self.client.create_collection(
            name=self.collection.name,
            metadata={"hnsw:space": "cosine"}
        )