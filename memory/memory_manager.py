import os
import json
import re
from datetime import datetime

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

IS_ANDROID = os.path.exists("/data/data/com.termux")

MEMORY_DIR = "memory"
os.makedirs(MEMORY_DIR, exist_ok=True)

if IS_ANDROID:
    CONV_FILE = os.path.join(MEMORY_DIR, "conversations.json")
    PATT_FILE = os.path.join(MEMORY_DIR, "patterns.json")

    def _load(path):
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return []

    def _save(path, data):
        with open(path, "w") as f:
            json.dump(data, f)

    def _keyword_search(query, entries, key, limit):
        query_words = set(re.findall(r'\w+', query.lower()))
        scored = []
        for e in entries:
            text_words = set(re.findall(r'\w+', e.get(key, "").lower()))
            score = len(query_words & text_words)
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def store_conversation(role: str, message: str):
        data = _load(CONV_FILE)
        data.append({
            "role": role,
            "message": message,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        _save(CONV_FILE, data)

    def store_pattern(pattern: str, category: str):
        data = _load(PATT_FILE)
        data.append({
            "category": category,
            "pattern": pattern,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        _save(PATT_FILE, data)

    def recall_relevant(query: str, limit: int = 5) -> list:
        data = _load(CONV_FILE)
        results = _keyword_search(query, data, "message", limit)
        return [{"message": e["message"], "role": e["role"], "timestamp": e["timestamp"]} for e in results]

    def recall_patterns(query: str, limit: int = 3) -> list:
        data = _load(PATT_FILE)
        results = _keyword_search(query, data, "pattern", limit)
        return [e["pattern"] for e in results]

    def get_memory_stats() -> dict:
        return {
            "total_conversations": len(_load(CONV_FILE)),
            "total_patterns": len(_load(PATT_FILE))
        }

else:
    import chromadb
    from sentence_transformers import SentenceTransformer

    _client = chromadb.PersistentClient(path="memory/chroma_store")
    _encoder = SentenceTransformer('all-MiniLM-L6-v2')
    _conversations = _client.get_or_create_collection(name="conversations")
    _patterns = _client.get_or_create_collection(name="patterns")

    def store_conversation(role: str, message: str):
        embedding = _encoder.encode(message).tolist()
        doc_id = f"{role}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        _conversations.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[message],
            metadatas=[{"role": role, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]
        )

    def store_pattern(pattern: str, category: str):
        embedding = _encoder.encode(pattern).tolist()
        doc_id = f"pattern_{category}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        _patterns.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[pattern],
            metadatas=[{"category": category, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]
        )

    def recall_relevant(query: str, limit: int = 5) -> list:
        embedding = _encoder.encode(query).tolist()
        results = _conversations.query(query_embeddings=[embedding], n_results=limit)
        if not results['documents'][0]:
            return []
        return [
            {"message": doc, "role": meta["role"], "timestamp": meta["timestamp"]}
            for doc, meta in zip(results['documents'][0], results['metadatas'][0])
        ]

    def recall_patterns(query: str, limit: int = 3) -> list:
        embedding = _encoder.encode(query).tolist()
        results = _patterns.query(query_embeddings=[embedding], n_results=limit)
        if not results['documents'][0]:
            return []
        return results['documents'][0]

    def get_memory_stats() -> dict:
        return {
            "total_conversations": _conversations.count(),
            "total_patterns": _patterns.count()
        }