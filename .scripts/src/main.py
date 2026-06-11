#!/usr/bin/env python3
"""
AI News & Finance Aggregator Agent
===================================
Main entry point. Runs on a schedule (9am, 1pm, 6pm) and delivers
synthesized news briefings to WhatsApp.

Can also be run with --test to do a single immediate run.
"""

import os
import sys
import time
import schedule
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path so imports work both locally and in Docker
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetchers.news_crawler import NewsCrawler
from src.fetchers.finance_crawler import FinanceCrawler
from src.agents.master_compiler import MasterCompiler
from src.delivery.whatsapp import WhatsAppDelivery

load_dotenv()


def get_time_label():
    """Get Morning/Evening based on current time (Eastern)."""
    # Simple check for demo purposes, in production use timezone-aware logic
    hour = datetime.now().hour
    return "Evening" if hour >= 14 else "Morning"


def run_ai_news_briefing(deliver=True):
    """Fetch, synthesize, and deliver the AI news briefing."""
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running AI News Briefing...")
    print(f"{'='*60}")

    crawler = NewsCrawler()
    compiler = MasterCompiler()
    time_label = get_time_label()

    raw_data = crawler.get_latest_news()
    print(f"Fetched {raw_data.count(chr(10))} lines of raw AI news data.")

    briefing = compiler.synthesize_news(raw_data, topic="ai", time_label=time_label)
    print(f"\n--- AI NEWS BRIEFING ({time_label}) ---")
    print(briefing)
    print("--- END ---\n")

    if deliver:
        wa = WhatsAppDelivery()
        wa.send_message(f"🧠 *AI News Briefing ({time_label})*\n\n{briefing}")

    return briefing


def run_finance_briefing(deliver=True):
    """Fetch, synthesize, and deliver the finance briefing."""
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running Finance Briefing...")
    print(f"{'='*60}")

    crawler = FinanceCrawler()
    compiler = MasterCompiler()
    time_label = get_time_label()

    raw_data = crawler.get_latest_news()
    print(f"Fetched {raw_data.count(chr(10))} lines of raw finance data.")

    briefing = compiler.synthesize_news(raw_data, topic="finance", time_label=time_label)
    print(f"\n--- FINANCE BRIEFING ({time_label}) ---")
    print(briefing)
    print("--- END ---\n")

    if deliver:
        wa = WhatsAppDelivery()
        wa.send_message(f"📈 *Finance Briefing ({time_label})*\n\n{briefing}")

    return briefing


def run_all(deliver=True):
    """Run both briefings."""
    run_ai_news_briefing(deliver=deliver)
    run_finance_briefing(deliver=deliver)


def main():
    if "--test" in sys.argv:
        # Single immediate run, no WhatsApp delivery
        print("Running in TEST mode (no WhatsApp delivery)...")
        run_all(deliver=False)
        return

    if "--test-deliver" in sys.argv:
        # Single immediate run WITH WhatsApp delivery
        print("Running in TEST-DELIVER mode (with WhatsApp delivery)...")
        run_all(deliver=True)
        return

    # --- Scheduled Mode ---
    tz = os.getenv("SCHEDULE_TZ", "America/New_York")
    print(f"Starting scheduler. Briefings at 09:00, 13:00, 18:00 ({tz})")
    print("Use --test for a single dry run, --test-deliver for a single run with WhatsApp.\n")

    schedule.every().day.at("09:00").do(run_all)
    schedule.every().day.at("13:00").do(run_all)
    schedule.every().day.at("18:00").do(run_all)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
