import time
import logging
import uuid

from fastapi import Request

logger = logging.getLogger(__name__)


async def log_requests(request: Request, call_next):

    start_time = time.time()

    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    logger.info(
        f"[{request_id}] [REQUEST START] {request.method} {request.url.path}"
    )

    response = await call_next(request)

    elapsed = time.time() - start_time

    logger.info(
        f"[{request_id}] [REQUEST END] "
        f"{request.method} "
        f"{request.url.path} "
        f"- {response.status_code} "
        f"- {elapsed:.2f}s"
    )

    return response