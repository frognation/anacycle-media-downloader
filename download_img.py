import os
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin, urlparse
from collections import deque
from typing import Callable, Optional, Set

# Default Configuration (used for CLI fallback)
BASE_URL = "https://www.anacycle.com"
OUTPUT_DIR = "anacycle_archive"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
}

def sanitize_filename(name):
    """Sanitizes a string to be safe for filenames."""
    # Remove invalid characters
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # Replace newlines and tabs with spaces
    name = name.replace("\n", " ").replace("\t", " ")
    # Strip leading/trailing whitespace
    return name.strip()

def download_file(url, filepath):
    """Downloads a file from a URL to a specific path."""
    try:
        response = requests.get(url, headers=HEADERS, stream=True)
        response.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"  [OK] Saved: {os.path.basename(filepath)}")
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to download {url}: {e}")
        return False

def get_high_res_url(img_url):
    """
    Attempts to guess the high-resolution URL for Cargo Collective images.
    Cargo often appends dimensions like _670.jpg. We want the original or largest.
    Common suffixes: _o.jpg (original), _2016.jpg, etc.
    """
    # Pattern to match size suffixes like _670, _1000, etc.
    # Example: https://.../name_670.jpg -> https://.../name_o.jpg
    
    # Try to find a size suffix at the end of the filename
    match = re.search(r'(_\d+)(?=\.\w+$)', img_url)
    if match:
        # Replace the size with _o (original) if possible, or just try to remove it?
        # Cargo is tricky. Often _o.jpg works.
        # Let's try to return a list of candidates or just the _o version.
        # For now, let's return the URL as is, but maybe strip query params.
        pass
    
    # Cargo images often look like: .../filename_size.jpg
    # We can try to replace the size with 'o' for original.
    return img_url

def ensure_dir_for_url_path(output_dir: str, media_url: str) -> str:
    """Create local directory structure mirroring the media URL path and return file path."""
    parsed = urlparse(media_url)
    # Use the path part for directory mirroring
    path = parsed.path
    # Ensure path is safe and normalized
    # Remove leading slashes
    while path.startswith('/'):
        path = path[1:]
    # If path ends with a slash, it's a directory — skip
    if not path:
        path = sanitize_filename(os.path.basename(media_url))
    local_path = os.path.join(output_dir, path)
    local_dir = os.path.dirname(local_path)
    if local_dir and not os.path.exists(local_dir):
        os.makedirs(local_dir, exist_ok=True)
    return local_path

ALLOWED_MEDIA_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
    ".mp4", ".mov", ".webm",
    ".mp3", ".wav", ".aac", ".m4a"
}

def is_media_url(u: str) -> bool:
    """Returns True if URL looks like a media file by extension."""
    # Strip query string
    ext = os.path.splitext(urlparse(u).path)[1].lower()
    return ext in ALLOWED_MEDIA_EXTS

def crawl_and_download(
    base_url: str,
    output_dir: str,
    progress_cb: Optional[Callable[[dict], None]] = None,
    max_pages: int = 500,
) -> dict:
    """
    Crawl a site starting from base_url, download all media files while
    mirroring the site's URL path structure under output_dir.

    progress_cb receives a dict with keys: status, pages_processed, pages_queued,
    files_downloaded, files_failed, message.
    Returns final stats dict.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    parsed_base = urlparse(base_url)
    base_netloc = parsed_base.netloc
    scheme = parsed_base.scheme or "https"

    visited: Set[str] = set()
    q: deque[str] = deque()
    q.append(base_url)

    files_downloaded = 0
    files_failed = 0
    pages_processed = 0

    def report(message: str = ""):
        if progress_cb:
            progress_cb({
                "status": "running",
                "pages_processed": pages_processed,
                "pages_queued": len(q),
                "files_downloaded": files_downloaded,
                "files_failed": files_failed,
                "message": message,
            })

    report("Starting crawl")

    try:
        while q and pages_processed < max_pages:
            url = q.popleft()
            if url in visited:
                continue
            visited.add(url)
            pages_processed += 1
            try:
                resp = requests.get(url, headers=HEADERS, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                files_failed += 1
                report(f"Failed to fetch page: {url} -> {e}")
                continue

            soup = BeautifulSoup(resp.content, 'html.parser')

            # Collect media links
            media_urls = set()

            # Images
            for tag in soup.select('img[src]'):
                u = urljoin(url, tag.get('src'))
                if is_media_url(u):
                    media_urls.add(u)

            # Video and audio sources
            for tag in soup.select('video[src], audio[src], source[src]'):
                u = urljoin(url, tag.get('src'))
                if is_media_url(u):
                    media_urls.add(u)

            # Download media
            for mu in sorted(media_urls):
                local_path = ensure_dir_for_url_path(output_dir, mu)
                ok = download_file(mu, local_path)
                if ok:
                    files_downloaded += 1
                else:
                    files_failed += 1
                report(f"Downloaded: {os.path.basename(local_path)}")
                time.sleep(0.05)  # light throttle

            # Enqueue same-origin page links
            for a in soup.select('a[href]'):
                href = a.get('href')
                next_url = urljoin(url, href)
                parsed = urlparse(next_url)
                if parsed.scheme in ("http", "https") and parsed.netloc == base_netloc:
                    # Only enqueue HTML-like pages
                    ext = os.path.splitext(parsed.path)[1].lower()
                    if ext in ("", ".html", ".htm"):
                        if next_url not in visited:
                            q.append(next_url)

            report(f"Processed page: {url}")

    finally:
        final_stats = {
            "status": "completed",
            "pages_processed": pages_processed,
            "pages_queued": len(q),
            "files_downloaded": files_downloaded,
            "files_failed": files_failed,
            "message": "Done",
        }
        if progress_cb:
            progress_cb(final_stats)
    return final_stats

def main():
    """CLI fallback: crawl base URL defined above and download media."""
    stats = crawl_and_download(BASE_URL, OUTPUT_DIR)
    print("\nDone!")
    print(stats)

if __name__ == "__main__":
    main()
