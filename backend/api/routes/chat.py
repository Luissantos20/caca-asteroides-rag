import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from api.core.limiter import limiter
from services.pipeline import rag_pipeline_stream
from schemas.chat import ChatRequest

router = APIRouter()
logger = logging.getLogger(__name__)


async def sse_format(pipeline_stream):
    """Converte dicts yieldados pelo pipeline em strings no formato SSE."""
    async for event in pipeline_stream:
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/chat")
@limiter.limit("120/minute")
async def chat(request: Request, body: ChatRequest):
    request_id = request.state.request_id

    # Converte HistoryMessage (Pydantic) em dicts simples
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in body.history
    ]

    logger.info(
        f"[{request_id}] [API] Nova pergunta recebida: "
        f"'{body.message[:100]}' "
        f"| history={len(history)} msgs"
    )

    pipeline_stream = rag_pipeline_stream(
        query=body.message,
        request_id=request_id,
        history=history,
    )

    return StreamingResponse(
        sse_format(pipeline_stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )