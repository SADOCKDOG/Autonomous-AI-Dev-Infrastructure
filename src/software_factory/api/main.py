"""Punto de entrada FastAPI para la Software Factory."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from software_factory import __version__
from software_factory.settings import settings
from software_factory.persistence.database import init_db
from software_factory.api.health import router as health_router
from software_factory.api.kanban import router as kanban_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización de la base de datos al arrancar
    init_db()
    yield


app = FastAPI(
    title="Software Factory Híbrida Local",
    description="Backend local de orquestación multiagente con Model Gateway y FCC",
    version=__version__,
    lifespan=lifespan,
)

# Enlace estricto a localhost / loopback
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000", "http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(kanban_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "software_factory.api.main:app",
        host=settings.factory_host,
        port=settings.factory_port,
        reload=(settings.factory_env == "development"),
    )
