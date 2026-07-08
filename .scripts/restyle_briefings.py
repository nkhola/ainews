#!/usr/bin/env python3
"""Re-render every existing daily briefing with the current page template.

Extracts the article content (AI + Markets sections) and reading time from
each published briefing, then rewrites the file using
generate_site.render_briefing_page. Run whenever the template changes so the
whole archive stays visually consistent.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bs4 import BeautifulSoup

from generate_site import render_briefing_page, build_recent_html


def extract_section_inner(soup, div_id):
    """Inner HTML of a briefing section, minus its heading chrome."""
    div = soup.find(id=div_id)
    if div is None:
        return None
    for chrome in div.find_all(class_=("section-header", "section-head")):
        chrome.decompose()
    inner = div.decode_contents().strip()
    return inner or None


def restyle_all():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)

    files = sorted(
        f for f in os.listdir(repo_root)
        if f.endswith('.html') and f != 'index.html' and re.match(r'^\d{4}-\d{2}-\d{2}', f)
    )

    failed = []
    for filename in files:
        path = os.path.join(repo_root, filename)
        with open(path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        ai_html = extract_section_inner(soup, "ai-news")
        fin_html = extract_section_inner(soup, "finance-news")
        if not ai_html and not fin_html:
            failed.append(filename)
            print(f"SKIP {filename}: no extractable content")
            continue

        base_name = filename.replace('.html', '')
        parts = base_name.split('-')
        date_str = "-".join(parts[:3])
        time_label = ("Evening" if parts[3] == "PM" else "Morning") if len(parts) == 4 else "Daily"

        m = re.search(r'(\d+)\s*min read', soup.get_text())
        if m:
            reading_time = int(m.group(1))
        else:
            words = len(soup.get_text().split())
            reading_time = max(1, words // 200)

        has_audio = os.path.exists(os.path.join(repo_root, "audio", f"{base_name}.mp3"))

        page = render_briefing_page(
            base_name=base_name,
            date_str=date_str,
            time_label=time_label,
            reading_time=reading_time,
            ai_html=ai_html or "",
            fin_html=fin_html or "",
            recent_html=build_recent_html(repo_root, exclude=filename),
            has_audio=has_audio,
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)
        print(f"OK   {filename} ({time_label}, {reading_time} min, audio={has_audio})")

    print(f"\nRestyled {len(files) - len(failed)}/{len(files)} briefings.")
    if failed:
        print(f"Left untouched: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    restyle_all()
