from fastapi import APIRouter, Depends, HTTPException

from app.auth.permissions import RequireRole
from app.auth.schemas import CurrentUser
from app.dependencies.forecast import get_forecast_store
from app.enums import Role
from app.ml import ForecastStore
from app.schemas.correction_factors import CorrectionFactorsRead

router = APIRouter(prefix="/correction-factors", tags=["Correction factors"])


@router.get("", response_model=CorrectionFactorsRead)
async def correction_factors(
    _current_user: CurrentUser = Depends(RequireRole(Role.USER)),
    store: ForecastStore = Depends(get_forecast_store),
) -> CorrectionFactorsRead:
    if store.correction_factors is None:
        raise HTTPException(status_code=503, detail="correction_factors_unavailable")
    return store.correction_factors
