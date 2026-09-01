from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
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
from ..services.recommande import generer_recommandation, generer_toutes_recommandations
from ..deps import require_api_key

router = APIRouter()

Profil = Literal["ong", "gouvernement", "agent_terrain", "communaute", "all"]


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
def get_prediction(
    source_id: int,
    profil: Profil = "communaute",
    db: Session = Depends(get_db),
):
    source = db.get(WaterSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source non trouvée")

    try:
        prediction = predire_tarissement(db, source_id)
    except ProphetUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if "erreur" in prediction:
        raise HTTPException(status_code=404, detail=prediction["erreur"])

    if profil == "all":
        prediction["recommandations"] = generer_toutes_recommandations(prediction)
    else:
        prediction["recommandation"] = generer_recommandation(prediction, profil)

    return prediction


@router.post("/admin/collect")
def trigger_collection(_: str = Depends(require_api_key)):
    """Déclenche une collecte satellite manuelle de la période courante."""
    from ..collectors.ingest import collect_latest_period

    inserted = collect_latest_period()
    return {"collected": inserted}
