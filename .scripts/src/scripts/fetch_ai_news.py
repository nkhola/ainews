#!/usr/bin/env python3
"""
AI News Crawler Script for Hermes Agent
=========================================
This script fetches and aggregates raw news data from all configured sources.
It outputs the raw data to stdout, which Hermes injects into an LLM prompt.

Hermes cron runs this script on schedule, feeds its output to the LLM,
and delivers the synthesized briefing to WhatsApp.
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.fetchers.news_crawler import NewsCrawler


def main():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml"))
    crawler = NewsCrawler(config_path=config_path)
    raw_data = crawler.get_latest_news()
    # Print to stdout — Hermes will pick this up
    print(raw_data)


if __name__ == "__main__":
    main()
