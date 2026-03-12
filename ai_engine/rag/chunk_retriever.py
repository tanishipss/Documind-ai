from vector_store.chroma_client import store_chunks, retrieve_chunks, clear_collection


def index_document(chunks, doc_id=None):
    """Index all chunks into ChromaDB."""
    clear_collection()  # fresh start for each new document
    store_chunks(chunks, doc_id=doc_id)


def retrieve_relevant_chunks(chunks=None, query="main concepts", top_k=5):
    """
    Retrieve chunks from ChromaDB using semantic search.
    `chunks` param kept for backward compatibility but ignored if ChromaDB has data.
    """
    return retrieve_chunks(query=query, top_k=top_k)