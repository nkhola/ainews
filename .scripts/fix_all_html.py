import os
import re
import glob

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Post-Human Brief - {date_str}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;700;800&family=Merriweather:ital,wght@0,300;0,700;1,300;1,700&display=swap" rel="stylesheet">
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
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid var(--border-color);
        }}
        .header-section .logo {{
            width: 80px;
            border-radius: 50%;
            margin-bottom: 16px;
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.4);
        }}
        .header-section h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 3rem;
            font-weight: 800;
            margin: 0 0 10px 0;
            background: linear-gradient(to right, #60a5fa, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -1px;
        }}
        .header-section .meta {{
            color: var(--text-muted);
            font-size: 1.1rem;
            font-family: 'Outfit', sans-serif;
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
        .section-card h2 {{
            font-family: 'Merriweather', serif;
            font-size: 1.8rem;
            color: #60a5fa;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 12px;
            margin-top: 0;
            margin-bottom: 24px;
        }}
        .section-card h3 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.3rem;
            color: var(--text-main);
            margin-top: 32px;
            margin-bottom: 12px;
            font-weight: 700;
        }}
        .section-card p {{
            font-size: 1.1rem;
            margin-bottom: 20px;
            color: #d1d5db;
        }}
        .section-card ul {{
            padding-left: 24px;
            color: #d1d5db;
        }}
        .section-card li {{
            margin-bottom: 10px;
            font-size: 1.05rem;
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
            <img src="img/logo_256.png" alt="Logo" class="logo">
            <h1>The Post-Human Brief</h1>
            <div class="meta">{date_str} &bull; {time_label} &bull; {reading_time} min read</div>
        </div>
        
        <div class="section-card" id="ai-news">
            <h2>🧠 Artificial Intelligence</h2>
            {ai_html}
        </div>

        <div class="section-card" id="finance-news">
            <h2>📈 Markets &amp; Macro</h2>
            {fin_html}
        </div>

        <div class="recent-briefings">
            <h3>Recent Briefings</h3>
            <div class="recent-list">
{recent_briefings_html}
            </div>
        </div>
    </div>
</body>
</html>
"""

def get_sort_key(filename):
    name = os.path.basename(filename).replace('.html', '')
    parts = name.split('-')
    if len(parts) == 4:
        date_str = "-".join(parts[:3])
        suffix = parts[3]
        weight = 1 if suffix == "PM" else 0
    else:
        date_str = name
        weight = 0
    return (date_str, weight)

def main():
    root = "/Users/nitinkhola/github_website/ainews"
    html_files = [f for f in glob.glob(os.path.join(root, "*.html")) if not f.endswith("index.html")]
    html_files.sort(key=get_sort_key, reverse=True)
    
    # Pre-generate recent list mapping
    # For any given file, recent briefings is the top 3 files excluding the file itself
    
    for filepath in html_files:
        filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Extract meta data (date, time, readtime)
        meta_match = re.search(r'<div class="meta">(.*?)</div>', content)
        meta_text = meta_match.group(1) if meta_match else ""
        meta_parts = meta_text.split('&bull;')
        if len(meta_parts) >= 3:
            date_str = meta_parts[0].strip()
            time_label = meta_parts[1].strip()
            reading_time = meta_parts[2].strip().replace("min read", "").strip()
        else:
            # Fallback based on filename
            name_parts = filename.replace('.html', '').split('-')
            if len(name_parts) == 4:
                date_str = f"{name_parts[0]}-{name_parts[1]}-{name_parts[2]}"
                time_label = "Evening" if name_parts[3] == "PM" else "Morning"
            else:
                date_str = filename.replace('.html', '')
                time_label = ""
            reading_time = "5"
            
        # Extract AI html
        ai_match = re.search(r'<h2>.*?Artificial Intelligence.*?</h2>(.*?)</div>\s*<div class="section-card" id="finance-news">', content, re.DOTALL)
        if ai_match:
            ai_html = ai_match.group(1).strip()
        else:
            ai_html = ""
            
        # Extract Finance html
        fin_match = re.search(r'<h2>.*?Markets &amp; Macro.*?</h2>(.*?)</div>\s*(?:<div class="recent-briefings"|</div>\s*</body>)', content, re.DOTALL)
        if fin_match:
            fin_html = fin_match.group(1).strip()
        else:
            fin_html = ""
            
        # Generate recent briefings HTML
        recent_html = ""
        count = 0
        for rf in html_files:
            if rf == filepath:
                continue
            if count >= 3:
                break
            
            rf_name = os.path.basename(rf).replace('.html', '')
            rf_parts = rf_name.split('-')
            if len(rf_parts) == 4:
                display_name = f"{rf_parts[0]}-{rf_parts[1]}-{rf_parts[2]} {'Evening' if rf_parts[3] == 'PM' else 'Morning'} Briefing"
            else:
                display_name = rf_name + " Briefing"
                
            recent_html += f'                <a href="{os.path.basename(rf)}"><span>{display_name}</span> <span class="date">Read →</span></a>\n'
            count += 1
            
        new_html = TEMPLATE.format(
            date_str=date_str,
            time_label=time_label,
            reading_time=reading_time,
            ai_html=ai_html,
            fin_html=fin_html,
            recent_briefings_html=recent_html
        )
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_html)
            
    print("All HTML files updated.")

if __name__ == "__main__":
    main()
