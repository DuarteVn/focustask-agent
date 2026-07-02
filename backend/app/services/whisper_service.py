import logging
import subprocess
import tempfile
from pathlib import Path

from faster_whisper import WhisperModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class WhisperService:
    _instance: "WhisperService | None" = None
    _model: WhisperModel | None = None

    def __new__(cls) -> "WhisperService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self) -> None:
        if self._model is not None:
            return
        logger.info(
            "Loading Whisper model=%s device=%s compute=%s",
            settings.whisper_model,
            settings.whisper_device,
            settings.whisper_compute_type,
        )
        self._model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
        logger.info("Whisper model loaded.")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _normalize_audio(self, input_path: Path) -> Path:
        """Convert any audio to 16kHz mono WAV via FFmpeg."""
        output_path = input_path.with_suffix(".norm.wav")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")
        return output_path

    def transcribe(self, audio_bytes: bytes, original_filename: str) -> dict:
        if self._model is None:
            raise RuntimeError("Whisper model not loaded. Call load() first.")

        suffix = Path(original_filename).suffix or ".webm"

        with tempfile.NamedTemporaryFile(
            dir=settings.temp_audio_dir,
            suffix=suffix,
            delete=False,
        ) as tmp:
            tmp.write(audio_bytes)
            raw_path = Path(tmp.name)

        try:
            norm_path = self._normalize_audio(raw_path)
            segments, info = self._model.transcribe(
                str(norm_path),
                beam_size=5,
                language=None,  # auto-detect
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )
            transcript = " ".join(seg.text.strip() for seg in segments)
            return {
                "raw_transcript": transcript,
                "language": info.language,
                "duration_seconds": round(info.duration, 2),
            }
        finally:
            raw_path.unlink(missing_ok=True)
            norm_path = raw_path.with_suffix(".norm.wav")
            norm_path.unlink(missing_ok=True)


whisper_service = WhisperService()
