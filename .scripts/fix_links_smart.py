import os
import re
import glob

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # 1. Update Title
    content = content.replace('<h1>The Daily Briefing</h1>', '<h1>The Post-Human Brief</h1>')

    # 2. Handle Citation format (e.g. [1] <a href="...">Title</a>)
    # Find the References section at the bottom if it exists
    ref_match = re.search(r'<hr />\s*<p><strong>References:</strong>(.*?)</p>', content, re.DOTALL)
    if ref_match:
        refs_text = ref_match.group(1)
        # Parse all [id] <a href="...">Title</a>
        citations = {}
        for line in refs_text.strip().split('\n'):
            line = line.strip()
            if not line: continue
            m = re.match(r'\[(\d+)\]\s*(<a href="[^"]+">.*?</a>)', line)
            if m:
                citations[m.group(1)] = m.group(2)
        
        # Replace inline [id] with the actual link
        for cid, tag in citations.items():
            content = re.sub(rf'\[{cid}\]', tag, content)
        
        # Remove the References section
        content = content.replace(ref_match.group(0), '')

    # 3. Handle inline raw URLs [http...]
    # We want to match: (some words) [http...]
    # Let's match up to 6 words before the bracket, stopping at punctuation like . ; :
    # We will use a regex replacement function
    def replacer(match):
        preceding_text = match.group(1)
        urls_text = match.group(2)
        
        # Extract URLs
        urls = [u.strip() for u in urls_text.split(',') if u.strip().startswith('http')]
        if not urls:
            return match.group(0) # no valid URL
        
        # We wrap the preceding_text with the FIRST URL
        main_url = urls[0]
        
        # If there are more URLs, we can append them as [2], [3] but that's messy.
        # Let's just use the first URL to wrap the preceding text.
        res = f'<a href="{main_url}">{preceding_text}</a>'
        
        # If multiple URLs, we can add them as small asterisks or just ignore for aesthetics, 
        # but let's just make it a single link for the preceding text.
        return res

    # Regex: capture preceding words (letters, numbers, spaces, maybe hyphens) up to 80 chars
    # We don't want to capture across sentences. So we stop at > or . or ! or ?
    # Let's just match the last 3-7 words.
    # ([^>.\?!]{5,60}?)\s*\[(https?://[^\]]+)\]
    
    # We need to be careful not to capture HTML tags in the preceding text if possible, 
    # but it's okay if we wrap a <strong>.
    # Let's find: a sequence of non-URL, non-bracket characters ending just before [http
    content = re.sub(r'([^>.\?!\[\]]{5,80}?)\s*\[(https?://[^\]]+)\]', replacer, content)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed {filepath}")

for f in glob.glob('*.html'):
    if f != 'index.html':
        fix_file(f)
