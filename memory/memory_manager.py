import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import json
import numpy as np
from sentence_transformers import SentenceTransformer
from datetime import datetime

# Detect platform
IS_ANDROID = os.path.exists("/data/data/com.termux")

print("Loading memory system...")
encoder = SentenceTransformer('all-MiniLM-L6-v2')

if IS_ANDROID:
    # Lightweight JSON + numpy vector store
    MEMORY_DIR = "memory"
    CONV_FILE = os.path.join(MEMORY_DIR, "conversations.json")
    PATT_FILE = os.path.join(MEMORY_DIR, "patterns.json")
    os.makedirs(MEMORY_DIR, exist_ok=True)

    def _load(path):
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return []

    def _save(path, data):
        with open(path, "w") as f:
            json.dump(data, f)

    def _cosine_search(query_vec, entries, limit):
        if not entries:
            return []
        vecs = np.array([e["embedding"] for e in entries], dtype=np.float32)
        q = np.array(query_vec, dtype=np.float32)
        q /= np.linalg.norm(q) + 1e-10
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
        scores = vecs @ q
        top = np.argsort(scores)[::-1][:limit]
        return [entries[i] for i in top]

    def store_conversation(role: str, message: str):
        data = _load(CONV_FILE)
        data.append({
            "id": f"{role}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "role": role,
            "message": message,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "embedding": encoder.encode(message).tolist()
        })
        _save(CONV_FILE, data)

    def store_pattern(pattern: str, category: str):
        data = _load(PATT_FILE)
        data.append({
            "id": f"pattern_{category}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "category": category,
            "pattern": pattern,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "embedding": encoder.encode(pattern).tolist()
        })
        _save(PATT_FILE, data)

    def recall_relevant(query: str, limit: int = 5) -> list:
        data = _load(CONV_FILE)
        q = encoder.encode(query).tolist()
        results = _cosine_search(q, data, limit)
        return [{"message": e["message"], "role": e["role"], "timestamp": e["timestamp"]} for e in results]

    def recall_patterns(query: str, limit: int = 3) -> list:
        data = _load(PATT_FILE)
        q = encoder.encode(query).tolist()
        results = _cosine_search(q, data, limit)
        return [e["pattern"] for e in results]

    def get_memory_stats() -> dict:
        return {
            "total_conversations": len(_load(CONV_FILE)),
            "total_patterns": len(_load(PATT_FILE))
        }

else:
    # PC — original ChromaDB
    import chromadb
    client = chromadb.PersistentClient(path="memory/chroma_store")
    conversations = client.get_or_create_collection(name="conversations")
    patterns = client.get_or_create_collection(name="patterns")

    def store_conversation(role: str, message: str):
        embedding = encoder.encode(message).tolist()
        doc_id = f"{role}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        conversations.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[message],
            metadatas=[{"role": role, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]
        )

    def store_pattern(pattern: str, category: str):
        embedding = encoder.encode(pattern).tolist()
        doc_id = f"pattern_{category}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        patterns.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[pattern],
            metadatas=[{"category": category, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]
        )

    def recall_relevant(query: str, limit: int = 5) -> list:
        query_embedding = encoder.encode(query).tolist()
        results = conversations.query(query_embeddings=[query_embedding], n_results=limit)
        if not results['documents'][0]:
            return []
        return [{"message": doc, "role": meta["role"], "timestamp": meta["timestamp"]}
                for doc, meta in zip(results['documents'][0], results['metadatas'][0])]

    def recall_patterns(query: str, limit: int = 3) -> list:
        query_embedding = encoder.encode(query).tolist()
        results = patterns.query(query_embeddings=[query_embedding], n_results=limit)
        if not results['documents'][0]:
            return []
        return results['documents'][0]

    def get_memory_stats() -> dict:
        return {
            "total_conversations": conversations.count(),
            "total_patterns": patterns.count()
        }

print("Memory system ready.")