import requests
from langchain_huggingface import HuggingFaceEmbeddings
import chromadb
from langchain_chroma import Chroma



embeddings = HuggingFaceEmbeddings(
    model_name=r".\local_models\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
)
client = chromadb.HttpClient(host="10.96.76.161", port=8000)  # Update host if server is remote
vectorstore = Chroma(
    client=client,
    collection_name="ssr_db",  # use same name as what was used when storing
    embedding_function=embeddings
)


def generate_response(context,query):
    url = "http://10.96.76.121:11434/api/generate"
    payload = {
        "model": "gemma3",
        "prompt": (
            f"You are a helpful assistant to using this information {context} "
            f"answer this {query} \n\n"
        ),
        "stream": False
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return response.json().get("response", "No response field found in the API response.")
    else:
        return f"Error: {response.status_code} - {response.text}"    


def main():
    query = "Price of 100 MVA power transformer 2024?"

    results = vectorstore.similarity_search(query, k=3)
    '''
    # Filter out low-relevance results (e.g., similarity < 0.75)
    threshold = 0.2
    filtered_results = [doc for doc, score in results_with_score if score >= threshold]
    print(filtered_results)
    if not filtered_results:
        print("No relevant context found.")
        return
    #print(embeddings.embed_query("HII"))  # Try this to ensure it's returning a vector
    '''
    response = generate_response(results, query)
    print("-" * 60)
    print("AI:")
    print(response)
    print("-" * 60)
    print("Sources")
    for i, doc in enumerate(results, 1):
        source = doc.metadata.get("source", "Unknown source")
        page = doc.metadata.get("page", "page not found")
        print(f"{i}. {source} - page: {page}")
    print("-" * 60)

if __name__ =="__main__":
    main()
