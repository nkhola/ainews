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

# Style instructions for Gemini-TTS. These go in SynthesisInput.prompt (a
# dedicated field that is never spoken), NOT prepended to the text — inline
# instructions get read aloud by the model.
# Deliberately flat delivery: chunks are synthesized independently, and a
# neutral, even register is what keeps consecutive chunks indistinguishable.
TTS_STYLE_PROMPT = (
    "Read the text verbatim in the even, measured, neutral tone of a "
    "public-radio news reader. Calm and steady, no dramatics, no enthusiasm "
    "swings: keep exactly the same pace, pitch, and energy from the first "
    "word to the last. Read only the text: add nothing, repeat nothing, "
    "skip nothing, and never speak these instructions."
)

# Gemini-TTS prebuilt voices for the daily narration, in order of
# preference. Charon is the flattest "informative newsreader" of the
# prebuilt voices (Puck, the original choice, is characterized as upbeat,
# which amplified tone drift between chunks) and also anchors the weekly
# Debrief. If a voice's backend is down (observed: repeated 502s on Charon
# while Puck worked minutes earlier), the whole file is resynthesized with
# the next voice rather than silently degrading to a non-Gemini engine.
TTS_VOICE_PREFERENCES = [
    os.environ.get("TTS_VOICE") or "Charon",
    "Schedar",   # characterized as "even" — closest neutral substitute
]

# Gemini-TTS accepts up to 4,000 bytes in the text field. Larger chunks mean
# fewer synthesis seams (each seam risks a tone shift), so pack close to the
# limit while leaving headroom for multi-byte characters.
TTS_MAX_CHUNK_BYTES = 3200


def html_to_speech_text(html_content):
    """Flatten briefing HTML into narration-friendly plain text.

    Block elements (headings, paragraphs, list items) become sentences —
    otherwise a heading runs straight into the following paragraph with no
    pause, which sounds robotic. HTML entities are decoded so the voice
    doesn't read '&amp;' style artifacts.
    """
    import html as html_lib
    blocks = re.sub(r'</(h[1-6]|p|li|blockquote|td|th|tr)>', '\n', html_content, flags=re.I)
    text = re.sub(r'<[^>]+>', ' ', blocks)
    text = html_lib.unescape(text)
    lines = []
    for line in text.split('\n'):
        line = re.sub(r'\s+', ' ', line).strip()
        if not line:
            continue
        if line[-1] not in '.!?:;':
            line += '.'
        lines.append(line)
    return ' '.join(lines)


def split_text_for_tts(plain_text, max_bytes=TTS_MAX_CHUNK_BYTES):
    """Split text into chunks on sentence boundaries, each under max_bytes.

    Splitting mid-sentence forces the model to invent intonation for a
    fragment, which is the main cause of rhythm shifts between chunks.
    """
    sentences = re.split(r'(?<=[.!?])\s+', plain_text)
    chunks = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate.encode("utf-8")) > max_bytes:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
        # A single sentence longer than max_bytes (rare) still has to be cut.
        while len(current.encode("utf-8")) > max_bytes:
            cut = current[:max_bytes]
            space = cut.rfind(" ")
            if space <= 0:
                space = max_bytes
            chunks.append(current[:space])
            current = current[space:].strip()
    if current:
        chunks.append(current)
    return chunks


def build_audio_script(briefing_text, date_str, time_label, compiler=None,
                       fallback_text=None):
    """Produce the narration text for a briefing.

    Primary path: the LLM rewrites the briefing as an audio-native script
    (welcome, spoken transitions, sign-off). If that fails or comes back
    suspiciously short/garbled, fall back to the flattened briefing text so
    audio generation never blocks publication.
    """
    fallback = fallback_text if fallback_text is not None else briefing_text
    try:
        if compiler is None:
            from src.agents.master_compiler import MasterCompiler as _MC
            compiler = _MC()
        date_line = pretty_date(date_str)
        script = compiler.synthesize_audio_script(briefing_text, date_line, time_label)
        if not isinstance(script, str):
            raise ValueError("audio script is not text")
        script = re.sub(r'[#*_`>\[\]]', '', script)   # strip stray markdown
        script = re.sub(r'\s+', ' ', script).strip()
        source_words = len(str(briefing_text).split())
        if len(script.split()) < max(150, source_words // 3):
            raise ValueError(
                f"audio script too short ({len(script.split())} words "
                f"vs {source_words} source words)")
        return script
    except Exception as e:
        print(f"Audio script generation failed ({e}); using flattened briefing text.")
        return re.sub(r'\s+', ' ', str(fallback)).strip()


def _synthesize_with_voice(client, texttospeech, chunks, voice_name):
    """Synthesize all chunks with one Gemini voice; raises on failure.

    A failure mid-file restarts with the next voice at the caller, never
    mixing voices within one briefing.
    """
    import time

    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name=voice_name,
        model_name="gemini-2.5-flash-tts"
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    full_audio_content = b""
    for idx, chunk in enumerate(chunks):
        print(f"  [{voice_name}] Synthesizing chunk {idx+1}/{len(chunks)}...")
        synthesis_input = texttospeech.SynthesisInput(
            text=chunk,
            prompt=TTS_STYLE_PROMPT,
        )
        # Retry transient failures (502s) instead of shrinking chunks —
        # small chunks are what caused the uneven pacing.
        last_error = None
        for attempt in range(4):
            try:
                response = client.synthesize_speech(
                    input=synthesis_input, voice=voice, audio_config=audio_config
                )
                full_audio_content += response.audio_content
                last_error = None
                break
            except Exception as e:
                last_error = e
                print(f"    Chunk {idx+1} attempt {attempt+1} failed: {e}")
                time.sleep(5 * (attempt + 1))
        if last_error is not None:
            raise last_error
    return full_audio_content


def generate_audio_with_fallback(plain_text, audio_file_path):
    """Synthesize narration with Gemini-TTS, trying each preferred voice.

    Deliberately does NOT fall back to a non-Gemini engine by default: a
    silently-published robotic voice is worse for the product than a loud
    failure, and with the staged pipeline a narrate re-run is nearly free
    (the audio script is persisted). Set EDGE_TTS_FALLBACK=1 to allow the
    old edge-tts fallback as a last resort.
    """
    from google.cloud import texttospeech

    location = os.environ.get("VERTEX_LOCATION", "us-central1") or "us-central1"
    endpoint = f"{location}-texttospeech.googleapis.com"
    client = texttospeech.TextToSpeechClient(
        client_options={"api_endpoint": endpoint}
    )

    chunks = split_text_for_tts(plain_text)
    last_error = None
    for voice_name in TTS_VOICE_PREFERENCES:
        print(f"Attempting Vertex AI TTS (Gemini {voice_name} voice) for {audio_file_path}...")
        try:
            audio = _synthesize_with_voice(client, texttospeech, chunks, voice_name)
            with open(audio_file_path, "wb") as out:
                out.write(audio)
            print(f"Vertex AI TTS successful ({voice_name}).")
            return
        except Exception as e:
            last_error = e
            print(f"Vertex AI TTS with {voice_name} failed: {e}")

    if os.environ.get("EDGE_TTS_FALLBACK") == "1":
        print("All Gemini voices failed. EDGE_TTS_FALLBACK=1, using edge-tts...")
        subprocess.run([
            "edge-tts",
            "--text", plain_text,
            "--write-media", audio_file_path,
            "--voice", "en-US-ChristopherNeural"
        ], check=True)
        print("edge-tts fallback successful.")
        return

    raise RuntimeError(
        f"Gemini-TTS failed for all voices {TTS_VOICE_PREFERENCES}: {last_error}. "
        f"Re-run the narrate stage (the audio script is persisted, so a retry "
        f"costs no LLM tokens), or set EDGE_TTS_FALLBACK=1 to accept a "
        f"non-Gemini voice.")


# ---------------------------------------------------------------------------
# Design system — "editorial modernism" derived from the cubist logo.
# Paper cream / ink navy surfaces, terracotta accent, ochre secondary.
# Fraunces (serif display) + Inter (body) + JetBrains Mono (data).
# Everything is static and self-contained: GitHub Pages friendly.
# ---------------------------------------------------------------------------

SITE_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400..700;1,9..144,400..700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'
)

