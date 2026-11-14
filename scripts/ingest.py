#!/usr/bin/env python3
"""scripts/ingest.py

CLI Driver for financial data ingestion.
Executes Drop 1, then Drop 2 against the configured PostgreSQL database.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.ingest import DataIngestor, ingest_all

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest financial data releases")
    parser.add_argument("--drop", choices=["1", "2", "all"], default="all", help="Which release to ingest")
    parser.add_argument("--test", action="store_true", help="Ingest into test database")
    args = parser.parse_args()

    ingestor = DataIngestor(is_test=args.test)
    if args.drop == "1":
        ingestor.ingest_release("drop1")
    elif args.drop == "2":
        ingestor.ingest_release("drop2")
    else:
        ingest_all(is_test=args.test)

