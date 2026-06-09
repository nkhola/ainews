#!/usr/bin/env python3
import os
import sys
from datetime import datetime
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

    date_str = datetime.now().strftime('%Y-%m-%d')
    print(f"Generating briefings for {date_str}...")

    compiler = MasterCompiler()

    # 1. Fetch & Compile AI News
    print("Fetching AI News...")
    ai_crawler = NewsCrawler()
    ai_raw = ai_crawler.get_latest_news()
    ai_md = compiler.synthesize_news(ai_raw, topic="ai")

    # 2. Fetch & Compile Finance News
    print("Fetching Finance News...")
    fin_crawler = FinanceCrawler()
    fin_raw = fin_crawler.get_latest_news()
    fin_md = compiler.synthesize_news(fin_raw, topic="finance")

    # Convert to HTML
    ai_html = markdown.markdown(ai_md, extensions=['tables', 'fenced_code'])
    fin_html = markdown.markdown(fin_md, extensions=['tables', 'fenced_code'])

    # 3. Create Daily HTML Page
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Briefing - {date_str} | AI News</title>
    <!-- Use the main website's stylesheet -->
    <link rel="stylesheet" href="https://nkhola.github.io/styles.css">
    <style>
        .briefing-container {{ max-width: 800px; margin: 40px auto; padding: 20px; }}
        .section-card {{ background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 40px; }}
        @media (prefers-color-scheme: dark) {{
            .section-card {{ background: #1a1a1a; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border: 1px solid #333; }}
        }}
        h1, h2, h3 {{ border-bottom: 1px solid #eee; padding-bottom: 10px; margin-top: 30px; }}
        @media (prefers-color-scheme: dark) {{ h1, h2, h3 {{ border-bottom: 1px solid #333; }} }}
        .nav-link {{ display: inline-block; margin-bottom: 20px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="briefing-container">
        <a href="index.html" class="nav-link">← Back to Archive</a>
        
        <h1>Briefing for {date_str}</h1>
        
        <div class="section-card" id="ai-news">
            <h2>🧠 AI News</h2>
            {ai_html}
        </div>

        <div class="section-card" id="finance-news">
            <h2>📈 Finance News</h2>
            {fin_html}
        </div>
    </div>
</body>
</html>
"""
    # Setup directories
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Save daily file in the root
    daily_file = os.path.join(repo_root, f"{date_str}.html")
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
        date_name = f.replace('.html', '')
        links_html += f'            <li><a href="{f}">{date_name} - AI & Finance Briefing</a></li>\n'

    index_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI & Finance Briefings Archive</title>
    <!-- Use the main website's stylesheet -->
    <link rel="stylesheet" href="https://nkhola.github.io/styles.css">
    <style>
        .archive-container {{ max-width: 800px; margin: 40px auto; padding: 20px; }}
        .archive-list {{ list-style-type: none; padding: 0; }}
        .archive-list li {{ margin-bottom: 10px; padding: 15px; background: rgba(0,0,0,0.02); border-radius: 6px; }}
        @media (prefers-color-scheme: dark) {{ .archive-list li {{ background: rgba(255,255,255,0.05); }} }}
        .archive-list a {{ text-decoration: none; font-size: 18px; font-weight: 500; display: block; }}
        .archive-list a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="archive-container">
        <a href="https://nkhola.github.io/" style="font-weight: bold;">← Back to Main Site</a>
        <h1>AI & Finance Briefings</h1>
        <p>A daily automated synthesis of the top AI and Finance news.</p>
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
