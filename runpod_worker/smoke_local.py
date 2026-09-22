from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from wan_runner import WanJob, WanRunner


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python runpod_worker/smoke_local.py <source-video> <reference-image>")
        return 2

    os.environ.setdefault("WAN_MOCK", "1")
    out_dir = Path(tempfile.mkdtemp(prefix="animatex-worker-smoke-"))
    output = out_dir / "output.mp4"
    result = WanRunner().run(
        WanJob(
            id="smoke",
            source_path=Path(sys.argv[1]),
            reference_path=Path(sys.argv[2]),
            mode="pose_retarget",
            profile="TikTok Standard",
            processing_mode="single_window",
            window_count=1,
        ),
        output,
    )
    print(json.dumps({"output": str(output), "size": output.stat().st_size, **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

