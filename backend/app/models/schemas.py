import logging
from typing import List, Optional

from pydantic import BaseModel, model_validator

logger = logging.getLogger(__name__)

# Constitution Principle III (ADHD-Friendly Output) numeric limits.
MAX_OBJETIVO_WORDS = 30
MIN_CHECKLIST_ITEMS = 3
MAX_CHECKLIST_ITEMS = 10
MIN_FLUXO_STAGES = 3
MAX_FLUXO_STAGES = 6


class StructuredOutput(BaseModel):
    objetivo: str
    checklist: List[str]
    fluxo: List[str]

    @model_validator(mode="after")
    def _enforce_adhd_limits(self) -> "StructuredOutput":
        # Out-of-range LLM output is clamped rather than rejected so the user
        # still receives a result; minima cannot be fabricated, so they only
        # log a warning for observability.
        words = self.objetivo.split()
        if len(words) > MAX_OBJETIVO_WORDS:
            logger.warning(
                "objetivo has %d words (limit %d); truncating",
                len(words),
                MAX_OBJETIVO_WORDS,
            )
            self.objetivo = " ".join(words[:MAX_OBJETIVO_WORDS])

        if len(self.checklist) > MAX_CHECKLIST_ITEMS:
            logger.warning(
                "checklist has %d items (limit %d); truncating",
                len(self.checklist),
                MAX_CHECKLIST_ITEMS,
            )
            self.checklist = self.checklist[:MAX_CHECKLIST_ITEMS]
        elif len(self.checklist) < MIN_CHECKLIST_ITEMS:
            logger.warning(
                "checklist has %d items (minimum %d for typical inputs)",
                len(self.checklist),
                MIN_CHECKLIST_ITEMS,
            )

        if len(self.fluxo) > MAX_FLUXO_STAGES:
            logger.warning(
                "fluxo has %d stages (limit %d); truncating",
                len(self.fluxo),
                MAX_FLUXO_STAGES,
            )
            self.fluxo = self.fluxo[:MAX_FLUXO_STAGES]
        elif len(self.fluxo) < MIN_FLUXO_STAGES:
            logger.warning(
                "fluxo has %d stages (minimum %d for typical inputs)",
                len(self.fluxo),
                MIN_FLUXO_STAGES,
            )

        return self


class TranscriptionResponse(BaseModel):
    raw_transcript: str
    language: str
    duration_seconds: float


class ProcessResponse(BaseModel):
    job_id: str
    raw_transcript: str
    structured: StructuredOutput
    markdown: str
    markdown_url: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    structured: Optional[StructuredOutput] = None
    transcript: Optional[str] = None
    error: Optional[str] = None
    markdown_url: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    whisper_loaded: bool
    llm: str  # "ready" | "unconfigured"