# Runs before first paint so there is no theme flash.
THEME_BOOT = (
    "<script>(function(){var t=null;try{t=localStorage.getItem('phb-theme')}catch(e){}"
    "if(t!=='dark'&&t!=='light'){t=(window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light'}"
    "document.documentElement.setAttribute('data-theme',t);})();</script>"
)

THEME_TOGGLE_JS = (
    "<script>function phbToggleTheme(){var r=document.documentElement;"
    "var t=r.getAttribute('data-theme')==='dark'?'light':'dark';"
    "r.setAttribute('data-theme',t);try{localStorage.setItem('phb-theme',t)}catch(e){}}</script>"
)

THEME_TOGGLE_BTN = (
    '<button class="theme-toggle" onclick="phbToggleTheme()" aria-label="Toggle color theme" title="Toggle theme">'
    '<svg class="icon-sun" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path></svg>'
    '<svg class="icon-moon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>'
    '</button>'
)

# Plain string (not an f-string) so CSS braces stay literal.
BASE_CSS = """
        :root {
            --bg: #f4eee1;
            --surface: #faf6ea;
            --surface-2: #ece4d1;
            --ink: #20242e;
            --ink-soft: #494e5c;
            --muted: #78715f;
            --accent: #b0512b;
            --accent-hover: #8f3f1e;
            --ochre: #a5762a;
            --teal: #3d6a78;
            --hairline: #ddd3bd;
            --rule: #20242e;
            --font-serif: 'Fraunces', Georgia, serif;
            --font-sans: 'Inter', -apple-system, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }
        [data-theme="dark"] {
            --bg: #14161d;
            --surface: #1a1d26;
            --surface-2: #232733;
            --ink: #eae5d6;
            --ink-soft: #c2bcab;
            --muted: #8f8a79;
            --accent: #d97950;
            --accent-hover: #e89570;
            --ochre: #cf9c45;
            --teal: #7aa7b5;
            --hairline: #2d3140;
            --rule: #eae5d6;
        }

        * { box-sizing: border-box; }

        html { scroll-behavior: smooth; }

        body {
            margin: 0;
            padding: 0;
            background: var(--bg);
            color: var(--ink);
            font-family: var(--font-sans);
            line-height: 1.7;
            min-height: 100vh;
            transition: background 0.25s ease, color 0.25s ease;
            -webkit-font-smoothing: antialiased;
        }

        a { color: var(--accent); text-decoration: none; }
        a:hover { color: var(--accent-hover); }

        .theme-toggle {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 30px;
            height: 30px;
            padding: 0;
            border: 1px solid var(--hairline);
            border-radius: 50%;
            background: transparent;
            color: var(--muted);
            cursor: pointer;
            transition: color 0.2s ease, border-color 0.2s ease;
        }
        .theme-toggle:hover { color: var(--ink); border-color: var(--muted); }
        [data-theme="dark"] .icon-moon { display: none; }
        [data-theme="light"] .icon-sun { display: none; }

        .kicker {
            font-family: var(--font-mono);
            font-size: 0.72rem;
            font-weight: 500;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: var(--muted);
        }

        .double-rule {
            border: 0;
            border-top: 3px solid var(--rule);
            border-bottom: 1px solid var(--rule);
            height: 3px;
            margin: 0;
        }
        .thin-rule {
            border: 0;
            border-top: 1px solid var(--hairline);
            margin: 0;
        }

        /* Audio player */
        .phb-player {
            display: flex;
            align-items: center;
            gap: 14px;
            padding: 10px 0 2px 0;
        }
        .phb-player button.pp-btn {
            flex-shrink: 0;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: none;
            background: var(--accent);
            color: var(--bg);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s ease;
            padding: 0;
        }
        .phb-player button.pp-btn:hover { background: var(--accent-hover); }
        .phb-player .pp-track {
            flex-grow: 1;
            height: 3px;
            background: var(--hairline);
            cursor: pointer;
            position: relative;
        }
        .phb-player .pp-fill {
            position: absolute;
            left: 0; top: 0; bottom: 0;
            width: 0%;
            background: var(--accent);
        }
        .phb-player .pp-time {
            flex-shrink: 0;
            font-family: var(--font-mono);
            font-size: 0.75rem;
            color: var(--muted);
            min-width: 88px;
            text-align: right;
        }
        .phb-player.pp-error .pp-time { min-width: 0; }

        footer.site-footer {
            max-width: 720px;
            margin: 72px auto 0 auto;
            padding: 24px 24px 48px 24px;
            border-top: 1px solid var(--hairline);
            font-family: var(--font-mono);
            font-size: 0.7rem;
            letter-spacing: 0.06em;
            color: var(--muted);
            text-align: center;
            line-height: 2;
        }
"""

