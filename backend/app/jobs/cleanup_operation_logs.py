from __future__ import annotations

import argparse
import json

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.operation_log_retention import cleanup_operation_logs


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean up expired operation logs in batches.")
    parser.add_argument("--dry-run", action="store_true", help="Only count expired rows, do not delete them.")
    parser.add_argument(
        "--admin-retention-days",
        type=int,
        default=settings.admin_operation_log_retention_days,
        help="Retention days for admin operation logs. <= 0 disables cleanup for this scope.",
    )
    parser.add_argument(
        "--user-retention-days",
        type=int,
        default=settings.user_operation_log_retention_days,
        help="Retention days for user operation logs. <= 0 disables cleanup for this scope.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=settings.operation_log_cleanup_batch_size,
        help="Delete rows in small batches to reduce long locks.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = cleanup_operation_logs(
            db,
            admin_retention_days=args.admin_retention_days,
            user_retention_days=args.user_retention_days,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
    finally:
        db.close()

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
