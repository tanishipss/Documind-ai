import chromadb

client = chromadb.PersistentClient(path="./data/chroma_db")

collection = client.get_or_create_collection(
    name="documind_chunks",
    metadata={"hnsw:space": "cosine"}
)


def store_chunks(chunks, doc_id=None):
    if not chunks:
        print("⚠️ No chunks to store")
        return

    prefix = doc_id or "doc_default"
    ids = [f"{prefix}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"doc_id": prefix} for _ in chunks]

    # Clear old chunks for this document slot
    try:
        old = collection.get(where={"doc_id": {"$eq": prefix}})
        if old["ids"]:
            collection.delete(ids=old["ids"])
            print(f"🗑️ Cleared {len(old['ids'])} old chunks for '{prefix}'")
    except Exception as e:
        print(f"⚠️ Could not clear old chunks: {e}")

    collection.add(
        documents=chunks,
        ids=ids,
        metadatas=metadatas
    )
    print(f"✅ Stored {len(chunks)} chunks under doc_id='{prefix}'")


def retrieve_chunks(query, doc_id_prefix=None, top_k=5):
    count = collection.count()

    if count == 0:
        print("⚠️ ChromaDB collection is empty")
        return []

    n = min(top_k, count)

    # Try filtered query first
    if doc_id_prefix:
        try:
            results = collection.query(
                query_texts=[query],
                n_results=n,
                where={"doc_id": {"$eq": doc_id_prefix}}
            )
            docs = results["documents"][0] if results["documents"] else []
            print(f"✅ Retrieved {len(docs)} chunks for doc_id='{doc_id_prefix}'")

            if docs:
                return docs

            print("⚠️ Filtered query returned nothing — trying unfiltered")

        except Exception as e:
            print(f"⚠️ Filtered query failed: {e} — trying unfiltered")

    # Fallback — no filter
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n
        )
        docs = results["documents"][0] if results["documents"] else []
        print(f"✅ Unfiltered retrieval: {len(docs)} chunks")
        return docs

    except Exception as e:
        print(f"❌ ChromaDB query failed completely: {e}")
        return []


def clear_collection():
    global collection
    client.delete_collection("documind_chunks")
    collection = client.get_or_create_collection(
        name="documind_chunks",
        metadata={"hnsw:space": "cosine"}
    )
    print("🗑️ Collection cleared")