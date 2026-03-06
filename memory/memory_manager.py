import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime

# Load once at startup and keep in memory
# This is the slow part — loading it once means it never reloads mid-session
print("Loading memory system...")
client = chromadb.PersistentClient(path="memory/chroma_store")
encoder = SentenceTransformer('all-MiniLM-L6-v2')
print("Memory system ready.")

conversations = client.get_or_create_collection(name="conversations")
patterns = client.get_or_create_collection(name="patterns")

def store_conversation(role: str, message: str):
    embedding = encoder.encode(message).tolist()
    doc_id = f"{role}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    conversations.add(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[message],
        metadatas=[{
            "role": role,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }]
    )

def store_pattern(pattern: str, category: str):
    embedding = encoder.encode(pattern).tolist()
    doc_id = f"pattern_{category}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    patterns.add(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[pattern],
        metadatas=[{
            "category": category,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }]
    )

def recall_relevant(query: str, limit: int = 5) -> list:
    query_embedding = encoder.encode(query).tolist()
    results = conversations.query(
        query_embeddings=[query_embedding],
        n_results=limit
    )
    if not results['documents'][0]:
        return []
    memories = []
    for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
        memories.append({
            "message": doc,
            "role": meta["role"],
            "timestamp": meta["timestamp"]
        })
    return memories

def recall_patterns(query: str, limit: int = 3) -> list:
    query_embedding = encoder.encode(query).tolist()
    results = patterns.query(
        query_embeddings=[query_embedding],
        n_results=limit
    )
    if not results['documents'][0]:
        return []
    return results['documents'][0]

def get_memory_stats() -> dict:
    return {
        "total_conversations": conversations.count(),
        "total_patterns": patterns.count()
    }