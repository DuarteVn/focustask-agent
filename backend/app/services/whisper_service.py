import logging
from typing import Optional

logger = logging.getLogger(__name__)

_model = None


class WhisperService:
    def __init__(self, settings=None):
        from app.core.config import get_settings
        self._settings = settings or get_settings()

    def _get_model(self):
        global _model
        if _model is None:
            from faster_whisper import WhisperModel
            logger.info(
                "loading_whisper_model model=%s device=%s compute_type=%s",
                self._settings.whisper_model,
                self._settings.whisper_device,
                self._settings.whisper_compute_type,
            )
            _model = WhisperModel(
                self._settings.whisper_model,
                device=self._settings.whisper_device,
                compute_type=self._settings.whisper_compute_type,
            )
        return _model

    def transcribe(self, file_path: str) -> tuple[str, str]:
        model = self._get_model()
        logger.info("transcribing file=%s", file_path)
        segments, info = model.transcribe(file_path, beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments)
        language = info.language or "pt"
        logger.info("transcribed language=%s chars=%d", language, len(text))
        return text.strip(), language
