#!/usr/bin/env python3
"""Stage 3/3: content/<edition> -> audio script -> audio/<edition>.mp3.

Idempotent: skips if the MP3 exists (FORCE_REGEN=1 to redo the TTS). The
LLM-written audio script is persisted alongside the content, so retries
never pay for a script rewrite. Pass an edition name to target a specific
briefing; defaults to the newest.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_site import narrate_stage


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    base_name = sys.argv[1] if len(sys.argv) > 1 else None
    narrate_stage(
        repo_root, base_name=base_name,
        force=os.getenv("FORCE_REGEN") == "1",
    )


if __name__ == "__main__":
    main()
