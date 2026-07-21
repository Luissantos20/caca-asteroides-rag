import os
import chromadb
from chromadb.config import Settings
import logging
import time
import asyncio
from services.openai_client import client_openai, openai_semaphore
# <<< MUDANÇA: removido o import de rewrite_query (agora é o pipeline que reescreve)

logger = logging.getLogger(__name__)

# ===== CONFIG =====
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")


chroma_client = chromadb.Client(
    Settings(
        persist_directory=CHROMA_PATH,
        is_persistent=True
    )
)

collection = chroma_client.get_collection(name="caca_asteroides")

retrieval_semaphore = asyncio.Semaphore(1)


# ===== EMBEDDING =====
async def get_embedding(text: str) -> list | None:

    logger.info("[RETRIEVAL] Gerando embedding da query")

    try:
        logger.info("[RETRIEVAL] Aguardando slot do openai_semaphore")

        async with openai_semaphore:
            logger.info("[RETRIEVAL] Slot do openai_semaphore adquirido")

            response = await client_openai.embeddings.create(
                model="text-embedding-3-small",
                input=text,
                timeout=10
            )

        embedding = response.data[0].embedding

        if not embedding or not isinstance(embedding, list):
            logger.error(
                "[RETRIEVAL ERROR] "
                "Embedding inválido retornado pela OpenAI"
            )
            return None

        logger.info("[RETRIEVAL] Embedding gerado com sucesso")
        return embedding

    except Exception as e:
        logger.error(
            f"[RETRIEVAL ERROR] "
            f"Falha ao gerar embedding: {str(e)}"
        )
        return None


# ===== NORMALIZAÇÃO =====
def normalize_scores(distances: list) -> list:
    # Chroma com space="l2" -> distância L2 ao quadrado.
    # Embeddings da OpenAI são normalizados (norma~1), então:
    #   cos = 1 - distância/2  → sinal ABSOLUTO de relevância, comparável entre queries.
    return [max(0.0, min(1.0, 1.0 - d / 2.0)) for d in distances]


active_retrievals = 0
# ===== RETRIEVAL =====
async def retrieve(
    search_query: str,          # <<< MUDANÇA: recebe a query JÁ reescrita pelo pipeline
    request_id: str,
    n_results: int = 5,
) -> list:                      # <<< MUDANÇA: history não é mais necessário aqui
    start_time = time.time()

    global active_retrievals
    active_retrievals += 1

    logger.info(
        f"[{request_id}] [RETRIEVAL] Ativos simultâneos: {active_retrievals}"
    )

    try:

        logger.info(
            f"[{request_id}] [RETRIEVAL] Buscando chunks para query='{search_query[:80]}'"
        )

        if not search_query.strip():

            logger.warning(
                f"[{request_id}] [RETRIEVAL WARNING] Query vazia recebida"
            )

            return []

        embedding = await get_embedding(search_query)  # <<< MUDANÇA: usa search_query

        if embedding is None:
            logger.warning(
                f"[{request_id}] [RETRIEVAL] Embedding não gerado"
            )

            return []

        logger.info(
            f"[{request_id}] [RETRIEVAL] Consultando ChromaDB (top_k={n_results})"
        )

        try:
            logger.info(
                    f"[{request_id}] [RETRIEVAL] Aguardando slot do semaphore"
                )

            async with retrieval_semaphore:
                logger.info(
                    f"[{request_id}] [RETRIEVAL] Slot adquirido"
                )
                results = await asyncio.to_thread(
                    collection.query,
                    query_embeddings=[embedding],
                    n_results=n_results
                )

        except Exception as e:

            logger.error(
                f"[{request_id}] [RETRIEVAL ERROR] "
                f"Falha ao consultar ChromaDB: {str(e)}"
            )

            return []

        try:
            raw = list(zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ))

        except Exception as e:

            logger.error(
                f"[{request_id}] [RETRIEVAL ERROR] "
                f"Estrutura inesperada retornada pelo ChromaDB: {str(e)}"
            )

            return []

        if not raw:
            logger.warning(f"[{request_id}] [RETRIEVAL] Nenhum chunk encontrado")

            elapsed = time.time() - start_time

            logger.info(
                f"[{request_id}] [RETRIEVAL] Finalizado em {elapsed:.2f}s"
            )

            return []

        distances = [r[3] for r in raw]
        scores = normalize_scores(distances)

        output = [
            {
                "id": r[0],
                "content": r[1],
                "metadata": r[2],
                "distance": r[3],
                "score": s
            }
            for r, s in zip(raw, scores)
        ]

        output.sort(key=lambda x: x["score"], reverse=True)

        logger.info(
            f"[{request_id}] [RETRIEVAL] {len(output)} chunks recuperados"
        )

        for chunk in output[:3]:
            logger.info(
                f"[{request_id}] [RETRIEVAL RESULT] "
                f"id={chunk['id']} "
                f"score={chunk['score']:.3f} "
                f"distance={chunk['distance']:.3f} "
                f"category={chunk['metadata'].get('category')}"
            )

        elapsed = time.time() - start_time

        logger.info(
            f"[{request_id}] [RETRIEVAL] Finalizado em {elapsed:.2f}s"
        )

        return output

    finally:

        active_retrievals -= 1

        logger.info(
            f"[{request_id}] [RETRIEVAL] Encerrado | ativos={active_retrievals}"
        )