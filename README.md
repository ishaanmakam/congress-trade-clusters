# Congress Trade Cluster Detector

Finds tickers where multiple members of Congress traded close together in time —
the "is everyone suddenly piling into the same stock" signal.

## Files

- `fetch_data.py` — pulls House + Senate disclosure data, normalizes it, caches it locally
- `analyze_clusters.py` — runs the cluster-detection algorithm, outputs `clusters.json`
- `cache/` — local cache so the script still works if the live source is down/blocked
- `congress_trade_clusters_dashboard.html` — the dashboard (also shown inline in chat).
  Click "Load clusters.json" inside it to swap in fresh data after a re-run.

## Quick start

```bash
pip install --break-system-packages requests   # only needed if you swap urllib for requests later
python fetch_data.py
python analyze_clusters.py --window-days 14 --min-politicians 3
```

Then open the dashboard and load the new `clusters.json`.

## The honest data-source situation

I tested three options before landing on this setup:

1. **Capitol Trades** — cleanest structured data, but their `robots.txt` explicitly
   disallows automated access. Several open-source projects scrape it anyway by hitting
   their internal `bff.capitoltrades.com` API, but I didn't want to build you something
   that starts off violating a site's stated terms.
2. **Quiver Quantitative** — has a proper, documented API, but it now requires a paid
   plan starting at $30/month for API access (free tier is dashboard-only).
3. **House Stock Watcher / Senate Stock Watcher** — what `fetch_data.py` uses. These
   scrape the *official* government sources (efdsearch.senate.gov and the House Clerk's
   disclosure site) and republish as clean JSON, updated daily, no ToS issue. This is
   what the script tries first.

When I tested the live S3-hosted JSON endpoints from this sandbox, AWS's bot detection
blocked the request — that's common for datacenter/cloud IPs, not residential ones, so
it will most likely work fine running from your own machine. If it doesn't: that's what
the cache fallback and the comments in `fetch_data.py` are for. The script degrades
gracefully — try live, fall back to cache, and as a last resort the comments point you
to scraping the official Senate/House sites directly (more work, since older filings are
scanned PDFs, but it's the ground-truth source everything else is built on).

I validated `analyze_clusters.py` against ~8,300 real historical Senate transactions
(2012-2020) — that's what's baked into the dashboard you're looking at right now. It
correctly found real clusters, like 5 different senators all trading AAPL within a
14-day window in August 2020. Once you run `fetch_data.py` fresh, you'll get current
2026 data instead.

## Tuning the algorithm

- `--window-days` — how many days apart counts as "close together." 14 is a reasonable
  start; tighten to 5-7 if you want only the most suspicious-looking clusters.
- `--min-politicians` — how many distinct politicians need to be involved. 3 is a decent
  floor; raise it to cut noise once you have live data with more volume.

## Where to take this next

- Enrich with party affiliation and committee assignments (theunitedstates.io publishes
  this as open JSON) — lets you flag clusters where committee members trade stocks tied
  to bills they oversee.
- Add a return-vs-S&P calculation: pull each ticker's price N days after the disclosed
  trade date (yfinance works well for this) to see who actually got lucky.
- Schedule `fetch_data.py` to run daily (cron or a GitHub Action) so the dashboard stays
  current without manual reruns.
