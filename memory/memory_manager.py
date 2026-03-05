import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime

# Initialize ChromaDB — stores everything locally in a folder called chroma_store
client = chromadb.PersistentClient(path="memory/chroma_store")

# This model converts text into vectors
# all-MiniLM-L6-v2 is small, fast, and runs locally — perfect for our use
encoder = SentenceTransformer('all-MiniLM-L6-v2')

# Two separate memory collections
# conversations — stores everything said between you and Lyra
# patterns — stores learned facts about you specifically
conversations = client.get_or_create_collection(name="conversations")
patterns = client.get_or_create_collection(name="patterns")

def store_conversation(role: str, message: str):
    # Convert message to vector so ChromaDB understands its meaning
    embedding = encoder.encode(message).tolist()

    # Unique ID based on timestamp so nothing overwrites anything
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
    # Stores a learned fact about you
    # category examples: preference, habit, schedule, personality
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
    # Given a query finds the most semantically similar past conversations
    # This is what makes Lyra remember things even without exact keyword match
    query_embedding = encoder.encode(query).tolist()

    results = conversations.query(
        query_embeddings=[query_embedding],
        n_results=limit
    )

    if not results['documents'][0]:
        return []

    # Return list of relevant past messages with their metadata
    memories = []
    for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
        memories.append({
            "message": doc,
            "role": meta["role"],
            "timestamp": meta["timestamp"]
        })

    return memories

def recall_patterns(query: str, limit: int = 3) -> list:
    # Finds relevant learned facts about you based on current context
    query_embedding = encoder.encode(query).tolist()

    results = patterns.query(
        query_embeddings=[query_embedding],
        n_results=limit
    )

    if not results['documents'][0]:
        return []

    return results['documents'][0]

def get_memory_stats() -> dict:
    # Returns how much Lyra remembers
    return {
        "total_conversations": conversations.count(),
        "total_patterns": patterns.count()
    }