import sys
import os
sys.path.insert(0, os.path.abspath('.scripts'))
from src.fetchers.news_crawler import NewsCrawler
from src.fetchers.finance_crawler import FinanceCrawler

ai_crawler = NewsCrawler('.scripts/config.yaml')
fin_crawler = FinanceCrawler('.scripts/config.yaml')

print("=== AI ===")
print(ai_crawler.get_latest_news())
print("=== FIN ===")
print(fin_crawler.get_latest_news())
