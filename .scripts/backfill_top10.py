import os
import glob
import re
import subprocess
from bs4 import BeautifulSoup

repo_root = "/Users/nitinkhola/github_website/ainews"
audio_dir = os.path.join(repo_root, "audio")
os.makedirs(audio_dir, exist_ok=True)

# Get all HTML files except index.html
html_files = glob.glob(os.path.join(repo_root, "*.html"))
html_files = [f for f in html_files if not f.endswith('index.html') and re.match(r'.*\d{4}-\d{2}-\d{2}', f)]

def get_sort_key(filepath):
    filename = os.path.basename(filepath)
    name = filename.replace('.html', '')
    parts = name.split('-')
    if len(parts) == 4:
        date_str = "-".join(parts[:3])
        suffix = parts[3]
        weight = 1 if suffix == "PM" else 0
    else:
        date_str = name
        weight = 0
    return (date_str, weight)

html_files.sort(key=get_sort_key, reverse=True)

# Process the top 10 files
for file_path in html_files[:10]:
    base_name = os.path.basename(file_path).replace('.html', '')
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "Listen to the Briefing" not in content:
        print(f"Adding audio to {base_name}...")
        soup = BeautifulSoup(content, 'html.parser')
        text = ""
        for section in soup.find_all('div', class_='section-card'):
            text += section.get_text(separator=' ')

        plain_text = re.sub(r'\s+', ' ', text).strip()
        audio_file_path = os.path.join(audio_dir, f"{base_name}.mp3")

        subprocess.run([
            os.path.join(repo_root, ".venv/bin/edge-tts"),
            "--text", plain_text,
            "--write-media", audio_file_path,
            "--voice", "en-US-ChristopherNeural"
        ], check=True)

        audio_player_html = f'''
        <div style="background: rgba(30, 32, 50, 0.6); padding: 15px 20px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.1); margin-bottom: 30px; display: flex; align-items: center; gap: 15px;">
            <div style="flex-shrink: 0; background: rgba(59, 130, 246, 0.15); color: #60a5fa; padding: 10px; border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"></path><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path></svg>
            </div>
            <div style="flex-grow: 1;">
                <h3 style="margin: 0 0 5px 0; font-family: 'Outfit', sans-serif; font-size: 1.1rem; color: #f0f4f8;">Listen to the Briefing</h3>
                <audio controls style="width: 100%; height: 36px; border-radius: 8px; outline: none;">
                    <source src="audio/{base_name}.mp3" type="audio/mpeg">
                    Your browser does not support the audio element.
                </audio>
            </div>
        </div>
'''

        content = content.replace('<div class="section-card" id="ai-news">', audio_player_html + '\n        <div class="section-card" id="ai-news">')

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Finished {base_name}")
    else:
        print(f"Already added to {base_name}")

print("Backfill complete.")
