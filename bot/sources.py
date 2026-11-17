import hashlib
import os
import re
import time
import requests
import feedparser
from bs4 import BeautifulSoup

DEFAULT_FEEDS = [
    "https://feeds.bbci.co.uk/persian/rss.xml",
    "https://rss.dw.com/xml/rss-far-all",
]

UA = {"User-Agent": "NabzIranBot/1.1 (Rubika channel publisher)"}
BAD_TITLE = ("map", "flag", "logo", "coat of arms", "diagram", "plan", "poster",
             "stamp", "banknote", "drawing", "painting", "locator", "route", "chart")

def clean_html(value: str) -> str:
    text = BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()

def norm(text: str) -> str:
    """یکسان‌سازی حروف عربی/فارسی و نیم‌فاصله برای جست‌وجوی کلمه کلیدی."""
    return (text or "").replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").lower()

def feeds():
    raw = os.getenv("RSS_FEEDS", "").strip()
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else DEFAULT_FEEDS

def get_news():
    results = []
    for feed_url in feeds():
        try:
            parsed = feedparser.parse(feed_url)
            source = parsed.feed.get("title", feed_url)
            for entry in parsed.entries[:40]:
                title = clean_html(entry.get("title", ""))
                summary = clean_html(entry.get("summary", entry.get("description", "")))
                link = entry.get("link", "")
                if not title or not link:
                    continue
                ts = entry.get("published_parsed") or entry.get("updated_parsed")
                results.append({
                    "title": title[:220], "summary": summary[:650],
                    "link": link, "source": source,
                    "key": hashlib.sha256(link.encode("utf-8")).hexdigest(),
                    "ts": time.mktime(ts) if ts else 0,
                })
        except Exception as exc:
            print(f"RSS error ({feed_url}): {exc}")
    results.sort(key=lambda x: x["ts"], reverse=True)  # تازه‌ترین اول
    return results

def _license_ok(name: str) -> bool:
    return bool(re.match(r"^(cc|public domain|pd)", name.strip().lower()))

def commons_image(query: str, output_path: str, skip=lambda key: False):
    """بهترین عکس مجاز (CC / Public domain) برای یک مکان خاص را از Commons می‌گیرد."""
    params = {
        "action": "query", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 20,
        "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime",
        "iiurlwidth": 1600, "format": "json",
    }
    r = requests.get("https://commons.wikimedia.org/w/api.php",
                     params=params, headers=UA, timeout=30)
    r.raise_for_status()
    pages = sorted(r.json().get("query", {}).get("pages", {}).values(),
                   key=lambda p: p.get("index", 0))
    for page in pages:
        title = page.get("title", "")
        key = f"commons:{title}"
        if skip(key) or any(b in title.lower() for b in BAD_TITLE):
            continue
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        license_name = clean_html(meta.get("LicenseShortName", {}).get("value", ""))
        url = info.get("thumburl") or info.get("url")
        if not url or not _license_ok(license_name):
            continue
        if info.get("mime") != "image/jpeg":
            continue
        w, h = info.get("width", 0), info.get("height", 0)
        if w < 1200 or w < h:   # فقط عکس افقی و باکیفیت
            continue
        img = requests.get(url, headers=UA, timeout=45)
        if img.status_code != 200 or not img.headers.get("Content-Type", "").startswith("image/"):
            continue
        if len(img.content) > 8_000_000:
            continue
        with open(output_path, "wb") as f:
            f.write(img.content)
        artist = clean_html(meta.get("Artist", {}).get("value", ""))[:60]
        return {"license": license_name, "artist": artist, "page": title, "key": key}
    raise RuntimeError(f"No suitable image for: {query}")
