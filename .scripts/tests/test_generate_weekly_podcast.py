import os
import sys
import ast
import json
import tempfile

import pytest

script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, script_dir)

import generate_weekly_podcast as podcast
import generate_site


def test_syntax_is_valid():
    file_path = os.path.join(script_dir, 'generate_weekly_podcast.py')
    with open(file_path, 'r', encoding='utf-8') as f:
        ast.parse(f.read())


def test_parse_podcast_script():
    script = (
        "TITLE: The Week Compute Got Cheap\n"
        "DESCRIPTION: A conversation about inference prices collapsing.\n"
        "HOST: Welcome to the Debrief. Big week.\n"
        "ANALYST: Huge. Let's start with the price cuts.\n"
        "This continues the analyst's previous turn.\n"
        "HOST: Right.\n"
    )
    title, description, turns = podcast.parse_podcast_script(script)
    assert title == "The Week Compute Got Cheap"
    assert "inference prices" in description
    assert turns[0] == ("HOST", "Welcome to the Debrief. Big week.")
    assert turns[1][0] == "ANALYST"
    assert "continues the analyst's previous turn" in turns[1][1]
    assert turns[2] == ("HOST", "Right.")


def test_parse_tolerates_markdown_bold_labels():
    script = (
        "TITLE: T\n"
        "DESCRIPTION: D\n"
        "**HOST:** Hello there.\n"
        "**ANALYST**: Hi.\n"
    )
    _, _, turns = podcast.parse_podcast_script(script)
    assert [t[0] for t in turns] == ["HOST", "ANALYST"]


def test_split_turns_respects_byte_limit_and_boundaries():
    turns = [("HOST", "Sentence one is here."), ("ANALYST", "Reply two.")] * 200
    segments = podcast.split_turns_into_segments(turns, max_bytes=500)
    # Every segment under the limit
    for seg in segments:
        total = sum(len(t.encode("utf-8")) for _, t in seg)
        assert total <= 500
    # No turns lost or reordered
    flattened = [t for seg in segments for t in seg]
    assert flattened == turns


def test_split_handles_oversized_single_turn():
    long_text = " ".join(["This is a fairly long sentence for testing."] * 50)
    segments = podcast.split_turns_into_segments([("HOST", long_text)], max_bytes=400)
    for seg in segments:
        for speaker, text in seg:
            assert speaker == "HOST"
            assert len(text.encode("utf-8")) <= 400
    reassembled = " ".join(text for seg in segments for _, text in seg)
    assert reassembled.split() == long_text.split()


def test_build_podcast_section_teaser_and_episodes():
    with tempfile.TemporaryDirectory() as repo_root:
        # No manifest -> teaser
        html = generate_site.build_podcast_section(repo_root)
        assert "The Post-Human Debrief" in html
        assert "coming soon" in html.lower()

        # With manifest -> featured episode + previous list
        podcast_dir = os.path.join(repo_root, "podcast")
        os.makedirs(podcast_dir)
        episodes = [
            {"file": "2026-W27.mp3", "title": "Latest Ep", "description": "Desc.",
             "week_range": "June 29 to July 5, 2026", "published": "2026-07-05",
             "duration_min": 31},
            {"file": "2026-W26.mp3", "title": "Older Ep", "description": "Old.",
             "week_range": "June 22 to June 28, 2026", "published": "2026-06-28",
             "duration_min": 29},
        ]
        with open(os.path.join(podcast_dir, "episodes.json"), "w") as f:
            json.dump(episodes, f)
        html = generate_site.build_podcast_section(repo_root)
        assert "Latest Ep" in html
        assert 'src="podcast/2026-W27.mp3"' in html
        assert "Older Ep" in html
        assert "coming soon" not in html.lower()


def test_manifest_rolling_window():
    with tempfile.TemporaryDirectory() as podcast_dir:
        # Seed manifest at the cap plus matching mp3 files
        old = []
        for week in range(23, 23 + podcast.MAX_EPISODES_KEPT):
            name = f"2026-W{week}.mp3"
            old.append({"file": name, "title": name, "description": "",
                        "week_range": "", "published": "", "duration_min": 1})
            open(os.path.join(podcast_dir, name), "wb").close()
        with open(os.path.join(podcast_dir, "episodes.json"), "w") as f:
            json.dump(old, f)

        new_name = "2026-W99.mp3"
        open(os.path.join(podcast_dir, new_name), "wb").close()
        episodes = podcast.update_episode_manifest(podcast_dir, {
            "file": new_name, "title": "New", "description": "",
            "week_range": "", "published": "", "duration_min": 1})

        assert len(episodes) == podcast.MAX_EPISODES_KEPT
        assert episodes[0]["file"] == new_name
        remaining = sorted(f for f in os.listdir(podcast_dir) if f.endswith(".mp3"))
        assert new_name in remaining
        assert len(remaining) == podcast.MAX_EPISODES_KEPT
