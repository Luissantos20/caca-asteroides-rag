import logging

logger = logging.getLogger(__name__)

def should_answer(results, threshold=0.5, gap_threshold=0.25, min_relevant=1, relevance_cutoff=0.4) -> bool:

    if not results:
        return False

    top_distance = results[0]["distance"]

    # Distância muito ruim
    if top_distance > 1.2:
        return False

    top_score = results[0]["score"]

    relevant_chunks = [r for r in results[:3] if r["score"] >= relevance_cutoff]

    gap = None
    if len(results) > 1:
        gap = top_score - results[1]["score"]

    # Gap baixo + distance média → suspeito
    if gap is not None and top_distance > 0.85:
        if gap < 0.2:
            #  só bloqueia se não houver suporte suficiente
            if len(relevant_chunks) < 2:
                logger.warning(
                    f"[DECISION BLOCK] "
                    f"dist={top_distance:.3f} "
                    f"score={top_score:.3f} "
                    f"gap={gap} "
                    f"n_rel={len(relevant_chunks)}"
                )
                return False

    # Distância média → exige confiança + suporte
    if gap is not None and top_distance > 0.9:
        if gap < 0.3 and len(relevant_chunks) < 2:
            logger.warning(
                f"[DECISION BLOCK] "
                f"dist={top_distance:.3f} "
                f"score={top_score:.3f} "
                f"gap={gap} "
                f"n_rel={len(relevant_chunks)}"
            )
            return False

    # Threshold (mantida por compatibilidade)
    if top_score < threshold:
        logger.warning(
            f"[DECISION BLOCK] "
            f"dist={top_distance:.3f} "
            f"score={top_score:.3f} "
            f"gap={gap} "
            f"n_rel={len(relevant_chunks)}"
        )
        return False

    # Gap principal (com suporte)
    if gap is not None:
        if gap < gap_threshold:
            if len(relevant_chunks) < 2 and top_distance > 0.85:
                logger.warning(
                    f"[DECISION BLOCK] "
                    f"dist={top_distance:.3f} "
                    f"score={top_score:.3f} "
                    f"gap={gap} "
                    f"n_rel={len(relevant_chunks)}"
                )
                return False

    return True