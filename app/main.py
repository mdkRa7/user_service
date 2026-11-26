import logging

from core import setup_root_logger

setup_root_logger(level=logging.INFO)

from contextlib import asynccontextmanager

import uvicorn
from api.exception_handlers import register_exception_handlers
from api.utils import register_limiter_handler
from api.v1 import router
from core import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from infrastructure.clients import redis
from infrastructure.database.engine import dispose


@asynccontextmanager
async def lifespan(app: FastAPI):

    yield
    await redis.aclose()
    await dispose()


app = FastAPI(lifespan=lifespan)
register_exception_handlers(app)
register_limiter_handler(app)

if settings.cors.origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_conf.host,
        port=settings.api_conf.port,
        reload=True,
    )
