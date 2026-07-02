import time
import httpx
import gradio as gr

API_BASE = "http://localhost:8000/api"


def _poll_job(job_id: str, timeout: int = 600) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = httpx.get(f"{API_BASE}/jobs/{job_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        status = data["status"]
        yield status, data
        if status in ("complete", "failed"):
            return
        time.sleep(3)
    yield "failed", {"error_message": "Polling timeout"}


def _format_checklist(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _format_flow(flow: dict) -> str:
    return (
        f"**Entrada:** {flow['input']}\n\n"
        f"**Processamento:** {flow['logic']}\n\n"
        f"**Resultado:** {flow['output']}"
    )


def _format_clipboard(objective: str, checklist: list[str], flow: dict) -> str:
    lines = [
        "## 🎯 Objetivo Direto",
        objective,
        "",
        "## ✅ Checklist de Tarefas",
        _format_checklist(checklist),
        "",
        "## ⚙️ Fluxo de Execução",
        f"**Entrada:** {flow['input']}",
        f"**Processamento:** {flow['logic']}",
        f"**Resultado:** {flow['output']}",
    ]
    return "\n".join(lines)


def _process_audio(file_path: str):
    if not file_path:
        yield "Nenhum arquivo fornecido.", "", "", "", "", ""
        return

    # Upload
    yield "📤 Enviando áudio...", "", "", "", "", ""
    try:
        with open(file_path, "rb") as f:
            filename = file_path.split("/")[-1].split("\\")[-1]
            resp = httpx.post(
                f"{API_BASE}/jobs",
                files={"file": (filename, f)},
                timeout=30,
            )
        resp.raise_for_status()
        job_id = resp.json()["job_id"]
    except Exception as exc:
        yield f"❌ Erro ao enviar: {exc}", "", "", "", "", ""
        return

    # Poll
    _STATUS_LABELS = {
        "received": "📨 Recebido...",
        "transcribing": "🎙 Transcrevendo...",
        "analyzing": "🤔 Analisando...",
        "complete": "✅ Pronto!",
        "failed": "❌ Falhou",
    }

    task_id = None
    for status, data in _poll_job(job_id):
        label = _STATUS_LABELS.get(status, status)
        yield label, "", "", "", "", ""
        if status == "complete":
            task_id = data.get("task_id")
        elif status == "failed":
            yield f"❌ {data.get('error_message', 'Erro desconhecido')}", "", "", "", "", ""
            return

    if not task_id:
        yield "❌ Processamento falhou sem retornar task_id.", "", "", "", "", ""
        return

    # Retrieve
    try:
        resp = httpx.get(f"{API_BASE}/tasks/{task_id}", timeout=10)
        resp.raise_for_status()
        task = resp.json()
    except Exception as exc:
        yield f"❌ Erro ao buscar resultado: {exc}", "", "", "", "", ""
        return

    objective = task["objective"]
    checklist = task["checklist"]
    flow = task["flow"]
    transcript = task["raw_transcript"]
    clipboard_text = _format_clipboard(objective, checklist, flow)

    yield (
        "✅ Pronto!",
        objective,
        _format_checklist(checklist),
        _format_flow(flow),
        transcript,
        clipboard_text,
    )


def _load_history():
    try:
        resp = httpx.get(f"{API_BASE}/tasks?limit=20", timeout=10)
        resp.raise_for_status()
        tasks = resp.json()["tasks"]
        if not tasks:
            return "Nenhuma tarefa encontrada."
        rows = []
        for t in tasks:
            dt = t["created_at"][:16].replace("T", " ")
            lang = t["detected_language"].upper()
            obj = t["objective"][:80] + ("..." if len(t["objective"]) > 80 else "")
            rows.append(f"**{dt}** [{lang}] — {obj}\n`{t['task_id']}`")
        return "\n\n---\n\n".join(rows)
    except Exception as exc:
        return f"❌ Erro ao carregar histórico: {exc}"


with gr.Blocks(title="FocusTask Agent", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎯 FocusTask Agent\nConverta áudio em tarefas estruturadas para foco total.")

    with gr.Tabs():
        # Tab 1: File upload
        with gr.Tab("📁 Arquivo"):
            with gr.Row():
                with gr.Column(scale=1):
                    file_input = gr.Audio(
                        label="Áudio da tarefa",
                        sources=["upload"],
                        type="filepath",
                    )
                    submit_btn = gr.Button("🚀 Processar", variant="primary")

            status_label = gr.Label(label="Status", value="Aguardando...")

            with gr.Row():
                with gr.Column():
                    objective_out = gr.Markdown(label="🎯 Objetivo Direto")
                with gr.Column():
                    checklist_out = gr.Markdown(label="✅ Checklist de Tarefas")

            flow_out = gr.Markdown(label="⚙️ Fluxo de Execução")
            transcript_out = gr.Textbox(
                label="📝 Transcrição bruta",
                lines=4,
                interactive=False,
                visible=True,
            )
            clipboard_box = gr.Textbox(visible=False, elem_id="clipboard_file")
            copy_btn = gr.Button("📋 Copiar tudo", variant="secondary")

            submit_btn.click(
                fn=_process_audio,
                inputs=[file_input],
                outputs=[
                    status_label,
                    objective_out,
                    checklist_out,
                    flow_out,
                    transcript_out,
                    clipboard_box,
                ],
            )

            copy_btn.click(
                fn=None,
                inputs=[clipboard_box],
                outputs=[],
                js="(text) => { navigator.clipboard.writeText(text).catch(() => {}); }",
            )

        # Tab 2: Microphone
        with gr.Tab("🎙 Microfone"):
            mic_input = gr.Audio(
                label="Grave sua instrução",
                sources=["microphone"],
                type="filepath",
            )
            mic_submit_btn = gr.Button("🚀 Processar gravação", variant="primary")
            mic_status = gr.Label(label="Status", value="Aguardando...")

            with gr.Row():
                with gr.Column():
                    mic_objective = gr.Markdown(label="🎯 Objetivo Direto")
                with gr.Column():
                    mic_checklist = gr.Markdown(label="✅ Checklist de Tarefas")

            mic_flow = gr.Markdown(label="⚙️ Fluxo de Execução")
            mic_transcript = gr.Textbox(label="📝 Transcrição bruta", lines=4, interactive=False)
            mic_clipboard = gr.Textbox(visible=False, elem_id="clipboard_mic")
            mic_copy_btn = gr.Button("📋 Copiar tudo", variant="secondary")

            mic_submit_btn.click(
                fn=_process_audio,
                inputs=[mic_input],
                outputs=[mic_status, mic_objective, mic_checklist, mic_flow, mic_transcript, mic_clipboard],
            )
            mic_copy_btn.click(
                fn=None,
                inputs=[mic_clipboard],
                outputs=[],
                js="(text) => { navigator.clipboard.writeText(text).catch(() => {}); }",
            )

        # Tab 3: History
        with gr.Tab("📋 Histórico"):
            refresh_btn = gr.Button("🔄 Atualizar histórico")
            history_out = gr.Markdown(value="Clique em 'Atualizar' para carregar o histórico.")

            refresh_btn.click(fn=_load_history, inputs=[], outputs=[history_out])
