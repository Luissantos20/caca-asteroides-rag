from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.extension import _rate_limit_exceeded_handler

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from api.routes.chat import router as chat_router
from api.routes.health import router as health_router

from api.core.limiter import limiter
from api.core.logging_config import setup_logging
from api.core.middleware import log_requests
from api.core.exception_handler import global_exception_handler

import logging

setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI()

# Confia nos headers do proxy (X-Forwarded-For, X-Forwarded-Proto)
# Necessário porque o Railway coloca um proxy na frente da aplicação
app.add_middleware(
    ProxyHeadersMiddleware,
    trusted_hosts="*",
)

# CORS - permite frontend acessar a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"], # mudar isso em produção
    allow_headers=["*"], # mudar isso em produção
)

# Middleware HTTP
app.middleware("http")(log_requests)

# Rate limiting
app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

app.add_middleware(SlowAPIMiddleware)

# Exception handler global
app.add_exception_handler(
    Exception,
    global_exception_handler
)

# Rotas
app.include_router(chat_router)
app.include_router(health_router)

# TODO TRATAR EXCEÇÕES/MELHORAR ENDPOINT/FRONTED/MEMORIA/DEPLOY
