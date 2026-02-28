"""
RAG system using ChromaDB and sentence-transformers for D&D SRD lookup.
This is a lightweight implementation — SRD documents can be added via the admin API.
"""
import os
from typing import List, Optional
from ..config import settings
from ..utils.logger import logger


class RAGSystem:
    def __init__(self):
        self._client = None
        self._collection = None
        self._embedder = None
        self._initialized = False

    def _ensure_initialized(self):
        if self._initialized:
            return
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            os.makedirs(settings.CHROMA_PATH, exist_ok=True)
            self._client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
            self._collection = self._client.get_or_create_collection(
                name="srd_documents",
                metadata={"hnsw:space": "cosine"},
            )
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            self._initialized = True
            logger.info("RAG system initialized")
        except Exception as e:
            logger.warning(f"RAG system initialization failed (non-fatal): {e}")

    def add_document(self, doc_id: str, text: str, metadata: Optional[dict] = None):
        self._ensure_initialized()
        if not self._initialized:
            return
        embedding = self._embedder.encode(text).tolist()
        self._collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata or {}],
        )

    def query(self, query_text: str, n_results: int = 3) -> List[str]:
        self._ensure_initialized()
        if not self._initialized:
            return []
        try:
            embedding = self._embedder.encode(query_text).tolist()
            results = self._collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
            )
            return results.get("documents", [[]])[0]
        except Exception as e:
            logger.warning(f"RAG query failed: {e}")
            return []

    def get_context_for_dm(self, player_action: str) -> str:
        """Retrieve relevant SRD context for a player action."""
        docs = self.query(player_action, n_results=2)
        if not docs:
            return ""
        return "\n\nRelevant D&D rules:\n" + "\n---\n".join(docs)


rag_system = RAGSystem()
