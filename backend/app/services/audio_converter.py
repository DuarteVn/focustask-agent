import logging

from pydub import AudioSegment

logger = logging.getLogger(__name__)


def convert_to_wav(input_path: str, output_path: str) -> None:
    try:
        audio = AudioSegment.from_file(input_path)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg not found in PATH — install ffmpeg") from exc

    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(output_path, format="wav")
    logger.info("audio_converted input=%s output=%s", input_path, output_path)
