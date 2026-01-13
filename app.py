import os
import threading
import time
import uuid
import sys
import subprocess
from flask import Flask, render_template, request, jsonify
from download_img import crawl_and_download

# Optional native folder chooser (local only)
try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:
    tk = None
    filedialog = None

app = Flask(__name__, template_folder="templates", static_folder="static")

jobs = {}


def start_job(url: str, output_dir: str) -> str:
    job_id = str(uuid.uuid4())
    state = {
        "status": "queued",
        "pages_processed": 0,
        "pages_queued": 0,
        "files_downloaded": 0,
        "files_failed": 0,
        "message": "Queued",
        "url": url,
        "output_dir": output_dir,
    }
    jobs[job_id] = state

    def progress_cb(update):
        # Merge update into state
        state.update(update)
        state["job_id"] = job_id

    def run():
        state["status"] = "running"
        try:
            crawl_and_download(url, output_dir, progress_cb)
            state["status"] = "completed"
            state["message"] = "Completed"
        except Exception as e:
            state["status"] = "error"
            state["message"] = f"Error: {e}"

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return job_id


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/start", methods=["POST"])
def start():
    data = request.get_json(force=True)
    url = data.get("url", "").strip()
    output_dir = data.get("outputDir", "").strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400

    if not output_dir:
        # Default to workspace subfolder 'downloads'
        output_dir = os.path.join(os.getcwd(), "downloads")

    os.makedirs(output_dir, exist_ok=True)

    job_id = start_job(url, output_dir)
    return jsonify({"jobId": job_id})


def _pick_directory() -> str:
    """Open a native folder selection dialog and return chosen path or empty string."""
    # Prefer tkinter if available
    if tk is not None and filedialog is not None:
        root = tk.Tk()
        try:
            root.withdraw()
            # Bring dialog to front
            try:
                root.attributes('-topmost', True)
            except Exception:
                pass
            path = filedialog.askdirectory(title="Select output directory")
            return path or ""
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    # macOS fallback via AppleScript
    if sys.platform == 'darwin':
        script = 'tell application "System Events" to POSIX path of (choose folder with prompt "Select output directory")'
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if proc.returncode == 0:
            return (proc.stdout or "").strip()
        # User cancel usually returns non-zero without reliable message
        if "User canceled" in (proc.stderr or "") or "User canceled" in (proc.stdout or ""):
            return ""
        raise RuntimeError(f"AppleScript error: {proc.stderr or proc.stdout}")

    raise RuntimeError("Native folder chooser unavailable")


@app.route("/choose-dir", methods=["POST"])
def choose_dir():
    """Trigger a local OS folder picker and return the selected path."""
    try:
        path = _pick_directory()
        if not path:
            return jsonify({"cancelled": True}), 200
        return jsonify({"path": path}), 200
    except Exception as e:
        return jsonify({"error": f"Native folder chooser unavailable ({e})"}), 500


@app.route("/status/<job_id>")
def status(job_id: str):
    state = jobs.get(job_id)
    if not state:
        return jsonify({"error": "Job not found"}), 404

    # Attempt a crude progress percent based on pages processed
    pages_processed = state.get("pages_processed", 0)
    pages_queued = state.get("pages_queued", 0)
    # Avoid division by zero; treat >0 processed as some progress
    total = max(pages_processed + pages_queued, 1)
    percent = min(int((pages_processed / total) * 100), 100)

    payload = {
        "status": state.get("status"),
        "message": state.get("message"),
        "pagesProcessed": pages_processed,
        "pagesQueued": pages_queued,
        "filesDownloaded": state.get("files_downloaded", 0),
        "filesFailed": state.get("files_failed", 0),
        "percent": percent,
        "url": state.get("url"),
        "outputDir": state.get("output_dir"),
    }
    return jsonify(payload)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=True)
