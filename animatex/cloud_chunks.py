from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .batch import ManifestJob, duration_bucket
from .chunking import chunk_windows, concat_videos, extract_video_chunk, trim_chunk_start
from .config import AppConfig
from .db import JobStore, utc_now
from .profiles import get_profile
from .r2 import R2Settings, R2Uploader
from .runpod_client import RunPodServerlessClient
from . import states


WAN_CLIP_LEN = 77


def stage_chunked_batch_to_r2(config: AppConfig, store: JobStore) -> tuple[str | None, Path | None, str | None]:
    jobs = store.queued_jobs()
    if not jobs:
        return None, None, None

    manifest_jobs = [_manifest_job_from_row(row) for row in jobs]
    config.manifests_dir.mkdir(parents=True, exist_ok=True)
    placeholder = config.manifests_dir / "pending-chunks.json"
    batch_id = store.create_batch([job.id for job in manifest_jobs], placeholder)
    coordinator_path = config.manifests_dir / f"{batch_id}.chunks.json"

    uploader = R2Uploader(R2Settings.from_env())
    chunk_root = config.data_dir / "chunks" / batch_id
    runs: list[dict[str, Any]] = []

    for job in sorted(manifest_jobs, key=lambda item: (item.group_key, item.id)):
        source = Path(job.source_path)
        reference = Path(job.reference_path)
        reference_key = f"inputs/{batch_id}/{job.id}/{reference.name}"
        reference_uri = uploader.upload_file(reference, reference_key)
        windows = _windows_for_job(job)

        for window in windows:
            chunk_id = f"{job.id}__chunk_{window.index:03d}"
            chunk_name = f"{source.stem}.chunk_{window.index:03d}.mp4"
            chunk_path = chunk_root / job.id / chunk_name
            extract_video_chunk(source, chunk_path, window, fps=job.target_fps)
            source_key = f"inputs/{batch_id}/{job.id}/chunks/{chunk_name}"
            source_uri = uploader.upload_file(chunk_path, source_key, "video/mp4")
            item = {
                **asdict(job),
                "id": chunk_id,
                "parent_job_id": job.id,
                "source_name": chunk_name,
                "reference_name": reference.name,
                "source_uri": source_uri,
                "reference_uri": reference_uri,
                "chunk": asdict(window),
                "chunk_count": len(windows),
                "is_chunk": True,
            }
            manifest = {"batch_id": batch_id, "jobs": [item]}
            manifest_key = f"manifests/{batch_id}/chunks/{chunk_id}.json"
            manifest_uri = uploader.upload_json(manifest, manifest_key)
            runs.append(
                {
                    "chunk_id": chunk_id,
                    "parent_job_id": job.id,
                    "chunk_index": window.index,
                    "chunk_count": len(windows),
                    "manifest_uri": manifest_uri,
                    "status": "STAGED",
                    "runpod_job_id": None,
                    "output_uri": None,
                    "error": None,
                }
            )

    coordinator = {
        "batch_id": batch_id,
        "mode": "parallel_chunks",
        "clip_len": WAN_CLIP_LEN,
        "jobs": [asdict(job) for job in manifest_jobs],
        "runs": runs,
    }
    _write_json(coordinator_path, coordinator)
    coordinator_uri = uploader.upload_json(coordinator, f"manifests/{batch_id}.chunks.json")
    store.mark_batch_staged(batch_id, coordinator_uri)
    with store.connect() as conn:
        conn.execute("UPDATE batches SET manifest_path = ? WHERE id = ?", (str(coordinator_path), batch_id))
    return batch_id, coordinator_path, coordinator_uri


def submit_chunked_batch(coordinator_path: Path, client: RunPodServerlessClient) -> dict[str, Any]:
    coordinator = _read_json(coordinator_path)
    batch_id = coordinator["batch_id"]
    for run in coordinator["runs"]:
        if run.get("runpod_job_id"):
            continue
        result = client.submit(batch_id=batch_id, manifest_url=run["manifest_uri"])
        run["runpod_job_id"] = result.get("id") or result.get("jobId") or result.get("job_id")
        run["status"] = result.get("status", "SUBMITTED")
    _write_json(coordinator_path, coordinator)
    return coordinator


