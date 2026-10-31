"""GSA backend v0.2 - RSS candidate detection and cautious cross-source grouping.

This service performs rule-based triage only. It does NOT establish ground truth.
"""
import os
import re
import sqlite3
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from gsa_grouping import same_event
from urllib.parse import urlparse

import feedparser
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gsa")
DB = os.getenv("DATABASE_PATH", "./gsa.db")
POLL_ON_REQUEST = os.getenv("POLL_ON_REQUEST", "true").lower() == "true"

# Keep this list conservative. Add feeds only after checking ownership and reliability.
FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
]

# Candidate categories are deliberately broad; severity is assigned separately.
RULES = [
    ("nuclear_use", 5, ["nuclear weapon used", "nuclear attack", "nuclear strike", "detonated nuclear"]),
    ("war_declaration", 5, ["declares war", "declared war", "declaration of war"]),
    ("invasion", 5, ["invasion begins", "invaded", "troops crossed the border", "cross-border invasion"]),
    ("government_overthrow", 5, ["coup succeeds", "government overthrown", "government has fallen", "military takeover"]),
    ("major_strike", 4, ["airstrike on", "air strikes on", "missile strike on", "strikes on nuclear facility", "attacked nuclear facility"]),
    ("strait_closure", 4, ["strait of hormuz closed", "strait of hormuz closure", "blocked the strait of hormuz"]),
    ("blockade", 4, ["naval blockade", "imposed a blockade", "blockade of"]),
    ("war_outbreak", 4, ["war breaks out", "war has broken out", "full-scale war begins"]),
    ("military_coup", 4, ["military coup", "coup attempt", "seized power"]),
]

# Language that commonly signals a forecast, threat, denial, or unverified claim.
CAUTION_TERMS = [
    "could", "may", "might", "would", "if", "warns", "warning", "threatens",
    "threat", "plans to", "prepares to", "preparing to", "expected to", "unlikely",
    "denies", "denied", "not confirmed", "unconfirmed", "false claim", "rumour", "rumor",
]

