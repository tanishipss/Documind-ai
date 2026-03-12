from vector_store.chroma_client import store_chunks, retrieve_chunks


def index_document(chunks, doc_id=None):
    """Store document chunks in ChromaDB under a clean namespace."""
    if not chunks:
        print(f"⚠️ No chunks to index for doc_id='{doc_id}'")
        return
    store_chunks(chunks, doc_id=doc_id)
    print(f"✅ Indexed {len(chunks)} chunks for doc_id='{doc_id}'")


def retrieve_relevant_chunks(chunks=None, query="main concepts",
                              doc_id_prefix=None, top_k=8):
    """
    Retrieve semantically relevant chunks from ChromaDB.
    doc_id_prefix: 'doc1' or 'doc2' to filter by document.
    """
    results = retrieve_chunks(
        query=query,
        doc_id_prefix=doc_id_prefix,
        top_k=top_k
    )
    print(f"✅ retrieve_relevant_chunks: got {len(results)} chunks")
    return results