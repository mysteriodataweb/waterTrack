from fastapi import APIRouter

from .routes import health, navigation, prediction, report, reservoirs, water

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(water.router)
api_router.include_router(prediction.router)
api_router.include_router(navigation.router)
api_router.include_router(report.router)
api_router.include_router(reservoirs.router)
