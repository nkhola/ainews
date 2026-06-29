#!/usr/bin/env python3
import os
import sys
import platform
import argparse
import json
import glob
import re

if platform.system() == "Darwin" and os.environ.get('OBJC_DISABLE_INITIALIZE_FORK_SAFETY') != 'YES':
    os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
    os.execv(sys.executable, [sys.executable] + sys.argv)

from datetime import datetime, timezone, timedelta

# Ensure we can import from src and pipeline
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(script_dir, "pipeline"))

from crawler import fetch_all_news
from summarizer import summarize_news
from html_builder import build_daily_html, update_index_page
from tts_generator import generate_audio_with_fallback

def get_base_info():
    eastern = timezone(timedelta(hours=-4))
    now = datetime.now(eastern)
    date_str = now.strftime('%Y-%m-%d')
    force_time = os.getenv("FORCE_TIME_LABEL")
    if force_time == "AM":
        is_evening = False
    elif force_time == "PM":
        is_evening = True
    else:
        is_evening = now.hour >= 14
    time_label = "Evening" if is_evening else "Morning"
    file_suffix = "PM" if is_evening else "AM"
    base_name = f"{date_str}-{file_suffix}"
    return date_str, time_label, base_name

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run without hitting Vertex AI API")
    args = parser.parse_args()

    repo_root = os.path.dirname(script_dir)
    os.chdir(script_dir) # For config.yaml finding

    date_str, time_label, base_name = get_base_info()
    print(f"Generating {time_label.lower()} briefing for {date_str}...")
    
    state_dir = os.path.join(script_dir, "state")
    os.makedirs(state_dir, exist_ok=True)
    
    raw_state_file = os.path.join(state_dir, f"raw_news_{date_str}.json")
    llm_state_file = os.path.join(state_dir, f"llm_summary_{date_str}.txt")

    # 1. Crawler
    if os.path.exists(raw_state_file):
        print(f"Loading raw news from state file: {raw_state_file}")
        with open(raw_state_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    else:
        raw_data = fetch_all_news()
        with open(raw_state_file, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2)

    # 2. Summarizer
    if os.path.exists(llm_state_file):
        print(f"Loading LLM summary from state file: {llm_state_file}")
        with open(llm_state_file, "r", encoding="utf-8") as f:
            summary_data = json.load(f)
    else:
        summary_data = summarize_news(raw_data, time_label, dry_run=args.dry_run)
        with open(llm_state_file, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)

    ai_md = summary_data["ai_md"]
    fin_md = summary_data["fin_md"]

    # 3. HTML Builder
    total_words = len(ai_md.split()) + len(fin_md.split())
    reading_time = max(1, total_words // 200)

    ai_html, fin_html, html_content = build_daily_html(date_str, time_label, reading_time, base_name, ai_md, fin_md, repo_root)

    # 4. Audio Generation
    audio_dir = os.path.join(repo_root, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    plain_text = "Artificial Intelligence. " + re.sub(r'<[^>]+>', ' ', ai_html) + " Markets and Macro. " + re.sub(r'<[^>]+>', ' ', fin_html)
    plain_text = re.sub(r'\\s+', ' ', plain_text).strip()
    
    audio_file_path = os.path.join(audio_dir, f"{base_name}.mp3")
    generate_audio_with_fallback(plain_text, audio_file_path, dry_run=args.dry_run)

    # 5. Clean old MP3s
    mp3_files = glob.glob(os.path.join(audio_dir, "*.mp3"))
    mp3_files.sort(key=os.path.getmtime, reverse=True)
    if len(mp3_files) > 10:
        for file_to_delete in mp3_files[10:]:
            try:
                os.remove(file_to_delete)
                print(f"Deleted old audio file: {file_to_delete}")
            except Exception as e:
                pass

    # Save HTML
    daily_file = os.path.join(repo_root, f"{base_name}.html")
    with open(daily_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Saved daily briefing to {daily_file}")

    # Update Index
    update_index_page(repo_root, date_str)

if __name__ == "__main__":
    main()
