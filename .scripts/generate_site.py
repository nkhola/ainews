#!/usr/bin/env python3
import os
import sys
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

    # Convert to HTML
    ai_html = markdown.markdown(ai_md, extensions=['tables', 'fenced_code'])
    fin_html = markdown.markdown(fin_md, extensions=['tables', 'fenced_code'])

    # 3. Create Daily HTML Page
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Briefing - {date_str} | AI & Finance</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Merriweather:ital,wght@0,300;0,700;1,300;1,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #f9f9f9;
            --surface-color: #ffffff;
            --text-main: #2b2b2b;
            --text-muted: #555555;
            --accent-color: #0056b3;
            --border-color: #e5e5e5;
            --shadow: 0 4px 12px rgba(0,0,0,0.05);
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg-color: #121212;
                --surface-color: #1e1e1e;
                --text-main: #e0e0e0;
                --text-muted: #a0a0a0;
                --accent-color: #58a6ff;
                --border-color: #333333;
                --shadow: 0 4px 12px rgba(0,0,0,0.2);
            }}
        }}
        body.light-theme {{
            --bg-color: #f9f9f9;
            --surface-color: #ffffff;
            --text-main: #2b2b2b;
            --text-muted: #555555;
            --accent-color: #0056b3;
            --border-color: #e5e5e5;
            --shadow: 0 4px 12px rgba(0,0,0,0.05);
        }}
        body.dark-theme {{
            --bg-color: #121212;
            --surface-color: #1e1e1e;
            --text-main: #e0e0e0;
            --text-muted: #a0a0a0;
            --accent-color: #58a6ff;
            --border-color: #333333;
            --shadow: 0 4px 12px rgba(0,0,0,0.2);
        }}
        body {{
            margin: 0;
            padding: 0;
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.6;
            transition: background-color 0.3s ease, color 0.3s ease;
        }}
        .theme-toggle {{
            background: none;
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 6px 12px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: 500;
            float: right;
            transition: all 0.2s ease;
            font-family: 'Inter', sans-serif;
        }}
        .theme-toggle:hover {{
            background: var(--surface-color);
            box-shadow: var(--shadow);
        }}
        .briefing-container {{
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
        }}
        .header-section {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid var(--border-color);
        }}
        .header-section h1 {{
            font-family: 'Merriweather', serif;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 10px;
            color: var(--text-main);
        }}
        .header-section p {{
            color: var(--text-muted);
            font-size: 1.1rem;
        }}
        .section-card {{
            background: var(--surface-color);
            padding: 40px;
            border-radius: 12px;
            box-shadow: var(--shadow);
            margin-bottom: 40px;
            border: 1px solid var(--border-color);
        }}
        .section-card h2 {{
            font-family: 'Merriweather', serif;
            font-size: 1.8rem;
            color: var(--text-main);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 12px;
            margin-top: 0;
            margin-bottom: 24px;
        }}
        .section-card h3 {{
            font-family: 'Merriweather', serif;
            font-size: 1.3rem;
            color: var(--text-main);
            margin-top: 32px;
            margin-bottom: 12px;
        }}
        .section-card p {{
            font-size: 1.1rem;
            margin-bottom: 20px;
        }}
        a {{
            color: var(--accent-color);
            text-decoration: none;
            font-weight: 500;
            transition: color 0.2s ease;
            word-wrap: break-word;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .nav-link {{
            display: inline-block;
            margin-bottom: 30px;
            font-size: 0.95rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        ul {{
            padding-left: 24px;
        }}
        li {{
            margin-bottom: 8px;
        }}
        blockquote {{
            border-left: 4px solid var(--accent-color);
            margin: 0;
            padding: 10px 20px;
            background: rgba(0,0,0,0.03);
            font-style: italic;
        }}
        @media (prefers-color-scheme: dark) {{
            blockquote {{
                background: rgba(255,255,255,0.03);
            }}
        }}
    </style>
</head>
<body>
    <script>
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {{
            document.body.classList.add(savedTheme + '-theme');
        }}
        function toggleTheme() {{
            const body = document.body;
            if (body.classList.contains('dark-theme')) {{
                body.classList.remove('dark-theme');
                body.classList.add('light-theme');
                localStorage.setItem('theme', 'light');
            }} else if (body.classList.contains('light-theme')) {{
                body.classList.remove('light-theme');
                body.classList.add('dark-theme');
                localStorage.setItem('theme', 'dark');
            }} else {{
                if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {{
                    body.classList.add('light-theme');
                    localStorage.setItem('theme', 'light');
                }} else {{
                    body.classList.add('dark-theme');
                    localStorage.setItem('theme', 'dark');
                }}
            }}
        }}
    </script>
    <div class="briefing-container">
        <button class="theme-toggle" onclick="toggleTheme()">🌓 Theme</button>
        <a href="index.html" class="nav-link">← Back to Archive</a>
        
        <div class="header-section">
            <h1>The Daily Briefing</h1>
            <p>{date_str}</p>
        </div>
        
        <div class="section-card" id="ai-news">
            <h2>🧠 Artificial Intelligence</h2>
            {ai_html}
        </div>

        <div class="section-card" id="finance-news">
            <h2>📈 Markets &amp; Macro</h2>
            {fin_html}
        </div>
    </div>
</body>
</html>
"""
    
    # Save daily file in the root
    daily_file = os.path.join(repo_root, f"{base_name}.html")
    with open(daily_file, "w", encoding="utf-8") as f:
        f.write(html_template)
    print(f"Saved daily briefing to {daily_file}")

    # 4. Update Index Page
    update_index_page(repo_root, date_str)

def update_index_page(repo_root, new_date_str):
    # Find all html files in the directory that look like dates
    files = [f for f in os.listdir(repo_root) if f.endswith('.html') and f != 'index.html']
    # Sort files descending (newest first)
    files.sort(reverse=True)

    links_html = ""
    for f in files:
        name_parts = f.replace('.html', '').split('-')
        if len(name_parts) == 4:
            year, month, day, am_pm = name_parts
            label = "Evening" if am_pm == "PM" else "Morning"
            display_name = f"{year}-{month}-{day} &mdash; {label} Briefing"
        else:
            date_name = f.replace('.html', '')
            display_name = f"Briefing for {date_name}"
            
        links_html += f'            <li><a href="{f}">{display_name} <span>Read →</span></a></li>\n'

    index_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Intelligence Briefings</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #f9f9f9;
            --surface-color: #ffffff;
            --text-main: #2b2b2b;
            --text-muted: #555555;
            --accent-color: #0056b3;
            --border-color: #e5e5e5;
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg-color: #121212;
                --surface-color: #1e1e1e;
                --text-main: #e0e0e0;
                --text-muted: #a0a0a0;
                --accent-color: #58a6ff;
                --border-color: #333333;
            }}
        }}
        body.light-theme {{
            --bg-color: #f9f9f9;
            --surface-color: #ffffff;
            --text-main: #2b2b2b;
            --text-muted: #555555;
            --accent-color: #0056b3;
            --border-color: #e5e5e5;
        }}
        body.dark-theme {{
            --bg-color: #121212;
            --surface-color: #1e1e1e;
            --text-main: #e0e0e0;
            --text-muted: #a0a0a0;
            --accent-color: #58a6ff;
            --border-color: #333333;
        }}
        body {{
            margin: 0;
            padding: 0;
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Inter', -apple-system, sans-serif;
            line-height: 1.6;
            transition: background-color 0.3s ease, color 0.3s ease;
        }}
        .theme-toggle {{
            background: none;
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 6px 12px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: 500;
            float: right;
            transition: all 0.2s ease;
            font-family: 'Inter', sans-serif;
        }}
        .theme-toggle:hover {{
            background: var(--surface-color);
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }}
        .archive-container {{
            max-width: 800px;
            margin: 60px auto;
            padding: 20px;
        }}
        h1 {{
            font-family: 'Merriweather', serif;
            font-size: 2.5rem;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 8px;
        }}
        p.subtitle {{
            color: var(--text-muted);
            font-size: 1.1rem;
            margin-bottom: 40px;
        }}
        .archive-list {{
            list-style-type: none;
            padding: 0;
        }}
        .archive-list li {{
            margin-bottom: 16px;
        }}
        .archive-list a {{
            text-decoration: none;
            font-size: 1.2rem;
            font-weight: 500;
            display: flex;
            align-items: center;
            padding: 16px 20px;
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-main);
            transition: all 0.2s ease;
        }}
        .archive-list a:hover {{
            border-color: var(--accent-color);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }}
        .archive-list a span {{
            color: var(--accent-color);
            font-size: 0.95rem;
            margin-left: auto;
            font-weight: 600;
        }}
        .back-link {{
            display: inline-block;
            margin-bottom: 20px;
            color: var(--accent-color);
            font-weight: 600;
            text-decoration: none;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-size: 0.9rem;
        }}
        .back-link:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <script>
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {{
            document.body.classList.add(savedTheme + '-theme');
        }}
        function toggleTheme() {{
            const body = document.body;
            if (body.classList.contains('dark-theme')) {{
                body.classList.remove('dark-theme');
                body.classList.add('light-theme');
                localStorage.setItem('theme', 'light');
            }} else if (body.classList.contains('light-theme')) {{
                body.classList.remove('light-theme');
                body.classList.add('dark-theme');
                localStorage.setItem('theme', 'dark');
            }} else {{
                if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {{
                    body.classList.add('light-theme');
                    localStorage.setItem('theme', 'light');
                }} else {{
                    body.classList.add('dark-theme');
                    localStorage.setItem('theme', 'dark');
                }}
            }}
        }}
    </script>
    <div class="archive-container">
        <button class="theme-toggle" onclick="toggleTheme()">🌓 Theme</button>
        <a href="https://nkhola.github.io/" class="back-link">← Back to Main Site</a>
        <h1>Intelligence Briefings</h1>
        <p class="subtitle">A daily automated synthesis of the top AI and Finance news.</p>
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