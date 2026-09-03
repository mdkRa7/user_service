import uvicorn
from core import settings
from fastapi import FastAPI

app = FastAPI()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_conf.host,
        port=settings.api_conf.port,
        reload=True,
    )
