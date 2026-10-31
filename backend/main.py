import os, sqlite3, hashlib, logging
from datetime import datetime, timezone
import feedparser
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gsa")
DB = os.getenv("DATABASE_PATH", "./gsa.db")
FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
]
app = FastAPI(title="GSA Critical Events API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])

LEVEL5 = ["nuclear weapon used", "nuclear attack", "declares war", "declared war",
          "invasion begins", "coup succeeds", "government overthrown"]
LEVEL4 = ["airstrike on iran", "strikes on iran", "iran attacked", "cross-border invasion",
          "invades", "military coup", "strait of hormuz closed", "blockade",
          "war breaks out", "attacks nuclear facility", "mass uprising"]

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, title TEXT, summary TEXT, source TEXT, url TEXT, level INTEGER, published TEXT, first_seen TEXT)")
    c.commit()
    return c

def classify(title, summary):
    text = (title + " " + summary).lower()
    if any(k in text for k in LEVEL5):
        return 5
    if any(k in text for k in LEVEL4):
        return 4
    return 0

def ingest():
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    conn = db()
    for source, feed_url in FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:40]:
                title = (getattr(entry, "title", "") or "").strip()
                summary = (getattr(entry, "summary", "") or "").strip()
                url = (getattr(entry, "link", "") or "").strip()
                published = getattr(entry, "published", "") or getattr(entry, "updated", "") or ""
                if not title or not url:
                    continue
                level = classify(title, summary)
                if level < 4:
                    continue
                event_id = hashlib.sha256(url.encode()).hexdigest()
                cur = conn.execute("INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (event_id, title, summary[:1800], source, url, level, published, now))
                added += cur.rowcount
        except Exception:
            log.exception("Feed failed: %s", source)
    conn.commit()
    conn.close()
    return {"new_events": added, "checked_at": now}

@app.get("/health")
def health():
    return {"status": "ok", "service": "GSA API", "utc": datetime.now(timezone.utc).isoformat()}

@app.get("/sources")
def sources():
    return {"sources": [{"name": n, "feed": u} for n, u in FEEDS]}

@app.post("/refresh")
def refresh():
    return ingest()

@app.get("/events")
def events(min_level: int = Query(4, ge=4, le=5), limit: int = Query(50, ge=1, le=200)):
    if os.getenv("POLL_ON_REQUEST", "true").lower() == "true":
        ingest()
    conn = db()
    rows = conn.execute("SELECT * FROM events WHERE level >= ? ORDER BY first_seen DESC LIMIT ?",
                        (min_level, limit)).fetchall()
    conn.close()
    return {"events": [dict(r) for r in rows], "count": len(rows),
            "warning": "RSS keyword triage only; events are not independently corroborated."}
