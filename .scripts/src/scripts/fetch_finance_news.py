#!/usr/bin/env python3
"""
Finance News Crawler Script for Hermes Agent
==============================================
This script fetches and aggregates raw finance data from all configured sources.
It outputs the raw data to stdout, which Hermes injects into an LLM prompt.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.fetchers.finance_crawler import FinanceCrawler


def main():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml"))
    crawler = FinanceCrawler(config_path=config_path)
    raw_data = crawler.get_latest_news()
    print(raw_data)


if __name__ == "__main__":
    main()
