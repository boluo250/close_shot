#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _resolve_backend_dir() -> Path:
    explicit = (os.environ.get("BACKEND_DIR") or "").strip()
    if explicit:
        return Path(explicit).resolve()
    return Path(__file__).resolve().parents[1]


BACKEND_DIR = _resolve_backend_dir()
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.storage import restore_soft_deleted_object  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restore an object previously archived in STORAGE_SOFT_DELETE_PREFIX.")
    parser.add_argument("archived_object_key", help="Archived object key under the recycle bin prefix.")
    parser.add_argument(
        "--restore-to-key",
        dest="restore_to_key",
        help="Optional target object key. Defaults to the original key inferred from the archive path.",
    )
    parser.add_argument(
        "--purge-archive",
        action="store_true",
        help="Delete the archived copy after the restore succeeds.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    restored_key = restore_soft_deleted_object(
        args.archived_object_key,
        restore_to_key=args.restore_to_key,
        purge_archive=args.purge_archive,
    )
    print(restored_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
