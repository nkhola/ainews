import os
import glob
import re

def update_generate_site():
    generate_file = '/Users/nitinkhola/github_website/ainews/.scripts/generate_site.py'
    with open(generate_file, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'import subprocess' not in content:
        content = content.replace('import os', 'import os\nimport subprocess\nimport re\nimport glob')

    # Replace the HTML for the button and script with the new audio player
    old_button_pattern = r'<button id="readAloudBtn".*?</button>'
    content = re.sub(old_button_pattern, f'''<div style="background: rgba(30, 32, 50, 0.6); padding: 15px 20px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.1); margin-bottom: 30px; display: flex; align-items: center; gap: 15px;">
            <div style="flex-shrink: 0; background: rgba(59, 130, 246, 0.15); color: #60a5fa; padding: 10px; border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"></path><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path></svg>
            </div>
            <div style="flex-grow: 1;">
                <h3 style="margin: 0 0 5px 0; font-family: 'Outfit', sans-serif; font-size: 1.1rem; color: #f0f4f8;">Listen to the Briefing</h3>
                <audio controls style="width: 100%; height: 36px; border-radius: 8px; outline: none;">
                    <source src="audio/{{base_name}}.mp3" type="audio/mpeg">
                    Your browser does not support the audio element.
                </audio>
            </div>
        </div>''', content, flags=re.DOTALL)

    old_script_pattern = r'<script>\s*const readAloudBtn = document.getElementById\(\'readAloudBtn\'\);.*?</script>\s*</body>'
    content = re.sub(old_script_pattern, '</body>', content, flags=re.DOTALL)

    # Insert the audio generation and rolling window logic right before "daily_file = os.path.join(repo_root, f"{base_name}.html")"
    if 'audio_dir = os.path.join(repo_root, "audio")' not in content:
        audio_generation_logic = '''
    # --- AUDIO GENERATION ---
    audio_dir = os.path.join(repo_root, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    # Extract plain text
    plain_text = "Artificial Intelligence. " + re.sub(r'<[^>]+>', ' ', ai_html) + " Markets and Macro. " + re.sub(r'<[^>]+>', ' ', fin_html)
    plain_text = re.sub(r'\\s+', ' ', plain_text).strip()
    
    # Generate MP3 using edge-tts
    audio_file_path = os.path.join(audio_dir, f"{base_name}.mp3")
    print(f"Generating audio for {base_name}...")
    try:
        subprocess.run([
            os.path.join(repo_root, ".venv/bin/edge-tts"),
            "--text", plain_text,
            "--write-media", audio_file_path,
            "--voice", "en-US-ChristopherNeural"
        ], check=True)
    except Exception as e:
        print(f"Error generating audio: {e}")

    # Rolling window: Keep only the 5 most recent MP3s
    mp3_files = glob.glob(os.path.join(audio_dir, "*.mp3"))
    mp3_files.sort(key=os.path.getmtime, reverse=True)
    if len(mp3_files) > 5:
        for file_to_delete in mp3_files[5:]:
            try:
                os.remove(file_to_delete)
                print(f"Deleted old audio file: {file_to_delete}")
            except Exception as e:
                pass
    # ------------------------

    # Save daily file in the root
'''
        content = content.replace('    # Save daily file in the root\n    daily_file = os.path.join(repo_root, f"{base_name}.html")', audio_generation_logic + '    daily_file = os.path.join(repo_root, f"{base_name}.html")')

    with open(generate_file, 'w', encoding='utf-8') as f:
        f.write(content)


def clean_existing_htmls():
    html_files = glob.glob('/Users/nitinkhola/github_website/ainews/*.html')
    old_button_pattern = r'<button id="readAloudBtn".*?</button>'
    old_script_pattern = r'<script>\s*const readAloudBtn = document.getElementById\(\'readAloudBtn\'\);.*?</script>\s*</body>'

    for file_path in html_files:
        if file_path.endswith('index.html'):
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        changed = False
        if 'id="readAloudBtn"' in content:
            content = re.sub(old_button_pattern, '', content, flags=re.DOTALL)
            changed = True
            
        if 'readAloudBtn' in content and '<script>' in content:
            content = re.sub(old_script_pattern, '</body>', content, flags=re.DOTALL)
            changed = True
            
        if changed:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
if __name__ == "__main__":
    update_generate_site()
    clean_existing_htmls()
    print("Done applying audio changes.")
