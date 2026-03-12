import chromadb
import hashlib

# Persistent so data survives app restarts
client = chromadb.PersistentClient(path="./data/chroma_db")

collection = client.get_or_create_collection(
    name="documind_chunks",
    metadata={"hnsw:space": "cosine"}  # cosine similarity
)


def store_chunks(chunks, doc_id=None):
    """Store chunks with document ID to avoid mixing documents."""
    
    if not chunks:
        return
    
    # Use doc_id prefix so each document's chunks are isolated
    prefix = doc_id or "doc"
    ids = [f"{prefix}_{i}" for i in range(len(chunks))]
    
    # Avoid duplicate inserts
    existing = collection.get(ids=ids)["ids"]
    
    new_ids = [i for i in ids if i not in existing]
    new_chunks = [chunks[j] for j, i in enumerate(ids) if i not in existing]
    
    if new_chunks:
        collection.add(documents=new_chunks, ids=new_ids)


def retrieve_chunks(query, doc_id=None, top_k=5):
    """Retrieve chunks relevant to a specific query."""
    
    where = None
    # Future: filter by doc_id metadata for multi-doc support
    
    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
        where=where
    )
    
    return results["documents"][0] if results["documents"] else []


def clear_collection():
    """Call this when a new document is uploaded."""
    global collection
    client.delete_collection("documind_chunks")
    collection = client.get_or_create_collection(
        name="documind_chunks",
        metadata={"hnsw:space": "cosine"}
    )