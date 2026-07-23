#!/usr/bin/env python3
"""Surface durable feature checkpoints without scheduling or resuming work."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    event = sys.argv[1] if len(sys.argv) > 1 else "session-start"
    root = Path(__file__).resolve().parents[2]
    print(f"Codex {event}: surfacing durable checkpoint context for the parent.")
    for checkpoint in sorted(root.glob("work/*/logs/checkpoint.yml")):
        print(checkpoint.relative_to(root).as_posix())
    print("The parent must validate approvals and live runtime capability before any resume decision.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
