from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import create_all
from .router import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("watertracker")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all()
    if settings.scheduler_enabled:
        from .collectors.scheduler import start_scheduler

        start_scheduler()
        logger.info("Scheduler activé")
    yield
    if settings.scheduler_enabled:
        from .collectors.scheduler import stop_scheduler

        stop_scheduler()


app = FastAPI(
    title="WaterTracker API v2",
    version="2.0.0",
    description="Système d'alerte précoce de tarissement des sources d'eau (Burkina Faso)",
    lifespan=lifespan,
)

# CORS restreint : uniquement les origines configurées.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    return {"message": "WaterTracker API v2 en ligne", "docs": "/docs"}
