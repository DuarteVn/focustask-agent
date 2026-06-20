from pydantic import BaseModel
from typing import List


class MicroTask(BaseModel):
    order: int
    action: str


class GlossaryItem(BaseModel):
    term: str
    definition: str


class StructuredTask(BaseModel):
    big_picture: str
    micro_tasks: List[MicroTask]
    definition_of_done: List[str]
    glossary: List[GlossaryItem]


class TranscriptionResponse(BaseModel):
    raw_transcript: str
    language: str
    duration_seconds: float


class ProcessResponse(BaseModel):
    raw_transcript: str
    structured: StructuredTask


class HealthResponse(BaseModel):
    status: str
    whisper_loaded: bool
    ollama_reachable: bool
