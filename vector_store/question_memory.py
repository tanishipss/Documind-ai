import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

client = chromadb.Client()

collection = client.get_or_create_collection(name="question_memory")


def store_document(text, questions):

    embedding = model.encode(text).tolist()

    collection.add(
        documents=[text],
        embeddings=[embedding],
        metadatas=[{"questions": str(questions)}],
        ids=[str(hash(text))]
    )


def find_similar_document(text):

    embedding = model.encode(text).tolist()

    results = collection.query(
        query_embeddings=[embedding],
        n_results=1
    )

    if results["documents"]:

        similarity_questions = results["metadatas"][0][0]["questions"]

        return similarity_questions

    return None