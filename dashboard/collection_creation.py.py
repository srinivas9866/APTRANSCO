from chromadb import HttpClient, Collection
from chromadb.utils import embedding_functions

def get_or_create_collection(
    host: str,
    port: int,
    collection_name: str,
    embedding_function_name: str = "all-MiniLM-L6-v2",
) -> Collection:
    """Fetch collection if it exists, else create it."""
    client = HttpClient(host=host, port=port)
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=embedding_function_name
    )

    try:
        # Try to get the collection
        collection = client.get_collection(
            name=collection_name,
            embedding_function=embedding_fn,
        )
        print(f"✅ Collection '{collection_name}' already exists.")
    except Exception:
        # If not found, create it
        collection = client.create_collection(
            name=collection_name,
            embedding_function=embedding_fn,
        )
        print(f"🆕 Created new collection: '{collection_name}'.")
    return collection

# Example usage
if __name__ == "__main__":
    collection = get_or_create_collection(
        host="",
        port=8002,
        collection_name="ssrrules",
        embedding_function_name="all-MiniLM-L6-v2",  # Change if needed
    )
    print(f"🔗 Ready to use collection: {collection.name}")
