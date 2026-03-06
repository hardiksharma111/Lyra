import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import json
import re
from datetime import datetime

# Detect platform
IS_ANDROID = os.path.exists("/data/data/com.termux")

print("Loading memory system...")

if IS_ANDROID:
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

    def _keyword_search(query, entries, key, limit):
        query_words = set(re.findall(r'\w+', query.lower()))
        scored = []
        for e in entries:
            text_words = set(re.findall(r'\w+', e.get(key, "").lower()))
            score = len(query_words & text_words)
            if score > 0:
                scored.append((score, e))
        scored.sort(reverse=True)
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
    # PC — ChromaDB with sentence transformers
    import chromadb
    from sentence_transformers import SentenceTransformer

    client = chromadb.PersistentClient(path="memory/chroma_store")
    encoder = SentenceTransformer('all-MiniLM-L6-v2')
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