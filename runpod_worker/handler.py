from __future__ import annotations

import json
import tempfile
import traceback
from pathlib import Path

import runpod

from storage_r2 import R2Config, R2Store
from wan_runner import WanJob, WanRunner


def handler(event: dict) -> dict:
    payload = event.get("input", event)
    manifest_url = payload["manifest_url"]
    batch_id = payload.get("batch_id", "batch")
    work_dir = Path(tempfile.mkdtemp(prefix=f"animatex-{batch_id}-"))

    store = R2Store(R2Config.from_env())
    manifest_path = store.download(manifest_url, work_dir / "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runner = WanRunner()

    results = []
    for item in manifest["jobs"]:
        job_dir = work_dir / item["id"]
        source_path = store.download(item["source_uri"], job_dir / "input" / Path(item["source_name"]).name)
        reference_path = store.download(item["reference_uri"], job_dir / "input" / Path(item["reference_name"]).name)
        output_path = job_dir / "output" / f"{item['id']}.mp4"

        try:
            run_result = runner.run(
                WanJob(
                    id=item["id"],
                    source_path=source_path,
                    reference_path=reference_path,
                    mode=item["mode"],
                    profile=item["profile"],
                    processing_mode=item["processing_mode"],
                    window_count=int(item["window_count"]),
                ),
                output_path,
            )
            output_key = f"outputs/{batch_id}/{item['id']}.mp4"
            output_uri = store.upload(output_path, output_key, "video/mp4")
            results.append(
                {
                    "id": item["id"],
                    "status": "COMPLETED",
                    "output_uri": output_uri,
                    **run_result,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "id": item["id"],
                    "status": "FAILED",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )

    return {"batch_id": batch_id, "results": results}


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})

