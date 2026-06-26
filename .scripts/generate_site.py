#!/usr/bin/env python3
import os
import sys
import platform

if platform.system() == "Darwin" and os.environ.get('OBJC_DISABLE_INITIALIZE_FORK_SAFETY') != 'YES':
    os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
    os.execv(sys.executable, [sys.executable] + sys.argv)

import subprocess
import re
import glob
from datetime import datetime, timezone, timedelta
import markdown

# Ensure we can import from src
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.fetchers.news_crawler import NewsCrawler
from src.fetchers.finance_crawler import FinanceCrawler
from src.agents.master_compiler import MasterCompiler

def generate_daily_briefing():
    # Setup directories
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    
    # Change working directory to .scripts so config.yaml is found by the crawlers
    os.chdir(script_dir)

    # Use Eastern Time for the briefing date
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
    print(f"Generating {time_label.lower()} briefing for {date_str}...")

    compiler = MasterCompiler()

    # 1. Fetch & Compile AI News
    print("Fetching AI News...")
    ai_crawler = NewsCrawler()
    ai_raw = ai_crawler.get_latest_news()
    ai_md = compiler.synthesize_news(ai_raw, topic="ai", time_label=time_label)

    # 2. Fetch & Compile Finance News
    print("Fetching Finance News...")
    fin_crawler = FinanceCrawler()
    fin_raw = fin_crawler.get_latest_news()
    fin_md = compiler.synthesize_news(fin_raw, topic="finance", time_label=time_label)

    # Calculate reading time (rough estimate: 200 words per minute)
    total_words = len(ai_md.split()) + len(fin_md.split())
    reading_time = max(1, total_words // 200)

    # Convert to HTML
    ai_html = markdown.markdown(ai_md, extensions=['tables', 'fenced_code'])
    fin_html = markdown.markdown(fin_md, extensions=['tables', 'fenced_code'])

    # 2.5 Generate Recent Briefings HTML
    import re
    existing_files = [f for f in os.listdir(repo_root) if f.endswith('.html') and f != 'index.html' and re.match(r'^\d{4}-\d{2}-\d{2}', f)]
    
    def recent_sort_key(filename):
        name = filename.replace('.html', '')
        parts = name.split('-')
        weight = 1 if len(parts) == 4 and parts[3] == "PM" else 0
        return ("-".join(parts[:3]) if len(parts) == 4 else name, weight)
        
    existing_files.sort(key=recent_sort_key, reverse=True)
    
    recent_html = ""
    for rf in existing_files[:3]:
        rf_name = rf.replace('.html', '')
        rf_parts = rf_name.split('-')
        display_name = f"{rf_parts[0]}-{rf_parts[1]}-{rf_parts[2]} {'Evening' if len(rf_parts) == 4 and rf_parts[3] == 'PM' else 'Morning'} Briefing" if len(rf_parts) == 4 else f"{rf_name} Briefing"
        recent_html += f'                <a href="{rf}"><span>{display_name}</span> <span class="date">Read →</span></a>\n'
    recent_html += '                <a href="index.html"><span>View All Briefings</span> <span class="date">Archive →</span></a>\n'

    # 3. Create Daily HTML Page
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Post-Human Briefing - {date_str}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;700;800&family=Space+Mono:ital,wght@0,400;0,700;1,400;1,700&display=swap" rel="stylesheet">
    <link rel="icon" type="image/png" href="img/logo_favicon.png">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --bg-gradient: linear-gradient(135deg, #0b0f19 0%, #1a1b35 100%);
            --surface-color: rgba(30, 32, 50, 0.6);
            --surface-hover: rgba(45, 48, 75, 0.8);
            --text-main: #f0f4f8;
            --text-muted: #a0aec0;
            --accent-glow: #3b82f6;
            --accent-glow-secondary: #8b5cf6;
            --border-color: rgba(255, 255, 255, 0.1);
            --shadow: 0 10px 25px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.1);
        }}
        
        body {{
            margin: 0;
            padding: 0;
            background: var(--bg-gradient);
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Inter', -apple-system, sans-serif;
            line-height: 1.7;
            min-height: 100vh;
        }}

        .ambient-glow {{
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            overflow: hidden;
            z-index: -1;
            pointer-events: none;
        }}
        .ambient-glow::before, .ambient-glow::after {{
            content: '';
            position: absolute;
            width: 600px;
            height: 600px;
            border-radius: 50%;
            filter: blur(120px);
            opacity: 0.15;
            animation: float 20s infinite alternate;
        }}
        .ambient-glow::before {{
            background: var(--accent-glow);
            top: -100px; left: -100px;
        }}
        .ambient-glow::after {{
            background: var(--accent-glow-secondary);
            bottom: -100px; right: -100px;
            animation-delay: -10s;
        }}

        @keyframes float {{
            0% {{ transform: translate(0, 0); }}
            100% {{ transform: translate(50px, 50px); }}
        }}

        .briefing-container {{
            max-width: 850px;
            margin: 0 auto;
            padding: 40px 20px 80px 20px;
            position: relative;
        }}

        /* Navbar */
        .nav-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
        }}

        .nav-link {{
            display: inline-block;
            color: var(--text-main);
            text-decoration: none;
            font-weight: 600;
            font-size: 0.95rem;
            padding: 8px 16px;
            border-radius: 20px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.2s ease;
            backdrop-filter: blur(10px);
        }}

        .nav-link:hover {{
            background: rgba(255,255,255,0.1);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }}

        /* Header Section */
        .header-section {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 40px;
            padding-bottom: 16px;
            border-bottom: 2px solid var(--border-color);
            flex-wrap: wrap;
            gap: 16px;
        }}
        .header-title {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .header-section .logo {{
            width: 48px;
            height: auto;
            border-radius: 6px;
            margin: 0;
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.4);
        }}
        .header-section h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.8rem;
            font-weight: 800;
            margin: 0;
            background: linear-gradient(to right, #60a5fa, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }}
        .header-section .meta {{
            text-align: right;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 4px;
        }}
        .header-section .date {{
            font-family: 'Space Mono', monospace;
            font-size: 1.3rem;
            color: #f0f4f8;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .header-section .reading-time {{
            font-size: 0.95rem;
            color: var(--text-muted);
            font-family: 'Outfit', sans-serif;
        }}
        
        @media (max-width: 600px) {{
            .header-section {{
                flex-direction: column;
                align-items: flex-start;
            }}
            .header-section .meta {{
                align-items: flex-start;
                text-align: left;
            }}
        }}

        /* Section Cards */
        .section-card {{
            background: var(--surface-color);
            padding: 40px;
            border-radius: 16px;
            box-shadow: var(--shadow);
            margin-bottom: 40px;
            border: 1px solid var(--border-color);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
        }}
        .section-header {{
            border-bottom: 2px solid rgba(255, 255, 255, 0.15);
            padding-bottom: 12px;
            margin-bottom: 28px;
        }}
        .section-header h2 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2rem;
            font-weight: 800;
            color: var(--text-main);
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .section-card h3 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.4rem;
            color: #f0f4f8;
            margin-top: 48px;
            margin-bottom: 16px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .section-card p {{
            font-size: 1.15rem;
            margin-bottom: 24px;
            color: #d1d5db;
            line-height: 1.8;
        }}
        .section-card ul {{
            padding-left: 24px;
            color: #d1d5db;
            margin-bottom: 24px;
        }}
        .section-card li {{
            margin-bottom: 12px;
            font-size: 1.1rem;
            line-height: 1.7;
        }}
        a {{
            color: #3b82f6;
            text-decoration: none;
            font-weight: 500;
            transition: color 0.2s ease;
        }}
        a:hover {{
            text-decoration: underline;
            color: #60a5fa;
        }}
        blockquote {{
            border-left: 4px solid #8b5cf6;
            margin: 0;
            padding: 10px 20px;
            background: rgba(255,255,255,0.03);
            font-style: italic;
            border-radius: 0 8px 8px 0;
            color: #9ca3af;
        }}

        /* Recent Briefings at bottom */
        .recent-briefings {{
            margin-top: 60px;
            padding-top: 40px;
            border-top: 2px solid var(--border-color);
        }}
        .recent-briefings h3 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.5rem;
            margin-bottom: 20px;
            text-align: center;
        }}
        .recent-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        .recent-list a {{
            display: flex;
            justify-content: space-between;
            padding: 16px 20px;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            color: var(--text-main);
            transition: all 0.2s ease;
        }}
        .recent-list a:hover {{
            background: rgba(255,255,255,0.08);
            border-color: rgba(96, 165, 250, 0.3);
            transform: translateY(-2px);
        }}
        .recent-list .date {{
            color: #9ca3af;
            font-family: 'Outfit', sans-serif;
        }}

        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg-color); }}
        ::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.2); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: rgba(255,255,255,0.3); }}

    </style>
