import logging
import time

from services.retrieval import retrieve
from services.rewrite_query import rewrite_query
from services.decision import should_answer
from services.grader import grade_answerability          # <<< NOVO
from services.generate_answer import generate_answer_stream

logger = logging.getLogger(__name__)

# Mensagem mostrada quando o sistema decide NÃO responder (piso, grader, ou
# falha de geração). Vive aqui porque recusar é decisão do PIPELINE — a geração
# não recusa mais.
FALLBACK_MESSAGE = (
    "Não consegui encontrar essa informação com segurança. "
    "Mas posso te ajudar! 😊\n\n"
    "Você pode enviar sua dúvida para o e-mail:\n"
    "📩 cacaasteroidesbrasil@gmail.com"
)


async def rag_pipeline_stream(query: str, request_id: str, history: list = None):
    """
    Gerador assíncrono. Yields dicionários representando eventos:
    - {"type": "metadata", "should_answer": bool, "request_id": str}
    - {"type": "token", "content": str}
    - {"type": "error", "message": str}
    - {"type": "done"}

    Ordem do pipeline:
      rewrite_query -> retrieve -> PISO (score) -> GRADER (semântico) -> geração
    Piso barra out-of-scope; grader barra adversarial; geração só responde.
    """
    if history is None:
        history = []

    start_time = time.time()
    logger.info(
        f"[{request_id}] [RAG PIPELINE] Nova query: '{query}' "
        f"| history={len(history)} msgs"
    )

    # ===== Query rewriting (uma vez, usado na busca, no grader E na geração) =====
    search_query = await rewrite_query(query, request_id, history)

    # ===== Retrieval =====
    try:
        results = await retrieve(search_query, request_id)
    except Exception as e:
        logger.error(
            f"[{request_id}] [RAG PIPELINE ERROR] Falha no retrieve: {str(e)}"
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

    # ===== Piso (decision layer) — barra o out-of-scope por score =====
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

    # ===== Grader (relevância semântica) — pega o adversarial =====
    # O piso já barrou o out-of-scope. O grader lê a pergunta contra os chunks e
    # decide se o contexto REALMENTE responde. Ele é o dono da recusa agora — por
    # isso a geração não recusa mais (não existe mais <FALLBACK> pra vazar).
    answerable = await grade_answerability(search_query, results, request_id)
    logger.info(
        f"[{request_id}] [RAG PIPELINE] Grader: answerable={answerable}"
    )

    if not answerable:
        logger.warning(
            f"[{request_id}] [RAG PIPELINE] Resposta bloqueada pelo grader"
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
        async for token in generate_answer_stream(
            search_query, request_id, results, history=history
        ):
            # None agora significa só FALHA de geração (sem chunks ou erro na
            # OpenAI) — não mais "recusa", que virou trabalho do grader.
            if token is None:
                if streamed_any_token:
                    logger.warning(
                        f"[{request_id}] [RAG PIPELINE] Stream interrompida no meio"
                    )
                    yield {
                        "type": "error",
                        "message": "A resposta foi interrompida. Tente novamente."
                    }
                else:
                    logger.warning(
                        f"[{request_id}] [RAG PIPELINE] Falha antes de qualquer token"
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