AUDIO_PLAYER_JS = """
    <script>
    (function() {
        var players = document.querySelectorAll('.phb-player');
        var fmt = function(s) {
            if (!isFinite(s)) return '--:--';
            var m = Math.floor(s / 60), r = Math.floor(s % 60);
            return m + ':' + (r < 10 ? '0' : '') + r;
        };
        players.forEach(function(p) {
            var audio = p.querySelector('audio');
            var btn = p.querySelector('.pp-btn');
            var track = p.querySelector('.pp-track');
            var fill = p.querySelector('.pp-fill');
            var time = p.querySelector('.pp-time');
            var iconPlay = btn.querySelector('.pp-play');
            var iconPause = btn.querySelector('.pp-pause');
            if (!audio) return;
            var update = function() {
                var d = audio.duration, c = audio.currentTime;
                fill.style.width = (d ? (c / d * 100) : 0) + '%';
                time.textContent = fmt(c) + ' / ' + fmt(d);
            };
            audio.addEventListener('loadedmetadata', update);
            audio.addEventListener('timeupdate', update);
            audio.addEventListener('ended', function() {
                iconPlay.style.display = ''; iconPause.style.display = 'none';
            });
            audio.addEventListener('error', function() {
                p.classList.add('pp-error');
                btn.disabled = true;
                btn.style.opacity = '0.4';
                time.textContent = 'audio unavailable';
            });
            btn.addEventListener('click', function() {
                if (audio.paused) {
                    document.querySelectorAll('.phb-player audio').forEach(function(a) {
                        if (a !== audio) a.pause();
                    });
                    document.querySelectorAll('.phb-player').forEach(function(q) {
                        if (q !== p) {
                            var pl = q.querySelector('.pp-play'), pa = q.querySelector('.pp-pause');
                            if (pl && pa) { pl.style.display = ''; pa.style.display = 'none'; }
                        }
                    });
                    audio.play();
                    iconPlay.style.display = 'none'; iconPause.style.display = '';
                } else {
                    audio.pause();
                    iconPlay.style.display = ''; iconPause.style.display = 'none';
                }
            });
            track.addEventListener('click', function(e) {
                if (!audio.duration) return;
                var r = track.getBoundingClientRect();
                audio.currentTime = ((e.clientX - r.left) / r.width) * audio.duration;
            });
        });
    })();
    </script>
"""

FOOTER_HTML = """
    <footer class="site-footer">
        &copy; 2026 Nitin Khola / Post-Human Engineering&trade;. All Rights Reserved.<br>
        "The Post-Human Briefing&trade;" and "The Post-Human Debrief&trade;" are proprietary trademarks.
    </footer>
"""


def render_player(src):
    """Markup for the shared custom audio player."""
    return f"""<div class="phb-player">
                <audio preload="metadata" src="{src}"></audio>
                <button class="pp-btn" aria-label="Play or pause">
                    <svg class="pp-play" width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"></path></svg>
                    <svg class="pp-pause" style="display:none" width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z"></path></svg>
                </button>
                <div class="pp-track"><div class="pp-fill"></div></div>
                <span class="pp-time">0:00 / --:--</span>
            </div>"""


def pretty_date(date_str):
    """'2026-06-30' -> 'Monday, June 30, 2026'."""
    d = datetime.strptime(date_str, '%Y-%m-%d')
    return d.strftime('%A, %B %-d, %Y')


