import logging

logger = logging.getLogger(__name__)

RELEVANCE_FLOOR = 0.40  # cos mínimo do melhor chunk para tentar responder

def should_answer(results) -> bool:
    if not results:
        return False
    top_cos = max(r["score"] for r in results)   # não depende de ordenação externa
    if top_cos < RELEVANCE_FLOOR:
        logger.warning(f"[DECISION BLOCK] top_cos={top_cos:.3f} < {RELEVANCE_FLOOR}")
        return False
    return True