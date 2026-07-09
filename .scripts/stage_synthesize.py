#!/usr/bin/env python3
"""Stage 1/3: crawl sources + LLM synthesis -> content/<edition>/.

Idempotent: exits without spending tokens if the edition's content already
exists. Set FORCE_REGEN=1 to regenerate.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_site import edition_info, synthesize_stage


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    os.chdir(script_dir)  # crawlers resolve config.yaml from the working dir

    base_name, date_str, time_label = edition_info()
    synthesize_stage(
        repo_root, base_name, date_str, time_label,
        force=os.getenv("FORCE_REGEN") == "1",
    )


if __name__ == "__main__":
    main()
