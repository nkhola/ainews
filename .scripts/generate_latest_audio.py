#!/usr/bin/env python3
"""Back-compat shim: regenerate audio for the newest briefing.

The logic now lives in the narrate stage (stage_narrate.py /
generate_site.narrate_stage). This entry point forces a regeneration of
the newest edition's MP3, reusing the persisted audio script when one
exists.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_site import narrate_stage


def backfill_latest_audio():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    narrate_stage(repo_root, force=True)


if __name__ == "__main__":
    backfill_latest_audio()
