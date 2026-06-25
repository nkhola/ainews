import os
import requests
import feedparser
from bs4 import BeautifulSoup
import yaml
from datetime import datetime, timezone, timedelta
import calendar


class NewsCrawler:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)["sources"]["ai_news"]

    def _fetch_feed(self, url, max_items=15, time_label=None):
        """Fetch and parse an RSS/Atom feed, returning structured items."""
        items = []
        eastern = timezone(timedelta(hours=-4))
        now_est = datetime.now(eastern)
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                # Apply date filtering (keep only items from the last 36 hours)
                struct_time = entry.get("published_parsed") or entry.get("updated_parsed")
                if struct_time:
                    try:
                        dt = datetime.fromtimestamp(calendar.timegm(struct_time), timezone.utc)
                        dt_est = dt.astimezone(eastern)
                        
                        if now_est - dt_est > timedelta(hours=36):
                            continue
                            
                        # Apply time cutoffs
                        if time_label == "Morning":
                            cutoff = now_est.replace(hour=9, minute=0, second=0, microsecond=0)
                            if dt_est >= cutoff:
                                continue
                        elif time_label == "Evening":
                            cutoff = now_est.replace(hour=18, minute=0, second=0, microsecond=0)
                            if dt_est >= cutoff:
                                continue
                                
                    except Exception as e:
                        print(f"  ⚠ Error parsing date for {entry.get('title')}: {e}")

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

    def fetch_rss_feeds(self, time_label=None):
        """Fetch all configured RSS feeds."""
        items = []
        for url in self.config.get("rss_feeds", []):
            fetched = self._fetch_feed(url, max_items=15, time_label=time_label)
            items.extend(fetched)
            print(f"  ✓ {len(fetched)} items from {url[:60]}...")
        return items

    def fetch_subreddits(self, time_label=None):
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

    def fetch_podcasts(self, time_label=None):
        """Fetch latest podcast episode titles/descriptions."""
        items = []
        for url in self.config.get("podcast_feeds", []):
            fetched = self._fetch_feed(url, max_items=5, time_label=time_label)
            items.extend(fetched)
            if fetched:
                print(f"  ✓ {len(fetched)} podcast episodes from {url[:60]}...")
        return items

    def get_latest_news(self, time_label=None):
        """Aggregate all news sources into a structured text block for the LLM."""
        print("[NewsCrawler] Fetching AI news from all sources...")
        rss_items = self.fetch_rss_feeds(time_label)
        reddit_items = self.fetch_subreddits(time_label)
        podcast_items = self.fetch_podcasts(time_label)

        all_items = rss_items + reddit_items + podcast_items

        raw_text = f"Raw AI News Data ({len(all_items)} items):\n\n"
        for item in all_items:
            raw_text += f"Source: {item['source']}\n"
            raw_text += f"Title: {item['title']}\n"
            if item.get("summary"):
                raw_text += f"Summary: {item['summary']}\n"
            if item.get("link"):
                raw_text += f"URL: {item['link']}\n"
            raw_text += "---\n\n"

        print(f"[NewsCrawler] Done. {len(all_items)} total items aggregated.\n")
        return raw_text

