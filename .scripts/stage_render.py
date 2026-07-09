#!/usr/bin/env python3
"""Stage 2/3: content/ -> briefing pages + index. Pure and free; re-run any
time. Set FORCE_REGEN=1 to re-render pages whose HTML already exists.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_site import render_stage


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    render_stage(repo_root, force=os.getenv("FORCE_REGEN") == "1")


if __name__ == "__main__":
    main()
