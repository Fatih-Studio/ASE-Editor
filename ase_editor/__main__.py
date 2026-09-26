from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    # Use the project file even when launched from a different working directory.
    # Explicit process/user environment variables retain precedence.
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False, encoding="utf-8-sig")
    try:
        from .ui import run
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print(
                "PySide6 is not installed. Install dependencies with:\n"
                "  python -m pip install -r requirements.txt\n"
            )
            return 1
        raise
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
