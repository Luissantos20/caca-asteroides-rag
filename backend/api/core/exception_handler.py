import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Se alguma exceção esacpar, chama essa função
async def global_exception_handler(
    request: Request,
    exc: Exception
):

    logger.error(
        f"[UNHANDLED ERROR] "
        f"{request.method} "
        f"{request.url} "
        f"| {str(exc)}"
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Erro interno do servidor"
        }
    )