def render_briefing_page(base_name, date_str, time_label, reading_time,
                         ai_html, fin_html, recent_html, has_audio):
    """Render a full standalone daily-briefing page."""
    audio_block = ""
    if has_audio:
        audio_block = f"""
        <div class="listen-block">
            <span class="kicker">Listen to this briefing</span>
            {render_player(f"audio/{base_name}.mp3")}
        </div>
"""

    briefing_css = """
        .progress-bar {
            position: fixed;
            top: 0; left: 0;
            height: 2px;
            width: 0%;
            background: var(--accent);
            z-index: 10;
        }

        .page {
            max-width: 720px;
            margin: 0 auto;
            padding: 28px 24px 40px 24px;
        }

        .top-nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            padding-bottom: 18px;
            border-bottom: 1px solid var(--hairline);
        }
        .top-nav .nav-left, .top-nav .nav-right {
            display: flex;
            align-items: center;
            gap: 18px;
        }
        .top-nav a {
            font-family: var(--font-mono);
            font-size: 0.75rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted);
        }
        .top-nav a:hover { color: var(--ink); }

        .briefing-head {
            padding: 44px 0 28px 0;
            text-align: left;
        }
        .briefing-head .kicker { color: var(--accent); }
        .briefing-head h1 {
            font-family: var(--font-serif);
            font-size: 2.7rem;
            font-weight: 600;
            letter-spacing: -0.02em;
            line-height: 1.12;
            margin: 10px 0 12px 0;
        }
        .briefing-head .dateline {
            font-family: var(--font-mono);
            font-size: 0.78rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted);
        }

        .listen-block {
            border-top: 1px solid var(--hairline);
            border-bottom: 1px solid var(--hairline);
            padding: 16px 0;
            margin-bottom: 8px;
        }

        section.brief-section { padding-top: 40px; }
        .section-head { margin-bottom: 8px; }
        .section-head h2 {
            font-family: var(--font-serif);
            font-size: 1.7rem;
            font-weight: 600;
            letter-spacing: -0.01em;
            margin: 10px 0 0 0;
        }
        .brief-body { font-size: 1.02rem; color: var(--ink-soft); }
        .brief-body > p:first-of-type::first-letter {
            font-family: var(--font-serif);
            font-size: 3.4em;
            font-weight: 600;
            float: left;
            line-height: 0.82;
            padding: 4px 10px 0 0;
            color: var(--accent);
        }
        .brief-body h3 {
            font-family: var(--font-serif);
            font-size: 1.3rem;
            font-weight: 600;
            color: var(--ink);
            margin: 2.2em 0 0.5em 0;
            letter-spacing: -0.01em;
        }
        .brief-body h4 {
            font-family: var(--font-mono);
            font-size: 0.72rem;
            font-weight: 500;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: var(--ochre);
            margin: 1.6em 0 0.4em 0;
        }
        .brief-body p { margin: 0 0 1.2em 0; }
        .brief-body ul { padding-left: 1.3em; margin: 0 0 1.2em 0; }
        .brief-body li { margin-bottom: 0.5em; }
        .brief-body a {
            color: var(--accent);
            text-decoration: underline;
            text-decoration-color: color-mix(in srgb, var(--accent) 45%, transparent);
            text-underline-offset: 3px;
        }
        .brief-body a:hover { color: var(--accent-hover); text-decoration-color: var(--accent-hover); }
        .brief-body blockquote {
            border-left: 2px solid var(--ochre);
            margin: 1.4em 0;
            padding: 2px 0 2px 18px;
            font-family: var(--font-serif);
            font-style: italic;
            color: var(--ink-soft);
        }
        .brief-body strong { color: var(--ink); }

        .recent {
            margin-top: 64px;
            padding-top: 8px;
        }
        .recent .kicker { display: block; margin: 14px 0 10px 0; }
        .recent-list { display: flex; flex-direction: column; }
        .recent-list a {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 12px;
            padding: 11px 2px;
            border-bottom: 1px solid var(--hairline);
            color: var(--ink);
            font-size: 0.95rem;
        }
        .recent-list a:hover { color: var(--accent); }
        .recent-list a .go {
            font-family: var(--font-mono);
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted);
        }
        .recent-list a:hover .go { color: var(--accent); }

        @media (max-width: 600px) {
            .briefing-head h1 { font-size: 2.1rem; }
        }
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Post-Human Briefing — {date_str} {time_label}</title>
    {THEME_BOOT}
    {SITE_FONTS}
    <link rel="icon" type="image/png" href="img/logo_favicon.png">
    <style>{BASE_CSS}{briefing_css}</style>
</head>
<body>
    <div class="progress-bar" id="progress-bar"></div>
    <div class="page">
        <nav class="top-nav">
            <div class="nav-left">
                <a href="index.html">&larr; The Post-Human Briefing</a>
            </div>
            <div class="nav-right">
                <a href="https://www.khola.blog/" target="_blank" rel="noopener">Khola.Blog</a>
                {THEME_TOGGLE_BTN}
            </div>
        </nav>

        <header class="briefing-head">
            <span class="kicker">The Post-Human Briefing</span>
            <h1>{time_label} Briefing</h1>
            <div class="dateline">{pretty_date(date_str)} &nbsp;&middot;&nbsp; {reading_time} min read</div>
        </header>
{audio_block}
        <section class="brief-section" id="ai-news">
            <div class="section-head">
                <hr class="double-rule">
                <h2>Artificial Intelligence</h2>
            </div>
            <div class="brief-body">
{ai_html}
            </div>
        </section>

        <section class="brief-section" id="finance-news">
            <div class="section-head">
                <hr class="double-rule">
                <h2>Markets &amp; Macro</h2>
            </div>
            <div class="brief-body">
{fin_html}
            </div>
        </section>

        <div class="recent">
            <hr class="double-rule">
            <span class="kicker">Recent briefings</span>
            <div class="recent-list">
{recent_html}
            </div>
        </div>
    </div>
{FOOTER_HTML}
    {THEME_TOGGLE_JS}
{AUDIO_PLAYER_JS}
    <script>
    (function() {{
        var bar = document.getElementById('progress-bar');
        var onScroll = function() {{
            var h = document.documentElement;
            var max = h.scrollHeight - h.clientHeight;
            bar.style.width = (max > 0 ? (h.scrollTop / max * 100) : 0) + '%';
        }};
        window.addEventListener('scroll', onScroll, {{ passive: true }});
        onScroll();
    }})();
    </script>
</body>
</html>
"""


def build_recent_html(repo_root, exclude=None, count=3):
    """Rows linking to the newest briefings, for a briefing page footer."""
    files = [f for f in os.listdir(repo_root)
             if f.endswith('.html') and f != 'index.html' and re.match(r'^\d{4}-\d{2}-\d{2}', f)]

    def sort_key(filename):
        name = filename.replace('.html', '')
        parts = name.split('-')
        weight = 1 if len(parts) == 4 and parts[3] == "PM" else 0
        return ("-".join(parts[:3]), weight)

    files.sort(key=sort_key, reverse=True)
    rows = ""
    shown = 0
    for rf in files:
        if exclude and rf == exclude:
            continue
        if shown >= count:
            break
        name = rf.replace('.html', '')
        parts = name.split('-')
        date_part = "-".join(parts[:3])
        label = ("Evening" if parts[3] == "PM" else "Morning") if len(parts) == 4 else "Daily"
        rows += (f'                <a href="{rf}"><span>{label} Briefing '
                 f'&middot; {pretty_date(date_part)}</span> <span class="go">Read</span></a>\n')
        shown += 1
    rows += '                <a href="index.html"><span>All briefings</span> <span class="go">Archive</span></a>\n'
    return rows


