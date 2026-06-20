import os
import re
import sys
import time
import json
import openai
from bs4 import BeautifulSoup

# Initialize client using environment variables
API_KEY = os.getenv("LLM_API_KEY", "")
if not API_KEY:
    print("Error: LLM_API_KEY environment variable is not set. Please set it before running this script.")
    sys.exit(1)

BASE_URL = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
MODEL = "gemini-2.5-flash-lite"

print(f"Using model: {MODEL}")
print(f"Using base URL: {BASE_URL}")

client = openai.OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

# Search results context for error-corrupted sections
JUNE_11_FINANCE_CONTEXT = """
Market Summary (June 11, 2026):
- U.S. Markets: U.S. stocks experienced a significant rally, marking their best day in two months. This occurred after President Donald Trump called off a threat to bomb Iran, which eased investor concerns.
- Commodities: Oil prices fell as investors monitored the U.S.-Iran conflict. West Texas Intermediate (WTI) crude slipped 0.87% to $89.25 a barrel, and Brent crude declined 1.13% to $92.05. Gold fell 0.51% to $4,112.10 per ounce and silver fell 0.96% to $64.12.
- Economic Policy & Regulation: The European Central Bank (ECB) raised its three key interest rates by 25 basis points, citing inflationary pressures stemming from the war in the Middle East.
- SEC Rule Proposals: The SEC proposed rescinding Regulation NMS Rules 610(e) and 611 (the order protection / trade-through rule), which is one of the most significant potential changes to U.S. equity market structure in two decades.
- Economic Data: Wholesale inflation was strong, with the PPI rising 1.1% in May and 6.5% year-over-year. Jobless claims were 229,000.
- Corporate News: Schwab implemented fee reductions across several managed funds. Broadcom announced cash tender offers for outstanding debt.
"""

JUNE_17_AI_CONTEXT = """
AI Industry News (June 17, 2026):
- SpaceX Acquires Cursor: SpaceX announced a $60 billion all-stock acquisition of Anysphere (developer of Cursor), the largest AI acquisition of the year. This followed SpaceX's recent IPO, positioning it as one of the most valuable companies in the U.S.
- HSBC and Google Cloud: A multi-year partnership to integrate advanced AI across HSBC's global operations, focusing on hyper-personalized wealth management, financial crime risk management, using Gemini and agentic AI.
- Southwest Airlines & AWS: Southwest partnering with AWS to move to an AI-enabled, cloud-based architecture by 2028.
- G7 Summit Discussions: AI governance took center stage at G7 Summit in France. Leaders held a lunch meeting with AI figures (Sam Altman, Dario Amodei, Demis Hassabis) to discuss AI weaponization.
- Anthropic Export Restrictions: Trump administration ordered Anthropic to restrict access to its most powerful models for non-U.S. citizens, straining international alliances and sparking European discussions on tech sovereignty.
- OpenAI Financials: Audited 2025 financials revealed OpenAI spent $34B and made $13B revenue, resulting in a net loss of $38.5B.
- Fable 5 Status: Fable 5 model remained offline amid pressure and CEO concerns, leading to high-level meetings in Washington.
"""

def generate_from_scratch(context, topic, date_str):
    print(f"Generating section {topic} for {date_str} from scratch...")
    prompt = f"""You are a "Master Compiler" writing a private daily briefing. 
Topic: {topic}
Date: {date_str}

Use the following raw news context:
{context}

INSTRUCTIONS:
1. Generate the briefing section in clean HTML. Do NOT include <html> or <body> tags. Start directly with the content.
2. Use standard HTML tags: <h3> for headings, <p> for paragraphs, and <a> for inline links.
3. Organize into a cohesive flow:
   - Start with a paragraph summarizing the main theme.
   - Use 3 distinct themes, each starting with a <h3> header followed by 1-2 detailed paragraphs.
   - Weave in descriptive hyperlinks based on the context. If you use a URL, make it descriptive (e.g. <a href="https://ft.com/...">SpaceX's Cursor acquisition</a>).
   - End with a single-sentence "Bottom Line" paragraph: <p><strong>The Bottom Line:</strong> [Summary sentence]</p>.
4. Authoritative, human expert tone. No AI clichés ("delve", "tapestry", "landscape", etc.).
5. Return ONLY the HTML content. No markdown code block backticks (like ```html), no preamble, no commentary."""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        content = response.choices[0].message.content.strip()
        content = content.removeprefix("```html").removesuffix("```").strip()
        return content
    except Exception as e:
        print(f"API Error in generate_from_scratch: {e}")
        return None

