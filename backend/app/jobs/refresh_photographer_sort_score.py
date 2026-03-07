from __future__ import annotations

import argparse
import json

from app.db.session import SessionLocal
from app.services.photographer_ranking import recalculate_photographer_sort_scores


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh photographer sort_score.")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=30,
        help="Analytics lookback window in days (default: 30).",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = recalculate_photographer_sort_scores(
            db,
            lookback_days=args.lookback_days,
        )
    finally:
        db.close()

    print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
