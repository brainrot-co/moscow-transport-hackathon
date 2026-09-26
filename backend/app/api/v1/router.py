from fastapi import APIRouter

from .endpoints import auth_router, forecast_router, scenarios_router, users_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(users_router)
router.include_router(forecast_router)
router.include_router(scenarios_router)
