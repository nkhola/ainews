#!/usr/bin/env python3
"""Generate The Post-Human Debrief: the weekly two-host podcast.

Feeds the past week of daily briefings to Gemini on Vertex AI to write a
two-voice conversational script, then synthesizes it with Gemini-TTS
multi-speaker (two prebuilt voices in a single request per segment, so
every seam falls on a natural dialogue turn).

Outputs:
  podcast/<YYYY>-W<week>.mp3   the episode audio
  podcast/episodes.json        metadata consumed by update_index_page()
"""
import os
import sys
import platform

if platform.system() == "Darwin" and os.environ.get('OBJC_DISABLE_INITIALIZE_FORK_SAFETY') != 'YES':
    os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
    os.execv(sys.executable, [sys.executable] + sys.argv)

import glob
import json
import re
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_site import html_to_speech_text, update_index_page
from src.agents.master_compiler import MasterCompiler

# Two-voice cast. Charon reads the HOST (anchor), Kore the ANALYST.
SPEAKER_VOICES = {"HOST": "Charon", "ANALYST": "Kore"}

PODCAST_STYLE_PROMPT = (
    "Synthesize speech for the provided dialogue. This note is direction "
    "only: a relaxed two-host news podcast, natural back-and-forth, warm "
    "and steady from start to finish. Speak only the dialogue turns."
)

# Gemini-TTS multi-speaker limit: prompt and dialogue each <=4,000 bytes,
# combined <=8,000. Pack turns close to the limit so seams are rare, and
# always land between turns.
SEGMENT_MAX_BYTES = 3000

# Episode metadata is kept forever (podcast.html lists the full catalogue);
# only the MP3s age out, newest N kept (~5-8 MB each). Scripts are small
# and stay as the written record of every episode.
MAX_AUDIO_KEPT = 12

SPOKEN_WORDS_PER_MINUTE = 150


