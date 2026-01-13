# Website Media Downloader

Download images/audio/video from a given website and save them locally while mirroring the site's URL path structure. Includes a simple web UI with progress.

## Run

1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Start the server

```bash
python app.py
```

3. Open in browser: http://127.0.0.1:5000

## Usage
- Enter the start page URL (e.g., https://example.com).
- Set the save location either by typing a folder path or clicking the "Choose Folder" button. If left empty, a `downloads/` folder inside the project is used.
- Click Start and track the progress and status in the bottom panel.

## Notes
- Only same-origin links (same host) are crawled, up to 500 pages by default.
- Supported extensions: images (jpg, jpeg, png, gif, webp, svg), video (mp4, mov, webm), audio (mp3, wav, aac, m4a).
- Folder selection uses a native dialog. On macOS, it falls back to AppleScript when `tkinter` is unavailable. If native selection fails, type the path manually.
- Web security prevents a browser from giving a server direct access to local folders; hence native selection is handled on the server-side.
