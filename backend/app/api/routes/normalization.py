from fastapi import APIRouter, Depends

from app.api.deps import get_sessions
from app.config import Settings, get_settings
from app.core.session_manager import SessionManager, Stage
from app.schemas.normalization import NormalizationRequest, NormalizationResponse
from app.services import demo_data
from app.services.dialect_normalizer import DISCLAIMER, normalize
from app.services.glossary_service import load_glossary
from app.services.providers.llm import llm_configured

router = APIRouter(prefix="/api", tags=["normalization"])


@router.post("/normalization", response_model=NormalizationResponse)
async def normalization(
    req: NormalizationRequest,
    s: Settings = Depends(get_settings),
    sessions: SessionManager = Depends(get_sessions),
):
    session = sessions.require(req.session_id, Stage.TRANSCRIBED)
    original = session.data["original"]
    if session.mode == "demo":
        scenario = demo_data.get_scenario(session.demo_scenario_id or "")
        matches = load_glossary().match(original)
        result = NormalizationResponse(
            session_id=session.id, original=original, normalized=scenario["normalized"], source="demo_prepared",
            glossary_matches=matches, uncertain_spans=[m.regional for m in matches if m.verification != "verified"],
            warnings=["DEMO: the standard Bangla text is prepared, not model output. Glossary matches are computed live."],
            provider="demo", disclaimer=DISCLAIMER,
        )
    else:
        result = await normalize(original, s, use_llm=llm_configured(s))
        result.session_id = session.id
    session.data["normalized"] = result.normalized
    session.data["norm_source"] = result.source
    session.stage = max(session.stage, Stage.NORMALIZED)
    return result
