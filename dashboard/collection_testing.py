from chromadb import HttpClient
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from pathlib import Path
from langchain_community.document_loaders import PyMuPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
#----------------------------LOADING DOCUMENTS-------------------------------------------------------------#
def load_documents(folder_path):
    documents = []
    for file_path in Path(folder_path).glob("*.pdf"):
        loader = PyMuPDFLoader(str(file_path))
        documents.extend(loader.load())
    return documents
#----------------------CHUNKING TEST DATA---------------------------------------------------------#
def chunk_documents(documents):
    splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50)
    return splitter.split_documents(documents)
#-------------------------------------------------------------------------------------------------#
def load_vector_store(documents):
    embeddings = HuggingFaceEmbeddings(
        model_name=r".\embeddings\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
    )

    # Connect to Chroma server
    client = HttpClient(host="localhost", port=8000)  # Ensure Chroma server is running
    collection_name = "dga_db"

    # Create or retrieve collection
    if collection_name not in [col.name for col in client.list_collections()]:
        print("📦 Creating new collection on server...")
        collection = client.create_collection(name=collection_name)
    else:
        print("🔁 Using existing collection on server...")
        collection = client.get_collection(name=collection_name)

    # Wrap it in LangChain-compatible Chroma object
    vectorstore = Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=embeddings,
    )

    # Get already indexed sources
    existing_sources = set()
    try:
        existing_chunks = vectorstore.similarity_search("test", k=1000)
        existing_sources = set(doc.metadata.get("source") for doc in existing_chunks if doc.metadata)
    except Exception as e:
        print(f"⚠️ Couldn't fetch existing data: {e}")

    # Filter and add new docs
    new_docs = [doc for doc in documents if doc.metadata.get("source") not in existing_sources]
    if new_docs:
        print(f"➕ Adding {len(new_docs)} new chunks to vectorstore")
        vectorstore.add_documents(new_docs)
    else:
        print("✅ No new documents to add")

    return vectorstore
def main():
    print("Loading documents")
    folder_path=r".\docs_dga"
    raw_docs = load_documents(folder_path)
    if not raw_docs:
        print(f"No.of .pdf files found in: {folder_path}")
        return
    print("chunking the document")
    chunks = chunk_documents(raw_docs)
    vectorstore=load_vector_store(chunks)
    print("\n")
    #print(chunks)
    print("\n")
    print(vectorstore)

if __name__ =="__main__":
    main()