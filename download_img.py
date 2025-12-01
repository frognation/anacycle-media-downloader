import os
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin

# Configuration
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

def main():
    # Create output directory
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created directory: {OUTPUT_DIR}")

    print(f"Fetching homepage: {BASE_URL}")
    try:
        response = requests.get(BASE_URL, headers=HEADERS)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch homepage: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find all project thumbnails
    # Based on analysis: div.project_thumb contains the link and info
    projects = soup.select('div.project_thumb')
    
    for index, project in enumerate(projects):
        # Extract Project Info
        try:
            link_tag = project.find('a')
            if not link_tag:
                continue
                
            project_url = urljoin(BASE_URL, link_tag.get('href'))
            
            # Title
            title_div = project.select_one('.thumb_title .text')
            title = title_div.get_text(strip=True) if title_div else "Untitled"
            
            # Tags
            tags_div = project.select_one('.thumb_tag .text')
            tags = tags_div.get_text(strip=True) if tags_div else ""
            
            # Thumbnail
            thumb_img = project.select_one('.cardimgcrop img')
            thumb_url = thumb_img.get('src') if thumb_img else None
            
            # Construct Folder Name: "Thumbnail + Title" (User request: "썸네일 + 제목")
            # Interpreting "Thumbnail" as maybe the visual order or just the project name?
            # User said: "각 폴더이름은 웹사이트에서 볼수있는 대로 썸네일 + 제목 으로 정리되있는구조"
            # And "각 프로젝트가 폴더별로 정리되있고 폴더이름은 그 프로젝트의 이름이었으면하고, 태그도 포함하면 더 좋음."
            # So: "Project Name - Tags" seems appropriate.
            
            folder_name = f"{title}"
            if tags:
                folder_name += f" - {tags}"
            
            folder_name = sanitize_filename(folder_name)
            project_dir = os.path.join(OUTPUT_DIR, folder_name)
            
            if not os.path.exists(project_dir):
                os.makedirs(project_dir)
            
            print(f"\n[{index+1}/{len(projects)}] Processing: {folder_name}")
            
            # Download Thumbnail
            if thumb_url:
                thumb_ext = os.path.splitext(thumb_url)[1]
                if not thumb_ext: thumb_ext = ".jpg"
                download_file(thumb_url, os.path.join(project_dir, f"00_thumbnail{thumb_ext}"))

            # Fetch Project Detail Page
            print(f"  Fetching: {project_url}")
            time.sleep(1) # Politeness
            
            proj_response = requests.get(project_url, headers=HEADERS)
            proj_soup = BeautifulSoup(proj_response.content, 'html.parser')
            
            # Find Images
            # Cargo usually puts images in a slideshow container or just in the body
            # We'll look for all images in the main content area if possible, or just all images that look like content.
            # Based on analysis: div.slideshow_container img
            
            images = []
            
            # Method 1: Slideshow container
            slideshow_imgs = proj_soup.select('.slideshow_container img')
            for img in slideshow_imgs:
                src = img.get('src')
                if src: images.append(src)
                
            # Method 2: Look for other content images if slideshow is empty
            if not images:
                content_imgs = proj_soup.select('#content img, .project_content img')
                for img in content_imgs:
                    src = img.get('src')
                    if src: images.append(src)
            
            # Deduplicate
            images = list(set(images))
            
            # Download Images
            for i, img_url in enumerate(images):
                # Try to get high res?
                # For now, just download what we found.
                
                ext = os.path.splitext(img_url)[1]
                if not ext: ext = ".jpg"
                # Remove query params from extension
                ext = ext.split('?')[0]
                
                filename = f"{sanitize_filename(title)}_{i+1:03d}{ext}"
                filepath = os.path.join(project_dir, filename)
                
                download_file(img_url, filepath)
                time.sleep(0.2)
                
        except Exception as e:
            print(f"  [ERROR] Processing project failed: {e}")

    print("\nDone!")

if __name__ == "__main__":
    main()