def refresh_chunked_status(coordinator_path: Path, client: RunPodServerlessClient) -> dict[str, Any]:
    coordinator = _read_json(coordinator_path)
    for run in coordinator["runs"]:
        runpod_job_id = run.get("runpod_job_id")
        if not runpod_job_id or run.get("status") == "COMPLETED":
            continue
        status = client.status(runpod_job_id)
        run["remote_status"] = status.get("status")
        if status.get("status") == "COMPLETED":
            result = (status.get("output", {}).get("results") or [{}])[0]
            run["status"] = result.get("status", "COMPLETED")
            run["output_uri"] = result.get("output_uri")
            run["error"] = result.get("error")
        elif status.get("status") in {"FAILED", "CANCELLED", "TIMED_OUT"}:
            run["status"] = status.get("status")
            run["error"] = json.dumps(status, default=str)
        else:
            run["status"] = status.get("status", "IN_PROGRESS")
    _write_json(coordinator_path, coordinator)
    return coordinator


def stitch_completed_chunks(config: AppConfig, store: JobStore, coordinator_path: Path) -> dict[str, str]:
    coordinator = _read_json(coordinator_path)
    settings = R2Settings.from_env()
    uploader = R2Uploader(settings)
    outputs: dict[str, str] = {}

    for job in coordinator["jobs"]:
        parent_id = job["id"]
        runs = sorted(
            [run for run in coordinator["runs"] if run["parent_job_id"] == parent_id],
            key=lambda item: item["chunk_index"],
        )
        if not runs:
            continue
        incomplete = [run for run in runs if run.get("status") != "COMPLETED" or not run.get("output_uri")]
        if incomplete:
            raise RuntimeError(f"Job {parent_id} still has {len(incomplete)} incomplete chunks")

        local_dir = config.data_dir / "chunks" / coordinator["batch_id"] / parent_id / "outputs"
        stitched_parts: list[Path] = []
        overlap_seconds = float(job["overlap_frames"]) / float(job["target_fps"])
        for run in runs:
            raw_part = local_dir / f"{run['chunk_index']:03d}.raw.mp4"
            stitched_part = local_dir / f"{run['chunk_index']:03d}.mp4"
            _download_r2(settings, run["output_uri"], raw_part)
            trim_chunk_start(
                raw_part,
                stitched_part,
                trim_seconds=0.0 if run["chunk_index"] == 0 else overlap_seconds,
            )
            stitched_parts.append(stitched_part)

        final_path = local_dir / f"{parent_id}.stitched.mp4"
        concat_videos(stitched_parts, final_path)
        output_key = f"outputs/{coordinator['batch_id']}/{parent_id}.stitched.mp4"
        output_uri = uploader.upload_file(final_path, output_key, "video/mp4")
        outputs[parent_id] = output_uri
        with store.connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?, output_path = ?
                WHERE id = ?
                """,
                (states.COMPLETED, utc_now(), output_uri, parent_id),
            )
            conn.execute(
                """
                INSERT INTO job_events (job_id, ts, status, message, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    parent_id,
                    utc_now(),
                    states.COMPLETED,
                    "Parallel chunks stitched and uploaded to R2.",
                    json.dumps({"output_uri": output_uri}),
                ),
            )
    return outputs


def _manifest_job_from_row(row: Any) -> ManifestJob:
    profile = get_profile(row["profile"])
    group_key = "|".join(
        [
            row["character"].strip().lower(),
            row["mode"],
            row["reference_hash"][:16],
            row["profile"],
            profile.generation_size,
            row["processing_mode"],
            str(row["window_count"]),
            duration_bucket(float(row["duration_seconds"])),
        ]
    )
    return ManifestJob(
        id=row["id"],
        character=row["character"],
        mode=row["mode"],
        source_path=row["source_path"],
        reference_path=row["reference_path"],
        source_hash=row["source_hash"],
        reference_hash=row["reference_hash"],
        profile=row["profile"],
        generation_size=profile.generation_size,
        final_size=profile.final_size,
        duration_seconds=float(row["duration_seconds"]),
        processing_mode=row["processing_mode"],
        target_fps=int(row["target_fps"]),
        estimated_frames=int(row["estimated_frames"]),
        window_count=int(row["window_count"]),
        overlap_frames=int(row["overlap_frames"]),
        first_frame_strategy=row["first_frame_strategy"],
        group_key=group_key,
    )


def _windows_for_job(job: ManifestJob):
    clip_len = int(job.estimated_frames) if int(job.window_count) <= 1 else WAN_CLIP_LEN
    return chunk_windows(
        estimated_frames=int(job.estimated_frames),
        fps=int(job.target_fps),
        clip_len=clip_len,
        overlap_frames=int(job.overlap_frames),
    )


def _download_r2(settings: R2Settings, uri: str, dest: Path) -> None:
    from urllib.parse import urlparse

    import boto3

    parsed = urlparse(uri)
    if parsed.scheme != "r2":
        raise ValueError(f"Expected r2:// URI, got {uri}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    client = boto3.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        region_name="auto",
    )
    client.download_file(parsed.netloc, parsed.path.lstrip("/"), str(dest))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
