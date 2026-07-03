import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_duration_seconds(audio_bytes: bytes, filename: str) -> float:
    """Probe audio duration from metadata (pydub) without transcribing.

    Used for upfront 45-min rejection and sync/async routing (contracts/api.md).
    """
    import io

    from pydub import AudioSegment

    fmt = Path(filename).suffix.lstrip(".").lower() or None
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
    return len(audio) / 1000.0


def convert_to_wav(input_path: str, output_path: str) -> str:
    """Convert audio to 16kHz mono WAV via pydub+ffmpeg. Returns output_path."""
    from pydub import AudioSegment

    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(output_path, format="wav")
    logger.debug("Converted %s -> %s", Path(input_path).name, Path(output_path).name)
    return output_path
