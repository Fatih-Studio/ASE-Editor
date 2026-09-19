from __future__ import annotations

import argparse
from pathlib import Path

from .sector_database import build_sector_database


ROOT = Path(__file__).resolve().parents[1]
DATABASES = {
    "indonesia": {
        "name": "Indonesia",
        "source": ROOT / "WIII_Demo.sct",
        "output": ROOT / "data" / "sector" / "indonesia.sqlite3",
    }
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build packaged sector databases.")
    parser.add_argument("database", choices=sorted(DATABASES))
    parser.add_argument("--source", type=Path, help="Override source .sct path")
    parser.add_argument("--output", type=Path, help="Override output SQLite path")
    args = parser.parse_args()

    config = DATABASES[args.database]
    source = args.source or config["source"]
    output = args.output or config["output"]
    data = build_sector_database(source, output, str(config["name"]))
    print(
        f"Built {config['name']} database: {output} "
        f"({len(data.points)} points, {len(data.lines)} lines, {len(data.regions)} regions)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
