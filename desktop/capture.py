"""FocusTask Desktop Capture — Windows WASAPI loopback + mic → cloud API → clipboard."""

import os
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import keyboard
import numpy as np
import pyperclip
import requests
import scipy.io.wavfile as wav
import sounddevice as sd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL = os.environ.get("FOCUSTASK_API_URL", "http://localhost:8000/api")
SAMPLE_RATE = 16000
CHANNELS = 1
POLL_INTERVAL = 5
POLL_TIMEOUT = 660  # 11 minutes (covers 45-min audio processing SC-007)
HOTKEY = "F9"

# ---------------------------------------------------------------------------
# Device discovery (WASAPI loopback)
# ---------------------------------------------------------------------------


def _find_loopback_device() -> int | None:
    devices = sd.query_devices()
    loopback_keywords = ["stereo mix", "what u hear", "wave out mix", "loopback"]
    for i, dev in enumerate(devices):
        name_lower = dev["name"].lower()
        if dev["max_input_channels"] > 0:
            if any(kw in name_lower for kw in loopback_keywords):
                return i
    return None


def _find_mic_device() -> int | None:
    default = sd.query_devices(kind="input")
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev["name"] == default["name"]:
            return i
    return sd.default.device[0]


# ---------------------------------------------------------------------------
# Recording state
# ---------------------------------------------------------------------------

_is_recording = False
_system_chunks: list[np.ndarray] = []
_mic_chunks: list[np.ndarray] = []
_system_q: queue.Queue = queue.Queue()
_mic_q: queue.Queue = queue.Queue()
_system_device: int | None = None
_mic_device: int | None = None


def _system_callback(indata, frames, time_info, status):
    _system_q.put(indata.copy())


def _mic_callback(indata, frames, time_info, status):
    _mic_q.put(indata.copy())


