import chromadb

client = chromadb.Client()

collection = client.get_or_create_collection(
    name="documind_chunks"
)


def store_chunks(chunks):

    ids = [str(i) for i in range(len(chunks))]

    collection.add(
        documents=chunks,
        ids=ids
    )


def retrieve_chunks(query, top_k=5):

    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )

    return results["documents"][0]