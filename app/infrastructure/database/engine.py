import logging

from core import settings
from sqlalchemy.ext.asyncio import create_async_engine

log = logging.getLogger(__name__)


async_engine = create_async_engine(
    url=str(settings.db.url),
    echo=settings.db.echo,
    pool_pre_ping=True,
)


async def dispose():
    await async_engine.dispose()
    log.info("Dispose engine")
