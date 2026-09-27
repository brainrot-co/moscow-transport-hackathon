from .auth import router as auth_router
from .correction_factors import router as correction_factors_router
from .forecast import router as forecast_router
from .scenarios import router as scenarios_router
from .users import router as users_router

__all__ = (
    "auth_router",
    "correction_factors_router",
    "forecast_router",
    "scenarios_router",
    "users_router",
)
