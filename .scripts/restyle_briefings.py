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

from generate_site import (
    list_content_editions,
    render_content_edition,
    rerender_archive_page,
)


def restyle_all():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)

    files = sorted(
        f for f in os.listdir(repo_root)
        if f.endswith('.html') and f != 'index.html' and re.match(r'^\d{4}-\d{2}-\d{2}', f)
    )
    editions = list_content_editions(repo_root)
    newest = editions[-1] if editions else None

    failed = []
    for filename in files:
        base_name = filename[:-5]
        # Content-store editions re-render from markdown (lossless);
        # older pages re-render from their own markup.
        if base_name in editions:
            ok = render_content_edition(repo_root, base_name, newest)
        else:
            ok = rerender_archive_page(repo_root, filename)
        if ok:
            print(f"OK   {filename}")
        else:
            failed.append(filename)
            print(f"SKIP {filename}: no extractable content")

    print(f"\nRestyled {len(files) - len(failed)}/{len(files)} briefings.")
    if failed:
        print(f"Left untouched: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    restyle_all()
