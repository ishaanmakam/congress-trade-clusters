"""
analyze_clusters.py
Finds "clusters": cases where multiple different politicians traded the same
stock within a tight time window. That's the core signal for "is everyone
suddenly piling into/out of the same name at the same time" — which is
either a coincidence, a reaction to the same public news, or worth a closer
look.

For each ticker, we look at all trades sorted by date and find groups where
N+ distinct politicians transacted within WINDOW_DAYS of each other.
Clusters are scored higher when:
  - more distinct politicians are involved
  - the date spread is tighter
  - trades lean the same direction (all buying or all selling, vs mixed)
    same-direction clustering is the more interesting signal — mixed
    buy/sell could just mean people have different existing positions.

Usage:
    python analyze_clusters.py [--window-days 14] [--min-politicians 3]
"""

import json
import argparse
from datetime import datetime
from collections import defaultdict

PURCHASE_TYPES = {"purchase", "purchase (partial)"}
SALE_TYPES = {"sale (full)", "sale (partial)", "sale"}


def parse_date(s: str):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    return None


def direction(tx_type: str) -> str:
    t = (tx_type or "").strip().lower()
    if t in PURCHASE_TYPES:
        return "buy"
    if t in SALE_TYPES:
        return "sell"
    return "other"


def find_clusters(trades, window_days=14, min_politicians=3):
    by_ticker = defaultdict(list)
    for t in trades:
        d = parse_date(t["transaction_date"])
        if d is None:
            continue
        t = dict(t)
        t["_date"] = d
        t["_direction"] = direction(t["type"])
        by_ticker[t["ticker"]].append(t)

    clusters = []
    for ticker, txs in by_ticker.items():
        txs.sort(key=lambda x: x["_date"])
        n = len(txs)
        i = 0
        while i < n:
            window_start = txs[i]["_date"]
            j = i
            group = []
            while j < n and (txs[j]["_date"] - window_start).days <= window_days:
                group.append(txs[j])
                j += 1

            distinct_pols = {g["politician"] for g in group}
            if len(distinct_pols) >= min_politicians:
                directions = [g["_direction"] for g in group if g["_direction"] != "other"]
                buy_count = directions.count("buy")
                sell_count = directions.count("sell")
                same_direction = (buy_count == 0 or sell_count == 0) and len(directions) > 0

                dates = [g["_date"] for g in group]
                spread_days = (max(dates) - min(dates)).days

                clusters.append({
                    "ticker": ticker,
                    "asset": group[0]["asset"],
                    "num_politicians": len(distinct_pols),
                    "politicians": sorted(distinct_pols),
                    "num_trades": len(group),
                    "buy_count": buy_count,
                    "sell_count": sell_count,
                    "same_direction": same_direction,
                    "window_start": min(dates).strftime("%Y-%m-%d"),
                    "window_end": max(dates).strftime("%Y-%m-%d"),
                    "spread_days": spread_days,
                    "trades": [
                        {
                            "politician": g["politician"],
                            "chamber": g["chamber"],
                            "date": g["_date"].strftime("%Y-%m-%d"),
                            "direction": g["_direction"],
                            "amount": g["amount"],
                            "owner": g["owner"],
                        }
                        for g in group
                    ],
                })
            # slide window forward past this group's start to avoid
            # re-finding near-identical overlapping clusters
            i = j if j > i else i + 1

    # score: prioritize more politicians, then tighter spread, then same-direction
    def score(c):
        return (c["num_politicians"], c["same_direction"], -c["spread_days"])

    clusters.sort(key=score, reverse=True)

    # de-duplicate near-identical overlapping clusters per ticker, keep best
    seen_tickers = set()
    deduped = []
    for c in clusters:
        key = (c["ticker"], c["window_start"])
        if key in seen_tickers:
            continue
        seen_tickers.add(key)
        deduped.append(c)

    return deduped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-days", type=int, default=14)
    ap.add_argument("--min-politicians", type=int, default=3)
    ap.add_argument("--input", default="all_trades.json")
    ap.add_argument("--output", default="clusters.json")
    args = ap.parse_args()

    with open(args.input) as f:
        trades = json.load(f)

    clusters = find_clusters(
        trades,
        window_days=args.window_days,
        min_politicians=args.min_politicians,
    )

    with open(args.output, "w") as f:
        json.dump(clusters, f, indent=2)

    print(f"Analyzed {len(trades)} trades")
    print(f"Found {len(clusters)} clusters (>= {args.min_politicians} politicians, "
          f"{args.window_days}-day window)")
    print(f"Top 5 clusters by score:")
    for c in clusters[:5]:
        print(f"  {c['ticker']:6s} | {c['num_politicians']} politicians | "
              f"{c['window_start']} to {c['window_end']} ({c['spread_days']}d) | "
              f"{'SAME DIRECTION' if c['same_direction'] else 'mixed'}")


if __name__ == "__main__":
    main()
