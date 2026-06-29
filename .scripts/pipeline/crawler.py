import os
import sys

# Ensure we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetchers.news_crawler import NewsCrawler
from src.fetchers.finance_crawler import FinanceCrawler

def fetch_all_news():
    print("Fetching AI News...")
    ai_crawler = NewsCrawler()
    ai_raw = ai_crawler.get_latest_news()

    print("Fetching Finance News...")
    fin_crawler = FinanceCrawler()
    fin_raw = fin_crawler.get_latest_news()

    return {
        "ai": ai_raw,
        "finance": fin_raw
    }
