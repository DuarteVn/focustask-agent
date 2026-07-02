from typing import Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    whisper: str
    llm: str


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str
    created_at: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    updated_at: str
    task_id: Optional[str] = None
    error_message: Optional[str] = None


class ExecutionFlow(BaseModel):
    input: str
    logic: str
    output: str


class TaskDetailResponse(BaseModel):
    task_id: str
    created_at: str
    detected_language: str
    audio_duration_seconds: Optional[float] = None
    raw_transcript: str
    objective: str
    checklist: list[str]
    flow: ExecutionFlow


class TaskSummaryItem(BaseModel):
    task_id: str
    created_at: str
    objective: str
    detected_language: str


class TaskListResponse(BaseModel):
    tasks: list[TaskSummaryItem]
    total: int
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