# ---------------------------------------------------------------------------
# Staged pipeline.
#
# The pipeline is three idempotent stages with file-based contracts, so a
# failure in one stage never repeats the expensive work of an earlier one:
#
#   synthesize  crawl + LLM  ->  content/<edition>/{ai.md,finance.md,meta.json}
#   render      content/     ->  <edition>.html + index.html   (pure, free)
#   narrate     content/     ->  content/<edition>/audio_script.txt
#                            ->  audio/<edition>.mp3
#
# content/ is the canonical artifact and is committed. Each stage skips
# itself when its output already exists (set FORCE_REGEN=1 to override), so
# re-running the workflow after a partial failure costs no LLM tokens for
# the stages that already succeeded.
# ---------------------------------------------------------------------------

CONTENT_DIRNAME = "content"


def edition_info(now=None):
    """(base_name, date_str, time_label) for the current edition, Eastern."""
    eastern = timezone(timedelta(hours=-4))
    now = now or datetime.now(eastern)
    date_str = now.strftime('%Y-%m-%d')
    force_time = os.getenv("FORCE_TIME_LABEL")
    if force_time == "AM":
        is_evening = False
    elif force_time == "PM":
        is_evening = True
    else:
        is_evening = now.hour >= 14
    time_label = "Evening" if is_evening else "Morning"
    base_name = f"{date_str}-{'PM' if is_evening else 'AM'}"
    return base_name, date_str, time_label


def content_dir_for(repo_root, base_name):
    return os.path.join(repo_root, CONTENT_DIRNAME, base_name)


def load_content(repo_root, base_name):
    """Load a persisted edition. Returns dict or None if absent/incomplete."""
    import json
    cdir = content_dir_for(repo_root, base_name)
    ai_p = os.path.join(cdir, "ai.md")
    fin_p = os.path.join(cdir, "finance.md")
    meta_p = os.path.join(cdir, "meta.json")
    if not (os.path.exists(ai_p) and os.path.exists(fin_p)):
        return None
    with open(ai_p, encoding="utf-8") as f:
        ai_md = f.read()
    with open(fin_p, encoding="utf-8") as f:
        fin_md = f.read()
    meta = {}
    if os.path.exists(meta_p):
        try:
            with open(meta_p, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}
    return {"ai_md": ai_md, "fin_md": fin_md, "meta": meta}


