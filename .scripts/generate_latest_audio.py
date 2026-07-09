import os
import re
import glob
from bs4 import BeautifulSoup
from generate_site import (
    build_audio_script,
    generate_audio_with_fallback,
    html_to_speech_text,
)

def backfill_latest_audio():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    audio_dir = os.path.join(repo_root, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    # Find the most recent HTML file
    html_files = glob.glob(os.path.join(repo_root, "*.html"))
    # Filter out index.html
    html_files = [f for f in html_files if not f.endswith("index.html")]
    html_files.sort(reverse=True)

    if not html_files:
        print("No HTML files found.")
        return

    # Just take the single most recent file (index 0)
    html_file = html_files[0]
    base_name = os.path.splitext(os.path.basename(html_file))[0]
    audio_file_path = os.path.join(audio_dir, f"{base_name}.mp3")

    print(f"Processing ONLY the latest briefing: {base_name}...")

    with open(html_file, "r", encoding="utf-8") as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')

    # Extract AI and Finance news
    ai_div = soup.find(id='ai-news')
    fin_div = soup.find(id='finance-news')

    if not ai_div and not fin_div:
        print(f"  Skipping {base_name}, no relevant content found.")
        return

    ai_text = html_to_speech_text(ai_div.decode_contents()) if ai_div else ""
    fin_text = html_to_speech_text(fin_div.decode_contents()) if fin_div else ""

    flattened = f"Artificial Intelligence. {ai_text} Markets and Macro. {fin_text}"
    flattened = re.sub(r'\s+', ' ', flattened).strip()

    parts = base_name.split('-')
    date_str = "-".join(parts[:3])
    time_label = ("Evening" if parts[3] == "PM" else "Morning") if len(parts) == 4 else "Morning"

    briefing_source = (
        f"## Artificial Intelligence\n\n{ai_text}\n\n## Markets and Macro\n\n{fin_text}"
    )
    plain_text = build_audio_script(
        briefing_source, date_str, time_label, fallback_text=flattened,
    )

    # Generate the audio
    generate_audio_with_fallback(plain_text, audio_file_path)
    print(f"Finished generating {audio_file_path}!")

if __name__ == "__main__":
    backfill_latest_audio()
