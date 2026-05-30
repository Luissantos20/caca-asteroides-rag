import logging
import time

from services.retrieval import retrieve
from services.rewrite_query import rewrite_query  # <<< MUDANÇA: import
from services.decision import should_answer
from services.generate_answer import generate_answer_stream, FALLBACK_MESSAGE

logger = logging.getLogger(__name__)


async def rag_pipeline_stream(query: str, request_id: str, history: list = None):
    """
    Gerador assíncrono. Yields dicionários representando eventos:
    - {"type": "metadata", "should_answer": bool, "request_id": str}
    - {"type": "token", "content": str}
    - {"type": "error", "message": str}
    - {"type": "done"}
    """
    if history is None:
        history = []

    start_time = time.time()
    logger.info(
        f"[{request_id}] [RAG PIPELINE] Nova query: '{query}' "
        f"| history={len(history)} msgs"
    )

    # ===== Query rewriting (uma vez, usado na busca E na geração) =====
    # <<< MUDANÇA: reescreve aqui no pipeline. Sem histórico, devolve a própria
    # query (custo zero). A reescrita resolve pronomes/referências e desfaz a
    # ambiguidade de perguntas vagas ("e como?", "quero participar").
    search_query = await rewrite_query(query, request_id, history)

    # ===== Retrieval =====
    try:
        results = await retrieve(search_query, request_id)  # <<< MUDANÇA: passa a reescrita
    except Exception as e:
        logger.error(
            f"[{request_id}] [RAG PIPELINE ERROR] "
            f"Falha no retrieve: {str(e)}"
        )
        yield {"type": "metadata", "should_answer": False, "request_id": request_id}
        yield {"type": "error", "message": FALLBACK_MESSAGE}
        yield {"type": "done"}
        return

    if not isinstance(results, list):
        logger.error(
            f"[{request_id}] [RAG PIPELINE ERROR] "
            "Retrieval retornou estrutura inválida"
        )
        yield {"type": "metadata", "should_answer": False, "request_id": request_id}
        yield {"type": "error", "message": FALLBACK_MESSAGE}
        yield {"type": "done"}
        return

    logger.info(
        f"[{request_id}] [RAG PIPELINE] Retrieval retornou {len(results)} chunks"
    )

    # ===== Decision =====
    decision = should_answer(results)
    logger.info(
        f"[{request_id}] [RAG PIPELINE] Decision layer: should_answer={decision}"
    )

    if not decision:
        logger.warning(
            f"[{request_id}] [RAG PIPELINE] Resposta bloqueada pela decision layer"
        )
        yield {"type": "metadata", "should_answer": False, "request_id": request_id}
        yield {"type": "error", "message": FALLBACK_MESSAGE}
        yield {"type": "done"}
        elapsed = time.time() - start_time
        logger.info(f"[{request_id}] [RAG PIPELINE] Finalizado em {elapsed:.2f}s")
        return

    # ===== Streaming generation =====
    yield {"type": "metadata", "should_answer": True, "request_id": request_id}

    streamed_any_token = False

    try:
        # <<< MUDANÇA: gera com a query reescrita (search_query), não a crua.
        # Assim a geração avalia os chunks contra a MESMA pergunta usada na busca.
        async for token in generate_answer_stream(
            search_query, request_id, results, history=history
        ):
            if token is None:
                if streamed_any_token:
                    logger.warning(
                        f"[{request_id}] [RAG PIPELINE] "
                        "Stream interrompida no meio"
                    )
                    yield {
                        "type": "error",
                        "message": "A resposta foi interrompida. Tente novamente."
                    }
                else:
                    logger.warning(
                        f"[{request_id}] [RAG PIPELINE] "
                        "Falha antes de qualquer token"
                    )
                    yield {"type": "error", "message": FALLBACK_MESSAGE}
                break

            streamed_any_token = True
            yield {"type": "token", "content": token}

    except Exception as e:
        logger.error(
            f"[{request_id}] [RAG PIPELINE ERROR] "
            f"Exception inesperada durante stream: {str(e)}"
        )
        if streamed_any_token:
            yield {
                "type": "error",
                "message": "A resposta foi interrompida. Tente novamente."
            }
        else:
            yield {"type": "error", "message": FALLBACK_MESSAGE}

    yield {"type": "done"}

    elapsed = time.time() - start_time
    logger.info(f"[{request_id}] [RAG PIPELINE] Finalizado em {elapsed:.2f}s")