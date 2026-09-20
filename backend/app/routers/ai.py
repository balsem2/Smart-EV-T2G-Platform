from fastapi import APIRouter, HTTPException, status

from app.ml.energy_forecaster import model_metadata


router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/model-info")
def get_model_info() -> dict:
    try:
        return model_metadata()
    except FileNotFoundError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            str(error),
        ) from error
