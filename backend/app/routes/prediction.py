from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import WaterSource
from ..schemas import (
    PredictRequest,
    PredictResponse,
    TarissementPrediction,
)
from ..services.ml import PredictionService, MLUnavailableError, RuleBasedRiskService
from ..services.prophet_service import predire_tarissement, ProphetUnavailableError
from ..deps import require_api_key

router = APIRouter()


@router.post("/predict", response_model=PredictResponse)
def predict_risk(
    payload: PredictRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    data = payload.model_dump()
    service = PredictionService

    if isinstance(service, RuleBasedRiskService):
        res = service.get_risk_score(data)
        return PredictResponse(**res, source="règles")

    try:
        res = service.get_risk_score(data)
        return PredictResponse(
            score=res["score"],
            status=res["status"],
            periods_until_dry=res.get("periods_until_dry"),
            source="ml",
        )
    except MLUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/water-sources/{source_id}/prediction", response_model=TarissementPrediction)
def get_prediction(source_id: int, db: Session = Depends(get_db)):
    """[v2, historique] Courbe NDWI par semestre (Prophet). Le conseil pour agir est servi par
    /reservoirs/{id}/advice, construit sur les prévisions v3."""
    source = db.get(WaterSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source non trouvée")

    try:
        prediction = predire_tarissement(db, source_id)
    except ProphetUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if "erreur" in prediction:
        raise HTTPException(status_code=404, detail=prediction["erreur"])

    return prediction


@router.post("/admin/collect")
def trigger_collection(_: str = Depends(require_api_key)):
    """[v2, historique] Collecte NDWI semestrielle. Le suivi v3 passe par /admin/monthly-update."""
    from ..collectors.ingest import collect_latest_period

    inserted = collect_latest_period()
    return {"collected": inserted}