def synthesize_stage(repo_root, base_name, date_str, time_label, force=False):
    """Crawl sources and write the edition's markdown. The only stage that
    spends synthesis tokens; skipped entirely when content already exists."""
    import json
    cdir = content_dir_for(repo_root, base_name)
    if load_content(repo_root, base_name) and not force:
        print(f"[synthesize] content/{base_name} already exists; skipping "
              f"(FORCE_REGEN=1 to regenerate).")
        return False

    print(f"[synthesize] Generating {time_label.lower()} briefing for {date_str}...")
    compiler = MasterCompiler()

    print("[synthesize] Fetching AI News...")
    ai_raw = NewsCrawler().get_latest_news()
    ai_md = compiler.synthesize_news(ai_raw, topic="ai", time_label=time_label)

    print("[synthesize] Fetching Finance News...")
    fin_raw = FinanceCrawler().get_latest_news()
    fin_md = compiler.synthesize_news(fin_raw, topic="finance", time_label=time_label)

    total_words = len(ai_md.split()) + len(fin_md.split())
    meta = {
        "date": date_str,
        "time_label": time_label,
        "reading_time": max(1, total_words // 200),
    }

    os.makedirs(cdir, exist_ok=True)
    with open(os.path.join(cdir, "ai.md"), "w", encoding="utf-8") as f:
        f.write(ai_md)
    with open(os.path.join(cdir, "finance.md"), "w", encoding="utf-8") as f:
        f.write(fin_md)
    with open(os.path.join(cdir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[synthesize] Wrote content/{base_name}/ ({total_words} words).")
    return True


def list_content_editions(repo_root):
    croot = os.path.join(repo_root, CONTENT_DIRNAME)
    if not os.path.isdir(croot):
        return []
    return sorted(
        d for d in os.listdir(croot)
        if re.match(r'^\d{4}-\d{2}-\d{2}', d)
        and os.path.isdir(os.path.join(croot, d))
    )


def render_stage(repo_root, force=False):
    """Render pages for persisted editions and refresh the index.

    Pure content -> HTML; costs nothing, safe to re-run any time. Editions
    that predate the content store keep their existing HTML (see
    restyle_briefings.py for re-rendering those from their own markup).
    """
    editions = list_content_editions(repo_root)
    newest = editions[-1] if editions else None
    rendered = []
    for base_name in editions:
        page_path = os.path.join(repo_root, f"{base_name}.html")
        if os.path.exists(page_path) and not force:
            continue
        content = load_content(repo_root, base_name)
        if not content:
            continue
        meta = content["meta"]
        parts = base_name.split('-')
        date_str = meta.get("date") or "-".join(parts[:3])
        time_label = meta.get("time_label") or (
            ("Evening" if parts[3] == "PM" else "Morning") if len(parts) == 4 else "Daily")
        reading_time = meta.get("reading_time") or max(
            1, (len(content["ai_md"].split()) + len(content["fin_md"].split())) // 200)

        ai_html = markdown.markdown(content["ai_md"], extensions=['tables', 'fenced_code'])
        fin_html = markdown.markdown(content["fin_md"], extensions=['tables', 'fenced_code'])

        # The newest edition gets a player even before narration lands
        # (the player shows "audio unavailable" until the MP3 exists).
        has_audio = (
            os.path.exists(os.path.join(repo_root, "audio", f"{base_name}.mp3"))
            or base_name == newest
        )
        page = render_briefing_page(
            base_name=base_name,
            date_str=date_str,
            time_label=time_label,
            reading_time=reading_time,
            ai_html=ai_html,
            fin_html=fin_html,
            recent_html=build_recent_html(repo_root, exclude=f"{base_name}.html"),
            has_audio=has_audio,
        )
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(page)
        rendered.append(base_name)
        print(f"[render] Wrote {base_name}.html")

    update_index_page(repo_root, datetime.now(timezone(timedelta(hours=-4))).strftime('%Y-%m-%d'))
    print(f"[render] {len(rendered)} page(s) rendered; index refreshed.")
    return rendered


def narrate_stage(repo_root, base_name=None, force=False):
    """Produce the MP3 for an edition (newest by default).

    The LLM audio script is persisted next to the content, so a TTS retry
    reuses it instead of paying for a rewrite. Editions without a content
    dir (pre-content-store archive) fall back to extracting from their HTML.
    """
    if base_name is None:
        editions = list_content_editions(repo_root)
        if editions:
            base_name = editions[-1]
        else:
            pages = sorted(
                f[:-5] for f in os.listdir(repo_root)
                if f.endswith('.html') and re.match(r'^\d{4}-\d{2}-\d{2}', f))
            if not pages:
                print("[narrate] Nothing to narrate.")
                return False
            base_name = pages[-1]

    audio_dir = os.path.join(repo_root, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    audio_file_path = os.path.join(audio_dir, f"{base_name}.mp3")
    if os.path.exists(audio_file_path) and not force:
        print(f"[narrate] audio/{base_name}.mp3 already exists; skipping "
              f"(FORCE_REGEN=1 to regenerate).")
        return False

    parts = base_name.split('-')
    date_str = "-".join(parts[:3])
    time_label = ("Evening" if parts[3] == "PM" else "Morning") if len(parts) == 4 else "Morning"

    content = load_content(repo_root, base_name)
    if content:
        script_path = os.path.join(content_dir_for(repo_root, base_name), "audio_script.txt")
        if os.path.exists(script_path):
            print(f"[narrate] Reusing persisted audio script for {base_name}.")
            with open(script_path, encoding="utf-8") as f:
                plain_text = f.read().strip()
        else:
            ai_html = markdown.markdown(content["ai_md"], extensions=['tables', 'fenced_code'])
            fin_html = markdown.markdown(content["fin_md"], extensions=['tables', 'fenced_code'])
            flattened = (
                "Artificial Intelligence. " + html_to_speech_text(ai_html)
                + " Markets and Macro. " + html_to_speech_text(fin_html)
            )
            source = (f"## Artificial Intelligence\n\n{content['ai_md']}\n\n"
                      f"## Markets and Macro\n\n{content['fin_md']}")
            plain_text = build_audio_script(
                source, date_str, time_label, fallback_text=flattened)
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(plain_text)
            print(f"[narrate] Persisted audio script to content/{base_name}/audio_script.txt")
    else:
        # Archive edition: no content store, extract from the page itself.
        from bs4 import BeautifulSoup
        page_path = os.path.join(repo_root, f"{base_name}.html")
        with open(page_path, encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        ai_div = soup.find(id='ai-news')
        fin_div = soup.find(id='finance-news')
        ai_text = html_to_speech_text(ai_div.decode_contents()) if ai_div else ""
        fin_text = html_to_speech_text(fin_div.decode_contents()) if fin_div else ""
        flattened = f"Artificial Intelligence. {ai_text} Markets and Macro. {fin_text}"
        source = (f"## Artificial Intelligence\n\n{ai_text}\n\n"
                  f"## Markets and Macro\n\n{fin_text}")
        plain_text = build_audio_script(
            source, date_str, time_label, fallback_text=flattened)

    plain_text = re.sub(r'\s+', ' ', plain_text).strip()
    generate_audio_with_fallback(plain_text, audio_file_path)

    # Rolling window: Keep only the 10 most recent MP3s
    mp3_files = glob.glob(os.path.join(audio_dir, "*.mp3"))
    mp3_files.sort(key=os.path.getmtime, reverse=True)
    for file_to_delete in mp3_files[10:]:
        try:
            os.remove(file_to_delete)
            print(f"[narrate] Deleted old audio file: {file_to_delete}")
        except Exception:
            pass
    return True


def generate_daily_briefing():
    """Run the full pipeline in-process (local runs and tests).

    CI runs the same three stages as separate jobs — see
    .github/workflows/daily-briefing.yml.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    # Crawlers resolve config.yaml relative to the working directory.
    os.chdir(script_dir)

    force = os.getenv("FORCE_REGEN") == "1"
    base_name, date_str, time_label = edition_info()
    synthesize_stage(repo_root, base_name, date_str, time_label, force=force)
    render_stage(repo_root)
    narrate_stage(repo_root, base_name, force=force)


def build_podcast_section(repo_root):
    """Render the Weekly Debrief section for the index page.

    Reads podcast/episodes.json (written by generate_weekly_podcast.py).
    Falls back to a slim teaser row until the first episode exists.
    """
    import json
    manifest_path = os.path.join(repo_root, "podcast", "episodes.json")
    episodes = []
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                episodes = json.load(f)
        except Exception:
            episodes = []

    if not episodes:
        return """
        <section class="podcast-section">
            <div class="podcast-label">
                <span class="kicker teal">The Post-Human Debrief</span>
                <span class="kicker">Weekly Podcast</span>
            </div>
            <hr class="thin-rule">
            <p class="podcast-teaser">Two voices. One conversation. Everything that mattered this week in AI and markets. <em>First episode coming soon.</em></p>
        </section>"""

    latest = episodes[0]
    prev_html = ""
    for ep in episodes[1:]:
        prev_html += f"""
                <details class="podcast-prev-item">
                    <summary><span class="prev-title">{ep['title']}</span><span class="prev-meta">{ep['week_range']} &middot; {ep['duration_min']} min</span></summary>
                    {render_player(f"podcast/{ep['file']}")}
                </details>"""
    prev_block = f'\n            <div class="podcast-previous">{prev_html}\n            </div>' if prev_html else ''

    return f"""
        <section class="podcast-section">
            <div class="podcast-label">
                <span class="kicker teal">The Post-Human Debrief</span>
                <span class="kicker">Weekly Podcast</span>
            </div>
            <hr class="thin-rule">
            <div class="podcast-feature">
                <div class="podcast-meta kicker teal">Week of {latest['week_range']} &middot; {latest['duration_min']} min listen</div>
                <h2 class="podcast-title">{latest['title']}</h2>
                <p class="podcast-desc">{latest['description']}</p>
                {render_player(f"podcast/{latest['file']}")}
            </div>{prev_block}
        </section>"""


def build_lead_story(repo_root, latest_file):
    """Pull the executive summary and Bottom Line out of the newest briefing
    so the front page shows the synthesis, not just a link."""
    try:
        from bs4 import BeautifulSoup
        with open(os.path.join(repo_root, latest_file), "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        excerpt, bottom_line = "", ""
        ai_div = soup.find(id="ai-news")
        if ai_div:
            first_p = ai_div.find("p")
            if first_p:
                excerpt = first_p.get_text(" ", strip=True)

        for p in soup.find_all("p"):
            text = p.get_text(" ", strip=True)
            if re.match(r'^\W*THE BOTTOM LINE', text, re.I):
                bottom_line = re.sub(r'^\W*THE BOTTOM LINE\W*:?\s*', '', text, flags=re.I)

        if len(excerpt) > 340:
            cut = excerpt[:340].rsplit(' ', 1)[0].rstrip('.,;:')
            excerpt = cut + '&hellip;'
        return excerpt, bottom_line
    except Exception as e:
        print(f"Lead story extraction failed ({e}); front page falls back to links only.")
        return "", ""


def build_archive_html(files):
    """Group briefing files by week: date rows with edition links."""
    from collections import OrderedDict

    by_date = OrderedDict()
    for f in files:  # files arrive newest-first
        name = f.replace('.html', '')
        parts = name.split('-')
        date_part = "-".join(parts[:3])
        suffix = parts[3] if len(parts) == 4 else None
        by_date.setdefault(date_part, {})[suffix] = f

    weeks = OrderedDict()
    for date_part, editions in by_date.items():
        d = datetime.strptime(date_part, '%Y-%m-%d')
        monday = d - timedelta(days=d.weekday())
        weeks.setdefault(monday.strftime('%Y-%m-%d'), []).append((date_part, editions))

    html = ""
    for monday_str, days in weeks.items():
        monday = datetime.strptime(monday_str, '%Y-%m-%d')
        html += f'            <div class="week-group">\n'
        html += f'                <span class="kicker week-label">Week of {monday.strftime("%B %-d, %Y")}</span>\n'
        for date_part, editions in days:
            d = datetime.strptime(date_part, '%Y-%m-%d')
            chips = ""
            if "AM" in editions:
                chips += f'<a class="edition-chip" href="{editions["AM"]}">Morning</a>'
            if "PM" in editions:
                chips += f'<a class="edition-chip" href="{editions["PM"]}">Evening</a>'
            if None in editions:
                chips += f'<a class="edition-chip" href="{editions[None]}">Briefing</a>'
            html += (f'                <div class="archive-row">'
                     f'<span class="archive-date">{d.strftime("%A, %B %-d")}</span>'
                     f'<span class="edition-chips">{chips}</span></div>\n')
        html += '            </div>\n'
    return html


def update_index_page(repo_root, new_date_str):
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

    # --- Lead story (latest briefing, pulled onto the front page) ---
    lead_html = ""
    if files:
        latest = files[0]
        name_parts = latest.replace('.html', '').split('-')
        lead_date = "-".join(name_parts[:3])
        lead_label = ("Evening" if name_parts[3] == "PM" else "Morning") if len(name_parts) == 4 else "Daily"
        excerpt, bottom_line = build_lead_story(repo_root, latest)

        reading_time = ""
        try:
            with open(os.path.join(repo_root, latest), "r", encoding="utf-8") as f:
                m = re.search(r'(\d+)\s*min read', f.read())
                if m:
                    reading_time = f' &middot; {m.group(1)} min read'
        except Exception:
            pass

        base = latest.replace('.html', '')
        has_audio = os.path.exists(os.path.join(repo_root, "audio", f"{base}.mp3"))
        listen_html = render_player(f"audio/{base}.mp3") if has_audio else ""

        excerpt_html = f'\n                <p class="lead-excerpt"><a href="{latest}">{excerpt}</a></p>' if excerpt else ""
        bottom_html = f'\n                <p class="lead-bottom"><span class="kicker accent">The Bottom Line</span>{bottom_line}</p>' if bottom_line else ""

        lead_html = f"""
        <section class="lead-story">
            <div class="lead-meta kicker accent">Latest edition &middot; {lead_label} &middot; {pretty_date(lead_date)}{reading_time}</div>{excerpt_html}{bottom_html}
            <div class="lead-actions">
                <a class="read-link" href="{latest}">Read the full briefing &rarr;</a>
            </div>
            {listen_html}
        </section>"""

    archive_html = build_archive_html(files)
    podcast_section_html = build_podcast_section(repo_root)

    eastern = timezone(timedelta(hours=-4))
    today_line = datetime.now(eastern).strftime('%A, %B %-d, %Y')

    index_css = """
        .front-page {
            max-width: 720px;
            margin: 0 auto;
            padding: 28px 24px 40px 24px;
        }

        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            padding-bottom: 14px;
        }
        .top-bar .kicker a { color: var(--muted); }
        .top-bar .kicker a:hover { color: var(--ink); }
        .top-bar .bar-right { display: flex; align-items: center; gap: 18px; }

        .masthead {
            text-align: center;
            padding: 40px 0 28px 0;
        }
        .masthead img {
            width: 76px;
            height: auto;
            border-radius: 10px;
        }
        .masthead h1 {
            font-family: var(--font-serif);
            font-size: 3.1rem;
            font-weight: 600;
            letter-spacing: -0.02em;
            line-height: 1.05;
            margin: 18px 0 12px 0;
            color: var(--ink);
        }
        .masthead .tagline {
            font-family: var(--font-mono);
            font-size: 0.75rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: var(--muted);
            margin: 0;
        }

        .lead-story { padding: 30px 0 8px 0; }
        .lead-excerpt {
            font-family: var(--font-serif);
            font-size: 1.45rem;
            font-weight: 400;
            line-height: 1.45;
            letter-spacing: -0.01em;
            margin: 14px 0 18px 0;
        }
        .lead-excerpt a { color: var(--ink); }
        .lead-excerpt a:hover { color: var(--accent); }
        .kicker.accent { color: var(--accent); }
        .lead-bottom {
            border-left: 2px solid var(--ochre);
            padding: 4px 0 4px 18px;
            margin: 0 0 18px 0;
            color: var(--ink-soft);
            font-size: 0.98rem;
        }
        .lead-bottom .kicker { display: block; margin-bottom: 4px; color: var(--ochre); }
        .lead-actions { margin-bottom: 6px; }
        .read-link {
            font-family: var(--font-mono);
            font-size: 0.8rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--accent);
        }
        .read-link:hover { color: var(--accent-hover); }

        .kicker.teal { color: var(--teal); }
        .podcast-section { padding: 44px 0 10px 0; }
        .podcast-section .pp-btn { background: var(--teal); }
        .podcast-section .pp-btn:hover { background: var(--ink); }
        .podcast-section .pp-fill { background: var(--teal); }
        .podcast-label {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 12px;
            margin-bottom: 10px;
        }
        .podcast-teaser {
            color: var(--ink-soft);
            font-size: 0.98rem;
            margin: 16px 0 0 0;
        }
        .podcast-teaser em { color: var(--teal); font-style: normal; font-weight: 500; }
        .podcast-feature { padding-top: 18px; }
        .podcast-title {
            font-family: var(--font-serif);
            font-size: 1.7rem;
            font-weight: 600;
            letter-spacing: -0.01em;
            margin: 8px 0 8px 0;
        }
        .podcast-desc {
            color: var(--ink-soft);
            font-size: 0.98rem;
            margin: 0 0 6px 0;
        }
        .podcast-previous { margin-top: 18px; display: flex; flex-direction: column; }
        .podcast-prev-item {
            border-top: 1px solid var(--hairline);
            padding: 12px 0;
        }
        .podcast-prev-item summary {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 6px 12px;
            flex-wrap: wrap;
            cursor: pointer;
            list-style: none;
        }
        .podcast-prev-item summary::-webkit-details-marker { display: none; }
        .podcast-prev-item .prev-title {
            font-family: var(--font-serif);
            font-size: 1.05rem;
            font-weight: 500;
            color: var(--ink);
            flex: 1 1 auto;
            min-width: 55%;
        }
        .podcast-prev-item summary:hover .prev-title { color: var(--accent); }
        .podcast-prev-item .prev-meta {
            font-family: var(--font-mono);
            font-size: 0.72rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: var(--muted);
            white-space: nowrap;
        }

        .archive { padding: 44px 0 0 0; }
        .archive-head {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 10px;
        }
        .week-group { padding: 18px 0 6px 0; }
        .week-label { display: block; margin-bottom: 6px; color: var(--ochre); }
        .archive-row {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 12px;
            padding: 9px 0;
            border-bottom: 1px solid var(--hairline);
        }
        .archive-date {
            font-size: 0.98rem;
            color: var(--ink);
        }
        .edition-chips { display: flex; gap: 8px; flex-shrink: 0; }
        .edition-chip {
            font-family: var(--font-mono);
            font-size: 0.7rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--ink-soft);
            border: 1px solid var(--hairline);
            padding: 3px 10px;
            /* cubist snip: one clipped corner, echoing the logo's shards */
            clip-path: polygon(0 0, calc(100% - 7px) 0, 100% 7px, 100% 100%, 0 100%);
            transition: all 0.15s ease;
        }
        .edition-chip:hover {
            color: var(--bg);
            background: var(--accent);
            border-color: var(--accent);
        }

        @media (max-width: 600px) {
            .masthead h1 { font-size: 2.3rem; }
            .lead-excerpt { font-size: 1.25rem; }
            .archive-row { flex-direction: column; align-items: flex-start; gap: 6px; }
        }
"""

    index_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Post-Human Briefing</title>
    <meta name="description" content="A twice-daily synthesis of frontier AI and global markets, written and narrated end-to-end by autonomous agents.">
    {THEME_BOOT}
    {SITE_FONTS}
    <link rel="icon" type="image/png" href="img/logo_favicon.png">
    <style>{BASE_CSS}{index_css}</style>
</head>
<body>
    <div class="front-page">
        <div class="top-bar">
            <span class="kicker">{today_line}</span>
            <div class="bar-right">
                <span class="kicker"><a href="https://nkhola.github.io/">Post-Human Engineering</a></span>
                <span class="kicker"><a href="https://www.khola.blog/" target="_blank" rel="noopener">Khola.Blog</a></span>
                {THEME_TOGGLE_BTN}
            </div>
        </div>
        <hr class="thin-rule">

        <header class="masthead">
            <a href="index.html"><img src="img/logo_256.png" alt="The Post-Human Briefing logo"></a>
            <h1>The Post-Human Briefing</h1>
            <p class="tagline">Frontier AI &middot; Global Markets &middot; Zero Human Editors</p>
        </header>
        <hr class="double-rule">
{lead_html}
{podcast_section_html}

        <section class="archive">
            <div class="archive-head">
                <span class="kicker accent">All briefings</span>
                <span class="kicker">Morning &amp; Evening, ET</span>
            </div>
            <hr class="thin-rule">
{archive_html}
        </section>
    </div>
{FOOTER_HTML}
    {THEME_TOGGLE_JS}
{AUDIO_PLAYER_JS}
</body>
</html>
"""
    index_file = os.path.join(repo_root, "index.html")
    with open(index_file, "w", encoding="utf-8") as f:
        f.write(index_template)
    print("Updated index.html")

if __name__ == "__main__":
    generate_daily_briefing()