def _collect_chunks(q: queue.Queue, chunks: list[np.ndarray], stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            chunk = q.get(timeout=0.1)
            chunks.append(chunk)
        except queue.Empty:
            pass
    while not q.empty():
        chunks.append(q.get_nowait())


# ---------------------------------------------------------------------------
# Mix + export
# ---------------------------------------------------------------------------


def _mix_and_save(system_chunks: list, mic_chunks: list, output_path: str) -> str:
    def to_mono_float(chunks: list) -> np.ndarray | None:
        if not chunks:
            return None
        arr = np.concatenate(chunks, axis=0)
        if arr.ndim > 1:
            arr = arr.mean(axis=1)
        return arr.astype(np.float32)

    system_audio = to_mono_float(system_chunks)
    mic_audio = to_mono_float(mic_chunks)

    if system_audio is not None and mic_audio is not None:
        min_len = min(len(system_audio), len(mic_audio))
        mixed = (system_audio[:min_len] + mic_audio[:min_len]) / 2.0
    elif system_audio is not None:
        mixed = system_audio
    elif mic_audio is not None:
        mixed = mic_audio
    else:
        raise RuntimeError("No audio captured in either channel.")

    mixed = np.clip(mixed, -1.0, 1.0)
    pcm = (mixed * 32767).astype(np.int16)
    wav.write(output_path, SAMPLE_RATE, pcm)
    print(f"💾 Arquivo salvo: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------


def _upload(file_path: str) -> str:
    print("📤 Enviando para API...")
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{API_BASE_URL}/jobs",
            files={"file": (Path(file_path).name, f, "audio/wav")},
            timeout=60,
        )
    resp.raise_for_status()
    job_id = resp.json()["job_id"]
    print(f"🔑 Job ID: {job_id}")
    return job_id


def _poll(job_id: str, file_path: str) -> str | None:
    _STATUS_LABELS = {
        "received": "📨 Recebido...",
        "transcribing": "🎙 Transcrevendo...",
        "analyzing": "🤔 Analisando...",
        "complete": "✅ Completo!",
        "failed": "❌ Falhou",
    }
    deadline = time.time() + POLL_TIMEOUT
    prev_status = ""
    while time.time() < deadline:
        resp = requests.get(f"{API_BASE_URL}/jobs/{job_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        status = data["status"]
        if status != prev_status:
            print(f"   {_STATUS_LABELS.get(status, status)}")
            prev_status = status
        if status == "complete":
            return data["task_id"]
        if status == "failed":
            error = data.get("error_message", "Erro desconhecido")
            print(f"❌ Processamento falhou: {error}")
            print(f"📁 Arquivo preservado em: {file_path}")
            return None
        time.sleep(POLL_INTERVAL)
    print(f"⏱ Timeout aguardando job. Arquivo preservado em: {file_path}")
    return None


def _retrieve(task_id: str) -> str:
    resp = requests.get(f"{API_BASE_URL}/tasks/{task_id}", timeout=10)
    resp.raise_for_status()
    task = resp.json()

    checklist_lines = "\n".join(f"- {item}" for item in task["checklist"])
    flow = task["flow"]
    text = (
        f"## 🎯 Objetivo Direto\n{task['objective']}\n\n"
        f"## ✅ Checklist de Tarefas\n{checklist_lines}\n\n"
        f"## ⚙️ Fluxo de Execução\n"
        f"**Entrada:** {flow['input']}\n"
        f"**Processamento:** {flow['logic']}\n"
        f"**Resultado:** {flow['output']}"
    )
    return text


# ---------------------------------------------------------------------------
# Toggle handler
# ---------------------------------------------------------------------------


def _toggle():
    global _is_recording, _system_chunks, _mic_chunks

    if not _is_recording:
        # Start recording
        _is_recording = True
        _system_chunks = []
        _mic_chunks = []

        if _system_device is None:
            print("⚠️  Capturando apenas microfone (Stereo Mix não encontrado).")

        print(f"\n🎙 Gravação iniciada — pressione {HOTKEY} para parar\n")
        return

    # Stop recording
    _is_recording = False
    print(f"\n⏹ Gravação encerrada.")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main():
    global _system_device, _mic_device

    _system_device = _find_loopback_device()
    _mic_device = _find_mic_device()

    if _system_device is None:
        print(
            "⚠️  Dispositivo 'Stereo Mix' não encontrado.\n"
            "   Para capturar áudio do sistema:\n"
            "   1. Painel de Controle → Som → Gravação\n"
            "   2. Clique com botão direito → 'Mostrar Dispositivos Desabilitados'\n"
            "   3. Habilite 'Stereo Mix'\n"
            "   Continuando com captura apenas do microfone...\n"
        )

    print(f"🎯 FocusTask Desktop Capture")
    print(f"   API: {API_BASE_URL}")
    print(f"   Pressione {HOTKEY} para iniciar/parar gravação")
    print(f"   Ctrl+C para sair\n")

    keyboard.add_hotkey(HOTKEY, _toggle, suppress=False)

    stop_event = threading.Event()

    try:
        streams = []
        sys_chunks_ref: list[np.ndarray] = []
        mic_chunks_ref: list[np.ndarray] = []

        while True:
            # Wait for recording to start
            while not _is_recording:
                time.sleep(0.1)

            # Capture session starts
            session_sys_chunks: list[np.ndarray] = []
            session_mic_chunks: list[np.ndarray] = []
            session_sys_q: queue.Queue = queue.Queue()
            session_mic_q: queue.Queue = queue.Queue()
            session_stop = threading.Event()

            def _sys_cb(indata, frames, t, status):
                session_sys_q.put(indata.copy())

            def _mic_cb(indata, frames, t, status):
                session_mic_q.put(indata.copy())

            sys_thread = threading.Thread(
                target=_collect_chunks,
                args=(session_sys_q, session_sys_chunks, session_stop),
                daemon=True,
            )
            mic_thread = threading.Thread(
                target=_collect_chunks,
                args=(session_mic_q, session_mic_chunks, session_stop),
                daemon=True,
            )

            open_streams = []
            if _system_device is not None:
                s = sd.InputStream(
                    device=_system_device,
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    callback=_sys_cb,
                )
                s.start()
                open_streams.append(s)

            mic_stream = sd.InputStream(
                device=_mic_device,
                samplerate=SAMPLE_RATE,
                channels=1,
                callback=_mic_cb,
            )
            mic_stream.start()
            open_streams.append(mic_stream)

            sys_thread.start()
            mic_thread.start()

            # Wait for recording to stop
            while _is_recording:
                time.sleep(0.1)

            # Tear down
            session_stop.set()
            for s in open_streams:
                s.stop()
                s.close()
            sys_thread.join()
            mic_thread.join()

            # Build output path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(Path.home() / f"recording_{timestamp}.wav")

            try:
                _mix_and_save(session_sys_chunks, session_mic_chunks, output_path)
            except RuntimeError as exc:
                print(f"❌ {exc}")
                continue

            # Upload → poll → deliver
            file_preserved = True
            try:
                job_id = _upload(output_path)
                task_id = _poll(job_id, output_path)
                if task_id:
                    text = _retrieve(task_id)
                    pyperclip.copy(text)
                    print("✅ Copiado para a área de transferência!")
                    file_preserved = False
                    os.remove(output_path)
            except requests.RequestException as exc:
                print(f"❌ Erro de comunicação com API: {exc}")
                print(f"📁 Arquivo preservado em: {output_path}")

    except KeyboardInterrupt:
        print("\n👋 Encerrando FocusTask Capture.")
        sys.exit(0)


if __name__ == "__main__":
    main()
