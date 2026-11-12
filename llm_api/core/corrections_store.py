import json
import os
from core.config import CORRECTIONS_COLLECTION, CHROMA_DIR
from core.embeddings import embedder
import chromadb
from chromadb.config import Settings


class CorrectionsStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.collection = self.client.get_or_create_collection(
            name=CORRECTIONS_COLLECTION,
            metadata={"hnsw:space": "cosine"}
        )

    def add_correction(self, correction_id, original_json, corrected_json, metadata=None):
        original_text = json.dumps(original_json, ensure_ascii=False)
        corrected_text = json.dumps(corrected_json, ensure_ascii=False)
        document = f"Original: {original_text}\nCorrigido: {corrected_text}"
        if metadata is None:
            metadata = {}
        embedding = embedder.encode_passages([document])[0]
        self.collection.upsert(
            ids=[correction_id],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[document]
        )

    def retrieve_similar(self, query_text, n_results=3):
        query_embedding = embedder.encode_queries([query_text])[0]
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        corrections = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                corrections.append({
                    "document": doc,
                    "metadata": meta,
                    "distance": results["distances"][0][i] if results["distances"] else None
                })
        return corrections


corrections_store = CorrectionsStore()