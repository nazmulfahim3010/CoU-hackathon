from fastapi import APIRouter, Depends

from app.api.deps import get_sessions
from app.config import Settings, get_settings
from app.core.session_manager import SessionManager, Stage
from app.schemas.glossary import GlossaryStatsResponse
from app.schemas.normalization import (
    NormalizationChange,
    NormalizationRequest,
    NormalizationResponse,
    UncertainSegment,
)
from app.services import demo_data
from app.services.dialect_normalizer import DISCLAIMER, normalize
from app.services.glossary_service import get_glossary_stats, load_glossary
from app.services.llm_provider import llm_configured

router = APIRouter(prefix="/api", tags=["normalization"])


@router.get("/glossary/stats", response_model=GlossaryStatsResponse)
def glossary_stats():
    """Return counts per dialect and verification status."""
    return get_glossary_stats()


@router.post("/normalization", response_model=NormalizationResponse)
async def normalization(
    req: NormalizationRequest,
    s: Settings = Depends(get_settings),
    sessions: SessionManager = Depends(get_sessions),
):
    """Normalize regional dialect transcript to standard Bangla."""
    # Requires minimum stage TRANSCRIBED; raises 409 if session is still CREATED
    session = sessions.require(req.session_id, Stage.TRANSCRIBED)
    if session.stage > Stage.NORMALIZED:
        session.invalidate_after_confirmation()
    original = session.data.get("original", session.original_transcript or "")

    if session.mode == "demo":
        result = None
        # Try real normalization pipeline first if LLM provider is configured
        if llm_configured(s):
            try:
                result = await normalize(original, s, use_llm=True)
                result.session_id = session.id
                result.mode = "demo"
                result.warnings.append("DEMO: Live LLM normalization ran on this prepared demo sample.")
            except Exception:
                result = None

        if result is None:
            # Fall back to cached demo output ONLY when LLM provider is unconfigured or fails
            cached = demo_data.get_cached_output(session.demo_scenario_id or "")
            cached_norm = cached.get("normalization", {})
            scenario = demo_data.get_scenario(session.demo_scenario_id or "")
            norm_text = cached_norm.get("normalized") or scenario.get("normalized", original)
            matches = load_glossary().match(original)
            uncertain = [
                UncertainSegment(text=m.regional, reason=f"Unverified dialect term ({m.dialect})")
                for m in matches
                if m.verification != "verified"
            ]
            changes = [
                NormalizationChange(
                    original=m.regional,
                    normalized=m.standard,
                    reason=f"Glossary match ({m.category})",
                    source="glossary",
                )
                for m in matches
            ]
            result = NormalizationResponse(
                session_id=session.id,
                original=original,
                normalized=norm_text,
                source="cached_demo_output",
                glossary_matches=matches,
                changes=changes,
                uncertain_segments=uncertain,
                uncertain_spans=[m.regional for m in matches if m.verification != "verified"],
                warnings=["cached demo output: LLM provider unavailable; pre-saved sample / unverified demo normalization shown."],
                provider="cached_demo_output",
                mode="demo",
                disclaimer=DISCLAIMER,
            )
    else:
        # LIVE MODE: NEVER reads cached outputs!
        result = await normalize(original, s, use_llm=llm_configured(s))
        result.session_id = session.id
        result.mode = session.mode

    session.normalized_transcript = result.normalized
    session.normalization_notes = result.warnings
    session.data["normalized"] = result.normalized
    session.data["norm_source"] = result.source
    session.stage = Stage.NORMALIZED
    return result
