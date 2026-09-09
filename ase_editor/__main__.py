from __future__ import annotations

import sys


def main() -> int:
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