def parse_json_response(content):
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-zA-Z0-9]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
    content = content.strip()
    try:
        return json.loads(content)
    except Exception as e:
        print(f"Error parsing JSON content: {e}. Raw content: {content}")
        # Manual fallback parsing
        completion = ""
        bottom_line = ""
        comp_match = re.search(r'"completion":\s*"(.*?)"', content, re.DOTALL)
        if comp_match:
            completion = comp_match.group(1)
        bl_match = re.search(r'"bottom_line":\s*"(.*?)"', content, re.DOTALL)
        if bl_match:
            bottom_line = bl_match.group(1)
        return {"completion": completion, "bottom_line": bottom_line}

def get_paragraph_completion(paragraph_text, topic):
    print(f"Generating completion for paragraph in {topic}...")
    prompt = f"""You are a professional daily briefing editor. I will provide you with the last paragraph of a daily briefing section (topic: {topic}).
The paragraph might be truncated (cut off mid-sentence) at the very end.

Input Paragraph:
"{paragraph_text}"

INSTRUCTIONS:
1. Determine if the input paragraph is truncated mid-sentence.
   - If it is truncated (e.g., ends without a period or with unfinished words/brackets like "[LLMs for medical"), write the natural completion to finish the sentence and paragraph. Do NOT repeat any part of the input paragraph. Maintain the exact same style, vocabulary, and tone. Ensure all brackets, parentheses, and quotes are properly balanced and closed.
   - If it is NOT truncated, set the completion to an empty string.
2. Generate a single-sentence "Bottom Line" summary for this paragraph/section. It must start with "The Bottom Line: " and be authoritative and professional.

Return your response as a JSON object with the following keys:
- "completion": (string) the completion text (or empty string if not truncated).
- "bottom_line": (string) the "The Bottom Line: [summary sentence]" text.

Return ONLY the raw JSON object. Do NOT wrap it in markdown code blocks.
"""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        content = response.choices[0].message.content.strip()
        return parse_json_response(content)
    except Exception as e:
        print(f"API Error in get_paragraph_completion: {e}")
        return {"completion": "", "bottom_line": ""}

