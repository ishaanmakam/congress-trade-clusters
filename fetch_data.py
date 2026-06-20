"""
fetch_data.py
Pulls congressional stock trading disclosures from the best available source.

Tries, in order:
  1. House Stock Watcher live data (S3-hosted, updated daily from House Clerk filings)
  2. Senate Stock Watcher live data (S3-hosted, updated daily from Senate eFD filings)
  3. Falls back to a local cached copy if both are unreachable (e.g. blocked,
     rate-limited, or you're offline)

These two projects scrape the *official* government disclosure sources
(efdsearch.senate.gov and disclosures-clerk.house.gov) and republish them as
clean JSON. That's the legal, ToS-clean path — unlike Capitol Trades, which
disallows bots in robots.txt.

If both live sources ever go dark permanently, the fallback is to scrape
efdsearch.senate.gov and disclosures-clerk.house.gov directly. That's more
work (PDF parsing for older filings) but is the ground-truth source these
projects themselves pull from.

Usage:
    python fetch_data.py            # fetches fresh data, caches it locally
    python fetch_data.py --offline  # uses whatever is in cache/ already
"""

import json
import sys
import os
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

SOURCES = {
    "house": {
        "url": "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json",
        "cache_file": os.path.join(CACHE_DIR, "house_transactions.json"),
    },
    "senate": {
        "url": "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json",
        "cache_file": os.path.join(CACHE_DIR, "senate_transactions.json"),
    },
}

HEADERS = {
    # A normal browser UA avoids some basic bot-detection blocks.
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
}


def fetch_live(chamber: str) -> list | None:
    src = SOURCES[chamber]
    req = Request(src["url"], headers=HEADERS)
    try:
        with urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        print(f"[{chamber}] fetched {len(data)} records live from {src['url']}")
        with open(src["cache_file"], "w") as f:
            json.dump(data, f)
        return data
    except (URLError, HTTPError) as e:
        print(f"[{chamber}] live fetch failed ({e}). Will try cache.")
        return None
    except Exception as e:
        print(f"[{chamber}] unexpected error during live fetch: {e}")
        return None


def load_cache(chamber: str) -> list | None:
    src = SOURCES[chamber]
    if os.path.exists(src["cache_file"]):
        with open(src["cache_file"]) as f:
            data = json.load(f)
        print(f"[{chamber}] loaded {len(data)} records from local cache")
        return data
    print(f"[{chamber}] no cache available either.")
    return None


def get_chamber_data(chamber: str, offline: bool = False) -> list:
    if not offline:
        data = fetch_live(chamber)
        if data:
            return data
    data = load_cache(chamber)
    if data:
        return data
    raise RuntimeError(
        f"Could not get {chamber} data live or from cache. "
        f"If this keeps happening, the fallback is scraping "
        f"efdsearch.senate.gov / disclosures-clerk.house.gov directly."
    )


def normalize(records: list, chamber: str) -> list:
    """Normalize House and Senate records to a common schema."""
    out = []
    for r in records:
        ticker = (r.get("ticker") or "").strip()
        if not ticker or ticker in ("--", "N/A"):
            continue
        # House uses 'representative', Senate uses 'senator'
        politician = r.get("representative") or r.get("senator") or "Unknown"
        politician = politician.strip().rstrip(",").strip()
        out.append({
            "politician": politician,
            "chamber": chamber,
            "ticker": ticker.upper(),
            "asset": r.get("asset_description", ""),
            "transaction_date": r.get("transaction_date", ""),
            "disclosure_date": r.get("disclosure_date") or r.get("date_recieved", ""),
            "type": r.get("type", ""),
            "amount": r.get("amount", ""),
            "owner": r.get("owner", ""),
        })
    return out


def main():
    offline = "--offline" in sys.argv
    all_records = []
    for chamber in ("house", "senate"):
        try:
            raw = get_chamber_data(chamber, offline=offline)
            all_records.extend(normalize(raw, chamber))
        except RuntimeError as e:
            print(f"WARNING: {e}")

    out_path = os.path.join(os.path.dirname(__file__), "all_trades.json")
    with open(out_path, "w") as f:
        json.dump(all_records, f, indent=2)
    print(f"\nWrote {len(all_records)} normalized records to {out_path}")


if __name__ == "__main__":
    main()