app = FastAPI(title="GSA Critical Events API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


def utcnow():
    return datetime.now(timezone.utc)


def db():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS articles (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT, source TEXT NOT NULL,
        domain TEXT NOT NULL, url TEXT NOT NULL, category TEXT NOT NULL,
        level INTEGER NOT NULL, published TEXT, first_seen TEXT NOT NULL,
        normalized TEXT NOT NULL
    )""")
    conn.commit()
    return conn


def classify(title, summary):
    title_text = re.sub(r"\s+", " ", title).strip().lower()
    text = re.sub(r"\s+", " ", f"{title} {summary}").strip().lower()

    # Caution markers are checked in the headline only.
    headline_caution = [
        "could", "might", "would", "if", "warns", "warning",
        "threatens", "threat", "plans to", "prepares to",
        "preparing to", "expected to", "unlikely",
        "denies", "denied", "not confirmed", "unconfirmed",
        "false claim", "rumour", "rumor"
    ]
    if any(re.search(r"\b" + re.escape(term) + r"\b", title_text)
           for term in headline_caution):
        return None

    for category, level, phrases in RULES:
        if any(phrase in text for phrase in phrases):
            return category, level
    return None


def normalized_title(title):
    words = re.findall(r"[a-z]{3,}", title.lower())
    stop = {"the", "and", "for", "with", "from", "after", "over", "into", "amid", "says", "said", "that"}
    return " ".join(w for w in words if w not in stop)


def source_domain(url):
    host = (urlparse(url).hostname or "unknown").lower()
    return host[4:] if host.startswith("www.") else host


def ingest():
    now = utcnow().isoformat()
    added = 0
    checked = 0
    failed = []
    conn = db()
    for source, feed_url in FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            if getattr(feed, "bozo", False) and not feed.entries:
                raise RuntimeError(str(getattr(feed, "bozo_exception", "feed parse error")))
            for entry in feed.entries[:50]:
                checked += 1
                title = (getattr(entry, "title", "") or "").strip()
                summary = re.sub(r"<[^>]+>", " ", getattr(entry, "summary", "") or "")
                summary = re.sub(r"\s+", " ", summary).strip()
                url = (getattr(entry, "link", "") or "").strip()
                published = getattr(entry, "published", "") or getattr(entry, "updated", "") or ""
                if not title or not url:
                    continue
                result = classify(title, summary)
                if not result:
                    continue
                category, level = result
                article_id = hashlib.sha256(url.encode("utf-8")).hexdigest()
                cur = conn.execute(
                    "INSERT OR IGNORE INTO articles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (article_id, title, summary[:2500], source, source_domain(url), url,
                     category, level, published, now, normalized_title(title))
                )
                added += cur.rowcount
        except Exception as exc:
            log.exception("Feed failed: %s", source)
            failed.append({"source": source, "error": str(exc)[:300]})
    conn.commit()
    conn.close()
    return {"new_articles": added, "articles_checked": checked, "failed_feeds": failed, "checked_at": now}


def build_event_groups(rows):
    """Conservative heuristic grouping; grouping is not verification."""
    groups = []
    cutoff = utcnow() - timedelta(hours=72)

    for row in rows:
        try:
            seen = datetime.fromisoformat(
                row["first_seen"].replace("Z", "+00:00")
            )
            if seen.tzinfo is None:
                seen = seen.replace(tzinfo=timezone.utc)
        except Exception:
            seen = utcnow()

        if seen < cutoff:
            continue

        best = None
        best_score = 0

        for group in groups:
            if group["category"] != row["category"]:
                continue

            matches = [
                article for article in group["articles"]
                if same_event(row["title"], article["title"])
            ]

            if matches and len(matches) > best_score:
                best = group
                best_score = len(matches)

        if best is not None:
            best["articles"].append(dict(row))
        else:
            groups.append({
                "category": row["category"],
                "representative": row["normalized"],
                "articles": [dict(row)]
            })

    output = []
    for group in groups:
        articles = group["articles"]
        domains = sorted({a["domain"] for a in articles})
        articles.sort(
            key=lambda a: (a["level"], a["first_seen"]),
            reverse=True
        )
        lead = articles[0]

        output.append({
            "id": hashlib.sha256(
                (group["category"] + "|" + group["representative"]).encode()
            ).hexdigest()[:20],
            "title": lead["title"],
            "summary": lead["summary"],
            "source": ", ".join(sorted({a["source"] for a in articles})),
            "url": lead["url"],
            "level": max(a["level"] for a in articles),
            "published": lead["published"],
            "category": group["category"],
            "source_count": len(domains),
            "sources": sorted({a["source"] for a in articles}),
            "verification_status": (
                "MULTI_SOURCE_REPORTING_NOT_VERIFIED"
                if len(domains) >= 2 else "SINGLE_SOURCE_UNCONFIRMED"
            ),
            "verification_note": (
                "Heuristic grouping only. Different publisher domains "
                "do not prove independent confirmation."
            ),
        })

    output.sort(
        key=lambda e: (e["level"], e["source_count"]),
        reverse=True
    )
    return output


@app.get("/")
def root():
    return {"service": "GSA API", "version": "0.2.0", "status": "ok", "docs": "/docs", "warning": "Experimental triage; not an emergency warning service."}


@app.get("/health")
def health():
    return {"status": "ok", "service": "GSA API", "version": "0.2.0", "utc": utcnow().isoformat()}


@app.get("/sources")
def sources():
    return {"sources": [{"name": name, "feed": url, "domain": source_domain(url)} for name, url in FEEDS]}


@app.post("/refresh")
def refresh():
    return ingest()


@app.get("/events")
def events(min_level: int = Query(4, ge=4, le=5), limit: int = Query(50, ge=1, le=200)):
    ingest_result = ingest() if POLL_ON_REQUEST else None
    conn = db()
    rows = conn.execute(
        "SELECT * FROM articles WHERE level >= ? ORDER BY first_seen DESC LIMIT 500",
        (min_level,)
    ).fetchall()
    conn.close()
    grouped = build_event_groups(rows)
    result = [event for event in grouped if event["level"] >= min_level][:limit]
    return {
        "events": result,
        "count": len(result),
        "ingestion": ingest_result,
        "warning": "Experimental RSS keyword triage. Similar headlines are grouped heuristically; source count does not prove independent verification. Do not rely on GSA for emergency decisions.",
    }


@app.get("/diagnostics")
def diagnostics():
    conn = db()
    count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    by_source = conn.execute("SELECT source, COUNT(*) AS n FROM articles GROUP BY source ORDER BY n DESC").fetchall()
    conn.close()
    return {"stored_candidate_articles": count, "articles_by_source": [dict(r) for r in by_source], "poll_on_request": POLL_ON_REQUEST, "classification": "keyword rules; English-language feeds", "verification": "heuristic grouping only; no independent fact-checking"}
