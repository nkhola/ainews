import feedparser
from bs4 import BeautifulSoup
import yaml
from datetime import datetime, timezone, timedelta
import calendar


class FinanceCrawler:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)["sources"]["finance"]

    def get_latest_news(self):
        """Aggregate all finance sources into a structured text block for the LLM."""
        print("[FinanceCrawler] Fetching finance news from all sources...")
        items = []
        for url in self.config.get("rss_feeds", []):
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:15]:
                    # Apply date filtering (keep only items from the last 36 hours)
                    struct_time = entry.get("published_parsed") or entry.get("updated_parsed")
                    if struct_time:
                        try:
                            dt = datetime.fromtimestamp(calendar.timegm(struct_time), timezone.utc)
                            now = datetime.now(timezone.utc)
                            if now - dt > timedelta(hours=36):
                                continue
                        except Exception as e:
                            print(f"  ⚠ Error parsing date for {entry.get('title')}: {e}")

                    summary = getattr(entry, "summary", "")
                    if summary:
                        summary = BeautifulSoup(summary, "html.parser").get_text(separator=" ")

                    items.append({
                        "title": entry.get("title", "Untitled"),
                        "link": entry.get("link", ""),
                        "summary": summary,
                        "source": feed.feed.title if hasattr(feed.feed, "title") else url,
                    })
                print(f"  ✓ {min(15, len(feed.entries))} items from {url[:60]}...")
            except Exception as e:
                print(f"  ⚠ Error fetching {url}: {e}")

        raw_text = f"Raw Finance & Equity Data ({len(items)} items):\n\n"
        for item in items:
            raw_text += f"Source: {item['source']}\n"
            raw_text += f"Title: {item['title']}\n"
            if item.get("summary"):
                raw_text += f"Summary: {item['summary']}\n"
            if item.get("link"):
                raw_text += f"URL: {item['link']}\n"
            raw_text += "---\n\n"

        print(f"[FinanceCrawler] Done. {len(items)} total items aggregated.\n")
        return raw_text
