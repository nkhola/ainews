import os
import requests
import feedparser
from bs4 import BeautifulSoup
import yaml


class NewsCrawler:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)["sources"]["ai_news"]

    def _fetch_feed(self, url, max_items=15):
        """Fetch and parse an RSS/Atom feed, returning structured items."""
        items = []
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                summary = getattr(entry, "summary", "")
                # Strip HTML from summary
                if summary:
                    summary = BeautifulSoup(summary, "html.parser").get_text(separator=" ")

                items.append({
                    "title": entry.get("title", "Untitled"),
                    "link": entry.get("link", ""),
                    "summary": summary,
                    "source": feed.feed.title if hasattr(feed.feed, "title") else url,
                    "published": getattr(entry, "published", ""),
                })
        except Exception as e:
            print(f"  ⚠ Error fetching {url}: {e}")
        return items

    def fetch_rss_feeds(self):
        """Fetch all configured RSS feeds."""
        items = []
        for url in self.config.get("rss_feeds", []):
            fetched = self._fetch_feed(url, max_items=15)
            items.extend(fetched)
            print(f"  ✓ {len(fetched)} items from {url[:60]}...")
        return items

    def fetch_subreddits(self):
        """Fetch top daily posts from configured subreddits via RSS."""
        items = []
        for sub in self.config.get("subreddits", []):
            url = f"https://www.reddit.com/r/{sub}/top/.rss?t=day"
            try:
                headers = {"User-Agent": "ai-news-agent/1.0"}
                response = requests.get(url, headers=headers, timeout=10)
                feed = feedparser.parse(response.content)
                for entry in feed.entries[:10]:
                    items.append({
                        "title": entry.get("title", "Untitled"),
                        "link": entry.get("link", ""),
                        "summary": "",
                        "source": f"r/{sub}",
                        "published": getattr(entry, "published", ""),
                    })
                print(f"  ✓ {min(10, len(feed.entries))} items from r/{sub}")
            except Exception as e:
                print(f"  ⚠ Error fetching r/{sub}: {e}")
        return items

    def fetch_podcasts(self):
        """Fetch latest podcast episode titles/descriptions."""
        items = []
        for url in self.config.get("podcast_feeds", []):
            fetched = self._fetch_feed(url, max_items=5)
            items.extend(fetched)
            if fetched:
                print(f"  ✓ {len(fetched)} podcast episodes from {url[:60]}...")
        return items

    def get_latest_news(self):
        """Aggregate all news sources into a structured text block for the LLM."""
        print("[NewsCrawler] Fetching AI news from all sources...")
        rss_items = self.fetch_rss_feeds()
        reddit_items = self.fetch_subreddits()
        podcast_items = self.fetch_podcasts()

        all_items = rss_items + reddit_items + podcast_items

        raw_text = f"Raw AI News Data ({len(all_items)} items):\n\n"
        for idx, item in enumerate(all_items, 1):
            raw_text += f"{idx}. [{item['source']}] {item['title']}\n"
            if item.get("summary"):
                raw_text += f"   Summary: {item['summary']}\n"
            if item.get("link"):
                raw_text += f"   Link: {item['link']}\n"
            raw_text += "\n"

        print(f"[NewsCrawler] Done. {len(all_items)} total items aggregated.\n")
        return raw_text
