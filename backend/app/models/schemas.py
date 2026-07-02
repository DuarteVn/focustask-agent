from typing import List, Optional

from pydantic import BaseModel


class StructuredOutput(BaseModel):
    objetivo: str
    checklist: List[str]
    fluxo: List[str]


class TranscriptionResponse(BaseModel):
    raw_transcript: str
    language: str
    duration_seconds: float


class ProcessResponse(BaseModel):
    job_id: str
    raw_transcript: str
    structured: StructuredOutput


class JobStatus(BaseModel):
    job_id: str
    status: str
    structured: Optional[StructuredOutput] = None
    transcript: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    whisper_loaded: bool
    llm: str  # "ready" | "unconfigured"
