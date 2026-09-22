from __future__ import annotations

import json
import sys
from pathlib import Path

from handler import handler


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python runpod_worker/local_test.py runpod_worker/test_input.json")
        return 2
    event = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(handler(event), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

