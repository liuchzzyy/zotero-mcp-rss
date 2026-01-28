import feedparser
import requests
import time

urls = [
    "https://rss.sciencedirect.com/publication/science/25897780",
    "https://www.nature.com/nature.rss",
    "https://www.nature.com/nmeth.rss",
    "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science",
    "https://pubs.acs.org/action/showFeed?type=axatoc&feed=rss&jc=cmatex",
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

print(f"Testing {len(urls)} feeds...")

for url in urls:
    print(f"\n--- Testing: {url} ---")
    try:
        # Try with requests first to check connectivity/blocking
        print("1. Testing with requests...")
        start = time.time()
        response = requests.get(url, headers=headers, timeout=30, stream=True)
        print(f"   Status: {response.status_code}")
        print(f"   Time: {time.time() - start:.2f}s")

        # Read content to check for IncompleteRead
        content_len = 0
        for chunk in response.iter_content(chunk_size=8192):
            content_len += len(chunk)
        print(f"   Content Length downloaded: {content_len} bytes")

        # Try with feedparser
        print("2. Testing with feedparser...")
        d = feedparser.parse(url, agent=headers["User-Agent"])
        if hasattr(d, "bozo") and d.bozo:
            print(f"   Bozo Error: {d.bozo_exception}")
        else:
            print(f"   Success! Entries: {len(d.entries)}")

    except Exception as e:
        print(f"   ERROR: {e}")