</head>
<body>
    <div class="ambient-glow"></div>
    <div class="briefing-container">
        <div class="nav-bar">
            <a href="index.html" class="nav-link">← All Briefings</a>
            <a href="https://www.khola.blog/" class="nav-link" target="_blank">Khola.Blog ↗</a>
        </div>
        
        <div class="header-section">
            <div class="header-title">
                <img src="img/logo_256.png" alt="Logo" class="logo">
                <h1>The Post-Human Briefing</h1>
            </div>
            <div class="meta">
                <span class="date">{date_str} &bull; {time_label}</span>
                <span class="reading-time">{reading_time} min read</span>
            </div>
        </div>
        
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

        <div class="section-card" id="ai-news">
            <div class="section-header">
                <h2>Artificial Intelligence</h2>
            </div>
            {ai_html}
        </div>

        <div class="section-card" id="finance-news">
            <div class="section-header">
                <h2>Markets &amp; Macro</h2>
            </div>
            {fin_html}
        </div>

        <div class="recent-briefings">
            <h3>Recent Briefings</h3>
            <div class="recent-list">
{recent_html}
            </div>
        </div>
    </div>

    </body>
</html>
"""
    

    # --- AUDIO GENERATION ---
    audio_dir = os.path.join(repo_root, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    # Extract plain text
    plain_text = "Artificial Intelligence. " + re.sub(r'<[^>]+>', ' ', ai_html) + " Markets and Macro. " + re.sub(r'<[^>]+>', ' ', fin_html)
    plain_text = re.sub(r'\s+', ' ', plain_text).strip()
    
    # Generate MP3 using edge-tts
    audio_file_path = os.path.join(audio_dir, f"{base_name}.mp3")
    print(f"Generating audio for {base_name}...")
    try:
        subprocess.run([
            "edge-tts",
            "--text", plain_text,
            "--write-media", audio_file_path,
            "--voice", "en-US-ChristopherNeural"
        ], check=True)
    except Exception as e:
        print(f"Error generating audio: {e}")

    # Rolling window: Keep only the 10 most recent MP3s
    mp3_files = glob.glob(os.path.join(audio_dir, "*.mp3"))
    mp3_files.sort(key=os.path.getmtime, reverse=True)
    if len(mp3_files) > 10:
        for file_to_delete in mp3_files[10:]:
            try:
                os.remove(file_to_delete)
                print(f"Deleted old audio file: {file_to_delete}")
            except Exception as e:
                pass
    # ------------------------

    # Save daily file in the root
    daily_file = os.path.join(repo_root, f"{base_name}.html")
    with open(daily_file, "w", encoding="utf-8") as f:
        f.write(html_template)
    print(f"Saved daily briefing to {daily_file}")

    # 4. Update Index Page
    update_index_page(repo_root, date_str)

def update_index_page(repo_root, new_date_str):
    import re
    # Find all html files in the directory that look like dates (e.g. YYYY-MM-DD)
    files = [f for f in os.listdir(repo_root) if f.endswith('.html') and f != 'index.html' and re.match(r'^\d{4}-\d{2}-\d{2}', f)]
    
    def get_sort_key(filename):
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

    # Sort files descending (newest first)
    files.sort(key=get_sort_key, reverse=True)

    links_html = ""
    for f in files:
        name_parts = f.replace('.html', '').split('-')
        if len(name_parts) == 4:
            year, month, day, am_pm = name_parts
            label = "Evening" if am_pm == "PM" else "Morning"
            display_name = f'<span class="date">{year}-{month}-{day}</span> {label} Briefing'
        else:
            date_name = f.replace('.html', '')
            display_name = f'<span class="date">{date_name}</span> Briefing'
            
        links_html += f'            <li><a href="{f}">{display_name} <span class="read-more">Read →</span></a></li>\n'

    index_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Post-Human Briefing</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;700;800&display=swap" rel="stylesheet">
    <link rel="icon" type="image/png" href="img/logo_favicon.png">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --bg-gradient: linear-gradient(135deg, #0b0f19 0%, #1a1b35 100%);
            --surface-color: rgba(30, 32, 50, 0.6);
            --surface-hover: rgba(45, 48, 75, 0.8);
            --text-main: #f0f4f8;
            --text-muted: #a0aec0;
            --accent-glow: #3b82f6;
            --accent-glow-secondary: #8b5cf6;
            --border-color: rgba(255, 255, 255, 0.1);
        }}
        
        body {{
            margin: 0;
            padding: 0;
            background: var(--bg-gradient);
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Inter', -apple-system, sans-serif;
            line-height: 1.6;
            min-height: 100vh;
        }}

        .ambient-glow {{
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            overflow: hidden;
            z-index: -1;
            pointer-events: none;
        }}
        .ambient-glow::before, .ambient-glow::after {{
            content: '';
            position: absolute;
            width: 600px;
            height: 600px;
            border-radius: 50%;
            filter: blur(120px);
            opacity: 0.15;
            animation: float 20s infinite alternate;
        }}
        .ambient-glow::before {{
            background: var(--accent-glow);
            top: -100px; left: -100px;
        }}
        .ambient-glow::after {{
            background: var(--accent-glow-secondary);
            bottom: -100px; right: -100px;
            animation-delay: -10s;
        }}

        @keyframes float {{
            0% {{ transform: translate(0, 0); }}
            100% {{ transform: translate(50px, 50px); }}
        }}

        .archive-container {{
            max-width: 850px;
            margin: 0 auto;
            padding: 40px 20px 80px 20px;
            position: relative;
        }}

        header {{
            text-align: center;
            margin-bottom: 60px;
            animation: fade-in-down 0.8s ease-out;
        }}
        
        @keyframes fade-in-down {{
            from {{ opacity: 0; transform: translateY(-20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .logo-container {{
            position: relative;
            display: inline-block;
            margin-bottom: 24px;
        }}
        
        .logo-container img {{
            width: 120px;
            height: auto;
            border-radius: 12px;
            box-shadow: 0 0 30px rgba(59, 130, 246, 0.4);
            border: 2px solid rgba(255,255,255,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}

        .logo-container img:hover {{
            transform: scale(1.05);
            box-shadow: 0 0 45px rgba(139, 92, 246, 0.6);
        }}

        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 3.5rem;
            font-weight: 800;
            margin: 0 0 10px 0;
            background: linear-gradient(to right, #60a5fa, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -1px;
        }}

        p.subtitle {{
            color: var(--text-muted);
            font-size: 1.25rem;
            max-width: 600px;
            margin: 0 auto;
        }}

        .nav-links {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 30px;
        }}
        
        .nav-link {{
            display: inline-block;
            color: var(--text-main);
            text-decoration: none;
            font-weight: 600;
            font-size: 0.95rem;
            padding: 8px 16px;
            border-radius: 20px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.2s ease;
            backdrop-filter: blur(10px);
        }}

        .nav-link:hover {{
            background: rgba(255,255,255,0.1);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }}

        .archive-list {{
            list-style: none;
            padding: 0;
            margin: 0;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}

        .archive-list li {{
            animation: fade-in-up 0.6s ease-out both;
        }}
        
        .archive-list li:nth-child(1) {{ animation-delay: 0.1s; }}
        .archive-list li:nth-child(2) {{ animation-delay: 0.15s; }}
        .archive-list li:nth-child(3) {{ animation-delay: 0.2s; }}
        .archive-list li:nth-child(4) {{ animation-delay: 0.25s; }}
        .archive-list li:nth-child(5) {{ animation-delay: 0.3s; }}
        .archive-list li:nth-child(6) {{ animation-delay: 0.35s; }}

        @keyframes fade-in-up {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .archive-list a {{
            display: flex;
            align-items: center;
            padding: 20px 24px;
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            color: var(--text-main);
            text-decoration: none;
            font-size: 1.15rem;
            font-weight: 500;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}

        .archive-list a:hover {{
            background: var(--surface-hover);
            border-color: rgba(96, 165, 250, 0.5);
            transform: translateY(-3px) scale(1.01);
            box-shadow: 0 10px 25px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.1);
        }}

        .archive-list a span.date {{
            color: #94a3b8;
            font-family: 'Outfit', sans-serif;
            font-size: 1.05rem;
            margin-right: 16px;
            background: rgba(0,0,0,0.3);
            padding: 4px 10px;
            border-radius: 8px;
        }}

        .archive-list a span.read-more {{
            margin-left: auto;
            color: #60a5fa;
            font-size: 0.95rem;
            font-weight: 600;
            opacity: 0.8;
            transition: opacity 0.2s ease, transform 0.2s ease;
        }}

        .archive-list a:hover span.read-more {{
            opacity: 1;
            transform: translateX(4px);
        }}

        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg-color); }}
        ::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.2); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: rgba(255,255,255,0.3); }}

    </style>
</head>
<body>
    <div class="ambient-glow"></div>
    
    <div class="archive-container">
        <header>
            <div class="logo-container">
                <img src="img/logo_256.png" alt="The Post-Human Briefing Logo">
            </div>
            <h1>The Post-Human Briefing</h1>
            <p class="subtitle">A daily automated synthesis of top-tier AI and Finance intelligence, generated entirely by autonomous agents.</p>
            
            <div class="nav-links">
                <a href="https://nkhola.github.io/" class="nav-link">← Main Site</a>
                <a href="https://www.khola.blog/" class="nav-link" target="_blank" rel="noopener">Read Khola.Blog ↗</a>
            </div>
        </header>

        <ul class="archive-list">
{links_html}
        </ul>
    </div>
</body>
</html>
"""
    index_file = os.path.join(repo_root, "index.html")
    with open(index_file, "w", encoding="utf-8") as f:
        f.write(index_template)
    print("Updated index.html")

if __name__ == "__main__":
    generate_daily_briefing()