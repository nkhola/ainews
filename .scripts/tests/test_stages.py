import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, script_dir)

import generate_site


def write_content(repo_root, base, ai="AI body. " * 30, fin="Fin body. " * 30):
    cdir = os.path.join(repo_root, "content", base)
    os.makedirs(cdir, exist_ok=True)
    with open(os.path.join(cdir, "ai.md"), "w") as f:
        f.write(ai)
    with open(os.path.join(cdir, "finance.md"), "w") as f:
        f.write(fin)
    with open(os.path.join(cdir, "meta.json"), "w") as f:
        json.dump({"date": base[:10], "time_label": "Morning", "reading_time": 3}, f)


@patch('generate_site.MasterCompiler')
@patch('generate_site.FinanceCrawler')
@patch('generate_site.NewsCrawler')
def test_synthesize_skips_when_content_exists(MockNews, MockFin, MockCompiler):
    """The expensive stage must be a no-op when its artifact exists."""
    with tempfile.TemporaryDirectory() as repo_root:
        write_content(repo_root, "2026-07-09-AM")
        ran = generate_site.synthesize_stage(
            repo_root, "2026-07-09-AM", "2026-07-09", "Morning", force=False)
        assert ran is False
        MockCompiler.assert_not_called()
        MockNews.assert_not_called()

        # force=True regenerates
        MockCompiler.return_value.synthesize_news.return_value = "regenerated " * 40
        ran = generate_site.synthesize_stage(
            repo_root, "2026-07-09-AM", "2026-07-09", "Morning", force=True)
        assert ran is True
        assert "regenerated" in open(
            os.path.join(repo_root, "content", "2026-07-09-AM", "ai.md")).read()


def test_render_stage_builds_pages_from_content():
    with tempfile.TemporaryDirectory() as repo_root:
        write_content(repo_root, "2026-07-09-AM")
        rendered = generate_site.render_stage(repo_root)
        assert rendered == ["2026-07-09-AM"]
        page = open(os.path.join(repo_root, "2026-07-09-AM.html")).read()
        assert "Morning Briefing" in page
        assert "AI body." in page
        # newest edition gets a player even before the MP3 lands
        assert "phb-player" in page
        assert os.path.exists(os.path.join(repo_root, "index.html"))

        # idempotent: second run renders nothing new
        assert generate_site.render_stage(repo_root) == []


def test_narrate_skips_existing_audio_and_reuses_script():
    with tempfile.TemporaryDirectory() as repo_root:
        base = "2026-07-09-AM"
        write_content(repo_root, base)
        audio_dir = os.path.join(repo_root, "audio")
        os.makedirs(audio_dir)
        open(os.path.join(audio_dir, f"{base}.mp3"), "wb").close()

        # existing MP3 -> full skip, no TTS call
        with patch('generate_site.generate_audio_with_fallback') as tts:
            assert generate_site.narrate_stage(repo_root, base, force=False) is False
            tts.assert_not_called()

        # force + persisted script -> TTS runs with the script, no LLM rewrite
        script_path = os.path.join(repo_root, "content", base, "audio_script.txt")
        with open(script_path, "w") as f:
            f.write("Good morning. Persisted script body.")
        with patch('generate_site.generate_audio_with_fallback') as tts, \
             patch('generate_site.build_audio_script') as builder:
            assert generate_site.narrate_stage(repo_root, base, force=True) is True
            builder.assert_not_called()
            assert "Persisted script body" in tts.call_args[0][0]