def _extract_briefing_text(repo_root, base_name, path):
    """Text of one briefing: prefer the committed markdown in content/,
    fall back to parsing the published page (works for both the old
    section-card template and the current brief-section one, since the
    ai-news / finance-news ids survived the redesign)."""
    from generate_site import load_content
    content = load_content(repo_root, base_name)
    if content:
        return f"{content['ai_md']}\n\n{content['fin_md']}"

    from bs4 import BeautifulSoup
    with open(path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    parts = []
    for div_id in ("ai-news", "finance-news"):
        node = soup.find(id=div_id)
        if node:
            parts.append(html_to_speech_text(node.decode_contents()))
    return "\n".join(parts) if parts else None


def collect_week_briefings(repo_root, now=None):
    """Return (briefings_text, week_range_label) for the past 7 days."""
    eastern = timezone(timedelta(hours=-4))
    now = now or datetime.now(eastern)
    cutoff = (now - timedelta(days=7)).strftime('%Y-%m-%d')

    files = []
    for path in glob.glob(os.path.join(repo_root, "*.html")):
        name = os.path.basename(path)
        m = re.match(r'^(\d{4}-\d{2}-\d{2})(-(AM|PM))?\.html$', name)
        if m and m.group(1) > cutoff:
            files.append((m.group(1), name, path))
    files.sort()
    if not files:
        return None, None

    sections = []
    for date_str, name, path in files:
        base_name = name.replace('.html', '')
        text = _extract_briefing_text(repo_root, base_name, path)
        if text:
            label = base_name.replace('-AM', ' Morning').replace('-PM', ' Evening')
            sections.append(f"=== BRIEFING: {label} ===\n{text}")

    if not sections:
        return None, None

    first = datetime.strptime(files[0][0], '%Y-%m-%d')
    last = datetime.strptime(files[-1][0], '%Y-%m-%d')
    week_range = f"{first.strftime('%B %-d')} to {last.strftime('%B %-d, %Y')}"
    return "\n\n".join(sections), week_range


def parse_podcast_script(script):
    """Parse the LLM output into (title, description, turns).

    turns is a list of (speaker, text) with speaker in SPEAKER_VOICES.
    Lines that don't start a new turn continue the previous one.
    """
    title, description = "", ""
    turns = []
    for raw_line in script.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not title and line.upper().startswith("TITLE:"):
            title = line[len("TITLE:"):].strip().strip('"')
            continue
        if not description and line.upper().startswith("DESCRIPTION:"):
            description = line[len("DESCRIPTION:"):].strip()
            continue
        m = re.match(r'^\**\s*(HOST|ANALYST)\s*\**\s*:\s*(.*)$', line, re.I)
        if m:
            speaker = m.group(1).upper()
            text = m.group(2).strip()
            if text:
                turns.append((speaker, text))
        elif turns:
            turns[-1] = (turns[-1][0], turns[-1][1] + " " + line)
    return title, description, turns


def split_turns_into_segments(turns, max_bytes=SEGMENT_MAX_BYTES):
    """Group consecutive turns into synthesis segments under max_bytes.

    A single oversized turn is split on sentence boundaries so it still
    fits; the split pieces keep the same speaker.
    """
    def turn_bytes(t):
        return len(t[1].encode("utf-8"))

    normalized = []
    for speaker, text in turns:
        if turn_bytes((speaker, text)) <= max_bytes:
            normalized.append((speaker, text))
            continue
        sentences = re.split(r'(?<=[.!?])\s+', text)
        piece = ""
        for sentence in sentences:
            candidate = f"{piece} {sentence}".strip()
            if piece and len(candidate.encode("utf-8")) > max_bytes:
                normalized.append((speaker, piece))
                piece = sentence
            else:
                piece = candidate
        if piece:
            normalized.append((speaker, piece))

    segments = []
    current, current_size = [], 0
    for turn in normalized:
        size = turn_bytes(turn)
        if current and current_size + size > max_bytes:
            segments.append(current)
            current, current_size = [], 0
        current.append(turn)
        current_size += size
    if current:
        segments.append(current)
    return segments


def synthesize_podcast_audio(segments, audio_file_path):
    """Synthesize dialogue segments with Gemini-TTS multi-speaker.

    Tries each Cloud TTS endpoint (regional, then global) because a
    regional Gemini-TTS backend can 502 for hours while global is healthy.
    """
    from generate_site import tts_endpoint_candidates
    from google.cloud import texttospeech

    last_error = None
    for endpoint in tts_endpoint_candidates():
        try:
            _synthesize_podcast_on_endpoint(segments, audio_file_path, endpoint)
            return
        except Exception as e:
            last_error = e
            print(f"Multi-speaker synthesis via {endpoint} failed: {e}")
    raise RuntimeError(
        f"Gemini-TTS multi-speaker failed on all endpoints: {last_error}. "
        f"Re-run this workflow; the episode script is persisted, so the "
        f"retry costs no LLM tokens.")


def _synthesize_podcast_on_endpoint(segments, audio_file_path, endpoint):
    from google.cloud import texttospeech

    print(f"Synthesizing podcast via {endpoint}...")
    client = texttospeech.TextToSpeechClient(client_options={"api_endpoint": endpoint})

    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        model_name="gemini-2.5-flash-tts",
        multi_speaker_voice_config=texttospeech.MultiSpeakerVoiceConfig(
            speaker_voice_configs=[
                texttospeech.MultispeakerPrebuiltVoice(
                    speaker_alias=alias, speaker_id=voice_id)
                for alias, voice_id in SPEAKER_VOICES.items()
            ]
        ),
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    full_audio = b""
    for idx, segment in enumerate(segments):
        print(f"  Synthesizing segment {idx+1}/{len(segments)} ({len(segment)} turns)...")
        markup = texttospeech.MultiSpeakerMarkup(
            turns=[
                texttospeech.MultiSpeakerMarkup.Turn(speaker=speaker, text=text)
                for speaker, text in segment
            ]
        )
        synthesis_input = texttospeech.SynthesisInput(
            multi_speaker_markup=markup,
            prompt=PODCAST_STYLE_PROMPT,
        )
        segment_text = " ".join(text for _, text in segment)
        last_error = None
        for attempt in range(3):
            try:
                response = client.synthesize_speech(
                    input=synthesis_input, voice=voice, audio_config=audio_config
                )
                from generate_site import audio_matches_text
                if not audio_matches_text(response.audio_content, segment_text):
                    raise RuntimeError(
                        f"segment {idx+1} spoke non-transcript content (QA)")
                full_audio += response.audio_content
                last_error = None
                break
            except Exception as e:
                last_error = e
                print(f"    Segment {idx+1} attempt {attempt+1} failed: {e}")
                time.sleep(5 * (attempt + 1))
        if last_error is not None:
            raise last_error

    with open(audio_file_path, "wb") as out:
        out.write(full_audio)
    print(f"Wrote {audio_file_path} ({len(full_audio) / 1024 / 1024:.1f} MB)")


def update_episode_manifest(podcast_dir, episode):
    manifest_path = os.path.join(podcast_dir, "episodes.json")
    episodes = []
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                episodes = json.load(f)
        except Exception:
            episodes = []

    replaced = next((e for e in episodes if e.get("file") == episode["file"]), None)
    episodes = [e for e in episodes if e.get("file") != episode["file"]]
    if replaced and replaced.get("number"):
        episode["number"] = replaced["number"]
    else:
        episode["number"] = (episodes[0].get("number", 0) + 1) if episodes else 1
    episodes.insert(0, episode)

    # Rolling audio window: metadata stays forever, MP3s beyond the newest
    # MAX_AUDIO_KEPT are evicted (podcast.html shows those as archived).
    kept_files = {e["file"] for e in episodes[:MAX_AUDIO_KEPT]}
    for mp3 in glob.glob(os.path.join(podcast_dir, "*.mp3")):
        if os.path.basename(mp3) not in kept_files:
            try:
                os.remove(mp3)
                print(f"Evicted old episode audio: {mp3}")
            except Exception:
                pass

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(episodes, f, indent=2)
    print(f"Updated {manifest_path} ({len(episodes)} episodes)")
    return episodes


def generate_weekly_podcast():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    os.chdir(script_dir)

    briefings_text, week_range = collect_week_briefings(repo_root)
    if not briefings_text:
        print("No briefings found for the past week; nothing to do.")
        return

    print(f"Collected briefings for the week of {week_range} "
          f"({len(briefings_text)} chars).")

    eastern = timezone(timedelta(hours=-4))
    now = datetime.now(eastern)
    iso_year, iso_week, _ = now.isocalendar()
    episode_stem = f"{iso_year}-W{iso_week:02d}"
    episode_file = f"{episode_stem}.mp3"

    podcast_dir = os.path.join(repo_root, "podcast")
    os.makedirs(podcast_dir, exist_ok=True)
    audio_file_path = os.path.join(podcast_dir, episode_file)
    force = os.getenv("FORCE_REGEN") == "1"

    if os.path.exists(audio_file_path) and not force:
        print(f"podcast/{episode_file} already exists; skipping "
              f"(FORCE_REGEN=1 to regenerate).")
        return

    # The script is the expensive artifact: persist it before synthesis so
    # a TTS failure re-run never pays for the writing twice.
    script_path = os.path.join(podcast_dir, f"{episode_stem}.script.txt")
    if os.path.exists(script_path) and not force:
        print(f"Reusing persisted script podcast/{episode_stem}.script.txt")
        with open(script_path, encoding="utf-8") as f:
            script = f.read()
    else:
        compiler = MasterCompiler()
        script = compiler.synthesize_podcast_script(briefings_text, week_range)
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)
        print(f"Persisted script to podcast/{episode_stem}.script.txt")

    title, description, turns = parse_podcast_script(script)
    if len(turns) < 10:
        raise RuntimeError(
            f"Podcast script parsing produced only {len(turns)} turns; "
            f"the script format was likely violated. First 500 chars:\n{script[:500]}")

    word_count = sum(len(text.split()) for _, text in turns)
    duration_min = max(1, round(word_count / SPOKEN_WORDS_PER_MINUTE))
    print(f"Script: '{title}' — {len(turns)} turns, {word_count} words "
          f"(~{duration_min} min).")

    segments = split_turns_into_segments(turns)
    print(f"Synthesizing {len(segments)} multi-speaker segments...")
    synthesize_podcast_audio(segments, audio_file_path)

    episode = {
        "file": episode_file,
        "title": title or f"The Week of {week_range}",
        "description": description,
        "week_range": week_range,
        "published": now.strftime('%Y-%m-%d'),
        "duration_min": duration_min,
    }
    update_episode_manifest(podcast_dir, episode)

    update_index_page(repo_root, now.strftime('%Y-%m-%d'))
    print("Done.")


if __name__ == "__main__":
    generate_weekly_podcast()