def process_file(filepath):
    print(f"\nProcessing {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        html_data = f.read()
    
    soup = BeautifulSoup(html_data, 'html.parser')
    changed = False
    
    filename = os.path.basename(filepath)
    date_str = filename.replace('.html', '')
    
    for section_id in ['ai-news', 'finance-news']:
        section = soup.find('div', id=section_id)
        if not section:
            continue
            
        h2 = section.find('h2')
        if not h2:
            continue
            
        # Get the inner HTML content after H2
        siblings = list(h2.find_next_siblings())
        if not siblings:
            continue
            
        # Check if we should regenerate from scratch or fix truncation
        first_sibling_text = siblings[0].get_text()
        is_error = "Error during LLM" in first_sibling_text or "unavailable due to a temporary" in first_sibling_text
        
        if is_error:
            new_inner = None
            if date_str.startswith("2026-06-11") and section_id == "finance-news":
                new_inner = generate_from_scratch(JUNE_11_FINANCE_CONTEXT, "Markets & Macro", date_str)
            elif date_str.startswith("2026-06-17") and section_id == "ai-news":
                new_inner = generate_from_scratch(JUNE_17_AI_CONTEXT, "Artificial Intelligence", date_str)
            
            if new_inner:
                # Remove old siblings
                for sibling in h2.find_next_siblings():
                    sibling.extract()
                
                # Parse and append new content
                new_soup = BeautifulSoup(new_inner, 'html.parser')
                for elem in new_soup:
                    section.append(elem)
                changed = True
                print(f"Regenerated {section_id} from scratch for {date_str}")
                # Wait to prevent hitting rate limits (5 RPM limit = sleep 13s)
                time.sleep(13)
        else:
            # Check if this section needs a Bottom Line
            has_bottom_line = any("Bottom Line" in s.get_text() for s in siblings)
            if not has_bottom_line:
                print(f"Section {section_id} is missing a Bottom Line. Let's complete it.")
                
                # Get the last paragraph
                last_p = None
                for s in reversed(siblings):
                    if s.name == 'p':
                        last_p = s
                        break
                
                if last_p:
                    p_html = last_p.decode_contents()
                    # Strip manually added endings to restore original truncation if possible
                    p_html = re.sub(r'[,.]\s*(balancing the short-term|as the rupiah slumps|indicating some shifts|which could help temper|to buy US goods).*$', '', p_html)
                    p_html = re.sub(r'\s*([a-zA-Z\s]+ is becoming a primary focus).*$', '', p_html)
                    
                    # Generate the completion
                    res = get_paragraph_completion(p_html, "AI" if section_id == "ai-news" else "Finance")
                    
                    completion_text = res.get("completion", "").strip()
                    bottom_line_text = res.get("bottom_line", "").strip()
                    
                    # Apply completion if present
                    if completion_text:
                        # Ensure there's a space if completion starts with an alphanumeric character
                        if completion_text[0].isalnum() and not p_html.endswith(" "):
                            completion_text = " " + completion_text
                        
                        # Ensure all brackets/parentheses are balanced
                        combined = p_html + completion_text
                        if combined.count("[") > combined.count("]"):
                            completion_text += "]"
                        if combined.count("(") > combined.count(")"):
                            completion_text += ")"
                        
                        print(f"Applying completion: {repr(completion_text)}")
                        # Clear last paragraph to restore the stripped HTML and append the completion
                        last_p.clear()
                        # Parse original HTML and append it
                        orig_soup = BeautifulSoup(p_html, 'html.parser')
                        for child in list(orig_soup.children):
                            last_p.append(child)
                        # Parse completion and append it
                        comp_soup = BeautifulSoup(completion_text, 'html.parser')
                        for child in list(comp_soup.children):
                            last_p.append(child)
                    else:
                        print("No completion text returned (already complete paragraph).")
                    
                    # Append Bottom Line paragraph
                    if bottom_line_text:
                        print(f"Appending Bottom Line: {repr(bottom_line_text)}")
                        # Create new <p> tag for Bottom Line
                        # Make sure it starts with strong
                        clean_bl = bottom_line_text.replace("**", "").strip()
                        if clean_bl.lower().startswith("the bottom line:"):
                            clean_bl = re.sub(r'^[Tt]he\s+[Bb]ottom\s+[Ll]ine:\s*', '<strong>The Bottom Line:</strong> ', clean_bl)
                        elif clean_bl.startswith("<strong>The Bottom Line:</strong>"):
                            pass
                        else:
                            clean_bl = f"<strong>The Bottom Line:</strong> {clean_bl}"
                        
                        bl_soup = BeautifulSoup(f"<p>{clean_bl}</p>", 'html.parser')
                        last_p.insert_after(bl_soup.find())
                    
                    changed = True
                    # Wait to prevent hitting rate limits (5 RPM limit = sleep 13s)
                    time.sleep(13)
            else:
                print(f"Section {section_id} already has a Bottom Line.")
            
    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(str(soup))
        print(f"Saved changes to {filepath}")

def main():
    target_files = [
        "2026-06-11-AM.html",
        "2026-06-11-PM.html",
        "2026-06-15-PM.html",
        "2026-06-16-PM.html",
        "2026-06-17-AM.html",
        "2026-06-17-PM.html",
        "2026-06-18-AM.html",
        "2026-06-18-PM.html",
        "2026-06-19-PM.html"
    ]
    
    for f in target_files:
        filepath = os.path.join("/Users/nitinkhola/github_website/ainews", f)
        if os.path.exists(filepath):
            try:
                process_file(filepath)
            except Exception as e:
                print(f"Error processing {f}: {e}")
        else:
            print(f"File not found: {filepath}")

if __name__ == "__main__":
    main()
