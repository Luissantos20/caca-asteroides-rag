import os
import json
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from openai import OpenAI

# Carregar variáveis de ambiente
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Persistência em disco
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")

chroma_client = chromadb.Client(
    Settings(
        persist_directory=CHROMA_PATH,
        is_persistent=True 
    )
)

try:
    chroma_client.delete_collection(name="caca_asteroides")
except:
    pass

collection = chroma_client.get_or_create_collection(name="caca_asteroides")

# Ler os arquivos
DATA_PATH = os.path.join(BASE_DIR, "data")

def load_documents():
    documents = []

    for file in os.listdir(DATA_PATH):
        if file.endswith(".json"):
            with open(os.path.join(DATA_PATH, file), "r", encoding="utf-8") as f:
                data = json.load(f)
                documents.append(data)

    return documents


# Processar Chunks
def prepare_chunks(documents):
    all_chunks = []

    # Pega metadados do documento
    for doc in documents:
        metadata = doc["metadata"]

        # Virará embedding (apenas entendimento semêntico)
        for chunk in doc["chunks"]:
            text = f"""
            [{chunk['category'].upper()}]

            {chunk['title']}

            {chunk['content']}

            Esse chunk responde perguntas como?
            {chr(10).join("- " + q for q in chunk.get("related_questions", []))}

            Keywords:
            {", ".join(chunk.get("keywords", []))}
            """

            # Controle técnico (filtro/ordenação/regras)
            all_chunks.append({
                "id": chunk["id"],
                "text": text,
                "metadata": {
                    "document_id": metadata["document_id"],
                    "source": metadata["source"],
                    "category": chunk["category"],
                    "importance": chunk.get("importance", "medium"),
                    "chunk_index": chunk.get("chunk_index", 0)
                }
            })

    return all_chunks


def index_chunks(chunks, batch_size=100):
    # Processamento em lotes (coleta todos os textos primeiro e faz chamadas de 100 em 100 para a API de embeddings e para o banco de dados)
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]

        texts = [chunk["text"] for chunk in batch]

        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )

        embeddings = [item.embedding for item in response.data]

        ids = [chunk["id"] for chunk in batch]
        metadatas = [chunk["metadata"] for chunk in batch]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )


if __name__ == "__main__":
    docs = load_documents()
    chunks = prepare_chunks(docs)
    index_chunks(chunks)

    print("✅ Indexação concluída!")